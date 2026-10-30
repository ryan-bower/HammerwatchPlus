"""mods/pets courier (issue #13) and the hwplib bag item actions it rides on.

check="eat": in town, a caught fish in the bag shows "[F] Eat" after [Q] Drop and no hint on
E (the menu's own Destroy key); F eats it (the old fixed E did both). A mace in town has no
Send home hint (the stash is right there).

check="courier": buy a pet, start a run, put the starting mace in the bag; its hints read
[Q] Drop, [H] Send home. H hands it over: it leaves the bag, lands in the stash tab "Pet
deliveries" and the hint goes (a level 1 pet carries one item). Closing the menu sends the
pet off (no pet unit near), and after the trip (pets.courier_secs 5) it is back.
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


def pets_near(c, r=600):
    return c.gl("near", r, "pets/").get("units") or []


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
    c.flag("pet_bought", ok, title)
    c.hwp("set pets.courier_secs 5")
    r = c.gl("equip", LONGSWORD, "common", 1)  # the starting mace goes to the bag
    n_town = bag_count(c)
    c.flag("courier_bag_item", bool(r.get("ok")) and n_town >= 1, f"bag {n_town}")
    run = c.gl("mission", "bandit_keep", 0)
    c.flag("run_started", bool(run.get("ok")) and c.wait_phase("mission"), json.dumps(run)[:200])
    time.sleep(3)
    pets0 = pets_near(c)
    c.flag("pet_in_run", len(pets0) == 1, json.dumps(pets0)[:300])
    stash_before = c.gl("stash", 1)
    c.menu()
    h = c.hover(BAG, 0)
    name, nav, click = h.get("item", ""), h.get("nav") or [], h.get("clickable") or []
    c.flag("courier_hint", h.get("type") == INVENTORY and nav[4:] == ["[Q] Drop", "[H] Send home"], str(nav))
    c.flag("courier_hint_clickable", len(click) == 6 and click[5], str(click))
    n0 = bag_count(c)
    mark = len(c.g.read_log())
    c.press("h")
    log = wait_log(c, mark, "[HWP:pets] courier: ")
    n1 = bag_count(c)
    st = c.gl("stash", 1)
    c.flag("courier_handed", f"[HWP:pets] courier: {name} to the stash tab 'Pet deliveries' (1/1)" in log
           and n1 == n0 - 1, f"bag {n0} -> {n1}: {log.strip()[-240:]}")
    c.flag("courier_in_stash", st.get("name") == "Pet deliveries" and len(st.get("items") or []) == 1,
           f"before {json.dumps(stash_before)[:160]} after {json.dumps(st)[:200]}")
    h = c.hover(BAG, 0) if n1 > 0 else {"nav": []}
    c.flag("courier_full_no_hint", not any("Send home" in t for t in h.get("nav") or []), str(h.get("nav")))
    # the pet keeps following while the menu is open; it leaves when the menu closes
    c.flag("pet_waits_for_close", len(pets_near(c)) == 1)
    mark = len(c.g.read_log())
    c.close()
    log = wait_log(c, mark, "the pet leaves")
    gone = pets_near(c)
    c.flag("pet_leaves", "[HWP:pets] courier: the pet leaves with 1 item(s), back in 5 s" in log and not gone,
           f"{json.dumps(gone)[:200]} | {log.strip()[-200:]}")
    end = time.time() + 12
    back = []
    while time.time() < end and not back:
        time.sleep(1)
        back = pets_near(c)
    log = c.log_since(mark)
    c.flag("pet_back", "[HWP:pets] courier: the pet is back" in log and len(back) == 1, json.dumps(back)[:200])
    # hwp pet courier reports the next trip's room
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
