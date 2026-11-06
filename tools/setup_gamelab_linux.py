#!/usr/bin/env python3
"""Install the pinned Windows Python and wheels for GameLab's private Wine host.

Run with native Linux Python. Downloads are hash-checked and stay in the repo;
this does not boot Wine/the game, confirm saves, or change a Steam prefix.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "gamelab/env/userdata/linux"
ARTIFACTS = [
    ("python", "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip",
     "009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b"),
    ("python-site", "https://files.pythonhosted.org/packages/18/47/715865a6c7071f417bef9b57c8644f29cb7a55b77742bd5d93a609274e7e/lz4-4.4.5-cp311-cp311-win_amd64.whl",
     "8a842ead8ca7c0ee2f396ca5d878c4c40439a527ebad2b996b0444f0074ed004"),
    ("python-site", "https://files.pythonhosted.org/packages/54/16/12b82f791c7f50ddec566873d5bdd245baa1491bac11d15ffb98aecc8f8b/pefile-2024.8.26-py3-none-any.whl",
     "76f8b485dcd3b1bb8166f1128d395fa3d87af26360c2358fb75b80019b957c6f"),
    ("python-site", "https://files.pythonhosted.org/packages/4d/42/aaca386de5cc8bd8a0254516957c1f265e3521c91515b16e286c662854c4/pillow-12.0.0-cp311-cp311-win_amd64.whl",
     "b583dc9070312190192631373c6c8ed277254aa6e6084b74bdd0a6d3b221608e"),
]


def install(state: Path = STATE) -> None:
    for directory, url, digest in ARTIFACTS:
        cache = state / "downloads" / url.rsplit("/", 1)[1]
        cache.parent.mkdir(parents=True, exist_ok=True)
        if not cache.is_file():
            print(f"Downloading {cache.name}", flush=True)
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"SHA-256 mismatch: {cache.name}")
            cache.write_bytes(data)
        data = cache.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"SHA-256 mismatch: {cache}")
        dest = state / directory
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                target = dest / name
                if not target.resolve().is_relative_to(dest.resolve()):
                    raise ValueError(f"Unsafe archive path: {name}")
                if name.endswith("/"):
                    continue
                payload = archive.read(name)
                if target.is_file() and target.read_bytes() == payload:
                    continue
                # The search-path file below is managed separately.
                if target.is_file() and name != "python311._pth":
                    raise ValueError(f"Refusing to overwrite a different existing file: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
    # Relative paths make a cloned/moved checkout usable without local edits.
    (state / "python/python311._pth").write_text(
        "python311.zip\n.\n../python-site\n../../../../../\nimport site\n", encoding="utf-8")
    print("Windows Python 3.11.9 and pinned GameLab dependencies ready.")


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("Run this setup with native Linux Python.")
    import fcntl
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "host.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("REFUSED: another Linux GameLab host holds the runtime")
            sys.exit(4)
        install()
