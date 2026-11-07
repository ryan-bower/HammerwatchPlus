#!/usr/bin/env python3
"""make_partyframes_art.py - bake the Striped edge shield for mods/partyframes.

One 102 wide strip per bar height (Thick 28 on top, Thin 14 below), bright end on the right.
The drawing right-aligns a shield's width in it, so per-pixel hatching costs one sprite.

    python tools/generate/make_partyframes_art.py
"""
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[2] / "mods/partyframes/gui/hwp_partyframes_stripes.png"
WIDTH = 102
SHEET = (128, 64)  # the engine refuses textures that are not a power of two
HEIGHTS = (28, 14)
RAMP = ((96, 150, 235), (124, 172, 245), (160, 200, 252), (190, 222, 255))
LINE = (0, 24, 200)
PATTERN = (.36, .4, .1, .06)  # alpha by diagonal, period 4


def over(under, top, alpha):
    """Straight-alpha `top` at `alpha` over an RGBA `under`."""
    r, g, b, a = under
    out = alpha + a * (1 - alpha)
    if out <= 0:
        return (0, 0, 0, 0)
    mix = [(t * alpha + u * a * (1 - alpha)) / out for t, u in zip(top, (r, g, b))]
    return (*mix, out)


def strip(height):
    px = {}
    last = len(RAMP) - 1
    for y in range(height):
        t = 1 - abs(y / (height - 1) * 2 - 1)
        col = RAMP[min(last, round(t * last))]
        for x in range(WIDTH):
            u = x / (WIDTH - 1)
            p = over((0, 0, 0, 0), col, .35 + .62 * u)
            p = over(p, LINE, PATTERN[(x + y) % len(PATTERN)] * (.4 + .6 * u))
            if x == WIDTH - 1:
                p = over(p, (255, 255, 255), .85)
            px[x, y] = p
    return px


def main():
    im = Image.new("RGBA", SHEET, (0, 0, 0, 0))
    top = 0
    for height in HEIGHTS:
        for (x, y), (r, g, b, a) in strip(height).items():
            im.putpixel((x, top + y), (round(r), round(g), round(b), round(a * 255)))
        top += height
    im.save(OUT)
    print(OUT, im.size)


if __name__ == "__main__":
    main()
