---
name: release
description: Merge ready PRs and cut a HammerwatchPlus GitHub release, or edit release notes. Use for "cut a release", "new release", "merge open PRs then release", or when writing/editing release descriptions.
---

# release

## Merging first
- Merge only open, non-draft PRs. Skip any PR whose description says not to merge yet, and list the skipped ones for the user.
- Stacked PRs need the async API: `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/merge-async -f merge_method=merge -f merge_action=direct_merge`.

## Building
- Build from a clean checkout of `origin/main` (a worktree), never the user's working tree. Run `uv run python tools/build.py --check` then `uv run python tools/build.py`.
- Use the same assets as the last release: `HammerwatchPlus-X.Y-windows.zip`, `HammerwatchPlus-X.Y-linux.tar.gz` (each a `HammerwatchPlus-X.Y/` folder of every `.bin`, `INSTALL.txt`, `SHA256SUMS.txt`), `HammerwatchPlus-All.bin` and `SHA256SUMS.txt`.
- After uploading, re-download the assets and check them against `SHA256SUMS.txt`.

## Notes
Concise and accurate, for players. No intro line, no "built from", no QA disclaimers, no SHA256 text.

```markdown
## Updates
- <one short line per change> (#PR, or a commit hash when there's no PR)

## Downloads
`HammerwatchPlus-All.bin` is the whole mod in one file and works on **both Windows and Linux**. The `-windows.zip` and `-linux.tar.gz` hold that same file plus each package separately (`HWP-<package>.bin`, each works on its own); only the archive format differs.

**Install:** copy the `.bin` into the game's `mods/` folder and enable it under Resource Mods. Everyone in the lobby needs the same files.
```

- Call it "Updates", never "What's new since X".
- Player-facing changes only: leave out tests, dev tools, docs and launcher-only changes.
