"""Builds the Firearms guns' ground sprites: mods/firearms/items/hwp/firearms_drops.png and
the scenes of mods/firearms/items/hwp/firearms_drops.unit that point into it.

    python tools/make_firearms_drops.py           # write both
    python tools/make_firearms_drops.py --check   # exit 1 if either differs from what the
                                                  # tool would write; write nothing

16x16 cells (vanilla items' size), 1 px dark 4-neighbour outline, no ground; the sheet is
128 wide (a power of two, which the engine requires) and one row of cells per gun family:
- row 0: rifle_01..03, glock_01..03 (drawn by hand; kept here pixel for pixel)
- row 1: hcannon_01..03 (the Hand Cannon), flamerifle_01..03 (the rifle with its launcher
  a fuel tank and a nozzle with a pilot flame)
- row 2: autorifle_01..03 (the Full Auto Rifle: the launcher a perforated barrel shroud,
  the box mag a drum)
Scene names are the cells' names; a BaseItem drops with `<unit>:<scene>`.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PNG = ROOT / "mods" / "firearms" / "items" / "hwp" / "firearms_drops.png"
UNIT = ROOT / "mods" / "firearms" / "items" / "hwp" / "firearms_drops.unit"
CELL = 16
OUTLINE = (16, 12, 10)

PAL = {
    "a": (16, 12, 10), "b": (22, 20, 28), "c": (102, 109, 126), "d": (22, 26, 14), "e": (152, 92, 44),
    "f": (94, 104, 54), "g": (146, 153, 171), "h": (70, 75, 88), "i": (44, 46, 56), "j": (196, 136, 74),
    "k": (74, 42, 18), "l": (14, 20, 32), "m": (64, 100, 158), "n": (106, 60, 38), "o": (106, 148, 204),
    "p": (44, 68, 112), "q": (28, 42, 68), "r": (142, 90, 58), "s": (46, 26, 16), "t": (200, 150, 44),
    "u": (234, 196, 84), "v": (106, 68, 16), "w": (60, 60, 70), "x": (42, 42, 50), "y": (248, 216, 96),
    "z": (42, 28, 6), "A": (160, 112, 24),
}

RIFLE = [
    "............aa..",
    "...........abba.",
    "..........acca..",
    ".........accaaa.",
    "........accaadda",
    ".......acceeffa.",
    "......aggeeffa..",
    ".....agghhaaa...",
    "....aaahhcciia..",
    "...ajjeeaahhbba.",
    "..ajjeekkaaaaa..",
    ".ajjeeaaa.......",
    "aiieea..........",
    ".aiikka.........",
    "..aaaa..........",
]
GLOCK = [
    "",
    "",
    "",
    "",
    "...aaaaaaaaa....",
    "..aggggggggba...",
    "..ahhhhhhhhha...",
    "..awwwwwwwwa....",
    "...awwwaxxa.....",
    "...awwwaaa......",
    "..awwwa.........",
    "..ahhha.........",
    "...aaa..........",
]
# the hand-drawn tiers, as letter swaps of the t1 sprites
RIFLE_T2 = {"b": "l", "c": "m", "e": "n", "g": "o", "h": "p", "i": "q", "j": "r", "k": "s"}
RIFLE_T3 = {"e": "t", "j": "u", "k": "v"}
GLOCK_T2 = {"g": "o", "b": "l", "h": "p"}
GLOCK_T3 = {"g": "y", "b": "z", "h": "A"}

# the Hand Cannon: the pistol's slide ramps (art/firearms/override/glock_mh_0N.png)
SLIDE = {1: ((200, 206, 216), (146, 153, 171), (102, 109, 126), (70, 75, 88), (44, 46, 56)),
         2: ((168, 204, 240), (106, 148, 204), (64, 100, 158), (44, 68, 112), (28, 42, 68)),
         3: ((255, 246, 192), (248, 216, 96), (216, 164, 40), (160, 112, 24), (94, 64, 12))}
FRAME = ((84, 84, 94), (60, 60, 70), (42, 42, 50), (28, 28, 34))
WOOD = {1: ((196, 136, 74), (152, 92, 44), (110, 62, 28), (74, 42, 18)),
        2: ((142, 90, 58), (106, 60, 38), (72, 40, 26), (46, 26, 16))}
WOOD[3] = WOOD[1]
TANK = ((236, 112, 72), (204, 52, 44), (130, 30, 28), (70, 16, 14))
STEEL = ((200, 206, 216), (146, 153, 171), (102, 109, 126), (70, 75, 88))
FLAME = ((255, 246, 192), (255, 186, 58), (232, 110, 28))
SHROUD = {"d": (34, 34, 42), "f": (132, 138, 154)}         # the launcher's olive -> gunmetal
HOLE = (16, 14, 20)
DRUM = ((154, 160, 174), (108, 114, 130), (74, 78, 90), (50, 52, 62), (32, 33, 40))
# hand cannon interior: digits 1-5 the slide ramp, k/h/i/j the frame, n/f/w/o the grip
HCANNON = [
    "",
    "",
    "",
    ".k.223........3.",
    ".kh213511222222.",
    "..h324533333333.",
    "..i324544444444.",
    "..nf445.......5.",
    ".nfwiij.........",
    ".nfw.i..........",
    ".nfo............",
    ".444............",
]
HC_FRAME = {"k": 0, "h": 1, "i": 2, "j": 3}
HC_WOOD = {"n": 0, "f": 1, "w": 2, "o": 3}


def outline(px: dict) -> dict:
    out = dict(px)
    for (x, y) in px:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in px and 0 <= q[0] < CELL and 0 <= q[1] < CELL:
                out[q] = OUTLINE
    return out


def grid(rows, swap=None) -> dict:
    swap = swap or {}
    return {(x, y): PAL[swap.get(c, c)] for y, r in enumerate(rows) for x, c in enumerate(r) if c != "."}


def hcannon(tier: int) -> dict:
    m, w = SLIDE[tier], WOOD[tier]
    px = {}
    for y, r in enumerate(HCANNON):
        for x, c in enumerate(r):
            if c.isdigit():
                px[(x, y)] = m[int(c) - 1]
            elif c in HC_FRAME:
                px[(x, y)] = FRAME[HC_FRAME[c]]
            elif c in HC_WOOD:
                px[(x, y)] = w[HC_WOOD[c]]
    return outline(px)


def flamerifle(tier: int) -> dict:
    swap = {1: {}, 2: RIFLE_T2, 3: RIFLE_T3}[tier]
    px = grid(RIFLE, swap)
    olive = {PAL["f"]: TANK[1]}
    for k, c in list(px.items()):
        if c in olive:
            px[k] = olive[c]
    # the tank's lit and dark sides, the launcher's mouth a nozzle with a pilot flame
    px[(12, 5)], px[(11, 6)] = TANK[0], TANK[0]
    px[(13, 5)], px[(12, 6)] = TANK[2], TANK[2]
    px[(13, 4)], px[(14, 4)] = STEEL[2], STEEL[3]
    px[(14, 3)], px[(15, 3)], px[(15, 4)] = FLAME[1], FLAME[2], FLAME[2]
    px[(14, 2)] = FLAME[0]
    return px


def autorifle(tier: int) -> dict:
    """The rifle with its olive launcher a gunmetal shroud with cooling holes and its box
    mag a drum: dark gunmetal, a rim in the tier's slide colour, a hub."""
    swap = {1: {}, 2: RIFLE_T2, 3: RIFLE_T3}[tier]
    rows = [r.replace("f", "F").replace("d", "D") for r in RIFLE]   # mark the launcher
    pal = dict(PAL, F=SHROUD["f"], D=SHROUD["d"])
    px = {(x, y): pal[swap.get(c, c)] for y, r in enumerate(rows) for x, c in enumerate(r) if c != "."}
    for (x, y) in list(px):
        if x >= 9 and 8 <= y <= 10:
            del px[(x, y)]                                  # the box mag goes
    for (x, y) in ((13, 5), (11, 6)):                       # the shroud's cooling holes
        px[(x, y)] = HOLE
    px[(9, 8)], px[(10, 8)] = PAL[swap.get("c", "c")], PAL[swap.get("i", "i")]   # the receiver's belly
    rim, drum = SLIDE[tier], {}
    for y in range(7, 15):
        for x in range(7, 16):
            dx, dy = x - 11, y - 11
            d = (dx * dx + dy * dy) ** 0.5
            if d > 2.7:
                continue
            lit = -(dx + dy) / 3.7                          # +1 at the upper left
            if d > 1.9:
                drum[(x, y)] = rim[max(0, min(4, round(2 - lit * 1.6)))]
            elif d < 0.5:
                drum[(x, y)] = rim[1]
            else:
                drum[(x, y)] = DRUM[max(0, min(4, round(2.2 - lit * 1.5)))]
    px.update(drum)
    for (x, y) in list(px):
        if px[(x, y)] == OUTLINE and all((x + dx, y + dy) not in px or px[(x + dx, y + dy)] == OUTLINE
                                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            del px[(x, y)]                                  # stray outline the mag left
    body = {k: c for k, c in px.items() if c != OUTLINE}
    out = outline(body)
    for k, c in px.items():
        out.setdefault(k, c)
    return out


CELLS = [  # (scene, row, col, pixels, pickup sound)
    ("rifle_01", 0, 0, grid(RIFLE), "item_wood"),
    ("rifle_02", 0, 1, grid(RIFLE, RIFLE_T2), "item_wood"),
    ("rifle_03", 0, 2, grid(RIFLE, RIFLE_T3), "item_wood"),
    ("glock_01", 0, 3, grid(GLOCK), "item_metal"),
    ("glock_02", 0, 4, grid(GLOCK, GLOCK_T2), "item_metal"),
    ("glock_03", 0, 5, grid(GLOCK, GLOCK_T3), "item_metal"),
    ("hcannon_01", 1, 0, hcannon(1), "item_metal"),
    ("hcannon_02", 1, 1, hcannon(2), "item_metal"),
    ("hcannon_03", 1, 2, hcannon(3), "item_metal"),
    ("flamerifle_01", 1, 3, flamerifle(1), "item_wood"),
    ("flamerifle_02", 1, 4, flamerifle(2), "item_wood"),
    ("flamerifle_03", 1, 5, flamerifle(3), "item_wood"),
    ("autorifle_01", 2, 0, autorifle(1), "item_wood"),
    ("autorifle_02", 2, 1, autorifle(2), "item_wood"),
    ("autorifle_03", 2, 2, autorifle(3), "item_wood"),
]


def sheet() -> Image.Image:
    rows = max(r for _, r, _, _, _ in CELLS) + 1
    h = 1
    while h < rows * CELL:
        h *= 2
    im = Image.new("RGBA", (128, h), (0, 0, 0, 0))
    for _, r, c, px, _ in CELLS:
        for (x, y), rgb in px.items():
            im.putpixel((c * CELL + x, r * CELL + y), rgb + (255,))
    return im


def unit() -> str:
    scenes = "".join(f'''		<scene name="{name}">
			<data name="sound"><s>event:/sfx/items/{sound}</s></data>
			<sprite origin="8 8" texture="items/hwp/firearms_drops.png" material="items/items.mats:item">
				<frame>{c * CELL} {r * CELL} {CELL} {CELL}</frame>
			</sprite>
		</scene>
''' for name, r, c, _, sound in CELLS)
    return ('<!-- HammerwatchPlus Firearms: the guns lying on the ground (scene = gun + tier). Sprites: '
            'items/hwp/firearms_drops.png. Written by tools/make_firearms_drops.py; edit that, not this. -->\n'
            '<unit slot="item">\n\t<behavior class="Pickup">\n\t\t<bool name="global">true</bool>\n'
            '\t\t<bool name="secure">true</bool>\n\t</behavior>\n\t<scenes>\n' + scenes + '\t</scenes>\n</unit>\n')


def png_bytes(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare, write nothing")
    args = ap.parse_args(argv)
    im, text = sheet(), unit()
    if args.check:
        bad = 0
        old = Image.open(PNG).convert("RGBA")
        if old.size != im.size or old.tobytes() != im.tobytes():
            print(f"{PNG.relative_to(ROOT)} differs")
            bad += 1
        if UNIT.read_text(encoding="utf-8") != text:
            print(f"{UNIT.relative_to(ROOT)} differs")
            bad += 1
        print("drops ok" if not bad else "re-run tools/make_firearms_drops.py")
        return 1 if bad else 0
    PNG.write_bytes(png_bytes(im))
    UNIT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {PNG.relative_to(ROOT)} ({im.width}x{im.height}) and {UNIT.relative_to(ROOT)} ({len(CELLS)} scenes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
