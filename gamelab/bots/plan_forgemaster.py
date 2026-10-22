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
        new = self.g.read_log()[mark:]
        return [ln.strip()[:160] for ln in new.splitlines() if "Script exception" in ln or "[ERR]" in ln or "ERROR" in ln.upper()[:40]]

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
                  and abs(fo.get("dd-elite", 0) - 0.15) < 1e-3 and abs(fo.get("dd-boss", 0) - 0.3) < 1e-3
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
        # the shot lands 1-2 s into the eating (a shot is slow); the counters below are read after the
        # devouring ends, from the status's record of the last eating (facing at each bob, up is -90)
        self.g.shot("eating", settle=False)   # the pose: under the body, facing up, blood out of it
        time.sleep(2.5)
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
