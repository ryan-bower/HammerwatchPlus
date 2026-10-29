"""Builds mods/roulette/doodads/hwp/roulette_wheel.png: the roulette wheel that sits on a
tavern table (doodads/hwp/hwp_roulette_wheel.unit), drawn from scratch (no game art).

FRAMES frames, each FW x FH, COLS a row on a power-of-two sheet (the game refuses other
sizes): frame i at x = (i % COLS) * FW, y = (i // COLS) * ROW. The wheel seen from the usual
three-quarter view, turned 360 / FRAMES degrees a frame (the pockets in the real
single-zero order), so looping the frames spins it one turn. The unit plays them slowly
when idle and fast while the lobby's spin runs.

    python tools/make_roulette_art.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "mods" / "roulette" / "doodads" / "hwp" / "roulette_wheel.png"

FRAMES = 24
FW, FH = 32, 22
COLS, ROW = 8, 32
SHEET = (256, 128)
S = 8                      # drawn at S times the size, then reduced
SQUASH = 0.58              # the disc's height over its width in the view
DEPTH = 3                  # the bowl's side, in pixels

WHEEL = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16,
         33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

WOOD = (122, 70, 34, 255)
WOOD_DARK = (74, 40, 20, 255)
WOOD_LIGHT = (160, 98, 50, 255)
GOLD = (226, 186, 74, 255)
RED = (190, 30, 28, 255)
BLACK = (24, 22, 24, 255)
GREEN = (24, 140, 60, 255)


def disc(angle: float) -> Image.Image:
    """The wheel from straight above, turned by angle (radians), size R*2 square."""
    R = 14 * S
    im = Image.new("RGBA", (R * 2, R * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = lambda r: (R - r, R - r, R + r, R + r)
    d.ellipse(box(R), fill=WOOD)
    d.ellipse(box(int(R * 0.93)), fill=WOOD_LIGHT)
    d.ellipse(box(int(R * 0.88)), fill=GOLD)
    # the pockets
    step = 360.0 / len(WHEEL)
    base = math.degrees(angle)
    for i, n in enumerate(WHEEL):
        col = GREEN if n == 0 else RED if n in REDS else BLACK
        a0 = base + i * step
        d.pieslice(box(int(R * 0.86)), a0 + 0.6, a0 + step - 0.6, fill=col)
    # the cone, with its four turning spokes
    d.ellipse(box(int(R * 0.66)), fill=WOOD_DARK)
    d.ellipse(box(int(R * 0.60)), fill=WOOD)
    for k in range(4):
        a = angle + k * math.pi / 2
        x, y = R + math.cos(a) * R * 0.55, R + math.sin(a) * R * 0.55
        d.line((R, R, x, y), fill=GOLD, width=int(S * 1.4))
        d.ellipse((x - S, y - S, x + S, y + S), fill=GOLD)
    d.ellipse(box(int(R * 0.16)), fill=GOLD)
    return im


def frame(i: int) -> Image.Image:
    big = Image.new("RGBA", (FW * S, FH * S), (0, 0, 0, 0))
    top = disc(2 * math.pi * i / FRAMES)
    w, h = top.width, int(top.height * SQUASH)
    top = top.resize((w, h), Image.LANCZOS)
    x0 = (big.width - w) // 2
    y0 = S
    # the bowl's side: dark wood ellipses down to DEPTH under the rim
    side = ImageDraw.Draw(big)
    for dy in range(DEPTH * S, 0, -S // 2):
        side.ellipse((x0, y0 + dy, x0 + w, y0 + dy + h), fill=WOOD_DARK)
    big.alpha_composite(top, (x0, y0))
    small = big.resize((FW, FH), Image.BOX)
    # hard edges: pixel art, no half-clear pixels
    px = small.load()
    for y in range(FH):
        for x in range(FW):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)
    return small


def main() -> None:
    sheet = Image.new("RGBA", SHEET, (0, 0, 0, 0))
    for i in range(FRAMES):
        sheet.paste(frame(i), ((i % COLS) * FW, (i // COLS) * ROW))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)} ({FRAMES} frames of {FW}x{FH})")


if __name__ == "__main__":
    main()
