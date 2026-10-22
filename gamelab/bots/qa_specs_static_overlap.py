"""Two actual overlapping Thunder Orb casts with independently measured crits.

Cooldown reset and one100px lab teleport are explicit stress prerequisites. Crit
events, damage and positive stacks are never injected. Negative projectile IDs are
not identity evidence: measured leading/trailing geometry isolates each orb's hits.
"""
import json
import math

from gamelab.bots.qa_specs_wizard_ranks import Checks, TT, SC, STACK, spawn, wait_ready
from gamelab.bots.qa_specs_static_native import assemble_observation, crit_text, hp_falls

PHASES = ("before_first", "before_second", "second_setup", "new_orb_only", "old_orb_only_start", "old_orb_only", "finished")


def orb_geometry(phase, data):
    orbs = phase.get("projectiles") or []
    if len(orbs) != 2:
        return None
    dx, dy = data.get("aim_x", 0), data.get("aim_y", 0)
    ordered = sorted(orbs, key=lambda row: row["x"] * dx + row["y"] * dy)
    return [[math.hypot(target["x"] - orb["x"], target["y"] - orb["y"]) for target in phase.get("targets", [])] for orb in ordered]


def evaluate(data):
    phases = {row.get("phase"): row for row in data.get("phases", [])}
    samples = data.get("samples") or []
    complete = (data.get("complete") is True and not data.get("error") and not data.get("retention_error")
                and not data.get("truncated") and 4800 <= data.get("ms", 0) <= 4950
                and 80 <= data.get("frames", 0) <= 200 and len(samples) == data.get("frames")
                and all(name in phases for name in PHASES))
    results = {"complete": (complete, f"native ms={data.get('ms')} frames={data.get('frames')} error={data.get('error')} retention={data.get('retention_error')}")}
    if not complete:
        return {**results, **{name: (False, "no complete native observation") for name in ("setup", "two_casts", "new_orb_crit", "old_orb_crit", "two_bonuses")}}
    before, pre_second, setup, new, old_start, old, end = [phases[name] for name in PHASES]
    ids = {row.get("unit") for row in before.get("targets", [])}
    stable = len(ids) == 3 and all(
        len(phase.get("targets", [])) == 3 and {row.get("unit") for row in phase["targets"]} == ids
        and all(row.get("valid") and not row.get("dead") and row.get("hpMax") == 15000 and row.get("hpExact", 0) > 0 for row in phase["targets"])
        and phase.get("tt_crit") == 1 and phase.get("spell_crit") == 0 for phase in phases.values())
    controlled = (stable and before.get("stacks") == 0 and not before.get("projectiles") and not before.get("crits")
                  and pre_second.get("stacks") == 1 and not pre_second.get("crits")
                  and data.get("cooldown_before_setup", 0) > 0 and data.get("cooldown_after_setup") == 0
                  and abs(math.hypot(setup.get("player_x", 0) - before.get("player_x", 0), setup.get("player_y", 0) - before.get("player_y", 0)) - 100) <= 1)
    results["setup"] = (controlled, f"stable native15k targets={stable}; no first-orb crit before second cast; cooldown {data.get('cooldown_before_setup')} -> {data.get('cooldown_after_setup')}; actual100px displacement")
    previous, jumps = 0, 0
    for sample in samples:
        current = sample.get("tt_cd", -1)
        jumps += current > previous + 100
        previous = current
    two = (controlled and jumps == 2 and data.get("first_input_frames", 0) >= 2 and data.get("second_input_frames", 0) >= 2
           and data.get("second_input_at", 0) > data.get("first_input_at", 0)
           and pre_second.get("mana", 1e9) < before.get("mana", 0) - 1
           and new.get("mana", 1e9) < setup.get("mana", 0) - 1)
    results["two_casts"] = (two, f"two real input edges/animations and mana costs; native cooldown activations={jumps}; input frames {data.get('first_input_frames')}/{data.get('second_input_frames')}")
    geometry_new = orb_geometry(new, data)
    new_isolated = (geometry_new and len(geometry_new[0]) == 3 and min(geometry_new[0]) > 75
                    and max(geometry_new[1]) < 70)
    new_crit = (two and new_isolated and hp_falls(setup, new, every=True)
                and any(crit_text(row) and row.get("born", 0) > data["second_input_at"] + 200 for row in new.get("crits", []))
                and new.get("stacks") == 3)
    results["new_orb_crit"] = (bool(new_crit), f"older orb outside radius+circle5, newer inside70: distances {geometry_new}; actual numeric critical HP loss; stacks {new.get('stacks')}")
    a, b = orb_geometry(old_start, data), orb_geometry(old, data)
    old_isolated = (a and b and all(len(geometry[0]) == 3 and max(geometry[0]) < 70 and min(geometry[1]) > 85 for geometry in (a, b)))
    old_crit = (two and old_isolated and hp_falls(old_start, old, every=True)
                and any(crit_text(row) and row.get("born", 0) > old_start.get("now", 0) for row in old.get("crits", [])))
    results["old_orb_crit"] = (bool(old_crit), f"older orb inside70, newer outside85 throughout last300ms: {a}->{b}; actual new critical HP loss")
    late = [row.get("stacks") for row in samples if row.get("t", 0) >= 3200]
    correct = new_crit and old_crit and late and all(count == 4 for count in late) and old.get("stacks") == end.get("stacks") == 4
    results["two_bonuses"] = (bool(correct), f"two actual casts + independently proven first crit on each require4 stacks; actual late counts {late}")
    return results


def checkpoint(c, records, complete=False):
    path = c.g.results / "qa-specs-static-overlap.partial.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"complete": complete, "checks": c.out, "notes": c.notes, "trials": records}, indent=2), encoding="utf-8")
    tmp.replace(path)


def clear_overlap_lane(c):
    """Require native350px rays across the orb's full collision width.

    open_dir returns its best fallback when every ray is blocked. That is useful
    for returning arrows, but cannot certify two orbs' late isolated flight.
    A bounded lab relocation toward one room edge can expose a full-diameter lane.
    """
    original, attempts = c.pos(), []

    def probe(origin, direction):
        dx, dy = direction
        readings = c.g.gl_multi([
            ["rayhit", round(origin[0] - dy * side, 3), round(origin[1] + dx * side, 3),
             round(origin[0] - dy * side + dx * 350, 3), round(origin[1] + dx * side + dy * 350, 3)]
            for side in (-8, 0, 8)])
        clear = all(row.get("ok") and row.get("wall") is False and row.get("tile") is False for row in readings)
        attempts.append({"origin": origin, "direction": direction, "rays": readings, "clear": clear})
        return clear, readings

    candidates = []
    for index in range(32):
        angle = index * math.pi / 16
        direction = (round(math.cos(angle), 5), round(math.sin(angle), 5))
        clear, rays = probe(original, direction)
        if clear:
            return original, direction, {"original": original, "attempts": attempts}
        if len(rays) == 3 and rays[1].get("ok"):
            candidates.append((float(rays[1].get("wd") or 0), direction))
    for free, direction in sorted(candidates, reverse=True)[:4]:
        if free < 150:
            continue
        destination = (original[0] + direction[0] * (free - 32), original[1] + direction[1] * (free - 32))
        moved = c.gl("teleport", round(destination[0], 3), round(destination[1], 3))
        actual = c.pos()
        if not moved.get("ok") or math.dist(actual, destination) > 1:
            attempts.append({"relocation": destination, "actual": actual, "reply": moved, "clear": False})
            continue
        opposite = (-direction[0], -direction[1])
        clear, _ = probe(actual, opposite)
        if clear:
            return actual, opposite, {"original": original, "bounded_lab_relocation": destination, "attempts": attempts}
    c.gl("teleport", *original)
    return None, None, {"original": original, "attempts": attempts, "error": "no certified350px collision-width lane"}


def run(p, trials=3, **_):
    c = Checks(p)
    records = []
    c.setup("staticoverlap", "wizard", "hwp_wizard_invocation", [TT, SC], orbs=(("hwp_wiz_tt_lingering_storm", 2),))
    raised = c.gl("skill", TT, 3)
    if not c.enter_floor("staticoverlap"):
        return {**c.out, "notes": c.notes}
    origin, direction, geometry = clear_overlap_lane(c)
    c.out["staticoverlap_geometry"] = geometry
    c.flag("staticoverlap_lane", origin is not None and direction is not None, str(geometry))
    if origin is None:
        checkpoint(c, records, True)
        return {**c.out, "notes": c.notes, "blocked": "no physically certified isolated-flight lane"}
    c.button_for("staticoverlap_input", TT, "skill2")
    c.flag("staticoverlap_rank_radius_lifetime", raised.get("level") == 5 and c.bind(TT, "tt-radius") == "70"
           and c.bind(TT, "tt-ttl") == "3000" and c.bind(TT, "tt-ttl-add") == "2000", "TT5, radius70, natural5s lifetime")
    original = c.gl("skillcrit", TT)
    try:
        for index in range(1, max(1, min(5, int(trials))) + 1):
            c.gl("teleport", *origin)
            is_ready = wait_ready(c)
            before = spawn(c, direction, [(180, -15), (180, 0), (180, 15)])
            c.set_stacks(STACK, 0)
            c.gl("mana", 250)
            crit = c.gl("skillcrit", TT, 1)
            tag = f"overlap_{index}"
            queue = c.gl("qa_static_overlap", tag, direction[0], direction[1])
            final = c.g.wait_gl(lambda event: event.get("ev") == "qa_static_overlap" and event.get("tag") == tag, 15) if queue.get("ok") else None
            data = assemble_observation(c.g.gl, final, PHASES, "qa_overlap") if final else {}
            c.flag(f"overlap_{index}_ready", is_ready and crit.get("crit_chance") == 1 and crit.get("spell_crit_chance") == 0 and queue.get("ok"), f"{crit}; queue {queue}")
            for name, (ok, detail) in evaluate(data).items():
                c.flag(f"overlap_{index}_{name}", bool(ok), detail)
            records.append({"trial": index, "before": before, "crit": crit, "queue": queue, "observation": data})
            c.gl("skillcrit", TT, "restore")
            checkpoint(c, records)
    finally:
        restored = c.gl("skillcrit", TT, "restore")
        final = c.gl("skillcrit", TT)
        c.flag("staticoverlap_restored", restored.get("ok") and not final.get("override_active")
               and final.get("crit_chance") == original.get("crit_chance") and final.get("spell_crit_chance") == original.get("spell_crit_chance"), f"{original}->{restored}->{final}")
        checkpoint(c, records)
        c.gl("timescale", 1)
        c.to_town()
    checkpoint(c, records, True)
    return {**c.out, "notes": c.notes, "trials": records,
            "measurement_only": "two real native inputs/damage/crit paths at1x; native1st cooldown is explicitly reset once and lab player teleported100px for overlapping casts, no ordinary-cooldown claim",
            "not_covered": "non-TT delayed native spell attribution is a separate gap"}
