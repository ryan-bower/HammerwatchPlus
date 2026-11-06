"""mods/pets courier (issue #13) and the hwplib bag item actions it rides on.

check="eat": in town, a caught fish in the bag shows "[F] Eat" after [Q] Drop and no hint on
E (the menu's own Destroy key); F eats it (the old fixed E did both). A mace in town has no
Send home hint (the stash is right there).

check="courier": buy a pet, put two eligible common weapons in the bag before the
measurement, then start a run. H hands the first item over: bag 2 -> 1 and one delivery.
The actual remaining item's native inventory hover keeps Drop but has no Send home at
the live 1/1 capacity status. Closing the menu sends the pet off; after 5 s it is back.
These are native metadata/count/UI observations, not full serialized-item conservation.
"""
import json
import re
import time

from gamelab.bots.fix_pets import buy_pet
from gamelab.bots.plan_gear import BAG, INVENTORY, LONGSWORD, Checks


def bag_count(c):
    """Bag items as the game holds them (bagitems; `hwp bag` needs the keys mod)."""
    return c.gl("bagitems").get("count", -1)


def wait_log(c, mark, needle, timeout=5.0):
    """The log since mark, polled until needle shows (the game flushes its log late)."""
    end = time.time() + timeout
    log = c.log_since(mark)
    while needle not in log and time.time() < end:
        time.sleep(0.25)
        log = c.log_since(mark)
    return log


def native_reply(reply, label):
    """Refused or incomplete telemetry cannot establish an absent action/pet."""
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        raise RuntimeError(label + " refused")
    cut = reply.get("truncated", 0)
    if type(cut) not in (bool, int) or cut != 0 or reply.get("complete", True) is not True:
        raise RuntimeError(label + " incomplete/truncated")
    return reply


def courier_bag(c):
    """Complete native bagitems projection, not a serialized Item::SaveItem read."""
    reply = native_reply(c.gl("bagitems"), "courier bag")
    items, count = reply.get("bag"), reply.get("count")
    if type(count) is not int or not 0 <= count <= 32 or not isinstance(items, list) or len(items) != count:
        raise RuntimeError("courier bag count/rows missing or truncated")
    for i, item in enumerate(items):
        if (not isinstance(item, dict) or type(item.get("index")) is not int or item["index"] != i
                or any(type(item.get(key)) is not str or not item[key] for key in ("id", "name", "slot"))
                or type(item.get("quality")) is not int or item["quality"] <= 0
                or type(item.get("ilvl")) is not int or item["ilvl"] < 1):
            raise RuntimeError("courier bag item metadata incomplete")
    return items


def courier_hover(c, item):
    reply = native_reply(c.hover(BAG, 0), "courier inventory hover")
    nav, click = reply.get("nav"), reply.get("clickable")
    if (reply.get("window") != "PlayerMenu" or type(reply.get("type")) is not int
            or reply["type"] != INVENTORY or reply.get("item") != item["name"]
            or not isinstance(nav, list) or not nav or not all(type(text) is str for text in nav)
            or not isinstance(click, list) or len(click) != len(nav) or not all(type(value) is bool for value in click)):
        raise RuntimeError("courier hover did not select a complete real inventory item")
    return reply


def pets_near(c, r=600):
    reply = native_reply(c.gl("near", r, "pets/"), "courier pet query")
    units, count = reply.get("units"), reply.get("count")
    if type(count) is not int or not isinstance(units, list) or count != len(units):
        raise RuntimeError("courier pet query count/rows incomplete")
    if any(not isinstance(unit, dict) or type(unit.get("unit")) is not int for unit in units):
        raise RuntimeError("courier pet query has incomplete unit identity")
    return units


def eat(c):
    r = c.gl("equip", LONGSWORD, "common", 1)  # the starting mace goes to the bag
    c.hwp("set fishing.debug 1")
    got = c.hwp("fishing catch 1", 0.6)
    n0 = bag_count(c)
    c.flag("eat_setup", bool(r.get("ok")) and n0 >= 2, f"bag {n0}, {got.strip()[-160:]}")
    c.menu()
    items = c.gl("bagitems").get("bag") or []
    fish_at = next((i for i, it in enumerate(items) if "fish" in json.dumps(it).lower()), -1)
    mace_at = next((i for i, it in enumerate(items) if i != fish_at), -1)
    h = c.hover(BAG, fish_at)
    nav = h.get("nav") or []
    click = h.get("clickable") or []
    c.flag("eat_hint_f", fish_at >= 0 and h.get("type") == INVENTORY and nav[-1:] == ["[F] Eat"]
           and "[Q] Drop" in nav and not any(t.startswith("[E]") for t in nav), str(nav))
    c.flag("eat_hint_clickable", len(click) == len(nav) and all(click[3:]), str(click))
    mark = len(c.g.read_log())
    c.press("f")
    log = wait_log(c, mark, "[HWP:fishing] ate ")
    n1 = bag_count(c)
    c.flag("eat_f_eats", "[HWP:fishing] ate " in log and n1 == n0 - 1, f"bag {n0} -> {n1}: {log.strip()[-200:]}")
    c.flag("eat_no_destroy_dialog", c.gl("state").get("window") == "PlayerMenu", str(c.gl("state").get("window")))
    h = c.hover(BAG, 0)
    nav = h.get("nav") or []
    c.flag("town_no_courier", h.get("type") == INVENTORY and not any("Send home" in t for t in nav), str(nav))
    c.close()


def courier(c):
    title, ok = buy_pet(c)
    c.flag("pet_bought", ok is True, title)
    if ok is not True:
        return
    c.hwp("set pets.courier_secs 5")
    # Both legal native equips precede the bag/handoff measurement. Replacing
    # the sword moves it into the bag beside the starting mace.
    equips = []
    for base in (LONGSWORD, "mainhand_mace_01"):
        reply = c.gl("equip", base, "common", 1)
        equips.append(reply)
        if not isinstance(reply, dict) or reply.get("ok") is not True:
            c.flag("courier_bag_item", False, str(equips))
            return
    town_items = courier_bag(c)
    ready = (len(town_items) == 2 and [item["id"] for item in town_items]
             == ["mainhand_mace_01", LONGSWORD]
             and all(item["quality"] == 1 and item["ilvl"] == 1 for item in town_items))
    c.flag("courier_bag_item", ready, f"equips {equips}, bag {town_items}")
    if not ready:
        return
    run = c.gl("mission", "bandit_keep", 0)
    started = isinstance(run, dict) and run.get("ok") is True and c.wait_phase("mission")
    c.flag("run_started", started, json.dumps(run)[:200])
    if not started:
        return
    time.sleep(3)
    pets0 = pets_near(c)
    c.flag("pet_in_run", len(pets0) == 1, json.dumps(pets0)[:300])
    if len(pets0) != 1:
        return
    stash_before = c.gl("stash", 1)  # tab may not exist until the first delivery
    native_reply(c.menu(), "courier inventory menu")
    before = courier_bag(c)
    if len(before) != 2:
        raise RuntimeError("courier measurement requires two actual bag items")
    h = courier_hover(c, before[0])
    name, nav, click = h["item"], h["nav"], h["clickable"]
    hint = nav[4:] == ["[Q] Drop", "[H] Send home"]
    clickable = len(click) == 6 and click[5]
    c.flag("courier_hint", hint, str(nav))
    c.flag("courier_hint_clickable", clickable, str(click))
    if not hint or not clickable:
        return
    n0 = len(before)
    mark = len(c.g.read_log())
    c.press("h")
    log = wait_log(c, mark, "[HWP:pets] courier: ")
    after = courier_bag(c)
    n1 = len(after)
    st = native_reply(c.gl("stash", 1), "courier delivery stash")
    handed = (f"[HWP:pets] courier: {name} to the stash tab 'Pet deliveries' (1/1)" in log
              and n0 == 2 and n1 == 1 and n1 == n0 - 1)
    c.flag("courier_handed", handed, f"bag {n0} -> {n1}: {log.strip()[-240:]}")
    delivered = st.get("name") == "Pet deliveries" and isinstance(st.get("items"), list) and len(st["items"]) == 1
    c.flag("courier_in_stash", delivered, f"before {json.dumps(stash_before)[:160]} after {json.dumps(st)[:200]}")
    if not handed or not delivered:
        return
    # This must be an actual remaining item; an empty bag never supplies absence evidence.
    h = courier_hover(c, after[0])
    nav, click = h["nav"], h["clickable"]
    full_status = c.hwp("pet courier", 0.5, until="Pet courier")
    full = (not any("Send home" in text for text in nav) and "[Q] Drop" in nav
            and click[nav.index("[Q] Drop")] is True
            and re.search(r"Pet courier:\s+1/1(?:\s|$)", full_status) is not None)
    c.flag("courier_full_no_hint", full, f"remaining {after[0]}, hover {h}, status {full_status.strip()[-160:]}")
    if not full:
        return
    # The pet keeps following while the menu is open; it leaves when the menu closes.
    menu_state = native_reply(c.gl("state"), "courier menu state")
    waiting_pets = pets_near(c)
    # Observe the open window and the same solo fixture pet. Menu-open does not
    # imply paused; the actual E013 heartbeat was unpaused with this UI open.
    waiting = (menu_state.get("window") == "PlayerMenu" and menu_state.get("phase") == "mission"
               and isinstance(menu_state.get("player"), dict) and menu_state["player"].get("dead") is False
               and len(waiting_pets) == 1 and waiting_pets[0]["unit"] == pets0[0]["unit"])
    c.flag("pet_waits_for_close", waiting, f"state {menu_state}, initial pet {pets0}, waiting {waiting_pets}")
    if not waiting:
        return
    mark = len(c.g.read_log())
    if not c.close():
        c.flag("pet_leaves", False, "inventory menu did not close")
        return
    log = wait_log(c, mark, "the pet leaves")
    gone = pets_near(c)
    left = "[HWP:pets] courier: the pet leaves with 1 item(s), back in 5 s" in log and not gone
    c.flag("pet_leaves", left, f"{json.dumps(gone)[:200]} | {log.strip()[-200:]}")
    if not left:
        return
    end = time.time() + 12
    back = []
    while time.time() < end and not back:
        time.sleep(1)
        back = pets_near(c)
    log = c.log_since(mark)
    returned = "[HWP:pets] courier: the pet is back" in log and len(back) == 1
    c.flag("pet_back", returned, json.dumps(back)[:200])
    if not returned:
        return
    # hwp pet courier reports the next trip's room.
    rep = c.hwp("pet courier", 0.5, until="Pet courier")
    c.flag("courier_status", "Pet courier: 0/1" in rep, rep.strip()[-160:])


def run(pilot, check="courier", **kwargs):
    c = Checks(pilot)
    try:
        {"eat": eat, "courier": courier}[check](c)
    except Exception as e:  # noqa: BLE001 - report what broke, keep the flags so far
        c.flag("exception", False, repr(e)[:300])
    out = dict(c.out)
    out["ok"] = all(v for k, v in c.out.items() if not k.endswith("_note"))
    out["notes"] = c.notes
    return out
