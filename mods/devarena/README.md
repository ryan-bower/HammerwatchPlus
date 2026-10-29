# devarena

A dev-only overlay for tuning and composing class skills. It lives in the GameLab environment
and is never deployed to a play install. The spec is `docs/devarena/SPEC.md`, and the goal and
its done-checks are in `docs/devarena/GOAL.md`.

## Launch

```
python -m gamelab run devarena/arena --mode watch
```

A lab copy of the game (the fixture's ranger, never your saves or install) boots onto
dark_citadel floor 13, culls it, applies `ranger_nature/mid` and holds until you close the
window (up to 4 h). Press F1.

## Keys

The keys below are defaults. Those with an option id can be rebound in the player menu's Plus
tab (top section, "Dev Arena: ..."); the binding is kept per save as `devarena.key.<name>`, per
player. The dock's buttons and texts show the current binding. For undo/redo only the letter
is bound; Ctrl stays the modifier (Z and Y are the US positions, swapped on QWERTZ).

| Key | Option id | Does |
|---|---|---|
| F1 | `devarena-dock` | Open or close the dock (right 35% of the screen, 45% on Loadout). The game keeps running. |
| F2 | `devarena-ab` | Swap the live slot between A and B. |
| Ctrl+Z / Ctrl+Y | `devarena-undo` / `devarena-redo` | Step the live slot back or forward through versions. |
| Enter / Esc | | Commit or revert the field being typed in. A click elsewhere commits. |
| F3 | `devarena-reset` | Arena reset: kill what the brush placed, clear encounters, fresh golem. |
| F4 | `devarena-golem` | Into / out of the golem room. |
| F6 | `devarena-pause` | Pause / resume. |
| Middle click | | Place the armed brush unit or encounter at the pointer. Esc disarms. |

While the pointer is over the dock or a field is being typed in, the player takes no attack,
skill or move input.

## Tune tab

- Pick a skill chip, then:
  - **FEEL** fields: castpoint (moves the matching timeline times too), anim-length, blocking.
  - **NUMBERS**: one cell per level, with a growth stepper, a slider (drag, commits on release)
    and a sparkline. Pin mode makes the growth stepper leave a cell alone.
  - **REFS**: string binds that point at other files. They need a relaunch.
- Every commit is a new version, made in B; A stays the champion. A small "DEV A v.. B v.."
  line shows top-left while the dock is closed.

## Loadout tab

- **Browser**: class and subclass chips, a search field, and one row per preset (early/mid/end
  and hand variants). A click applies the preset in place, cross-class too. `[x]` ticks it for
  compare (two at most), and `*` makes it a favorite. Favorites are a one-click row at the top.
- **Sheet**: the live build. Level, stats, skills and combos have [-]/[+] steppers. Rows that
  differ from the preset are marked `*`, and so is the mini HUD (`DEV | <preset>*`). The
  sheet also lists gear (base id, quality, ilvl; requirements off) and trinkets.
- **Revert** re-applies the preset. **Save variant** logs the build as `<preset>+eN`.

## Arena tab

- **FLOOR**: Reset (F3 by default), Reload (same seed, the NG+ set here), Cull, Pause (F6 by default).
- **MOBS**: freeze, unkillable (hp kept at 1 or more), passive (never targets).
- **ME**: god, no cooldowns, free mana, speed x0.5-x4, boons by level.
- **BRUSH**: a unit chip arms it, single/pack/swarm picks the encounter, a middle click places it.
- **ENCOUNTERS**: the newest 8, with clear time, hp taken and deaths.
- The toggles, golem settings, tab and dock survive a level change (town save).

## Golem tab

- F4 (by default) walls a room in (barracks wall pieces) where you stand and spawns the golem north of
  you; other enemies near it are culled. F4 again takes the walls down and you back. Profile (dummies, guard elites, knight), NG+, hp pool, debuffs and how
  often they are re-applied.
- A pull starts on the first hit and ends 4 s after the last: dps, hits, time to kill and a
  per-skill breakdown with an unattributed row, logged as `golem-pull {...}`.
- Golem damage counts toward the game's stats and accomplishments. Use a dev save.

## Bench tab

- **SETUP**: vs versions (A/B) or loadouts (two ticked on the Loadout tab), the driver (bot:
  the rotation; me: you play and it records; replay: the recording), A+B / A / B, pulls per
  variant and seconds per pull. The golem itself is set on the Golem tab.
- **ROTATION**: priority rules, top first; `main` is held as filler. `+ rule`, `default`.
- **Start bench** runs the pulls interleaved A B A B, with cooldowns, mana and the golem reset
  before each. Any input that is not the driver's aborts it (Abort too).
- **RESULT**: per variant the mean dps with its spread, the 95% interval and the n that pins
  it to 3%; B vs A is a Welch t-test (`B better`, `B worse`, `no difference`).
  **Keep B>A** makes B the champion, **Discard B** drops it, **Promote** logs the result for
  `tools/devarena/bench.py promote`. **HISTORY** keeps earlier benches.
- **PENDING** (only while one waits): an auto-tuner proposal with its bench evidence.
  **Accept (B>A)** keeps it, **Discard** drops it. Nothing is kept until you press one.
- Every pull and result is a log line; `tools/devarena/bench.py` turns them into CSV.

## Compose tab

- Pick a spell slot, a start (projectile or another template), then what it shoots, ON CAST
  snippets (fan, burst, ...), ON HIT explosions, the damage type, a status and a name. CAST
  overrides castpoint, cooldown, mana and damage (empty = the start's value).
- **CHECK** lists what is missing; **PREVIEW** shows the slot's new base dict. **Apply**
  makes a version in B like any tuner edit; **Revert slot** puts the vanilla skill back.
- The catalog is generated: `python tools/devarena/make_compose.py [--check]`.

## Relaunch

A REFS edit (or anything else the engine only reads at load) marks the footer `needs
relaunch` with a **Relaunch** button. It saves, logs the session (preset, tab, dock, level, mission,
floor, seed, NG+, position; Relaunch.as) while A/B and the golem ride the override file and the save, and a GameLab run with a `relaunch` step syncs the override file,
quits and boots again; the mod re-enters the same floor and seed and puts everything back.
In `devarena/arena` (watch) there is no runner step to do the reboot: close the game, run
`python tools/devarena/overrides.py sync --log gamelab/results/<run>/logs/pass1.HWR2.exe.log`
and launch again. The tuner versions come back; the floor and position do not (the run starts
from the fixture). Empty the override file again before committing.

## Auto-tuner

```
{"do": "bot", "bot": "devarena_autotune",
 "kwargs": {"fields": ["ran_mark:binds.proj-dmg"], "target": "+15%", "muls": [1.25, 4]}}
python tools/devarena/autotune.py --run gamelab/results/<run>   # docs/devarena/proposals/<run>.md
```

It searches 1-3 numeric fields for the smallest change that meets a dps target against A,
using the Bench tab's own benches, and files the hit as a PENDING proposal. Feel fields
(castpoint, timeline, cooldown, move speed, blocking, animation) are refused unless unlocked
by name. Scenario: `devarena/hp7-autotune`.

## Files

| File | What |
|---|---|
| `scripts/HWP/DevArena/Dock.as` | immediate-mode UI, hotkeys, text entry |
| `scripts/HWP/DevArena/TuneTab.as` | the Tune tab |
| `scripts/HWP/DevArena/Tuner.as` | versions, A/B, deferred apply (`Commit`, `Flush`) |
| `scripts/HWP/DevArena/Patch.as` | copy-on-write patches of a skill's level params |
| `scripts/HWP/DevArena/Curve.as` | level curves (same math as `tools/devarena/curve.py`) |
| `scripts/HWP/DevArena/Overrides.as` | override file at boot; one override log line per change |
| `scripts/HWP/DevArena/Loadout.as` | presets at boot, apply in place, read back, sheet edits |
| `scripts/HWP/DevArena/LoadoutTab.as` | the Loadout tab |
| `scripts/HWP/DevArena/Freeze.as` | Arena: freeze the mobs (three locks) |
| `scripts/HWP/DevArena/Arena.as` | the Arena tab: floor, cheats, brush, encounters, F3/F4/F6/Esc |
| `scripts/HWP/DevArena/Golem.as` | the golem room and pulls |
| `scripts/HWP/DevArena/ArenaSave.as` | Arena and Golem state through the town save |
| `scripts/HWP/DevArena/Bench.as` | the Bench tab: A/B pulls, drivers, stats, CSV lines |
| `scripts/HWP/DevArena/Proposal.as` | auto-tuner proposals: PENDING, Accept / Discard |
| `scripts/HWP/DevArena/Compose.as`, `ComposeTab.as` | composed skills and the Compose tab |
| `scripts/HWP/DevArena/Relaunch.as` | [Relaunch]: save the session, restore it at boot |
| `scripts/HWP/DevArena/Ship.as` | `da-ship`: a spec class as the game parsed it |
| `scripts/HWP/DevArena/Verbs.as` | read-only `da-*` probes and setup verbs (`docs/generated/verbs.md`) |

## Keep a session / ship it

```
python tools/devarena/overrides.py sync [--follow]   # log -> tweak/hwp/devarena_overrides.sval
python tools/devarena/export.py --version live [--dry-run]   # one version -> the mods' own skill files (vanilla refused)
python tools/make_presets.py [--check]                # presets -> tweak/hwp/devarena_presets.sval
python tools/make_presets.py --import-log LOG         # saved variants + favorites -> presets_hand.json
python tools/devarena/clone_spec.py --from ranger_nature --id ranger_test --name "Test Warden" --log LOG --version N
                                                      # a tuned or composed spec -> mods/spec-<id>/
python tools/devarena/ship_check.py --run gamelab/results/<hp6-ship run>   # docs/devarena/ship/<id>.md
python tools/devarena/tooltip_lint.py                 # tooltips the override/export edits left stale
```

Commit the override file empty (vanilla). `tests/test_devarena_tools.py` checks for that.

## Test

- `python -m gamelab run devarena/acceptance --mode lab`: the Definition of done, one run.
- `python -m gamelab run devarena/res --mode lab`: every tab shot at 1920x1080 and 2560x1440 (`gl da-res` sets the size in session and never saves it to the profile).
- `python -m gamelab run devarena/hp1-feel --mode lab` ... `hp7-autotune`: the happy paths.
- `python -m gamelab run devarena/bench-baseline --mode lab`, then
  `python tools/devarena/bench.py baseline --log <run>/logs/pass1.HWR2.exe.log`.
- `python -m gamelab run devarena/tuner-dock --mode lab`: the Tune tab as a player uses it.
- `python -m gamelab run devarena/loadout-all --mode lab`: every preset applied and read back.
- `python -m gamelab run devarena/loadout-dock --mode lab`: the Loadout tab as a player uses it.
- `python -m gamelab run devarena/arena-dock --mode lab`: the Arena tab, brush, F3/F6/Esc, Reload.
- `python -m gamelab run devarena/golem-room --mode lab`: F4, a pull, the golem chips.
- `python tools/devarena/run_export_boot.py`: the override file and the export, read back at
  boot. It writes both input files and restores them afterwards.
