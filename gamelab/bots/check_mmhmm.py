"""The Mm-hmm! hat bonus (mods/mmhmm: scripts/HWP/MmHmm/MmHmm.as, tweak/hwp/modifiers_mmhmm.sval).

Rare item-level-1 head items from the `kit` verb (ilvl 20 ones ask for more attributes than
the lab character has, so `kit` could not put them on) (Equipment::Generator mods, as a drop rolls them), one
after another: each one that qualifies (25 %, a function of the item) gets the bonus on top
of its rolled modifiers, the others never do; a common hat never does. Then the worn hat
gets it (`hwp mmhmm give`) and the Service Pistol shoots a target dummy (`bench`): the crits made while
wearing it are counted. The voice itself is the modifier's crit TriggerEffect; GameLab is
muted, so the sound is not measured.

moments (in a Bandit Keep run, the worn hat given the bonus): every other moment plays the voice
once (the `[HWP:mmhmm] voice: <why>` line and the moments count): the last orb of a 3-orb tree
(gl orb, SkillTempUp) but not its earlier orbs nor a 1-orb tree; a well and a secret room
(gl statadd: the run stat each one's use adds, not the use itself); a real Ace chest (mods/keys); the 4th piece
of Charms of Fortune but not the 3rd; nothing without the hat. A real revive needs two
players: only the swapped corpse and a quiet cht_revive (no other reviver) are covered."""
import re
import time

from gamelab.bots.bench import CLIP, DUMMY
from gamelab.bots.plan_checks import Checks as Base

LINE = r"mmhmm: hat (\S+)(?: \((.*?)\))?, bonus (yes|no), qualifies (yes|no), added (\d+), crits with it (\d+), moments (\d+)"


class Checks(Base):
    def status(self):
        m = re.findall(LINE, self.hwp("mmhmm", 0.4, until="mmhmm: hat"))
        return m[-1] if m else None

    def hats(self, n=16):
        self.gl("char", "hwp_firearms", "Hat")
        self.wait_phase("town", 60)
        time.sleep(2)
        self.g.console("e_cheats 1")
        self.hwp("levelup 20", 1.0)
        seen, bad = [], []
        for _ in range(n):
            self.gl("kit", 1, "rare", "head")
            time.sleep(1.2)  # checked twice a second
            st = self.status()
            if not st:
                bad.append("no status")
                continue
            hat, name, bonus, qual, _, _, _ = st
            seen.append((hat, bonus, qual))
            if bonus != qual:
                bad.append(f"{name}: bonus {bonus}, qualifies {qual}")
        yes = sum(1 for _, b, _ in seen if b == "yes")
        self.flag("mmhmm_rare_rule", len(seen) == n and not bad and 0 < yes < n,
                  f"{yes} of {len(seen)} rare hats with it; {bad}")
        self.gl("kit", 1, "common", "head")
        time.sleep(1.2)
        st = self.status()
        self.flag("mmhmm_common_never", bool(st) and st[2] == "no" and st[3] == "no", f"{st}")
        # a rerolled check never takes it off or adds it twice
        before = st[4] if st else "?"
        time.sleep(1.5)
        st2 = self.status()
        self.flag("mmhmm_stable", bool(st2) and st2[4] == before, f"added {before} -> {st2[4] if st2 else '?'}")

    def crits(self, ms=40000):  # ~100 pistol hits at a few % crit
        st = self.status()
        self.hwp("mmhmm give", 0.4, until="mmhmm: hat")
        st = self.status()
        self.flag("mmhmm_given", bool(st) and st[2] == "yes", f"{st}")
        c0 = int(st[5]) if st else 0
        # the character's Service Pistol shoots (an ilvl 20 rifle asks for more Dexterity)
        self.gl("kill", 600, "target_dummy")
        self.gl("spawn", DUMMY, 0, 80)
        self.gl("givestacks", CLIP, 999)
        # a gun aims at the mouse cursor (firearms Combat.as AimAtCursor), not the bench's aim
        self.gl("cursor", 0, 80)
        time.sleep(0.5)
        self.gl("bench", "mmhmm", ms, 400, "noskills")
        ev = self.g.wait_gl(lambda o: o.get("ev") == "bench" and o.get("tag") == "mmhmm", ms / 1000 + 30) or {}
        st = self.status()
        c1 = int(st[5]) if st else 0
        self.flag("mmhmm_crits", c1 > c0, f"crits with it {c0} -> {c1}; bench {str(ev)[:200]}")


    def moments_n(self):
        st = self.status()
        return int(st[6]) if st else -1

    def said(self, step, why=None, wait=1.4):
        """moments count after `step` (polled twice a second), and whether `why` was voiced"""
        n0 = self.moments_n()
        step()
        time.sleep(wait)
        n1 = self.moments_n()
        return n1 - n0, f"{n0} -> {n1}"

    def open_ace(self):
        """a real Ace chest (mods/keys): every gold chest red, an ace key, opened with gl use
        (HWPChest.Use from where the player stands: the walk-up can lose the chest to another
        usable, 220827)"""
        self.hwp("set keys.ace_chance 1")
        self.hwp("keygive ace 1")
        dx, dy = self.chest_spot()
        self.gl("spawn", "items/chests/chest_gold_equipment.unit", dx, dy)
        time.sleep(1.5)
        mark = len(self.g.read_log())
        r = self.gl("use", "chest_gold_equipment")
        time.sleep(1.5)
        log = self.g.read_log()[mark:]
        self.ace_note = f"use {r.get('ok')} {r.get('error', '')}; unlocked {'unlocked a ace chest' in log}"

    def moments(self):
        self.start_floor(0)
        self.gl("cull")
        self.hwp("mmhmm give", 0.4, until="mmhmm: hat")
        st = self.status()
        self.flag("mmhmm_run_hat", bool(st) and st[2] == "yes", f"{st}")
        d, note = self.said(lambda: self.gl("orb", "hwp_fs_reload_dodge", 1))
        self.flag("mmhmm_single_orb_quiet", d == 0, "1-orb tree: " + note)
        d1, n1 = self.said(lambda: self.gl("orb", "hwp_fs_frag_stun", 1))
        d2, n2 = self.said(lambda: self.gl("orb", "hwp_fs_frag_stun", 5))
        self.flag("mmhmm_last_orb", d1 == 0 and d2 == 1, f"first orb {n1}, to the last {n2}")
        for stat, name in (("wells-used", "well"), ("secrets-found", "secret")):
            d, note = self.said(lambda: self.gl("statadd", stat))
            self.flag(f"mmhmm_{name}", d == 1, note)
        d, note = self.said(self.open_ace)
        self.flag("mmhmm_ace", d == 1, note + "; " + getattr(self, "ace_note", ""))
        pieces = ("hwp_lucky_hat", "hwp_lucky_horseshoe", "hwp_key_ring", "hwp_fancy_plume")
        d3, n3 = self.said(lambda: [self.gl("cheat", "cht_give_specific_trinket", t) for t in pieces[:3]], wait=2)
        d4, n4 = self.said(lambda: self.gl("cheat", "cht_give_specific_trinket", pieces[3]))
        self.flag("mmhmm_trinket_set", d3 == 0 and d4 == 1, f"3 of 4 {n3}, the 4th {n4}")
        # the corpse is the class-swapped HWPMmHmmCorpse; cht_revive revives with no other
        # player (reviver = revived), which is not a revive moment
        mark = len(self.g.read_log())
        self.gl("cheat", "ply_kill")
        time.sleep(2)
        corpse = [ln for ln in self.g.read_log()[mark:].splitlines() if "corpse: HWPMmHmmCorpse" in ln]
        d, note = self.said(lambda: self.gl("cheat", "cht_revive"), wait=2.5)
        alive = (self.gl("state").get("player") or {}).get("hp", 0) > 0
        self.flag("mmhmm_corpse_swapped", bool(corpse), str(corpse[:1]))
        self.flag("mmhmm_self_revive_quiet", alive and d == 0, f"alive {alive}; {note}")
        self.gl("kit", 1, "common", "head")
        time.sleep(1.2)
        st = self.status()
        d, note = self.said(lambda: self.gl("statadd", "wells-used"))
        self.flag("mmhmm_needs_hat", bool(st) and st[2] == "no" and d == 0, f"{st[:4] if st else st}; {note}")


def run(p, sections="hats,crits,moments", **_):
    c = Checks(p)
    for s in sections.split(","):
        if not s:
            continue
        try:
            getattr(c, s)()
        except Exception as e:
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
