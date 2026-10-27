"""The Paladin's Generosity icons, round 4: three ideas each for the seven round-3 picks the user
noted (the picker's specsPal3.<name>, 2026-10-27). The round-3 pick is beside each as "now".

    python tools/icon_art/sp_pal4.py [names...]   # out/specs/pal4/<name>_<a|b|c>.png, out/specs/pal4/sheet_paladin.png
    python tools/icon_art/sp_pal4.py --picker     # also out/specs/pal4/picker.html, ids specsPal4.<name>
    python tools/icon_art/sp_pal4.py --finals     # the settled round-2 pick (Holy Sacrifice) to art/specs/override/
    python tools/icon_art/sp_pal4.py --pick FILE  # the picks ({name: "a"|"b"|"c"|"keep"} or the picker's
                                                  # {"specsPal4.<name>": {"choice": ..}}) to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
from vm import sun, star
import sp
from sp_pal import SUNR, BEAM, ROBE, BEARD, rays, shadow_foe, pips
from sp_pal3 import STAFF, spikes, big_sun, dragon_head, mini_sun

OUT = sp.HERE / "out" / "specs" / "pal4"
R3 = sp.HERE / "out" / "specs" / "pal3"
R2 = sp.HERE / "out" / "specs" / "pal"
# Round 3 (the picker's specsPal3.<name>): the base each icon here builds on, and the note.
BASE = {"pal_class": ("c", "Fix black spec in the bottom middle"),
        "pal_pelors_fury": ("a", "Needs to be moved down a bit, too much black space at bottom"),
        "pal_pelors_blessing": ("c", "Beard isnt filled in enough"),
        "pal_pf_blinding_sun": ("c", "Remove weird pinky, add thumb to right side sticking right direction. And make sun a "
                                     "little more blinding in some of the attempts, keep it the same as here for one"),
        "pal_pb_display_of_generosity": ("c", "Hand needs improvement"),
        "pal_pb_descendent_of_pentival": ("a", "More iterations"),
        "hud_pelors_blessing": ("b", "Center sun should be larger, rays moved closer to edge")}
FINALS = {"pal_pf_holy_sacrifice": (R2, "c")}

WARM = (176, 92, 20)   # the sun's features: a deep orange, never near black on the white disc


# ---------------------------------------------------------------- shapes
def sun_features(ic, cx, cy, r, col=WARM):
    """Pelor's calm face on a sun disc, in a warm orange that reads at 24px: two closed eyes and a
    smile, each a 1px arc."""
    ic.paint(union(arc(cx - r * 0.4, cy - r * 0.12, r * 0.24, r * 0.16, 200, 340),
                   arc(cx + r * 0.4, cy - r * 0.12, r * 0.24, r * 0.16, 200, 340),
                   arc(cx, cy + r * 0.12, r * 0.42, r * 0.16, 30, 150)), lambda x, y, d: col)


def hand(ic, cx, cy, s=1.0, rmp=SKIN, seed=0):
    """An open hand raised palm out: a palm, four fingers with a shadow line between each, and the
    thumb on the right standing out to the right, all inside a dark outline so it holds against
    glare. (cx, cy) the palm's middle."""
    palm = box(cx, cy + 1.6 * s, 3.4 * s, 3.4 * s, 0, 1.4 * s)
    fingers = [seg(cx + dx * s, cy - 1.0 * s, cx + dx * 1.08 * s, cy - 1.0 * s - h * s, 0.82 * s, 0.72 * s)
               for dx, h in ((-2.55, 4.4), (-0.85, 5.4), (0.85, 5.6), (2.55, 4.6))]
    thumb = seg(cx + 3.0 * s, cy + 2.4 * s, cx + 6.6 * s, cy + 0.2 * s, 1.0 * s, 0.8 * s)
    whole = union(palm, thumb, *fingers)
    ic.shade(lambda x, y: whole(x, y) - 0.8, 0.35)
    ic.solid(palm, rmp, seed=seed, base=2.8)
    for k, f in enumerate(fingers):
        ic.solid(f, rmp, seed=seed + k + 1, base=3.0)
    for dx in (-1.7, 0.0, 1.7):   # the gaps between the fingers
        ic.shade(seg(cx + dx * s, cy - 1.8 * s, cx + dx * 1.08 * s, cy - 4.4 * s, 0.12 * s), 0.78)
    ic.solid(thumb, rmp, seed=seed + 6, base=3.0)
    ic.shade(seg(cx + 3.0 * s, cy + 1.2 * s, cx + 4.6 * s, cy + 0.4 * s, 0.16 * s), 0.6)


def hand_down(ic, cx, cy, s=1.0, rmp=SKIN, sleeve=ROBE, seed=0, cuff=True):
    """A hand reaching down from above, palm toward us and fingers spread down, its sleeve going
    up out of the icon. (cx, cy) the palm's middle."""
    cuff_ = box(cx, cy - 4.6 * s, 3.4 * s, 3.0 * s, 0, 1.0 * s) if cuff else (lambda x, y: 99.0)
    palm = box(cx, cy, 3.0 * s, 2.4 * s, 0, 1.2 * s)
    fingers = [seg(cx + dx * s, cy + 1.4 * s, cx + dx * 1.22 * s, cy + 1.4 * s + h * s, 0.74 * s, 0.64 * s)
               for dx, h in ((-2.3, 3.4), (-0.78, 4.2), (0.78, 4.4), (2.3, 3.6))]
    thumb = seg(cx + 2.6 * s, cy + 0.2 * s, cx + 5.0 * s, cy + 2.6 * s, 0.85 * s, 0.7 * s)
    whole = union(cuff_, palm, thumb, *fingers)
    ic.shade(lambda x, y: whole(x, y) - 0.8, 0.35)
    if cuff:
        ic.solid(cuff_, sleeve, seed=seed, base=2.8)
    ic.solid(palm, rmp, seed=seed + 1, base=2.8)
    for k, f in enumerate(fingers):
        ic.solid(f, rmp, seed=seed + k + 2, base=3.0)
    for dx in (-1.55, 0.0, 1.55):
        ic.shade(seg(cx + dx * s, cy + 2.2 * s, cx + dx * 1.2 * s, cy + 4.4 * s, 0.12 * s), 0.78)
    ic.solid(thumb, rmp, seed=seed + 7, base=3.0)


def elder_full(ic, cx, cy, s=1.0, seed=0, hood=True, bushy=1.0, strands=0.0):
    """sp_pal.elder with the beard filled in: wider and fuller (bushy widens it), no dark gap under
    the moustache, and (strands > 0) only faint strands. (cx, cy) the face."""
    if hood:
        ic.solid(union(ellipse(cx, cy - 0.4 * s, 4.4 * s, 4.8 * s),
                       poly([(cx - 7.0 * s, cy + 12 * s), (cx - 4.6 * s, cy + 2.0 * s), (cx + 4.6 * s, cy + 2.0 * s),
                             (cx + 7.0 * s, cy + 12 * s)])), ROBE, seed=seed, base=2.6)
    ic.solid(ellipse(cx, cy, 2.9 * s, 3.3 * s), SKIN, seed=seed + 1, base=3.2)
    w = 3.2 * bushy
    b = union(poly([(cx - w * s, cy + 0.4 * s), (cx + w * s, cy + 0.4 * s), (cx + (w - 0.2) * s, cy + 5.8 * s),
                    (cx + 1.0 * s, cy + 11.2 * s), (cx - 1.0 * s, cy + 11.2 * s), (cx - (w - 0.2) * s, cy + 5.8 * s)]),
              ellipse(cx, cy + 1.2 * s, (w + 0.2) * s, 1.8 * s), ellipse(cx, cy + 4.6 * s, w * s, 3.0 * s))
    ic.solid(b, BEARD, seed=seed + 2, base=4.0, spread=0.7, rim=0.6, core=0.4)
    if strands:
        for k in (-1, 1):
            ic.shade(seg(cx + k * 1.2 * s, cy + 4.0 * s, cx + k * 0.5 * s, cy + 9.4 * s, 0.2 * s), strands)
    ic.solid(union(seg(cx - 2.6 * s, cy - 1.4 * s, cx - 0.6 * s, cy - 1.0 * s, 0.55 * s),
                   seg(cx + 0.6 * s, cy - 1.0 * s, cx + 2.6 * s, cy - 1.4 * s, 0.55 * s)), BEARD, seed=seed + 3, base=4.2)
    for d in (-1, 1):
        ic.px([(int(cx + d * 1.4 * s), int(cy - 0.3 * s))], (40, 24, 12))
    ic.solid(union(seg(cx - 2.0 * s, cy + 0.9 * s, cx + 2.0 * s, cy + 0.9 * s, 0.6 * s),
                   ellipse(cx, cy + 1.6 * s, 1.6 * s, 0.9 * s)), BEARD, seed=seed + 4, base=4.4)   # moustache into beard
    return b


def crook_scene(ic, elder_kw):
    """Round-3 Blessing C: the elder and his shepherd's crook curled round a sun."""
    elder_full(ic, 8.6, 9, 0.95, seed=9, **elder_kw)
    ic.solid(seg(17.2, 23.6, 17.2, 6.6, 0.7, 0.75), STAFF, seed=10, base=2.6)
    ic.solid(union(arc(19.0, 6.4, 1.9, 0.75, 180, 400), seg(20.6, 5.4, 20.4, 7.6, 0.4, 0.3)), STAFF, seed=11, base=3.0)
    ic.glow(19.0, 6.6, 6, "ffd860", 0.7)
    sun(ic, 19.0, 6.6, 1.15, SUNR, 8)
    for k in (9.2, 10.4):
        ic.solid(seg(16.2, k, 18.2, k, 0.4), GOLD, seed=12, base=3.4)
    ic.solid(ellipse(16.6, 13.2, 1.4, 1.2), SKIN, seed=13, base=3.0)
    ic.solid(seg(13.0, 15.6, 15.6, 13.6, 1.4, 1.1), ROBE, seed=14, base=2.6)


# ---------------------------------------------------------------- the emblem
def class_sun(ic, r=4.4, face=None):
    """Round-3 emblem C: twelve wedge rays round a ring, the sun inside."""
    ic.glow(12, 12, 12, "f0a818", 0.5)
    spikes(ic, 12, 12, 7.0, 11.8, 12, 7.0, SUNR, fall=0.8)
    ic.energy(ring(12, 12, 6.6, 0.8), SUNR, falloff=0.6)
    big_sun(ic, 12, 12, r, long_=1.45, short=1.3, n=8, half=13, face=False)
    if face:
        sun_features(ic, 12, 12, r, face)


def pal_class():
    # round 4 (round-3 C; "fix black spec in the bottom middle"): the speck was the sun face's mouth,
    # its eyes washed out by the white core. Without the face; with the whole face in warm orange;
    # without the face and a little larger disc
    A = G("paladin", (12, 12))
    class_sun(A)
    B = G("paladin", (12, 12))
    class_sun(B, face=WARM)
    C = G("paladin", (12, 12))
    class_sun(C, r=5.0)
    return A, B, C


# ---------------------------------------------------------------- skills
def fury(ic, dy, s=1.42, seed=1):
    """Round-3 Fury A moved down dy: the shadow under a broad pillar landing on its head."""
    shadow_foe(ic, 12, 17.2 + dy, s, seed=seed)
    by = 9.4 + dy - (s - 1.42) * 3
    ic.energy(poly([(9.0, 0), (15.0, 0), (15.8, by), (8.2, by)]), BEAM, falloff=2.0)
    ic.energy(ellipse(12, by + 0.2, 5.6, 1.3), BEAM, falloff=1.0)
    ic.energy(star(12, by, 1.2, 6.4, 6, -90), BEAM, falloff=1.0)
    for x, y in ((3.0, 9.4), (21.0, 9.0), (2.4, 15.0), (21.6, 15.6)):
        ic.energy(circle(x, y + dy * 0.5, 0.6), SUNR, falloff=0.55)


def pal_pelors_fury():
    # round 4 (round-3 A; "moved down a bit, too much black space at bottom"): down 2.5 px; down 4 px;
    # down 4 px with the shadow a little larger, so its shoulders run off the bottom
    A = G("paladin", (12, 6))
    fury(A, 2.5)
    B = G("paladin", (12, 7))
    fury(B, 4.0)
    C = G("paladin", (12, 7))
    fury(C, 4.0, s=1.6, seed=2)
    return A, B, C


def pal_pelors_blessing():
    # round 4 (round-3 C; "beard isnt filled in enough"): the beard filled solid, no dark strands;
    # filled with two faint strands; fuller and bushier still
    A = G("paladin", (17, 5))
    crook_scene(A, {})
    B = G("paladin", (17, 5))
    crook_scene(B, {"strands": 0.8})
    C = G("paladin", (17, 5))
    crook_scene(C, {"bushy": 1.2})
    return A, B, C


def pal_pf_blinding_sun():
    # round 4 (round-3 C; "remove weird pinky, add thumb to right side sticking right; make sun a
    # little more blinding in some, keep it the same as here for one"): the new hand with the
    # round-3 sun; a whiter sun with a glare cross; the sun whiting out the corner, the hand's
    # edge lit by it
    A = G("paladin", (15, 8))
    A.glow(14, 9, 13, "fff2b0", 0.6)
    big_sun(A, 15.4, 8.6, 4.2, long_=2.0, short=1.5, rmp=BEAM, face=False)
    A.solid(seg(0.0, 24.0, 5.6, 20.4, 2.2, 1.8), ROBE, seed=5, base=2.4)
    hand(A, 7.4, 15.4, 1.08, SKIN, seed=6)
    B = G("paladin", (15, 8))
    B.glow(15, 8, 15, "ffe08a", 0.7)
    big_sun(B, 15.4, 8.6, 4.6, long_=2.1, short=1.6, rmp=BEAM, face=False)
    for a in (0, 90):
        B.energy(rot(box(15.4, 8.6, 11.0, 0.55), 15.4, 8.6, a), BEAM, falloff=0.6)
    B.energy(circle(15.4, 8.6, 3.4), BEAM, falloff=3.4)
    B.solid(seg(0.0, 24.0, 5.6, 20.4, 2.2, 1.8), ROBE, seed=5, base=2.4)
    hand(B, 7.4, 15.4, 1.08, SKIN, seed=7)
    C = G("paladin", (16, 7))
    C.glow(16, 7, 18, "ffd870", 0.8)
    C.glow(16, 7, 10, "fff4c8", 0.8)
    big_sun(C, 16.0, 7.6, 5.0, long_=2.2, short=1.7, rmp=BEAM, face=False)
    C.energy(circle(16.0, 7.6, 4.0), BEAM, falloff=4.0)
    C.solid(seg(0.0, 24.0, 5.6, 20.4, 2.2, 1.8), ROBE, seed=5, base=2.4)
    hand(C, 7.4, 15.4, 1.08, SKIN, seed=8)
    C.energy(arc(7.4, 13.6, 6.4, 0.5, -95, 10), BEAM, falloff=0.35)   # the glare on the hand's edge
    return A, B, C


# ---------------------------------------------------------------- Pelor's Blessing orbs
def three_blessed(ic, seed=6):
    """Round-3 Display C's allies, smaller and lower to give the hand room: three figures, the
    Blessing's sun over each head."""
    for k, (x, y, s) in enumerate(((4.6, 20.2, 0.62), (19.4, 20.2, 0.62), (12.0, 19.6, 0.66))):
        figure(ic, x, y, s, ALLY, seed=k + seed)
        mini_sun(ic, x, y - 5.4 * s - 4.0, 0.95)


def pal_pb_display_of_generosity():
    # round 4 (round-3 C; "hand needs improvement"): the hand made the subject, the allies smaller
    # below it. An open hand, fingers apart and the thumb out; a hand reaching down from above,
    # fingers spread over the allies; that hand with light falling from it to the outer suns
    A = G("paladin", (11, 5))
    A.glow(11, 6, 8, "ffd860", 0.5)
    three_blessed(A)
    hand(A, 10.4, 6.6, 0.76, SKIN, seed=1)
    B = G("paladin", (12, 5))
    B.glow(12, 6, 8, "ffd860", 0.5)
    three_blessed(B)
    hand_down(B, 12, 2.2, 1.0, SKIN, seed=2, cuff=False)
    C = G("paladin", (12, 5))
    C.glow(12, 7, 9, "ffd860", 0.6)
    three_blessed(C)
    for x in (4.6, 19.4):
        C.energy(path([(12 + (x - 12) * 0.3, 7.6), (x, 10.4)], 0.5, 0.3), BEAM, falloff=0.45)
    hand_down(C, 12, 2.2, 1.0, SKIN, seed=3, cuff=False)
    return A, B, C


def pal_pb_descendent_of_pentival():
    # round 4 (round-3 A, the red dragon's head under the sun; "more iterations"): the head larger,
    # looking up at a bigger sun; roaring up at it, jaws open; the sun behind the head as a halo
    A = G("paladin", (17, 5))
    big_sun(A, 17.4, 5.4, 3.0, long_=1.9, short=1.45, face=False)
    dragon_head(A, 7.6, 14.0, 1.32, ang=-24, seed=1)
    B = G("paladin", (17, 5))
    big_sun(B, 18.0, 4.8, 2.6, long_=1.9, short=1.45, face=False)
    tip = dragon_head(B, 7.0, 15.0, 1.2, ang=-38, seed=2, open_=1.0)
    for k, (x, y) in enumerate(((tip[0] + 1.6, tip[1] - 0.6), (tip[0] + 2.6, tip[1] - 2.4), (tip[0] + 0.6, tip[1] - 2.6))):
        B.energy(circle(x, y, 0.55 - k * 0.08), SUNR, falloff=0.5)
    C = G("paladin", (12, 9))
    C.glow(12, 9, 12, "ffd860", 0.6)
    spikes(C, 12, 9.4, 6.0, 11.4, 12, 7.0, SUNR, fall=0.8)
    C.energy(circle(12, 9.4, 6.2), SUNR, falloff=4.0)
    dragon_head(C, 8.0, 12.6, 1.18, ang=-10, seed=3)
    return A, B, C


# ---------------------------------------------------------------- the Blessing stack (14x14)
def hud_pelors_blessing():
    # round 4 (round-3 B; "center sun should be larger, rays moved closer to edge"): a larger disc,
    # the rays starting farther out and ending at the beads; the rays between the beads instead;
    # the largest disc with short rays just inside the beads
    A = S("paladin", (7, 7))
    A.glow(7, 7, 7, "ffd860", 0.55)
    for k in range(10):
        a = math.radians(-90 + k * 36)
        A.energy(seg(7 + math.cos(a) * 3.8, 7 + math.sin(a) * 3.8, 7 + math.cos(a) * 5.6, 7 + math.sin(a) * 5.6, 0.5, 0.25), SUNR, falloff=0.45)
    pips(A, 7, 7, 6.0, 10, pr=0.75)
    A.energy(circle(7, 7, 3.3), SUNR, falloff=2.4)
    B = S("paladin", (7, 7))
    B.glow(7, 7, 7, "ffd860", 0.55)
    for k in range(10):
        a = math.radians(-72 + k * 36)
        B.energy(seg(7 + math.cos(a) * 3.8, 7 + math.sin(a) * 3.8, 7 + math.cos(a) * 6.4, 7 + math.sin(a) * 6.4, 0.55, 0.2), SUNR, falloff=0.45)
    pips(B, 7, 7, 6.0, 10, pr=0.75)
    B.energy(circle(7, 7, 3.3), SUNR, falloff=2.4)
    C = S("paladin", (7, 7))
    C.glow(7, 7, 7, "ffd860", 0.55)
    for k in range(10):
        a = math.radians(-90 + k * 36)
        C.energy(seg(7 + math.cos(a) * 4.2, 7 + math.sin(a) * 4.2, 7 + math.cos(a) * 5.4, 7 + math.sin(a) * 5.4, 0.55, 0.3), SUNR, falloff=0.45)
    pips(C, 7, 7, 6.1, 10, pr=0.72)
    C.energy(circle(7, 7, 3.7), SUNR, falloff=2.7)
    return A, B, C


def rot(f, cx, cy, ang):
    a = math.radians(-ang)
    ca, sa = math.cos(a), math.sin(a)
    return lambda x, y: f(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca)


ITEMS = [
    ("pal_class", "Generosity (emblem)", "Your round-3 C. The speck was the sun face's mouth (the eyes had washed out): A without the face; B the whole face in warm orange; C without the face, the disc a little larger."),
    ("pal_pelors_fury", "Pelor's Fury", "Your round-3 A moved down: A by 2.5 px; B by 4 px; C by 4 px with the shadow larger, its shoulders running off the bottom."),
    ("pal_pelors_blessing", "Pelor's Blessing", "Your round-3 C with the beard filled in: A solid, no dark strands; B two faint strands; C bushier still."),
    ("pal_pf_blinding_sun", "Blinding Sun (orb)", "Your round-3 C with a new hand, no pinky, the thumb out to the right: A the same sun; B a whiter sun with a glare cross; C the sun whiting out the corner, the hand's edge lit."),
    ("pal_pb_display_of_generosity", "Display of Generosity (orb)", "Your round-3 C with a better hand, now the subject, the allies smaller below: A an open hand, fingers apart and thumb out; B a hand reaching down from above; C that hand with light falling from it."),
    ("pal_pb_descendent_of_pentival", "Descendent of Pentival (orb)", "More of your round-3 A: A the head larger, looking up at a bigger sun; B roaring up at the sun, jaws open; C the sun behind the head as a halo."),
    ("hud_pelors_blessing", "Pelor's Blessing (stack)", "Your round-3 B, a larger sun, the rays farther out: A rays ending at the beads; B rays between the beads; C the largest sun, short rays just inside the beads. 14x14."),
]
ALL = {n: (lab, what) for n, lab, what in ITEMS}


def now(n):
    return Image.open(R3 / f"{n}_{BASE[n][0]}.png").convert("RGBA")


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
        sheet(rows, OUT / "sheet_paladin.png")
    return out


def picker():
    its = []
    for n, lab, what in ITEMS:
        imgs = {k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}
        imgs["now"] = sp.uri(now(n))
        its.append({"id": "specsPal4." + n, "name": lab, "key": n, "desc": what, "imgs": imgs})
    groups = [{"id": "specsPal4.paladin", "title": "Paladin: Generosity, round 4", "items": its}]
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
    """The chosen idea of each icon to art/specs/override/<name>.png; "keep" takes the round-3 pick."""
    raw = json.loads(Path(fn).read_text(encoding="utf-8"))
    for k, v in raw.items():
        n = k.split(".", 1)[1] if k.startswith("specsPal4.") else k
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
