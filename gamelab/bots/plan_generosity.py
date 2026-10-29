"""Test-plan checks for the Paladin of Generosity (the Paladin's 4th spec, mods/specs).

A level-20 Paladin takes hwp_paladin_generosity, learns Pelor's Fury and Pelor's Blessing (and
Lay on Hands and Conviction for the stack sources) and plays in an emptied Bandit Keep floor with
god mode on. `hwp gen` (Generosity.as CmdGen) is the debug command: the status line (stacks, the
cooldowns, every counter, the held target's armor, resistance and damage-taken multipliers and
how many of its skills are casting), `stacks <n>`, `cd` (cooldowns off), `solo on|off|auto` and
`fury [now] [dx dy]` (the cast through the skill's own Activate, aimed at the nearest enemy).

Sections:
- smoke: the character, the skills, the binds of the level, the status line, the Fury's button.
- refusals: a Fury that cannot take hold spends nothing (stacks, mana, cooldown): below 10
  stacks, no enemy at the aim, out of range, a breakable doodad, through the real button too.
- fury: on a bandit brute through the real cast: the stacks and the mana spent, the 30 s
  cooldown, the stun (the brute stays put and casts nothing), armor and resistances at 0, the
  damage-taken multiplier of the level, the strike, the end after the stun; solo free, party
  (`gen solo off`) locked: a walk moves nothing while the light burns.
- bosses: every boss of BOSSES spawned live 110 px east, let fight for a few seconds, then the
  Fury: held (or refused with the stacks, mana and cooldown kept), its attack cut (casting 0
  while held), it stays put, the 60 s cooldown, the beams (4 at least), no script error. The
  per-boss table is in the notes.
- hoh1: the HoH1 tower's bosses (mods/campaign, needs the HoH1 import): each boss floor of
  hwp_forsaken_tower_hoh1 loaded and its fight started the way the level does
  (tower_bosses.TowerBoss), then the Fury on every boss unit of it in turn, checked as in
  bosses (flags hoh1_*). kwargs only: a comma list of level names (boss_mines...).
- stacks: the sources (Lay on Hands on oneself alone, a Blessed Strike kill, Conviction mana),
  the shared 2 s cooldown, the cap at 10, the multiplier, the carry to the next floor, the reset
  on the player's death and in town.
- orbs: the orbs' binds, Blinding Sun's blindness after the stun, Holy Sacrifice (the target dies
  while held: half the cooldown and the stacks), Descendent of Pentival on a dragon trinket.
"""
import re
import time

from gamelab.bots.plan_specs import Checks as Base, DUMMY, TARGET
from gamelab.bots.tower_bosses import RECIPES, TowerBoss, level_name

PF = "hwp_pal_pelors_fury"
PB = "hwp_pal_pelors_blessing"
LOH = "pal_lay_on_hands"
BS = "pal_blessed_strikes"
CONV = "pal_conviction"
SUB = "hwp_paladin_generosity"
STACK = "players/hwp/specs/stacks_specs.sval:pelors_blessing"
FURY_BUFF = "players/hwp/specs/buffs_specs.sval:pelors_fury"
BOSSES = [
    "actors/bosses/boss_bandit/boss_bandit.unit",
    "actors/bosses/boss_arista/boss_arista.unit",
    "actors/bosses/boss_spider_queen/boss_spider_queen.unit",
    "actors/bosses/bone_serpent/boss_serpent.unit",
    "actors/bosses/boss_face/boss_face.unit",
    "actors/bosses/boss_judges/boss_judges_caster.unit",
    "actors/bosses/boss_judges/boss_judges_heavy.unit",
    "actors/bosses/boss_totempole/boss_totempole_earth.unit",
    "actors/bosses/boss_totempole/boss_totempole_fire.unit",
    "actors/bosses/boss_totempole/boss_totempole_ice.unit",
    "actors/bosses/boss_totempole/boss_totempole_lightning.unit",
    "actors/bosses/boss_wraith/boss_dace_arden.unit",
    "actors/bosses/boss_avatar/boss_avatar.unit",
    "actors/bosses/spirits/arcane/boss_spirit_arcane.unit",
    "actors/bosses/spirits/avarice/boss_spirit_avarice.unit",
    "actors/bosses/spirits/benevolence/boss_spirit_benevolence.unit",
    "actors/bosses/spirits/hunt/boss_spirit_hunt.unit",
    "actors/bosses/spirits/warrior/boss_spirit_warrior.unit",
]
# the level the setup leaves the Fury at (2): stun 3000, damage taken +40%, 80 mana
STUN = {1: 3000, 2: 3000, 3: 4000, 4: 4000, 5: 5000}
DMG = {1: 0.2, 2: 0.4, 3: 0.4, 4: 0.6, 5: 0.6}
MANA = {1: 80, 2: 80, 3: 100, 4: 100, 5: 120}
PCT = {1: 0.005, 2: 0.01, 3: 0.015, 4: 0.02, 5: 0.025}


def _num(text, pat):
    m = re.findall(pat, text)
    return int(m[-1]) if m else None


class Checks(Base, TowerBoss):
    # --- plumbing
    def gen(self, sub="status"):
        """The reply of `hwp gen <sub>`: the [HWP] gen: line between the command's own rx and
        reply lines (the inbox transport's gl ids). Matching any "gen:" after a log mark read a
        stale reply: the mark can fall inside the last, half-flushed status line (plan-generosity
        20261027-011818 read blessing 9 with 10 in the log)."""
        for _ in range(2):
            mark = len(self.g.read_log())
            r = self.g.console("hwp gen " + sub) or {}
            cid = r.get("id")
            end = time.time() + 3.0
            while True:
                log = self.g.read_log()[mark:]
                a = log.find(f'"cid":"{cid}"') if cid else 0
                b = log.find(f'"id":"{cid}"', max(a, 0)) if cid else len(log)
                if a >= 0 and b >= 0:
                    seg = log[a:b]
                    lines = [ln for ln in seg.splitlines() if "[HWP] gen:" in ln]
                    if lines:
                        return lines[-1][lines[-1].index("gen:"):]
                if time.time() > end:
                    break
                time.sleep(0.15)
        return ""

    def st(self):
        """The status line as a dict (None for a field it lacks)."""
        t = self.gen("status")
        d = {"raw": t}
        for key, pat in (("stacks", r"(?m)^gen: blessing (\d+)/"), ("mul", r" mul (\d+)"), ("gaincd", r"gaincd (\d+)"),
                         ("convcd", r"convcd (\d+)"), ("gained", r"gained (\d+)"), ("blocked", r"blocked (\d+)"),
                         ("loh", r"blocked \d+ loh (\d+)"), ("kills", r" kills (\d+)"), ("conv", r"kills \d+ conv (\d+)"),
                         ("resets", r"resets (\d+)"), ("bs_scaled", r"scaled bs (\d+)"), ("loh_scaled", r"scaled bs \d+ loh (\d+)"),
                         ("conv_scaled", r"scaled bs \d+ loh \d+ conv (\d+)"), ("casts", r"fury casts (\d+)"),
                         ("refused", r"refused (\d+)"), ("failed", r"failed (\d+)"), ("sacrifices", r"sacrifices (\d+)"),
                         ("blinds", r"blinds (\d+)"), ("cancels", r"cancels (\d+)"), ("pulses", r"pulses (\d+)"),
                         ("asks", r"asks (\d+)"), ("cd", r"; cd (\d+)/"), ("cdmax", r"; cd \d+/(\d+)"), ("holding", r"holding (\d+)"),
                         ("left", r"holding \d+ left (-?\d+)"), ("armormul", r"armormul (\d+)"), ("resmul", r"resmul (\d+)"),
                         ("taken", r"taken (\d+)"), ("casting", r"casting (\d+)"), ("mana", r"; mana (\d+)"),
                         ("pentival", r"pentival runs (\d+)")):
            d[key] = _num(t, pat)
        m = re.search(r"casting \d+ \[([^\]]*)\]", t)
        d["casting_names"] = m.group(1) if m else ""
        d["bodiless"] = " bodiless" in t
        d["solo"] = "solo yes" in t
        d["locked"] = "locked yes" in t
        d["held_locked"] = bool(re.search(r"holding \d+ left -?\d+ locked", t))
        m = re.search(r" last (.*?); (?:pentival|cd)", t)
        d["last"] = m.group(1) if m else ""
        return d

    def fbind(self, skill, name):
        """A numeric bind (the verb replies with text), None when it isn't a number."""
        try:
            return float(self.bind(skill, name))
        except (TypeError, ValueError):
            return None

    def stacks(self, n):
        self.gen(f"stacks {n}")
        return self.st()["stacks"]

    def errors_since(self, mark):
        """Script errors since mark. Floor loads log unrelated [ERR] lines (the map and
        waypoints widgets with no HUD mod, plan-generosity 20261027-011818), so only exceptions and
        errors that name the specs mod or a script file count."""
        new = self.g.read_log()[mark:]
        # not ".as" alone: a floor's DungeonGenerationCommands.as logs [ERR] lines of its own
        # (plan-generosity 20261027-013805)
        return [ln.strip()[:160] for ln in new.splitlines()
                if "Script exception" in ln or ("[ERR]" in ln and any(k in ln for k in ("HWP:specs", "Specs/", "Generosity.as")))
                or ("SValue param error" in ln and "hwp/" in ln.lower())]

    def setup_gen(self, key, levels=0, extra=(LOH, CONV)):
        self.setup(key, "paladin", SUB, [PF, PB])
        for s in extra:
            self.gl("skill", s, 1)
        for _ in range(levels):
            self.gl("skill", PF, 1)
            self.gl("skill", PB, 1)
        self.gen("solo auto")

    def unit_at(self, rel, dx, dy=0, wait=0.6):
        self.gl("spawn", rel, dx, dy)
        time.sleep(wait)
        name = rel.split("/")[-1].replace(".unit", "")
        us = [u for u in self.gl("near", 600, name).get("units") or [] if not u.get("dead")]
        return us[0] if us else None

    def clear(self):
        self.gl("kill", 1500, "tag:enemy")
        self.gl("kill", 900, "target_dummy")
        time.sleep(0.3)

    def unit(self, uid, r=900, name=""):
        """The unit with id uid within r; name filters `near` first (its list is capped, and the
        Spider Queen's spiderlings pushed her out of it, plan-generosity-bosses 20261027-013518)."""
        return next((u for u in self.gl("near", r, name).get("units") or [] if u.get("unit") == uid), None)

    def ready(self, n=10):
        """The Fury off cooldown, n stacks, full mana."""
        self.gen("cd")
        self.stacks(n)
        self.gl("cheat", "cht_give_mana", 500)
        time.sleep(0.2)

    def wait_hold_end(self, limit=8.0):
        end = time.time() + limit
        while time.time() < end:
            s = self.st()
            if s["holding"] is None:
                return s
            time.sleep(0.3)
        return self.st()

    # --- smoke
    def smoke(self):
        self.setup_gen("gen")
        lf, lb = self.lvl.get(PF, 0), self.lvl.get(PB, 0)
        binds = {k: self.fbind(PF, k) for k in ("pf-stun", "pf-dmg", "hs-stacks")}
        binds.update({k: self.fbind(PB, k) for k in ("pb-pct", "dg-max", "dp-on")})
        self.flag("gen_binds", binds.get("pf-stun") == STUN.get(lf) and abs((binds.get("pf-dmg") or 0) - DMG.get(lf, -1)) < 1e-3
                  and abs((binds.get("pb-pct") or 0) - PCT.get(lb, -1)) < 1e-4 and binds.get("dg-max") == 1 and not binds.get("dp-on"),
                  f"levels fury {lf} blessing {lb}: {binds}")
        s = self.st()
        self.flag("gen_status", s["stacks"] == 0 and s["cd"] == 0 and s["cdmax"] == 30000 and s["solo"], s["raw"][:400])
        bar = {b["id"]: b for b in self.gl("skillbar").get("skills") or []}
        fb = bar.get(PF, {})
        self.flag("gen_fury_button", bool(fb.get("button")) and fb.get("mode") == 4 and abs((fb.get("mana") or 0) - MANA[lf]) < 1,
                  f"{PF} in the bar: {fb}; blessing passive: {bar.get(PB)}")
        tip = self.gl("skilltip", PF).get("text", "") + self.gl("skilltip", PB).get("text", "")
        self.flag("gen_tooltips", bool(tip) and "%" not in re.sub(r"\d+%", "", tip) and "hwp.specs" not in tip, tip[:400])
        self.notes.append("smoke status: " + s["raw"][:500])

    # --- refusals: nothing spent
    def spent(self, before, after):
        return {"stacks": (before["stacks"], after["stacks"]), "mana": (before["mana"], after["mana"]), "cd": (before["cd"], after["cd"])}

    def kept(self, before, after):
        return (after["stacks"] == before["stacks"] and after["cd"] == 0 and after["holding"] is None
                and before["mana"] is not None and after["mana"] is not None and after["mana"] >= before["mana"] - 1)

    def refuse_case(self, key, prep, cmd="fury", n=10):
        self.ready(n)
        prep()
        b = self.st()
        r = self.gen(cmd)
        time.sleep(0.8)
        a = self.st()
        self.flag(key, self.kept(b, a) and a["casts"] == b["casts"], f"{r} | {self.spent(b, a)}; last {a['last']}")
        self.clear()
        return a

    def refusals(self):
        self.setup_gen("ref")
        if not self.enter_floor("ref"):
            return
        self.clear()
        self.refuse_case("ref_below_10", lambda: self.unit_at(DUMMY, 80), n=9)
        self.refuse_case("ref_no_target", lambda: None, cmd="fury 80 0")
        self.refuse_case("ref_out_of_range", lambda: self.unit_at(DUMMY, 420), cmd="fury 420 0")
        # a brute's body: dead, not a target (the breakable target dummy is an enemy actor and a
        # fair target, plan-generosity 20261027-011818 held one)
        self.refuse_case("ref_dead", lambda: (self.unit_at(DUMMY, 80), self.gl("kill", 200, "bandit_brute"), time.sleep(0.4)), cmd="fury 80 0")
        # the breakable target dummy: held, a fair target
        self.ready(10)
        self.unit_at(TARGET, 80)
        b, r, a = self.fury_on(cmd="fury 80 0")
        self.flag("ref_dummy_target", a["holding"] is not None or a["casts"] == b["casts"] + 1, f"{r} | {a['last']}")
        self.wait_hold_end(5)
        self.clear()
        self.refuse_case("ref_zero_stacks", lambda: self.unit_at(DUMMY, 80), n=0)
        button = self.button_for("ref", PF, "skill2")
        # the real button at 10: held (the press and its aim reach the skill)
        self.ready(10)
        self.unit_at(DUMMY, 80)
        b = self.st()
        self.gl("cursor", 80, 0)
        self.press(button, aim=(1, 0))
        self.press("main", 0.8, aim=(1, 0))
        a = self.st()
        # the reticle aims at the real mouse (TargetAOE reads input.MousePos, not the emulated
        # aim): a cast, or its refusal at an empty spot, shows the press reached Activate
        reached = a["holding"] is not None or (a["casts"] or 0) > (b["casts"] or 0) or (a["refused"] or 0) > (b["refused"] or 0)
        self.flag("ref_button_cast", reached and (a["stacks"] == 0 if a["holding"] is not None else a["stacks"] == 10),
                  f"{button} at 10: casts {b['casts']} -> {a['casts']}, refused {b['refused']} -> {a['refused']}, holding {a['holding']}, stacks {a['stacks']}, {a['last']}")
        self.wait_hold_end(5)
        self.press("off", 0.3)
        self.clear()
        # the real button below 10: no mana, no cooldown, the "cant" refusal logged
        self.ready(5)
        self.unit_at(DUMMY, 80)
        b = self.st()
        mark = len(self.g.read_log())
        self.gl("cursor", 80, 0)
        self.press(button, aim=(1, 0))
        self.press("main", 0.8, aim=(1, 0))
        a = self.st()
        log = self.g.read_log()[mark:]
        self.flag("ref_button_below_10", self.kept(b, a) and "pelor's fury refused" in log,
                  f"{button}: {self.spent(b, a)}; asks {b['asks']} -> {a['asks']}, refusal lines {log.count('fury refused')}")
        self.press("off", 0.3)
        self.clear()

    # --- fury on a brute
    def fury_on(self, uid_hint=None, cmd="fury"):
        b = self.st()
        r = self.gen(cmd)
        time.sleep(0.6)
        a = self.st()
        return b, r, a

    def fury(self):
        self.setup_gen("fury")
        if not self.enter_floor("fury"):
            return
        lf = self.lvl.get(PF, 2)
        self.clear()
        self.ready(10)
        u = self.unit_at(DUMMY, 90)
        mark = len(self.g.read_log())
        b, r, a = self.fury_on()
        self.flag("fury_cast", a["holding"] is not None and a["casts"] == b["casts"] + 1, f"{r} | {a['raw'][:300]}")
        self.flag("fury_spent", a["stacks"] == 0 and b["mana"] - a["mana"] >= MANA[lf] * 0.8 and 25000 <= (a["cd"] or 0) <= 30000,
                  f"{self.spent(b, a)} (cost {MANA[lf]}, cooldown 30000)")
        self.flag("fury_debuff", a["armormul"] == 0 and a["resmul"] == 0 and abs((a["taken"] or 0) - 1000 * (1 + DMG[lf])) <= 5,
                  f"armormul {a['armormul']} resmul {a['resmul']} taken {a['taken']} (want 0, 0, {1000 * (1 + DMG[lf]):.0f})")
        # the buffs have no display name (actorbuffs' name is m_def.m_name, ""): the Fury is the
        # debuff with the stun's time left
        ab = self.gl("actorbuffs", 200, "bandit_brute").get("actors") or []
        bl = [(x.get("name"), x.get("left"), x.get("debuff")) for act in ab for x in act.get("buffs") or []]
        self.flag("fury_buff_on", any(d and 0 < (left or 0) <= STUN[lf] for _, left, d in bl), f"brute buffs {bl}")
        # the brute stays put and casts nothing (god mode is on, so it would swing at the paladin)
        p0 = self.unit(u["unit"]) if u else None
        casting, moved = [], 0.0
        for _ in range(4):
            time.sleep(0.3)
            p1 = self.unit(u["unit"]) if u else None
            s = self.st()
            if s["holding"] is None:   # the stun is over: it may walk again
                break
            casting.append(s["casting"])
            if p0 and p1:
                moved = max(moved, abs(p1["x"] - p0["x"]) + abs(p1["y"] - p0["y"]))
        self.flag("fury_stun", u is not None and bool(casting) and moved < 3 and all(c == 0 for c in casting),
                  f"moved {moved:.1f} px, casting {casting}")
        self.flag("fury_solo_free", a["solo"] and not a["locked"], f"solo {a['solo']} locked {a['locked']}")
        end = self.wait_hold_end(STUN[lf] / 1000 + 3)
        log = self.g.read_log()[mark:]
        strikes = re.findall(r"fury strikes on \d+: (\d+) beam", log)
        self.flag("fury_strike", bool(strikes) and int(strikes[0]) == 1 and (end["pulses"] or 0) >= 3,
                  f"strike lines {strikes}, pulses {end['pulses']}")
        self.flag("fury_ends", end["holding"] is None and "pelor's fury ended" in log, f"after the stun: {end['raw'][-200:]}")
        ab = self.gl("actorbuffs", 300, "bandit_brute").get("actors") or []
        bl = [(x.get("name"), x.get("left"), x.get("debuff")) for act in ab for x in act.get("buffs") or []]
        self.flag("fury_buff_off", not any(d for _, _, d in bl), f"brute buffs after {bl}")
        # a second cast at once: the cooldown refuses, the new stacks are kept
        self.stacks(10)
        b2, r2, a2 = self.fury_on()
        self.flag("fury_cooldown_refuses", a2["holding"] is None and a2["stacks"] == 10 and a2["mana"] >= b2["mana"] - 1, f"{r2} | {self.spent(b2, a2)}")
        # party: locked
        self.gen("solo off")
        self.ready(10)
        b3, r3, a3 = self.fury_on()
        x0, y0 = self.pos()   # after the cast: its own swing may step
        self.gl("input", 1000, 1, 0)
        time.sleep(1.2)
        x1, y1 = self.pos()
        a4 = self.st()
        self.flag("fury_party_locked", a3["holding"] is not None and a3["locked"] and a3["held_locked"] and abs(x1 - x0) + abs(y1 - y0) < 3,
                  f"{r3} | locked {a3['locked']}, moved {abs(x1 - x0) + abs(y1 - y0):.1f} px while held; {a4['raw'][-120:]}")
        end = self.wait_hold_end(STUN[lf] / 1000 + 3)
        self.gl("input", 600, 1, 0)
        time.sleep(0.8)
        x2, y2 = self.pos()
        self.flag("fury_party_unlocked", not end["locked"] and abs(x2 - x1) + abs(y2 - y1) > 10, f"moved {abs(x2 - x1) + abs(y2 - y1):.1f} px after; {end['raw'][-120:]}")
        self.gen("solo auto")
        self.flag("fury_no_errors", not self.errors_since(mark), str(self.errors_since(mark)[:3]))
        self.clear()

    # --- every boss
    def one_boss(self, rel):
        row = {"boss": rel.split("/")[-1].replace(".unit", ""), "spawned": False, "held": False, "refused": "", "cut": None,
               "moved": None, "cd": None, "beams": None, "kept": None, "errors": []}
        mark = len(self.g.read_log())
        self.clear()
        self.origin_back()
        u = self.unit_at(rel, 110, 0, wait=1.0)
        if not u:
            row["errors"].append("no unit")
            return row
        row["spawned"] = True
        # let it fight: its attacks start (god mode on)
        time.sleep(3.0)
        self.fury_unit(row, u, rel.split("/")[-1].replace(".unit", ""), mark)
        self.clear()
        return row

    def fury_unit(self, row, u, name, mark, wait_solid=0.0):
        """The Fury on the live boss unit u (a `near`/`unitsof` entry) and what it did: held or
        refused, the attack cut, standing still, the cooldown, the cost, armor 0, the beams,
        errors since mark; filled into row. wait_solid: seconds to keep trying a boss refused as
        "untargetable" (HoH1's Councilors and Vampire Lord drift untouchable between casts and
        stand solid only while casting)."""
        self.ready(10)
        # the boss may have moved off (a flying spirit, plan-generosity-bosses 20261027-013012: four
        # spirits out of the 250 range read "no target"): stand 100 px from it and aim at it
        def aim_at():
            v = self.unit(u["unit"], 3000, name)
            if not v or v.get("dead"):
                return None, "fury"
            x, y = self.pos()
            d = max(1.0, ((v["x"] - x) ** 2 + (v["y"] - y) ** 2) ** 0.5)
            if d > 160:
                self.gl("teleport", round(v["x"] - (v["x"] - x) / d * 100, 1), round(v["y"] - (v["y"] - y) / d * 100, 1))
                time.sleep(0.3)
                v = self.unit(u["unit"], 3000, name) or v
            x, y = self.pos()
            return round(d), f"fury {round(v['x'] - x)} {round(v['y'] - y)}"

        row["dist"], aim = aim_at()
        b = self.st()
        r = self.gen(aim)
        time.sleep(0.5)
        a = self.st()
        for _ in range(5):
            if a["holding"] is not None or not any(k in (a["last"] or "") for k in ("before the castpoint", "out of reach", "no target")):
                break
            # the boss's hit cut the paladin's own cast, or the boss is mid-dive or tunnelling (no
            # body), or it flew off: stacks kept, find it again and once more (a stale aim missed the
            # diving spirits, plan-generosity-bosses 20261027-021757)
            row.setdefault("retried", []).append(a["last"])
            time.sleep(0.8)
            self.ready(10)
            _, aim = aim_at()
            b = self.st()
            r = self.gen(aim)
            time.sleep(0.5)
            a = self.st()
        end = time.time() + wait_solid
        # the command's own reply: "cast refused ... untargetable". The status line's last refusal
        # stays "untargetable" after a cast that started and lands at its cast point, and a retry
        # then reset the cooldown of the hold that landed (plan-generosity-hoh1 20261028-165541)
        while a["holding"] is None and "cast refused" in (r or "") and "untargetable" in r and time.time() < end:
            # it drifts: try again until a cast stands it solid
            row["solid_tries"] = row.get("solid_tries", 0) + 1
            time.sleep(0.4)
            self.ready(10)
            _, aim = aim_at()
            b = self.st()
            r = self.gen(aim)
            time.sleep(0.5)
            a = self.st()
        row["held"] = a["holding"] is not None
        if not row["held"]:
            row["refused"] = a["last"] or r
            row["kept"] = self.kept(b, a)
        else:
            row["cd"] = a["cd"]
            row["boss_cd"] = a["cdmax"] == 60000 and 55000 <= (a["cd"] or 0) <= 60000
            row["spent"] = a["stacks"] == 0 and b["mana"] - a["mana"] >= 60
            p0 = self.unit(u["unit"], 1500, name)
            casting, moved = [], 0.0
            for _ in range(5):
                time.sleep(0.45)
                s = self.st()
                if s["holding"] is None:
                    break
                casting.append(None if s["bodiless"] else s["casting"])
                if s["casting_names"]:
                    row.setdefault("casting_names", []).append(s["casting_names"])
                p1 = self.unit(u["unit"], 1500, name)
                if p0 and p1:
                    moved = max(moved, abs(p1["x"] - p0["x"]) + abs(p1["y"] - p0["y"]))
            row["casting"] = casting
            row["cut"] = any(c is not None for c in casting) and all(c == 0 for c in casting if c is not None)
            row["moved"] = round(moved, 1)
            row["armor0"] = a["armormul"] == 0 and a["resmul"] == 0
            self.wait_hold_end(6)
        log = self.g.read_log()[mark:]
        beams = re.findall(r"fury strikes on \d+: (\d+) beam", log)
        row["beams"] = int(beams[0]) if beams else None
        row["errors"] = self.errors_since(mark)[:3]

    # --- Pelor's favour (mods/farming): crops grow twice as fast, wild plots twice as often
    def farm(self):
        self.setup_gen("farm")
        self.hwp("set farm.debug 1", 0.5)
        c = self.hwp("farm chance", 0.5, until="wild chance")
        m = re.findall(r"wild chance (\d+)%", c)
        self.flag("farm_chance", bool(m) and int(m[-1]) == 70 and "pelor's favour" in c, f"{c.strip()[-80:]!r} (farm.run_chance 35)")
        self.set_gold(2000)
        self.hwp("farm buy cabbage", 0.5)
        self.hwp("farm plant 1 cabbage", 0.5)
        planted0 = re.findall(r"Planted: (.*)", self.hwp("farm", 0.5, until="Farm:"))
        mark = len(self.g.read_log())
        g = self.hwp("farm grow", 0.5, until="runs counted")
        planted1 = re.findall(r"Planted: (.*)", self.hwp("farm", 0.5, until="Farm:"))
        said = "pelor's favour: the crops grew twice as fast" in self.g.read_log()[mark:]
        # an unwatered cabbage (2 runs to grow) grows 2 in one run: ready
        self.flag("farm_growth", "1:2" in g and "pelor's favour" in g and said and bool(planted1) and "ready" in planted1[-1],
                  f"{planted0[-1] if planted0 else ''!r} -> {planted1[-1] if planted1 else ''!r}; {g.strip()[-80:]!r}; logged {said}")

    def origin_back(self):
        sx, sy = getattr(self, "start", (None, None))
        if sx is None:
            self.start = self.pos()
            return
        x, y = self.pos()
        if abs(x - sx) > 2 or abs(y - sy) > 2:
            self.gl("teleport", round(sx, 1), round(sy, 1))
            time.sleep(0.3)

    def bosses(self, only=""):
        self.setup_gen("boss")
        if not self.enter_floor("boss"):
            return
        self.start = self.pos()
        rels = [r for r in BOSSES if not only or any(o in r for o in only.split(","))]
        rows = []
        for rel in rels:
            try:
                rows.append(self.one_boss(rel))
            except Exception as e:
                rows.append({"boss": rel, "errors": [repr(e)]})
            self.notes.append(f"boss {rows[-1]}")
        self.boss_flags("boss", rows)

    def boss_flags(self, k, rows):
        held = [r for r in rows if r.get("held")]
        refused = [r for r in rows if r.get("spawned") and not r.get("held")]
        self.flag(k + "_spawned", all(r.get("spawned") for r in rows), str([r["boss"] for r in rows if not r.get("spawned")]))
        self.flag(k + "_held_most", len(held) >= len(rows) * 2 // 3, f"held {len(held)} of {len(rows)}; refused {[(r['boss'], r['refused']) for r in refused]}")
        # a refusal is by design only for a boss that can't be targeted or buffed right then (the
        # burrowed Serpent, the Shadow Face): every other boss is held
        design = ("untargetable", "immune to buffs", "invulnerable", "out of reach")
        self.flag(k + "_refused_by_design", all(any(k in (r.get("refused") or "") for k in design) for r in refused),
                  str([(r["boss"], r["refused"]) for r in refused if not any(k in (r.get("refused") or "") for k in design)]))
        self.flag(k + "_refusal_keeps", all(r.get("kept") for r in refused), str([(r["boss"], r.get("kept")) for r in refused]))
        self.flag(k + "_attack_cut", all(r.get("cut") for r in held), str([(r["boss"], r.get("casting")) for r in held if not r.get("cut")]))
        self.flag(k + "_stays", all((r.get("moved") or 0) < 4 for r in held), str([(r["boss"], r.get("moved")) for r in held if (r.get("moved") or 0) >= 4]))
        self.flag(k + "_cooldown_60", all(r.get("boss_cd") for r in held), str([(r["boss"], r.get("cd")) for r in held if not r.get("boss_cd")]))
        self.flag(k + "_spent", all(r.get("spent") for r in held), str([r["boss"] for r in held if not r.get("spent")]))
        self.flag(k + "_armor_0", all(r.get("armor0") for r in held), str([r["boss"] for r in held if not r.get("armor0")]))
        self.flag(k + "_beams", all((r.get("beams") or 0) >= 4 for r in held), str([(r["boss"], r.get("beams")) for r in held]))
        self.flag(k + "_no_errors", not any(r.get("errors") for r in rows), str([(r["boss"], r["errors"]) for r in rows if r.get("errors")]))

    # --- the Serpents of Demise on their own floor (issue #34)
    def serpent_floor(self):
        """dark_citadel floor 18 (levels/boss_bone_serpent.lvl) started by its own BossStart
        script; returns the live serpent heads (TransferDamageActor) and body segments
        (BossWormSegment) within 5000 px."""
        r = self.gl("mission", "dark_citadel", 18)
        ok = bool(r.get("ok")) and str(r.get("level", "")).endswith("boss_bone_serpent.lvl") and self.wait_phase("mission")
        self.flag("srp_floor", ok, str(r))
        if not ok:
            return False
        time.sleep(3)
        if not self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"):
            self.hwp("god", 0.4)
        ws = self.gl("wsexec", "ScriptLink", "BossStart")
        self.flag("srp_start", ws.get("ok") is True, str(ws))
        return ws.get("ok") is True

    def serpent_parts(self):
        # filtered: `actors` lists at most 32, and the floor has more
        heads = [a for a in self.gl("actors", 5000, "TransferDamageActor").get("actors", []) if not a.get("dead")]
        segs = [a for a in self.gl("actors", 5000, "BossWormSegment").get("actors", []) if not a.get("dead")]
        return heads, segs

    def pick_at(self, a):
        x, y = self.pos()
        t = self.gen(f"pick {round(a['x'] - x)} {round(a['y'] - y)}")
        m = re.search(r"gen: pick (none|(\d+) (\S+) (\S+)); (holds|refused: [^;\n]*)(?:; via (\d+))?", t)
        if not m:
            return {"raw": t[-120:]}
        return {"aimed": a["unit"], "picked": int(m.group(2)) if m.group(2) else None,
                "picked_name": (m.group(3) or "none").rsplit("/", 1)[-1], "picked_kind": m.group(4),
                "verdict": m.group(5).strip(), "via": int(m.group(6)) if m.group(6) else None}

    def serpent_probe(self, seconds=40, setup=True):
        """What the Fury would pick and say, aimed at each serpent head and at body segments,
        every ~1.5 s of the real fight."""
        if setup:
            self.setup_gen("srp")
            if not self.serpent_floor():
                return []
        rows = []
        end = time.time() + seconds
        while time.time() < end:
            heads, segs = self.serpent_parts()
            for a in heads:
                rows.append(dict(at="head", scene=a.get("scene"), targetable=a.get("targetable"), **self.pick_at(a)))
            for a in segs[:2]:
                rows.append(dict(at="segment", **self.pick_at(a)))
            time.sleep(1.5)
        self.out["srp_probe"] = rows
        def tally(at):
            t = {}
            for r in rows:
                if r.get("at") == at:
                    k = f"{r.get('picked_kind')}: {r.get('verdict')}"
                    t[k] = t.get(k, 0) + 1
            return t
        self.notes.append(f"serpent heads: {tally('head')}")
        self.notes.append(f"serpent segments: {tally('segment')}")
        return rows

    def serpent_fury(self):
        """Issue #34: Pelor's Fury on the real Serpents of Demise. Aimed at the body, a segment
        stands for its serpent: the pick is the head (via the segment), held when the head can
        be (surfaced), its own reason when not (underground); aimed at a surfaced head, a segment
        over it no longer takes the pick. Then a real cast through the skill aimed at the body
        holds the head (60 s boss cooldown, Blessing spent)."""
        self.setup_gen("srp")
        if not self.serpent_floor():
            return
        rows = self.serpent_probe(30, setup=False)
        segs = [r for r in rows if r.get("at") == "segment" and r.get("picked") is not None]
        heads = [r for r in rows if r.get("at") == "head" and r.get("picked") is not None]
        seg_bad = [r for r in segs if r.get("picked_kind") == "BossWormSegment"]
        self.flag("srp_body_is_serpent", len(segs) >= 6 and not seg_bad,
                  f"{len(segs)} body aims; still a segment: {seg_bad[:4]}")
        seg_held = [r for r in segs if r.get("verdict") == "holds" and r.get("picked_kind") == "TransferDamageActor"]
        # via: the pick went through the segment (none when the head itself was nearest the aim)
        self.flag("srp_body_holds", any(r.get("via") for r in seg_held),
                  f"{len(seg_held)} of {len(segs)} body aims hold the head, "
                  f"{sum(1 for r in seg_held if r.get('via'))} through the segment, e.g. {seg_held[:2]}")
        stolen = [r for r in heads if r.get("targetable") and r.get("picked_kind") == "BossWormSegment"]
        self.flag("srp_head_not_stolen", len(heads) >= 6 and not stolen, f"{len(heads)} head aims; a segment took {stolen[:3]}")
        # the real cast, aimed at a body segment whose pick holds right now
        mark = len(self.g.read_log())
        held_head, tries, said, seen = None, 0, "", {}
        # a head is up a few seconds at a time, so the pick is looked at again right before the
        # cast (a head that dove in between was refused once, 20261029-052347)
        end = time.time() + 90
        self.ready(10)
        while time.time() < end and held_head is None:
            _, segs_now = self.serpent_parts()
            # newest first: the trail a moving head leaves (the level also places static,
            # ownerless dive segments that stand for nothing)
            for a in sorted(segs_now, key=lambda v: -v["unit"])[:12]:
                pk = self.pick_at(a)
                k = f"{pk.get('picked_kind')}: {pk.get('verdict')}"
                seen[k] = seen.get(k, 0) + 1
                if pk.get("verdict") != "holds" or pk.get("picked_kind") != "TransferDamageActor":
                    continue
                x, y = self.pos()
                d = ((a["x"] - x) ** 2 + (a["y"] - y) ** 2) ** 0.5
                if d > 200:
                    self.gl("teleport", round(a["x"] - (a["x"] - x) / d * 120, 1), round(a["y"] - (a["y"] - y) / d * 120, 1))
                    time.sleep(0.2)
                    x, y = self.pos()
                    pk = self.pick_at(a)
                    if pk.get("verdict") != "holds" or pk.get("picked_kind") != "TransferDamageActor":
                        continue
                tries += 1
                said = self.gen(f"fury {round(a['x'] - x)} {round(a['y'] - y)}")
                time.sleep(0.6)
                s = self.st()
                if s["holding"] is not None:
                    held_head = (s, pk, a)
                    break
                self.ready(10)
            if held_head is None:
                time.sleep(0.5)
        log = self.g.read_log()[mark:]
        on = re.search(r"pelor's fury on (\d+) \((\S+)\) boss", log)
        ok = held_head is not None and on is not None and on.group(2).endswith("boss_serpent.unit")
        detail = f"{tries} cast(s); {said.strip()[-160:]!r}; log {on.group(0) if on else None}; body picks seen {seen}"
        if held_head:
            s, pk, a = held_head
            detail += f"; holding {s['holding']} aimed at segment {a['unit']} (pick {pk})"
        self.flag("srp_cast_holds_head", ok, detail)
        if held_head:
            s = held_head[0]
            self.flag("srp_cast_boss_cd", (s.get("cdmax") or 0) >= 60000 and (s.get("stacks") or 0) == 0,
                      f"cd {s.get('cd')}/{s.get('cdmax')}, blessing {s.get('stacks')}")
            self.wait_hold_end(8)
        self.flag("srp_no_errors", not self.errors_since(mark), str(self.errors_since(mark)[:3]))
        self.g.shot("fury-serpent")

    # --- the HoH1 tower's bosses
    def hoh1(self, only=""):
        self.setup_gen("h1")
        floors = [(i, lvl) for i, _, lvl in self.levels() if level_name(lvl) in RECIPES
                  and (not only or level_name(lvl) in only.split(","))]
        self.flag("hoh1_floors", bool(floors), str(floors))
        rows = []
        for i, lvl in floors:
            name = level_name(lvl)
            files = RECIPES[name][1]
            mark = len(self.g.read_log())
            try:
                found, r, started = self.start_boss(i, lvl)
            except Exception as e:
                found, r, started = [], {"error": repr(e)}, []
            if not found:
                rows.append({"boss": name, "spawned": False, "errors": [f"{r} {started}"]})
                self.notes.append(f"hoh1 {rows[-1]}")
                continue
            # the boss fights a while first, as on a vanilla floor
            time.sleep(3.0)
            # unitsof replies per file: which boss each unit is
            r = self.gl("unitsof", *files)
            for f, u in [(f, u) for f in files for u in (r.get(f) or {}).get("units") or []]:
                unit = f.rsplit("/", 1)[-1].replace(".unit", "")
                row = {"boss": f"{name}:{unit}", "spawned": True, "held": False, "refused": "", "cut": None,
                       "moved": None, "cd": None, "beams": None, "kept": None, "errors": []}
                try:
                    self.fury_unit(row, u, unit, mark, wait_solid=20.0)
                except Exception as e:
                    row["errors"].append(repr(e))
                rows.append(row)
                self.notes.append(f"hoh1 {row}")
                mark = len(self.g.read_log())
            self.g.shot(f"hoh1-{name}")
        self.boss_flags("hoh1", rows)

    # --- stacks
    def stacks_section(self):
        self.setup_gen("stk")
        if not self.enter_floor("stk"):
            return
        self.clear()
        lb = self.lvl.get(PB, 2)
        # Lay on Hands on oneself, alone: +1 (and the heal scaled by the stacks it had)
        self.gl("hurt", 0.4)
        self.stacks(0)
        self.gen("cd")
        b = self.st()
        presses, spent, button = self.cast_skill("stk_loh", LOH, 40, aim=(0, 0))
        time.sleep(0.4)
        a = self.st()
        self.flag("stk_loh_self", presses > 0 and a["stacks"] == 1 and a["loh"] == (b["loh"] or 0) + 1, f"{presses} press(es) on {button}: {b['stacks']} -> {a['stacks']}, loh {a['loh']}")
        # the shared 2 s cooldown: two brutes killed by one Blessed Strike give one stack
        time.sleep(2.2)
        self.gl("spawn", DUMMY, 34, -10)
        self.gl("spawn", DUMMY, 34, 10)
        time.sleep(0.6)
        self.gl("kill", 200, "bandit_brute", 0.01)
        b2 = self.st()
        self.cast_skill("stk_bs", BS, 20, aim=(1, 0))
        time.sleep(0.5)
        a2 = self.st()
        two = (a2["kills"] or 0) - (b2["kills"] or 0) + (a2["blocked"] or 0) - (b2["blocked"] or 0)
        self.flag("stk_shared_cd", a2["stacks"] == b2["stacks"] + 1 and (a2["blocked"] or 0) >= (b2["blocked"] or 0) + 1,
                  f"two kills in one swing: stacks {b2['stacks']} -> {a2['stacks']}, blocked {b2['blocked']} -> {a2['blocked']}, kills {b2['kills']} -> {a2['kills']} ({two} sources)")
        # a Blessed Strike kill after the cooldown: +1
        time.sleep(2.2)
        self.clear()
        self.unit_at(DUMMY, 50)
        self.gl("kill", 200, "bandit_brute", 0.01)
        b3 = self.st()
        self.cast_skill("stk_bs2", BS, 20, aim=(1, 0))
        time.sleep(0.5)
        a3 = self.st()
        self.flag("stk_bs_kill", a3["stacks"] == b3["stacks"] + 1 and a3["kills"] == (b3["kills"] or 0) + 1, f"{b3['stacks']} -> {a3['stacks']}, kills {a3['kills']}")
        # the multiplier and Blessed Strike scaled
        self.stacks(10)
        s = self.st()
        self.flag("stk_mul", abs((s["mul"] or 0) - round(1000 * (1 + 10 * PCT[lb]))) <= 1, f"mul {s['mul']} at 10 (pct {PCT[lb]})")
        self.clear()
        self.unit_at(DUMMY, 50)
        self.gen("cd")
        self.cast_skill("stk_bs3", BS, 20, aim=(1, 0))
        time.sleep(0.4)
        s2 = self.st()
        self.flag("stk_bs_scaled", (s2["bs_scaled"] or 0) > (s["bs_scaled"] or 0), f"bs scaled {s['bs_scaled']} -> {s2['bs_scaled']}")
        # the cap
        self.stacks(15)
        self.flag("stk_cap", self.st()["stacks"] == 10, "stacks 15 asked")
        # Conviction: melee hits until it gives mana (10% at level 1): +1, then 6 s before the next
        self.stacks(0)
        self.gen("cd")
        self.gl("cheat", "cht_give_mana", -500)
        self.clear()
        self.unit_at(DUMMY, 30)
        self.gl("kill", 200, "bandit_brute", 1.0)
        b4 = self.st()
        conv_seen = False
        for _ in range(70):   # 10% a hit: 30 swings found none in 20261027-015913
            self.gl("input", 400, 0, 0, 1, 0, "main")
            time.sleep(0.45)
            self.gl("kill", 200, "bandit_brute", 1.0)
            s4 = self.st()
            if (s4["conv"] or 0) > (b4["conv"] or 0):
                conv_seen = True
                break
        self.flag("stk_conviction", conv_seen and s4["stacks"] == 1 and (s4["convcd"] or 0) > 4000, f"conv {b4['conv']} -> {s4['conv']}, stacks {s4['stacks']}, convcd {s4['convcd']}")
        self.clear()
        # the carry to the next floor
        self.stacks(7)
        self.next_floor()
        self.gl("kill", 6000, "tag:enemy")
        time.sleep(0.5)
        self.flag("stk_carry", self.st()["stacks"] == 7, "7 before the exit")
        # the player's death resets
        r0 = self.st()["resets"] or 0
        self.god(False)
        self.gl("cheat", "ply_kill")
        time.sleep(1.5)
        self.gl("cheat", "cht_revive")
        time.sleep(1.5)
        self.god(True)
        s5 = self.st()
        self.flag("stk_death_reset", s5["stacks"] == 0 and (s5["resets"] or 0) > r0, f"after the death: stacks {s5['stacks']}, resets {r0} -> {s5['resets']}")
        # town resets
        self.stacks(6)
        self.gl("abort")
        self.wait_phase("town", 90)
        time.sleep(1.5)
        self.flag("stk_town_reset", self.st()["stacks"] == 0, "6 before town")

    # --- orbs
    def orbs(self):
        self.setup_gen("orb")
        for orb, n in (("hwp_pal_pf_blinding_sun", 1), ("hwp_pal_pf_holy_sacrifice", 1), ("hwp_pal_pb_display_of_generosity", 2)):
            self.gl("orb", orb, n)
        time.sleep(0.4)
        binds = {"bs-buff": self.bind(PF, "bs-buff"), "hs-stacks": self.fbind(PF, "hs-stacks")}
        binds["dg-max"] = self.fbind(PB, "dg-max")
        self.flag("orb_binds", "blindness_minor" in str(binds.get("bs-buff")) and binds.get("hs-stacks") == 1 and binds.get("dg-max") == 3, str(binds))
        if not self.enter_floor("orb"):
            return
        self.clear()
        # Blinding Sun: the brute is blind when the stun ends
        self.ready(10)
        self.unit_at(DUMMY, 90)
        b, r, a = self.fury_on()
        end = self.wait_hold_end(6)
        # the blindness: a debuff on the brute after the Fury's ended, up to 4 s left (unnamed)
        ab = self.gl("actorbuffs", 300, "bandit_brute").get("actors") or []
        bl = [(x.get("name"), x.get("left"), x.get("debuff")) for act in ab for x in act.get("buffs") or []]
        self.flag("orb_blinding_sun", (end["blinds"] or 0) >= 1 and any(d and 1500 < (lf or 0) <= 4000 for _, lf, d in bl),
                  f"{r} | blinds {end['blinds']}, brute buffs {bl}")
        self.clear()
        # Holy Sacrifice: the brute dies while held: half the cooldown, +1 stack
        self.ready(10)
        self.unit_at(DUMMY, 90)
        b, r, a = self.fury_on()
        self.gl("kill", 300, "bandit_brute")
        time.sleep(0.6)
        s = self.st()
        self.flag("orb_holy_sacrifice", a["holding"] is not None and (s["sacrifices"] or 0) >= 1 and s["holding"] is None and s["stacks"] == 1
                  and 10000 <= (s["cd"] or 0) <= 15500, f"{r} | sacrifices {s['sacrifices']}, stacks {s['stacks']}, cd {s['cd']} (30000 halved)")
        self.clear()
        # Descendent of Pentival: a dragon trinket's stats grow with the stacks
        self.gl("orb", "hwp_pal_pb_descendent_of_pentival", 1)
        self.gl("cheat", "cht_give_specific_trinket", "dragon_heart")
        time.sleep(0.4)
        self.stacks(0)
        time.sleep(0.3)
        s0 = self.gl("benchstats")
        p0 = self.st()["pentival"] or 0
        self.stacks(10)
        time.sleep(0.4)
        s10 = self.gl("benchstats")
        st10 = self.st()
        diff = {k: (s0.get(k), s10.get(k)) for k in set(s0) | set(s10)
                if isinstance(s0.get(k), (int, float)) and isinstance(s10.get(k), (int, float)) and abs(s10[k] - s0[k]) > 1e-6}
        self.flag("orb_pentival", (st10["pentival"] or 0) > p0 and bool(diff), f"runs {p0} -> {st10['pentival']}; {st10['raw'][-160:]}; stats changed {diff}")


def run(p, sections="smoke,refusals,fury,stacks_section,orbs,bosses", only="", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            if s in ("bosses", "hoh1"):
                getattr(c, s)(only)
            else:
                getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
