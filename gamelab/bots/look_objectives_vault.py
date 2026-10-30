"""Look at an objectives vault (issue #26): from the generator's log line, put the player in
the middle of a floor's first vault, or just outside its door, and stay there, so the
scenario's shots show the room's floor and walls next to the floor around it. `level` picks
the latest vault on that level (the line's "on <level>"); without it, the latest of any.
Teleports are measurement, not play."""
import time

from gamelab.bots.plan_checks import Checks
from gamelab.bots.fix_objectives import VAULT


def run(p, at="centre", level=None, **kwargs):
    c = Checks(p)
    v = None
    for line in c.g.read_log().splitlines():
        if "[preload]" in line or (level and " on %s" % level not in line):
            continue
        m = VAULT.search(line)
        if m and m.group("i") == "0":
            v = m
    c.flag("vault_logged", v is not None, "no 'vault 0 at cell' line" if v is None else v.group(0))
    if v is None:
        return c.out
    world = (int(v.group("wx")), int(v.group("wy")))
    w, h = int(v.group("w")), int(v.group("h"))
    door = (int(v.group("dx")), int(v.group("dy")))
    spots = {"centre": (world[0] + w / 2, world[1] + h / 2),
             "door": (door[0] + 16, door[1] + 40)}
    x, y = spots.get(at, spots["centre"])
    c.gl("teleport", x, y)
    time.sleep(0.6)
    c.out["at"] = [x, y]
    c.out["ok"] = True
    return c.out
