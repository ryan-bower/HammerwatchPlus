"""Deadeye rank/strike/orb behavior measured from actual inputs and native HP.

Tailwind is earned by killing native1HP fixtures through the real Lightning Arrow
damage path. Its positive measured count is never set by the harness.
"""
import json
import math
import re
import time

from gamelab.bots.plan_specs import Checks
from gamelab.bots.qa_specs_wizard_ranks import spawn, targets, health, target_ok, progression

ARROW, WINDS = "hwp_ran_electric_circuit", "hwp_ran_gathering_winds"
BOOM, ROD = "hwp_ran_ec_charged_boomerang", "hwp_ran_ec_lightning_rod"
STACK = "players/hwp/specs/stacks_specs.sval:tailwind"
FRAGILE = "gamelab/qa_specs_fragile_target_dummy.unit"
FRAGILE_FILTER = "qa_specs_fragile_target_dummy"


def status(c):
    raw = c.specs()
    return {label: (lambda values: int(values[-1]) if values else None)(re.findall(re.escape(label) + r" (-?\d+)", raw))
            for label in ("circuit returns", "back hits", "tailwind", "tailwind kills", "gale arrows")}


def checkpoint(c, rows, complete=False):
    path = c.g.results / "qa-specs-deadeye.partial.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"complete": complete, "checks": c.out, "notes": c.notes, "cases": rows}, indent=2), encoding="utf-8")
    tmp.replace(path)


def ready(c):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        cd = c.skill_cd(ARROW)
        if cd is not None and cd <= 0:
            return True
        time.sleep(0.25)
    return False


def shot(c, direction, offsets, tag):
    is_ready = ready(c)
    before = spawn(c, direction, offsets)
    hp0 = health(before)
    c.gl("mana", 250)
    crit = c.gl("skillcrit", ARROW, 0)
    s0 = status(c)
    fired = c.gl("input", 400, 0, 0, direction[0], direction[1], c.qa_arrow_button)
    time.sleep(1.8)
    after = targets(c)
    hp1 = health(after)
    s1 = status(c)
    setup = (is_ready and target_ok(before, len(offsets)) and target_ok(after, len(offsets)) and fired.get("ok")
             and crit.get("crit_chance") == 0 and crit.get("spell_crit_chance") == 0)
    drops = {unit: hp0[unit] - hp1.get(unit, hp0[unit]) for unit in hp0}
    c.flag(tag + "_setup", bool(setup), f"ready {is_ready}, native15k targetHP {before}, crit {crit}, actual input {fired}")
    c.flag(tag + "_returned", bool(setup and s1["circuit returns"] - s0["circuit returns"] == 3
           and s1["back hits"] > s0["back hits"]), f"native return/hit observations {s0}->{s1}; HP {hp0}->{hp1}")
    return {"tag": tag, "before": before, "after": after, "damage": drops, "offsets": offsets,
            "input": fired, "crit": crit, "status_before": s0, "status_after": s1,
            "mean_damage": sum(drops.values()) / len(drops) if drops else None}


def earn(c, direction, tag):
    c.gl("kill", 600, "target_dummy")
    c.set_stacks(STACK, 0)
    time.sleep(0.7)
    is_ready = ready(c)
    dx, dy = direction
    spawned = [c.gl("spawn", FRAGILE, round(dx * (20 + i * 5), 3), round(dy * (20 + i * 5), 3)) for i in range(25)]
    before = c.gl("actorbuffs", 250, FRAGILE_FILTER).get("actors") or []
    c.gl("mana", 250)
    c.gl("skillcrit", ARROW, 0)
    s0 = status(c)
    clock0 = c.gl("clock")
    fired = c.gl("input", 400, 0, 0, dx, dy, c.qa_arrow_button)
    time.sleep(0.6)
    s1 = status(c)
    after = c.gl("near", 250, FRAGILE_FILTER).get("units") or []
    live = [row for row in after if not row.get("dead") and row.get("hp", 1) > 0]
    good = (is_ready and all(row.get("ok") for row in spawned) and len(before) == 25
            and all(row.get("hpMax") == 1 and row.get("hpExact") == 1 for row in before)
            and fired.get("ok") and not live and s0["tailwind"] == 0 and s1["tailwind"] == 5
            and s1["tailwind kills"] - s0["tailwind kills"] == 25)
    c.flag(tag + "_earned", bool(good), f"actual25 native1HP targets, live after {live}; input {fired}; kill/stack reads {s0}->{s1}")
    return {"tag": tag, "setup": before, "after": after, "input": fired, "clock_before_input": clock0,
            "status_before": s0, "status_after": s1, "valid": good}


def run(p, **_):
    c = Checks(p)
    rows, arrow_rows, boom_rows = [], [], []
    c.setup("deadeyeqa", "ranger", "hwp_ranger_stormbringer", [])
    if not c.enter_floor("deadeyeqa"):
        return {**c.out, "notes": c.notes}
    c.gl("timescale", 1)
    direction = c.open_dir(300)
    c.qa_arrow_button = c.button_for("deadeyeqa_input", ARROW, "skill2")
    original = c.gl("skillcrit", ARROW)
    failed = False
    try:
        for rank in range(1, 6):
            if rank > 1:
                c.gl("skill", ARROW, 1)
                c.gl("skill", WINDS, 1)
            levels = {skill: c.gl("skill", skill, 0).get("level") for skill in (ARROW, WINDS)}
            c.flag(f"deadeye_rank_{rank}_levels", levels == {ARROW: rank, WINDS: rank}, str(levels))
            c.set_stacks(STACK, 0)
            time.sleep(0.7)
            row = shot(c, direction, [(50, 0)], f"arrow_rank_{rank}")
            arrow_rows.append(row)
            rows.append(row)
            checkpoint(c, rows)
            baseline = c.gl("benchstats")
            earned = earn(c, direction, f"winds_rank_{rank}")
            boosted = c.gl("benchstats")
            ratio = 1 + 5 * (0.02, 0.025, 0.03, 0.035, 0.04)[rank - 1]
            speeds = {key: boosted.get(key, 0) / max(0.001, baseline.get(key, 0)) for key in ("castSpeed", "moveSpeed", "mhSpeed")}
            c.flag(f"winds_rank_{rank}_speeds", earned["valid"] and all(abs(value - ratio) < 0.004 for value in speeds.values()),
                   f"actual native move/cast/weapon speeds {baseline}->{boosted}; ratios {speeds}, source {ratio}")
            time.sleep(4.6)
            expired, s_end = c.gl("benchstats"), status(c)
            c.flag(f"winds_rank_{rank}_expired", s_end["tailwind"] == 0
                   and all(abs(expired.get(key, 0) - baseline.get(key, 0)) < 0.004 for key in speeds),
                   f"actual stacks and native speed stats after natural4s expiry {s_end}; {expired}")
            rows.append({**earned, "source_speed_ratio": ratio, "baseline": baseline, "boosted": boosted, "expired": expired})
            checkpoint(c, rows)
        progression(c, arrow_rows, (40, 50, 60, 70, 80), "arrow_rank_damage_progression")
        # Lone target: Boomerang adds two strikes to each leg as well as its return
        # multiplier. These expected totals are independently specified source damage.
        boom_rows.append(arrow_rows[-1])
        for quality in (1, 2):
            equipped = c.gl("orb", BOOM, 1)
            c.flag(f"boom_rank_{quality}_equipped", equipped.get("level") == quality, str(equipped))
            row = shot(c, direction, [(50, 0)], f"boom_rank_{quality}")
            boom_rows.append(row)
            rows.append(row)
        progression(c, boom_rows, (80, 176, 192), "boom_lone_return_damage")
        c.gl("orb", BOOM, "down")
        c.gl("orb", BOOM, "down")
        for quality, radius in enumerate((60, 69, 75, 84)):
            equipped = c.gl("orb", ROD, 1 if quality else 0)
            c.flag(f"rod_rank_{quality}_equipped", equipped.get("level") == quality, str(equipped))
            # All six neighbors are behind the player, beyond initial/return arrow
            # contact, but within60px of the primary. Only lightning can hit them.
            row = shot(c, direction, [(30, 0)] + [(-20, side) for side in (-5, -3, -1, 1, 3, 5)], f"rod_count_{quality}")
            x, y = c.pos()
            dx, dy = direction
            neighbors = [unit for unit, target in row["before"].items() if (target["x"] - x) * dx + (target["y"] - y) * dy < -10]
            hits = [unit for unit in neighbors if row["damage"].get(unit, 0) > 0.1]
            c.flag(f"rod_rank_{quality}_target_count", len(neighbors) == 6 and len(hits) == quality + 2,
                   f"source extra-target count {quality + 2}; actual isolated secondary HP changes {hits}; allHP {row['damage']}")
            rows.append(row)
            row = shot(c, direction, [(30, 0), (30 - radius + 1, 0), (30 - radius - 8, 0)], f"rod_radius_{quality}")
            units = list(row["before"].values())
            primary = max(units, key=lambda target: (target["x"] - x) * dx + (target["y"] - y) * dy)
            neighbors = [{"unit": target["unit"], "distance": math.hypot(target["x"] - primary["x"], target["y"] - primary["y"]),
                          "damage": row["damage"].get(target["unit"], 0)} for target in units if target["unit"] != primary["unit"]]
            inner = [target for target in neighbors if target["distance"] < radius]
            outer = [target for target in neighbors if target["distance"] > radius + 5]
            c.flag(f"rod_rank_{quality}_radius", len(inner) == len(outer) == 1 and inner[0]["damage"] > 0.1 and outer[0]["damage"] == 0,
                   f"source radius {radius}, actual circle5 target geometry and HP {neighbors}")
            rows.append({**row, "source_radius": radius, "measured_geometry": neighbors})
            checkpoint(c, rows)
    except Exception as exc:
        failed = True
        c.notes.append("Deadeye first failure: " + repr(exc))
        checkpoint(c, rows)
        raise
    finally:
        # A transport/setup failure may leave a native resource-error dialog.
        # More console cleanup calls would mask the first error (050849 c42).
        # The isolated runner owns teardown; never drive past that failure.
        if failed:
            checkpoint(c, rows)
        else:
            restored = c.gl("skillcrit", ARROW, "restore")
            final = c.gl("skillcrit", ARROW)
            c.flag("deadeyeqa_crit_restored", restored.get("ok") and not final.get("override_active")
                   and final.get("crit_chance") == original.get("crit_chance")
                   and final.get("spell_crit_chance") == original.get("spell_crit_chance"), f"{original}->{restored}->{final}")
            checkpoint(c, rows)
            c.gl("timescale", 1)
            c.to_town()
    checkpoint(c, rows, True)
    return {**c.out, "notes": c.notes, "cases": rows,
            "expected_source": ["mods/specs/players/hwp/specs/stormbringer/electric_circuit.sval", "mods/specs/players/hwp/specs/stormbringer/gathering_winds.sval", "mods/specs/scripts/HWP/Specs/Stormbringer.as"],
            "not_covered": ["Gale Force", "Wind Ward", "Tailwind Catch is a separate regression"],
            "measurement_only": "native1HP/15k fixtures, god mode, prerequisite zero stacks, bounded native crit setup; actual posted Lightning Arrow input, native target HP and speed/expiry observations at1x"}
