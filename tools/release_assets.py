"""Release asset names and manifest validation, shared by publishing and installation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPOSITORY = "ryan-bower/HammerwatchPlus"
MANIFEST = "hwp-release.json"


def package_filename(package: str) -> str:
    if package == "all":
        return "HammerwatchPlus-All.bin"
    if not re.fullmatch(r"[a-z0-9]+", package):
        raise ValueError(f"Invalid package id: {package!r}")
    return f"HWP-{package}.bin"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_manifest(path: Path, tag: str) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema") != 1 or doc.get("tag") != tag:
        raise ValueError("Release manifest schema or tag does not match")
    assets = doc.get("packages")
    if not isinstance(assets, dict) or "all" not in assets:
        raise ValueError("Release manifest has no package list/all-in-one pack")
    for package, asset in assets.items():
        if not isinstance(asset, dict) or asset.get("file") != package_filename(package):
            raise ValueError(f"Invalid asset for {package!r}")
        if not isinstance(asset.get("size"), int) or asset["size"] <= 0:
            raise ValueError(f"Invalid size for {package!r}")
        if not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
            raise ValueError(f"Invalid checksum for {package!r}")
    return doc


def verify_assets(directory: Path, assets: list[dict]) -> None:
    for asset in assets:
        path = directory / asset["file"]
        if path.stat().st_size != asset["size"] or digest(path) != asset["sha256"]:
            raise ValueError(f"Checksum/size mismatch: {path.name}")


def owned_binary(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".bin") and name.startswith(("hwp-", "hammerwatchplus"))
