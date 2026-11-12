"""Source/data contracts; native stack timing still requires GameLab."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "mods/specs"
SOURCE = (SPECS / "scripts/HWP/Specs/Stormbringer.as").read_text()


def test_duration_and_native_fallback_agree():
    duration = int(re.search(r"const int TAILWIND_MS = (\d+);", SOURCE)[1])
    assert duration == 6000
    document = (SPECS / "players/hwp/specs/stacks_specs.sval").read_text()
    stacks = ET.fromstring("<root>" + document + "</root>").find("array")
    tailwind = next(row for row in stacks if row.findtext("string[@name='id']") == "tailwind")
    assert tailwind.findtext("int[@name='max']") == "5"
    timer = tailwind.find("dict[@name='timer']")
    assert int(timer.findtext("int[@name='time']")) == duration + 100
    assert timer.findtext("int[@name='add-stack']") == "-999"
    for field in ("gain-reset", "add-reset", "sub-reset"):
        assert timer.findtext(f"bool[@name='{field}']") == "true"


def test_every_gain_refreshes_all_script_deadlines_including_at_cap():
    gain = SOURCE.split("void AddTailwind(PlayerBase@ plr)", 1)[1].split("int g_wardC", 1)[0]
    assert "FollowTailwind(plr.GetStacks(def));" in gain
    assert "if (int(g_twExp.length()) > TAILWIND_MAX)" in gain
    assert "plr.AddStacks(plr, def, -1);" in gain
    # Refresh is outside the overflow branch, after the native take/add timer reset.
    assert re.search(
        r"}\s*plr.AddStacks\(plr, def, 1\);\s*"
        r"for \(uint i = 0; i < g_twExp.length\(\); i\+\+\)\s*"
        r"g_twExp\[i\] = g_twNow \+ TAILWIND_MS;",
        gain,
    )


def test_kills_and_catches_share_the_refresh_path():
    kills = SOURCE.split("class HWPSpecsKillTailwind", 1)[1]
    catch = SOURCE.split("class HWPSpecsReturn", 1)[1].split("class HWPSpecsKillTailwind", 1)[0]
    assert "HWP::Specs::AddTailwind(plr);" in kills
    assert "HWP::Specs::AddTailwind(owner);" in catch


def test_player_descriptions_match_duration_and_refresh():
    language = ET.parse(SPECS / "res/language/english/hwp_specs.lang").getroot()
    description = language.findtext("string[@name='hwp.specs.gathering_winds.desc']")
    planner = json.loads((ROOT / "planner/data/skills/ranger-spec4-passive.json").read_text())
    assert "6 seconds" in description
    assert "6s" in planner["summary"]
    for text in (description, planner["summary"]):
        assert "refreshes all stacks, including at max stacks" in text
