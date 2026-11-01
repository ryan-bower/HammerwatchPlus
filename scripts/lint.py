"""Lint the Python with ruff (rules in pyproject.toml: real bugs only).

    python scripts/lint.py [--fix]
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.exit(subprocess.run([sys.executable, "-m", "ruff", "check", ".", *sys.argv[1:]], cwd=REPO).returncode)
