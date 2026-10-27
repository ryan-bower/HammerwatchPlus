"""The Paladin's 4th specialization, Generosity (Pelor): three ideas each for the emblem, its two
skills, the four orbs and the Pelor's Blessing stack's buff-bar icon. The designs are in the
planner (planner/data/skills/paladin-spec4-*.json, planner/data/mods/); none of the icons exist
in game yet.

    python tools/icon_art/sp_pal.py [names...]   # out/specs/pal/<name>_<a|b|c>.png, out/specs/pal/sheet_paladin.png
    python tools/icon_art/sp_pal.py --picker     # also out/specs/pal/picker.html, ids specsPal.<name>
    python tools/icon_art/sp_pal.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                 # {"specsPal.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
from vm import arc, hand_open, hammer, shield, sun, star, hourglass, drop
import sp

OUT = sp.HERE / "out" / "specs" / "pal"
sp.GROUNDS["paladin"] = ("0e0a04", "2a1e0a")   # a warm, dim temple

SUNR = R("2a1404", "6a3a08", "b8700c", "f0a818", "ffd860", "fff4c0", "ffffff")      # Pelor's sun
BEAM = R("3a2a08", "806010", "c8a028", "f0d860", "fff2b0", "ffffff", "ffffff")     # the pillar of light
PALE = R("0c0a08", "201c16", "3a342a", "5a5244", "847a66", "b4aa92")               # a held, stunned enemy
SCALE_R = R("140404", "3a0806", "6e1208", "a8240e", "dc4a1c", "ff8a4a")
SCALE_B = R("040814", "081838", "102e66", "1e4c9a", "3a78cc", "7ab0f0")
DRAGON = R("0e0806", "2a1810", "4a2c18", "704424", "9a6436", "c8925a")


# ---------------------------------------------------------------- objects
def pillar(ic, cx, top, bottom, w, rmp=BEAM, fall=1.6):
    """A beam of light straight down, widening a little toward the ground, with a pool of light."""
    ic.glow(cx, bottom - 1, w * 2.6, rmp[3], 0.6)
    ic.energy(poly([(cx - w * 0.6, top), (cx + w * 0.6, top), (cx + w, bottom), (cx - w, bottom)]), rmp, falloff=fall)
    ic.energy(ellipse(cx, bottom, w * 1.9, w * 0.55), rmp, falloff=0.9)


def rays(ic, cx, cy, r0, r1, n, rmp=SUNR, w=0.5, a0=-90, fall=0.4):
    for k in range(n):
        a = math.radians(a0 + k * 360 / n)
        ic.energy(seg(cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * r1, cy + math.sin(a) * r1, w, w * 0.3),
                  rmp, falloff=fall)


def sun_face(ic, cx, cy, r, rmp=SUNR, n=12):
    """Pelor's sun: a disc with straight and wavy rays alternating, and a calm face."""
    ic.glow(cx, cy, r * 2.4, rmp[4], 0.6)
    rays(ic, cx, cy, r * 1.05, r * 1.85, n // 2, rmp, w=r * 0.22)
    for k in range(n // 2):   # the wavy ones between
        a = math.radians(-90 + 180 / (n // 2) * (2 * k + 1))
        pts = [(cx + math.cos(a + 0.18 * math.sin(t * 3)) * (r * (1.05 + 0.55 * t)), cy + math.sin(a + 0.18 * math.sin(t * 3)) * (r * (1.05 + 0.55 * t)))
               for t in (0, 0.33, 0.66, 1.0)]
        ic.energy(path(pts, r * 0.16, r * 0.05), rmp, falloff=0.35)
    ic.energy(circle(cx, cy, r), rmp, falloff=r * 0.75)
    dark = lambda x, y, d: (120, 60, 8)
    ic.paint(union(arc(cx - r * 0.38, cy - r * 0.05, r * 0.2, r * 0.12, 200, 340),
                   arc(cx + r * 0.38, cy - r * 0.05, r * 0.2, r * 0.12, 200, 340),
                   arc(cx, cy + r * 0.2, r * 0.36, r * 0.12, 30, 150)), dark)


def stunned_foe(ic, cx, cy, s=1.0, rmp=PALE, seed=0):
    """An enemy frozen in the light, its eyes gone white, stars over its head."""
    f = foe(ic, cx, cy, s, rmp, seed)
    for d in (-1, 1):
        ic.px([(int(cx + d * 1.2 * s), int(cy - 3.2 * s))], (255, 248, 220))
    return f


def coin(ic, cx, cy, r, rmp=GOLD, seed=0):
    ic.solid(circle(cx, cy, r), rmp, seed=seed, base=3.0)
    ic.solid(circle(cx, cy, r * 0.62), rmp, seed=seed + 1, base=2.2)


def eye(ic, cx, cy, s, iris=SUNR, seed=0, open_=1.0):
    f = lambda x, y: (abs((y - cy) / s) - 2.8 * open_ * max(0, 1 - ((x - cx) / (6 * s)) ** 2)) * s
    ic.solid(f, R("1a1610", "4a4230", "8a8068", "c8c0a8", "f0ecdc"), base=3.2, spread=0.8, seed=seed, rim=0.4)
    ic.energy(inter(f, circle(cx, cy, 2.2 * s)), iris, falloff=1.4 * s, seed=seed)
    return f


def scale(ic, cx, cy, s, rmp, seed=0):
    """A dragon scale: a pointed shield shape with a ridge down the middle."""
    f = poly([(cx, cy - 7 * s), (cx + 5.6 * s, cy - 2.6 * s), (cx + 4.6 * s, cy + 3.6 * s), (cx, cy + 7.4 * s),
              (cx - 4.6 * s, cy + 3.6 * s), (cx - 5.6 * s, cy - 2.6 * s)])
    ic.solid(f, rmp, seed=seed, base=2.4)
    ic.solid(seg(cx, cy - 5.6 * s, cx, cy + 5.8 * s, 0.7 * s, 0.3 * s), rmp, seed=seed + 1, base=3.6)
    return f


def talon(ic, cx, cy, s, rmp=DRAGON, claw=BONE, seed=0):
    """A dragon's foot from above: a palm and three hooked claws reaching up."""
    ic.solid(ellipse(cx, cy + 3.6 * s, 4.6 * s, 3.6 * s), rmp, seed=seed, base=2.4)
    for k, a in enumerate((-125, -90, -55)):
        r = math.radians(a)
        x0, y0 = cx + math.cos(r) * 3.0 * s, cy + 3.0 * s + math.sin(r) * 3.0 * s
        x1, y1 = cx + math.cos(r) * 7.0 * s, cy + 3.0 * s + math.sin(r) * 7.6 * s
        ic.solid(seg(x0, y0, x1, y1, 1.4 * s, 1.0 * s), rmp, seed=seed + k + 1, base=2.6)
        hook = math.radians(a + (25 if a < -90 else -25 if a > -90 else 0))
        ic.solid(seg(x1, y1, x1 + math.cos(hook) * 2.6 * s, y1 + math.sin(hook) * 2.6 * s, 0.9 * s, 0.15 * s),
                 claw, seed=seed + k + 5, base=3.4)


def pips(ic, cx, cy, r, lit, n=10, rmp=SUNR, dim=None, pr=0.75):
    """The ten Blessing stacks as beads round a ring; the first `lit` of them glowing."""
    dim = dim or R("0e0a04", "2a1e0a", "4a3a1a")
    for k in range(n):
        a = math.radians(-90 + k * 360 / n)
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        if k < lit:
            ic.energy(circle(x, y, pr), rmp, falloff=pr)
        else:
            ic.solid(circle(x, y, pr * 0.8), dim, base=2.0)


# ---------------------------------------------------------------- the emblem
BEARD = R("2a2824", "5a5650", "8e887e", "c4beb2", "e8e4dc", "ffffff")     # an old man's white beard
ROBE = R("1a1408", "3a2e14", "6a5428", "a08848", "d0bc80", "f4ead0")      # a cream priest's robe
SHADOW = R("020204", "06050a", "0c0a14", "141020", "1e182e", "2a2240")    # an enemy's shadow


def elder(ic, cx, cy, s=1.0, seed=0, hood=True):
    """An old man's head and shoulders: a cream hood and robe, a lined face, bushy white brows and a
    long white beard falling to a point. (cx, cy) the face. Returns the beard's sdf."""
    if hood:
        ic.solid(union(ellipse(cx, cy - 0.4 * s, 4.4 * s, 4.8 * s),
                       poly([(cx - 7.0 * s, cy + 12 * s), (cx - 4.6 * s, cy + 2.0 * s), (cx + 4.6 * s, cy + 2.0 * s),
                             (cx + 7.0 * s, cy + 12 * s)])), ROBE, seed=seed, base=2.6)
    ic.solid(ellipse(cx, cy, 2.9 * s, 3.3 * s), SKIN, seed=seed + 1, base=3.2)
    b = union(poly([(cx - 3.0 * s, cy + 0.6 * s), (cx + 3.0 * s, cy + 0.6 * s), (cx + 2.6 * s, cy + 5.6 * s),
                    (cx + 0.3 * s, cy + 11.0 * s), (cx - 0.3 * s, cy + 11.0 * s), (cx - 2.6 * s, cy + 5.6 * s)]),
              ellipse(cx, cy + 1.4 * s, 3.1 * s, 1.6 * s))
    ic.solid(b, BEARD, seed=seed + 2, base=3.4, spread=1.2)
    for k in range(3):   # strands down the beard
        x = cx + (k - 1) * 1.1 * s
        ic.shade(seg(x, cy + 3.0 * s, cx + (k - 1) * 0.35 * s, cy + 9.6 * s, 0.22 * s), 0.25)
    ic.solid(union(seg(cx - 2.6 * s, cy - 1.4 * s, cx - 0.6 * s, cy - 1.0 * s, 0.55 * s),
                   seg(cx + 0.6 * s, cy - 1.0 * s, cx + 2.6 * s, cy - 1.4 * s, 0.55 * s)), BEARD, seed=seed + 3, base=4.2)
    for d in (-1, 1):
        ic.px([(int(cx + d * 1.4 * s), int(cy - 0.3 * s))], (40, 24, 12))
    ic.solid(seg(cx - 1.6 * s, cy + 0.7 * s, cx + 1.6 * s, cy + 0.7 * s, 0.5 * s), BEARD, seed=seed + 4, base=4.4)  # the moustache
    return b


def raised_hand(ic, cx, cy, s=1.0, sleeve=ROBE, seed=0):
    """A hand raised palm out in blessing, two fingers up, with its sleeve below."""
    ic.solid(seg(cx + 1.4 * s, cy + 7.6 * s, cx, cy + 2.0 * s, 1.5 * s, 1.1 * s), sleeve, seed=seed, base=2.8)
    hand_open(ic, cx, cy, 0.55 * s, SKIN, seed=seed + 1)


def shadow_foe(ic, cx, cy, s=1.0, seed=0, eyes=True):
    """An enemy made of shadow: the hunched horned shape in near-black, red slit eyes, wisps
    trailing from its edge."""
    f = union(ellipse(cx, cy + 2 * s, 5.2 * s, 4.2 * s), circle(cx, cy - 3 * s, 3.0 * s),
              poly([(cx - 2.6 * s, cy - 4.6 * s), (cx - 4.4 * s, cy - 8.2 * s), (cx - 1.2 * s, cy - 5.6 * s)]),
              poly([(cx + 2.6 * s, cy - 4.6 * s), (cx + 4.4 * s, cy - 8.2 * s), (cx + 1.2 * s, cy - 5.6 * s)]),
              seg(cx - 4.6 * s, cy + 4.6 * s, cx - 6.4 * s, cy + 6.6 * s, 0.9 * s, 0.2 * s),
              seg(cx + 4.6 * s, cy + 4.6 * s, cx + 6.6 * s, cy + 6.2 * s, 0.9 * s, 0.2 * s))
    ic.solid(f, SHADOW, seed=seed, base=2.0, rim=0.5)
    if eyes:
        for d in (-1, 1):
            ic.energy(seg(cx + d * 0.7 * s, cy - 3.3 * s, cx + d * 1.9 * s, cy - 3.0 * s, 0.4 * s, 0.25 * s), HELL, falloff=0.45)
    return f


def flat_shadow(ic, cx, cy, s=1.0):
    """An enemy's shadow lying on the ground: the horned shape squashed flat and dark."""
    f = union(ellipse(cx, cy, 6.4 * s, 2.0 * s), ellipse(cx - 6.0 * s, cy - 0.2 * s, 2.6 * s, 1.5 * s),
              poly([(cx - 7.6 * s, cy - 1.0 * s), (cx - 10.6 * s, cy - 2.4 * s), (cx - 7.8 * s, cy + 0.2 * s)]),
              poly([(cx - 7.4 * s, cy + 0.8 * s), (cx - 10.4 * s, cy + 1.8 * s), (cx - 7.2 * s, cy + 1.6 * s)]))
    ic.solid(f, SHADOW, base=1.4, rim=0.3)
    return f


def pal_class():
    # Generosity, Pelor's paladin: the sun shield; the hammer raised before the sun; the sun's face
    A = G("paladin", (12, 10))
    A.glow(12, 11, 10, "f0a818", 0.45)
    shield(A, 12, 11, 1.05, GOLD, face=R("2a1404", "5a3008", "8a4c10", "b06818"), boss=None)
    sun_face(A, 12, 10, 2.8, SUNR, n=8)
    B = G("paladin", (12, 8))
    sun_face(B, 12, 8.5, 4.2, SUNR)
    hammer(B, 12.5, 15.5, -90, 1.05, GOLD, WOOD)
    C = G("paladin", (12, 12))
    sun_face(C, 12, 12, 5.0, SUNR)
    return A, B, C


# ---------------------------------------------------------------- skills
def pal_pelors_fury():
    # round 2 (the user: "a light beam striking a shadow of an enemy"): a beam from the sky striking a
    # shadow-enemy, the light breaking round it; a beam hitting an enemy's shadow on the ground, the
    # shadow pinned; a diagonal beam searing a shadow-enemy that recoils
    A = G("paladin", (12, 3))
    shadow_foe(A, 12, 15.4, 1.05, seed=1)
    pillar(A, 12, 0, 13.6, 2.6, fall=1.4)
    A.energy(star(12, 12.6, 1.2, 6.2, 6, -90), BEAM, falloff=1.0)
    for x, y in ((5.4, 10.4), (18.6, 10.0), (4.4, 15.0), (19.6, 15.6)):
        A.energy(circle(x, y, 0.55), SUNR, falloff=0.5)
    B = G("paladin", (9, 3))
    # the shadow lies dark on a pool of light, so it reads; the beam lands on its head
    B.glow(12, 18, 9, "ffd860", 0.5)
    B.energy(ellipse(12.4, 18.4, 10.4, 3.8), SUNR, falloff=2.6)
    flat_shadow(B, 15.4, 18.4, 0.95)
    pillar(B, 9.4, 0, 17.8, 2.0, fall=1.3)
    B.energy(star(9.4, 17.6, 0.8, 4.2, 6, -90), BEAM, falloff=0.8)
    C = G("paladin", (4, 3))
    shadow_foe(C, 15.0, 15.6, 1.0, seed=2)
    C.energy(seg(2.0, 0.0, 14.0, 12.4, 2.1, 1.2), BEAM, falloff=1.8)
    C.glow(14, 12, 6, "fff2b0", 0.7)
    C.energy(star(14.0, 12.4, 1.0, 5.0, 5, -60), BEAM, falloff=0.8)
    for x, y in ((19.6, 9.0), (21.0, 13.6), (18.4, 6.6)):
        C.energy(circle(x, y, 0.5), SUNR, falloff=0.45)
    return A, B, C


def pal_pelors_blessing():
    # round 2 (the user: "an old man with a long beard giving a blessing of light"): the elder's
    # raised hand under a sun; the elder blessing a kneeling figure with light from his palm; the
    # elder's face haloed by the sun, both hands raised
    A = G("paladin", (17, 4))
    A.glow(17, 5, 7, "ffd860", 0.7)
    elder(A, 10, 9, 1.0, seed=1)
    raised_hand(A, 17.4, 7.6, 1.0, seed=4)
    sun(A, 17.4, 2.8, 1.9, SUNR, 8)
    for x, y in ((21.4, 9.6), (14.6, 3.6), (21.0, 4.4)):
        A.energy(circle(x, y, 0.55), SUNR, falloff=0.55)
    B = G("paladin", (12, 6))
    elder(B, 8.4, 6.6, 0.82, seed=2)
    raised_hand(B, 14.6, 6.0, 0.8, seed=5)
    B.energy(poly([(14.4, 7.8), (16.2, 7.8), (21.6, 18.0), (12.4, 18.0)]), BEAM, falloff=2.2)
    B.glow(17, 14, 6, "fff2b0", 0.5)
    figure(B, 17.0, 17.4, 0.62, ALLY, seed=3)
    C = G("paladin", (12, 7))
    C.glow(12, 7, 11, "ffd860", 0.6)
    rays(C, 12, 7, 6.6, 10.8, 12, SUNR, 0.5, fall=0.35)
    C.energy(ring(12, 7, 6.0, 0.55), SUNR, falloff=0.6)
    elder(C, 12, 8.6, 1.0, seed=6, hood=False)
    for d in (-1, 1):
        raised_hand(C, 12 + d * 7.6, 12.0, 0.8, sleeve=ROBE, seed=7 + d)
    return A, B, C


def pal_pf_blinding_sun():
    # at the end of the channel the target is blinded: the sun flaring over a white-eyed enemy; an
    # eye seared shut by a starburst; a sun eclipsing an eye
    A = G("paladin", (12, 4))
    sun(A, 12, 4.4, 2.8, BEAM, 12)
    A.glow(12, 5, 10, "fff2b0", 0.5)
    stunned_foe(A, 12, 16, 1.05)
    A.paint(box(12, 12.8, 3.4, 0.7), lambda x, y, d: (255, 240, 200))
    B = G("paladin", (12, 12))
    eye(B, 12, 12, 1.25, SUNR, open_=0.55)
    B.energy(star(12, 12, 1.4, 9.5, 4, -90), BEAM, falloff=1.2)
    B.energy(star(12, 12, 0.9, 6.0, 4, -45), BEAM, falloff=0.8)
    C = G("paladin", (12, 8))
    eye(C, 12, 17.0, 1.25, SUNR)
    C.paint(box(12, 13.6, 8, 2.0), lambda x, y, d: (14, 10, 4))
    sun_face(C, 12, 7.6, 3.4, BEAM, n=12)
    for d in (-1, 1):
        C.energy(seg(12 + d * 2.4, 11.4, 12 + d * 5.0, 15.6, 0.5, 0.2), BEAM, falloff=0.4)
    return A, B, C


def pal_pf_holy_sacrifice():
    # the held enemy dies in the light: halves the cooldown and returns stacks: a skull in the
    # pillar breaking into gold motes; an hourglass halved by a beam; a falling foe with three
    # stacks rising from it
    A = G("paladin", (12, 4))
    pillar(A, 12, 0, 22, 3.6, fall=1.2)
    skull(A, 12, 14, 0.78, BONE, eyes=SUNR)
    for k, (x, y, r) in enumerate(((7, 9, 0.7), (17, 8, 0.7), (9, 4, 0.6), (15.5, 3.5, 0.6), (12, 6.4, 0.5))):
        A.energy(circle(x, y, r), SUNR, falloff=r)
    B = G("paladin", (12, 12))
    hourglass(B, 12, 12, 1.0, GOLD, SUNR, t=0.5)
    B.energy(seg(2, 20, 22, 4, 0.9, 0.9), BEAM, falloff=1.0)
    C = G("paladin", (12, 6))
    pillar(C, 12, 0, 22, 2.8, fall=1.2)
    lying = union(circle(5.8, 19.4, 2.0), ellipse(11.4, 20, 3.8, 2.1), seg(14.6, 19.4, 19.6, 19.8, 1.0))
    C.solid(lying, PALE, base=2.2)
    for k in range(3):
        C.energy(circle(12, 13.4 - k * 4.2, 1.2 - k * 0.15), SUNR, falloff=1.0)
    return A, B, C


# ---------------------------------------------------------------- Pelor's Blessing orbs
def pal_pb_display_of_generosity():
    # Lay on Hands gives a stack for each ally it heals: a hand pouring light onto three allies; three
    # heal crosses each with a stack bead; three gold coins given from an open hand
    A = G("paladin", (12, 4))
    A.glow(12, 5, 8, "ffd860", 0.6)
    hand_open(A, 12, 5.4, 0.62, SKIN)
    for k, x in enumerate((4.6, 12.0, 19.4)):
        A.energy(path([(12, 9.4), (x, 12.4)], 0.7, 0.4), BEAM, falloff=0.6)
    for k, x in enumerate((4.6, 12.0, 19.4)):
        figure(A, x, 17.6, 0.74, ALLY, seed=k)
        A.energy(circle(x, 12.6, 0.9), LIFE, falloff=0.8)
    B = G("paladin", (12, 12))
    for k, (x, y) in enumerate(((6.0, 8.0), (18.0, 8.0), (12.0, 17.0))):
        plus(B, x, y, 3.4, LIFE, 0.95)
        B.energy(circle(x + 3.6, y - 3.6, 1.0), SUNR, falloff=1.0)
    C = G("paladin", (12, 14))
    hand_open(C, 12, 16.5, 0.95, SKIN)
    for k, (x, y) in enumerate(((6.0, 6.0), (12.0, 3.6), (18.0, 6.0))):
        coin(C, x, y, 2.2, GOLD, seed=k)
    return A, B, C


def pal_pb_descendent_of_pentival():
    # the Dragon trinkets and the Dragon Lord set grow with each stack: the red and blue scales under
    # the sun; a dragon's foot holding the sun; the dragon heart glowing gold
    A = G("paladin", (12, 6))
    A.glow(12, 6, 7, "ffd860", 0.5)
    scale(A, 8.0, 15.0, 0.95, SCALE_R, seed=1)
    scale(A, 16.0, 15.0, 0.95, SCALE_B, seed=2)
    sun(A, 12, 5.0, 2.4, SUNR, 10)
    B = G("paladin", (12, 6))
    talon(B, 12, 13.0, 1.05, DRAGON)
    sun_face(B, 12, 6.4, 2.8, SUNR, n=8)
    C = G("paladin", (12, 12))
    C.glow(12, 12, 10, "f0a818", 0.6)
    rays(C, 12, 12.5, 7.4, 10.6, 10, SUNR, 0.55)
    C.solid(heart(12, 12.8, 6.2), R("1a0404", "4a0a08", "861410", "c42a14", "f05a24", "ffa060"), base=2.6)
    C.solid(union(seg(9.2, 13.4, 12, 9.6, 0.5), seg(12, 9.6, 14.8, 13.4, 0.5), seg(12, 9.6, 12, 16.2, 0.5)),
            SUNR, base=3.6)
    return A, B, C


# ---------------------------------------------------------------- the Blessing stack (14x14)
def hud_pelors_blessing():
    # a small sun; the sun with its stack beads; a gold open hand
    A = S("paladin", (7, 7))
    sun(A, 7, 7, 2.6, SUNR, 8)
    B = S("paladin", (7, 7))
    pips(B, 7, 7, 5.4, 10, pr=0.75)
    B.energy(circle(7, 7, 2.6), SUNR, falloff=1.8)
    C = S("paladin", (7, 5))
    C.glow(7, 4, 5, "ffd860", 0.6)
    hand_open(C, 7, 8.2, 0.62, GOLD)
    C.energy(circle(7, 2.6, 1.3), SUNR, falloff=1.2)
    return A, B, C


PAL = [
    ("pal_class", "Generosity (emblem)", "The Paladin's 4th spec, Pelor's paladin: the subclass emblem."),
    ("pal_pelors_fury", "Pelor's Fury (active)",
     "Spend 10 Blessing stacks: a channeled pillar of light stuns the enemy you aim at, strips its armor and "
     "resistances and makes it take more damage. 30 s cooldown, 60 s on bosses."),
    ("pal_pelors_blessing", "Pelor's Blessing (passive)",
     "Lay on Hands on allies, Blessed Strike kills and Conviction mana give stacks (up to 10); each stack raises all three."),
    ("pal_pf_blinding_sun", "Blinding Sun (Fury orb)", "When the stun ends the target is blinded: 4 s Minor or 6 s Greater Blindness."),
    ("pal_pf_holy_sacrifice", "Holy Sacrifice (Fury orb)",
     "If the held enemy dies during the stun, the cooldown is halved and you get 1/3/5 Blessing stacks back."),
    ("pal_pb_display_of_generosity", "Display of Generosity (Blessing orb)", "Lay on Hands gives a stack per ally healed, up to 2/3/4."),
    ("pal_pb_descendent_of_pentival", "Descendent of Pentival (Blessing orb)",
     "The Dragon trinkets and the Dragon Lord set bonuses grow with each Blessing stack."),
    ("hud_pelors_blessing", "Pelor's Blessing (status)", "The stack count on the buff bar. A 14x14 buff-bar icon, shown at its size."),
]
ALL = {n: (lab, what) for n, lab, what in PAL}


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    rows = [(n, out[n]) for n, _, _ in PAL if n in out]
    if rows:
        sheet(rows, OUT / "sheet_paladin.png")
    return out


def picker():
    its = []
    for n, lab, what in PAL:
        imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
        its.append({"id": "specsPal." + n, "name": lab, "key": n, "desc": what, "imgs": imgs})
    groups = [{"id": "specsPal.paladin", "title": "Paladin: Generosity", "items": its}]
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
        n = k.split(".", 1)[1] if k.startswith("specsPal.") else k
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
