# Installing

## Released binaries (no build)

With Python 3.11+ and GitHub CLI installed, close the game and run
`python tools/install_release.py` from the checkout. This installs the latest stable GitHub
release; pass a tag to pin one. Restart and enable the pack in Resource Mods for your profile.
See [releases](releases.md) for package selection, custom paths and recovery.

## Build and play from source

To build and install the current checkout without creating a profile or launching:

```console
uv run python tools/install.py modded-prod
```

This replaces stale HWP binaries in the detected install's `mods/` folder. Close the game
first. Use `--dry-run` to preview, or `--no-local` to exclude personal HoH1 imports.
Build/setup prerequisites and the existing save-safety confirmation are still required.

To build, create a fresh profile and launch instead:

1. Double-click `run.cmd` (or `python tools/run.py`).
2. In the save builder, add characters (class and level 1–20) and set starting gold, then
   **Build save & launch**.
3. Pick your character. In game, open the console with <kbd>&#96;</kbd> and type `hwp help`.

Each run builds every package from your checkout, deploys it, and starts the game in a **new
profile** with the mods enabled. Your saves and config are backed up first; old profiles are
untouched. The first run also sets up the game files, which takes a few minutes. Everyone in a
lobby needs the same mods.

## Options

| Flag | Effect |
|---|---|
| `--character sorc:15:Name` | Add a character without the UI (repeatable; no spaces in names) |
| `--gold N` | Starting gold (default 1,000,000; 0 for a fresh start) |
| `--no-ui` | Skip the save builder |
| `--profile-name "Name"` | Name the new profile |
| `--no-launch` | Prepare everything, don't start the game |
| `--dry-run` | Only print the plan |
| `--packages ID ...` | Build only these packages (default: all) |
| `--no-setup` | Skip the setup step |

## Notes

- **No Heroes of Hammerwatch 1?** Everything still works, with HoH2 tiles and placeholder
  icons (`hwp hoh1` lists what's missing). If asked, run
  `python -m gamelab doctor --hoh1 "<folder>" --fix` or `--no-hoh1` once.
- **Also subscribed on the Workshop?** Your build deploys under a separate `-local` id, so the
  two don't clash.
- **Sharing by hand:** `python tools/build.py`, then copy `dist/HWP-<package>.bin` (or
  `HammerwatchPlus-All.bin`) into `<Steam>/steamapps/common/Heroes of Hammerwatch 2/mods/`.
- **Publishing:** see [WORKSHOP.md](WORKSHOP.md).
