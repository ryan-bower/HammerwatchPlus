"""Behavioral Lightning Arrow return/catch regression, not ordinary-play evidence.

Every trial fires one posted skill input and retains its outcome. Normal flight records
target HP before, after the outgoing leg and after the return. The close-wall case moves
only the isolated lab character and accelerates scene time to stress a return step that
can cross the catcher between endpoints. Its raw ray geometry, HP, stack snapshots and
return-hit counts distinguish a missed catch from a premature outbound catch.
"""
import json
import math
import re
import time

from gamelab.bots.plan_specs import Checks, TARGET

ARROW = "hwp_ran_electric_circuit"
WINDS = "hwp_ran_gathering_winds"
CATCH = "hwp_ran_ec_tailwind_catch"
TAILWIND = "players/hwp/specs/stacks_specs.sval:tailwind"


def numbers(text):
    result = {}
    for name in ("circuit returns", "back hits", "catches", "tailwind"):
        found = re.findall(re.escape(name) + r" (-?\d+)", text)
        result[name] = int(found[-1]) if found else None
    return result


def status(checks):
    return numbers(checks.hwp("specs", 0.05, until="specs:", timeout=1.0))


def checkpoint(checks, records, geometry, complete=False):
    """Keep completed trials reviewable even if a later console command fails."""
    target = checks.g.results / "qa-specs-return.partial.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps({"complete": complete, "checks": checks.out, "notes": checks.notes,
                                "trials": records, "fixture_geometry": geometry}, indent=2), encoding="utf-8")
    temp.replace(target)


def ray(checks, direction, distance=350):
    x, y = checks.pos()
    dx, dy = direction
    return checks.gl("rayhit", round(x, 2), round(y, 2),
                     round(x + dx * distance, 2), round(y + dy * distance, 2))


def ready(checks):
    end = time.monotonic() + 45
    while time.monotonic() < end:
        cd = checks.skill_cd(ARROW)
        if cd is not None and cd <= 0:
            return True
        time.sleep(0.25)
    return False


def sample(checks, button, direction, tag, slow=False):
    checks.gl("kill", 700, "target_dummy")
    checks.set_stacks(TAILWIND, 0)
    time.sleep(0.7)  # old speed buffs expire before measuring the next cast
    is_ready = ready(checks)
    checks.flag(tag + "_ready", is_ready, "cooldown is readable and over")
    if not is_ready:
        return {"tag": tag, "setup_failed": "cooldown never became ready"}
    distance = 50 if slow else 22
    dx, dy = direction
    spawn = checks.gl("spawn", TARGET, round(dx * distance, 2), round(dy * distance, 2))
    time.sleep(0.25)
    targets = checks.gl("near", 120, "target_dummy").get("units") or []
    hp0 = checks.dummy_hp("target_dummy")
    mana0 = checks.gl("mana", 250)
    before = status(checks)
    origin = checks.pos()
    clock0 = checks.gl("clock")
    expected_scale = 0.5 if slow else 6
    scale = checks.gl("timescale", expected_scale)
    snapshots = []
    hp_out = {}
    input_reply = {}
    track_tag = "return_" + tag
    track = checks.gl("track", track_tag, 3000, 260, "stormbringer/circuit.unit")
    try:
        # Keep aim held beyond a coarse scene step as well as the castpoint. There is
        # still exactly one Pressed edge, and this hold is shorter than the cooldown.
        hold = 320 if slow else 1200
        input_reply = checks.gl("input", hold, 0, 0, dx, dy, button)
        if slow:
            time.sleep(0.95)
        if slow:
            hp_out = checks.dummy_hp("target_dummy")
            time.sleep(2.7)
        else:
            # The lab runs at about 30 FPS: 6x gives an approximately 60px return
            # step across the measured 45px gap. Restore promptly, before the real
            # four-second Tailwind lifetime, and read at normal console timing.
            checks.gl("timescale", 1)
        for _ in range(4):
            snapshots.append(status(checks))
            time.sleep(0.10)
    finally:
        checks.gl("timescale", 1)
    hp_back = checks.dummy_hp("target_dummy")
    trajectory = checks.g.wait_gl(lambda event: event.get("ev") == "track" and event.get("tag") == track_tag, 8) if track.get("ok") else None
    clock1 = checks.gl("clock")
    after = snapshots[-1] if snapshots else {}
    catch_delta = max((s.get("catches") or 0) - (before.get("catches") or 0) for s in snapshots)
    return_delta = (after.get("circuit returns") or 0) - (before.get("circuit returns") or 0)
    back_delta = (after.get("back hits") or 0) - (before.get("back hits") or 0)
    stack_peak = max(s.get("tailwind") or 0 for s in snapshots)
    setup_ok = bool(spawn.get("ok") and input_reply.get("ok")
                    and len(hp0) == 1 and all(hp > 0 for hp in hp0.values())
                    and scale.get("ok") and scale.get("timescale") == expected_scale
                    and before.get("tailwind") == 0 and all(value is not None for value in before.values())
                    and (mana0.get("now") or 0) >= 50)
    damage = setup_ok and all(hp_back.get(unit, 0.0) < hp - 0.001 for unit, hp in hp0.items())
    checks.flag(tag + "_setup", setup_ok, f"spawn {spawn}; targets {targets}; scale {scale}")
    checks.flag(tag + "_damage", damage, f"target HP {hp0} -> outgoing {hp_out} -> returned {hp_back}")
    checks.flag(tag + "_returned", return_delta == 3 and back_delta >= 1,
                f"returns +{return_delta}, return hits +{back_delta}; {snapshots}")
    checks.flag(tag + "_caught", catch_delta == 3 and stack_peak == 3,
                f"one input: catches +{catch_delta}, actual Tailwind peak {stack_peak}; {snapshots}")
    if slow:
        outgoing = setup_ok and all(hp_out.get(unit, 1.0) < hp - 0.001 for unit, hp in hp0.items())
        returning = outgoing and all(hp_back.get(unit, 0.0) < hp - 0.001 for unit, hp in hp_out.items())
        checks.flag(tag + "_outgoing_damage", outgoing, f"{hp0} -> {hp_out}")
        checks.flag(tag + "_return_damage", returning, f"{hp_out} -> {hp_back}")
    return {"tag": tag, "origin": origin, "aim": direction,
            "geometry": ray(checks, direction), "targets": targets,
            "hp_before": hp0, "hp_outgoing": hp_out, "hp_returned": hp_back,
            "status_before": before, "status_samples": snapshots,
            "clock_before": clock0, "clock_after": clock1, "mana_setup": mana0,
            "mana_after": checks.mana_exact(), "scale_reply": scale, "input_reply": input_reply,
            "track_queue": track, "trajectory": trajectory}


def run(p, trials=3, **_):
    trials = max(1, min(5, int(trials)))
    c = Checks(p)
    records = []
    geometry = {"rays": [], "close_candidates": []}
    c.setup("returnqa", "ranger", "hwp_ranger_stormbringer", [ARROW, WINDS])
    if not c.enter_floor("returnqa"):
        return {**c.out, "notes": c.notes, "trials": records}
    c.gl("orb", CATCH, 1)
    c.flag("returnqa_orb", c.bind(ARROW, "ec-catch") == "1", "Tailwind Catch alone; bind readback")
    button = c.button_for("returnqa_input", ARROW, "skill3")
    scan_origin = c.pos()
    # The entrance has a narrow clear direction between the old eight spokes.
    # Retain a bounded fixture search rather than silently skipping normal flight.
    for index in range(32):
        angle = index * math.pi / 16
        direction = (round(math.cos(angle), 5), round(math.sin(angle), 5))
        geometry["rays"].append({"direction": direction, "ray": ray(c, direction, 450)})
    normal_entry = max(geometry["rays"], key=lambda entry: float(entry["ray"].get("wd") or 0)
                       if entry["ray"].get("wall") else 450)
    normal, normal_ray = normal_entry["direction"], normal_entry["ray"]
    normal_ok = not normal_ray.get("wall") or float(normal_ray.get("wd") or 0) >= 220
    c.flag("returnqa_normal_geometry", normal_ok, str(normal_ray))
    checkpoint(c, records, geometry)
    try:
        if normal_ok:
            for trial in range(1, trials + 1):
                records.append(sample(c, button, normal, f"normal_{trial}", slow=True))
                checkpoint(c, records, geometry)
        c.gl("kill", 700, "target_dummy")
        walls = []
        for entry in geometry["rays"]:
            direction, reading = entry["direction"], entry["ray"]
            distance = float(reading.get("wd") or 0)
            name = reading.get("wname", "")
            if reading.get("wall") and 100 <= distance <= 450 and "crn_" not in name and "_exit" not in name:
                walls.append((distance, direction, reading))
        close_ok = False
        if walls:
            for distance, direction, reading in sorted(walls, reverse=True)[:4]:
                intended = (scan_origin[0] + direction[0] * (distance - 45),
                            scan_origin[1] + direction[1] * (distance - 45))
                moved = c.gl("teleport", round(intended[0], 2), round(intended[1], 2))
                time.sleep(0.3)
                actual = c.pos()
                close_ray = ray(c, direction, 180)
                behind = ray(c, (-direction[0], -direction[1]), 90)
                shift = math.hypot(actual[0] - intended[0], actual[1] - intended[1])
                close_ok = bool(close_ray.get("wall") and 43 <= float(close_ray.get("wd") or 0) <= 47
                                and shift <= 2 and (not behind.get("wall") or float(behind.get("wd") or 0) >= 50))
                geometry["close_candidates"].append({"initial": reading, "aim": direction, "intended": intended,
                                                       "actual": actual, "shift": shift, "teleport": moved,
                                                       "close": close_ray, "behind": behind, "valid": close_ok})
                checkpoint(c, records, geometry)
                if close_ok:
                    break
            c.flag("returnqa_close_geometry", close_ok, str(geometry["close_candidates"]))
            if close_ok:
                for trial in range(1, trials + 1):
                    records.append(sample(c, button, direction, f"close_{trial}"))
                    checkpoint(c, records, geometry)
        else:
            c.flag("returnqa_close_geometry", False, "no measured non-corner/non-exit wall 100..450 px from the lab spawn")
    finally:
        checkpoint(c, records, geometry)
        c.gl("timescale", 1)
        c.g.shot("return qa end", settle=False)
        c.to_town()
    checkpoint(c, records, geometry, complete=True)
    return {**c.out, "notes": c.notes, "trials": records,
            "fixture_geometry": geometry,
            "measurement_only": "isolated fixture, god mode, lab teleport and timescale; no ordinary-play claim"}
