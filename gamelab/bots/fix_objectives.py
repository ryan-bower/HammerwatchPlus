"""Floor objectives (bugs 10.22.26 line 46, mods/objectives): on a generated keep floor
the host placed one loot vault (a sealed room, two chests, a lever elsewhere) and the
exit switch. From the generator's log lines this bot reads where they are, then:
the vault is closed (a walk up the corridor stops at the door), the floor's exits are
disabled, the HUD says "Find the switch to open the way down"; the vault lever (gl use,
the host's own use path) opens the door (the walk reaches the room, the vault line reads
1/1, two chests inside); the exit lever enables the exits and the HUD says "The way down
is open", then clears; hwp objectives reports it all. The engine pathfinder's answers
around the vault go into the notes only: the carved corridor is off its graph (measured
2026-10-26), so a path test would fail sealed and open alike.
Teleports are measurement, not play (the lever is used through IUsable.Use directly).
"""
import re
import time

from gamelab.bots.plan_checks import Checks

VAULT = re.compile(r"\[HWP:objectives\] vault (?P<i>\d+) at cell (?P<cx>\d+),(?P<cy>\d+) of \d+x\d+, corridor (?P<corr>\d+), "
                   r"world (?P<wx>-?\d+),(?P<wy>-?\d+) (?P<w>\d+)x(?P<h>\d+), door (?P<dx>-?\d+),(?P<dy>-?\d+), "
                   r"switch (?P<sw>none|(?P<sx>-?\d+),(?P<sy>-?\d+))")
EXIT = re.compile(r"\[HWP:objectives\] exit switch at cell \d+,\d+ world (?P<ex>-?\d+),(?P<ey>-?\d+)")
EXIT_FIND = "Find the switch to open the way down"
EXIT_OPEN = "The way down is open"
# the cave/citadel floors exit through area scripts, the keep through a LevelExitNext
# fired by a UseTrigger (prefabs/keep/level_exit_part_*.pfb); the module seals all four
EXIT_TYPES = ("LevelExitAreaNext", "LevelExitAreaJump", "LevelExitNext", "LevelExitJump")


def run(p, **kwargs):
    c = Checks(p)
    objectives(c)
    c.out["notes"] = c.notes
    return c.out


def wait_log(c, pattern, mark, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        m = re.search(pattern, c.g.read_log()[mark:])
        if m:
            return m
        time.sleep(0.25)
    return None


def exits(c):
    """(total exit scripts, enabled exit scripts) over both exit area types."""
    total = enabled = 0
    for t in EXIT_TYPES:
        r = c.gl("ws", t)
        for s in r.get("scripts", []):
            total += 1
            enabled += 1 if s.get("e") else 0
    return total, enabled


def walk_in(c, outside, door_y, label):
    """The player's own test of the door: stand in the corridor below the doorway, hold up
    for a moment, read where the player ended. Sealed: the door's static collision stops
    the walk at the doorway (y stays below the door line). Open: the walk crosses the
    doorway into the room. Returns (crossed, note). A screenshot of each attempt is kept."""
    c.gl("teleport", outside[0], outside[1])
    time.sleep(0.4)
    c.g.shot(f"vault-door-{label}")
    c.gl("input", 900, 0, -1)
    time.sleep(1.3)
    x, y = c.pos()
    crossed = y < door_y - 8
    return crossed, f"walked from {outside} to ({x:.0f}, {y:.0f}); door line y={door_y}"


def path_into(c, outside, centre):
    """Pathfind nodes from the corridor point outside the door to the vault's centre (the
    engine's answer for the AI; a note, not a flag: the generated corridor's cells answer
    empty from the pathfinder even where the player walks, see the README)."""
    c.gl("teleport", outside[0], outside[1])
    time.sleep(0.4)
    r = c.gl("pathfind", centre[0], centre[1], 12, 2000, 2000)
    return int(r.get("nodes", -1)), r


def reach_notes(c, label, world, w, h, outside, centre, corridor_end):
    """Pathfinder diagnostics as notes: the reachmap around the vault from the outside
    point, short legs between the corridor, the doorway and the room, and the corridor
    from its far end (where it meets the floor) up to the door."""
    rm = c.gl("reachmap", world[0] - 16, world[1] - 16, world[0] + w + 16, world[1] + h + 48, 16)
    for row in rm.get("rows", []):
        c.notes.append(f"{label} reach: {row}")
    c.gl("teleport", corridor_end[0], corridor_end[1])
    time.sleep(0.4)
    rm = c.gl("reachmap", corridor_end[0] - 32, outside[1] - 48, corridor_end[0] + 32, corridor_end[1] + 32, 16)
    c.notes.append(f"{label} corridor reach from its end {corridor_end}: {rm.get('reachable')} of {rm.get('nx', 0) * rm.get('ny', 0)}: "
                   + "|".join(rm.get("rows", [])))
    for name, a, b in (("outside->corridor", outside, (outside[0], outside[1] + 64)),
                       ("outside->doorway", outside, (outside[0], outside[1] - 32)),
                       ("centre->west", centre, (centre[0] - 24, centre[1] + 16)),
                       ("centre->doorway", centre, (outside[0], outside[1] - 32)),
                       ("end->outside", corridor_end, outside),
                       ("end->out64", corridor_end, (corridor_end[0], corridor_end[1] + 64))):
        r = c.gl("pathfind", b[0], b[1], 12, 2000, 2000, a[0], a[1])
        c.notes.append(f"{label} {name}: nodes {r.get('nodes')} {str(r)[:100]}")


def hud_line(c):
    return (c.widget("hwp-objective") or {}).get("text", "")


def objectives(c):
    g = c.g
    # the next floor preloads while this one runs and logs its own placement lines
    # tagged [preload]: only this floor's lines count
    log = "\n".join(l for l in g.read_log().splitlines() if "[preload]" not in l)
    vaults = [m for m in VAULT.finditer(log)]
    last = {}
    for m in vaults:  # the newest floor's lines come last; keep one record per index
        last[m.group("i")] = m
    v = last.get("0")
    c.flag("vault_logged", v is not None, "no 'vault 0 at cell' line" if v is None else v.group(0))
    e = None
    for e in EXIT.finditer(log):
        pass
    c.flag("exit_switch_logged", e is not None, "no 'exit switch at cell' line" if e is None else e.group(0))
    if v is None or e is None:
        return
    c.flag("vault_has_switch", v.group("sw") != "none", v.group("sw"))
    if v.group("sw") == "none":
        return

    world = (int(v.group("wx")), int(v.group("wy")))
    w, h = int(v.group("w")), int(v.group("h"))
    centre = (world[0] + w / 2, world[1] + h / 2)          # the room's middle cell (9x8: 72,64)
    door = (int(v.group("dx")), int(v.group("dy")))         # the door unit (world + 48,112)
    outside = (door[0] + 16, door[1] + 24)                  # the first cell beyond the doorway
    corridor_end = (outside[0], outside[1] + (int(v.group("corr")) - 1) * 16)  # where it meets the floor
    switch = (int(v.group("sx")), int(v.group("sy")))
    exit_sw = (int(e.group("ex")), int(e.group("ey")))
    home = c.pos()

    # 1. the vault is sealed: no path from outside the door to the middle of the room
    crossed, note = walk_in(c, outside, door[1], "sealed")
    c.flag("vault_sealed_blocks_walk", not crossed, note)
    nodes, r = path_into(c, outside, centre)
    c.notes.append(f"sealed pathfind: nodes {nodes} from {outside} to {centre}")
    reach_notes(c, "sealed", world, w, h, outside, centre, corridor_end)
    inside = c.gl("teleport", centre[0], centre[1])
    time.sleep(0.4)
    near = c.gl("near", 90, "chest")
    c.flag("vault_two_chests", near.get("count", 0) == 2, f"count {near.get('count')} within 90 of the centre")

    # 2. the exits are disabled and the HUD asks for the switch
    total, enabled = exits(c)
    c.flag("exits_present", total > 0, f"{total} exit area script(s)")
    c.flag("exits_sealed", total > 0 and enabled == 0, f"{enabled} of {total} enabled")
    c.flag("hud_exit_find", hud_line(c) == EXIT_FIND, repr(hud_line(c)))
    vl = (c.widget("hwp-objective-vaults") or {}).get("text", "")
    c.flag("hud_vaults_0_of_1", vl == "Vaults: 0/1", repr(vl))

    # 3. the vault lever: the host's use path, the broadcast, the door opens
    mark = len(g.read_log())
    c.gl("teleport", switch[0], switch[1] + 20)
    time.sleep(0.4)
    r = c.gl("use", "objective_switch")
    c.flag("vault_switch_used", bool(r.get("ok")) and "objective_switch" in str(r.get("unit", "")), str(r)[:120])
    m = wait_log(c, r"\[HWP:objectives\] vault 0 opened by ", mark)
    c.flag("vault_opened_logged", m is not None, m.group(0) if m else "no 'vault 0 opened by' line")
    m = wait_log(c, r"\[HWP:objectives\] vault 0 doors opened \((\d+) unit\(s\) found of (\d+)\)", mark)
    c.flag("vault_units_found", m is not None and m.group(1) == m.group(2), m.group(0) if m else "no 'doors opened' line")
    time.sleep(0.8)
    crossed, note = walk_in(c, outside, door[1], "open")
    c.flag("vault_open_walk_in", crossed, note)
    nodes, r = path_into(c, outside, centre)
    c.notes.append(f"open pathfind: nodes {nodes} from {outside} to {centre}")
    if nodes <= 0:
        reach_notes(c, "open", world, w, h, outside, centre, corridor_end)
    vl = (c.widget("hwp-objective-vaults") or {}).get("text", "")
    c.flag("hud_vaults_1_of_1", vl == "Vaults: 1/1", repr(vl))
    # a second use does nothing (the lever is spent)
    mark2 = len(g.read_log())
    c.gl("teleport", switch[0], switch[1] + 20)
    time.sleep(0.3)
    c.gl("use", "objective_switch")
    time.sleep(0.8)
    c.flag("vault_switch_spent", "vault 0 opened by" not in g.read_log()[mark2:])

    # 4. the exit lever: exits enabled, the HUD line changes then clears
    mark = len(g.read_log())
    c.gl("teleport", exit_sw[0], exit_sw[1] + 20)
    time.sleep(0.4)
    r = c.gl("use", "objective_exit_switch")
    c.flag("exit_switch_used", bool(r.get("ok")) and "objective_exit_switch" in str(r.get("unit", "")), str(r)[:120])
    m = wait_log(c, r"\[HWP:objectives\] exit opened by ", mark)
    c.flag("exit_opened_logged", m is not None, m.group(0) if m else "no 'exit opened by' line")
    m = wait_log(c, r"\[HWP:objectives\] exits open: (\d+)", mark)
    c.flag("exits_open_logged", m is not None and int(m.group(1)) == total, m.group(0) if m else "no 'exits open' line")
    time.sleep(0.5)
    total2, enabled2 = exits(c)
    c.flag("exits_enabled", total2 > 0 and enabled2 == total2, f"{enabled2} of {total2} enabled")
    c.flag("hud_exit_open", hud_line(c) == EXIT_OPEN, repr(hud_line(c)))
    end = time.time() + 9
    while time.time() < end and hud_line(c) != "":
        time.sleep(0.5)
    c.flag("hud_exit_line_clears", hud_line(c) == "", repr(hud_line(c)))

    # 5. the status command
    reply = c.hwp("objectives", until="Objectives:", timeout=4)
    c.flag("status_reply", "Objectives: 1 vault(s), 1 open; exit switch pressed" in reply, reply.strip()[-200:])
    c.gl("teleport", home[0], home[1])
