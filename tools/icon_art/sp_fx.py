"""The 4th specializations' world sprites (art/specs/REQUESTS.md, second priority), painted
with vpaint like the icons but on a transparent ground: each a horizontal strip of frames.

    python tools/icon_art/sp_fx.py   # art/specs/fx/<name>.png, and previews in out/specs/fx/
                                     # (<name>.gif at 4x on a dark floor, sheet.png)

fx_pyrebrand_sigil      4 x 24x24   the brand hovering over a branded enemy, a slow burning pulse
fx_hellfire_claw        6 x 32x48   the claw tearing up out of the ground, then dying down
fx_battlefield_standard 4 x 24x40   frames 0-1 carried (cloth streaming), 2-3 planted (staked, calmer)
fx_tempest_orb          4 x 24x24   the Tempest Torrent orb, crackling

tools/make_specs_fx.py packs these strips into the mod's effects/fx.png (256x128) and its
effects hard-code the frame rects: keep the strip sizes, and after a redraw run that tool.

Fire and lightning are meant for an additive material: their dim halo pixels are kept
(they add little). The standard is a solid sprite for an alpha-blended material.
Unpainted pixels are fully transparent."""
import math
from pathlib import Path
from PIL import Image
import sp
from sp import ball, sigil, banner, path, zig, ELEC, HELL, ESS
from vpaint import Icon, BLACK, R, circle, ellipse, seg, union, EMBER, FIRE

HERE = Path(__file__).resolve().parent
FX = sp.REPO / "art" / "specs" / "fx"
PREV = HERE / "out" / "specs" / "fx"
SIZE = {"fx_pyrebrand_sigil": (24, 24, 4), "fx_hellfire_claw": (32, 48, 6),
        "fx_battlefield_standard": (24, 40, 4), "fx_tempest_orb": (24, 24, 4)}


class Frame:
    """A w x h frame painted on a square vpaint canvas: (ox, oy) is the frame's corner on
    it, so a painter adds ox/oy to its coordinates. cut() keeps the frame, alpha 0 where
    nothing was painted."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ic = Icon(max(w, h))
        self.ox, self.oy = (self.ic.n - w) / 2, (self.ic.n - h) / 2

    def cut(self):
        ox, oy = int(self.ox), int(self.oy)
        im = self.ic.im.crop((ox, oy, ox + self.w, oy + self.h)).convert("RGBA")
        px = im.load()
        for y in range(self.h):
            for x in range(self.w):
                if px[x, y][:3] == BLACK:
                    px[x, y] = (0, 0, 0, 0)
        return im


# ---------------------------------------------------------------- the four
def tempest_orb():
    out = []
    for k in range(4):
        f = Frame(24, 24)
        ic = f.ic
        r = 5.6 + (0.4 if k % 2 else 0)
        ball(ic, f.ox + 12, f.oy + 12, r, seed=k * 3 + 1, bolts=3)
        # two arcs licking out of the ball, a different way each frame
        for j in range(2):
            a = math.radians(k * 97 + j * 180 + 20)
            x0, y0 = 12 + math.cos(a) * r * 0.8, 12 + math.sin(a) * r * 0.8
            x1, y1 = 12 + math.cos(a + 0.5) * 11, 12 + math.sin(a + 0.5) * 11
            ic.energy(path(zig(f.ox + x0, f.oy + y0, f.ox + x1, f.oy + y1, 3, 1.4, k * 5 + j), 0.55, 0.3), ELEC, falloff=0.4)
        out.append(f.cut())
    return out


def pyrebrand_sigil():
    out = []
    for k, (pulse, w) in enumerate(((0.2, 0.45), (0.6, 0.55), (1.0, 0.65), (0.6, 0.55))):
        f = Frame(24, 24)
        ic = f.ic
        cx, cy = f.ox + 12, f.oy + 12.5
        ic.glow(cx, cy, 11, "a81e08", pulse)
        sigil(ic, cx, cy, 7.4, HELL, w=w, fall=0.4 + pulse * 0.5)
        # embers rising off it, a little higher each frame
        for j, (x, y0) in enumerate(((6, 18), (17, 16), (11, 21), (19, 8))):
            y = y0 - k * 2.2 - j
            if 1 < y < 23:
                ic.energy(circle(f.ox + x + math.sin(k + j) * 0.8, f.oy + y, 0.6), EMBER, falloff=0.5)
        out.append(f.cut())
    return out


CLAW = R("0a0204", "2a0806", "4e120a", "7a2010", "b03a18", "e07030")   # the talons: dark horn, lit by the fire


def claw_frame(ic, cx, by, s, t, fire, seed=0):
    """Three hooked talons grown to t of their height: dark horn in a fringe of fire."""
    for k, (dx, h, bow, hook) in enumerate(((-4.2, 10.5, -2.6, 3.0), (0, 13, 0.8, -1.6), (4.2, 10, 2.6, -3.0))):
        h = h * t
        n = 8
        pts = [(cx + (dx + bow * math.sin(math.pi * u * 0.9) + hook * u ** 3) * s, by - h * u * s)
               for u in (j / n for j in range(n + 1))]
        w0 = 1.05 * s * (0.6 + 0.4 * t)
        ic.energy(path(pts, w0 + 1.0, 0.8), fire, falloff=0.9, seed=seed + k)
        ic.solid(path(pts, w0, 0.25 * s), CLAW, seed=seed + k, base=2.6, light=(-0.8, -0.6))


def hellfire_claw():
    out = []
    # grow from a burning crack, peak, flare, die down
    for k, (t, flare) in enumerate(((0.0, 0.3), (0.38, 0.6), (0.72, 0.8), (1.0, 1.0), (1.0, 0.7), (0.8, 0.35))):
        f = Frame(32, 48)
        ic = f.ic
        cx, by = f.ox + 16, f.oy + 43
        ic.glow(cx, by - 4, 16, "a81e08", flare * 0.8)
        ic.energy(ellipse(cx, by + 0.5, 12, 2.8), HELL if k < 5 else EMBER, falloff=1.0 + flare)
        for j, (x0, x1) in enumerate(((-12, -3), (3, 13))):
            ic.energy(path(zig(cx + x0, by + 1, cx + x1, by - 0.5, 3, 1.0, j + k), 0.5), HELL, falloff=0.4)
        if t > 0:
            claw_frame(ic, cx, by, 2.6, t, HELL if k < 5 else EMBER, seed=k)
        if k >= 3:  # embers thrown off the talon tips
            for j, (x, y) in enumerate(((-10, 6), (9, 10), (-3, 3), (13, 18))):
                yy = f.oy + y + (k - 3) * -2.5
                ic.energy(circle(f.ox + 16 + x, yy, 0.8), FIRE, falloff=0.6)
        out.append(f.cut())
    return out


def battlefield_standard():
    out = []
    for k in range(4):
        f = Frame(24, 40)
        ic = f.ic
        planted = k >= 2
        px = f.ox + 4.5
        if planted:
            # staked in the ground: a mound of earth at the pole's foot, the cloth calmer
            banner(ic, px, f.oy + 2, f.oy + 38.5, 1.55, wave=0.3 + (k - 2) * 0.9, seed=1)
            ic.solid(ellipse(px, f.oy + 38.4, 4.2, 1.4), sp.EARTH, base=2.2)
        else:
            # carried: the pole's foot in the bearer's hands, the cloth streaming
            banner(ic, px, f.oy + 3, f.oy + 39.5, 1.55, wave=1.4 + k * 1.6, seed=1)
        out.append(f.cut())
    return out


PAINT = {"fx_pyrebrand_sigil": pyrebrand_sigil, "fx_hellfire_claw": hellfire_claw,
         "fx_battlefield_standard": battlefield_standard, "fx_tempest_orb": tempest_orb}


def strip(frames):
    w, h = frames[0].size
    im = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        im.paste(fr, (k * w, 0))
    return im


def preview(name, frames, z=4):
    """A looping 4x GIF on a dark floor, and the frames for the sheet."""
    floor = (34, 30, 28, 255)
    big = []
    for fr in frames:
        bg = Image.new("RGBA", fr.size, floor)
        bg.alpha_composite(fr)
        big.append(bg.resize((fr.width * z, fr.height * z), Image.Resampling.NEAREST).convert("P", palette=Image.Palette.ADAPTIVE))
    big[0].save(PREV / f"{name}.gif", save_all=True, append_images=big[1:], duration=160, loop=0)
    return big


def main():
    FX.mkdir(parents=True, exist_ok=True)
    PREV.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, fn in PAINT.items():
        frames = fn()
        w, h, n = SIZE[name]
        assert len(frames) == n and all(fr.size == (w, h) for fr in frames), name
        im = strip(frames)
        im.save(FX / f"{name}.png")
        rows.append(preview(name, frames))
        print(name, im.size)
    W = max(sum(b.width for b in r) + 8 * len(r) for r in rows)
    H = sum(r[0].height + 8 for r in rows)
    sheet = Image.new("RGB", (W, H), (20, 20, 24))
    y = 0
    for r in rows:
        x = 0
        for b in r:
            sheet.paste(b.convert("RGB"), (x, y))
            x += b.width + 8
        y += r[0].height + 8
    sheet.save(PREV / "sheet.png")


if __name__ == "__main__":
    main()
