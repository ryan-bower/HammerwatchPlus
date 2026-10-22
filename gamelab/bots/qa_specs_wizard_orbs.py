"""Native1x Wizard orb effects, with fixed retained trials and real spell inputs.

The single-target HP observer sees complete native zap groups. Expected damage
uses the pinned two-stage damage_round pipeline, including integer quantization.
Prerequisite casts may reset cooldowns; measured positive stacks are never set.
"""
import json
import time

from gamelab.bots.plan_specs import Checks
from gamelab.bots.qa_observe import collect
from gamelab.bots.qa_specs_wizard_ranks import TT, SC, MM, STACK, PROJECTILE, spawn, wait_ready

FOCAL = "hwp_wiz_tt_overcharge"
CLAP = "hwp_wiz_tt_thunderclap"
FONT = "hwp_wiz_sc_static_channel"
CONDUIT = "hwp_wiz_sc_conduit"


def rounded(value):
    # Behaviors/Armor.as damage_round: positive int(f+.5), with minimum1.
    return 0 if value == 0 else max(1, int(value + .5))


def pulse_damage(coefficient, per, index):
    return sum(rounded(rounded(10 * (1 + per * min(index * 3 + zap, 10))) * coefficient)
               for zap in range(3))


def hp_pulses(observation):
    pulses = []
    for before, after in zip(observation.get("events", []), observation.get("events", [])[1:]):
        if not before.get("target_valid") or not after.get("target_valid"):
            continue
        damage = before.get("target_hpExact", -1) - after.get("target_hpExact", -1)
        if damage > .01:
            pulses.append({"now": after["now"], "elapsed": after["elapsed"], "damage": damage})
    return pulses


def matching_coefficients(cases, candidates=None):
    candidates = candidates if candidates is not None else (k / 2000 for k in range(1, 20001))
    return [coefficient for coefficient in candidates
            if all(len(case["pulses"]) >= 6 and all(
                abs(row["damage"] - pulse_damage(coefficient, case["per"], index)) <= .025
                for index, row in enumerate(case["pulses"])) for case in cases)]


def checkpoint(c, rows, complete=False):
    path = c.g.results / "qa-specs-wizard-orbs.partial.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"complete": complete, "checks": c.out, "notes": c.notes, "cases": rows}, indent=2), encoding="utf-8")
    tmp.replace(path)


def orb_off(c, skill):
    for _ in range(3):
        c.gl("orb", skill, "down")


def pulse_trial(c, direction, tag):
    ready = wait_ready(c)
    before = spawn(c, direction, [(85, 0)])
    uid = next(iter(before), None)
    c.set_stacks(STACK, 0)
    c.gl("mana", 250)
    crit = c.gl("skillcrit", TT, 0)
    old = c.gl("unitsof", PROJECTILE).get(PROJECTILE, {}).get("units", [])
    if uid is None:
        return {"tag": tag, "valid": False, "pulses": [], "error": "no fresh target"}
    queued, track, fired = c.g.gl_multi([
        ["buffobserve", tag, 4200, "-", STACK, uid],
        ["track", tag + ".orb", 4200, 300, "invocation/torrent.unit"],
        ["input", 600, 0, 0, *direction, c.qa_tt_button],
    ])
    observation = collect(c.g, tag, 10)
    trajectory = c.g.wait_gl(lambda row: row.get("ev") == "track" and row.get("tag") == tag + ".orb", 3) or {}
    remaining = c.gl("unitsof", PROJECTILE).get(PROJECTILE, {}).get("units", [])
    final_crit = c.gl("skillcrit", TT)
    pulses = hp_pulses(observation)
    tracks = trajectory.get("tracks", [])
    initial = (observation.get("events") or [{}])[0]
    final = (observation.get("events") or [{}])[-1]
    valid = (ready and len(before) == 1 and before[uid].get("hpMax") == 15000
             and before[uid].get("hpExact") == 15000 and not old and not remaining
             and queued.get("ok") and track.get("ok") and fired.get("ok") and observation.get("usable")
             and initial.get("target_hpMax") == final.get("target_hpMax") == 15000
             and initial.get("target_hpExact") == 15000 and final.get("target_hpExact", 0) > 0
             and crit.get("crit_chance") == final_crit.get("crit_chance") == 0
             and crit.get("spell_crit_chance") == final_crit.get("spell_crit_chance") == 0
             and trajectory.get("most") == 1 and not trajectory.get("truncated") and len(tracks) == 1
             and 2900 <= tracks[0].get("t1", 0) - tracks[0].get("t0", 0) <= 3100
             and len(pulses) >= 6)
    return {"tag": tag, "valid": bool(valid), "before": before, "crit": crit, "final_crit": final_crit,
            "observer_queue": queued, "track_queue": track, "input": fired, "observation": observation,
            "trajectory": trajectory, "pulses": pulses, "total_damage": sum(row["damage"] for row in pulses)}


def charged(c, direction, tag, prerequisite_skill=TT):
    if prerequisite_skill != TT:
        wait_ready(c)
    c.gl("kill", 600, "target_dummy")
    c.set_stacks(STACK, 0)
    c.gl("skillcrit", TT, 0)
    casts = []
    for _ in range(5):
        c.gl("mana", 250)
        casts.append(c.gl("castat", prerequisite_skill, *direction, "nocd"))
        time.sleep(.65)
    time.sleep(4)
    old = c.gl("unitsof", PROJECTILE).get(PROJECTILE, {}).get("units", [])
    stacks = c.specs()
    c.flag(tag + "_earned", all(row.get("activated") for row in casts) and "static charge 5" in stacks and not old,
           f"five real prerequisite casts {casts}; actual stacks {stacks}; old producers {old}")
    return {"casts": casts, "status": stacks, "old": old}


def impact(c, direction, tag, skill, mana=90):
    before = spawn(c, direction, [(60, -20), (60, 0), (60, 20)])
    c.gl("mana", mana)
    queued = c.gl("qa_spec_impact", tag, skill, *direction)
    data = c.g.wait_gl(lambda row: row.get("ev") == "qa_spec_impact" and row.get("tag") == tag, 8) if queued.get("ok") else {}
    data = data or {}
    initial, first, after = (data.get(key) or {} for key in ("before", "first", "after"))
    ids = set(before)
    phases = (initial, first, after)
    controlled = (len(ids) == 3 and all({row.get("unit") for row in phase.get("targets", [])} == ids
                  and phase.get("skill_crit") == phase.get("spell_crit") == 0 for phase in phases))
    first_hp = {r.get("unit"): r.get("hpExact", 15000) for r in first.get("targets", [])}
    # Static release happens at cast start. Its first HP event precedes normal
    # mana payment/primary effects, so first.mana cannot prove cast completion.
    primary_hit = any(r.get("hpExact", 15000) < first_hp.get(r.get("unit"), 0) - .1
                      for r in after.get("targets", []))
    valid = (queued.get("ok") and data.get("complete") and not data.get("error") and not data.get("truncated")
             and data.get("input_frames", 0) >= 2 and controlled and initial.get("stacks") == 5
             and first.get("stacks") == after.get("stacks") == 0
             and after.get("cooldown", 0) > 0 and primary_hit
             and all(row.get("hpExact") == 15000 for row in initial.get("targets", []))
             and all(row.get("hpMax") == 15000 and row.get("hpExact", 0) > 0 for phase in phases for row in phase.get("targets", []))
             and all(row.get("hpExact", 15000) < 15000 for row in first.get("targets", [])))
    return {"tag": tag, "valid": bool(valid), "queued": queued, "native": data,
            "mana_change": after.get("mana", 0) - initial.get("mana", 0)}



def cast_window(data):
    """Independent native cast-start/end/primary-producer brackets, not cooldown arithmetic."""
    rows = data.get("cast_trace") or []
    bad = (not isinstance(rows, list) or not 3 <= len(rows) <= 32
           or data.get("cast_trace_truncated") is not False
           or len(rows) != data.get("frames"))
    if bad:
        return {"valid": False, "reason": "missing/capped/incomplete native cast trace", "rows": rows}
    if any(not isinstance(r.get("now"), int) or not 0 < r.get("dt", 0) <= 100 for r in rows):
        return {"valid": False, "reason": "invalid native clock/frame delta", "rows": rows}
    if any(b["now"] < a["now"] for a, b in zip(rows, rows[1:])):
        return {"valid": False, "reason": "native clock moved backwards", "rows": rows}
    active = [i for i, r in enumerate(rows) if r.get("ct", -2) >= 0]
    if not active or active != list(range(active[0], active[-1] + 1)):
        return {"valid": False, "reason": "no single contiguous actual cast", "rows": rows}
    lo, hi = active[0], active[-1]
    if lo == 0 or hi + 1 >= len(rows) or rows[lo-1].get("ct") != -1 or rows[hi+1].get("ct") != -1:
        return {"valid": False, "reason": "native idle/cast/idle brackets missing", "rows": rows}
    born = next((i for i, r in enumerate(rows) if r.get("pc", 0) > 0), None)
    if born is None or born == 0 or any(r.get("pc", 0) not in (0, 1) for r in rows):
        return {"valid": False, "reason": "actual fresh single TT producer missing/ambiguous", "rows": rows}
    # The native timeline executes cast at150; Deactivate at600 resetsct/tl.
    progressed = all(b.get("ct", -1) > a.get("ct", -1) for a, b in zip(rows[lo:hi+1], rows[lo+1:hi+1]))
    timeline = any(r.get("tl", -1) >= 150 for r in rows[lo:hi+1])
    completed = rows[hi+1].get("cd", 0) > 0
    start = [rows[lo-1]["now"], rows[lo]["now"]]
    finish = [rows[hi]["now"], rows[hi+1]["now"]]
    spawn = [rows[born-1]["now"], rows[born]["now"]]
    duration = [finish[0] - start[1], finish[1] - start[0]]
    primary = [spawn[0] - start[1], spawn[1] - start[0]]
    valid = (progressed and timeline and completed and 0 < duration[0] <= duration[1]
             and 0 <= primary[0] <= primary[1] <= duration[1])
    return {"valid": bool(valid), "start": start, "finish": finish, "primary_spawn": spawn,
            "duration_ms": duration, "primary_delay_ms": primary, "rows": rows}


def overlaps(a, b):
    return len(a) == len(b) == 2 and max(a[0], b[0]) <= min(a[1], b[1])

def run(p, section="orb_damage", **_):
    c = Checks(p)
    rows = []
    c.setup("wizorbs", "wizard", "hwp_wizard_invocation", [])
    if not c.enter_floor("wizorbs"):
        return {**c.out, "notes": c.notes}
    c.gl("timescale", 1)
    direction = c.open_dir(300)
    c.qa_tt_button = c.button_for("wizorbs_input", TT, "skill3")
    rank = c.gl("skill", TT, 4)
    c.flag("wizorbs_rank5", rank.get("level") == 5, str(rank))
    original = c.gl("skillcrit", TT)
    try:
        if section == "orb_damage":
            controls, focal = [], []
            for quality, per in enumerate((0, .04, .07)):
                equipped = c.gl("orb", FOCAL, 1 if quality else 0)
                c.flag(f"focal_{quality}_equipped", equipped.get("level") == quality, str(equipped))
                for trial in range(1, 4):
                    row = pulse_trial(c, direction, f"focal_{quality}_{trial}")
                    row.update(orb=FOCAL, rank=quality, per=per)
                    models = matching_coefficients([row]) if row["valid"] else []
                    c.flag(f"focal_{quality}_{trial}_native_curve", row["valid"] and bool(models),
                           f"source+{per} per earlier zap capped10; actual pulses {row['pulses']}; compatible native coefficient interval {models[:1]}..{models[-1:]}")
                    (focal if quality else controls).append(row)
                    rows.append(row)
                    checkpoint(c, rows)
            coefficients = matching_coefficients(controls + focal)
            c.flag("focal_common_native_model", len(controls) == 3 and len(focal) == 6 and all(row["valid"] for row in controls + focal) and bool(coefficients),
                   f"all9 actual native curves share a coefficient under pinned Damage then PlayerBase integer rounding: {coefficients[:1]}..{coefficients[-1:]}")
            orb_off(c, FOCAL)
            equipped = c.gl("orb", CLAP, 1)
            c.flag("clap_equipped", equipped.get("level") == 1, str(equipped))
            plain = controls[0]["pulses"][0]["damage"] if controls and controls[0]["pulses"] else 0
            extras = sorted({rounded(rounded(10 * 1.5) * coefficient) for coefficient in coefficients})
            for trial in range(1, 4):
                row = pulse_trial(c, direction, f"clap_{trial}")
                fits = [(count, extra) for count in range(6, 15) for extra in extras
                        if abs(row.get("total_damage", 0) - count * plain - extra) <= .04]
                last = row["pulses"][-1] if row["pulses"] else {}
                ok = (row["valid"] and plain > 0 and bool(coefficients) and bool(fits)
                      and last.get("elapsed", 0) >= 3000)
                c.flag(f"clap_{trial}_natural_expiry_extra_damage", bool(ok),
                       f"actual native3s producer lifetime and last hit {last}; totalHP {row.get('total_damage')}; body group {plain}; expected150% single-zap extra {extras}; fits {fits}")
                row.update(orb=CLAP, rank=1, expected_extras=extras, matching_period_counts=fits)
                rows.append(row)
                checkpoint(c, rows)
        elif section == "charge_orbs":
            font_rows = []
            for quality, share in enumerate((0, .1, .2)):
                equipped = c.gl("orb", FONT, 1 if quality else 0)
                c.flag(f"font_{quality}_equipped", equipped.get("level") == quality, str(equipped))
                prerequisite = charged(c, direction, f"font_{quality}")
                maximum = c.gl("mana", 90).get("max", 0)
                row = impact(c, direction, f"font_{quality}", MM)
                expected = int(maximum * share + .5)
                baseline = font_rows[0]["mana_change"] if font_rows else row["mana_change"]
                extra = row["mana_change"] - baseline
                native = row["native"]
                native_ms = native.get("after", {}).get("now", 0) - native.get("before", {}).get("now", 0)
                baseline_ms = (font_rows[0]["native"]["after"]["now"] - font_rows[0]["native"]["before"]["now"]) if font_rows else native_ms
                # Equal native windows and unchanged MM rank/cost make passive
                # regeneration cancel; control must really pay a net mana cost.
                paid_control = baseline < -1
                equal_window = native_ms == baseline_ms and 0 < native_ms <= 1000
                c.flag(f"font_{quality}_actual_refund", row["valid"] and maximum > 0 and paid_control and equal_window and abs(extra - expected) <= .4,
                       f"five earned charges released by actual MM input; extraMana {extra}, source delayed refund {expected} from max{maximum}; native {row}")
                row.update(orb=FONT, rank=quality, source_share=share, source_refund=expected, prerequisite=prerequisite)
                font_rows.append(row); rows.append(row); checkpoint(c, rows)
            orb_off(c, FONT)
            animations = []
            for quality, per in enumerate((0, .04, .08)):
                equipped = c.gl("orb", CONDUIT, 1 if quality else 0)
                c.flag(f"conduit_{quality}_equipped", equipped.get("level") == quality, str(equipped))
                prerequisite = charged(c, direction, f"conduit_{quality}", MM)
                speed = c.gl("benchstats")
                row = impact(c, direction, f"conduit_{quality}", TT, 120)
                window = cast_window(row["native"])
                if not animations:
                    baseline = speed.get("castSpeed", 0)
                    base_window = window
                else:
                    baseline = animations[0]["speed"].get("castSpeed", 0)
                    base_window = animations[0]["cast_window"]
                ratio = 1 + 5 * per
                measured = speed.get("castSpeed", 0) / max(.001, baseline)
                expected_animation = [v / ratio for v in base_window.get("duration_ms", [])]
                expected_primary = [v / ratio for v in base_window.get("primary_delay_ms", [])]
                timing = (window["valid"] and base_window["valid"]
                          and overlaps(window.get("duration_ms", []), expected_animation)
                          and overlaps(window.get("primary_delay_ms", []), expected_primary))
                ok = (row["valid"] and abs(measured - ratio) <= .004 and timing)
                c.flag(f"conduit_{quality}_actual_cast_speed", bool(ok),
                       f"actual native idle/cast/idle +timeline150 +newTT producer; statratio {measured} source{ratio}; "
                       f"observedclock brackets {window}; expectedfullanimation {expected_animation}; expectedprimary {expected_primary}")
                row.update(orb=CONDUIT, rank=quality, source_per_stack=per, prerequisite=prerequisite,
                           speed=speed, cast_window=window, expected_animation_ms=expected_animation,
                           expected_primary_ms=expected_primary)
                animations.append(row); rows.append(row); checkpoint(c, rows)
        else:
            raise ValueError(section)
    finally:
        restored = c.gl("skillcrit", TT, "restore")
        final = c.gl("skillcrit", TT)
        c.flag("wizorbs_crit_restored", restored.get("ok") and not final.get("override_active")
               and final.get("crit_chance") == original.get("crit_chance")
               and final.get("spell_crit_chance") == original.get("spell_crit_chance"), f"{original}->{restored}->{final}")
        checkpoint(c, rows)
        c.gl("timescale", 1)
        c.to_town()
    checkpoint(c, rows, True)
    return {**c.out, "notes": c.notes, "cases": rows, "measurement_only": "native1x actual inputs and damage; repeated fixed trials; explicit prerequisite cooldown resets, zero-stack/resource setup; no positive measured stacks or event hooks",
            "expected_source": ["mods/specs/scripts/HWP/Specs/Invocation.as", "gamecode/sdk/hoh2/scripts/Behaviors/Effects/Damage.as", "gamecode/sdk/hoh2/scripts/Behaviors/Armor.as", "gamecode/sdk/hoh2/scripts/Behaviors/Actors/Player/PlayerBase.as"],
            "not_covered": ["non-TT delayed critical attribution", "ordinary combat and co-op", "all Conduit intermediate stack counts (max-stack effect and real cast timing only)"]}
