"""Independent native PointCost and normalized-resource payment predictions."""
import math


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def pyrebrand_cost(raw):
    """Fixed fresh Warlock fixture: authored rank5 cost60 and native starter boots .95.

    Player.UsePoints773..789 applies combined PointCost, the global multiplier,
    and UsePoints adjustments. Those are independent native readbacks, not a
    cost fitted from the measured resource decrease.
    """
    errors = []
    if not (raw.get("ok") is True and raw.get("skill") == "hwp_wlk_pyrebrand"
            and raw.get("class") == "hwp_warlock_branding" and raw.get("matches") == 1
            and raw.get("truncated") is False and type(raw.get("skill_count")) is int
            and 1 <= raw["skill_count"] <= 128 and type(raw.get("unit")) is int and raw["unit"] > 0
            and raw.get("free_mana") is False and raw.get("free_health") is False):
        errors.append("wrong native skill/class/owner, incomplete skill list, or free-cost fixture")
    keys = ("max_health", "max_mana", "health_fraction", "mana_fraction",
            "global_health_multiplier", "global_mana_multiplier", "use_points_health",
            "use_points_mana", "scaled_health", "scaled_mana", "expense_health", "expense_mana")
    if any(not number(raw.get(k)) for k in keys):
        errors.append("missing/nonfinite native pool or cost-chain field")
    point_keys = ("health_flat", "mana_flat", "health_max_percent", "mana_max_percent",
                  "health_current_percent", "mana_current_percent", "health_multiplier", "mana_multiplier", "dash")
    for name in ("base", "modified", "combined"):
        point = raw.get(name, {})
        if not isinstance(point, dict) or any(not number(point.get(k)) for k in point_keys):
            errors.append("missing/nonfinite " + name + " PointCost")
    if errors:
        return {"valid": False, "errors": errors, "raw": raw}
    base, mod, cost = (raw[k] for k in ("base", "modified", "combined"))
    # Native fresh Warlock equips feet_int_t1a; its spell SkillCost multiplier
    # is .95. Keep that controlled setup explicit rather than accepting any cost.
    for name, point, flat, multiplier in (("base", base, 60, 1), ("modified", mod, 0, .95),
                                          ("combined", cost, 60, .95)):
        if not (point["mana_flat"] == flat and abs(point["mana_multiplier"] - multiplier) <= 1e-6
                and point["mana_max_percent"] == point["mana_current_percent"] == 0
                and point["health_flat"] == point["health_max_percent"] == point["health_current_percent"] == 0
                and point["dash"] == 0):
            errors.append("unexpected source fixture " + name + " cost")
    if not (raw["max_mana"] > 0 and raw["max_health"] > 0
            and 0 <= raw["mana_fraction"] <= 1 and 0 <= raw["health_fraction"] <= 1
            and raw["global_mana_multiplier"] == 1 and raw["use_points_mana"] == 0
            and raw["use_points_health"] == 0):
        errors.append("unexpected native pools/global cost adjustment")
    scaled = ((cost["mana_max_percent"] * raw["max_mana"]
               + cost["mana_current_percent"] * raw["mana_fraction"] * raw["max_mana"]
               + cost["mana_flat"]) * raw["global_mana_multiplier"] * cost["mana_multiplier"])
    expense = scaled + raw["use_points_mana"] * raw["global_mana_multiplier"]
    if not (abs(scaled - raw["scaled_mana"]) <= .00002
            and abs(expense - raw["expense_mana"]) <= .00002
            and abs(expense - 57) <= .00002 and raw["expense_health"] == 0):
        errors.append("native effective expense contradicts the independent source calculation")
    return {"valid": not errors, "errors": errors, "expense": expense,
            "max_mana": raw["max_mana"], "mana_fraction": raw["mana_fraction"], "raw": raw}


def normalized_payment(trace, prediction, refund=False, baseline_max=None):
    """One real cost and optional400ms refund, without confusing a new maximum.

    Player.UsePoints subtracts expense/MaxMana from record.mana. A later stats
    refresh preserves that normalized value while Essence changes MaxMana;
    absolute mana therefore changes without another payment. Each actual
    fraction drop remains bounded by measured native regeneration. Recast
    Refund rounds the same57 cost, then adds it at the then-current maximum.
    """
    rows, errors = trace.get("samples", []), []
    if not (trace.get("usable") is True and prediction.get("valid") is True
            and 1200 <= trace.get("ms", -1) <= 1300 and trace.get("frames", 0) >= 10
            and len(rows) >= 10):
        return {"valid": False, "errors": ["incomplete native trace or source cost prediction"]}
    required = ("now", "mana", "manaFraction", "maxMana", "statMana", "manaRegen", "manaGain")
    if any(any(not number(row.get(k)) for k in required) or row["maxMana"] <= 0
           or row["statMana"] <= 0 or row["manaRegen"] < 0 or row["manaGain"] < 0
           or not 0 < row["manaFraction"] < .9999
           or abs(row["mana"] - row["manaFraction"] * row["maxMana"]) > .00001 for row in rows):
        return {"valid": False, "errors": ["missing/nonfinite native fields, floor/cap, or inconsistent normalization"]}
    if rows[0]["maxMana"] != prediction["max_mana"]:
        errors.append("native maximum changed between source cost query and input")
    if not number(baseline_max) or baseline_max <= 0:
        return {"valid": False, "errors": ["missing independently queried zero-Essence maximum"]}
    if any(row["maxMana"] not in (baseline_max, prediction["max_mana"]) for row in rows):
        errors.append("unexplained native maximum pool")
    decreases, increases, rescalings = [], [], []
    maximum_dt = 0
    for index, (a, b) in enumerate(zip(rows, rows[1:]), 1):
        dt = b.get("dt")
        if type(dt) is not int or not 0 < dt <= 100:
            errors.append("invalid native frame duration")
            continue
        maximum_dt = max(maximum_dt, dt)
        normalized_regen = max(row["manaRegen"] * row["manaGain"] / row["statMana"] for row in (a, b)) * dt / 1000
        fraction_drop = a["manaFraction"] - b["manaFraction"]
        if a["maxMana"] != b["maxMana"]:
            rescalings.append({"now": b["now"], "from_max": a["maxMana"], "to_max": b["maxMana"],
                               "absolute_drop": a["mana"] - b["mana"], "fraction_drop": fraction_drop,
                               "rescale_contribution": b["manaFraction"] * (b["maxMana"] - a["maxMana"])})
        if fraction_drop * prediction["max_mana"] > .5:
            observed = fraction_drop * prediction["max_mana"]
            bound = normalized_regen * prediction["max_mana"]
            decreases.append({"index": index, "now": b["now"], "actual_drop": observed, "source_regen_bound": bound,
                              "expected_expense": prediction["expense"], "matches":
                              prediction["expense"] - bound - .02 <= observed <= prediction["expense"] + .02})
        elif -fraction_drop * b["maxMana"] > .5:
            observed = -fraction_drop * b["maxMana"]
            bound = normalized_regen * b["maxMana"]
            expected = int(prediction["expense"] + .5)
            increases.append({"index": index, "now": b["now"], "actual_gain": observed, "source_regen_bound": bound,
                              "expected_refund": expected, "matches": expected - .02 <= observed <= expected + bound + .02})
    if len(decreases) != 1 or not all(row["matches"] for row in decreases):
        errors.append("must observe exactly one source-predicted normalized expense")
    if len(increases) != int(refund) or not all(row["matches"] for row in increases):
        errors.append("missing, extra, or wrong source-predicted refund")
    expect_rescale = bool(refund and prediction["max_mana"] != baseline_max)
    if len(rescalings) != int(expect_rescale):
        errors.append("wrong count of source-predicted Essence maximum changes")
    if expect_rescale and len(rescalings) == len(decreases) == 1:
        change = rescalings[0]
        if not (change["from_max"] == prediction["max_mana"] and change["to_max"] == baseline_max
                and abs(change["now"] - decreases[0]["now"]) <= 2 * maximum_dt):
            errors.append("maximum pool change differs from same-callback Claw Essence spend")
    if refund and len(increases) == len(decreases) == 1:
        lag = increases[0]["now"] - decreases[0]["now"]
        if not 400 - 2 * maximum_dt <= lag <= 400 + 2 * maximum_dt:
            errors.append("refund outside authored400ms plus two native endpoint frames")
    # Event thresholds identify the two large source actions; they must not
    # hide smaller repeated changes. Conserve the entire normalized trajectory
    # from ONE fixed initial anchor, at every prefix. Player.as1242 supplies
    # regen Gain*Regen/statMana. Adjacent measured rates bound the one stats
    # transition. Two native endpoint frames bound observer/actor ordering;
    # float32 addition/division error accumulates with callbacks, never resets.
    maximum_rate = max(row["manaRegen"] * row["manaGain"] / row["statMana"] for row in rows)
    phase_bound = 2 * maximum_dt / 1000 * maximum_rate
    event_effect = regen_low = regen_high = 0.0
    expense_indices = {row["index"] for row in decreases}
    refund_indices = {row["index"] for row in increases}
    conservation = []
    for index, (a, b) in enumerate(zip(rows, rows[1:]), 1):
        native_ms = b["now"] - a["now"]
        if not 0 <= native_ms <= 100 or abs((b["now"] - rows[0]["now"]) - b.get("elapsed", -9999)) > maximum_dt:
            errors.append("native clock/elapsed exceeds one-frame ordering bound")
            continue
        rates = [row["manaRegen"] * row["manaGain"] / row["statMana"] for row in (a, b)]
        regen_low += min(rates) * native_ms / 1000
        regen_high += max(rates) * native_ms / 1000
        if index in expense_indices:
            event_effect -= prediction["expense"] / prediction["max_mana"]
        if index in refund_indices:
            event_effect += int(prediction["expense"] + .5) / b["maxMana"]
        float32_bound = (index + 2) * 3 * 2**-24 + 2e-9
        low = rows[0]["manaFraction"] + regen_low + event_effect - phase_bound - float32_bound
        high = rows[0]["manaFraction"] + regen_high + event_effect + phase_bound + float32_bound
        valid = low <= b["manaFraction"] <= high
        conservation.append({"index": index, "now": b["now"], "actual_fraction": b["manaFraction"],
                             "predicted_low": low, "predicted_high": high, "valid": valid,
                             "cumulative_regen_low": regen_low, "cumulative_regen_high": regen_high,
                             "cumulative_source_events": event_effect, "phase_bound": phase_bound,
                             "cumulative_float32_bound": float32_bound})
    if len(conservation) != len(rows) - 1 or not all(row["valid"] for row in conservation):
        errors.append("anchored whole-trace native mana conservation failed")
    return {"valid": not errors, "errors": errors, "expected_expense": prediction["expense"],
            "decreases": decreases, "refunds": increases, "rescalings": rescalings,
            "conservation": conservation,
            "model": "native normalized record.mana; exact cost/refund, observed current maxima, measured per-frame regen"}
