"""The Hand Cannon's, the Flamethrower Rifle's and the Full Auto Rifle's icons, drawn the
way the hand-made gun icons in art/firearms/override/ are (glock_mh_0N, rifle_0N,
rifle_gl_0N, glock_attack, glock_dual): the items as pixel shapes in those icons' ramps
with a 1 px 4-neighbour dark outline and no ground; the attacks as those item sprites or
vpaint guns over a vpaint ground with a muzzle flash, tracers or flame. Unlike the idea generators here it writes its picks straight into
art/firearms/override/; tools/make_firearms_icons.py then puts them in the atlases.

    python tools/icon_art/fa_guns.py          # write the override PNGs
    python tools/icon_art/fa_guns.py --sheet  # also out/fa_guns.png: them beside the
                                              # pistol and rifle icons, labelled
"""
import math
import sys
from pathlib import Path
from PIL import Image
from vpaint import *
from motifs import L, lbox, parts, pistol, flash, cartridge

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OVR = REPO / "art" / "firearms" / "override"
OUTLINE = (12, 10, 16)

# the pistol slide's ramps, light to dark (glock_mh_01/02/03)
SLIDE = {
    1: R("c8ced8", "9299ab", "666d7e", "464b58", "2c2e38", "16141c"),
    2: R("a8ccf0", "6a94cc", "40649e", "2c4470", "1c2a44", "0e1420"),
    3: R("fff6c0", "f8d860", "d8a428", "a07018", "5e400c", "2a1c06"),
}
FRAME = R("54545e", "3c3c46", "2a2a32", "1c1c22")            # the pistol's grey frame
WOOD = {                                                      # rifle_01/02 stock ramps
    1: R("c4884a", "985c2c", "6e3e1c", "4a2a12"),
    2: R("8e5a3a", "6a3c26", "48281a", "2e1a10"),
}
WOOD[3] = WOOD[1]
TANK = R("f08a5a", "dc4a30", "a82a20", "6e1814", "3a0c0c")     # the fuel tank, light to dark
STEEL = R("c8ced8", "9299ab", "666d7e", "464b58", "2c2e38")
STEELV = R("16181f", "2b303b", "485060", "6e788a", "a2acbc", "dfe6ef")   # vpaint's STEEL
FLAME = R("fffbe0", "ffe070", "ffa830", "e86010", "a82a08")


def outlined(px: dict, size=24) -> Image.Image:
    """{(x, y): rgb} -> a 24x24 icon, the 4-neighbour outline in OUTLINE around it."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for (x, y) in px:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in px and 0 <= x + dx < size and 0 <= y + dy < size:
                im.putpixel((x + dx, y + dy), OUTLINE + (255,))
    for (x, y), c in px.items():
        if 0 <= x < size and 0 <= y < size:
            im.putpixel((x, y), tuple(c) + (255,))
    return im


def fill(px, x0, x1, y0, y1, c):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            px[(x, y)] = c


# ---------------------------------------------------------------- the hand cannon
def hand_cannon(tier: int) -> Image.Image:
    """Muzzle to the right, as glock_mh_0N: a long two-tone barrel with a vent rib and a
    flared muzzle, a fluted cylinder, a grey frame with a hammer spur, a wooden grip."""
    m, w, f = SLIDE[tier], WOOD[tier], FRAME
    px = {}
    # grip: a slanted wooden block, checkered, a metal butt cap
    for y in range(13, 21):
        x0 = 3 - (y - 13) // 3 + (0 if y < 15 else 0)
        x0 = {13: 3, 14: 3, 15: 2, 16: 2, 17: 2, 18: 1, 19: 1, 20: 1}[y]
        for i, x in enumerate(range(x0, x0 + 4 if y > 14 else x0 + 3)):
            px[(x, y)] = (w[0], w[1], w[1], w[2])[i]
    for (x, y) in ((3, 16), (4, 18), (2, 19), (3, 14)):
        px[(x, y)] = w[3]
    fill(px, 1, 4, 20, 20, m[3])
    px[(1, 20)] = m[2]
    # frame behind the cylinder, the hammer spur over it
    for y in range(7, 13):
        px[(3, y)], px[(4, y)], px[(5, y)] = f[0], f[1], f[2]
    px[(3, 7)] = px[(4, 7)] = f[0]
    px[(2, 6)], px[(3, 6)], px[(2, 5)] = f[1], f[1], f[0]
    # trigger guard and trigger
    fill(px, 6, 10, 14, 14, f[2])
    px[(6, 15)] = f[1]
    px[(10, 15)] = f[2]
    fill(px, 7, 10, 16, 16, f[2])
    px[(8, 15)] = f[3]
    # cylinder: flutes down it, lit from the upper left
    cols = {6: 1, 7: 0, 8: 3, 9: 1, 10: 4}
    rows = {7: -1, 8: 0, 9: 0, 10: 0, 11: 0, 12: 1, 13: 2}
    for x, c in cols.items():
        for y, r in rows.items():
            px[(x, y)] = m[max(0, min(5, c + r))]
    # barrel: lit top rib with vent notches, body, dark ejector shroud under it
    fill(px, 11, 20, 8, 8, m[0])
    for x in (13, 16, 19):
        px[(x, 8)] = m[1]
    fill(px, 11, 20, 9, 9, m[1])
    fill(px, 11, 20, 10, 10, m[2])
    fill(px, 11, 20, 11, 11, m[3])
    fill(px, 12, 18, 12, 12, m[4])
    px[(12, 12)] = m[3]
    # flared muzzle and the front sight
    for y, (a, b) in zip(range(7, 13), ((1, 2), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5))):
        px[(21, y)], px[(22, y)] = m[a], m[b]
    px[(19, 7)] = m[2]
    return outlined(px)


# ---------------------------------------------------------------- the flamethrower rifle
def rifle_px(name):
    im = Image.open(OVR / f"{name}.png").convert("RGBA")
    return im, {(x, y): im.getpixel((x, y))[:3] for y in range(24) for x in range(24) if im.getpixel((x, y))[3]}


# rifle_0N's olive launcher colours -> the tank's
OLIVE2TANK = {(168, 178, 112): TANK[0], (128, 140, 76): TANK[1], (66, 74, 38): TANK[2], (22, 26, 14): TANK[4],
              (94, 104, 54): TANK[2], (42, 48, 24): TANK[3]}


def flame_rifle(tier: int) -> Image.Image:
    """rifle_0N with the olive launcher tube a red fuel tank, a steel band at its back,
    its open muzzle a steel nozzle with a pilot flame."""
    im, px = rifle_px(f"rifle_0{tier}")
    out = im.copy()
    for (x, y), c in px.items():
        if c in OLIVE2TANK:
            out.putpixel((x, y), OLIVE2TANK[c] + (255,))
    # the tube's mouth (its dark 'e' pixels at the top right) -> nozzle and flame
    for (x, y) in ((20, 4), (21, 5)):
        out.putpixel((x, y), STEEL[2] + (255,))
    for (x, y) in ((21, 4), (22, 5)):
        out.putpixel((x, y), STEEL[3] + (255,))
    for (x, y), c in (((22, 4), FLAME[1]), ((22, 3), FLAME[2]), ((23, 4), FLAME[3]), ((21, 3), FLAME[3]),
                      ((23, 3), FLAME[4])):
        out.putpixel((x, y), c + (255,))
    # a steel band round the tank, near its back
    for (x, y) in ((16, 8), (17, 8), (18, 7)):
        if px.get((x, y)) in OLIVE2TANK:
            out.putpixel((x, y), STEEL[1] + (255,))
    return out


def flame_nozzle(tier: int) -> Image.Image:
    """rifle_gl_0N's layout (barrel and handguard of the tier above, the launcher's
    forward grip below) with the launcher swapped for a red fuel tank with a domed steel
    cap, a valve and a nozzle with a small flame at its tip."""
    im, px = rifle_px(f"rifle_gl_0{tier}")
    keep = {(x, y): c for (x, y), c in px.items() if y <= 9 and not (x >= 16 and y == 9)}
    keep.update({(x, y): c for (x, y), c in px.items() if y >= 19 and x <= 10})
    keep = {k: c for k, c in keep.items() if c != OUTLINE}
    out = dict(keep)
    # tank body: rows 10..18, x 0..12, lit from above, steel bands
    shade = {10: 1, 11: 0, 12: 1, 13: 1, 14: 2, 15: 2, 16: 3, 17: 3, 18: 4}
    for y, s in shade.items():
        for x in range(0, 13):
            out[(x, y)] = TANK[s]
    for x in (3, 8):
        for y, s in shade.items():
            out[(x, y)] = STEEL[min(4, s + 1)]
    out[(5, 11)] = out[(6, 11)] = (255, 212, 187)          # a hard glint on the top
    # domed cap
    for y, (x1, s) in {10: (13, 2), 11: (14, 1), 12: (15, 1), 13: (15, 2), 14: (15, 2), 15: (15, 3), 16: (15, 3),
                       17: (14, 4), 18: (13, 4)}.items():
        for x in range(13, x1 + 1):
            out[(x, y)] = STEEL[s]
    out[(14, 11)] = STEEL[0]
    # valve on top of the cap
    out[(14, 9)], out[(15, 9)] = STEEL[1], STEEL[2]
    # nozzle: a pipe out of the cap and a flared tip
    fill(out, 16, 19, 13, 13, STEEL[1])
    fill(out, 16, 19, 14, 14, STEEL[2])
    fill(out, 16, 19, 15, 15, STEEL[3])
    for y, s in zip(range(12, 17), (1, 1, 2, 3, 4)):
        out[(20, y)] = STEEL[s]
    out[(16, 13)] = STEEL[0]
    # the flame at its tip
    for (x, y), k in (((21, 13), 0), ((21, 14), 0), ((21, 12), 2), ((21, 15), 2), ((22, 13), 1), ((22, 14), 1),
                      ((22, 12), 3), ((22, 15), 3), ((23, 13), 2), ((23, 14), 3), ((23, 12), 4)):
        out[(x, y)] = FLAME[k]
    return outlined(out)


# ---------------------------------------------------------------- the full auto rifle
# rifle_0N's olive launcher colours -> a gunmetal barrel shroud's
OLIVE2SHROUD = {(168, 178, 112): (178, 184, 198), (128, 140, 76): (132, 138, 154), (66, 74, 38): (78, 82, 96),
                (22, 26, 14): (34, 34, 42), (94, 104, 54): (78, 82, 96), (42, 48, 24): (50, 52, 62)}
HOLE = (16, 14, 20)
DRUM = R("9aa0ae", "6c7282", "4a4e5a", "32343e", "202128")     # the drum's dark gunmetal


def drum(px, cx, cy, r, tier, hub=1.1):
    """A round drum magazine seen side on into px: dark gunmetal lit from the upper left,
    a tier-coloured rim, a winding hub. Returns the pixels it set."""
    m = SLIDE[tier]
    put = {}
    for y in range(int(cy - r - 1), int(cy + r + 2)):
        for x in range(int(cx - r - 1), int(cx + r + 2)):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            if d > r:
                continue
            lit = -(dx + dy) / (r * 1.414)                 # +1 at the upper left
            if d > r - 1:
                c = m[max(0, min(4, round(2 - lit * 1.6)))]
            elif d < hub:
                c = m[1]
            else:
                c = DRUM[max(0, min(4, round(2.2 - lit * 1.5)))]
            put[(x, y)] = c
    px.update(put)
    return put


def autorifle(tier: int) -> Image.Image:
    """rifle_0N with no launcher: the olive tube under the barrel a perforated gunmetal
    shroud round it, the curved box mag a drum."""
    im, px = rifle_px(f"rifle_0{tier}")
    out = {}
    for (x, y), c in px.items():
        if 14 <= x and 12 <= y <= 16 or (x, y) == (13, 13):
            continue                                       # the box mag goes
        out[(x, y)] = OLIVE2SHROUD.get(c, c)
    # the shroud's cooling holes: every other pixel down its middle
    for (x, y) in ((20, 5), (18, 7), (16, 9), (19, 7), (17, 9)):
        if px.get((x, y)) in OLIVE2SHROUD:
            out[(x, y)] = HOLE
    new = drum(out, 15.5, 15.5, 3.5, tier, hub=0.75)
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for (x, y), c in out.items():
        img.putpixel((x, y), tuple(c) + (255,))
    for (x, y) in new:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in out and 0 <= q[0] < 24 and 0 <= q[1] < 24:
                img.putpixel(q, OUTLINE + (255,))
    return img


def autorifle_mode(tier: int) -> Image.Image:
    """rifle_gl_0N's close-up layout (barrel and handguard on top) with the launcher a big
    drum magazine under the receiver, a ribbed feed neck up into it and a wooden fore-grip
    in front."""
    im, px = rifle_px(f"rifle_gl_0{tier}")
    keep = {(x, y): c for (x, y), c in px.items() if y <= 9 and not (x >= 16 and y == 9)}
    keep = {k: c for k, c in keep.items() if c != OUTLINE}
    out = dict(keep)
    w, f = WOOD[tier], FRAME
    # the feed neck under the handguard
    for y in (10, 11):
        for x, s in zip(range(4, 10), (0, 1, 1, 1, 2, 3)):
            out[(x, y)] = f[s] if y == 10 else f[min(3, s + 1)]
    drum(out, 7.5, 17.5, 6.3, tier, hub=1.5)
    for (x, y) in list(out):                               # a groove round the face, rivets
        d = math.hypot(x + 0.5 - 7.5, y + 0.5 - 17.5)
        if 3.6 < d < 4.4:
            out[(x, y)] = DRUM[4] if (x - 7) + (y - 17) < 0 else DRUM[3]
    for (x, y) in ((3, 14), (11, 14), (7, 22), (3, 20), (11, 20)):
        out[(x, y)] = DRUM[0]
    out[(7, 17)] = DRUM[4]                                 # the hub's arbor
    out[(4, 13)] = out[(3, 14)] = DRUM[0]                  # a hard glint on its face
    # the fore-grip: a wooden post hanging off the handguard's front, finger grooves
    for y in range(10, 21):
        for x, s in zip(range(16, 20), (0, 1, 1, 3)):
            out[(x, y)] = w[s]
    for y in (13, 16, 19):
        out[(16, y)], out[(17, y)] = w[2], w[2]
    for x, s in zip(range(16, 20), (1, 2, 2, 3)):
        out[(x, 21)] = f[s]
    return outlined(out)


# ---------------------------------------------------------------- the attacks
def revolver(ic, cx, cy, ang=0, s=1.0, metal=GUN, grip=None, seed=0, flip=False, cyl=None):
    """motifs.pistol's hand cannon: about 17 units long at s=1 (the pistol is 13), a
    fluted cylinder over the trigger, a long barrel with an under-lug, a flared muzzle,
    a hammer spur and a wooden grip hanging below (v+)."""
    grip = grip or R("1a0e06", "3a200c", "5e3614", "86521e", "b07a34", "d8a860")
    fv = -1 if flip else 1
    items = [
        (lbox(-3.4, 3.8 * fv, 1.7, 3.2, 0.6), grip, {"base": 2.2}),
        (lambda x, y: ring(0.6, 2.9 * fv, 1.3, 0.8)(x, y), metal, {"base": 1.8}),
        (lbox(-2.6, 0.2 * fv, 1.6, 1.9, 0.4), metal, {"base": 2.0}),
        (lbox(-4.2, -1.9 * fv, 0.9, 0.7, 0.2), metal, {"base": 1.6}),
        (lbox(5.6, 1.0 * fv, 3.2, 0.7, 0.2), metal, {"base": 1.3}),
        (lbox(6.4, -0.4 * fv, 4.2, 1.5, 0.3), metal, {"rim": 1.4}),
        (lbox(10.8, -0.3 * fv, 0.9, 2.1, 0.3), metal, {"base": 3.0, "rim": 1.4}),
        (lbox(9.6, -2.3 * fv, 0.5, 0.5, 0.1), metal, {"base": 1.4}),
        (lbox(0.6, 0.3 * fv, 2.3, 2.8, 0.8), cyl or STEELV, {"base": 3.0, "rim": 1.2}),
    ]
    parts(ic, cx, cy, ang, s, items, seed)
    for k, v in enumerate((-1.0, 0.0, 1.0)):                # the cylinder's flutes
        ic.shade(L(lbox(0.6, (0.3 + v * 1.5) * fv, 1.8, 0.24, 0.0), cx, cy, ang, s), 0.5)


def revolver_tip(cx, cy, ang, s, flip=False):
    a = math.radians(ang)
    u, v = 11.8 * s, -0.3 * s * (-1 if flip else 1)
    return cx + math.cos(a) * u - math.sin(a) * v, cy + math.sin(a) * u + math.cos(a) * v


def _pistol_tip(cx, cy, ang, s):
    a = math.radians(ang)
    return cx + math.cos(a) * 7.4 * s, cy + math.sin(a) * 7.4 * s


def hcannon_attack():
    # glock_attack's pick: the gun tipped up as it kicks, the flash at its muzzle, and
    # a puff of smoke off the cylinder where the pistol throws a case
    ic = G()
    revolver(ic, 5.5, 14.5, -15, 1.2)
    flash(ic, *revolver_tip(5.5, 14.5, -15, 1.2), 3.4)
    for k, (x, y, r) in enumerate(((8.6, 7.4, 0.9), (9.6, 4.8, 1.2))):
        ic.solid(circle(x, y, r), SMOKE, base=2.2 + k * 0.4, seed=k)
    return ic.done()


def G():
    return Icon().ground("0a0c14", "1e2434", light=(12, 6))


def hcannon_mixed():
    # glock_dual's pick: back to back, aiming up and out at 45 degrees, both firing; the
    # pistol on the left, the hand cannon on the right
    ic = G()
    pistol(ic, 7.0, 15.5, -135, 1.0, flip=True)
    revolver(ic, 14.5, 17.5, -45, 0.9)
    flash(ic, *_pistol_tip(7.0, 15.5, -135, 1.0), 2.4)
    flash(ic, *revolver_tip(14.5, 17.5, -45, 0.9), 2.6)
    return ic.done()


def hcannon_dual():
    ic = G()
    revolver(ic, 9.5, 17.5, -135, 0.9, flip=True)
    revolver(ic, 14.5, 17.5, -45, 0.9)
    flash(ic, *revolver_tip(9.5, 17.5, -135, 0.9, flip=True), 2.6)
    flash(ic, *revolver_tip(14.5, 17.5, -45, 0.9), 2.6)
    return ic.done()


def paste(ic, im, dx, dy):
    for y in range(im.height):
        for x in range(im.width):
            c = im.getpixel((x, y))
            if c[3] and 0 <= x + dx < ic.n and 0 <= y + dy < ic.n:
                ic.p[x + dx, y + dy] = c[:3]


def flamer_attack():
    # gl_attack's kept close-up, on fire: the nozzle in from the left, a roaring jet to
    # the frame's edge
    ic = Icon().ground("140604", "34100a", light=(16, 12))
    ic.glow(18, 13, 11, "ff6010", 0.8)
    paste(ic, flame_nozzle(1), -8, -1)
    ic.energy(lambda x, y: (abs(y - 13.0) - ((x - 13) * 0.42 + 1.6) * (0.85 + 0.18 * math.sin(x * 1.3 + y * 0.4)))
              if x > 13 else 1, FIRE, falloff=3.2)
    ic.glint(15, 13, (255, 255, 240))
    return ic.done()


TRACER = ((255, 255, 236), (255, 236, 140), (255, 190, 70), (226, 110, 30))   # head to tail


def tracer(ic, x0, y0, ang, r0, n):
    """A tracer dash n px long, r0 px out from (x0, y0) along ang: white-hot head first."""
    a = math.radians(ang)
    for i in range(n):
        r = r0 + n - 1 - i
        x, y = round(x0 + math.cos(a) * r - 0.5), round(y0 + math.sin(a) * r - 0.5)
        if 0 <= x < ic.n and 0 <= y < ic.n:
            ic.p[x, y] = TRACER[min(3, i)]


# the drum gun side on, muzzle right, its stock off the frame's left: digits the steel ramp,
# x the shroud's holes, n/f/w/o the fore-grip's wood
TOMMY = [
    "", "", "", "", "", "", "", "", "",
    "...........22",
    "1111111111122",
    "2222x2x2x2x23",
    "3333444444434",
    "........nfw..",
    "........nfw..",
    "........nfo..",
    "........nfo..",
    "........fwo..",
]


def tommy_side(tier=1):
    m, w = STEEL, WOOD[tier]
    px = {}
    for y, r in enumerate(TOMMY):
        for x, c in enumerate(r):
            if c.isdigit():
                px[(x, y)] = m[int(c) - 1]
            elif c == "x":
                px[(x, y)] = HOLE
            elif c in "nfwo":
                px[(x, y)] = w["nfwo".index(c)]
    drum(px, 3.5, 16.5, 3.6, tier, hub=0.75)
    return outlined(px)


def autofire_attack():
    # the drum gun hosing, side on: tracer dashes fanning out across the shot's ±20
    # degrees off the muzzle, a flash at it, a spent case kicked up out of the side
    ic = G()
    paste(ic, tommy_side(), 0, 1)
    mx, my = 13.5, 12.0
    flash(ic, mx, my, 2.0)
    for k, (d, r0) in enumerate(((-20, 3), (-7, 5), (6, 4), (19, 3))):
        tracer(ic, mx, my, d, r0, 4)
        tracer(ic, mx, my, d, r0 + 6, 3)
    cartridge(ic, 6.0, 5.5, -110, 0.4, tip=BRASS, case=BRASS, length=8, w=2.6)
    return ic.done()


def icons():
    out = {}
    for t in (1, 2, 3):
        mh = hand_cannon(t)
        out[f"hcannon_mh_0{t}"] = mh
        out[f"hcannon_oh_0{t}"] = mh.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        out[f"flamerifle_0{t}"] = flame_rifle(t)
        out[f"flamerifle_nozzle_0{t}"] = flame_nozzle(t)
        out[f"autorifle_0{t}"] = autorifle(t)
        out[f"autorifle_mode_0{t}"] = autorifle_mode(t)
    out["hcannon_attack"] = hcannon_attack()
    out["hcannon_mixed"] = hcannon_mixed()
    out["hcannon_dual"] = hcannon_dual()
    out["flamer_attack"] = flamer_attack()
    out["autofire_attack"] = autofire_attack()
    return out


def main(argv):
    made = icons()
    for name, im in made.items():
        im.save(OVR / f"{name}.png")
    print(f"wrote {len(made)} icons in {OVR.relative_to(REPO)}")
    if "--sheet" in argv:
        from grid import grid
        old = ["glock_mh_01", "glock_mh_02", "glock_mh_03", "glock_oh_01", "glock_oh_02", "glock_oh_03",
               "rifle_01", "rifle_02", "rifle_03", "rifle_gl_01", "rifle_gl_02", "rifle_gl_03",
               "glock_attack", "glock_dual", "rifle_attack", "gl_attack"]
        items = [(n, Image.open(OVR / f"{n}.png").convert("RGBA")) for n in old]
        items += list(made.items())
        (HERE / "out").mkdir(exist_ok=True)
        grid(items, HERE / "out" / "fa_guns.png", z=5, cols=6)
        print("wrote", (HERE / "out" / "fa_guns.png").relative_to(REPO))


if __name__ == "__main__":
    main(sys.argv[1:])
