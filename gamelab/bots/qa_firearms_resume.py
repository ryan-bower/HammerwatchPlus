"""Same-record native save/resume of an unequally depleted mixed magazine.

Requires the dedicated native seed fixture and runner's optional resume choice.
One Firearms record is created after normal scenario mod activation, before all
measurements; that same record is saved/resumed. Verification reads gear/ammo
before any setter after restart.
"""
import time

from gamelab.bots.qa_firearms_magazine_edges import Checks as Base


class Checks(Base):
    def identity(self):
        state = self.gl("state")
        player = state.get("player", {})
        return {"phase": state.get("phase"), "name": player.get("name"),
                "class": player.get("class"), "level": player.get("level"),
                "dead": player.get("dead"), "clip": self.clip(), "capacity": self.clip_max(),
                "steady_rank": self.current_rank("hwp_fs_steady"),
                "gear": self.gl("bagitems").get("main", {}),
                "skills": [s.get("id") for s in self.bar().get("skills", [])]}

    @staticmethod
    def correct_record(row):
        return row["name"] == "QAMagResume" and row["class"] == "hwp_firearms" and not row["dead"]

    def prepare_save(self):
        seed = self.gl("state")
        player = seed.get("player", {})
        valid_seed = (seed.get("phase") == "town" and player.get("class") == "paladin"
                      and player.get("name") == "ZZMagSeed" and player.get("level") == 1
                      and not player.get("dead"))
        self.check("resume_native_seed_fixture", valid_seed, seed)
        if not valid_seed:
            return
        # The fixture is built with GameLab only. The scenario activates content
        # through the runner's alias -> native hwp-* ID mapping before this call.
        # Do not use Base.new_char: it also equips/levels/learns before readbacks.
        made = self.gl("char", "hwp_firearms", "QAMagResume")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = self.gl("state")
            player = state.get("player", {})
            if (state.get("phase") == "town" and player.get("class") == "hwp_firearms"
                    and player.get("name") == "QAMagResume" and not player.get("dead")):
                break
            time.sleep(0.25)
        time.sleep(1)
        initial = self.identity()
        valid_initial = made.get("ok") and self.correct_record(initial) and initial["phase"] == "town"
        valid_initial = (valid_initial
                   and initial["level"] == 1 and initial["gear"].get("id") == "hwp_glock_mh_01"
                   and initial["gear"].get("quality") == 1 and initial["capacity"] == 10)
        self.check("resume_fixture_identity", valid_initial, {"created": made, "record": initial})
        if not valid_initial:
            return
        # Pinned native XP for level20, without the levelup command's delta/target
        # ambiguity. The eventual save and restart both require actual level20.
        self.gl("xp", 1301032)
        self.hwp("skillpoints 999", 0.3, until="skill points")
        assigned = [self.gl("assign", "str", 10), self.gl("assign", "dex", 10)]
        self.base_skills()
        if not self.start_floor(0):
            self.check("resume_first_floor", False, {})
            return
        self.god_on()
        self.gl("kill", 6000, "tag:enemy")
        # Save on floor2 so a resumed run cannot be mistaken for a genuinely new
        # first-floor spawn, which intentionally starts with a full shared clip.
        self.next_floor()
        time.sleep(2)
        self.god_on()
        self.gl("kill", 6000, "tag:enemy")
        self.check("resume_setup_god_disabled", self.ordinary_damage(), {})
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        self.g.console("dbg_cht_ignore_equipment_requirements 1")
        time.sleep(0.25)
        ok, gear = self.fixture_loadout("hwp_glock_mh_01", "hwp_hcannon_oh_01")
        d = self.open_dirs(130)[0]
        self.tough(d, 60)
        self.baseline = self.probe(rolls=1)
        rank = self.learn_rank("hwp_fs_steady", 5)
        rows = [self.cycle(d, refill=trial == 0) for trial in range(4)]
        row = rows[-1]
        after = self.identity()
        bonuses = self.bonuses(row)
        self.check("resume_unequal_saved_setup", ok and all(x.get("ok") for x in assigned) and rank == 5
                   and self.correct_record(after) and after["phase"] == "mission" and after["level"] == 20
                   and row["clip"] == [15, 12] and after["capacity"] == 24 and all(x["actual_damage"] > 0 for x in rows)
                   and abs(self.baseline["mainCritDmg"] - self.baseline["offCritDmg"]) < 0.001
                   and abs(bonuses[0] - 0.14) < 0.003 and abs(bonuses[1] - 0.10) < 0.003,
                   {"record": after, "gear_setup": gear, "attributes": assigned,
                    "baseline": self.baseline, "four_natural_bursts": rows, "own_rounds": [7, 5], "crit_bonuses": bonuses})
        self.g.shot("magazine-before-save")
        self.clear_dummies()

    def verify_resume(self):
        # Identity, native ammo and equipment are captured before a setup mutation.
        resumed = self.identity()
        self.check("resumed_record_and_native_ammo", self.correct_record(resumed) and resumed["phase"] == "mission"
                   and resumed["level"] == 20 and resumed["steady_rank"] == 5
                   and resumed["clip"] == 12 and resumed["capacity"] == 24
                   and resumed["gear"].get("id") == "hwp_glock_mh_01" and resumed["gear"].get("quality") == 1
                   and "hwp_attack_glock" in resumed["skills"] and "hwp_attack_hcannon_off" in resumed["skills"], resumed)
        self.check("resume_god_disabled", self.ordinary_damage(), {})
        self.gl("kill", 6000, "tag:enemy")
        d = self.open_dirs(130)[0]
        self.tough(d, 60)
        stats = self.probe(rolls=1)
        gap = stats.get("mainCritDmg", -99) - stats.get("offCritDmg", 99)
        # Both common guns have no crit affix, and their equal base multipliers
        # were read back before Steady. With total12, a+.04 hand gap means7+5.
        # Proportional reconstruction would produce8+4 and is therefore rejected.
        self.check("resume_preserves_unequal_bonus_split", self.clip() == 12 and abs(gap - 0.04) < 0.003,
                   {"resumed_stats": stats, "main_minus_off_crit_damage": gap,
                    "shared_rounds": self.clip(), "expected_own_rounds": [7, 5]})
        self.g.shot("magazine-after-resume")
        fixture = self.gl("skillcrit", "hwp_attack_hcannon_off", 1)
        try:
            row = self.cycle(d)
        finally:
            restored = self.gl("skillcrit", "hwp_attack_hcannon_off", "restore")
        gap = row["stats"].get("mainCritDmg", -99) - row["stats"].get("offCritDmg", 99)
        self.check("resume_next_real_critical_mixed_burst", fixture.get("override_active") and not restored.get("override_active")
                   and row["clip"] == [12, 9] and row["actual_damage"] > 0 and abs(gap - 0.02) < 0.003,
                   {"natural_critical_burst": row, "expected_own_rounds": [5, 4],
                    "main_minus_off_crit_damage": gap, "fixture": fixture, "fixture_restore": restored})
        self.clear_dummies()
        self.to_town()


def run(p, stage="prepare_save", **_):
    c = Checks(p)
    try:
        getattr(c, stage)()
    except Exception as exc:
        c.check("resume_crashed", False, {"stage": stage, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
