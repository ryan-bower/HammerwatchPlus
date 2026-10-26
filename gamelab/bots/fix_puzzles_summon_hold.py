"""Summons stay out of puzzle rooms (mods/puzzles SummonHold.as).

The scenario brings a player with a summon (a Beastmaster Ranger's wolf by default; any
unit under PlayerRecord.summons works, `unit` is the `near` filter) onto a keep floor whose
puzzle room was forced (the [HWP:puzzles] "forced ... (door ...; world X,Y WxH)" line gives
the room's world rect and doorway). The bot waits for the summons, parks the player in the
corridor outside the doorway (the leash pulls them there), then steps into the room's
centre and samples their positions for a few seconds: every one must stay outside the
room's rect and the hold must be logged. Stepping back out must log the release and the
summons must rejoin (within the 350 px leash) again.
"""
import re
import time

from gamelab.bots.plan_checks import Checks

FORCED = re.compile(r"forced (?P<id>\S+) at (?P<cx>\d+),(?P<cy>\d+) of \d+x\d+, corridor (?P<len>\d+) "
                    r"\(door (?P<dx>-?\d+),(?P<dy>-?\d+) width (?P<w>\d+) out (?P<ox>-?\d+),(?P<oy>-?\d+); "
                    r"world (?P<x>-?\d+),(?P<y>-?\d+) (?P<rw>\d+)x(?P<rh>\d+)\)")


def run(p, settle=3.0, samples=8, unit="players/ranger/units/wolf"):
    c = Checks(p)
    g = p.game
    out = c.out
    m = None
    for hit in FORCED.finditer(g.read_log()):
        m = hit
    if m is None:
        c.flag("forced_room_logged", False, "no forced puzzle room line in the log")
        return out
    d = {k: int(v) for k, v in m.groupdict().items() if k != "id"}
    room = (d["x"], d["y"], d["rw"], d["rh"])
    # the doorway's first cell and the corridor spot 3 cells out, halfway along the door
    door = (d["x"] + (d["dx"] - d["cx"]) * 16 + 8, d["y"] + (d["dy"] - d["cy"]) * 16 + 8)
    along = (abs(d["oy"]), abs(d["ox"]))  # the door runs across the way out
    spot = (door[0] + d["ox"] * 48 + along[0] * (d["w"] // 2) * 16,
            door[1] + d["oy"] * 48 + along[1] * (d["w"] // 2) * 16)
    centre = (room[0] + room[2] / 2, room[1] + room[3] / 2)
    c.flag("forced_room_logged", True, f"{m.group('id')} world {room}, door {door}, corridor spot {spot}")

    def inside(u, margin=0):
        return (room[0] - margin <= u["x"] <= room[0] + room[2] + margin
                and room[1] - margin <= u["y"] <= room[1] + room[3] + margin)

    def summons(radius=6000):
        us = c.gl("near", radius, unit).get("units") or []
        return [u for u in us if not u.get("dead")]

    end = time.time() + 50
    cs = []
    while time.time() < end:
        cs = summons()
        if cs:
            break
        time.sleep(2)
    c.flag("summons_out", bool(cs), f"{len(cs)} summon(s) matching {unit!r}")
    if not cs:
        return out
    c.hwp("god")
    c.hwp("killall")
    # outside the doorway: the leash brings the summons along
    c.gl("teleport", spot[0], spot[1])
    time.sleep(settle)
    near = [u for u in summons() if u.get("dist", 1e9) < 400]
    c.flag("summons_follow_to_door", len(near) == len(cs), f"{len(near)}/{len(cs)} within 400 px at the doorway")
    mark = len(g.read_log())
    # into the room
    c.gl("teleport", centre[0], centre[1])
    worst = 0
    bad = []
    for _ in range(samples):
        time.sleep(0.5)
        for u in summons():
            if inside(u):
                bad.append((round(u["x"]), round(u["y"])))
            worst = max(worst, u.get("dist", 0))
    c.flag("summons_outside_room", not bad and len(summons()) == len(cs),
           f"{len(bad)} sample(s) inside the room {room}, farthest {worst:.0f} px from the player")
    held = re.findall(r"\[HWP:puzzles\] summons of \S+ held outside (\S+)", g.read_log()[mark:])
    c.flag("hold_logged", bool(held), held[-1] if held else "no hold line")
    # back out to the corridor spot: released, following again. Not just past the door: the
    # _b rooms keep puzzle units near it, within puzzles.radius, which still counts as inside
    # (summon-hold 20261026-135047 and -140708: no release 16 px out)
    mark = len(g.read_log())
    c.gl("teleport", spot[0], spot[1])
    time.sleep(settle)
    released = "[HWP:puzzles] summons of" in g.read_log()[mark:] and "released" in g.read_log()[mark:]
    near = [u for u in summons() if u.get("dist", 1e9) < 400]
    c.flag("release_logged", released)
    c.flag("summons_rejoin", len(near) == len(cs), f"{len(near)}/{len(cs)} within 400 px after leaving")
    out["ok"] = all(v for k, v in out.items() if isinstance(v, bool))
    out["notes"] = c.notes
    return out
