"""Builds the committed placeholder for the HoH1 Remastered specs' skill icons:
mods/classes/players/hwp/remastered/icons.png, 256x256 like HoH1's gui/icons_skills.png, with a
placeholder shape in each cell of import_hoh1.HOH1_REMASTERED_ICONS (one colour per class).
`import_hoh1.py classes` writes HoH1's own sheet over it in the gitignored hoh1art/ overlay.
python tools/make_remastered_icons.py"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_hoh1 import CLASSES_MODULE, HOH1_REMASTERED_ICONS  # noqa: E402

OUT = CLASSES_MODULE / "players/hwp/remastered/icons.png"
COLOURS = {"paladin": (214, 178, 90), "priest": (236, 226, 190), "ranger": (120, 196, 110),
           "sorcerer": (120, 180, 240), "warlock": (176, 120, 220), "wizard": (236, 120, 80),
           "rogue": (200, 200, 200), "warrior": (200, 90, 70)}


def shape(d, k, c):
    """one of six symbols in the 24x24 cell at the origin"""
    if k == 0:
        d.ellipse((7, 7, 16, 16), fill=c)
    elif k == 1:
        d.polygon([(12, 5), (19, 12), (12, 19), (5, 12)], fill=c)
    elif k == 2:
        d.rectangle((10, 6, 13, 17), fill=c); d.rectangle((6, 10, 17, 13), fill=c)
    elif k == 3:
        d.polygon([(12, 6), (18, 17), (6, 17)], fill=c)
    elif k == 4:
        d.rectangle((7, 7, 16, 16), outline=c, width=2)
    else:
        d.polygon([(13, 5), (8, 13), (12, 13), (10, 19), (16, 10), (12, 10)], fill=c)


def main():
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    for cls, cells in HOH1_REMASTERED_ICONS.items():
        for k, (x, y) in enumerate(cells.values()):
            cell = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
            d = ImageDraw.Draw(cell)
            d.rounded_rectangle((1, 1, 22, 22), radius=4, fill=(26, 30, 38, 255), outline=COLOURS[cls], width=2)
            shape(d, k % 6, COLOURS[cls])
            sheet.paste(cell, (x, y))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT, optimize=True)
    print(OUT, sum(len(c) for c in HOH1_REMASTERED_ICONS.values()), "cells")


if __name__ == "__main__":
    main()
