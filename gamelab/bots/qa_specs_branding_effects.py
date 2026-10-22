"""Branding rank/orb effects measured with native damage and live target HP.

Cooldown/mana and Essence setup isolate individual cases. They do not establish
ordinary play. Native Damage rounds its input, so HP ratios allow two damage
points for independent native rounding; large real Tail hits separate all ranks.
"""
import math
import time

from gamelab.bots.qa_specs_banner_brand import Checks as Base
from gamelab.bots.plan_specs import TARGET
from gamelab.bots.qa_classes import QA_DUMMY
from gamelab.bots.qa_observe import collect
from gamelab.bots.qa_specs_navigation import walk_trident_lane

PB = "hwp_wlk_pyrebrand"
EE = "hwp_wlk_essence_extraction"
ESSENCE = "players/warlock/stacks_warlock.sval:essence"
COMBUST = "hwp_wlk_pb_combustion"
SPREAD = "hwp_wlk_pb_proliferation"
EMPOWER = "hwp_wlk_ee_essence_empowerment"
RELEASE = "hwp_wlk_ee_released_essence"


def audit_rate(events, cooldown_ms, gain):
    """Compare each real HP hit with native stack transitions, allowing two frames.

    A cooldown can only be distinguished at actual qualifying hits; raw hit
    times remain evidence of that resolution rather than implying finer timing.
    """
    errors, hits, gains = [], [], []
    needed = {"now", "stacks", "target_hpExact", "target_valid"}
    if not events or any(not needed.issubset(event) for event in events):
        return {"ok": False, "errors": ["native rate event fields missing"]}
    if events[0]["stacks"] != 0:
        return {"ok": False, "errors": ["initial native stack count is not zero"]}
    last_gain = None
    for before, after in zip(events, events[1:]):
        if not before.get("target_valid") or not after.get("target_valid"):
            errors.append("target invalid during rate observation")
            continue
        damage = before["target_hpExact"] - after["target_hpExact"]
        delta = after["stacks"] - before["stacks"]
        now = after["now"]
        if delta not in (0, gain):
            errors.append(f"unexpected stack transition {delta} at {now}")
        if damage > .001:
            hits.append({"now": now, "damage": damage, "gain": delta})
            if (last_gain is None or now - last_gain > cooldown_ms + 67) and delta != gain:
                errors.append(f"eligible real hit missed its gain at {now}")
        elif delta > 0:
            errors.append(f"stack gain without observed target damage at {now}")
        if delta > 0:
            if last_gain is not None and now - last_gain < cooldown_ms - 67:
                errors.append(f"gain inside cooldown at {now}: {now-last_gain}ms")
            gains.append(now)
            last_gain = now
    if len(gains) < 2 or len(hits) < len(gains):
        errors.append("insufficient real hits and repeated gains")
    if events[-1].get("stacks") != gain * len(gains) or events[-1].get("stacks", 10) >= 10:
        errors.append("stack total mismatch or cap obscures rate")
    return {"ok": not errors, "errors": errors, "hits": hits, "gain_times": gains,
            "intervals_ms": [b-a for a, b in zip(gains, gains[1:])]}


class Checks(Base):
    def prepare(self, tag, wide=False):
        self.setup(tag, "warlock", "hwp_warlock_branding", [])
        if not self.out.get(tag + "_char") or not self.out.get(tag + "_learned"):
            return False
        if not self.enter_floor(tag):
            return False
        self.hwp("skillpoints 100")
        points = [(x, y, 12) for x, y in ((-64, 0), (64, 0), (0, -64), (0, 64))] if wide else ()
        lane, note = walk_trident_lane(self, front=141, back_neighbor=True, ray_distance=141,
                                         tag=tag, clearance_points=points)
        self.flag(tag + "_lane", bool(lane), note)
        if not lane:
            return False
        self.direction = lane[0]
        return self.noncrit(tag)

    def noncrit(self, tag):
        reply = self.gl("skillcrit", PB, 0)
        stats = self.gl("benchstats")
        ok = bool(reply.get("ok")) and stats.get("spellCrit") == 0
        self.flag(tag + "_noncrit", ok, str({"override": reply, "stats": stats}))
        return ok

    def orb_rank(self, orb, wanted):
        # Only called in fresh characters/sections, increasing one orb at a time.
        for _ in range(3):
            self.gl("orb", orb, "down")
        return self.gl("orb", orb, wanted) if wanted else {}

    def hps(self):
        return {u["unit"]: u for u in self.gl("near", 300, "target_dummy").get("units", [])
                if not u.get("dead") and "hpExact" in u and "hpMax" in u}

    def fresh(self, inside=None, outside=None, homogeneous=False):
        self.gl("kill", 350, "target_dummy")
        ox, oy = self.pos()
        dx, dy = self.direction
        offsets = [40] + ([40 + inside] if inside is not None else []) + ([40 - outside] if outside is not None else [])
        for index, offset in enumerate(offsets):
            self.gl("spawn", QA_DUMMY if homogeneous or index == 0 else TARGET, round(dx * offset), round(dy * offset))
        current = self.hps()
        ordered = []
        for offset in offsets:
            matches = [u for u in current.values()
                       if math.hypot(u["x"] - ox - dx * offset, u["y"] - oy - dy * offset) <= 1]
            ordered.append(matches[0]["unit"] if len(matches) == 1 else None)
        ok = (len(current) == len(offsets) and None not in ordered
              and current.get(ordered[0], {}).get("hpMax") == 15000
              and (not homogeneous or all(current[u].get("hpMax") == 15000
                    and abs(current[u].get("hpExact", 0) - 15000) < .01 for u in ordered)))
        self.flag("fresh_" + str(len(self.out)), ok, str({"offsets": offsets, "units": current}))
        return ordered if ok else []

    @staticmethod
    def loss(before, after, uid):
        if uid not in before or uid not in after:
            return None
        return before[uid]["hpExact"] - after[uid]["hpExact"]

    @staticmethod
    def close(actual, expected, tolerance=.01):
        return actual is not None and expected is not None and abs(actual - expected) <= tolerance

    def detonate(self):
        return self.brand_cast(PB, *self.direction, nocd=False)

    @staticmethod
    def native_round(value):
        return max(1, int(value + .5)) if value > 0 else 0

    def measured_claw(self, tag, uid, source_amount):
        """Native recast, source-predicted full Fire HP, and an actual settling trace."""
        caster = self.g.gl_multi([["benchstats"], ["critprobe", 0, 300, "target_dummy", PB], ["dmgmuls"]])
        self.gl("mana", 250)
        dx, dy = self.direction
        self.gl("input", 700, 0, 0, dx, dy)
        time.sleep(.1)
        mark = len(self.g.read_log())
        begun, cast = self.g.gl_multi([["buffobserve", tag, 3500, "-", "-", uid],
                                      ["castat", PB, dx, dy]])
        time.sleep(.6)  # Native400ms animation must end before cooldown readback.
        early_cd = self.skill_cd(PB)
        observed = collect(self.g, tag)
        log = "\n".join(line for line in self.g.read_log()[mark:].splitlines() if "pyrebrand" in line)
        events = observed.get("events", [])
        stats, probe, elements = caster
        buff_mul = events[0].get("damageMul") if events else None
        fields = (all(row.get("ok") for row in caster) and isinstance(buff_mul, (float, int))
                  and probe.get("skill") == PB and probe.get("rolls") == 0
                  and probe.get("skillCrit") == 0 and probe.get("spellCrit") == 0
                  and all(abs(row.get("damageMul", -1) - buff_mul) < .0001 for row in events))
        expected = None
        direct = pool = ticks = None
        if fields:
            multiplier = (buff_mul * stats["damageMul"] * (200 + stats["spellPower"]) / 200
                          * probe["skillDmgMul"] * probe["damageMul"][1] * elements["fire"])
            direct = self.native_round(self.native_round(source_amount) * multiplier)
            pool = int(direct * .33)
            expected = direct + pool
            left, ticks = pool, 0
            while left > 0:
                left -= max(1, int(left * .5))
                ticks += 1
        hp_events = [b for a, b in zip(events, events[1:])
                     if a.get("target_hpExact", 0) - b.get("target_hpExact", 0) > .01]
        settled = (bool(hp_events) and ticks is not None
                   and observed.get("end", 0) - hp_events[0]["now"] >= ticks * 250 + 67)
        valid = (begun.get("ok") and cast.get("activated") and "claw (recast)" in log
                 and observed.get("usable") and fields and settled
                 and all(row.get("target_valid") and row.get("target_hpMax") == 15000 for row in events)
                 and expected is not None and abs(events[0]["target_hpExact"]
                     - events[-1]["target_hpExact"] - expected) <= .02)
        return {"activated": bool(cast.get("activated")), "log": log, "valid": bool(valid),
                "source_amount": source_amount, "expected_hp_loss": expected, "early_cooldown_ms": early_cd,
                "native_fire_direct": direct, "native_fire_pool": pool,
                "source_pool_tick_bound": ticks, "settled": bool(settled),
                "caster_fields": caster, "observer": observed,
                "scope": "Exact fully settled Fire damage on identical zero-defense QA actors; no finite-time ratio fit."}

    def ranks(self):
        if not self.prepare("pyre_ranks"):
            return
        self.rank("demons_tail", 5, "feed_tail")
        rows, passed, first = [], True, None
        for rank, (base, pct) in enumerate(zip((20, 25, 30, 35, 40), (.10, .15, .25, .35, .50)), 1):
            tag = f"pyre_r{rank}"
            if not self.rank(PB, rank, tag) or not self.noncrit(tag):
                passed = False
                continue
            targets = self.fresh(36, 55, homogeneous=True)
            if not targets:
                passed = False
                continue
            ok, initial_log = self.brand_cast(PB, *self.direction)
            before = self.hps()
            measured = self.measured_claw(tag + "-base", targets[0], base)
            recast, claw_log = measured["activated"], measured["log"]
            after = self.hps()
            base_loss = self.loss(before, after, targets[0])
            last = self.status_num("last")
            first = base_loss if first is None else first
            base_ok = (ok and recast and last == base and base_loss is not None and base_loss > 0
                       and measured["valid"] and abs(base_loss - measured["expected_hp_loss"]) <= .02
                       and self.close(self.loss(before, after, targets[1]), base_loss)
                       and self.close(self.loss(before, after, targets[2]), 0)
                       and (measured["early_cooldown_ms"] or 0) > 7000)
            self.flag(tag + "_claw_damage_radius_cd", bool(base_ok), str({"before": before, "after": after,
                      "base": base, "loss": base_loss, "last": last, "initial_log": initial_log, "claw_log": claw_log}))
            targets = self.fresh(36, 55, homogeneous=True)
            if not targets:
                passed = False
                continue
            branded, _ = self.brand_cast(PB, *self.direction)
            hp0 = self.hps()
            self.tails(1, *self.direction)
            time.sleep(.4)  # native Tail lifetime500ms, castpoint150ms, after the helper's400ms
            hp1 = self.hps()
            fed = self.loss(hp0, hp1, targets[0])
            stored = self.status_num("stored")
            measured_feed = self.measured_claw(tag + "-fed", targets[0], base + (fed or 0) * pct)
            recast, log = measured_feed["activated"], measured_feed["log"]
            hp2 = self.hps()
            actual = self.loss(hp1, hp2, targets[0])
            expected = measured_feed["expected_hp_loss"]
            feed_ok = (branded and recast and fed is not None and fed >= 50 and stored is not None
                       and abs(stored - fed * pct) <= 1.1 and actual is not None and expected is not None
                       and measured_feed["valid"] and abs(actual - expected) <= .02 and self.close(self.loss(hp1, hp2, targets[2]), 0))
            self.flag(tag + "_stored_damage", bool(feed_ok), str({"feed_hp": fed, "stored": stored,
                      "expected_damage": expected, "actual_damage": actual, "log": log}))
            rows.append({"rank": rank, "base": base, "pct": pct, "baseline_loss": base_loss,
                         "base_before": before, "base_after": after, "feed_before": hp0,
                         "feed_after": hp1, "claw_after": hp2, "stored": stored,
                         "expected_damage": expected, "actual_damage": actual,
                         "base_measurement": measured, "feed_measurement": measured_feed})
            passed &= bool(base_ok and feed_ok)
        self.out["pyre_rank_trials"] = rows
        self.flag("pyre_all_ranks", passed and len(rows) == 5)
        self.gl("skillcrit", PB, "restore")
        self.to_town()

    def orbs(self):
        if not self.prepare("brand_orbs", wide=True):
            return
        rows, passed = [], True
        for rank, per in enumerate((.02, .03, .04), 1):
            tag = f"combust_r{rank}"
            self.noncrit(tag)
            self.orb_rank(COMBUST, rank)
            radius = 40 * (1 + per * 10)
            targets = self.fresh(round(radius) - 1, round(radius) + 8)
            if not targets:
                passed = False
                continue
            branded, _ = self.brand_cast(PB, *self.direction)
            self.set_stacks(ESSENCE, 10)
            before = self.hps()
            recast, log = self.detonate()
            after = self.hps()
            loss = self.loss(before, after, targets[0])
            ok = (branded and recast and self.status_num("essence") == 0
                  and self.status_num("last") == round(20 * (1 + per * 10))
                  and loss is not None and loss > 0
                  and self.close(self.loss(before, after, targets[1]), loss)
                  and self.close(self.loss(before, after, targets[2]), 0))
            self.flag(tag + "_damage_radius_spend", bool(ok), str({"radius": radius, "before": before, "after": after, "log": log}))
            rows.append({"orb": COMBUST, "rank": rank, "expected_radius": radius, "before": before, "after": after, "log": log})
            passed &= bool(ok)
        self.orb_rank(COMBUST, 0)
        self.set_stacks(ESSENCE, 0)
        for rank, spread in enumerate((60, 80, 100), 1):
            tag = f"proliferation_r{rank}"
            self.noncrit(tag)
            self.orb_rank(SPREAD, rank)
            targets = self.fresh(spread - 1, spread + 8)
            if not targets:
                passed = False
                continue
            branded, log0 = self.brand_cast(PB, *self.direction)
            self.gl("kill", 50, "qa_class_target_dummy")
            time.sleep(.35)
            before = self.hps()
            recast, log1 = self.detonate()
            after = self.hps()
            hit, outside = self.loss(before, after, targets[1]), self.loss(before, after, targets[2])
            ok = (branded and "for 3000 ms" in log0 and recast and hit is not None and hit > 0
                  and outside is not None and abs(outside) <= .01)
            self.flag(tag + "_spread_boundary_damage", bool(ok), str({"before": before, "after": after, "logs": [log0, log1]}))
            rows.append({"orb": SPREAD, "rank": rank, "spread": spread, "before": before, "after": after, "logs": [log0, log1]})
            passed &= bool(ok)
        self.orb_rank(SPREAD, 0)
        self.rank(PB, 5, "empower_damage_skill")
        for rank, per in enumerate((.01, .02, .03), 1):
            self.noncrit(f"empower_r{rank}")
            self.orb_rank(EMPOWER, rank)
            self.set_stacks(ESSENCE, 0)
            zero = self.gl("dmgmuls")
            values = []
            ok = True
            for n in (1, 5, 10):
                self.set_stacks(ESSENCE, n)
                live = self.gl("dmgmuls")
                delta = live.get("fire", 0) - zero.get("fire", 0)
                expected = per * n * live.get("physical", 0)
                ok &= expected > 0 and abs(delta - expected) <= .002
                values.append({"stacks": n, "multipliers": live, "delta": delta, "expected": expected})
            self.set_stacks(ESSENCE, 0)
            restored = self.gl("dmgmuls")
            ok &= abs(restored.get("fire", 0) - zero.get("fire", 0)) <= .002
            damage_trials = []
            for n in (0, 10):
                targets = self.fresh()
                if not targets:
                    ok = False
                    break
                cast, _ = self.brand_cast(PB, *self.direction)
                self.set_stacks(ESSENCE, n)
                multipliers, before = self.gl("dmgmuls"), self.hps()
                recast, log = self.detonate()
                after = self.hps()
                amount = self.loss(before, after, targets[0])
                ok &= bool(cast and recast and amount is not None and amount > 0)
                damage_trials.append({"stacks": n, "multipliers": multipliers,
                                      "before": before, "after": after, "damage": amount, "log": log})
            if (len(damage_trials) == 2 and all(isinstance(t["damage"], (int, float)) and t["damage"] > 0
                                               and t["multipliers"].get("fire", 0) > 0 for t in damage_trials)):
                d0, d10 = damage_trials
                expected_damage = d0["damage"] * d10["multipliers"]["fire"] / d0["multipliers"]["fire"]
                ok &= d10["damage"] > d0["damage"] and abs(d10["damage"] - expected_damage) <= 2.1
            else:
                expected_damage = None
                ok = False
            self.set_stacks(ESSENCE, 0)
            self.flag(f"empower_r{rank}_actual_multiplier_and_revert", bool(ok), str(values))
            rows.append({"orb": EMPOWER, "rank": rank, "skill_rank": 5, "zero": zero,
                         "values": values, "restored": restored, "damage_trials": damage_trials,
                         "expected_damage": expected_damage})
            passed &= bool(ok)
        # All four legal orbs at max: two transferred brands, one Essence pool.
        # The first claw uses Empowerment before spending; the second has no
        # Essence. Unordered HP losses avoid assuming native query iteration order.
        self.noncrit("brand_combo")
        self.set_stacks(ESSENCE, 0)
        targets = self.fresh()
        base_damage = None
        if targets:
            self.brand_cast(PB, *self.direction)
            before = self.hps()
            self.detonate()
            base_damage = self.loss(before, self.hps(), targets[0])
        self.orb_rank(COMBUST, 3)
        self.orb_rank(SPREAD, 3)
        self.orb_rank(RELEASE, 2)
        targets = self.fresh(60, 60)
        combo_ok = False
        if targets and base_damage is not None and base_damage > 0:
            branded, brand_log = self.brand_cast(PB, *self.direction)
            self.gl("kill", 50, "qa_class_target_dummy")
            time.sleep(.35)
            self.set_stacks(ESSENCE, 0)
            zero_fire = self.gl("dmgmuls")
            self.set_stacks(ESSENCE, 10)
            live_fire, before = self.gl("dmgmuls"), self.hps()
            recast, claw_log = self.detonate()
            after = self.hps()
            actual = [self.loss(before, after, uid) for uid in targets[1:]]
            measured = all(isinstance(n, (int, float)) for n in actual) and zero_fire.get("fire", 0) > 0
            actual = sorted(actual) if measured else actual
            expected = sorted([base_damage, base_damage * 1.4 * live_fire["fire"] / zero_fire["fire"]]) if measured else []
            combo_ok = (branded and "for 3000 ms" in brand_log and recast
                        and measured and len(expected) == 2 and all(abs(a-e) <= 2.1 for a, e in zip(actual, expected))
                        and self.status_num("essence") == 0)
            rows.append({"orbs": [COMBUST, SPREAD, EMPOWER, RELEASE], "ranks": [3, 3, 3, 2],
                         "before": before, "after": after, "actual_damage": actual,
                         "expected_damage": expected, "base_damage": base_damage,
                         "multipliers": [zero_fire, live_fire], "logs": [brand_log, claw_log]})
        self.flag("brand_max_combo_transfer_damage_spend", bool(combo_ok))
        passed &= bool(combo_ok)
        self.out["branding_orb_trials"] = rows
        self.flag("branding_orbs_measured", passed and len(rows) == 10)
        self.gl("skillcrit", PB, "restore")
        self.to_town()

    def scene_gap(self, ms):
        start = self.gl("clock").get("sceneMs")
        if start is None:
            return False
        until = time.monotonic() + 15
        while time.monotonic() < until:
            if self.gl("clock").get("sceneMs", start) - start >= ms:
                return True
            time.sleep(.1)
        return False

    def rate_trial(self, tag, uid, duration_ms, branded):
        self.set_stacks(ESSENCE, 0)
        claws_before = self.status_num("claws") if branded else None
        dx, dy = self.direction
        if branded:
            # Prepare all RPC setup before the six-second brand starts. The native
            # castpoint precedes the first ordinary wand hit in this same-frame batch.
            self.gl("mana", 250)
            self.gl("input", 700, 0, 0, dx, dy)
            time.sleep(.1)
        mark = len(self.g.read_log())
        commands = [["buffobserve", tag, duration_ms + (500 if branded else 1000), "-", ESSENCE, uid]]
        if branded:
            commands.append(["castat", PB, dx, dy, "nocd"])
        commands.append(["input", duration_ms, 0, 0, dx, dy, "main"])
        replies = self.g.gl_multi(commands)
        start, input_reply = replies[0], replies[-1]
        observed = collect(self.g, tag)
        analyzed = audit_rate(observed.get("events", []), self.rate_cd, 2 if branded else 1)
        log = "\n".join(line for line in self.g.read_log()[mark:].splitlines() if "pyrebrand" in line)
        claws_after = self.status_num("claws") if branded else None
        no_claw = not branded or (claws_before is not None and claws_before == claws_after)
        # The extra status read and slow generic brand_cast wrapper previously
        # delayed recast past expiry. Recast directly; it uses existing brands,
        # so no new target aiming or mana preparation is necessary here.
        recast, claw_log = True, ""
        if branded:
            mark = len(self.g.read_log())
            recast_reply = self.gl("castat", PB, dx, dy)
            time.sleep(.4)
            claw_log = "\n".join(line for line in self.g.read_log()[mark:].splitlines() if "pyrebrand" in line)
            recast = bool(recast_reply.get("activated")) and "claw (recast)" in claw_log
        brand_ok = not branded or (replies[1].get("activated") and "for 6000 ms" in log)
        ok = (start.get("ok") and input_reply.get("ok") and observed.get("usable")
              and analyzed["ok"] and no_claw and brand_ok and recast)
        self.flag(tag + "_native_rate", bool(ok), str({"errors": observed.get("errors"), "analysis": analyzed,
                  "no_auto_claw": no_claw, "brand": log, "recast": claw_log}))
        return {"branded": branded, "observer": observed, "analysis": analyzed,
                "claws_before": claws_before, "claws_after": claws_after,
                "brand_ok": bool(brand_ok), "brand_log": log, "recast": recast,
                "claw_log": claw_log, "ok": bool(ok)}

    def essence_rates(self):
        if not self.prepare("essence_rates"):
            return
        equip = self.gl("equip", "mainhand_wand_ice_01", 1, 1)
        self.flag("essence_legal_wand", bool(equip.get("ok")), str(equip))
        rows, passed = [], bool(equip.get("ok"))
        for rank, cooldown in enumerate((2000, 1750, 1500, 1250, 1000), 1):
            if not self.rank(EE, rank, f"essence_r{rank}"):
                passed = False
                continue
            self.rate_cd = cooldown
            targets = self.fresh()
            ready = self.scene_gap(2100)
            self.flag(f"essence_r{rank}_ready", ready)
            if not targets or not ready:
                passed = False
                continue
            plain = self.rate_trial(f"ee-r{rank}-plain", targets[0], 6000, False)
            ready = self.scene_gap(2100)
            double = self.rate_trial(f"ee-r{rank}-branded", targets[0], 3200, True)
            ok = ready and plain["ok"] and double["ok"]
            self.flag(f"essence_r{rank}_both_effects", bool(ok), str({"ready": ready, "brand": double["brand_log"], "claw": double["claw_log"]}))
            rows.append({"rank": rank, "expected_cooldown_ms": cooldown, "plain": plain, "branded": double})
            passed &= bool(ok)
        self.out["essence_rate_trials"] = rows
        self.flag("essence_all_rank_rates", passed and len(rows) == 5)
        self.gl("skillcrit", PB, "restore")
        self.to_town()


def run(pilot, section, **_):
    c = Checks(pilot)
    {"ranks": c.ranks, "orbs": c.orbs, "essence_rates": c.essence_rates}[section]()
    return {**c.out, "notes": c.notes, "measurement_only": True,
            "expected_source": ["mods/specs/scripts/HWP/Specs/Branding.as",
                                "mods/specs/players/hwp/specs/branding/pyrebrand.sval",
                                "mods/specs/players/hwp/specs/branding/essence_extraction.sval"],
            "unclaimed": ["ordinary runs", "co-op", "Released Essence elite/boss payout ranks",
                          "other orb/rank combinations and transferred stored-damage magnitude"]}
