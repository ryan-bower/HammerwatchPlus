"""The 4th specializations' icons, round 2: three new ideas for each icon the user left a
note on in round 1 (out/specs/picks_r1.json), built on that pick and doing what the note
asks, and for every Ranger (Deadeye) and Wizard (Aerotheurge) icon, whose skills changed
with Noah's PR #4. Same painters and grounds as sp.py; hud_* icons at their 14x14.

    python tools/icon_art/sp_r2.py [names...]   # out/specs/r2/<name>_<a|b|c>.png, out/specs/r2/sheet_<spec>.png
                                                # (the round-1 pick, "now", beside the three)
    python tools/icon_art/sp_r2.py --picker     # also out/specs/r2/picker.html, ids specs2.<name>
    python tools/icon_art/sp_r2.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                # {"specs2.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
import sp

OUT = sp.HERE / "out" / "specs" / "r2"
PICKS = sp.HERE / "out" / "specs" / "picks_r1.json"

PURPLE = R("0a0418", "200a44", "3e1a78", "6a34b0", "a070e8", "dcc0ff", "ffffff")   # mana, in violet
LIT_ALLY = R("44306a", "6a4e9a", "9a7ccc", "d0bcf0", "f0e8ff", "ffffff")     # a tiny figure that must read
PURPLE_ALLY = R("0e0a18", "26183e", "44306a", "6a4e9a", "9a7ccc", "d0bcf0")


# ---------------------------------------------------------------- new shapes
def banner_c(ic, cx, top, bottom, s=1.0, cloth=CLOTH, crest=GOLD, pole=WOOD, wave=0.0, seed=0, emblem="shield"):
    """A war standard with the pole up the back of the cloth's centre: finial and crossbar
    above, the swallow-tailed cloth hanging square in front, the pole's foot below.
    Returns the crest centre."""
    w, h = 9.6 * s, 11.0 * s
    x0, y0 = cx - w / 2, top + 2.0 * s
    ic.solid(box(cx, (top + bottom) / 2, 0.75 * s, (bottom - top) / 2, 0, 0.3), pole, seed=seed, base=2.4)
    ic.solid(box(cx, top + 1.5 * s, w / 2 + 0.7 * s, 0.65 * s, 0, 0.3), pole, seed=seed + 2, base=3.0)
    for d in (-1, 1):
        ic.solid(circle(cx + d * (w / 2 + 0.7 * s), top + 1.5 * s, 0.8 * s), crest, seed=seed + 5, base=3.2)
    ic.solid(circle(cx, top + 0.3 * s, 1.0 * s), crest, seed=seed + 3, base=3.4)

    def cl(x, y):
        u = (x - x0) / w
        if u < 0 or u > 1:
            return 1.0
        sag = math.sin(u * 3.0 + wave) * 0.7 * s * (0.3 + u * 0.7)
        yt = y0 + sag * 0.4
        notch = max(0.0, 1 - abs(u - 0.5) / 0.22) * 2.8 * s
        yb = y0 + h - notch + sag
        return max(yt - y, y - yb, -u * w, (u - 1) * w)
    ic.solid(cl, cloth, seed=seed + 1, base=2.8, light=(-0.6, -0.8))
    ccx, ccy = cx, y0 + h * 0.4 + math.sin(0.5 * 3.0 + wave) * 0.7 * s * 0.65
    if emblem == "shield":
        ic.solid(poly([(ccx - 2.6 * s, ccy - 2.8 * s), (ccx + 2.6 * s, ccy - 2.8 * s), (ccx + 2.6 * s, ccy + 0.4 * s),
                       (ccx, ccy + 3.2 * s), (ccx - 2.6 * s, ccy + 0.4 * s)]), crest, seed=seed + 4, base=3.0)
    elif emblem == "sun":
        sun(ic, ccx, ccy, 1.6 * s, HOLY, 8)
    return ccx, ccy


def big_arrow(ic, cx, cy, ang, s=1.0, head=STEEL, fletch=FLETCH, shaft=WOOD, seed=0, length=18):
    """An arrow that reads at a glance: a broad barbed head, a plain shaft, three long vanes."""
    h = length / 2
    items = [
        (lbox(-1.0, 0, h - 2.0, 0.75, 0.3), shaft, {"base": 3.0, "rim": 0.6}),
        (lambda x, y: poly([(h - 4.4, -3.0), (h + 1.6, 0), (h - 4.4, 3.0), (h - 3.2, 0)])(x, y), head, {"base": 3.0, "rim": 1.6}),
        (lambda x, y: poly([(-h, -0.4), (-h + 4.6, -0.4), (-h + 3.0, -2.6), (-h - 1.0, -2.6)])(x, y), fletch, {"base": 3.2}),
        (lambda x, y: poly([(-h, 0.4), (-h + 4.6, 0.4), (-h + 3.0, 2.6), (-h - 1.0, 2.6)])(x, y), fletch, {"base": 2.2}),
    ]
    parts(ic, cx, cy, ang, s, items, seed)


def font(ic, cx, cy, s=1.0, seed=0, liquid=MANA):
    """A stone font seen from the front and a little above: a bowl on a short pillar."""
    ic.solid(box(cx, cy + 5.6 * s, 2.0 * s, 3.2 * s, 0, 0.4), SMOKE, seed=seed, base=2.2)
    ic.solid(box(cx, cy + 8.6 * s, 4.4 * s, 1.0 * s, 0, 0.4), SMOKE, seed=seed + 1, base=2.6)
    ic.solid(union(ellipse(cx, cy, 7.2 * s, 2.4 * s), poly([(cx - 7.2 * s, cy), (cx + 7.2 * s, cy), (cx + 3.6 * s, cy + 3.6 * s), (cx - 3.6 * s, cy + 3.6 * s)])),
             SMOKE, seed=seed + 2, base=3.0)
    ic.energy(ellipse(cx, cy - 0.1 * s, 5.8 * s, 1.5 * s), liquid, falloff=1.4)


def pips(ic, cx, cy, r, n, lit, rmp=ELEC, a0=-90, spread=360, pr=1.1):
    """n stack pips on an arc around (cx, cy); the first `lit` bright, the rest dim."""
    for k in range(n):
        a = math.radians(a0 + (spread * k / n if spread >= 360 else spread * (k / (n - 1) - 0.5)))
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        if k < lit:
            ic.energy(circle(x, y, pr), rmp, falloff=pr)
        else:
            ic.solid(circle(x, y, pr * 0.8), rmp[:4], base=1.6, spread=0.4)


def fork(ic, x0, y0, tips, rmp=ELEC, w=0.8, seed=0, trunk=None):
    """A trunk of lightning from (x0, y0) to a split point, then a jagged branch to each tip."""
    tx, ty = trunk or (x0, y0)
    if trunk:
        zap(ic, x0, y0, tx, ty, rmp, w, 3, 1.0, seed)
    for k, (x, y) in enumerate(tips):
        zap(ic, tx, ty, x, y, rmp, w * 0.8, 4, 1.2, seed + k + 1)


def burst(ic, cx, cy, r, rmp, seed=0, lobes=7):
    """An explosion: a lobed fireball, hottest in the middle."""
    def f(x, y):
        a = math.atan2(y - cy, x - cx)
        rr = r * (0.72 + 0.28 * math.sin(a * lobes + seed) * math.sin(a * 3 - seed * 0.7))
        return math.hypot(x - cx, y - cy) - rr
    ic.energy(f, rmp, falloff=r * 0.8, seed=seed)


# ================================================================ notes: HUD
def hud_arcane_feedback():
    # the picked star, now a purple blast
    A = S("sorcerer")
    A.glow(7, 7, 7, "9a6ae0", 0.8)
    burst(A, 7, 7, 4.6, ARCANE, seed=1)
    A.energy(star(7, 7, 6.5, 1.6, 4, -90), ARCANE, falloff=1.0)
    B = S("sorcerer")
    B.rays(7, 7, ARCANE, n=8, hi=4.5)
    burst(B, 7, 7, 3.8, ARCANE, seed=3, lobes=5)
    C = S("sorcerer")
    flash(C, 7, 7, 5.2, ARCANE, 2)
    for x, y in ((1.5, 2), (12.5, 2.5), (2, 12), (12, 12.5)):
        C.energy(circle(x, y, 0.6), ARCANE, falloff=0.5)
    return A, B, C


def hud_standard_raised():
    A = S("warrior")
    banner_c(A, 7, 0, 14, 0.85, seed=1)
    B = S("warrior")
    banner_c(B, 7, 0, 14, 0.85, wave=1.4, seed=2)
    C = S("warrior")
    C.glow(7, 6, 7, "ffe070", 0.55)
    banner_c(C, 7, 0, 14, 0.85, seed=3)
    return A, B, C


def hud_standard_planted():
    A = S("warrior")
    banner_c(A, 7, 0, 13, 0.8, seed=1)
    A.solid(ellipse(7, 13, 4.6, 1.2), EARTH, base=2.2)
    # the picked one's twin chevrons: doubled reduction
    B = S("warrior")
    banner_c(B, 6, 0, 13, 0.75, seed=2)
    B.solid(ellipse(6, 13, 4.0, 1.1), EARTH, base=2.2)
    for k, y in enumerate((7.5, 10.5)):
        B.energy(path([(10.3, y + 1.6), (12, y), (13.7, y + 1.6)], 0.45), GOLD, falloff=0.4)
    C = S("warrior")
    C.energy(ellipse(7, 12.6, 6.4, 1.6), R("2a1a04", "6a4a10", "b08a20", "e8c850", "fff0a0"), falloff=0.6)
    banner_c(C, 7, 0, 12.8, 0.8, seed=3)
    return A, B, C


def hud_void_barrier():
    # the picked ring, with a little figure squeezed inside
    A = S("sorcerer")
    A.energy(cut(circle(7, 7, 6.6), circle(7, 7, 5.2)), VOID, falloff=0.8)
    figure(A, 7, 7.4, 0.42, LIT_ALLY)
    B = S("sorcerer")
    B.solid(circle(7, 7, 6.2), VOID, base=1.4, spread=0.8)
    B.energy(ring(7, 7, 5.9, 0.35), ARCANE, falloff=0.35)
    figure(B, 7, 7.4, 0.42, R("2c1850", "44306a", "6a4e9a", "9a7ccc", "d0bcf0", "ffffff"))
    C = S("sorcerer")
    C.energy(cut(circle(7, 7, 6.6), circle(7, 7, 5.0)), VOID, falloff=0.8)
    C.glow(7, 7, 4.5, "7a3ab0", 0.6)
    figure(C, 7, 7.6, 0.44, LIT_ALLY)
    C.glint(3, 3)
    return A, B, C


# ================================================================ notes: Sorcerer, Rogue, Warrior, Warlock
def sor_living_mana():
    # the picked mana heart, with B's red rim round it
    A = G("sorcerer", (8, 6))
    A.glow(12, 12, 12, "5a90e8", 0.45)
    A.solid(cut(heart(12, 12, 8.2), heart(12, 12, 6.8)), CRIMSON, base=3.0)
    A.energy(heart(12, 12, 6.8), MANA, falloff=3.6)
    A.energy(heart(10, 10, 2.0), R("ffffff", "ffffff"), falloff=1)
    B = G("sorcerer", (8, 6))
    B.solid(heart(12, 12, 8.4), CRIMSON, base=2.4)
    B.energy(heart(12, 12.2, 6.4), MANA, falloff=3.2)
    B.glint(8, 8)
    C = G("sorcerer", (8, 6))
    C.glow(12, 12, 12, "5a90e8", 0.5)
    C.energy(heart(12, 11.5, 7.2), MANA, falloff=3.8)
    C.energy(cut(heart(12, 11.5, 8.4), heart(12, 11.5, 7.2)), CRIMSON, falloff=0.6)
    C.energy(drop(14.5, 21, 1.4), MANA, falloff=1.2)
    return A, B, C


def _conduit(ic, rmp, ally, drop_y=7):
    for k, x in enumerate((4.5, 19.5)):
        ic.energy(path([(12, drop_y + 2), ((12 + x) / 2, drop_y + 2.5), (x, 14)], 0.8, 0.4), rmp, falloff=0.6)
        figure(ic, x, 16, 0.55, ally, seed=k)
    ic.energy(drop(12, drop_y, 3.6), rmp, falloff=2.6)


def sor_lm_mana_conduit():
    # the picked one in violet: the drop, the streams, the allies
    A = G("sorcerer", (12, 8))
    _conduit(A, PURPLE, R("0a1018", "18263a", "2a4260", "426488", "6a90b0", "a0c4dc"))
    B = G("sorcerer", (12, 8))
    _conduit(B, ARCANE, PURPLE_ALLY)
    C = G("sorcerer", (12, 8))
    _conduit(C, PURPLE, PURPLE_ALLY)
    for x in (4.5, 19.5):
        C.energy(ring(x, 16, 4.6, 0.3), ARCANE, falloff=0.3)
    return A, B, C


def rog_sw_shared_breath():
    # the picked split gust to two allies, much windier
    A = G("rogue", (6, 12))
    A.energy(path([(0, 12), (7, 12)], 0.6, 1.4), BREEZE, falloff=0.8)
    for k, (x, y) in enumerate(((19, 6), (19, 18))):
        gust(A, 7, 12, 14.5, y + (-2.5 if k == 0 else 2.5), 0.9 if k == 0 else -0.9, 1.1, BREEZE)
        figure(A, x + 1.5, y + 1, 0.5, ALLY, seed=k)
    for k, y in enumerate((8, 16)):
        line(A, 0, y, 5, y, 0.5, BREEZE, seed=k)
    B = G("rogue", (6, 12))
    for k, (x, y) in enumerate(((19, 6), (19, 18))):
        for j, off in enumerate((-1.6, 1.6)):
            B.energy(path([(1, 12 + off * 0.6), (8, 12 + off), (13, (12 + y) / 2 + off), (16.5, y + off * 0.6)], 0.6, 0.3), BREEZE, falloff=0.5)
        figure(B, x + 2, y + 1, 0.5, ALLY, seed=k)
    gust(B, 2, 4, 9, 3, 0.8, 0.8, BREEZE)
    gust(B, 2, 21, 9, 21, 0.8, 0.8, BREEZE)
    C = G("rogue", (8, 12))
    swirl(C, 6, 12, 5, 1.2, 180, -1.1, 0.3, 1.0, BREEZE)
    for k, (x, y) in enumerate(((19, 6), (19, 18))):
        gust(C, 9, 12, x - 4, y, 0.0, 1.0, BREEZE)
        C.energy(path(arc_pts(x + 0.5, y + 1, 5.0, 100, 260), 0.3, 0.8), BREEZE, falloff=0.5)
        figure(C, x + 0.5, y + 1, 0.5, ALLY, seed=k)
    return A, B, C


def war_battlefield_standard():
    # the picked rays and ground, the pole up the cloth's back
    A = G("warrior", (12, 6))
    A.rays(12, 8, HOLY, n=9, hi=3)
    banner_c(A, 12, 1, 22.5, 1.3, wave=0.6, seed=2)
    A.solid(ellipse(12, 22.5, 5, 1.3), EARTH, base=2.0)
    B = G("warrior", (12, 8))
    banner_c(B, 12, 0, 24, 1.5, wave=0.4, seed=3)
    C = G("warrior", (12, 6))
    C.glow(12, 9, 13, "e8c850", 0.55)
    banner_c(C, 12, 1, 22.5, 1.3, wave=1.6, seed=4)
    C.solid(ellipse(12, 22.5, 5, 1.3), EARTH, base=2.0)
    return A, B, C


def war_righteous_crusade():
    # the picked sun banner, the pole up the cloth's back
    A = G("warrior", (12, 8))
    banner_c(A, 12, 0, 24, 1.5, wave=0.4, seed=3, emblem="sun")
    B = G("warrior", (12, 6))
    B.rays(12, 9, HOLY, n=11, hi=3.2)
    banner_c(B, 12, 1, 24, 1.35, wave=0.8, seed=4, emblem="sun")
    C = G("warrior", (12, 8))
    C.glow(12, 10, 12, "ffe070", 0.6)
    banner_c(C, 12, 0, 24, 1.5, cloth=R("140406", "3a0a10", "6e1220", "a81e2e", "dc3a40", "ff7060"), crest=HOLY,
             wave=1.5, seed=5, emblem="sun")
    return A, B, C


def wlk_pb_combustion():
    # the picked claw, now in a fiery blast, a little essence in it
    A = G("warlock", (12, 14))
    A.glow(12, 15, 13, "ff8a2a", 0.8)
    burst(A, 12, 13, 9.5, HELL, seed=2)
    claw(A, 12, 22, 1.15, R("1e0604", "3a0806", "5a0c06", "a81e08", "e04a10", "ff8a2a", "ffd070"), seed=1)
    for k, (x, y) in enumerate(((4, 5), (20, 4), (3, 15), (21, 14))):
        A.energy(circle(x, y, 1.3), ESS, falloff=1.2)
    B = G("warlock", (12, 14))
    B.rays(12, 16, HELL, n=10, hi=4)
    B.energy(flame(12, 23, 10, 22, 0, 3, 4), HELL, falloff=3)
    claw(B, 12, 22, 1.0, ESS, seed=2)
    for k, (x, y) in enumerate(((5, 6), (19, 7))):
        B.energy(circle(x, y, 1.0), ESS, falloff=1)
    C = G("warlock", (12, 14))
    burst(C, 12, 12, 10, ESS, seed=4, lobes=6)
    burst(C, 12, 13, 7.5, HELL, seed=5)
    claw(C, 12, 22, 1.1, seed=3)
    return A, B, C


# ================================================================ Ranger: Deadeye
def ran_electric_circuit():
    # Lightning Arrow: three electric arrows forking out in a V, no ring
    A = G("ranger", (12, 16))
    for k, a in enumerate((-122, -90, -58)):
        r = math.radians(a)
        x, y = 12 + math.cos(r) * 11.5, 23 + math.sin(r) * 11.5
        zap(A, 12 + math.cos(r) * 2, 23 + math.sin(r) * 2, x + math.cos(r) * 4, y + math.sin(r) * 4, VOLT, 0.35, 4, 1.2, k)
        arrowv(A, x, y, a, 0.68, head=VHEAD, seed=k)
    B = G("ranger", (6, 18))
    for k, a in enumerate((-80, -45, -10)):
        r = math.radians(a)
        x, y = 3 + math.cos(r) * 11.5, 21 + math.sin(r) * 11.5
        zap(B, 3 + math.cos(r) * 3, 21 + math.sin(r) * 3, x + math.cos(r) * 3, y + math.sin(r) * 3, VOLT, 0.35, 4, 1.2, k + 3)
        arrowv(B, x, y, a, 0.6, head=VHEAD, seed=k)
    # a fork of lightning, an arrowhead riding each prong
    C = G("ranger", (12, 16))
    fork(C, 12, 23, [(4, 8), (12, 6), (20, 8)], VOLT, 0.8, 2, trunk=(12, 15))
    for k, (x, y, a) in enumerate(((4, 6.5, -118), (12, 4.5, -90), (20, 6.5, -62))):
        C.solid(L(lambda u, v: poly([(-2.6, -2.4), (2.4, 0), (-2.6, 2.4), (-1.6, 0)])(u, v), x, y, a, 1.0), VHEAD, base=3.4, seed=k)
    return A, B, C


def ran_gathering_winds():
    # every 5 kills a Tailwind stack: the picked bow and wind lines
    A = G("ranger", (14, 10))
    for k, (y, x0, x1) in enumerate(((3, 0, 9), (7, 0, 7), (11, 1, 8), (15, 0, 10))):
        line(A, x0, y, x1, y, 0.6, GUST, seed=k)
    for k in range(5):
        A.energy(circle(6.5 + k * 3.4, 20.5, 1.25), GUST, falloff=1.0)
    bow(A, 15, 11.5, 0, 0.9, drawn=3)
    arrowv(A, 13, 11.5, 0, 0.72)
    B = G("ranger", (14, 10))
    for k, (y, x0, x1) in enumerate(((6, 6, 12), (18, 6, 12))):
        line(B, x0, y, x1, y, 0.5, GUST, seed=k)
    bow(B, 16, 12, 0, 0.9, drawn=3)
    arrowv(B, 14, 12, 0, 0.7)
    skull(B, 5, 15, 0.55, BONE)
    swirl(B, 5, 9, 4, 1, 180, -1.0, 0.25, 0.8, GUST)
    C = G("ranger", (14, 10))
    for k in range(5):
        y = 3 + k * 4.5
        gust(C, 0, y, 7, y + (12 - y) * 0.25, 0.5 if k % 2 else 0.0, 0.8, GUST)
    bow(C, 15, 12, 0, 0.95, drawn=3)
    arrowv(C, 13, 12, 0, 0.75)
    return A, B, C


def _boom_trail(ic, rmp, w0=0.3, w1=1.1):
    ic.energy(path([(3, 4.5), (11, 3.5), (17.5, 4.5), (21.5, 9.5), (20, 15), (16, 17.5)], w0, w1), rmp, falloff=0.7)


def ran_ec_boomerang():
    # the picked U-turn: a bigger, plainer arrow and no stray bolt
    A = G("ranger", (14, 8))
    _boom_trail(A, VOLT)
    big_arrow(A, 9, 17.5, 180, 0.85, head=VHEAD)
    B = G("ranger", (14, 8))
    _boom_trail(B, GUST, 0.25, 0.9)
    big_arrow(B, 9, 17.5, 180, 0.85, head=VHEAD, fletch=VOLT)
    C = G("ranger", (14, 10))
    C.energy(path(arc_pts(12, 10.5, 7.5, 200, 470), 0.3, 1.2), VOLT, falloff=0.7)
    big_arrow(C, 8, 18.5, 200, 0.8, head=VHEAD)
    return A, B, C


def ran_ec_lightning_rod():
    # Storm Arrow: more strikes, a wider ring of them round the arrow
    A = G("ranger", (12, 8))
    for k, x in enumerate((2.5, 7, 12, 17, 21.5)):
        zap(A, x + 1.5, 0, x, 13 + abs(x - 12) * 0.35, VOLT, 0.5, 4, 1.2, k + 3)
    arrowv(A, 12, 17, 0, 0.9)
    B = G("ranger", (12, 8))
    B.energy(ring(12, 18, 9.5, 0.4), VOLT, falloff=0.3)
    for k, x in enumerate((3, 8, 16, 21)):
        y = 18 - math.sqrt(max(0, 9.5 ** 2 - (x - 12) ** 2)) * 0.35
        zap(B, x + 1, 0, x, y, VOLT, 0.5, 4, 1.2, k)
        B.energy(circle(x, y, 1.0), VOLT, falloff=0.8)
    arrowv(B, 12, 14, 90, 0.7)
    C = G("ranger", (12, 8))
    for k, (x0, x1) in enumerate(((1, 2), (6, 6.5), (13, 11), (19, 17), (24, 22))):
        zap(C, x0, 0, x1, 15, VOLT, 0.45, 4, 1.3, k + 6)
    for x in (2, 6.5, 11, 17, 22):
        C.energy(ellipse(x, 15.5, 1.6, 0.6), VOLT, falloff=0.5)
    arrowv(C, 12, 19, 0, 0.9)
    return A, B, C


def ran_ec_tailwind_catch():
    # a hand closing on a returning arrow, close up and nothing else
    A = G("ranger", (8, 6))
    big_arrow(A, 12, 12, -135, 1.15)
    fist(A, 12.5, 12.5, 1.0, SKIN)
    B = G("ranger", (8, 6))
    big_arrow(B, 11, 10, -160, 1.15)
    B.solid(box(18.5, 19, 3.6, 4.2, -20, 1.0), LEATHER, base=2.4)
    fist(B, 13.5, 11.5, 1.0, SKIN)
    C = G("ranger", (8, 6))
    big_arrow(C, 12, 11, 160, 1.15)
    fist(C, 15, 12, 1.05, SKIN)
    for k, y in enumerate((19, 22)):
        line(C, 13, y, 22, y, 0.45, GUST, seed=k)
    return A, B, C


def ran_gw_gale_force():
    # at 5 Tailwind two more arrows: the picked gusts with arrowheads, three plus two
    A = G("ranger", (12, 12))
    for k, y in enumerate((3, 7.5, 12, 16.5, 21)):
        extra = k in (0, 4)
        gust(A, 1, y, 13, y, 0.6, 0.9 if extra else 1.1, GUST if not extra else R("060c16", "0e2236", "3a73a0", "7cb2d8", "c4e6f8", "ffffff"))
        A.solid(poly([(16, y - 1.9), (21, y), (16, y + 1.9)]), VHEAD if extra else STEEL, base=3.2)
    B = G("ranger", (12, 12))
    for k, y in enumerate((6, 12, 18)):
        gust(B, 1, y, 14, y, 0.6, 1.2, GUST)
        B.solid(poly([(16, y - 2.2), (22, y), (16, y + 2.2)]), STEEL, base=3.2)
    for k, (y0, y1) in enumerate(((9, 2.5), (15, 21.5))):
        B.energy(path([(12, y0), (17, (y0 + y1) / 2), (19.5, y1)], 0.3, 0.6), GUST, falloff=0.4)
        B.solid(L(lambda u, v: poly([(-2, -1.6), (2.2, 0), (-2, 1.6)])(u, v), 21, y1, -25 if k == 0 else 25, 1.0), VHEAD, base=3.4)
    C = G("ranger", (12, 12))
    swirl(C, 5, 12, 4.5, 1, 180, -1.0, 0.3, 0.9, GUST)
    for k, a in enumerate((-50, -25, 0, 25, 50)):
        r = math.radians(a)
        C.energy(path([(7 + math.cos(r) * 3, 12 + math.sin(r) * 3), (7 + math.cos(r) * 10, 12 + math.sin(r) * 10)], 0.3, 0.8), GUST, falloff=0.4)
        C.solid(L(lambda u, v: poly([(-2, -1.8), (2.4, 0), (-2, 1.8)])(u, v), 7 + math.cos(r) * 13, 12 + math.sin(r) * 13, a, 1.0),
                VHEAD if k in (0, 4) else STEEL, base=3.2)
    return A, B, C


def ran_gw_wind_ward():
    # Tailwind stacks soften blows: the picked shield and wind arcs
    A = G("ranger", (12, 12))
    shield(A, 12, 11, 0.62, STEEL, face=GUST, boss=None, kite=True)
    for k in range(3):
        A.energy(path(arc_pts(12, 12, 10.5, k * 120 + 10, k * 120 + 95), 0.3, 1.0), GUST, falloff=0.5)
    B = G("ranger", (12, 12))
    swirl(B, 12, 12, 11, 8.6, 200, 0.95, 0.3, 1.1, GUST)
    shield(B, 12, 11, 0.6, STEEL, face=GUST, boss=None, kite=True)
    C = G("ranger", (10, 12))
    shield(C, 10, 11, 0.6, STEEL, face=GUST, boss=None, kite=True)
    C.energy(path(arc_pts(10, 11, 8.5, -70, 70), 0.9, 0.9), GUST, falloff=0.8)
    arrowv(C, 21, 6, 150, 0.5, fletch=CRIMSON)
    spark(C, 18.3, 7.4, 1.8, GUST)
    return A, B, C


def hud_tailwind():
    A = S("ranger")
    swirl(A, 7, 7, 6.2, 1, 180, -1.25, 0.35, 1.1, GUST)
    B = S("ranger")
    swirl(B, 8, 7, 5.2, 1, 180, -1.2, 0.3, 1.0, GUST)
    for k, y in enumerate((3, 11)):
        line(B, 0, y, 5, y, 0.5, GUST, seed=k)
    C = S("ranger")
    swirl(C, 7, 7, 6.4, 3.2, 180, -0.85, 0.3, 0.9, GUST)
    swirl(C, 7, 7, 3.0, 0.6, 0, -0.9, 0.25, 0.7, GUST)
    return A, B, C


# ================================================================ Wizard: Aerotheurge
def wiz_tempest_torrent():
    # Thunder Orb: a slow orb zapping three foes
    A = G("wizard", (12, 6))
    for k, (x, y) in enumerate(((4, 19), (12, 21), (20, 19))):
        zap(A, 12, 7, x, y - 3, ELEC, 0.5, 4, 1.4, k)
        foe(A, x, y, 0.45, seed=k)
    ball(A, 12, 7, 4.4, seed=1)
    B = G("wizard", (14, 10))
    B.energy(path([(1, 22), (5, 18.5), (10, 14)], 0.3, 2.6), ELEC, falloff=1.2)
    for k, (x, y) in enumerate(((22, 3), (23, 14), (16, 23))):
        zap(B, 14, 11, x, y, ELEC, 0.55, 4, 1.4, k + 3)
    ball(B, 13, 12, 5, seed=2)
    C = G("wizard", (12, 12))
    for k in range(3):
        a = math.radians(-90 + k * 120)
        zap(C, 12, 12, 12 + math.cos(a) * 12, 12 + math.sin(a) * 12, ELEC, 0.65, 4, 1.4, k + 6)
    ball(C, 12, 12, 6.2, seed=3, bolts=4)
    return A, B, C


def wiz_static_charge():
    # a stack per cast, five sparks; at five a strike split three ways
    A = G("wizard", (12, 12))
    hand_open(A, 12, 18, 0.8, SKIN)
    pips(A, 12, 11, 8.5, 5, 5, ELEC, a0=-90, spread=150, pr=1.3)
    B = G("wizard", (12, 12))
    spark(B, 12, 12, 4.5)
    pips(B, 12, 12, 8.8, 5, 3, ELEC, a0=-90, pr=1.4)
    C = G("wizard", (12, 6))
    pips(C, 12, 4, 5, 5, 5, ELEC, a0=180, spread=180, pr=1.0)
    fork(C, 12, 5, [(4, 21), (12, 22), (20, 21)], ELEC, 0.8, 1, trunk=(12, 12))
    return A, B, C


def wiz_tt_overcharge():
    # Focal Point: zap after zap into one foe, each harder
    A = G("wizard", (12, 8))
    for k, (x0, y0) in enumerate(((3, 2), (12, 1), (21, 2))):
        zap(A, x0, y0, 12, 15, ELEC, 0.35 + k * 0.25, 4, 1.2, k)
    foe(A, 12, 17, 0.75, seed=1)
    A.glow(12, 14, 6, "bfe0ff", 0.7)
    B = G("wizard", (12, 12))
    B.energy(ring(12, 13, 7.5, 0.4), ELEC, falloff=0.3)
    for d in (-1, 1):
        B.energy(seg(12 + d * 9.5, 13, 12 + d * 5.5, 13, 0.5), ELEC, falloff=0.4)
        B.energy(seg(12, 13 + d * 9.5, 12, 13 + d * 5.5, 0.5), ELEC, falloff=0.4)
    zap(B, 14, 0, 12, 13, ELEC, 1.0, 4, 1.4, 4)
    B.energy(circle(12, 13, 2.2), ELEC, falloff=2)
    C = G("wizard", (12, 12))
    for k, (x, w) in enumerate(((5, 0.35), (12, 0.65), (19, 1.0))):
        zap(C, x, 1, x, 17, ELEC, w, 4, 1.0 + k * 0.3, k + 2)
        C.energy(ellipse(x, 18.5, 1.6 + k * 0.8, 0.6 + k * 0.3), ELEC, falloff=0.5 + k * 0.3)
    return A, B, C


def wiz_tt_lightning_rod():
    # more zaps per tick, farther: the orb reaching every edge of the frame
    A = G("wizard", (12, 12))
    for k in range(6):
        a = math.radians(k * 60 + 15)
        zap(A, 12, 12, 12 + math.cos(a) * 13, 12 + math.sin(a) * 13, ELEC, 0.45, 5, 1.3, k)
    ball(A, 12, 12, 4.0, seed=9)
    B = G("wizard", (12, 12))
    for k, (x, y) in enumerate(((3, 3), (21, 4), (2, 13), (22, 13), (6, 21), (18, 21))):
        zap(B, 12, 12, x, y - 1.5, ELEC, 0.45, 4, 1.2, k + 6)
        foe(B, x, y, 0.32, seed=k)
    ball(B, 12, 12, 3.8, seed=10)
    C = G("wizard", (12, 12))
    C.energy(ring(12, 12, 10.6, 0.35), ELEC, falloff=0.3)
    C.energy(ring(12, 12, 6.0, 0.25), R("04081e", "0a1848", "15338a", "2a62d0"), falloff=0.25)
    for k in range(4):
        a = math.radians(k * 90 + 45)
        zap(C, 12, 12, 12 + math.cos(a) * 10.4, 12 + math.sin(a) * 10.4, ELEC, 0.45, 4, 1.0, k + 3)
    ball(C, 12, 12, 3.8, seed=11)
    return A, B, C


def wiz_tt_lingering_storm():
    # a longer orb: the hourglass, the long tail, a long clock arc
    A = G("wizard", (10, 10))
    ball(A, 8, 8, 5.2, seed=4)
    hourglass(A, 17.5, 15.5, 0.8, frame=BRASS, sand=ELEC, t=0.2)
    B = G("wizard", (17, 7))
    B.energy(path([(0, 23), (3, 21), (6, 18.5), (9, 15.5), (12, 13), (15, 10), (17.5, 7.5)], 0.3, 3.0), ELEC, falloff=1.2)
    for k, (x, y) in enumerate(((5, 14), (10, 20), (13, 9))):
        spark(B, x, y, 1.2)
    ball(B, 18, 6, 4.4, seed=5)
    C = G("wizard", (12, 12))
    C.energy(path(arc_pts(12, 12, 9.8, -90, 230), 0.6, 0.6), ELEC, falloff=0.5)
    for k in range(12):
        a = math.radians(-90 + k * 30)
        C.px([(int(12 + math.cos(a) * 9.8), int(12 + math.sin(a) * 9.8))], "ffffff")
    ball(C, 12, 12, 5, seed=6)
    return A, B, C


def wiz_tt_thunderclap():
    # the orb bursting as it ends
    A = G("wizard", (12, 12))
    A.rays(12, 12, ELEC, n=12, hi=4.5)
    burst(A, 12, 12, 6.5, ELEC, seed=2, lobes=8)
    A.energy(ring(12, 12, 10, 0.4), ELEC, falloff=0.3)
    B = G("wizard", (12, 12))
    for k in range(8):
        a = math.radians(k * 45 + 10)
        zap(B, 12 + math.cos(a) * 3, 12 + math.sin(a) * 3, 12 + math.cos(a) * 11, 12 + math.sin(a) * 11, ELEC, 0.5, 3, 1.0, k)
    B.energy(circle(12, 12, 3.4), ELEC, falloff=3)
    C = G("wizard", (12, 12))
    for k, r in enumerate((5.5, 8.5, 11.2)):
        C.energy(ring(12, 12, r, 0.55 - k * 0.12), ELEC, falloff=0.35)
    for k in range(6):
        a = math.radians(k * 60 + 30)
        C.energy(circle(12 + math.cos(a) * 7, 12 + math.sin(a) * 7, 0.9), ELEC, falloff=0.8)
    burst(C, 12, 12, 3.6, ELEC, seed=5, lobes=5)
    return A, B, C


def wiz_sc_static_channel():
    # Charged Font: the release pouring back as mana
    A = G("wizard", (12, 6))
    zap(A, 13, 0, 12, 12, ELEC, 0.9, 4, 1.4, 2)
    font(A, 12, 14, 1.05)
    for k, (x, y) in enumerate(((7, 10), (17, 9))):
        A.energy(circle(x, y, 0.9), MANA, falloff=0.8)
    B = G("wizard", (12, 10))
    zap(B, 6, 0, 10, 10, ELEC, 0.7, 4, 1.4, 3)
    B.energy(drop(14, 15, 5.4), MANA, falloff=3.2)
    B.energy(path([(10, 10), (12, 12)], 0.5), ELEC, falloff=0.4)
    C = G("wizard", (12, 10))
    hand_open(C, 12, 18, 0.75, SKIN)
    for k, (x, y) in enumerate(((7, 8), (12, 6), (17, 8))):
        C.energy(drop(x, y, 1.8), MANA, falloff=1.4)
    zap(C, 2, 1, 22, 1.5, ELEC, 0.45, 6, 1.2, 4)
    return A, B, C


def wiz_sc_conduit():
    # Conduit: stacks of Static Charge, casting faster
    A = G("wizard", (14, 12))
    for k, y in enumerate((6, 11, 16, 21)):
        line(A, 0, y, 7, y, 0.55, ELEC, seed=k)
    hand_open(A, 15, 15, 0.85, SKIN)
    pips(A, 15, 11, 7.5, 5, 5, ELEC, a0=-90, spread=160, pr=1.1)
    B = G("wizard", (12, 12))
    hourglass(B, 13, 12, 0.85, frame=BRASS, sand=ELEC, t=0.7)
    for k, y in enumerate((6, 12, 18)):
        line(B, 0, y, 6, y, 0.55, ELEC, seed=k)
    for k, (x, y) in enumerate(((19, 4), (20, 19))):
        spark(B, x, y, 2.0)
    C = G("wizard", (12, 12))
    for k, y in enumerate((5, 9.5, 14.5, 19)):
        line(C, 0, y, 9, y, 0.55, ELEC, seed=k)
    spark(C, 15, 12, 6)
    return A, B, C


def hud_static_charge():
    A = S("wizard")
    spark(A, 7, 7, 4.8)
    B = S("wizard")
    spark(B, 7, 6, 3.4)
    for k in range(5):
        B.energy(circle(2.4 + k * 2.3, 12, 0.55), ELEC, falloff=0.5)
    C = S("wizard")
    C.energy(poly([(8.6, 0.5), (3.6, 7.6), (6.8, 7.6), (4.8, 13.5), (10.8, 5.8), (7.6, 5.8), (10.2, 0.5)]), ELEC, falloff=1.2)
    C.glow(7, 7, 6, "60a0ff", 0.4)
    return A, B, C


# ================================================================ the list, the runner
R2 = [  # (spec key, title, [(name, label, what it is now)])
    ("ranger", "Ranger: Deadeye", [
        ("ran_electric_circuit", "Lightning Arrow (active)", "A volley of 3 piercing arrows in a V; each enemy hit calls lightning on 2 others; the arrows return to where they were fired."),
        ("ran_gathering_winds", "Gathering Winds (passive)", "Every 5 kills grants a Tailwind stack (4 s, up to 5): +Action Speed. Kill-driven now."),
        ("ran_ec_boomerang", "Boomerang (orb)", "The returning arrow deals more damage."),
        ("ran_ec_lightning_rod", "Storm Arrow (orb)", "More lightning strikes, in a larger radius."),
        ("ran_ec_tailwind_catch", "Tailwind Catch (orb)", "Catching the returning arrow grants Tailwind."),
        ("ran_gw_gale_force", "Gale Force (orb)", "At 5 Tailwind stacks, bow skills fire 2 extra projectiles."),
        ("ran_gw_wind_ward", "Wind Ward (orb)", "Tailwind stacks reduce damage taken."),
        ("hud_tailwind", "Tailwind (status)", "Stacking Action Speed."),
    ]),
    ("wizard", "Wizard: Aerotheurge", [
        ("wiz_tempest_torrent", "Thunder Orb (active)", "A slow lightning orb that zaps up to 3 enemies every 0.25 s."),
        ("wiz_static_charge", "Static Charge (passive)", "Each spell cast grants a stack; at 5 the next spell releases a lightning strike split between up to 3 enemies."),
        ("wiz_tt_overcharge", "Focal Point (orb)", "Consecutive zaps on the same enemy deal more damage."),
        ("wiz_tt_lightning_rod", "Lightning Rod (orb)", "More zaps per tick and more range."),
        ("wiz_tt_lingering_storm", "Lingering Storm (orb)", "The orb lasts longer."),
        ("wiz_tt_thunderclap", "Thunderclap (orb)", "The orb bursts when it ends."),
        ("wiz_sc_static_channel", "Charged Font (orb)", "The Static Charge release restores mana."),
        ("wiz_sc_conduit", "Conduit (orb)", "Static Charge stacks grant cast speed."),
        ("hud_static_charge", "Static Charge (status)", "Stacks to 5."),
    ]),
    ("sorcerer", "Sorcerer: Arcane", [
        ("sor_living_mana", "Living Mana (passive)", "A heart filled with mana instead of blood."),
        ("sor_lm_mana_conduit", "Mana Conduit (orb)", "Mana flowing out to two allies."),
        ("hud_void_barrier", "Void Barrier (status)", "Cannot die for 1 s."),
        ("hud_arcane_feedback", "Arcane Feedback (status)", "Next spell empowered."),
    ]),
    ("rogue", "Rogue: Winddancer", [
        ("rog_sw_shared_breath", "Shared Breath (orb)", "One gust splitting to two allies."),
    ]),
    ("warrior", "Warrior: Bannerlord", [
        ("war_battlefield_standard", "Battlefield Standard (active)", "A war banner held high, a shield crest on the cloth."),
        ("war_righteous_crusade", "Righteous Crusade (passive)", "A banner with a sunburst (buffs last longer)."),
        ("hud_standard_raised", "Battlefield Standard, carried (status)", "Damage reduction."),
        ("hud_standard_planted", "Battlefield Standard, planted (status)", "Double damage reduction."),
    ]),
    ("warlock", "Warlock: Branding", [
        ("wlk_pb_combustion", "Combustion (orb)", "The hellfire claw erupting, fed by essence orbs."),
    ]),
]
ALL2 = {n: (key, lab, what) for key, _, items in R2 for n, lab, what in items}


def now(n):
    p = sp.OVR / f"{n}.png"
    return Image.open(p).convert("RGBA") if p.exists() else None


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    for key, _, items in R2:
        rows = [(n, out[n] + ([now(n)] if now(n) else [])) for n, _, _ in items if n in out]
        if rows:
            sheet(rows, OUT / f"sheet_{key}.png")
    return out


CH = {"a": "A", "b": "B", "c": "C", "keep": "the placeholder", "": "none"}


def picker():
    r1 = json.loads(PICKS.read_text(encoding="utf-8"))
    groups = []
    for key, title, items in R2:
        its = []
        for n, lab, what in items:
            p = r1.get(n)
            desc = what + " " + (f"Round 1: you picked {CH[p['choice']]}" + (f'; "{p["note"]}"' if p["note"] else "") + "."
                                 if p else "Round 1: no pick; three fresh ideas.")
            if n.startswith("hud_"):
                desc += " A 14x14 buff-bar icon, shown at its size."
            imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
            if now(n):
                imgs["now"] = sp.uri(now(n))
            its.append({"id": "specs2." + n, "name": lab, "key": n, "desc": desc, "imgs": imgs})
        groups.append({"id": "specs2." + key, "title": title + ", round 2", "items": its})
    tpl = (sp.HERE / "picker_tpl.html").read_text(encoding="utf-8").replace("Skill Icon Picks", "Spec Icon Picks")
    assert "/*DATA*/null" in tpl
    page = OUT / "picker.html"
    page.write_text(tpl.replace("/*DATA*/null", json.dumps(groups)), encoding="utf-8")
    return page


def pick(fn):
    """The chosen idea of each icon to art/specs/override/<name>.png; "keep" leaves the round-1 one."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    sp.OVR.mkdir(parents=True, exist_ok=True)
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specs2.") else k
        c = v.get("choice") if isinstance(v, dict) else v
        if n not in ALL2 or c not in ("a", "b", "c"):
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
        render([x for x in a if not x.startswith("--")] or list(ALL2))
        if "--picker" in a:
            print(picker())
