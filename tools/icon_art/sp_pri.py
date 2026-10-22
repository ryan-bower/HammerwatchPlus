"""The Priest's 4th specialization, the Devil Forgemaster: three ideas each for its two skills,
the alternate form Necrotic Resurrection turns into at max Favor, and the Heresy stack's two
buff-bar icons (below 5 and 5+, which must read apart at a glance). The designs are in the
planner (planner/data/skills/priest-spec4-*.json); none of the icons exist in game yet.

    python tools/icon_art/sp_pri.py [names...]   # out/specs/pri/<name>_<a|b|c>.png, out/specs/pri/sheet_priest.png
    python tools/icon_art/sp_pri.py --picker     # also out/specs/pri/picker.html, ids specsP.<name>
    python tools/icon_art/sp_pri.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                 # {"specsP.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
from vm import arc, dagger, book, hand_open, drop
import sp

OUT = sp.HERE / "out" / "specs" / "pri"
sp.GROUNDS["priest"] = ("0c0806", "261a0e")   # a dim, smoky chapel

NECRO = R("040c08", "0a2216", "144030", "206a4a", "40a070", "90e0b0", "e8fff0")      # necrotic green
BODY = R("0c0c0e", "1e1e22", "34343a", "50505a", "767680", "a8a8b0")                 # a raised body is gray
HERESY = R("0c0410", "240a2a", "42124a", "6a1e6a", "9a3a8a", "d070b0", "ffd0f0")      # Heresy, below 5
HERESY5 = R("140202", "3a0404", "700a06", "b01a0a", "f04010", "ff9a40", "fff0c0")     # Heresy at 5+: red hot
STONE = R("0e0c0a", "221e1a", "3a342c", "56504a", "7a7468", "a8a094")
DEMON = R("140404", "3a0a08", "6a140c", "9a2410", "c8401a", "f07a34")
IRON = R("0a0a0c", "1a1a20", "2e2e36", "46464e", "66666e", "9a9aa2")


# ---------------------------------------------------------------- objects
def lying(ic, cx, cy, s=1.0, rmp=BODY, seed=0):
    """A body on its side, head to the left: the gray copy an enemy leaves."""
    f = union(circle(cx - 6.2 * s, cy - 0.6 * s, 2.0 * s), ellipse(cx - 1.0 * s, cy, 3.8 * s, 2.2 * s),
              seg(cx + 2.4 * s, cy - 0.6 * s, cx + 7.6 * s, cy - 0.2 * s, 1.0 * s),
              seg(cx + 2.4 * s, cy + 0.8 * s, cx + 7.4 * s, cy + 1.6 * s, 1.0 * s),
              seg(cx - 3.0 * s, cy + 1.2 * s, cx + 1.0 * s, cy + 2.4 * s, 0.75 * s))
    ic.solid(f, rmp, seed=seed, base=2.2)
    return f


def halo(cx, cy, rx, ry, w):
    """A halo seen a little from above: an elliptical ring."""
    return cut(ellipse(cx, cy, rx + w / 2, ry + w / 2), ellipse(cx, cy, rx - w / 2, ry - w / 2))


def cracked_halo(ic, cx, cy, rx, ry, w, rmp, gaps=((-60, 44), (150, 48)), fall=0.5):
    f = halo(cx, cy, rx, ry, w)
    for a, wd in gaps:   # wedge cuts: a crack at angle a, wd degrees wide
        a0, a1 = math.radians(a - wd / 2), math.radians(a + wd / 2)
        f = cut(f, poly([(cx, cy), (cx + math.cos(a0) * 20, cy + math.sin(a0) * 20), (cx + math.cos(a1) * 20, cy + math.sin(a1) * 20)]))
    ic.energy(f, rmp, falloff=fall)


def bell(ic, cx, cy, s=1.0, rmp=IRON, seed=0):
    """A chapel bell, mouth down, its clapper showing."""
    body = union(poly([(cx - 2.6 * s, cy - 4.4 * s), (cx + 2.6 * s, cy - 4.4 * s), (cx + 4.0 * s, cy + 2.2 * s),
                       (cx + 5.4 * s, cy + 3.6 * s), (cx - 5.4 * s, cy + 3.6 * s), (cx - 4.0 * s, cy + 2.2 * s)]),
                 ellipse(cx, cy - 4.4 * s, 2.6 * s, 1.6 * s))
    ic.solid(body, rmp, seed=seed, base=2.6)
    ic.solid(ring(cx, cy - 6.6 * s, 1.0 * s, 0.6 * s), rmp, seed=seed + 1, base=3.2)
    ic.solid(box(cx, cy + 1.2 * s, 4.4 * s, 0.4 * s), rmp, seed=seed + 2, base=1.4, spread=0.3)
    ic.solid(circle(cx, cy + 4.4 * s, 1.1 * s), rmp, seed=seed + 3, base=3.4)


def inv_tri(ic, cx, cy, r, rmp, w=0.5, fall=0.5):
    """The heretic's mark: a ring with a downward triangle and an eye-dot in it."""
    tri = [(cx + math.cos(math.radians(90 + k * 120)) * r * 0.86, cy + math.sin(math.radians(90 + k * 120)) * r * 0.86) for k in range(3)]
    ic.energy(union(ring(cx, cy, r, w * 2), *[seg(*tri[k], *tri[(k + 1) % 3], w) for k in range(3)]), rmp, falloff=fall)
    ic.energy(circle(cx, cy - r * 0.12, r * 0.18), rmp, falloff=0.6)


def slit_eye(ic, cx, cy, s, rmp, open_=1.0, seed=0):
    """An almond eye with a slit pupil, all in one energy ramp."""
    f = lambda x, y: (abs((y - cy) / s) - 3.0 * open_ * max(0, 1 - ((x - cx) / (6 * s)) ** 2)) * s
    ic.solid(f, R("140a18", "2a1632", "40224a", "583060"), base=1.8, spread=0.8, seed=seed, rim=0.4)
    ic.energy(inter(f, circle(cx, cy, 2.6 * s)), rmp, falloff=1.6 * s, seed=seed)
    ic.paint(inter(f, ellipse(cx, cy, 0.5 * s, 2.2 * s)), lambda x, y, d: (8, 4, 6))


# ---------------------------------------------------------------- skills
def pri_necrotic_resurrection():
    # raise a body as a gray summon: one climbing out of its grave; the spirit standing up out of the
    # body; a skull lit green over the ritual ring
    A = G("priest", (12, 14))
    A.glow(12, 14, 9, "40a070", 0.5)
    fig = union(circle(12, 6.8, 2.6), box(12, 13, 3.2, 4.4, 0, 1.4),
                seg(9.4, 10.4, 5.4, 5.6, 1.0), seg(14.6, 10.4, 18.6, 5.6, 1.0))
    A.solid(cut(fig, ellipse(12, 22, 11, 4.6)), BODY, base=2.6)
    A.px([(11, 7), (13, 7)], NECRO[5])
    A.solid(ellipse(12, 22, 11, 4.0), EARTH, base=2.0, spread=1.2)
    for k, (x, y) in enumerate(((4, 15), (20, 14), (7, 19.5), (17.5, 19))):
        A.energy(path([(x, y), (x + (1 if k % 2 else -1) * 0.8, y - 3.4)], 0.7, 0.2), NECRO, falloff=0.5)
    B = G("priest", (12, 18))
    lying(B, 12, 19.5, 1.15)
    ghost = union(circle(12, 4.6, 2.2), poly([(9.0, 7.2), (15.0, 7.2), (16.4, 15.6), (12, 18), (7.6, 15.6)]))
    B.energy(ghost, NECRO, falloff=2.2)
    B.px([(11, 4), (13, 4)], NECRO[0])
    for d in (-1, 1):
        B.energy(path([(12 + d * 3.6, 9), (12 + d * 7.6, 6.8), (12 + d * 8.8, 4.2)], 0.6, 0.25), NECRO, falloff=0.4)
    C = G("priest", (12, 12))
    C.energy(ring(12, 12.5, 10.0, 1.0), NECRO, falloff=0.5)
    for k in range(5):
        a = math.radians(-90 + k * 72)
        C.energy(circle(12 + math.cos(a) * 10, 12.5 + math.sin(a) * 10, 1.1), NECRO, falloff=1.0)
    skull(C, 12, 12, 1.05, BODY, eyes=NECRO)
    return A, B, C


def pri_sacrificial_penance():
    # at max Favor, a body given up to wash Heresy away: the knife over the body; the body rising
    # as golden motes into the halo; a cracked purple halo mended gold
    A = G("priest", (12, 8))
    A.glow(12, 17, 9, "e8c850", 0.7)
    lying(A, 12, 19.5, 1.15)
    dagger(A, 12, 8.5, -90, 1.0, STEEL, LEATHER, GOLD)
    A.energy(union(seg(12, 15.6, 12, 17.4, 0.6), seg(9.6, 15, 7.4, 13.6, 0.4), seg(14.4, 15, 16.6, 13.6, 0.4)), HOLY, falloff=0.5)
    B = G("priest", (12, 6))
    B.glow(12, 5, 6, "e8c850", 0.35)
    B.energy(halo(12, 4.4, 6.0, 1.8, 1.0), HOLY, falloff=0.5)
    body = lying(B, 12, 19.5, 1.15)
    B.shade(inter(body, box(12, 18.4, 12, 1.0)), 0.55)
    for k, (x, y, r) in enumerate(((7, 15.5, 0.8), (10.5, 13, 0.7), (14.5, 14.5, 0.8), (16, 11, 0.6), (12, 9.5, 0.6), (9, 10, 0.5))):
        B.energy(circle(x, y, r), HOLY, falloff=r)
    C = G("priest", (12, 12))
    C.glow(12, 12, 10, "e8c850", 0.45)
    full = halo(12, 12, 8.6, 5.2, 2.0)
    C.energy(inter(full, box(4, 12, 8, 10)), HERESY, falloff=0.8)
    C.energy(inter(full, box(20, 12, 8, 10)), HOLY, falloff=0.8)
    C.paint(union(seg(12, 5.6, 11.2, 8.0, 0.35), seg(12, 18.4, 12.8, 16.0, 0.35)), lambda x, y, d: (12, 8, 6))
    C.energy(drop(12, 12.6, 1.9), CRIMSON, falloff=1.4)
    return A, B, C


def pri_call_of_heresy():
    # Heresy is a stack of its own, and bodies call to you: a chapel bell tolling purple; a hooded
    # priest under a horned, cracked halo; a heretic's book open on its mark
    A = G("priest", (12, 10))
    for k, r in enumerate((9.4, 11.6)):
        A.energy(arc(12, 13, r, 0.9, 200, 340), HERESY, falloff=0.4)
        if k == 0:
            A.energy(arc(12, 13, r - 2.4, 0.7, 30, 150), HERESY, falloff=0.3)
    bell(A, 12, 11.4, 1.05)
    B = G("priest", (12, 10))
    hood = union(poly([(12, 8.2), (17.2, 13.6), (19.2, 23.5), (4.8, 23.5), (6.8, 13.6)]), circle(12, 12.6, 4.6))
    B.solid(hood, R("0a0608", "1e1418", "34262c", "4e3a42", "6e5660"), base=2.2)
    B.paint(ellipse(12, 14.2, 2.6, 3.0), lambda x, y, d: (6, 4, 6))
    B.px([(11, 14), (13, 14)], HERESY[5])
    cracked_halo(B, 12, 4.8, 6.4, 1.9, 1.2, HERESY, gaps=((-90, 16),))
    for d in (-1, 1):
        B.solid(poly([(12 + d * 5.0, 4.0), (12 + d * 8.8, 0.4), (12 + d * 6.6, 4.8)]), DEMON, base=3.0)
    C = G("priest", (12, 8))
    C.glow(12, 9, 9, "9a3a8a", 0.55)
    book(C, 12, 17, 1.0, R("10060a", "2a0e1a", "48182e", "6a2442", "8e3458"), PAPER, open_=True)
    inv_tri(C, 12, 7.6, 5.0, HERESY, 0.55)
    return A, B, C


# ---------------------------------------------------------------- the Heresy stack (14x14)
def hud_heresy():
    # below 5: a cracked halo; a purple eye half open; the heretic's mark
    A = S("priest", (7, 7))
    cracked_halo(A, 7, 7.4, 5.0, 2.8, 1.5, HERESY)
    B = S("priest", (7, 7))
    slit_eye(B, 7, 7, 1.05, HERESY, open_=1.0)
    C = S("priest", (7, 7))
    inv_tri(C, 7, 7, 5.4, HERESY, 0.5)
    return A, B, C


def hud_heresy_5():
    # 5+ (raising is blocked): each the same idea as hud_heresy's, but red hot and gone too far: the
    # halo burst apart; the eye wide open and burning; the mark ablaze
    A = S("priest", (7, 7))
    A.energy(circle(7, 7, 0.9), HERESY5, falloff=0.8)
    for k in range(4):   # the halo burst into four shards, flung apart
        a0 = -70 + k * 90
        r = 4.6 + (k % 2) * 0.7
        A.energy(arc(7, 7, r, 1.3, a0, a0 + 48), HERESY5, falloff=0.6)
        m = math.radians(a0 + 24)
        A.px([(int(7 + math.cos(m) * (r + 2.0)), int(7 + math.sin(m) * (r + 2.0)))], HERESY5[4])
    B = S("priest", (7, 7))
    B.glow(7, 7, 7, "f04010", 0.7)
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        B.energy(seg(7 + math.cos(a) * 4.8, 7 + math.sin(a) * 4.0, 7 + math.cos(a) * 6.6, 7 + math.sin(a) * 6.2, 0.35, 0.2), HERESY5, falloff=0.3)
    slit_eye(B, 7, 7, 1.0, HERESY5, open_=1.25)
    C = S("priest", (7, 9))
    C.energy(flame(7, 13, 6.4, 13, 0, 4, 3), HERESY5, falloff=1.6)
    inv_tri(C, 7, 7.6, 4.4, R("100206", "300610", "5a0c1a"), 0.55, 0.5)
    return A, B, C


PRI = [
    ("pri_necrotic_resurrection", "Necrotic Resurrection (active)",
     "Raises a nearby intact body as a gray summon that follows you; normal +1, elite +2, boss +3 Heresy."),
    ("pri_sacrificial_penance", "Sacrificial Penance (active, at max Favor)",
     "Necrotic Resurrection's other form while Divine Favor is full: a 3 s channel that sacrifices a body to remove 1-3 Heresy."),
    ("pri_call_of_heresy", "Call of Heresy (passive)",
     "Heresy is its own stack; you lunge at bodies you come near; the spec grants Divine Favor's first level."),
    ("hud_heresy", "Heresy, below 5 (status)", "Heresy stacks 1-4: you can still raise. A 14x14 buff-bar icon, shown at its size."),
    ("hud_heresy_5", "Heresy, 5+ (status)",
     "Heresy at 5 or more: raising is blocked until Penance. Each idea matches the same letter of the below-5 icon. A 14x14 buff-bar icon."),
]
ALL = {n: (lab, what) for n, lab, what in PRI}


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    rows = [(n, out[n]) for n, _, _ in PRI if n in out]
    if rows:
        sheet(rows, OUT / "sheet_priest.png")
    return out


def picker():
    its = []
    for n, lab, what in PRI:
        imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
        its.append({"id": "specsP." + n, "name": lab, "key": n, "desc": what, "imgs": imgs})
    groups = [{"id": "specsP.priest", "title": "Priest: Devil Forgemaster", "items": its}]
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
        n = k.split(".", 1)[1] if k.startswith("specsP.") else k
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
