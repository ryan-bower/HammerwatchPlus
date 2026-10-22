"""Controlled native melee damage checks for the declared Parrying Dirk passive.

The existing damagefrom helper calls real Player.Damage. Its TrueStrike flag
is tested by the game after the Parry branch; its incoming direction is(0,-1).
Same-frame floating-text deltas and exact integer HP establish real parries.
Raw native stats-run snapshots retain the independent serialized counter.
No new attack or modifier, HP setter, or shared observer is introduced.
"""
import json
import time

from gamelab.bots.plan_classesa import Checks as Base
from gamelab.hps import hash_string


DUMMY = "gamelab/qa_firearms_target_dummy_resist_tough.unit"
DIRK = "hwp_oh_parrying_dirk"


def ids_in(value):
    if isinstance(value, dict):
        return ([value["id"]] if isinstance(value.get("id"), str) else []) + [
            item for sub in value.values() for item in ids_in(sub)]
    if isinstance(value, list):
        return [item for sub in value for item in ids_in(sub)]
    return []


class Checks(Base):
    def __init__(self, p):
        super().__init__(p)
        self.rows = []

    def check(self, case, ok, **data):
        self.flag(case, ok, str(data))
        self.rows.append(dict(case=case, runtime="PASS" if ok else "FAIL", **data))

    def parsed(self, path):
        reply = self.gl("sval", path, timeout=30)
        value = json.loads(reply["chunk"]) if reply.get("ok") else None
        return dict(path=path, ok=reply.get("ok"), ids=ids_in(value), value=value)

    def condition(self, tag, attacker, trials):
        start_counter = self.gl("inspect", "player", "stats-run")
        aim = self.gl("input", 20000, 0, 0, 0, -1)
        time.sleep(0.2)
        samples = []
        for index in range(trials):
            before, hit, after = self.g.gl_multi([["floats"], ["damagefrom", attacker, 1, "melee"], ["floats"]])
            parries_before = sum("parry" in t.get("text", "").lower() for t in before.get("texts", []))
            parries_after = sum("parry" in t.get("text", "").lower() for t in after.get("texts", []))
            new_parry = parries_after - parries_before
            valid = (before.get("ok") and hit.get("ok") and after.get("ok")
                     and before.get("truncated") == 0 and after.get("truncated") == 0
                     and hit.get("mode") == "melee" and hit.get("amount") == 1
                     and not hit.get("attacker_dead") and hit.get("hp", 0) > 0)
            actual_parry = valid and new_parry == 1 and hit.get("took") == 0 and hit.get("hp") == hit.get("hp0")
            actual_damage = valid and new_parry == 0 and hit.get("took", 0) > 0 and hit.get("hp", 0) < hit.get("hp0", 0)
            samples.append(dict(index=index, valid=bool(valid), parry=bool(actual_parry), damaged=bool(actual_damage),
                                before=before, hit=hit, after=after))
            time.sleep(0.12)
        finish_counter = self.gl("inspect", "player", "stats-run")
        result = dict(aim=aim, trials=samples, native_stats_run_before=start_counter,
                      native_stats_run_after=finish_counter,
                      parries=sum(s["parry"] for s in samples), damage_hits=sum(s["damaged"] for s in samples),
                      valid=len(samples) == trials and all(s["valid"] and (s["parry"] or s["damaged"]) for s in samples))
        self.out[tag] = result
        return result

    def dirk(self, trials=24):
        if not self.new_char("paladin", "QADirkDefense"):
            return
        self.gl("xp", 1301032)
        self.hwp("statpoints 450", 0.3)
        points = [self.gl("assign", stat, 150) for stat in ("str", "dex")]
        if not self.arena("dirk_defense"):
            return
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        native_skills = self.parsed("players/attacks/attacks_offhand.sval")
        native_weapons = self.parsed("tweak/items/equipment/equipment_weapons_offhand.sval")
        self.out["native_parsed_tables"] = dict(skills=native_skills, weapons=native_weapons)
        self.check("dirk_native_tables_observed", native_skills["ok"] and native_weapons["ok"],
                   native_stab_registered="attack_offhand_dirk" in native_skills["ids"],
                   native_dirk_registered="offhand_dirk_01" in native_weapons["ids"],
                   limits="Read-only engine parse; no prototype ability is enabled.")
        self.gl("equip", "twohanded_shortbow_01", "common", 1)
        control_gear = self.gl("equip", "mainhand_mace_01", "common", 1)
        spawned = self.gl("spawn", DUMMY, 0, -28)
        attacker = spawned.get("unit")
        target = next((u for u in self.gl("near", 100, "target_dummy").get("units", [])
                       if u.get("unit") == attacker), {})
        self.p.reflex(potion=0, fire=0)
        if self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"):
            self.hwp("god", 0.3)
        god = self.gl("cvars", "cht_god").get("cvars", {})
        requirements = self.gl("cvars", "dbg_cht_ignore_equipment_requirements").get("cvars", {})
        attributes = self.gl("benchstats")
        prepared = all(p.get("ok") for p in points) and control_gear.get("ok") and spawned.get("ok")
        prepared = prepared and target.get("hpMax") == 10000000 and god.get("cht_god") in (0, False)
        prepared = prepared and requirements.get("dbg_cht_ignore_equipment_requirements") in (0, False)
        prepared = prepared and all(attributes.get(stat, 0) >= 150 for stat in ("str", "dex"))
        self.check("dirk_fixed_native_damage_fixture", prepared, points=points, control_gear=control_gear,
                   attacker=target, god=god, requirements=requirements, native_attributes=attributes)
        if not prepared:
            return
        # The setup and parsed-table observations outlast native spawn invulnerability.
        time.sleep(4)
        control = self.condition("unequipped_control", attacker, trials)
        self.check("dirk_control_all_hits_damage", control["valid"] and control["damage_hits"] == trials
                   and control["parries"] == 0, control=control)
        if not self.out["dirk_control_all_hits_damage"]:
            return
        equipped = self.gl("equip", DIRK, "common", 35)
        gear = self.gl("inspect", "player", "equipped").get("value") or []
        bar = self.gl("skillbar")
        present = any(isinstance(item, list) and len(item) >= 4 and int(item[1]) & 0xFFFFFFFF == hash_string(DIRK)
                      and item[3] == 35 for item in gear)
        worn = equipped.get("ok") and equipped.get("quality") == 1 and equipped.get("ilvl") == 35 and present
        self.check("dirk_common_actually_worn", worn, equip=equipped, actual_equipped=gear, skillbar=bar)
        if not worn:
            return
        defense = self.condition("dirk_native_defense", attacker, trials)
        self.check("dirk_passive_native_parry", defense["valid"] and defense["parries"] > 0,
                   control_parries=control["parries"], defense=defense,
                   expected="At least one native parry in24 fixed frontal melee hits at declared60%; no rate balance assertion.",
                   native_sources={"parry": "scripts/Behaviors/Actors/Player/Player.as:429",
                                   "truestrike_block_gate": "scripts/Behaviors/Actors/Player/Player.as:478",
                                   "arc": "scripts/Behaviors/Actors/Modifiers/StatModifier.as:469"})
        self.gl("kill", 100, "target_dummy")
        self.to_town()


def run(p, **kwargs):
    c = Checks(p)
    try:
        c.dirk(**kwargs)
    except Exception as exc:
        c.check("content_dirk_crashed", False, error=repr(exc))
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
