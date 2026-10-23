#!/usr/bin/env python3
"""run.py - one command from a clone to playing: set up, build, deploy to your Steam install, launch.

    run.py                      # setup (doctor --fix, no lab boot), build every release module, deploy, launch
    run.py --no-launch          # everything but starting the game
    run.py --no-setup           # skip the doctor step (you just ran it)
    run.py --dry-run            # say what would happen; write nothing, launch nothing
    run.py --mods core fishing  # only these modules (the rest stay as deployed)

The steps, in order (each prints a `run:` line; the exit code is the first failing step's):

1. setup     `python -m gamelab doctor --fix --no-smoke`: uv sync, the save backup, the
             game dumps (gamecode/), generated units, and the HoH1 imports when a Heroes of
             Hammerwatch (1) install is found. When doctor cannot find HoH1 and nobody has
             answered yet, the run goes on without HoH1 content and says how to answer
             (`python -m gamelab doctor --hoh1 "<dir>"` or `--no-hoh1`).
2. build     tools/build.py for the modded-prod module list (gamelab/env/environments.json),
             with --with-local whenever the HoH1 campaign import is present, so your own
             .bin files carry the real HoH1 levels (never publish those: `build.py` without
             --with-local makes the shareable ones).
3. deploy    tools/deploy.py modded-prod: copies dist/HWP-<id>.bin into <install>/mods/.
             Refuses while the game is running (Windows keeps the .bin files open).
4. launch    the game through Steam (steam://rungameid/619820), so the overlay, cloud
             saves and achievements work as usual. The user asked for this (2026-10-23);
             GameLab's hidden-desktop rules are for test runs, not for playing.

Enabling the mods is a one-time step in the game: Resource Mods > tick every HWP-* entry,
then restart. The game remembers the set per save by the mod's id, so a redeploy of the
same ids stays enabled; only a NEW module needs ticking once (this tool lists them).
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

HOH2_STEAM_URL = f"steam://rungameid/{gamepaths.HOH2_APPID}"
ENVIRONMENTS = gamepaths.GAMELAB / "env" / "environments.json"
CAMPAIGN_MARKER = gamepaths.MODS / "campaign" / "hoh1" / ".hwp-generated"
LAUNCH_WAIT_S = 45


def python() -> str:
    venv = gamepaths.REPO / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.is_file() else sys.executable


def say(step: str, text: str) -> None:
    print(f"run: {step}: {text}", flush=True)


def release_mods() -> list[str]:
    decl = json.loads(ENVIRONMENTS.read_text(encoding="utf-8"))["modded-prod"]
    return list(decl["mods"])


def game_running() -> bool:
    if sys.platform != "win32":
        return False
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq HWR2.exe", "/NH"], capture_output=True, text=True)
    return "HWR2.exe" in out.stdout


def deployed_ids(install: Path) -> set[str]:
    mods = install / "mods"
    return {p.stem[4:] for p in mods.glob("HWP-*.bin")} if mods.is_dir() else set()


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


def build_and_deploy(mods: list[str], dry_run: bool) -> int:
    with_local = CAMPAIGN_MARKER.is_file()
    say("build", f"{len(mods)} modules" + (" with your HoH1 content (--with-local)" if with_local else
                                           " (no HoH1 import: the HoH2-tiles campaign)"))
    cmd = [python(), str(gamepaths.TOOLS / "deploy.py"), "modded-prod"] + mods
    if with_local:
        cmd.append("--with-local")
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
    ap.add_argument("--mods", nargs="+", metavar="ID", help="only these modules (default: the modded-prod list)")
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

    mods = a.mods or release_mods()
    before = deployed_ids(install)
    code = build_and_deploy(mods, a.dry_run)
    if code:
        return code
    new = sorted(set(mods) - before)
    if new:
        say("enable", "NEW modules to tick once in the game's Resource Mods, then restart: "
                      + ", ".join(f"HWP-{m}" for m in new))
    else:
        say("enable", "no new modules; the ones you ticked before stay enabled")

    if a.no_launch:
        say("launch", "skipped (--no-launch)")
        return 0
    return launch(a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
