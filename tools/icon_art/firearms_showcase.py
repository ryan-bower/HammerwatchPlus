"""The Firearms Specialist's character-select figure (class_showcase.png, 32x32): the vanilla Ranger
figure with its bow, string and arrow removed and the t1 rifle icon held at port arms, stock at the
left hip and barrel over the right shoulder. The user asked for a normal character holding guns
(2026-10-22) in place of the hooded figure.
    python tools/icon_art/firearms_showcase.py [<out.png>] [a|b]   # b: a 20 px rifle (not used)
Writes <out> and <out>_x8.png (a preview, next to it; delete it when out is in the mod)."""
import sys
from pathlib import Path
from PIL import Image
REPO = str(Path(__file__).resolve().parents[2]) + "/"
out = sys.argv[1] if len(sys.argv) > 1 else REPO + "mods/firearms/players/hwp/firearms/class_showcase.png"
sh = Image.open(REPO + "gamecode/sdk/hoh2/players/class_showcase.png").convert("RGBA")
fig = sh.crop((64, 0, 96, 32)).copy()
icon = Image.open(REPO + "mods/firearms/items/hwp/firearms_items.png").convert("RGBA").crop((0, 0, 24, 24))
T = (0, 0, 0, 0)
SH = (0, 0, 0, 126)
px = fig.load()
def rgb(x, y): return px[x, y][:3]
BOW = {(0xac,0x58,0x40), (0x7f,0x39,0x2a), (0x60,0x2a,0x21), (0x3a,0x21,0x1a)}
STRING = {(0xc8,0xc8,0xc9), (0xa7,0xb8,0xcf), (0x7e,0x7f,0x7f), (0x72,0x80,0x92), (0xed,0xed,0xed), (0xab,0xab,0xab), (0xa9,0x63,0x3b)}
# the bow's limbs and tip (left of the body), the string outside the body
for y in range(32):
    for x in range(0, 13):
        if rgb(x, y) in BOW or (rgb(x, y) in STRING and y <= 18):
            px[x, y] = SH if y >= 21 else T
# the lower limb over the shadow (rows 26-30, right of the feet)
for y in range(26, 31):
    for x in range(13, 23):
        if rgb(x, y) in BOW:
            px[x, y] = SH
# the arrow's fletching at the bottom left
for y in range(26, 29):
    for x in range(9, 12):
        if rgb(x, y) in STRING:
            px[x, y] = T if y == 28 else SH
# the arrow shaft up the left arm (column 12, rows 13-16) and the string across the tunic
fill = {(12, 13): (0x91,0xad,0x5d), (12, 14): (0xa5,0xc1,0x6b), (12, 15): (0x61,0x7b,0x3f), (12, 16): (0x49,0x60,0x2e),
        (11, 18): (0x2b,0x39,0x1e), (11, 19): (0x49,0x60,0x2e), (12, 19): (0x49,0x60,0x2e),
        (12, 20): (0x39,0x48,0x25), (13, 20): (0x39,0x48,0x25), (14, 21): (0x1b,0x2b,0x15)}
for (x, y), c in fill.items():
    px[x, y] = c + (255,)
mode = sys.argv[2] if len(sys.argv) > 2 else "a"
if mode == "a":      # the icon as is, stock at the left hip, barrel over the right shoulder
    gun, pos = icon, (8, 5)
else:                # a smaller rifle
    gun = icon.resize((20, 20), Image.LANCZOS)
    pal = [icon.getpixel((x, y)) for y in range(24) for x in range(24) if icon.getpixel((x, y))[3]]
    g = gun.load()
    for y in range(20):
        for x in range(20):
            c = g[x, y]
            if c[3] < 128:
                g[x, y] = T
            else:
                g[x, y] = min(pal, key=lambda p: sum((p[i] - c[i]) ** 2 for i in range(3)))
    pos = (9, 7)
fig.alpha_composite(gun, pos)
fig.save(out)
fig.resize((256, 256), Image.NEAREST).save(out.replace(".png", "_x8.png"))
print("wrote", out)
