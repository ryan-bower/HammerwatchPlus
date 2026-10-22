"""Matched level20 HoH1-port fixture, then ordinary HoH2 Bandit Keep completion.

Only prepare mutates build stats/gear. The run uses normal Pilot walking/combat,
native potion reflexes, a real boss, its reward window, and its unlocked portal.
No teleport, direct kill, cull, god, timescale, or HP/mana setters in run.
"""
import json
import time
from collections import Counter
from dataclasses import asdict

from gamelab.bots import floor_runner
from gamelab.bots.qa_class_integration import Checks as IntegrationChecks, CLASSES
from gamelab.bots.qa_class_drive import ClassPilot
from gamelab.hps import hash_string
from gamelab.bots.qa_firearms_input_sequence import Checks as SequenceChecks


GEAR = {
    "hwp_thief": ("dex", "twohanded_daggers_01", "twohanded_daggers_03"),
    "hwp_gladiator": ("str", "hwp_trident_01", "hwp_trident_01"),
    "hwp_witch_hunter": ("dex", "hwp_crossbow_01", "hwp_crossbow_01"),
}
BOSS_FLAG = hash_string("boss_bandit")


def has_item(items, name, ilvl=None):
    return any(isinstance(x, list) and len(x) >= 4
               and int(x[1]) & 0xFFFFFFFF == hash_string(name)
               and (ilvl is None or x[3] == ilvl) for x in items or [])


class Checks(IntegrationChecks):
    def new_char(self, cls, name):
        # Ordinary fixtures must not inherit plan_classesa's additional20SP.
        made = self.gl("char", cls, name)
        town = self.wait_phase("town", 60)
        time.sleep(2)
        state = self.gl("state")
        player = state.get("player", {})
        ok = (made.get("ok") is True and town and player.get("class") == cls
              and player.get("name") == name and player.get("dead") is False
              and player.get("bonusSkillPoints") == 0
              and type(player.get("skillFree")) is int and player["skillFree"] >= 0)
        self.flag(f"{cls}_char", bool(ok), str({"made": made, "state": state}))
        return bool(ok)

    @staticmethod
    def legal_points(snapshot):
        player = snapshot.get("state", {}).get("player", {})
        return (type(player.get("skillFree")) is int and player["skillFree"] >= 0
                and player.get("bonusSkillPoints") == 0
                and snapshot.get("bonus_skills") == 0 and snapshot.get("bonus_stats") == 0)

    def at_1x(self):
        value = self.gl("cvars", "g_timescale").get("cvars", {}).get("g_timescale")
        return isinstance(value, (int, float)) and abs(value - 1.0) < 0.0001

    def record(self):
        primary = GEAR[self.cls][0]
        flags = self.gl("inspect", "player", "flags").get("value") or []
        return {"state": self.gl("state"),
                "bonus_skills": self.gl("inspect", "player", "bonus-skills").get("value"),
                "bonus_stats": self.gl("inspect", "player", "bonus-stats").get("value"),
                "equipped": self.gl("inspect", "player", "equipped").get("value"),
                "equipment": self.gl("inspect", "player", "equipment").get("value"),
                "primary": self.gl("inspect", "player", "picked-" + primary).get("value"),
                "ranks": {sid: self.gl("skilltip", sid).get("level") for sid in self.expected_skills(self.cls)},
                "boss_flag": any(int(f) & 0xFFFFFFFF == BOSS_FLAG for f in flags),
                "stats": self.gl("benchstats"), "materials": self.gl("inv").get("materials", {})}

    @property
    def prepared_path(self):
        return self.g.results / "qa-class-boss-prepared.json"

    def persist(self, snapshot):
        self.prepared_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    def prepare(self, cls):
        self.cls = cls
        if not self.new_char(cls, CLASSES[cls]["name"]):
            return
        attr, starter, weapon = GEAR[cls]
        fresh = self.gl("inspect", "player", "equipped").get("value") or []
        self.flag("fresh_starting_weapon", has_item(fresh, starter), str(fresh))
        self.gl("xp", 1301032)
        # Native level-earned points only. No bonus points or unlock writes.
        earned = self.record()
        self.flag("native_earned_points_before_learning", self.legal_points(earned)
                  and earned["state"].get("player", {}).get("level") == 20, str(earned))
        if not self.out["native_earned_points_before_learning"]:
            return
        self.out["native_earned_before_learning"] = earned
        self.out["native_town_baseline"] = self.gl("inspect", "town")
        for sid in self.expected_skills(cls):
            if self.gl("skilltip", sid).get("level", 0) == 0:
                self.gl("skill", sid, 1)
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        requirements = self.gl("cvars", "dbg_cht_ignore_equipment_requirements")
        self.flag("native_requirements_enabled", requirements.get("ok") is True
                  and requirements.get("cvars", {}).get("dbg_cht_ignore_equipment_requirements") == 0,
                  str(requirements))
        assigned = self.gl("assign", attr, "all")
        weapon_reply = self.gl("equip", weapon, "common", 20)
        armor = self.gl("kit", 20, "rare", "head,chest,hands,feet", "seed=20261022")
        potion = self.gl("upgrade", "apothecary", "potion-charges", 4)
        snapshot = self.record()
        self.flag("native_earned_points_after_learning", self.legal_points(snapshot), str(snapshot))
        self.flag("prepared_level20", snapshot["state"].get("player", {}).get("level") == 20, str(snapshot["state"]))
        back = {"slot": 6, "expected": None, "equipped": (snapshot["equipped"] or [])[6] if len(snapshot["equipped"] or []) == 7 else "invalid equipped readback",
                "scope": "Explicitly empty back; four legal matched20 rare armor pieces, common20 class weapon"}
        self.out["setup"] = {"fresh_equipped": fresh, "assign": assigned, "weapon": weapon_reply,
                             "armor": armor, "back": back, "potion": potion, "snapshot": snapshot,
                             "requirements": requirements,
                             "fixture_scope": "Controlled nativeXP20, common20 weapon/fourrare20 armor/emptyback, provided5potion capacity via native upgrade minus cost; no natural purchase/unlock/acquisition credit."}
        self.flag("legal_level20_gear", weapon_reply.get("ok") and weapon_reply.get("ilvl") == 20
                  and weapon_reply.get("quality") == 1
                  and has_item(snapshot["equipped"], weapon, 20) and armor.get("ok")
                  and armor.get("ilvl") == 20 and len(armor.get("items", [])) == 4 and not armor.get("failed")
                  and len(snapshot["equipped"] or []) == 7 and snapshot["equipped"][6] is None,
                  str(self.out["setup"]))
        self.flag("primary57", assigned.get("ok") and assigned.get("left") == 0 and snapshot["primary"] == 57,
                  str(assigned))
        self.flag("potion5", potion.get("ok") and potion.get("potionCharges") == 5, str(potion))
        self.flag("fresh_boss_flag_absent", not snapshot["boss_flag"])
        self.persist(snapshot)
        self.verify(cls)
        self.flag("prepared", all(self.out.get(k) for k in ("fresh_starting_weapon", "legal_level20_gear",
                  "primary57", "potion5", "fresh_boss_flag_absent", "verified", "prepared_level20",
                  "native_earned_points_before_learning", "native_earned_points_after_learning", "native_requirements_enabled")))
        snapshot["setup_valid"] = bool(self.out.get("prepared"))
        self.persist(snapshot)
        self.gl("save")

    def verify(self, cls):
        self.cls = cls
        expected = json.loads(self.prepared_path.read_text(encoding="utf-8"))
        now = self.record()
        player = now["state"].get("player", {})
        expected_level = expected["state"].get("player", {}).get("level")
        self.flag("class_record", isinstance(expected_level, int) and expected_level >= 20
                  and player.get("class") == cls and player.get("name") == CLASSES[cls]["name"]
                  and player.get("level") == expected_level and not player.get("dead"),
                  str({"actual": player, "exact_expected_level": expected_level}))
        self.flag("native_points_legal", self.legal_points(now), str(now))
        self.flag("native_points_persisted", self.legal_points(expected)
                  and player.get("skillFree") == expected["state"]["player"].get("skillFree"),
                  str({"actual": player.get("skillFree"), "expected": expected["state"]["player"].get("skillFree")}))
        self.flag("base_ranks", bool(now["ranks"]) and now["ranks"] == expected["ranks"]
                  and all(rank == 1 for rank in now["ranks"].values()), str(now["ranks"]))
        self.flag("gear_persisted", now["equipped"] == expected["equipped"]
                  and has_item(now["equipped"], GEAR[cls][2], 20), str(now["equipped"]))
        self.flag("bag_persisted", isinstance(now["equipment"], list) and now["equipment"] == expected["equipment"],
                  str(now["equipment"]))
        actual_bag = Counter(json.dumps(x, sort_keys=True) for x in now["equipment"] or [])
        required_reward = Counter(expected.get("reward_items", []))
        self.flag("reward_persisted", not (required_reward - actual_bag))
        self.flag("primary_persisted", now["primary"] == expected["primary"] == 57)
        self.flag("boss_flag_persisted", now["boss_flag"] == expected["boss_flag"])
        self.flag("god_off", self.god_off())
        self.flag("verified", all(self.out.get(k) for k in ("class_record", "base_ranks", "gear_persisted", "bag_persisted", "reward_persisted",
                  "primary_persisted", "boss_flag_persisted", "god_off", "native_points_legal", "native_points_persisted")))
        self.out["verification"] = now

    def boss_unit(self):
        found = self.gl("near", 2000, "boss_bandit")
        return next((u for u in found.get("units", []) if not u.get("dead") and u.get("hpMax") == 20000), None)

    def flag_set(self):
        flags = self.gl("inspect", "player", "flags").get("value") or []
        return any(int(f) & 0xFFFFFFFF == BOSS_FLAG for f in flags)

    def ordinary(self, cls, floor_budget_s=180, boss_budget_s=480):
        self.cls = cls
        prepared = json.loads(self.prepared_path.read_text(encoding="utf-8"))
        self.flag("ordinary_valid_prepared_fixture", prepared.get("setup_valid") is True)
        if not self.out["ordinary_valid_prepared_fixture"]:
            return
        self.verify(cls)
        if not self.out.get("verified"):
            return
        before = self.record()
        self.flag("ordinary_god_off", self.god_off())
        self.flag("ordinary_1x", self.at_1x())
        self.flag("ordinary_fresh_boss", not before["boss_flag"])
        if not all(self.out.get(k) for k in ("ordinary_god_off", "ordinary_1x", "ordinary_fresh_boss")):
            return
        start = self.gl("mission", "bandit_keep", 0)
        if not start.get("ok") or not self.wait_phase("mission", 90):
            self.flag("ordinary_entered", False, str(start))
            return
        time.sleep(3)
        floors = []
        self.out["floors"] = floors
        driver = ClassPilot(self.p, cls)
        self.out["ordinary_driver"] = driver.description()
        for index in range(5):
            result = floor_runner.run(driver, budget_s=floor_budget_s, kite_range=CLASSES[cls]["kite"])
            floors.append(result)
            if result.get("terminal") != "next_floor":
                self.flag("ordinary_floors", False, str(floors))
                return
            if not self.wait_phase("mission", 90):
                self.flag("ordinary_floors", False, str(floors))
                return
            time.sleep(2)
        self.flag("ordinary_floors", len(floors) == 5 and all(x.get("terminal") == "next_floor" for x in floors))
        state = self.gl("state")
        self.flag("boss_level", "boss_bandits" in str(state.get("level", "")), str(state))
        if not self.out["boss_level"]:
            return
        # Normal path crosses the fixed level's intro area; native scripts spawn the boss.
        driver.reflex(potion=50, fire=0)
        approach = driver.path_to(0, -128, until=["dead"], timeout=45)
        self.out["boss_approach"] = asdict(approach)
        boss = None
        until = time.time() + 15
        while time.time() < until and not boss:
            boss = self.boss_unit()
            if not boss:
                time.sleep(0.5)
        valid = boss is not None and boss.get("hpMax") == 20000 and boss.get("hpExact", 0) > 0
        self.flag("natural_boss", valid, str(boss))
        if not valid:
            return
        driver.reflex(potion=50, fire=160)
        samples = [{"boss": boss, "state": self.gl("state")}]
        self.out["boss_samples"] = samples
        end = time.time() + boss_budget_s
        initial_hp = boss["hpExact"]
        damaged = False
        while time.time() < end and not self.flag_set():
            result = driver.kite(boss["unit"], CLASSES[cls]["kite"], until=["dead", "target_dead"], timeout=20)
            current = self.boss_unit()
            state = self.gl("state")
            samples.append({"boss": current, "state": state, "intent": asdict(result)})
            damaged |= current is not None and current.get("hpExact", initial_hp) < initial_hp
            if state.get("player", {}).get("dead"):
                break
            if not current and not self.flag_set():
                # Live lookup excludes Actor.IsDead immediately; the level's
                # UnitDestroyedTrigger waits for the separate native Destroyed
                # event. Observe that bounded transition without attacking or
                # invoking a death/flag callback from the test fixture.
                grace, deadline = [], time.monotonic() + 8
                while time.monotonic() < deadline:
                    raw = self.gl("near", 2000, "boss_bandit")
                    original = next((u for u in raw.get("units", []) if u.get("unit") == boss["unit"]), None)
                    observed_state = self.gl("state")
                    native_flag = self.flag_set()
                    grace.append({"boss": original, "state": observed_state, "native_defeat_flag": native_flag})
                    if original is not None and isinstance(original.get("hpExact"), (int, float)):
                        damaged |= original["hpExact"] < initial_hp
                    if native_flag or observed_state.get("player", {}).get("dead"):
                        break
                    time.sleep(0.1)
                self.out["boss_destroyed_flag_observations"] = grace
                break
        defeated = self.flag_set()
        # The native UnitDestroyedTrigger sets this flag only after the live boss dies.
        # With no damage/kill setters in this phase, live HP -> destruction is damage proof
        # even if a summon lands the final hit between two Python observations.
        damaged |= defeated and boss.get("hpExact", 0) > 0
        self.flag("boss_actual_damage", damaged, str(samples))
        self.flag("boss_defeated", defeated and not self.gl("state").get("player", {}).get("dead"))
        if not defeated:
            return
        time.sleep(3)
        rewards = self.gl("near", 2000, "equipment_map_reward").get("units", [])
        self.flag("boss_reward_spawned", len(rewards) == 1, str(rewards))
        if len(rewards) != 1:
            return
        # ShopWindow pauses native PilotFrame. Accept the normal path/use intent,
        # then consume the real reward before waiting for its later unpaused end.
        started = self.p.start("use", rewards[0]["unit"], until=["dead"], timeout=40)
        shop, polls = {}, []
        deadline = time.monotonic() + 45
        while started.get("ok") is True and time.monotonic() < deadline:
            shop = self.gl("shop")
            observed = self.gl("state")
            polls.append({"shop": shop, "state": observed})
            if shop.get("window") == "EquipmentGiverWindow" or observed.get("player", {}).get("dead"):
                break
            time.sleep(.1)
        self.out["reward_use_started"], self.out["reward_shop"] = started, shop
        self.out["reward_window_observations"] = polls
        self.flag("boss_reward_window", started.get("ok") is True
                  and isinstance(started.get("id"), str) and bool(started["id"])
                  and started.get("accepted") == "use" and started.get("target") == rewards[0]["unit"]
                  and shop.get("ok") is True and shop.get("window") == "EquipmentGiverWindow"
                  and shop.get("count", 0) > 0, str(shop))
        if not self.out["boss_reward_window"]:
            return
        # Release only the QA Pilot intent while the real shop remains paused.
        # PilotEnd emits immediately; no CanUse-after-Buy assumption or second
        # Use pulse is needed. This does not close or buy from the shop.
        reflex_off = driver.reflex(potion=0, fire=0)
        paused_controller, paused_clock = self.gl("controller"), self.gl("clock")
        stopped = self.p.stop()
        use = self.p.wait_end(started["id"], timeout=5)
        still_shop = self.gl("shop")
        stop_valid = (reflex_off.get("ok") is True and stopped.get("ok") is True
                      and stopped.get("stopped") is True and use.result == "interrupted"
                      and use.reason == "stop" and use.intent == "use"
                      and isinstance(use.event, dict) and use.event.get("id") == started["id"]
                      and still_shop.get("ok") is True and still_shop.get("window") == "EquipmentGiverWindow"
                      and still_shop.get("count") == shop.get("count"))
        self.out["reward_use"] = {"stop": stopped, "end": asdict(use), "shop_still_open": still_shop,
                                   "reflex_off": reflex_off, "valid_expected_stop": bool(stop_valid)}
        if not stop_valid:
            self.flag("boss_reward_taken", False, str(self.out["reward_use"]))
            return
        bag_before = self.gl("inspect", "player", "equipment").get("value")
        picked = self.gl("shop", "buy", 0)
        time.sleep(0.3)
        released = SequenceChecks.released(self)
        resumed_clock = self.gl("clock")
        clocks = (paused_clock, resumed_clock)
        native_resumed = (all(c.get("ok") is True and type(c.get("sceneMs")) is int
                              and type(c.get("frames")) is int for c in clocks)
                          and resumed_clock["sceneMs"] > paused_clock["sceneMs"]
                          and resumed_clock["frames"] >= paused_clock["frames"] + 2)
        final_controller = released.get("second", [{}])[0]
        input_released = (paused_controller.get("ok") is True
                          and type(paused_controller.get("frames")) is int
                          and type(final_controller.get("frames")) is int
                          and final_controller["frames"] >= paused_controller["frames"] + 2)
        self.out["reward_release"] = {"controller": released, "before": paused_controller,
                                      "clock_before": paused_clock, "clock_after": resumed_clock,
                                      "native_resumed": bool(native_resumed), "two_native_input_frames": bool(input_released)}
        reflex_restored = driver.reflex(potion=50, fire=160)
        bag_after = self.gl("inspect", "player", "equipment").get("value")
        state = self.gl("state")
        reward_items = list((Counter(json.dumps(x, sort_keys=True) for x in bag_after or [])
                             - Counter(json.dumps(x, sort_keys=True) for x in bag_before or [])).elements())
        self.flag("boss_reward_taken", stop_valid and picked.get("ok") and released.get("valid")
                  and native_resumed and input_released and reflex_restored.get("ok") is True
                  and isinstance(bag_before, list) and isinstance(bag_after, list)
                  and len(bag_after) == len(bag_before) + 1 and len(reward_items) == 1
                  and not (Counter(json.dumps(x, sort_keys=True) for x in bag_before)
                           - Counter(json.dumps(x, sort_keys=True) for x in bag_after))
                  and state.get("window") != "EquipmentGiverWindow",
                  str({"before": bag_before, "after": bag_after, "buy": picked, "state": state}))
        self.out["reward_inventory"] = {"before": bag_before, "after": bag_after, "buy": picked}
        portal = self.p.exit(until=["dead"], timeout=60)
        town = self.wait_phase("town", 90)
        self.flag("natural_town_return", portal.ok and town, str(asdict(portal)))
        if not town:
            return
        state = self.gl("state")
        if state.get("window"):
            self.g.key("escape")
        after = self.record()
        self.flag("ordinary_finishes_1x", self.at_1x())
        final_god = self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
        self.flag("ordinary_class_survives", after["state"].get("player", {}).get("class") == cls
                  and not after["state"].get("player", {}).get("dead")
                  and isinstance(final_god, (int, float)) and final_god == 0)
        self.flag("ordinary_gear_unchanged", after["equipped"] == before["equipped"])
        after["reward_items"] = reward_items
        self.out["ordinary_before"], self.out["ordinary_after"] = before, after
        self.persist(after)
        self.gl("save")


def run(p, cls="hwp_thief", section="prepare", **kwargs):
    c = Checks(p)
    c.cls = cls
    try:
        getattr(c, section)(cls, **kwargs)
    except Exception as exc:
        c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
