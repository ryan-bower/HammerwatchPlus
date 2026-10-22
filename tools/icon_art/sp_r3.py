"""The 4th specializations' icons, round 3: every icon that is a recolour, shrink or copy of
another, or reuses another icon's main motif, redrawn as its own design, and the six spec
(class) emblems, which had only placeholders. Three ideas each, none of them built on any
of the 49 current icons (art/specs/override/) or on each other's motifs.

    python tools/icon_art/sp_r3.py [names...]   # out/specs/r3/<name>_<a|b|c>.png, out/specs/r3/sheet_<spec>.png
                                                # (the current icon, "now", beside the three)
    python tools/icon_art/sp_r3.py --picker     # also out/specs/r3/picker.html, ids specs3.<name>
    python tools/icon_art/sp_r3.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                # {"specs3.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
import sp

OUT = sp.HERE / "out" / "specs" / "r3"

LEAF = R("061204", "10300a", "1e5a14", "3a8a24", "6cc040", "b8ec80")
CRUST = R("1e1006", "4a2a0c", "7a4a18", "b07a30", "d8a850", "f4d898")     # bread crust
MEAT = R("1a0806", "4a1a10", "7a321c", "a85a30", "d08a50", "f0c088")
BLUE_STEEL = R("0a1220", "1a2a44", "2e4a70", "4a72a0", "7aa4cc", "c0dcf4")
PINK_GEM = R("2a0a1e", "5a1440", "8e2468", "c84a90", "f088c0", "ffd0ea", "ffffff")
DEMON = R("140404", "3a0a08", "6a140c", "9a2410", "c8401a", "f07a34")
EMBERS = R("140404", "3a0804", "6a1406", "a82a0a", "e05a14", "ffa040", "ffe0a0")


# ---------------------------------------------------------------- new objects
def helm(ic, cx, cy, s=1.0, rmp=STEEL, seed=0, slit=True):
    """A great helm from the front: flat-topped barrel, eye slit, breaths."""
    f = union(box(cx, cy + 0.8 * s, 5.0 * s, 5.4 * s, 0, 1.2 * s), ellipse(cx, cy - 3.8 * s, 5.0 * s, 2.8 * s))
    ic.solid(f, rmp, seed=seed, base=2.6)
    ic.solid(box(cx, cy + 0.6 * s, 0.8 * s, 5.4 * s, 0, 0.3), rmp, seed=seed + 1, base=3.6, spread=0.5)
    if slit:
        ic.paint(box(cx, cy - 1.2 * s, 4.2 * s, 0.55 * s, 0, 0.2), lambda x, y, d: rmp[0])
        for k in (-1, 1):
            for j in range(2):
                ic.px([(int(cx + k * 2.4 * s), int(cy + (2.2 + j * 1.6) * s))], rmp[0])


def feather(ic, cx, cy, ang, s=1.0, rmp=BREEZE, seed=0):
    """A long feather: the quill toward -u, the vane full, two notches in its edge."""
    def vane(u, v):
        d = ellipse(1.2, 0, 8.6, 2.6)(u, v)
        for nu in (-2.5, 3.0):
            d = max(d, -seg(nu, -3.2, nu + 1.6, -1.2, 0.35)(u, v))
        return d
    items = [(vane, rmp, {"base": 2.8}), (lseg(-10.5, 0, 9.4, 0, 0.45, 0.2), rmp, {"base": 4.4, "spread": 0.4})]
    parts(ic, cx, cy, ang, s, items, seed)


def tornado(ic, cx, top, bottom, w, rmp, seed=0):
    """A funnel: stacked ellipses narrowing toward the ground, leaning a little."""
    n = 7
    for k in range(n):
        t = k / (n - 1)
        y = top + (bottom - top) * t
        rx = w * (1 - t * 0.8)
        x = cx + math.sin(t * 3.2 + seed) * 1.6 * (1 - t * 0.3)
        ic.energy(cut(ellipse(x, y, rx, rx * 0.32 + 0.6), ellipse(x, y - 0.6, rx - 1.1, rx * 0.25)), rmp, falloff=0.6)


def hat(ic, cx, by, s=1.0, rmp=R("04061a", "0e1640", "1c2a6a", "2e4294", "4a64bc", "7a94e0"), band=ELEC, seed=0):
    """A wizard's pointed hat, brim at by, tip bending to the right."""
    ic.solid(ellipse(cx, by, 10.5 * s, 2.4 * s), rmp, seed=seed, base=2.0)
    ic.solid(poly([(cx - 6.0 * s, by - 0.6 * s), (cx + 6.0 * s, by - 0.6 * s), (cx + 2.4 * s, by - 10 * s), (cx + 6.4 * s, by - 15.5 * s),
                   (cx - 0.6 * s, by - 10.5 * s)]), rmp, seed=seed + 1, base=2.8)
    ic.energy(path(zig(cx - 5.6 * s, by - 2.0 * s, cx + 5.6 * s, by - 2.0 * s, 5, 0.9 * s, seed + 3), 0.6 * s), band, falloff=0.5)


def crystal(ic, cx, cy, s=1.0, rmp=ARCANE, seed=0):
    """A long faceted crystal standing on its point."""
    pts = [(cx, cy - 10 * s), (cx + 5 * s, cy - 3 * s), (cx + 3.4 * s, cy + 5 * s), (cx, cy + 10 * s), (cx - 3.4 * s, cy + 5 * s), (cx - 5 * s, cy - 3 * s)]
    ic.solid(poly(pts), rmp, seed=seed, base=3.0, light=(-0.8, -0.6))
    ic.solid(poly([(cx, cy - 10 * s), (cx + 5 * s, cy - 3 * s), (cx + 3.4 * s, cy + 5 * s), (cx, cy + 10 * s), (cx + 0.6 * s, cy - 1 * s)]),
             rmp, seed=seed + 1, base=1.8, spread=0.8)
    ic.solid(poly([(cx - 5 * s, cy - 3 * s), (cx, cy - 10 * s), (cx + 0.6 * s, cy - 1 * s), (cx - 3.4 * s, cy + 5 * s)]), rmp, seed=seed + 2, base=4.4, spread=0.8)


def quiver(ic, cx, cy, s=1.0, seed=0):
    """A quiver slung on a slant, three fletched arrow ends standing out of its mouth."""
    x0, y0, x1, y1 = cx - 3.4 * s, cy + 9.5 * s, cx + 2.4 * s, cy - 3.2 * s
    a = math.degrees(math.atan2(y1 - y0, x1 - x0))
    for k, dx in enumerate((-2.6, 0.2, 3.0)):
        bx, by = x1 + dx * s, y1 + 0.6 * s
        tx, ty = bx + (dx * 0.7 + 2.0) * s, by - 12.0 * s
        ic.energy(seg(bx, by, tx, ty, 0.5), VOLT, falloff=0.5)
        for d in (-1, 1):
            ic.solid(ellipse(tx + d * 0.9, ty + 1.8, 0.8, 2.0, d * 14), GUST, seed=seed + k + 4, base=3.6 - d * 0.6)
    ic.solid(seg(x0, y0, x1, y1, 2.9 * s, 3.4 * s), LEATHER, seed=seed + 8, base=2.6)
    ic.solid(ellipse(x1, y1, 3.4 * s, 1.3 * s, a + 90), R("0a0604", "1e140c", "3a2818"), base=1.4, spread=0.4)
    for t in (0.18, 0.78):
        px_, py_ = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        ic.solid(box(px_, py_, 3.3 * s, 0.7 * s, a + 90, 0.2), BRASS, seed=seed + 9, base=3.0)


def mask(ic, cx, cy, s=1.0, rmp=DEMON, eyes=HELL, seed=0):
    """A horned demon mask: a broad face, curling horns, burning eye slits."""
    for d in (-1, 1):
        ic.solid(path([(cx + d * 3.6 * s, cy - 3.6 * s), (cx + d * 7.4 * s, cy - 6.2 * s), (cx + d * 8.6 * s, cy - 10.4 * s), (cx + d * 7.0 * s, cy - 12.0 * s)],
                      1.4 * s, 0.3 * s), BONE, seed=seed + 3, base=2.8)
    ic.solid(union(ellipse(cx, cy, 6.0 * s, 6.6 * s), poly([(cx - 4.4 * s, cy + 3 * s), (cx + 4.4 * s, cy + 3 * s), (cx, cy + 9.4 * s)])), rmp, seed=seed, base=2.6)
    for d in (-1, 1):
        ic.energy(poly([(cx + d * 0.8 * s, cy - 0.6 * s), (cx + d * 4.6 * s, cy - 2.6 * s), (cx + d * 4.0 * s, cy + 0.6 * s)]), eyes, falloff=0.6)
    ic.paint(box(cx, cy + 4.4 * s, 2.4 * s, 0.5 * s, 0, 0.2), lambda x, y, d: rmp[0])


def horned_flame(ic, cx, by, s=1.0, rmp=HELL, seed=0):
    ic.energy(flame(cx, by, 6.0 * s, 15 * s, 0, seed, 2), rmp, falloff=3.0 * s)
    for d in (-1, 1):
        ic.solid(path([(cx + d * 3.2 * s, by - 9 * s), (cx + d * 6.8 * s, by - 12.5 * s), (cx + d * 6.6 * s, by - 17 * s)], 1.2 * s, 0.25 * s),
                 DEMON, seed=seed + 2, base=3.0)
    for d in (-1, 1):
        ic.paint(ellipse(cx + d * 1.8 * s, by - 6.2 * s, 0.9 * s, 0.6 * s, d * 20), lambda x, y, dd: (40, 6, 4))


def lantern(ic, cx, cy, s=1.0, seed=0, light=ELEC):
    ic.solid(ring(cx, cy - 9.2 * s, 1.6 * s, 0.9 * s), GUN, seed=seed, base=2.8)
    ic.solid(box(cx, cy - 6.8 * s, 4.2 * s, 1.1 * s, 0, 0.4), GUN, seed=seed + 1, base=3.0)
    ic.solid(box(cx, cy + 7.0 * s, 4.6 * s, 1.2 * s, 0, 0.4), GUN, seed=seed + 2, base=2.4)
    ic.solid(box(cx, cy, 3.8 * s, 5.6 * s, 0, 0.6), R("04081e", "0a1848", "15338a", "2a4a90"), seed=seed + 3, base=1.6, spread=0.6)
    ic.glow(cx, cy, 7 * s, "60a0ff", 0.7)
    ic.energy(path(zig(cx - 0.6 * s, cy - 4.4 * s, cx + 0.4 * s, cy + 4.6 * s, 4, 1.4 * s, seed + 5), 0.7 * s, 0.4 * s), light, falloff=0.6)
    for d in (-1, 1):
        ic.solid(box(cx + d * 4.0 * s, cy, 0.6 * s, 5.6 * s, 0, 0.2), GUN, seed=seed + 4, base=3.0)


def candle(ic, cx, by, s=1.0, wax=PAPER, fire=ELEC, seed=0):
    ic.solid(box(cx, by - 5 * s, 2.8 * s, 6 * s, 0, 0.5), wax, seed=seed, base=3.0)
    ic.solid(ellipse(cx + 1.6 * s, by - 9.8 * s, 0.8 * s, 2.0 * s), wax, seed=seed + 1, base=3.6)   # a drip
    ic.solid(seg(cx, by - 11 * s, cx, by - 12.6 * s, 0.3 * s), GUN, base=2)
    ic.glow(cx, by - 15 * s, 7 * s, fire[4], 0.6)
    ic.energy(flame(cx, by - 11.6 * s, 2.4 * s, 7.4 * s, 0, seed, 1), fire, falloff=1.6 * s)


def laurel(ic, cx, cy, r, rmp=GOLD, seed=0):
    """A wreath open at the top: leaves along two arcs meeting at the bottom."""
    for d in (-1, 1):
        for k in range(6):
            a = math.radians(90 + d * (18 + k * 26))
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            ic.solid(ellipse(x, y, 2.4, 1.1, math.degrees(a) + 90 + d * 35), rmp, seed=seed + k, base=3.0 - k * 0.15)
    ic.solid(ellipse(cx, cy + r + 0.4, 1.6, 1.2), CLOTH, seed=seed + 9, base=3)


def scroll(ic, cx, cy, s=1.0, seed=0):
    ic.solid(box(cx, cy, 7.4 * s, 6.0 * s, 0, 0.4), PAPER, seed=seed, base=3.4, spread=0.9)
    for d in (-1, 1):
        ic.solid(box(cx, cy + d * 6.6 * s, 8.4 * s, 1.4 * s, 0, 1.2 * s), R("2a2620", "5a5444", "8e8670", "c0b89e", "e8e0c8"), seed=seed + 1, base=2.8)
    for k in range(3):
        ic.paint(box(cx - 1 * s, cy - 3 * s + k * 2.2 * s, 5.0 * s - k * s, 0.35 * s, 0, 0.1), lambda x, y, d: (120, 108, 86))
    ic.solid(circle(cx + 4.4 * s, cy + 3.4 * s, 2.0 * s), CRIMSON, seed=seed + 2, base=2.8)
    ic.solid(seg(cx + 4.0 * s, cy + 5 * s, cx + 3.0 * s, cy + 8.8 * s, 0.6 * s), CRIMSON, seed=seed + 3, base=2.4)


def brazier(ic, cx, by, s=1.0, fire=HOLY, seed=0):
    ic.solid(poly([(cx - 6.4 * s, by - 7 * s), (cx + 6.4 * s, by - 7 * s), (cx + 4.4 * s, by - 3.2 * s), (cx - 4.4 * s, by - 3.2 * s)]), BRASS, seed=seed, base=2.8)
    for d in (-1, 1):
        ic.solid(seg(cx + d * 3.6 * s, by - 3.5 * s, cx + d * 5.2 * s, by, 0.6 * s), BRASS, seed=seed + 1, base=2.4)
    ic.glow(cx, by - 11 * s, 9 * s, "fff0a0", 0.6)
    ic.energy(flame(cx, by - 6.6 * s, 5.4 * s, 13 * s, 0, seed, 3), fire, falloff=2.5 * s)


def lion(ic, cx, cy, s=1.0, mane=GOLD, eyes=CRIMSON, seed=0):
    """A heraldic lion's face: a spiked mane round a broad muzzle, fangs bared."""
    def m(x, y):
        a = math.atan2(y - cy, x - cx)
        return math.hypot(x - cx, y - cy) - (9.4 + 1.6 * math.sin(a * 9 + seed)) * s
    ic.solid(m, mane, seed=seed, base=2.2)
    ic.solid(union(ellipse(cx, cy - 0.6 * s, 5.4 * s, 5.8 * s), ellipse(cx, cy + 3.6 * s, 3.8 * s, 3.2 * s)), mane, seed=seed + 1, base=3.4)
    for d in (-1, 1):
        ic.energy(poly([(cx + d * 0.8 * s, cy - 1.6 * s), (cx + d * 4.2 * s, cy - 3.0 * s), (cx + d * 3.6 * s, cy - 0.6 * s)]), eyes, falloff=0.5)
    ic.solid(ellipse(cx, cy + 2.0 * s, 1.6 * s, 1.0 * s), R("1a0806", "3a1408", "5a2410"), base=1.2)
    ic.paint(ellipse(cx, cy + 5.0 * s, 2.8 * s, 1.4 * s), lambda x, y, d: (40, 8, 8))
    for d in (-1, 1):
        ic.solid(poly([(cx + d * 1.8 * s, cy + 4.0 * s), (cx + d * 1.0 * s, cy + 4.0 * s), (cx + d * 1.4 * s, cy + 6.0 * s)]), BONE, base=4)


def breastplate(ic, cx, cy, s=1.0, rmp=STEEL, seed=0):
    f = union(poly([(cx - 7 * s, cy - 6 * s), (cx - 2.6 * s, cy - 7.6 * s), (cx, cy - 5.6 * s), (cx + 2.6 * s, cy - 7.6 * s), (cx + 7 * s, cy - 6 * s),
                    (cx + 6.2 * s, cy + 4 * s), (cx, cy + 8.4 * s), (cx - 6.2 * s, cy + 4 * s)]))
    ic.solid(f, rmp, seed=seed, base=2.6)
    ic.solid(box(cx, cy + 0.6 * s, 0.7 * s, 6.8 * s, 0, 0.2), rmp, seed=seed + 1, base=4.0, spread=0.4)
    return f


def crown(ic, cx, cy, s=1.0, rmp=GOLD, gem=PINK_GEM, seed=0):
    f = union(box(cx, cy + 2.4 * s, 6.6 * s, 2.2 * s, 0, 0.4),
              *[poly([(cx + x * s - 1.8 * s, cy + 0.6 * s), (cx + x * s, cy - 4.6 * s - abs(x) * -0.1 * s), (cx + x * s + 1.8 * s, cy + 0.6 * s)]) for x in (-5, 0, 5)])
    ic.solid(f, rmp, seed=seed, base=2.8)
    for x in (-3.4, 0, 3.4):
        ic.energy(circle(cx + x * s, cy + 2.4 * s, 0.9 * s), gem, falloff=0.8)


def chevrons(ic, x, y, n, rmp, w=0.6, gap=3.0, size=2.6, up=True):
    """n stacked chevrons, pointing up (or right)."""
    for k in range(n):
        if up:
            yy = y - k * gap
            ic.energy(path([(x - size, yy + size * 0.8), (x, yy), (x + size, yy + size * 0.8)], w), rmp, falloff=w)
        else:
            xx = x + k * gap
            ic.energy(path([(xx, y - size), (xx + size * 0.8, y), (xx, y + size)], w), rmp, falloff=w)


def clock(ic, cx, cy, r, face=PAPER, rim=GOLD, hands=(-90, 30), seed=0):
    ic.solid(circle(cx, cy, r), rim, seed=seed, base=2.8)
    ic.solid(circle(cx, cy, r * 0.76), face, seed=seed + 1, base=3.4, spread=0.6)
    for k, a in enumerate(hands):
        r_ = math.radians(a)
        ic.paint(seg(cx, cy, cx + math.cos(r_) * r * (0.62 - k * 0.18), cy + math.sin(r_) * r * (0.62 - k * 0.18), 0.45), lambda x, y, d: (30, 24, 20))


def spire(ic, cx, top, bottom, s=1.0, rmp=COPPER, seed=0):
    """A lightning rod: a tapering copper spike, two collars, an orb at the tip."""
    ic.solid(seg(cx, bottom, cx, top + 2.2 * s, 1.5 * s, 0.5 * s), rmp, seed=seed, base=2.8)
    for k, t in enumerate((0.45, 0.72)):
        y = top + (bottom - top) * t
        ic.solid(box(cx, y, 2.4 * s, 0.6 * s, 0, 0.2), rmp, seed=seed + k + 1, base=3.4)
    ic.solid(circle(cx, top + 1.4 * s, 1.4 * s), rmp, seed=seed + 4, base=3.8)


def coil(ic, cx, top, bottom, w, rmp=COPPER, seed=0):
    """A coil of wire wound round a post, a ball on top."""
    ic.solid(box(cx, (top + bottom) / 2 + 1, 1.2, (bottom - top) / 2, 0, 0.3), GUN, seed=seed, base=2.2)
    y = bottom - 1.5
    while y > top + 3:
        ic.solid(ellipse(cx, y, w, 0.9), rmp, seed=seed + int(y), base=3.0)
        y -= 2.2
    ic.solid(box(cx, bottom, w + 1.4, 1.0, 0, 0.3), GUN, seed=seed + 1, base=2.6)


def leaf(ic, cx, cy, ang, s=1.0, rmp=LEAF, seed=0):
    items = [(ellipse(0, 0, 6, 3.0), rmp, {"base": 3.0}), (lseg(-7.5, 0, 4.6, 0, 0.35, 0.15), rmp, {"base": 4.4, "spread": 0.3})]
    parts(ic, cx, cy, ang, s, items, seed)


def bread(ic, cx, cy, s=1.0, seed=0):
    ic.solid(union(ellipse(cx, cy, 6.0 * s, 3.4 * s), box(cx, cy + 1.6 * s, 5.8 * s, 1.8 * s, 0, 0.8 * s)), CRUST, seed=seed, base=3.0)
    for k in (-1, 1):
        ic.solid(seg(cx + k * 2.4 * s - 1.0 * s, cy - 1.4 * s, cx + k * 2.4 * s + 1.0 * s, cy - 2.6 * s, 0.4 * s), PAPER, base=3.6, noise=0.2)
    ic.solid(seg(cx - 1.0 * s, cy - 1.0 * s, cx + 1.0 * s, cy - 2.2 * s, 0.4 * s), PAPER, base=3.6, noise=0.2)


def drumstick(ic, cx, cy, ang, s=1.0, seed=0):
    items = [(lambda u, v: ellipse(2.0, 0, 4.8, 3.6)(u, v), MEAT, {"base": 3.0}), (lseg(-5.4, 0, -1.0, 0, 0.9, 1.4), BONE, {"base": 3.6}),
             (lambda u, v: union(circle(-6.0, -1.0, 1.1), circle(-6.0, 1.0, 1.1))(u, v), BONE, {"base": 4.0})]
    parts(ic, cx, cy, ang, s, items, seed)


def portal(ic, cx, cy, rx, ry, rmp=ARCANE, seed=0):
    ic.solid(ellipse(cx, cy, rx, ry), R("04020a", "0e0620", "1a0c34"), base=1.0, spread=0.6, seed=seed)
    ic.energy(cut(ellipse(cx, cy, rx + 0.8, ry + 0.8), ellipse(cx, cy, rx - 0.6, ry - 0.6)), rmp, falloff=0.7)


def flame_mark(ic, cx, cy, s=1.0, rmp=HELL):
    """A brand glyph: a downward trident burnt in."""
    ic.energy(union(seg(cx, cy - 5 * s, cx, cy + 5 * s, 0.75 * s), path([(cx - 3.8 * s, cy - 5 * s), (cx - 3.4 * s, cy - 0.6 * s), (cx, cy + 1.6 * s),
                                                                         (cx + 3.4 * s, cy - 0.6 * s), (cx + 3.8 * s, cy - 5 * s)], 0.7 * s)),
              rmp, falloff=0.6 * s)


def ekg(ic, x0, x1, y, rmp, w=0.5, amp=4.0):
    xs = [x0, x0 + (x1 - x0) * 0.32, x0 + (x1 - x0) * 0.42, x0 + (x1 - x0) * 0.52, x0 + (x1 - x0) * 0.62, x1]
    ys = [y, y, y - amp, y + amp * 0.7, y, y]
    ic.energy(path(list(zip(xs, ys)), w), rmp, falloff=w)


def tabard(ic, cx, cy, s=1.0, rmp=PAPER, seed=0):
    """An empty surcoat: shoulders, a neck opening, hanging to a hem."""
    f = cut(poly([(cx - 6.4 * s, cy - 6 * s), (cx - 2.6 * s, cy - 7.4 * s), (cx + 2.6 * s, cy - 7.4 * s), (cx + 6.4 * s, cy - 6 * s),
                   (cx + 5.0 * s, cy + 8.6 * s), (cx - 5.0 * s, cy + 8.6 * s)]), circle(cx, cy - 7.6 * s, 2.4 * s))
    ic.solid(f, rmp, seed=seed, base=3.0)
    ic.solid(inter(f, holy_cross(cx, cy + 0.6 * s, 0.75 * s)), CLOTH, seed=seed + 1, base=2.8)
    return f


# ================================================================ the six spec emblems
def ran_class():
    # Deadeye: the archer's eye, lightning in it; a quiver of charged arrows; an arrowhead crest
    A = G("ranger", (10, 8))
    A.energy(path(arc_pts(12, 13, 10.5, 200, 340), 0.3, 1.0), GUST, falloff=0.5)
    eye(A, 12, 12, 1.15, R("0a1848", "15338a", "2a62d0", "60a0ff", "bfe0ff"), seed=1)
    zap(A, 12.5, 6, 11.5, 18, VOLT, 0.45, 3, 1.0, 2)
    B = G("ranger", (10, 8))
    for k, y in enumerate((16, 20)):
        line(B, 1, y, 6, y, 0.5, GUST, seed=k)
    quiver(B, 12, 15, 0.82)
    C = G("ranger", (12, 8))
    C.energy(path(arc_pts(12, 13, 9.5, 120, 420), 0.25, 0.9), GUST, falloff=0.5)
    C.solid(poly([(12, 1.5), (19, 14), (15, 12.6), (12, 22), (9, 12.6), (5, 14)]), BLUE_STEEL, base=3.0)
    C.energy(poly([(13, 6), (10.6, 12.6), (12.6, 12.6), (11, 18.4), (14.4, 10.8), (12.4, 10.8), (13.8, 6)]), VOLT, falloff=0.8)
    return A, B, C


def wiz_class():
    # Aerotheurge: a staff with a vortex at its head; a tornado full of lightning; the pointed hat
    A = G("wizard", (14, 6))
    staff(A, 9, 16, -70, 1.0, WOOD, ELEC)
    swirl(A, 13.4, 5.6, 7.5, 1.0, 0, -1.2, 0.3, 1.0, R("06101e", "102a44", "2a5a88", "5a90c0", "a8d8f4", "f4ffff"))
    B = G("wizard", (12, 6))
    tornado(B, 12, 4, 21, 9, R("06101e", "102a44", "2a5a88", "5a90c0", "a8d8f4", "f4ffff"))
    zap(B, 10, 6, 13, 16, ELEC, 0.6, 4, 1.6, 2)
    C = G("wizard", (10, 8))
    hat(C, 11, 20, 1.0)
    zap(C, 19, 2, 22, 9, ELEC, 0.45, 3, 1.0, 5)
    swirl(C, 5, 6, 3.6, 0.6, 0, -1.0, 0.25, 0.7, R("06101e", "102a44", "2a5a88", "5a90c0", "a8d8f4", "f4ffff"))
    return A, B, C


def sor_class():
    # Arcane: a mana crystal; a mage scattering into a blink; a square rune of the blink
    A = G("sorcerer", (10, 8))
    A.glow(12, 12, 11, "9a6ae0", 0.6)
    crystal(A, 12, 12, 1.0)
    A.glint(9, 6)
    B = G("sorcerer", (12, 10))
    body = union(circle(9, 8, 3.4), poly([(3, 23), (5, 13), (9, 11.4), (13, 13), (15, 23)]))
    hood = cut(union(circle(9, 7.4, 4.4), poly([(4.6, 8), (13.4, 8), (14, 13), (4, 13)])), circle(9.6, 8.6, 2.6))
    B.solid(inter(body, lambda x, y: x - 13.5), R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc", "d0bcf0"), base=2.4)
    B.solid(inter(hood, lambda x, y: x - 13.5), R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc"), base=2.8)
    B.energy(inter(circle(9.6, 8.6, 2.0), lambda x, y: x - 13.5), ARCANE, falloff=0.8)
    for k in range(9):
        x = 14 + (k % 3) * 3 + h2(k, 3) * 2
        y = 8 + (k // 3) * 5 + h2(k, 4) * 3
        B.energy(box(x, y, 0.7 + 0.2 * (k % 2), 0.7, 45), ARCANE, falloff=0.5)
    C = G("sorcerer", (12, 12))
    C.energy(cut(box(12, 12, 7.4, 7.4, 45, 0.3), box(12, 12, 6.0, 6.0, 45, 0.3)), ARCANE, falloff=0.6)
    C.energy(cut(circle(12, 12, 5.2), circle(12, 12, 4.2)), ARCANE, falloff=0.5)
    for k in range(4):
        a = math.radians(k * 90)
        C.energy(circle(12 + math.cos(a) * 10.4, 12 + math.sin(a) * 10.4, 0.9), ARCANE, falloff=0.8)
    C.energy(star(12, 12, 3.4, 1.0, 4, -90), R("6a3ab0", "9a6ae0", "d0b0ff", "ffffff"), falloff=1.0)
    return A, B, C


def rog_class():
    # Winddancer: crossed daggers in a whirl of wind; a feather on the breeze; a shuriken riding the wind
    A = G("rogue", (12, 10))
    swirl(A, 12, 12, 10.5, 9.4, 200, 0.85, 0.3, 1.0, BREEZE)
    dagger(A, 12, 12, -45, 1.05, STEEL, LEATHER, BRASS, 1)
    dagger(A, 12, 12, -135, 1.05, STEEL, LEATHER, BRASS, 2)
    B = G("rogue", (12, 10))
    for k, (y, x0, x1) in enumerate(((6, 1, 8), (17, 13, 22))):
        gust(B, x0, y, x1, y, 0.7, 0.8, BREEZE)
    feather(B, 12, 12, -50, 1.0, R("0a1410", "1e3a30", "3a6a58", "6aa088", "b0e0c8", "f4fff8"))
    C = G("rogue", (14, 8))
    for k, (x0, y0, x1, y1) in enumerate(((1, 21, 9, 16), (2, 14, 8, 11.5), (8, 23, 14, 19))):
        C.energy(path([(x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2 + 1.2), (x1, y1)], 0.25, 0.8), BREEZE, falloff=0.5)
    C.solid(cut(star(14, 10, 8.6, 2.4, 4, -70), circle(14, 10, 1.3)), STEEL, base=3.0, light=(-0.6, -0.8))
    C.solid(cut(circle(14, 10, 2.6), circle(14, 10, 1.3)), GUN, base=2.6)
    return A, B, C


def war_class():
    # Bannerlord: a helm before two crossed pennants; the gilded finial of a standard; a war horn
    A = G("warrior", (12, 8))
    for d in (-1, 1):
        A.solid(seg(12 - d * 9, 23, 12 + d * 8, 2, 0.6), WOOD, base=2.6)
        x, y = 12 + d * 8, 2
        A.solid(poly([(x, y + 0.8), (x - d * 8.5, y + 3.6), (x - d * 1.4, y + 6.2)]), CLOTH, base=3.0, seed=4 + d)
    helm(A, 12, 14, 1.15, STEEL)
    B = G("warrior", (12, 8))
    B.solid(box(12, 19, 1.4, 6, 0, 0.3), WOOD, base=2.4)
    B.solid(box(12, 13.6, 3.0, 1.2, 0, 0.4), GOLD, base=3.0)
    B.solid(poly([(12, 1), (16, 8), (13.4, 12.4), (10.6, 12.4), (8, 8)]), GOLD, base=3.2)
    B.solid(poly([(12, 4), (13.6, 8), (12, 10.6), (10.4, 8)]), CLOTH, base=3.0)
    for d in (-1, 1):
        B.solid(path([(12 + d * 2.8, 14), (12 + d * 6, 16), (12 + d * 6.8, 20.5), (12 + d * 9.5, 23)], 1.2, 0.6), CLOTH, base=2.8, seed=d + 3)
    C = G("warrior", (10, 8))
    C.solid(poly([(11.4, 15.6), (13.6, 17.4), (12.6, 21.6), (11.4, 19.6), (10.2, 21.8)]), CLOTH, base=3.0)
    C.solid(path(arc_pts(5, 3, 14, 100, 18, 12), 0.8, 3.6), BONE, base=2.8)
    bx, by = 5 + math.cos(math.radians(18)) * 14, 3 + math.sin(math.radians(18)) * 14
    C.solid(ellipse(bx, by, 4.0, 1.4, 18), BRASS, base=3.0)
    C.solid(ellipse(bx + 0.4, by - 1.0, 2.6, 0.8, 18), R("1a1006", "3a2810", "5a4018"), base=1.4, spread=0.3)
    for a in (75, 45):
        r = math.radians(a)
        C.solid(ellipse(5 + math.cos(r) * 14, 3 + math.sin(r) * 14, 0.9, 2.2 + (a - 45) / 40, a), BRASS, base=2.8)
    C.solid(circle(2.6, 16.8, 1.1), BRASS, base=3.0)
    for k, r in enumerate((3.4, 5.6)):
        C.energy(path(arc_pts(bx, by, r, -110, -40, 8), 0.4 - k * 0.1), GOLD, falloff=0.3)
    return A, B, C


def wlk_class():
    # Branding: the iron, red hot; a horned demon mask; a horned flame
    A = G("warlock", (12, 8))
    brand_iron(A, 21, 2, 9, 15, 1.1)
    A.glow(8, 16, 7, "ff8a2a", 0.8)
    A.energy(circle(8, 16.5, 4.0), HELL, falloff=2.5)
    flame_mark(A, 8, 16.5, 0.65, R("3a0804", "6a1406", "2a0604", "140404"))
    B = G("warlock", (12, 10))
    mask(B, 12, 14, 0.95)
    C = G("warlock", (12, 14))
    horned_flame(C, 12, 23, 1.2)
    for k, (x, y) in enumerate(((4, 9), (20, 11))):
        C.energy(circle(x, y, 1.0), ESS, falloff=1)
    return A, B, C


# ================================================================ recolours and copies
def wlk_ee_essence_empowerment():
    # essence stacks feeding fire damage: a fireball fed four streams; essence wisps fed to a bonfire; stacked orbs over a flame
    A = G("warlock", (12, 10))
    for k, (x, y) in enumerate(((3, 4), (21, 4), (3, 20), (21, 20))):
        A.energy(path([(x, y), (12, 12)], 0.6, 0.3), ESS, falloff=0.5)
        A.energy(circle(x, y, 1.6), ESS, falloff=1.4)
    fireball(A, 12, 12, 4.4, -90, HELL, 0.5)
    B = G("warlock", (12, 12))
    for d in (-1, 1):
        B.solid(seg(12 - d * 8, 22.5, 12 + d * 7, 18.5, 1.3), WOOD, seed=d + 2, base=2.6)
    B.energy(flame(12, 20, 7.5, 15, 0, 3, 3), HELL, falloff=2.4)
    for k, (x, y) in enumerate(((4, 3), (20, 2), (13, 1.5))):
        B.energy(path([(x, y), ((x + 12) / 2 + 2 * (1 if x < 12 else -1), (y + 10) / 2), (12 + (x - 12) * 0.2, 10)], 0.9, 0.3), ESS, falloff=0.7)
    C = G("warlock", (12, 14))
    C.energy(flame(14, 22, 6.5, 15, 0, 5, 2), HELL, falloff=2.2)
    for k in range(3):
        C.energy(circle(4.5, 19 - k * 5, 1.9), ESS, falloff=1.6)
        C.energy(path([(6.6, 19 - k * 5), (10.5, 17 - k * 2.5)], 0.4, 0.2), ESS, falloff=0.3)
    return A, B, C


def wiz_sc_conduit():
    # Static Charge stacks: casting faster: a spellbook's pages riffling with lightning; a spinning cog; a wand flicked fast
    A = G("wizard", (12, 8))
    book(A, 12, 17, 0.95, R("04081e", "0a1848", "15338a", "2a4a90", "3e6ab8"), PAPER, open_=True)
    for k, r in enumerate((5.5, 7.5, 9.5)):
        A.solid(path(arc_pts(12, 14, r, -170 + k * 18, -100 + k * 10, 8), 0.5, 0.35), PAPER, seed=k, base=3.6 - k * 0.5)
    for k, (x0, y0, x1, y1) in enumerate(((13, 11, 17, 2), (15, 13, 22, 7))):
        zap(A, x0, y0, x1, y1, ELEC, 0.5, 3, 1.1, k)
    B = G("wizard", (12, 12))
    cog(B, 12, 12, 7.0, STEEL, 9)
    B.energy(circle(12, 12, 2.4), ELEC, falloff=2)
    for k in range(3):
        a0 = k * 120 + 20
        B.energy(path(arc_pts(12, 12, 10.8, a0, a0 + 60), 0.25, 0.8), ELEC, falloff=0.4)
    C = G("wizard", (12, 10))
    WAND = R("0a0a10", "1a1a24", "2e2e40", "4a4a64", "6e6e90", "a0a0c0")
    for k, a in enumerate((-15, -30)):
        r = math.radians(a)
        C.energy(seg(5, 20, 5 + math.cos(r) * 13, 20 + math.sin(r) * 13, 0.4, 0.25), R("04081e", "0a1848", "15338a", "2a62d0")[:4 - k], falloff=0.4)
    C.solid(seg(5, 20, 14.5, 7.5, 1.0, 0.7), WAND, base=3.0)
    C.solid(seg(5, 20, 7, 17.4, 1.1), BRASS, base=3.0)
    spark(C, 15.5, 6.5, 3.6)
    return A, B, C


def wiz_tt_lightning_rod():
    # more zaps per tick, farther: a lightning rod drawing the storm; a chain across many; a tesla coil
    A = G("wizard", (12, 6))
    A.solid(poly([(0, 24), (0, 20), (12, 15), (24, 20), (24, 24)]), R("0a0c18", "16182c", "242844", "34385c"), base=2.0)
    spire(A, 12, 2, 18, 1.0)
    for k, (x, y) in enumerate(((1, 0), (23, 0), (2, 11), (22, 10))):
        zap(A, x, y, 12, 3, ELEC, 0.6, 4, 1.4, k)
    B = G("wizard", (12, 12))
    pts = [(2, 15), (6, 6), (12, 3), (18, 6), (22, 15)]
    for k in range(len(pts) - 1):
        zap(B, *pts[k], *pts[k + 1], ELEC, 0.45, 3, 1.2, k)
    for k, (x, y) in enumerate(pts):
        B.energy(circle(x, y, 1.6), ELEC, falloff=1.4)
    B.energy(circle(12, 18, 2.6), ELEC, falloff=2.2)
    for k, (x, y) in enumerate(pts[1:4]):
        zap(B, 12, 18, x, y + 1.5, ELEC, 0.35, 3, 0.8, k + 5)
    C = G("wizard", (12, 8))
    coil(C, 12, 6, 22, 4.0)
    C.energy(circle(12, 5, 2.8), ELEC, falloff=2.2)
    for k, (x, y) in enumerate(((1, 2), (23, 3), (2, 14), (22, 13))):
        zap(C, 12, 5, x, y, ELEC, 0.4, 4, 1.4, k + 2)
    return A, B, C


def hud_void_barrier():
    # can't die for 1 s after a Blink: time held; death barred; a heartbeat that won't flatline
    A = S("sorcerer")
    hourglass(A, 7, 7, 0.78, frame=R("1a0e30", "2c1850", "44306a", "6a4e9a", "9a7ccc"), sand=ARCANE, t=0.15)
    B = S("sorcerer")
    skull(B, 7, 7.4, 0.68, BONE)
    B.energy(union(ring(7, 7, 6.0, 0.9), seg(2.8, 2.8, 11.2, 11.2, 0.65)), ARCANE, falloff=0.5)
    C = S("sorcerer")
    C.energy(path([(0.5, 8.5), (3.5, 8.5), (5.0, 2.5), (7.4, 12.5), (9.0, 6.5), (10.0, 8.5), (13.5, 8.5)], 0.75), ARCANE, falloff=0.6)
    return A, B, C


def hud_protective_gale():
    # Evasion from the gale: a wing; an arrow turned aside; the gale's offset arcs
    A = S("rogue")
    WING = R("0a1410", "1e3a30", "3a6a58", "6aa088", "b0e0c8", "f4fff8")
    for k, (a, L_) in enumerate(((-150, 11.0), (-128, 9.6), (-106, 8.0))):
        r = math.radians(a)
        A.solid(ellipse(11 + math.cos(r) * L_ * 0.5, 11.5 + math.sin(r) * L_ * 0.5, L_ * 0.5, 1.5, a), WING, seed=k, base=3.6 - k * 0.5)
    A.solid(ellipse(9.4, 8.6, 3.6, 2.4, -40), WING, seed=5, base=3.0)
    B = S("rogue")
    B.energy(path(arc_pts(7, 7, 4.2, 100, 260), 0.6), BREEZE, falloff=0.5)
    B.solid(L(union(lbox(-2, 0, 3.6, 0.45), poly([(1.2, -1.6), (3.8, 0), (1.2, 1.6)])), 10, 4, -45, 1.0), STEEL, base=3.2)
    B.solid(L(lbox(0, 0, 1.0, 0.5), 4.6, 10.4, -45, 1.0), STEEL, base=2.6)
    C = S("rogue")
    for k, x in enumerate((3.5, 7, 10.5)):
        C.energy(path(arc_pts(x - 3, 7, 4.8, -45, 45), 0.4 + k * 0.15), BREEZE, falloff=0.4)
    return A, B, C


def hud_pyrebrand():
    # this enemy is branded: the brand's trident glyph; a coal, cracked and burning; a flame in the sights
    A = S("warlock")
    flame_mark(A, 7, 7, 1.05)
    B = S("warlock")
    B.glow(7, 8, 6, "ff8a2a", 0.5)
    coal = union(ellipse(7, 8, 5.6, 4.2, -10), ellipse(5.2, 6.4, 3.0, 2.4))
    B.solid(coal, R("0e0604", "1e0a06", "2e100a", "40180c"), base=1.6, spread=0.8)
    B.energy(inter(coal, union(path([(2.4, 7), (5, 8.4), (7.2, 6.4), (9.6, 8.2), (11.6, 7.4)], 0.5), path([(5, 8.4), (6, 11.4)], 0.45),
                               path([(7.2, 6.4), (7.6, 3.8)], 0.4), path([(9.6, 8.2), (9.2, 10.8)], 0.4))), HELL, falloff=0.4)
    C = S("warlock")
    crosshair(C, 7, 7, 5.0, HELL, 0.5)
    C.energy(flame(7, 9.5, 2.2, 6, 0, 1, 1), HELL, falloff=1.2)
    return A, B, C


def hud_shared_provisions():
    # cooldown reduction stacks: a loaf; a drumstick; a clock turned back
    A = S("warrior")
    bread(A, 7, 7.5, 0.95)
    B = S("warrior")
    drumstick(B, 7, 7, -45, 0.95)
    C = S("warrior")
    clock(C, 7, 7, 5.6, hands=(-90, 120))
    C.energy(path(arc_pts(7, 7, 6.4, -60, -170), 0.4), GOLD, falloff=0.3)
    C.energy(poly([(1.0, 4.4), (3.2, 3.8), (1.8, 6.6)]), GOLD, falloff=0.4)
    return A, B, C


def hud_standard_raised():
    # damage reduction while the standard is carried: a pennant on the move; one chevron on a shield; a spear held high
    A = S("warrior")
    A.solid(seg(4, 13.5, 8, 1, 0.55), WOOD, base=2.6)
    A.solid(poly([(8, 1.2), (13.5, 3.6), (7, 6.2)]), CLOTH, base=3.0)
    A.solid(circle(8, 1, 0.9), GOLD, base=3.4)
    for k, y in enumerate((8, 11)):
        line(A, 9, y, 13, y, 0.35, R("2a1a04", "6a4a10", "b08a20"), seed=k)
    B = S("warrior")
    heater = poly([(1.6, 1.2), (12.4, 1.2), (12.4, 6.2), (7, 13), (1.6, 6.2)])
    B.solid(heater, STEEL, base=2.6)
    B.solid(poly([(2.8, 2.4), (11.2, 2.4), (11.2, 6.0), (7, 11.4), (2.8, 6.0)]), CLOTH, base=2.6)
    B.solid(path([(3.4, 8.0), (7, 4.4), (10.6, 8.0)], 0.95), GOLD, base=3.4)
    C = S("warrior")
    C.solid(seg(7, 13.5, 7, 4, 0.5), WOOD, base=2.6)
    C.solid(poly([(7, 0.4), (9.4, 4.4), (7, 5.6), (4.6, 4.4)]), STEEL, base=3.2)
    for d in (-1, 1):
        C.solid(path([(7, 5.6), (7 + d * 3.6, 7.6), (7 + d * 4.4, 10.6)], 0.8, 0.4), CLOTH, base=2.8, seed=d)
    return A, B, C


def hud_standard_planted():
    # double reduction once planted: driven into the ground; two chevrons on the shield; a wall held
    A = S("warrior")
    A.solid(poly([(5.6, 9), (8.4, 9), (7, 12.5)]), STEEL, base=3.0)
    A.solid(seg(7, 9, 7, 0.5, 0.55), WOOD, base=2.6)
    A.solid(ellipse(7, 12.4, 6.4, 1.4), EARTH, base=2.0)
    for d in (-1, 1):
        A.energy(path([(7 + d * 1.6, 12.2), (7 + d * 3.6, 11.4), (7 + d * 5.6, 12.6)], 0.35), GOLD, falloff=0.3)
    B = S("warrior")
    heater = poly([(1.6, 1.2), (12.4, 1.2), (12.4, 6.2), (7, 13), (1.6, 6.2)])
    B.solid(heater, STEEL, base=2.6)
    B.solid(poly([(2.8, 2.4), (11.2, 2.4), (11.2, 6.0), (7, 11.4), (2.8, 6.0)]), CLOTH, base=2.6)
    for k in range(2):
        B.solid(path([(3.6, 6.0 + k * 3.6), (7, 3.0 + k * 3.6), (10.4, 6.0 + k * 3.6)], 0.7), GOLD, base=3.4, seed=k)
    C = S("warrior")
    C.solid(union(box(7, 9.5, 6.4, 3.6, 0, 0.3), box(2.4, 5.2, 1.6, 1.2), box(7, 5.2, 1.6, 1.2), box(11.6, 5.2, 1.6, 1.2)), SMOKE, base=3.0)
    for k, (x, y) in enumerate(((4, 9), (9, 9), (6.5, 11.6), (11.5, 11.6))):
        C.paint(box(x, y, 1.8, 0.25), lambda xx, yy, d: (40, 40, 48))
    C.solid(seg(7, 4, 7, 0.4, 0.4), WOOD, base=2.6)
    C.solid(poly([(7.3, 0.4), (11, 1.6), (7.3, 2.8)]), CLOTH, base=3.0)
    return A, B, C


def hud_lingering_breeze():
    # health regeneration over time
    A = S("rogue")
    leaf(A, 7, 7, -45, 0.95)
    B = S("rogue")
    for k, (x, y, r) in enumerate(((4, 10.5, 1.5), (8.5, 7, 1.3), (5.5, 3.5, 1.0), (10.5, 2.4, 0.8))):
        B.energy(circle(x, y, r), LIFE, falloff=r)
    B.energy(path([(10, 12.5), (12, 10.5), (12.6, 8)], 0.35), BREEZE, falloff=0.3)
    C = S("rogue")
    C.energy(path(arc_pts(7, 7, 5.6, -90, 200), 0.5), BREEZE, falloff=0.4)
    C.energy(drop(7, 7.4, 2.6), LIFE, falloff=2.0)
    return A, B, C


# ================================================================ reused motifs
def wiz_tt_lingering_storm():
    # the orb lasts longer: a storm cloud that hangs on; a storm kept in a lantern; a slow candle
    A = G("wizard", (10, 6))
    cloud(A, [(7, 8, 4.4), (13, 6, 5.2), (18, 9, 4.0), (11, 10, 4.2)], R("06081a", "10163a", "1e2a60", "34448a", "5266b0", "8098d8"), base=2.4)
    for k, x in enumerate((6, 11.5, 17)):
        zap(A, x, 12, x - 1.5, 23, ELEC, 0.5, 4, 1.2, k)
    B = G("wizard", (12, 8))
    lantern(B, 12, 12, 1.15)
    C = G("wizard", (12, 8))
    candle(C, 12, 23, 1.15)
    for k, (x, y) in enumerate(((5, 6), (19, 8))):
        spark(C, x, y, 1.4)
    return A, B, C


def war_righteous_crusade():
    # buffs last longer: a gold laurel; a sealed proclamation; a brazier that never goes out
    A = G("warrior", (12, 8))
    laurel(A, 12, 11.5, 8.0)
    A.energy(star(12, 11, 3.6, 1.4, 5, -90), HOLY, falloff=1.2)
    B = G("warrior", (12, 8))
    scroll(B, 12, 12, 1.15)
    C = G("warrior", (12, 8))
    brazier(C, 12, 22, 1.15)
    return A, B, C


def war_bs_feared_crest():
    # enemies near the standard are vulnerable: the crest's lion roaring; armour cracking; a sword snapped
    A = G("warrior", (12, 8))
    lion(A, 12, 12, 1.0)
    B = G("warrior", (12, 8))
    f = breastplate(B, 12, 12, 1.15)
    B.energy(inter(f, path(zig(8, 4, 15, 20, 5, 2.2, 3), 0.7, 0.4)), CRIMSON, falloff=0.6)
    for k, (x, y) in enumerate(((19, 18), (21, 21))):
        B.solid(poly([(x, y), (x + 2.0, y + 0.6), (x + 0.6, y + 2.0)]), STEEL, base=2.6)
    C = G("warrior", (12, 8))
    C.solid(seg(5, 19.6, 11.4, 12.8, 1.35, 1.15), STEEL, base=3.0)
    C.solid(seg(3.6, 15.6, 8.8, 20.6, 0.85), GOLD, base=3.0)
    C.solid(seg(5.4, 19.2, 3.0, 21.8, 0.75), LEATHER, base=2.6)
    C.solid(circle(2.6, 22.2, 1.1), GOLD, base=3.4)
    C.solid(union(seg(13.8, 10.0, 18.8, 4.6, 1.15, 0.95), poly([(18.0, 3.6), (21.8, 1.2), (19.6, 5.4)])), STEEL, base=3.0)
    C.glow(12.6, 11.4, 6, "ff3020", 0.8)
    C.energy(circle(12.6, 11.4, 1.5), CRIMSON, falloff=1.2)
    for k, (x, y) in enumerate(((15, 15), (10, 7), (17, 12))):
        C.solid(poly([(x, y), (x + 1.4, y + 0.4), (x + 0.4, y + 1.4)]), STEEL, base=2.8, seed=k)
    return A, B, C


def war_bs_martyrs_banner():
    # allies get double reduction, you none: a halo over an empty surcoat; a knight kneeling, bleeding; the scales tipped
    A = G("warrior", (12, 6))
    A.energy(cut(ellipse(12, 3.6, 6.4, 2.0), ellipse(12, 3.6, 4.6, 0.9)), HOLY, falloff=0.7)
    A.glow(12, 4, 6, "fff0a0", 0.4)
    tabard(A, 12, 14.4, 1.05)
    for k, (x, y) in enumerate(((9, 23), (15.5, 22.4))):
        A.energy(drop(x, y, 1.1), BLOOD, falloff=1.0)
    B = G("warrior", (12, 4))
    B.solid(ellipse(11, 22.8, 9, 1.4), EARTH, base=2.0)
    B.solid(poly([(8.4, 10.6), (6.6, 12.4), (3.6, 21.6), (9.0, 21.6)]), CLOTH, base=2.6)
    kn = union(circle(10.6, 9.0, 2.6), seg(10.6, 11.4, 11.6, 16.4, 2.6, 2.3), seg(11.6, 16.8, 16.6, 16.8, 1.7), seg(16.6, 16.8, 16.8, 22.4, 1.4, 1.6),
               seg(11.4, 17, 9.6, 22.0, 1.6), seg(9.6, 22.0, 5.0, 22.6, 1.2), seg(11.6, 12.4, 15.0, 14.4, 1.0))
    B.solid(kn, STEEL, base=2.8)
    B.paint(box(11.4, 8.8, 1.6, 0.4, -20), lambda x, y, d: (20, 20, 26))
    B.energy(drop(14, 21.4, 1.2), BLOOD, falloff=1.1)
    C = G("warrior", (12, 8))
    C.solid(seg(12, 6, 12, 20.6, 0.75), GOLD, base=2.8)
    C.solid(box(12, 21.6, 4.4, 1.0, 0, 0.4), GOLD, base=2.6)
    C.solid(seg(2.6, 9.6, 21.4, 4.6, 0.6), GOLD, base=3.2)
    C.solid(circle(12, 6.6, 1.3), GOLD, base=3.6)
    for x0, y0, py in ((2.6, 9.6, 17.0), (21.4, 4.6, 11.6)):
        for d in (-1, 1):
            C.solid(seg(x0, y0, x0 + d * 2.6, py, 0.25), GOLD, base=3.0)
        C.solid(inter(ellipse(x0, py, 3.2, 1.6), lambda x, y, py=py: (py - 0.3) - y), GOLD, base=2.6)
    for k, x in enumerate((1.4, 4.0)):
        C.solid(poly([(x - 1.3, 12.4), (x + 1.3, 12.4), (x + 1.3, 14.2), (x, 15.8), (x - 1.3, 14.2)]), STEEL, base=3.2, seed=k)
    C.glow(2.6, 14, 4.5, "fff0a0", 0.5)
    C.energy(drop(21.4, 14.6, 1.1), BLOOD, falloff=1.0)
    return A, B, C


def wlk_pb_proliferation():
    # the brand jumps to everyone nearby when its victim dies: from a grave; a ring of new fires round an ember; a chain of fire
    A = G("warlock", (12, 12))
    A.solid(ellipse(12, 23, 10, 1.6), EARTH, base=2.0)
    stone = union(box(12, 19.2, 4.0, 3.6, 0, 0.4), circle(12, 15.8, 4.0))
    A.solid(stone, SMOKE, base=2.6)
    A.paint(union(box(12, 16.4, 0.45, 2.4), box(12, 15.4, 1.6, 0.45)), lambda x, y, d: (30, 26, 30))
    for k, (x, y) in enumerate(((3.5, 4.5), (12, 2.5), (20.5, 4.5))):
        mid = ((12 + x) / 2 + (0 if k == 1 else (2 if x < 12 else -2)), (11.5 + y) / 2 - 1.5)
        A.energy(path([(12, 11.6), mid, (x, y + 2.8)], 0.8, 0.35), HELL, falloff=0.6)
        flame_mark(A, x, y, 0.42)
    B = G("warlock", (12, 12))
    B.energy(circle(12, 12, 2.6), R("140404", "3a0804", "6a1406", "a82a0a"), falloff=2.0)
    for k in range(6):
        a = math.radians(-90 + k * 60)
        x, y = 12 + math.cos(a) * 8.0, 12 + math.sin(a) * 8.0
        B.energy(seg(12 + math.cos(a) * 3, 12 + math.sin(a) * 3, 12 + math.cos(a) * 5.6, 12 + math.sin(a) * 5.6, 0.35), HELL, falloff=0.3)
        B.energy(flame(x, y + 2.4, 2.2, 5.4, 0, k + 2, 1), HELL, falloff=1.0)
    C = G("warlock", (12, 12))
    chain(C, 3, 20, 12, 12, EMBERS, 3.4, 1)
    chain(C, 12, 12, 21, 4, EMBERS, 3.4, 4)
    for k, (x, y) in enumerate(((3, 20), (12, 12), (21, 4))):
        C.energy(circle(x, y, 2.2), HELL, falloff=1.8)
    return A, B, C


def wlk_essence_extraction():
    # melee hits on branded elites and bosses draw essence: an axe biting; an elite's crown dripping into a vial; a hook
    A = G("warlock", (10, 8))
    axe(A, 10, 12, -60, 1.0, STEEL, WOOD)
    for k, (x, y, r) in enumerate(((17, 15, 1.5), (20, 12, 1.0), (19, 19, 1.1), (22, 16, 0.8))):
        A.energy(circle(x, y, r), ESS, falloff=r)
    A.energy(path([(14, 14), (18, 15.6)], 0.6), ESS, falloff=0.4)
    B = G("warlock", (12, 8))
    crown(B, 9, 7, 0.95)
    for k, y in enumerate((11.5, 14.5)):
        B.energy(drop(10 + k * 0.6, y, 0.9), ESS, falloff=0.8)
    potion(B, 15, 16, 0.85, ESS)
    C = G("warlock", (10, 8))
    C.solid(path([(3, 3), (9, 5), (12, 9), (13, 14), (11, 18.5), (7, 19), (5.6, 16)], 0.9, 0.7), GUN, base=3.0)
    C.solid(poly([(5.6, 16), (4.2, 13.4), (7.4, 15.4)]), STEEL, base=3.4)
    C.glow(15, 15, 7, "e05a80", 0.6)
    C.energy(circle(16.5, 15, 3.0), ESS, falloff=2.4)
    return A, B, C


def hud_tailwind():
    # Action Speed stacks: chevrons racing; a sail full of wind; a gauge pegged
    A = S("ranger")
    chevrons(A, 2.5, 7, 3, GUST, 0.6, 3.6, 3.2, up=False)
    B = S("ranger")
    B.solid(seg(5, 0.8, 5, 13.4, 0.5), WOOD, base=2.6)
    B.solid(poly([(5.5, 1.2), (9.2, 2.6), (11.6, 6.4), (10.4, 10.6), (5.5, 12)]), R("0e2236", "1c4466", "3a73a0", "7cb2d8", "c4e6f8", "ffffff"), base=3.2,
            light=(0.8, -0.4))
    for k, y in enumerate((4, 9)):
        line(B, 0, y, 3, y, 0.4, GUST, seed=k)
    C = S("ranger")
    C.energy(path(arc_pts(7, 10, 5.8, 180, 300, 10), 0.55), GUST, falloff=0.4)
    C.energy(path(arc_pts(7, 10, 5.8, 305, 360, 6), 0.6), R("3a0804", "a81e08", "e04a10", "ff8a2a", "ffd070"), falloff=0.4)
    for k in range(5):
        a = math.radians(180 + k * 45)
        C.px([(int(7 + math.cos(a) * 3.6), int(10 + math.sin(a) * 3.6))], (120, 170, 210))
    C.solid(seg(7, 10, 11.6, 6.0, 0.65, 0.35), R("5a0c06", "a81e08", "e04a10", "ff8a2a", "ffd070", "ffffff"), base=3.6)
    C.solid(circle(7, 10, 1.2), STEEL, base=3.4)
    line(C, 1, 13, 13, 13, 0.4, GUST)
    return A, B, C


def sor_bl_far_step():
    # Blink goes farther: two portals far apart; a road to the horizon, the blink at its end; a comet across the frame
    A = G("sorcerer", (12, 12))
    portal(A, 5, 18, 3.2, 4.4)
    portal(A, 19, 6, 3.2, 4.4)
    for k in range(5):
        t = (k + 1) / 6
        A.energy(circle(5 + 14 * t, 18 - 12 * t, 0.7), ARCANE, falloff=0.6)
    B = G("sorcerer", (12, 4))
    B.solid(poly([(-1, 24), (25, 24), (12.6, 9), (11.4, 9)]), R("0a0614", "1a0e30", "2c1850", "40246e"), base=2.4, light=(0, 1))
    for k, (y0, y1) in enumerate(((22, 19.4), (17.4, 15.4), (14.0, 12.6), (11.6, 10.8))):
        B.energy(seg(12, y0, 12, y1, 0.55 - k * 0.1), ARCANE, falloff=0.3)
    B.glow(12, 8, 6, "9a6ae0", 0.6)
    flash(B, 12, 7, 3.6, ARCANE, 1)
    C = G("sorcerer", (16, 8))
    C.energy(path([(1, 22), (6, 17.5), (11, 13), (16, 8.4)], 0.2, 2.6), ARCANE, falloff=1.2)
    C.energy(star(18.5, 6, 5.0, 1.6, 4, -90), R("6a3ab0", "9a6ae0", "d0b0ff", "ffffff"), falloff=1.2)
    return A, B, C


# ================================================================ the list, the runner
WHY_CLASS = "Round 3: the spec's emblem, never drawn before (a tinted vanilla placeholder until now)."
R3 = [  # (spec key, title, [(name, label, skill text, why)])
    ("ranger", "Ranger: Deadeye", [
        ("ran_class", "Deadeye (spec emblem)", "A wind and lightning archer.", WHY_CLASS),
        ("hud_tailwind", "Tailwind (status)", "Stacks of Action Speed.", "Round 3: the blue spiral repeats the Rogue's Lasting Gale spiral."),
    ]),
    ("wizard", "Wizard: Aerotheurge", [
        ("wiz_class", "Aerotheurge (spec emblem)", "A storm and air mage.", WHY_CLASS),
        ("wiz_tt_lightning_rod", "Lightning Rod (orb)", "More zaps per tick and more range.", "Round 3: it was the Thunder Orb's starburst again."),
        ("wiz_tt_lingering_storm", "Lingering Storm (orb)", "The orb lasts longer.", "Round 3: it reused the Thunder Orb, with an hourglass."),
        ("wiz_sc_conduit", "Conduit (orb)", "Static Charge stacks give cast speed.", "Round 3: it was Static Charge's hand with speed lines."),
    ]),
    ("sorcerer", "Sorcerer: Arcane", [
        ("sor_class", "Arcane (spec emblem)", "Blink, and mana as life.", WHY_CLASS),
        ("sor_bl_far_step", "Far Step (orb)", "Blink goes farther.", "Round 3: its row of figures was too close to the Rogue's ring of figures."),
        ("hud_void_barrier", "Void Barrier (status)", "Can't die for 1 s after a Blink.", "Round 3: it was a shrunken Void Barrier ring."),
    ]),
    ("rogue", "Rogue: Winddancer", [
        ("rog_class", "Winddancer (spec emblem)", "An evasive rogue who shares gales with allies.", WHY_CLASS),
        ("hud_protective_gale", "Protective Gale (status)", "Evasion from the gale.", "Round 3: it was a shrunken Protective Gale ring of figures."),
        ("hud_lingering_breeze", "Lingering Breeze (status)", "Health regeneration over time.", "Round 3: it was a shrunken copy of a skill icon."),
    ]),
    ("warrior", "Warrior: Bannerlord", [
        ("war_class", "Bannerlord (spec emblem)", "A war-banner leader.", WHY_CLASS),
        ("war_righteous_crusade", "Righteous Crusade (passive)", "Buffs last longer.", "Round 3: it was the Battlefield Standard's banner again."),
        ("war_bs_feared_crest", "Feared Crest (orb)", "Enemies near the standard are vulnerable.", "Round 3: it was the Battlefield Standard's banner again."),
        ("war_bs_martyrs_banner", "Martyr's Banner (orb)", "Allies get double the standard's damage reduction; you get none.",
         "Round 3: it was the Battlefield Standard's banner again."),
        ("hud_standard_raised", "Battlefield Standard, carried (status)", "Damage reduction while the standard is carried.",
         "Round 3: it was a shrunken banner; carried and planted must differ too."),
        ("hud_standard_planted", "Battlefield Standard, planted (status)", "Double damage reduction while it is planted.",
         "Round 3: it was a shrunken banner; carried and planted must differ too."),
        ("hud_shared_provisions", "Shared Provisions (status)", "Cooldown reduction stacks.", "Round 3: it was a shrunken copy of the sack."),
    ]),
    ("warlock", "Warlock: Branding", [
        ("wlk_class", "Branding (spec emblem)", "Demonic fire brands and stolen essence.", WHY_CLASS),
        ("wlk_ee_essence_empowerment", "Essence Empowerment (orb)", "Essence stacks add to Fire damage.", "Round 3: it was Combustion's flame column in pink."),
        ("wlk_pb_proliferation", "Proliferation (orb)", "The brand spreads to everyone nearby when its victim dies.", "Round 3: it was three Pyrebrand sigils."),
        ("wlk_essence_extraction", "Essence Extraction (passive)", "Melee hits on branded elites and bosses give Essence.",
         "Round 3: it reused the Pyrebrand sigil, with an essence wisp."),
        ("hud_pyrebrand", "Pyrebrand (status)", "This enemy is branded.", "Round 3: it was a shrunken Pyrebrand sigil."),
    ]),
]
ALL3 = {n: (key, lab, what, why) for key, _, items in R3 for n, lab, what, why in items}


def now(n):
    """The icon in game: the override when there is one, else the placeholder cell of the mod's sheet."""
    p = sp.OVR / f"{n}.png"
    if p.exists():
        return Image.open(p).convert("RGBA")
    if n.endswith("_class"):
        row = ["ran", "wiz", "sor", "rog", "war", "wlk"].index(n[:3])
        sheet_ = sp.REPO / "mods/specs/players/hwp/specs/icons.png"
        if sheet_.exists():
            return Image.open(sheet_).convert("RGBA").crop((0, row * 24, 24, row * 24 + 24))
    return None


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    for key, _, items in R3:
        rows = [(n, out[n] + ([now(n)] if now(n) else [])) for n, _, _, _ in items if n in out]
        if rows:
            sheet(rows, OUT / f"sheet_{key}.png")
    return out


def picker():
    groups = []
    for key, title, items in R3:
        its = []
        for n, lab, what, why in items:
            desc = what + " " + why
            if n.startswith("hud_"):
                desc += " A 14x14 buff-bar icon, shown at its size."
            imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
            if now(n):
                imgs["now"] = sp.uri(now(n))
            its.append({"id": "specs3." + n, "name": lab, "key": n, "desc": desc, "imgs": imgs})
        groups.append({"id": "specs3." + key, "title": title + ", round 3", "items": its})
    tpl = (sp.HERE / "picker_tpl.html").read_text(encoding="utf-8").replace("Skill Icon Picks", "Spec Icon Picks")
    assert "/*DATA*/null" in tpl
    page = OUT / "picker.html"
    page.write_text(tpl.replace("/*DATA*/null", json.dumps(groups)), encoding="utf-8")
    return page


def pick(fn):
    """The chosen idea of each icon to art/specs/override/<name>.png; "keep" leaves the current one."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    sp.OVR.mkdir(parents=True, exist_ok=True)
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specs3.") else k
        c = v.get("choice") if isinstance(v, dict) else v
        if n not in ALL3 or c not in ("a", "b", "c"):
            print("skip", k, c)
            continue
        im = Image.open(OUT / f"{n}_{c}.png").convert("RGBA")
        assert im.size == ((14, 14) if n.startswith("hud_") else (24, 24)), (n, im.size)
        im.save(sp.OVR / f"{n}.png")
        print("wrote", sp.OVR / f"{n}.png", c)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--pick"]:
        pick(a[1])
    else:
        render([x for x in a if not x.startswith("--")] or list(ALL3))
        if "--picker" in a:
            print(picker())
