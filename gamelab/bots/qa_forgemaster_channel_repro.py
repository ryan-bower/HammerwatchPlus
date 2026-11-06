"""Original-product channel consumers, with declared mana/body interventions.

Pure trace/oracle functions import no game or launcher modules. Native execution
uses ordinary owned input via forgechannel; no RaiseNow/Activate/castat/reset.
Healthy expectations stay healthy when the original product fails.
"""
import math
import re
import time

NR = "hwp_pri_necrotic_resurrection"
COH = "hwp_pri_call_of_heresy"
CLASS = "hwp_priest_forgemaster"
ORIGINAL_SHA = "0e368e88745142b6aa7db19b0e21105eb2727e24da332f6d8225ac3f95ea27b3"
BODY_PREFIX = "players/hwp/specs/forgemaster/bodies/"
RISEN_PREFIX = "players/hwp/specs/forgemaster/risen/"
TARGET = "doodads/generic/target_dummy_breakable.unit"
BOSS = "bosses/boss_bandit/boss_bandit_encounter.unit"
NORMAL = "humans/bandits/bandit_brute.unit"
PRIMARY = ("P0", "P1", "P2", "P3", "C0", "C1")
SUPPLEMENTAL = {
    "exact_cost": "not implemented: exact-cost and depleted-then-restored completion",
    "pending_1ms": "not implemented: scheduled pending dash interruption",
    "death_floor_class": "not implemented: death/floor/class cleanup and next-dash distance",
}
PHASE = "native_pre_player_update; fixture actions have adjacent before/after samples"


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def require(ok, name, errors):
    if not ok:
        errors.append(name)
    return bool(ok)


def _trace(accepted, chunks):
    """Reassemble every bounded chunk, rejecting duplicates/missing/foreign rows."""
    errors, rows = [], []
    if not chunks or any(type(c) is not dict for c in chunks):
        return {"valid": False, "errors": ["missing native chunks"], "samples": []}
    head = chunks[0]
    count, parts = head.get("stored"), head.get("parts")
    require(type(count) is int and 1 <= count <= 2048 and type(parts) is int
            and parts == (count + 1)//2 and len(chunks) == parts, "chunk/count bounds", errors)
    # session.Game.pump adds per-receipt wall time after decoding native JSON.
    # Raw native controls omit it entirely; annotated traces must be complete and
    # finite/nondecreasing (ties are normal at the millisecond transport clock).
    envelope = (accepted, *chunks)
    annotated = any("_t" in row for row in envelope)
    stamps = [row.get("_t") for row in envelope]
    require(not annotated or (all("_t" in row for row in envelope)
            and all(finite(value) and value >= 0 for value in stamps)
            and all(a <= b for a, b in zip(stamps, stamps[1:]))),
            "invalid/mixed/regressing transport timestamp envelope", errors)
    keys = tuple(k for k in head if k not in ("part", "samples", "_t"))
    for index, chunk in enumerate(chunks):
        require(chunk.get("ev") == "forgechannel" and type(chunk.get("part")) is int
                and chunk["part"] == index and all(chunk.get(k) == head.get(k) for k in keys),
                "foreign/duplicate/inconsistent chunk", errors)
        samples = chunk.get("samples")
        if not require(type(samples) is list and 1 <= len(samples) <= 2
                       and all(type(s) is dict for s in samples), "bad sample chunk", errors):
            continue
        rows.extend(samples)
    require(accepted.get("ok") is True and type(accepted.get("id")) is str
            and bool(accepted.get("id")) and type(accepted.get("tag")) is str and bool(accepted.get("tag"))
            and type(head.get("player")) is int and head["player"] > 0
            and type(head.get("body")) is int and type(head.get("target")) is int
            and accepted.get("id") == head.get("id") and accepted.get("tag") == head.get("tag")
            and accepted.get("case") == head.get("case") and accepted.get("player") == head.get("player")
            and accepted.get("body") == head.get("body") and accepted.get("target") == head.get("target")
            and accepted.get("button") == head.get("button"), "foreign acceptance/owner", errors)
    require(head.get("complete") is True and head.get("error") == ""
            and head.get("truncated") is False and head.get("dropped") == 0
            and head.get("seen") == count == len(rows) and head.get("phase") == PHASE
            and head.get("released") is True and head.get("cursor_restored") is True
            and head.get("projection_failures") == [], "incomplete/late/truncated/release", errors)
    receipts = head.get("restore")
    require(type(receipts) is list and 1 <= len(receipts) <= 8
            and all(type(r) is dict and r.get("buffer") == i and r.get("restored") is True
                    and (r.get("owned_last_value") is True or r.get("already_neutral") is True)
                    for i, r in enumerate(receipts or [])), "cursor restoration receipt", errors)
    integer_fields = ("now", "dt", "player", "raising_left", "stance_left", "devouring_left", "heresy", "favor",
                      "favor_timer", "nr_cd", "nr_base_cd", "dash_cd", "dash_cast", "dash_dist", "dash_charges",
                      "dash_base_cd", "dash_recharge", "dash_max", "body", "target", "target_max", "shot_hits", "max_mana", "max_health")
    numeric_fields = ("x", "y", "nr_cd_mul", "dash_remaining", "mana", "mana_fraction", "stat_mana",
                      "mana_regen", "mana_gain", "dash_cd_mul", "dash_recharge_ms", "body_x", "body_y", "target_x", "target_y",
                      "move_x", "move_y", "cursor_world_x", "cursor_world_y", "projection_error")
    for r in rows:
        require(all(type(r.get(k)) is int for k in integer_fields)
                and all(finite(r.get(k)) for k in numeric_fields)
                and 0 < r.get("dt", 0) <= 100 and r.get("class") == CLASS and r.get("skill") == NR
                and r.get("player") == head.get("player") and r.get("owned_skill") is True
                and r.get("body") == head.get("body") and r.get("target") == head.get("target")
                and type(r.get("body_valid")) is bool and type(r.get("target_valid")) is bool
                and type(r.get("geometry_checked")) is bool and type(r.get("shot_wall")) is bool
                and all(type(r.get(k)) is bool for k in ("root", "silence", "disarm", "infinite_dashes", "body_position_current"))
                and r.get("body_position_current") is r.get("body_valid")
                and type(r.get("risen")) is list and r.get("devouring_left") == -1
                and r.get("phase") in ("frame", "before_fixture", "after_fixture")
                and r.get("max_mana", 0) > 0 and r.get("stat_mana", 0) > 0
                and abs(r.get("mana", -99) - r.get("mana_fraction", 0)*r.get("max_mana", 0)) < .003,
                "native owner/identity/resource/sample", errors)
        if r.get("phase") == "frame":
            require(finite(r.get("projection_error")) and 0 <= r["projection_error"] <= .101,
                    "native cursor projection", errors)
            c = r.get("cursor", {})
            require(type(c) is dict and c.get("now") == r["now"] and c.get("dt") == r["dt"]
                    and c.get("release") is False and c.get("gamepad") is False and type(c.get("buffer")) is int
                    and 0 <= c["buffer"] < 8 and all(finite(c.get(k)) for k in
                        ("x", "y", "screen_x", "screen_y", "world_x", "world_y", "round_error", "manaExact", "hpExact"))
                    and abs(c["manaExact"]-r["mana"]) < .003 and c["hpExact"] > 0
                    and math.dist((c["x"], c["y"]), (r["x"], r["y"])) <= .003
                    and math.dist((c["world_x"], c["world_y"]), (r["cursor_world_x"], r["cursor_world_y"])) <= .101
                    and 0 <= c["round_error"] <= .101,
                    "exact inherited F1 corrected cursor row missing/foreign", errors)
        else:
            require(r.get("cursor") is None, "fixture rows cannot pretend a second cursor write", errors)
    frames = [r for r in rows if r.get("phase") == "frame"]
    require(bool(frames) and all(0 < b["now"]-a["now"] <= 100
                                and b["now"]-a["now"] == b["dt"] for a, b in zip(frames, frames[1:])),
            "nonconsecutive native frames", errors)
    require(type(head.get("writes")) is int and head["writes"] == len(frames)+2
            and head.get("cursor_seen") == len(frames) and head.get("cursor_dropped") == 0
            and head.get("start") == (frames[0].get("now") if frames else None)
            and type(head.get("end")) is int and frames and 0 < head["end"]-frames[-1]["now"] <= 200,
            "native writer/release/clock count", errors)
    return {"valid": not errors, "errors": errors, "samples": rows, "frames": frames,
            "head": head, "accepted": accepted, "chunks": chunks}


def trace(accepted, chunks):
    try:
        return _trace(accepted, chunks)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        return {"valid": False, "errors": ["malformed native trace: " + repr(exc)], "samples": [], "frames": []}


def expense(row, nominal):
    """Independent Player.UsePoints arithmetic; raw native adjustment stays visible."""
    c = row["cost"]
    p = c["combined"]
    assert p["mana_flat"] == nominal and p["health_flat"] == 0 and p["dash"] == 0
    assert all(p[k] == 0 for k in ("health_max_percent", "mana_max_percent", "health_current_percent", "mana_current_percent"))
    assert c["free_mana"] is False and c["free_health"] is False
    assert c["expense_health"] == c["scaled_health"] == c["use_points_health"] == 0
    assert finite(p["mana_multiplier"]) and p["mana_multiplier"] > 0
    assert finite(c["global_mana_multiplier"]) and c["global_mana_multiplier"] > 0
    assert type(c["use_points_mana"]) is int
    scaled = nominal*p["mana_multiplier"]*c["global_mana_multiplier"]
    value = scaled + c["use_points_mana"]*c["global_mana_multiplier"]
    assert value > 0 and abs(c["scaled_mana"]-scaled) < .003 and abs(c["expense_mana"]-value) < .003
    return value


def resource_ledger(samples):
    """Per-frame regeneration including saturation; explicit drain is separate."""
    result = []
    for a, b in zip(samples, samples[1:]):
        assert b["now"] >= a["now"]
        assert a["max_mana"] == b["max_mana"] and a["stat_mana"] == b["stat_mana"]
        assert a["mana_regen"] == b["mana_regen"] and a["mana_gain"] == b["mana_gain"]
        if a["phase"] == "before_fixture" and b["phase"] == "after_fixture":
            assert a["now"] == b["now"]
            continue
        regen = (b["now"]-a["now"])/1000*a["mana_regen"]*a["mana_gain"]/a["stat_mana"]
        predicted = min(1, max(0, a["mana_fraction"]+regen))*a["max_mana"]
        result.append({"now": b["now"], "spend": predicted-b["mana"], "regen": regen*a["max_mana"]})
    return result


def favor_natural(frames):
    """Allow the recorded native five-second timer to remove one stack at a time."""
    for a, b in zip(frames, frames[1:]):
        if b["favor"] != a["favor"]:
            if not (b["favor"] == a["favor"]-1 and 0 <= a["favor_timer"] <= b["now"]-a["now"]+100):
                return False
    return True


def status_number(raw, key):
    values = re.findall(r"\b"+re.escape(key)+r" (-?\d+)\b", raw)
    return int(values[-1]) if values else None


def evaluate(row):
    """Fail closed on prerequisites; return independent contract/effect booleans."""
    errors, case = [], row.get("case")
    t = trace(row.get("accepted", {}), row.get("chunks", []))
    result = {"valid": False, "healthy": False, "errors": errors, "trace": t}
    if not require(case in (*PRIMARY, "CAL") and t["valid"] and row.get("before") is not None
                   and row.get("after") is not None, "trace/before/after prerequisite", errors):
        return result
    f, h, samples = t["frames"], t["head"], t["samples"]
    a, z = f[0], f[-1]
    try:
        before_status, after_status = row["before"]["status"], row["after"]["status"]
        require(type(before_status) is str and type(after_status) is str and "channel none" in before_status
                and "eat none" in before_status and "eat none" in after_status
                and status_number(before_status, "lunges") is not None
                and status_number(before_status, "lunges") == status_number(after_status, "lunges"),
                "complete raw product status and no independent lunge", errors)
        require(all(r["body_name"] == h["body_name"] for r in f if r["body_valid"])
                and all(type(u.get("unit")) is int and u["unit"] > 0 and u.get("owned") is True
                        and u.get("name", "").startswith(RISEN_PREFIX) for r in f for u in r["risen"]),
                "body/risen identity or owner", errors)
        if case == "CAL":
            require(h["channel_at"] == -1 and not h["actions"] and all(r["raising_left"] == -1
                    and not r["risen"] for r in f), "calibration must have no ability/body effect", errors)
            require(a["geometry_checked"] is True and a["shot_wall"] is False and 0 <= a["shot_hits"] <= 128,
                    "actual calibration start ray geometry", errors)
        else:
            nominal = 50 if case in ("P2", "P3", "C1") else 70
            rank = row.get("rank_setup", {})
            require(rank.get("levels") == {NR: 2, COH: 2} and rank.get("nr_penance") == 1
                    and rank.get("coh_lunge") == .02
                    and h["body_name"] == BODY_PREFIX+(BOSS if case in ("P0", "P1", "C0") else NORMAL),
                    "authored rank2/boss-or-normal body prerequisite", errors)
            costs = [expense(r, nominal) for r in f]
            ledger = resource_ledger(samples)
            cost = row.get("cost", {})
            require(cost.get("ok") is True and cost.get("skill") == NR and cost.get("class") == CLASS
                    and cost.get("unit") == h["player"] and cost.get("matches") == 1 and cost.get("truncated") is False
                    and cost.get("combined") == a["cost"]["combined"] and cost.get("free_mana") is False
                    and abs(cost.get("expense_mana", -99)-costs[0]) < .003,
                    "independent generic owned native source-cost observation", errors)
            require(all(abs(v-costs[0]) < .003 for v in costs), "cost/modifier chain changed", errors)
            require(a["mana"] >= costs[0] and a["raising_left"] == -1 and a["nr_cd"] <= 0
                    and a["body_valid"] and a["body_name"].startswith(BODY_PREFIX)
                    and all(not r["risen"] for r in f if r["now"] < h["channel_at"]), "legal initial activation", errors)
            active = [r for r in f if r["raising_left"] > 0]
            duration = 3000 if nominal == 50 else 10000
            require(active and h["duration"] == duration and h["channel_at"] == active[0]["now"]
                    and h["deadline"] == active[0]["now"]+active[0]["raising_left"]
                    and duration-200 <= active[0]["raising_left"] <= duration
                    and h["channel_at"]-h["start"] <= 1000
                    and any(r["button"] == h["button"] for r in f[:max(1, f.index(active[0]))])
                    and any(r["button"] == "-" for r in f), "real channel/button/timing", errors)
            if case in ("P2", "P3", "C1"):
                require(a["heresy"] == 4 and a["favor"] == 5
                        and active[0]["stance_left"] > 0, "real Penance readiness/stance", errors)
            else:
                require(a["heresy"] == 0 and a["favor"] == 0 and active[0]["stance_left"] == -1,
                        "real raise readiness", errors)
            if case == "P3":
                pre = row.get("pre_roll", {})
                require(pre.get("valid") is True and pre.get("heresy") == 0
                        and pre.get("body") == h["body"] and pre.get("ordinary_input") is True
                        and pre.get("rolled") is True and type(pre.get("raw")) is str
                        and re.search(r"\| " + str(h["body"]) + r" [^|]*\brolled\b", pre["raw"]) is not None,
                        "H0 ordinary-input pre-roll prerequisite", errors)
            acts = h["actions"]
            intervention = case in ("P1", "P3", "C0", "C1")
            require(type(acts) is list and len(acts) == int(intervention), "fixture action count", errors)
            if intervention:
                action = acts[0]
                expected_kind = "drain" if case in ("P1", "P3") else "remove_body"
                require(action["kind"] == expected_kind and action["now"] == h["action_at"]
                        and action["now"] >= h["channel_at"]+500 and action["raising_left"] > 0,
                        "fixture after actual activation", errors)
                before = [r for r in samples if r["phase"] == "before_fixture"]
                after = [r for r in samples if r["phase"] == "after_fixture"]
                require(len(before) == len(after) == 1 and before[0]["now"] == after[0]["now"] == action["now"]
                        and before[0]["body_valid"] and before[0]["raising_left"] == action["raising_left"],
                        "adjacent before/after intervention", errors)
                if case in ("P1", "P3"):
                    require(after[0]["mana"] == action["mana_after"] == 0
                            and abs(before[0]["mana"]-action["mana_before"]) < .003
                            and after[0]["body_valid"] and before[0]["heresy"] == after[0]["heresy"],
                            "single mana-only fixture", errors)
                    require(all(r["mana"] < costs[0]-.1 for r in f
                                if r["now"] >= h["action_at"]), "unaffordable through completion despite regen", errors)
                else:
                    require(not after[0]["body_valid"] and before[0]["mana"] == after[0]["mana"]
                            and before[0]["heresy"] == after[0]["heresy"], "exact body-only fixture", errors)
                    actual = before[0]
                    require(actual["geometry_checked"] is True and actual["shot_wall"] is False and actual["body_position_current"] is True
                            and 0 <= actual["shot_hits"] <= 128
                            and 40 <= math.dist((actual["x"], actual["y"]), (actual["target_x"], actual["target_y"])) <= 200,
                            "actual intervention actor-to-owned-target clear ray", errors)
                    if case == "C1":
                        require(action["landed"] is True and action["raising_left"] >= 2000
                                and before[0]["dash_cast"] <= 0 and before[0]["dash_remaining"] <= 0
                                and math.dist((actual["x"], actual["y"]), (actual["body_x"], actual["body_y"]+10)) <= 2
                                and row.get("landed_geometry", {}).get("valid") is True,
                                "landed Penance with>=2000ms remaining", errors)
            else:
                require(h["action_at"] == -1, "unexpected intervention", errors)
            if case.startswith("P"):
                require(z["now"] >= h["deadline"]+400 and all(r["body_valid"] for r in f
                        if r["now"] < h["deadline"]-200), "complete channel, not early body loss", errors)
            paid = [v for v in ledger if v["spend"] > .02]
            require(all(v["spend"] >= -.01 for v in ledger), "unexplained mana gain", errors)
            require(sum(abs(v["spend"]) for v in ledger if abs(v["spend"]) <= .02) <= .05,
                    "accumulated small mana drift beyond float tolerance", errors)
            if case in ("P0", "P2"):
                payment = (len(paid) == 1 and abs(paid[0]["spend"]-costs[0]) <= .03
                           and abs(paid[0]["now"]-h["deadline"]) <= 200)
                if case == "P0":
                    matching = [u for u in z["risen"] if u["name"] == RISEN_PREFIX+h["body_name"][len(BODY_PREFIX):]]
                    effect = (not z["body_valid"] and len(z["risen"]) == len(matching) == 1 and z["heresy"] == 3
                              and 0 < z["nr_cd"] <= int(z["nr_base_cd"]*z["nr_cd_mul"])
                              and z["nr_cd"] >= int(z["nr_base_cd"]*z["nr_cd_mul"])-1000)
                else:
                    effect = (not z["body_valid"] and not z["risen"] and z["heresy"] == 3
                              and z["favor"] == 0 and z["nr_cd"] <= 0)
                key = "raises" if case == "P0" else "penances"
                effect = effect and (status_number(after_status, key) is not None
                    and status_number(before_status, key) is not None
                    and status_number(after_status, key) == status_number(before_status, key)+1)
                result.update(payment=payment, consumer_effect=effect)
            else:
                no_spend = not paid
                no_effect = (all(not r["risen"] and r["heresy"] == a["heresy"] and r["nr_cd"] <= 0 for r in f)
                             and favor_natural(f))
                no_effect = no_effect and all(status_number(before_status, key) is not None
                    and status_number(before_status, key) == status_number(after_status, key) for key in ("raises", "penances"))
                if case in ("P1", "P3"):
                    no_effect = no_effect and all(r["body_valid"] for r in f)
                result.update(payment=no_spend, consumer_effect=no_effect)
        if case in ("CAL", "C0", "C1"):
            require(all(r["target_valid"] and r["target"] == h["target"] and r["target_name"] == TARGET
                        and r["target_max"] == 500 and finite(r["target_hp"]) and r["target_hp"] > 0 for r in f),
                    "identified live target HP, no disappearance credit", errors)
            action_at = h["action_at"]
            target_before = [r for r in f if r["now"] <= action_at+100]
            require(target_before and all(abs(r["target_hp"]-a["target_hp"]) < .003 for r in target_before),
                    "no target damage before recovery input", errors)
            recovery = [r for r in f if r["now"] >= action_at+100]
            moved = bool(recovery and math.dist((recovery[0]["x"], recovery[0]["y"]), (z["x"], z["y"])) > 4)
            hit = a["target_hp"]-z["target_hp"] > .01 and any(r["button"] == "main" for r in recovery)
            controls = moved and hit and all(r["raising_left"] == r["stance_left"] == -1
                and not r["root"] and not r["silence"] and not r["disarm"] for r in recovery if r["now"] > action_at+200)
            controls = controls and "channel none" in after_status and all(status_number(after_status, key) == 0
                    for key in ("locked", "beam", "dashpin"))
            if case != "CAL":
                calibration = evaluate(row.get("calibration", {}))
                require(calibration.get("valid") is True and calibration.get("healthy") is True,
                        "actual same-lane movement/attack positive control", errors)
                cal_frames = calibration.get("trace", {}).get("frames", [])
                interventions = [r for r in samples if r["phase"] == "before_fixture"]
                if cal_frames and interventions:
                    ca, actual = cal_frames[0], interventions[0]
                    require(math.dist((ca["target_x"]-ca["x"], ca["target_y"]-ca["y"]),
                                      (actual["target_x"]-actual["x"], actual["target_y"]-actual["y"])) <= 2,
                            "calibration matches actual landed target geometry", errors)
                require(z["now"] < h["deadline"]-100 and row.get("geometry", {}).get("valid") is True,
                        "recovery before original expiry and certified free lane", errors)
                require(type(row["after"].get("clock", {}).get("sceneMs")) is int
                        and row["after"]["clock"]["sceneMs"] < h["deadline"]-100,
                        "after product beam/channel/pin observation before original expiry", errors)
                # Normal Penance approach consumes its own dash charge. Never ask
                # for a refund; restoration must preserve its measured own clock.
                if case == "C1":
                    require(dash_accounting(row).get("valid") is True,
                            "authored approach dash charge/cooldown accounting", errors)
            result.update(recovery=controls)
            if case == "CAL":
                result.update(payment=True, consumer_effect=True)
        result["valid"] = not errors
        result["healthy"] = not errors and result.get("payment", False) and result.get("consumer_effect", False) and result.get("recovery", True)
    except (KeyError, TypeError, ValueError, AssertionError, IndexError, OverflowError) as exc:
        errors.append("missing/invalid source/timing observation: " + repr(exc))
    return result


def all_rows(rows, expected):
    """Every requested row remains visible, including exceptions and setup refusal."""
    return (type(rows) is list and [r.get("case") for r in rows] == list(expected)
            and all(evaluate(r).get("healthy") is True for r in rows))


def run_rows(rows, trial, read_log, score, initial_stop=None):
    """Stop setup/native dispatch after an invalid prerequisite; retain all rows.

    A valid consumer FAIL may proceed to the next independent fresh row. A
    blocked setup, uncertain acknowledgement, exception or invalid trace stops
    all further setup/native dispatches. Remaining placeholders score false
    with a causal unrun marker; they never read the game or retry setup.
    """
    reason, failed_case, dispatched = initial_stop, None, 0
    for row in rows:
        if reason is not None:
            row["unrun"] = {"cause": reason, "after_case": failed_case, "no_setup_or_native_dispatch": True}
            row["log"] = ""
            row["evaluation"] = {"valid": False, "healthy": False, "errors": ["unrun: "+reason]}
        else:
            mark = None
            try:
                mark = len(read_log())
                dispatched += 1
                trial(row)
            except Exception as exc:
                row["exception"] = repr(exc)
            finally:
                try:
                    row["log"] = read_log()[mark:] if mark is not None else ""
                except Exception as exc:
                    row["log_error"] = repr(exc)
                    row["log"] = ""
                try:
                    row["evaluation"] = evaluate(row)
                except Exception as exc:
                    row["evaluation"] = {"valid": False, "healthy": False, "errors": ["oracle exception: "+repr(exc)]}
                if any(key in row for key in ("blocked", "exception", "log_error")):
                    row["evaluation"]["valid"] = False
                    row["evaluation"]["healthy"] = False
                    row["evaluation"]["errors"].append("trial setup/dispatch prerequisite failed")
        try:
            score(row)
        except Exception as exc:
            row["scoring_error"] = repr(exc)
            row["evaluation"]["valid"] = row["evaluation"]["healthy"] = False
            row["evaluation"]["errors"].append("row scoring failed: "+repr(exc))
        if reason is None and row["evaluation"].get("valid") is not True:
            failed_case = row["case"]
            detail = next((str(row[key]) for key in ("blocked", "exception", "log_error", "scoring_error") if key in row),
                          "; ".join(row["evaluation"].get("errors", [])))
            reason = str(failed_case)+" prerequisite/dispatch failure: "+detail
    return {"stopped_on_prerequisite": reason is not None, "after_case": failed_case,
            "reason": reason, "dispatched_rows": dispatched}


def collect(game, accepted, timeout=20):
    if not finite(timeout) or not 0 < timeout <= 30:
        raise ValueError("collector requires a single absolute deadline in(0,30] seconds")
    deadline = time.monotonic()+timeout
    first = game.wait_gl(lambda e: e.get("ev") == "forgechannel" and e.get("id") == accepted.get("id")
                         and e.get("tag") == accepted.get("tag") and e.get("part") == 0, max(0, deadline-time.monotonic())) or {}
    parts = first.get("parts")
    if type(parts) is int and 1 <= parts <= 1024:
        for part in range(1, parts):
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                break
            found = game.wait_gl(lambda e: e.get("ev") == "forgechannel" and e.get("id") == accepted.get("id")
                                and e.get("tag") == accepted.get("tag") and e.get("part") == part, remaining)
            if not found:
                break  # Return all retained partial chunks; the strict trace rejects incompleteness.
    return [e for e in game.gl if e.get("ev") == "forgechannel" and e.get("id") == accepted.get("id")
            and e.get("tag") == accepted.get("tag")]


def run(p, mode="payment", expected_product_sha=ORIGINAL_SHA, **_):
    from gamelab.bots.plan_forgemaster import Checks as Base
    from gamelab.bots.qa_forgemaster_channel_navigation import prepare_forge_lane
    import hashlib
    from pathlib import Path

    class Checks(Base):
        def raw(self):
            return {"state": self.gl("state"), "skills": self.gl("skills"), "status": self.forge_status(),
                    "clock": self.gl("clock"), "bodies": self.hwp("forge bodies", .2, until="forge bodies"), "risen": self.risen()}

        def native(self, row, body, target, direction, favor):
            row["before"] = self.raw()
            row["cost"] = self.gl("skillcost", NR, CLASS)
            row["accepted"] = self.gl("forgechannel", row["case"]+"-"+str(time.time_ns()), row["case"],
                                      body, target, *direction, favor)
            row["chunks"] = collect(self.g, row["accepted"], 22) if row["accepted"].get("ok") else []
            row["after"] = self.raw()

        def trial(self, row):
            case = row["case"]
            self.setup_forge(case)
            if not self.to_arena(case):
                row["blocked"] = "arena setup failed"; return
            if not self.god(False):
                row["blocked"] = "god/free-resource setup failed"; return
            row["rank_setup"] = {"levels": dict(self.lvl), "nr_penance": int(self.bind(NR, "nr-penance")),
                                 "coh_lunge": float(self.bind(COH, "coh-lunge"))}
            direction, row["geometry"] = prepare_forge_lane(self, case)
            if direction is None:
                row["blocked"] = "bounded legal walk found no complete current200px certificate"; return
            x, y = self.pos()
            favor = self.favor_path()
            self.set_heresy(0); self.set_stacks(favor, 0)
            self.gl("mana", 99999)
            target = -1
            penance = case in ("P2", "P3", "C1")
            body_offset = (70*direction[0], 70*direction[1])
            landing = (x+body_offset[0], y+body_offset[1]+10) if penance else (x, y)
            if case.startswith("C"):
                # Actual calibration at the intended post-approach geometry;
                # teleporting is setup only, never counted as recovery movement.
                self.gl("teleport", *landing); time.sleep(.2)
                spawned = self.gl("spawn", TARGET, 100*direction[0], 100*direction[1])
                cal = {"case": "CAL"}; row["calibration"] = cal
                self.native(cal, -1, spawned.get("unit", -1), direction, favor)
                if not evaluate(cal).get("healthy"):
                    row["blocked"] = "actual walking/owned-target attack calibration failed"; return
                self.gl("kill", 900, "target_dummy")
                self.gl("teleport", *landing); time.sleep(.2)
                spawned = self.gl("spawn", TARGET, 100*direction[0], 100*direction[1])
                target = spawned.get("unit", -1)
                target_xy = (spawned.get("x"), spawned.get("y"))
                ray = self.gl("rayhit", *landing, *target_xy) if all(finite(v) for v in target_xy) else {}
                row["landed_geometry"] = {"valid": spawned.get("ok") is True and target > 0
                    and ray.get("ok") is True and ray.get("wall") is False, "spawn": spawned, "ray": ray, "landing": landing}
                if not row["landed_geometry"]["valid"]:
                    row["blocked"] = "post-approach target geometry not certified"; return
                self.gl("teleport", x, y); time.sleep(.2)
            uid = self.body(BOSS if case in ("P0", "P1", "C0") else NORMAL, *body_offset)
            row["body"] = uid
            if penance:
                # The legitimate H0 lunge check marks the actual body rolled.
                # It is done before H4/Favor5, never by a roll/chance setter.
                approach = self.gl("input", 350, *direction)
                approach_done = self.g.wait_gl(lambda e: e.get("ev") == "input_done" and e.get("id") == approach.get("id"), 4) or {}
                time.sleep(.1)
                rolled = self.hwp("forge bodies", .2, until="forge bodies")
                h0 = self.heresy()
                retreat = self.gl("input", 350, -direction[0], -direction[1])
                retreat_done = self.g.wait_gl(lambda e: e.get("ev") == "input_done" and e.get("id") == retreat.get("id"), 4) or {}
                time.sleep(.1)
                actual = self.pos()
                input_valid = all(r.get("ok") is True for r in (approach, retreat)) and all(type(r.get("frames")) is int and r["frames"] > 0
                    for r in (approach_done, retreat_done))
                row["pre_roll"] = {"body": uid, "heresy": h0, "ordinary_input": input_valid, "raw": rolled,
                    "approach": approach, "approach_done": approach_done, "retreat": retreat, "retreat_done": retreat_done,
                    "rolled": bool(re.search(r"\| " + str(uid) + r" [^|]*\brolled\b", rolled)),
                    "approach_end": actual}
                row["pre_roll"]["valid"] = input_valid and h0 == 0 and row["pre_roll"]["rolled"]
                if not row["pre_roll"]["valid"]:
                    row["blocked"] = "ordinary H0 approach did not establish exact body pre-roll"; return
                # Return to the certified origin only as fixture preparation.
                self.gl("teleport", x, y); time.sleep(.2)
                self.set_heresy(4)
                self.set_stacks(favor, 5)  # last setup action: natural expiry observed natively
            self.native(row, uid, target, direction, favor)
            if case == "C1":
                row["dash_accounting"] = dash_accounting(row)

    c = Checks(p)
    expected = ("P0", "P1", "P2", "P3") if mode == "payment" else ("C0", "C1") if mode == "cancel" else ()
    rows = [{"case": name, "before": None, "after": None, "accepted": {}, "chunks": []} for name in expected]
    c.out["rows"] = rows; c.out["supplemental"] = dict(SUPPLEMENTAL)
    product = Path(__file__).resolve().parents[2]/"mods/specs/scripts/HWP/Specs/Forgemaster.as"
    actual_sha = hashlib.sha256(product.read_bytes()).hexdigest()
    c.out["product_guard"] = {"actual": actual_sha, "expected": expected_product_sha, "original": ORIGINAL_SHA}
    def score(row):
        c.flag(row["case"]+"_contract", row["evaluation"]["valid"], str(row["evaluation"]["errors"]))
        c.flag(row["case"]+"_healthy", row["evaluation"]["healthy"], str({k: v for k, v in row["evaluation"].items() if k != "trace"}))
    if actual_sha != expected_product_sha:
        c.flag("product_guard", False, "Product bytes differ from explicitly requested baseline/repair SHA")
        c.out["row_dispatch"] = run_rows(rows, c.trial, c.g.read_log, score,
            initial_stop="global product SHA prerequisite mismatch; no setup/native dispatch authorized")
        c.flag("all_rows", False, "No native fixture run after source mismatch")
        return c.out
    c.out["row_dispatch"] = run_rows(rows, c.trial, c.g.read_log, score)
    c.flag("all_rows", bool(expected) and all_rows(rows, expected), "Every primary row retained and independently scored")
    c.out.update(notes=c.notes, scope="controlled original-product input consumers; no supplemental or ordinary-play credit",
        dispatch_policy="Stop all further setup/native rows after blocked/exception/invalid prerequisite; retain causal unrun placeholders. Valid product consumer FAILs may proceed to later independent fresh rows; no unchanged setup retry.")
    return c.out


def dash_accounting(row):
    """Compare recorded approach charge consumption and own cooldown restoration.

    The first completed approach sample is the pin's recorded native cooldown;
    restore is bounded by the original own cooldown, never a requested refund.
    This is an explicit preliminary gate: missing native clock provenance blocks
    C1 rather than manufacturing a valid result from post-cancel cooldown alone.
    """
    t = trace(row.get("accepted", {}), row.get("chunks", []))
    result = {"valid": False, "trace_valid": t["valid"]}
    if not t["valid"]:
        return result
    f, h = t["frames"], t["head"]
    try:
        active = [r for r in f if r["dash_cast"] > 0 or r["dash_remaining"] > 0]
        if not active:
            return {**result, "reason": "actual approach dash not observed before landing/pin"}
        first, initial, last = active[0], f[0], f[-1]
        own_at_end = max(0, first["dash_cd"]-(last["now"]-first["now"]))
        # First active frame must precede landing/removal and show the actual
        # cast's own cooldown, before a larger channel pin replaces it.
        upper = int(first["dash_base_cd"]*first["dash_cd_mul"])
        valid = (first["now"] < h["action_at"] and 0 < first["dash_cd"] <= upper
            and abs(last["dash_cd"]-own_at_end) <= 2*max(r["dt"] for r in f)
            and last["dash_dist"] == initial["dash_dist"]
            and all(abs(r["dash_cd"]-max(0, first["dash_cd"]-(r["now"]-first["now"]))) <= 2*max(v["dt"] for v in f)
                    for r in f if r["now"] >= h["action_at"]+200)
            and all(r["infinite_dashes"] is False and r["dash_max"] == initial["dash_max"]
                    and r["dash_recharge_ms"] == initial["dash_recharge_ms"] for r in f)
            and initial["dash_charges"] > 0 and initial["dash_charges"] == initial["dash_max"])
        # Declared fresh full pool permits exactly the actual approach's one
        # charge loss; each later gain must match the recorded native timer.
        spent = gained = 0
        for a, b in zip(f, f[1:]):
            delta = b["dash_charges"]-a["dash_charges"]
            if delta < 0:
                spent -= delta
                valid = valid and delta == -1 and b["now"] <= first["now"]+100
            if delta > 0:
                gained += delta
                valid = valid and delta == 1 and a["dash_recharge"]+(b["now"]-a["now"]) >= a["dash_recharge_ms"]-100
        valid = valid and spent == 1 and last["dash_charges"] == initial["dash_charges"]-1+gained
        return {"valid": valid, "own_cooldown_at_first_dash": first["dash_cd"], "expected_at_end": own_at_end,
                "actual_at_end": last["dash_cd"], "charges_spent": spent, "natural_charges_gained": gained,
                "first_dash": first, "last": last}
    except (KeyError, TypeError, ValueError):
        return {**result, "reason": "missing native own-clock/charge/recharge inputs"}
