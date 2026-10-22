"""HoH1 summon ranks and pack caps through native passive spawning/combat.

No summon is directly spawned by this bot. Player input stays idle; a known
hostile target is the only enemy, so target HP loss is natural summon combat.
The exact configured damage is recorded for review; HP tables and pack counts
are independent live assertions, not claims about damage per attack.
"""
import time

from gamelab.bots.qa_class_procs import Checks as ProcChecks
from gamelab.bots.qa_classes import QA_DUMMY, QA_DUMMY_FILTER


FAMILIES = {
    "pit_fighters": ("hwp_gladiator", None, "hwp_gladiator_pit_fighters", "crusader_pikeman",
                     (600, 800, 1000, 1200, 1400), (50, 65, 80, 95, 110)),
    "beast": ("hwp_gladiator", "hwp_gladiator_beastmaster", "hwp_gladiator_beast",
              "players/ranger/units/wolf", (600, 850, 1100, 1350, 1600), (40, 55, 70, 85, 100)),
    "hound": ("hwp_witch_hunter", None, "hwp_witch_hunter_hound", "players/ranger/units/wolf",
              (500, 700, 900, 1100, 1300), (35, 50, 65, 80, 95)),
}
PACKS = {
    "beast_pack": ("beast", "hwp_gladiator_pack_leader", "hwp_gladiator_beastmaster"),
    "hound_pack": ("hound", "hwp_witch_hunter_pack", "hwp_witch_hunter_hunter"),
}


class Checks(ProcChecks):
    def owned(self, filt):
        near = self.gl("near", 1000, filt)
        if near.get("truncated"):
            return None
        rows = []
        for unit in near.get("units", []):
            if unit.get("dead"):
                continue
            info = self.gl("summonmove", unit["unit"])
            if not info.get("ok"):
                return None
            rows.append(info)
        return rows

    def wait_count(self, filt, count, timeout=45):
        samples, until = [], time.monotonic() + timeout
        while time.monotonic() < until:
            rows = self.owned(filt)
            samples.append({"owned": rows})
            if rows is None or len(rows) > count:
                return None, samples
            if len(rows) == count:
                return rows, samples
            time.sleep(0.25)
        return None, samples

    def lane(self, tag):
        # Includes the full20x30 passive-spawn jitter and actor body clearance.
        lane, note = self.to_trident_lane(front=96, back_neighbor=True, ray_distance=96,
                                          clearance_points=((0, 0, 40),), tag=tag)
        self.flag(tag + "_lane", bool(lane), note)
        return lane

    def combat(self, direction, tag, seconds=10):
        self.gl("kill", 1200, QA_DUMMY_FILTER)
        # Snapshot the target before any AI/native attack frame can run.
        replies = self.g.gl_multi([["spawn", QA_DUMMY, round(direction[0] * 96), round(direction[1] * 96)],
                                   ["actorbuffs", 200, QA_DUMMY_FILTER]])
        spawn = next((r for r in replies if "unit" in r), {})
        before = next((a for r in replies for a in r.get("actors", []) if a.get("unit") == spawn.get("unit")), None)
        valid = before is not None and before.get("hpMax") == 15000 and abs(before.get("hpExact", 0) - 15000) < 0.01
        samples, until = [], time.monotonic() + seconds
        while valid and time.monotonic() < until:
            mark = len(self.g.gl)
            self.gl("multi", "actorbuffs", 200, QA_DUMMY_FILTER, "+", "floats")
            observed = self.g.gl[mark:]
            target = next((a for r in observed for a in r.get("actors", []) if a.get("unit") == before["unit"]), None)
            samples.append({"target": target, "floats": next((r for r in observed if "texts" in r), {})})
            time.sleep(0.12)
        after = samples[-1]["target"] if samples else None
        hit = (valid and after is not None and not after.get("dead")
               and 0 < after.get("hpExact", 0) < before["hpExact"])
        self.flag(tag + "_natural_combat", bool(hit), f"known target setup {valid}; before {before}; after {after}")
        return bool(hit), {"before": before, "samples": samples, "after": after,
                           "scope": "actual natural summon HP loss; configured per-hit damage recorded separately, not inferred from sampling cadence"}

    def summon_ranks(self, family):
        cls, mastery, skill, filt, hp_table, dmg_table = FAMILIES[family]
        if not self.prepare(cls, mastery, "QASummon" + family):
            return
        lane = self.lane(family)
        if not lane:
            return
        self.gl("input", 10, 0, 0)
        rows, passed = [], True
        for rank, (hp, dmg) in enumerate(zip(hp_table, dmg_table), 1):
            tag = f"{family}_r{rank}"
            self.gl("kill", 1200, QA_DUMMY_FILTER)
            self.gl("kill", 1200, filt)
            learned = self.learn(skill, rank, tag)
            summons, spawn_samples = self.wait_count(filt, 1, 25)
            correct_hp = bool(summons) and all(s.get("hpMax") == hp and s.get("hpExact", 0) > 0 for s in summons)
            self.flag(tag + "_owned_hp", learned and correct_hp, str(summons))
            hit, combat = self.combat(lane[0], tag) if correct_hp else (False, {})
            passed &= bool(learned and correct_hp and hit)
            rows.append({"rank": rank, "expected_hp": hp, "configured_damage": dmg,
                         "owned": summons, "spawn_samples": spawn_samples, "combat": combat})
        self.out[family + "_trials"] = rows
        self.flag(family + "_all_ranks", passed and len(rows) == 5)
        self.to_town()

    def pack(self, key):
        family, skill, mastery = PACKS[key]
        cls, _, summon_skill, filt, hp_table, _ = FAMILIES[family]
        if not self.prepare(cls, mastery, "QAPack" + family):
            return
        lane = self.lane(key)
        if not lane or not self.learn(summon_skill, 1, key + "_summon"):
            return
        self.gl("input", 10, 0, 0)
        control, control_samples = self.wait_count(filt, 1, 25)
        self.flag(key + "_one_without_pack", bool(control), str(control_samples))
        passed, rows = bool(control), []
        for rank, count in enumerate((2, 2, 2, 3, 3), 1):
            tag = f"{key}_r{rank}"
            learned = self.learn(skill, rank, tag)
            summons, samples = self.wait_count(filt, count, 45)
            # Observe longer than one native20s spawn interval to detect an
            # incorrect higher cap rather than accepting its initial prefix.
            hold, stable = [], summons is not None
            until = time.monotonic() + 21
            while stable and time.monotonic() < until:
                owned = self.owned(filt)
                hold.append(owned)
                stable &= owned is not None and len(owned) == count and all(s.get("hpMax") == hp_table[0] for s in owned)
                time.sleep(0.4)
            hit, combat = self.combat(lane[0], tag, seconds=5) if stable else (False, {})
            self.gl("kill", 1200, QA_DUMMY_FILTER)
            ok = bool(learned and stable and hit)
            self.flag(tag + "_cap_and_combat", ok, f"expected {count} owned wolves; stable {stable}; natural combat {hit}")
            passed &= ok
            rows.append({"rank": rank, "expected_count": count, "owned": summons,
                         "spawn_samples": samples, "full_interval_rosters": hold, "combat": combat})
        self.out[key + "_trials"] = rows
        self.flag(key + "_all_ranks", passed and len(rows) == 5)
        self.to_town()


def run(p, sections="pit_fighters,beast,hound", **_):
    c = Checks(p)
    for section in sections.split(","):
        try:
            c.summon_ranks(section) if section in FAMILIES else c.pack(section)
        except Exception as exc:
            c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
