#!/usr/bin/env python3
"""Build and publish a GitHub release: python tools/release.py [v0.4.0].

Requires a clean, pushed checkout, the game dump required by build.py, and authenticated gh.
Without a tag, bump the highest stable GitHub tag's patch version (first release: v0.1.0).
Use --build-only to prepare assets without contacting GitHub or creating a tag/release.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from release_assets import MANIFEST, REPOSITORY, digest, package_filename, read_manifest, verify_assets

REPO = Path(__file__).resolve().parents[1]


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=REPO, check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def require_clean() -> None:
    if run("git", "status", "--porcelain", capture=True):
        raise ValueError("Checkout is dirty; commit changes before cutting a release")


def next_tag(tags: list[str]) -> str:
    versions = []
    for tag in tags:
        # Older releases used two components (v0.3); treat those as patch zero.
        match = re.fullmatch(r"v([0-9]+)\.([0-9]+)(?:\.([0-9]+))?", tag.removeprefix("refs/tags/"))
        if match:
            versions.append(tuple(int(part or 0) for part in match.groups()))
    if not versions:
        return "v0.1.0"
    major, minor, patch = max(versions)
    return f"v{major}.{minor}.{patch + 1}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag", nargs="?", help="new release tag; omitted = next patch version")
    ap.add_argument("--repo", default=REPOSITORY, help="GitHub OWNER/REPO")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--draft", action="store_true", help="leave the uploaded release as a draft")
    ap.add_argument("--prerelease", action="store_true")
    args = ap.parse_args(argv)
    if args.tag is not None and not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", args.tag):
        raise ValueError("Use a version tag such as v0.4.0 or v0.4.0-rc.1")
    require_clean()
    revision = run("git", "rev-parse", "HEAD", capture=True)
    if not args.build_only:
        run("gh", "auth", "status")
    if args.tag is None:
        if args.build_only:
            tags = run("git", "tag", "--list", capture=True).splitlines()
        else:
            tags = run("gh", "api", f"repos/{args.repo}/git/matching-refs/tags/", "--paginate",
                       "--jq", ".[].ref", capture=True).splitlines()
        args.tag = next_tag(tags)
        print(f"Selected release {args.tag}", flush=True)
    output = REPO / "dist" / "releases" / args.tag
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new tag or move it aside")
    if not args.build_only:
        tags = json.loads(run("gh", "api", f"repos/{args.repo}/git/matching-refs/tags/{args.tag}", capture=True))
        if any(tag["ref"] == f"refs/tags/{args.tag}" for tag in tags):
            raise ValueError(f"Tag {args.tag} already exists on GitHub; releases are not overwritten")
    run(sys.executable, "scripts/test.py")
    run(sys.executable, "tools/build.py", "--check")
    run(sys.executable, "tools/build.py")
    require_clean()
    if run("git", "rev-parse", "HEAD", capture=True) != revision:
        raise ValueError("HEAD changed during the build")
    packages = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in packages["packages"]] + ["all"]
    output.mkdir(parents=True)
    assets = {}
    for package in ids:
        name = package_filename(package)
        source = REPO / "dist" / name
        shutil.copy2(source, output / name)
        assets[package] = {"file": name, "size": source.stat().st_size, "sha256": digest(output / name)}
    manifest = output / MANIFEST
    manifest.write_text(json.dumps({"schema": 1, "tag": args.tag, "revision": revision,
                                    "packages": assets}, indent=2) + "\n", encoding="utf-8")
    read_manifest(manifest, args.tag)
    verify_assets(output, list(assets.values()))
    print(f"Release assets: {output}", flush=True)
    if args.build_only:
        return 0
    # Keep incomplete uploads out of latest; a failed upload leaves a recoverable draft.
    run("gh", "release", "create", args.tag, "--repo", args.repo, "--target", revision,
        "--title", args.tag, "--generate-notes", "--draft", *(["--prerelease"] if args.prerelease else []))
    run("gh", "release", "upload", args.tag, "--repo", args.repo, str(manifest),
        *(str(output / asset["file"]) for asset in assets.values()))
    if not args.draft:
        run("gh", "release", "edit", args.tag, "--repo", args.repo, "--draft=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f"release: {exc}")
