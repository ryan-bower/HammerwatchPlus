"""Experimental Linux host for the existing Windows GameLab runtime.

The Windows game, injected DLL and Win32 input code run together in Wine's
Windows Python, on a private X server. Never use the player's Proton prefix or
display. All existing Windows preflight and post-run assertions still apply;
Wine support is not a reason to weaken them.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import select
import secrets
import shutil
import signal
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "gamelab" / "env" / "userdata" / "linux"
PREFIX = STATE / "proton" / "pfx" if os.environ.get("HWP_PROTON") == "1" else STATE / "wine64-prefix"


@contextlib.contextmanager
def termination_signals():
    """Unwind cleanup on SIGTERM as well as Ctrl-C (e.g. a harness timeout)."""
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def windows_path(path: str | Path) -> str:
    """Wine's default Z: mapping, without starting Wine on the user's display."""
    return "Z:" + str(Path(path).expanduser().resolve()).replace("/", "\\")


def steam_running(proc_root: Path = Path("/proc")) -> bool:
    """Check this user's native Steam process, not Wine's Windows task list."""
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid == os.getuid() and (entry / "comm").read_text().strip() == "steam":
                return True
        except (OSError, UnicodeError):
            continue  # process exited, or belongs to another user
    return False


def mod_versions() -> dict:
    """Collect Git provenance on the host; Windows Python cannot run Linux git."""
    def git(*args):
        result = subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                                text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(f"git provenance failed: {result.stderr.strip()}")
        return result.stdout

    trees = {}
    for line in git("ls-tree", "HEAD:mods").splitlines():
        meta, name = line.split("\t", 1)
        trees[name] = {"tree": meta.split()[2], "dirty": False}
    changed = (git("diff", "--name-only", "-z", "HEAD", "--", "mods") +
               git("ls-files", "--others", "--exclude-standard", "-z", "--", "mods"))
    for path in changed.split("\0"):
        parts = path.split("/")
        if len(parts) > 1:
            trees.setdefault(parts[1], {"tree": None})["dirty"] = True
    return trees


def game_processes(proc_root: Path = Path("/proc")) -> list[int]:
    """Wine tasklist cannot see a player game in another prefix; check the host too.

    Refuse any existing HoH2 process owned by this user, including stale lab games.
    Do not inspect or kill the player's prefix to determine ownership.
    """
    found = []
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            if (entry / "comm").read_text().strip().lower() in ("hwr2.exe", "hwr2"):
                found.append(int(entry.name))
        except FileNotFoundError:
            continue  # process exited while being inspected
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"cannot inspect host process {entry.name}: {exc}") from exc
    return found


def prerequisites() -> tuple[dict[str, str], list[str]]:
    runtime = {}
    errors = []
    wine = os.environ.get("HWP_WINE", "wine64" if shutil.which("wine64") else "wine")
    wine_path = shutil.which(wine)
    # Prefer the server packaged with this Wine, rather than mixing versions.
    server = str(Path(wine_path).parent / "wineserver") if wine_path else "wineserver"
    for name, setting, default in (("wine", "HWP_WINE", wine),
                                    ("wineserver", "HWP_WINESERVER", server),
                                    ("Xvfb", "HWP_XVFB", "Xvfb")):
        executable = shutil.which(os.environ.get(setting, default))
        if executable:
            runtime[name] = executable
        else:
            errors.append(f"{name} not found; install it or set {setting}")
    python = Path(os.environ.get("HWP_WINE_PYTHON", str(STATE / "python" / "python.exe"))).expanduser()
    if python.is_file():
        runtime["python"] = str(python.resolve())
    else:
        errors.append("Windows Python 3.10+ not found; set HWP_WINE_PYTHON to a Windows "
                      "python.exe (not the Linux .venv interpreter). See docs/gamelab-linux.md")
    return runtime, errors


@contextlib.contextmanager
def isolated_display(executable: str):
    """Start a new X server; -displayfd confirms its socket was reserved."""
    read_fd, write_fd = os.pipe()
    proc = None
    try:
        # Avoid even a name collision with a socket-activated Xwayland display
        # that Xvfb's automatic free-number search may not see in this namespace.
        candidate = ":" + str(1000 + secrets.randbelow(50000))
        while candidate == os.environ.get("DISPLAY", "").split(".")[0]:
            candidate = ":" + str(1000 + secrets.randbelow(50000))
        proc = subprocess.Popen(
            [executable, candidate, "-displayfd", str(write_fd), "-screen", "0", "1280x720x24",
             "-nolisten", "tcp", "-noreset"],
            pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            start_new_session=True)
        os.close(write_fd)
        write_fd = None
        if not select.select([read_fd], [], [], 15)[0]:
            raise RuntimeError("Xvfb did not allocate a private display within 15 seconds")
        # Xvfb writes the display number followed by a newline once it is ready.
        display = os.read(read_fd, 64).decode("ascii").strip()
        if not display.isdecimal() or proc.poll() is not None:
            raise RuntimeError("Xvfb failed to allocate a private display")
        yield ":" + display
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
        if proc is not None:
            stop_process_group(proc)
            if proc.stderr:
                proc.stderr.close()


def stop_process_group(proc: subprocess.Popen) -> None:
    # Descendants can remain after the group leader exits.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The leader can exit while a descendant ignores SIGTERM.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=5)


def child_environment(display: str) -> dict[str, str]:
    sys.path.insert(0, str(REPO / "tools"))
    import gamepaths

    env = dict(os.environ)
    # Do not inherit the player's prefix, Wayland socket, or display credentials.
    for key in ("WAYLAND_DISPLAY", "XAUTHORITY", "WINEPREFIX", "WINELOADER", "WINESERVER",
                "WINEDLLPATH", "PYTHONHOME", "PYTHONPATH", "HWP_HOST_GCC_TARGET",
                "STEAM_COMPAT_DATA_PATH", "STEAM_COMPAT_CLIENT_INSTALL_PATH",
                "STEAM_COMPAT_INSTALL_PATH", "STEAM_COMPAT_SHADER_PATH",
                "SteamAppId", "SteamGameId"):
        env.pop(key, None)
    env.update(DISPLAY=display, WINEPREFIX=str(PREFIX), WINEARCH="win64", WINEDEBUG="-all",
               PYTHONUTF8="1", PYTHONUNBUFFERED="1",
               HWP_HOST_STEAM_RUNNING="1" if steam_running() else "0")
    # Force X11 even on Wine builds with a Wayland driver.
    # Disable optional Wine Mono/Gecko installation dialogs at first startup.
    env["WINEDLLOVERRIDES"] = "winewayland.drv,mscoree,mshtml=d"
    if os.environ.get("HWP_PROTON") == "1":
        # Proton supplies the native-Steam bridge. Its data stays separate from
        # both the user's prefix and the standalone Wine test prefix.
        steam = gamepaths.steam_root()
        if steam is None:
            raise RuntimeError("Proton requires a discovered Steam client install")
        env.update(STEAM_COMPAT_DATA_PATH=str(PREFIX.parent),
                   STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),
                   STEAM_COMPAT_INSTALL_PATH=str(STATE.parent / "game"),
                   STEAM_COMPAT_SHADER_PATH=str(STATE / "shaders"),
                   SteamAppId=gamepaths.HOH2_APPID, SteamGameId=gamepaths.HOH2_APPID,
                   PROTON_CRASH_REPORT_DIR=str(STATE / "crashes"),
                   PROTON_LOG="0", PROTON_LOG_DIR=str(STATE / "logs"))
    for key, path in (("HWP_STEAM_DIR", gamepaths.steam_root()),
                      ("HWP_HOH2_DIR", gamepaths.hoh2_dir(required=False)),
                      ("HWP_HOH1_DIR", gamepaths.hoh1_dir(required=False))):
        if path is not None:
            env[key] = windows_path(path)
    for key in ("HWP_LOCALAPPDATA", "HWP_PATHS_LOCAL"):
        if os.environ.get(key):
            env[key] = windows_path(os.environ[key])
    appdata = gamepaths.proton_localappdata()
    if "HWP_LOCALAPPDATA" not in os.environ and appdata is not None:
        env["HWP_LOCALAPPDATA"] = windows_path(appdata)
    return env


def translate_arguments(argv: list[str]) -> list[str]:
    args = list(argv)
    if args[:1] == ["run"] and len(args) > 1 and args[1].endswith(".json"):
        args[1] = windows_path(args[1])
    if "--hoh1" in args:
        index = args.index("--hoh1") + 1
        if index < len(args):
            args[index] = windows_path(args[index])
    args = ["--hoh1=" + windows_path(arg.split("=", 1)[1])
            if arg.startswith("--hoh1=") else arg for arg in args]
    return args


def main(argv: list[str]) -> int:
    try:
        with termination_signals():
            return _main(argv)
    except KeyboardInterrupt:
        return 130


def _main(argv: list[str]) -> int:
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        print("Use: python -m gamelab doctor [--fix], run SCENARIO --mode lab, or reset")
        print("Setup and limitations: docs/gamelab-linux.md")
        return 0
    # No watch mode on Linux: Wine must never use the player's display.
    if argv[:1] in (["run"], ["suite"]):
        is_suite = argv[0] == "suite"
        parser = argparse.ArgumentParser(prog="python -m gamelab " + argv[0])
        parser.add_argument("folder" if is_suite else "scenario")
        parser.add_argument("--mode", choices=("lab", "watch"), default="lab" if is_suite else "watch")
        parser.add_argument("--accept-build-drift", action="store_true")
        parser.add_argument("--wait", type=float, default=3600 if is_suite else 0)
        if is_suite:
            parser.add_argument("--stop-on-fail", action="store_true")
            parser.add_argument("--since", default="")
        args = parser.parse_args(argv[1:])
        if args.mode != "lab":
            print("PREFLIGHT: experimental Linux runs require explicit --mode lab")
            return 2
    runtime, errors = prerequisites()
    print("GameLab Linux/Wine backend (experimental)", flush=True)
    for error in errors:
        print("  [NO] " + error)
    if errors:
        print("No game started; no automatic fallback to the user's display or Proton prefix.")
        return 2
    if argv[:1] in (["run"], ["suite"]) and not steam_running():
        print("PREFLIGHT: start Steam and sign in to the account that owns HoH2; no game started.")
        return 2
    if argv[:1] in (["run"], ["suite"]) or (argv[:1] == ["doctor"] and
                                                   ("--fix" in argv or "--smoke" in argv)):
        try:
            players = game_processes()
        except RuntimeError as exc:
            print(f"REFUSED: {exc}; resolve host process visibility before running")
            return 4
        if players:
            print(f"REFUSED: an existing host HoH2 process owns the runtime: {players}; "
                  "close the player game or diagnose a stale lab run first")
            return 4
    STATE.mkdir(parents=True, exist_ok=True)
    # Held through wineserver cleanup. A second Linux invocation must not kill
    # the first invocation's Wine processes, even before the Windows lab lock.
    with open(STATE / "host.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("REFUSED: another Linux GameLab host holds the Wine prefix")
            return 4
        try:
            PREFIX.parent.mkdir(parents=True, exist_ok=True)
            with isolated_display(runtime["Xvfb"]) as display:
                env = child_environment(display)
                # Wine startup and cleanup must use the same server binary.
                env["WINESERVER"] = runtime["wineserver"]
                env["HWP_HOST_MODS_VERSION"] = json.dumps(mod_versions())
                compiler = shutil.which(os.environ.get("HWP_MINGW_CC", "x86_64-w64-mingw32-gcc"))
                if compiler:
                    target = subprocess.run([compiler, "-dumpmachine"], capture_output=True,
                                            text=True, timeout=15)
                    if target.returncode == 0:
                        env["HWP_HOST_GCC_TARGET"] = target.stdout.strip()
                    if argv[:1] == ["doctor"] and "--fix" in argv:
                        built = subprocess.run([sys.executable, "-c",
                                                "import sys; sys.path.insert(0, 'tools'); "
                                                "import bootstrap; bootstrap.build_shim(False)"],
                                               cwd=REPO, timeout=120)
                        if built.returncode:
                            return 2
                args = translate_arguments(argv)
                result = STATE / "host-result.json"
                output = STATE / "host-output.log"
                result.unlink(missing_ok=True)
                output.unlink(missing_ok=True)
                env["HWP_LINUX_RESULT"] = windows_path(result)
                env["HWP_LINUX_OUTPUT"] = windows_path(output)
                cmd = [runtime["wine"], windows_path(runtime["python"]),
                       "-m", "gamelab.wine_entry", *args]
                proc = None
                try:
                    proc = subprocess.Popen(cmd, cwd=REPO, env=env, start_new_session=True)
                    # The scenario launcher enforces its own deadline; doctor/reset
                    # also need a bound when Wine startup or a tool blocks on a dialog.
                    proc.wait(timeout=180 if argv[0] not in ("run", "suite") and "--fix" not in argv else None)
                    if output.is_file():
                        print(output.read_text(encoding="utf-8"), end="", flush=True)
                    if not result.is_file():
                        raise RuntimeError("Windows Python returned no bridge result; see Wine startup errors above")
                    return int(json.loads(result.read_text(encoding="utf-8"))["exit_code"])
                finally:
                    if proc is not None:
                        stop_process_group(proc)
                    # Only the private prefix; never the player's Wine/Proton server.
                    subprocess.run([runtime["wineserver"], "-k"], env=env, timeout=15,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            print(f"PREFLIGHT: Linux runtime failed: {exc}")
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
