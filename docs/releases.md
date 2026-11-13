# Releases

## Install a released build

Requires Python 3.11+ and [GitHub CLI](https://cli.github.com/) (`gh`) on PATH. No Python
packages, game dump, GameLab setup or build tools are needed. Run from this checkout:

```console
python tools/install_release.py
python tools/install_release.py v0.4.0
python tools/install_release.py v0.4.0 --packages qol coop
python tools/install_release.py --mods-dir "/path/to/Heroes of Hammerwatch 2/mods" --dry-run
```

Omit the tag for GitHub's latest stable release. Only releases created with the manifest
described below are supported; older releases without it fail without changing installed mods.
Private releases require `gh auth login`. `--repo OWNER/REPO` selects a fork for either script.

Close HoH2 first. By default the installer discovers the Steam install (Windows or Linux/Proton)
and uses `<install>/mods/`; `HWP_HOH2_DIR` or `--mods-dir` overrides discovery. It downloads
the all-in-one pack, **not** duplicate individual packs. `--packages` selects individual packs
instead; don't combine them with `all`.

All selected downloads must match the release manifest's SHA-256 and size before any mods
change. Existing `HWP-*.bin` and `HammerwatchPlus*.bin` files, including old `-local` builds,
are replaced/removed so mixed versions cannot load together. Unrelated binaries, unpacked
mod folders, saves, config and Workshop subscriptions are untouched. Disable any conflicting
unpacked/Workshop copies yourself. Choosing a subset removes the other installed HWP binaries.

On a copy failure, old binaries are restored. If restoration itself fails, the error gives a
`.hwp-backup-*` directory containing the old files for manual recovery. A process crash may
leave that backup and `.hwp-install.lock`: inspect/recover them before removing the lock and
retrying. Do not run another deploy tool concurrently. `--dry-run` downloads and verifies but
does not write to the mods directory.

Restart the game and enable the installed pack(s) in **Resource Mods** for the desired profile.
The installer does not create/select profiles or launch the game. Everyone in a lobby should
install the same release and package selection. Public builds exclude personal HoH1 imports;
use the source workflow if you need your locally imported content.

## Cut a release

Use a clean checkout at the commit to release, pushed to the selected GitHub repository.
Install the normal dev/build dependencies (`uv sync`), prepare the required HoH2 game dump
using the existing setup workflow, and authenticate `gh` with release-write access.

```console
uv run python tools/release.py
uv run python tools/release.py v0.4.0
uv run python tools/release.py v0.4.0-rc.1 --prerelease
uv run python tools/release.py v0.4.0 --draft
uv run python tools/release.py v0.4.0 --build-only
```

With no version argument, the script queries all GitHub tags and increments the highest
stable version's patch number (`v0.4.2` becomes `v0.4.3`). It starts at `v0.1.0` when no stable
version exists. Legacy two-part tags such as `v0.3` count as `v0.3.0`; prerelease and unrelated
tags are ignored. An explicit tag overrides this selection. With `--build-only`, automatic
selection uses local Git tags instead, so that mode still makes no GitHub requests.

The script runs `scripts/test.py`, the builder's override/package checks, then the default
release build (never `--with-local` or `--beta`). It stages exactly the current packages from
`packages.json` and the all-in-one `.bin` in `dist/releases/<tag>/`, along with
`hwp-release.json` (source commit, tag, package filenames, sizes and SHA-256 hashes).
Old unrelated files in `dist/` are not uploaded. The checkout must remain clean and at the
same commit throughout the build.

Publishing creates a draft with an exact source target, uploads all assets, then publishes it
with GitHub-generated notes. `--draft` leaves it unpublished for review; `--build-only` neither
contacts GitHub nor creates a tag/release. Existing remote tags and existing staging directories
are refused. This script does not commit, push, run the game, or install anything.

If upload fails, the release stays a draft, never a partial latest release. Inspect the draft
with `gh release view TAG`; upload missing files from its staging directory using
`gh release upload TAG <paths>`, verify the assets, then publish via
`gh release edit TAG --draft=false`. Do not overwrite an already-published release: cut a new tag.

## Agent routing

Prefer the installer for requests to install or update a released build. Do not run doctor,
bootstrap, build or the profile launcher just to install binaries. Ask before changing the
real install if the request doesn't authorize it. Use source builds for unreleased changes,
personal imports and GameLab tests; a downloaded release is not evidence for changed source.
Only publish to GitHub when explicitly requested.

For installation of the current local checkout instead, use
`uv run python tools/install.py modded-prod` (formerly `tools/deploy.py`). See
[installing](install.md) for prerequisites. This is a source build, not a release download.
