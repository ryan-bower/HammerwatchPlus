"""The Paladin's Generosity icons, round 3: three ideas each for the seven icons the user noted in
round 2 (the picker's specsPal.<name>, 2026-10-27). Holy Sacrifice was settled in round 2 (C) and
goes to art/specs/override/ with --finals. The round-2 pick is beside each as "now".

    python tools/icon_art/sp_pal3.py [names...]   # out/specs/pal3/<name>_<a|b|c>.png, out/specs/pal3/sheet_paladin.png
    python tools/icon_art/sp_pal3.py --picker     # also out/specs/pal3/picker.html, ids specsPal3.<name>
    python tools/icon_art/sp_pal3.py --finals     # the settled round-2 picks to art/specs/override/
    python tools/icon_art/sp_pal3.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                  # {"specsPal3.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
from vm import hand_open, sun, star
import sp
from sp_pal import (SUNR, BEAM, SCALE_R, SCALE_B, ROBE, rays, elder, shadow_foe, pips)

OUT = sp.HERE / "out" / "specs" / "pal3"
R2 = sp.HERE / "out" / "specs" / "pal"
# Round 2: the base each icon here builds on (None: no pick, a new take on the note), and the note.
BASE = {"pal_class": ("c", "more sun with sun rays like"),
        "pal_pelors_fury": ("a", "this but thicker beam, more zoomed in generally"),
        "pal_pelors_blessing": ("a", "staff should be more stafflike"),
        "pal_pf_blinding_sun": (None, "hand in bottom left shielding away the bright sun"),
        "pal_pb_display_of_generosity": ("a", "but put the pelors blessing over each of their heads"),
        "pal_pb_descendent_of_pentival": (None, "more dragony"),
        "hud_pelors_blessing": ("b", "more sun with sun rays like")}
FINALS = {"pal_pf_holy_sacrifice": "c"}

STAFF = R("140c04", "2e1c0a", "4e3016", "704824", "946436", "b8864e")   # an old oak staff
DRAG_R = R("120302", "360806", "641008", "9a1e0c", "d03e18", "ff7a3a")
HORN = R("1a140c", "3e3424", "6a5c44", "9c8e70", "cec2a2", "f4ecd8")


# ---------------------------------------------------------------- shapes
def spikes(ic, cx, cy, r0, r1, n, half=9.0, rmp=SUNR, a0=-90, fall=0.9):
    """A sun's rays as pointed wedges: n triangles from the disc's edge out to r1."""
    for k in range(n):
        a = a0 + k * 360 / n
        p = [(cx + math.cos(math.radians(a + d)) * r0, cy + math.sin(math.radians(a + d)) * r0) for d in (-half, half)]
        tip = (cx + math.cos(math.radians(a)) * r1, cy + math.sin(math.radians(a)) * r1)
        ic.energy(poly([p[0], tip, p[1]]), rmp, falloff=fall)


def big_sun(ic, cx, cy, r, long_=2.3, short=1.6, n=8, rmp=SUNR, face=True, half=11.0):
    """Pelor's sun with real rays: n long wedges and n short ones between, a glow, the disc and
    (face=True) the calm face."""
    ic.glow(cx, cy, r * (long_ + 0.6), rmp[4], 0.55)
    spikes(ic, cx, cy, r * 0.9, r * short, n, half, rmp, a0=-90 + 180 / n, fall=0.7)
    spikes(ic, cx, cy, r * 0.9, r * long_, n, half * 0.9, rmp, fall=1.0)
    ic.energy(circle(cx, cy, r), rmp, falloff=r * 0.75)
    if face:
        dark = lambda x, y, d: (120, 60, 8)
        ic.paint(union(arc(cx - r * 0.38, cy - r * 0.05, r * 0.2, r * 0.12, 200, 340),
                       arc(cx + r * 0.38, cy - r * 0.05, r * 0.2, r * 0.12, 200, 340),
                       arc(cx, cy + r * 0.2, r * 0.36, r * 0.12, 30, 150)), dark)


def staff(ic, x0, y0, x1, y1, w=0.75, seed=0, finial=True):
    """An old oak staff from its foot (x0, y0) to its head (x1, y1): a knotted pole, two gold
    bands below the head and a gold ring cradling a sun orb on top."""
    ic.solid(seg(x0, y0, x1, y1, w * 0.85, w), STAFF, seed=seed, base=2.6)
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    for t in (0.42, 0.7):   # knots
        ic.solid(circle(x0 + dx * t, y0 + dy * t, w * 1.05), STAFF, seed=seed + 1, base=3.0)
    for k in (1.6, 2.6):     # gold bands
        bx, by = x1 - ux * k, y1 - uy * k
        ic.solid(seg(bx - uy * w * 1.2, by + ux * w * 1.2, bx + uy * w * 1.2, by - ux * w * 1.2, 0.45), GOLD, seed=seed + 2, base=3.4)
    if finial:
        cx, cy = x1 + ux * 1.6, y1 + uy * 1.6
        ic.solid(arc(cx, cy, 1.9, 0.7, 0, 360), GOLD, seed=seed + 3, base=3.0)
        ic.glow(cx, cy, 5.0, "ffd860", 0.7)
        ic.energy(circle(cx, cy, 1.3), SUNR, falloff=1.2)
        rays(ic, cx, cy, 2.6, 4.2, 8, SUNR, 0.32, fall=0.3)


def rot(f, cx, cy, ang):
    """The sdf f turned ang degrees round (cx, cy)."""
    a = math.radians(-ang)
    ca, sa = math.cos(a), math.sin(a)
    return lambda x, y: f(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca)


def dragon_head(ic, cx, cy, s=1.0, ang=0, rmp=DRAG_R, seed=0, open_=0.0, eye=SUNR):
    """A dragon's head in profile facing right (ang turns it): a long snout, a jaw (open_ drops it,
    showing teeth), two horns swept back, spines down a slim neck and a glowing eye. (cx, cy) the
    back of the skull. Returns the snout's tip."""
    a = math.radians(ang)
    P = lambda x, y: (cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a))
    T = lambda f: rot(f, cx, cy, ang)
    j = open_ * 1.8 * s
    neck = seg(cx - 1.0 * s, cy + 1.0 * s, cx - 3.4 * s, cy + 11 * s, 1.9 * s, 2.6 * s)
    spines = union(*[poly([(cx - (2.6 + t * 2.4) * s, cy + (0.6 + t * 8) * s), (cx - (5.2 + t * 2.4) * s, cy + (1.0 + t * 8) * s),
                           (cx - (3.0 + t * 2.4) * s, cy + (2.4 + t * 8) * s)]) for t in (0.0, 0.3, 0.6)])
    ic.solid(T(spines), rmp, seed=seed + 1, base=3.2)
    ic.solid(T(neck), rmp, seed=seed + 2, base=2.0)
    jaw = poly([(cx - 0.4 * s, cy + 1.2 * s), (cx + 7.2 * s, cy + 1.6 * s + j), (cx + 6.6 * s, cy + 2.8 * s + j),
                (cx - 0.6 * s, cy + 3.4 * s)])
    ic.solid(T(jaw), rmp, seed=seed + 3, base=2.4)
    head = union(ellipse(cx, cy, 3.3 * s, 2.7 * s),
                 poly([(cx + 0.8 * s, cy - 2.4 * s), (cx + 7.4 * s, cy - 1.0 * s), (cx + 8.6 * s, cy + 0.1 * s),
                       (cx + 8.2 * s, cy + 1.2 * s), (cx + 0.8 * s, cy + 1.6 * s)]))
    ic.solid(T(head), rmp, seed=seed + 4, base=3.0)
    horns = union(seg(cx - 0.8 * s, cy - 1.8 * s, cx - 6.6 * s, cy - 4.4 * s, 1.1 * s, 0.2 * s),
                  seg(cx + 0.6 * s, cy - 2.2 * s, cx - 3.4 * s, cy - 6.8 * s, 0.9 * s, 0.15 * s))
    ic.solid(T(horns), HORN, seed=seed + 5, base=3.0)
    ic.solid(T(seg(cx + 1.0 * s, cy - 2.2 * s, cx + 5.8 * s, cy - 1.4 * s, 0.5 * s, 0.25 * s)), rmp, seed=seed + 6, base=4.2)  # brow
    if open_:
        ic.paint(T(poly([(cx + 1.6 * s, cy + 1.5 * s), (cx + 8.0 * s, cy + 1.2 * s), (cx + 7.0 * s, cy + 1.7 * s + j)])),
                 lambda x, y, d: (40, 8, 4))
        ic.px([tuple(int(v) for v in P(cx + k * s, cy + 1.7 * s)) for k in (3.4, 5.4)], (240, 232, 210))
    ic.px([tuple(int(v) for v in P(cx + 7.6 * s, cy - 0.4 * s))], (40, 8, 4))   # the nostril
    ex, ey = P(cx + 1.9 * s, cy - 1.0 * s)
    ic.energy(ellipse(ex, ey, 0.8 * s, 0.5 * s, ang), eye, falloff=0.6)
    return P(cx + 8.4 * s, cy + 1.2 * s + j * 0.5)


def wing(ic, cx, cy, d, s=1.0, rmp=DRAG_R, seed=0):
    """A dragon's bat wing from the shoulder (cx, cy) out to side d (-1 left, 1 right): the arm up
    to a clawed wrist, three long fingers fanning down, the membrane scalloped between them."""
    X = lambda x: cx + d * x * s
    wrist = (X(4.4), cy - 8.6 * s)
    tips = [(X(11.4), cy - 5.0 * s), (X(10.4), cy + 2.6 * s), (X(5.6), cy + 6.4 * s)]
    mid = lambda p, q, k: (wrist[0] + ((p[0] + q[0]) / 2 - wrist[0]) * k, wrist[1] + ((p[1] + q[1]) / 2 - wrist[1]) * k)
    notch = [mid(tips[0], tips[1], 0.84), mid(tips[1], tips[2], 0.84), (X(2.4), cy + 3.6 * s)]
    mem = [(cx, cy - 1.0 * s), wrist, tips[0], notch[0], tips[1], notch[1], tips[2], notch[2], (cx, cy + 1.6 * s)]
    ic.solid(poly(mem), rmp, seed=seed, base=2.2, rim=1.2)
    bone = union(seg(cx, cy, wrist[0], wrist[1], 0.8 * s, 0.6 * s),
                 *[seg(wrist[0], wrist[1], tx, ty, 0.5 * s, 0.25 * s) for tx, ty in tips])
    ic.solid(bone, rmp, seed=seed + 1, base=4.4)
    ic.solid(seg(wrist[0], wrist[1], wrist[0] - d * 0.4 * s, wrist[1] - 1.8 * s, 0.45 * s, 0.1 * s), HORN, seed=seed + 2, base=4.0)


# ---------------------------------------------------------------- the emblem
def pal_class():
    # round 3 (round-2 C, the sun's face; the user: "more sun with sun rays like"): eight long
    # wedge rays with short ones between; sixteen thin rays reaching the edge; the face with a
    # crown of rays and a ring
    A = G("paladin", (12, 12))
    big_sun(A, 12, 12, 4.4, long_=2.55, short=1.75)
    B = G("paladin", (12, 12))
    B.glow(12, 12, 12, "ffd860", 0.6)
    rays(B, 12, 12, 5.0, 11.6, 8, SUNR, 0.7, a0=-90, fall=0.45)
    rays(B, 12, 12, 5.0, 9.2, 8, SUNR, 0.45, a0=-67.5, fall=0.35)
    big_sun(B, 12, 12, 4.4, long_=1.5, short=1.3, n=8, half=14)
    C = G("paladin", (12, 12))
    C.glow(12, 12, 12, "f0a818", 0.5)
    spikes(C, 12, 12, 7.0, 11.8, 12, 7.0, SUNR, fall=0.8)
    C.energy(ring(12, 12, 6.6, 0.8), SUNR, falloff=0.6)
    big_sun(C, 12, 12, 4.4, long_=1.45, short=1.3, n=8, half=13)
    return A, B, C


# ---------------------------------------------------------------- skills
def pal_pelors_fury():
    # round 3 (round-2 A; "thicker beam, more zoomed in generally"): the shadow fills the icon and a
    # broad pillar lands on its head; broader still, the light bursting off its horns; a white-hot
    # core in a gold beam, the shadow breaking into wisps
    A = G("paladin", (12, 4))
    shadow_foe(A, 12, 17.2, 1.42, seed=1)
    A.energy(poly([(9.0, 0), (15.0, 0), (15.8, 9.4), (8.2, 9.4)]), BEAM, falloff=2.0)
    A.energy(ellipse(12, 9.6, 5.6, 1.3), BEAM, falloff=1.0)
    A.energy(star(12, 9.4, 1.2, 6.4, 6, -90), BEAM, falloff=1.0)
    for x, y in ((3.0, 9.4), (21.0, 9.0), (2.4, 15.0), (21.6, 15.6)):
        A.energy(circle(x, y, 0.6), SUNR, falloff=0.55)
    B = G("paladin", (12, 4))
    shadow_foe(B, 12, 18.0, 1.55, seed=2)
    B.glow(12, 11, 12, "fff2b0", 0.5)
    B.energy(poly([(8.2, 0), (15.8, 0), (16.8, 9.0), (7.2, 9.0)]), BEAM, falloff=2.4)
    B.energy(star(12, 9.2, 1.4, 8.0, 8, -90), BEAM, falloff=1.1)
    for d in (-1, 1):
        B.energy(seg(12 + d * 6.6, 6.0, 12 + d * 10.6, 3.0, 0.6, 0.15), SUNR, falloff=0.45)
    C = G("paladin", (12, 4))
    shadow_foe(C, 12, 17.6, 1.4, seed=3)
    for k, (x, y) in enumerate(((4.0, 18.0), (20.0, 17.4), (5.4, 22.4), (18.8, 22.2))):
        C.energy(seg(x, y, x + (-2 if x < 12 else 2), y - 2.4, 0.5, 0.15), R("06050a", "1e182e", "3a2e54"), falloff=0.4)
    C.energy(poly([(8.2, 0), (15.8, 0), (16.6, 9.6), (7.4, 9.6)]), SUNR, falloff=1.4)
    C.energy(poly([(10.4, 0), (13.6, 0), (14.0, 9.6), (10.0, 9.6)]), BEAM, falloff=1.8)
    C.energy(ellipse(12, 9.8, 6.4, 1.5), BEAM, falloff=1.1)
    return A, B, C


def pal_pelors_blessing():
    # round 3 (round-2 A; "staff should be more stafflike"): the elder leaning on a tall oak staff
    # with a sun orb on top, his other hand raised; the staff held up high, light pouring from the
    # orb; the staff planted beside him with a shepherd's crook curling round the sun
    A = G("paladin", (18, 4))
    elder(A, 9.4, 9, 1.0, seed=1)
    staff(A, 18.6, 23.6, 18.0, 5.0, 0.8, seed=2)
    A.solid(ellipse(17.2, 13.0, 1.5, 1.2), SKIN, seed=3, base=3.0)   # his hand on the staff
    A.solid(seg(13.6, 15.8, 16.4, 13.4, 1.4, 1.1), ROBE, seed=4, base=2.6)
    B = G("paladin", (17, 4))
    B.glow(17, 4, 9, "ffd860", 0.5)
    elder(B, 9.0, 10.0, 0.95, seed=5)
    staff(B, 15.0, 23.6, 17.2, 4.4, 0.75, seed=6)
    B.solid(seg(13.4, 16.8, 15.8, 11.6, 1.4, 1.1), ROBE, seed=7, base=2.6)
    B.solid(ellipse(16.0, 10.6, 1.4, 1.2), SKIN, seed=8, base=3.0)
    B.energy(poly([(16.6, 6.6), (18.4, 6.6), (22.4, 15.0), (19.4, 15.6)]), BEAM, falloff=1.8)
    C = G("paladin", (17, 5))
    elder(C, 8.6, 9, 0.95, seed=9)
    C.solid(seg(17.2, 23.6, 17.2, 6.6, 0.7, 0.75), STAFF, seed=10, base=2.6)
    C.solid(union(arc(19.0, 6.4, 1.9, 0.75, 180, 400), seg(20.6, 5.4, 20.4, 7.6, 0.4, 0.3)), STAFF, seed=11, base=3.0)
    C.glow(19.0, 6.6, 6, "ffd860", 0.7)
    sun(C, 19.0, 6.6, 1.15, SUNR, 8)
    for k in (9.2, 10.4):
        C.solid(seg(16.2, k, 18.2, k, 0.4), GOLD, seed=12, base=3.4)
    C.solid(ellipse(16.6, 13.2, 1.4, 1.2), SKIN, seed=13, base=3.0)
    C.solid(seg(13.0, 15.6, 15.6, 13.6, 1.4, 1.1), ROBE, seed=14, base=2.6)
    return A, B, C


def pal_pf_blinding_sun():
    # round 3 ("hand in bottom left shielding away the bright sun"): a white sun top right and a
    # hand raised against it from the bottom left; the hand dark against the glare, its edges
    # lit; the hand nearer, covering the sun's edge
    A = G("paladin", (16, 7))
    big_sun(A, 16.4, 7.4, 3.6, long_=2.0, short=1.5, rmp=BEAM, face=False)
    A.solid(seg(0.0, 24.0, 5.4, 19.2, 2.0, 1.6), ROBE, seed=1, base=2.4)
    hand_open(A, 6.8, 14.6, 0.78, SKIN, seed=2)
    B = G("paladin", (16, 7))
    B.glow(16, 8, 14, "fff2b0", 0.8)
    big_sun(B, 16.0, 7.6, 3.8, long_=2.3, short=1.6, rmp=BEAM, face=False)
    B.solid(seg(0.0, 24.0, 5.6, 19.4, 2.1, 1.7), R("06050a", "141020", "2a2240"), seed=3, base=1.6, rim=1.6)
    hand_open(B, 7.0, 14.8, 0.8, R("0c0806", "241810", "4a3020", "8a5a38", "e0a070", "fff0c0"), seed=4)
    C = G("paladin", (15, 8))
    C.glow(14, 9, 13, "fff2b0", 0.6)
    big_sun(C, 15.4, 8.6, 4.2, long_=2.0, short=1.5, rmp=BEAM, face=False)
    C.solid(seg(0.0, 24.0, 6.6, 18.6, 2.2, 1.8), ROBE, seed=5, base=2.4)
    hand_open(C, 9.0, 13.8, 0.92, SKIN, seed=6)
    return A, B, C


# ---------------------------------------------------------------- Pelor's Blessing orbs
def mini_sun(ic, cx, cy, r=0.9, n=8):
    """The Blessing's buff icon over a head: a small sun with its rays."""
    ic.glow(cx, cy, r * 3.2, "ffd860", 0.7)
    ic.energy(union(circle(cx, cy, r), *[seg(cx + math.cos(k * 6.283 / n) * r, cy + math.sin(k * 6.283 / n) * r,
                                             cx + math.cos(k * 6.283 / n) * r * 2.1, cy + math.sin(k * 6.283 / n) * r * 2.1,
                                             0.35, 0.12) for k in range(n)]), SUNR, falloff=r * 1.4)


def pal_pb_display_of_generosity():
    # round 3 (round-2 A; "put the pelors blessing over each of their heads"): the hand pouring light
    # onto three allies, each with the Blessing's sun over its head; the beams ending in the suns;
    # the allies closer and bigger, the hand above them
    A = G("paladin", (12, 4))
    A.glow(12, 4, 7, "ffd860", 0.6)
    hand_open(A, 12, 3.8, 0.55, SKIN)
    for x in (4.6, 12.0, 19.4):
        A.energy(path([(12, 7.4), (x, 10.6)], 0.6, 0.35), BEAM, falloff=0.55)
    for k, x in enumerate((4.6, 12.0, 19.4)):
        figure(A, x, 18.4, 0.7, ALLY, seed=k)
        mini_sun(A, x, 10.6, 1.25)
    B = G("paladin", (12, 4))
    B.glow(12, 4, 7, "ffd860", 0.6)
    hand_open(B, 12, 4.0, 0.55, SKIN)
    for k, x in enumerate((4.4, 12.0, 19.6)):
        B.energy(path([(12, 7.6), (x, 11.2)], 0.75, 0.55), BEAM, falloff=0.7)
        figure(B, x, 19.0, 0.66, ALLY, seed=k + 3)
        mini_sun(B, x, 11.6, 1.25)
    C = G("paladin", (12, 3))
    C.glow(12, 3, 6, "ffd860", 0.6)
    hand_open(C, 12, 2.8, 0.42, SKIN)
    for k, (x, y, s) in enumerate(((4.8, 18.6, 0.8), (19.2, 18.6, 0.8), (12.0, 17.6, 0.86))):
        figure(C, x, y, s, ALLY, seed=k + 6)
        mini_sun(C, x, y - 5.4 * s - 3.8, 1.3)
    return A, B, C


def pal_pb_descendent_of_pentival():
    # round 3 ("more dragony"): a red dragon's head with the sun as its eye's halo, horns swept
    # back; a dragon breathing a stream of sunfire; the sun between spread dragon wings, one red
    # and one blue for the two Dragon trinkets
    A = G("paladin", (16, 6))
    big_sun(A, 16.4, 6.4, 2.6, long_=2.0, short=1.5, face=False)
    dragon_head(A, 8.6, 13.2, 1.2, ang=-14, seed=1)
    B = G("paladin", (14, 8))
    tip = dragon_head(B, 6.4, 14.6, 1.0, ang=-22, seed=2, open_=1.0)
    tx, ty = tip
    B.energy(poly([(tx - 0.4, ty + 0.4), (22.4, 3.0), (23.8, 9.8)]), SUNR, falloff=2.0)
    B.glow(19, 7, 6, "ffd860", 0.6)
    B.energy(circle(19.6, 6.8, 2.2), SUNR, falloff=1.8)
    C = G("paladin", (12, 9))
    wing(C, 10.6, 13.4, -1, 0.95, DRAG_R, seed=3)
    wing(C, 13.4, 13.4, 1, 0.95, SCALE_B, seed=4)
    big_sun(C, 12, 12.6, 2.6, long_=1.8, short=1.4, face=False)
    return A, B, C


# ---------------------------------------------------------------- the Blessing stack (14x14)
def hud_pelors_blessing():
    # round 3 (round-2 B, the sun in its ring of stack beads; "more sun with sun rays like"): a
    # bigger sun with wedge rays inside the bead ring; the rays reaching out to the beads; no
    # beads, just the sun and its rays
    A = S("paladin", (7, 7))
    A.glow(7, 7, 6, "ffd860", 0.5)
    spikes(A, 7, 7, 2.2, 4.6, 10, 12, SUNR, a0=-90 + 18, fall=0.7)
    pips(A, 7, 7, 5.8, 10, pr=0.7)
    A.energy(circle(7, 7, 2.5), SUNR, falloff=1.8)
    B = S("paladin", (7, 7))
    B.glow(7, 7, 6, "ffd860", 0.5)
    for k in range(10):
        a = math.radians(-90 + k * 36)
        B.energy(seg(7 + math.cos(a) * 2.4, 7 + math.sin(a) * 2.4, 7 + math.cos(a) * 5.8, 7 + math.sin(a) * 5.8, 0.55, 0.2), SUNR, falloff=0.45)
    pips(B, 7, 7, 5.9, 10, pr=0.75)
    B.energy(circle(7, 7, 2.7), SUNR, falloff=1.9)
    C = S("paladin", (7, 7))
    big_sun(C, 7, 7, 2.6, long_=2.55, short=1.8, n=6, face=False, half=14)
    return A, B, C


ITEMS = [
    ("pal_class", "Generosity (emblem)", "Your round-2 C, the sun's face, with more and longer rays: A wedge rays long and short; B thin rays to the edge; C a crown of rays round a ring."),
    ("pal_pelors_fury", "Pelor's Fury", "Your round-2 A, zoomed in with a broader beam: A the beam on the shadow's head; B broader, light bursting; C a white-hot core, the shadow breaking into wisps."),
    ("pal_pelors_blessing", "Pelor's Blessing", "Your round-2 A's elder with a real staff: A a tall oak staff, sun orb on top; B the staff held up, light pouring down; C a shepherd's crook curled round the sun."),
    ("pal_pf_blinding_sun", "Blinding Sun (orb)", "A hand in the bottom left shielding against a white sun: A plain; B the hand dark against the glare, edges lit; C the hand closer, covering the sun's edge."),
    ("pal_pb_display_of_generosity", "Display of Generosity (orb)", "Your round-2 A with the Blessing's sun over each ally's head: A as it was; B beams ending in the suns; C bigger allies, no beams."),
    ("pal_pb_descendent_of_pentival", "Descendent of Pentival (orb)", "More dragon: A a red dragon's head under the sun; B a dragon breathing sunfire; C the sun between a red and a blue dragon wing."),
    ("hud_pelors_blessing", "Pelor's Blessing (stack)", "Your round-2 B with more sun: A wedge rays inside the bead ring; B rays reaching out to the beads; C just the sun and its rays. 14x14."),
]
ALL = {n: (lab, what) for n, lab, what in ITEMS}


def now(n):
    k = BASE[n][0]
    return Image.open(R2 / f"{n}_{k}.png").convert("RGBA") if k else None


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    rows = [(n, out[n] + ([now(n)] if now(n) else [])) for n, _, _ in ITEMS if n in out]
    if rows:
        sheet(rows, OUT / "sheet_paladin.png")
    return out


def picker():
    its = []
    for n, lab, what in ITEMS:
        imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
        if now(n):
            imgs["now"] = sp.uri(now(n))
        its.append({"id": "specsPal3." + n, "name": lab, "key": n, "desc": what, "imgs": imgs})
    groups = [{"id": "specsPal3.paladin", "title": "Paladin: Generosity, round 3", "items": its}]
    tpl = (sp.HERE / "picker_tpl.html").read_text(encoding="utf-8").replace("Skill Icon Picks", "Spec Icon Picks")
    assert "/*DATA*/null" in tpl
    page = OUT / "picker.html"
    page.write_text(tpl.replace("/*DATA*/null", json.dumps(groups)), encoding="utf-8")
    return page


def save(n, im):
    assert im.size == ((14, 14) if n.startswith("hud_") else (24, 24)), (n, im.size)
    sp.OVR.mkdir(parents=True, exist_ok=True)
    im.save(sp.OVR / f"{n}.png")
    print("wrote", sp.OVR / f"{n}.png")


def finals():
    for n, k in FINALS.items():
        save(n, Image.open(R2 / f"{n}_{k}.png").convert("RGBA"))


def pick(fn):
    """The chosen idea of each icon to art/specs/override/<name>.png; "keep" takes the round-2 pick."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specsPal3.") else k
        c = v.get("choice") if isinstance(v, dict) else v
        if n not in ALL or c not in ("a", "b", "c", "keep") or (c == "keep" and not now(n)):
            print("skip", k, c)
            continue
        save(n, now(n) if c == "keep" else Image.open(OUT / f"{n}_{c}.png").convert("RGBA"))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--pick"]:
        pick(a[1])
    elif a[:1] == ["--finals"]:
        finals()
    else:
        render([x for x in a if not x.startswith("--")] or list(ALL))
        if "--picker" in a:
            print(picker())
