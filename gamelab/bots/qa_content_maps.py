"""Native generation of every floor in the three added equipment-map missions.

Direct native mission selection isolates layout generation. God mode protects
the observer; no enemies are culled. This does not claim natural map drops,
unlock eligibility, exit traversal, ordinary completion, or boss defeat.
"""
import time

from gamelab.bots.plan_classesa import Checks as Base


MISSIONS = {
    "hwp_goblin_warrens": (["forest_1", "cave_dark_1", "cave_dark_2", "cave_dark_boss"], "levels/boss_totem_cave.lvl"),
    "hwp_sunken_dungeon": (["dungeon_1", "dungeon_2", "crypt_1", "dungeon_boss"], "levels/boss_arista.lvl"),
    "hwp_high_court": (["barracks_1", "courts_1", "courts_2", "courts_boss"], "levels/boss_bone_serpent.lvl"),
}


class Checks(Base):
    def __init__(self, p):
        super().__init__(p)
        self.rows = []

    def check(self, case, ok, **data):
        self.flag(case, ok, str(data))
        self.rows.append(dict(case=case, runtime="PASS" if ok else "FAIL", **data))

    def mission(self, mission):
        floors, boss_file = MISSIONS[mission]
        if not self.new_char("paladin", "QAMapLayouts"):
            return
        for index, floor in enumerate(floors):
            if index and not self.to_town():
                self.check(floor + "_town_boundary", False)
                return
            request = self.gl("mission", mission, index, 0)
            boot = self.g.wait_gl(lambda o: o.get("ev") == "boot" and not o.get("_preload"),
                                  90, fresh=True) if request.get("ok") else None
            entered = bool(boot) and self.wait_phase("mission", 90)
            self.check(floor + "_native_load", entered and request.get("mission") == mission
                       and request.get("floor") == index and request.get("ngp") == 0,
                       request=request, boot=boot)
            if not entered:
                return
            self.god_on()
            time.sleep(2)
            state, scan = self.gl("state"), self.gl("scan", 12000)
            expected_level = boss_file if index == 3 else "levels/generated.lvl"
            actual_level = str(state.get("level", "")).replace("\\", "/")
            self.check(floor + "_actual_identity", scan.get("place") == mission + "/" + floor
                       and actual_level.endswith(expected_level) and state.get("phase") == "mission"
                       and not state.get("player", {}).get("dead"),
                       expected_place=mission + "/" + floor, expected_level=expected_level,
                       state=state, scan=scan)
            if index < 3:
                hostiles = [enemy for enemy in scan.get("enemies", []) if enemy.get("hp", 0) > 0]
                exits = [exit for exit in scan.get("exits", []) if exit.get("enabled")]
                self.check(floor + "_generated_enemies_and_exit", scan.get("ok") and bool(hostiles) and bool(exits),
                           live_hostiles=hostiles, native_exits=scan.get("exits", []),
                           sources=scan.get("sources"),
                           limits="Presence only; reachability and natural exit traversal are not measured.")
            else:
                self.check(floor + "_native_boss_scene", actual_level.endswith(boss_file)
                           and scan.get("rawCount", 0) > 0,
                           level=actual_level, raw_count=scan.get("rawCount"),
                           limits="Pinned boss scene loads; native intro, spawned boss attacks and defeat remain unverified.")
        self.to_town()


def run(p, mission="hwp_goblin_warrens", **_):
    c = Checks(p)
    try:
        c.mission(mission)
    except Exception as exc:
        c.check("content_map_crashed", False, mission=mission, error=repr(exc))
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
