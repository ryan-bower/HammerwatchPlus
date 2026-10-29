"""Issue #16: a Ranger with a pistol in the main hand and a hand crossbow in the off hand.

The pistol never fired for anyone but a Firearms Specialist. A gun shoots only while its clip
stack holds rounds, and the clip was filled (on spawn) and reloaded (on an empty trigger, the
magazine's bookkeeping) only for that class (`IsFirearms`). Now those go with the gun
(`UsesGuns`: the class, or a gun in either hand). The hand crossbow fired already.

Checks, on the town-ranger fixture:
- in town the clip fills to the gun's size, and `hwp firearms` says the gun is held by a ranger;
- on floor 1 the clip is full, the pistol (left click) hurts a breakable target dummy and
  spends rounds, the hand crossbow (right click) hurts it and spends none;
- an emptied clip (`hwp firearms empty`) reloads on the next trigger pull;
- a Ranger without a gun has no clip and no fill attempt in the log.
"""
import re
import time

from gamelab.bots.plan_firearms import Checks as Base

# A target that stands still and doesn't block: a bandit brute blocks a front hit 1 in 4 for 30
# physical, more than a pistol round does (24), and a bandit hunter walks out of the line.
TARGET = "doodads/generic/target_dummy_breakable.unit"
FOE = "target_dummy_breakable"

PISTOL = "hwp_glock_mh_01"
CROSSBOW = "offhand_crossbow_01"
AIM_HEIGHT = 11  # Combat.as HWP::Firearms::AIM_HEIGHT


class Checks(Base):
    def gun_line(self):
        out = self.hwp("firearms", 0.6, until="guns:")
        m = re.findall(r"guns: ([^\n\[]*)", out)
        return m[-1].strip() if m else "?"

    def fire(self, hand, ms=800):
        """Hold one hand's attack at a breakable target dummy 70 px out along open floor. A gun
        shoots at the cursor from the height its round is drawn at (Combat.as AimAtCursor,
        AIM_HEIGHT), so the round's collision line passes AIM_HEIGHT px below the cursor: the
        cursor goes on the target's body, where a player aims, not on its feet. On the feet a
        sideways shot passes under it (RE_NOTES 2026-10-29). (hp before, after, clip before, after)."""
        self.gl("kill", 600, FOE)
        time.sleep(0.3)
        if not hasattr(self, "aim"):
            self.aim = self.open_dirs(130)[0]
        ux, uy = self.aim
        self.gl("spawn", TARGET, round(ux * 70, 1), round(uy * 70, 1))
        time.sleep(0.3)

        def foe():
            us = self.gl("near", 300, FOE).get("units") or []
            return us[0] if us else {}

        b0, c0 = foe(), self.stacks("clip")
        cur = self.gl("cursor", round(ux * 70, 1), round(uy * 70 - AIM_HEIGHT, 1))
        self.gl("input", ms, 0, 0, ux, uy, hand)
        time.sleep(ms / 1000 + 0.4)
        b1 = foe()
        if hand == "main":
            aim = re.findall(r"aim: [^\n\[]*", self.hwp("firearms aim", 0.6, until="aim:"))
            self.notes.append(f"pistol shot: dummy {b0} -> {b1}; cursor {cur}; {aim[-1] if aim else 'no aim'}")
        hp = lambda u: round(u["hp"], 3) if "hp" in u else None
        out = hp(b0), hp(b1), c0, self.stacks("clip")
        self.gl("kill", 600, FOE)
        return out

    def ranger(self):
        pl = self.gl("state").get("player", {})
        mark = len(self.g.read_log())
        time.sleep(1.0)
        bare = self.stacks("clip")
        self.flag("no_gun_no_clip", pl.get("class") == "ranger" and bare <= 0 and self.gun_line() == "none",
                  f"class {pl.get('class')}, clip {bare}")

        self.gl("equip", PISTOL, "common")
        self.gl("equip", CROSSBOW, "common")
        time.sleep(2.0)
        town_clip = self.stacks("clip")
        line = self.gun_line()
        self.flag("town_clip_filled", town_clip > 0 and line == "held by a ranger", f"clip {town_clip}; guns: {line}")

        if not self.enter_floor("ranger"):
            return
        time.sleep(1.0)
        floor_clip = self.stacks("clip")
        self.flag("floor_clip_full", floor_clip == town_clip, f"town {town_clip}, floor 1 {floor_clip}")

        h0, h1, c0, c1 = self.fire("main")
        self.flag("pistol_fires", h0 is not None and h1 is not None and h1 < h0 and c1 < c0,
                  f"dummy hp {h0} -> {h1}, clip {c0} -> {c1}")
        time.sleep(2.0)
        h0, h1, c0, c1 = self.fire("off")
        self.flag("crossbow_fires", h0 is not None and h1 is not None and h1 < h0 and c1 == c0,
                  f"dummy hp {h0} -> {h1}, clip {c0} -> {c1}")

        self.hwp("firearms empty", 0.6)
        empty = self.stacks("clip")
        self.gl("input", 200, 0, 0, 1, 0, "main")
        time.sleep(2.6)  # the Reloading stack: 1.6 s
        refilled = self.stacks("clip")
        log = self.g.read_log()[mark:]
        self.flag("empty_trigger_reloads", empty == 0 and refilled == town_clip
                  and "trigger on an empty clip: reloading" in log,
                  f"clip after empty {empty}, 2.6 s after a trigger pull {refilled}")
        self.flag("no_fill_timeout", "no gun gave the clip a size" not in log, "")


def run(p, **_):
    c = Checks(p)
    try:
        c.ranger()
    except Exception as e:
        c.flag("crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    c.out["ok"] = all(v for k, v in c.out.items() if isinstance(v, bool))
    return c.out
