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
