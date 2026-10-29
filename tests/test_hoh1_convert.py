"""tools/hoh1_convert.py: HoH1 world-script params under HoH2's names, and HoH1's
"magical" damage as a HoH2 element."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import hoh1_convert as hc  # noqa: E402


def rewriter():
    return hc.Rewriter(copied=set(), hoh2_materials={}, class_map={"ShowSpeechBubble": "HoH1ShowSpeechBubble"},
                       material_map={})


def test_script_params_renamed_keeping_feeds():
    assert hc.script_params("ChangeVariables", {"Function": 2, "Value": 1, "Variables": [12]}) == \
        {"Function": 2, "ModConstant": 1, "Variables": [12]}
    assert hc.script_params("RandomChance", {"#ToExecute": [5, "LastSpawned"]}) == {"#OnTrue": [5, "LastSpawned"]}
    assert hc.script_params("DestroyUnitCount", {"NumToDestroy": 2}) == {"MinNumToDestroy": 2, "MaxNumToDestroy": 2}
    assert hc.script_params("CheckTimeOfDay", {"OnDay": [1], "OnNight": [2]}) == {"OnTrue": [2], "OnFalse": [2]}
    assert hc.script_params("DamageUnits", {"Physical": 0, "Buff": "x"}) == {"Damage": 0, "Buff": "x"}


def test_announce_time_by_length_dropped():
    assert hc.script_params("AnnounceText", {"Time": -2, "Text": "t"}) == {"Text": "t"}
    assert hc.script_params("AnnounceText", {"Time": 2000}) == {"TimeOverride": 2000}


def test_level_rows_get_params_then_class():
    row = ["RandomChance", 7, "0 0 0", True, -1, False, {"ChanceToExecute": 0.5, "ToExecute": [3]}]
    assert hc.Rewriter.svalue(rewriter(), row, "levels/x.lvl")[6] == {"ChanceToExecute": 0.5, "OnTrue": [3]}
    row = ["ShowSpeechBubble", 8, "0 0 0", True, -1, False, {"Objects": [4]}]
    out = hc.Rewriter.svalue(rewriter(), row, "levels/x.lvl")
    assert out[0] == "HoH1ShowSpeechBubble" and out[6] == {"Objects": [4]}


def test_magical_element_by_source():
    unit = '<dict><string name="class">Damage</string><int name="magical">45</int></dict>'
    for path, el in (("actors/projectiles/snowball.unit", "ice"), ("actors/pop/projectiles/spider_spit_1.unit", "poison"),
                     ("doodads/generic/trap_fire.inc", "fire"), ("actors/wisp_1_bomb.unit", "lightning"),
                     ("actors/bosses/wraith/wraith_mage_nova.unit", "lightning")):
        assert f'<int name="{el}">45</int>' in rewriter().text(unit, path), path
    buffs = ('<dict>\n\t<dict name="burning">' + unit + '</dict>\n\t<dict name="poison">' + unit + '</dict></dict>')
    out = rewriter().text(buffs, "actors/buffs.sval")
    assert out.index('name="fire"') < out.index('name="poison">45') and "magical" not in out


def test_lang_keys_prefixed_and_collected():
    rw = rewriter()
    rw.lang = hc.read_lang('﻿<lang>\n\t<string name="meta.info.gatherparty">Gather your\nparty</string>\n</lang>')
    out = rw.text('<string name="Text">.meta.info.gatherparty</string><string name="T">.not.a.key</string>', "levels/x.lvl")
    assert '>.hoh1.meta.info.gatherparty<' in out and '>.not.a.key<' in out
    assert rw.lang_used == {"meta.info.gatherparty"}
    f = hc.lang_file({k: rw.lang[k] for k in rw.lang_used})
    assert '<string name="hoh1.meta.info.gatherparty">Gather your\nparty</string>' in f
    assert f.splitlines()[1] == '<lang name="English" official="false">'


def test_boss_name_key_strips_suffixes():
    lang = {"bestiary.name.bosses.golem": "Stone Guardian", "bestiary.name.bosses.wraith_mage": "Councilor of Magic"}
    assert hc.boss_name_key("actors/bosses/golem_rock.unit", lang) == "bestiary.name.bosses.golem"
    assert hc.boss_name_key("actors/bosses/wraith_mage.unit", lang) == "bestiary.name.bosses.wraith_mage"
    assert hc.boss_name_key("actors/bosses/eye.unit", lang) is None
