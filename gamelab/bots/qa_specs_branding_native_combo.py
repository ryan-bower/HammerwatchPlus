"""One legal native Pyrebrand recast, two transferred brands, one Essence pool.

All ability activations use the unique live native button. Initial Essence,
mana and controlled central-actor death are explicit measurement prerequisites;
they are not ordinary acquisition/kill evidence. No castat or cooldown reset.
"""
import json
import math
import re
import time

from gamelab.bots.qa_specs_branding_effects import Checks as Base
from gamelab.bots.qa_specs_branding_effects import PB, EE, ESSENCE, COMBUST, SPREAD, EMPOWER, RELEASE
from gamelab.bots.qa_specs_living_mana import collect as collect_resources
from gamelab.bots.qa_specs_cost_oracle import pyrebrand_cost, normalized_payment
from gamelab.bots.qa_observe import collect


def expected_fire(amount, caster, buff_mul, fire):
    """Independent pinned Damage.FillDamage -> PlayerBase -> zero-res enemy pool."""
    stats, probe, _ = caster
    multiplier = (buff_mul * stats["damageMul"] * (200 + stats["spellPower"]) / 200
                  * probe["skillDmgMul"] * probe["damageMul"][1] * fire)
    direct = Base.native_round(Base.native_round(amount) * multiplier)
    pool = int(direct * .33)
    left, ticks = pool, 0
    while left > 0:
        left -= max(1, int(left * .5))
        ticks += 1
    return {"amount": amount, "fire": fire, "multiplier": multiplier,
            "direct": direct, "pool": pool, "hp_loss": direct + pool, "ticks": ticks}


class Checks(Base):
    def ready(self, timeout=14):
        end, samples = time.monotonic() + timeout, []
        while time.monotonic() < end:
            raw = self.gl("skills")
            matches = [s for s in raw.get("skills", []) if s.get("id") == PB]
            entry = matches[0] if len(matches) == 1 else {}
            samples.append(raw)
            button = entry.get("button")
            if (button and sum(s.get("button") == button for s in raw.get("skills", [])) == 1
                    and isinstance(entry.get("cd"), (int, float)) and entry["cd"] <= 0
                    and not raw.get("truncated")):
                return entry, samples
            time.sleep(.2)
        return {}, samples

    def native_cast(self, tag, observe_uid=None):
        entry, readiness = self.ready()
        before = self.gl("state").get("player", {})
        setup = (bool(entry) and before.get("manaCostMul") == 1
                 and before.get("manaExact", 0) >= 65 and not before.get("dead"))
        result = {"ready": entry, "readiness": readiness, "before": before, "setup": setup}
        if not setup:
            return result
        commands = [["skillcost", PB, "hwp_warlock_branding"],
                    ["resourceobserve", tag + "-mana", 1200]]
        if observe_uid is not None:
            commands.append(["buffobserve", tag + "-hp", 3500, "-", "-", observe_uid])
        commands.append(["input", 420, 0, 0, *self.direction, entry["button"]])
        mark = len(self.g.read_log())
        replies = self.g.gl_multi(commands)
        held = replies[-1]
        done = self.g.wait_gl(lambda e: e.get("ev") == "input_done"
                              and e.get("id") == held.get("id"), 8) or {}
        resources = collect_resources(self.g, tag + "-mana", 8)
        cost_prediction = pyrebrand_cost(replies[0])
        paid = normalized_payment(resources, cost_prediction, refund=observe_uid is not None,
                                  baseline_max=self.zero_cost.get("max_mana"))
        result.update({"commands": commands, "replies": replies, "input_done": done,
                       "resources": resources, "paid": paid, "source_cost": cost_prediction,
                       "input_valid": (all(r.get("ok") for r in replies)
                           and done.get("id") == held.get("id") and done.get("frames", 0) > 0)})
        if observe_uid is not None:
            result["observer"] = collect(self.g, tag + "-hp", timeout=10)
        result["log"] = self.g.read_log()[mark:]
        result["after"] = self.gl("state").get("player", {})
        result["cooldown"] = self.skill_cd(PB)
        return result

    def trial(self, trial, essence):
        tag = f"native-brand-{trial}-e{essence}"
        entry, natural_ready = self.ready()
        targets = self.fresh(60, 60) if entry else []
        row = {"trial": trial, "essence": essence, "natural_ready": natural_ready,
               "targets": targets, "tag": tag}
        if len(targets) != 3:
            self.flag(tag + "_setup", False, str(row))
            return row
        # The bounded native override expires after60s. Refresh it per fixed
        # trial rather than allowing naturalCD waits to outlive its contract.
        crit_begin = self.gl("skillcrit", PB, 0)
        self.set_stacks(ESSENCE, 0)
        zero = self.gl("dmgmuls")
        self.zero_cost = pyrebrand_cost(self.gl("skillcost", PB, "hwp_warlock_branding"))
        self.set_stacks(ESSENCE, essence)
        caster = self.g.gl_multi([["benchstats"], ["critprobe", 0, 300, "target_dummy", PB], ["dmgmuls"]])
        self.gl("mana", 250)
        before = self.hps()
        initial = self.native_cast(tag + "-initial")
        # This explicit controlled prerequisite invokes the actual Actor death
        # and normal module's PassOn update. No brand/counter setter is used.
        kill = self.gl("kill", 50, "qa_class_target_dummy")
        time.sleep(.1)
        transferred_before = self.hps()
        recast = self.native_cast(tag + "-recast", targets[1])
        after = self.hps()
        crit_end = self.gl("skillcrit", PB)
        fixture_ok = all(q.get("ok") and q.get("override_active")
                         and q.get("crit_chance") == 0 and q.get("spell_crit_chance") == 0
                         and q.get("left", 0) > 0 for q in (crit_begin, crit_end))
        text = initial.get("log", "") + recast.get("log", "")
        # Transfer logging occurs between the two cast windows; preserve the
        # complete native interval as the separate transcript below.
        actor_ok = (len(before) == 3 and before.get(targets[0], {}).get("hpMax") == 15000
                    and all(before.get(uid, {}).get("hpMax") == 500
                            and before.get(uid, {}).get("hpExact") == 500 for uid in targets[1:]))
        survivors = (set(transferred_before) == set(targets[1:]) == set(after)
                     and all(transferred_before[u].get("hpExact") == 500 for u in targets[1:])
                     and all(not after[u].get("dead") for u in targets[1:]))
        observed = recast.get("observer", {})
        events = observed.get("events", [])
        buff_mul = events[0].get("damageMul") if events else None
        probe = caster[1]
        fields = (all(x.get("ok") for x in caster) and zero.get("ok")
                  and probe.get("skill") == PB and probe.get("rolls") == 0
                  and probe.get("skillCrit") == 0 and probe.get("spellCrit") == 0
                  and isinstance(buff_mul, (int, float))
                  and all(abs(x.get("damageMul", -99) - buff_mul) < .0001 for x in events)
                  and zero.get("fire", 0) > 0 and caster[2].get("fire", 0) > 0)
        fire_setup = (fields and abs(caster[2]["fire"] - zero["fire"]
                      - .03 * essence * caster[2]["physical"]) <= .002)
        predictions = []
        if fields:
            predictions = [expected_fire(40 * (1 + .04 * essence), caster, buff_mul, caster[2]["fire"]),
                           expected_fire(40, caster, buff_mul, zero["fire"])]
        losses = [self.loss(transferred_before, after, uid) for uid in targets[1:]]
        hits = [b for a, b in zip(events, events[1:])
                if a.get("target_hpExact", 0) - b.get("target_hpExact", 0) > .01]
        settled = (bool(hits) and bool(predictions) and observed.get("usable")
                   and observed.get("end", 0) - hits[0]["now"]
                       >= max(p["ticks"] for p in predictions) * 250 + 67
                   and all(e.get("target_valid") and e.get("target_hpMax") == 500 for e in events))
        claws = re.findall(r"claw \(recast\) (\d+) fire, radius (\d+), (\d+) hit, (\d+) essence spent", recast.get("log", ""))
        claws = [tuple(map(int, match)) for match in claws]
        expected_claws = [(round(40 * (1 + .04 * essence)), round(40 * (1 + .04 * essence)), 1, essence),
                          (40, 40, 1, 0)]
        cost_ok = all(c.get("setup") and c.get("input_valid") and c.get("paid", {}).get("valid")
                      for c in (initial, recast))
        native_initial = ("branded an enemy for 3000 ms" in initial.get("log", "")
                          and "claw (" not in initial.get("log", "")
                          and isinstance(initial.get("cooldown"), (int, float))
                          and initial["cooldown"] <= 0)
        max_pool_ok = (self.zero_cost.get("valid") is True and all(
            cast.get("source_cost", {}).get("max_mana") == self.native_round(
                self.zero_cost["max_mana"] * (1 + .02 * essence))
            for cast in (initial, recast)))
        setup = bool(max_pool_ok and actor_ok and survivors and fire_setup and cost_ok and fixture_ok and native_initial
                     and observed.get("usable") and settled and claws == expected_claws
                     and "claw (expired)" not in text)
        actual_ok = (setup and all(isinstance(n, (int, float)) and math.isfinite(n) for n in losses)
                     and all(abs(a - b) <= .02 for a, b in zip(sorted(losses), sorted(p["hp_loss"] for p in predictions))))
        spent = self.status_num("essence") == 0
        cooldown = recast.get("cooldown")
        full_cd = isinstance(cooldown, (int, float)) and 5000 <= cooldown <= 10000
        self.flag(tag + "_setup", setup)
        self.flag(tag + "_fully_settled_damage", bool(actual_ok))
        self.flag(tag + "_spend_full_cd", bool(setup and spent and full_cd))
        row.update({"crit_fixture_begin": crit_begin, "crit_fixture_end": crit_end,
                    "crit_fixture_valid": fixture_ok, "before": before, "transferred_before": transferred_before, "after": after,
                    "kill": kill, "zero": zero, "caster": caster, "initial": initial, "recast": recast,
                    "fields": fields, "fire_setup": fire_setup, "zero_cost": self.zero_cost, "source_maxima_valid": max_pool_ok, "actor_ok": actor_ok,
                    "survivors": survivors, "native_initial": native_initial, "cost_ok": cost_ok,
                    "predictions": predictions, "actual_damage": losses, "settled": bool(settled),
                    "claws": claws, "expected_claws": expected_claws, "setup_valid": setup,
                    "damage_valid": bool(actual_ok), "spent": spent, "full_cd": full_cd})
        return row


def run(pilot):
    c, trials = Checks(pilot), []
    try:
        if c.prepare("native_brand_combo", wide=True):
            c.rank(PB, 5, "native_pb5")
            c.rank(EE, 5, "native_ee5")
            orb_rows = {orb: c.orb_rank(orb, rank) for orb, rank in
                        ((COMBUST, 3), (SPREAD, 3), (EMPOWER, 3), (RELEASE, 2))}
            c.out["equipped_orbs"] = orb_rows
            c.flag("native_combo_orb_setup", all(row.get("level") == rank
                   for row, rank in zip(orb_rows.values(), (3, 3, 3, 2))))
            if c.out.get("native_pb5_rank") and c.out.get("native_ee5_rank") and c.out["native_combo_orb_setup"]:
                for trial in range(1, 4):
                    for essence in (0, 10):
                        mark = len(c.g.read_log())
                        row = c.trial(trial, essence)
                        row["native_transcript"] = c.g.read_log()[mark:]
                        trials.append(row)
                        (c.g.results / "branding-native-combo-partial.json").write_text(
                            json.dumps({"flags": c.out, "trials": trials}, indent=2) + "\n", encoding="utf-8")
            c.flag("native_combo_all_trials", len(trials) == 6 and all(
                row.get("setup_valid") and row.get("damage_valid") and row.get("spent") and row.get("full_cd") for row in trials))
    except Exception as exc:
        c.flag("native_combo_exception", False, repr(exc))
    finally:
        try:
            c.gl("skillcrit", PB, "restore")
            c.to_town()
        except Exception as exc:
            c.notes.append("cleanup after retained result: " + repr(exc))
    return {**c.out, "trials": trials, "notes": c.notes,
            "scope": "Three fixed zero/ten-Essence controls each: one real native recast loops two actual transferred brands. Fully settled source-predicted enemy HP. Controlled prerequisites are not ordinary acquisition/kill proof.",
            "sources": ["mods/specs/scripts/HWP/Specs/Branding.as:143", "mods/specs/scripts/HWP/Specs/Branding.as:176",
                        "mods/specs/scripts/HWP/Specs/Branding.as:325", "mods/specs/scripts/HWP/Specs/Branding.as:390",
                        "gamecode/sdk/hoh2/scripts/Behaviors/Actors/Player/PlayerBase.as:928",
                        "gamecode/sdk/hoh2/scripts/Behaviors/Actors/ActorBuffList.as:543"]}
