"""Package updates (issue #24): every package tells HWP::Builds which update it is, and packages
of other updates call the library by these exact signatures, so they never change."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import build  # noqa: E402

CORE = REPO / "mods" / "hwplib" / "scripts" / "HWP" / "Core"


def test_the_update_is_a_date_and_a_commit():
    assert re.fullmatch(r"\d{4}-\d\d-\d\d [0-9a-f]{7,}\+?|unknown", build.update_id())


def test_every_package_check_reports_its_update_and_keeps_the_old_call():
    check = next(e for e in build.stamp_entries("qol", "0123456789ab", True, "2026-10-29 1a2b3c4")
                 if e.path == "scripts/HWP/Packages/qol.as").blob.decode()
    assert 'HWP::Builds::Package("HWP-qol", "2026-10-29 1a2b3c4", "0123456789ab", HWP::LIB_STAMP);' in check
    # libraries from before update stamps only have Mismatch
    assert 'HWP::Packages::Mismatch("HWP-qol");' in check


def test_the_calls_other_updates_make_keep_their_signatures():
    builds = (CORE / "Builds.as").read_text(encoding="utf-8")
    assert ("void Package(const string &in name, const string &in update, const string &in stamp, "
            "const string &in loadedStamp)") in builds
    assert "void Mismatch(const string &in package)" in (CORE / "Packages.as").read_text(encoding="utf-8")


def _module(root, files, local=()):
    """A module folder for build.load_module: module.json plus the given files."""
    d = root / "mods" / "demo"
    for rel, text in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_bytes(text)
    if not (d / "info.xml").exists():
        (d / "info.xml").write_text("<mod><name>Demo</name></mod>", encoding="utf-8")
    (d / "module.json").write_text('{"id": "demo", "local": %s}' % list(local).__repr__().replace("'", '"'),
                                   encoding="utf-8")
    return build.load_module(d)


def test_the_same_files_from_another_commit_are_the_same_content(tmp_path):
    a = _module(tmp_path / "a", {"scripts/A.as": b"void A() {}\n"})
    b = _module(tmp_path / "b", {"scripts/A.as": b"void A() {}\r\n"})  # git's line endings on another machine
    assert build.package_content([a]) == build.package_content([b])
    assert re.fullmatch(r"[0-9a-f]{12}", build.package_content([a]))


def test_a_changed_shipped_file_is_other_content(tmp_path):
    a = _module(tmp_path / "a", {"scripts/A.as": b"void A() {}\n"})
    b = _module(tmp_path / "b", {"scripts/A.as": b"void A() { return; }\n"})
    assert build.package_content([a]) != build.package_content([b])


def test_local_content_a_release_never_ships_is_left_out(tmp_path):
    # a friend's build from source packs their own HoH1 import; the release never does
    a = _module(tmp_path / "a", {"scripts/A.as": b"x\n"}, local=["hoh1"])
    b = _module(tmp_path / "b", {"scripts/A.as": b"x\n", "hoh1/levels/l.lvl": b"theirs"}, local=["hoh1"])
    assert build.package_content([a]) == build.package_content([b])


def test_builds_compares_the_file_hash_and_hides_it():
    builds = (CORE / "Builds.as").read_text(encoding="utf-8")
    assert 'int at = update.findFirst(" #");' in builds   # Content(): the hash after " #"
    assert "if (Same(m, t))" in builds                     # Differences() goes by Same, not ==
    assert 'parts[1].findFirst("#") == 0' in builds        # Show() never prints the hash as a commit


def test_info_xml_meta_counts(tmp_path):
    a = _module(tmp_path / "a", {"scripts/A.as": b"x\n", "info.xml": b"<mod><name>Demo</name></mod>"})
    b = _module(tmp_path / "b", {"scripts/A.as": b"x\n", "info.xml": b"<mod><name>Demo</name><desc>other</desc></mod>"})
    assert build.package_content([a]) != build.package_content([b])
