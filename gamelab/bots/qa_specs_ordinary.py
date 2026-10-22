from gamelab.bots.qa_firearms_input_sequence import Checks as SequenceChecks
"""Legal level20 built fourth-spec fixture, then ordinary HoH2 Bandit Keep completion.

Only prepare mutates build stats/gear. The run uses normal Pilot walking/combat,
native potion reflexes, a real boss, its reward window, and its unlocked portal.
No teleport, direct kill, cull, god, timescale, or HP/mana setters in run.
"""
import json
import time
from collections import Counter
from dataclasses import asdict

from gamelab.bots import floor_runner
from gamelab.bots.qa_class_integration import Checks as IntegrationChecks
from gamelab.bots.qa_class_drive import ClassPilot
from gamelab.hps import hash_string


CLASSES = {'hwp_ranger_stormbringer': {'name': 'QADeadeyeRun', 'kite': 90, 'melee': False, 'extra': ['hwp_ran_electric_circuit', 'hwp_ran_gathering_winds']}, 'hwp_wizard_invocation': {'name': 'QAInvocationRun', 'kite': 90, 'melee': False, 'extra': ['hwp_wiz_tempest_torrent', 'hwp_wiz_static_charge']}, 'hwp_sorcerer_arcane': {'name': 'QAArcaneRun', 'kite': 90, 'melee': False, 'extra': ['hwp_sor_blink', 'hwp_sor_living_mana']}, 'hwp_rogue_winddancer': {'name': 'QAWinddancerRun', 'kite': 24, 'melee': True, 'extra': ['hwp_rog_protective_gale', 'hwp_rog_second_wind']}, 'hwp_warrior_bannerlord': {'name': 'QABannerlordRun', 'kite': 24, 'melee': True, 'extra': ['hwp_war_battlefield_standard', 'hwp_war_righteous_crusade']}, 'hwp_warlock_branding': {'name': 'QABrandingRun', 'kite': 24, 'melee': True, 'extra': ['hwp_wlk_pyrebrand', 'hwp_wlk_essence_extraction']}}
GEAR = {'hwp_ranger_stormbringer': ('dex', 'twohanded_shortbow_01', 'twohanded_shortbow_01'), 'hwp_wizard_invocation': ('int', 'mainhand_wand_fire_01', 'mainhand_wand_fire_01'), 'hwp_sorcerer_arcane': ('int', 'twohanded_staff_lightning_01', 'twohanded_staff_lightning_01'), 'hwp_rogue_winddancer': ('dex', 'twohanded_daggers_01', 'twohanded_daggers_01'), 'hwp_warrior_bannerlord': ('str', 'twohanded_greataxe_01', 'twohanded_greataxe_01'), 'hwp_warlock_branding': ('int', 'mainhand_dirk_01', 'mainhand_dirk_01')}
BOSS_FLAG = hash_string("boss_bandit")


def has_item(items, name, ilvl=None):
    return any(isinstance(x, list) and len(x) >= 4
               and int(x[1]) & 0xFFFFFFFF == hash_string(name)
               and (ilvl is None or x[3] == ilvl) for x in items or [])


def native_skill_budget(player):
    return (type(player.get("skillFree")) is int and player["skillFree"] >= 0
            and type(player.get("bonusSkillPoints")) is int and player["bonusSkillPoints"] == 0)


class Checks(IntegrationChecks):
    def new_char(self, cls, name):
        # Own creation rather than inherited plan_classesa's controlled-ability
        # skillpoint grant. These classes author both fourth-spec skills at1.
        made = self.gl("char", cls, name)
        town = self.wait_phase("town", 60)
        time.sleep(2)
        state = self.gl("state")
        valid = (made.get("ok") and town and state.get("player", {}).get("class") == cls
                 and state.get("player", {}).get("name") == name
                 and native_skill_budget(state.get("player", {})))
        self.flag(cls + "_char", bool(valid), str({"create": made, "state": state}))
        return bool(valid)

    def expected_skills(self, cls):
        return CLASSES[cls]["extra"]

    def at_1x(self):
        value = self.gl("cvars", "g_timescale").get("cvars", {}).get("g_timescale")
        return isinstance(value, (int, float)) and abs(value - 1.0) < 0.0001

    def record(self):
        primary = GEAR[self.cls][0]
        flags = self.gl("inspect", "player", "flags").get("value") or []
        return {"state": self.gl("state"),
                "equipped": self.gl("inspect", "player", "equipped").get("value"),
                "equipment": self.gl("inspect", "player", "equipment").get("value"),
                "primary": self.gl("inspect", "player", "picked-" + primary).get("value"),
                "ranks": {sid: self.gl("skilltip", sid).get("level") for sid in self.expected_skills(self.cls)},
                "boss_flag": any(int(f) & 0xFFFFFFFF == BOSS_FLAG for f in flags),
                "stats": self.gl("benchstats"), "materials": self.gl("inv").get("materials", {})}

    @property
    def prepared_path(self):
        return self.g.results / "qa-specs-ordinary-prepared.json"

    def persist(self, snapshot):
        self.prepared_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    def prepare(self, cls):
        self.cls = cls
        if not self.new_char(cls, CLASSES[cls]["name"]):
            return
        attr, starter, weapon = GEAR[cls]
        # Player.ChangeClass was invoked on the actual requested class; verify
        # native requirements at both town setup and ordinary mission entry.
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        requirement = self.gl("cvars", "dbg_cht_ignore_equipment_requirements")
        self.flag("native_requirements_enabled", requirement.get("cvars", {}).get("dbg_cht_ignore_equipment_requirements") == 0,
                  str(requirement))
        fresh = self.gl("inspect", "player", "equipped").get("value") or []
        self.flag("fresh_starting_weapon", has_item(fresh, starter), str(fresh))
        self.gl("xp", 1301032)
        # Both authored fourth-spec skills start at rank1. Do not manufacture
        # skill points or learn missing skills: a missing starting rank is a defect.
        assigned = self.gl("assign", attr, "all")
        weapon_reply = self.gl("equip", weapon, "common", 20)
        armor = self.gl("kit", 20, "rare", "head,chest,hands,feet", "seed=20261022")
        potion = self.gl("upgrade", "apothecary", "potion-charges", 4)
        snapshot = self.record()
        self.flag("prepared_level20", snapshot["state"].get("player", {}).get("level") == 20, str(snapshot["state"]))
        self.flag("native_skill_budget", native_skill_budget(snapshot["state"].get("player", {})),
                  str(snapshot["state"].get("player", {})))
        back = {"slot": 6, "expected": None, "equipped": (snapshot["equipped"] or [])[6] if len(snapshot["equipped"] or []) == 7 else "invalid equipped readback",
                "scope": "Explicitly empty back; four legal matched20 rare armor pieces, common20 class weapon"}
        self.out["setup"] = {"fresh_equipped": fresh, "assign": assigned, "weapon": weapon_reply,
                             "armor": armor, "back": back, "potion": potion, "snapshot": snapshot}
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
                  "primary57", "potion5", "fresh_boss_flag_absent", "verified", "native_requirements_enabled", "prepared_level20", "native_skill_budget")))
        snapshot["setup_valid"] = bool(self.out.get("prepared"))
        self.persist(snapshot)
        self.gl("save")

    def verify(self, cls):
        self.cls = cls
        expected = json.loads(self.prepared_path.read_text(encoding="utf-8"))
        now = self.record()
        player = now["state"].get("player", {})
        expected_level = expected["state"].get("player", {}).get("level")
        self.flag("class_record", isinstance(expected_level, int) and expected_level >= 20 and player.get("class") == cls and player.get("name") == CLASSES[cls]["name"]
                  and player.get("level") == expected_level and not player.get("dead"), str({"actual": player, "exact_expected_level": expected_level}))
        expected_player = expected["state"].get("player", {})
        self.flag("skill_budget_persisted", native_skill_budget(player) and native_skill_budget(expected_player)
                  and player["skillFree"] == expected_player["skillFree"],
                  str({"actual": player, "expected": expected_player}))
        self.flag("spec_ranks", bool(now["ranks"]) and now["ranks"] == expected["ranks"]
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
        self.flag("verified", all(self.out.get(k) for k in ("class_record", "spec_ranks", "gear_persisted", "bag_persisted", "reward_persisted",
                  "primary_persisted", "boss_flag_persisted", "god_off", "skill_budget_persisted")))
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
        # Native scene globals reset on floor load. Explicitly set the normal
        # requirements policy here and read it; this grants no stats/gear.
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        req = self.gl("cvars", "dbg_cht_ignore_equipment_requirements")
        self.flag("ordinary_native_requirements", req.get("cvars", {}).get("dbg_cht_ignore_equipment_requirements") == 0,
                  str(req))
        if not self.out["ordinary_native_requirements"]:
            return
        floors = []
        self.out["floors"] = floors
        driver = ClassPilot(self.p, cls)
        # Native starting/main equipment attack geometry, not a spoofed class ID.
        driver.melee = CLASSES[cls]["melee"]
        self.out["ordinary_driver"] = driver.description()
        self.out["ordinary_active_cast_scope"] = "Primary-input compatibility only; each fourth-spec active's ordinary use remains UNTESTED."
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



    def death(self, cls):
        """Controlled native lethal damage and DeadMenu, separate from ordinary combat."""
        if not self.god_off():
            self.flag("death_god_off", False)
            return
        self.gl("mission", "bandit_keep", 0)
        if not self.wait_phase("mission", 90):
            self.flag("death_entered", False)
            return
        time.sleep(2)
        pl = self.gl("state").get("player", {})
        pools = [pl.get("hpMax"), pl.get("manaMax")]
        valid = all(isinstance(v, (int,float)) and v > 0 for v in pools)
        self.flag("death_valid_native_pools", valid, str(pl))
        if not valid:
            return
        hit = self.gl("damageme", int(max(pools)*3)+1)
        time.sleep(.5)
        dead = self.gl("state")
        self.flag("death_damage_path", hit.get("dead") and dead.get("player", {}).get("dead"), str(hit))
        if dead.get("player", {}).get("dead"):
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


def run(p, cls="hwp_ranger_stormbringer", section="prepare", **kwargs):
    c = Checks(p)
    c.cls = cls
    try:
        getattr(c, section)(cls, **kwargs)
    except Exception as exc:
        c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
