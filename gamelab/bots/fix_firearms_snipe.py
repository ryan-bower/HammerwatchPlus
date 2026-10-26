"""Firearms Marksman Snipe fixes (the user's items of 2026-10-22), one section each:

- snipe_ranks: a fresh Marksman raises Sniper Shot from rank 1 to 5 (gl skill) and after each
  rank `hwp firearms snipe` (Marksman.as CmdSnipe) reads the live skill's channel (castpoint)
  and the rank's armor penetration bind: 650/570/490/410/325 ms and 30/35/45/50/60 %. At ranks
  1 and 5 a real Snipe (a held Skill3 press along a clear line) hits a dummy 70 px out, and the
  rank-5 hit lands sooner after the press than the rank-1 one: the upgrade dicts' timeline
  entries fire at the new castpoints.
- snipe_recoil: Recoil Roll (gl orb hwp_fs_snipe_recoil). The shot line is certified both
  ways first (gl rayhit: no wall or hard tile 86 px ahead for the dummy and 110 px behind for
  the roll, no blocker near either line; the bot walks to another spot when the floor start
  has none: run 20261025-223130 rolled 17 px into the wall behind the start), and the vanilla
  dash along the roll's way is measured as the baseline. Without the orb a Snipe leaves the
  shooter where they stood; with it the shot throws them back along the shot's line by about a
  dash (90 px; at least 60 counted backwards, under 15 sideways, and `hwp firearms snipe`
  reports the roll the module measured), the snipe_recoil evade buff shows in `gl state`
  while they roll, "[HWP:firearms] snipe recoil:" is logged and the round still hits the
  dummy. With the orb taken off again nothing moves and nothing is logged.

    {"do": "bot", "bot": "fix_firearms_snipe", "kwargs": {"sections": "snipe_ranks"}, ...}
"""
from __future__ import annotations

import math
import re
import time

from gamelab.bots.plan_firearms import BLOCKERS, Checks as Base, hold

SNIPE = "hwp_fs_snipe"
ORB = "hwp_fs_snipe_recoil"
SVAL = "sniper_snipe.sval"
RECOIL_BUFF = ".skills.hwp_firearms.snipe_recoil.buff"  # ActorBuffDef.m_name, as gl state lists buffs
CHANNEL = {1: 650, 2: 570, 3: 490, 4: 410, 5: 325}  # ms, sniper_snipe.sval castpoint per rank
PEN = {1: 30, 2: 35, 3: 45, 4: 50, 5: 60}  # %, snipe-pen per rank
STATUS = (r"snipe: rank (\d+), channel (\d+) ms, armor pen (\d+)%, damage (\d+)%, cooldown (\d+) ms, "
          r"recoil (\w+), rolls (\d+), last roll (\S+) px")
AHEAD = 70 + 16  # the dummy's distance plus the clear_dir margin
BEHIND = 110  # the dash's 90 px plus a margin


class Checks(Base):
    # --- plumbing
    def status(self):
        """`hwp firearms snipe` parsed; the raw tail when it did not answer."""
        txt = self.hwp("firearms snipe", 0.5, until="snipe:")
        m = re.search(STATUS, txt)
        if not m:
            return {"raw": txt[-200:]}
        return {"rank": int(m.group(1)), "channel": int(m.group(2)), "pen": int(m.group(3)),
                "damage": int(m.group(4)), "cooldown": int(m.group(5)), "recoil": m.group(6),
                "rolls": int(m.group(7)), "last_roll": None if m.group(8) == "none" else float(m.group(8))}

    def both_open(self, dist=130):
        """An open direction whose opposite is open too (the shot one way, the roll the other)."""
        dirs = self.open_dirs(dist)
        for d in dirs:
            if any(abs(o[0] + d[0]) < 0.01 and abs(o[1] + d[1]) < 0.01 for o in dirs):
                return d
        return dirs[0]

    def line_clear(self, px, py, u, dist, near):
        """No wall or hard tile dist out along u from (px, py), and no blocker within 12 of the line."""
        r = self.gl("rayhit", round(px, 1), round(py, 1), round(px + u[0] * dist, 1), round(py + u[1] * dist, 1))
        if not r.get("ok") or r.get("wall") or r.get("tile"):
            return False
        return not [n for n in near if 6 < (n["x"] - px) * u[0] + (n["y"] - py) * u[1] < dist
                    and abs((n["x"] - px) * u[1] - (n["y"] - py) * u[0]) < 12]

    def roll_dir(self):
        """A direction with the shot's line clear AHEAD px and the roll's line clear BEHIND px
        the other way, from where the player stands; when the spot has none, walk 100 px along
        an open direction and look again (up to 3 spots)."""
        compass = [(round(math.cos(math.radians(a)), 3), round(math.sin(math.radians(a)), 3)) for a in range(0, 360, 45)]
        for attempt in range(3):
            px, py = self.pos()
            near = [u for u in self.gl("near", BEHIND + 30).get("units") or []
                    if u.get("behavior") in BLOCKERS and "target_dummy" not in u.get("name", "")]
            opens = self.open_dirs(130)
            for u in opens + [c for c in compass if c not in opens]:
                if self.line_clear(px, py, u, AHEAD, near) and self.line_clear(px, py, (-u[0], -u[1]), BEHIND, near):
                    self.notes.append(f"roll line {u} from {round(px)},{round(py)}: clear {AHEAD} ahead, {BEHIND} behind")
                    return u
            step = opens[0]
            self.notes.append(f"no two-way line at {round(px)},{round(py)}; walking 100 along {step}")
            self.p.path_to(px + step[0] * 100, py + step[1] * 100, tol=6, timeout=20)
        return self.both_open()

    def dash_baseline(self, d):
        """The vanilla dash along the roll's way (-d): px moved back along d, as the recoil is
        measured. The player walks back after."""
        self.ready("dash_skill", 5)
        p0 = self.pos()
        self.gl("input", 150, -d[0], -d[1], -d[0], -d[1], "dash")  # move and aim both: the kbm dash takes the move dir (Player.as:1184)
        time.sleep(0.9)
        p1 = self.pos()
        back = -((p1[0] - p0[0]) * d[0] + (p1[1] - p0[1]) * d[1])
        self.p.path_to(p0[0], p0[1], tol=4, timeout=20)
        return round(back, 1)

    def one_shot(self, d, secs=1.6):
        """A Snipe along d at a dummy 70 px out: whether it hit, ms from the press to the hp
        drop (polled), the shooter's displacement along and across d, whether the recoil buff
        was seen and whether the recoil line was logged."""
        d2, (du,) = self.line_dummies(d, [70])
        if d2 != d:
            self.notes.append(f"shot line moved from {d} to {d2}: the roll's way behind it is not certified")
        self.top_up()
        p0 = self.pos()
        hp0 = self.hps([du])[du]
        mark = self.log_pos()
        t0 = time.time()
        self.aimed_cast(SNIPE, d2, hold(SVAL))
        hit_ms, buff, n = None, False, 0
        end = time.time() + secs
        while time.time() < end:
            st = self.gl("state").get("player", {})
            n += 1
            if RECOIL_BUFF in (st.get("buffs") or []):
                buff = True
            if hit_ms is None and self.hps([du])[du] < hp0 - 0.001:
                hit_ms = round((time.time() - t0) * 1000)
        p1 = self.pos()
        hp1 = self.hps([du])[du]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        back = -(dx * d2[0] + dy * d2[1])
        side = abs(dx * d2[1] - dy * d2[0])
        log = self.log_from(mark)
        self.clear_dummies()
        # back to the spot the line was cleared from
        self.p.path_to(p0[0], p0[1], tol=4, timeout=20)
        return {"hit": hp1 < hp0 - 0.001, "hit_ms": hit_ms, "hp": (round(hp0, 3), round(hp1, 3)),
                "back": round(back, 1), "side": round(side, 1), "buff": buff, "samples": n,
                "log": "snipe recoil:" in log, "dir": d2}

    # --- 1. channel and armor penetration per rank
    def snipe_ranks(self):
        self.new_char("LabSnipeRank", "hwp_firearms_sniper")
        if not self.enter_floor("snipe_ranks"):
            return
        if not self.level("snipe_ranks", SNIPE):
            return
        d = self.both_open()
        got, shots = {}, {}
        for rank in range(1, 6):
            if rank > 1:
                r = self.gl("skill", SNIPE, 1)
                time.sleep(0.6)  # SkillUp reloads the skills (LoadSkills)
                if r.get("level", 0) != rank:
                    self.notes.append(f"gl skill to rank {rank} answered {r}")
            got[rank] = self.status()
            if rank in (1, 5):
                shots[rank] = self.one_shot(d)
        raws = [got[r].get("raw") for r in got if "raw" in got[r]]
        self.flag("snipe_rank_readback", all(got[r].get("rank") == r for r in got),
                  f"ranks reported {[got[r].get('rank') for r in got]}; unparsed {raws}")
        self.flag("snipe_channel_per_rank", all(got[r].get("channel") == CHANNEL[r] for r in got),
                  f"channel ms per rank {[got[r].get('channel') for r in got]}, want {list(CHANNEL.values())}")
        self.flag("snipe_armor_steps", all(got[r].get("pen") == PEN[r] for r in got),
                  f"armor pen % per rank {[got[r].get('pen') for r in got]}, want {list(PEN.values())}")
        self.flag("snipe_damage_steps", [got[r].get("damage") for r in got] == [300, 400, 500, 600, 750],
                  f"damage % per rank {[got[r].get('damage') for r in got]}")
        s1, s5 = shots.get(1, {}), shots.get(5, {})
        self.flag("snipe_fires_rank1", s1.get("hit"), f"{s1}")
        self.flag("snipe_fires_rank5", s5.get("hit"), f"{s5}")
        sooner = bool(s1.get("hit_ms")) and bool(s5.get("hit_ms")) and s5["hit_ms"] <= s1["hit_ms"] - 150
        self.flag("snipe_rank5_sooner", sooner,
                  f"press to hit: rank 1 {s1.get('hit_ms')} ms, rank 5 {s5.get('hit_ms')} ms (channel 650 vs 325, polled)")
        self.to_town()

    # --- 2. Recoil Roll
    def snipe_recoil(self):
        self.new_char("LabRecoil", "hwp_firearms_sniper")
        if not self.enter_floor("snipe_recoil"):
            return
        if not self.level("snipe_recoil", SNIPE):
            return
        d = self.roll_dir()
        base = self.dash_baseline(d)
        self.notes.append(f"vanilla dash along {(-d[0], -d[1])}: {base} px (90 nominal)")
        plain = self.one_shot(d)
        ok, lvl = self.orb(ORB)
        st = self.status()
        self.flag("recoil_orb_taken", ok and lvl == 1 and st.get("recoil") == "orb", f"orb level {lvl}, status {st}")
        roll = self.one_shot(d)
        self.flag("recoil_shot_hits", roll.get("hit"), f"{roll}")
        self.flag("recoil_pushes_back", roll["back"] >= 60 and roll["side"] <= 15,
                  f"moved {roll['back']} back, {roll['side']} aside along {roll['dir']} (a dash is 90; the vanilla dash here went {base})")
        self.flag("recoil_matches_dash", base > 0 and roll["back"] >= 0.7 * base, f"roll {roll['back']} vs dash {base}")
        self.flag("recoil_buff_seen", roll["buff"],
                  f"{RECOIL_BUFF} in gl state during the roll: {roll['buff']} ({roll['samples']} samples)")
        self.flag("recoil_logged", roll["log"], "snipe recoil: in the log")
        st2 = self.status()
        self.flag("recoil_counted", st2.get("rolls", 0) >= 1, f"{st2}")
        self.flag("recoil_rolled_in_game", (st2.get("last_roll") or 0) >= 60,
                  f"the module measured the roll at {st2.get('last_roll')} px (snipe recoil: rolled ... in the log)")
        quiet = abs(plain["back"]) <= 4 and plain["side"] <= 4 and not plain["buff"] and not plain["log"]
        self.flag("recoil_none_without_orb", quiet, f"before the orb: {plain}")
        self.orb_off(ORB)
        st3 = self.status()
        after = self.one_shot(d)
        off = st3.get("recoil") == "none" and abs(after["back"]) <= 4 and not after["buff"] and not after["log"]
        self.flag("recoil_off_when_removed", off, f"status {st3}; shot {after}")
        self.to_town()


def run(p, sections="snipe_ranks", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
