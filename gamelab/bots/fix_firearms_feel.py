"""Firearms feel fixes (the user's bug list of 2026-10-22, items 1-5), one section each:

- aim_diagonal: the rifle's rounds cross the crosshair at 8 compass points (Combat.as
  AimAtCursor): the cursor is put 120 px out, a shot is fired along it, and every tracked
  round's path (first to last sight, gl track) must pass within 5 px of the crosshair,
  allowing for the round drawn 11 px above its collision point.
- reload_world: the reload bar draws over the player in the world (Combat.as OverReloadState
  .Render), centred on the player RELOAD_BAR_ABOVE px up, and `hwp firearms reload` says so.
- cannon_pistol_right: a Hand Cannon in the main hand with a pistol in the off hand (and the
  other way round): the right click fires two rounds, a held right click keeps firing, one
  round left fires alone, and no gun cycle fires nothing (Combat.as HWPFirearmsGun.Deactivate
  logs "cycle fired no round" with `hwp firearms hands`).
- poses: the gun pose state machine (Pose.as): rifle down idle, straight firing, down 1 s
  after the last shot or at once on a dodge, up reloading, 45 degrees up for the launcher,
  straight for full auto; pistols up idle, straight firing with a 100 ms kick on the hand
  that shot, down reloading. Frames of each pose for the eye.

    {"do": "bot", "bot": "fix_firearms_feel", "kwargs": {"sections": "aim_diagonal"}, ...}
"""
from __future__ import annotations

import math
import re
import time

from gamelab.bots.plan_firearms import Checks as Base

POSE = r"pose: main (\S+), off (\S+) \(([^)]*(?:\([^)]*\))?)\)"


class Checks(Base):
    # --- plumbing
    def setup(self, name):
        self.gl("char", "hwp_firearms", name)
        self.wait_phase("town", 60)
        time.sleep(2)
        if not self.enter_floor(name.lower()):
            return False
        self.g.console("dbg_cht_ignore_equipment_requirements 1")
        time.sleep(0.5)
        return True

    def equip(self, *items):
        got = [bool(self.gl("equip", it, "common").get("ok")) for it in items]
        time.sleep(1.0)  # the markers re-apply every 250 ms; an old one lasts 600 ms
        self.gl("givestacks", self.CLIP, 999)
        return got

    @staticmethod
    def compass(ux, uy):
        return ("n" if uy < -0.3 else "s" if uy > 0.3 else "") + ("e" if ux > 0.3 else "w" if ux < -0.3 else "")

    def since(self, pos, pattern):
        return re.findall(pattern, self.log_from(pos))

    # --- 1. rounds through the crosshair at every angle
    def aim_diagonal(self):
        if not self.setup("LabAim"):
            return
        eq = self.equip("hwp_rifle_01")
        self.flag("aim_rifle_equipped", all(eq), f"{eq}")
        dirs = self.open_dirs(150)
        R = 120
        fired, offs = 0, []
        for ux, uy in dirs[:8]:
            dx, dy = round(ux * R), round(uy * R)
            cur = self.gl("cursor", dx, dy)
            if abs(cur.get("dx", 1e9) - dx) > 2 or abs(cur.get("dy", 1e9) - dy) > 2:
                self.notes.append(f"cursor {dx},{dy} did not stick: {cur}")
                continue
            self.gl("givestacks", self.CLIP, 999)
            tag = f"aim{dx}x{dy}".replace("-", "m")
            if not self.gl("track", tag, 700, 400, "rifle_round").get("ok"):
                continue
            pos = self.log_pos()
            self.gl("input", 60, 0, 0, round(ux, 3), round(uy, 3), "main")
            ev = self.g.wait_gl(lambda o: o.get("ev") == "track" and o.get("tag") == tag, 12) or {}
            aim = self.wait_log(r"aim at cursor ([-\d.]+),([-\d.]+), engine ([-\d.]+) deg, gun ([-\d.]+) deg", pos, 1.0)
            best = None
            for t in ev.get("tracks") or []:
                x0, y0, x1, y1 = t["x0"], t["y0"], t["x1"], t["y1"]
                length = math.hypot(x1 - x0, y1 - y0)
                if length < 30:
                    continue
                # the crosshair C = player + (dx, dy); the round is drawn 11 px above its
                # collision path (rifle_round.unit height), so the path must cross C + (0, 11)
                cx, cy = t["px0"] + dx, t["py0"] + dy + 11
                d = abs((x1 - x0) * (cy - y0) - (y1 - y0) * (cx - x0)) / length
                best = d if best is None else min(best, d)
            name = f"aim_{self.compass(ux, uy)}_on_crosshair"
            if best is not None:
                fired += 1
                offs.append(round(best, 1))
            self.flag(name, best is not None and best <= 5.0,
                      f"path {best and round(best, 1)} px from the crosshair at {dx},{dy}; {aim and aim.group(0)}")
            time.sleep(0.6)
        self.flag("aim_directions_fired", fired >= 4, f"{fired} of {len(dirs[:8])} directions tracked a round")
        self.flag("aim_all_on_crosshair", fired >= 4 and all(o <= 5.0 for o in offs), f"offsets {offs} px")
        st = self.hwp("firearms aim", 0.3, until="aim: fixes")
        m = re.search(r"aim: fixes (\d+)", st)
        self.flag("aim_fix_active", bool(m) and int(m.group(1)) > 0, st.strip()[-220:])
        self.to_town()

    # --- 2. the reload bar over the player
    def reload_world(self):
        if not self.setup("LabBar"):
            return
        self.equip("hwp_rifle_01")
        pos = self.log_pos()
        self.gl("givestacks", self.CLIP, -999)  # dry: the automatic reload starts and the bar shows
        drawn = self.wait_log(r"reload bar: over the player at (-?\d+),(-?\d+) \(gui\), (\d+) px up", pos, 3.0)
        time.sleep(0.25)
        self.g.shot("reload bar over player", settle=False)
        st = self.hwp("firearms reload", 0.2, until="reload bar:")
        m = re.search(r"\(player at (-?\d+),(-?\d+), (\d+) px up, w (\d+)\)", st)
        self.flag("reload_bar_drawn_in_world", drawn is not None, f"{drawn and drawn.group(0)}")
        ok = False
        if drawn and m:
            bx, by = int(drawn.group(1)), int(drawn.group(2))
            px, py, up, w = (int(x) for x in m.groups())
            ok = abs(bx + w / 2 - px) <= 3 and up - 3 <= py - by <= up + 3
        self.flag("reload_bar_centered_over_player", ok, st.strip()[-300:])
        self.flag("reload_bar_not_on_hud", "over player:" in st, "the status names the world anchor")
        time.sleep(3.0)
        self.to_town()

    # --- 3. a Hand Cannon in the main hand, a pistol in the off hand: the right click
    def cannon_pistol_right(self):
        if not self.setup("LabRight"):
            return
        for name, items, marks in (("cannon_pistol", ("hwp_hcannon_mh_01", "hwp_glock_oh_01"), ("hcannon_main", "glock_off", "hwp_attack_glock_off")),
                                   ("pistol_cannon", ("hwp_glock_mh_01", "hwp_hcannon_oh_01"), ("glock_main", "hcannon_off", "hwp_attack_hcannon_off"))):
            eq = self.equip(*items)
            hands = self.hwp("firearms hands", 0.3, until="hands:")
            self.flag(f"{name}_markers", all(eq) and all(m in hands for m in marks), f"equip {eq}; {hands.strip()[-260:]}")
            pos = self.log_pos()
            b = [self.press("off", settle=1.3) for _ in range(2)]
            self.flag(f"{name}_right_two_rounds", all(c0 - c1 == 2 for c0, c1 in b), f"{b}")
            self.gl("givestacks", self.CLIP, 999)
            c0, c1, gaps = self.hold("off", 2300)
            # both rounds at 0, 1040 and 2080 ms of the held click
            self.flag(f"{name}_right_held_fires", 4 <= c0 - c1 <= 8, f"clip {c0}->{c1}, gaps {gaps}")
            c = self.clip()
            if c > 1:
                self.gl("givestacks", self.CLIP, -(c - 1))
            time.sleep(0.3)
            c0, c1 = self.press("off", settle=1.3)
            self.flag(f"{name}_right_last_round", c0 == 1 and c1 == 0, f"clip {c0}->{c1}")
            time.sleep(3.0)  # the automatic reload
            self.gl("givestacks", self.CLIP, 999)
            # the right click while the left is held: the main hand's mixed cycle already fires
            # both guns (PlayerTargetingHelper lets one repeating skill run at a time); noted
            k0 = self.clip()
            self.gl("input", 900, 0, 0, 1, 0, "main")
            time.sleep(0.3)
            self.gl("input", 60, 0, 0, 1, 0, "off")
            time.sleep(1.6)
            self.notes.append(f"{name}: right click during a 900 ms held left click: {k0 - self.clip()} rounds in all")
            empty = self.since(pos, r"cycle fired no round[^\n]*")
            self.flag(f"{name}_no_empty_cycle", not empty, f"{empty[:2]}")
        self.to_town()

    # --- 4. and 5. the gun poses
    def poses(self):
        if not self.setup("LabPose"):
            return
        self.rifle_poses()
        self.pistol_poses()
        st = self.hwp("firearms pose", 0.3, until="pose: state")
        self.flag("pose_status", "pose: state" in st, st.strip()[-240:])
        self.to_town()

    def shoot(self, button="main", ms=60):
        self.gl("givestacks", self.CLIP, 999)
        pos = self.log_pos()
        self.gl("input", ms, 0, 0, 1, 0, button)
        return pos, time.time()

    def rifle_poses(self):
        pos = self.log_pos()
        eq = self.equip("hwp_rifle_01")
        idle = self.wait_log(r"pose: main down, off - \(idle\)", pos, 2.0)
        self.flag("rifle_idle_down", all(eq) and idle is not None, f"equip {eq}, {idle and idle.group(0)}")
        time.sleep(0.3)
        self.g.shot("rifle idle down")

        pos, t0 = self.shoot()
        fire = self.wait_log(r"pose: main straight, off - \(firing\)", pos, 1.5)
        time.sleep(0.3)
        self.g.shot("rifle firing straight", settle=False)
        down = self.wait_log(r"pose: main down, off - \(idle \(1000 ms without a shot\)\)", pos, 3.0)
        dt = time.time() - t0
        self.flag("rifle_firing_straight", fire is not None, f"{fire and fire.group(0)}")
        # the pose counts the second from the end of the gun cycle, not from the click
        self.flag("rifle_down_after_1s", down is not None and 0.9 < dt < 2.6, f"{down and down.group(0)} {dt:.2f} s after the click")
        time.sleep(0.4)

        # held through a burst: straight the whole time, no down between the rounds
        pos, t0 = self.shoot(ms=1700)
        time.sleep(2.0)
        between = self.since(pos, POSE)
        self.flag("rifle_straight_through_burst", any(p[0] == "straight" for p in between) and not any(p[0] == "down" and "without" not in p[2] for p in between[:-1]),
                  f"{between}")
        time.sleep(1.2)

        pos, t0 = self.shoot()
        self.wait_log(r"\(firing\)", pos, 1.0)
        self.gl("input", 120, 0, 1, 0, 1, "dash")
        dodge = self.wait_log(r"pose: main down, off - \(idle \(another skill\)\)", pos, 1.5)
        # the reason is the check: "(another skill)", not the 1000 ms idle; the time is a note
        # (the inbox's round trips put the dodge itself ~1 s after the shot, poses 20261026-140606)
        self.flag("rifle_down_on_dodge", dodge is not None, f"{dodge and dodge.group(0)} {time.time() - t0:.2f} s after the shot")
        time.sleep(1.2)

        pos, t0 = self.shoot()
        self.gl("givestacks", self.CLIP, -999)
        up = self.wait_log(r"pose: main up, off - \(reloading\)", pos, 1.5)
        time.sleep(0.3)
        self.g.shot("rifle reloading up", settle=False)
        self.flag("rifle_up_reloading", up is not None, f"{up and up.group(0)}")
        time.sleep(3.0)

        # the launcher (the rifle's secondary, 4 mana): 45 degrees up
        pos, t0 = self.shoot("off")
        high = self.wait_log(r"pose: main high, off - \(secondary\)", pos, 1.5)
        time.sleep(0.2)
        self.g.shot("rifle launcher high", settle=False)
        self.flag("rifle_high_on_launcher", high is not None, f"{high and high.group(0)}")
        time.sleep(1.5)

        # full auto: straight, never high
        pos0 = self.log_pos()
        eq = self.equip("hwp_autorifle_01")
        pos, t0 = self.shoot("off", ms=600)
        time.sleep(1.0)
        got = self.since(pos, POSE)
        self.flag("autofire_straight", all(eq) and any(p[0] == "straight" and p[2] == "firing" for p in got) and not any(p[0] == "high" for p in got),
                  f"equip {eq}, {got}")
        time.sleep(1.5)

    def pistol_poses(self):
        pos = self.log_pos()
        eq = self.equip("hwp_glock_mh_01", "hwp_glock_oh_01")
        idle = self.wait_log(r"pose: main up, off up \(idle\)", pos, 2.0)
        self.flag("pistols_idle_up", all(eq) and idle is not None, f"equip {eq}, {idle and idle.group(0)}")
        time.sleep(0.3)
        self.g.shot("pistols idle up")

        # a slowed clock so a 100 ms kick is on screen for a second
        self.gl("givestacks", self.CLIP, 999)
        pos = self.log_pos()
        self.gl("timescale", 0.1)
        self.gl("input", 700, 0, 0, 1, 0, "main")  # game ms: left, right, left
        time.sleep(0.5)  # the left round's 100 game ms kick = 1 s real
        self.g.shot("pistols firing main kick", settle=False)
        time.sleep(3.0)  # the right-hand round, about 300 game ms in
        self.g.shot("pistols firing off kick", settle=False)
        self.gl("timescale", 1)
        time.sleep(1.5)
        got = self.since(pos, POSE)
        self.flag("pistols_main_kick", any(p[0] == "kick" and p[1] == "straight" and p[2] == "firing" for p in got), f"{got}")
        self.flag("pistols_off_kick", any(p[0] == "straight" and p[1] == "kick" and p[2] == "firing" for p in got), f"{got}")
        self.flag("pistols_straight_between", any(p[0] == "straight" and p[1] == "straight" and p[2] == "firing" for p in got), f"{got}")
        back = self.wait_log(r"pose: main up, off up \(idle \(1000 ms without a shot\)\)", pos, 2.5)
        self.flag("pistols_up_after_1s", back is not None, f"{back and back.group(0)}")

        pos, t0 = self.shoot()
        self.gl("givestacks", self.CLIP, -999)
        down = self.wait_log(r"pose: main down, off down \(reloading\)", pos, 1.5)
        time.sleep(0.3)
        self.g.shot("pistols reloading down", settle=False)
        self.flag("pistols_down_reloading", down is not None, f"{down and down.group(0)}")
        time.sleep(3.0)


def run(p, sections="poses", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
