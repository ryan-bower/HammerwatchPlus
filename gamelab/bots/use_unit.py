"""Use a unit as a player does and wait for the window it opens (a shop, a dialog), so the
next step can click in it. The unit is the nearest one matching `name` (the `near` probe's
filter: a unit file name or a behaviour class).

  {"do": "bot", "bot": "use_unit", "kwargs": {"name": "hwp_gambler", "teleport": true},
   "expect": {"terminal": "done", "window": "HWPGamblerMenu"}}

How it gets there:
- teleport (default false): first `teleport` next to the unit, trying each of `offsets` until
  the unit is the player's top usable. A setup cheat for town NPCs the Pilot cannot route to
  across the town (ui-click 20261018-051718: no_route after 299 NavRoute expansions, 1800
  units away). A town NPC is usable only while the player touches its 15-unit sensor circle
  (actors/npcs/town/_base.inc:126, NPCBehavior.as Collide -> AddUsable); 24 units away was
  outside it and the Pilot then wandered off (ui-click 20261018-053138).
  When another usable stays top instead (a wandering town NPC that entered range first:
  equal UsePriority, so the first one in stays first, IUsable.as:56-65, Player.as:135-168;
  ui-click 20261018-063339, npc_misc_kevin 8 units from the gambler), it steps out of every
  sensor, waits for the 250 ms sentinel to drop them (Player.as:1009-1020), and lands on the
  unit's far side from the other one.
- Then, when the unit is the player's top usable (the `usables` probe), the Use key (F, the
  default binding, posted like every GameLab key) is pressed, which is all a player does.
  Otherwise the Pilot `use` intent walks there and uses it.
kwargs: name, radius (4000), window (wait for this class; default any window), timeout (s),
teleport, offsets. First waits for any cinematic to end (the `cinema` probe). Returns terminal ("done", the
intent's result, "no_unit", "no_window", "not_usable", "cinematic"),
reason, how ("key" / "pilot"), unit, window.
"""
import math
import time


def usables(p):
    """(the top usable or None, every usable in range)"""
    us = p.cmd("usables").get("usables", [])
    return next((u for u in us if u.get("top")), None), us


def top_usable(p):
    return usables(p)[0]


def uid(entry):
    return ((entry or {}).get("unit") or {}).get("unit")


OFFSETS = ((0, 10), (0, -10), (10, 0), (-10, 0), (8, 8), (-8, 8), (8, -8), (-8, -8))
# landing on the far side of the unit from a competing usable: how far from the unit (inside
# its 15-unit sensor), how far out to leave every sensor first, and the angles to try
FAR_SIDE, CLEAR_OUT, ANGLES = 12, 60, (0, 35, -35, 70, -70)


def wait_cinema(p, limit=40):
    """Wait out a cinematic: while one runs the game walks the player itself and drops its
    input (Player.as:1388-1395; the town arrival walk, diag-teleport 20261018-053946)."""
    end, c = time.time() + limit, {}
    while time.time() < end:
        c = p.cmd("cinema")
        if not c.get("active"):
            break
        time.sleep(0.5)
    return c


def land(p, name, radius, u, dx, dy):
    """Teleport to the unit + (dx, dy); returns the unit re-read there and the cinema state."""
    p.cmd("teleport", round(u["x"] + dx), round(u["y"] + dy))
    time.sleep(0.35)
    c = p.cmd("cinema")
    if c.get("active"):
        # an area the teleport landed in started one (it walks the player away): wait it out
        # and land again
        wait_cinema(p)
        u = (p.cmd("near", radius, name).get("units") or [u])[0]
        p.cmd("teleport", round(u["x"] + dx), round(u["y"] + dy))
        time.sleep(0.35)
    return (p.cmd("near", 400, name).get("units") or [u])[0], c


def clear_usables(p, limit=3.0):
    """Out of every sensor, wait for the sentinel to drop them, one per 250 ms."""
    end = time.time() + limit
    while time.time() < end:
        if not p.cmd("usables").get("usables"):
            return True
        time.sleep(0.3)
    return False


def far_side(p, name, radius, u, others, tries):
    """Land on the unit's far side from the other usables, after leaving every sensor."""
    ox = sum(o["x"] for o in others) / len(others)
    oy = sum(o["y"] for o in others) / len(others)
    vx, vy = u["x"] - ox, u["y"] - oy
    n = math.hypot(vx, vy) or 1.0
    vx, vy = vx / n, vy / n
    top = None
    for deg in ANGLES:
        a = math.radians(deg)
        ax, ay = vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)
        land(p, name, radius, u, ax * CLEAR_OUT, ay * CLEAR_OUT)
        cleared = clear_usables(p)
        u, c = land(p, name, radius, u, ax * FAR_SIDE, ay * FAR_SIDE)
        top, us = usables(p)
        tries.append({"far_side": deg, "cleared": cleared, "dist": u.get("dist"), "cinema": c, "top": uid(top),
                      "others": [x.get("name") for x in others]})
        if uid(top) == u["unit"]:
            break
        others = [x["unit"] for x in us if uid(x) != u["unit"]] or others
    return u, top


def run(p, name, radius=4000, window=None, timeout=45, teleport=False, offsets=OFFSETS):
    cinema = wait_cinema(p)
    if cinema.get("active"):
        return {"terminal": "cinematic", "reason": f"a cinematic still runs: {cinema}", "unit": None,
                "window": p.state().get("window", "")}
    near = p.cmd("near", radius, name)
    units = near.get("units", [])
    if not units:
        return {"terminal": "no_unit", "reason": f"no {name!r} within {radius}", "unit": None, "window": p.state().get("window", "")}
    u = units[0]
    top, tries = None, []
    if teleport:
        for dx, dy in offsets:
            u, c = land(p, name, radius, u, dx, dy)
            top, us = usables(p)
            tries.append({"offset": [dx, dy], "dist": u.get("dist"), "cinema": c, "top": uid(top)})
            if uid(top) == u["unit"]:
                break
            others = [x["unit"] for x in us if uid(x) != u["unit"]]
            if top and others:
                # another usable got in range first and stays top while the player is in its
                # sensor too: nearer offsets cannot fix that
                u, top = far_side(p, name, radius, u, others, tries)
                break
    else:
        top = top_usable(p)
    if uid(top) == u["unit"] and top.get("canUse"):
        how, terminal, reason = "key", "done", "Use key on the top usable"
        p.game.key("f")
    elif teleport:
        return {"terminal": "not_usable",
                "reason": f"never the top usable next to it (top: {((top or {}).get('unit') or {}).get('name')}, "
                          f"tries: {tries})",
                "how": None, "unit": u, "window": p.state().get("window", ""), "top_usable": top,
                "teleported": True, "tries": tries}
    else:
        r = p.use(u["unit"], timeout=timeout)
        how, terminal, reason = "pilot", r.result, r.reason
    win, end = "", time.time() + 5
    while time.time() < end:
        win = p.state().get("window", "")
        if win and (window is None or win == window):
            break
        time.sleep(0.25)
    if terminal == "done" and not (win and (window is None or win == window)):
        terminal = "no_window"
    return {"terminal": terminal, "reason": reason, "how": how, "unit": u, "window": win,
            "top_usable": top, "teleported": bool(teleport), "tries": tries}
