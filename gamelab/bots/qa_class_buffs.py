"""Natural self-buff casts at all ranks, observed through live native factors.

This tests applied attack/move/armor/resistance/damage factors and natural
duration, cost and cooldown. A separate actual normal-attack bench at ranks1/5
proves the character still deals damage while the buff is active; it does not
claim a precise DPS or cadence multiplier from a short stochastic sample.
"""
import math
import time

from gamelab.bots.qa_class_procs import Checks as ProcChecks
from gamelab.bots.qa_observe import collect
from gamelab.bots.qa_specs_living_mana import collect as collect_resources


BUFFS = "tweak/hwp/buffs_classes.sval:"
CASES = {
    "slice": ("hwp_thief", "hwp_thief_trickster", "hwp_thief_slice", "hwp_thief_slice", 6000,
              10, (12000, 11000, 10000, 9000, 8000), {"attackMul": 1.3}),
    "cloak": ("hwp_thief", "hwp_thief_shadow", "hwp_thief_cloak", "hwp_thief_cloak", 2500,
              8, (10000, 9000, 8000, 7000, 6000), {"moveMul": 1.15, "evade": 1.0}),
    "shield_wall": ("hwp_gladiator", "hwp_gladiator_champion", "hwp_gladiator_shield_wall", "hwp_glad_shield_wall", 5000,
                    10, (15000, 14000, 13000, 12000, 11000), {"armorMul": 1.5, "resistanceMul": 1.5}),
    "immolation": ("hwp_witch_hunter", "hwp_witch_hunter_pyromancer", "hwp_witch_hunter_immolation", "hwp_wh_immolation", 8000,
                   12, (14000, 13000, 12000, 11000, 10000), {"damageMul": 1.1}),
}


def native_paid_cost(trace, expected):
    """Actual one-frame cost with independently source-bounded regeneration.

    Player.UsePoints subtracts fractional flat cost (Player.as773..850).
    Player.Update adds ManaRegen*ManaGain*dt/statMana (Player.as1242).
    Consecutive native samples isolate the real expense from transport latency.
    """
    rows, decreases = trace.get("samples", []), []
    if trace.get("usable") is not True:
        return {"valid":False,"decreases":[],"expected_expense":expected,"errors":trace.get("errors",[])}
    valid = (trace.get("usable") is True and 1200 <= trace.get("ms",0) <= 1300
             and trace.get("frames",0) >= 10 and expected > 0)
    for before,after in zip(rows,rows[1:]):
        dt = after.get("dt",0)
        if not 0 < dt <= 100:
            valid = False
        fields = ("maxMana","statMana","manaRegen","manaGain")
        if any(not isinstance(row.get(k),(int,float)) or isinstance(row.get(k),bool)
               or not math.isfinite(row[k]) or row[k] < 0 for row in (before,after) for k in fields):
            valid = False
            continue
        if min(before["maxMana"],after["maxMana"],before["statMana"],after["statMana"]) <= 0:
            valid = False
            continue
        # Native update phase may put the frame's regen on either side of the
        # actual cast. Bound it from the measured current stats, never fit it.
        gain = max(before["manaRegen"]*before["manaGain"]*before["maxMana"]/before["statMana"],
                   after["manaRegen"]*after["manaGain"]*after["maxMana"]/after["statMana"]) * dt/1000
        drop = before["mana"]-after["mana"]
        if drop > .5:
            decreases.append({"before":before,"after":after,"actual_drop":drop,"source_regen_bound":gain,
                              "expected_expense":expected,"matches":expected-gain-.02 <= drop <= expected+.02})
    return {"valid":bool(valid and len(decreases)==1 and decreases[0]["matches"]),
            "decreases":decreases,"expected_expense":expected,"precision_tolerance":.02}


class Checks(ProcChecks):
    def info(self, skill):
        return next((x for x in self.gl("skills").get("skills", []) if x.get("id") == skill), {})

    def ready(self, skill, timeout=25):
        end, rows = time.monotonic() + timeout, []
        while time.monotonic() < end:
            current = self.info(skill)
            rows.append(current)
            if isinstance(current.get("cd"), (int, float)) and current["cd"] <= 0:
                return current, rows
            time.sleep(0.25)
        return {}, rows

    def buff(self, key):
        cls, mastery, skill, buff, duration, cost, cooldowns, factors = CASES[key]
        if not self.prepare(cls, mastery, "QASelfBuff" + key):
            return
        rows, passed = [], True
        for rank, expected_cd in enumerate(cooldowns, 1):
            tag = f"{key}_r{rank}"
            learned = self.learn(skill, rank, tag)
            current, ready_rows = self.ready(skill)
            live = self.gl("skills").get("skills", [])
            button = current.get("button")
            unique = bool(button) and sum(x.get("button") == button for x in live) == 1
            self.flag(tag + "_normal_input_setup", learned and bool(current) and unique, str(live))
            if not learned or not current or not unique:
                passed = False
                continue
            self.gl("mana", 999)
            before = self.gl("state").get("player", {})
            baseline_stats = self.gl("benchstats")
            target = self.fresh_dummy(tag) if rank in (1, 5) else None
            observer_tag = f"clbuff{time.time_ns()}"
            observer_args = ["buffobserve", observer_tag, duration + 4000, BUFFS + buff]
            if target:
                observer_args += ["-", target["unit"]]
            resource_tag = f"clmana{time.time_ns()}"
            started = self.g.gl_multi([observer_args,
                                       ["resourceobserve",resource_tag,1200],
                                       ["input", 320, 0, 0, 1, 0, button]])
            time.sleep(0.4)
            commands = [["state"], ["skills"], ["benchstats"]]
            combat_tag = f"clbuffhit{time.time_ns()}"
            if target:
                commands += [["bench", combat_tag, 1000, 200, "noskills"]]
            replies = self.g.gl_multi(commands)
            after = replies[0].get("player", {})
            actual = next((x for x in replies[1].get("skills", []) if x.get("id") == skill), {})
            applied_stats = replies[2]
            combat = self.g.wait_gl(lambda x: x.get("ev") == "bench" and x.get("tag") == combat_tag, 15) if target else None
            resources = collect_resources(self.g,resource_tag,timeout=10)
            paid = native_paid_cost(resources,cost*before.get("manaCostMul",-1))
            observed = collect(self.g, observer_tag, timeout=duration / 1000 + 15)
            events = observed.get("events", [])
            on = next((x for x in events if x.get("buff_on")), None)
            off = next((x for x in events if on and not x.get("buff_on") and x.get("now", 0) > on["now"]), None)
            applied = bool(observed.get("usable") and on and all(abs(on.get(k, -100) - v) < 0.002 for k, v in factors.items()))
            native_duration = bool(on and off and on.get("buff_dur") == duration
                                   and duration - 67 <= on.get("buff_left", 0) <= duration
                                   and abs(off["now"] - (on["now"] + on["buff_left"])) <= 67)
            # Return to the captured initial native factors, including base evade.
            reverted = bool(events and off and all(abs(off.get(k, -100) - events[0].get(k, 100)) < 0.002 for k in factors))
            spent = before.get("manaExact", 0) - after.get("manaExact", 0)
            cast = isinstance(actual.get("cd"), (int, float)) and expected_cd - 2500 <= actual["cd"] <= expected_cd
            cast &= paid["valid"]
            self.flag(tag + "_cost_cooldown", bool(cast), str({"transport_net_spent": spent,"native_paid_cost":paid,
                      "resource_errors":resources.get("errors"),"skills": actual,"expected_cd":expected_cd}))
            self.flag(tag + "_live_effect", applied, str({"on": on, "expected": factors, "observer_errors": observed.get("errors")}))
            self.flag(tag + "_natural_expiry", native_duration and reverted, str({"on": on, "off": off}))
            extra = True
            if key == "immolation":
                extra = applied_stats.get("mhFire", 0) > baseline_stats.get("mhFire", 0)
                self.flag(tag + "_native_fire_added", extra, str({"before": baseline_stats, "on": applied_stats}))
            if target:
                active_damage = any(b.get("buff_on") and b.get("target_valid") and a.get("target_valid")
                                    and b.get("target_hpExact", 15000) < a.get("target_hpExact", 0)
                                    for a, b in zip(events, events[1:]))
                hit = bool(combat and combat.get("total", 0) > 0 and combat.get("hooked", 0) > 0 and active_damage)
                self.flag(tag + "_normal_attack_damage", hit, str(combat))
                extra &= hit
            row = {"rank": rank, "ready_samples": ready_rows, "start": started,
                   "mana_before": before, "mana_after": after, "actual_cooldown": actual,
                   "baseline_stats": baseline_stats, "applied_stats": applied_stats,
                   "native_observer": observed, "native_resources":resources,"native_paid_cost":paid,
                   "normal_combat": combat}
            rows.append(row)
            passed &= bool(cast and applied and native_duration and reverted and extra)
        self.out[key + "_trials"] = rows
        self.flag(key + "_all_ranks", passed and len(rows) == 5)
        self.to_town()


def run(p, sections="slice,cloak,shield_wall,immolation", **_):
    c = Checks(p)
    for key in sections.split(","):
        try:
            c.buff(key)
        except Exception as exc:
            c.flag(key + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
