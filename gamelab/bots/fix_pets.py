"""mods/pets: the Pet Shop keeper carries the old feeding bowl's menu, and the character tab
shows the pet's level.

check="merchant": buy a pet from the keeper (no pet: the vanilla shop opens directly), use the
keeper again: the Buy / Train choice shows the pet's status; Train opens the progression
menu (gui/hwp_pets.gui) with the skill rows, the feed section and the pickup toggles.

check="inventory": with a pet out, `gl menu character` shows "hwp-pet-level" reading
"pet lvl N (xx%)" beside the character level; after `hwp pet xp 500` (pets.debug) the text
moves to the new level.
"""
import re
import time

from gamelab.bots.plan_checks import Checks


def buy_pet(c):
    """A pet from the keeper; returns (title, ok)."""
    c.set_gold(60000)
    c.npc("npc_pets", "actors/npcs/town/npc_pets.unit")
    c.gl("use", "npc_pets")
    time.sleep(0.6)
    if not c.gl("wtext", "pet-state").get("missing"):
        c.gl("press", "buy-btn")  # already has a pet: the choice window first
        time.sleep(0.6)
    shop = c.gl("shop")
    items = shop.get("items") or []
    if not items:
        c.g.key("escape")
        return "", False
    pick = 0
    for i, it in enumerate(items):
        if it.get("gold", 1) > 0 and it.get("available", True):
            pick = i
            break
    c.gl("shop", "buy", pick)
    time.sleep(1.5)
    if c.gl("state").get("window"):
        c.g.key("escape")
        time.sleep(0.3)
    st = c.hwp("pet", 0.5, until="level")
    return items[pick].get("title", ""), "level" in st


def merchant(c):
    title, ok = buy_pet(c)
    c.flag("pet_bought", ok, title)
    c.gl("use", "npc_pets")
    time.sleep(0.6)
    state = c.gl("wtext", "pet-state", "buy-btn", "train-btn")
    texts = state.get("texts") or {}
    pet_state = texts.get("pet-state", "") if isinstance(texts, dict) else ""
    c.flag("keeper_offers_choice", not state.get("missing") and "level" in pet_state.lower(),
           f"pet-state={pet_state!r} missing={state.get('missing')}")
    c.gl("press", "train-btn")
    time.sleep(0.6)
    menu = c.gl("wtext", "state", "xp", "points", "title")
    mt = menu.get("texts") or {}
    c.flag("train_menu_open", not menu.get("missing") and "level" in str(mt.get("state", "")).lower(),
           f"{mt}")
    rows = c.gl("wchildren", "list", 2)
    raw = str(rows)
    c.flag("train_menu_rows", all(w in raw for w in ("row-0", "row-6")) and "row-7" in raw,
           f"{raw[:300]}")
    # a skill row press is refused without points (the message says so), the menu stays
    c.gl("press", "row-0")
    time.sleep(0.4)
    msg = c.gl("wtext", "message").get("texts") or {}
    c.flag("train_menu_skill_row", "point" in str(msg.get("message", "")).lower() or "max" in str(msg.get("message", "")).lower(),
           f"{msg}")
    c.g.key("escape")
    time.sleep(0.3)
    log = c.g.read_log()
    c.flag("train_logged", "[HWP:pets] pet shop: train" in log)


def inventory(c):
    title, ok = buy_pet(c)
    c.flag("pet_bought", ok, title)
    c.gl("menu", "character")
    time.sleep(0.5)
    # the tab is a MenuTab with its own widget tree (wtext reads only the window's own):
    # `menu character - <id>` finds the widget in the open tab, "texts" = its text(s)
    t = c.gl("menu", "character", "-", "hwp-pet-level")
    pet = str(t.get("texts") or "")
    c.flag("pet_level_shown", bool(t.get("ok")) and bool(t.get("shown")) and re.search(r"pet lvl \d+ \(\d+%\)", pet) is not None,
           f"{t.get('tab')}: shown={t.get('shown')} texts={pet!r}")
    c.flag("pet_level_logged", "[HWP:pets] pet level line added to the character tab" in c.g.read_log())
    c.g.key("escape")
    time.sleep(0.3)
    c.hwp("set pets.debug true")
    c.hwp("pet xp 500", 0.8, until="reached level")
    c.gl("menu", "character")
    time.sleep(0.5)
    t2 = c.gl("menu", "character", "-", "hwp-pet-level")
    pet2 = str(t2.get("texts") or "")
    m1, m2 = re.search(r"pet lvl (\d+)", pet), re.search(r"pet lvl (\d+)", pet2)
    c.flag("pet_level_updates", bool(m1 and m2) and int(m2.group(1)) > int(m1.group(1)), f"{pet!r} -> {pet2!r}")
    c.g.key("escape")


def run(p, check="merchant"):
    c = Checks(p)
    try:
        {"merchant": merchant, "inventory": inventory}[check](c)
    except Exception as exc:  # a crashed check is a failed check, not a crashed run
        c.flag(check + "_crashed", False, repr(exc))
    c.out["ok"] = bool(c.out) and all(v for v in c.out.values() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
