"""Pins for mods/pets PetLevelTab.as (issue #79): source facts the game can't check in CI.

Widget.CloneInto value-copies fields, so a clone of the vanilla `player-level` TextWidget
shares its BitmapString; the clone's first SetText would Cleanup() the character's level.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAB = (ROOT / "mods/pets/scripts/HWP/Pets/PetLevelTab.as").read_text(encoding="utf-8")
LANG = (ROOT / "mods/pets/res/language/english/hwp_pets.lang").read_text(encoding="utf-8")


def _body(sig: str) -> str:
    start = TAB.index(sig)
    depth = 0
    for i in range(TAB.index("{", start), len(TAB)):
        depth += {"{": 1, "}": -1}.get(TAB[i], 0)
        if depth == 0:
            return TAB[start:i + 1]
    raise AssertionError(f"unbalanced body: {sig}")


def test_detach_drops_the_shared_text_and_rebuilds_the_level():
    body = _body("void Detach(TextWidget@ mine, TextWidget@ level)")
    assert "mine.m_text !is level.m_text" in body
    assert "@mine.m_text = null;" in body
    assert "@mine.m_tooltip = null;" in body
    # force=true: vanilla skips SetText when its string is unchanged
    assert "level.SetText(level.m_str, true, true);" in body
    assert body.index("@mine.m_text = null;") < body.index("level.SetText(")


def test_new_clone_is_detached_before_any_set_text():
    tick = _body("void Tick()")
    clone = tick.index("level.Clone()")
    detach = tick.index("Detach(mine, level);", clone)
    assert detach < tick.index("SetText(", clone)
    assert detach < tick.index("AddChild(mine)", clone)


def test_clone_found_by_id_is_detached_too():
    tick = _body("void Tick()")
    assert re.search(r"else\s+Detach\(mine, level\);", tick)


def test_pet_text_never_runs_into_the_name():
    tick = _body("void Tick()")
    assert 'GetWidgetById("player-name")' in tick
    assert "ShortText(rec, petId)" in tick
    assert "g_text.m_visible = Fits(right, nameRight);" in tick
    assert '<string name="hwp.pets.inv_level_short">' in LANG
