"""Issue #73: catch-up experience. In a New Game+ run a player below the previous NG+'s level
cap (20 at NG+1, 25 at NG+2) has the Late Bloomer buff and gets +50% experience.

Sections:
- town: a fresh level 1 paladin in town has no bonus ("in town").
- run: Bandit Keep floor 0 started at NG+1 (g_ngp 1): the buff is on (gl state, the log), and
  `hwp xp 40` (PlayerRecord.GiveExperience with gain modifiers) gives 60.
- off: `hwp catchup ngp 0` checks against NG+0: the buff ends and the same 40 gives 40;
  `ngp 2` turns it back on with the NG+2 threshold 25; catchup.enabled off ends it.
- cap: `ngp off` back to the run's NG+1, then levelling to 20 turns it off ("level 20 >= 20").
"""
import json
import re
import time

from gamelab.bots.plan_checks import Checks as Base

BUFF = ".hwp.catchup.buff"
GIVE = 40


class Checks(Base):
    def buffs(self):
        pl = self.gl("state").get("player") or {}
        b = pl.get("buffs") or []
        if isinstance(b, dict):
            return list(b.keys())
        return [x.get("name") if isinstance(x, dict) else x for x in b]

    def has_buff(self, want, timeout=4.0):
        end = time.time() + timeout
        while True:
            on = BUFF in json.dumps(self.buffs())
            if on == want or time.time() > end:
                return on
            time.sleep(0.4)

    def xp(self):
        r = self.gl("inspect", "player", "experience")
        return int(r.get("value", 0))

    def gain(self, amount=GIVE):
        before = self.xp()
        self.hwp(f"xp {amount}", 0.4, until="gave ")
        time.sleep(0.4)
        return self.xp() - before

    def status(self):
        t = self.hwp("catchup", 0.3, until="Catch-up experience")
        lines = [ln for ln in t.splitlines() if "Catch-up experience" in ln]
        return lines[-1] if lines else ""

    def town(self):
        r = self.gl("char", "paladin", "LabCatch")
        ok = self.wait_phase("town", 60)
        time.sleep(2)
        pl = self.gl("state").get("player") or {}
        self.flag("LabCatch_ready", ok and pl.get("name") == "LabCatch" and pl.get("level") == 1,
                  json.dumps(r)[:200])
        s = self.status()
        self.flag("catch_town_off", "no (in town)" in s and not self.has_buff(False, 0), s)

    def run(self):
        mark = len(self.g.read_log())
        r = self.gl("mission", "bandit_keep", 0, 1)
        ok = bool(r.get("ok")) and self.wait_phase("mission")
        time.sleep(3)
        self.flag("catch_mission", ok, json.dumps(r)[:200])
        log = self.g.read_log()[mark:]
        on = self.has_buff(True)
        self.flag("catch_on_ngp1", on and "bonus on: level 1 < 20 at NG+1" in log,
                  f"buffs {self.buffs()}; {self.status()}")
        g = self.gain()
        self.out["gain_on"] = g
        self.flag("catch_xp_150", g == GIVE * 3 // 2, f"+{GIVE} gave {g}")

    def off(self):
        self.hwp("catchup ngp 0", 0.5, until="bonus off: NG+0")
        off = not self.has_buff(False)
        g = self.gain()
        self.out["gain_off"] = g
        self.flag("catch_off_ngp0", off and g == GIVE, f"buff gone {off}, +{GIVE} gave {g}")

        self.hwp("catchup ngp 2", 0.5, until="bonus on: level 1 < 25 at NG+2")
        self.flag("catch_on_ngp2", self.has_buff(True), self.status())

        self.hwp("set catchup.enabled 0", 0.5, until="bonus off: switched off")
        self.flag("catch_setting_off", not self.has_buff(False), self.status())
        self.hwp("set catchup.enabled 1", 0.5, until="bonus on:")
        self.hwp("catchup ngp off", 0.5, until="ngp forced: off")
        self.flag("catch_back_on", self.has_buff(True), self.status())

    def cap(self):
        self.hwp("levelup 19", 0.8, until="now level")
        time.sleep(0.5)
        s = self.status()
        self.flag("catch_cap_off", "level 20 >= 20" in s and not self.has_buff(False), s)
        g = self.gain(400)
        self.flag("catch_cap_plain", g in (0, 400), f"+400 at level 20 gave {g}")
        m = re.search(r"your level (\d+)", s)
        self.out["level"] = int(m.group(1)) if m else -1


def run(p, sections="town,run,off,cap", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
