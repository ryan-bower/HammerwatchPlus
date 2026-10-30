"""tools/make_hwp_traps.py: the HoH1 trap units, prefabs and set block are current, and every
unit a hwp_traps prefab places is in Traps.as's UNITS (the module's load check) and every
prefab family in its kind table."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import make_hwp_traps  # noqa: E402

MOD = make_hwp_traps.MOD
TRAPS_AS = MOD / "scripts" / "HWP" / "Campaign" / "Traps.as"


def test_generated_files_current():
    assert make_hwp_traps.main(["--check"]) == 0


def trap_prefabs():
    text = make_hwp_traps.DEFS.read_text(encoding="utf-8")
    return re.findall(r'<string name="id">prefabs/hwp/traps/(\w+)\.pfb</string>\s*<string name="theme">hwp_traps</string>', text)


def test_prefab_units_listed():
    src = TRAPS_AS.read_text(encoding="utf-8")
    listed = set(re.findall(r'"(doodads/[^"]+\.unit)"', re.search(r"UNITS = \{(.*?)\};", src, re.S).group(1)))
    placed = set()
    for pid in trap_prefabs():
        pfb = (MOD / "prefabs" / "hwp" / "traps" / f"{pid}.pfb").read_text(encoding="utf-8")
        placed |= set(re.findall(r'<array name="(doodads/[^"]+\.unit)">', pfb))
    assert placed <= listed, sorted(placed - listed)


def test_families_weighted():
    src = TRAPS_AS.read_text(encoding="utf-8")
    groups = re.findall(r'"(\w+)"', re.search(r"GROUPS = \{([^}]*)\}", src).group(1))
    fams = re.findall(r'"(\w+)"', re.search(r"FAMILIES = \{([^}]*)\}", src).group(1))
    body = re.search(r"WEIGHTS = \{(.*?)\};", src, re.S).group(1)
    nums = re.findall(r"-?\d+", re.sub(r"//.*", "", body))
    assert len(nums) == len(groups) * len(fams)
    used = {pid.rsplit("_", 1)[0] for pid in trap_prefabs()}
    assert used == set(fams), (sorted(used - set(fams)), sorted(set(fams) - used))
