"""Source/data contracts; native stack timing still requires GameLab."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "mods/specs"
SOURCE = (SPECS / "scripts/HWP/Specs/Stormbringer.as").read_text()


def _function(signature):
    """Body of a namespace-level function: up to its closing brace at two tabs."""
    return SOURCE.split(signature, 1)[1].split("\n\t\t}\n", 1)[0]


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


def test_refresh_restarts_script_deadlines_and_native_timer():
    refresh = _function("void RefreshTailwind(PlayerBase@ plr, ActorBuffStackDef@ def)")
    assert "g_twExp[i] = g_twNow + TAILWIND_MS;" in refresh
    # The native fallback/HUD timer is set directly, only on a live stack of this def,
    # so a refresh never changes the count or fires stack triggers.
    assert "st.m_def is def && st.m_stacks > 0" in refresh
    assert "st.m_timerTickC = Modifiers::lerp(st.m_defMod.m_timerTime, st.GetIntensity());" in refresh
    assert "AddStacks" not in refresh


def test_every_gain_refreshes_all_stacks_including_at_cap():
    gain = _function("void AddTailwind(PlayerBase@ plr)")
    assert "FollowTailwind(plr.GetStacks(def));" in gain
    assert "if (int(g_twExp.length()) > TAILWIND_MAX)" in gain
    assert "plr.AddStacks(plr, def, -1);" in gain
    # Refresh is outside the overflow branch, after the gain.
    assert re.search(r"}\s*plr\.AddStacks\(plr, def, 1\);\s*RefreshTailwind\(plr, def\);", gain)


def test_every_kill_refreshes_and_every_fifth_adds():
    assert "const int TAILWIND_KILLS = 5;" in SOURCE
    kill = _function("void KillTailwind(PlayerBase@ plr)")
    assert re.search(
        r"g_twKills\+\+;\s*if \(g_twKills % TAILWIND_KILLS == 0\)\s*\{\s*AddTailwind\(plr\);\s*return;\s*\}",
        kill,
    )
    # The other kills keep the count and only refresh what is held (#126).
    rest = kill.split("AddTailwind(plr);", 1)[1]
    assert "AddStacks" not in rest
    assert re.search(r"FollowTailwind\(plr\.GetStacks\(def\)\);\s*RefreshTailwind\(plr, def\);", rest)


def test_kills_and_catches_share_the_refresh_path():
    kills = SOURCE.split("class HWPSpecsKillTailwind", 1)[1]
    catch = SOURCE.split("class HWPSpecsReturn", 1)[1].split("class HWPSpecsKillTailwind", 1)[0]
    assert "HWP::Specs::KillTailwind(plr);" in kills
    assert "g_twKills" not in kills
    assert "HWP::Specs::AddTailwind(owner);" in catch


def test_player_descriptions_match_duration_and_refresh():
    language = ET.parse(SPECS / "res/language/english/hwp_specs.lang").getroot()
    description = language.findtext("string[@name='hwp.specs.gathering_winds.desc']")
    planner = json.loads((ROOT / "planner/data/skills/ranger-spec4-passive.json").read_text())
    assert "6 seconds" in description
    assert "6s" in planner["summary"]
    for text in (description, planner["summary"]):
        assert "Every kill and every Tailwind gained refreshes all stacks, including at max stacks" in text
