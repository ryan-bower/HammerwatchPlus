"""Engineer orb effects measured by natural placement, native HP and damage.

No turret HP, cap, fire chance or damage setter is used. The long Feed trials have
fixed durations and all samples are retained; failed samples are not retried.
"""
import math
import re
import time

from gamelab.bots.qa_firearms_passives import Checks as Base


TURRET = "hwp/firearms/units/turret"
RESIST_TOUGH = "gamelab/qa_firearms_target_dummy_resist_tough.unit"


class Checks(Base):
    def native_snapshot(self, filt):
        rows = self.g.gl_multi([["clock"], ["near", 500, filt]])
        return rows[0].get("sceneMs", -1), [u for u in rows[1].get("units", []) if not u.get("dead")]

    def turrets(self):
        return [u for u in self.gl("near", 500, TURRET).get("units", []) if not u.get("dead")]

    def place(self, d, dist, angle=0):
        self.ready("hwp_fs_turret", 25)
        self.top_up()
        a = math.atan2(d[1], d[0]) + math.radians(angle)
        mark = self.log_pos()
        target = self.targeted(self.entry(self.bar(), "hwp_fs_turret").get("button"),
                               math.cos(a) * dist, math.sin(a) * dist, (0, 120))
        time.sleep(0.9)
        return {"target": target, "turrets": self.turrets(), "log": self.log_from(mark),
                "cooldown": self.entry(self.bar(), "hwp_fs_turret").get("cd", 0)}

    def engineer(self):
        if not self.prepare("QAEngineerOrbs", "hwp_firearms_engineer"):
            return
        ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        self.check("engineer_common_pistol_fixture", ok, gear)
        d = self.open_dirs(150)[0]
        self.gl("kill", 800, TURRET)
        first = self.place(d, 45, -30)
        second = self.place(d, 45, 30)
        first_ids = {u["unit"] for u in first["turrets"]}
        second_ids = {u["unit"] for u in second["turrets"]}
        self.check("second_turret_without_orb_cap_one", len(first_ids) == len(second_ids) == 1
                   and first_ids.isdisjoint(second_ids)
                   and all(self.turret_distance(u) <= 60 for u in first["turrets"] + second["turrets"]),
                   {"first_natural_placement": first, "second_natural_placement": second,
                    "note": "My Turret repairs each nearby old turret; natural decay cannot explain its replacement."})
        orb_ok, rank = self.orb("hwp_fs_turret_second", 1)
        third = self.place(d, 45, -30)
        fourth = self.place(d, 55)
        third_ids = {u["unit"] for u in third["turrets"]}
        fourth_ids = {u["unit"] for u in fourth["turrets"]}
        self.check("second_turret_cap_two_replaces_oldest", orb_ok and rank == 1
                   and len(third_ids) == len(fourth_ids) == 2 and second_ids <= third_ids
                   and second_ids.isdisjoint(fourth_ids) and len(third_ids & fourth_ids) == 1
                   and all(self.turret_distance(u) <= 60 for u in third["turrets"] + fourth["turrets"]),
                   {"orb": "hwp_fs_turret_second", "rank": rank, "before_orb": second,
                    "first_orb_placement": third, "over_cap_placement": fourth})
        self.orb_off("hwp_fs_turret_second")
        for rank, share in enumerate((0.25, 0.5, 0.75), 1):
            self.gl("kill", 800, TURRET)
            orb_ok, got = self.orb("hwp_fs_turret_reinforced", 1)
            owner = self.gl("state").get("player", {})
            placed = self.place(d, 90)
            scene0, units0 = self.native_snapshot(TURRET)
            before = units0[0] if len(units0) == 1 else {}
            started = time.monotonic()
            time.sleep(2)
            scene1, units1 = self.native_snapshot(TURRET)
            after = units1[0] if len(units1) == 1 else {}
            wall_elapsed = time.monotonic() - started
            elapsed = (scene1 - scene0) / 1000
            expected_hp = 100 + int(share * owner.get("hpMax", 0))
            decay = before.get("hp", 0) - after.get("hp", 0)
            self.check(f"reinforced_turret_rank_{rank}_native_hp_and_decay", orb_ok and got == rank
                       and len(placed["turrets"]) == 1 and self.turret_distance(before) > 60
                       and before.get("hpMax") == expected_hp and after.get("hpMax") == expected_hp
                       and scene0 >= 0 and elapsed > 0 and after.get("hpExact", 0) > 0
                       and abs(decay - elapsed / 30) < 0.02,
                       {"orb": "hwp_fs_turret_reinforced", "rank": rank, "owner_hp_max": owner.get("hpMax"),
                        "owner_hp_share": share, "expected_native_max_hp": expected_hp,
                        "natural_placement": placed, "native_before": before, "native_after": after,
                        "native_scene_ms": [scene0, scene1], "native_elapsed": elapsed,
                        "wall_elapsed_diagnostic": wall_elapsed,
                        "observed_fraction_decay": decay, "expected_decay": elapsed / 30})
        self.gl("kill", 800, TURRET)
        self.to_town()

    def feed_sample(self, d, chance):
        self.gl("kill", 800, TURRET)
        self.clear_dummies()
        placed = self.place(d, 40)
        turret = self.turret_one()
        dd, dummy = self.tough(d, 120, RESIST_TOUGH)
        readback = next((u for u in self.gl("near", 500, "target_dummy").get("units", [])
                         if u.get("unit") == dummy), {})
        time.sleep(0.8)
        scene0, units = self.native_snapshot("target_dummy")
        initial = next((u for u in units if u.get("unit") == dummy), {})
        hp0 = initial.get("hpExact", 0) / max(1, initial.get("hpMax", 0))
        started = time.monotonic()
        samples = []
        for tick in range(12):
            time.sleep(5)
            scene, units = self.native_snapshot("target_dummy")
            target = next((u for u in units if u.get("unit") == dummy), {})
            samples.append({"tick": tick + 1, "wall_elapsed": time.monotonic() - started,
                            "scene_ms": scene, "native_elapsed": (scene - scene0) / 1000,
                            "hp": target.get("hpExact", 0) / max(1, target.get("hpMax", 0)),
                            "turret": self.turret_one()})
        wall_elapsed = time.monotonic() - started
        elapsed = (samples[-1]["scene_ms"] - scene0) / 1000
        hp1 = samples[-1]["hp"]
        damage = (hp0 - hp1) * readback.get("hpMax", 0)
        live = self.probe("hwp_fs_turret", 1)
        return {"chance": chance, "placement": placed, "turret_distance": self.turret_distance(turret),
                "fixture_native_readback": readback, "hp": [hp0, hp1], "fixed_samples": samples,
                "damage": damage, "elapsed": elapsed, "dps": damage / max(0.001, elapsed),
                "native_scene_ms": [scene0, samples[-1]["scene_ms"]], "wall_elapsed_diagnostic": wall_elapsed,
                "custom_feed": self.custom(live, "hwp-turret-feed"),
                "valid": (scene0 >= 0 and elapsed >= 45 and readback.get("hpMax") == 10000000
                          and initial.get("hpMax") == 10000000 and damage > 0 and hp1 > 0
                          and self.turret_distance(turret) <= 60
                          and all(x["turret"].get("unit") == turret.get("unit") for x in samples))}

    def feed(self):
        if not self.prepare("QAFeedRanks", "hwp_firearms_engineer"):
            return
        ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        rank = self.learn_rank("hwp_fs_turret", 5)
        self.check("belt_feed_damage_fixture", ok and rank == 5, {"gear": gear, "turret_rank": rank})
        d = self.open_dirs(170)[0]
        control = self.feed_sample(d, 0)
        self.check("belt_feed_plain_control", control["valid"] and control["custom_feed"] == 0, control)
        for rank, chance in enumerate((0.2, 0.4, 0.6), 1):
            ok, got = self.orb("hwp_fs_myturret_feed", 1)
            live = self.feed_sample(d, chance)
            ratio = live["dps"] / max(0.001, control["dps"])
            expected = 1 - chance + chance / 6
            self.check(f"elemental_belt_feed_rank_{rank}_real_damage", ok and got == rank and live["valid"]
                       and abs(live["custom_feed"] - chance) < 0.002 and abs(ratio - expected) < 0.11,
                       {"orb": "hwp_fs_myturret_feed", "rank": rank, "chance": chance,
                        "expected_dps_ratio_at1000_all_element_resistance": expected,
                        "actual_dps_ratio": ratio, "control": control, "natural_turret_trial": live,
                        "note": "Fixed60s trials include native crit/element RNG and integer damage rounding; tolerance0.11 remains below the smallest expected effect0.167. No retries."})
        self.gl("kill", 800, TURRET)
        self.clear_dummies()
        self.to_town()


def run(p, section="engineer", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("engineer_orbs_crashed", False, {"section": section, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
