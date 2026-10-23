"""Pick a subclass at the real Subclass Picker NPC, as a player does (docs/devarena/SPEC.md HP6).

  {"do": "bot", "bot": "devarena_pick_spec", "kwargs": {"spec": "ranger_test"},
   "expect": {"terminal": "done", "picked": true}}

1. The harness's use_unit bot on npc_subclass_picker (actors/npcs/town/npc_subclass_picker.unit):
   the Use key on the NPC opens SubclassPickWindow, at level 10 and up (its conditionals; below
   that it only talks). teleport (default true) is use_unit's setup cheat for town NPCs the Pilot
   cannot route to.
2. The picker's right arrow (func "nextclass", a mouse-only spritebutton, gui/shops/
   subclass_picker.gui:52) clicked with the emulated mouse (gamelab-hands `pointer ... click`)
   until the window shows `spec` (devarena `da-ship`: the window's m_classes[m_currPickedIndex]).
   The next-class keys are mouse buttons 4/5 (res/controls_default.cfg:46-47), which a posted
   key cannot be.
3. MenuContext, R (res/controls_default.cfg:35): SwitchClass -> PlayerRecord.ChangeClass
   (Town/SubclassPickShopContent.as:131-141).
4. Escape closes the window when close=True.

tour=True first clicks the next arrow once per offered class and records what the window shows
after each (`toured`): the arrow wraps (SetCurrSubclass, % numPicks), so a full tour ends where it
began. A base-class player opens the window on the last sibling (pickedIdx -1), which is where a
new spec lands, so without the tour the arrows may never be pressed.

Returns terminal ("done", "no_window", "not_offered", "not_picked"), picked, clicks, open (the
use_unit reply), before / after (da-ship replies), window.
"""
import time

from gamelab.pilot import load_bot


def ship(p, spec):
    return p.cmd("da-ship", spec)


def next_arrow(p):
    btn = [c for c in p.cmd("clickables", "top").get("items", []) if c.get("func") == "nextclass"]
    if not btn:
        return False
    p.cmd("pointer", btn[0]["px"], btn[0]["py"], "click")
    time.sleep(0.25)
    return True


def run(p, spec, teleport=True, close=True, limit=12, switch_key="r", tour=False):
    opened = load_bot("use_unit").run(p, name="npc_subclass_picker", teleport=teleport)
    time.sleep(0.4)
    before = ship(p, spec)
    if not before.get("picker"):
        return {"terminal": "no_window", "picked": False, "open": opened, "before": before,
                "window": p.state().get("window", "")}
    if before.get("pickerIndex", -1) < 0:
        return {"terminal": "not_offered", "picked": False, "open": opened, "before": before}
    clicks, s, toured = 0, before, []
    for _ in range(before.get("offered", 0) if tour else 0):
        if not next_arrow(p):
            break
        clicks += 1
        s = ship(p, spec)
        toured.append(s.get("shows"))
    while s.get("shows") != spec and clicks < limit + len(toured):
        if not next_arrow(p):
            break
        clicks += 1
        s = ship(p, spec)
    shown = s
    if shown.get("shows") == spec:
        p.cmd("pointer", 6, 6, "move")
        p.game.key(switch_key)
        time.sleep(0.6)
    after = ship(p, spec)
    if close and after.get("picker"):
        p.game.key("escape")
        time.sleep(0.4)
    return {"terminal": "done" if after.get("picked") else "not_picked", "picked": bool(after.get("picked")),
            "clicks": clicks, "toured": toured, "open": opened, "before": before, "shown": shown, "after": after,
            "window": p.state().get("window", "")}
