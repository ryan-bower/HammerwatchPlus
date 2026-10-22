"""The six 4th specializations' icons (art/specs/REQUESTS.md): three ideas each, A (the
gear or body up close), B (the moment it happens) and C (an abstract mark), painted with
vpaint in the vanilla skill-icon style. Skills and orbs are 24x24, the buff-bar status
icons (hud_*) 14x14 at their own size.

    python tools/icon_art/sp.py [names...]   # out/specs/<name>_<a|b|c>.png, out/specs/sheet_<spec>.png
    python tools/icon_art/sp.py --picker     # also out/specs/picker.html (picker_tpl.html)
    python tools/icon_art/sp.py --pick FILE  # write the picks ({name: "a"|"b"|"c"} or the
                                             # picker's {"specs.<name>": {"choice": ..}})
                                             # to art/specs/override/<name>.png
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from vm import *
from motifs import heart, skull, flash

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out" / "specs"
OVR = REPO / "art" / "specs" / "override"

GUST = R("060c16", "0e2236", "1c4466", "3a73a0", "7cb2d8", "c4e6f8", "ffffff")    # the Stormbringer's wind
BREEZE = R("06100e", "10302a", "1e5848", "3a8a70", "70c0a0", "b8ecd8", "f4fff8")  # the Winddancer's
ELEC = R("04081e", "0a1848", "15338a", "2a62d0", "60a0ff", "bfe0ff", "ffffff")    # the Invocation's lightning
ESS = R("12040e", "360a24", "661440", "a02858", "e05a80", "ffb0c0", "ffffff")      # demonic essence
HELL = R("1e0604", "5a0c06", "a81e08", "e04a10", "ff8a2a", "ffd070", "ffffff")    # hellfire
CLOTH = R("140406", "3a0a10", "6e1220", "a81e2e", "dc3a40", "ff7060")            # banner cloth
FLESH = R("1a0c08", "3e2014", "6a3a24", "9a5a3a", "c88660", "eab48c")
FOE = R("080608", "1a141c", "2e2432", "4a3c50", "6e5c74", "9a88a0")              # a generic enemy

GROUNDS = {
    "ranger": ("060a12", "142236"), "wizard": ("04061a", "0e1640"), "sorcerer": ("0a0614", "221034"),
    "rogue": ("040e0a", "0e2620"), "warrior": ("120806", "2e160c"), "warlock": ("140404", "300a08"),
}


def G(spec, light=(8, 6), n=24):
    d, m = GROUNDS[spec]
    return Icon(n).ground(d, m, light=light)


def S(spec, light=(5, 4)):
    return G(spec, light, 14)


# ---------------------------------------------------------------- shapes
def path(pts, w0, w1=None):
    """A tapered stroke along pts, w0 at the start to w1 at the end."""
    w1 = w0 if w1 is None else w1
    n = len(pts) - 1
    return union(*[seg(*pts[i], *pts[i + 1], w0 + (w1 - w0) * i / n, w0 + (w1 - w0) * (i + 1) / n) for i in range(n)])


def spiral_pts(cx, cy, r0, r1, a0, turns, n=24):
    """Points along a spiral from radius r0 at angle a0 (degrees) to r1, turning `turns`
    times clockwise on screen (negative: counter-clockwise)."""
    return [(cx + math.cos(math.radians(a0 + 360 * turns * k / n)) * (r0 + (r1 - r0) * k / n),
             cy + math.sin(math.radians(a0 + 360 * turns * k / n)) * (r0 + (r1 - r0) * k / n)) for k in range(n + 1)]


def arc_pts(cx, cy, r, a0, a1, n=12):
    return [(cx + math.cos(math.radians(a0 + (a1 - a0) * k / n)) * r,
             cy + math.sin(math.radians(a0 + (a1 - a0) * k / n)) * r) for k in range(n + 1)]


def zig(x0, y0, x1, y1, n=5, amp=1.8, seed=0):
    """A jagged lightning path from (x0, y0) to (x1, y1)."""
    dx, dy = x1 - x0, y1 - y0
    L_ = math.hypot(dx, dy) or 1
    nx, ny = -dy / L_, dx / L_
    pts = [(x0, y0)]
    for k in range(1, n):
        t = k / n
        o = (h2(k, seed, 77) - 0.5) * 2 * amp
        pts.append((x0 + dx * t + nx * o, y0 + dy * t + ny * o))
    pts.append((x1, y1))
    return pts


def zap(ic, x0, y0, x1, y1, rmp=ELEC, w=0.7, n=5, amp=1.8, seed=0, fall=0.7):
    ic.energy(path(zig(x0, y0, x1, y1, n, amp, seed), w, w * 0.6), rmp, falloff=fall)


def swirl(ic, cx, cy, r0, r1, a0, turns, w0, w1, rmp, fall=0.6):
    ic.energy(path(spiral_pts(cx, cy, r0, r1, a0, turns), w0, w1), rmp, falloff=fall)


def gust(ic, x0, y0, x1, y1, curl, w, rmp, fall=0.6):
    """A wind stroke from (x0, y0) to (x1, y1), its tip curling round `curl` turns."""
    pts = [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + math.sin(t * 3.14) * -1.2) for t in (0, .25, .5, .75, 1)]
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    r = 2.6
    cx, cy = x1 + math.cos(math.radians(ang - 90)) * r, y1 + math.sin(math.radians(ang - 90)) * r
    pts += spiral_pts(cx, cy, r, r * 0.35, ang + 90, curl, 10)[1:]
    ic.energy(path(pts, w * 0.5, w), rmp, falloff=fall)


def figure(ic, cx, cy, s=1.0, rmp=FOE, seed=0, base=None):
    """A person standing, about 16s tall, (cx, cy) the middle."""
    f = union(circle(cx, cy - 5.4 * s, 2.1 * s), box(cx, cy - 0.6 * s, 2.4 * s, 3.2 * s, 0, 1.2 * s),
              seg(cx - 1.2 * s, cy + 2.4 * s, cx - 1.6 * s, cy + 7.6 * s, 1.0 * s),
              seg(cx + 1.2 * s, cy + 2.4 * s, cx + 1.6 * s, cy + 7.6 * s, 1.0 * s),
              seg(cx - 2.3 * s, cy - 2.4 * s, cx - 3.4 * s, cy + 2.2 * s, 0.8 * s),
              seg(cx + 2.3 * s, cy - 2.4 * s, cx + 3.4 * s, cy + 2.2 * s, 0.8 * s))
    ic.solid(f, rmp, seed=seed, base=base)
    return f


def foe(ic, cx, cy, s=1.0, rmp=FOE, seed=0):
    """A hunched enemy: round head, horns, broad shoulders."""
    f = union(ellipse(cx, cy + 2 * s, 5.2 * s, 4.2 * s), circle(cx, cy - 3 * s, 3.0 * s),
              poly([(cx - 2.6 * s, cy - 4.6 * s), (cx - 4.4 * s, cy - 8.2 * s), (cx - 1.2 * s, cy - 5.6 * s)]),
              poly([(cx + 2.6 * s, cy - 4.6 * s), (cx + 4.4 * s, cy - 8.2 * s), (cx + 1.2 * s, cy - 5.6 * s)]))
    ic.solid(f, rmp, seed=seed)
    for d in (-1, 1):
        ic.energy(circle(cx + d * 1.2 * s, cy - 3.2 * s, 0.55 * s), HELL, falloff=0.5)
    return f


def ball(ic, cx, cy, r, rmp=ELEC, seed=0, bolts=3):
    """A crackling ball of lightning: a glowing core with white arcs over it."""
    ic.glow(cx, cy, r * 2.2, rmp[4], 0.7)
    ic.energy(circle(cx, cy, r), rmp, falloff=r * 0.9, seed=seed)
    for k in range(bolts):
        a = math.radians(k * 360 / bolts + 30 + seed * 40)
        ic.energy(path(zig(cx - math.cos(a) * r * 0.7, cy - math.sin(a) * r * 0.7,
                           cx + math.cos(a) * r * 0.8, cy + math.sin(a) * r * 0.8, 3, r * 0.3, seed + k), 0.35),
                  R("ffffff", "ffffff"), falloff=0.3)


def spark(ic, cx, cy, r, rmp=ELEC):
    ic.energy(union(seg(cx - r, cy, cx + r, cy, 0.45, 0.45), seg(cx, cy - r, cx, cy + r, 0.45, 0.45),
                    seg(cx - r * 0.6, cy - r * 0.6, cx + r * 0.6, cy + r * 0.6, 0.3),
                    seg(cx - r * 0.6, cy + r * 0.6, cx + r * 0.6, cy - r * 0.6, 0.3), circle(cx, cy, r * 0.35)),
              rmp, falloff=0.6)


def plus(ic, cx, cy, r, rmp=LIFE, w=0.6):
    ic.energy(union(seg(cx - r, cy, cx + r, cy, w), seg(cx, cy - r, cx, cy + r, w)), rmp, falloff=w)


def banner(ic, px, top, bottom, s=1.0, cloth=CLOTH, crest=GOLD, pole=WOOD, wave=0.0, seed=0, emblem="shield"):
    """A war standard: a pole from top to bottom at px, a crossbar, a swallow-tailed cloth
    hanging to the right with a crest on it."""
    w, h = 9.0 * s, 11.0 * s
    x0, y0 = px + 0.6 * s, top + 1.6 * s
    ic.solid(box(px, (top + bottom) / 2, 0.75 * s, (bottom - top) / 2, 0, 0.3), pole, seed=seed, base=2.4)

    def cl(x, y):
        u = (x - x0) / w
        if u < 0 or u > 1:
            return 1.0
        sag = math.sin(u * 3.0 + wave) * 0.8 * s * u
        yt = y0 + sag
        yb = y0 + h - (2.6 * s if abs(u - 0.62) < 0.2 and u > 0.42 else 0) * (1 - abs(u - 0.62) / 0.2) + sag
        return max(yt - y, y - yb, -u * w, (u - 1) * w)
    ic.solid(cl, cloth, seed=seed + 1, base=2.8, light=(-0.6, -0.8))
    ic.solid(box(px + 4.8 * s, top + 1.2 * s, 5.4 * s, 0.7 * s, 0, 0.3), pole, seed=seed + 2, base=3.0)
    ic.solid(circle(px, top + 0.4 * s, 1.1 * s), crest, seed=seed + 3, base=3.4)
    cx, cy = x0 + w * 0.47, y0 + h * 0.42 + math.sin(0.47 * 3.0 + wave) * 0.8 * s * 0.47
    if emblem == "shield":
        ic.solid(poly([(cx - 2.6 * s, cy - 2.8 * s), (cx + 2.6 * s, cy - 2.8 * s), (cx + 2.6 * s, cy + 0.4 * s),
                       (cx, cy + 3.2 * s), (cx - 2.6 * s, cy + 0.4 * s)]), crest, seed=seed + 4, base=3.0)
    elif emblem == "sun":
        sun(ic, cx, cy, 1.5 * s, HOLY, 8)
    return cx, cy


def drumkit(ic, cx, cy, s=1.0, seed=0):
    """A war drum seen from the front and a little above: a red shell, a hide head, ropes."""
    ic.solid(box(cx, cy + 1.5 * s, 6.4 * s, 4.4 * s, 0, 0.6 * s), CLOTH, seed=seed, base=2.6, light=(-1, 0))
    for k in range(5):
        x = cx - 5.2 * s + k * 2.6 * s
        ic.solid(seg(x, cy - 2.2 * s, x + 1.3 * s, cy + 5.2 * s, 0.35 * s), BONE, seed=seed + k, base=3.6, noise=0.2)
    ic.solid(box(cx, cy + 5.6 * s, 6.6 * s, 0.8 * s, 0, 0.3), BRASS, seed=seed + 7, base=2.8)
    ic.solid(ellipse(cx, cy - 2.8 * s, 6.6 * s, 2.0 * s), BRASS, seed=seed + 8, base=2.8)
    ic.solid(ellipse(cx, cy - 2.8 * s, 5.8 * s, 1.5 * s), PAPER, seed=seed + 9, base=3.4, spread=0.6)


def sack(ic, cx, cy, s=1.0, seed=0):
    f = union(ellipse(cx, cy + 1.5 * s, 5.6 * s, 5.0 * s), poly([(cx - 2 * s, cy - 3 * s), (cx + 2 * s, cy - 3 * s), (cx + 3.2 * s, cy - 6 * s), (cx - 3.2 * s, cy - 6 * s)]))
    ic.solid(f, LEATHER, seed=seed, base=2.8)
    ic.solid(box(cx, cy - 3.2 * s, 2.6 * s, 0.6 * s, 0, 0.3), CLOTH, seed=seed + 1, base=3.0)
    return f


def sigil(ic, cx, cy, r, rmp=HELL, w=0.55, fall=0.6, spokes=True):
    """The demonic brand: a ring, a downward triangle through it, three hooked spokes."""
    tri = [(cx + math.cos(math.radians(90 + k * 120)) * r * 0.82, cy + math.sin(math.radians(90 + k * 120)) * r * 0.82) for k in range(3)]
    fs = [ring(cx, cy, r, w * 2)] + [seg(*tri[k], *tri[(k + 1) % 3], w) for k in range(3)]
    if spokes:
        for k in range(3):
            a = math.radians(-90 + k * 120)
            fs.append(seg(cx + math.cos(a) * r, cy + math.sin(a) * r, cx + math.cos(a) * (r + 2.2), cy + math.sin(a) * (r + 2.2), w, w * 0.4))
    ic.energy(union(*fs), rmp, falloff=fall)


def claw(ic, cx, by, s=1.0, rmp=HELL, seed=0):
    """Three hooked talons tearing up out of the ground at (cx, by)."""
    for k, (dx, h, lean) in enumerate(((-3.6, 9, -1.6), (0, 12, 0.4), (3.6, 9.5, 2.0))):
        pts = [(cx + dx * s, by), (cx + (dx + lean * 0.4) * s, by - h * 0.5 * s), (cx + (dx + lean) * s, by - h * 0.85 * s),
               (cx + (dx + lean * 1.8) * s, by - h * s)]
        ic.energy(path(pts, 1.6 * s, 0.25 * s), rmp, falloff=1.2 * s, seed=seed + k)
    ic.energy(ellipse(cx, by + 0.5 * s, 7 * s, 1.6 * s), rmp, falloff=1.0)


VHEAD = R("8a7010", "d0b020", "ffe848", "fffcc0", "ffffff", "ffffff")   # a charged arrowhead


def line(ic, x0, y0, x1, y1, w, rmp, seed=3):
    """A speed line through pixel centres, thick enough to read at 24x24."""
    ic.streak(x0 + 0.5, y0 + 0.5, x1 + 0.5, y1 + 0.5, max(w * 1.6, 0.9), rmp, seed)


FLETCH = R("060c16", "0e2236", "1c4466", "2e5a88", "4a80b0")    # blue-grey feathers, darker than the head


def arrowv(ic, cx, cy, ang, s=0.8, fletch=FLETCH, head=STEEL, seed=0):
    arrow(ic, cx, cy, ang, s, WOOD, head, fletch, seed)


def foot(cx, cy, s=1.0, ang=0):
    return union(ellipse(cx, cy, 1.5 * s, 2.6 * s, ang), ellipse(cx + 0.2 * s, cy + 3.3 * s, 1.1 * s, 1.1 * s, ang))


# ================================================================ Ranger: Deadeye (was Stormbringer)
def ran_electric_circuit():
    # three arrows in a V flying out to the upper right, crackling, a path bending back
    A = G("ranger", (12, 16))
    for d in (-1, 1):
        A.energy(path(arc_pts(12, 12, 11, -90 + d * 30, -90 + d * 150), 0.2, 0.7), GUST, falloff=0.4)
    for k, (x, y) in enumerate(((12, 9), (5.5, 14.5), (18.5, 14.5))):
        zap(A, x - 1.8, y + 7, x + 1.8, y - 3, VOLT, 0.3, 4, 1.4, k)
        arrowv(A, x, y, -90, 0.66, head=VHEAD, seed=k)
    # the moment they turn: three curved trails out and back, the arrows on their way home
    B = G("ranger", (12, 12))
    for k, (r, a1) in enumerate(((5.5, 250), (8.0, 260), (10.5, 270))):
        B.energy(path(arc_pts(12, 13, r, 100, a1), 0.25, 0.8), VOLT if k == 1 else GUST, falloff=0.5)
        a = math.radians(a1)
        arrowv(B, 12 + math.cos(a) * r, 13 + math.sin(a) * r, a1 + 90, 0.42, seed=k)
    # a V of lightning with the return hook
    C = G("ranger", (12, 8))
    zap(C, 4, 4, 12, 19, VOLT, 0.8, 4, 1.2, 1)
    zap(C, 20, 4, 12, 19, VOLT, 0.8, 4, 1.2, 2)
    C.energy(path(arc_pts(12, 10, 5, 200, 340), 0.4, 0.8), GUST, falloff=0.5)
    C.energy(poly([(16.5, 5.2), (19.5, 8.6), (15.2, 9.4)]), GUST, falloff=0.6)
    return A, B, C


def ran_gathering_winds():
    A = G("ranger", (10, 8))
    swirl(A, 12, 12, 10, 3, 200, -0.85, 0.3, 1.1, GUST)
    bow(A, 13, 12, -45, 0.85, drawn=2.5)
    arrowv(A, 11.5, 13.5, -45, 0.7)
    B = G("ranger", (14, 10))
    for k, (y, x0, x1) in enumerate(((5, 0, 9), (10, 0, 7), (15, 1, 8), (20, 0, 10))):
        line(B, x0, y, x1, y, 0.6, GUST, seed=k)
    bow(B, 15, 12, 0, 0.95, drawn=3)
    arrowv(B, 13, 12, 0, 0.75)
    C = G("ranger", (12, 12))
    swirl(C, 12, 12, 9.5, 1.5, 0, -1.6, 0.4, 1.4, GUST)
    for k, y in enumerate((5, 19)):
        line(C, 1, y, 9, y, 0.5, GUST, seed=k)
    return A, B, C


def ran_ec_boomerang():
    A = G("ranger", (14, 8))
    A.energy(path([(4, 4), (11, 3.5), (17.5, 4.5), (21.5, 9.5), (20, 15), (15, 17.5)], 0.3, 1.2), VOLT, falloff=0.7)
    arrowv(A, 9, 17.5, 180, 0.78, head=VHEAD)
    zap(A, 3, 13, 12, 13.5, VOLT, 0.35, 4, 1.0, 0)
    B = G("ranger", (12, 12))
    for k in range(3):
        B.energy(path(arc_pts(12, 12, 9 - k * 0.6, 160 + k * 30, 420 + k * 10), 0.2, 0.6), GUST, falloff=0.4)
    arrowv(B, 12, 12, 180, 0.75, fletch=VOLT)
    for k, (x, y) in enumerate(((6, 8), (17, 16), (18, 7))):
        spark(B, x, y, 1.6, VOLT)
    C = G("ranger", (12, 8))
    C.energy(path(arc_pts(12, 13, 7, 180, 440), 1.1, 1.1), VOLT, falloff=0.9)
    C.energy(poly([(3.5, 15), (5, 8.5), (10, 13)]), VOLT, falloff=0.8)
    return A, B, C


def ran_ec_lightning_rod():
    A = G("ranger", (12, 6))
    arrowv(A, 12, 15, 90, 0.8)
    A.energy(ellipse(12, 21, 6, 1.4), VOLT, falloff=0.8)
    for k, (x0, x1) in enumerate(((3, 6), (12, 11), (21, 17))):
        zap(A, x0, 0, x1, 20, VOLT, 0.65, 5, 1.6, k)
    B = G("ranger", (12, 8))
    for k, x in enumerate((6, 12, 18)):
        zap(B, x + 2, 0, x, 15, VOLT, 0.55, 4, 1.3, k + 3)
    arrowv(B, 12, 16, 0, 0.9)
    C = G("ranger", (12, 10))
    arrowv(C, 12, 13, -90, 0.95)
    for k, (x, y) in enumerate(((2, 2), (22, 3), (2, 13), (22, 14))):
        zap(C, x, y, 12, 5, VOLT, 0.5, 3, 1.0, k)
    C.energy(circle(12, 4.6, 1.6), VOLT, falloff=1.2)
    return A, B, C


def ran_ec_tailwind_catch():
    A = G("ranger", (10, 10))
    swirl(A, 10, 13, 9, 3, 0, -0.8, 0.3, 1.0, GUST)
    hand_open(A, 7, 16, 0.75, SKIN)
    arrowv(A, 14, 8, 145, 0.66)
    B = G("ranger", (12, 12))
    B.energy(path(arc_pts(12, 11, 8, -60, 160), 0.3, 1.0), GUST, falloff=0.5)
    arrowv(B, 6, 15, 160 + 90, 0.55)
    hand_open(B, 6, 19, 0.55, SKIN)
    C = G("ranger", (12, 12))
    swirl(C, 12, 12, 9.5, 2, 90, -1.3, 0.4, 1.3, GUST)
    arrowv(C, 12, 12, 180, 0.7)
    return A, B, C


def ran_gw_gale_force():
    A = G("ranger", (6, 12))
    swirl(A, 6, 12, 6, 1.5, 90, -1.2, 0.3, 1.0, GUST)
    for k, a in enumerate((-35, -12, 12, 35)):
        r = math.radians(a)
        arrowv(A, 8 + math.cos(r) * 8, 12 + math.sin(r) * 8, a, 0.5, seed=k)
    B = G("ranger", (6, 12))
    for k, a in enumerate((-40, -20, 0, 20, 40)):
        r = math.radians(a)
        line(B, 2, 12, 2 + math.cos(r) * 10, 12 + math.sin(r) * 10, 0.4, GUST, seed=k)
        arrowv(B, 4 + math.cos(r) * 13, 12 + math.sin(r) * 13, a, 0.42, seed=k)
    C = G("ranger", (12, 12))
    for k, y in enumerate((6, 12, 18)):
        gust(C, 1, y, 14, y, 0.6, 1.2, GUST)
        C.solid(poly([(16, y - 2.2), (22, y), (16, y + 2.2)]), STEEL, base=3.2)
    return A, B, C


def ran_gw_wind_ward():
    A = G("ranger", (12, 12))
    figure(A, 12, 13, 0.85, R("0a1018", "18263a", "2a4260", "426488", "6a90b0", "a0c4dc"))
    swirl(A, 12, 12, 9.5, 9.0, 0, 0.9, 0.5, 1.1, GUST)
    arrowv(A, 20, 4, 135, 0.5, fletch=CRIMSON)
    spark(A, 18, 6, 2, R("3a73a0", "7cb2d8", "c4e6f8", "e8f8ff", "ffffff", "ffffff"))
    B = G("ranger", (10, 14))
    B.energy(path(arc_pts(6, 12, 9, -70, 70), 1.2, 1.2), GUST, falloff=0.9)
    arrowv(B, 18, 8, 160, 0.6, fletch=CRIMSON)
    arrowv(B, 18, 17, 200, 0.6, fletch=CRIMSON)
    spark(B, 14, 12, 2.2, GUST)
    C = G("ranger", (12, 12))
    shield(C, 12, 12, 0.6, STEEL, face=GUST, boss=None, kite=True)
    for k in range(3):
        C.energy(path(arc_pts(12, 12, 10, k * 120 + 10, k * 120 + 90), 0.3, 1.0), GUST, falloff=0.5)
    return A, B, C


def hud_tailwind():
    A = S("ranger")
    swirl(A, 7, 7, 6, 1, 180, -1.2, 0.3, 1.0, GUST)
    B = S("ranger")
    for k, y in enumerate((4, 10)):
        line(B, 0, y, 7, y, 0.5, GUST, seed=k)
    swirl(B, 9, 7, 4.2, 1, 90, -1.1, 0.3, 0.9, GUST)
    C = S("ranger")
    for k, (y, x0, x1) in enumerate(((3, 2, 12), (7, 0, 9), (11, 3, 13))):
        line(C, x0, y, x1, y, 0.6, GUST, seed=k)
    return A, B, C


# ================================================================ Wizard: Aerotheurge (was Invocation)
def wiz_tempest_torrent():
    A = G("wizard", (9, 9))
    for k, (x, y) in enumerate(((22, 3), (23, 15), (14, 23), (2, 22))):
        zap(A, 9, 10, x, y, ELEC, 0.55, 5, 1.6, k)
    ball(A, 9, 10, 4.6, seed=1)
    B = G("wizard", (8, 6))
    for k, (x, y) in enumerate(((5, 19), (18, 20))):
        foe(B, x, y, 0.55, seed=k)
        zap(B, 11, 7, x, y - 3, ELEC, 0.5, 4, 1.4, k + 2)
    ball(B, 11, 7, 4.0, seed=2)
    C = G("wizard", (12, 12))
    C.energy(ring(12, 12, 9.5, 0.8), ELEC, falloff=0.4)
    ball(C, 12, 12, 6.5, seed=3, bolts=4)
    return A, B, C


def wiz_static_charge():
    A = G("wizard", (12, 10))
    hand_open(A, 12, 17, 0.85, SKIN)
    for k, (x, y) in enumerate(((9.2, 7.0), (11.1, 5.6), (13.0, 5.5), (14.9, 6.8))):
        spark(A, x, y - 2.2, 1.5)
    B = G("wizard", (12, 12))
    hand_open(B, 12, 17, 1.1, SKIN)
    for k in range(3):
        zap(B, 8.4 + k * 2.4, 6.6, 10.8 + k * 2.4, 6.4, ELEC, 0.4, 3, 1.0, k)
    B.glow(12, 7, 7, "60a0ff", 0.6)
    C = G("wizard", (12, 12))
    for k, (x, y, r) in enumerate(((12, 12, 4.6), (5, 6, 2.4), (19, 7, 2.0), (6, 18, 1.8), (18, 18, 2.6))):
        spark(C, x, y, r)
    return A, B, C


def wiz_tt_overcharge():
    A = G("wizard", (12, 16))
    for k, (x0, y0) in enumerate(((3, 0), (12, 0), (21, 0))):
        zap(A, x0, y0, 12, 17, ELEC, 0.55, 5, 1.4, k)
    A.glow(12, 17, 9, "a0d0ff", 0.9)
    A.energy(circle(12, 17, 2.6), ELEC, falloff=2)
    B = G("wizard", (12, 18))
    for k, r in enumerate((3, 5.5, 8)):
        B.energy(ring(12, 19, r, 0.6), ELEC, falloff=0.4)
    zap(B, 13, 0, 12, 18, ELEC, 1.1, 5, 1.6, 7)
    B.energy(circle(12, 18.5, 1.8), ELEC, falloff=1.6)
    C = G("wizard", (12, 12))
    for k in range(3):
        y = 17 - k * 5
        C.energy(path([(5, y + 3), (12, y - 2), (19, y + 3)], 0.6 + k * 0.25), ELEC, falloff=0.4 + k * 0.2)
    zap(C, 13, 0, 11, 6, ELEC, 0.6, 3, 1, 3)
    return A, B, C


def wiz_tt_lingering_storm():
    A = G("wizard", (10, 10))
    ball(A, 8, 8, 5, seed=4)
    hourglass(A, 17, 15, 0.78, frame=WOOD, sand=ELEC, t=0.35)
    B = G("wizard", (16, 8))
    B.energy(path([(1, 22), (5, 19), (9, 15.5), (13, 12), (17, 8)], 0.4, 3.6), ELEC, falloff=1.6)
    ball(B, 17, 7, 4.4, seed=5)
    C = G("wizard", (12, 12))
    C.energy(path(arc_pts(12, 12, 9.5, -90, 200), 0.3, 1.2), ELEC, falloff=0.5)
    C.energy(poly([(2.0, 7.5), (5.6, 9.4), (1.8, 11.6)]), ELEC, falloff=0.6)
    ball(C, 12, 12, 5, seed=6)
    return A, B, C


def wiz_tt_thunderclap():
    A = G("wizard", (12, 12))
    pts = [(12 + math.cos(math.radians(k * 30)) * (9 + (1.3 if k % 2 else -0.3)),
            12 + math.sin(math.radians(k * 30)) * (9 + (1.3 if k % 2 else -0.3))) for k in range(13)]
    A.energy(path(pts, 0.6), ELEC, falloff=0.5)
    ball(A, 12, 12, 4.2, seed=7)
    B = G("wizard", (12, 12))
    B.rays(12, 12, ELEC, n=10, hi=4.5)
    for k in range(6):
        a = math.radians(k * 60 + 15)
        zap(B, 12, 12, 12 + math.cos(a) * 12, 12 + math.sin(a) * 12, ELEC, 0.5, 4, 1.2, k)
    ball(B, 12, 12, 3.6, seed=8)
    C = G("wizard", (12, 12))
    for k, r in enumerate((4, 7.5, 11)):
        pts = [(12 + math.cos(math.radians(j * 24)) * (r + (0.9 if j % 2 else -0.5)),
                12 + math.sin(math.radians(j * 24)) * (r + (0.9 if j % 2 else -0.5))) for j in range(16)]
        C.energy(path(pts, 0.7 - k * 0.15), ELEC, falloff=0.4)
    return A, B, C


def wiz_tt_lightning_rod():
    # more targets: the orb forking out to many foes at the frame's edges
    A = G("wizard", (12, 12))
    for k, (x, y) in enumerate(((3, 4), (21, 3), (2, 15), (22, 14), (8, 22), (17, 22))):
        zap(A, 12, 12, x, y, ELEC, 0.45, 4, 1.3, k)
    for k, (x, y) in enumerate(((3, 4), (21, 3), (2, 15), (22, 14), (8, 22), (17, 22))):
        A.energy(circle(x, y, 1.3), ELEC, falloff=1.0)
    ball(A, 12, 12, 4.2, seed=9)
    # a lightning rod: an iron spire crowned with the orb, bolts thrown wide
    B = G("wizard", (12, 6))
    B.solid(seg(12, 9, 12, 23, 0.9, 1.4), GUN, base=2.6)
    for y in (14, 18):
        B.solid(box(12, y, 2.4, 0.6, 0, 0.3), GUN, base=3.0)
    for k, (x, y) in enumerate(((1, 2), (23, 3), (1, 13), (23, 12))):
        zap(B, 12, 6, x, y, ELEC, 0.45, 4, 1.2, k + 4)
    ball(B, 12, 6, 3.8, seed=10)
    # increased range: the orb with a wide ring, chevrons pushing it outward
    C = G("wizard", (12, 12))
    C.energy(ring(12, 12, 6.6, 0.35), R("04081e", "0a1848", "15338a", "2a62d0"), falloff=0.3)
    for k in range(4):
        a = math.radians(k * 90 + 45)
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux
        x, y = 12 + ux * 9.4, 12 + uy * 9.4
        C.energy(path([(x - ux * 1.2 + px * 1.8, y - uy * 1.2 + py * 1.8), (x + ux * 0.8, y + uy * 0.8),
                       (x - ux * 1.2 - px * 1.8, y - uy * 1.2 - py * 1.8)], 0.55), ELEC, falloff=0.4)
    ball(C, 12, 12, 3.8, seed=11)
    return A, B, C


def wiz_sc_static_channel():
    A = G("wizard", (12, 12))
    spark(A, 6, 8, 4)
    A.energy(path([(9, 11), (12, 13), (14, 14)], 0.3, 0.8), ELEC, falloff=0.4)
    A.energy(drop(17, 17, 4.2), MANA, falloff=2.4)
    B = G("wizard", (12, 12))
    B.energy(drop(12, 14, 6.5), MANA, falloff=3)
    zap(B, 10, 5, 13, 18, R("ffffff", "ffffff"), 0.6, 4, 1.4, 2, 0.4)
    C = G("wizard", (12, 10))
    for k, (x, y) in enumerate(((6, 5), (12, 4), (18, 6))):
        spark(C, x, y, 2.4)
        C.energy(path([(x, y + 2.5), (12, 15)], 0.25, 0.6), ELEC, falloff=0.4)
    C.energy(drop(12, 17, 4), MANA, falloff=2.4)
    return A, B, C


def wiz_sc_conduit():
    A = G("wizard", (14, 10))
    for k, (y, x1) in enumerate(((6, 9), (11, 7), (16, 8), (21, 9))):
        line(A, 0, y, x1, y, 0.5, ELEC, seed=k)
    hand_open(A, 15, 13, 0.95, SKIN)
    A.glow(15, 9, 8, "60a0ff", 0.7)
    zap(A, 11, 5, 19, 4, ELEC, 0.35, 3, 1.0, 3)
    B = G("wizard", (14, 12))
    for k, y in enumerate((5, 9, 14, 18)):
        line(B, 0, y, 8, y, 0.5, ELEC, seed=k)
    fist(B, 15, 12, 1.0, SKIN)
    for k, (x0, y0, x1, y1) in enumerate(((12, 6, 19, 4), (19, 10, 23, 14), (11, 17, 18, 20))):
        zap(B, x0, y0, x1, y1, ELEC, 0.4, 3, 1.2, k)
    C = G("wizard", (12, 12))
    for k, y in enumerate((6, 12, 18)):
        line(C, 0, y, 8, y, 0.6, ELEC, seed=k)
    C.energy(poly([(15, 2), (9, 13), (13, 13), (10, 22), (18, 9), (14, 9), (18, 2)]), ELEC, falloff=1.4)
    return A, B, C


def hud_static_charge():
    A = S("wizard")
    spark(A, 7, 7, 4.6)
    B = S("wizard")
    B.energy(poly([(8.5, 1), (4, 8), (7, 8), (5, 13), (10.5, 6), (7.5, 6), (10, 1)]), ELEC, falloff=1.2)
    C = S("wizard")
    for k, (x, y, r) in enumerate(((7, 7, 3.2), (3, 3, 1.4), (11, 11, 1.6))):
        spark(C, x, y, r)
    return A, B, C


# ================================================================ Sorcerer: Arcane
GHOST = R("0a0614", "1a0e30", "2c1850", "40246e", "583490", "7048b0")   # a dim afterimage


def sor_blink():
    # gone from the left in a flash, standing on the right; the afterimage between
    A = G("sorcerer", (16, 8))
    A.energy(path([(5, 15), (11, 13), (17, 12)], 0.3, 1.0), ARCANE, falloff=0.5)
    figure(A, 5, 13, 0.75, GHOST, base=2.2)
    flash(A, 5, 12, 4.2, ARCANE, 2)
    A.glow(17, 11, 9, "9a6ae0", 0.6)
    figure(A, 17, 13, 0.85, R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc", "d0bcf0"))
    # the arrival: a burst ring with the figure stepping out of it
    B = G("sorcerer", (12, 12))
    B.rays(12, 12, ARCANE, n=8, hi=4)
    B.energy(ring(12, 12, 8.5, 0.7), ARCANE, falloff=0.5)
    figure(B, 12, 12.5, 0.8, R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc", "d0bcf0"))
    for k, (x, y) in enumerate(((4, 4), (20, 5), (19, 20))):
        spark(B, x, y, 1.5, ARCANE)
    # two flashes joined by a dotted jump
    C = G("sorcerer", (12, 12))
    for k in range(5):
        t = k / 4
        C.energy(circle(6 + 12 * t, 17 - 10 * t - math.sin(t * 3.14) * 3, 0.6 + 0.2 * k), ARCANE, falloff=0.5)
    flash(C, 5, 18, 3.6, ARCANE, 1)
    flash(C, 18, 6, 4.6, ARCANE, 3)
    return A, B, C


def sor_living_mana():
    A = G("sorcerer", (8, 6))
    A.glow(12, 12, 12, "5a90e8", 0.5)
    A.energy(heart(12, 12, 7.6), MANA, falloff=4.0)
    A.energy(heart(10, 10, 2.2), R("ffffff", "ffffff"), falloff=1)
    # a heart vessel, half full of mana
    B = G("sorcerer", (8, 6))
    h = heart(12, 12, 7.6)
    B.solid(h, SHADOW, base=1.4, spread=1.0)
    B.energy(inter(h, lambda x, y: 10.5 - y), MANA, falloff=2.5)
    B.solid(cut(h, heart(12, 12, 6.2)), CRIMSON, base=3.0)
    B.glint(9, 9)
    # a heart drawn in mana, a drop for its core
    C = G("sorcerer", (10, 8))
    C.energy(cut(heart(12, 12.5, 8), heart(12, 12.3, 5.6)), ARCANE, falloff=0.9)
    C.energy(drop(12, 12, 3.2), MANA, falloff=2.4)
    return A, B, C


def sor_bl_void_barrier():
    A = G("sorcerer", (12, 12))
    figure(A, 12, 12.5, 0.8, R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc", "d0bcf0"))
    A.energy(cut(circle(12, 12, 10.5), circle(12, 12, 8.8)), VOID, falloff=1.0)
    A.glint(6, 6)
    # the shell taking a blow: a dark dome, a strike splintering on it
    B = G("sorcerer", (12, 12))
    B.solid(circle(12, 13, 9.5), VOID, base=1.4, spread=1.4, light=(-0.6, -0.8))
    figure(B, 12, 14, 0.7, GHOST)
    for k, a in enumerate((-60, -30, 0)):
        r = math.radians(a)
        line(B, 21 + math.cos(r) * 4, 4 + math.sin(r) * 4, 19, 6, 0.6, R("6a3ab0", "9a6ae0", "d0b0ff", "ffffff"), seed=k)
    spark(B, 18.5, 6.5, 2.6, ARCANE)
    # a void shield, a crescent of violet
    C = G("sorcerer", (12, 12))
    shield(C, 12, 11, 0.95, VOID, face=SHADOW, boss=None, kite=False)
    C.energy(ring(12, 11, 5.4, 0.5), ARCANE, falloff=0.4)
    C.energy(circle(12, 11, 1.8), ARCANE, falloff=1.4)
    return A, B, C


def sor_bl_far_step():
    A = G("sorcerer", (14, 8))
    for k in range(6):
        t = (k + 1) / 7
        A.energy(circle(5 + 13 * t, 18 - 12 * t, 0.5 + 0.12 * k), ARCANE, falloff=0.5)
    A.glow(18, 6, 7, "9a6ae0", 0.6)
    for k, (x, y, s) in enumerate(((4.5, 17, 1.0), (17.5, 4.5, 1.05))):
        A.energy(foot(x, y, s, 40), ARCANE, falloff=1.2 + k * 0.6)
    B = G("sorcerer", (18, 10))
    for k, x in enumerate((3, 8, 13)):
        figure(B, x, 13, 0.6 + k * 0.08, GHOST, base=1.0 + k, seed=k)
    B.glow(19, 11, 8, "9a6ae0", 0.6)
    figure(B, 19, 13, 0.8, R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc", "d0bcf0"))
    C = G("sorcerer", (12, 12))
    for k, (x, y) in enumerate(((4.5, 17), (11.5, 11), (18.5, 4))):
        C.energy(foot(x + (1.4 if k % 2 else -1.4), y, 0.95, 45), ARCANE, falloff=1.0 + k * 0.45)
    return A, B, C


def sor_lm_arcane_feedback():
    # a crack across a dark plate, violet spilling out
    A = G("sorcerer", (12, 12))
    shield(A, 12, 11, 1.05, STEEL, face=SHADOW, boss=None, kite=True)
    A.glow(12, 11, 9, "9a6ae0", 0.6)
    A.energy(path(zig(7, 3, 15, 20, 5, 2.0, 3), 1.1, 0.4), ARCANE, falloff=0.8)
    for k, (x, y) in enumerate(((7, 13), (15, 9), (17, 16))):
        A.energy(circle(x, y, 0.7), ARCANE, falloff=0.5)
    # a blow landing, and the force flowing into the caster's hand
    B = G("sorcerer", (12, 12))
    sword(B, 15, 9, 135, 0.8, STEEL)
    B.glow(9, 15, 9, "9a6ae0", 0.7)
    flash(B, 9, 15, 4.2, ARCANE, 2)
    for k, (x, y, a) in enumerate(((4, 21, 120), (3, 10, 200), (14, 21, 60))):
        wisp(B, x, y, 1.3, ARCANE, a, k)
    # a cracked heart pouring violet
    C = G("sorcerer", (8, 6))
    h = heart(12, 11, 7)
    C.solid(h, CRIMSON, base=2.2)
    C.energy(inter(h, path(zig(10, 4, 13, 19, 4, 1.6, 5), 0.8, 0.4)), ARCANE, falloff=0.6)
    C.energy(path([(13, 17), (13.5, 20), (13, 23)], 0.9, 0.3), ARCANE, falloff=0.6)
    return A, B, C


def sor_lm_mana_conduit():
    A = G("sorcerer", (12, 8))
    for k, x in enumerate((4.5, 19.5)):
        A.energy(path([(12, 9), ((12 + x) / 2, 9 + (k - 0.5) * 0), (x, 14)], 0.8, 0.4), MANA, falloff=0.6)
        figure(A, x, 16, 0.55, R("0a1018", "18263a", "2a4260", "426488", "6a90b0", "a0c4dc"), seed=k)
    A.energy(drop(12, 7, 3.6), MANA, falloff=2.6)
    B = G("sorcerer", (12, 14))
    hand_open(B, 12, 17, 0.8, SKIN)
    for k, (x, y) in enumerate(((4, 3), (20, 3))):
        B.energy(path([(12, 10), ((12 + x) / 2, 9), (x, y)], 0.9, 0.4), MANA, falloff=0.6)
        B.energy(circle(x, y, 2.0), MANA, falloff=1.6)
    C = G("sorcerer", (12, 12))
    for k, (x, y) in enumerate(((5, 18), (19, 18))):
        C.energy(path([(12, 8), (x, y)], 0.7, 0.5), ARCANE, falloff=0.5)
        C.energy(circle(x, y, 2.6), MANA, falloff=2)
    C.energy(circle(12, 8, 4), MANA, falloff=3)
    return A, B, C


def hud_void_barrier():
    A = S("sorcerer")
    A.energy(cut(circle(7, 7, 6.4), circle(7, 7, 4.6)), VOID, falloff=0.8)
    A.energy(circle(7, 7, 1.6), ARCANE, falloff=1.2)
    B = S("sorcerer")
    B.solid(circle(7, 7, 5.8), VOID, base=2.4, spread=1.6)
    B.energy(circle(7, 7, 1.8), ARCANE, falloff=1.4)
    B.glint(5, 4)
    C = S("sorcerer")
    C.energy(cut(heart(7, 7.5, 5), heart(7, 7.3, 3.2)), VOID, falloff=0.8)
    C.energy(heart(7, 7.3, 2.8), ARCANE, falloff=1.4)
    return A, B, C


def hud_arcane_feedback():
    A = S("sorcerer")
    spark(A, 7, 7, 5, ARCANE)
    B = S("sorcerer")
    B.energy(path(zig(2, 2, 12, 12, 4, 1.4, 3), 1.0, 0.5), ARCANE, falloff=0.7)
    C = S("sorcerer")
    C.energy(star(7, 7, 6, 2.4, 4, -90), ARCANE, falloff=1.4)
    return A, B, C


# ================================================================ Rogue: Winddancer
ALLY = R("0a1410", "182a22", "2a4638", "426a54", "6a9478", "a0c8aa")


def rog_protective_gale():
    A = G("rogue", (12, 12))
    for k, (x, y, s) in enumerate(((7, 13, 0.55), (17, 13, 0.55), (12, 11, 0.65))):
        figure(A, x, y, s, ALLY, seed=k)
    swirl(A, 12, 13, 10.5, 9.5, 160, 0.9, 0.3, 1.1, BREEZE)
    A.energy(path(arc_pts(12, 13, 10.5, -20, 60), 0.3, 1.0), BREEZE, falloff=0.5)
    B = G("rogue", (12, 12))
    swirl(B, 12, 12, 10.5, 1.5, 200, -1.5, 0.3, 1.4, BREEZE)
    for k, (x, y) in enumerate(((5, 5), (19, 7), (6, 19))):
        B.energy(ellipse(x, y, 1.6, 0.8, 30 + k * 50), BREEZE, falloff=0.8)
    C = G("rogue", (12, 12))
    for k in range(3):
        a = k * 120
        C.energy(path(spiral_pts(12, 12, 10, 2.5, a, -0.4, 10), 1.2, 0.3), BREEZE, falloff=0.7)
    C.energy(circle(12, 12, 2.2), BREEZE, falloff=1.6)
    return A, B, C


def rog_second_wind():
    A = G("rogue", (14, 8))
    figure(A, 17, 12, 0.8, ALLY)
    for k, y in enumerate((8, 12, 16)):
        line(A, 1, y + 1, 11, y, 0.7, BREEZE, seed=k)
    plus(A, 5, 5, 2.4, LIFE)
    B = G("rogue", (12, 12))
    gust(B, 1, 16, 14, 12, 0.9, 1.4, BREEZE)
    gust(B, 3, 8, 13, 5, 0.7, 1.0, BREEZE)
    plus(B, 18, 16, 3.4, LIFE, 0.9)
    C = G("rogue", (12, 12))
    swirl(C, 12, 12, 10, 3.5, 90, -1.0, 0.3, 1.2, BREEZE)
    plus(C, 12, 12, 3.2, LIFE, 1.0)
    return A, B, C


def rog_pg_lasting_gale():
    A = G("rogue", (16, 8))
    A.energy(path([(1, 22), (4, 19), (6, 15), (9, 13), (12, 12)], 0.3, 1.4), BREEZE, falloff=0.8)
    swirl(A, 16, 8, 6.5, 1, 180, -1.2, 0.4, 1.2, BREEZE)
    B = G("rogue", (10, 10))
    swirl(B, 9, 9, 8, 1.5, 180, -1.2, 0.3, 1.2, BREEZE)
    hourglass(B, 18, 16, 0.6, frame=WOOD, sand=BREEZE, t=0.3)
    C = G("rogue", (12, 12))
    for k in range(4):
        C.energy(path(arc_pts(12, 12, 3 + k * 2.4, 180 + k * 40, 420 + k * 40), 0.3 + k * 0.1), BREEZE, falloff=0.5)
    return A, B, C


def rog_pg_tailwind():
    A = G("rogue", (14, 8))
    boot(A, 14, 12, 0.85, LEATHER, wing=BREEZE)
    for k, y in enumerate((16, 20)):
        line(A, 0, y, 7, y, 0.6, BREEZE, seed=k)
    B = G("rogue", (14, 10))
    boot(B, 14, 10, 0.72, LEATHER)
    for k, y in enumerate((7, 12, 17)):
        gust(B, 0, y, 6 + k, y, 0.6, 1.0, BREEZE)
    swirl(B, 15, 19, 5, 1.5, 180, -0.9, 0.3, 1.0, BREEZE)
    C = G("rogue", (12, 12))
    for k, (y, x0, x1) in enumerate(((4, 3, 14), (8, 1, 19), (12, 0, 22), (16, 2, 18), (20, 5, 13))):
        line(C, x0, y, x1, y, 0.7 if k == 2 else 0.5, BREEZE, seed=k)
    C.energy(poly([(17, 9), (22.5, 12.5), (17, 16)]), BREEZE, falloff=0.8)
    return A, B, C


def rog_sw_lingering_breeze():
    A = G("rogue", (10, 10))
    for k, y in enumerate((7, 13, 19)):
        A.energy(path([(1 + k, y), (7, y - 1.6), (13, y), (19, y - 1.6), (23, y)], 0.3, 0.9), BREEZE, falloff=0.5)
    for k, (x, y) in enumerate(((6, 4), (16, 10), (9, 16), (19, 20))):
        plus(A, x, y, 1.4, LIFE, 0.5)
    B = G("rogue", (12, 12))
    swirl(B, 12, 13, 9, 4, 180, -0.8, 0.3, 1.0, BREEZE)
    for k, (x, y, r) in enumerate(((12, 12, 2.0), (6, 7, 1.0), (18, 8, 1.2), (8, 18, 0.8), (17, 18, 1.0))):
        B.glow(x, y, r * 3, "5ad05a", 0.6)
        B.energy(circle(x, y, r), LIFE, falloff=r)
    C = G("rogue", (12, 12))
    plus(C, 12, 12, 6, LIFE, 1.8)
    C.energy(path(arc_pts(12, 12, 9.5, 200, 340), 0.3, 1.0), BREEZE, falloff=0.5)
    C.energy(path(arc_pts(12, 12, 9.5, 20, 160), 0.3, 1.0), BREEZE, falloff=0.5)
    return A, B, C


def rog_sw_shared_breath():
    A = G("rogue", (6, 12))
    for k, (x, y) in enumerate(((19, 6), (19, 18))):
        A.energy(path([(2, 12), (8, 12), (13, (12 + y) / 2), (16, y)], 1.2, 0.5), BREEZE, falloff=0.7)
        figure(A, x + 1.5, y + 1, 0.5, ALLY, seed=k)
    B = G("rogue", (12, 12))
    gust(B, 1, 12, 9, 12, 0.0, 1.6, BREEZE)
    for k, y in enumerate((5, 19)):
        gust(B, 9, 12, 18, y, 0.8, 1.1, BREEZE)
    C = G("rogue", (12, 14))
    hand_open(C, 12, 17, 0.75, SKIN)
    for k, x in enumerate((4, 20)):
        C.energy(path([(12, 9), (12 + (x - 12) * 0.4, 6), (x, 4)], 0.9, 0.4), BREEZE, falloff=0.6)
        plus(C, x, 4, 1.6, LIFE, 0.6)
    return A, B, C


def hud_protective_gale():
    A = S("rogue")
    swirl(A, 7, 7, 6, 1, 180, -1.2, 0.3, 1.0, BREEZE)
    B = S("rogue")
    figure(B, 7, 7, 0.45, ALLY)
    B.energy(path(arc_pts(7, 7, 5.6, 150, 420), 0.3, 0.8), BREEZE, falloff=0.5)
    C = S("rogue")
    for k in range(3):
        C.energy(path(spiral_pts(7, 7, 6, 1.5, k * 120, -0.4, 8), 0.9, 0.3), BREEZE, falloff=0.5)
    return A, B, C


def hud_lingering_breeze():
    A = S("rogue")
    plus(A, 7, 7, 4.4, LIFE, 1.3)
    B = S("rogue")
    for k, y in enumerate((4, 10)):
        B.energy(path([(1, y), (5, y - 1.3), (9, y), (13, y - 1.3)], 0.3, 0.7), BREEZE, falloff=0.4)
    plus(B, 7, 7, 2.2, LIFE, 0.6)
    C = S("rogue")
    swirl(C, 7, 7, 6, 2.5, 180, -0.8, 0.3, 0.8, BREEZE)
    plus(C, 7, 7, 2.4, LIFE, 0.7)
    return A, B, C


# ================================================================ Warrior: Bannerlord
def war_battlefield_standard():
    A = G("warrior", (12, 8))
    banner(A, 4.5, 1, 24, 1.45, wave=0.4, seed=1)
    B = G("warrior", (14, 6))
    B.rays(14, 8, HOLY, n=9, hi=3)
    banner(B, 6, 2, 22, 1.2, wave=1.2, seed=2)
    B.solid(ellipse(6, 22, 4.5, 1.2), EARTH, base=2.0)
    # the crest close up: the shield on red cloth
    C = G("warrior", (8, 6))
    C.solid(box(12, 12, 13, 13), CLOTH, base=2.6, light=(-0.6, -0.8))
    for k in range(3):
        C.shade(box(3 + k * 9, 12, 1.0, 13), 0.7)
    shield(C, 12, 11, 0.95, GOLD, face=CLOTH, boss=GOLD, kite=True)
    return A, B, C


def war_righteous_crusade():
    A = G("warrior", (12, 8))
    banner(A, 4.5, 1, 24, 1.45, wave=0.4, seed=3, emblem="sun")
    B = G("warrior", (15, 9))
    sun(B, 15, 9, 3.6, HOLY, 12)
    banner(B, 5, 3, 24, 1.1, wave=0.8, seed=4)
    C = G("warrior", (12, 12))
    sun(C, 10, 10, 4.2, HOLY, 10)
    hourglass(C, 18, 16, 0.55, frame=WOOD, sand=HOLY, t=0.6)
    return A, B, C


def war_bs_feared_crest():
    A = G("warrior", (8, 6))
    cx, cy = banner(A, 3, 1, 24, 1.15, wave=0.4, seed=5)
    foe(A, 18, 20, 0.6, seed=1)
    for d in (-1, 1):
        A.energy(seg(cx + d * 0.5, cy - 0.3, cx + d * 2.3, cy - 1.3, 0.55, 0.3), R("ff8a2a", "ffd070", "ffffff"), falloff=0.3)
    # the shield crest with glaring eyes over a cringing foe
    B = G("warrior", (12, 6))
    shield(B, 12, 9, 0.85, GOLD, face=CLOTH, boss=None, kite=True)
    for d in (-1, 1):
        B.energy(seg(12 + d * 0.8, 7.8, 12 + d * 3.8, 6.2, 0.7, 0.35), R("ff8a2a", "ffd070", "ffffff"), falloff=0.4)
    foe(B, 12, 21, 0.55, seed=2)
    # a cowering foe with a cracked-armour mark (vulnerability)
    C = G("warrior", (12, 8))
    C.rays(12, 3, GOLD, n=7, hi=3)
    foe(C, 12, 15, 0.95, seed=3)
    C.energy(path(zig(8, 13, 16, 20, 4, 1.4, 2), 0.6), CRIMSON, falloff=0.5)
    return A, B, C


def war_bs_martyrs_banner():
    A = G("warrior", (10, 6))
    banner(A, 4, 1, 15, 0.85, wave=0.6, seed=6)
    for k, x in enumerate((9, 15, 21)):
        figure(A, x, 18, 0.55, R("100c08", "241a10", "3e2e1c", "5e4630", "86684a", "b09068"), seed=k)
    for k, (x, y) in enumerate(((4, 18), (5.5, 21.5))):
        A.energy(drop(x, y, 1.1), BLOOD, falloff=1.0)
    B = G("warrior", (12, 6))
    banner(B, 6, 1, 24, 1.3, wave=0.6, seed=7)
    for k, (x, y, r) in enumerate(((14, 18, 1.8), (19, 15, 1.3), (11, 22, 1.2))):
        B.energy(drop(x, y, r), BLOOD, falloff=r)
    C = G("warrior", (12, 8))
    C.energy(heart(12, 12, 7), BLOOD, falloff=3)
    C.solid(box(12, 12, 0.8, 11), WOOD, base=2.4)
    C.solid(poly([(12.8, 3), (21, 4), (18.6, 7.5), (21, 11), (12.8, 10.5)]), CLOTH, base=3)
    return A, B, C


def war_rc_war_drum():
    A = G("warrior", (12, 8))
    for k, r in enumerate((8.5, 11)):
        A.energy(path(arc_pts(12, 10, r, 195, 345), 0.5), R("6a4a10", "b08a20", "e8c850", "fff0a0"), falloff=0.4)
    drumkit(A, 12, 13, 1.25, seed=1)
    B = G("warrior", (12, 8))
    drumkit(B, 12, 14, 1.0, seed=2)
    for k in range(3):
        B.energy(ring(12, 14, 9 + k * 2.4, 0.4), R("2a1a04", "6a4a10", "b08a20", "e8c850"), falloff=0.3)
    B.solid(seg(4, 2, 10, 9, 0.9), WOOD, base=3.0)
    B.solid(circle(4, 2, 1.6), BONE, base=3.4)
    # a drum's hit landing on a foe: the foe shrinking under the rings
    C = G("warrior", (12, 8))
    foe(C, 12, 16, 0.9, seed=4)
    for k, r in enumerate((4, 6.5, 9)):
        C.energy(path(arc_pts(12, 2, r, 30, 150), 0.5), R("6a4a10", "b08a20", "e8c850", "fff0a0"), falloff=0.4)
    C.energy(path([(18, 8), (18, 14)], 0.8), CRIMSON, falloff=0.5)
    C.energy(poly([(15.8, 13), (20.2, 13), (18, 16.5)]), CRIMSON, falloff=0.8)
    return A, B, C


def war_rc_shared_provisions():
    A = G("warrior", (10, 8))
    sack(A, 10, 14, 1.2, seed=1)
    hourglass(A, 18.5, 9, 0.62, frame=WOOD, sand=GOLD, t=0.4)
    B = G("warrior", (12, 8))
    sack(B, 12, 14, 1.25, seed=2)
    for k, (x, y) in enumerate(((3, 7), (21, 7))):
        B.energy(path([(12, 5), (x, y)], 0.5), GOLD, falloff=0.4)
        B.energy(circle(x, y, 1.6), GOLD, falloff=1.2)
    C = G("warrior", (12, 12))
    hourglass(C, 12, 12, 1.05, frame=WOOD, sand=GOLD, t=0.6)
    C.energy(path(arc_pts(12, 12, 10, 200, 330), 0.3, 1.0), GOLD, falloff=0.5)
    C.energy(poly([(19.5, 4.5), (21.5, 9.5), (16.4, 8.4)]), GOLD, falloff=0.6)
    return A, B, C


def mini_banner(ic, x, top, bottom, s, wave=0.4, planted=False):
    banner(ic, x, top, bottom, s, wave=wave, seed=1)
    if planted:
        ic.solid(ellipse(x, bottom - 0.5, 3.6, 1.0), EARTH, base=2.2)


def hud_standard_raised():
    A = S("warrior")
    mini_banner(A, 3, 0, 14, 0.85)
    B = S("warrior")
    mini_banner(B, 3, 0, 14, 0.85)
    B.glow(7, 6, 6, "ffe070", 0.5)
    C = S("warrior")
    shield(C, 7, 6.5, 0.6, GOLD, face=CLOTH, boss=None)
    return A, B, C


def hud_standard_planted():
    A = S("warrior")
    mini_banner(A, 3, 0, 13, 0.85, planted=True)
    B = S("warrior")
    mini_banner(B, 3, 0, 13, 0.85, planted=True)
    for k, y in enumerate((4, 7)):
        B.energy(poly([(10, y + 2.6), (12.5, y), (15, y + 2.6)]), GOLD, falloff=0.5)
    C = S("warrior")
    shield(C, 7, 6, 0.55, GOLD, face=CLOTH, boss=None)
    C.solid(ellipse(7, 12.6, 6.0, 1.2), EARTH, base=2.0)
    return A, B, C


def hud_shared_provisions():
    A = S("warrior")
    sack(A, 7, 7.5, 0.95)
    B = S("warrior")
    hourglass(B, 7, 7, 0.8, frame=WOOD, sand=GOLD, t=0.45)
    C = S("warrior")
    sack(C, 6, 8, 0.75)
    C.energy(path(arc_pts(7, 7, 5.8, 200, 330), 0.25, 0.7), GOLD, falloff=0.4)
    return A, B, C


# ================================================================ Warlock: Branding
def brand_iron(ic, x0, y0, x1, y1, s=1.0, seed=0):
    ic.solid(seg(x0, y0, x1, y1, 0.8 * s), GUN, seed=seed, base=2.6)
    ic.solid(seg(x0, y0, x0 + (x1 - x0) * 0.28, y0 + (y1 - y0) * 0.28, 1.2 * s), WOOD, seed=seed + 1, base=2.6)


def wlk_pyrebrand():
    A = G("warlock", (12, 8))
    foe(A, 12, 15, 1.1, seed=1)
    A.glow(12, 15, 8, "ff8a2a", 0.6)
    sigil(A, 12, 15, 4.0, w=0.45)
    B = G("warlock", (12, 12))
    B.glow(12, 12, 12, "e04a10", 0.6)
    sigil(B, 12, 12, 7.0, w=0.7, fall=0.7)
    # a branding iron searing the sigil into a hide
    C = G("warlock", (12, 8))
    C.solid(box(12, 19, 13, 6), FLESH, base=2.0, light=(-0.4, -1))
    sigil(C, 9, 18, 3.6, w=0.45, spokes=False)
    brand_iron(C, 22, 2, 12, 13)
    C.energy(circle(12, 13.5, 2.6), HELL, falloff=1.6)
    return A, B, C


def wlk_essence_extraction():
    A = G("warlock", (10, 8))
    foe(A, 8, 15, 0.85, seed=2)
    sigil(A, 8, 15, 3.0, w=0.35, spokes=False)
    dagger(A, 16, 16, -45, 0.8, CRIMSON)
    wisp(A, 16, 6, 2.6, ESS, -60, 1)
    B = G("warlock", (12, 10))
    dagger(B, 12, 15, -90, 1.0, STEEL)
    B.energy(path([(12, 7), (10, 4), (13, 2), (11, 0)], 1.0, 0.4), ESS, falloff=0.6)
    for k, (x, y) in enumerate(((7, 4), (17, 6))):
        B.energy(circle(x, y, 1.1), ESS, falloff=1)
    C = G("warlock", (12, 12))
    sigil(C, 12, 14, 6.0, w=0.5)
    wisp(C, 12, 6, 3.2, ESS, -90, 2)
    return A, B, C


def wlk_pb_combustion():
    A = G("warlock", (12, 14))
    A.glow(12, 18, 12, "e04a10", 0.6)
    claw(A, 12, 21, 1.2, seed=1)
    for k, (x, y) in enumerate(((4, 6), (20, 5), (6, 14), (19, 14))):
        A.energy(circle(x, y, 1.6), ESS, falloff=1.4)
    B = G("warlock", (12, 12))
    claw(B, 12, 22, 1.0, seed=2)
    for k, (x, y) in enumerate(((4, 4), (20, 4))):
        B.energy(path([(x, y), ((x + 12) / 2, 9), (12, 12)], 0.4, 0.9), ESS, falloff=0.6)
        B.energy(circle(x, y, 2.2), ESS, falloff=1.8)
    C = G("warlock", (12, 12))
    sigil(C, 12, 12, 7.5, w=0.5)
    claw(C, 12, 18, 0.8, seed=3)
    return A, B, C


def wlk_pb_proliferation():
    A = G("warlock", (12, 6))
    for k, (x, y) in enumerate(((5, 18), (19, 18))):
        foe(A, x, y, 0.55, seed=k)
        sigil(A, x, y - 1, 2.2, w=0.3, spokes=False)
        A.energy(path([(12, 7), (x, y - 5)], 0.4), HELL, falloff=0.4)
    sigil(A, 12, 6, 3.8, w=0.4)
    B = G("warlock", (12, 12))
    sigil(B, 12, 12, 5, w=0.5)
    for k, (x, y) in enumerate(((4, 4), (20, 4), (4, 20), (20, 20))):
        sigil(B, x, y, 2.0, w=0.3, spokes=False)
    C = G("warlock", (12, 12))
    for k, (x, y, r) in enumerate(((7, 8, 4.2), (17, 9, 3.4), (12, 18, 3.6))):
        sigil(C, x, y, r, w=0.4, spokes=False)
    return A, B, C


def wlk_ee_essence_empowerment():
    A = G("warlock", (12, 12))
    A.energy(flame(12, 23, 6, 22, 0.0, 2, 3), HELL, falloff=2.5)
    sword(A, 12, 13, -90, 1.0, STEEL)
    for k, (x, y) in enumerate(((4, 9), (20, 13))):
        A.energy(circle(x, y, 1.6), ESS, falloff=1.4)
    B = G("warlock", (12, 12))
    B.energy(flame(14, 22, 7, 20, 0.4, 4, 3), HELL, falloff=2.5)
    dagger(B, 12, 13, -45, 1.1, STEEL)
    wisp(B, 5, 18, 2.4, ESS, 30, 2)
    C = G("warlock", (12, 14))
    C.energy(flame(12, 22, 8, 21, 0, 5, 3), ESS, falloff=2.5)
    C.energy(flame(12, 22, 5, 15, 0, 6, 2), HELL, falloff=2.0)
    return A, B, C


def wlk_ee_released_essence():
    A = G("warlock", (12, 14))
    skull(A, 12, 14, 0.95, BONE, eyes=ESS)
    for k, (x, y, a) in enumerate(((4, 6, -120), (12, 3, -90), (20, 6, -60))):
        wisp(A, x, y, 1.8, ESS, a, k)
    B = G("warlock", (12, 12))
    B.rays(12, 14, ESS, n=8, hi=4)
    foe(B, 12, 16, 1.0, seed=5)
    for k, (x, y, a) in enumerate(((3, 6, -135), (21, 6, -45), (12, 2, -90))):
        wisp(B, x, y, 1.6, ESS, a, k)
    C = G("warlock", (12, 12))
    for k in range(6):
        a = k * 60 - 90
        r = math.radians(a)
        wisp(C, 12 + math.cos(r) * 7, 12 + math.sin(r) * 7, 1.7, ESS, a, k)
    C.energy(circle(12, 12, 2.6), ESS, falloff=2)
    return A, B, C


def hud_pyrebrand():
    A = S("warlock")
    sigil(A, 7, 7, 4.2, w=0.4, spokes=False)
    B = S("warlock")
    sigil(B, 7, 7.5, 3.4, w=0.35)
    C = S("warlock")
    C.glow(7, 7, 7, "e04a10", 0.6)
    C.energy(poly([(2, 3), (12, 3), (7, 12)]), HELL, falloff=1.2)
    return A, B, C


# ================================================================ the list, the runner
SPECS = [  # (spec key, title, [(name, what it is)]) from art/specs/REQUESTS.md
    ("ranger", "Ranger: Deadeye", [
        ("ran_electric_circuit", "Active. A V of three arrows crackling with lightning, flying out and curving back like a boomerang."),
        ("ran_gathering_winds", "Passive. Wind gusting around a drawn bow; speed lines."),
        ("ran_ec_boomerang", "Orb Boomerang: the returning arrow, brighter and charged, curved path."),
        ("ran_ec_lightning_rod", "Orb Storm Arrow: an arrow calling several lightning bolts down around it."),
        ("ran_ec_tailwind_catch", "Orb Tailwind Catch: a hand catching a returning arrow, wind swirl."),
        ("ran_gw_gale_force", "Orb Gale Force: extra arrows fanning out of a gust."),
        ("ran_gw_wind_ward", "Orb Wind Ward: a ring of wind deflecting a hit."),
        ("hud_tailwind", "Status Tailwind (stacking speed): a small swirl of wind."),
    ]),
    ("wizard", "Wizard: Aerotheurge", [
        ("wiz_tempest_torrent", "Active. A slow ball of lightning lashing out at targets with forked bolts."),
        ("wiz_static_charge", "Passive. Static sparks gathering on fingertips."),
        ("wiz_tt_overcharge", "Orb Focal Point: one bolt hitting the same point again and again, intensifying."),
        ("wiz_tt_lingering_storm", "Orb Lingering Storm: the lightning orb with an hourglass / long trailing tail."),
        ("wiz_tt_thunderclap", "Orb Thunderclap: the orb bursting in a ring of lightning."),
        ("wiz_tt_lightning_rod", "Orb Lightning Rod (new): Tempest Orb zaps more enemies per tick and has increased range."),
        ("wiz_sc_static_channel", "Orb Charged Font: a spark turning into blue mana."),
        ("wiz_sc_conduit", "Orb Conduit: a charged hand with speed lines (faster casting)."),
        ("hud_static_charge", "Status Static Charge (stacks to 5): a tiny spark."),
    ]),
    ("sorcerer", "Sorcerer: Arcane", [
        ("sor_blink", "Active. A figure vanishing in a violet arcane flash and reappearing; afterimage."),
        ("sor_living_mana", "Passive. A heart filled with blue-violet mana instead of blood."),
        ("sor_bl_void_barrier", "Orb Void Barrier: a dark violet shell around a blinking figure."),
        ("sor_bl_far_step", "Orb Far Step: a long blink trail, footsteps far apart."),
        ("sor_lm_arcane_feedback", "Orb Arcane Feedback: a hit turning into arcane power (a crack spilling violet energy)."),
        ("sor_lm_mana_conduit", "Orb Mana Conduit: mana flowing out to two allies."),
        ("hud_void_barrier", "Status Void Barrier (cannot die for 1 s)."),
        ("hud_arcane_feedback", "Status Arcane Feedback (next spell empowered)."),
    ]),
    ("rogue", "Rogue: Winddancer", [
        ("rog_protective_gale", "Active. A swirling gale wrapped around several allies; pale green-white wind."),
        ("rog_second_wind", "Passive. A dodge leaving behind a green healing gust."),
        ("rog_pg_lasting_gale", "Orb Lasting Gale: the gale with a long, lingering tail."),
        ("rog_pg_tailwind", "Orb Tailwind (movement speed): wind at running feet."),
        ("rog_sw_lingering_breeze", "Orb Lingering Breeze: a soft green breeze with small healing motes."),
        ("rog_sw_shared_breath", "Orb Shared Breath: one gust splitting to two allies."),
        ("hud_protective_gale", "Status Protective Gale (evasion up)."),
        ("hud_lingering_breeze", "Status Lingering Breeze (health regeneration)."),
    ]),
    ("warrior", "Warrior: Bannerlord", [
        ("war_battlefield_standard", "Active. A war banner held high, a shield crest on the cloth."),
        ("war_righteous_crusade", "Passive. A banner with a sunburst (buffs last longer)."),
        ("war_bs_feared_crest", "Orb Feared Crest: the banner's crest glaring, a cowering enemy (Vulnerability)."),
        ("war_bs_martyrs_banner", "Orb Martyr's Banner: the banner over allies, the bearer bleeding."),
        ("war_rc_war_drum", "Orb War Drum: a war drum with shock rings (Weakness on enemies)."),
        ("war_rc_shared_provisions", "Orb Shared Provisions: a supply sack and an hourglass (cooldowns)."),
        ("hud_standard_raised", "Status Battlefield Standard, carried (damage reduction)."),
        ("hud_standard_planted", "Status Battlefield Standard, planted (double damage reduction)."),
        ("hud_shared_provisions", "Status Shared Provisions (cooldown reduction)."),
    ]),
    ("warlock", "Warlock: Branding", [
        ("wlk_pyrebrand", "Active. A burning demonic sigil seared onto an enemy."),
        ("wlk_essence_extraction", "Passive. A dagger drawing a wisp of essence out of a branded foe."),
        ("wlk_pb_combustion", "Orb Combustion: the hellfire claw erupting, fed by essence orbs."),
        ("wlk_pb_proliferation", "Orb Proliferation: the sigil splitting onto several enemies."),
        ("wlk_ee_essence_empowerment", "Orb Essence Empowerment: a weapon wreathed in fire fed by essence."),
        ("wlk_ee_released_essence", "Orb Released Essence: a slain elite bursting into essence wisps."),
        ("hud_pyrebrand", "Status Pyrebrand on an enemy: the branded sigil, small."),
    ]),
]
ALL = {n: (key, title, desc) for key, title, items in SPECS for n, desc in items}


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    for key, title, items in SPECS:
        rows = [(n, out[n]) for n, _ in items if n in out]
        if rows:
            sheet(rows, OUT / f"sheet_{key}.png")
    return out


def uri(im):
    import base64
    import io
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


NAMES = {  # actives renamed since their icon names were given (the ids and icon slots stay)
    "ran_electric_circuit": "Lightning Arrow", "wiz_tempest_torrent": "Thunder Orb",
}


def label(n, desc):
    """The card title: "Lightning Arrow (active)", "Boomerang (orb)", "Tailwind (status)"."""
    for kind in ("Active", "Passive"):
        if desc.startswith(kind + "."):
            return NAMES.get(n, n.split("_", 1)[1].replace("_", " ").title()) + f" ({kind.lower()})"
    kind, rest = desc.split(" ", 1)
    for stop in (":", " (", "."):
        rest = rest.split(stop)[0]
    return f"{rest} ({kind.lower()})"


def picker():
    groups = []
    for key, title, items in SPECS:
        its = []
        for n, desc in items:
            if n.startswith("hud_"):
                desc += " A 14x14 buff-bar icon, shown at its size."
            its.append({"id": "specs." + n, "name": label(n, desc), "key": n, "desc": desc,
                        "imgs": {k: uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}})
        groups.append({"id": "specs." + key, "title": title, "items": its})
    tpl = (HERE / "picker_tpl.html").read_text(encoding="utf-8")
    assert "/*DATA*/null" in tpl
    page = OUT / "picker.html"
    tpl = tpl.replace("Skill Icon Picks", "Spec Icon Picks")   # the published page's name, apart from the vanilla picker's
    page.write_text(tpl.replace("/*DATA*/null", json.dumps(groups)), encoding="utf-8")
    return page


def pick(fn):
    """Copy the chosen idea of each icon to art/specs/override/<name>.png, at its size."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    OVR.mkdir(parents=True, exist_ok=True)
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specs.") else k
        c = v.get("choice") if isinstance(v, dict) else v
        if n not in ALL or c not in ("a", "b", "c"):
            print("skip", k, c)
            continue
        im = Image.open(OUT / f"{n}_{c}.png").convert("RGBA")
        assert im.size == ((14, 14) if n.startswith("hud_") else (24, 24)), (n, im.size)
        im.save(OVR / f"{n}.png")
        print("wrote", OVR / f"{n}.png", c)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--pick"]:
        pick(a[1])
    else:
        names = [x for x in a if not x.startswith("--")] or list(ALL)
        render(names)
        if "--picker" in a:
            print(picker())
