#!/bin/sh
# Build the same mod packages as tools/build.py without Windows/GameLab setup.
set -eu
cd "$(dirname "$0")"

if command -v uv >/dev/null 2>&1; then
    exec uv run python tools/build.py "$@"
fi

# Keep dependencies out of the system Python (including on PEP 668 distros).
if ! command -v python3 >/dev/null 2>&1; then
    echo 'Python 3.10+ is required. Install python3 and python3-venv, or install uv.' >&2
    exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv || {
        echo 'Cannot create .venv. Install python3-venv (Debian/Ubuntu), or install uv.' >&2
        exit 1
    }
fi
# uv-created environments may not contain pip when uv is no longer on PATH.
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    .venv/bin/python -m ensurepip --upgrade || {
        echo 'Cannot bootstrap pip. Install python3-venv, or install uv.' >&2
        exit 1
    }
fi
.venv/bin/python -m pip install -r tools/requirements-build.txt
exec .venv/bin/python tools/build.py "$@"
