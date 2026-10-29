"""The Arcane (Sorcerer) and Aerotheurge (Wizard) fixes of 2026-10-25 (mods/specs, scenario
fix-specs-arcane), each section a fresh level-20 character in an emptied Bandit Keep floor:

- blink_range: Blink is 112 px (90 before), the whole way when nothing is in the way; a shot
  150 ms after the cast catches the new effects (blink_out, the trail beads, blink_in), the log
  line counts them; Far Step rare makes it 151; `hwp specs arcane` reads the distance.
- blink_ledge: a 48 px line of ledge rails (doodads/ledges/barracks/e_16.unit or w_16.unit, a
  2 px shoot-through rect) 46 px ahead. `gl bodies` sees the rail bodies on the way (they stop a
  walk and the dash), `gl rayhit` (the Shot ray) does not stop at them, a dash press does not
  get past them, and Blink lands on the far side ("over ledge" in its log line).
- orb: the Thunder Orb's unit file reads speed 2.0, a 3 px body, the ball at radius 5 and the
  sprite at 1.5x; a cast logs `thunder orb: speed 2.00 px/tick`; the orb's position read twice
  through `gl near` gives about 60 px/s; a shot in flight. The wizard's status reads the vanilla
  bars (`living 0 bar off`).
- pool: an Arcane's `hwp specs arcane` reads `living 1 bar on` and the log says the health and
  mana bars are hidden; the pool number is the state's manaExact, health is the pool's fraction,
  a real hit drains the pool by what it took, a heal fills it; a shot of the one blue bar.

Sections: blink_range, blink_ledge, orb, pool (all by default).
"""
import re
import time
from pathlib import Path

from gamelab.bots.plan_specs import Checks as Base

REPO = Path(__file__).resolve().parents[2]
BL, LM = "hwp_sor_blink", "hwp_sor_living_mana"
TT, SC = "hwp_wiz_tempest_torrent", "hwp_wiz_static_charge"
# a ledge rail: e_16's rect is x 6..8 of the unit, 16 tall; w_16's is x 0..2
LEDGE_E = "doodads/ledges/barracks/e_16.unit"
LEDGE_W = "doodads/ledges/barracks/w_16.unit"


def num(text, label):
    m = re.findall(re.escape(label) + r" (-?\d+)", text)
    return int(m[-1]) if m else None


class Checks(Base):
    def arcane_char(self, key):
        """A level-20 sorcerer with the Arcane spec and both skills (plan_specs.arcane's setup)."""
        r, pl, lv = self.new_char("sorcerer", "LabArc" + key.capitalize())
        time.sleep(0.5)
        pl = self.gl("state").get("player", {})
        self.flag(f"{key}_char", r.get("ok") and pl.get("class") == "sorcerer" and pl.get("level", 0) >= 20,
                  f"{r} class {pl.get('class')} level {pl.get('level')}")
        took = self.gl("subclass", "hwp_sorcerer_arcane").get("class")
        self.hwp("skillpoints 40")
        self.lvl = {s: self.gl("skill", s, 1).get("level", 0) for s in (BL, LM)}
        self.flag(f"{key}_learned", took == "hwp_sorcerer_arcane" and all(v >= 1 for v in self.lvl.values()),
                  f"subclass {took}, levels {self.lvl}")
        time.sleep(0.5)

    def status(self):
        """The `hwp specs arcane` line."""
        return self.hwp("specs arcane", 0.5, until="specs arcane:")

    def blink_shot(self, dx, dy, shot):
        """Blink through castat inside an aim hold, a shot 150 ms after the cast (the effects
        live 300-450 ms). Returns (activated, the blink log line, position before, after)."""
        self.gl("input", 600, 0, 0, dx, dy)
        time.sleep(0.1)
        p0 = self.pos()
        mark = len(self.g.read_log())
        r = self.gl("castat", BL, dx, dy, "nocd")
        time.sleep(0.15)
        self.g.shot(shot, settle=False)
        time.sleep(0.45)
        line = "\n".join(l for l in self.g.read_log()[mark:].splitlines() if "blink:" in l)
        return bool(r.get("activated")), line, p0, self.pos()

    @staticmethod
    def moved(p0, p1):
        return ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5

    # --- sections
    def blink_range(self):
        self.arcane_char("range")
        if not self.enter_floor("range"):
            return
        fx, fy = self.open_dir(260)
        x0, y0 = self.pos()
        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink_shot(fx, fy, "blink_fx")
        moved = self.moved(p0, p1)
        self.flag("range_112", ok and 104 <= moved <= 118 and "px of 112" in line,
                  f"activated {ok}, moved {moved:.1f} px (112 wanted): {line[-100:]!r}")
        fxn = re.findall(r"fx (\d+)", line)
        # blink_out, a bead every 16 px (6 for 112), blink_in, the arcane explosion: 9
        self.flag("range_fx", bool(fxn) and int(fxn[-1]) >= 8, f"effects counted {fxn}; shot blink_fx")

        self.gl("teleport", round(x0, 1), round(y0, 1))
        time.sleep(0.2)
        self.gl("orb", "hwp_sor_bl_far_step", 3)
        time.sleep(0.3)
        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink_shot(fx, fy, "blink_far_step")
        moved = self.moved(p0, p1)
        self.flag("range_far_step", ok and 143 <= moved <= 158 and "px of 151" in line,
                  f"moved {moved:.1f} px (112 x 1.35 = 151): {line[-100:]!r}")
        st = self.status()
        self.flag("range_status", "dist 151" in st and num(st, "blinks") == 2 and num(st, "ledges") == 0 and num(st, "want") == 151,
                  st.strip()[-200:])
        self.to_town()

    def blink_ledge(self):
        self.arcane_char("ledge")
        if not self.enter_floor("ledge"):
            return
        # the rail is vertical: a lane east or west with 200 px free. The floor's entry spot
        # has walls 80 and 96 px away (lab 20261025-225429), so when neither side is free the
        # sorcerer is teleported 120 px along the clearest direction and looks again (5 tries).
        x, y = self.pos()
        d = 0
        tries = 0
        while d == 0 and tries < 5:
            for dx in (1, -1):
                r = self.gl("rayhit", round(x, 1), round(y, 1), round(x + dx * 200, 1), round(y, 1))
                free = 200 if not r.get("wall") else float(r.get("wd", 0.0))
                if free >= 200:
                    d = dx
                    break
            if d == 0:
                ox, oy = self.open_dir(230)
                self.gl("teleport", round(x + ox * 120, 1), round(y + oy * 120, 1))
                time.sleep(0.3)
                x, y = self.pos()
                tries += 1
        self.flag("ledge_lane", d != 0, f"east/west lane {d} from {x:.0f},{y:.0f} after {tries} move(s)")
        if d == 0:
            return
        unit, ox = (LEDGE_E, 40) if d > 0 else (LEDGE_W, -48)
        for dy in (-24, -8, 8):
            self.gl("spawn", unit, ox, dy)
        time.sleep(0.6)
        rail_x = x + d * 46

        b = self.gl("bodies", round(x + d * 112, 1), round(y, 1), 8)
        rails = [e for e in b.get("bodies") or [] if not e.get("actor") and abs(float(e.get("atX", -9999)) - rail_x) <= 12]
        self.flag("ledge_body", len(rails) >= 1 and any("ledges" in (e.get("name") or "") for e in rails),
                  f"bodies on the way: {[(e.get('name'), round(float(e.get('atX', 0)))) for e in (b.get('bodies') or []) if not e.get('actor')]}")
        r = self.gl("rayhit", round(x, 1), round(y, 1), round(x + d * 112, 1), round(y, 1))
        self.flag("ledge_shot_ray", not r.get("wall") or abs(float(r.get("wx", 0)) - rail_x) > 10,
                  f"the Shot ray from the player past the rail: wall {r.get('wall')} at {r.get('wx')},{r.get('wy')} ({r.get('wname')})")

        # the dash does not get through (the user's premise)
        self.gl("input", 320, d, 0, d, 0, "dash")
        time.sleep(1.0)
        px, py = self.pos()
        self.flag("ledge_dash_blocked", (px - rail_x) * d < 0, f"after a dash toward the rail at x {rail_x:.0f}: {px:.1f},{py:.1f}")
        self.gl("teleport", round(x, 1), round(y, 1))
        time.sleep(0.3)

        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink_shot(d, 0, "blink_ledge_fx")
        moved = self.moved(p0, p1)
        past = (p1[0] - rail_x) * d > 4
        self.flag("ledge_crossed", ok and past and moved >= 100 and "over ledge" in line,
                  f"rail at x {rail_x:.0f}; {p0[0]:.0f},{p0[1]:.0f} -> {p1[0]:.0f},{p1[1]:.0f} ({moved:.1f} px): {line[-100:]!r}")
        self.g.shot("blink_ledge", settle=False)
        st = self.status()
        self.flag("ledge_status", num(st, "ledges") == 1, st.strip()[-200:])
        self.to_town()

    def orb(self):
        self.setup("orb", "wizard", "hwp_wizard_invocation", [TT, SC])
        unit = (REPO / "mods/specs/players/hwp/specs/invocation/torrent.unit").read_text(encoding="utf-8")
        fxf = (REPO / "mods/specs/players/hwp/specs/effects/orb.effect").read_text(encoding="utf-8")
        wants = ('<float name="speed">2.0</float>' in unit, '<circle radius="3" projectile="true" />' in unit,
                 "lightning_projectile_ball_2.effect?radius=5" in unit, 'scale-x="1.5" scale-y="1.5"' in fxf)
        self.flag("orb_unit_file", all(wants), f"speed 2.0, body 3, ball 5, sprite 1.5x: {wants}")
        st = self.status()
        self.flag("orb_vanilla_bars", "living 0 bar off" in st, st.strip()[-160:])
        if not self.enter_floor("orb"):
            return
        fx, fy = self.open_dir(300)

        def orb_pos():
            for u in self.gl("near", 600, "torrent").get("units") or []:
                return (float(u.get("x", 0)), float(u.get("y", 0)))
            return None

        self.gl("mana", 200)
        mark = len(self.g.read_log())
        self.gl("input", 600, 0, 0, fx, fy)
        time.sleep(0.1)
        r = self.gl("castat", TT, fx, fy, "nocd")
        time.sleep(0.5)
        a = orb_pos()
        t0 = time.time()
        self.g.shot("thunder_orb", settle=False)
        time.sleep(0.6)
        b = orb_pos()
        dt = time.time() - t0
        line = "\n".join(l for l in self.g.read_log()[mark:].splitlines() if "thunder orb:" in l)
        self.flag("orb_cast", bool(r.get("activated")) and "speed 2.00 px/tick" in line, f"activated {r.get('activated')}: {line[-100:]!r}")
        speed = self.moved(a, b) / dt if a and b and dt > 0 else -1
        self.flag("orb_speed", 45 <= speed <= 75, f"orb {a} -> {b} in {dt:.2f} s: {speed:.1f} px/s (2.0 px a tick, 60 wanted)")
        self.to_town()

    def pool(self):
        self.arcane_char("pool")
        mark0 = self.g.read_log()
        st = self.status()
        self.flag("pool_bar_on", "living 1 bar on" in st and "living mana bar: on" in mark0, st.strip()[-160:])
        if not self.enter_floor("pool"):
            return
        self.gl("mana", 80)
        time.sleep(0.4)
        pl = self.gl("state").get("player", {})
        st = self.status()
        m = re.findall(r"pool (\d+)/(\d+)", st)
        cur, mx = (int(m[-1][0]), int(m[-1][1])) if m else (-1, -1)
        # the pool regenerates between the two reads (lab 20261025-225429: 85 vs 82.3 of 413)
        self.flag("pool_numbers", abs(cur - pl.get("manaExact", -99)) <= max(3.0, 0.02 * mx) and mx == pl.get("manaMax"),
                  f"status pool {cur}/{mx}; state mana {pl.get('manaExact')}/{pl.get('manaMax')}, health {pl.get('hp')}/{pl.get('hpMax')}")
        hpf = pl.get("hp", 0) / max(1, pl.get("hpMax", 1))
        mf = pl.get("manaExact", 0) / max(1, pl.get("manaMax", 1))
        self.flag("pool_one_fraction", abs(hpf - mf) < 0.03, f"health fraction {hpf:.3f}, pool fraction {mf:.3f}")
        self.g.shot("pool_bar", settle=False)

        self.god(False)
        r = self.gl("damageme", 30)
        time.sleep(0.3)
        self.god(True)
        took, lost = r.get("took", 0), (r.get("mana0") or 0) - (r.get("mana") or 0)
        self.flag("pool_hit_drains", took > 0 and abs(lost - took) <= 1 and not r.get("dead"),
                  f"30 pure: took {took}, pool {r.get('mana0')} -> {r.get('mana')} (lost {lost:.1f}), dead {r.get('dead')}")

        # a heal fills the one pool (the health the game gives turns into mana next frame)
        c0 = num(self.specs(), "converted") or 0
        pl = self.gl("state").get("player", {})
        f0 = pl.get("manaExact", 0) / max(1, pl.get("manaMax", 1))
        self.gl("hurt", round(min(0.95, f0 + 0.2), 3))
        time.sleep(0.4)
        c1 = num(self.specs(), "converted") or 0
        want = (min(0.95, f0 + 0.2) - f0) * pl.get("hpMax", 1)
        self.flag("pool_heal_fills", c1 - c0 >= want - 2, f"health +{want:.0f}: converted {c0} -> {c1}")
        self.g.shot("pool_bar_after", settle=False)
        self.to_town()


def run(p, sections="blink_range,blink_ledge,orb,pool", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
