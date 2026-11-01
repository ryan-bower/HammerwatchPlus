# Contributing

Read [CLAUDE.md](CLAUDE.md) first: it has the safety rules for running the game and the
evidence rules for claiming a fix works. Every change ends with a line in
[docs/status.md](docs/status.md) and its notes in [docs/RE_NOTES.md](docs/RE_NOTES.md).

## Setup

Requirements:
- Windows, with Steam running.
- Python 3.14+ with [uv](https://docs.astral.sh/uv/).
- gcc from mingw-w64 (x86_64), which builds the GameLab capture shim. It can be on PATH,
  or extracted under `gamelab/fixtures/cache/toolchain/` as `mingw64/bin/gcc.exe` or
  `w64devkit/bin/gcc.exe`. Doctor and bootstrap prefer PATH, then those local copies;
  only compiler child processes get the compiler's bin directory added to PATH.
- HoH2 installed.
- HoH1 optional: with it, doctor imports the HoH1 content (pets, levels, campaign, class art).

After setup creates `.venv`, use `uv run python` in place of `python` below, or run
`.\.venv\Scripts\python.exe` directly, so GameLab uses the installed project dependencies.

```
python tools/run.py                   # everything below that a play session needs, then launch (run.cmd; flags: --no-launch --dry-run)
python -m gamelab doctor              # first thing on a new clone: checks every prerequisite
python -m gamelab doctor --fix        # uv sync, back up + verify your saves, bootstrap.py (gamecode/, tools/bin/),
                                      # env_link.py, class_units.py, the HoH1 imports when HoH1 is found,
                                      # make_pet_dyes.py, then one smoke boot (null-payload, hidden)
python -m gamelab doctor --confirm-saves   # only if --fix printed AMBIGUOUS save lines and the backup is still what you want
python -m gamelab doctor --hoh1 "D:\Games\Heroes of Hammerwatch" --fix   # HoH1 not found automatically: say where it is
python -m gamelab doctor --no-hoh1    # you don't own HoH1: skip its content, stop asking
python -m gamelab doctor --smoke      # boot null-payload again; a failure names its cause (antivirus, GPU, cores)
python tools/build.py                 # pack dist/HWP-<module>.bin + dist/HammerwatchPlus-All.bin
python tools/generate/make_herbs.py            # farming's Holy Herb strains from one table: buffs, joints, lang, art (--check)
python tools/hwr_archive.py --help    # low-level archive tool (list/extract/pack HW2R and HWRR)
python tools/art/icon_art/render.py all   # skill icon ideas in the vanilla style (tools/art/icon_art/README.md)
python -m planner                     # the class planner in your browser (or planner.cmd / ./planner.sh; planner/README.md)
python tools/hoh1/import_hoh1.py pets|levels|campaign|classes   # HoH1 content by hand (doctor --fix runs all four)
```

Mods live in `mods/<id>/`. Conventions are in `docs/modules.md`, the archive format in
`docs/archive-format.md`, the script hooks in `docs/hooks.md`. What to do when the game
updates is in `docs/GAME_UPDATES.md`.

HoH1 assets are never committed. `tools/hoh1/import_hoh1.py` writes into gitignored
`hoh1_import/`, and `build.py` leaves it out of packages unless `--with-local`, so each
player imports it themselves.


## Testing

```
python scripts/test.py        # offline tests (tests/), the verb list and generated-config checks
python scripts/lint.py        # ruff
```

Native checks boot the game through GameLab:


GameLab is the test harness: it boots a sandboxed copy of the game hidden and muted,
drives it through its own scripts (no real input, no focus steals, never touching your
config or saves), and scores what happened. Start with the [quickstart](gamelab/README.md)
and [regression map](docs/qa/REGRESSIONS.md); the [detailed skill](.claude/skills/gamelab/SKILL.md)
covers authoring and troubleshooting.
Before merging to main, run `python -m gamelab run mod-all --mode lab` (every content
mod loaded together; GUI textures must be power-of-two sized or the game won't boot).
The lab game also loads your Steam account's Workshop subscriptions (the game asks Steam,
with no switch to turn that off). A built package whose id a subscription has goes into
the lab as `<id>-gamelab` (the run records `workshop_shadowed`), and every run asserts that
no enabled mod was found twice.
