"""The HoH1 import fingerprint (issue #123): build.py writes mods/hwplib/hoh1/hwp_import_stamp.sval
from every module's `local` content, HWP::HoH1 reads it and the host plays HoH1 floors and pets
only when every player's matches its own. Two imports of the same files must agree (images by
path only: two PNG encoders need not), a different import must not, and no import means no file."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build  # noqa: E402


def module(root: Path, mid: str, cfg: dict, files: dict[str, bytes | str]) -> dict:
    d = root / mid
    for rel, data in {**files, "info.xml": f"<mod><name>{mid}</name></mod>"}.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            (d / rel).write_bytes(data)
        else:
            (d / rel).write_text(data, encoding="utf-8")
    (d / "module.json").write_text(json.dumps(cfg), encoding="utf-8")
    return build.load_module(d)


def lobby(root: Path, level: str, png: bytes = b"\x89PNG one encoder", extra: dict | None = None) -> list[dict]:
    lib = module(root, "hwplib", {"library": True, "local": ["hoh1/"]}, {"scripts/a.as": "// lib"})
    campaign = module(root, "campaign", {"local": ["hoh1/"]},
                      {"scripts/c.as": "// shipped", "hoh1/levels/battlements_1.lvl": level,
                       "hoh1/tex/wall.png": png, **(extra or {})})
    rider = module(root, "holylocal", {"local": ["players/"], "local_only": True, "beta_into": "hwplib"},
                   {"players/priest.txt": "DLC"})
    return [lib, campaign, rider]


def stamp_text(mods: list[dict]) -> str:
    path = mods[0]["dir"] / build.HOH1_STAMP_REL
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_same_import_same_stamp_images_by_path(tmp_path):
    a = build.write_hoh1_stamp(lobby(tmp_path / "a", "<level/>"))
    b = build.write_hoh1_stamp(lobby(tmp_path / "b", "<level/>", png=b"\x89PNG another encoder"))
    assert a and a == b


def test_text_files_ignore_line_endings(tmp_path):
    # build.py's TEXT_EXTS (.unit, .sval, ...) compare without line endings, as the library stamp does
    a = build.write_hoh1_stamp(lobby(tmp_path / "a", "<level/>", extra={"hoh1/u.unit": b"<unit>\n</unit>\n"}))
    b = build.write_hoh1_stamp(lobby(tmp_path / "b", "<level/>", extra={"hoh1/u.unit": b"<unit>\r\n</unit>\r\n"}))
    assert a == b


def test_different_import_different_stamp(tmp_path):
    base = build.write_hoh1_stamp(lobby(tmp_path / "a", "<level/>"))
    assert build.write_hoh1_stamp(lobby(tmp_path / "b", "<level changed/>")) != base
    # a file the other import lacks (the Battlements floor that hung game night 10.28.26)
    assert build.write_hoh1_stamp(lobby(tmp_path / "c", "<level/>", extra={"hoh1/levels/battlements_2.lvl": "<l/>"})) != base


def test_stamp_file_and_beta_rider_left_out(tmp_path):
    mods = lobby(tmp_path, "<level/>")
    first = build.write_hoh1_stamp(mods)
    text = stamp_text(mods)
    assert f'<string name="stamp">{first}</string>' in text and '<int name="files">2</int>' in text
    # writing it again (the stamp file now on disk, inside hwplib's local hoh1/) changes nothing
    assert build.write_hoh1_stamp(mods) == first and stamp_text(mods) == text
    # the local_only rider is not the HoH1 import
    (mods[2]["dir"] / "players/priest.txt").write_text("other DLC", encoding="utf-8")
    assert build.write_hoh1_stamp(mods) == first


def test_no_import_no_stamp_file(tmp_path):
    lib = module(tmp_path, "hwplib", {"library": True, "local": ["hoh1/"]}, {"scripts/a.as": "// lib"})
    campaign = module(tmp_path, "campaign", {"local": ["hoh1/"]}, {"scripts/c.as": "// shipped"})
    stale = lib["dir"] / build.HOH1_STAMP_REL
    stale.parent.mkdir(parents=True)
    stale.write_text("<dict/>", encoding="utf-8")
    assert build.write_hoh1_stamp([lib, campaign]) == ""
    assert not stale.exists() and not stale.parent.exists()


def test_release_build_never_packs_it(tmp_path):
    mods = lobby(tmp_path, "<level/>")
    build.write_hoh1_stamp(mods)
    release = {e.path for e in build.module_entries(mods[0], True, False)}
    personal = {e.path for e in build.module_entries(mods[0], True, True)}
    assert build.HOH1_STAMP_REL not in release
    assert build.HOH1_STAMP_REL in personal
    # and it is no part of the library stamp, which a release and a personal build share
    assert build.library_stamp(mods) == build.library_stamp(lobby(tmp_path / "other", "<other/>")[:1] + mods[1:])


def test_hwplib_declares_it_local():
    cfg = json.loads((Path(__file__).resolve().parents[1] / "mods/hwplib/module.json").read_text(encoding="utf-8"))
    assert "hoh1/" in cfg.get("local", [])
