"""Builds the class planner's icon sheet: every skill and orb icon the planner shows, cut
from the icon atlases (vanilla, Firearms, the HoH1 classes, the 4th specs), packed 24x24 into icons.png,
with icons.json mapping each in-game id to its cell.
python planner_icons.py [<data>] -> planner/web/icons.png, icons.json; <data> holds the
planner's records as classes/*.json, skills/*.json and mods/*.json (default planner/data).
A record with `hoh1_icon` ("<class>/<skill>", a key of HOH1_REMASTERED_ICONS in
tools/import_hoh1.py: the HoH1 Remastered specs) gets that cell of the Remastered sheet.
A class skill with `hoh1_rect` (the HoH1 row) gets that cell too: the Remastered sheet is
HoH1's gui/icons_skills.png copied whole, so only icons.local.png shows those (the committed
placeholder has shapes only in the Remastered cells).
An orb record on such a skill, unbuilt, shows its skill's icon (HoH1 had no orbs).
A record not built yet whose icon is picked has `icon_art` (art/specs/override/<name>.png,
keyed by the record's file name), and a skill's `hud_art` ([[label, name], ...]) adds its
status icons (keyed by name); a 14x14 status icon sits centred in its 24x24 cell.
The HoH1 classes' atlases are committed placeholders; when the local HoH1 art is imported
(mods/classes/hoh1art/), the same sheet cut from it is written as icons.local.png
(git-ignored), which the planner serves instead.
Needs gamecode/ (python -m gamelab doctor) for the vanilla atlases."""
import json, re, sys, glob
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
S = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "planner/data"
SVALS = [REPO / "gamecode/sdk/hoh2/players", REPO / "mods/firearms/players", REPO / "mods/classes/players",
         REPO / "mods/specs/players"]
# a texture path resolves in the first package that has it, as the game's do
BASES = [REPO / "mods/classes", REPO / "mods/firearms", REPO / "mods/specs", REPO / "gamecode/sdk/hoh2", REPO]
ART = "art/specs/override/"
OVERLAY = REPO / "mods/classes/hoh1art"
REMASTERED = "players/hwp/remastered/icons.png"
sys.path.insert(0, str(REPO / "tools"))
from import_hoh1 import HOH1_REMASTERED_ICONS  # noqa: E402
ID = re.compile(r'<string name="id">([^<]+)</string>')
ICON = re.compile(r'<array name="icon">\s*<(?:string|s)>([^<]+)</(?:string|s)>\s*<(?:int|i)>\d+</(?:int|i)>\s*<vec4>([^<]+)</vec4>', re.S)

icons = {}   # id -> (texture path, rect)
for root in SVALS:
    for f in root.rglob("*.sval"):
        s = f.read_text(encoding="utf-8", errors="replace")
        ev = sorted([(m.start(), "icon", m) for m in ICON.finditer(s)] + [(m.start(), "id", m) for m in ID.finditer(s)], key=lambda e: e[0])
        last = None
        for _, kind, m in ev:
            if kind == "icon":
                last = (m.group(1), tuple(int(float(x)) for x in m.group(2).split()))
            else:
                if last and m.group(1) not in icons:
                    icons[m.group(1)] = last
                last = None

# the ids the planner shows
want = set()
for f in glob.glob(str(S / "classes/*.json")):
    c = json.load(open(f, encoding="utf-8")); c = c.get("data", c)
    for sk in c.get("base", []) + [x for sp in c.get("specs", []) for x in sp.get("skills", [])]:
        want.add(sk["id"]); want.update(m["id"] for m in sk.get("mods", []))
        if sk.get("hoh1_rect"):   # the HoH1 row (tools/planner_hoh1.py): a cell of HoH1's skill sheet
            icons[sk["id"]] = (REMASTERED, (*sk["hoh1_rect"], 24, 24))
            for m in sk.get("mods", []):   # HoH1 had no orbs: a new one shows its skill's icon
                icons.setdefault(m["id"], icons[sk["id"]])
for coll in ("skills", "mods"):
    for f in glob.glob(str(S / f"{coll}/*.json")):
        d = json.load(open(f, encoding="utf-8")); d = d.get("data", d)
        if (d.get("built") or "").startswith("hwp_"):
            want.add(d["built"])
        if d.get("hoh1_icon"):
            cls, sk = d["hoh1_icon"].split("/")
            key = Path(f).stem
            want.add(key)
            icons[key] = (REMASTERED, (*HOH1_REMASTERED_ICONS[cls][sk], 24, 24))

# picked art for records not built yet
for coll in ("doctrines", "skills", "mods"):
    for f in glob.glob(str(S / f"{coll}/*.json")):
        d = json.load(open(f, encoding="utf-8")); d = d.get("data", d)
        for key, name in ([(Path(f).stem, d["icon_art"])] if d.get("icon_art") else []) + [(n, n) for _, n in d.get("hud_art", [])]:
            art = REPO / ART / f"{name}.png"
            if not art.is_file():   # a typo or a renamed file in one record must not sink the whole sheet
                print(f"warning: {Path(f).relative_to(REPO)}: no art {ART}{name}.png, skipped", file=sys.stderr)
                continue
            im = Image.open(art)
            want.add(key); icons[key] = (ART + name + ".png", (0, 0, *im.size))

# an orb record (mods/*.json) on an HoH1 skill has no art of its own (HoH1 had no orbs): it
# shows its skill's icon until it is built
for f in glob.glob(str(S / "mods/*.json")):
    d = json.load(open(f, encoding="utf-8")); d = d.get("data", d)
    key = Path(f).stem
    if key not in icons and d.get("skill") in icons and not (d.get("built") or "").startswith("hwp_"):
        want.add(key); icons[key] = icons[d["skill"]]

found = {i: icons[i] for i in want if i in icons}
missing = sorted(want - set(found))
cells, index = [], {}
for i in sorted(found):
    key = found[i]
    if key not in index:
        index[key] = len(cells); cells.append(key)
COLS = 16
rows = (len(cells) + COLS - 1) // COLS


def texture(rel, overlay):
    for base in ([OVERLAY] if overlay else []) + BASES:
        if (base / rel).exists():
            return base / rel
    raise FileNotFoundError(rel)


def sheet(overlay):
    out = Image.new("RGBA", (COLS * 24, rows * 24), (0, 0, 0, 0))
    tex = {}
    for n, (rel, (x, y, w, h)) in enumerate(cells):
        path = texture(rel, overlay)
        im = tex.setdefault(path, Image.open(path).convert("RGBA"))
        cut = im.crop((x, y, x + w, y + h))
        ox = oy = 0
        if rel.startswith(ART) and (w, h) != (24, 24):   # a status icon: centred, not stretched
            ox, oy = (24 - w) // 2, (24 - h) // 2
        elif (w, h) != (24, 24):
            cut = cut.resize((24, 24), Image.NEAREST)
        out.paste(cut, ((n % COLS) * 24 + ox, (n // COLS) * 24 + oy))
    return out


web = REPO / "planner/web"
sheet(False).save(web / "icons.png", optimize=True)
local = any((OVERLAY / rel).exists() for rel, _ in cells)
if local:
    sheet(True).save(web / "icons.local.png", optimize=True)
json.dump({"cell": 24, "cols": COLS, "icons": {i: index[(p, r)] for i, (p, r) in sorted(found.items())}},
          open(web / "icons.json", "w"), separators=(",", ":"))
print(len(want), "wanted,", len(found), "found,", len(cells), "cells", "(and icons.local.png from the HoH1 art)" if local else "")
print("missing:", missing)
