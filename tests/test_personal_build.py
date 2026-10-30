"""A personal build (build.py --with-local, what deploy.py modded-prod makes when the player
imported HoH1 content) is told apart from a release build by its content, so tools/workshop.py
never puts one in the upload kit; and deploy.py's default counts every module's imports but
not a local_only beta rider's (2026-10-29: the HoH1 trinket icons never reached the player's
install, because only the campaign import turned --with-local on)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build  # noqa: E402
import hwr_archive as hwr  # noqa: E402


def module(root: Path, mid: str, cfg: dict, files: dict[str, str]) -> dict:
    d = root / mid
    for rel, text in {**files, "info.xml": f"<mod><name>{mid}</name></mod>"}.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")
    (d / "module.json").write_text(json.dumps(cfg), encoding="utf-8")
    return build.load_module(d)


def package(path: Path, mods: list[dict], with_local: bool) -> Path:
    entries = [e for m in mods for e in build.module_entries(m, True, with_local)]
    hwr.Archive("hoh2", hwr.GAMES["hoh2"][1], 0, {"name": "t"}, entries).write(path)
    return path


def test_personal_build_is_recognised(tmp_path):
    trinkets = module(tmp_path, "trinkets", {"local": ["gui/hwp/sheet.txt"]},
                      {"scripts/a.as": "// shipped", "gui/hwp/sheet.txt": "made from HoH1"})
    classes = module(tmp_path, "classes", {"local_overlay": "hoh1art/"},
                     {"players/icons.txt": "placeholder", "hoh1art/players/icons.txt": "HoH1 art"})
    mods = [trinkets, classes]
    local = build.local_entries(mods)
    assert set(local) == {"gui/hwp/sheet.txt", "players/icons.txt"}
    assert build.personal_files(package(tmp_path / "release.bin", mods, False), local) == []
    assert build.personal_files(package(tmp_path / "mine.bin", mods, True), local) == \
        ["gui/hwp/sheet.txt", "players/icons.txt"]


def test_default_counts_imports_not_beta_riders(tmp_path):
    pets = module(tmp_path, "pets", {"local": ["players/pets/hwp/"]}, {"players/pets/hwp/dog.txt": "HoH1 dog"})
    rider = module(tmp_path, "holylocal", {"local": ["players/"], "local_only": True, "beta_into": "hwplib"},
                   {"players/priest.txt": "DLC"})
    assert build.personal_content([pets, rider]) == ["pets/players/pets/hwp/dog.txt"]
    assert build.personal_content([rider]) == []
