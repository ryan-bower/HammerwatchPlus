"""Co-op map fixes (bugs 10.22.26 lines 24 and 41): the per-player map colours of
mods/colors (PlayerColors.as) and the "The chest was trapped!!" banner of mods/keys
(Trapped.as). `section` picks the checks: "colors" drives hwp playercolors through its
palette, names and distance settings and the usage reply; "trapped" opens a cursed chest
1500 px from the player (the keys.trapped event arrives but is out of the 900 px banner
range) and a plain bronze chest (never trapped). Both run on a floor with god mode on.
"""
import re
import time

from gamelab.bots.plan_checks import Checks

STATUS = re.compile(r"Player colours: palette (?P<palette>\w+), you are peer (?P<peer>\d+) #(?P<color>[0-9a-f]{6}), "
                    r"map names (?P<names>on|off) beyond (?P<distance>\d+) px")
SAFE0 = "e69f00"  # Okabe-Ito, peer 0


def run(p, section="colors", **kwargs):
    c = Checks(p)
    if section == "colors":
        colors(c)
    elif section == "trapped":
        trapped(c)
    else:
        c.flag("section_known", False, f"unknown section {section!r}")
    c.out["notes"] = c.notes
    return c.out


def status(c, line, want):
    """hwp playercolors <line>; the status reply it logged (the last one), or None."""
    log = c.hwp(("playercolors " + line).strip(), until=want, timeout=4)
    m = None
    for hit in STATUS.finditer(log):
        m = hit
    return m


def colors(c):
    m = status(c, "", "Player colours:")
    c.flag("status_reply", m is not None and m.group("palette") == "default",
           m.group(0) if m else "no status reply")
    peer = int(m.group("peer")) if m else 0

    m = status(c, "safe", "palette safe")
    want = SAFE0 if peer == 0 else None
    c.flag("safe_palette", m is not None and m.group("palette") == "safe" and (want is None or m.group("color") == want),
           m.group(0) if m else "no reply")
    log = c.g.read_log()
    c.flag("safe_logged", "[HWP:colors] player colours set: Player colours: palette safe" in log)

    m = status(c, "names off", "map names off")
    c.flag("names_off", m is not None and m.group("names") == "off", m.group(0) if m else "no reply")

    m = status(c, "distance 250", "beyond 250 px")
    c.flag("distance_set", m is not None and m.group("distance") == "250", m.group(0) if m else "no reply")

    log = c.hwp("playercolors bogus", until="hwp playercolors [default|safe]", timeout=3)
    c.flag("junk_usage", "hwp playercolors [default|safe] [names on|off] [distance N]" in log)

    m = status(c, "default names on distance 300", "beyond 300 px")
    c.flag("reset_default", m is not None and m.group("palette") == "default" and m.group("names") == "on"
           and m.group("distance") == "300", m.group(0) if m else "no reply")


def trapped(c):
    g = c.g
    me = c.pos()
    # the event arrives on this machine (the host) but the player is beyond RANGE
    mark = len(g.read_log())
    r = c.gl("spawn", "items/chests/chest_cursed.unit", 1500, 0)
    c.flag("far_chest_spawned", bool(r.get("ok")), str(r)[:120])
    time.sleep(0.5)
    r = c.gl("use", "chest_cursed")
    c.flag("far_chest_used", bool(r.get("ok")), str(r)[:120])
    end = time.time() + 4
    new = ""
    while time.time() < end:
        new = g.read_log()[mark:]
        if "out of range" in new:
            break
        time.sleep(0.25)
    c.flag("far_chest_out_of_range", bool(re.search(r"\[HWP:keys\] trapped chest at -?\d+,-?\d+ out of range \(\d+\)", new)),
           "no out-of-range line" if "out of range" not in new else "")
    c.flag("far_chest_no_banner", "trapped chest banner at" not in new)
    time.sleep(1)
    c.gl("cull")  # the shade ambush the far chest spawned
    c.gl("teleport", me[0], me[1])
    time.sleep(0.4)

    # a plain chest: HWPChest locks it (keys.lock_chance) so the opening fails without a
    # key, but the trap hook is before that and must stay silent either way
    mark = len(g.read_log())
    r = c.gl("spawn", "items/chests/chest_bronze_equipment.unit", 48, 0)
    c.flag("plain_chest_spawned", bool(r.get("ok")), str(r)[:120])
    time.sleep(0.5)
    c.gl("use", "chest_bronze")
    time.sleep(1.5)
    new = g.read_log()[mark:]
    c.flag("plain_chest_silent", "trapped chest" not in new)
