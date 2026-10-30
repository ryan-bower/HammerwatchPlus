#!/usr/bin/env python3
"""Rebuild current local mods, select a NEW local profile, and launch through Steam.

    run.py                         # all normal modules plus available HoH1 imports
    run.py --profile-name MyRun     # choose the new profile name
    run.py --no-launch              # prepare mods AND a fresh default profile
    run.py --no-setup               # skip doctor when setup was just refreshed
    run.py --dry-run                # plan only; no writes or launch
    run.py --packages town keys     # selected packages instead of all
    run.py --character sorcerer:15:TestSorc  # prepare this character, bypassing the UI
    run.py --no-ui                  # no preset characters, default starting gold
    run.py --character sorc:15:TestSorc --gold 2500000  # configure starting gold

Every invocation creates a new profile with exactly the deployed mods enabled.
Saves and config are backed up first; existing characters are preserved. A
conflicting Workshop id uses a separate -local id so published files cannot win.
Builds the current checkout without pulling or replacing local source edits.
This is the requested real play workflow; tests still use GameLab lab mode.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gamepaths  # noqa: E402
import play_profile  # noqa: E402
import saves  # noqa: E402
import pin_build  # noqa: E402
import profile_seed  # noqa: E402
import save_builder  # noqa: E402
from gamelab import env, lock, logparse  # noqa: E402

HOH2_STEAM_URL = f"steam://rungameid/{gamepaths.HOH2_APPID}"
ENVIRONMENTS = gamepaths.GAMELAB / "env" / "environments.json"
LAUNCH_WAIT_S = 120


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
    if out.returncode:
        raise RuntimeError("cannot check running games: " + (out.stderr or out.stdout).strip())
    return "HWR2.exe" in out.stdout


@contextmanager
def runtime_lock(dry_run: bool):
    """Share GameLab's exclusive lock without clearing its scratch saves or teardown."""
    if dry_run:
        yield
        return
    lock.LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock.LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f"runtime lock held: {lock.LOCK.read_text()}; diagnose the owner before retrying")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"pid": os.getpid(), "scenario": "player-run", "mode": "play"}, file)
        last = json.loads(lock.TEARDOWN.read_text()) if lock.TEARDOWN.exists() else {"clean": True}
        if not last.get("clean"):
            raise RuntimeError(f"previous GameLab teardown is dirty: {last}; diagnose before retrying")
        yield
    finally:
        lock.LOCK.unlink()


def prepare_profile(install: Path, packages: list[str], dry_run: bool, name: str | None,
                    native_data: bytes | None = None, seed_run: str | None = None) -> int:
    ids = [Path(env.personal_package_name(p)).stem for p in packages]
    if dry_run:
        say("profile", "would back up saves/config, create a NEW local profile with " + ", ".join(ids)
            + ", and make it the default")
        return 0
    problems = saves.confirmation_problems() + pin_build.mismatch()
    if problems:
        say("profile", "REFUSED: " + "; ".join(problems))
        return 2
    code = saves.backup()
    if code:
        return code
    code = saves.verify()
    if code:
        return code
    receipt = play_profile.create(install, ids, gamepaths.SAVES_BACKUP / "play-profiles", name, native_data)
    if seed_run:
        receipt["seed_run"] = seed_run
        (Path(receipt["backup"]) / "profile.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    say("profile", f"NEW local profile {receipt['slot']}: {receipt['name']}; default selected")
    say("enable", "already enabled: " + ", ".join(ids))
    say("backup", receipt["backup"])
    for character in receipt["characters"]:
        say("character", f"{character['name']}: {character['class']}, level {character['level']}")
    say("gold", f"{receipt['starting_gold']:,} starting gold")
    return 0


def choose_save(args, packages: list[str]) -> save_builder.Plan | None:
    plan = save_builder.Plan(args.profile_name, [save_builder.parse_character(c) for c in args.character], args.gold)
    available = profile_seed.available_classes(packages)
    plan.validate(available)
    if args.dry_run or args.no_ui or args.character:
        if args.dry_run and not args.no_ui and not args.character:
            say("builder", "would open the pre-launch character/save builder")
        return plan
    say("builder", "opening the character/save builder; add characters, start empty, or cancel")
    return save_builder.show(plan, available)


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
    cmd = [python(), str(gamepaths.TOOLS / "deploy.py"), "modded-prod", *packages, "--avoid-workshop"]
    if dry_run:
        cmd.append("--dry-run")
    c = subprocess.run(cmd, cwd=gamepaths.REPO)
    if c.returncode:
        say("deploy", f"failed (exit {c.returncode}); see above")
        return c.returncode
    say("deploy", "done" if not dry_run else "dry run")
    return 0


def launch(dry_run: bool, expected_ids: list[str] | None = None) -> int:
    if dry_run:
        say("launch", f"would open {HOH2_STEAM_URL}")
        return 0
    if sys.platform != "win32":
        say("launch", "only on Windows")
        return 2
    log = gamepaths.hoh2_dir() / "HWR2.exe.log"
    previous = log.stat().st_mtime_ns if log.exists() else None
    say("launch", HOH2_STEAM_URL)
    os.startfile(HOH2_STEAM_URL)  # type: ignore[attr-defined]
    t0 = time.time()
    while time.time() - t0 < LAUNCH_WAIT_S:
        running = game_running()
        if log.exists() and log.stat().st_mtime_ns != previous:
            text = log.read_text(encoding="utf-8", errors="replace")
            if logparse.compile_failed(text):
                say("launch", "scripts failed to compile; inspect " + str(log))
                return 1
            enabled = all(f"Adding packed mod '{mid}'" in text for mid in expected_ids or [])
            if running and enabled and "Started menu level" in text:
                say("launch", f"main menu loaded with the deployed mods after {time.time() - t0:.0f} s")
                return 0
        time.sleep(1)
    say("launch", f"menu with the deployed mods was not ready within {LAUNCH_WAIT_S} s; inspect {log}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packages", nargs="+", metavar="ID",
                    help="these packages.json ids or `all` (default: the modded-prod list, the all-in-one pack)")
    ap.add_argument("--no-setup", action="store_true", help="skip the doctor step")
    ap.add_argument("--no-launch", action="store_true", help="prepare mods and a fresh default profile without launching")
    ap.add_argument("--profile-name", help="name for the new local profile (default: HammerwatchPlus plus date/time)")
    ap.add_argument("--character", action="append", default=[], metavar="CLASS:LEVEL[:NAME]",
                    help="add a prepared character (repeat for more); bypasses the builder UI")
    ap.add_argument("--gold", type=save_builder.parse_gold, default=save_builder.DEFAULT_GOLD, metavar="AMOUNT",
                    help="starting gold shared by the new profile (default: 1,000,000; 0 starts broke)")
    ap.add_argument("--no-ui", action="store_true", help="skip the builder UI; omit characters unless --character is supplied; --gold still applies")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; write and launch nothing")
    a = ap.parse_args(argv)

    install = gamepaths.hoh2_dir(required=False)
    if install is None:
        say("install", "Heroes of Hammerwatch II not found through Steam; set HWP_HOH2_DIR")
        return 2
    say("install", str(install))
    try:
        if not a.dry_run and game_running():
            say("deploy", "the game is running: close Heroes of Hammerwatch II first (its .bin files are locked)")
            return 3
        packages = list(dict.fromkeys(a.packages or release_packages()))
        if "all" in packages and len(packages) > 1:
            say("build", "REFUSED: choose all OR individual packages; all already includes them")
            return 2
        plan = choose_save(a, packages)
        if plan is None:
            say("builder", "cancelled; no setup, deployment or profile changes")
            return 0
        with runtime_lock(a.dry_run):
            if not a.dry_run and game_running():
                say("deploy", "the game is running: close Heroes of Hammerwatch II first (its .bin files are locked)")
                return 3
            if not a.no_setup:
                code, _pending = setup(a.dry_run)
                if code:
                    return code
            code = build_and_deploy(packages, a.dry_run)
            if code:
                return code
        # GameLab must own its own lock for the entire isolated native session.
        # Real profile writes happen only after its verdict/teardown is verified.
        native_data, seed_run = None, None
        if plan.characters or plan.starting_gold:
            if a.dry_run:
                roster = ", ".join(f"{c.name} ({c.class_id} level {c.level})" for c in plan.characters)
                say("characters", "would prepare in isolated lab mode: " + (roster or "no preset characters"))
                say("gold", f"would prepare {plan.starting_gold:,} starting gold for the profile")
            else:
                say("characters", "preparing the requested save and gold privately; this can take a few minutes")
                native_data, seed_run = profile_seed.generate(plan, packages)
        with runtime_lock(a.dry_run):
            if not a.dry_run and game_running():
                say("profile", "a game started during preparation; close it before creating the play profile")
                return 3
            code = prepare_profile(install, packages, a.dry_run, plan.profile_name, native_data, seed_run)
            if code:
                return code
            if a.no_launch:
                say("launch", "skipped (--no-launch)")
                return 0
            return launch(a.dry_run, [Path(env.personal_package_name(p)).stem for p in packages])
    except (OSError, ValueError, RuntimeError) as error:
        say("refused", str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
