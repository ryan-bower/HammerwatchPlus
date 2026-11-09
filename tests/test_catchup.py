"""Pins for mods/catchup (issue #73): the NG+ catch-up experience bonus. Source facts the game
can't check in CI: the threshold formula, the buff def, the setting and the module listings."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/catchup"
SRC = (MOD / "scripts/HWP/CatchUp/CatchUp.as").read_text(encoding="utf-8")
BUFF = MOD / "tweak/hwp/buffs_catchup.sval"
LANG = (MOD / "res/language/english/hwp_catchup.lang").read_text(encoding="utf-8")
VANILLA_PLAYER = ROOT / "gamecode/sdk/hoh2/scripts/Data/Player.as"

# vanilla's Tweak::LevelCap and Tweak::LevelCapNGPAdd (Data/Player.as, build 25932569)
LEVEL_CAP, NGP_ADD = 20, 5


def threshold(ngp: int) -> int:
    """The Python mirror of HWP::CatchUp::Threshold: the cap of NG+ (ngp - 1), 0 at NG+0."""
    if ngp <= 0:
        return 0
    return int(LEVEL_CAP + (ngp - 1) * NGP_ADD + 0.5)


@pytest.mark.parametrize("ngp,expected", [(0, 0), (1, 20), (2, 25), (3, 30), (4, 35)])
def test_threshold_is_the_previous_ngp_cap(ngp, expected):
    # the owner's examples: NG+1 below 20, NG+2 below 25
    assert threshold(ngp) == expected


def test_threshold_source_matches_the_mirror():
    body = SRC[SRC.index("int Threshold(int ngp)"):]
    body = body[:body.index("}\n\n")]
    assert "if (ngp <= 0)" in body and "return 0;" in body
    assert "Tweak::LevelCap + float(ngp - 1) * Tweak::LevelCapNGPAdd + 0.5f" in body


def test_run_ngp_is_the_runs_not_the_characters():
    body = SRC[SRC.index("int RunNgp()"):SRC.index("int Threshold(int ngp)")]
    assert "int(g_ngp + 0.5f)" in body
    assert "rec.ngp" not in SRC


@pytest.mark.skipif(not VANILLA_PLAYER.exists(), reason="gamecode/ not bootstrapped")
def test_vanilla_cap_constants():
    text = VANILLA_PLAYER.read_text(encoding="utf-8", errors="replace")
    assert re.search(r"const int LevelCap = %d;" % LEVEL_CAP, text)
    assert re.search(r"const int LevelCapNGPAdd = %d;" % NGP_ADD, text)


def test_buff_def_gives_half_again_experience():
    root = ET.parse(BUFF).getroot()
    d = root.find("dict[@name='hwp_catchup']")
    assert d is not None
    assert d.find("float[@name='experience-mul']").text == "1.5"
    assert d.find("string[@name='name']").text == ".hwp.catchup.buff"
    assert d.find("bool[@name='display-timer-radius']").text == "false"
    assert d.find("bool[@name='debuff']").text == "false"
    assert d.find("array[@name='hud']") is not None
    assert 'BUFF = "tweak/hwp/buffs_catchup.sval:hwp_catchup"' in SRC
    assert 'PCT = "+50%"' in SRC


def test_buff_timer_stays_short():
    # a long timer is saved with the player's buffs and outlives the condition (cc01a6a5)
    m = re.search(r"const int KEEP_MS = (\d+);", SRC)
    assert m and int(m.group(1)) <= 10000
    assert "ActorBuff(pb, g_def, 1.0f, true, 0, KEEP_MS)" in SRC
    assert "buff.m_duration = KEEP_MS;" in SRC
    assert "buff.m_duration = 0;" in SRC


def test_buff_name_and_tooltip_strings():
    assert '<string name="hwp.catchup.buff">Late Bloomer</string>' in LANG
    for key in ("lvl", "ngp", "pct"):
        assert "%" + key + "%" in LANG
    for key in re.findall(r'GetString\("\.(hwp\.catchup\.[a-z.]+)"', SRC):
        assert f'name="{key}"' in LANG, key


def test_setting_and_command():
    cfg = json.loads((MOD / "module.json").read_text(encoding="utf-8"))["config"]
    assert cfg["toggle"] == "catchup.enabled"
    assert cfg["scope"] == "host"
    assert 'GetBool("catchup.enabled", true)' in SRC
    assert 'Commands::Register("catchup"' in SRC
    assert 'HWP::Log("catchup", "bonus on: ' in SRC and 'HWP::Log("catchup", "bonus off: ' in SRC


def test_listed_in_coop_everywhere():
    pk = json.loads((ROOT / "packages.json").read_text(encoding="utf-8"))
    coop = next(p for p in pk["packages"] if p["id"] == "coop")
    assert "catchup" in coop["mods"]
    assert "catchup" in json.loads((ROOT / "gamelab/scenarios/mod-all.json").read_text(encoding="utf-8"))["mods"]
    features = (ROOT / "docs/features.md").read_text(encoding="utf-8")
    row = next(line for line in features.splitlines() if line.startswith("| `HWP-coop`"))
    assert row.split("|")[2].strip().split(", ") == coop["mods"]
    assert "| `catchup` |" in (ROOT / "mods/README.md").read_text(encoding="utf-8")
    assert "| `catchup` |" in (ROOT / "docs/modules.md").read_text(encoding="utf-8")
    art = (ROOT / "tools/workshop_art.py").read_text(encoding="utf-8")
    assert f'"coop": ("Co-op Play", "{len(coop["mods"])} party features")' in art
