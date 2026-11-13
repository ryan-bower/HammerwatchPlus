#!/usr/bin/env python3
"""Download and install release binaries without building or setting up GameLab.

python tools/install_release.py [v0.4.0] [--mods-dir PATH] [--packages qol coop]
Requires Python 3.11+ and gh. Defaults to the latest stable release and the all-in-one pack.
Close the game first. Only HWP-*.bin and HammerwatchPlus*.bin are replaced/removed;
unrelated mods, unpacked folders, saves, config and Workshop subscriptions are untouched.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import gamepaths
from release_assets import MANIFEST, REPOSITORY, owned_binary, read_manifest, verify_assets


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, text=True, stdout=subprocess.PIPE).stdout


def installed_binaries(target: Path) -> list[Path]:
    if target.is_symlink():
        raise ValueError(f"Refusing symlinked mods directory: {target}")
    old = sorted(p for p in target.iterdir() if owned_binary(p)) if target.exists() else []
    if any(p.is_symlink() or not p.is_file() for p in old):
        raise ValueError("An HWP .bin path is a link or directory; move it aside manually")
    return old


def install(directory: Path, target: Path, assets: list[dict], dry_run: bool = False) -> None:
    verify_assets(directory, assets)
    old = installed_binaries(target)
    print(f"Install into {target}")
    for path in old:
        print(f"  replace/remove {path.name}")
    for asset in assets:
        print(f"  install {asset['file']}")
    if dry_run:
        return
    target.mkdir(parents=True, exist_ok=True)
    lock = target / ".hwp-install.lock"
    handle = lock.open("x")
    try:
        old = installed_binaries(target)
        backup = Path(tempfile.mkdtemp(prefix=".hwp-backup-", dir=target))
        moved, written = [], []
        try:
            for path in old:
                path.rename(backup / path.name)
                moved.append(path.name)
            for asset in assets:
                destination = target / asset["file"]
                written.append(destination)
                shutil.copy2(directory / asset["file"], destination)
        except OSError:
            try:
                for path in written:
                    path.unlink(missing_ok=True)
                for name in moved:
                    (backup / name).rename(target / name)
            except OSError as exc:
                raise OSError(f"Rollback failed; recover old binaries from {backup}: {exc}") from exc
            shutil.rmtree(backup)
            raise
        shutil.rmtree(backup)
    finally:
        handle.close()
        lock.unlink()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag", nargs="?", help="release tag; omitted = latest stable")
    ap.add_argument("--repo", default=REPOSITORY)
    ap.add_argument("--mods-dir", type=Path, help="default: Steam HoH2 install/mods (or HWP_HOH2_DIR/mods)")
    ap.add_argument("--packages", nargs="+", default=["all"])
    ap.add_argument("--dry-run", action="store_true", help="download and verify, but do not change mods")
    args = ap.parse_args(argv)
    if "all" in args.packages and len(args.packages) != 1:
        raise ValueError("Choose all OR individual packages, not both")
    release = json.loads(gh("release", "view", *([args.tag] if args.tag else []), "--repo", args.repo,
                            "--json", "tagName,isDraft"))
    if release["isDraft"]:
        raise ValueError("Refusing an unpublished draft release")
    tag = release["tagName"]
    target = args.mods_dir if args.mods_dir is not None else gamepaths.hoh2_dir() / "mods"
    with tempfile.TemporaryDirectory(prefix="hwp-release-") as tmp:
        directory = Path(tmp)
        gh("release", "download", tag, "--repo", args.repo, "--dir", tmp, "--pattern", MANIFEST)
        doc = read_manifest(directory / MANIFEST, tag)
        unknown = set(args.packages) - doc["packages"].keys()
        if unknown:
            raise ValueError(f"Packages absent from {tag}: {', '.join(sorted(unknown))}")
        assets = [doc["packages"][p] for p in dict.fromkeys(args.packages)]
        patterns = [arg for asset in assets for arg in ("--pattern", asset["file"])]
        gh("release", "download", tag, "--repo", args.repo, "--dir", tmp, *patterns)
        print(f"Release {tag}, source {doc.get('revision', 'unknown')}")
        install(directory, target, assets, args.dry_run)
    print("Dry run: no mods changed." if args.dry_run else
          "Installed. Restart the game and enable the installed pack(s) in Resource Mods for your profile.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f"install-release: {exc}")
