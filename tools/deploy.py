#!/usr/bin/env python3
"""deploy.py - put mods into one of the environments declared in gamelab/env/environments.json.

    deploy.py gamelab [mod ...]          # junction repo mods into the GameLab game dir, verify
    deploy.py modded-prod [package ...]  # build the Workshop packages (tools/build.py) and copy them to
                                         # <install>/mods; default: the environment's list (the all pack)
    deploy.py modded-prod --dry-run      # list what would be written, write nothing
    deploy.py modded-prod --beta         # a beta build: build.py --beta folds the `beta_into` modules
                                         # (holylocal, the Priest without the DLC) into their hosts' .bin
    deploy.py modded-prod                # packs what you imported from your own HoH1 install (the HoH1
                                         # campaign floors, pets, trinket icons, class art: build.py
                                         # --with-local) whenever any of it is there: it is your install
    deploy.py modded-prod --no-local     # a release build in your install (what the Workshop has)
    deploy.py modded-prod --with-local   # pack the local content (the default when there is some)
    deploy.py vanilla                    # refuses: vanilla declares no mods

gamelab: mods are directory junctions into mods/<id>/, so an edit in the repo *is* the
deployed copy. Nothing is copied; this only creates/repairs the junctions and verifies
them (gamelab/env.py link()). GameLab scenarios enable a mod per save, so a mod also
needs a scenario's "mods" list (or a fixture) to load.

modded-prod: the player's real install. Packages from packages.json (`all` is the
all-in-one pack, the environment's default). Each goes through build.py to
dist/HWP-<package>.bin (or HammerwatchPlus-All.bin) and is copied to <install>/mods/.
HWP-*.bin and HammerwatchPlus*.bin files there that this deploy does not write are removed:
an old per-module HWP-core.bin would load first and win every shared path. Nothing else in
that folder is touched.

Reload trigger (measured, gamelab/scenarios/reload-mark.json, run 20261017-144317):
a script edit is NOT picked up on a level load inside a running game (the next level's
module constructor still runs the old code); it is picked up after a restart. So the
trigger is a game restart. Every GameLab run boots a fresh process, so for GameLab the
next `python -m gamelab run ...` is the reload. For modded-prod the player restarts the game.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402
import gamepaths  # noqa: E402
import saves  # noqa: E402
from gamelab import env  # noqa: E402

RELOAD = "reload trigger: restart the game (a level load does not recompile scripts; reload-mark scenario)"


def deploy_gamelab(mods: list[str]) -> int:
    problems = env.link(fix=True, mods=mods)
    for p in problems:
        print("PROBLEM", p)
    linked = sorted(p.name for p in (env.GAME / "mods").iterdir())
    print(f"gamelab: {'green' if not problems else 'NOT green'}; linked {linked}")
    print(RELOAD + "; the next `python -m gamelab run` boots fresh")
    return 1 if problems else 0


def package_ids() -> set[str]:
    doc = json.loads((gamepaths.REPO / "packages.json").read_text(encoding="utf-8"))
    return {p["id"] for p in doc["packages"]} | {"all"}


def stale_packages(target: Path, keep: set[str]) -> list[Path]:
    """HWP .bin files in the install's mods/ this deploy does not write (old module or package builds)."""
    if not target.is_dir():
        return []
    return sorted(p for p in target.iterdir() if env.is_package_copy(p) and p.name not in keep)


def personal_default() -> bool:
    """modded-prod is the player's own install, so the content made from their own HoH1 install goes
    in whenever there is some. Without it a deploy silently drops the HoH1 floors, pets and trinket
    icons the player imported (2026-10-29: a deploy without --with-local left every HoH1 trinket on
    a vanilla trinket's icon; only tools/run.py passed it, and only for the campaign import)."""
    found = build.personal_content([build.load_module(d) for d in gamepaths.module_dirs()])
    mods = sorted({f.split("/", 1)[0] for f in found})
    if found:
        print(f"modded-prod: packing {len(found)} file(s) made from your own HoH1 install ({', '.join(mods)}); "
              "--no-local leaves them out")
    else:
        print("modded-prod: nothing imported from HoH1 (tools/import_hoh1.py): a release build")
    return bool(found)


def deploy_prod(packages: list[str], dry_run: bool, beta: bool = False, with_local: bool | None = None,
                avoid_workshop: bool = False) -> int:
    """with_local None: personal_default()."""
    decl = env.environments()["modded-prod"]
    forbidden = decl.get("forbidden_mods", [])
    wanted = packages or decl["packages"]
    bad = [p for p in wanted if p not in package_ids() or any(fnmatch.fnmatch(p, f) for f in forbidden)]
    if bad:
        print(f"REFUSED: not a package in packages.json (or forbidden): {bad}; known: {sorted(package_ids())}")
        return 2
    if with_local is None:
        with_local = personal_default()
    target = Path(env.install()) / "mods"
    plan = [(env.package_file(p), target / (env.personal_package_name(p) if avoid_workshop
                                          else env.package_file(p).name)) for p in wanted]
    stale = stale_packages(target, {dst.name for _, dst in plan})
    if dry_run:
        for src, dst in plan:
            flags = (" (--beta)" if beta else "") + (" (--with-local)" if with_local else "")
            print(f"would build {src.relative_to(gamepaths.REPO)}{flags} and copy it to {dst}")
        for p in stale:
            print(f"would remove {p} (not in this deploy)")
        print(RELOAD)
        return 0
    unconfirmed = saves.confirmation_problems()
    if unconfirmed:
        print("REFUSED: modded-prod runs on the player's real saves; " + "; ".join(unconfirmed))
        return 2
    flags = (["--no-all"] if "all" not in wanted else []) + (["--beta"] if beta else [])         + (["--with-local"] if with_local else [])
    r = subprocess.run([sys.executable, str(gamepaths.TOOLS / "build.py"), *flags, *wanted])
    if r.returncode:
        return r.returncode
    target.mkdir(exist_ok=True)
    for p in stale:
        try:
            p.unlink()
        except PermissionError:
            print(f"REFUSED: cannot remove {p}: the game is holding it open. Close Heroes of Hammerwatch II "
                  "and deploy again")
            return 3
        print(f"removed {p}")
    for src, dst in plan:
        try:
            shutil.copy2(src, dst)
        except PermissionError:
            print(f"REFUSED: cannot replace {dst}: the game is holding it open. Close Heroes of Hammerwatch II "
                  "and deploy again")
            return 3
        print(f"deployed {dst}")
    print(RELOAD)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("env", choices=["gamelab", "modded-prod", "vanilla"])
    ap.add_argument("names", nargs="*", metavar="mod|package",
                    help="gamelab: repo mods to link; modded-prod: packages.json ids or `all`")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--beta", action="store_true", help="modded-prod: build with build.py --beta (never publish those .bin files)")
    ap.add_argument("--avoid-workshop", action="store_true",
                    help="modded-prod: use a separate -local id if a Workshop copy has the package id")
    local = ap.add_mutually_exclusive_group()
    local.add_argument("--with-local", dest="with_local", action="store_true", default=None,
                       help="modded-prod: build with build.py --with-local, packing the content made from your "
                            "own HoH1 install (never publish those .bin files); the default when there is some")
    local.add_argument("--no-local", dest="with_local", action="store_false",
                       help="modded-prod: a release build, without the content made from your own HoH1 install")
    a = ap.parse_args(argv)
    if a.env == "vanilla":
        print("REFUSED: the vanilla environment declares no mods")
        return 2
    if a.env == "gamelab":
        return deploy_gamelab(a.names)
    return deploy_prod(a.names, a.dry_run, a.beta, a.with_local, a.avoid_workshop)


if __name__ == "__main__":
    sys.exit(main())
