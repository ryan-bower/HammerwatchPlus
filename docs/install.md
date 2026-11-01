# Installing

No Workshop release yet. Build and play from the repo:

1. Double-click `run.cmd` (or `python tools/run.py`).
2. In the save builder, add characters (class and level 1–20) and set starting gold, then
   **Build save & launch**.
3. Pick your character. In game, the console (key left of 1) takes `hwp help`.

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
