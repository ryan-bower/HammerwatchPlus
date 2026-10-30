"""Issue #36, "projectile colors option not changing anything": what the projectiles in flight
really draw with, per preset.

A ranger in an empty Bandit Keep floor (god mode) fires its bow while a fire magic tower
shoots fireballs back (a NewProjectile that flies for seconds; a guard sentry's crossbow bolt is
a ray projectile, gone between two polls). For each preset (`hwp colors <preset>`), `gl projs` (GameLab verb, the
unit's GetMultiplyColor, its owner and whether that owner is a player's) is read while shots fly:
every projectile seen, friendly and enemy, is tallied by unit and by the colour it draws with.
A shot per preset is taken for the eye.

Sections: pixels (measure only: each projectile held still and shot plain, multiplied and
overlaid; mode "town" or "floor"), tint (the checks: the multiply colours on live shots and a
ring in the team's colour drawn around held ones)."""
import math
import re
import time

from gamelab.bots.plan_classesb import Checks as Base

TOWER = "actors/misc/tower_magic/tower_magic_fire.unit"
PRESETS = {
    "contrast": ((1.0, .35, .35), (.45, .8, 1.0)),
    "deuteranopia": ((1.0, .6, .1), (.3, .6, 1.0)),
    "default": ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
}


def close(mul, rgb, tol=.02):
    return mul is not None and all(abs(a - b) <= tol for a, b in zip(mul[:3], rgb))


class Checks(Base):
    def setup_ranger(self):
        r, pl, _ = self.new_char("ranger", "LabColors")
        self.flag("col_char", pl.get("level", 0) >= 20, str(pl)[:200])
        if not self.enter_floor("col"):
            return False
        return True

    def volley(self, seconds=3.0):
        """The ranger fires along +x while the tower (90 px out) shoots back; `gl projs` every
        ~0.15 s. Returns {unit name: {"friendly": bool, "muls": {mul tuple: count}}}."""
        seen = {}
        self.gl("kill", 400, "tower_magic")
        self.gl("spawn", TOWER, 90, 0)
        time.sleep(0.8)
        end = time.time() + seconds
        while time.time() < end:
            self.gl("input", 400, 0, 0, 1, 0, "main")
            for _ in range(3):
                r = self.gl("projs", 400)
                for p in r.get("projs", []):
                    row = seen.setdefault(p["name"].rsplit("/", 1)[-1], {"friendly": p.get("friendly"), "behavior": p.get("behavior"), "muls": {}})
                    key = tuple(round(v, 2) for v in p.get("mul", []))
                    row["muls"][key] = row["muls"].get(key, 0) + 1
                time.sleep(0.1)
        return seen

    def preset(self, name):
        said = self.hwp(f"colors {name}", 0.5, until="Projectile colours")
        return said

    def pixels(self, mode="floor"):
        """Each SHOW projectile held still beside the player: shot plain, with the contrast
        preset's colour as a multiply (what the module did) and as an overlay at 0.6 (what the
        damage flash does), and the pixels it covers compared. Where the shot lands on screen:
        the player's screen position from a shot of the empty scene is not needed, the
        projectile is found by difference against the empty shot."""
        if mode == "floor":
            if not self.setup_ranger():
                return
        else:
            self.god(True)
        self.preset("default")
        self.gl("kill", 400, "tag:enemy")
        time.sleep(0.5)
        rows = {}
        # the control: the player's own unit, multiplied and overlaid blue
        pid = "me"
        for how, args in (("mul", (.2, .3, 1)), ("overlay", (.2, .3, 1, .6))):
            self.gl("unitcolor", pid, how, *args)
            time.sleep(0.3)
            self.g.shot(f"px-player-{how}")
            self.gl("unitcolor", pid, "mul", 1, 1, 1)
            self.gl("unitcolor", pid, "overlay", 1, 1, 1, 0)
        base = self.g.shot("px-base")
        for path, friendly in SHOW:
            name = "-".join(path.replace(".unit", "").split("/")[-3::2])
            enemy, fr = PRESETS["contrast"]
            col = fr if friendly else enemy
            r = self.gl("projshow", path, OFF[0], OFF[1], 1 if friendly else 0)
            uid = r.get("unit")
            if not r.get("ok") or not uid:
                rows[name] = {"err": str(r)[:160]}
                continue
            time.sleep(0.4)
            live = [q for q in self.gl("projs", 200).get("projs", []) if q.get("unit") == uid]
            plain = self.g.shot(f"px-{name}-plain")
            self.gl("unitcolor", uid, "mul", *col)
            time.sleep(0.3)
            mul = self.g.shot(f"px-{name}-mul")
            self.gl("unitcolor", uid, "mul", 1, 1, 1)
            self.gl("unitcolor", uid, "overlay", *col, 0.6)
            time.sleep(0.3)
            over = self.g.shot(f"px-{name}-overlay")
            self.gl("unitdestroy", 200, path)
            time.sleep(0.3)
            # where the sprite is: the pixels that changed between the empty shot and the plain one
            from PIL import Image, ImageChops
            # near where it was put (the player is mid-screen, 1 px a pixel at 640x360): elsewhere
            # torches and foliage flicker
            win = (320 + OFF[0] - 30, 180 + OFF[1] - 30, 320 + OFF[0] + 30, 180 + OFF[1] + 30)
            diff = ImageChops.difference(Image.open(base).convert("RGB"), Image.open(plain).convert("RGB")).crop(win)
            box = diff.convert("L").point(lambda v: 255 if v > 30 else 0).getbbox()
            if box:
                box = (box[0] + win[0], box[1] + win[1], box[2] + win[0], box[3] + win[1])
            if not box:
                rows[name] = {"err": "not drawn", "reply": r, "live": live}
                continue
            cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
            st = {k: sprite_stats(base, f, cx, cy) for k, f in (("plain", plain), ("mul", mul), ("overlay", over))}
            rows[name] = {"friendly": friendly, "box": box, "reply_mul": r.get("mul"), "live": live, **st}
        self.out["pixels"] = rows
        self.notes.append(f"pixels: {rows}")

    @staticmethod
    def ring_pixels(shot, bare, at, rgb, half=16, tol=70):
        """A marker ring in `rgb` near a screen point: for each centre within `half` px, the
        pixels 4.5-7.5 px out that match the colour in `shot` but not in `bare` (the same scene
        with markers off). It counts only if it is ring-shaped: at least 3 in each quadrant and
        a hollow middle. The best centre's count; 0 when there is no ring. The ring draws
        lighter than its colour (#73ccff came out (173,225,249)), hence the wide tolerance;
        the shape test keeps torch flicker and fire sparks out (pf 20261029-062036 counted 7 of
        them as ring with a plain colour count). The centre is not exactly 40 px from the
        screen's middle, since the camera leads the aim."""
        from PIL import Image
        want = [round(255 * c) for c in rgb]
        on, off = (Image.open(s).convert("RGB").load() for s in (shot, bare))
        def match(px, x, y):
            return all(abs(v - w) <= tol for v, w in zip(px[x, y], want))
        ring = [(dx, dy) for dx in range(-8, 9) for dy in range(-8, 9) if 4.5 <= math.hypot(dx, dy) <= 7.5]
        middle = [(dx, dy) for dx in range(-3, 4) for dy in range(-3, 4) if math.hypot(dx, dy) <= 3]
        top = 0
        for cy in range(at[1] - half, at[1] + half + 1):
            for cx in range(at[0] - half, at[0] + half + 1):
                hit = [(dx, dy) for dx, dy in ring if match(on, cx + dx, cy + dy) and not match(off, cx + dx, cy + dy)]
                quads = [sum(1 for dx, dy in hit if (dx >= 0) == qx and (dy >= 0) == qy) for qx in (0, 1) for qy in (0, 1)]
                if min(quads) >= 3 and sum(match(on, cx + dx, cy + dy) for dx, dy in middle) <= 2:
                    top = max(top, len(hit))
        return top

    @staticmethod
    def drawn_most(said):
        m = re.findall(r"markers (on|off) \((\d+) at once", said)
        return int(m[-1][1]) if m else -1

    def tint(self):
        """Per preset: the live shots of both sides carry the preset's multiply colour (gl projs),
        and a projectile held still beside the player, a friendly wizard fireball and an enemy
        cult shadow bolt, has a ring in its team's colour drawn around it on screen (pixels of
        that colour around it); with the default preset no ring and no tint."""
        if not self.setup_ranger():
            return
        # on the floor beside the player (at y -30 the left one sat in the wall and died)
        held = (("players/wizard/projectiles/fireball.unit", True, (40, 10)),
                ("actors/humans/cult/projectiles/shadow_bolt.unit", False, (-40, 10)))
        for name, (enemy, friendly) in PRESETS.items():
            said = self.preset(name)
            seen = self.volley()
            self.g.shot(f"colors-{name}", settle=False)
            fr = {k: v for k, v in seen.items() if v["friendly"]}
            en = {k: v for k, v in seen.items() if not v["friendly"]}
            bad = {k: list(v["muls"]) for k, v in seen.items()
                   if not all(close(m, friendly if v["friendly"] else enemy) for m in v["muls"])}
            self.flag(f"col_{name}_friendly_seen", bool(fr), f"{said.strip()[-120:]!r}; friendly {list(fr)}")
            self.flag(f"col_{name}_enemy_seen", bool(en), f"enemy {list(en)}")
            self.flag(f"col_{name}_drawn", bool(seen) and not bad, f"not drawn in the preset's colour: {bad}; all {seen}")
            # the rings, on projectiles held still
            self.gl("kill", 400, "tower_magic")
            time.sleep(1.0)
            for path, fr_, off in held:
                self.gl("projshow", path, off[0], off[1], 1 if fr_ else 0)
            time.sleep(0.5)
            shot = self.g.shot(f"rings-{name}")
            self.hwp("colors markers off", 0.5, until="markers off")
            bare = self.g.shot(f"rings-{name}-off")
            self.hwp("colors markers on", 0.5, until="markers on")
            rings = {}
            for path, fr_, off in held:
                rgb = friendly if fr_ else enemy
                # the ring is the team colour; for default, look for the contrast colours instead
                look = rgb if name != "default" else PRESETS["contrast"][1 if fr_ else 0]
                at = (320 + off[0], 180 + off[1])
                rings[path.rsplit("/", 1)[-1]] = self.ring_pixels(shot, bare, at, look)
                self.gl("unitdestroy", 200, path)
            said = self.hwp("colors", 0.5, until="Projectile colours")
            most = self.drawn_most(said)
            if name == "default":
                # (most drawn at once is per level, so it still holds the earlier presets' count)
                self.flag("col_default_no_rings", all(n <= 2 for n in rings.values()),
                          f"ring pixels (ring-shaped, markers on over off) {rings}; most drawn at once {most}")
            else:
                self.flag(f"col_{name}_rings", all(n >= 12 for n in rings.values()) and most >= 2,
                          f"ring pixels (ring-shaped, markers on over off) {rings}; most drawn at once {most}")
        self.preset("default")

def run(p, sections="tint", mode="floor", **_):
    c = Checks(p)
    for s in sections.split(","):
        getattr(c, s)(mode) if s == "pixels" else getattr(c, s)()
    return {**c.out, "notes": c.notes}
