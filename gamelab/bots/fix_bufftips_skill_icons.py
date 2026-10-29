"""Issue #28: War Cry (and vanilla's other class skill buffs with no "hud" icon) on the buff bar.

A fresh Warrior on Bandit Keep floor 0 learns War Cry and casts it (`gl castat`, the
targeting helper's activate path). Then:
- `gl buffs`: the War Cry buff's def has a HUD icon and HUD.ShowBuffIcon gave it a shown widget;
- `gl buffbar`: the icon's shown name and description (as bufftips resolves them);
- hovering it (`gl mouse buff`) makes bufftips log `tip: War Cry`;
- with `bufftips.skill_icons` off, a new cast leaves the bar without it; on again, it is back;
- each of the other buffs in SkillBuffs.as (`gl givebuff`, its first level) gets a shown icon
  with a name and a description.
Shots: `warcry-bar`, `warcry-tip`, `skill-buffs-bar`."""
import re
import time

from gamelab.bots.plan_checks import Checks as Base

WARCRY_KEY = ".skills.warrior.spell_2.name"
# the first level of every other family in mods/bufftips/scripts/HWP/BuffTips/SkillBuffs.as
OTHERS = [
    "players/paladin/buffs_paladin.sval:fuel_the_flames_1",
    "players/paladin/buffs_paladin.sval:invigorating_1",
    "players/paladin/buffs_paladin.sval:cleansing_touch",
    "players/priest/buffs_priest.sval:holy_flames_1",
    "players/ranger/buffs_ranger.sval:entangle_heal_1",
    "players/ranger/buffs_ranger.sval:marked_pursuit_1",
    "players/rogue/buffs_rogue.sval:sidestep_opening_1",
    "players/sorcerer/buffs_sorcerer.sval:flamewalker_1",
    "players/sorcerer/buffs_sorcerer.sval:powersurge_1",
    "tweak/buffs/buffs_combo.sval:speed",
    "tweak/buffs/buffs_combo.sval:damage",
    "tweak/buffs/buffs_combo.sval:protection",
]


class Checks(Base):
    def bar_icon(self, key):
        for e in self.gl("buffbar").get("icons") or []:
            if e.get("shown") and e.get("key") == key:
                return e
        return None

    def warcry_buff(self):
        for b in self.gl("buffs").get("buffs") or []:
            if b.get("dur") == 8000 and b.get("left", 0) > 0 and b.get("name") in ("", WARCRY_KEY):
                return b
        return None

    def cast(self):
        r = self.gl("castat", "warcry", 1, 0, "nocd")
        time.sleep(0.6)
        return r

    def run(self):
        self.gl("char", "warrior", "LabWarcry")
        ok = self.wait_phase("town", 60)
        time.sleep(2)
        ok = self.start_floor(0) and ok
        self.hwp("god", 0.4)
        self.gl("kill", 6000, "tag:enemy")
        time.sleep(1)
        self.flag("warrior_run", ok, f"phase {self.gl('state').get('phase')}")
        self.gl("points", "skill", 5)
        lv = self.gl("skill", "warcry")
        self.flag("warcry_learned", lv.get("level", 0) >= 1, str(lv))

        # cast: the buff, its def's icon, the bar's widget, name and description
        c = self.cast()
        b = self.warcry_buff()
        self.flag("warcry_buff_on", b is not None, f"cast {c}; buff {b}")
        self.flag("warcry_has_icon", bool(b and b.get("hud") and b.get("icon")), str(b))
        ic = self.bar_icon(WARCRY_KEY)
        self.flag("warcry_on_bar", ic is not None and ic.get("max") == 8000
                  and ic.get("name") == "War Cry" and ic.get("desc") == "Faster weapon and movement speed.",
                  str(ic))
        self.g.shot("warcry-bar")

        # hover: bufftips' tooltip
        mark = len(self.g.read_log())
        r = self.gl("mouse", "buff", "warrior.spell_2")
        time.sleep(0.6)
        self.flag("warcry_tip", "[HWP:bufftips] tip: War Cry" in self.g.read_log()[mark:], str(r))
        self.g.shot("warcry-tip")
        self.gl("mouse", "off")

        # the setting: off takes the icon away from the next cast, on gives it back
        time.sleep(8.5)
        log = self.hwp("set bufftips.skill_icons 0", until="skill buff icons off")
        m = re.search(r"skill buff icons off: 0 of (\d+)", log)
        self.cast()
        b_off = self.warcry_buff()
        self.flag("setting_off", bool(m) and b_off is not None and not b_off.get("hud") and not b_off.get("icon")
                  and self.bar_icon(WARCRY_KEY) is None, f"log {m and m.group(0)}; buff {b_off}")
        time.sleep(8.5)
        log = self.hwp("set bufftips.skill_icons 1", until="skill buff icons on")
        m = re.search(r"skill buff icons on: (\d+) of (\d+) buff\(s\) given an icon, 0 with their own, 0 missing", log)
        self.cast()
        b_on = self.warcry_buff()
        self.flag("setting_on", bool(m) and m.group(1) == m.group(2) and b_on is not None and b_on.get("icon")
                  and self.bar_icon(WARCRY_KEY) is not None, f"log {m and m.group(0)}; buff {b_on}")

        # every other family
        missing = []
        for path in OTHERS:
            g = self.gl("givebuff", path, 20000)
            time.sleep(0.3)
            if not g.get("applied"):
                missing.append(f"{path}: not applied {g}")
        time.sleep(0.3)
        bar = self.gl("buffbar").get("icons") or []
        shown = [e for e in bar if e.get("shown")]
        named = [e for e in shown if e.get("name") and e.get("desc")]
        self.notes.append("bar: " + "; ".join(f"{e.get('name')} - {e.get('desc')}" for e in shown))
        self.flag("others_on_bar", not missing and len(named) >= len(OTHERS) + 1,
                  f"{len(named)} named icons shown of {len(OTHERS) + 1} wanted; {missing}")
        self.g.shot("skill-buffs-bar")


def run(p, **_):
    c = Checks(p)
    try:
        c.run()
    except Exception as e:
        c.flag("crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
