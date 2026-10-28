"""The Workshop preview cards: one card per package, all in one HammerwatchPlus look, drawn
from the game's own art and the modules' art, at the game's pixel scale.

    python tools/workshop_art.py            every card into dist/workshop-art/ (a look at them)
    python tools/workshop_art.py --sheet    the symbol check sheet: every module's symbol, named

tools/workshop.py calls cards() for the kit. A card is drawn at NATIVE size, as the game
draws its GUI, then scaled up SCALE times without smoothing:

  - the frame is the game's gold knotwork panel (gui/panelstyles.png), nine-sliced;
  - every symbol is a game or module sprite (SYMBOLS), in the game's octagon icon frame;
  - the text is the game's own pixel font (empire, size 16 with a 1 px outline, as
    gui/fonts/*.fnt use it); the HammerwatchPlus wordmark is UnifrakturMaguntia
    (tools/fonts/, SIL Open Font License), in the gold of the game's logo.

The base game's art comes from gamecode/sdk/hoh2 (tools/bootstrap.py, never committed), so
the cards are built on a machine with the game installed and are never committed either:
they go to dist/ and are uploaded as the Workshop images only."""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import gamepaths as paths  # noqa: E402
import hwr_archive as hwr  # noqa: E402

BASE = paths.BASE_HOH2
MODS = REPO / "mods"
OUT = REPO / "dist" / "workshop-art"
FONTS = BASE / "gui" / "fonts"
WORDMARK_FONT = REPO / "tools" / "fonts" / "UnifrakturMaguntia-Book.ttf"
NATIVE = (480, 270)
SCALE = 3

# the game's palette: panel brown, the gold of the logo and frames, the outline black
INK = (20, 14, 10)
PANEL = (33, 27, 22)
PANEL_LO = (24, 19, 15)
TEXT = (236, 226, 204)
DIM = (168, 156, 136)
GOLD_HI, GOLD, GOLD_LO = (255, 236, 140), (240, 184, 48), (176, 96, 24)
RED = (200, 52, 40)

# sprite sheets: name -> (path, cell size); a module path is mods/<...>
SHEETS = {
    "gui": ("gui/icons.png", 16),
    "town": ("gui/icons_town.png", 24),
    "pet": ("gui/pet_icons.png", 16),
    "skills": ("players/icons_skills.png", 24),
    "combo": ("players/icons_combo.png", 24),
    "special": ("items/icons_special.png", 24),
    "trade": ("items/icons_tradeware.png", 24),
    "food": ("items/icons_consumables.png", 24),
    "equip": ("items/icons_equipment.png", 24),
}


def cell(sheet, col, row):
    return (sheet, col, row)


def px(path, x, y, w, h):
    """A sprite by pixels: a game path, or mods/<module>/<path> for a module's own art."""
    return (path, x, y, w, h)


def mc(path, x, y, w, h, *colors):
    """A multicolour unit's frame, coloured: colors as the unit's Colorize block, per channel."""
    return ("multicolor", path, x, y, w, h, colors)


# the town's exit guard (actors/npcs/town/npc_misc_guard_exit.unit) in its colours: the idle
# frame facing the camera, helmet to knees (so it shows at twice its size)
EXIT_GUARD = mc("players/shared/units/mercenary_pikeman.tif", 113, 13, 14, 21,
                ("#4f2205", "#e9925c", "#fec79d"), ("#182426", "#829093", "#dff2f5"),
                ("#0D090B", "#382627", "#5c3e43"), ("#270f00", "#442606", "#b27f42"),
                ("#413025", "#ab947f", "#fff7dd"), ("#0e0400", "#411f0c", "#80593c"))


# every module's symbol: one sprite, or several where one thing is several (farming's crops)
SYMBOLS = {
    # Quality of Life
    "bufftips": [cell("gui", 11, 0)],
    "chatlinks": [cell("special", 9, 0)],
    "stash": [px("gui/icons.png", 13, 128, 13, 13)],
    "deathrecap": [px("gui/icons.png", 93, 77, 11, 11)],
    "laststats": [cell("town", 4, 4)],
    "colors": [px("gui/icons.png", 142, 11, 14, 13)],
    "waygates": [px("doodads/generic/generic.png", 0, 800, 32, 33)],
    "weaponswap": [cell("equip", 19, 3), px("gui/icons.png", 36, 63, 13, 12), cell("equip", 3, 3)],
    "summons": [cell("skills", 7, 1)],
    "petrooms": [px("gui/pet_icons.png", 131, 2, 16, 17), px("gui/icons.png", 96, 0, 12, 12)],  # a pet, the puzzle mark
    "legacy": [px("mods/legacy/gui/hwp_legacy.png", 0, 0, 16, 16)],
    "goldworth": [px("gui/icons.png", 0, 128, 13, 13)],
    "mmhmm": [cell("equip", 4, 11)],
    "orbwarn": [px("doodads/generic/skill_sphere.png", 0, 0, 10, 10)],
    "mapicons": [px("mods/hwplib/gui/hwp/map_icons.png", 12, 0, 11, 11)],
    # Co-op Play
    "groupcombo": [cell("combo", 0, 0)],
    "architect": [cell("town", 0, 0)],
    "droptrade": [px("gui/icons.png", 104, 77, 20, 12)],
    # Auto Aim
    "autoaim": [cell("skills", 6, 2)],
    # Firearms Specialist, Fourth Specializations
    "firearms": [px("mods/firearms/players/hwp/firearms/class_showcase.png", 0, 0, 32, 32)],
    "specs": [px("mods/specs/players/hwp/specs/icons.png", 0, 96, 24, 24)],
    # Keys and Ace Chests
    "keys": [cell("town", 0, 4), cell("town", 1, 4), cell("town", 2, 4),
             px("mods/keys/items/hwp/keys/key_ace.png", 0, 0, 16, 16)],
    # The Forsaken Tower
    "campaign": [cell("skills", 5, 15)],
    # Challenge Modes
    "mercenary": [cell("special", 6, 2)],
    "wavemode": [cell("town", 0, 6)],
    # Dungeon Loot and Encounters
    "puzzles": [px("gui/icons.png", 96, 0, 12, 12)],
    "objectives": [cell("town", 7, 3)],
    "strongbox": [px("items/misc/base.png", 100, 54, 16, 18)],
    "abyss": [cell("skills", 0, 6)],
    "maps": [px("items/quest/base.png", 16, 0, 16, 16)],      # the map drop (items/quest/quests.unit:seachart)
    "weapons": [cell("equip", 19, 3), cell("equip", 13, 3)],
    "trinkets": [px("mods/trinkets/gui/hwp/icons_trinkets_hoh1.png", 80, 16, 16, 16),    # frying pan
                 px("mods/trinkets/gui/hwp/icons_trinkets_hoh1.png", 0, 64, 16, 16)],    # lucky hat
    "valuables": [cell("trade", 0, 4)],
    # Town Life
    "fishing": [px("mods/fishing/gui/hwp/rods.png", 0, 0, 16, 16), px("mods/fishing/items/hwp/fish.png", 96, 0, 24, 24)],
    "farming": [px("mods/farming/doodads/hwp/farm.png", 64, 0, 16, 16),        # the watering can
                px("doodads/terrain/crops.png", 31, 0, 19, 16), px("doodads/terrain/crops.png", 108, 0, 14, 22)],
    "gambler": [px("mods/gambler/gui/hwp/token.png", 0, 0, 16, 16), cell("town", 7, 4)],
    "roulette": [px("mods/roulette/doodads/hwp/roulette_wheel.png", 0, 0, 32, 32)],
    "tavern": [cell("town", 5, 0)],
    # Pets
    "pets": [px("gui/pet_icons.png", 3, 2, 16, 17)],
    # HoH1 Classes (held)
    "classes": [px("mods/classes/players/hwp/thief/class_showcase.png", 0, 0, 64, 64)],
}


def _tiff_samples(data: bytes):
    """A game TIFF PIL can't read: uncompressed, 8 bits, interleaved, RGBA and then one mask per
    multicolour channel. (width, height, samples per pixel, the pixel bytes)."""
    import struct
    e = "<" if data[:2] == b"II" else ">"
    (ifd,) = struct.unpack_from(e + "I", data, 4)
    (count,) = struct.unpack_from(e + "H", data, ifd)
    tags = {}
    for i in range(count):
        tag, typ, n, raw = struct.unpack_from(e + "HHI4s", data, ifd + 2 + 12 * i)
        if n == 1 and typ in (3, 4):
            tags[tag] = struct.unpack(e + ("H" if typ == 3 else "I"), raw[:2 if typ == 3 else 4])[0]
    w, h, spp = tags[256], tags[257], tags[277]
    if tags.get(259, 1) != 1 or tags.get(284, 1) != 1 or tags.get(258) != 8 or spp < 4:
        raise ValueError("an uncompressed, interleaved 8-bit TIFF with 4+ samples")
    return w, h, spp, data[tags[273]:tags[273] + w * h * spp]


def _tiff_rgba(data: bytes):
    from PIL import Image
    w, h, spp, px = _tiff_samples(data)
    rgba = bytearray(w * h * 4)
    for c in range(4):
        rgba[c::4] = px[c::spp]
    return Image.frombytes("RGBA", (w, h), bytes(rgba))


def _hex(c: str):
    return tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=None)
def multicolor(rel: str, colors: tuple):
    """A multicolour unit sprite (a TIFF with a mask per colour channel) coloured as a unit's
    Colorize block colours it: in a masked pixel the grey is the shade, from the channel's dark
    colour at 0 through its mid at 128 to its bright at 255; other pixels keep their colour.
    colors: one (dark, mid, bright) of hex strings per channel."""
    from PIL import Image
    w, h, spp, px = _tiff_samples((BASE / rel).read_bytes())
    ramps = [[_hex(c) for c in ch] for ch in colors]
    out = bytearray(w * h * 4)
    for i in range(w * h):
        p = px[i * spp:(i + 1) * spp]
        r, g, b, a = p[0], p[1], p[2], p[3]
        for ch, m in enumerate(p[4:4 + len(ramps)]):
            if m >= 128:
                lo, hi, t = (ramps[ch][0], ramps[ch][1], r / 128) if r < 128 else (ramps[ch][1], ramps[ch][2], (r - 128) / 127)
                r, g, b = (round(lo[k] + (hi[k] - lo[k]) * t) for k in range(3))
                break
        out[i * 4:i * 4 + 4] = bytes((r, g, b, a))
    return Image.frombytes("RGBA", (w, h), bytes(out))


def _open(path: Path):
    from PIL import Image, UnidentifiedImageError
    data = path.read_bytes()
    if hwr.is_texture(data):
        data = hwr.texture_to_png(data)
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except UnidentifiedImageError:
        return _tiff_rgba(data)


@lru_cache(maxsize=None)
def image(rel: str):
    """A sheet: mods/... from the repo, else the game's own (gamecode/sdk/hoh2)."""
    p = REPO / rel if rel.startswith("mods/") else BASE / rel
    if not p.is_file():
        raise SystemExit(f"workshop_art: {p} is missing (run tools/bootstrap.py for the game's art)")
    return _open(p)


def sprite(ref):
    """A symbol reference -> the sprite, trimmed to its pixels."""
    if ref[0] == "multicolor":
        _, rel, x, y, w, h, colors = ref
        im = multicolor(rel, colors).crop((x, y, x + w, y + h))
        bb = im.getchannel("A").getbbox()
        return im.crop(bb) if bb else im
    if len(ref) == 3:
        sheet, col, row = ref
        rel, size = SHEETS[sheet]
        box = (col * size, row * size, col * size + size, row * size + size)
    else:
        rel, x, y, w, h = ref
        box = (x, y, x + w, y + h)
    im = image(rel).crop(box)
    bb = im.getchannel("A").getbbox()
    return im.crop(bb) if bb else im


# --- text --------------------------------------------------------------------------------

@lru_cache(maxsize=None)
def font(name: str, size: int = 16):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / f"{name}.ttf" if not name.endswith(".ttf") else name), size)


def text_layer(s: str, f, fill, outline=INK, shadow=False):
    """Text as the game draws it: no smoothing, a 1 px outline (and a drop shadow)."""
    from PIL import Image, ImageDraw
    l, t, r, b = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), s, font=f)
    w, h = r - l + 4, b - t + 4
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.fontmode = "1"
    md.text((2 - l, 2 - t), s, font=f, fill=255)
    out = Image.new("RGBA", (w + (1 if shadow else 0), h + (1 if shadow else 0)), (0, 0, 0, 0))
    ring = mask.copy()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            ring.paste(255, (0, 0), _shift(mask, dx, dy))
    if shadow:
        out.paste(outline, (1, 1), ring)
    out.paste(outline, (0, 0), ring)
    if callable(fill):
        out.paste(fill(w, h), (0, 0), mask)
    else:
        out.paste(fill, (0, 0), mask)
    return out


def _shift(mask, dx, dy):
    from PIL import ImageChops
    return ImageChops.offset(mask, dx, dy)


def text_width(s: str, f) -> int:
    from PIL import Image, ImageDraw
    l, _, r, _ = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), s, font=f)
    return r - l


def gold_ramp(w, h):
    """The logo's gold: pale at the top, deep orange at the foot, in hard bands."""
    from PIL import Image
    im = Image.new("RGB", (w, h))
    stops = [GOLD_HI, (255, 214, 92), GOLD, (220, 140, 36), GOLD_LO]
    for y in range(h):
        im.paste(stops[min(len(stops) - 1, y * len(stops) // max(1, h))], (0, y, w, y + 1))
    return im


def wordmark(size: int):
    """HammerwatchPlus in blackletter, gold on a black outline with a drop shadow."""
    from PIL import ImageFont
    f = ImageFont.truetype(str(WORDMARK_FONT), size)
    return text_layer("HammerwatchPlus", f, gold_ramp, shadow=True)


# --- frames ------------------------------------------------------------------------------

def gold_frame(w: int, h: int):
    """The game's gold knotwork panel frame (gui/panelstyles.png 72,40 47x47, 8 px border),
    nine-sliced to w x h: corners as they are, edges repeated."""
    from PIL import Image
    src = image("gui/panelstyles.png").crop((72, 40, 119, 87))
    B, S = 8, 47
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mid = S - 2 * B

    def run(piece_box, x0, y0, length, horizontal):
        piece = src.crop(piece_box)
        pos = 0
        while pos < length:
            n = min(mid, length - pos)
            p = piece.crop((0, 0, n, piece.height) if horizontal else (0, 0, piece.width, n))
            out.paste(p, (x0 + pos, y0) if horizontal else (x0, y0 + pos))
            pos += n
    run((B, 0, S - B, B), B, 0, w - 2 * B, True)
    run((B, S - B, S - B, S), B, h - B, w - 2 * B, True)
    run((0, B, B, S - B), 0, B, h - 2 * B, False)
    run((S - B, B, S, S - B), w - B, B, h - 2 * B, False)
    for sx, sy, dx, dy in ((0, 0, 0, 0), (S - B, 0, w - B, 0), (0, S - B, 0, h - B), (S - B, S - B, w - B, h - B)):
        out.paste(src.crop((sx, sy, sx + B, sy + B)), (dx, dy))
    return out


def icon_frame():
    """The game's octagon icon frame (gui/gui.png icon-frame 411,97 32x32)."""
    return image("gui/gui.png").crop((411, 97, 443, 129))


def fit(sp, box: int):
    """A sprite at the largest whole scale that fits a box x box slot (pixel art stays crisp)."""
    from PIL import Image
    k = max(1, box // max(sp.width, sp.height))
    if max(sp.width, sp.height) > box:
        k = 1
        sp = sp.resize((max(1, sp.width * box // max(sp.width, sp.height)),
                        max(1, sp.height * box // max(sp.width, sp.height))), Image.NEAREST)
    return sp.resize((sp.width * k, sp.height * k), Image.NEAREST) if k > 1 else sp


def badge(canvas, icons, x, y, slot=32):
    """Icons side by side, each in a slot x slot square (the game's octagon icon frame when the
    slot is 32); returns the width used."""
    fr = icon_frame() if slot == 32 else None
    inner = 24 if fr is not None else slot
    cx = x
    for ref in icons:
        sp = fit(sprite(ref), inner)
        if fr is not None:
            canvas.alpha_composite(fr, (cx, y))
        canvas.alpha_composite(sp, (cx + (slot - sp.width) // 2, y + (slot - sp.height) // 2))
        cx += slot - (2 if fr is not None else -1)
    return cx - x


# --- cards -------------------------------------------------------------------------------

def canvas(title: str, subtitle: str = "", prereq: str = ""):
    """The shared card: dark panel, gold frame, the wordmark, the package's name; at the foot
    the game and multiplayer, and in red what the package needs beyond the game."""
    from PIL import Image, ImageDraw
    W, H = NATIVE
    im = Image.new("RGBA", (W, H), PANEL + (255,))
    d = ImageDraw.Draw(im)
    for y in range(0, H, 2):            # the panel's fine stripes, as the game's inventory panels
        d.line([(0, y), (W, y)], fill=PANEL_LO + (255,))
    im.alpha_composite(gold_frame(W, H))
    wm = wordmark(30)
    im.alpha_composite(wm, ((W - wm.width) // 2, 8))
    y = 8 + wm.height
    d.line([(40, y + 1), (W - 41, y + 1)], fill=GOLD_LO + (255,))
    d.line([(40, y), (W - 41, y)], fill=GOLD + (255,))
    t = text_layer(title, font("empire_9h"), TEXT, shadow=True)
    t = t.resize((t.width * 2, t.height * 2), Image.NEAREST) if t.width * 2 < W - 40 else t
    im.alpha_composite(t, ((W - t.width) // 2, y + 5))
    y += 5 + t.height
    if subtitle:
        s = text_layer(subtitle, font("empire_7p"), DIM)
        im.alpha_composite(s, ((W - s.width) // 2, y))
        y += s.height
    foot = text_layer("Heroes of Hammerwatch II  -  multiplayer supported", font("empire_7p"), DIM)
    fy = H - 10 - foot.height
    if prereq:
        r = text_layer(prereq, font("empire_7p"), (255, 120, 96))
        im.alpha_composite(foot, (16, fy))
        im.alpha_composite(r, (W - 16 - r.width, fy))
    else:
        im.alpha_composite(foot, ((W - foot.width) // 2, fy))
    return im, y + 4, fy - 2


def tiles_card(title, tiles, subtitle="", prereq=""):
    """tiles: (label, [sprite refs]) or (label, [sprite refs], note); a grid of symbols with
    their names, as many columns as the longest name allows."""
    im, top, bottom = canvas(title, subtitle, prereq)
    W, _ = NATIVE
    n = len(tiles)
    if n <= 8:
        return big_tiles(im, top, bottom, tiles)
    lab, small = font("empire_7h"), font("empire_7p")
    widest = max(text_width(t[0], lab) + 34 * len(t[1]) + 8 for t in tiles)
    cols = max(1, min(3, (W - 40) // widest, n))
    rows = (n + cols - 1) // cols
    while rows > 1 and (bottom - top) // rows < 22 and cols < 3:
        cols += 1
        rows = (n + cols - 1) // cols
    row_h = min(44, (bottom - top) // rows)
    slot = 32 if row_h >= 33 else max(16, row_h - 2)
    colw = (W - 40) // cols
    y0 = top + max(0, (bottom - top - rows * row_h) // 2)
    for i, t in enumerate(tiles):
        label, icons = t[0], t[1]
        c, r = i // rows, i % rows
        x = 20 + c * colw + (8 if cols == 1 else 0)
        y = y0 + r * row_h + (row_h - slot) // 2
        used = badge(im, icons, x, y, slot)
        tl = text_layer(label, lab, TEXT)
        if len(t) > 2 and t[2]:
            nl = text_layer(t[2], small, DIM)
            ty = y + (slot - tl.height - nl.height + 2) // 2
            im.alpha_composite(tl, (x + used + 3, ty))
            im.alpha_composite(nl, (x + used + 3, ty + tl.height - 2))
        else:
            im.alpha_composite(tl, (x + used + 3, y + (slot - tl.height) // 2))
    return im


def big_tiles(im, top, bottom, tiles):
    """Up to eight entries: one or two columns of framed symbols, each with its name in the
    title font and a few words under it; the symbols as large as the card's width allows."""
    from PIL import ImageDraw
    W, _ = NATIVE
    d = ImageDraw.Draw(im)
    n = len(tiles)
    cols = 1 if (bottom - top) // n >= 36 else 2
    rows = (n + cols - 1) // cols
    row_h = min(64, (bottom - top) // rows)
    lab, small = font("empire_9h"), font("empire_7p")
    gap = 18
    sets = [tiles[c * rows:(c + 1) * rows] for c in range(cols)]
    textw = [max(max(text_width(t[0], lab), text_width(t[2] if len(t) > 2 else "", small)) for t in cs)
             for cs in sets]
    for slot in range(min(48, row_h - 6), 27, -2):
        iconw = [max(len(t[1]) for t in cs) * (slot + 4) for cs in sets]
        total = sum(iconw) + sum(textw) + 4 * cols + gap * (cols - 1)
        if total <= W - 36:
            break
    else:
        raise ValueError(f"tiles too wide for a card: {[t[0] for t in tiles]}")
    y0 = top + max(0, (bottom - top - rows * row_h) // 2)
    x = (W - total) // 2
    for c, cs in enumerate(sets):
        tx = x + iconw[c] + 4
        for r, t in enumerate(cs):
            y = y0 + r * row_h + (row_h - slot) // 2
            cx = tx - 4 - len(t[1]) * (slot + 4)     # the symbols sit right against the name
            for ref in t[1]:
                sp = fit(sprite(ref), slot - 6)
                d.rectangle([cx, y, cx + slot - 1, y + slot - 1], fill=PANEL_LO + (255,), outline=GOLD + (255,))
                d.rectangle([cx + 1, y + 1, cx + slot - 2, y + slot - 2], outline=GOLD_LO + (255,))
                im.alpha_composite(sp, (cx + (slot - sp.width) // 2, y + (slot - sp.height) // 2))
                cx += slot + 4
            tl = text_layer(t[0], lab, TEXT)
            note = t[2] if len(t) > 2 else ""
            if note:
                nl = text_layer(note, small, DIM)
                ty = y + (slot - tl.height - nl.height + 2) // 2
                im.alpha_composite(tl, (tx, ty))
                im.alpha_composite(nl, (tx, ty + tl.height - 2))
            else:
                im.alpha_composite(tl, (tx, y + (slot - tl.height) // 2))
        x = tx + textw[c] + gap
    return im


def game_pets() -> list:
    """Every pet the game's Pet Shop sells, as its own shop icon (tweak/pets.sval), in order."""
    text = re.sub(r"<!--.*?-->", "", (BASE / "tweak" / "pets.sval").read_text(encoding="utf-8"), flags=re.S)
    out = []
    for d in re.findall(r"<dict>(.*?)</dict>", text, re.S):
        m = re.search(r'name="icon"><s>([^<]+)</s><i>\d+</i><vec4>(\d+) (\d+) (\d+) (\d+)</vec4>', d)
        if m and re.search(r'name="unit">[^<]+<', d):     # "none", the no-pet entry, has no unit
            out.append(px(m.group(1), *map(int, m.groups()[1:])))
    return out


def showcase_card(title, icons, lines, subtitle="", prereq=""):
    """A row of large framed symbols (every pet, say), and under it a few lines of what is in it."""
    from PIL import ImageDraw
    im, top, bottom = canvas(title, subtitle, prereq)
    W, _ = NATIVE
    d = ImageDraw.Draw(im)
    gap = 6
    slot = min(52, (W - 40 - gap * (len(icons) - 1)) // len(icons))
    lab = font("empire_7h")
    line_h = 13
    block = slot + 12 + line_h * len(lines)
    y = top + max(0, (bottom - top - block) // 2)
    x = (W - (len(icons) * slot + gap * (len(icons) - 1))) // 2
    for ref in icons:
        sp = fit(sprite(ref), slot - 8)
        d.rectangle([x, y, x + slot - 1, y + slot - 1], fill=PANEL_LO + (255,), outline=GOLD + (255,))
        d.rectangle([x + 1, y + 1, x + slot - 2, y + slot - 2], outline=GOLD_LO + (255,))
        im.alpha_composite(sp, (x + (slot - sp.width) // 2, y + (slot - sp.height) // 2))
        x += slot + gap
    y += slot + 12
    for ln in lines:
        t = text_layer(ln, lab, TEXT)
        im.alpha_composite(t, ((W - t.width) // 2, y))
        y += line_h
    return im


def kit_card(title, groups, per_skill: bool, subtitle="", prereq=""):
    """groups: (heading, [(skill ref, [orb refs])]); every ability (gold edge) with its orbs.
    per_skill: a row per ability, the group's name on its first row (a class's kit);
    otherwise a block per group, its name above and all its abilities on one row (the specs)."""
    from PIL import ImageDraw
    im, top, bottom = canvas(title, subtitle, prereq)
    W, _ = NATIVE
    d = ImageDraw.Draw(im)
    head_f = font("empire_7h")
    colw = (W - 36) // 2

    def skill_row(x, y, skill, orbs):
        sp = fit(sprite(skill), 24)
        im.alpha_composite(sp, (x, y))
        d.rectangle([x - 1, y - 1, x + 24, y + 24], outline=GOLD + (255,))
        ox = x + 28
        for o in orbs:
            if o == skill:
                continue
            op = fit(sprite(o), 22)
            im.alpha_composite(op, (ox, y + (24 - op.height) // 2))
            ox += 23
        return ox

    if per_skill:
        rows = [(h if j == 0 else "", sk) for h, sks in groups for j, sk in enumerate(sks)]
        # columns break between groups, as evenly as the groups allow
        half, acc, split = len(rows) / 2, 0, len(groups)
        for gi, (_, sks) in enumerate(groups):
            if acc + len(sks) / 2 >= half:
                split = gi if abs(acc - half) <= abs(acc + len(sks) - half) else gi + 1
                break
            acc += len(sks)
        left = sum(len(s) for _, s in groups[:split])
        cols = [rows[:left], rows[left:]]
        pitch = min(27, (bottom - top) // max(len(c) for c in cols))
        for ci, col in enumerate(cols):
            for ri, (head, (skill, orbs)) in enumerate(col):
                x, y = 18 + ci * colw + ci * 4, top + 2 + ri * pitch
                ox = skill_row(x, y, skill, orbs)
                if head:
                    t = text_layer(head, head_f, GOLD)
                    im.alpha_composite(t, (max(ox + 4, x + colw - 8 - t.width), y + (24 - t.height) // 2))
    else:
        per = (len(groups) + 1) // 2
        pitch = min(40, (bottom - top) // per)
        for gi, (head, sks) in enumerate(groups):
            ci, ri = gi // per, gi % per
            x, y = 18 + ci * colw + ci * 4, top + ri * pitch
            t = text_layer(head, head_f, GOLD)
            im.alpha_composite(t, (x - 1, y - 1))
            ox, yy = x, y + t.height - 1
            for skill, orbs in sks:
                ox = skill_row(ox + 1, yy, skill, orbs) + 4
    return im


def save(im, path: Path) -> Path:
    from PIL import Image
    big = im.convert("RGB").resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    big.save(path, optimize=True)
    return path


# --- class kits --------------------------------------------------------------------------

def lang_strings(mod: str) -> dict:
    out = {}
    for f in (MODS / mod / "res").rglob("*.lang"):
        out.update(re.findall(r'<string name="([^"]+)">([^<]*)<', f.read_text(encoding="utf-8")))
    return out


ICON = re.compile(r'<string name="name">\.([^<]+)</string>|<array name="icon">\s*<s(?:tring)?>([^<]+)</s(?:tring)?>\s*<i(?:nt)?>\d+</i(?:nt)?>\s*<vec4>([\d ]+)</vec4>')


def skill_icons(mod: str, rel: str):
    """A skill file -> [(name key, sprite ref)]: the skill, then its orbs, in file order."""
    text = (MODS / mod / rel).read_text(encoding="utf-8")
    out, name = [], None
    for m in ICON.finditer(text):
        if m.group(1):
            name = m.group(1)
        else:
            x, y, w, h = (int(v) for v in m.group(3).split())
            path = m.group(2)
            ref = px(f"mods/{mod}/{path}", x, y, w, h) if (MODS / mod / path).is_file() else px(path, x, y, w, h)
            out.append((name, ref))
            name = None
    return out


def class_kit(mod: str, class_rel: str, own: str):
    """[(subclass name, [(skill ref, [orb refs])])] for the skills under players/hwp/<own>."""
    text = (MODS / mod / class_rel).read_text(encoding="utf-8")
    lang = lang_strings(mod)
    groups, seen = [], set()
    for block in re.split(r"\n\t<dict>", text)[1:]:
        nm = re.search(r'<string name="name">\.([^<]+)</string>', block)
        skills = [s for s in re.findall(r"<string>(players/hwp/[^<]+\.sval)</string>", block)
                  if s.startswith(f"players/hwp/{own}") and s not in seen]
        if not nm or not skills:
            continue
        seen.update(skills)
        kit = []
        for s in skills:
            icons = skill_icons(mod, s)
            if icons and icons[0][1][0].startswith("mods/"):    # its own art, not a vanilla skill's
                kit.append((icons[0][1], [r for _, r in icons[1:]]))
        groups.append((lang.get(nm.group(1), nm.group(1)), kit))
    return groups


# --- the cards per package ---------------------------------------------------------------

def module_title(mod: str) -> str:
    sys.path.insert(0, str(REPO / "tools"))
    import workshop
    return workshop.module_title(mod)


CHEST = {t: px("items/misc/base.png", 100, y, 16, 18) for t, y in (("bronze", 0), ("silver", 18), ("gold", 36))}
# the ace chest: mods/keys/tweak/hwp/chest_art.sval u_gold_large, the red-lidded gold chest
ACE_CHEST = px("items/misc/base.png", 70, 54, 14, 18)
FEATURES = {
    # single-module packages: what is inside, as tiles (label, symbols, a few words)
    "autoaim": [("Reticle snaps on", [cell("skills", 6, 2)], "to the enemy in your aim cone"),
                ("Auto fire, auto skills", [cell("skills", 0, 4)], "ready skills cast themselves"),
                ("Controller or mouse", [px("gui/icons.png", 204, 171, 13, 13), px("gui/icons.png", 33, 114, 11, 14)],
                 "on for controllers by default")],
    "keys": [("Keys", [cell("town", 0, 4), cell("town", 1, 4), cell("town", 2, 4)], "one for each chest tier"),
             ("Locked chests", [CHEST["bronze"], CHEST["silver"], CHEST["gold"]], "keys drop in runs"),
             ("Ace chests", [px("mods/keys/items/hwp/keys/key_ace.png", 0, 0, 16, 16), ACE_CHEST],
              "the red ace key, 7 legendaries"),
             ("Exit guard shop", [EXIT_GUARD], "keys, bag slots, trinkets")],
    "campaign": [("The Forsaken Tower", [cell("skills", 5, 15)], "18 floors, 6 bosses, Mines to Battlements"),
                 ("A portal in town", [cell("town", 2, 1)], "on the chapel courtyard campfire"),
                 ("Traps and tricks", [cell("town", 6, 2), cell("skills", 3, 15)], "spikes, flame jets, teleporters")],
    "classes": [("Thief", [px("mods/classes/players/hwp/thief/class_showcase.png", 0, 0, 64, 64)]),
                ("Gladiator", [px("mods/classes/players/hwp/gladiator/class_showcase.png", 0, 0, 64, 64)]),
                ("Witch Hunter", [px("mods/classes/players/hwp/witchhunter/class_showcase.png", 0, 0, 64, 64)])],
}
# a few words per module, on the cards with room for them
NOTES = {
    "groupcombo": "party combo bonus, combo orbs", "architect": "everyone picks and pays",
    "droptrade": "drop gear for friends", "mercenary": "enlist, rank up, die for good",
    "wavemode": "survival arena, from a town statue", "fishing": "on the coast and run floors",
    "farming": "crops and Holy Herbs", "gambler": "Higher or Lower, rerolls",
    "roulette": "one table, whole lobby", "tavern": "three more tavern levels",
    "puzzles": "puzzle rooms on most floors", "objectives": "levers, vaults, sealed exits",
    "strongbox": "open it, beat the pack, loot", "abyss": "waves of enemies, deeper is richer",
    "maps": "three new map layouts", "weapons": "twelve ilvl 35 weapons",
    "trinkets": "scale with NG+, 37 more", "valuables": "worth twice the gold",
}
def prereq(pids) -> str:
    """The card's red footer: what in these packages needs a DLC (tools/workshop.py DLC)."""
    import workshop
    return ", ".join(f"{card}: {dlc} DLC" for dlc, _, card in (workshop.DLC[p] for p in pids if p in workshop.DLC))
# the All pack's cover: a short name and what the package is, in a few words
SHORT = {
    "qol": ("Quality of Life", "15 helpers"), "coop": ("Co-op Play", "3 party features"),
    "autoaim": ("Auto Aim", "aim assist"), "firearms": ("Firearms", "a new class"),
    "specs": ("4th Specs", "8 new specializations"),
    "keys": ("Keys & Chests", "locked loot, ace chests"), "campaign": ("Forsaken Tower", "18-floor campaign"),
    "modes": ("Challenge Modes", "mercenary, wave arena"), "dungeon": ("Dungeon Loot", "8 run features"),
    "town": ("Town Life", "fish, farm, gamble"), "pets": ("Pets", "levels, skills, dyes"),
}


def cover_icons(pid: str) -> list:
    """A package's few symbols on the All pack's cover: what its own card shows most."""
    if pid == "firearms":
        return [SYMBOLS["firearms"][0]] + [sk for sk, _ in class_kit(
            "firearms", "players/hwp/firearms/class_firearms.sval", "firearms")[0][1][:2]]
    if pid == "specs":
        return [sks[0][0] for _, sks in class_kit("specs", "players/hwp/specs/class_specs.sval", "specs")[:3]]
    if pid == "pets":
        return game_pets()[:3]
    return COVER.get(pid) or [t[1][-1] for t in FEATURES[pid]][:3]


# the cover's symbols for the packages of several modules: one each from three of them
COVER = {
    "qol": [SYMBOLS["bufftips"][0], SYMBOLS["waygates"][0], SYMBOLS["orbwarn"][0]],
    "coop": [SYMBOLS["groupcombo"][0], SYMBOLS["architect"][0], SYMBOLS["droptrade"][0]],
    "modes": [SYMBOLS["mercenary"][0], SYMBOLS["wavemode"][0]],
    "dungeon": [SYMBOLS["strongbox"][0], SYMBOLS["trinkets"][0], SYMBOLS["abyss"][0]],
    "town": [SYMBOLS["fishing"][0], SYMBOLS["farming"][0], SYMBOLS["roulette"][0]],
    "keys": [px("mods/keys/items/hwp/keys/key_ace.png", 0, 0, 16, 16), ACE_CHEST, EXIT_GUARD],
}


def package_card(pkg: dict):
    pid = pkg["id"]
    title = pkg["name"].split(": ", 1)[-1]
    need = prereq([pid])
    if pid == "firearms":
        groups = class_kit("firearms", "players/hwp/firearms/class_firearms.sval", "firearms")
        groups = [("Core" if h == title else h, sks) for h, sks in groups]
        return kit_card(title, groups, True, "", need)
    if pid == "specs":
        groups = class_kit("specs", "players/hwp/specs/class_specs.sval", "specs")
        return kit_card(title, groups, False, "", need)
    if pid == "pets":
        return showcase_card(title, game_pets(), ["Pets level up and learn skills at the Pet Shop",
                                                  "Pet dyes at the tailor", "Pickup toggles for each pet",
                                                  "Pets wait outside trap and puzzle rooms"], "", need)
    if len(pkg["mods"]) == 1 and pid in FEATURES:
        return tiles_card(title, FEATURES[pid], "", need)
    return tiles_card(title, [(module_title(m), SYMBOLS[m], NOTES.get(m, "")) for m in pkg["mods"]], "", need)


def all_card(packages: list[dict], held: set[str] = frozenset()):
    """The All pack's cover: every package it names (not the held ones), a few of its symbols
    and what it is."""
    shown = [p for p in packages if p["id"] not in held]
    tiles = [(SHORT[p["id"]][0], cover_icons(p["id"]), SHORT[p["id"]][1]) for p in shown]
    mods = sum(len(p["mods"]) for p in shown)
    return tiles_card("All Packages", tiles, f"{len(shown)} packages, {mods} modules, one subscription",
                      prereq([p["id"] for p in shown]))


def symbol_sheet():
    """Every module's symbol with its id: the check that each ref points at the right art."""
    from PIL import Image
    mods = list(SYMBOLS)
    W, H = 480, 12 + 34 * ((len(mods) + 2) // 3)
    im = Image.new("RGBA", (W, H), PANEL + (255,))
    for i, m in enumerate(mods):
        x, y = 6 + (i % 3) * 158, 6 + (i // 3) * 34
        used = badge(im, SYMBOLS[m], x, y)
        im.alpha_composite(text_layer(m, font("empire_7p"), TEXT), (x + used + 2, y + 10))
    return im


def cards(packages: list[dict], held: set[str] = frozenset()) -> dict[str, object]:
    """package id (or "all") -> card image, for tools/workshop.py. held: package ids whose own
    item is on hold (the All pack names them by what they give now)."""
    out = {p["id"]: package_card(p) for p in packages}
    out["all"] = all_card(packages, held)
    return out


def held_ids() -> set[str]:
    led = json.loads((REPO / "workshop.json").read_text(encoding="utf-8"))
    return {k[4:] for k, v in led["items"].items() if v.get("hold") and k.startswith("HWP-")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", action="store_true", help="the symbol check sheet only")
    args = ap.parse_args(argv)
    if args.sheet:
        print(save(symbol_sheet(), OUT / "symbols.png"))
        return 0
    pk = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    for pid, im in cards(pk["packages"], held_ids()).items():
        print(save(im, OUT / f"{pid}.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
