"""Offline checks: the test suite, then every generated file that must match its source.

    python scripts/test.py [pytest args...]

Needs no game. Tests marked `needs_gamecode` skip without the local dump (gamelab doctor --fix).
Exit 0 only when everything passes. CI runs exactly this.

pytest runs on every core (pytest-xdist, `-n auto`) when xdist is installed (`uv sync`); pass
`-n 0` to run serially, e.g. to debug one test with `-k`.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def pytest_args(args):
    """Add `-n auto` unless the caller already chose a worker count or disabled xdist."""
    if any(a.startswith(("-n", "--numprocesses", "--dist")) or "no:xdist" in a for a in args):
        return args
    if importlib.util.find_spec("xdist") is None:
        print("pytest-xdist is not installed, so the tests run serially; `uv sync` installs it.", flush=True)
        return args
    return ["-n", "auto", *args]


CHECKS = [
    ["-m", "pytest", *pytest_args(sys.argv[1:])],
    ["tools/list_verbs.py", "--check"],
    ["tools/generate/make_config.py", "--check"],
]

failed = []
for args in CHECKS:
    print(f"\n=== python {' '.join(args)}", flush=True)
    if subprocess.run([sys.executable, *args], cwd=REPO).returncode:
        failed.append(" ".join(args))
print("\nFAILED: " + "; ".join(failed) if failed else "\nall checks passed")
sys.exit(1 if failed else 0)
