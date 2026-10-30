"""Issue #37 ("add all the traps from hoh1"): the HWPTrap kinds work and generation mixes them by theme.

Sections:

- kinds (any indoor floor): each trap kind is spawned next to the player (`gl spawn`), and
  the bot polls the trap's scenes (`gl traps`: HWPTrap is a DangerAreaBehavior), the
  player's health and mana and the kind's buff until the trap does what it is for: health
  lost, the buff on, mana drained. A kind with a telegraph must show its "warn" scene before
  the first effect, and for at least WARN_MIN ms (issue #38: a trap that bites with no
  warning). Shooters and the turret are spawned 48-64 px away, aimed at the player, and the player aims away (a paladin's shield blocks shots from the front). Between
  kinds the trap is destroyed, the player healed until health holds and the buffs left to run out.
- floor: the generated floor's `traps: theme` and `traps: kinds` lines; every kind placed
  must have a weight above 0 for the floor's theme group in Traps.as's WEIGHTS (parsed from
  the source, so the test follows the table), and no prefab over its max-num
  (campaign_prefabs.sval). The nearest placed wall shooter, if any, is visited for a
  screenshot (the scenario's shot after the bot).

- confusion_off (after `hwp set campaign.confusion 0` and a new floor; issue #38): the floor's
  `traps: theme` line rolls no confusion family, and a confusion glyph and plate spawned
  under the player stay dark (their `setting` param) and confuse no one in 7 s.

kwargs: sections ("kinds,floor"), only (comma list of kind names for kinds)."""
import re
import time
from pathlib import Path

from gamelab.bots.plan_checks import Checks as Base

REPO = Path(__file__).resolve().parents[2]
TRAPS_AS = REPO / "mods" / "campaign" / "scripts" / "HWP" / "Campaign" / "Traps.as"
DEFS = REPO / "mods" / "campaign" / "tweak" / "hwp" / "campaign_prefabs.sval"
U = "doodads/hwp/traps/"
BUFFS = "tweak/hwp/campaign_buffs.sval:"
STATUS = "tweak/buffs/status_effects.sval:"
WARN_MIN = 600   # ms of warning seen before the first effect, for the 1 s telegraphs

# name: (unit, dx, dy, what to watch: hp / mana / a buff path, warn expected (ms, 0 = none), seconds)
# (the shooters get two shots: a player can evade or block one)
KINDS = {
    "plate_spikes": (U + "hwp_plate_spikes.unit", 0, 0, "hp", 1000, 7),
    "pressure_spikes": (U + "hwp_pressure_spikes.unit", 0, 0, "hp", 500, 4),
    "plate_poison": (U + "hwp_plate_poison.unit", 0, 0, BUFFS + "hwp_trap_poison", 1000, 8),
    "plate_drain": (U + "hwp_plate_drain.unit", 0, 0, "mana", 1000, 8),
    "plate_frost": (U + "hwp_plate_frost.unit", 0, 0, STATUS + "slow_area", 1000, 8),
    "plate_confusion": (U + "hwp_plate_confusion.unit", 0, 0, BUFFS + "hwp_trap_confusion", 1000, 9),
    "glyph_frost": (U + "hwp_glyph_frost.unit", 0, 0, STATUS + "freeze_minor", 1000, 4),
    # issue #38: the confusion and dart glyphs, HWPTraps now (they were TripMines that fired
    # 0.15-0.2 s after a player came near)
    "glyph_confusion": (U + "hwp_glyph_confusion.unit", 0, 0, BUFFS + "hwp_trap_confusion", 1000, 5),
    "glyph_dart": (U + "hwp_glyph_dart.unit", 0, 0, "hp", 1000, 5),
    "dropper_stalactite": (U + "hwp_dropper_stalactite.unit", 0, 0, "hp", 900, 4),
    "crusher_bricks": (U + "hwp_crusher_bricks.unit", 0, 0, "hp", 1000, 4),
    "bear_trap": (U + "hwp_bear_trap.unit", 0, 0, STATUS + "immobilize_minor", 0, 3),
    "shooter_arrow": (U + "hwp_shooter_arrow_e.unit", -48, 8, "hp", 0, 6),
    "shooter_poison": (U + "hwp_shooter_poison_w.unit", 48, 8, "hp", 0, 6),
    "shooter_fire": (U + "hwp_shooter_fire_e.unit", -48, 8, "hp", 0, 7),
    "shooter_blade": (U + "hwp_shooter_blade_s.unit", 0, -48, "hp", 0, 6),
    "turret_arrows": (U + "hwp_turret_arrows.unit", 64, 0, "hp", 500, 8),
    # north of the player, shooting south: its barrel is the one an arrow started inside
    "turret_arrows_south": (U + "hwp_turret_arrows.unit", 0, -64, "hp", 500, 8),
    # the bomb glyph is still a TripMine (no scenes for gl traps; its telegraph is the 1.1 s
    # fuse). Last: its OnDeath puts it back 8 s later, after the bot's clean-up, and it blew
    # up during the next two kinds
    "glyph_bomb": (U + "hwp_glyph_bomb.unit", 0, 0, "hp", 0, 5),
    # off the dart glyph's middle: one arrow, not the whole ring
    "glyph_dart_side": (U + "hwp_glyph_dart.unit", 16, 0, "hp", 1000, 5),
}


def weights():
    """{family: [cave, crypt, barracks, halls, dungeon, other]} and the group names, from Traps.as."""
    src = TRAPS_AS.read_text(encoding="utf-8")
    groups = re.findall(r'"(\w+)"', re.search(r"GROUPS = \{([^}]*)\}", src).group(1))
    fams = re.findall(r'"(\w+)"', re.search(r"FAMILIES = \{([^}]*)\}", src).group(1))
    body = re.search(r"WEIGHTS = \{(.*?)\};", src, re.S).group(1)
    nums = [int(n) for n in re.findall(r"-?\d+", re.sub(r"//.*", "", body))]
    w = {f: nums[i * len(groups):(i + 1) * len(groups)] for i, f in enumerate(fams)}
    return w, groups


def caps():
    """{prefab id: max-num} of the hwp_traps set."""
    out = {}
    for m in re.finditer(r'<string name="id">prefabs/hwp/traps/(\w+)\.pfb</string>\s*<string name="theme">hwp_traps</string>\s*<int name="max-num">(-?\d+)</int>', DEFS.read_text(encoding="utf-8")):
        out[m.group(1)] = int(m.group(2))
    return out


def family(pid):
    return pid.rsplit("_", 1)[0] if "_" in pid else pid


class Checks(Base):
    def player(self):
        return self.gl("state").get("player") or {}

    def buff_on(self, path):
        for b in self.gl("hasbuff", path).get("buffs") or []:
            if b.get("path") == path:
                return bool(b.get("on"))
        return False

    def trap_scenes(self, unit):
        """The scene names of the nearest trap area whose name has the unit's file name."""
        base = unit.split("/")[-1].removesuffix(".unit")
        for a in self.gl("traps", 300).get("areas") or []:
            if base in str(a.get("name")):
                return str(a.get("scenes") or "")
        return None

    def god(self, want):
        """God mode on or off (`hwp god` toggles: the floor section's screenshot turns it on,
        and a kinds run after it saw no damage at all)."""
        for _ in range(2):
            reply = self.hwp("god", 0.3, until="god mode")
            if ("god mode on" in reply) == want:
                return
        self.notes.append(f"god mode not {want}: {reply[-80:]!r}")

    def reset(self):
        self.gl("unitdestroy", 400, "hwp/traps")
        self.gl("cull", "all")
        self.gl("hurt", 1.0)
        self.gl("mana", 1.0)
        time.sleep(0.2)
        # a burn or poison from the last kind still ticking reads as this kind's hit (the
        # blade shooter "hit" at 0 ms after the fire shooter): heal until health holds
        end = time.time() + 8
        while time.time() < end:
            self.gl("hurt", 1.0)
            h1 = self.player().get("hp", 0)
            time.sleep(0.7)
            if self.player().get("hp", 0) >= h1:
                break

    def clear_line(self, x1, y1):
        """No wall between the player and (x1, y1) for a trap shot (gl rayhit)."""
        p = self.player()
        x0, y0 = float(p.get("x", 0)), float(p.get("y", 0))
        r = self.gl("rayhit", round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
        return bool(r.get("ok")) and not r.get("wall")

    def placing(self, name, unit, dx, dy):
        """Where a shooter or the turret goes: the KINDS spot if the shot's line from it is
        clear, else another facing / side that is (a crypt with 96 px corridors has no spot
        clear 48 px all round, and a shooter spawned into a wall never hits)."""
        if not (dx or dy):
            return unit, dx, dy
        p = self.player()
        x, y = float(p.get("x", 0)), float(p.get("y", 0))
        if name.startswith("shooter_"):
            base = unit[:-len("_e.unit")]
            opts = [("e", -48, 8), ("w", 48, 8), ("s", 0, -48)]
            opts.sort(key=lambda o: f"{base}_{o[0]}.unit" != unit)
            for f, ox, oy in opts:
                # to the wall face the shot leaves from, 4 px past the shooter
                tx, ty = (x + ox * 1.1, y) if f != "s" else (x, y + oy * 1.1)
                if self.clear_line(tx, ty):
                    return f"{base}_{f}.unit", ox, oy
        else:
            for ox, oy in [(dx, dy), (-dx, dy), (0, -64), (0, 64)]:
                # the turret's body reaches 16 px past its middle
                if self.clear_line(x + ox * 1.4, y + oy * 1.4):
                    return unit, ox, oy
        self.notes.append(f"{name}: no clear line from any side")
        return unit, dx, dy

    def kind(self, name, spec):
        unit, dx, dy, watch, warn, secs = spec
        self.reset()
        unit, dx, dy = self.placing(name, unit, dx, dy)
        # let the last kind's buffs run out (the longest, poison, is 4 s)
        end = time.time() + 6
        while time.time() < end and any(self.buff_on(b) for b in (BUFFS + "hwp_trap_poison", STATUS + "freeze_minor", STATUS + "immobilize_minor")):
            time.sleep(0.5)
        p0 = self.player()
        hp0, mana0 = p0.get("hp", 0), p0.get("mana", 0)
        r = self.gl("spawn", unit, dx, dy)
        if dx or dy:
            # the paladin's shield blocks a shot from the front (the poison shooter, on the
            # right, never landed): aim away from the shooter for the whole check
            self.gl("input", secs * 1000, 0, 0, -dx, -dy)
        t0 = time.time()
        first_warn = first_on = hit = None
        hwptrap = False
        seen = []
        while time.time() - t0 < secs:
            now = int((time.time() - t0) * 1000)
            sc = self.trap_scenes(unit)
            if sc is not None:
                hwptrap = True
                if not seen or seen[-1] != sc:
                    seen.append(sc)
            names = (sc or "").split(",")
            if first_warn is None and any(n.startswith("warn") for n in names):
                first_warn = now
            if first_on is None and any(n.startswith("on") for n in names):
                first_on = now
            p = self.player()
            if watch == "hp":
                # only once the trap has gone off: a leftover burn the settle loop outlasted
                # read as the arrow shooter's hit at 122 ms, before it had fired
                fired = first_warn is not None or first_on is not None or not hwptrap
                got = fired and (p.get("hp", hp0) < hp0 or p.get("dead"))
            elif watch == "mana":
                got = p.get("mana", mana0) < mana0
            else:
                got = self.buff_on(watch)
            if got:
                hit = now
                break
            time.sleep(0.05)
        if hit is not None and name.startswith("glyph_dart"):
            # the whole ring has flown by in 0.6 s. One arrow or the stab is 20 + 20% of
            # current health (36 from 160); a player at the stab's edge can get both (69),
            # never the whole ring (138 before)
            time.sleep(0.6)
            lost = hp0 - self.player().get("hp", hp0)
            self.flag(f"{name}_one_hit", lost <= 70, f"lost {lost} health to the glyph (an arrow and the stab at most: 69)")
        p1 = self.player()
        note = (f"{unit.split('/')[-1]} at {dx},{dy}; spawn ok {r.get('ok')}; scenes {seen[:6]}; warn at {first_warn} ms, on at {first_on} ms, "
                f"{watch.split(':')[-1]} at {hit} ms; hp {hp0}->{p1.get('hp')} mana {mana0}->{p1.get('mana')}")
        self.flag(f"{name}_works", hit is not None, note)
        if warn:
            lead = None if first_warn is None or hit is None else hit - first_warn
            # the first warn poll can land up to a poll late (~0.1-0.2 s)
            need = WARN_MIN if warn >= 900 else warn // 2
            self.flag(f"{name}_telegraphed", lead is not None and lead >= need, f"warned {lead} ms before the {watch.split(':')[-1]} (want >= {need})")
        if p1.get("dead"):
            self.gl("cheat", "cht_revive")
            time.sleep(1.0)

    def open_spot(self, needs=(80, 64, 48)):
        """The nearest point with clear floor `need` px all round (gl terrain, 16 px cells),
        the first of `needs` that some point has (a crypt of 96 px corridors has none at 80):
        the floor section leaves the player 40 px from a wall shooter, and a shooter or turret
        spawned 48-64 px off went into that wall (a shot that never came, a turret that never
        saw the player). (x, y), or the player's spot when none is found."""
        p = self.player()
        x0, y0 = float(p.get("x", 0)), float(p.get("y", 0))
        t = self.gl("terrain", 368, 16)
        rows, n, step = t.get("rows") or [], t.get("size", 0), t.get("step", 16)
        tx, ty = float(t.get("x", x0)), float(t.get("y", y0))
        for need in needs:
            k = need // step
            best = None
            for cy in range(k, len(rows) - k):
                for cx in range(k, len(rows[cy]) - k):
                    if any(rows[y][x] == "#" for y in range(cy - k, cy + k + 1) for x in range(cx - k, cx + k + 1)):
                        continue
                    d = (cx - n // 2) ** 2 + (cy - n // 2) ** 2
                    if best is None or d < best[0]:
                        best = (d, cx, cy)
            if best is not None:
                self.notes.append(f"clear for {need} px all round")
                return tx + (best[1] - n // 2) * step, ty + (best[2] - n // 2) * step
        self.notes.append(f"no spot clear for {needs[-1]} px within 368 px; testing at {x0:.0f},{y0:.0f}")
        return x0, y0

    def sec_kinds(self, only=""):
        want = [k.strip() for k in only.split(",") if k.strip()] or list(KINDS)
        self.god(False)
        x, y = self.open_spot()
        self.gl("teleport", x, y)
        time.sleep(0.5)
        self.notes.append(f"kinds tested at {x:.0f},{y:.0f}")
        for name in want:
            try:
                # each kind on the same spot: the bot destroys the last one first
                self.gl("teleport", x, y)
                self.kind(name, KINDS[name])
            except Exception as e:
                self.flag(f"{name}_raised", False, repr(e))
        self.reset()

    def sec_floor(self, only=""):
        log = self.g.read_log()
        themes = re.findall(r"traps: theme (\S+) \((\w+)\): (.*)", log)
        kinds = re.findall(r"traps: kinds (.*)", log)
        placed = re.findall(r"traps: placed (\d+)/(\d+) on a \d+x\d+ floor", log)
        self.flag("floor_theme_logged", bool(themes), f"{themes[-1:]}")
        self.flag("floor_placed", bool(placed) and int(placed[-1][0]) > 0, f"{placed[-1:]}")
        if not themes or not kinds:
            return
        theme, group, _ = themes[-1]
        w, groups = weights()
        g = groups.index(group)
        got = {}
        for part in kinds[-1].strip().split(", "):
            pid, _, n = part.rpartition(" ")
            got[pid] = int(n)
        wrong = {pid: n for pid, n in got.items() if w.get(family(pid), [1] * len(groups))[g] <= 0}
        cap = caps()
        over = {pid: n for pid, n in got.items() if cap.get(pid, -1) >= 0 and n > cap[pid]}
        fams = sorted({family(pid) for pid in got})
        self.flag("floor_kinds_fit_theme", not wrong, f"theme {theme} ({group}): {got}; not for this theme: {wrong}")
        self.flag("floor_kinds_capped", not over, f"over max-num: {over}")
        self.out["families"] = fams
        # a wall shooter, for the screenshot
        r = self.gl("unitsof", *[f"{U}hwp_shooter_{a}_{f}.unit" for a in ("arrow", "poison", "fire", "blade") for f in "sew"])
        spots = [(k, u) for k, v in r.items() if isinstance(v, dict) for u in (v.get("units") or [])]
        self.out["shooters"] = len(spots)
        if spots:
            k, u = spots[0]
            face = k.removesuffix(".unit")[-1]
            dx, dy = {"s": (0, 40), "e": (40, 0), "w": (-40, 0)}[face]
            self.gl("cull", "all")
            self.god(True)
            self.gl("teleport", u["x"] + dx, u["y"] + dy)
            time.sleep(1.5)
            self.notes.append(f"shooter for the screenshot: {k} at {u['x']:.0f},{u['y']:.0f}")


    def sec_confusion_off(self, only=""):
        themes = re.findall(r"traps: theme (\S+) \((\w+)\): (.*)", self.g.read_log())
        line = themes[-1][2] if themes else ""
        self.flag("confusion_off_not_rolled", bool(themes) and "confusion" not in line, f"rolls: {line}")
        self.god(False)
        x, y = self.open_spot()
        self.gl("teleport", x, y)
        for unit in ("hwp_glyph_confusion.unit", "hwp_plate_confusion.unit"):
            self.reset()
            self.gl("spawn", U + unit, 0, 0)
            t0 = time.time()
            got = False
            scenes = set()
            while time.time() - t0 < 7 and not got:
                sc = self.trap_scenes(U + unit)
                if sc is not None:
                    scenes.add(sc)
                got = self.buff_on(BUFFS + "hwp_trap_confusion")
                time.sleep(0.2)
            self.flag(f"confusion_off_{unit.split('_')[1]}_dark", not got and scenes == {"off"}, f"buff {got}; scenes {sorted(scenes)}")
        self.reset()


def run(p, sections="kinds,floor", only=""):
    c = Checks(p)
    for s in [s.strip() for s in sections.split(",") if s.strip()]:
        fn = getattr(c, "sec_" + s, None)
        if fn is None:
            c.flag("unknown_section_" + s, False, "")
            continue
        try:
            fn(only)
        except Exception as e:  # a failed read must not hide the other sections
            c.flag(s + "_raised", False, repr(e))
    c.out["ok"] = all(v for k, v in c.out.items() if isinstance(v, bool))
    c.out["notes"] = c.notes
    c.out["terminal"] = "; ".join(f"{k}={v}" for k, v in c.out.items() if isinstance(v, bool) and not v) or "all checks passed"
    return c.out
