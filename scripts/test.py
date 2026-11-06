"""Offline checks: the test suite, then every generated file that must match its source.

    python scripts/test.py [pytest args...]

Needs no game. Tests marked `needs_gamecode` skip without the local dump (gamelab doctor --fix).
Exit 0 only when everything passes. CI runs exactly this.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECKS = [
    ["-m", "pytest", *sys.argv[1:]],
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
