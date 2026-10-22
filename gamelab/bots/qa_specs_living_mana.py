"""Native resource trajectories identify Living Mana's five regeneration coefficients."""
import json
import math
import time

from gamelab.bots.plan_specs import Checks

MANA = "hwp_sor_living_mana"
COEFFICIENTS = (0, .5, .75, 1, 1.25, 1.5)
STAT_FIELDS = ("maxMana", "maxHp", "statMana", "statHealth",
               "manaRegen", "manaGain", "healthRegen", "healthGain")
NUM_FIELDS = STAT_FIELDS + ("mana", "manaFraction", "hp", "hpFraction", "healthRegenC")
FLOAT_EPSILON = 2 ** -23


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def collect(game, tag, timeout=12):
    first = game.wait_gl(lambda row: row.get("ev") == "resourceobserve"
                         and row.get("tag") == tag and row.get("part") == 0, timeout)
    if first is None:
        return {"usable": False, "errors": ["missing resource part0"], "samples": []}
    parts, chunks, errors = first.get("parts"), [first], []
    if not isinstance(parts, int) or not 1 <= parts <= 16:
        return {**first, "usable": False, "errors": ["invalid part count"], "samples": []}
    for index in range(1, parts):
        chunk = game.wait_gl(lambda row: row.get("ev") == "resourceobserve"
                            and row.get("tag") == tag and row.get("part") == index, 5)
        if chunk is None:
            errors.append(f"missing resource part{index}")
            break
        chunks.append(chunk)
    fields = ("parts", "stored", "seen", "dropped", "truncated", "start", "end", "ms", "frames")
    rows = []
    for index, chunk in enumerate(chunks):
        if chunk.get("part") != index or any(chunk.get(k) != first.get(k) for k in fields):
            errors.append(f"inconsistent header{index}")
        samples = chunk.get("samples", [])
        if not isinstance(samples, list) or not 1 <= len(samples) <= 16:
            errors.append(f"invalid chunk length{index}")
        else:
            rows.extend(samples)
    if not (len(rows) == first.get("stored") == first.get("seen")
            == first.get("frames", -2) + 1 and 2 <= len(rows) <= 256
            and first.get("dropped") == 0 and first.get("truncated") is False):
        errors.append("incomplete/truncated frame trace")
    if not rows or rows[0].get("dt") != 0 or rows[0].get("elapsed") != 0:
        errors.append("missing initial snapshot")
    if not rows or rows[-1].get("final") is not True or rows[-1].get("elapsed") != first.get("ms"):
        errors.append("missing final snapshot")
    for index, row in enumerate(rows):
        if row.get("valid") is not True or any(not number(row.get(k)) for k in NUM_FIELDS):
            errors.append(f"invalid native resource/stat snapshot{index}")
        if index:
            prev = rows[index-1]
            if not (isinstance(row.get("dt"), int) and row["dt"] > 0
                    and row.get("elapsed") - prev.get("elapsed", 0) == row["dt"]
                    and row.get("now", -1) >= prev.get("now", 0)):
                errors.append(f"discontinuous native frame{index}")
    return {**first, "samples": rows, "usable": not errors, "errors": errors}


def coefficient_model(trace, coefficient, living=True):
    """Independent source bounds, including native update ordering and float32 error.

    Player.as1242 supplies native mana regeneration A*MaxMana/statMana.
    Player.as1244 supplies HP regeneration; Arcane.as338 converts it only when
    its normalized change exceeds .00001. Arcane.as358 adds A*r*missing.
    Bounds integrate each observed native frame, rather than fit endpoint rates.
    """
    if not trace.get("usable"):
        return {"valid": False, "errors": trace.get("errors", ["unusable trace"])}
    rows = trace["samples"]
    base = rows[0]
    errors = []
    if any(any(abs(row[k]-base[k]) > 1e-7 for k in STAT_FIELDS) for row in rows):
        errors.append("current regeneration stats/maxima changed during measurement")
    if any(row["healthRegenC"] > 0 for row in rows):
        errors.append("native HP regeneration delay still active")
    if not all(row["maxMana"] > 0 and row["maxHp"] > 0
               and row["statMana"] > 0 and row["statHealth"] > 0 for row in rows):
        errors.append("nonpositive resource denominator")
    if any(not 1.5 < row["mana"] < row["maxMana"]-2 for row in rows):
        errors.append("mana floor/cap can contaminate trajectory")
    if any(b["mana"] < a["mana"]-1e-6 for a, b in zip(rows, rows[1:])):
        errors.append("non-regeneration mana loss")
    if errors:
        return {"valid": False, "errors": errors}
    max_mana = base["maxMana"]
    a = base["manaRegen"] * base["manaGain"]
    h = base["healthRegen"] * base["healthGain"]
    if a <= 0 or h < 0:
        return {"valid": False, "errors": ["nonpositive mana or negative health baseline"]}
    frames = rows[1:]
    max_dt = max(row["dt"] for row in frames) / 1000
    seconds = sum(row["dt"] for row in frames) / 1000
    if not (3.9 <= seconds <= 4.2 and max_dt <= .1
            and abs((trace["end"]-trace["start"])/1000-seconds) <= max_dt+.001):
        return {"valid": False, "errors": ["unexpected native trace time/frequency"]}
    mana_base = a * max_mana / base["statMana"]
    hp_base = h * base["maxHp"] / base["statHealth"]
    baseline_lo = baseline_hi = mana_base * seconds
    missing_lo = missing_hi = 0
    for left, right in zip(rows, rows[1:]):
        dt = right["dt"]/1000
        # Native HP increment is normalized before Arcane's .00001 comparison.
        # Preserve either outcome near the float32 threshold; never assume a heal.
        normalized_hp = h * dt / base["statHealth"]
        if living and normalized_hp > 1e-5 + 4*FLOAT_EPSILON:
            baseline_lo += hp_base*dt
            baseline_hi += hp_base*dt
        elif living and normalized_hp >= 1e-5 - 4*FLOAT_EPSILON:
            baseline_hi += hp_base*dt
        missing_lo += dt * (1-right["mana"]/max_mana)
        missing_hi += dt * (1-left["mana"]/max_mana)
    # Initial/final queued-task sampling may straddle a native Player/Specs update.
    # Two full source-bounded frame gains cover that phase; no fitted tolerance.
    phase_pad = 2*max_dt*(mana_base + (hp_base if living else 0) + a*1.5)
    # At most16 float32 roundoff units per frame, using full MaxMana as scale.
    # This also covers nine-decimal trace serialization and HP conversion roundoff.
    float_pad = 16*FLOAT_EPSILON*max_mana*(len(rows)+2) + 2e-8*len(rows)
    gain = rows[-1]["mana"]-base["mana"]
    denominator_lo, denominator_hi = a*missing_lo, a*missing_hi
    if denominator_lo <= 0:
        return {"valid": False, "errors": ["no missing-mana integral"]}
    lower = (gain-baseline_hi-phase_pad-float_pad)/denominator_hi
    upper = (gain-baseline_lo+phase_pad+float_pad)/denominator_lo
    contains = lower <= coefficient <= upper
    excluded = all(not lower <= other <= upper for other in COEFFICIENTS if other != coefficient)
    mirror_bound = (2*max_dt*(mana_base+a*1.5)/max_mana
                    + 2*max_dt*h/base["statHealth"] + 8*FLOAT_EPSILON)
    mirror_error = max(abs(row["hpFraction"]-row["manaFraction"]) for row in rows)
    return {"valid": contains and excluded and (not living or mirror_error <= mirror_bound),
            "coefficient_interval": [lower, upper], "expected": coefficient,
            "expected_inside": contains, "other_built_coefficients_excluded": excluded,
            "native_gain": gain, "native_seconds": seconds, "max_frame_seconds": max_dt,
            "baseline_bounds": [baseline_lo, baseline_hi], "native_mana_baseline": mana_base,
            "converted_hp_baseline": hp_base if living else 0,
            "missing_integral_bounds": [missing_lo, missing_hi],
            "source_phase_padding": phase_pad, "float32_padding": float_pad,
            "mirror_error": mirror_error, "source_mirror_bound": mirror_bound,
            "errors": []}


def window(c, tag, fraction, coefficient, living):
    maximum = c.gl("state").get("player", {}).get("manaMax", 0)
    prepared = c.gl("mana", maximum*fraction)
    time.sleep(.4)  # Bind refresh250ms and HP mirror settle before measurement.
    queued = c.gl("resourceobserve", tag, 4000)
    trace = collect(c.g, tag) if queued.get("ok") else {"usable": False, "errors": [str(queued)]}
    model = coefficient_model(trace, coefficient, living)
    c.flag(tag+"_trajectory", bool(model.get("valid")), str(model))
    return {"tag": tag, "fixture_fraction": fraction, "mana_prerequisite": prepared,
            "queued": queued, "trace": trace, "model": model}


def checkpoint(c, cases):
    path = c.g.results/"qa-specs-living-mana.partial.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"checks":c.out,"notes":c.notes,"cases":cases},indent=2),encoding="utf-8")
    tmp.replace(path)


def run(p, **_):
    c, cases = Checks(p), []
    char, _, _ = c.new_char("sorcerer", "LabLivingMana")
    initial = c.gl("state").get("player", {})
    c.flag("lmqa_char", char.get("ok") and initial.get("class")=="sorcerer"
           and initial.get("level",0)>=20, str(initial))
    if not c.out["lmqa_char"]:
        return {**c.out,"notes":c.notes}
    baseline_floor = c.enter_floor("lmqa_baseline")
    c.flag("lmqa_baseline_floor", bool(baseline_floor), "native mission entry; no geometry-dependent ability")
    if not baseline_floor:
        return {**c.out,"notes":c.notes}
    c.god(True)
    c.gl("timescale",1)
    cases.append(window(c,"lm_rank0_native",.1,0,False))
    checkpoint(c,cases)
    c.to_town()
    took = c.gl("subclass","hwp_sorcerer_arcane")
    c.hwp("skillpoints 80")
    level = c.gl("skill",MANA,0).get("level")
    time.sleep(.4)
    converted = c.gl("state").get("player",{})
    c.flag("lmqa_learned", took.get("class")=="hwp_sorcerer_arcane" and level==1,str(took))
    c.flag("lmqa_max_conversion", abs(converted.get("manaMax",0)-initial.get("manaMax",0)
           -initial.get("hpMax",0))<=1, str({"before":initial,"after":converted}))
    orbs={oid:c.gl("orb",oid,0).get("level") for oid in
          ("hwp_sor_lm_arcane_feedback","hwp_sor_lm_mana_conduit","hwp_sor_bl_void_barrier","hwp_sor_bl_far_step")}
    c.flag("lmqa_no_orbs",all(n==0 for n in orbs.values()),str(orbs))
    entered = c.enter_floor("lmqa_positive")
    c.flag("lmqa_positive_floor",bool(entered),"native mission entry; stationary resource measurement")
    if not entered:
        return {**c.out,"notes":c.notes,"cases":cases}
    c.god(True)
    c.gl("timescale",1)
    controls=c.gl("cvars","cht_god","g_timescale").get("cvars",{})
    c.flag("lmqa_controls",controls.get("cht_god")==1 and controls.get("g_timescale")==1,str(controls))
    for rank,coefficient in enumerate(COEFFICIENTS[1:],1):
        if rank>1:
            c.gl("skill",MANA,1)
        actual=c.gl("skill",MANA,0).get("level")
        bind=float(c.bind(MANA,"lm-regen") or -1)
        c.flag(f"lm_rank{rank}_setup",actual==rank and bind==coefficient,str({"level":actual,"bind":bind}))
        for label,fraction in (("low",.1),("high",.55)):
            cases.append(window(c,f"lm_rank{rank}_{label}",fraction,coefficient,True))
            checkpoint(c,cases)
    c.to_town()
    checkpoint(c,cases)
    return {**c.out,"notes":c.notes,"cases":cases,
            "source":["mods/specs/scripts/HWP/Specs/Arcane.as:338",
                      "mods/specs/scripts/HWP/Specs/Arcane.as:358",
                      "mods/specs/players/hwp/specs/arcane/living_mana.sval",
                      "gamecode/sdk/hoh2/scripts/Behaviors/Actors/Player/Player.as:1242"],
            "scope":"Controlled native passive regeneration trajectories at all5ranks plus native no-LivingMana baseline; actual resource/mirror observations, independent current-stat source model; no positive measured proc injection.",
            "not_covered":["actual healing/potions/leech/DoT conversion and lethal thresholds",
                           "spell-floor boundaries, acquisition/UI, transitions/death/save-reload and co-op"]}
