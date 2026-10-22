"""Arcane rank/Far Step behavior from real Blink input, native HP and resources.

The temporary crit fixture is setup only. No damage, heal or measured event is
injected. Resource timers are bracketed by native scene clocks, not wall time.
"""
import json
import math
import time

from gamelab.bots.plan_specs import Checks
from gamelab.bots.qa_specs_wizard_ranks import spawn, targets, health, target_ok, progression

BLINK = "hwp_sor_blink"
MANA = "hwp_sor_living_mana"
FAR = "hwp_sor_bl_far_step"
DAMAGE = (25, 30, 35, 40, 50)
RADIUS = (20, 20, 25, 25, 30)
REGEN = (0.5, 0.75, 1.0, 1.25, 1.5)


def blink_lanes(terrain):
    """Grid-clear144px corridors wide enough for native rays and radius targets."""
    rows, size, step = terrain.get("rows") or [], terrain.get("size", 0), terrain.get("step", 8)
    if size < 3 or len(rows) != size or any(len(row) != size for row in rows) or step <= 0:
        return []
    center = size // 2
    cells = sorted(((x, y) for y in range(size) for x in range(size)),
                   key=lambda cell: ((cell[0]-center)**2 + (cell[1]-center)**2, cell[1], cell[0]))
    result = []
    for x, y in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            valid = True
            for forward in range(-16, 145, 8):
                for side in range(-48, 49, 8):
                    ix = x + round((dx * forward - dy * side) / step)
                    iy = y + round((dy * forward + dx * side) / step)
                    if not (0 <= ix < size and 0 <= iy < size and rows[iy][ix] != "#"):
                        valid = False
                        break
                if not valid:
                    break
            if valid:
                result.append(((x-center)*step, (y-center)*step, dx, dy))
        if len(result) >= 16:
            break
    return result


def certified_lane(c):
    """Explicit bounded lab relocation, then native three-wide collision readback."""
    original = c.pos()
    terrain = c.gl("terrain", 240, 8)
    attempts = []
    for x, y, dx, dy in blink_lanes(terrain)[:16]:
        destination = (original[0] + x, original[1] + y)
        moved = c.gl("teleport", *destination)
        actual = c.pos()
        if not moved.get("ok") or math.dist(actual, destination) > 1:
            attempts.append({"intended": destination, "actual": actual, "reply": moved})
            continue
        rays = c.g.gl_multi([
            ["rayhit", actual[0] - dy * side, actual[1] + dx * side,
             actual[0] - dy * side + dx * 144, actual[1] + dx * side + dy * 144]
            for side in (-12, 0, 12)])
        valid = len(rays) == 3 and all(row.get("ok") and row.get("wall") is False and row.get("tile") is False for row in rays)
        attempts.append({"intended": destination, "actual": actual, "rays": rays, "clear": valid})
        if valid:
            return actual, (dx, dy), {"terrain": terrain, "attempts": attempts,
                                     "native_teleport_ray_width": 9, "verified_width": 24,
                                     "verified_corridor_half_width": 48, "verified_length": 144}
    c.gl("teleport", *original)
    return None, None, {"terrain": terrain, "attempts": attempts, "error": "no physically certified Blink landing/target corridor"}


def record(c, rows, complete=False):
    path = c.g.results / "qa-specs-arcane-ranks.partial.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"complete": complete, "checks": c.out, "notes": c.notes, "cases": rows}, indent=2), encoding="utf-8")
    tmp.replace(path)


def state_at(c):
    start = c.gl("clock").get("sceneMs")
    player = c.gl("state").get("player", {})
    end = c.gl("clock").get("sceneMs")
    return {"start": start, "end": end, "player": player}


def recovery(c, amount):
    c.gl("mana", amount)
    time.sleep(0.35)  # Living Mana reads its changed rank binds every250scene ms.
    a = state_at(c)
    time.sleep(3)
    b = state_at(c)
    gain = b["player"].get("manaExact", 0) - a["player"].get("manaExact", 0)
    lo_ms = (b["start"] or 0) - (a["end"] or 0)
    hi_ms = (b["end"] or 0) - (a["start"] or 0)
    valid = gain > 0 and 2000 <= lo_ms <= hi_ms <= 6000
    bounds = (gain * 1000 / hi_ms, gain * 1000 / lo_ms) if valid else None
    missing = 1 - (a["player"].get("manaExact", 0) + b["player"].get("manaExact", 0)) / (2 * max(1, a["player"].get("manaMax", 1)))
    mirrored = all(abs(point["player"].get("hp", 0) / max(1, point["player"].get("hpMax", 1))
                       - point["player"].get("manaExact", 0) / max(1, point["player"].get("manaMax", 1))) < 0.02 for point in (a, b))
    return {"before": a, "after": b, "gain": gain, "rate_bounds": bounds, "missing": missing,
            "valid": valid, "mirrored": mirrored}


def blink(c, origin, direction, tag, radius, expected_distance):
    c.gl("kill", 600, "qa_class_target_dummy")
    c.gl("teleport", *origin)
    time.sleep(0.2)
    end = time.monotonic() + 15
    while time.monotonic() < end:
        cd = c.skill_cd(BLINK)
        if cd is not None and cd <= 0:
            break
        time.sleep(0.3)
    p0 = c.pos()
    before = spawn(c, direction, [(expected_distance, side) for side in (0, radius - 1, -radius - 8)])
    hp0 = health(before)
    c.gl("mana", 10000)
    crit = c.gl("skillcrit", BLINK, 0)
    mana0 = c.gl("state").get("player", {}).get("manaExact", 0)
    fired = c.gl("input", 400, 0, 0, direction[0], direction[1], c.qa_blink_button)
    time.sleep(0.65)
    p1 = c.pos()
    after = targets(c)
    hp1 = health(after)
    moved = math.dist(p0, p1)
    geometry = [{"unit": unit, "distance": math.hypot(row["x"] - p1[0], row["y"] - p1[1]),
                 "damage": hp0[unit] - hp1.get(unit, hp0[unit])} for unit, row in before.items()]
    inner = [row for row in geometry if row["distance"] < radius]
    outer = [row for row in geometry if row["distance"] > radius + 5]
    setup = (target_ok(before, 3) and target_ok(after, 3) and fired.get("ok")
             and crit.get("crit_chance") == 0 and crit.get("spell_crit_chance") == 0)
    c.flag(tag + "_setup", bool(setup), f"native15kHP, actual crit controls {crit}, native input {fired}")
    c.flag(tag + "_distance", bool(setup and abs(moved - expected_distance) <= 1),
           f"actual position {p0}->{p1}, distance {moved}, native Teleport95% endpoint {expected_distance}")
    c.flag(tag + "_damage_radius", bool(setup and len(inner) == 2 and len(outer) == 1
           and all(row["damage"] > 0.1 for row in inner) and outer[0]["damage"] == 0),
           f"native target circle5, source radius {radius}, observed HP geometry {geometry}")
    drops = [row["damage"] for row in inner]
    return {"tag": tag, "origin": p0, "landing": p1, "distance": moved, "source_distance": expected_distance,
            "before": before, "after": after, "geometry": geometry, "input": fired, "crit": crit,
            "mana_before": mana0, "mana_after": c.gl("state").get("player", {}).get("manaExact"),
            "mean_damage": sum(drops) / len(drops) if drops else None}


def run(p, **_):
    c = Checks(p)
    cases, ranks, regen = [], [], []
    char, _, _ = c.new_char("sorcerer", "LabArcaneRanks")
    initial = c.gl("state").get("player", {})
    c.flag("arcqa_char", char.get("ok") and initial.get("class") == "sorcerer" and initial.get("level", 0) >= 20, str(initial))
    took = c.gl("subclass", "hwp_sorcerer_arcane")
    c.hwp("skillpoints 80")
    levels = {skill: c.gl("skill", skill, 0).get("level") for skill in (BLINK, MANA)}
    c.flag("arcqa_learned", took.get("class") == "hwp_sorcerer_arcane" and levels == {BLINK: 1, MANA: 1}, str(levels))
    time.sleep(0.3)
    converted = c.gl("state").get("player", {})
    c.flag("arcqa_max_mana", abs(converted.get("manaMax", 0) - initial.get("manaMax", 0) - initial.get("hpMax", 0)) <= 1,
           f"native before subclass {initial}; after Living Mana {converted}")
    if not c.enter_floor("arcqa"):
        return {**c.out, "notes": c.notes}
    c.god(True)
    c.gl("timescale", 1)
    origin, direction, geometry = certified_lane(c)
    c.out["arcqa_geometry"] = geometry
    c.flag("arcqa_lane", origin is not None and direction is not None, str(geometry))
    if origin is None:
        record(c, cases, True)
        return {**c.out, "notes": c.notes, "blocked": "no physically certified Blink fixture corridor"}
    c.qa_blink_button = c.button_for("arcqa_blink", BLINK, "skill2")
    original = c.gl("skillcrit", BLINK)
    try:
        for rank in range(1, 6):
            if rank > 1:
                c.gl("skill", BLINK, 1)
                c.gl("skill", MANA, 1)
            levels = {skill: c.gl("skill", skill, 0).get("level") for skill in (BLINK, MANA)}
            c.flag(f"arc_rank_{rank}_levels", levels == {BLINK: rank, MANA: rank}
                   and float(c.bind(MANA, "lm-regen") or -1) == REGEN[rank - 1], str(levels))
            row = blink(c, origin, direction, f"blink_rank_{rank}", RADIUS[rank - 1], 90 * 0.95)
            ranks.append(row)
            cases.append(row)
            c.gl("kill", 600, "qa_class_target_dummy")
            low = recovery(c, 30)
            high = recovery(c, converted.get("manaMax", 0) * 0.75)
            valid = low["valid"] and high["valid"] and low["mirrored"] and high["mirrored"]
            c.flag(f"mana_rank_{rank}_recovery", bool(valid), f"native clock-bounded low/high recovery {low}; {high}")
            row = {"tag": f"mana_rank_{rank}", "factor": REGEN[rank - 1], "low": low, "high": high}
            regen.append(row)
            cases.append(row)
            record(c, cases)
        progression(c, ranks, DAMAGE, "blink_rank_damage_progression")
        # The common baseline regeneration/converted native health regeneration
        # cancels when comparing the two mana fractions at the same skill rank.
        intervals = []
        for row in regen:
            a, b = row["low"], row["high"]
            factor = row["factor"] * (a["missing"] - b["missing"])
            if a["rate_bounds"] and b["rate_bounds"] and factor > 0:
                intervals.append(((a["rate_bounds"][0] - b["rate_bounds"][1]) / factor,
                                  (a["rate_bounds"][1] - b["rate_bounds"][0]) / factor))
        common_lo = max((lo for lo, _ in intervals), default=1)
        common_hi = min((hi for _, hi in intervals), default=0)
        strongest = regen[-1]
        positive = (strongest["low"]["rate_bounds"] and strongest["high"]["rate_bounds"]
                    and strongest["low"]["rate_bounds"][0] > strongest["high"]["rate_bounds"][1])
        c.flag("mana_rank_regen_progression", bool(len(intervals) == 5 and common_lo <= common_hi and common_hi > 0 and positive),
               f"rank factors {REGEN}; compatible native baseline-mana-regen intervals {intervals}; positive rank5 missing-mana effect={positive}")
        for quality, extra in enumerate((0.15, 0.25, 0.35), 1):
            equipped = c.gl("orb", FAR, 1)
            c.flag(f"far_rank_{quality}_equipped", equipped.get("level") == quality, str(equipped))
            cases.append(blink(c, origin, direction, f"far_rank_{quality}", 30, 90 * (1 + extra) * 0.95))
            record(c, cases)
    finally:
        restored = c.gl("skillcrit", BLINK, "restore")
        final = c.gl("skillcrit", BLINK)
        c.flag("arcqa_crit_restored", restored.get("ok") and not final.get("override_active")
               and final.get("crit_chance") == original.get("crit_chance")
               and final.get("spell_crit_chance") == original.get("spell_crit_chance"), f"{original}->{restored}->{final}")
        record(c, cases)
        c.gl("timescale", 1)
        c.to_town()
    record(c, cases, True)
    return {**c.out, "notes": c.notes, "cases": cases,
            "expected_source": ["mods/specs/players/hwp/specs/arcane/blink.sval", "mods/specs/players/hwp/specs/arcane/living_mana.sval", "mods/specs/scripts/HWP/Specs/Arcane.as"],
            "not_covered": ["Void Barrier", "Arcane Feedback", "Mana Conduit teammate behavior"],
            "measurement_only": "fresh15k fixtures, god mode, prerequisite mana setup, lab teleport and bounded native crit control; actual Blink input and native HP/position/resource observations at1x"}
