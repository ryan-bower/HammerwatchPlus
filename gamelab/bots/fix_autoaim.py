"""Auto aim (mods/autoaim: HWP/AutoAim, on core's aim hooks HWP/Core/Aim.as), in town as a
ranger whose Marked Shot (ran_mark, Skill 1) is a reticle skill (TargetingMode::TargetAOE),
with a target dummy spawned 80 px south of the player. The lab has no gamepad, so every
check runs with autoaim.mode 2 (controller and mouse) on the mouse path; the gamepad path
differs only in feeding the stick's reticle (CalcGamepadTargetPos) instead of the cursor.

- Auto fire: holding Skill 1 fires Marked Shot at the dummy without the attack press
  (`hwp autoaim`: one shot, "auto fire ran_mark at ...target_dummy_normal..."), and the skill
  goes on cooldown.
- Fire off: holding Skill 1 snaps the reticle onto the dummy (the snap count rises, the
  snap spot is the dummy's) and nothing fires.
- The cone: with a 90 degree cone and the cursor pinned north of the player, the dummy
  (south) is not picked; with the cursor south, it is.
- Auto skill: with nothing pressed, the ready Marked Shot casts itself at the dummy.
- Mode off: no snap and no auto cast.
- The Plus tab: the four rows show, and clicking the mode row cycles the setting.

Shots: autoaim-snap, autoaim-options.

Sections: autoaim, options."""
import re
import time

from gamelab.bots.plan_runs import Checks as Base

DUMMY = "doodads/generic/target_dummy_normal.unit"
STATUS = re.compile(r"shots (\d+), skill shots (\d+); snaps (\d+), snap (-?\d+),(-?\d+); last (.*)$")


class Checks(Base):
    def status(self):
        # "autoaim: on, mode 2 (...)" (or "off (autoaim.enabled), mode ...")
        log = self.hwp("autoaim", 0.4, until="] autoaim: ")
        lines = [ln for ln in log.splitlines() if "] autoaim: " in ln and ", mode " in ln]
        if not lines:
            return None
        m = STATUS.search(lines[-1])
        if not m:
            return None
        return {"shots": int(m[1]), "skill": int(m[2]), "snaps": int(m[3]), "snap": (int(m[4]), int(m[5])),
                "last": m[6].strip(), "line": lines[-1]}

    def mark_cd(self):
        for s in self.gl("skillbar").get("skills") or []:
            if s.get("id") == "ran_mark":
                return s.get("cd", 0.0)
        return None

    def ready(self, timeout=25):
        end = time.time() + timeout
        while time.time() < end:
            cd = self.mark_cd()
            if cd is not None and cd <= 0:
                return True
            time.sleep(0.5)
        return False

    def set(self, **kv):
        for k, v in kv.items():
            self.hwp(f"set autoaim.{k} {v}", 0.25)

    def hold_skill(self, ms=400, aim_y=1):
        self.gl("input", ms, 0, 0, 0, aim_y, "skill1")
        time.sleep(ms / 1000 + 0.4)

    def cancel(self):
        self.gl("input", 150, 0, 0, 0, 1, "off")
        time.sleep(0.4)

    def autoaim(self):
        self.set(mode=2, cone=360, skill=0, fire=1, debug=1, skill_mana=60)
        sp = self.gl("spawn", DUMMY, 0, 80, "clear")
        dummy = (round(sp.get("x", 0)), round(sp.get("y", 0)))
        time.sleep(0.6)
        self.notes.append(f"dummy at {dummy}")

        # auto fire
        self.ready()
        s0 = self.status()
        self.hold_skill()
        s1 = self.status()
        cd = self.mark_cd()
        self.flag("aa_fire", bool(s0 and s1 and s1["shots"] == s0["shots"] + 1 and "auto fire ran_mark" in s1["last"]
                  and "target_dummy" in s1["last"] and cd is not None and cd > 0),
                  f"{s1 and s1['line']}; ran_mark cd {cd}")

        # fire off: the reticle snaps, nothing fires
        self.set(fire=0)
        self.ready()
        s0 = self.status()
        self.gl("input", 500, 0, 0, 0, 1, "skill1")
        time.sleep(0.3)
        self.g.shot("autoaim-snap")
        time.sleep(0.6)
        s1 = self.status()
        cd = self.mark_cd()
        self.cancel()
        snap_ok = bool(s1) and abs(s1["snap"][0] - dummy[0]) <= 2 and abs(s1["snap"][1] - dummy[1]) <= 2
        self.flag("aa_snap", bool(s0 and s1 and s1["snaps"] > s0["snaps"] and s1["shots"] == s0["shots"] and snap_ok
                  and cd is not None and cd <= 0), f"{s1 and s1['line']}; dummy {dummy}; ran_mark cd {cd}")

        # the cone: the cursor held 100 px north of the player (the dummy behind), then south
        # (inputtarget writes the cursor every frame; gl mouse pins only the UI's)
        self.set(cone=90)
        px, py = dummy[0], dummy[1] - 80
        s0 = self.status()
        self.gl("inputtarget", "cone_n", "-", px, py - 100, "500/0/0/0/-1/skill1", "200/0/0/0/-1/off", "200/0/0/0/-1/-")
        time.sleep(1.4)
        s1 = self.status()
        self.gl("inputtarget", "cone_s", "-", px, py + 100, "500/0/0/0/1/skill1", "200/0/0/0/1/off", "200/0/0/0/1/-")
        time.sleep(1.4)
        s2 = self.status()
        self.flag("aa_cone", bool(s0 and s1 and s2 and s1["snaps"] == s0["snaps"] and s2["snaps"] > s1["snaps"]),
                  f"north: {s0 and s0['snaps']} -> {s1 and s1['snaps']}; south: -> {s2 and s2['snaps']}")

        # auto skill: nothing pressed
        self.set(cone=360, fire=1, skill_mana=0)
        self.ready()
        s0 = self.status()
        self.set(skill=1)
        time.sleep(3)
        s1 = self.status()
        self.flag("aa_skill", bool(s0 and s1 and s1["skill"] > s0["skill"] and "auto skill ran_mark" in s1["last"]
                  and "target_dummy" in s1["last"]), f"{s0 and s0['skill']} -> {s1 and s1['line']}")

        # mode off
        self.set(mode=0)
        self.ready()
        s0 = self.status()
        time.sleep(3)
        self.hold_skill()
        s1 = self.status()
        self.cancel()
        self.flag("aa_off", bool(s0 and s1 and s1["skill"] == s0["skill"] and s1["snaps"] == s0["snaps"]),
                  f"{s0 and s0['line']} -> {s1 and s1['line']}")
        self.set(mode=2, skill=0)

    def opt(self, widget):
        return self.gl("menu", "hwp_options", "-", widget)

    def options(self):
        self.gl("menu", "character")
        time.sleep(0.5)
        # the Plus tab lists auto aim's rows under its package (the mode row also on top)
        self.gl("menu", "hwp_options", "-", "hwp-pkg-autoaim", "hwp-open", "autoaim")
        time.sleep(0.3)
        rows = {r: self.opt(f"hwp-opt-{r}") for r in ("autoaim", "aimcone", "autofire", "autoskill")}
        self.g.shot("autoaim-options")
        texts = {r: (v.get("texts", ""), v.get("shown")) for r, v in rows.items()}
        before = rows["autoaim"].get("texts", "")
        self.gl("menu", "hwp_options", "-", "hwp-opt-autoaim", "hwp-opt", "autoaim")
        time.sleep(0.4)
        after = self.opt("hwp-opt-autoaim").get("texts", "")
        st = self.status()
        self.flag("aa_rows", all(t[1] for t in texts.values()) and "Auto aim" in texts["autoaim"][0]
                  and "Auto skill" in texts["autoskill"][0], f"{texts}")
        self.flag("aa_cycle", before != after and st is not None and "mode 0 (Off)" in st["line"],
                  f"{before!r} -> {after!r}; {st and st['line'][:80]}")
        self.set(mode=1)


def run(p, sections="autoaim,options", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
