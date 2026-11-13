"""Offline checks: the test suite, then every generated file that must match its source.

    python scripts/test.py [pytest args...]

Needs no game. Tests marked `needs_gamecode` skip without the local dump (gamelab doctor --fix).
Exit 0 only when everything passes. CI runs exactly this.

A full run is parallel (pytest-xdist, installed by `uv sync`): every core on CI, all but two
locally, at below-normal priority so a game or GameLab run on the same machine keeps its share.
A narrowed run stays serial, because xdist's start-up costs more than it saves and swallows
`-s` output: a test file or node ID, `-k`, `-s`/`--capture=no`, `--lf` or `--sw`. Pass `-n N`
to choose yourself (`-n 0` is serial). Bytecode isn't written during the run: parallel workers
racing to cache the same test modules leave orphaned `*.pyc.<pid>` files on Windows.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NARROWING = ("-s", "--capture=no", "--lf", "--last-failed", "--sw", "--stepwise")


def narrowed(args):
    """Whether the caller picked a few tests: a path or node ID, -k, or a debugging flag."""
    for arg in args:
        if arg in NARROWING or arg.startswith("-k"):
            return True
        if not arg.startswith("-") and ("::" in arg or (REPO / arg).exists()):
            return True
    return False


def xdist_loads(args):
    """pytest-xdist is installed and pytest will load it."""
    if importlib.util.find_spec("xdist") is None:
        print("pytest-xdist is not installed, so the tests run serially; `uv sync` installs it.", flush=True)
        return False
    if "no:xdist" in os.environ.get("PYTEST_ADDOPTS", "").replace(" ", ""):
        return False
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"):
        return any("xdist" in arg for arg in args)  # only an explicit `-p xdist` loads it
    return True


def workers():
    if os.environ.get("CI"):
        return "auto"
    return str(max(1, (os.cpu_count() or 1) - 2))


def pytest_args(args):
    """Add `-n <workers>` to a full run, unless the caller chose a worker count or disabled xdist."""
    if any(a.startswith(("-n", "--numprocesses")) or "no:xdist" in a for a in args):
        return args
    if narrowed(args) or not xdist_loads(args):
        return args
    return ["-n", workers(), *args]


if __name__ == "__main__":
    CHECKS = [
        ["-m", "pytest", *pytest_args(sys.argv[1:])],
        ["tools/list_verbs.py", "--check"],
        ["tools/generate/make_config.py", "--check"],
    ]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    priority = 0 if os.environ.get("CI") else getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    failed = []
    for args in CHECKS:
        print(f"\n=== python {' '.join(args)}", flush=True)
        if subprocess.run([sys.executable, *args], cwd=REPO, env=env, creationflags=priority).returncode:
            failed.append(" ".join(args))
    print("\nFAILED: " + "; ".join(failed) if failed else "\nall checks passed")
    sys.exit(1 if failed else 0)
