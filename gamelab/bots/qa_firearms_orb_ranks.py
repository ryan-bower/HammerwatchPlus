"""Additional orb ranks measured by natural casts and real target damage.

Fixed trials retain every result. The bounded GameLab crit fixture only controls
crit chance; native skill input, projectiles, damage and modifiers still execute.
Cleared-floor fixture measurements do not establish ordinary-run or co-op coverage.
"""
import time

from gamelab.bots.plan_firearms_more import RESIST
from gamelab.bots.qa_firearms_passives import Checks as Base


class Checks(Base):
    def reset_focus(self, d):
        self.clear_dummies()
        self.top_up()
        self.gl("input", 320, 0, 0, -d[0], -d[1], "main")
        time.sleep(1.8)
        return self.stacks("focus")

    def snipe_damage(self, d, forced=True):
        initial = self.reset_focus(d)
        dd, (dummy,) = self.line_dummies(d, [90])
        self.ready("hwp_fs_snipe", 8)
        self.top_up()
        before = self.probe("hwp_fs_snipe", 1)
        hp0 = self.hps([dummy])[dummy]
        fixture = self.gl("skillcrit", "hwp_fs_snipe", 1) if forced else {}
        try:
            self.gl("input", 770, 0, 0, dd[0], dd[1], "skill3")
            time.sleep(1.3)
            hp1 = self.hps([dummy])[dummy]
            after = self.probe("hwp_fs_snipe", 1)
        finally:
            restored = self.gl("skillcrit", "hwp_fs_snipe", "restore") if forced else {}
        return {"initial_focus": initial, "before": before, "after": after,
                "hp": [hp0, hp1], "damage": (hp0 - hp1) * 500,
                "fixture": fixture, "fixture_restore": restored,
                "fixture_ok": not forced or (fixture.get("override_active") and fixture.get("crit_chance") == 1
                                               and not restored.get("override_active"))}

    def marksman(self):
        if not self.prepare("QAOrbMarks", "hwp_firearms_sniper"):
            return
        d = self.open_dirs(190)[0]
        baseline = self.snipe_damage(d)
        self.check("snipe_forced_crit_fixture", baseline["fixture_ok"] and baseline["initial_focus"] == 0
                   and baseline["damage"] > 0 and baseline["hp"][1] > 0, baseline)
        for rank, (chance, damage) in enumerate(zip((0.03, 0.04, 0.05), (0.1, 0.2, 0.3)), 1):
            ok, got = self.orb("hwp_fs_focus_boom", 1)
            live = self.snipe_damage(d)
            b, a = baseline["before"], live["before"]
            delta = {k: a.get(k, 0) - b.get(k, 0) for k in
                     ("mainCrit", "mainCritDmg", "spellCrit", "spellCritDmg", "skillCrit", "skillCritDmg")}
            expected = {"mainCrit": chance * (1 - b.get("mainCrit", 0)), "mainCritDmg": damage,
                        "spellCrit": chance * (1 - b.get("spellCrit", 0)), "spellCritDmg": damage,
                        "skillCrit": chance, "skillCritDmg": damage}
            # Both the global spell bonus and Snipe's own bonus apply. The same
            # natural first hit earns one Focus in every sample, including baseline.
            total = baseline["after"].get("spellCritDmg", 0) + baseline["after"].get("skillCritDmg", 0)
            want_ratio = (total + 2 * damage) / max(0.001, total)
            ratio = live["damage"] / max(0.001, baseline["damage"])
            self.check(f"boom_rank_{rank}", ok and got == rank and live["fixture_ok"] and live["initial_focus"] == 0
                       and all(abs(delta[k] - value) < 0.003 for k, value in expected.items())
                       and live["hp"][1] > 0 and abs(ratio - want_ratio) < 0.04,
                       {"orb": "hwp_fs_focus_boom", "rank": rank, "readback_rank": got,
                        "stat_deltas": delta, "expected_deltas": expected,
                        "expected_real_damage_ratio": want_ratio, "real_damage_ratio": ratio,
                        "baseline": baseline, "natural_cast": live})
        self.orb_off("hwp_fs_focus_boom")
        for rank in range(1, 4):
            ok, got = self.orb("hwp_fs_snipe_pierce", 1)
            focus = self.reset_focus(d)
            cap = 1 + rank * 2
            distances = [40 + 18 * i for i in range(cap + 1)]
            dd, targets = self.line_dummies(d, distances)
            hp0 = self.hps(targets)
            self.ready("hwp_fs_snipe", 8)
            self.top_up()
            fixture = self.gl("skillcrit", "hwp_fs_snipe", 1)
            try:
                self.gl("input", 770, 0, 0, dd[0], dd[1], "skill3")
                time.sleep(1.3)
                hp1 = self.hps(targets)
            finally:
                restored = self.gl("skillcrit", "hwp_fs_snipe", "restore")
            losses = [(hp0[x] - hp1[x]) * 500 for x in targets]
            falloff = [losses[i] / max(0.001, losses[i - 1]) for i in range(1, cap)]
            self.check(f"pierce_rank_{rank}", ok and got == rank and focus == 0 and len(set(targets)) == cap + 1
                       and fixture.get("override_active") and not restored.get("override_active")
                       and all(x > 0 for x in losses[:cap]) and losses[cap] == 0
                       and all(0.79 <= x <= 0.91 for x in falloff),
                       {"orb": "hwp_fs_snipe_pierce", "rank": rank, "readback_rank": got,
                        "expected_enemies_hit": cap, "distances": distances, "hp_before": hp0,
                        "hp_after": hp1, "actual_damage_by_target": losses, "successive_damage_ratios": falloff,
                        "fixture": fixture, "fixture_restore": restored})
        self.orb_off("hwp_fs_snipe_pierce")
        plain = [self.snipe_damage(d, forced=False) for _ in range(3)]
        ok, got = self.orb("hwp_fs_snipe_headshot", 1)
        headshot = [self.snipe_damage(d, forced=False) for _ in range(3)]
        control = min(x["damage"] for x in plain)
        self.check("headshot_first_enemy_real_crit", ok and got == 1 and control > 0
                   and all(x["initial_focus"] == 0 for x in plain + headshot)
                   and all(x["hp"][1] > 0 and x["damage"] > control * 1.35 for x in headshot),
                   {"orb": "hwp_fs_snipe_headshot", "rank": got, "without_orb": plain, "with_orb": headshot,
                    "note": "Three fixed controls and three fixed orb casts, no crit override or retries. Every orb cast must exceed the minimum control by35%; all controls critting remains a recorded failure."})
        self.clear_dummies()
        self.to_town()

    def exposure(self):
        # A fresh floor for each rank prevents an earlier burning area contaminating
        # the clean control. All three rank trials run exactly once.
        for rank in range(1, 4):
            if not self.prepare("QAExposure" + str(rank), "hwp_firearms_sniper"):
                return
            d = self.open_dirs(130)[0]
            self.orb("hwp_fs_focus_exposure", rank)
            dd, (dummy,) = self.line_dummies(d, [90])
            clean = self.probe()
            ok, fire_rank = self.orb("hwp_fs_frag_fire", 1)
            self.top_up()
            hp0 = self.hps([dummy])[dummy]
            self.skill_press("hwp_fs_frag", "fs_frag.sval", dd)
            time.sleep(1.5)
            tags = sorted({t for ac in self.gl("actorbuffs", 300, "target_dummy").get("actors", [])
                           for bf in ac.get("buffs", []) for t in bf.get("tags", [])})
            burning = self.probe()
            hp1 = self.hps([dummy])[dummy]
            self.check(f"exposure_rank_{rank}", self.current_rank("hwp_fs_focus_exposure") == rank
                       and ok and fire_rank == 1 and clean["rate"] < 0.002 and hp1 < hp0
                       and any("blind" in t for t in tags)
                       and abs(burning["rate"] - rank * 0.01) < 0.008,
                       {"orb": "hwp_fs_focus_exposure", "rank": rank, "clean_probe": clean,
                        "burning_probe": burning, "expected_crit_rate": rank * 0.01,
                        "natural_incendiary_hp": [hp0, hp1], "tags": tags})
            self.clear_dummies()
            self.to_town()

    def rocket_sample(self, d):
        dd, dummy = self.tough(d, 90, RESIST)
        hp0 = self.hps([dummy])[dummy]
        trials = []
        fixture = self.gl("skillcrit", "hwp_fs_rpg", 1)
        try:
            for trial in range(3):
                self.bank_clear()
                self.ready("hwp_fs_rpg", 15)
                self.top_up()
                self.gl("input", 720, 0, 0, dd[0], dd[1], "skill3")
                time.sleep(1.5)
                trials.append({"trial": trial + 1, "hp": self.hps([dummy])[dummy],
                               "cooldown": self.entry(self.bar(), "hwp_fs_rpg").get("cd", 0)})
        finally:
            restored = self.gl("skillcrit", "hwp_fs_rpg", "restore")
        hp1 = self.hps([dummy])[dummy]
        return {"damage": (hp0 - hp1) * 600, "hp": [hp0, hp1], "fixed_trials": trials,
                "fixture": fixture, "fixture_restore": restored,
                "fixture_ok": fixture.get("override_active") and fixture.get("crit_chance") == 1
                              and not restored.get("override_active")}

    def demolitionist(self):
        if not self.prepare("QAOrbDemo", "hwp_firearms_demolitions"):
            return
        d = self.open_dirs(130)[0]
        baseline = self.rocket_sample(d)
        self.check("rocket_rank_orb_control", baseline["fixture_ok"] and baseline["damage"] > 0 and baseline["hp"][1] > 0, baseline)
        for rank, multiplier in enumerate((1.15, 1.25), 1):
            ok, got = self.orb("hwp_fs_hoarder_overpacked", 1)
            live = self.rocket_sample(d)
            muls = {sid: self.probe(sid, 1).get("skillDmgMul", 0) for sid in
                    ("hwp_fs_rpg", "hwp_fs_frag", "hwp_attack_rifle_gl")}
            ratio = live["damage"] / max(0.001, baseline["damage"])
            self.check(f"overpacked_rank_{rank}", ok and got == rank and live["fixture_ok"] and live["hp"][1] > 0
                       and all(abs(m - multiplier) < 0.002 for m in muls.values()) and abs(ratio - multiplier) < 0.05,
                       {"orb": "hwp_fs_hoarder_overpacked", "rank": rank, "expected_multiplier": multiplier,
                        "live_explosive_skill_multipliers": muls, "real_damage_ratio": ratio, "natural_rockets": live})
        self.orb_off("hwp_fs_hoarder_overpacked")
        for rank, penetration in enumerate((0.06, 0.12), 1):
            ok, got = self.orb("hwp_fs_hoarder_shrapnel", 1)
            live = self.rocket_sample(d)
            custom = self.custom(self.probe("hwp_fs_rpg", 1), "hwp-shrapnel")
            ratio = live["damage"] / max(0.001, baseline["damage"])
            expected = 6 / (1 + 5 * (1 - penetration))
            self.check(f"elemental_shrapnel_rank_{rank}", ok and got == rank and live["fixture_ok"] and abs(custom - penetration) < 0.002
                       and live["hp"][1] > 0 and abs(ratio - expected) < 0.05,
                       {"orb": "hwp_fs_hoarder_shrapnel", "rank": rank, "penetration": custom,
                        "expected_damage_ratio_at1000resistance": expected, "real_damage_ratio": ratio,
                        "natural_rockets": live, "control": baseline})
        self.clear_dummies()
        self.to_town()


def run(p, section="marksman", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("orb_rank_crashed", False, {"section": section, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
