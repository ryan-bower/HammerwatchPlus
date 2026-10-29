"""The Steam Workshop upload kit: one folder per package, ready for the game's own uploader.

    python tools/workshop.py              build every package (tools/build.py), then the kit
    python tools/workshop.py --no-build   the kit from the .bin files already in dist/
    python tools/workshop.py --check      the texts only (packages.json, README, workshop.json)

For each package in packages.json, and the all-in-one pack, it writes
dist/workshop/<file>/:

    <file>.bin         the package (dist/<file>.bin)
    preview.png        the Workshop image (under 1 MB, the uploader's limit): the package's
                       card from tools/workshop_art.py, drawn from the game's own art
    gallery/NN-<id>.png  the All pack only: every published package's card, the item's
                       additional pictures
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
ALL_FILE = "HammerwatchPlus-All"
# one short line per module for its Workshop page: what a player gets, nothing else
TERSE = {
    "bufftips": "hover a buff to see what it does and how long it has left.",
    "chatlinks": "linked items stay in chat with their slot and item level.",
    "stash": "a Sort button on the town stash.",
    "deathrecap": "what killed you, and everyone's damage after each boss.",
    "laststats": "the party's last-run stats on a board by the town fountain.",
    "colors": "colour-blind projectile tints; each player in their own colour on the map.",
    "waygates": "teleport gates in the town square and at every building.",
    "weaponswap": "a second weapon set on a hotkey (X).",
    "summons": "summons follow you to the next floor with their HP.",
    "petrooms": "pets wait outside puzzle and trap rooms, and walk back out of one they wander into.",
    "legacy": "your best hero of each class buffs every character.",
    "goldworth": "gold on the floor looks like what it is worth.",
    "mmhmm": "some rare and epic hats say \"mm-hmm\" on crits, revives and more.",
    "orbwarn": "the orb picker shows which orbs a pick locks out.",
    "attrclick": "Shift+Click places 20 attribute points at the Attribute Trainer, Ctrl+Click 5.",
    "mapicons": "dye pots marked on the minimap.",
    "groupcombo": "a party combo bonus, and rare combo orbs from boxes and vases.",
    "architect": "every player can pick and pay for Architect alterations; three saved presets.",
    "droptrade": "drop gear for friends (Q in the inventory).",
    "autoaim": ["the reticle of an aimed skill snaps to an enemy in your aim cone",
                "aimed skills can fire by themselves, ready area skills cast themselves",
                "on for controllers by default, an option for mouse players"],
    "firearms": ["rifles, pistols and hand cannons that fire from a clip and reload",
                 "base kit: Reload, Frag Grenade, Elemental Bullets",
                 "Marksman: Sniper Shot, Critical Aim",
                 "Demolitionist: Rocket Launcher, Ordinance Hoarder",
                 "Assault: Double Barrel Burst, Adrenaline",
                 "Engineer: Deploy Turret, My Turret!",
                 "every skill has its orbs"],
    "specs": ["Deadeye (Ranger): Lightning Arrow, Gathering Winds",
              "Aerotheurge (Wizard): Thunder Orb, Static Charge",
              "Arcane (Sorcerer): Blink, Living Mana",
              "Winddancer (Rogue): Protective Gale, Second Wind",
              "Bannerlord (Warrior): Battlefield Standard, Righteous Crusade",
              "Branding (Warlock): Pyrebrand, Essence Extraction",
              "Devil Forgemaster (Priest): Necrotic Resurrection, Call of Heresy",
              "Generosity (Paladin): Pelor's Fury, Pelor's Blessing",
              "every skill has its orbs"],
    "classes": "the Skill 4-6 keys; the Thief, Gladiator and Witch Hunter are coming back later.",
    "keys": ["every chest needs a key of its tier: bronze, silver, gold",
             "keys drop in runs",
             "ace chests, opened with the red ace key, and seven new legendaries",
             "the exit guard sells keys, bag slots and trinkets for your next run"],
    "campaign": ["a portal in town to an 18-floor campaign, the Mines to the Battlements",
                 "6 bosses, with their own NG+ versions",
                 "HoH1 traps, teleporter pads and confusion glyphs on generated floors"],
    "mercenary": "enlist a fresh character once its class has a level-20 hero (console: hwp merc enlist); "
                 "climb from Private to General for more gold and XP; death is permanent.",
    "wavemode": "a survival arena from a statue in town; each boss kill raises your rank.",
    "puzzles": "puzzle rooms on most floors, and HoH1's Constellation puzzle.",
    "objectives": "lever-locked loot vaults, and exits sealed until you find the lever.",
    "strongbox": "open one, beat the pack that spawns, take the loot.",
    "abyss": "cracks that spawn waves of enemies; the reward grows the deeper you are.",
    "maps": "three new map layouts: Goblin Warrens, Sunken Dungeon, The High Court.",
    "weapons": "twelve new item level 35 weapons.",
    "trinkets": "trinket bonuses grow with NG+; 37 HoH1 trinkets and eight new trinket sets.",
    "valuables": "vases, gems and other valuables are worth twice the gold.",
    "affixes": "Rare and Epic items can roll a second suffix, and Epic items a second prefix.",
    "fishing": "fishing spots in town and on run floors, a bait and rod shop; sell or eat the fish.",
    "farming": "farm plots in town: crops and Holy Herbs grow with every run; smoke a herb for a buff.",
    "gambler": "Higher or Lower for gold, and rerolls of your equipped gear.",
    "roulette": "a roulette table in the tavern for the whole lobby.",
    "tavern": "three more tavern levels: up to 3 foods and 5 drinks per run.",
    "pets": ["pets level up and learn skills, trained at the Pet Shop",
             "pet dyes at the tailor",
             "pickup toggles per pet",
             "pets wait outside trap and puzzle rooms"],
}
# what a package needs beyond the game: DLC name, what in the package needs it, and that in a
# few words for the card
DLC = {"specs": ("Celestial Ruins", "the Priest's 4th specialization (the Devil Forgemaster)", "Priest's 4th spec")}
# stand-ins a page doesn't mention: the module's line never claims the HoH1 content
QUIET_STANDINS = {"pets", "classes"}
# the All pack's line for a one-module package
ONE_LINE = {
    "autoaim": "aim assist for reticle skills, for controllers and mouse.",
    "firearms": "a new class with guns, grenades and four specializations.",
    "specs": "a 4th specialization for eight classes.",
    "keys": "locked chests, keys, ace chests and new legendaries.",
    "campaign": "an 18-floor campaign from a portal in town.",
    "pets": "pet levels, skills, dyes and pickup toggles.",
}


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


# words about this repo, not the game (its paths, its tools, the HoH1 import): never on a page
DEV_TEXT = re.compile(r"tools/|mods/|docs/|art/|\.py\b|gitignored|doctor|the user's picks|HoH1 installed|\bcore's\b")


WORKSHOP_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="


def item_url(file: str, led: dict) -> str:
    e = led.get("items", {}).get(file, {})
    return WORKSHOP_URL + e["item_id"] if e.get("item_id") and not e.get("hold") else ""


def short(p: dict) -> str:
    return p["name"].split(": ", 1)[-1]


def requires(mods: list[str], pids: list[str], stand: dict[str, str]) -> list[str]:
    """The page's first lines: multiplayer, and everything the package needs beyond the game."""
    need = "Heroes of Hammerwatch II"
    dlc = [DLC[p] for p in pids if p in DLC]
    if dlc:
        need += "; " + "; ".join(f"the [b]{d} DLC[/b] only if you want to use {what}" for d, what, _ in dlc)
    hoh1 = "[b]Heroes of Hammerwatch 1:[/b] not needed."
    notes = [stand[m] for m in mods if m in stand and m not in QUIET_STANDINS]
    if notes:
        hoh1 += " In this Workshop version " + "; ".join(notes) + "."
    return ["[b]Multiplayer supported.[/b]", f"[b]Requires:[/b] {need}.", hoh1]


def module_item(mod: str) -> list[str]:
    t = TERSE[mod]
    if isinstance(t, str):
        return [f"[*][b]{module_title(mod)}[/b]: {t}"]
    return [f"[*][b]{module_title(mod)}[/b]", "[list]"] + [f"[*]{s[0].upper() + s[1:]}" for s in t] + ["[/list]"]


def need_line(pids: list[str]) -> str:
    """The install step that says what to own: the game, and each DLC with what needs it."""
    dlc = "".join(f" If you want to use {what}, you also need the {d} DLC." for d, what, _ in
                  (DLC[p] for p in pids if p in DLC))
    return f"[*]You need Heroes of Hammerwatch II.{dlc} Heroes of Hammerwatch 1 is not needed."


def install(name: str, pids: list[str]) -> list[str]:
    return ["[h2]Install[/h2]", "[olist]",
            "[*]Subscribe.",
            f"[*]In the game's main menu, open [b]Resource Mods[/b], tick [b]{name}[/b] and restart the game.",
            need_line(pids),
            "[*]Everyone in a lobby needs the same packages.",
            "[/olist]",
            "[b]Settings:[/b] open the player menu (inventory), [b]Plus[/b] tab. Every module has an "
            "on/off switch there; in a lobby the host's settings count."]


def describe(pkg: dict, led: dict, inside: list[dict] | None = None,
             stand: dict[str, str] | None = None) -> str:
    stand = stand or {}
    if inside is None:
        out = requires(pkg["mods"], [pkg.get("pid", pkg["id"])], stand) + ["", "[h2]What's in it[/h2]", "[list]"]
        for mod in pkg["mods"]:
            out += module_item(mod)
        out += ["[/list]", ""] + install(pkg["name"], [pkg.get("pid", pkg["id"])])
        allp = item_url(ALL_FILE, led)
        if allp:
            out += ["", f"Want everything? [url={allp}]HammerwatchPlus: All[/url] has every "
                        "HammerwatchPlus package in one subscription."]
        return "\n".join(out) + "\n"
    shown = listed(inside, led)
    mods = [m for p in shown for m in p["mods"]]
    out = requires(mods, [p["id"] for p in shown], stand) + [
        "", f"Every HammerwatchPlus package in one subscription: {len(shown)} packages, {len(mods)} "
            "modules. The pictures show each package.", "", "[h2]What's in it[/h2]", "[list]"]
    for p in shown:
        url = item_url(f"HWP-{p['id']}", led)
        name = f"[url={url}]{short(p)}[/url]" if url else short(p)
        titles = [module_title(m) for m in p["mods"]] if len(p["mods"]) > 1 else []
        what = ", ".join(titles) if titles else ONE_LINE[p["id"]]
        out.append(f"[*][b]{name}[/b]: {what}")
    out += ["[/list]", "Each package's own page lists what every module does.", ""]
    out += ["[h2]Install[/h2]", "[olist]", "[*]Subscribe.",
            f"[*]In the game's main menu, open [b]Resource Mods[/b], tick [b]{pkg['name']}[/b] and restart the game.",
            need_line([p["id"] for p in shown]),
            "[*]Everyone in a lobby needs it too.",
            "[/olist]",
            "No need to enable the single packages as well. Any you already have can stay on beside this one.",
            "", "[h2]Settings[/h2]",
            "Open the player menu (inventory) and go to the [b]Plus[/b] tab: one row per package, every module "
            "and its settings, with a search field. In a lobby the host's settings count.",
            "", "[h2]Turning modules off[/h2]",
            "Don't want a module? Switch it off in the Plus tab; the rest keep working. Turn it back on any time."]
    return "\n".join(out) + "\n"


def card(im, path: Path) -> None:
    import workshop_art
    workshop_art.save(im, path)
    if path.stat().st_size >= PREVIEW_MAX:
        raise SystemExit(f"{path}: the image is {path.stat().st_size} bytes, Steam takes under 1 MB")


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


def on_workshop(packages: list[dict]) -> list[dict]:
    """The packages the Workshop has: not packages.json `"workshop": false` ones (the All pack's
    Workshop build leaves those out too: tools/build.py --workshop)."""
    return [p for p in packages if p.get("workshop", True)]


def items(packages: list[dict], allp: dict) -> list[tuple[str, dict, list[dict] | None]]:
    packages = on_workshop(packages)
    out = [(f"HWP-{p['id']}", dict(p, pid=p["id"]), None) for p in packages]
    out.append((allp["file"], dict(allp, pid="all", mods=[m for p in packages for m in p["mods"]]), packages))
    return out


def listed(inside: list[dict], led: dict) -> list[dict]:
    """The packages the All pack's page and cover name: not the held ones (their item isn't out)."""
    return [p for p in inside if not led["items"].get(f"HWP-{p['id']}", {}).get("hold")]


def check(packages, allp, led) -> list[str]:
    errors = []
    lines = module_lines()
    for file, p, inside in items(packages, allp):
        if inside is None:
            for mod in p["mods"]:
                if mod not in lines:
                    errors.append(f"{file}: README.md has no module line for {mod}")
            for mod in p["mods"]:
                if mod not in TERSE:
                    errors.append(f"{file}: no Workshop line (TERSE) for {mod}")
        elif any(q["id"] not in ONE_LINE for q in listed(inside, led) if len(q["mods"]) == 1):
            errors.append(f"{file}: a one-module package has no ONE_LINE")
        if file not in led.get("items", {}):
            errors.append(f"workshop.json: no entry for {file}")
            continue
        if not errors:
            m = DEV_TEXT.search(describe(p, led, inside, standins()))
            if m:
                errors.append(f"{file}: the description names {m.group(0)!r}, a repo path or dev step")
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
        if build.main(["--workshop"]) not in (0, None):
            return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    stand = standins()
    try:
        sys.path.insert(0, str(REPO / "tools"))
        import workshop_art
        art = workshop_art.cards(on_workshop(packages), workshop_art.held_ids())
    except FileNotFoundError as e:
        print(f"workshop: the cards are drawn from the game's art, and {e.filename} is missing "
              "(python -m gamelab doctor --fix makes gamecode/)", file=sys.stderr)
        return 1
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
        (d / "description.txt").write_text(describe(p, led, inside, stand), encoding="utf-8", newline="\n")
        (d / "changenote.txt").write_text(stamp + "\n", encoding="utf-8", newline="\n")
        card(art[p["pid"]], d / "preview.png")
        if inside:          # the All pack's gallery: every published package's own card
            for n, q in enumerate(listed(inside, led), 1):
                card(art[q["id"]], d / "gallery" / f"{n:02d}-{q['id']}.png")
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
