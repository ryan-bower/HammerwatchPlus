"""Corrected native-time passive regressions; retain the original failed captures.

All damage/healing comes from native inputs or explicitly controlled cht_damage.
No ordinary-run, acquisition, exact general DPS, or co-op credit is implied.
"""
import math
import re
import time

from gamelab.bots.qa_firearms_missing_orbs import Checks as Base
from gamelab.bots.qa_firearms_passives import RESIST

GLOW = "players/hwp/firearms/buffs_firearms.sval:turret_glow"
TURRET = "hwp_fs_turret"


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def crit_control(reply):
    return (reply.get("ok") is True and reply.get("skill") == TURRET
            and reply.get("override_active") is True and finite(reply.get("left"))
            and reply["left"] > 0 and reply.get("crit_chance") == 0
            and reply.get("spell_crit_chance") == 0)


def live_trace(trace, hp_max):
    rows = trace.get("samples", [])
    return bool(trace.get("valid") and len(rows) >= 4 and all(
        row.get("valid") is True and row.get("hpMax") == hp_max
        and row.get("actor_tick_rate") == 0 and finite(row.get("hpExact"))
        and 0 < row["hpExact"] <= hp_max and finite(row.get("now"))
        and (i == 0 or type(row.get("dt")) is int and 0 < row["dt"] <= 66)
        for i, row in enumerate(rows)))


def hp_slope(trace, repair):
    """Anchored native time, with explicit callback-phase/float32 error bounds.

    turret.unit omits tick-rate; CompositeActorProperties defaults it to zero.
    Turret.Update applies decay and optional repair every callback. At 1x time,
    observer/actor ordering can shift each endpoint by at most one native frame.
    The bound uses both endpoints and both unsigned terms, plus three float32
    arithmetic operations per callback. It never resets accumulated error.
    """
    rows = trace.get("samples", [])
    if not live_trace(trace, 100) or any(row["hpExact"] >= 99 for row in rows):
        return {"valid": False, "reason": "incomplete/nonlive/tick-rate/frame/HP fixture"}
    anchor = rows[1]  # omit initial observer-start phase from the anchor
    max_dt = max(row["dt"] for row in rows[1:])
    net = repair - 100 / 30
    phase = 2 * max_dt / 1000 * (repair + 100 / 30)
    float32 = (len(rows) + 2) * 3 * 100 * 2**-24
    bound = phase + float32 + 2e-9
    residuals = []
    for row in rows[1:]:
        elapsed = (row["now"] - anchor["now"]) / 1000
        predicted = anchor["hpExact"] + net * elapsed
        residuals.append({"now": row["now"], "actual": row["hpExact"],
                          "predicted": predicted, "error": row["hpExact"] - predicted})
    monotone = all((b["hpExact"] >= a["hpExact"] if net > 0 else b["hpExact"] <= a["hpExact"])
                   for a, b in zip(rows, rows[1:]))
    span = rows[-1]["now"] - anchor["now"]
    return {"valid": span >= 1300 and monotone and all(abs(r["error"]) <= bound for r in residuals),
            "native_span_ms": span, "repair_hp_per_second": repair, "net_hp_per_second": net,
            "max_native_frame_ms": max_dt, "phase_bound_hp": phase,
            "float32_bound_hp": float32, "total_bound_hp": bound, "residuals": residuals}


def shot_sample(trace):
    rows = trace.get("samples", [])
    if not live_trace(trace, 600):
        return {"valid": False, "reason": "incomplete/nonlive/target/frame fixture", "hits": []}
    hits = [{"now": b["now"], "damage": a["hpExact"] - b["hpExact"]}
            for a, b in zip(rows, rows[1:]) if b["hpExact"] < a["hpExact"]]
    amounts = [hit["damage"] for hit in hits]
    # 600HP float32 unit health gives <=0.000036HP per arithmetic ULP.
    # 0.02HP permits serialization/arithmetic noise, not a merged shot or crit.
    constant = bool(amounts) and max(amounts) - min(amounts) <= .02
    return {"valid": len(hits) >= 5 and constant, "hits": hits,
            "mean_damage": sum(amounts) / max(1, len(amounts)),
            "constant_normal_hit_amplitude": constant, "final_hp": rows[-1]["hpExact"]}


class Checks(Base):
    def actor_window(self, uid, tag, ms):
        started = self.gl("actorbuffobserve", tag, ms, uid, GLOW)
        trace = self.collect_trace("actorbuffobserve", tag, ms / 1000 + 4) if started.get("ok") else {
            "valid": False, "samples": [], "parts": []}
        trace["accepted"] = started
        trace["valid"] = trace["valid"] and started.get("ok") is True
        return trace

    def damage_window(self, direction, tag):
        actual, uid = self.tough(direction, 120, RESIST)
        trace = self.actor_window(uid, tag, 5000)
        return {"target": uid, "direction": actual, "trace": trace, **shot_sample(trace)}

    def myturret(self):
        if not self.prepare("QAMyTurNative", "hwp_firearms_engineer"):
            return
        equipped, gear = self.fixture_loadout("hwp_glock_mh_01")
        self.check("myturret_native_pistol", equipped, gear)
        scale = self.gl("cvars", "g_timescale")
        self.check("myturret_native_1x", scale.get("cvars", {}).get("g_timescale") == 1, scale)
        if not equipped or scale.get("cvars", {}).get("g_timescale") != 1:
            return
        direction = self.open_dirs(150)[0]
        for rank, (repair, boost) in enumerate(zip((10, 15, 15, 20, 20), (.1, .1, .15, .15, .2)), 1):
            learned = self.learn_rank("hwp_fs_myturret", rank)
            self.gl("kill", 800, "hwp/firearms/units/turret")
            self.ready(TURRET, 25)
            self.top_up()
            fixture = self.gl("skillcrit", TURRET, 0)
            try:
                self.targeted(self.entry(self.bar(), TURRET).get("button"),
                              direction[0] * 80, direction[1] * 80, (0, 120))
                time.sleep(.8)
                turret = self.turret_one()
                far_distance = self.turret_distance(turret)
                far_damage = self.damage_window(direction, f"mytur-r{rank}-far-damage")
                self.gl("kill", 400, "hwp/firearms/units/turret", .2)
                self.gl("input", 400, *direction, *direction)
                time.sleep(.6)  # >200ms booster refresh; native trace is the measurement
                near = self.turret_one()
                near_distance = self.turret_distance(near)
                repair_trace = self.actor_window(near.get("unit"), f"mytur-r{rank}-repair", 1500)
                repaired = hp_slope(repair_trace, repair)
                near_after = self.turret_one()
                self.check(f"myturret_native_r{rank}_repair", learned == rank
                           and turret.get("unit") == near.get("unit") == near_after.get("unit")
                           and far_distance > 60 and near_distance <= 60
                           and self.turret_distance(near_after) <= 60 and repaired["valid"],
                           {"rank": rank, "far_distance": far_distance, "near_distance": near_distance,
                            "after_distance": self.turret_distance(near_after),
                            "native_model": repaired, "trace": repair_trace})
                near_damage = self.damage_window(direction, f"mytur-r{rank}-near-damage")
                ratio = near_damage.get("mean_damage", 0) / max(.001, far_damage.get("mean_damage", 0))
                self.check(f"myturret_native_r{rank}_damage", far_damage["valid"] and near_damage["valid"]
                           and abs(ratio - (1 + boost)) < .045 and ratio > 1.03,
                           {"rank": rank, "expected_ratio": 1 + boost, "observed_ratio": ratio,
                            "far": far_damage, "near": near_damage})
                self.gl("input", 800, -direction[0], -direction[1], -direction[0], -direction[1])
                time.sleep(.6)
                left = self.turret_one()
                distance = self.turret_distance(left)
                decay_trace = self.actor_window(left.get("unit"), f"mytur-r{rank}-leave", 1500)
                decay = hp_slope(decay_trace, 0)
                after = self.turret_one()
                final_crit = self.gl("skillcrit", TURRET)
                self.check(f"myturret_native_r{rank}_leave", distance > 60
                           and left.get("unit") == after.get("unit")
                           and self.turret_distance(after) > 60 and decay["valid"],
                           {"rank": rank, "distance": distance, "after_distance": self.turret_distance(after),
                            "native_model": decay, "trace": decay_trace})
                self.check(f"myturret_native_r{rank}_crit_fixture", crit_control(fixture) and crit_control(final_crit),
                           {"rank": rank, "before": fixture, "after": final_crit,
                            "scope": "DeployTurret Spell weapon routing; constant actual per-hit HP controls also required."})
            finally:
                self.gl("skillcrit", TURRET, "restore")
        self.gl("kill", 800, "hwp/firearms/units/turret")
        self.clear_dummies()
        self.to_town()

    def earn_adrenaline(self, cap, direction, tag):
        self.clear_dummies()
        actual, _ = self.clear_dir(direction, 80)
        targets = [self.dummy(actual[0] * 80, actual[1] * 80) for _ in range(35)]
        self.gl("kill", 300, "target_dummy", .001)
        setup = self.hps(targets)
        setup_ok = len(set(targets)) == 35 and None not in targets and all(abs(setup[x] - .001) < .0001 for x in targets)
        self.top_up()  # CLIP + mana only; deliberately never heals the injured player
        trials = []
        for trial in range(2):
            self.gl("input", 10000, 0, 0, *actual, "main")
            time.sleep(10.4)
            trials.append({"trial": trial + 1, "stacks": self.stacks("adrenaline")})
        earned = self.stacks("adrenaline")
        killed = sum(hp == 0 for hp in self.hps(targets).values())
        valid = setup_ok and killed > cap and earned == cap and all(row["stacks"] <= cap for row in trials)
        result = {"expected_cap": cap, "earned": earned, "actual_gunfire_kills": killed,
                  "fixture_hp": setup, "fixed_trials": trials}
        self.check(tag, valid, result)
        return valid

    def adrenaline_hurt(self, rank, cap, heal, damage, tag, require_deficit):
        before = self.gl("state").get("player", {})
        requested = int(cap * heal * before.get("hpMax", 0) + .5)
        expected_hp = min(before.get("hpMax", 0), before.get("hp", 0) - damage + requested)
        unclipped = before.get("hp", 0) - damage + requested < before.get("hpMax", 0) - 2
        mark = self.log_pos()
        self.g.console("cht_damage 60")
        time.sleep(.3)
        after = self.gl("state").get("player", {})
        log = self.log_from(mark)
        spent = re.search(r"adrenaline: hurt, (\d+) stacks spent for (\d+) health", log)
        healed = re.search(r"adrenaline: healed (\d+) of (\d+)", log)
        remaining = self.stacks("adrenaline")
        valid = (damage > 0 and before.get("hp", 0) > damage and remaining == 0
                 and spent is not None and int(spent[1]) == cap and int(spent[2]) == requested
                 and healed is not None and int(healed[1]) == requested and int(healed[2]) == requested
                 and abs(after.get("hp", 0) - expected_hp) <= 2
                 and (unclipped if require_deficit else before.get("hp") == before.get("hpMax")))
        self.check(tag, valid, {"rank": rank, "native_hurt_input": 60, "baseline_damage_without_stacks": damage,
                              "before": before, "after": after, "expected_heal_request": requested,
                              "expected_final_hp": expected_hp, "full_heal_fits_missing_hp": unclipped,
                              "separate_overcap_control": not require_deficit,
                              "hurt_log": spent.group(0) if spent else None,
                              "heal_return_before_hp_cap": int(healed[1]) if healed else None,
                              "native_return_source": "Player.as326-346", "remaining_stacks": remaining})

    def adrenaline(self):
        if not self.prepare("QAAdrenNative", "hwp_firearms_assault"):
            return
        direction = self.open_dirs(130)[0]
        for rank, (cap, heal) in enumerate(zip((20, 25, 25, 30, 30), (.005, .005, .01, .01, .015)), 1):
            learned = self.learn_rank("hwp_fs_adrenaline", rank)
            self.g.console("cht_give_health 999")
            full = self.gl("state").get("player", {})
            calibration_bank = self.stacks("adrenaline")
            self.g.console("cht_damage 60")
            time.sleep(.25)
            damaged = self.gl("state").get("player", {})
            baseline = full.get("hp", 0) - damaged.get("hp", 0)
            self.g.console("cht_give_health 999")
            self.check(f"adrenaline_native_r{rank}_rank", learned == rank and baseline > 0 and calibration_bank == 0,
                       {"rank": rank, "learned": learned, "full": full, "damaged": damaged, "baseline": baseline, "calibration_bank": calibration_bank})
            self.earn_adrenaline(cap, direction, f"adrenaline_native_r{rank}_full_cap")
            self.adrenaline_hurt(rank, cap, heal, baseline, f"adrenaline_native_r{rank}_full_hp_control", False)
            self.g.console("cht_give_health 999")
            empty = self.stacks("adrenaline")
            prior = self.gl("state").get("player", {})
            self.g.console("cht_damage 120")  # injury is made only while bank0
            time.sleep(.25)
            injured = self.gl("state").get("player", {})
            empty_after = self.stacks("adrenaline")
            self.check(f"adrenaline_native_r{rank}_injury_bank0", empty == empty_after == 0
                       and prior.get("hp") == prior.get("hpMax")
                       and 0 < injured.get("hp", 0) < prior.get("hp", 0) - baseline,
                       {"bank_before": empty, "bank_after": empty_after, "before": prior, "after": injured,
                        "controlled_native_hurt_input": 120})
            self.earn_adrenaline(cap, direction, f"adrenaline_native_r{rank}_injured_cap")
            self.adrenaline_hurt(rank, cap, heal, baseline, f"adrenaline_native_r{rank}_full_actual_heal", True)
        self.clear_dummies()
        self.to_town()


def run(p, section="myturret", **_):
    checks = Checks(p)
    try:
        getattr(checks, section)()
    except Exception as exc:
        checks.check(section + "_crashed", False, {"error": repr(exc)})
    checks.out["ok"] = bool(checks.rows) and all(row["runtime"] == "PASS" for row in checks.rows)
    checks.out["rows"] = checks.rows
    checks.out["notes"] = checks.notes
    checks.out["terminal"] = " | ".join(checks.notes)[-5000:]
    return checks.out
