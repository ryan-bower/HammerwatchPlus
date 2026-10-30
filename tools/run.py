#!/usr/bin/env python3
"""run.py - one command from a clone to playing: set up, build, deploy to your Steam install, launch.

    run.py                        # setup (doctor --fix, no lab boot), build the all-in-one pack, deploy, launch
    run.py --no-launch            # everything but starting the game
    run.py --no-setup             # skip the doctor step (you just ran it)
    run.py --dry-run              # say what would happen; write nothing, launch nothing
    run.py --packages town keys   # these Workshop packages instead (packages.json)

The steps, in order (each prints a `run:` line; the exit code is the first failing step's):

1. setup     `python -m gamelab doctor --fix --no-smoke`: uv sync, the save backup, the
             game dumps (gamecode/), generated units, and the HoH1 imports when a Heroes of
             Hammerwatch (1) install is found. When doctor cannot find HoH1 and nobody has
             answered yet, the run goes on without HoH1 content and says how to answer
             (`python -m gamelab doctor --hoh1 "<dir>"` or `--no-hoh1`).
2. build     tools/build.py for the modded-prod packages (gamelab/env/environments.json:
             `all`, the all-in-one pack),
             with everything you imported from HoH1 (the HoH1 floors, pets, trinket icons, class
             art: deploy.py packs it whenever it is there), so your own .bin files carry it
             (never publish those: `build.py` without --with-local makes the shareable ones).
3. deploy    tools/deploy.py modded-prod: copies dist/HammerwatchPlus-All.bin (or
             HWP-<package>.bin) into <install>/mods/ and removes the HWP .bin files it did
             not write. Refuses while the game is running (Windows keeps the .bin files open).
             Warns (`run: workshop:`) when the Steam account is subscribed to a Workshop
             item with a deployed package's id: the game would load both and keep the
             Workshop's files.
4. launch    the game through Steam (steam://rungameid/619820), so the overlay, cloud
             saves and achievements work as usual. The user asked for this (2026-10-23);
             GameLab's hidden-desktop rules are for test runs, not for playing.

Enabling the mods is a one-time step in the game: Resource Mods > tick the deployed entry
(HammerwatchPlus-All), then restart. The game remembers the set per save by the mod's id
(the file name), so a redeploy of the same ids stays enabled; only a NEW package needs
ticking once (this tool lists them).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gamepaths  # noqa: E402
from gamelab import env  # noqa: E402

HOH2_STEAM_URL = f"steam://rungameid/{gamepaths.HOH2_APPID}"
ENVIRONMENTS = gamepaths.GAMELAB / "env" / "environments.json"
LAUNCH_WAIT_S = 45


def python() -> str:
    venv = gamepaths.REPO / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.is_file() else sys.executable


def say(step: str, text: str) -> None:
    print(f"run: {step}: {text}", flush=True)


def release_packages() -> list[str]:
    decl = json.loads(ENVIRONMENTS.read_text(encoding="utf-8"))["modded-prod"]
    return list(decl["packages"])


def mod_id(package: str) -> str:
    """The id the game's Resource Mods menu shows for a package: its .bin file stem."""
    return env.package_file(package).stem


def game_running() -> bool:
    if sys.platform != "win32":
        return False
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq HWR2.exe", "/NH"], capture_output=True, text=True)
    return "HWR2.exe" in out.stdout


def deployed_ids(install: Path) -> set[str]:
    mods = install / "mods"
    if not mods.is_dir():
        return set()
    return {p.stem for p in [*mods.glob("HWP-*.bin"), *mods.glob("HammerwatchPlus*.bin")]}


def setup(dry_run: bool) -> tuple[int, bool]:
    """doctor --fix --no-smoke. Returns (exit, hoh1_pending): a pending HoH1 question is not a failure
    here; the build just goes on without HoH1 content."""
    cmd = [python(), "-m", "gamelab", "doctor", "--fix", "--no-smoke"]
    if dry_run:
        say("setup", "would run " + " ".join(cmd[1:]))
        return 0, False
    say("setup", " ".join(cmd[1:]))
    c = subprocess.run(cmd, cwd=gamepaths.REPO, capture_output=True, text=True)
    out = c.stdout + c.stderr
    print(out.rstrip())
    pending = "ASK THE USER" in out
    bad = [ln for ln in out.splitlines() if ln.startswith("doctor: NOT ready")]
    if c.returncode and bad:
        rows = bad[0].split("NOT ready:", 1)[1].strip()
        # the HoH1 question is the only row a play session can live without
        others = [r.strip() for r in rows.split(",") if "HoH1" not in r]
        if others:
            say("setup", f"NOT ready: {', '.join(others)}. Fix the rows above, then run again")
            return 2, pending
        say("setup", "HoH1 not answered: building without HoH1 content. To add it later: "
                     "`python -m gamelab doctor --hoh1 \"<HoH1 folder>\" --fix` (or `--no-hoh1`), then run again")
        return 0, True
    if c.returncode:
        say("setup", f"doctor exit {c.returncode}; see above")
        return c.returncode, pending
    say("setup", "green")
    return 0, pending


def build_and_deploy(packages: list[str], dry_run: bool) -> int:
    # deploy.py packs your HoH1 imports whenever there are some, and says so
    say("build", ", ".join(mod_id(p) for p in packages))
    cmd = [python(), str(gamepaths.TOOLS / "deploy.py"), "modded-prod"] + packages
    if dry_run:
        cmd.append("--dry-run")
    c = subprocess.run(cmd, cwd=gamepaths.REPO)
    if c.returncode:
        say("deploy", f"failed (exit {c.returncode}); see above")
        return c.returncode
    say("deploy", "done" if not dry_run else "dry run")
    return 0


def launch(dry_run: bool) -> int:
    if dry_run:
        say("launch", f"would open {HOH2_STEAM_URL}")
        return 0
    if sys.platform != "win32":
        say("launch", "only on Windows")
        return 2
    say("launch", HOH2_STEAM_URL)
    os.startfile(HOH2_STEAM_URL)  # type: ignore[attr-defined]
    t0 = time.time()
    while time.time() - t0 < LAUNCH_WAIT_S:
        if game_running():
            say("launch", f"HWR2.exe is up after {time.time() - t0:.0f} s")
            return 0
        time.sleep(1)
    say("launch", f"no HWR2.exe process within {LAUNCH_WAIT_S} s: is Steam running and logged in? "
                  "Start the game from Steam yourself")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packages", nargs="+", metavar="ID",
                    help="these packages.json ids or `all` (default: the modded-prod list, the all-in-one pack)")
    ap.add_argument("--no-setup", action="store_true", help="skip the doctor step")
    ap.add_argument("--no-launch", action="store_true", help="build and deploy only")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; write and launch nothing")
    a = ap.parse_args(argv)

    install = gamepaths.hoh2_dir(required=False)
    if install is None:
        say("install", "Heroes of Hammerwatch II not found through Steam; set HWP_HOH2_DIR")
        return 2
    say("install", str(install))
    if game_running() and not a.dry_run:
        say("deploy", "the game is running: close Heroes of Hammerwatch II first (its .bin files are locked)")
        return 3

    if not a.no_setup:
        code, _pending = setup(a.dry_run)
        if code:
            return code

    packages = a.packages or release_packages()
    before = deployed_ids(install)
    code = build_and_deploy(packages, a.dry_run)
    if code:
        return code
    # a Workshop subscription with a deployed package's id: the game loads both copies and keeps
    # the Workshop's file of every path they share (gamelab/env.py SHADOW_SUFFIX), so the game
    # would run a mix of the published build and this one, or fail to compile
    shadowed = env.workshop_ids()
    mixed = sorted(i for i in {mod_id(p) for p in packages} if i in shadowed)
    if mixed:
        say("workshop", "you are subscribed to " + ", ".join(f"{i} ({shadowed[i].parent.name})" for i in mixed)
            + " on the Steam Workshop: the game loads that copy as well and its files win over the ones "
            "just deployed. Unsubscribe in Steam while you play your own build")
    new = sorted({mod_id(p) for p in packages} - before)
    if new:
        say("enable", "NEW packages to tick once in the game's Resource Mods, then restart: " + ", ".join(new))
    else:
        say("enable", "no new packages; the ones you ticked before stay enabled")

    if a.no_launch:
        say("launch", "skipped (--no-launch)")
        return 0
    return launch(a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
