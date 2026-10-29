---
name: run
description: Set up, build, deploy every HammerwatchPlus module into the user's real Heroes of Hammerwatch II install and start the game for them to play. Use when the user says /run, "run the game", "deploy the mods", "start the game with the mods", or "get all mods to load". Not for tests: a test boot is GameLab (`gamelab` skill).
---

# run

One command does everything; the user never runs python steps by hand:

```
.venv\Scripts\python.exe tools\run.py          # or: run.cmd (double-click)
```

Flags: `--no-launch` (build and deploy only), `--no-setup` (skip the doctor step), `--dry-run`
(plan only), `--packages town keys ...` (Workshop packages from `packages.json` instead of the
all-in-one pack).

It runs, in order, and prints one `run: <step>: ...` line per step:

1. **setup**: `python -m gamelab doctor --fix --no-smoke` (uv sync, the save backup, the game
   dumps, generated units, HoH1 imports when HoH1 is installed). No lab boot.
2. **build**: `tools/build.py` for the modded-prod packages (the all-in-one pack), with `--with-local` when the HoH1
   campaign import exists, so the user's own .bin files carry the real HoH1 levels.
3. **deploy**: `tools/deploy.py modded-prod` copies `dist/HammerwatchPlus-All.bin` into `<install>/mods/` and removes the HWP .bin files it did not write (the old per-module ones).
4. **launch**: opens `steam://rungameid/619820`. The user authorized launching their real
   install this way (2026-10-23, memory `zero-friction-setup`); do not start `HWR2.exe` directly.

## What to tell the user

- Read every `run:` line. The exit code is the first failing step's: 2 setup/install problem
  (the doctor rows above it say what; relay the row's hint), 3 the game is running (ask them
  to close it, then run again), 1 the launch found no process (Steam not running/logged in).
- The `run: enable:` line lists **new** packages (by default `HammerwatchPlus-All`). Mods are
  enabled per save, in the game's **Resource Mods** menu, once; the game remembers them by id
  (the .bin file name), so redeploys stay enabled. Tell the user exactly which entries to tick
  and that a restart follows. The first deploy after the per-module builds removes the old
  `HWP-<module>.bin` files, so a save that had those ticked needs `HammerwatchPlus-All` ticked once. Never edit
  their save to do it (gamelab/hps.py refuses real saves by design).
- When doctor says the HoH1 install is unknown (`ASK THE USER`), the build goes on without
  HoH1 content. Ask the user where Heroes of Hammerwatch (1) is, or whether they own it, and
  record the answer with `python -m gamelab doctor --hoh1 "<dir>"` / `--no-hoh1`, then run again.
- Never run this while a GameLab scenario is running (the doctor step touches gamecode/
  only when it is missing, but the deploy replaces the install's .bin files).

## Adding a module

A new module ships only when it is in a package's `mods` in `packages.json` (the all-in-one pack
takes every package) and in `gamelab/scenarios/mod-all.json`; `tools/make_package_scenarios.py`
then rewrites the `pkg-*` scenarios. Any new generated content (imports, generated units) must
be made by `doctor --fix`, never by a documented manual command.
