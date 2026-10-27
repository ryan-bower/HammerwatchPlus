"""Test-plan checks for the Devil Forgemaster (the Priest's 4th spec, mods/specs).

A level-20 Priest takes hwp_priest_forgemaster, learns Necrotic Resurrection and Call of Heresy
and casts in an emptied Bandit Keep floor with god mode on. `hwp forge` (Forgemaster.as CmdForge)
is the debug command: the host drops any raisable enemy's intact body beside the player, a raise
or a Penance can be done at once, Heresy set, the risen listed with their movement class.

Sections:
- forge: the character, the skills, the orbs' binds, the free Divine Favor, the body rolls on
  the floor's own deaths.
- raise_all: every unit of RISEN_RELS (Forgemaster_Units.as) in turn: a body, a raise, the
  risen stands (hp, max hp, movement class), it hits a bandit brute put beside it (hp lost in
  4 s), it teleports after the priest (the 350 leash) and walks with it, no script error. The
  per-unit table is in the notes; the flags count the failures.
- bosses: the same for the boss bodies only (they are in raise_all too: the flags here are
  theirs alone, with the longer 10 s channel checked on one of them).
- penance: the removal per rank and body kind (table + 1 elite + 2 boss), the 50 mana, no
  cooldown, Divine Favor spent.
- heresy: the block at 5, the overshoot, the carry to the next floor, the reset in town.
- lunge: the forced lunge's effects, then the real roll (Heresy x coh-lunge) over many bodies.
- decay: 1% every 3 s to death, Rot Bloom on the way out; the cap kills the oldest.
- channel_lock (fix-forgemaster-channels): the Penance first, then a boss raise (10 s): the facing
  holds against a turned aim, a dash press is refused (and logged) and moves nothing, the beam
  and the pulses run, the bar is drawn; the dash is free again after; the same for a Penance.
- penance_icon: the skill's icon is the Penance one at max Divine Favor, the raise one below.
- pyre_heresy: a brazier is usable (CanUse) with Heresy and no curse and removes ps-reduce
  Heresy; not usable with neither; the large WorldScript pyre does the same when the floor (or
  a fabricated pyre prefab) has one.
- orb_boss: Deeper Depravity's epic rank reads dd-boss 1.0 and every boss death leaves a body.
- risen_speed (fix-specs-risen-speed): a risen's follower movement runs (speed >= 4.5, roaming 1.0,
  run-back 1.4x; `hwp risen`), it runs back to a priest 260 px away, and it damages a brute 150 px
  east, then one west, within 5 s each.
- risen_look (fix-specs-risen-look): the generated files (npc material and dot, the marker ring;
  a body npc-noxray, no dot, no ring, shoot-through; the wisp body's dead core), the body's grey
  log line and no map icon, the risen's map icon, the wisp body standing (a shot follows).
- body_passthrough (fix-specs-body-passthrough): a brute's body 50 px east between the priest and a
  breakable target at 110 px: the main attack and Holy Blast damage the target through it.
- risen_floors (fix-specs-risen-floors): two risen at 60% HP come along to the next floor at that
  HP; mods/summons' floor restore line and no 'Exception when saving summons'.
"""
import re
import time
from pathlib import Path

from gamelab.bots.plan_specs import Checks as Base, DUMMY

NR = "hwp_pri_necrotic_resurrection"
COH = "hwp_pri_call_of_heresy"
SUB = "hwp_priest_forgemaster"
STACKS = "players/hwp/specs/stacks_specs.sval:"
RISEN = "forgemaster/risen"
TARGET = "doodads/generic/target_dummy_breakable.unit"  # 500 hp, stands still, enemy team
# skill classes that are not attacks: retargeting, buffs for friends, death and damage triggers
PASSIVE_SKILLS = {"CompositeActorUtilitySkill", "CompositeActorFriendlySkill", "CompositeActorTriggeredSkill"}
ROOT = Path(__file__).resolve().parents[2]
UNITS_AS = ROOT / "mods/specs/scripts/HWP/Specs/Forgemaster_Units.as"
BODIES = ROOT / "mods/specs/players/hwp/specs/forgemaster/bodies"


def risen_rels():
    """The raisable units, from the generated list; {rel: (elite, boss)} from the body units."""
    text = UNITS_AS.read_text(encoding="utf-8")
    block = text[text.find("const array<string> RISEN_RELS"):]
    rels = re.findall(r'"([^"]+\.unit)"', block[:block.find("};")])
    out = {}
    for rel in rels:
        if not (BODIES / rel).is_file():   # a generator bug, never a quiet "not elite, not boss"
            raise FileNotFoundError(f"no body unit for {rel}: run tools/make_forgemaster_risen.py")
        body = (BODIES / rel).read_text(encoding="utf-8")
        out[rel] = ('<bool name="elite">true</bool>' in body, '<bool name="boss">true</bool>' in body)
    return out


class Checks(Base):
    def forge_status(self):
        return self.hwp("forge", 0.3, until="forge:")

    def fnum(self, text, label):
        m = re.findall(re.escape(label) + r" (-?\d+)", text)
        return int(m[-1]) if m else None

    def heresy(self):
        return self.fnum(self.forge_status(), "heresy")

    def set_heresy(self, n):
        return self.fnum(self.hwp(f"forge heresy {n}", 0.3, until="forge:"), "heresy")

    def body(self, rel, dx=40, dy=0):
        r = self.hwp(f"forge body {rel} {dx} {dy}", 0.3, until="forge:")
        m = re.findall(r"forge: body \S+ unit (-?\d+)", r)
        return int(m[-1]) if m else -1

    def raise_now(self):
        return self.hwp("forge raise now", 0.4, until="forge:")

    def risen(self, r=900):
        return [u for u in self.gl("near", r, RISEN).get("units") or [] if not u.get("dead")]

    def risen_lines(self):
        """[{name, id, hp, max, x, y, dist, move, target}] from `hwp forge risen`."""
        txt = self.hwp("forge risen", 0.3, until="forge risen")
        out = []
        for m in re.finditer(r"\| (\S+) id (\d+) hp (-?\d+) max (-?\d+) at (-?\d+) (-?\d+) dist (-?\d+) move (\S+) target (\S+) dead (\d)", txt):
            out.append({"name": m.group(1), "id": int(m.group(2)), "hp": int(m.group(3)) / 1000, "max": int(m.group(4)),
                        "x": int(m.group(5)), "y": int(m.group(6)), "dist": int(m.group(7)), "move": m.group(8),
                        "target": m.group(9), "dead": m.group(10) == "1"})
        return out

    def cull(self):
        self.hwp("forge cull", 0.3, until="forge:")
        self.gl("kill", 900, DUMMY)
        self.gl("kill", 900, "target_dummy")
        time.sleep(0.3)

    def origin(self):
        """The arena origin: the mission start, and the priest put back on it. Reading the priest's
        place instead drifted a few px per unit (the walk, the teleport back), and in plan-forgemaster
        20261022-064242 the body spot 60 px right of it had wandered onto a level obstacle by the 47th
        unit: fifty risen sat 13 px off it with no target, their must-see aim ray blocked at 4 px."""
        sx, sy = getattr(self, "start", (None, None))
        if sx is None:
            return self.pos()
        x, y = self.pos()
        if abs(x - sx) > 2 or abs(y - sy) > 2:
            self.gl("teleport", round(sx, 1), round(sy, 1))
            time.sleep(0.3)
        return sx, sy

    def arena_terrain(self, key):
        """The occupancy grid around the origin, in the notes: the body spot (+60, 0) must be free."""
        self.origin()
        t = self.gl("terrain", 110, 10)
        rows = t.get("rows") or t.get("grid") or t
        self.notes.append(f"{key} terrain at {self.pos()} step 10: {rows}")

    def dummies(self, r=400):
        """The brutes within r: the vanilla unit only, never a risen bandit brute."""
        return [u for u in self.gl("near", r, DUMMY).get("units") or [] if RISEN not in u.get("name", "")]

    def targets(self, r=400):
        """The breakable target dummies within r (hp, dead)."""
        return self.gl("near", r, "target_dummy").get("units") or []

    def target_hit(self, before):
        """Did a target dummy alive in `before` lose HP or die."""
        now = {u["unit"]: u for u in self.targets()}
        for u in before:
            v = now.get(u["unit"])
            if v is None or v.get("dead") or v.get("hp", 1) < u.get("hp", 1) - 0.001:
                return True
        return False

    def errors_since(self, mark):
        """Script errors since mark. Not every line with "error" in it: a level load logs the
        vanilla [WRN] "SValue param error: missing string 'description' (file: tweak/pets.sval)"
        (pf-plan-forgemaster-units 20261027-044247), and floor loads log vanilla [ERR] lines (the
        HUD widgets, DungeonGenerationCommands.as), as plan_generosity.errors_since says. So only
        exceptions, errors that name an HWP mod or the specs scripts, and SValue param errors in
        HWP's own files (players/hwp/..., the pyre.sval `blocking` kind) count."""
        new = self.g.read_log()[mark:]
        return [ln.strip()[:160] for ln in new.splitlines()
                if "Script exception" in ln or ("[ERR]" in ln and any(k in ln for k in ("HWP", "Specs/")))
                or ("SValue param error" in ln and "hwp/" in ln.lower())]

    def setup_forge(self, key="forge", levels=0):
        self.setup(key, "priest", SUB, [NR, COH])
        for _ in range(levels):
            self.gl("skill", NR, 1)
            self.gl("skill", COH, 1)

    def to_arena(self, tag):
        if not self.enter_floor(tag):
            return False
        self.cull()
        return True

    # --- forge: the character and the floor
    def forge(self):
        mark = len(self.g.read_log())
        self.setup_forge("forge")
        binds = {k: self.bind(NR, k) for k in ("nr-hp-pct", "nr-dmg-pct", "nr-count", "nr-penance", "ps-reduce", "rb-dmg")}
        binds.update({k: self.bind(COH, k) for k in ("coh-body", "coh-dmg", "coh-lunge", "dd-elite", "dd-boss", "rl-dmg", "rl-knock")})
        # setup levels both skills to 2 (one SkillUp): level 2's numbers, orbs at 0
        fb = {k: float(v) for k, v in binds.items() if v not in (None, "")}
        self.flag("forge_binds", fb.get("nr-count") == 2 and abs(fb.get("nr-hp-pct", 0) - 0.6) < 1e-3 and abs(fb.get("nr-dmg-pct", 0) - 0.6) < 1e-3
                  and abs(fb.get("coh-body", 0) - 0.04) < 1e-3 and abs(fb.get("coh-dmg", 0) - 0.10) < 1e-3 and fb.get("ps-reduce") == 0
                  and fb.get("rb-dmg") == 0 and fb.get("dd-elite") == 0 and fb.get("rl-dmg") == 0, f"{binds}")
        # the orbs' top levels (orb N: N levels from 0): Pyre uncommon, Rot Bloom rare, Deeper Depravity epic, Ravenous Lunge rare
        self.gl("orb", "hwp_pri_nr_pyre_sacrifice", 2)
        self.gl("orb", "hwp_pri_nr_rot_bloom", 2)
        self.gl("orb", "hwp_pri_coh_deeper_depravity", 3)
        self.gl("orb", "hwp_pri_coh_ravenous_lunge", 2)
        time.sleep(0.5)
        orbs = {k: self.bind(NR, k) for k in ("ps-reduce", "rb-dmg")}
        orbs.update({k: self.bind(COH, k) for k in ("dd-elite", "dd-boss", "rl-dmg", "rl-knock")})
        fo = {k: float(v) for k, v in orbs.items() if v not in (None, "")}
        self.flag("forge_orb_binds", fo.get("ps-reduce") == 3 and abs(fo.get("rb-dmg", 0) - 1.2) < 1e-3
                  and abs(fo.get("dd-elite", 0) - 0.15) < 1e-3 and abs(fo.get("dd-boss", 0) - 1.0) < 1e-3
                  and abs(fo.get("rl-dmg", 0) - 1.5) < 1e-3 and fo.get("rl-knock") == 1, f"{orbs}")
        # the floor: its enemies die with a Forgemaster on it, so every death rolls a body
        mark2 = len(self.g.read_log())
        if not self.enter_floor("forge"):
            return
        time.sleep(1.5)
        log = self.g.read_log()[mark2:]
        st = self.forge_status()
        rolls, bodies = self.fnum(st, "rolls"), self.fnum(st, "bodies")
        self.flag("forge_body_rolls", (rolls or 0) > 20, f"rolls {rolls}, bodies on the floor {bodies} spawned {self.fnum(st, 'spawned')} (3% each)")
        # the free Divine Favor: the hook on the player's Initialize (the floor's load)
        favor = self.fnum(st, "favor")
        skills = self.skills_info() or {}
        self.flag("forge_free_favor", favor is not None and favor >= 0 and "Divine Favor level 1 for free" in self.g.read_log()[mark:],
                  f"favor stacks {favor}, live skills {sorted(skills)}")
        self.cull()
        # a body by hand, the glow on the Forgemaster's screen, a raise through the real cast
        uid = self.body("humans/bandits/bandit_brute.unit")
        time.sleep(0.5)
        st = self.hwp("forge bodies", 0.3, until="forge bodies")
        self.flag("forge_body_glow", uid > 0 and f"| {uid} humans/bandits/bandit_brute.unit" in st and "glow 1" in st, st.strip()[-200:])
        h0 = self.heresy()
        m0 = self.mana_exact()
        presses, spent, button = self.cast_skill("forge", NR, 70, done=lambda: self.has("raising")["raising"].get("on"))
        time.sleep(0.3)
        rb = self.has("raising")["raising"]
        self.flag("forge_cast", presses > 0 and bool(rb.get("on")), f"presses {presses}, raising buff {rb}, mana {m0:.0f} -> {self.mana_exact():.0f}")
        time.sleep(3.5)
        rs = self.risen()
        h1 = self.heresy()
        self.flag("forge_raised", len(rs) == 1 and h1 == (h0 or 0) + 1 and rs[0]["name"].endswith("bandit_brute.unit"),
                  f"risen {[r['name'].split('/')[-1] for r in rs]}, heresy {h0} -> {h1}")
        cd = self.skill_cd(NR)
        self.flag("forge_cooldown", cd is not None and cd > 10000, f"cooldown left {cd}")
        self.cull()

    # --- raise_all / bosses
    def one_unit(self, rel, elite, boss, walk=True):
        """A body, a raise, the checks; a dict row."""
        mark = len(self.g.read_log())
        row = {"unit": rel, "kind": "boss" if boss else "elite" if elite else "", "raised": False, "hit": False, "attacked": False,
               "support": False, "casts": [], "leash": False, "walk": None, "move": "", "hp": None, "max": None, "errors": []}
        x0, y0 = self.origin()
        self.set_heresy(0)   # a lunge roll at high Heresy ate the body (judges_heavy, plan-forgemaster 20261022-022037)
        uid = self.body(rel, 60, 0)
        if uid <= 0:
            row["errors"].append("no body")
            return row
        self.raise_now()
        time.sleep(0.6)
        lines = self.risen_lines()
        if not lines:
            time.sleep(1.0)
            lines = self.risen_lines()
        if lines:
            r = lines[0]
            row.update(raised=not r["dead"], move=r["move"], hp=r["hp"], max=r["max"])
        rid = lines[0]["id"] if lines else -1
        # the leash first, while the risen is whole (a bat or a beetle dies to the brute within the
        # fight window, plan-forgemaster 20261022-064242): 700 px away, the risen is back within 2.5 s
        self.gl("teleport", round(x0 + 700, 1), round(y0, 1))
        time.sleep(2.5)
        near = self.risen(420)
        row["leash"] = bool(near)
        if walk and near:
            # a walk: 1.2 s right, the risen within 350 after it settles
            self.gl("input", 1200, 1, 0)
            time.sleep(2.2)
            row["walk"] = bool(self.risen(350))
        self.gl("teleport", round(x0, 1), round(y0, 1))
        time.sleep(0.8)
        # a brute below the risen (the face aims downward only): hit within the window (6 s; a
        # boss 15 s, its attacks wind up and Arista's spikes land at random), and whom the risen
        # targets meanwhile
        # a boss gets 25 s: the risen Face found the brute 10 s after the raise (the brute spawns after the
        # leash and the walk) and its first spew came 3 s later at plan-forgemaster-bosses 20261022-084131,
        # but not within the 15 s window at plan-forgemaster 20261022-102006 (its spew cooldown is 6-8 s)
        window = 25.0 if boss else 6.0
        self.gl("spawn", DUMMY, 40, 100)
        time.sleep(0.6)
        before = [u for u in self.dummies(400) if not u.get("dead")]
        # a sample a second: the brute's health and place, the risen's place and target at the
        # middle and the end (a brute knocked out of range is not a hit; a dead one is, and so is
        # one that vanished: nothing else removes it from the arena)
        samples, lost, t0 = [], 0.0, time.time()
        while time.time() - t0 < window:
            time.sleep(max(0.0, 1.0 - ((time.time() - t0) % 1.0)))
            # the risen kept whole (its health fraction written back to 1): the question is whether
            # it attacks, and a yellow jacket died to the brute in two seconds (20261022-085643);
            # the decay section measures health on its own
            self.gl("kill", 600, RISEN, 1.0)
            now = {u["unit"]: u for u in self.dummies(1500)}
            t = round(time.time() - t0, 1)
            for u in before:
                v = now.get(u["unit"])
                if v is None:
                    samples.append((t, "gone"))
                    lost = 1.0
                    continue
                hp = v.get("hp", 1)
                samples.append((t, 0.0 if v.get("dead") else round(hp, 3), int(v.get("x", 0)), int(v.get("y", 0))))
                lost = max(lost, 1.0 if v.get("dead") else u.get("hp", 1) - hp)
            if abs((time.time() - t0) - window / 2) < 0.6 or time.time() - t0 >= window - 0.6:
                rl = self.risen_lines()
                if rl:
                    samples.append((t, "risen", rl[0]["x"], rl[0]["y"], rl[0]["target"], rl[0]["hp"]))
                    row["target"] = rl[0]["target"] if row.get("target") in (None, "none") else row["target"]
        row["samples"] = samples
        # the attack skills it started casting meanwhile (hwp forge trace): a risen that fires and
        # misses a lone brute (the fire totem's sweep, Arista's spike fans) still attacks; a unit
        # whose skills are all auras, triggers and buffs (the bannermen) has nothing to attack with
        log = self.g.read_log()[mark:]
        casts = re.findall(r"risen " + str(rid) + r" casts skill (\d+) (\w+)", log)
        row["casts"] = [f"{i}:{t}" for i, t in casts if t not in PASSIVE_SKILLS]
        kinds = re.findall(r"risen " + str(rid) + r" target .*? skills:((?: \d+:\w+(?:\([^)]*\))?)*)", log)
        types = re.findall(r"\d+:(\w+)", max(kinds, key=len, default=""))
        row["skills"] = types
        row["support"] = bool(types) and all(t in PASSIVE_SKILLS or t == "CompositeActorAuraSkill" for t in types)
        row["hit"] = lost > 0.001
        row["attacked"] = row["hit"] or bool(row["casts"])
        row["lost"] = round(lost, 3)
        lines2 = self.risen_lines()
        row["alive_end"] = bool(lines2) and not lines2[0]["dead"]
        self.cull()
        row["errors"] += self.errors_since(mark)[:3]
        return row

    def unit_table(self, key, rels, walk=True):
        rows = []
        for rel, (elite, boss) in rels.items():
            try:
                rows.append(self.one_unit(rel, elite, boss, walk))
            except Exception as e:  # one unit's crash is its own row
                rows.append({"unit": rel, "kind": "boss" if boss else "elite" if elite else "", "raised": False, "hit": False,
                             "attacked": False, "casts": [], "leash": False, "walk": None, "move": "", "errors": [repr(e)[:160]]})
            r = rows[-1]
            self.notes.append(f"{key} {rel}: raised {r['raised']} move {r.get('move')} hp {r.get('hp')} max {r.get('max')} "
                              f"hit {r['hit']} lost {r.get('lost')} casts {r.get('casts')} support {r.get('support')} target {r.get('target')} leash {r['leash']} walk {r['walk']} errors {r['errors']} "
                              f"samples {r.get('samples')}")
        self.out[f"{key}_rows"] = rows
        n = len(rows)
        bad_raise = [r["unit"] for r in rows if not r["raised"]]
        bad_hit = [r["unit"] for r in rows if r["raised"] and not r.get("attacked") and not r.get("support")]
        support = [r["unit"] for r in rows if r.get("support")]
        bad_leash = [r["unit"] for r in rows if r["raised"] and not r["leash"]]
        bad_err = [r["unit"] for r in rows if r["errors"]]
        self.flag(f"{key}_raised", n > 0 and not bad_raise, f"{n - len(bad_raise)}/{n} raised; not: {bad_raise[:20]}")
        self.flag(f"{key}_attack", n > 0 and not bad_hit, f"{n - len(bad_hit)}/{n} attacked (hurt the brute or cast an attack skill) within the window; not: {bad_hit[:30]}; support units with no attack skill: {support}")
        self.flag(f"{key}_leash", n > 0 and not bad_leash, f"{n - len(bad_leash)}/{n} teleported after the priest; not: {bad_leash[:30]}")
        self.flag(f"{key}_no_errors", not bad_err, f"script errors with: {bad_err[:20]}; first: {[r['errors'][0] for r in rows if r['errors']][:5]}")
        return rows

    def raise_all(self):
        self.setup_forge("all", levels=4)   # level 5: 4 risen, 100%: the hit check sees the full damage
        if not self.to_arena("all"):
            return
        rels = risen_rels()
        only = getattr(self, "only", [])
        if only:   # a quick re-test of a few (the `units` kwarg)
            rels = {k: v for k, v in rels.items() if k in only}
        self.notes.append(f"{len(rels)} raisable units, {sum(1 for v in rels.values() if v[1])} bosses, {sum(1 for v in rels.values() if v[0])} elites")
        self.hwp("forge trace on", 0.2)   # the log says which skills each risen casts
        self.arena_terrain("all")
        self.unit_table("all", rels)
        self.hwp("forge trace off", 0.2)

    def near_priest(self):
        """A brute that stands on the god-mode priest: does a risen beside them find and fight it? (In
        plan-forgemaster 20261022-064242 fifty risen idled with no target while the brute hugged the
        priest; the trace line's `foes:` says what the must-see aim ray hits. The cause was a level
        pillar at the drifted body spot, not the priest: plan-forgemaster-occlude 20261022-083736.)"""
        self.setup_forge("near_priest", levels=4)
        if not self.to_arena("near_priest"):
            return
        self.hwp("forge trace on", 0.2)
        cases = [("beasts/wolves/wolf_grey.unit", 0, 0), ("beasts/wolves/wolf_grey.unit", 40, 100),
                 ("humans/cult/cult_brother.unit", -6, 6), ("misc/tower_magic/tower_magic_fire.unit", 0, 0)]
        for i, (rel, dx, dy) in enumerate(cases):
            mark = len(self.g.read_log())
            self.set_heresy(0)
            self.body(rel, 60, 0)
            self.raise_now()
            time.sleep(0.6)
            self.gl("spawn", DUMMY, dx, dy)
            time.sleep(6.5)
            rl = self.risen_lines()
            brutes = [(int(u.get("x", 0)), int(u.get("y", 0)), u.get("hp")) for u in self.dummies(1500)]
            trace = [ln.split("[HWP:specs] ", 1)[-1].strip() for ln in self.g.read_log()[mark:].splitlines()
                     if "foes:" in ln or "casts skill" in ln]
            self.out[f"near_priest_{i}"] = {"unit": rel, "brute_at": (dx, dy), "priest": self.pos(), "risen": rl[:1], "brutes": brutes, "trace": trace[-4:]}
            self.notes.append(f"near_priest {rel} brute at +{dx},{dy}: risen {rl[:1]} brutes {brutes} trace {trace[-3:]}")
            self.cull()
        self.hwp("forge trace off", 0.2)
        self.flag("near_priest_done", True, f"{len(cases)} cases")

    def bosses(self):
        self.setup_forge("boss", levels=4)
        if not self.to_arena("boss"):
            return
        rels = {k: v for k, v in risen_rels().items() if v[1]}
        self.hwp("forge trace on", 0.2)
        self.arena_terrain("boss")
        rows = self.unit_table("boss", rels)
        self.hwp("forge trace off", 0.2)
        hps = {r["unit"].split("/")[-1]: r.get("max") for r in rows}
        self.notes.append(f"boss risen max hp: {hps}")
        # the 10 s channel on a boss body through the real cast
        first = next(iter(rels))
        self.set_heresy(0)   # 5+ blocks the cast
        self.body(first, 60)
        time.sleep(0.4)
        h0 = self.heresy()
        presses, spent, button = self.cast_skill("boss", NR, 70, done=lambda: self.has("raising")["raising"].get("on"))
        time.sleep(0.5)
        rb = self.has("raising")["raising"]
        left = rb.get("left") or 0
        time.sleep(4.0)
        mid = self.risen()
        time.sleep(6.5)
        rs = self.risen()
        self.flag("boss_channel", presses > 0 and left > 8000 and not mid and len(rs) == 1 and self.heresy() == (h0 or 0) + 3,
                  f"raising left {left} ms right after the cast, risen at 4.5 s {len(mid)}, at 11 s {len(rs)}, heresy {h0} -> {self.heresy()}")
        self.cull()

    # --- penance
    def favor_path(self):
        return self.bind("divine_favor", "stacks-buff") or "players/priest/stacks_priest.sval:divine_favor_1"

    def penance_once(self, rel, heresy, want_removed, tag):
        fav = self.favor_path()
        self.set_heresy(heresy)
        uid = self.body(rel, 70)   # past the lunge's 40 (a roll ate the elite's body at Heresy 4)
        time.sleep(0.4)
        cd0 = self.skill_cd(NR)
        self.hwp("god", 0.2)   # off for the cast: god mode makes mana free
        m0 = self.mana_exact()
        # last, right before the press: Divine Favor loses a stack every 5 s (stacks_priest.sval
        # timer), and 5 s of setup once turned a Penance into a raise (bosses 20261022-052506)
        self.set_stacks(fav, 5)
        lights0 = self.fnum(self.forge_status(), "lights") or 0
        presses, spent, button = self.cast_skill(tag, NR, 50, done=lambda: self.has("raising")["raising"].get("on"))
        time.sleep(0.3)
        rb = self.has("raising")["raising"]
        if tag == "pen_normal":
            self.g.shot("penance_light", settle=False)   # the stance and the golden light, 1-2 s into the channel
        # the cost lands when the channel completes (CompleteChannel, the review's fix), so god mode stays
        # off until then (the arena is empty) and the drop is read across the moment the raising buff ends
        # (mana first, then the buff: a read is a round trip, and the channel once completed between
        # a "still raising" check and the mana read after it, eat 20261022-151923, "spent -2")
        m_pre = m1 = m0
        for _ in range(60):
            m = self.mana_exact()
            if not self.has("raising")["raising"].get("on"):
                break
            m_pre = m
            time.sleep(0.1)
        m1 = self.mana_exact()
        self.hwp("god", 0.2)
        time.sleep(0.5)
        h = self.heresy()
        st = self.forge_status()
        favor = self.fnum(st, "favor")
        cd1 = self.skill_cd(NR)
        bodies = self.fnum(st, "bodies")
        if tag == "pen_normal":
            # the stance, from the status's record at each light pulse after the landing: the priest 10 px
            # under the body facing up (-90), a pulse every 150 ms of the 3 s channel
            beside = self.fnum(st, "beside")   # 0 is a measurement ("or 99" read it as 99, eat 20261022-153545)
            self.flag("pen_faces_up", abs((self.fnum(st, "shine") or 0) + 90) <= 10 and beside is not None and abs(beside) < 6 and 4 <= (self.fnum(st, "under") or 0) <= 16,
                      f"facing {self.fnum(st, 'shine')} (up is -90), {self.fnum(st, 'beside')} px beside and {self.fnum(st, 'under')} px under the body at the light pulses")
            self.flag("pen_light", (self.fnum(st, "lights") or 0) - lights0 >= 12, f"{(self.fnum(st, 'lights') or 0) - lights0} light pulses (150 ms each) over the 3 s channel")
        ok = presses > 0 and h == max(0, heresy - want_removed) and (favor or 0) == 0 and bodies == 0 and (cd1 or 0) <= (cd0 or 0) + 100
        self.flag(tag, ok, f"heresy {heresy} -> {h} (want -{want_removed}), favor {favor}, mana {m0:.0f} -> {m_pre:.0f} in the channel -> {m1:.0f} at its end (spent {m_pre - m1:.0f}), "
                           f"cooldown {cd0} -> {cd1}, raising {rb.get('on')} left {rb.get('left')}, bodies left {bodies}, presses {presses}")
        self.cull()
        return m_pre - m1

    def penance(self):
        self.setup_forge("pen")
        if not self.to_arena("pen"):
            return
        # the icon: Penance shows at max Divine Favor (the skill's m_icon swaps)
        spent = self.penance_once("humans/bandits/bandit_brute.unit", 4, 1, "pen_normal")
        self.flag("pen_mana", 40 <= spent <= 60, f"a Penance cost {spent:.0f} mana (50, not the raise's 70)")
        self.penance_once("humans/bandits/bandit_brute_elite.unit", 4, 2, "pen_elite")
        self.penance_once("bosses/boss_bandit/boss_bandit_encounter.unit", 5, 3, "pen_boss")
        # rank 5: 3 + 2 for a boss's body
        for _ in range(4):
            self.gl("skill", NR, 1)
        time.sleep(0.3)
        self.flag("pen_rank5_bind", str(self.bind(NR, "nr-penance")) == "3", f"nr-penance {self.bind(NR, 'nr-penance')}")
        self.penance_once("bosses/boss_bandit/boss_bandit_encounter.unit", 8, 5, "pen_boss_rank5")
        self.penance_once("humans/bandits/bandit_brute_elite.unit", 3, 4, "pen_elite_rank5")
        # no Penance below max Favor: the same cast is a raise
        self.set_stacks(self.favor_path(), 2)
        self.set_heresy(0)
        # five Penances leave too little mana for the 70 a raise costs (20261026-222826: 35 left)
        self.gl("cheat", "cht_give_mana", 500)
        self.body("humans/bandits/bandit_brute.unit")
        time.sleep(0.4)
        presses, spent, button = self.cast_skill("pen_raise", NR, 70, done=lambda: self.has("raising")["raising"].get("on"))
        time.sleep(3.8)
        self.flag("pen_needs_max_favor", presses > 0 and self.heresy() == 1 and len(self.risen()) == 1,
                  f"2 Favor: heresy -> {self.heresy()}, risen {len(self.risen())}, mana spent {spent:.0f}")
        self.cull()

    # --- heresy
    def heresy_rules(self):
        self.setup_forge("her")
        if not self.to_arena("her"):
            return
        # the block at 5: the cast is refused (no channel, no mana)
        self.set_heresy(5)
        self.body("humans/bandits/bandit_brute.unit")
        time.sleep(0.4)
        m0 = self.mana_exact()
        presses, spent, button = self.cast_skill("her_block", NR, 70, done=lambda: self.has("raising")["raising"].get("on"))
        time.sleep(0.5)
        st = self.forge_status()
        self.flag("her_block", not self.has("raising")["raising"].get("on") and "channel none" in st and abs(self.mana_exact() - m0) < 5,
                  f"heresy 5: presses {presses}, raising {self.has('raising')['raising'].get('on')}, mana {m0:.0f} -> {self.mana_exact():.0f}, {st.strip()[-120:]}")
        self.cull()
        # the overshoot: 4 + a boss's 3 = 7
        self.set_heresy(4)
        self.body("bosses/boss_bandit/boss_bandit_encounter.unit")
        time.sleep(0.4)
        self.raise_now()
        time.sleep(0.6)
        self.flag("her_overshoot", self.heresy() == 7 and len(self.risen()) == 1, f"heresy 4 + boss -> {self.heresy()}, risen {len(self.risen())}")
        # the HUD icon at 5+: the stack buff's hud sprite swaps (hasbuff reports the HUD flag)
        # the stack def's HUD sprite is swapped at 5+ (UpdateHeresyHud); the status line names the one in
        st7 = self.forge_status()
        self.set_heresy(2)
        st2 = self.forge_status()
        self.set_heresy(7)
        self.flag("her_hud", "hud high" in st7 and "hud low" in st2, f"status at 7 says high: {'hud high' in st7}; at 2 says low: {'hud low' in st2}")
        # the carry: the next floor keeps the Heresy and the risen comes along
        log = self.next_floor()
        time.sleep(2.0)
        h = self.heresy()
        rs = self.risen()
        self.flag("her_carry", h == 7, f"heresy on the next floor {h}, risen there {len(rs)} {[r['name'].split('/')[-1] for r in rs]}")
        self.flag("her_risen_follow", len(rs) == 1, f"risen on arrival {len(rs)}")
        # town: Heresy resets, no risen
        self.gl("abort")
        ok = self.wait_phase("town", 90)
        time.sleep(2.5)
        self.flag("her_town_reset", ok and self.heresy() == 0 and not self.risen(), f"town {ok}, heresy {self.heresy()}, risen {len(self.risen())}")

    # --- lunge
    def lunge(self):
        self.setup_forge("lunge")
        self.gl("orb", "hwp_pri_coh_ravenous_lunge", 2)  # rare: 150%, knockback
        if not self.to_arena("lunge"):
            return
        # the forced lunge: the priest lands on the body, eats it (devouring), the brute beside it is hit
        x0, y0 = self.pos()
        self.body("humans/bandits/bandit_brute.unit", 120, 0)
        # a breakable target dummy 30 px past the body (LUNGE_HIT_RADIUS 50): it stands still, where a
        # brute walks at the priest and once stood 140 px from the body when the lunge landed
        # (plan-forgemaster-bosses 20261022-122738: "hitting for 60" logged, nothing in reach)
        self.gl("spawn", TARGET, 150, 0)
        time.sleep(0.6)
        before = [u for u in self.targets(400) if not u.get("dead")]
        self.hwp("forge lunge", 0.3, until="forge:")
        time.sleep(0.4)
        x1, y1 = self.pos()
        dv = self.has("devouring")["devouring"]
        hit = self.target_hit(before)
        st = self.forge_status()
        # the priest stands EAT_BELOW (10) px under the body, facing up (-90), the body still there
        self.flag("lunge_jump", abs(x1 - (x0 + 120)) < 8 and 4 <= y1 - y0 <= 16, f"priest {x0:.0f},{y0:.0f} -> {x1:.0f},{y1:.0f} (body at +120, the priest 10 under it)")
        self.flag("lunge_devour", bool(dv.get("on")) and (dv.get("left") or 0) > 500 and self.fnum(st, "bodies") == 1,
                  f"devouring {dv}, bodies on the floor {self.fnum(st, 'bodies')} (the body stays while it is eaten)")
        self.flag("lunge_hit", hit, f"the target dummy 30 px past the body hit by Ravenous Lunge: {hit}")
        self.flag("lunge_lift", (self.fnum(st, "lift") or 0) in (0, -1), f"while eating the priest is 0 or 1 px above its spot: lift {self.fnum(st, 'lift')}")
        # the devouring heal: 30% of the maximum health a second (HWPSpecsMaxHealthRegen), after
        # the pose reads above (the second it takes would let the brute push the priest)
        self.gl("hurt", 0.05)
        def frac():
            p = self.gl("state").get("player") or {}
            return p.get("hp", 0) / max(1, p.get("hpMax", 1))
        t0 = time.time()
        hp0 = frac()
        time.sleep(1.0)
        hp1 = frac()
        rate = (hp1 - hp0) / max(0.1, time.time() - t0)
        self.flag("lunge_heal", 0.2 <= rate <= 0.4, f"hp {hp0:.2f} -> {hp1:.2f}: {rate:.2f} of the maximum a second while devouring (0.30)")
        # the shot lands 1-2 s into the eating (a shot is slow); the counters below are read after the
        # devouring ends, from the status's record of the last eating (facing at each bob, up is -90)
        self.g.shot("eating", settle=False)   # the pose: under the body, facing up, blood out of it
        time.sleep(1.5)
        st = self.forge_status()
        self.flag("lunge_faces_up", abs((self.fnum(st, "facing") or 0) + 90) <= 10, f"facing {self.fnum(st, 'facing')} at the bobs (up is -90)")
        self.flag("lunge_bobs", (self.fnum(st, "bobs") or 0) >= 6, f"{self.fnum(st, 'bobs')} bobs (1 px every 250 ms over the 3 s devouring, after the dodge)")
        self.flag("lunge_blood", (self.fnum(st, "bloods") or 0) >= 5, f"{self.fnum(st, 'bloods')} blood bursts (300 ms each)")
        self.flag("lunge_body_eaten", self.fnum(st, "bodies") == 0 and "eat none" in st, f"after the devouring: bodies {self.fnum(st, 'bodies')}, eat state {'none' if 'eat none' in st else 'still on'}")
        self.cull()
        # the die itself: randf() under 0.16, 20000 throws in one frame (15-17% expected; 14-18 passes)
        r = self.hwp("forge roll 20000 0.16", 0.3, until="forge:")
        m = re.search(r"roll (\d+) of (\d+)", r)
        frac = int(m.group(1)) / int(m.group(2)) if m else -1
        self.flag("lunge_rng", 0.14 <= frac <= 0.18, f"randf() < 0.16 on {frac:.4f} of 20000 throws")
        # the roll: Heresy 8 x 2% = 16%, 40 bodies walked into one by one: at least one lunge
        # (none in 40 at 16%: 0.09%; 25 bodies gave 2, 3 and 0 lunges at 064242, 085643 and 102006)
        self.set_heresy(8)
        rolls = 0
        lunges0 = self.fnum(self.forge_status(), "lunges") or 0
        mark = len(self.g.read_log())
        for i in range(40):
            x, y = self.pos()
            self.body("humans/bandits/bandit_brute.unit", 25, 0)
            time.sleep(0.6)
            # the roll is logged once per body (a lunge eats the body before `forge bodies` lists it)
            rolls += self.g.read_log()[mark:].count("lunge roll on")
            mark = len(self.g.read_log())
            if (self.fnum(self.forge_status(), "lunges") or 0) > lunges0 + i:
                pass
            self.hwp("forge cull", 0.3, until="forge:")
            time.sleep(3.2 if self.has("devouring")["devouring"].get("on") else 0.1)
        lunges = (self.fnum(self.forge_status(), "lunges") or 0) - lunges0
        self.flag("lunge_rolls", rolls >= 39, f"{rolls}/40 bodies rolled once when the priest was within 40")
        self.flag("lunge_chance", 1 <= lunges <= 16, f"{lunges} lunges in 40 bodies at 16% (expected 6)")
        # no roll at 0 Heresy
        self.set_heresy(0)
        l0 = self.fnum(self.forge_status(), "lunges")
        for i in range(5):
            self.body("humans/bandits/bandit_brute.unit", 25, 0)
            time.sleep(0.5)
            self.hwp("forge cull", 0.3, until="forge:")
        self.flag("lunge_none_at_zero", self.fnum(self.forge_status(), "lunges") == l0, f"lunges {l0} -> {self.fnum(self.forge_status(), 'lunges')}")

    # --- decay, bloom, the cap
    def decay(self):
        self.setup_forge("decay")
        self.gl("orb", "hwp_pri_nr_rot_bloom", 2)  # rare: 120%
        if not self.to_arena("decay"):
            return
        self.body("humans/bandits/bandit_brute.unit")
        time.sleep(0.4)
        self.raise_now()
        time.sleep(0.6)
        r0 = self.risen_lines()
        # 30 s ahead: 10 steps of 1%
        self.hwp("forge decay 30000", 0.3, until="forge:")
        time.sleep(0.5)
        r1 = self.risen_lines()
        self.flag("decay_step", bool(r0) and bool(r1) and abs(r0[0]["hp"] - r1[0]["hp"] - 0.10) < 0.015,
                  f"hp {r0[0]['hp'] if r0 else None} -> {r1[0]['hp'] if r1 else None} after 30 s of decay (10 x 1%)")
        self.flag("decay_no_heal", bool(r1) and r1[0]["hp"] < 0.95, "a risen is never healed (regen off): " + (f"hp {r1[0]['hp']}" if r1 else "no risen"))
        # to death: the brute beside it takes Rot Bloom's poison
        self.gl("spawn", DUMMY, 60, 0)
        time.sleep(0.5)
        before = [u for u in self.dummies(400) if not u.get("dead")]
        mark = len(self.g.read_log())
        self.hwp("forge decay 400000", 0.3, until="forge:")
        time.sleep(1.0)
        log = self.g.read_log()[mark:]
        hit = self.dummy_hit(before)
        st = self.forge_status()
        self.flag("decay_death", not self.risen() and "decayed away" in log and (self.fnum(st, "decay deaths") or 0) >= 1,
                  f"risen left {len(self.risen())}, decay deaths {self.fnum(st, 'decay deaths')}")
        self.flag("decay_bloom", hit and "rot bloom" in log and (self.fnum(st, "blooms") or 0) >= 1, f"brute hit {hit}, blooms {self.fnum(st, 'blooms')}")
        self.cull()
        # the cap: level 1 keeps 2; the third raise kills the oldest
        self.set_heresy(0)
        ids = []
        for i in range(3):
            self.body("humans/bandits/bandit_brute.unit", 40 + 30 * i, 0)
            time.sleep(0.4)
            self.raise_now()
            time.sleep(0.5)
            ids.append([r["id"] for r in self.risen_lines()])
        time.sleep(0.8)
        now = [r["id"] for r in self.risen_lines()]
        st = self.forge_status()
        self.flag("decay_cap", len(ids[1]) == 2 and len(now) == 2 and ids[0] and ids[0][0] not in now and (self.fnum(st, "cap kills") or 0) >= 1,
                  f"after each raise {ids}, now {now}, cap kills {self.fnum(st, 'cap kills')}")
        self.cull()
        # Pyre Sacrifice: a Pyre's use removes ps-reduce Heresy (the class-swapped brazier)
        self.gl("orb", "hwp_pri_nr_pyre_sacrifice", 2)  # uncommon: 3
        self.set_heresy(4)
        self.gl("spawn", "doodads/lamps/brazier_pyre.unit", 50, 0)
        time.sleep(0.6)
        pyres = self.gl("near", 200, "brazier_pyre").get("units") or []
        if pyres:
            self.gl("use", "brazier_pyre")
            time.sleep(0.8)
        self.flag("decay_pyre", bool(pyres) and self.heresy() == 1, f"pyre units {len(pyres)}, heresy 4 -> {self.heresy()} (ps-reduce {self.bind(NR, 'ps-reduce')})")


    # --- the channel lock, effects and bar (the user, 2026-10-25)
    def lock_status(self):
        st = self.forge_status()
        return st, {k: self.fnum(st, k) for k in ("locked", "beam", "pulses", "lockface", "beamframes", "bar", "dashpin", "dashrefused", "dashcd", "angle")}

    def dash_try(self, dx=1, dy=0):
        """A dash press (move + aim that way); how far the priest moved in the next half second."""
        x0, y0 = self.pos()
        self.gl("input", 150, dx, dy, dx, dy, "dash")
        time.sleep(0.5)
        x1, y1 = self.pos()
        return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5

    def channel_ms(self, st):
        m = re.findall(r"channel (?:raise|penance) (-?\d+) ms", st)
        return int(m[-1]) if m else None

    def wait_channel_end(self, limit=12.0):
        end = time.time() + limit
        while time.time() < end:
            if not self.has("raising")["raising"].get("on"):
                return True
            time.sleep(0.2)
        return False

    def channel_lock(self):
        """The Penance first (the skill has no cooldown yet: a raise's 20 s would refuse the
        press, lab 20261025-171508), then a raise on a boss's body (10 s: room for the reads;
        the 5 s elite channel had ended before the dash press in that run)."""
        self.setup_forge("lock")
        if not self.to_arena("lock"):
            return
        fav = self.favor_path()
        # a Penance: the dodge lands, then the lock (facing up, -90), the dash refused, the golden beam
        self.set_heresy(4)
        self.body("humans/bandits/bandit_brute.unit", 70, 0)
        time.sleep(0.4)
        self.set_stacks(fav, 5)
        mark = len(self.g.read_log())
        presses, spent, button = self.cast_skill("lock_pen", NR, 50, done=lambda: self.has("raising")["raising"].get("on"))
        # no wait for the dodge: the lock is logged in the same second as the channel starts, the
        # cast itself already costs ~1.4 s of the 3 s channel and every status read ~0.3 s (labs
        # 20261025-185758 and -190659: the lock read or the dash press landed after the channel)
        st, e = self.lock_status()
        self.flag("lock_pen_locked", presses > 0 and e["locked"] == 1 and e["angle"] is not None and abs(e["angle"] + 90) <= 12 and e["beam"] == 1,
                  f"locked {e['locked']}, facing {e['angle']} (up is -90), beam {e['beam']}, bar {e['bar']}, {self.channel_ms(st)} ms left")
        moved = self.dash_try()
        f = e
        log = self.g.read_log()[mark:]
        self.flag("lock_pen_dash_refused", moved < 4 and ((f["dashrefused"] or 0) >= 1 or "dash refused during penance channel" in log),
                  f"moved {moved:.1f} px, refused {f['dashrefused']}, log {'dash refused during penance channel' in log}, {self.channel_ms(st)} ms left at the read")
        self.wait_channel_end(6)
        time.sleep(0.5)
        st = self.forge_status()
        self.flag("lock_pen_done", self.heresy() == 3 and (self.fnum(st, "favor") or 0) == 0 and self.fnum(st, "bodies") == 0,
                  f"heresy 4 -> {self.heresy()}, favor {self.fnum(st, 'favor')}, bodies {self.fnum(st, 'bodies')}")
        self.cull()
        self.origin()
        # a raise on a boss's body (10 s channel) 70 px east: the lock faces east (0)
        self.set_stacks(fav, 0)
        self.set_heresy(0)
        self.body("bosses/boss_bandit/boss_bandit_encounter.unit", 70, 0)
        time.sleep(0.4)
        mark = len(self.g.read_log())
        presses, spent, button = self.cast_skill("lock", NR, 70, done=lambda: self.has("raising")["raising"].get("on"))
        st, a = self.lock_status()
        self.flag("lock_raise_locked", presses > 0 and a["locked"] == 1 and a["angle"] is not None and abs(a["angle"]) <= 12,
                  f"locked {a['locked']}, facing {a['angle']} (the body is east: 0), dash pinned {a['dashpin']} cd {a['dashcd']}, {self.channel_ms(st)} ms left")
        self.flag("lock_beam", a["beam"] == 1, f"beam unit alive {a['beam']}")
        self.flag("lock_bar", a["bar"] == 1, f"bar drawn this frame {a['bar']}")
        # a dash press mid-channel: refused (the pinned cooldown), nothing moves, the log says so
        moved = self.dash_try()
        st, c = self.lock_status()
        log = self.g.read_log()[mark:]
        self.flag("lock_dash_refused", moved < 4 and ((c["dashrefused"] or 0) >= 1 or "dash refused during raise channel" in log),
                  f"moved {moved:.1f} px, refused count {c['dashrefused']}, log line {'dash refused during raise channel' in log}, dash cd {c['dashcd']}, {self.channel_ms(st)} ms left")
        # the aim turned south for 1.2 s: the facing holds east
        self.gl("input", 1200, 0, 0, 0, 1)
        time.sleep(0.6)
        st, b = self.lock_status()
        self.flag("lock_facing_held", b["locked"] == 1 and b["angle"] is not None and abs(b["angle"]) <= 12,
                  f"facing {b['angle']} with the aim turned south (90), {self.channel_ms(st)} ms left")
        time.sleep(0.7)
        st, c2 = self.lock_status()
        self.flag("lock_fx", (c2["pulses"] or 0) >= 8 and (c2["beamframes"] or 0) >= 60 and c2["beam"] == 1,
                  f"pulses {c2['pulses']} (150 ms each), beam frames {c2['beamframes']}, beam alive {c2['beam']}, {self.channel_ms(st)} ms left")
        # the channel completes: the risen, Heresy +3, the beam gone, the dash free again
        self.wait_channel_end(12)
        time.sleep(0.6)
        st, d = self.lock_status()
        self.flag("lock_raise_done", len(self.risen()) == 1 and self.heresy() == 3 and d["beam"] in (0, None) and d["dashpin"] == 0,
                  f"risen {len(self.risen())}, heresy {self.heresy()}, beam {d['beam']}, dash pinned {d['dashpin']} cd {d['dashcd']}")
        moved = self.dash_try(0, 1)
        self.flag("lock_dash_after", moved >= 20, f"a dash after the channel moved {moved:.1f} px")
        self.cull()

    # --- the Penance icon
    def icon_name(self):
        m = re.findall(r"; icon (\w+)", self.forge_status())
        return m[-1] if m else None

    def penance_icon(self):
        self.setup_forge("icon")
        if not self.to_arena("icon"):
            return
        fav = self.favor_path()
        self.set_stacks(fav, 0)
        time.sleep(0.4)
        low = self.icon_name()
        mark = len(self.g.read_log())
        self.set_stacks(fav, 5)
        time.sleep(0.5)
        high = self.icon_name()
        log = self.g.read_log()[mark:]
        self.set_stacks(fav, 2)
        time.sleep(0.5)
        back = self.icon_name()
        self.flag("icon_raise_below_max", low == "raise", f"icon at 0 Favor: {low}")
        self.flag("icon_penance_at_max", high == "penance" and "resurrection icon -> penance" in log, f"icon at 5 Favor: {high}, log swap {'resurrection icon -> penance' in log}")
        self.flag("icon_back_to_raise", back == "raise", f"icon at 2 Favor: {back}")

    # --- pyres with Heresy and no curse; the large pyre
    def usable(self, text):
        """The `usables` entry whose unit json mentions text, else None."""
        for u in self.gl("usables").get("usables") or []:
            if text in str(u.get("unit")) or text in str(u):
                return u
        return None

    def walk_into(self, text, dx, dy, tries=4):
        for _ in range(tries):
            u = self.usable(text)
            if u is not None:
                return u
            self.gl("input", 150, dx, dy)
            time.sleep(0.35)
        return self.usable(text)

    def pyre_heresy(self):
        self.setup_forge("pyre")
        self.gl("orb", "hwp_pri_nr_pyre_sacrifice", 2)   # uncommon: ps-reduce 3
        if not self.to_arena("pyre"):
            return
        curses = self.gl("state").get("player", {}).get("curses")
        # a brazier: with Heresy 4 and no curse it is usable (CanUse) and its use removes 3 Heresy
        self.set_heresy(4)
        self.gl("spawn", "doodads/lamps/brazier_pyre.unit", 26, 0)
        time.sleep(0.5)
        u = self.walk_into("brazier_pyre", 1, 0)
        self.flag("pyre_canuse_with_heresy", u is not None and u.get("canUse") is True, f"usables entry {u}, curses {curses}")
        mark = len(self.g.read_log())
        self.gl("use", "brazier_pyre")
        time.sleep(0.8)
        log = self.g.read_log()[mark:]
        self.flag("pyre_heresy_removed", self.heresy() == 1 and "brazier pyre used with no curse: heresy -3 -> 1" in log,
                  f"heresy 4 -> {self.heresy()}, log {[l.strip()[:90] for l in log.splitlines() if 'pyre used' in l]}")
        # with neither Heresy nor a curse the vanilla rule stands: not usable
        self.origin()
        self.set_heresy(0)
        self.gl("spawn", "doodads/lamps/brazier_pyre.unit", 26, 40)
        time.sleep(0.5)
        u2 = self.walk_into("brazier_pyre", 0.6, 1)
        self.flag("pyre_needs_heresy_or_curse", u2 is not None and u2.get("canUse") is False, f"usables entry {u2}")
        self.origin()
        # the large pyre (WorldScript::Pyre): the floor's own, else a fabricated pyre prefab
        ws = self.gl("ws", "Pyre").get("scripts") or []
        if not ws:
            pf = self.gl("prefab", "prefabs/barracks/special/pyre_crn_nw.pfb", 0, -560)
            time.sleep(1.0)
            ws = self.gl("ws", "Pyre").get("scripts") or []
            self.notes.append(f"pyre prefab fabricated: {pf}")
        self.flag("pyre_large_present", bool(ws), f"WorldScript Pyre scripts {ws[:2]}")
        if not ws:
            return
        # goto wants the script's comment, which a pyre has none of (lab 20261025-171508: "no Pyre '0'"),
        # and the script's own position is not its use area: that is the sensor circle (radius 32) on
        # the pyre_tower doodad, which sits 56 px off the script in every pyre prefab (west in
        # pyre_crn_nw, lab 20261025-185758). Teleport to the script, find the tower, stand 40 px
        # under it and walk north into the sensor.
        self.set_heresy(4)
        sx, sy = round(float(ws[0].get("x", 0)), 1), round(float(ws[0].get("y", 0)), 1)
        self.gl("teleport", sx, sy)
        time.sleep(0.3)
        towers = self.gl("near", 120, "pyre_tower").get("units") or []
        tx, ty = (round(float(towers[0]["x"]), 1), round(float(towers[0]["y"]), 1)) if towers else (sx, sy)
        r = self.gl("teleport", tx, ty + 40)
        r["tower"] = towers[0].get("name", "").split("/")[-1] if towers else None
        time.sleep(0.4)
        u3 = self.walk_into("Pyre", 0, -1, tries=6)
        self.flag("pyre_large_canuse", u3 is not None and u3.get("canUse") is True, f"goto {r}, usables entry {u3}")
        mark = len(self.g.read_log())
        self.gl("use", "Pyre")   # the nearest usable whose type name has Pyre: the large one under the priest
        time.sleep(0.8)
        log = self.g.read_log()[mark:]
        self.flag("pyre_large_heresy", self.heresy() == 1 and "large pyre used with no curse: heresy -3 -> 1" in log,
                  f"heresy 4 -> {self.heresy()}, log {[l.strip()[:90] for l in log.splitlines() if 'pyre used' in l]}")

    # --- Deeper Depravity: every boss leaves a body at epic
    def orb_boss(self):
        self.setup_forge("orb")
        self.gl("orb", "hwp_pri_coh_deeper_depravity", 2)   # rare: no boss chance yet
        time.sleep(0.3)
        rare = self.bind(COH, "dd-boss")
        self.gl("orb", "hwp_pri_coh_deeper_depravity", 1)   # epic
        time.sleep(0.3)
        epic = self.bind(COH, "dd-boss")
        self.flag("orb_boss_epic_only", str(rare) in ("0", "0.0") and abs(float(epic or 0) - 1.0) < 1e-6, f"dd-boss rare {rare}, epic {epic}")
        if not self.to_arena("orb"):
            return
        # three boss deaths on the floor (the host rolls each): three bodies
        rolls0 = self.fnum(self.forge_status(), "rolls") or 0
        bodies = 0
        sp = None
        for i in range(3):
            sp = self.gl("spawn", "actors/bosses/boss_bandit/boss_bandit_encounter.unit", 120, 0)
            time.sleep(0.6)
            self.gl("kill", 300, "boss_bandit")
            time.sleep(0.8)
            st = self.hwp("forge bodies", 0.3, until="forge bodies")
            bodies = len(re.findall(r"boss_bandit_encounter\.unit", st))
            self.cull()
            self.origin()
        rolls = self.fnum(self.forge_status(), "rolls") or 0
        self.flag("orb_boss_always", rolls - rolls0 >= 3 and bodies >= 1, f"rolls {rolls0} -> {rolls}, boss bodies after the last death {bodies} (spawn {sp})")
        self.cull()

    # --- the units' fixes (the user, 2026-10-25; Forgemaster_Risen.as, make_forgemaster_risen.py,
    # mods/summons): a risen runs and engages, looks like a summon; a body is grey, map-less and shot
    # through; the risen come along to the next floor
    RISEN_RE = re.compile(r"\| id (\d+) move (\S+) speed ([\d.]+) runback ([\d.]+) roaming ([\d.]+) search ([\d.]+) target (\S+) dist (-?\d+)")
    RUNS_RE = re.compile(r"\[HWP:specs\] risen (\d+) runs: (\S+) speed ([\d.]+) runback ([\d.]+) roaming ([\d.]+) search-mul ([\d.]+)")

    def risen_rows(self):
        """[{id, move, speed, runback, roaming, search, target, dist}] from `hwp risen`."""
        txt = self.hwp("risen", 0.3, until="risen ")
        return [{"id": int(m.group(1)), "move": m.group(2), "speed": float(m.group(3)), "runback": float(m.group(4)),
                 "roaming": float(m.group(5)), "search": float(m.group(6)), "target": m.group(7), "dist": int(m.group(8))}
                for m in self.RISEN_RE.finditer(txt)]

    def raise_body(self, rel, dx=40, dy=0, wait=0.8):
        """A body, raised at once; the log text since the raise."""
        self.body(rel, dx, dy)
        time.sleep(0.4)
        mark = len(self.g.read_log())
        self.raise_now()
        time.sleep(wait)
        return self.g.read_log()[mark:]

    def first_hit(self, before, timeout):
        """Seconds until a brute of `before` lost HP or died, or None."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.dummy_hit(before):
                return round(time.time() - t0, 1)
            time.sleep(0.2)
        return None

    def bodies_near(self, r=300):
        return [u for u in self.gl("near", r, "forgemaster/bodies").get("units") or []]

    def map_icons(self, units, filt):
        """mapicons at the first unit's spot: the rows (icon = its scene has a minimap sprite)."""
        if not units:
            return {}, []
        mi = self.gl("mapicons", round(units[0]["x"]), round(units[0]["y"]), 24, filt)
        return mi, mi.get("units") or []

    def lanes(self, radius=300, step=15):
        """Free straight lanes from the arena origin, {(dx, dy): px} for the four axis directions:
        the farthest cell such that every cell up to it, with its two neighbours across, is free
        in `gl terrain`. The mission start is a corridor (fix-specs-risen-speed 20261025-180859:
        a priest teleported 260 px east stood in rock, brutes spawned at +-150 px stood in rock,
        nothing could path or see anything), so every spot a section uses comes from here."""
        self.origin()
        t = self.gl("terrain", radius, step)
        rows = t.get("rows") or []
        n = len(rows)
        c = n // 2
        out = {}
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            far = 0
            for k in range(1, c + 1):
                x, y = c + dx * k, c + dy * k
                cells = [(x + dy * s, y + dx * s) for s in (-1, 0, 1)]   # the cell and its neighbours across
                if not all(0 <= cy < n and 0 <= cx < n and rows[cy][cx] in ".@" for cx, cy in cells):
                    break
                far = k * step
            out[(dx, dy)] = far
        self.notes.append(f"lanes from {self.pos()} (terrain step {step}): {out}")
        return out

    def best_lane(self, lanes):
        """(dx, dy), px of the longest lane."""
        d = max(lanes, key=lanes.get)
        return d, lanes[d]

    def fresh_target(self, dx, dy):
        """One live breakable target dummy at the origin + (dx, dy), the others gone; its rows."""
        self.gl("kill", 900, "target_dummy")
        time.sleep(0.2)
        self.gl("spawn", TARGET, dx, dy)
        time.sleep(0.4)
        return [u for u in self.targets(300) if not u.get("dead")]

    def risen_speed(self):
        """fix-specs-risen-speed: a risen moves at the chase pace at all times and attacks what
        comes near, like the vanilla summons. Every spot is on a free lane from the origin (the
        start is a corridor)."""
        self.setup_forge("speed")
        if not self.to_arena("speed"):
            return
        self.hwp("forge trace on", 0.3)   # 'risen N target ... skills:' every 2 s in the log
        lanes = self.lanes()
        (ax, ay), far = self.best_lane(lanes)
        back = lanes[(-ax, -ay)]
        log = self.raise_body("humans/bandits/bandit_brute.unit", 40 * ax, 40 * ay)
        m = self.RUNS_RE.search(log)
        self.flag("speed_log", bool(m), f"log: {m.group(0) if m else log[-400:]}")
        rows = self.risen_rows()
        ok = bool(rows) and all(r["speed"] >= 4.5 - 1e-3 and r["runback"] >= r["speed"] * 1.4 - 0.05 and r["roaming"] >= 0.99
                                and r["search"] <= 0.5 + 1e-3 and "Follower" in r["move"] for r in rows)
        self.flag("speed_values", ok, f"hwp risen: {rows} (speed >= 4.5, run-back >= 1.4 x speed, roaming 1.0, search 0.5)")
        # the pace: the priest down the lane (inside the 350 teleport leash; past the 180 run-back
        # distance when the lane allows, else the idle walk toward the owner at roaming 1.0 does
        # it): the risen closes in within 1.5 s
        sx, sy = self.origin()
        lane = min(far, 260)
        self.gl("teleport", round(sx + lane * ax, 1), round(sy + lane * ay, 1))
        time.sleep(0.3)
        d0 = [r["dist"] for r in self.risen_rows()]
        time.sleep(1.5)
        d1 = [r["dist"] for r in self.risen_rows()]
        need = min(100, max(20, lane - 80))
        self.flag("speed_runs_back", bool(d0) and bool(d1) and (d1[0] <= 80 or (lane >= 100 and d0[0] - d1[0] >= need)),
                  f"lane {lane} px {(ax, ay)}: distance to the priest {d0} -> {d1} after 1.5 s (closed {need}+ px, or within 80)")
        self.origin()
        time.sleep(0.8)
        # the engagement: a brute down the lane, then one up the opposite lane (a second target
        # search after the first kill), each damaged within 5 s. The mission start is often a
        # corridor open one way only: with no lane back, the second brute goes down the same lane
        # instead (the second search still has to find it).
        second = ("west", (-ax, -ay), back) if min(back, 150) >= 50 else ("west", (ax, ay), far)
        for key, (dx, dy), avail in (("east", (ax, ay), far), second):
            d = min(avail, 150)
            if d < 50:
                self.flag(f"speed_attacks_{key}", False, f"no free lane {(dx, dy)} ({avail} px) for a brute")
                continue
            self.gl("spawn", DUMMY, d * dx, d * dy)
            time.sleep(0.3)
            before = [u for u in self.dummies(400) if not u.get("dead")]
            t = self.first_hit(before, 5.0)
            self.flag(f"speed_attacks_{key}", bool(before) and t is not None,
                      f"brute {d} px {(dx, dy)}: first damage after {t} s (5 s allowed, {len(before)} brute(s))")
            self.gl("kill", 600, "tag:enemy")
            time.sleep(0.5)
        self.hwp("forge trace off", 0.3)
        self.cull()

    def risen_look(self):
        """fix-specs-risen-look: a body is grey and off the map; a risen has the summons' map dot
        and the orange ring (file checks: the live colours cannot be read back); a dead electric
        orb is a still core (the unit, then a shot for the eye)."""
        self.setup_forge("look")
        if not self.to_arena("look"):
            return
        rel = "undead/horde/horde_soldier_elite.unit"
        risen_txt = (BODIES.parent / "risen" / rel).read_text(encoding="utf-8")
        body_txt = (BODIES / rel).read_text(encoding="utf-8")
        wisp_txt = (BODIES / "aberrations/wisp/wisp_lightning.unit").read_text(encoding="utf-8")
        marker = BODIES.parent / "marker"
        self.flag("look_files", 'mats:npc"' in risen_txt and "minimap.unit:npc_normal" in risen_txt
                  and "marker/elite_marker.unit:16" in risen_txt and "mats:enemy" not in risen_txt
                  and "mats:npc-noxray" in body_txt and "mats:enemy" not in body_txt and "minimap.unit" not in body_txt
                  and "elite_marker" not in body_txt and 'shoot-through="true"' in body_txt
                  and "dead_core.png" in wisp_txt and "<effect" not in wisp_txt
                  and (marker / "elite_marker.png").is_file() and (marker / "elite_marker_16.effect").is_file(),
                  "risen: npc material, npc_normal dot, marker ring; body: npc-noxray, no dot, no ring, shoot-through; wisp body: dead_core")
        # the body: grey (its log line), no map dot (mapicons: no minimap sprite in its scene)
        mark = len(self.g.read_log())
        uid = self.body(rel, 60, 0)
        time.sleep(0.5)
        log = self.g.read_log()[mark:]
        self.flag("look_body_grey", uid > 0 and f"body {uid} " in log and "tint grey" in log, f"body unit {uid}; log has 'body {uid} ... tint grey': {'tint grey' in log}")
        mi, icons = self.map_icons(self.bodies_near(), "bodies")
        self.flag("look_body_no_map", bool(icons) and not any(u.get("icon") for u in icons), f"mapicons at the body: {icons[:2]} (minimap {mi.get('minimap')})")
        # raised: the elite risen has a map dot (npc_normal) and its ring scene loads without an error
        mark = len(self.g.read_log())
        self.raise_now()
        time.sleep(0.8)
        rs = self.risen()
        mi, icons = self.map_icons(rs, "risen")
        self.flag("look_risen_map", bool(rs) and bool(icons) and all(u.get("icon") for u in icons), f"risen {len(rs)}; mapicons at it: {icons[:2]}")
        errs = self.errors_since(mark)
        self.flag("look_no_errors", bool(rs) and not errs, f"errors since the raise: {errs[:3]}")
        self.cull()
        # a dead electric orb: the wisp's body stands as a still grey core (the shot after this bot is for the eye)
        uid = self.body("aberrations/wisp/wisp_lightning.unit", 60, 0)
        time.sleep(0.5)
        wisps = [u for u in self.bodies_near() if "wisp" in u.get("name", "")]
        self.flag("look_wisp_body", uid > 0 and bool(wisps), f"wisp body unit {uid}: {wisps[:1]}")

    def body_passthrough(self):
        """fix-specs-body-passthrough: a body between the priest and a target never stops the
        scepter's hitscan (attack_holy_scepter: Hitscan, range 65) or the lantern's heal beam
        (attack_offhand_lantern: Skills::ShootBeam, distance 160, penetration 0): the breakable
        target behind it loses HP. Each attack is proven on the bare lane first (the control),
        then with a brute's body 22 px out on the same line, the target at 60 px (the scepter's
        smite at a stopped ray, radius 26 around ~17 px, cannot reach a target edge at 56)."""
        self.setup_forge("pass")
        if not self.to_arena("pass"):
            return
        lanes = self.lanes()
        (ax, ay), far = self.best_lane(lanes)
        self.flag("pass_lane", far >= 80, f"lane {(ax, ay)} {far} px (80 needed)")
        t = self.fresh_target(60 * ax, 60 * ay)
        for _ in range(3):
            self.shoot("main", 600, (ax, ay))
        hit = self.target_hit(t)
        self.flag("pass_main_control", hit, f"the scepter on the bare lane: target damaged {hit}")
        t = self.fresh_target(60 * ax, 60 * ay)
        self.gl("input", 1500, 0, 0, ax, ay, "off")   # the beam: castpoint 200, a tick per 200 ms; input returns at once
        time.sleep(1.8)
        hit = self.target_hit(t)
        self.flag("pass_beam_control", hit, f"the lantern beam on the bare lane: target damaged {hit}")
        # the body on the line
        uid = self.body("humans/bandits/bandit_brute.unit", 22 * ax, 22 * ay)
        time.sleep(0.4)
        t = self.fresh_target(60 * ax, 60 * ay)
        self.flag("pass_setup", uid > 0 and len(t) == 1 and len(self.bodies_near()) == 1, f"body unit {uid}, targets {len(t)}, bodies {len(self.bodies_near())}")
        for _ in range(3):
            self.shoot("main", 600, (ax, ay))
        hit = self.target_hit(t)
        self.flag("pass_main_through_body", hit, f"the scepter through the body: target damaged {hit}")
        t = self.fresh_target(60 * ax, 60 * ay)
        self.gl("input", 1500, 0, 0, ax, ay, "off")   # the beam: castpoint 200, a tick per 200 ms; input returns at once
        time.sleep(1.8)
        hit2 = self.target_hit(t)
        self.flag("pass_beam_through_body", hit2, f"the lantern beam through the body: target damaged {hit2}")
        self.flag("pass_body_stays", len(self.bodies_near()) == 1, "the body is nobody's target: still there after the shots")
        self.cull()

    def risen_floors(self):
        """fix-specs-risen-floors: the risen come along to the next floor with their HP (the game's
        own summon carry, with mods/summons filling any shortfall), and none into town. The new
        floor's enemies die the moment it is up and the decay (1% per 3 s, RisenDecay) is allowed
        for: 20261025-181000 read 0.58 and 0.407 after 2.5 s among 25 brutes."""
        self.setup_forge("floors")
        if not self.to_arena("floors"):
            return
        lanes = self.lanes()
        (ax, ay), far = self.best_lane(lanes)
        for i in range(2):
            self.raise_body("humans/bandits/bandit_brute.unit", (40 + 30 * i) * ax, (40 + 30 * i) * ay, wait=0.6)
        self.gl("kill", 900, RISEN, 0.6)  # hp 60%: the carry keeps it
        time.sleep(0.5)
        r0 = self.risen_lines()
        self.flag("floors_raised", len(r0) == 2 and all(abs(r["hp"] - 0.6) < 0.08 for r in r0), f"risen before the exit: {[(r['name'].split('/')[-1], r['hp']) for r in r0]}")
        t_exit = time.time()
        log = self.next_floor()
        self.gl("kill", 1500, "tag:enemy")   # before anything on the new floor reaches them
        r1 = self.risen_lines()
        elapsed = time.time() - t_exit
        allowed = 0.01 * (elapsed / 3 + 2)   # the decay over the floor change, two steps of slack
        time.sleep(1.5)
        log += self.g.read_log()[-4000:]
        self.flag("floors_carry", len(r1) == 2, f"risen on the next floor: {[(r['name'].split('/')[-1], r['hp']) for r in r1]}")
        self.flag("floors_hp", len(r1) == 2 and all(0.6 - allowed <= r["hp"] <= 0.61 for r in r1),
                  f"hp on the next floor {[r['hp'] for r in r1]} (0.6 before, {elapsed:.1f} s of decay allowed: >= {0.6 - allowed:.3f})")
        self.flag("floors_save_ok", "Exception when saving summons" not in log, "no 'Exception when saving summons' (PlayerRecord.Save's catch) in the log")
        m = re.search(r"\[HWP:summons\] floor restore: (\d+) in the snapshot, (\d+) already live, (\d+) produced", log)
        self.flag("floors_summons_restore", bool(m) and int(m.group(1)) == 2 and int(m.group(2)) + int(m.group(3)) == 2,
                  f"summons restore line: {m.group(0) if m else 'none'}")
        self.notes.append("floors: hwp summons: " + self.hwp("summons", 0.3, until="summons").strip()[-200:])
        self.cull()


def run(p, sections="forge,penance,heresy_rules,lunge,decay,bosses,raise_all", units="", **_):
    c = Checks(p)
    c.only = [u for u in units.split(",") if u]   # raise_all on these units only
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
