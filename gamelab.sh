#!/bin/sh
# Stage only the Nix definitions: never copy game assets or save backups to /nix/store.
set -eu
cd "$(dirname "$0")"
if ! command -v nix >/dev/null 2>&1; then
    echo 'Nix is required for the pinned Linux GameLab runtime. See docs/gamelab-linux.md.' >&2
    exit 2
fi
temp=$(mktemp -d "${TMPDIR:-/tmp}/hwp-gamelab-nix.XXXXXXXX")
trap 'rm -f "$temp/flake.nix" "$temp/flake.lock"; rmdir "$temp"' EXIT
trap 'exit 130' INT TERM
cp flake.nix flake.lock "$temp/"
if [ "${1:-}" = setup ]; then
    shift
    if [ "$#" -ne 0 ]; then
        echo 'Usage: ./gamelab.sh setup' >&2
        exit 2
    fi
    nix --extra-experimental-features 'nix-command flakes' develop "path:$temp" \
        --no-update-lock-file --command python tools/setup_gamelab_linux.py
else
    nix --extra-experimental-features 'nix-command flakes' develop "path:$temp" \
        --no-update-lock-file --command python -m gamelab "$@"
fi
