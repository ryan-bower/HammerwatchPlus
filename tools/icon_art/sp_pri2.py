"""The Devil Forgemaster's icons, round 2. Two parts:
- The second pass on the user's round-1 picks (sp_pri.py): three ideas each, built on the
  pick and its note, with the pick ("now") beside them.
- Round 1 of the icons round 1 left out: the spec emblem, the four orbs (Ravenous Lunge, Rot
  Bloom, Pyre Sacrifice, Deeper Depravity) and the status shown while you eat a body.

    python tools/icon_art/sp_pri2.py [names...]   # out/specs/pri2/<name>_<a|b|c>.png, out/specs/pri2/sheet_priest.png
    python tools/icon_art/sp_pri2.py --picker     # also out/specs/pri2/picker.html, ids specsP2.<name>
    python tools/icon_art/sp_pri2.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                  # {"specsP2.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
from vm import arc, dagger, book, drop, hammer, cloud
from sp_r3 import crown
import sp
import sp_pri
from sp_pri import NECRO, BODY, HERESY, HERESY5, IRON, DEMON, lying, halo, slit_eye

OUT = sp.HERE / "out" / "specs" / "pri2"
R1 = sp.HERE / "out" / "specs" / "pri"
# The user's round-1 picks (the picker's specsP.<name>, 2026-10-22).
PICKS = {"pri_necrotic_resurrection": ("a", ""), "pri_sacrificial_penance": ("a", ""),
         "pri_call_of_heresy": ("c", "but replace the sigil with an eye"),
         "hud_heresy": ("b", ""), "hud_heresy_5": ("b", "")}

GORE = R("140406", "3a0a0c", "6a1418", "a0222a", "d04a4a", "f08a80")          # raw flesh, the maw
ROTG = R("0a1006", "1a2a0e", "2e4a16", "4e7220", "84a830", "c8e070", "f4ffd0")   # rot: yellow-green
SOOT = R("0a0808", "1a1414", "2e2626", "463a3a", "64585a")
GRAVE = R("0c0a08", "1c1812", "2e281e", "463c2e", "62563e")                   # dark grave earth


# ---------------------------------------------------------------- objects
def maw(ic, cx, cy, s=1.0, open_=1.0, seed=0):
    """An open mouth from the front: fleshy lips, a dark throat, fangs top and bottom."""
    ic.solid(ellipse(cx, cy, 7.4 * s, (3.6 + 2.0 * open_) * s), GORE, base=2.6, seed=seed)
    inner = ellipse(cx, cy + 0.3 * s, 5.8 * s, (2.0 + 2.0 * open_) * s)
    ic.paint(inner, lambda x, y, d: (22, 4, 8))
    top, bot = cy - (1.7 + 1.9 * open_) * s, cy + (2.2 + 1.9 * open_) * s
    fangs = []
    for k, x in enumerate((-4.2, -2.1, 0, 2.1, 4.2)):
        L = (2.6 if k in (0, 4) else 1.7) * s
        fangs.append(poly([(cx + (x - 0.85) * s, top), (cx + (x + 0.85) * s, top), (cx + x * s, top + L)]))
        if k in (1, 2, 3):
            fangs.append(poly([(cx + (x - 0.75) * s, bot), (cx + (x + 0.75) * s, bot), (cx + x * s, bot - 1.4 * s)]))
    ic.solid(inter(union(*fangs), ellipse(cx, cy, 7.4 * s, (3.6 + 2.0 * open_) * s)), BONE, base=4.0, spread=0.8, seed=seed + 1)


def anvil(ic, cx, cy, s=1.0, rmp=IRON, seed=0):
    """A smith's anvil side on: the face and horn, the waist, the foot."""
    f = union(box(cx + 1.2 * s, cy - 2.4 * s, 6.0 * s, 1.5 * s, 0, 0.3),
              poly([(cx - 4.8 * s, cy - 3.9 * s), (cx - 10.0 * s, cy - 3.2 * s), (cx - 4.8 * s, cy - 0.9 * s)]),
              box(cx + 1.2 * s, cy + 0.6 * s, 2.8 * s, 1.8 * s),
              poly([(cx - 3.2 * s, cy + 4.6 * s), (cx + 5.6 * s, cy + 4.6 * s), (cx + 4.0 * s, cy + 2.2 * s), (cx - 1.6 * s, cy + 2.2 * s)]))
    ic.solid(f, rmp, seed=seed, base=2.6)


def logs(ic, cx, by, s=1.0, seed=0):
    """A pyre's stacked logs, ends toward you."""
    for k, (x, y) in enumerate(((-4.6, 0), (0, 0), (4.6, 0), (-2.3, -3.2), (2.3, -3.2))):
        ic.solid(circle(cx + x * s, by + y * s - 1.6 * s, 2.0 * s), WOOD, seed=seed + k, base=2.6)
        ic.solid(circle(cx + x * s, by + y * s - 1.6 * s, 0.9 * s), WOOD, seed=seed + k + 5, base=4.0, spread=0.4)


def spore_burst(ic, cx, cy, r, rmp=ROTG, n=8, seed=0):
    for k in range(n):
        a = math.radians(k * 360 / n + seed * 13)
        rr = r * (0.75 + 0.25 * h2(k, seed, 5))
        ic.energy(circle(cx + math.cos(a) * rr, cy + math.sin(a) * rr, 0.8 + 0.5 * h2(k, seed, 9)), rmp, falloff=0.8)


# ================================================================ second pass on the picks
def pri_necrotic_resurrection():
    # the pick: a gray body climbing out of its grave, green wisps. Closer, one hand on the edge;
    # the same figure cleaner, on dark earth with a green seam; behind it a tombstone and green light
    A = G("priest", (12, 16))
    A.glow(12, 17, 10, "40a070", 0.7)
    A.solid(ellipse(12, 23, 12, 5.0), GRAVE, base=2.0, spread=1.0)
    A.energy(ellipse(12, 19.6, 9.0, 1.2), NECRO, falloff=0.9)
    head = union(circle(12, 9.0, 3.6), box(12, 16.4, 5.6, 3.6, 0, 1.6))
    A.solid(cut(head, ellipse(12, 23, 12, 4.4)), BODY, base=2.6)
    A.paint(union(circle(10.6, 8.8, 0.7), circle(13.4, 8.8, 0.7)), lambda x, y, d: NECRO[6])
    A.solid(union(seg(6.0, 17.6, 3.6, 13.4, 1.1), seg(18.0, 17.6, 21.0, 19.2, 1.1)), BODY, base=2.2, seed=3)
    for x in (3.0, 4.0, 5.0):
        A.solid(seg(3.8, 13.0, x - 0.4, 10.8, 0.45), BODY, base=3.0, seed=4)
    for k, (x, y) in enumerate(((19, 9), (6.5, 6), (20.5, 4))):
        A.energy(path([(x, y + 3), (x + 0.6, y)], 0.6, 0.2), NECRO, falloff=0.4)
    B = G("priest", (12, 14))
    B.glow(12, 15, 9, "40a070", 0.45)
    fig = union(circle(12, 6.8, 2.6), box(12, 13, 3.2, 4.4, 0, 1.4), seg(9.4, 10.2, 6.0, 4.6, 1.0), seg(14.6, 10.6, 17.4, 14.6, 1.0))
    B.solid(cut(fig, ellipse(12, 22, 11, 4.6)), BODY, base=2.6)
    B.px([(11, 7), (13, 7)], NECRO[6])
    B.solid(ellipse(12, 22.2, 11, 4.0), GRAVE, base=2.0, spread=1.0)
    B.energy(cut(ellipse(12, 18.6, 9.4, 1.4), ellipse(12, 18.0, 9.0, 0.9)), NECRO, falloff=0.6)
    for k, (x, y) in enumerate(((4, 15), (20, 13.5), (6.6, 10))):
        B.energy(path([(x, y), (x + (1 if k % 2 else -1) * 0.8, y - 3.4)], 0.7, 0.2), NECRO, falloff=0.5)
    C = G("priest", (12, 10))
    C.rays(12, 18, NECRO, n=7, lo=0, hi=2.4, width=0.35)
    stone = union(box(16.6, 10.6, 4.0, 4.6, 0, 0.4), circle(16.6, 6.4, 4.0))
    C.solid(stone, R("0e0c0a", "221e1a", "3a342c", "56504a", "7a7468"), base=2.2)
    C.paint(union(box(16.6, 7.4, 0.4, 2.2), box(16.6, 6.6, 1.5, 0.4)), lambda x, y, d: (24, 20, 18))
    fig = union(circle(9, 8.6, 2.4), box(9, 14.4, 3.0, 4.2, 0, 1.3), seg(6.6, 11.8, 3.2, 7.4, 0.95), seg(11.4, 11.8, 13.6, 8.0, 0.95))
    C.solid(cut(fig, ellipse(12, 23, 12, 4.4)), BODY, base=2.6)
    C.px([(8, 8), (10, 8)], NECRO[6])
    C.solid(ellipse(12, 23, 12, 4.0), GRAVE, base=2.0, spread=1.0)
    return A, B, C


def pri_sacrificial_penance():
    # the pick: a knife over the body, gold light. A gold ring round the strike; a gilded hilt
    # and a drop of blood; the blade sunk in, gold rays rising
    A = G("priest", (12, 10))
    A.glow(12, 16, 8, "e8c850", 0.55)
    A.energy(halo(12, 16.4, 7.4, 2.2, 0.9), HOLY, falloff=0.5)
    lying(A, 12, 19.6, 1.15)
    dagger(A, 13, 7.6, -100, 1.0, STEEL, LEATHER, GOLD)
    for k, (x, y, r) in enumerate(((5, 10, 0.6), (19.5, 8.5, 0.7), (7.5, 5, 0.5), (18, 3.5, 0.5))):
        A.energy(circle(x, y, r), HOLY, falloff=r)
    B = G("priest", (12, 8))
    B.glow(12, 17, 8, "e8c850", 0.6)
    lying(B, 12, 19.6, 1.15)
    dagger(B, 12, 7.6, -90, 1.05, STEEL, R("2a0a0a", "5a1414", "8a2020", "b83030"), GOLD)
    B.energy(drop(12, 15.4, 1.1), CRIMSON, falloff=0.9)
    B.energy(union(seg(9.4, 16.6, 7.0, 15.2, 0.4), seg(14.6, 16.6, 17.0, 15.2, 0.4)), HOLY, falloff=0.4)
    C = G("priest", (12, 6))
    C.rays(12, 17, HOLY, n=9, lo=0, hi=2.6, width=0.3)
    body = lying(C, 12, 19.6, 1.15)
    dagger(C, 12, 13.0, -90, 1.0, STEEL, LEATHER, GOLD)
    C.energy(circle(12, 18.4, 1.2), HOLY, falloff=1.0)
    return A, B, C


def pri_call_of_heresy():
    # the pick: the heretic's book open, the sigil above it, now an eye (the note). An eye
    # floating over the pages; the eye drawn across the open spread; the eye in a ring, weeping
    COVER = R("10060a", "2a0e1a", "48182e", "6a2442", "8e3458")
    A = G("priest", (12, 8))
    A.glow(12, 8, 9, "9a3a8a", 0.55)
    book(A, 12, 17, 1.0, COVER, PAPER, open_=True)
    for k in range(6):
        a = math.radians(-90 + (k - 2.5) * 30)
        A.energy(seg(12 + math.cos(a) * 6.4, 7.4 + math.sin(a) * 5.0, 12 + math.cos(a) * 8.4, 7.4 + math.sin(a) * 6.4, 0.4, 0.2), HERESY, falloff=0.3)
    slit_eye(A, 12, 7.4, 1.25, HERESY, open_=0.9)
    B = G("priest", (12, 8))
    B.glow(12, 13, 10, "9a3a8a", 0.4)
    book(B, 12, 15, 1.25, COVER, PAPER, open_=True)
    slit_eye(B, 12, 13.6, 1.05, HERESY, open_=0.85)
    C = G("priest", (12, 8))
    C.glow(12, 8, 9, "9a3a8a", 0.5)
    book(C, 12, 18, 0.95, COVER, PAPER, open_=True)
    C.energy(ring(12, 7.6, 6.2, 0.9), HERESY, falloff=0.4)
    slit_eye(C, 12, 7.6, 0.85, HERESY, open_=0.95)
    C.energy(drop(12.6, 13.6, 0.9), HERESY, falloff=0.7)
    return A, B, C


def hud_heresy():
    # the pick: a purple slit eye. Bigger, filling the icon; with a purple tear; with horned lids
    A = S("priest", (7, 7))
    slit_eye(A, 7, 7, 1.15, HERESY, open_=1.15)
    B = S("priest", (7, 6))
    slit_eye(B, 7, 6, 1.0, HERESY, open_=1.0)
    B.energy(drop(8.6, 11.0, 0.9), HERESY, falloff=0.7)
    C = S("priest", (7, 8))
    for d in (-1, 1):
        C.solid(poly([(7 + d * 2.6, 5.4), (7 + d * 5.4, 1.0), (7 + d * 4.4, 5.6)]), DEMON, base=3.0)
    slit_eye(C, 7, 8, 1.0, HERESY, open_=1.0)
    return A, B, C


def hud_heresy_5():
    # the pick: the eye wide open, red hot, rays round it. Each the same letter as hud_heresy's:
    # bigger with flame rays; a tear of blood; horned lids with a burning crown
    A = S("priest", (7, 7))
    A.glow(7, 7, 7, "f04010", 0.6)
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        A.energy(flame(7 + math.cos(a) * 5.0, 7 + math.sin(a) * 5.0 + 1.0, 0.9, 2.4, 0, k, 1), HERESY5, falloff=0.5)
    slit_eye(A, 7, 7, 1.15, HERESY5, open_=1.3)
    B = S("priest", (7, 6))
    B.glow(7, 6, 6, "f04010", 0.6)
    slit_eye(B, 7, 6, 1.0, HERESY5, open_=1.25)
    B.energy(drop(8.6, 11.0, 0.9), BLOOD, falloff=0.7)
    for k in range(4):
        a = math.radians(-160 + k * 45)
        B.energy(seg(7 + math.cos(a) * 4.6, 6 + math.sin(a) * 3.6, 7 + math.cos(a) * 6.2, 6 + math.sin(a) * 5.4, 0.35, 0.2), HERESY5, falloff=0.3)
    C = S("priest", (7, 8))
    C.energy(flame(7, 6.2, 4.6, 6.0, 0, 3, 3), HERESY5, falloff=1.2)
    for d in (-1, 1):
        C.solid(poly([(7 + d * 2.6, 5.4), (7 + d * 5.4, 1.0), (7 + d * 4.4, 5.6)]), DEMON, base=3.4)
    slit_eye(C, 7, 8.4, 1.0, HERESY5, open_=1.2)
    return A, B, C


# ================================================================ round 1 of the rest
def pri_class():
    # Devil Forgemaster: a gray skull on the anvil, the hammer raised over it; a horned green halo
    # over a hooded face; a broken holy cross with the hammer beside it, in green fire
    A = G("priest", (12, 10))
    A.glow(11, 12, 8, "40a070", 0.45)
    anvil(A, 11, 18.4, 0.95)
    skull(A, 12, 10.6, 0.6, BODY, eyes=NECRO)
    hammer(A, 17.6, 6.4, -120, 0.62, IRON, WOOD)
    for k, (x, y) in enumerate(((5, 9), (19.6, 13.4), (6.4, 4.6))):
        A.energy(circle(x, y, 0.6), NECRO, falloff=0.6)
    B = G("priest", (12, 12))
    hood = union(poly([(12, 10.0), (17.4, 15.0), (19.4, 23.5), (4.6, 23.5), (6.6, 15.0)]), circle(12, 14.0, 4.6))
    B.solid(hood, R("0a0608", "1e1418", "34262c", "4e3a42", "6e5660"), base=2.2)
    B.paint(ellipse(12, 15.6, 2.7, 3.1), lambda x, y, d: (6, 4, 6))
    B.px([(11, 15), (13, 15)], NECRO[6])
    for d in (-1, 1):
        B.solid(poly([(12 + d * 3.4, 7.6), (12 + d * 8.0, 1.8), (12 + d * 6.4, 7.8)]), DEMON, base=3.0)
    B.energy(halo(12, 7.4, 6.2, 1.8, 1.1), NECRO, falloff=0.6)
    C = G("priest", (12, 12))
    C.energy(flame(12, 23, 8.4, 20, 0, 2, 3), NECRO, falloff=2.6)
    cross = union(box(9, 13, 1.2, 7.4), box(9, 9.6, 4.4, 1.2))
    C.solid(cut(cross, seg(6.6, 15.4, 11.6, 13.0, 0.5)), GOLD, base=2.8)
    hammer(C, 16.2, 13, -70, 0.78, IRON, WOOD)
    return A, B, C


def pri_ravenous_lunge():
    # the lunge lands and hits: a maw lunging with an impact ring; a body leaping onto its
    # prey, streaks behind; bite marks over a shock ring
    A = G("priest", (12, 12))
    A.energy(ring(15, 14, 8.6, 0.8), BLOOD, falloff=0.4)
    for k, y in enumerate((8, 12, 16)):
        A.streak(1, y + 1, 6, y, 0.8, R("1a0406", "460a0e", "801418"))
    maw(A, 14, 13, 1.0, 1.0)
    B = G("priest", (12, 14))
    B.solid(ellipse(16, 20.5, 6.4, 1.6), SOOT, base=2.0)
    lying(B, 16, 19.4, 0.8)
    fig = union(circle(9.6, 6.6, 2.2), ellipse(12.2, 10.2, 3.6, 2.2, 35), seg(13.6, 11.8, 17, 13.2, 0.9), seg(8.6, 9.0, 4.6, 12.4, 0.9))
    B.solid(fig, R("0a0608", "1e1418", "34262c", "4e3a42", "6e5660"), base=2.6)
    for k, (x0, y0) in enumerate(((1, 2), (1, 6), (3, 10))):
        B.streak(x0, y0, x0 + 5, y0 + 2.4, 0.7, R("2a1a2a", "4e3a4e", "7a5a7a"))
    for k in range(5):
        a = math.radians(200 + k * 35)
        B.energy(seg(16 + math.cos(a) * 3.6, 18.4 + math.sin(a) * 3.0, 16 + math.cos(a) * 6.2, 18.4 + math.sin(a) * 4.8, 0.45, 0.2), HOLY, falloff=0.3)
    C = G("priest", (12, 12))
    C.energy(ring(12, 12, 9.4, 1.0), R("1a0604", "4a0e06", "8a1e08", "c84010"), falloff=0.4)
    for k in range(3):
        x = 7.4 + k * 4.6
        C.energy(path([(x + 1.4, 4.6 + abs(k - 1) * 1.2), (x, 12), (x - 1.2, 19.4 - abs(k - 1) * 1.2)], 1.1, 0.3), BLOOD, falloff=0.8)
    return A, B, C


def pri_rot_bloom():
    # a risen summon dies and bursts into poison: a gray body bursting in a green cloud; a rot
    # flower opening from a skull; a ring of spores round a burst
    A = G("priest", (12, 14))
    A.glow(12, 12, 10, "84a830", 0.5)
    for k, (x, y, r) in enumerate(((7, 11, 3.6), (17, 10, 3.8), (12, 6.4, 4.0), (12, 12.6, 3.4))):
        A.energy(circle(x, y, r), R("0a1006", "1a2a0e", "2e4a16", "4e7220", "84a830"), falloff=r * 1.4, seed=k)
    lying(A, 12, 19.6, 1.1)
    for k in range(6):
        a = math.radians(-160 + k * 28)
        A.energy(seg(12 + math.cos(a) * 3.0, 17.6 + math.sin(a) * 2.0, 12 + math.cos(a) * 9.4, 17.6 + math.sin(a) * 8.0, 0.5, 0.2), ROTG, falloff=0.4)
    B = G("priest", (12, 10))
    for k in range(6):
        a = math.radians(-90 + k * 60)
        B.energy(ellipse(12 + math.cos(a) * 5.4, 10 + math.sin(a) * 5.4, 3.0, 1.7, math.degrees(a)), ROTG if k % 2 else R("0c0410", "240a2a", "42124a", "6a1e6a", "9a3a8a"), falloff=1.4)
    skull(B, 12, 11, 0.62, BODY, eyes=ROTG)
    B.solid(path([(12, 15.4), (11.2, 19), (12.6, 23.5)], 0.8, 0.6), R("0a1006", "1a2a0e", "2e4a16"), base=1.6)
    C = G("priest", (12, 12))
    C.glow(12, 12, 9, "84a830", 0.6)
    C.energy(circle(12, 12, 3.0), ROTG, falloff=2.4)
    for k in range(8):
        a = math.radians(k * 45 + 10)
        C.energy(seg(12 + math.cos(a) * 3.6, 12 + math.sin(a) * 3.6, 12 + math.cos(a) * 6.8, 12 + math.sin(a) * 6.8, 0.45, 0.2), ROTG, falloff=0.3)
    spore_burst(C, 12, 12, 9.0, ROTG, 10, 2)
    return A, B, C


def pri_pyre_sacrifice():
    # the pyre burns Heresy away: a body burning on its pyre; the purple eye of Heresy burning up
    # over logs; a brazier with gold fire and purple smoke leaving it
    A = G("priest", (12, 14))
    logs(A, 12, 23.5, 0.95)
    A.energy(flame(12, 17, 8.4, 15, 0, 1, 3), HOLY, falloff=2.4)
    lying(A, 12, 15.8, 0.95)
    for k, (x, y) in enumerate(((5, 4), (18.5, 3))):
        A.energy(path([(x, y + 3), (x + 0.6, y)], 0.6, 0.2), HERESY, falloff=0.4)
    B = G("priest", (12, 14))
    logs(B, 12, 23.5, 0.95)
    B.energy(flame(12, 18, 8.6, 17, 0, 4, 3), FIRE, falloff=2.6)
    slit_eye(B, 12, 9.6, 0.95, HERESY, open_=0.7)
    B.energy(union(seg(5.4, 5.6, 8.0, 8.0, 0.4), seg(18.6, 5.6, 16.0, 8.0, 0.4)), HERESY, falloff=0.3)
    C = G("priest", (12, 14))
    bowl = union(cut(ellipse(12, 15.4, 7.0, 3.6), box(12, 12.0, 8, 3.4)), box(12, 20.6, 1.2, 3.0), box(12, 23.0, 4.0, 0.8))
    C.energy(flame(12, 15.0, 6.4, 11, 0, 2, 3), HOLY, falloff=2.2)
    C.solid(bowl, IRON, base=2.4)
    cloud(C, [(6.6, 4.4, 2.2), (9.4, 3.0, 2.0), (5.0, 6.4, 1.6)], HERESY)
    return A, B, C


def pri_deeper_depravity():
    # more elite and boss bodies, bosses raisable: a crowned gray skull lit green; a hulking
    # horned gray boss rising, small risen behind; a crown dropped on a body
    A = G("priest", (12, 12))
    A.glow(12, 13, 9, "40a070", 0.5)
    skull(A, 12, 14, 0.9, BODY, eyes=NECRO)
    crown(A, 12, 5.4, 0.72, GOLD, R("040c08", "0a2216", "144030", "206a4a", "40a070", "90e0b0"))
    B = G("priest", (12, 12))
    B.glow(12, 12, 10, "40a070", 0.45)
    for x in (4.5, 19.5):
        figure(B, x, 15, 0.55, BODY, base=1.6)
    foe(B, 12, 12, 1.25, BODY)
    B.solid(ellipse(12, 22.6, 11, 2.6), GRAVE, base=2.0)
    for d in (-1, 1):
        B.energy(circle(12 + d * 1.5, 8.2, 0.7), NECRO, falloff=0.6)
    C = G("priest", (12, 10))
    C.glow(12, 15, 8, "40a070", 0.45)
    lying(C, 12, 19.0, 1.15)
    crown(C, 7.4, 13.6, 0.55, GOLD, R("040c08", "0a2216", "144030", "206a4a", "40a070", "90e0b0"))
    for k in range(3):
        C.energy(path([(10 + k * 4, 6.6), (12 + k * 1.5 - 1.5, 10.6)], 0.5, 0.2), NECRO, falloff=0.3)
    return A, B, C


def hud_devouring():
    # eating a body (3 s, abilities blocked, +50 health regen a second): a maw; two fangs
    # dripping; a bitten heart, a green plus beside it
    A = S("priest", (7, 7))
    maw(A, 7, 7, 0.82, 1.0)
    B = S("priest", (7, 5))
    B.solid(union(poly([(2.0, 1.4), (6.0, 1.4), (4.4, 9.0)]), poly([(8.0, 1.4), (12.0, 1.4), (9.6, 9.0)])), BONE, base=3.6)
    B.energy(union(drop(4.4, 11.0, 1.0), drop(9.6, 11.4, 0.9)), BLOOD, falloff=0.7)
    C = S("priest", (7, 7))
    C.solid(cut(heart(6.4, 7.6, 4.6), circle(10.8, 4.0, 2.2), circle(11.6, 7.2, 1.5)), GORE, base=3.0)
    C.energy(union(seg(10.2, 11.0, 13.0, 11.0, 0.5), seg(11.6, 9.6, 11.6, 12.4, 0.5)), LIFE, falloff=0.4)
    return A, B, C


PASS2 = [
    ("pri_necrotic_resurrection", "Necrotic Resurrection (active)", "Second pass on your pick: the gray body climbing out of its grave."),
    ("pri_sacrificial_penance", "Sacrificial Penance (active, at max Favor)", "Second pass on your pick: the knife over the body, gold light."),
    ("pri_call_of_heresy", "Call of Heresy (passive)", "Second pass on your pick, with your note: the sigil over the book is now an eye."),
    ("hud_heresy", "Heresy, below 5 (status)", "Second pass on your pick: the purple slit eye. 14x14, shown at its size; each letter pairs with the 5+ one."),
    ("hud_heresy_5", "Heresy, 5+ (status)", "Second pass on your pick: the red-hot eye. 14x14; each letter pairs with the below-5 one."),
]
NEW = [
    ("pri_class", "Devil Forgemaster (spec emblem)", "The spec's emblem, like the other five 4th specs have."),
    ("pri_ravenous_lunge", "Ravenous Lunge (orb, Call of Heresy)", "Your flesh-eating lunge slams into enemies where you land, damaging them before you eat."),
    ("pri_rot_bloom", "Rot Bloom (orb, Necrotic Resurrection)", "When a risen summon dies, its body bursts, dealing poison damage around it."),
    ("pri_pyre_sacrifice", "Pyre Sacrifice (orb, Necrotic Resurrection)", "Using the pyre reduces your Heresy by 1, then 3."),
    ("pri_deeper_depravity", "Deeper Depravity (orb, Call of Heresy)", "More elite intact bodies; at its top level, boss bodies, which you can raise."),
    ("hud_devouring", "Devouring a body (status)",
     "Shown during the 3 s lunge-and-eat channel: abilities blocked, +50 health regen a second. 14x14, shown at its size."),
]
ALL = {n: (lab, what) for n, lab, what in PASS2 + NEW}


def now(n):
    if n in PICKS:
        return Image.open(R1 / f"{n}_{PICKS[n][0]}.png").convert("RGBA")
    return None


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    rows = [(n, out[n] + ([now(n)] if now(n) else [])) for n, _, _ in PASS2 + NEW if n in out]
    if rows:
        sheet(rows, OUT / "sheet_priest.png")
    return out


def picker():
    groups = []
    for gid, title, items in (("pass2", "Priest: Devil Forgemaster, second pass on your picks", PASS2),
                              ("new", "Priest: Devil Forgemaster, the rest (emblem, orbs, status)", NEW)):
        its = []
        for n, lab, what in items:
            imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
            if now(n):
                imgs["now"] = sp.uri(now(n))
            its.append({"id": "specsP2." + n, "name": lab, "key": n, "desc": what, "imgs": imgs})
        groups.append({"id": "specsP2." + gid, "title": title, "items": its})
    tpl = (sp.HERE / "picker_tpl.html").read_text(encoding="utf-8").replace("Skill Icon Picks", "Spec Icon Picks")
    assert "/*DATA*/null" in tpl
    page = OUT / "picker.html"
    page.write_text(tpl.replace("/*DATA*/null", json.dumps(groups)), encoding="utf-8")
    return page


def pick(fn):
    """The chosen idea of each icon to art/specs/override/<name>.png."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    sp.OVR.mkdir(parents=True, exist_ok=True)
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specsP2.") else k
        c = v.get("choice") if isinstance(v, dict) else v
        if n not in ALL or c not in ("a", "b", "c"):
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
        render([x for x in a if not x.startswith("--")] or list(ALL))
        if "--picker" in a:
            print(picker())
