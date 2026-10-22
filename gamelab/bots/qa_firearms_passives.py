"""Firearms passive/orb rank measurements, using fixed trials without retry loops.

RollElement runs the same live function as natural gunfire; actual firing and target
damage accompany every base rank. Focus caps are earned by natural hits, then lost
through a natural miss. Cleared-floor fixtures are not ordinary-run evidence.
"""
import math
import re
import time

from gamelab.bots.plan_firearms_more import ELEMENTS, RESIST, ROLLS
from gamelab.bots.qa_firearms_ranks import Checks as Base


class Checks(Base):
    def prepare(self, name, subclass=None):
        self.new_char(name, subclass)
        if not self.enter_floor(name):
            return False
        self.check("god_disabled", self.ordinary_damage(), {"fixture": "cleared isolated combat floor"})
        self.hwp("skillpoints 999", 0.3, until="skill points")
        return True

    def elements(self):
        if not self.prepare("QAEleRanks"):
            return
        d = self.open_dirs(130)[0]
        for rank in range(1, 6):
            got = self.learn_rank("hwp_fs_scavenger", rank)
            chance, counts = self.rolls()
            elemental = sum(counts.get(e, 0) for e in ELEMENTS)
            shares = {e: counts.get(e, 0) / max(1, elemental) for e in ELEMENTS}
            expected = rank / 10
            self.check(f"elemental_rank_{rank}", got == rank and abs(chance - expected) < 0.001
                       and abs(elemental / ROLLS - expected) < 0.02
                       and all(abs(s - 0.25) < 0.03 for s in shares.values()),
                       {"skill": "hwp_fs_scavenger", "rank": rank, "readback_rank": got,
                        "live_chance": chance, "expected_chance": expected,
                        "rolls": ROLLS, "counts": counts, "shares": shares})
            dd, (dummy,) = self.line_dummies(d, [80])
            hp0 = self.hps([dummy])[dummy]
            tags, fired = self.fire_at(dd, 1500)
            hp1 = self.hps([dummy])[dummy]
            self.check(f"elemental_rank_{rank}_natural_gunfire", sum(fired.values()) >= 3 and hp1 < hp0,
                       {"skill": "hwp_fs_scavenger", "rank": rank, "fired": fired,
                        "dummy_hp": [hp0, hp1], "buff_tags": tags,
                        "note": "Element distribution is asserted over20k live rolls; this short natural sample need not contain every element."})
        for element in ELEMENTS:
            oid = "hwp_fs_scavenger_" + element
            for rank, weight in enumerate((0.3, 0.6, 1.0), 1):
                ok, got = self.orb(oid, 1)
                chance, counts = self.rolls()
                elemental = sum(counts.get(e, 0) for e in ELEMENTS)
                share = counts.get(element, 0) / max(1, elemental)
                expected = (1 + weight) / (4 + weight)
                self.check(f"{oid}_rank_{rank}", ok and got == rank and abs(chance - 0.5) < 0.001
                           and abs(share - expected) < 0.025,
                           {"orb": oid, "rank": rank, "readback_rank": got,
                            "rolls": ROLLS, "counts": counts, "share": share,
                            "expected_share": expected,
                            "excluded": ["hwp_fs_scavenger_" + e for e in ELEMENTS if e != element]})
            self.orb_off(oid)
        self.clear_dummies()
        self.to_town()

    def focus(self):
        if not self.prepare("QAFocusRanks", "hwp_firearms_sniper"):
            return
        d = self.open_dirs(130)[0]
        for rank, cap in enumerate((15, 20, 25, 30, 40), 1):
            got = self.learn_rank("hwp_fs_focus", rank)
            # A natural miss resets any Focus retained from the previous trial.
            self.clear_dummies()
            self.top_up()
            self.gl("input", 320, 0, 0, -d[0], -d[1], "main")
            time.sleep(2)
            initial = self.stacks("focus")
            dd, dummy = self.tough(d, 80)
            before = self.probe(rolls=1)
            self.top_up()
            self.hwp("firearms elements reset", 0.2, until="elements: reset")
            hp0 = self.hps([dummy])[dummy]
            counts = []
            # Two fixed holds ensure even cap40 is reached through natural reloads.
            for trial in range(2):
                self.gl("input", 10000, 0, 0, dd[0], dd[1], "main")
                time.sleep(10.4)
                counts.append({"trial": trial + 1, "focus": self.stacks("focus"), "clip": self.clip()})
            final = self.stacks("focus")
            hp1 = self.hps([dummy])[dummy]
            after = self.probe(rolls=1)
            fired = self.fired()
            crit = after.get("mainCrit", -1) - before.get("mainCrit", 0)
            damage = after.get("mainCritDmg", -1) - before.get("mainCritDmg", 0)
            self.check(f"focus_rank_{rank}_cap", got == rank and initial == 0 and final == cap
                       and all(x["focus"] <= cap for x in counts) and sum(fired.values()) > cap and hp1 < hp0,
                       {"skill": "hwp_fs_focus", "rank": rank, "readback_rank": got,
                        "expected_cap": cap, "initial": initial, "fixed_trials": counts,
                        "final": final, "fired": fired, "dummy_hp": [hp0, hp1]})
            # Native Modifiers::CriticalHit combines complement probabilities
            # (StatModifier.as:683); Critical Aim injects chance 0->.01 at stack
            # intensity (sniper_focus.sval:44). CritDamage remains additive.
            expected_chance = (1.0 - before.get("mainCrit", 0)) * cap * 0.01
            valid_reads = (before.get("ok") and after.get("ok")
                           and 0 <= before.get("mainCrit", -1) < 1
                           and 0 <= after.get("mainCrit", -1) <= 1
                           and before.get("mainCritDmg", -1) > 0
                           and after.get("mainCritDmg", -1) > 0)
            self.check(f"focus_rank_{rank}_crit_modifiers", valid_reads
                       and abs(crit - expected_chance) < 0.002
                       and abs(damage - cap * 0.01) < 0.002,
                       {"skill": "hwp_fs_focus", "rank": rank, "naturally_earned_stacks": final,
                        "native_reads_valid": bool(valid_reads),
                        "baseline_crit_chance": before.get("mainCrit"),
                        "final_crit_chance": after.get("mainCrit"),
                        "crit_chance_delta": crit, "crit_damage_delta": damage,
                        "expected_chance_delta": expected_chance,
                        "expected_damage_delta": cap * 0.01})
            self.clear_dummies()
            self.gl("input", 320, 0, 0, -dd[0], -dd[1], "main")
            time.sleep(2)
            lost = self.stacks("focus")
            self.check(f"focus_rank_{rank}_miss_resets", final == cap and lost == 0,
                       {"skill": "hwp_fs_focus", "rank": rank, "before": final, "after_natural_miss": lost})
        self.to_town()

    def hoarder(self):
        if not self.prepare("QAHoardRanks", "hwp_firearms_demolitions"):
            return
        d = self.open_dirs(130)[0]
        for rank, cap in enumerate((1, 1, 2, 2, 3), 1):
            got = self.learn_rank("hwp_fs_hoarder", rank)
            self.ready("hwp_fs_rpg", 25)
            expected_period = 8 * (0.9091, 0.8333, 0.7692, 0.7143, 0.6667)[rank - 1]
            snapshots = []
            end = time.monotonic() + expected_period * cap + 3
            while time.monotonic() < end:
                bank = self.stacks("rocket_charges")
                shown = self.stacks("rocket_charges_shown")
                snapshots.append({"banked": bank, "shown": shown})
                if bank == cap and shown == cap + 1:
                    break
                time.sleep(0.2)
            self.check(f"hoarder_rank_{rank}_bank_cap", got == rank and bank == cap and shown == cap + 1,
                       {"skill": "hwp_fs_hoarder", "rank": rank, "readback_rank": got,
                        "expected_cap": cap, "banked": bank, "shown": shown, "samples": snapshots})
            dd, dummy = self.tough(d, 80)
            hp0 = self.hps([dummy])[dummy]
            self.top_up()
            casts = []
            for attempt in range(cap + 1):
                start = time.monotonic()
                self.gl("input", 720, 0, 0, dd[0], dd[1], "skill3")
                time.sleep(1.1)
                casts.append({"attempt": attempt + 1, "banked": self.stacks("rocket_charges"),
                              "cooldown": self.entry(self.bar(), "hwp_fs_rpg").get("cd", 0)})
            hp1 = self.hps([dummy])[dummy]
            self.check(f"hoarder_rank_{rank}_natural_spend", all(x["cooldown"] == 0 for x in casts[:-1])
                       and casts[-1]["cooldown"] > 0 and casts[-1]["banked"] == 0 and hp1 < hp0,
                       {"skill": "hwp_fs_hoarder", "rank": rank, "casts": casts, "dummy_hp": [hp0, hp1]})
            while time.monotonic() - start < expected_period + 1.5:
                if self.entry(self.bar(), "hwp_fs_rpg").get("cd", 0) == 0:
                    break
                time.sleep(0.06)
            elapsed = time.monotonic() - start
            ready = self.entry(self.bar(), "hwp_fs_rpg").get("cd", 0) == 0
            # PlayerSkill cooldown starts when the700ms casting animation ends.
            self.check(f"hoarder_rank_{rank}_recharge_rate", ready and abs(elapsed - (expected_period + 0.7)) < 0.65,
                       {"skill": "hwp_fs_hoarder", "rank": rank, "elapsed_from_final_press": elapsed,
                        "expected_cooldown_seconds": expected_period, "expected_cast_seconds": 0.7})
        self.clear_dummies()
        self.to_town()

    def steady(self):
        if not self.prepare("QASteadyRanks"):
            return
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        self.g.console("dbg_cht_ignore_equipment_requirements 1")
        d, dummy = self.tough(self.open_dirs(130)[0], 80)
        baseline = self.probe(rolls=1)
        configs = [
            ("rifle", "hwp_rifle_01", None, 30, 0, 3, 0, 320),
            ("pistol", "hwp_glock_mh_01", None, 10, 0, 1, 0, 180),
            ("dual_pistol", "hwp_glock_mh_01", "hwp_glock_oh_01", 10, 10, 1, 1, 420),
            ("cannon", "hwp_hcannon_mh_01", None, 6, 0, 1, 0, 180),
            ("dual_cannon", "hwp_hcannon_mh_01", "hwp_hcannon_oh_01", 6, 6, 1, 1, 720),
            ("pistol_cannon", "hwp_glock_mh_01", "hwp_hcannon_oh_01", 10, 6, 2, 1, 320),
            ("cannon_pistol", "hwp_hcannon_mh_01", "hwp_glock_oh_01", 6, 10, 1, 2, 320),
        ]
        for rank in range(1, 6):
            got = self.learn_rank("hwp_fs_steady", rank)
            for name, main, off, main_mag, off_mag, main_spent, off_spent, duration in configs:
                equipped, gear = self.fixture_loadout(main, off)
                dd, (dummy,) = self.line_dummies(d, [80])
                self.top_up()
                maximum = self.clip_max()
                expected_main = main_mag + int(main_mag * rank / 10 + 0.5)
                expected_off = off_mag + int(off_mag * rank / 10 + 0.5)
                hp0 = self.hps([dummy])[dummy]
                self.gl("input", duration, 0, 0, dd[0], dd[1], "main")
                time.sleep(duration / 1000 + 0.65)
                remaining = self.clip()
                hp1 = self.hps([dummy])[dummy]
                live = self.probe(rolls=1)
                added_main = live.get("mainCritDmg", -1) - baseline.get("mainCritDmg", 0)
                added_off = live.get("offCritDmg", -1) - baseline.get("offCritDmg", 0)
                expected_main_bonus = (expected_main - main_spent) * 0.02
                expected_off_bonus = (expected_off - off_spent) * 0.02
                self.check(f"steady_rank_{rank}_{name}", got == rank and equipped
                           and maximum == expected_main + expected_off
                           and remaining == maximum - main_spent - off_spent and hp1 < hp0
                           and abs(added_main - expected_main_bonus) < 0.003
                           and (not off or abs(added_off - expected_off_bonus) < 0.003),
                           {"skill": "hwp_fs_steady", "rank": rank, "configuration": name, "gear": gear,
                            "capacity": maximum, "expected_capacity_by_gun": [expected_main, expected_off],
                            "remaining_shared_rounds": remaining, "spent_by_gun": [main_spent, off_spent],
                            "added_main_crit_damage": added_main, "added_off_crit_damage": added_off,
                            "expected_main_crit_damage": expected_main_bonus, "expected_off_crit_damage": expected_off_bonus,
                            "dummy_hp": [hp0, hp1]})
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        self.clear_dummies()
        self.to_town()

    def adrenaline(self):
        if not self.prepare("QAAdrenRanks", "hwp_firearms_assault"):
            return
        d = self.open_dirs(130)[0]
        for rank, (cap, heal) in enumerate(zip((20, 25, 25, 30, 30), (0.005, 0.005, 0.01, 0.01, 0.015)), 1):
            got = self.learn_rank("hwp_fs_adrenaline", rank)
            self.clear_dummies()
            self.g.console("cht_give_health 999")
            time.sleep(0.15)
            full = self.gl("state").get("player", {})
            self.g.console("cht_damage 60")
            time.sleep(0.25)
            damaged = self.gl("state").get("player", {})
            baseline_damage = full.get("hp", 0) - damaged.get("hp", 0)
            self.g.console("cht_give_health 999")
            dd, _ = self.clear_dir(d, 80)
            targets = [self.dummy(dd[0] * 80, dd[1] * 80) for _ in range(35)]
            # Read back a low-health fixture; the final killing blow is real gunfire.
            # Vanilla target_dummy_breakable counts-as-kill defaults true.
            self.gl("kill", 300, "target_dummy", 0.001)
            setup = self.hps(targets)
            setup_ok = len(set(targets)) == 35 and None not in targets and all(abs(setup[x] - 0.001) < 0.0001 for x in targets)
            self.top_up()
            counts = []
            for trial in range(2):
                self.gl("input", 10000, 0, 0, dd[0], dd[1], "main")
                time.sleep(10.4)
                counts.append({"trial": trial + 1, "adrenaline": self.stacks("adrenaline")})
            earned = self.stacks("adrenaline")
            survivors = self.hps(targets)
            killed = sum(hp == 0 for hp in survivors.values())
            self.check(f"adrenaline_rank_{rank}_natural_kill_cap", got == rank and setup_ok and killed > cap
                       and earned == cap and all(x["adrenaline"] <= cap for x in counts),
                       {"skill": "hwp_fs_adrenaline", "rank": rank, "readback_rank": got,
                        "expected_cap": cap, "low_health_fixture_readback": setup,
                        "kills_from_gunfire": killed, "fixed_trials": counts, "final_stacks": earned})
            before = self.gl("state").get("player", {})
            expected = int(cap * heal * before.get("hpMax", 0) + 0.5)
            mark = self.log_pos()
            self.g.console("cht_damage 60")
            time.sleep(0.3)
            after = self.gl("state").get("player", {})
            log = self.log_from(mark)
            spent = re.search(r"adrenaline: hurt, (\d+) stacks spent for (\d+) health", log)
            healed = re.search(r"adrenaline: healed (\d+) of (\d+)", log)
            left = self.stacks("adrenaline")
            expected_heal = min(expected, baseline_damage)
            observed_heal = int(healed[1]) if healed else -1
            expected_final_hp = before.get("hp", 0) - baseline_damage + expected_heal
            self.check(f"adrenaline_rank_{rank}_hurt_heals", baseline_damage > 0 and earned == cap and left == 0
                       and spent is not None and int(spent[1]) == cap and int(spent[2]) == expected
                       and healed is not None and int(healed[2]) == expected
                       and abs(observed_heal - expected_heal) <= 2 and abs(after.get("hp", 0) - expected_final_hp) <= 2,
                       {"skill": "hwp_fs_adrenaline", "rank": rank, "heal_per_stack": heal,
                        "maximum_hp": before.get("hpMax"), "baseline_damage_without_stacks": baseline_damage,
                        "stacks_before": earned, "stacks_after": left, "expected_heal_requested": expected,
                        "heal_actual": observed_heal, "hp_before": before.get("hp"), "hp_after": after.get("hp"),
                        "expected_final_hp": expected_final_hp, "hurt_log": spent.group(0) if spent else None,
                        "heal_log": healed.group(0) if healed else None,
                        "note": "Native cht_damage supplies a controlled hurt event after naturally earned kills; not ordinary-combat proof."})
        self.clear_dummies()
        self.to_town()

    def turret_damage_sample(self, d):
        dd, dummy = self.tough(d, 120, RESIST)
        previous = self.hps([dummy])[dummy]
        changes = []
        end = time.monotonic() + 5
        while time.monotonic() < end:
            hp = self.hps([dummy])[dummy]
            if hp < previous:
                changes.append((previous - hp) * 600)
            previous = hp
            time.sleep(0.05)
        return {"hits": changes, "mean_damage": sum(changes) / max(1, len(changes)), "final_hp": previous}

    def turret_one(self):
        units = [u for u in self.gl("near", 400, "hwp/firearms/units/turret").get("units", []) if not u.get("dead")]
        return units[0] if len(units) == 1 else {}

    def turret_distance(self, turret):
        x, y = self.pos()
        return math.hypot(turret.get("x", 1e9) - x, turret.get("y", 1e9) - y)

    def myturret(self):
        if not self.prepare("QAMyTurRanks", "hwp_firearms_engineer"):
            return
        equipped, gear = self.fixture_loadout("hwp_glock_mh_01")
        self.check("myturret_pistol_gear", equipped, gear)
        if not equipped:
            return
        d = self.open_dirs(150)[0]
        for rank, (repair, boost) in enumerate(zip((10, 15, 15, 20, 20), (0.1, 0.1, 0.15, 0.15, 0.2)), 1):
            got = self.learn_rank("hwp_fs_myturret", rank)
            self.gl("kill", 800, "hwp/firearms/units/turret")
            self.ready("hwp_fs_turret", 25)
            self.top_up()
            self.targeted(self.entry(self.bar(), "hwp_fs_turret").get("button"), d[0] * 80, d[1] * 80, (0, 120))
            time.sleep(0.8)
            turret = self.turret_one()
            far_distance = self.turret_distance(turret)
            far_damage = self.turret_damage_sample(d)
            self.gl("kill", 400, "hwp/firearms/units/turret", 0.4)
            self.gl("input", 400, d[0], d[1], d[0], d[1])
            time.sleep(0.6)
            near_turret = self.turret_one()
            near_distance = self.turret_distance(near_turret)
            h0 = near_turret.get("hp", 0)
            start = time.monotonic()
            time.sleep(1.5)
            h1 = self.turret_one().get("hp", 0)
            elapsed = time.monotonic() - start
            expected_rise = (repair / 100 - 1 / 30) * elapsed
            self.check(f"myturret_rank_{rank}_repairs", got == rank and far_distance > 60 and near_distance <= 60
                       and h0 > 0 and h1 < 0.99 and abs((h1 - h0) - expected_rise) < 0.035,
                       {"skill": "hwp_fs_myturret", "rank": rank, "repair_hp_per_second": repair,
                        "distance_far": far_distance, "distance_near_after_walk": near_distance,
                        "hp_fraction": [h0, h1], "elapsed": elapsed, "expected_rise_net_of_decay": expected_rise})
            near_damage = self.turret_damage_sample(d)
            ratio = near_damage["mean_damage"] / max(0.001, far_damage["mean_damage"])
            self.check(f"myturret_rank_{rank}_boosts_real_damage", len(far_damage["hits"]) >= 5
                       and len(near_damage["hits"]) >= 5 and far_damage["final_hp"] > 0 and near_damage["final_hp"] > 0
                       and abs(ratio - (1 + boost)) < 0.045 and ratio > 1.03,
                       {"skill": "hwp_fs_myturret", "rank": rank, "expected_ratio": 1 + boost,
                        "observed_ratio": ratio, "far_damage": far_damage, "near_damage": near_damage})
            self.gl("input", 800, -d[0], -d[1], -d[0], -d[1])
            time.sleep(0.6)
            far = self.turret_one()
            distance = self.turret_distance(far)
            h2 = far.get("hp", 0)
            start = time.monotonic()
            time.sleep(1.5)
            h3 = self.turret_one().get("hp", 0)
            elapsed = time.monotonic() - start
            self.check(f"myturret_rank_{rank}_leaving_stops_repair", distance > 60 and h3 > 0
                       and abs((h2 - h3) - elapsed / 30) < 0.025,
                       {"skill": "hwp_fs_myturret", "rank": rank, "distance_after_walk": distance,
                        "hp_fraction": [h2, h3], "elapsed": elapsed, "expected_decay": elapsed / 30})
        self.gl("kill", 800, "hwp/firearms/units/turret")
        self.clear_dummies()
        self.to_town()


def run(p, section="elements", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("passive_crashed", False, {"error": repr(exc), "section": section})
    c.out["ok"] = bool(c.rows) and all(row["runtime"] == "PASS" for row in c.rows)
    c.out["rows"] = c.rows
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
