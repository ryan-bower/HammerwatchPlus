"""Writes the 4th specializations' visual effects, mods/specs/players/hwp/specs/effects/*.effect:
vanilla effects (gamecode/sdk/hoh2) recoloured for each spec, and fx.png, the bespoke world
sprites (art/specs/fx/*.png, from tools/icon_art/sp_fx.py) packed into one 256x128 sheet (the
texture loader wants powers of two). The standard's flag comes from that sheet; branded_sigil,
claw and orb.effect are hand-written and read it at the FX_SHEET offsets.

python tools/make_specs_fx.py [--check]

recolour() rewrites the colours in an effect: sprite color-r/g/b attributes, light
<color-r value=..>, particle color="r g b a; ..." lists and color-mul="r;g;b;a". Each triple keeps
its brightness (its largest channel) and takes the target hue; an expression triple is tinted
when r, g and b differ in one number only, else it stays as it is. Relative texture paths ("./x.png") are made absolute so the copy loads from its new
folder. --check exits 1 when a file on disk differs."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "gamecode/sdk/hoh2"
OUT = REPO / "mods/specs/players/hwp/specs/effects"

NUM = r"-?\d+(?:\.\d+)?"

# art/specs/fx strip: its top-left corner in fx.png (the hand-written effects use these numbers)
FX_SHEET = {"fx_pyrebrand_sigil": (0, 0), "fx_tempest_orb": (96, 0),
            "fx_hellfire_claw": (0, 24), "fx_battlefield_standard": (0, 72)}
FX_SIZE = (256, 128)


def fx_sheet():
    from PIL import Image
    sheet = Image.new("RGBA", FX_SIZE, (0, 0, 0, 0))
    for name, xy in FX_SHEET.items():
        sheet.paste(Image.open(REPO / "art/specs/fx" / f"{name}.png").convert("RGBA"), xy)
    return sheet


def tint(rgb, target):
    peak = max(rgb)
    if peak <= 0:
        return rgb
    tp = max(target)
    return tuple(round(peak * c / tp, 3) for c in target)


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def triple(exprs, target):
    """r, g, b expressions tinted: plain numbers, expressions that differ in one number only
    ("saturate(t)*0.8", "saturate(t)*0.4", ...) or, failing that, each one's leading number;
    None when they cannot be."""
    lead = [re.match(r"\s*(" + NUM + r")(?![\w.(])", e) for e in exprs]
    parts = [re.split(r"(?<![\w.])(" + NUM + r")(?![\w.])", e) for e in exprs]
    if len({len(p) for p in parts}) != 1 or len(parts[0]) < 2 or any(
            parts[0][i] != p[i] for p in parts for i in range(0, len(parts[0]), 2)):
        # different shapes ("1.3", "0.85-t*(1/pi)", ...): tint each one's leading number
        if not all(lead):
            return None
        rgb = tint(tuple(float(m.group(1)) for m in lead), target)
        return [e[:m.start(1)] + fmt(v) + e[m.end(1):] for e, m, v in zip(exprs, lead, rgb)]
    diff = [i for i in range(1, len(parts[0]), 2) if len({p[i] for p in parts}) > 1]
    if len(diff) > 1:
        return None
    i = diff[0] if diff else (1 if len(parts[0]) == 3 and parts[0][0] == parts[0][2] == "" else None)
    if i is None:
        return None
    rgb = tint(tuple(float(p[i]) for p in parts), target)
    out = []
    for p, v in zip(parts, rgb):
        q = list(p); q[i] = fmt(v); out.append("".join(q))
    return out


def recolour(text, target):
    # sprite attributes: color-r="0.9" color-g="0.2" color-b="0.05"
    def attr(m):
        t = triple((m.group(2), m.group(4), m.group(6)), target)
        if t is None:
            return m.group(0)
        return f'{m.group(1)}{t[0]}{m.group(3)}{t[1]}{m.group(5)}{t[2]}"'
    text = re.sub(r'(color-r=")([^"]*)("\s*color-g=")([^"]*)("\s*color-b=")([^"]*)"', attr, text)
    # lights: <color-r value="1" /> ...
    def light(m):
        t = triple((m.group(2), m.group(4), m.group(6)), target)
        if t is None:
            return m.group(0)
        return f'{m.group(1)}{t[0]}{m.group(3)}{t[1]}{m.group(5)}{t[2]}{m.group(7)}'
    text = re.sub(r'(<color-r value=")([^"]*)("\s*/>\s*<color-g value=")([^"]*)("\s*/>\s*<color-b value=")([^"]*)("\s*/>)',
                  light, text)
    # particles: color="150 0 0 50; 255 100 0 50" (0-255)
    def plist(m):
        quads = []
        for q in m.group(1).split(";"):
            v = q.split()
            if len(v) != 4 or not all(re.fullmatch(NUM, x) for x in v):
                return m.group(0)
            r, g, b = tint(tuple(float(x) for x in v[:3]), target)
            quads.append(" ".join([str(min(255, round(r))), str(min(255, round(g))), str(min(255, round(b))), v[3]]))
        return 'color="' + "; ".join(quads) + '"'
    text = re.sub(r'color="([^"]*)"', plist, text)

    def cmul(m):
        v = m.group(1).split(";")
        if len(v) != 4 or not all(re.fullmatch(NUM, x.strip()) for x in v):
            return m.group(0)
        r, g, b = tint(tuple(float(x) for x in v[:3]), target)
        return f'color-mul="{fmt(r)};{fmt(g)};{fmt(b)};{v[3].strip()}"'
    return re.sub(r'color-mul="([^"]*)"', cmul, text)


def absolute(text, src):
    folder = Path(src).parent.as_posix()
    return text.replace('texture="./', f'texture="{folder}/').replace('src="./', f'src="{folder}/')


def header(text, note):
    i = text.index("<effect")
    j = text.index(">", i) + 1
    return text[:j] + "\n<!-- " + note + " -->" + text[j:]


def standard():
    """Bannerlord's Battlefield Standard: the Holy Banner in red and gold, with a planted param."""
    src = "players/priest/effects/holy_banner.effect"
    s = absolute((SDK / src).read_text(encoding="utf-8"), src)
    s = s.replace('<param name="radius" default="40" />', '<param name="radius" default="40" />\n\t<param name="planted" default="1" />', 1)
    s = s.replace('%replace "flag_y_offset" "-30+30*prog_tl_fast_in"',
                  '%replace "flag_y_offset" "(-30+30*prog_tl_fast_in-18*(1-planted))"\n\t%replace "flag_x_offset" "(-7*(1-planted))"')
    s = s.replace('pos-y="flag_y_offset"', 'pos-x="flag_x_offset"\n\t\tpos-y="flag_y_offset"')
    s = s.replace('pos-x="0"\n\t\tpos-y="-20+flag_y_offset"', 'pos-x="flag_x_offset"\n\t\tpos-y="-20+flag_y_offset"')
    # the cloth crimson (the holy banner's is white)
    s = s.replace('\t\tcolor-r="1"\n\t\tcolor-g="1"\n\t\tcolor-b="1"\n\t\tcolor-a="prog_tl_fast_out"',
                  '\t\tcolor-r="CLOTH_R"\n\t\tcolor-g="CLOTH_G"\n\t\tcolor-b="CLOTH_B"\n\t\tcolor-a="prog_tl_fast_out"')
    s = s.replace('color-r="0.2*prog_tl_fast_out"\n\t\tcolor-g="0.2*prog_tl_fast_out"\n\t\tcolor-b="0.8*prog_tl_fast_out"',
                  'color-r="0.8*prog_tl_fast_out"\n\t\tcolor-g="0.25*prog_tl_fast_out"\n\t\tcolor-b="0.15*prog_tl_fast_out"')
    s = s.replace('<color-r value="0.1*prog_tl_fast_out" />\n\t\t<color-g value="0.1*prog_tl_fast_out" />\n\t\t<color-b value="2*prog_tl_fast_out" />',
                  '<color-r value="2*prog_tl_fast_out" />\n\t\t<color-g value="0.6*prog_tl_fast_out" />\n\t\t<color-b value="0.2*prog_tl_fast_out" />')
    # the ring faint while carried, full when planted
    s = s.replace('color-a="1*prog_tl_fast_out"', 'color-a="(0.35+0.65*planted)*prog_tl_fast_out"')
    s = s.replace('color-a="0.7*prog_tl_fast_out"', 'color-a="(0.25+0.45*planted)*prog_tl_fast_out"')
    s = recolour(s, (1.0, 0.42, 0.12))  # the cloth's markers are not numbers, so it keeps its own colour
    s = s.replace('"CLOTH_R"', '"1.25"').replace('"CLOTH_G"', '"0.45"').replace('"CLOTH_B"', '"0.4"')
    # the holy banner and its shadow give way to the standard's own art (fx.png): frames 0-1
    # carried, 2-3 planted in a mound; the effect is respawned on planting (StandardFx)
    x, y = FX_SHEET["fx_battlefield_standard"]
    flag = "<!-- FLAG -->"
    for p, frames in (("(1-planted)", (0, 1)), ("planted", (2, 3))):
        flag += (f'\n\t<sprite origin="4 39" looping="true" texture="players/hwp/specs/effects/fx.png" material="system/default.mats:default-noxray"\n'
                 f'\t\tpos-x="flag_x_offset"\n\t\tpos-y="flag_y_offset"\n\t\tcolor-a="{p}*prog_tl_fast_out"\n\t>\n'
                 + "".join(f'\t\t<frame time="220">{x + 24 * f} {y} 24 40</frame>\n' for f in frames) + "\t</sprite>\n")
    # the vanilla flag's 32 frames made the effect 4 s long; with no sprite that long the whole
    # effect stops drawing (GameLab: no standard at all in tmp runs 20261021-172055 and -172204,
    # the ring and flag back in -172522 with this), so an invisible one keeps the length
    flag += ('\n<!-- LENGTH -->\n\t<sprite origin="0 0" looping="true" texture="players/hwp/specs/effects/fx.png"'
             ' material="system/default.mats:default-noxray" color-a="0">\n\t\t<frame time="4000">0 0 1 1</frame>\n\t</sprite>\n')
    s = re.sub(r"<!-- FLAG SHADOW-->.*?(?=<!-- FLAG GLOW 1 -->)", "", s, flags=re.S)
    s = re.sub(r"<!-- FLAG -->.*?(?=<!-- LIGHT SHAFT -->)", lambda m: flag + "\n", s, flags=re.S)
    return header(s, "Bannerlord's Battlefield Standard (scripts/HWP/Specs/Bannerlord.as): " + src
                  + " in red and gold with the standard's art from fx.png (tools/make_specs_fx.py). planted 0:"
                  " carried over the bearer's shoulder, a faint ring; 1: planted in the ground.")


# out name: (vanilla source, target colour, what it is)
RECOLOURS = {
    "gale_cast.effect": ("players/warrior/effects/warcry_area.effect", (0.7, 1.0, 0.85),
                         "Winddancer's Protective Gale, the cast ring"),
    "gale_buff.effect": ("players/ranger/effects/dodge_buff.effect", (0.7, 1.0, 0.85),
                         "Winddancer's Protective Gale, on each player who has it"),
    "gust.effect": ("players/paladin/effects/lay_on_hands_radius.effect", (0.35, 1.0, 0.5),
                    "Winddancer's Second Wind, the healing gust (radius param)"),
}


def build():
    files = {"standard.effect": standard()}
    for name, (src, colour, note) in RECOLOURS.items():
        text = absolute((SDK / src).read_text(encoding="utf-8"), src)
        files[name] = header(recolour(text, colour), f"{note}: {src} recoloured (tools/make_specs_fx.py)")
    return files


def main():
    from PIL import Image, ImageChops
    files = build()
    stale = [n for n, t in files.items() if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != t]
    sheet = fx_sheet()
    if not (OUT / "fx.png").exists() or ImageChops.difference(
            Image.open(OUT / "fx.png").convert("RGBA"), sheet).getbbox():
        stale.append("fx.png")
    if "--check" in sys.argv:
        if stale:
            print("stale:", ", ".join(stale)); sys.exit(1)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in files.items():
        (OUT / n).write_text(t, encoding="utf-8", newline="\n")
    sheet.save(OUT / "fx.png")
    print("wrote", len(files), "effects and fx.png to", OUT.relative_to(REPO))


if __name__ == "__main__":
    main()
