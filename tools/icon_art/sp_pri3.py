"""The Devil Forgemaster's icons, round 3: three ideas each for the five round-2 picks the user
noted. Four go necrotic green to match Necrotic Resurrection; the eating status gets better
defined teeth and lips. The round-2 pick (or, for "keep", the round-1 pick) is beside them as
"now". The six icons settled in round 2 go to art/specs/override/ with --finals.

    python tools/icon_art/sp_pri3.py [names...]   # out/specs/pri3/<name>_<a|b|c>.png, out/specs/pri3/sheet_priest.png
    python tools/icon_art/sp_pri3.py --picker     # also out/specs/pri3/picker.html, ids specsP3.<name>
    python tools/icon_art/sp_pri3.py --finals     # the settled round-1/2 picks to art/specs/override/
    python tools/icon_art/sp_pri3.py --pick FILE  # the picks ({name: "a"|"b"|"c"} or the picker's
                                                  # {"specsP3.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
from vm import book, drop
import sp
from sp_pri import NECRO, BODY, lying
from sp_pri2 import GORE, logs

OUT = sp.HERE / "out" / "specs" / "pri3"
R1 = sp.HERE / "out" / "specs" / "pri"
R2 = sp.HERE / "out" / "specs" / "pri2"
# Round 2 (the picker's specsP2.<name>, 2026-10-22): the base each icon here builds on, and the note.
BASE = {"pri_call_of_heresy": (R2, "a", "but green eye/book cover instead matching necrotic res"),
        "pri_pyre_sacrifice": (R2, "a", "but green fire and particles instead matching necrotic res"),
        "hud_heresy": (R2, "a", "but green eye instead matching necrotic res"),
        "hud_heresy_5": (R1, "b", "keep, but green eye instead matching necrotic res"),
        "hud_devouring": (R2, "a", "better defined teeth and lips")}
# Settled: round-1 or round-2 picks with no note.
FINALS = {"pri_necrotic_resurrection": (R1, "a"), "pri_sacrificial_penance": (R2, "c"), "pri_class": (R2, "c"),
          "pri_deeper_depravity": (R2, "a"), "pri_ravenous_lunge": (R2, "b"), "pri_rot_bloom": (R2, "a")}

NCOVER = R("040a06", "0a1c10", "143420", "205030", "2e6e44")          # a green-bound book
NSCLERA = R("060c08", "0e1a12", "18281c", "243a2a")                   # the dark round a green eye
RED_SCLERA = R("1a0406", "3a0a0e", "5a1018", "7a1a20")
EMBER_RED = R("140202", "3a0404", "700a06", "b01a0a", "f04010", "ff9a40", "fff0c0")
NFIRE = R("040c06", "0a2a12", "126020", "1e9a34", "46d05a", "a8f8a8", "f4fff4")   # necrotic fire, saturated like vanilla fire
LIP = R("0a0204", "2a060a", "5a0e14", "8a1a22", "b83038")


def eye(ic, cx, cy, s, iris=NECRO, sclera=NSCLERA, open_=1.0, seed=0):
    """sp_pri's slit eye with its round coloured too: an almond, a glowing iris, a slit pupil."""
    f = lambda x, y: (abs((y - cy) / s) - 3.0 * open_ * max(0, 1 - ((x - cx) / (6 * s)) ** 2)) * s
    ic.solid(f, sclera, base=1.8, spread=0.8, seed=seed, rim=0.4)
    ic.energy(inter(f, circle(cx, cy, 2.6 * s)), iris, falloff=1.6 * s, seed=seed)
    ic.paint(inter(f, ellipse(cx, cy, 0.5 * s, 2.2 * s)), lambda x, y, d: (4, 8, 6))


def rays(ic, cx, cy, rmp, n=6, r0=6.4, r1=8.4, ry=0.78, a0=-90, spread=30):
    for k in range(n):
        a = math.radians(a0 + (k - (n - 1) / 2) * spread)
        ic.energy(seg(cx + math.cos(a) * r0, cy + math.sin(a) * r0 * ry, cx + math.cos(a) * r1, cy + math.sin(a) * r1 * ry, 0.4, 0.2), rmp, falloff=0.3)


# ================================================================ skills
def pri_call_of_heresy():
    # the pick: an eye floating over the open book, rays round it. All green: green eye, green
    # cover; a dark cover with glowing green edges; a green cover, runes on the pages
    A = G("priest", (12, 8))
    A.glow(12, 8, 9, "40a070", 0.55)
    book(A, 12, 17, 1.0, NCOVER, PAPER, open_=True)
    rays(A, 12, 7.4, NECRO)
    eye(A, 12, 7.4, 1.25, NECRO, open_=0.9)
    B = G("priest", (12, 8))
    B.glow(12, 9, 10, "40a070", 0.6)
    book(B, 12, 17, 1.0, R("06060a", "0e0e14", "18181f", "24242c", "32323a"), PAPER, open_=True)
    B.energy(cut(box(12, 20.6, 10.2, 1.0), box(12, 20.6, 9.4, 0.4)), NECRO, falloff=0.4)
    rays(B, 12, 7.4, NECRO, 8, 6.6, 9.0, 0.8, -90, 24)
    eye(B, 12, 7.4, 1.25, NECRO, open_=0.95)
    C = G("priest", (12, 8))
    C.glow(12, 8, 9, "40a070", 0.5)
    book(C, 12, 17, 1.0, NCOVER, PAPER, open_=True)
    for k, (x, y) in enumerate(((7.4, 16.2), (8.8, 18.0), (15.2, 16.2), (16.6, 18.0))):
        C.paint(box(x, y, 1.4, 0.35), lambda xx, yy, d: NECRO[3])
    eye(C, 12, 7.0, 1.3, NECRO, open_=1.0)
    for k, (x, y) in enumerate(((4, 5), (20, 4), (5.5, 11), (18.6, 10.6))):
        C.energy(circle(x, y, 0.6), NECRO, falloff=0.6)
    return A, B, C


def pri_pyre_sacrifice():
    # the pick: a body burning on its pyre, wisps rising. In green fire: green flame and motes;
    # a white-hot core and green embers in smoke; a taller flame, green sparks spiralling up
    A = G("priest", (12, 14))
    logs(A, 12, 23.5, 0.95)
    A.energy(flame(12, 17, 8.4, 15, 0, 1, 3), NFIRE, falloff=2.4)
    lying(A, 12, 15.8, 0.95)
    for k, (x, y, r) in enumerate(((5, 5, 0.7), (18.5, 3.6, 0.7), (7.4, 1.8, 0.5), (16.6, 8.4, 0.5))):
        A.energy(circle(x, y, r), NECRO, falloff=r)
    B = G("priest", (12, 14))
    for k, (x, y, r) in enumerate(((8, 4.4, 2.6), (14.6, 3.0, 2.8))):
        B.solid(circle(x, y, r), SMOKE, base=1.4, spread=0.6, seed=k)
    logs(B, 12, 23.5, 0.95)
    B.energy(flame(12, 17, 8.6, 16, 0, 3, 3), NFIRE, falloff=2.6)
    lying(B, 12, 15.8, 0.95)
    for k, (x, y) in enumerate(((5.4, 9), (18.4, 8), (10, 2.6), (16.6, 1.6))):
        B.px([(int(x), int(y))], NECRO[5])
    C = G("priest", (12, 16))
    logs(C, 12, 23.5, 0.95)
    C.energy(flame(12, 17, 9.0, 18, -0.4, 5, 3), NFIRE, falloff=2.6)
    lying(C, 12, 15.8, 0.95)
    for k, (x, y) in enumerate(spiral_pts(12, 6, 1.0, 7.0, 90, 0.8, 8)[2::2]):
        C.energy(circle(x, y, 0.55), NECRO, falloff=0.55)
    return A, B, C


# ================================================================ the Heresy stack (14x14)
def hud_heresy():
    # the pick: the big slit eye filling the icon. Green: a dark green round; a soft green glow
    # behind it; the purple round kept, only the iris green
    A = S("priest", (7, 7))
    eye(A, 7, 7, 1.15, NECRO, open_=1.15)
    B = S("priest", (7, 7))
    B.glow(7, 7, 6, "40a070", 0.45)
    eye(B, 7, 7, 1.15, NECRO, open_=1.15)
    C = S("priest", (7, 7))
    eye(C, 7, 7, 1.15, NECRO, R("140a18", "2a1632", "40224a", "583060"), open_=1.15)
    return A, B, C


def hud_heresy_5():
    # the round-1 pick: the eye wide open, rays and glow round it. A green eye, still red hot
    # round it, so it reads apart from below 5; all green and blazing; green iris, bloodshot round
    A = S("priest", (7, 7))
    A.glow(7, 7, 7, "f04010", 1.0)
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        A.energy(seg(7 + math.cos(a) * 4.8, 7 + math.sin(a) * 4.0, 7 + math.cos(a) * 6.6, 7 + math.sin(a) * 6.2, 0.35, 0.2), EMBER_RED, falloff=0.3)
    eye(A, 7, 7, 1.0, NFIRE, open_=1.25)
    B = S("priest", (7, 7))
    B.glow(7, 7, 7, "90e0b0", 0.7)
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        B.energy(seg(7 + math.cos(a) * 4.8, 7 + math.sin(a) * 4.0, 7 + math.cos(a) * 6.6, 7 + math.sin(a) * 6.2, 0.4, 0.25), NFIRE, falloff=0.35)
    eye(B, 7, 7, 1.0, NFIRE, open_=1.3)
    C = S("priest", (7, 7))
    C.glow(7, 7, 7, "d02010", 0.9)
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        C.energy(seg(7 + math.cos(a) * 4.8, 7 + math.sin(a) * 4.0, 7 + math.cos(a) * 6.6, 7 + math.sin(a) * 6.2, 0.35, 0.2), EMBER_RED, falloff=0.3)
    eye(C, 7, 7, 1.0, NFIRE, RED_SCLERA, open_=1.25)
    return A, B, C


def hud_devouring():
    # the pick: the open maw. Teeth and lips defined: a dark lip line, four big fangs over two,
    # gaps between; a wide snarl, three and three; long canines over a tongue
    def lips(ic, f, inner):
        ic.solid(f, LIP, base=3.0, spread=1.2)
        ic.paint(cut(f, moved(f, 0, 0) if False else inner), lambda x, y, d: None)
        ic.paint(inner, lambda x, y, d: (20, 2, 6))

    def fangs(ic, pts, clip):
        ic.solid(inter(union(*[poly(p) for p in pts]), clip), BONE, base=4.4, spread=0.6)

    A = S("priest", (7, 7))
    outer, inner = ellipse(7, 7, 6.4, 5.4), ellipse(7, 7.2, 4.6, 3.6)
    lips(A, outer, inner)
    A.paint(cut(ellipse(7, 7, 6.9, 5.9), outer), lambda x, y, d: (10, 2, 4))
    fangs(A, [[(x - 0.9, 3.4), (x + 0.9, 3.4), (x, 7.0 if k in (0, 3) else 6.0)] for k, x in enumerate((3.6, 5.9, 8.1, 10.4))]
          + [[(x - 0.8, 11.0), (x + 0.8, 11.0), (x, 8.6)] for x in (5.6, 8.4)], inner)
    B = S("priest", (7, 7))
    outer, inner = ellipse(7, 7, 6.6, 4.8), ellipse(7, 7, 5.0, 2.9)
    lips(B, outer, inner)
    fangs(B, [[(x - 1.0, 4.0), (x + 1.0, 4.0), (x, 6.6)] for x in (4.4, 7.0, 9.6)]
          + [[(x - 1.0, 10.0), (x + 1.0, 10.0), (x, 7.4)] for x in (5.7, 8.3)], inner)
    C = S("priest", (7, 7))
    outer, inner = ellipse(7, 7, 6.4, 5.4), ellipse(7, 7.2, 4.6, 3.8)
    lips(C, outer, inner)
    C.solid(inter(ellipse(7, 10.0, 2.8, 1.6), inner), GORE, base=3.6)
    fangs(C, [[(3.2, 3.4), (5.0, 3.4), (4.0, 8.6)], [(9.0, 3.4), (10.8, 3.4), (10.0, 8.6)],
              [(5.6, 3.4), (8.4, 3.4), (7.0, 5.0)]], inner)
    return A, B, C


ITEMS = [
    ("pri_call_of_heresy", "Call of Heresy (passive)", "Your round-2 A in necrotic green: the eye and the book's cover."),
    ("pri_pyre_sacrifice", "Pyre Sacrifice (orb)", "Your round-2 A with green fire and green particles."),
    ("hud_heresy", "Heresy, below 5 (status)", "Your round-2 A (the big eye) in green. 14x14, shown at its size."),
    ("hud_heresy_5", "Heresy, 5+ (status)",
     "Your round-1 pick (kept) with a green eye. It must still read apart from below 5: A and C keep the red heat round it, B is all green. 14x14."),
    ("hud_devouring", "Devouring a body (status)", "Your round-2 A, the maw, with better defined teeth and lips. 14x14."),
]
ALL = {n: (lab, what) for n, lab, what in ITEMS}


def now(n):
    d, k, _ = BASE[n]
    return Image.open(d / f"{n}_{k}.png").convert("RGBA")


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in names:
        ims = [ic.done() for ic in globals()[n]()]
        for k, im in zip("abc", ims):
            im.save(OUT / f"{n}_{k}.png")
        out[n] = ims
    rows = [(n, out[n] + [now(n)]) for n, _, _ in ITEMS if n in out]
    if rows:
        sheet(rows, OUT / "sheet_priest.png")
    return out


def picker():
    its = []
    for n, lab, what in ITEMS:
        imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
        imgs["now"] = sp.uri(now(n))
        its.append({"id": "specsP3." + n, "name": lab, "key": n, "desc": what, "imgs": imgs})
    groups = [{"id": "specsP3.priest", "title": "Priest: Devil Forgemaster, round 3", "items": its}]
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
    for n, (d, k) in FINALS.items():
        save(n, Image.open(d / f"{n}_{k}.png").convert("RGBA"))


def pick(fn):
    """The chosen idea of each icon to art/specs/override/<name>.png; "keep" takes the base."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specsP3.") else k
        c = v.get("choice") if isinstance(v, dict) else v
        if n not in ALL or c not in ("a", "b", "c", "keep"):
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
