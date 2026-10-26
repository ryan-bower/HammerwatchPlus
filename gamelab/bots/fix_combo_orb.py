"""The combo orb (mods/groupcombo/scripts/HWP/GroupCombo/ComboOrb.as, scenario
fix-combo-orb), solo on the first bandit keep floor:

- `hwp comboorb` reports the default 10 per mille from 5 breakable loot tables.
- with `hwp set groupcombo.orb.permille 1000` every box, barrel, sack and vase drops
  one. A big vase spawned next to the player and broken (`hwp comboorb break`, the
  game's own Breakable.Damage) while combo is locked logs "none for us, combo is
  locked" and leaves no orb.
- after a combo skill (`gl skill combo_kills 1 combo`) the next vase leaves one
  items/hwp/combo_orb.unit at the vase; combo stays off until the player stands on
  it, then combo is on and the orb is gone.
- an orb dropped while combo is on (`gl combo` right before) stays on the floor when
  walked over (HWPComboOrb.CanApply), and is taken once combo has lapsed.
"""
import re
import time

from gamelab.bots.plan_checks import Checks as Base

VASE = "doodads/containers/vase_big.unit"
ORB = "combo_orb"


class Checks(Base):
    def orbs(self, radius=600):
        return self.gl("near", radius, ORB).get("units") or []

    def combo(self):
        return bool(self.gl("state").get("player", {}).get("combo"))

    def home(self):
        sx, sy = self.start
        self.gl("teleport", sx, sy)
        time.sleep(0.4)

    def break_vase(self, dx=50):
        """A big vase dx right of the start, broken; the log since the spawn."""
        self.home()
        mark = len(self.g.read_log())
        sp = self.gl("spawn", VASE, dx, 0)
        time.sleep(0.5)
        r = self.hwp("comboorb break 150", 1.0, until="broke ")
        time.sleep(0.6)
        return sp, r, self.g.read_log()[mark:]

    def step_on(self, orb):
        """Teleport onto the orb, then a short nudge so the sensor sees the player."""
        self.gl("teleport", orb["x"], orb["y"] + 12)
        time.sleep(0.3)
        self.gl("input", 400, 0, -1)
        time.sleep(0.6)

    def sec_orb(self):
        if not self.start_floor(0):
            self.flag("mission", False)
            return
        self.gl("cull")  # a measurement step: no bandit interrupts the vases
        st = self.hwp("comboorb", 0.6, until="Combo orb:")
        self.flag("status_default", "10 per mille" in st and "(5 loot tables)" in st, st.strip()[-200:])
        locked = "unlocked: no" in st
        self.notes.append(f"combo locked at start: {locked}")

        self.hwp("set groupcombo.orb.permille 1000", 0.6)
        if locked:
            sp, r, log = self.break_vase()
            self.flag("locked_no_orb", "none for us, combo is locked" in log and not self.orbs(),
                      f"spawn {sp.get('ok')}; {r.strip()[-120:]!r}; "
                      + repr(re.findall(r"\[HWP:groupcombo\][^\n]*", log)[-3:]))

        self.gl("points", "skill", 5)
        sk = self.gl("skill", "combo_kills", 1, "combo")
        st = self.hwp("comboorb", 0.6, until="Combo orb:")
        self.flag("unlocked", "unlocked: yes" in st, f"skill {sk}; {st.strip()[-120:]}")

        sp, r, log = self.break_vase()
        orbs = self.orbs()
        before = self.combo()
        self.flag("orb_dropped", "combo orb at " in log and len(orbs) == 1 and not before,
                  f"spawn {sp.get('ok')}; {r.strip()[-120:]!r}; orbs {orbs}; combo {before}; "
                  + repr(re.findall(r"\[HWP:groupcombo\][^\n]*", log)[-3:]))
        if not orbs:
            return

        mark = len(self.g.read_log())
        self.step_on(orbs[0])
        on = self.combo()
        log = self.g.read_log()[mark:]
        left = self.orbs()
        self.flag("picked_combo", on and not left and "combo orb picked up: combo on" in log,
                  f"combo {on}; orbs left {left}; " + repr(re.findall(r"\[HWP:groupcombo\][^\n]*", log)[-3:]))

        # in combo: a second orb waits on the floor. combo_kills sustains combo for
        # 3.5 s without kills, so `gl combo` (Player.GiveCombo) enters it again right
        # before the step
        self.home()
        self.hwp("comboorb drop", 0.8, until="combo orb dropped")
        time.sleep(0.4)
        orbs = self.orbs()
        self.gl("combo")
        if orbs and self.combo():
            self.step_on(orbs[0])
            self.flag("in_combo_orb_stays", self.combo() and len(self.orbs()) == 1, f"orbs {self.orbs()}")
        else:
            self.flag("in_combo_orb_stays", False, f"orbs {orbs}, combo {self.combo()}")

        # combo lapses without kills (ComboSustainResetTime), then the orb is taken
        lapsed = False
        for _ in range(40):
            if not self.combo():
                lapsed = True
                break
            time.sleep(0.5)
        orbs = self.orbs()
        if lapsed and orbs:
            self.home()
            mark = len(self.g.read_log())
            self.step_on(orbs[0])
            log = self.g.read_log()[mark:]
            self.flag("taken_after_lapse", self.combo() and not self.orbs() and "combo orb picked up" in log,
                      f"orbs {self.orbs()}")
        else:
            self.flag("taken_after_lapse", False, f"lapsed {lapsed}, orbs {orbs}")

        self.hwp("set groupcombo.orb.permille 10", 0.6)


SECTIONS = ["orb"]


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
