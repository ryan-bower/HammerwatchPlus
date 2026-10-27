"""The Steam Workshop upload kit: one folder per package, ready for the game's own uploader.

    python tools/workshop.py              build every package (tools/build.py), then the kit
    python tools/workshop.py --no-build   the kit from the .bin files already in dist/
    python tools/workshop.py --check      the texts only (packages.json, README, workshop.json)

For each package in packages.json, and the all-in-one pack, it writes
dist/workshop/<file>/:

    <file>.bin         the package (dist/<file>.bin)
    preview.png        the Workshop image (under 1 MB, the uploader's limit)
    title.txt          the item's title
    description.txt    the item's description, in Steam's BBCode
    changenote.txt     version, commit and date, for an update's change note

and dist/workshop/UPLOAD.txt, the list of what to upload new and what to update, from
workshop.json (repo root), the ledger of published item ids. tools/workshop_publish.py
uploads the kit as the Steam user logged in to the running client; PACKAGER.exe > Steam
Workshop manager does the same by hand (docs/WORKSHOP.md)."""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
OUT = DIST / "workshop"
LEDGER = REPO / "workshop.json"
PREVIEW_MAX = 1024 * 1024
FONTS = Path("C:/Windows/Fonts")

# one accent per package for the preview cards
ACCENT = {
    "qol": (86, 160, 211), "coop": (120, 190, 120), "autoaim": (229, 115, 80),
    "firearms": (214, 162, 72), "specs": (171, 120, 214), "classes": (150, 150, 165),
    "keys": (232, 196, 80), "campaign": (120, 140, 220), "modes": (215, 80, 90),
    "dungeon": (190, 120, 70), "town": (110, 190, 170), "pets": (230, 140, 180),
    "all": (237, 147, 49),
}
SETTINGS_NOTE = ("Every module can be turned off, and its settings changed, in game: open the "
                 "inventory and go to the [b]Plus[/b] tab. Settings that change the game for "
                 "everyone follow the host in a lobby.")
COOP_NOTE = ("Co-op: everyone in a lobby should run the same version of the same packages. "
             "Each package works alone and beside any other HammerwatchPlus package.")


def load_packages() -> tuple[list[dict], dict]:
    pk = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    return pk["packages"], pk["all"]


def module_lines() -> dict[str, str]:
    """README.md's module tables: `id` -> the one-line description."""
    out = {}
    for ln in (REPO / "README.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([\w-]+)`\s*\|\s*(.+?)\s*\|\s*$", ln)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def module_title(mod: str) -> str:
    cfg = json.loads((REPO / "mods" / mod / "module.json").read_text(encoding="utf-8")).get("config") or {}
    if cfg.get("title"):
        return cfg["title"]
    info = (REPO / "mods" / mod / "info.xml").read_text(encoding="utf-8")
    m = re.search(r'<string name="name" value="([^"]+)"', info)
    name = m.group(1) if m else mod
    return re.sub(r"^HammerwatchPlus\s*:?\s*", "", name) or mod


def standins() -> dict[str, str]:
    """mod -> what a player without Heroes of Hammerwatch 1's own files gets instead: the
    HWP::HoH1::Report call's lang string, the same text the game tells the player. A Workshop
    package never carries HoH1 content (docs/modules.md, Packages)."""
    out = {}
    for f in (REPO / "mods").glob("*/scripts/**/*.as"):
        for m in re.finditer(r'HoH1::Report\("([\w-]+)",[^;]*,\s*"\.([\w.]+)"\s*\);', f.read_text(encoding="utf-8")):
            mod, key = m.groups()
            for lang in (REPO / "mods" / mod / "res").rglob("*.lang"):
                t = re.search(r'<string name="' + re.escape(key) + r'">([^<]+)<', lang.read_text(encoding="utf-8"))
                if t:
                    out[mod] = t.group(1)
    return out


# a README row's sentences about this repo, not the game: its paths, its tools, the HoH1 import
DEV_TEXT = re.compile(r"tools/|mods/|docs/|art/|\.py\b|gitignored|doctor|the user's picks|HoH1 installed|\bcore's\b")


def public(md: str, title: str) -> str:
    """A README row as a player reads it: without the sentences (or ;-parts) that name repo
    paths or developer steps, and without a leading **title**: the list item already shows."""
    parts = re.split(r"(?<=[.;])\s+", md)
    s = " ".join(p for p in parts if not DEV_TEXT.search(p))
    s = re.sub(r"^\*\*" + re.escape(title) + r"\*\*:\s*", "", s).strip()
    return s[:1].upper() + s[1:]


def bbcode(md: str) -> str:
    """The README's markdown, as Steam shows it."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    s = re.sub(r"\*\*([^*]+)\*\*", r"[b]\1[/b]", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.replace("\\|", "|")


def describe(pkg: dict, lines: dict[str, str], inside: list[dict] | None = None,
             stand: dict[str, str] | None = None) -> str:
    out = [pkg["description"], ""]
    if inside is None:
        out.append("[h2]What's in it[/h2]")
        out.append("[list]")
        for mod in pkg["mods"]:
            text = bbcode(public(lines.get(mod, ""), module_title(mod)))
            out.append(f"[*][b]{module_title(mod)}[/b]" + (f": {text}" if text else ""))
        out.append("[/list]")
    else:
        out.append("[h2]The packages inside[/h2]")
        out.append("[list]")
        for p in inside:
            name = p["name"].split(": ", 1)[-1]
            out.append(f"[*][b]{name}[/b]: {p['description']}")
        out.append("[/list]")
        out.append("Already subscribed to some of the single packages? They can stay enabled "
                   "beside this one; it carries the same files.")
    notes = [stand[m] for m in pkg["mods"] if stand and m in stand]
    if notes:
        out += ["", "[h2]Heroes of Hammerwatch 1 content[/h2]",
                "The Workshop version can't carry Heroes of Hammerwatch 1's own art and levels, so:",
                "[list]"] + [f"[*]{n[0].upper() + n[1:]}." for n in notes] + [
                "[/list]", "Everything else works without it."]
    out += ["", "[h2]Settings[/h2]", SETTINGS_NOTE, "", "[h2]Multiplayer[/h2]", COOP_NOTE]
    return "\n".join(out) + "\n"


def font(size: int, bold: bool = False):
    from PIL import ImageFont
    for name in (["georgiab.ttf", "cambriab.ttf"] if bold else ["segoeui.ttf", "georgia.ttf"]):
        p = FONTS / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def wrap(draw, text: str, f, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def preview(path: Path, pid: str, title: str, items: list[str]) -> None:
    """A 640x360 title card: the package's name and what is in it."""
    from PIL import Image, ImageDraw
    W, H = 640, 360
    acc = ACCENT.get(pid, (237, 147, 49))
    img = Image.new("RGB", (W, H), (22, 20, 26))
    d = ImageDraw.Draw(img)
    for y in range(H):   # a dark vertical wash toward the accent
        t = y / H
        c = tuple(int(22 + (a * 0.22 - 22) * (1 - t) * 0.6) for a in acc)
        d.line([(0, y), (W, y)], fill=c)
    d.rectangle([0, 0, 10, H], fill=acc)
    d.rectangle([28, 30, W - 28, 31], fill=acc)
    d.text((28, 40), "HAMMERWATCHPLUS", font=font(20, True), fill=acc)
    tf = font(44, True)
    y = 70
    for ln in wrap(d, title, tf, W - 56)[:2]:
        d.text((28, y), ln, font=tf, fill=(244, 238, 228))
        y += 52
    y += 10
    f = font(19)
    shown = items[:7]
    for it in shown:
        d.text((34, y), "\u2022 " + it, font=f, fill=(214, 208, 200))
        y += 26
    if len(items) > len(shown):
        d.text((34, y), f"and {len(items) - len(shown)} more", font=f, fill=(170, 165, 160))
    d.text((W - 28, H - 32), "Heroes of Hammerwatch II mod", font=font(16), fill=(150, 145, 140), anchor="ra")
    img.save(path, optimize=True)
    if path.stat().st_size >= PREVIEW_MAX:
        raise SystemExit(f"{path}: preview is {path.stat().st_size} bytes, the uploader takes under 1 MB")


def version() -> str:
    m = re.search(r'const string VERSION = "([^"]+)"',
                  (REPO / "mods/hwplib/scripts/HWP/Core/Log.as").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def ledger(packages: list[dict]) -> dict:
    """workshop.json: file -> {"item_id": <Workshop id or null>, "hold": <reason or absent>}."""
    data = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    return data


def items(packages: list[dict], allp: dict) -> list[tuple[str, dict, list[dict] | None]]:
    out = [(f"HWP-{p['id']}", dict(p, pid=p["id"]), None) for p in packages]
    out.append((allp["file"], dict(allp, pid="all", mods=[m for p in packages for m in p["mods"]]), packages))
    return out


def check(packages, allp, led) -> list[str]:
    errors = []
    lines = module_lines()
    for file, p, inside in items(packages, allp):
        if inside is None:
            for mod in p["mods"]:
                if mod not in lines:
                    errors.append(f"{file}: README.md has no module line for {mod}")
        if file not in led.get("items", {}):
            errors.append(f"workshop.json: no entry for {file}")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-build", action="store_true", help="use the .bin files already in dist/")
    ap.add_argument("--check", action="store_true", help="check the texts and the ledger, write nothing")
    args = ap.parse_args(argv)
    packages, allp = load_packages()
    led = ledger(packages)
    errors = check(packages, allp, led)
    if errors or args.check:
        for e in errors:
            print("workshop:", e, file=sys.stderr)
        if not errors:
            print("workshop: texts and ledger OK")
        return 1 if errors else 0
    if not args.no_build:
        sys.path.insert(0, str(REPO / "tools"))
        import build
        if build.main([]) not in (0, None):
            return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    lines = module_lines()
    stand = standins()
    stamp = f"HammerwatchPlus {version()} ({commit()}, {datetime.date.today().isoformat()})"
    plan = []
    for file, p, inside in items(packages, allp):
        src = DIST / f"{file}.bin"
        if not src.exists():
            print(f"workshop: {src} is missing (run tools/build.py)", file=sys.stderr)
            return 1
        d = OUT / file
        d.mkdir()
        shutil.copy2(src, d / src.name)
        title = p["name"]
        (d / "title.txt").write_text(title + "\n", encoding="utf-8", newline="\n")
        (d / "description.txt").write_text(describe(p, lines, inside, stand), encoding="utf-8", newline="\n")
        (d / "changenote.txt").write_text(stamp + "\n", encoding="utf-8", newline="\n")
        shown = ([q["name"].split(": ", 1)[-1] for q in inside] if inside
                 else [module_title(m) for m in p["mods"]])
        preview(d / "preview.png", p["pid"], title.split(": ", 1)[-1], shown)
        entry = led["items"][file]
        if entry.get("hold"):
            plan.append(f"HOLD     {file}: {entry['hold']}")
        elif entry.get("item_id"):
            plan.append(f"UPDATE   {file}: item {entry['item_id']} "
                        f"(https://steamcommunity.com/sharedfiles/filedetails/?id={entry['item_id']})")
        else:
            plan.append(f"NEW      {file}: Upload new, then put its item id in workshop.json")
    (OUT / "UPLOAD.txt").write_text(
        f"{stamp}\nPublish with tools/workshop_publish.py, or by hand in PACKAGER.exe (docs/WORKSHOP.md).\n"
        "Publish every package of one build together: they share the library.\n\n"
        + "\n".join(plan) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(plan))
    print(f"workshop: {len(plan)} item folder(s) in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
