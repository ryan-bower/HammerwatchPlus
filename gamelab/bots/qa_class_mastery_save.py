"""Controlled native mastery selection and exact save/reload persistence.

The runner performs WM_CLOSE/restart between select and verify. Verification
only reads the selected class, all available skill ranks, gear and picked stats.
This is separate from ordinary base-class mission/boss coverage.
"""
import json
from pathlib import Path

from gamelab.bots.qa_class_boss import Checks as BossChecks, GEAR
from gamelab.bots.qa_class_integration import CLASSES


MASTERIES = {
    "hwp_thief": ("hwp_thief_assassin", "hwp_thief_trickster", "hwp_thief_shadow"),
    "hwp_gladiator": ("hwp_gladiator_champion", "hwp_gladiator_beastmaster", "hwp_gladiator_retiarius"),
    "hwp_witch_hunter": ("hwp_witch_hunter_inquisitor", "hwp_witch_hunter_pyromancer", "hwp_witch_hunter_hunter"),
}


class Checks(BossChecks):
    @property
    def mastery_path(self):
        return self.g.results / "qa-class-mastery-expected.json"

    def mastery_skills(self, cls, mastery):
        source = Path(__file__).resolve().parents[2] / "docs/generated/qa_classes_inventory.json"
        entry = next(x for x in json.loads(source.read_text(encoding="utf-8"))["classes"] if x["id"] == cls)
        return {x["id"]: x["membership"] for x in entry["skills"] if x["membership"] in ("base", mastery)}

    def mastery_snapshot(self, cls, mastery):
        return {"state": self.gl("state"),
                "equipped": self.gl("inspect", "player", "equipped").get("value"),
                "equipment": self.gl("inspect", "player", "equipment").get("value"),
                "primary": self.gl("inspect", "player", "picked-" + GEAR[cls][0]).get("value"),
                "ranks": {sid: self.gl("skilltip", sid).get("level") for sid in self.mastery_skills(cls, mastery)}}

    def prepare_masteries(self, cls):
        super().prepare(cls)
        if self.out.get("prepared"):
            self.hwp("skillpoints 200", 0.3)
        self.flag("matrix_prepared", bool(self.out.get("prepared")))

    def select(self, cls, mastery):
        self.cls = cls
        if mastery not in MASTERIES[cls]:
            raise ValueError("mastery does not belong to the requested HoH1 port")
        prior_gear = self.gl("inspect", "player", "equipped").get("value")
        selected = self.gl("subclass", mastery)
        self.flag("mastery_selected", selected.get("class") == mastery, str(selected))
        if not self.out["mastery_selected"]:
            return
        membership = self.mastery_skills(cls, mastery)
        for sid in membership:
            current = self.gl("skilltip", sid).get("level", -1)
            if current == 0:
                self.gl("skill", sid, 1)
        snapshot = self.mastery_snapshot(cls, mastery)
        player = snapshot["state"].get("player", {})
        self.flag("selected_record", player.get("class") == mastery and player.get("name") == CLASSES[cls]["name"]
                  and player.get("level") == 20 and not player.get("dead"), str(player))
        own = [sid for sid, owner in membership.items() if owner == mastery]
        self.flag("mastery_ranks", len(own) == 3 and all(snapshot["ranks"].get(sid) == 1 for sid in membership),
                  str(snapshot["ranks"]))
        self.flag("selection_keeps_gear", snapshot["equipped"] == prior_gear and snapshot["primary"] == 57)
        expected = {"base": cls, "mastery": mastery, "snapshot": snapshot}
        self.mastery_path.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        self.flag("saved", bool(self.gl("save").get("ok")))
        self.out["expected_record"] = expected

    def verify_mastery(self, cls, mastery):
        self.cls = cls
        expected = json.loads(self.mastery_path.read_text(encoding="utf-8"))
        snapshot = self.mastery_snapshot(cls, mastery)
        player = snapshot["state"].get("player", {})
        old = expected["snapshot"]
        self.flag("selected_mastery_persisted", expected["base"] == cls and expected["mastery"] == mastery
                  and player.get("class") == mastery and player.get("name") == CLASSES[cls]["name"]
                  and player.get("level") == 20 and not player.get("dead") and snapshot["state"].get("phase") == "town", str(player))
        self.flag("available_ranks_persisted", snapshot["ranks"] == old["ranks"] and bool(snapshot["ranks"])
                  and all(rank == 1 for rank in snapshot["ranks"].values()), str(snapshot["ranks"]))
        self.flag("exact_gear_persisted", bool(snapshot["equipped"]) and snapshot["equipped"] == old["equipped"])
        self.flag("exact_bag_persisted", isinstance(snapshot["equipment"], list) and snapshot["equipment"] == old["equipment"])
        self.flag("picked_stats_persisted", snapshot["primary"] == old["primary"] == 57)
        # Read the cvar without toggling: this phase must not repair a bad loaded record.
        loaded_god = self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
        self.flag("loaded_god_off", isinstance(loaded_god, (int, float)) and loaded_god == 0)
        self.flag("mastery_verified", all(self.out.get(k) for k in ("selected_mastery_persisted",
                  "available_ranks_persisted", "exact_gear_persisted", "exact_bag_persisted", "picked_stats_persisted", "loaded_god_off")))
        self.out["loaded_record"] = snapshot


def run(p, cls="hwp_thief", section="prepare_masteries", mastery=None, **_):
    c = Checks(p)
    c.cls = cls
    try:
        getattr(c, section)(cls, mastery) if mastery else getattr(c, section)(cls)
    except Exception as exc:
        c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
