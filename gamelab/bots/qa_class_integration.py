"""HoH1 ports in actual HoH2 floors, plus explicitly controlled lifecycle checks.

Preparation is a lab fixture. The ordinary-floor phase clears no enemies,
teleports nowhere, keeps timescale1 and god off, and uses the existing Pilot.
"""
import json
import time
from pathlib import Path

from gamelab.bots import floor_runner
from gamelab.bots.plan_classesa import Checks as ClassChecks
from gamelab.bots.qa_class_drive import ClassPilot
from gamelab.hps import hash_string


CLASSES = {
    "hwp_thief": {"name": "QAThiefRun", "kite": 24, "summon": None},
    "hwp_gladiator": {"name": "QAGladiatorRun", "kite": 24, "summon": "crusader_pikeman", "weapon": "hwp_trident_01"},
    "hwp_witch_hunter": {"name": "QAHunterRun", "kite": 90, "summon": "players/ranger/units/wolf", "weapon": "hwp_crossbow_01"},
}


class Checks(ClassChecks):
    def god_off(self):
        for _ in range(3):
            reply = self.gl("cvars", "cht_god")
            if "cht_god" not in reply.get("cvars", {}):
                return False
            if not reply["cvars"]["cht_god"]:
                return True
            self.hwp("god", 0.3)
        return False

    def expected_skills(self, cls):
        path = Path(__file__).resolve().parents[2] / "docs/generated/qa_classes_inventory.json"
        inventory = json.loads(path.read_text(encoding="utf-8"))
        entry = next(c for c in inventory["classes"] if c["id"] == cls)
        return [s["id"] for s in entry["skills"] if s["membership"] == "base"]

    def snapshot(self):
        return {"state": self.gl("state"), "equipped": self.gl("inspect", "player", "equipped").get("value"),
                "stats": self.gl("benchstats"), "materials": self.gl("inv").get("materials", {})}

    def verify(self, cls):
        pl = self.gl("state").get("player", {})
        levels = {sid: self.gl("skilltip", sid).get("level") for sid in self.expected_skills(cls)}
        gear = self.gl("inspect", "player", "equipped").get("value") or []
        expected_weapon = CLASSES[cls].get("weapon")
        gear_ok = any(isinstance(x, list) and len(x) > 1 and int(x[1]) & 0xFFFFFFFF == hash_string(expected_weapon)
                      for x in gear) if expected_weapon else self.gl("benchstats").get("mhPhys", 0) > 0
        self.flag("class_record", pl.get("class") == cls and pl.get("name") == CLASSES[cls]["name"], str(pl))
        self.flag("base_ranks", bool(levels) and all(v == 1 for v in levels.values()), str(levels))
        self.flag("starting_weapon", gear_ok, str(gear))
        self.flag("god_off", self.god_off())
        self.flag("verified", all(self.out.get(k) for k in ("class_record", "base_ranks", "starting_weapon", "god_off")))

    def prepare(self, cls):
        if not self.new_char(cls, CLASSES[cls]["name"]):
            return
        self.hwp("levelup 4", 0.3)
        self.hwp("skillpoints 80", 0.3)
        for sid in self.expected_skills(cls):
            if self.gl("skilltip", sid).get("level", 0) == 0:
                self.gl("skill", sid, 1)
        self.verify(cls)
        self.out["prepared_snapshot"] = self.snapshot()
        self.flag("prepared", self.out.get("verified") and self.out["prepared_snapshot"]["state"].get("player", {}).get("level") == 5)
        self.gl("save")

    def ordinary(self, cls, floors=2, budget_s=180):
        if not self.god_off():
            self.flag("ordinary_god_off", False)
            return
        before = self.snapshot()
        start = self.gl("mission", "bandit_keep", 0)
        if not start.get("ok") or not self.wait_phase("mission", 90):
            self.flag("ordinary_entered", False, str(start))
            return
        time.sleep(3)
        self.flag("ordinary_god_off", self.god_off())
        summon_filter = CLASSES[cls]["summon"]
        summon_before = self.gl("near", 800, summon_filter).get("units", []) if summon_filter else []
        samples = []
        driver = ClassPilot(self.p, cls)
        self.out["ordinary_driver"] = driver.description()
        for index in range(int(floors)):
            result = floor_runner.run(driver, budget_s=budget_s, kite_range=CLASSES[cls]["kite"])
            samples.append(result)
            self.notes.append(f"ordinary floor {index}: {result}")
            if result.get("terminal") != "next_floor":
                break
            self.wait_phase("mission", 90)
            time.sleep(3)
        after = self.snapshot()
        b, a = before["state"].get("player", {}), after["state"].get("player", {})
        reward = (a.get("level", 0) > b.get("level", 0) or a.get("xp", 0) > b.get("xp", 0)
                  or after["materials"].get("gold", 0) > before["materials"].get("gold", 0))
        self.flag("ordinary_floors", len(samples) == floors and all(s.get("terminal") == "next_floor" for s in samples))
        self.flag("ordinary_class_survives", a.get("class") == cls and not a.get("dead") and after["state"].get("phase") == "mission", str(a))
        self.flag("ordinary_rewards", reward, f"before {b}, materials {before['materials']}; after {a}, materials {after['materials']}")
        if summon_filter:
            summon_after = self.gl("near", 800, summon_filter).get("units", [])
            self.flag("ordinary_summon_after_floor", any(not u.get("dead") for u in summon_before)
                      and any(not u.get("dead") for u in summon_after), f"before {summon_before}; after {summon_after}")
        self.out["ordinary_samples"] = samples
        self.out["ordinary_before"], self.out["ordinary_after"] = before, after
        self.to_town()

    def death(self, cls):
        """Controlled lethal trap damage, real DeadMenu acceptance and town save.

        This does not claim an unassisted enemy death during ordinary play.
        """
        if not self.god_off():
            self.flag("death_god_off", False)
            return
        self.gl("mission", "bandit_keep", 0)
        if not self.wait_phase("mission", 90):
            self.flag("death_entered", False)
            return
        time.sleep(2)
        pl = self.gl("state").get("player", {})
        hit = self.gl("damageme", max(1, pl.get("hpMax", 1)) * 3)
        time.sleep(0.5)
        dead = self.gl("state")
        self.flag("death_damage_path", hit.get("dead") and dead.get("player", {}).get("dead"), str(hit))
        if dead.get("player", {}).get("dead"):
            # Native DeadMenu ignores MenuAccept for its first1500ms. The old
            # single Enter arrived only727ms after lethal damage and was lost.
            # Let that normal guard elapse, then send one real menu accept.
            time.sleep(1.6)
            self.g.key("enter")
        town = self.wait_phase("town", 90)
        time.sleep(1)
        state = self.gl("state")
        if state.get("window") and town:
            self.g.key("escape")
        self.flag("death_town_return", town and state.get("player", {}).get("class") == cls
                  and not state.get("player", {}).get("dead"), str(state))
        self.gl("save")


def run(p, cls="hwp_thief", section="prepare", **kwargs):
    c = Checks(p)
    try:
        getattr(c, section)(cls, **kwargs)
    except Exception as exc:
        c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
