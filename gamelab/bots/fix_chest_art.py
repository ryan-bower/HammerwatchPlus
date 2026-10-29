"""Alt-art chests and the red skull ace key (mods/keys ChestArt.as, tweak/hwp/chest_art.sval,
scenario fix-chest-art):

- the area is the mission's act: `hwp chestart` reports area 1 on the first bandit keep
  floor, area 5 on Dark Citadel's first crypt floor (index 7: forest, dark caves, forest,
  temple, crypt) and area 9 on its first dark halls floor (index 19).
- with `hwp chestart area <n>` (keys.debug) chests spawned next to the player switch to the
  picked scene on their first tick, logged as `chest art <unit>: <scene> (area n)`: the
  trinket chests plain in areas 1-3, their own art in 4-5, strapped from 6; the cursed
  chest steel rimmed in 1-4, steel large from 5; area 9 takes area 8's art.
- at keys.ace_chance 1 a gold trinket chest shows the gold rimmed chest (areas 1-5) or the
  red and gold large one (6-8), and a gold equipment chest the map reward chest.
- the ace key on the floor (`hwp keydrop ace`) and in the HUD (`hwp keygive ace 1`) is the
  skull key tinted red; screenshots of each.
"""
import re
import time

from gamelab.bots.plan_checks import Checks as Base

CHESTS = "items/chests/chest_"
KINDS = ["bronze_trinket", "silver_trinket", "gold_trinket", "cursed"]
EXPECT = {
    1: ["u_bronze_plain", "u_silver_plain", "u_gold_plain", "u_steel_rimmed"],
    4: ["vanilla", "vanilla", "vanilla", "u_steel_rimmed"],
    6: ["u_bronze_strapped", "u_silver_strapped", "u_gold_strapped", "u_steel_large"],
    9: ["u_bronze_strapped", "u_silver_strapped", "u_gold_strapped", "u_steel_large"],
}
ACE = {3: ("u_gold_rimmed", "map_reward"), 7: ("u_gold_large", "map_reward")}


def art_lines(log):
    return re.findall(r"chest art (items/chests/chest_\w+)\.unit( \(ace\))?: (\w+) \(area (\d+)\)", log)


class Checks(Base):
    def area_reply(self):
        r = self.hwp("chestart", 0.6, until="chest art: area")
        return (re.findall(r"chest art: area[^\n]*", r) or [""])[-1]

    def go(self, mission, floor):
        r = self.gl("mission", mission, floor)
        ok = bool(r.get("ok")) and self.wait_phase("mission")
        time.sleep(3)
        pl = self.gl("state").get("player", {})
        self.start = (pl.get("x", 0.0), pl.get("y", 0.0))
        return ok

    def spawn_row(self, units, dy):
        """units in a row dy below the player; the art lines they logged"""
        mark = len(self.g.read_log())
        for i, u in enumerate(units):
            self.gl("spawn", u, -75 + 50 * i, dy)
        time.sleep(1.2)
        return art_lines(self.g.read_log()[mark:])

    def sec_area(self):
        if not self.go("bandit_keep", 0):
            self.flag("mission", False)
            return
        self.gl("cull")
        line = self.area_reply()
        self.flag("area_keep_floor0", "chest art: area 1;" in line and "mission level 0" in line, line)

    def sec_override(self):
        self.hwp("set keys.debug 1", 0.5)
        self.hwp("set keys.ace_chance 0", 0.5)
        sx, sy = self.start
        self.gl("teleport", sx, sy)
        time.sleep(0.4)
        got = {}
        for row, area in enumerate(EXPECT):
            self.hwp(f"chestart area {area}", 0.5, until="chest art: area")
            lines = self.spawn_row([CHESTS + k + ".unit" for k in KINDS], -70 + 45 * row)
            got[area] = [next((s for u, a, s, n in lines if u == CHESTS + k and not a and n == str(area)), None) for k in KINDS]
        self.g.shot("chest art rows areas 1 4 6 9 - bronze silver gold cursed")
        for area, want in EXPECT.items():
            self.flag(f"art_area{area}", got[area] == want, f"{got[area]}")
        self.gl("cull")

    def sec_ace(self):
        self.hwp("set keys.ace_chance 1", 0.5)
        sx, sy = self.start
        self.gl("teleport", sx + 400, sy)
        time.sleep(0.6)
        pl = self.gl("state").get("player", {})
        self.start = (pl.get("x", 0.0), pl.get("y", 0.0))
        for row, (area, want) in enumerate(ACE.items()):
            self.hwp(f"chestart area {area}", 0.5, until="chest art: area")
            lines = self.spawn_row([CHESTS + "gold_trinket.unit", CHESTS + "gold_equipment.unit"], -40 + 50 * row)
            got = (next((s for u, a, s, n in lines if u == CHESTS + "gold_trinket" and a), None),
                   next((s for u, a, s, n in lines if u == CHESTS + "gold_equipment" and a), None))
            self.flag(f"ace_area{area}", got == want, f"{got}; {lines}")
        self.g.shot("ace chests area 3 top area 7 bottom - trinket left equipment right")
        self.hwp("set keys.ace_chance 0.15", 0.5)
        self.hwp("chestart area off", 0.5, until="chest art: area")

    def sec_acekey(self):
        mark = len(self.g.read_log())
        self.hwp("keydrop ace", 0.8)
        self.hwp("keygive ace 1", 0.8)
        time.sleep(0.8)
        near = self.gl("near", 200, "key_ace").get("units") or []
        self.flag("ace_key_dropped", len(near) >= 1, f"{near}")
        self.g.shot("red skull ace key on the floor and in the HUD")
        log = self.g.read_log()[mark:]
        bad = [l for l in log.splitlines() if "key_ace" in l and any(w in l.lower() for w in ("error", "fail", "not found", "missing"))]
        self.flag("ace_key_no_errors", not bad, f"{bad[:3]}")

    def sec_citadel(self):
        if not self.go("dark_citadel", 7):
            self.flag("citadel_crypt", False, "mission did not start")
            return
        line = self.area_reply()
        self.flag("citadel_crypt", "chest art: area 5;" in line and "crypt_1" in line and ".location.act.crypt" in line, line)
        if not self.go("dark_citadel", 19):
            self.flag("citadel_dark_halls", False, "mission did not start")
            return
        line = self.area_reply()
        self.flag("citadel_dark_halls", "chest art: area 9;" in line and "dark_halls_1" in line, line)
        lines = art_lines(self.g.read_log())
        self.notes.append(f"floor chests with art on dark halls: {[l for l in lines if l[3] == '9'][:6]}")


SECTIONS = ["area", "override", "ace", "acekey", "citadel"]


def run(p, sections="all"):
    c = Checks(p)
    names = SECTIONS if sections == "all" else [s for s in sections.split(",") if s]
    for name in names:
        try:
            getattr(c, "sec_" + name)()
        except Exception as exc:  # a crashed section is a failed section, not a crashed run
            c.flag(name + "_crashed", False, repr(exc))
    c.out["ok"] = bool(c.out) and all(v for v in c.out.values() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
