# When the game updates

A Heroes of Hammerwatch II patch can break HammerwatchPlus scripts in two ways. These
measurements come from GameLab on Build 176 (docs/RE_NOTES.md, "Script errors and game
updates").

| what breaks | what the player sees | what protects them |
|---|---|---|
| **A compile error.** A mod calls a function, class or member the patch renamed or removed. | Nothing compiles, not even the base scripts. The game stops on an empty main menu and ignores the window's close button. The log has `ERR : <file>` and `Please correct the errors in the script and try again.` | No script can catch this. The only protection is to find it before players do (the checklist below), and to touch as little of the base game as possible. |
| **A runtime error.** A call the patch changed now throws (a null where there used to be a unit, an index out of range). | Without a guard: the game mode's frame update stops after the module loop on every frame. That loses screen shake, pings, spectating and the death check (no DeadMenu). | Every HWP module entry point runs inside `HWP::Guard` (`mods/hwplib/scripts/HWP/Core/Guard.as`). The error is logged with a stack trace, the rest of the frame runs, and after 30 errors in a row the module's entry point turns off until the next level, with one chat line. `hwp guard` lists what failed. |

Errors elsewhere are already contained by the engine:

- **A `[Hook]` that throws** only loses that hook's call; the other hooks and modules run.
- **A module constructor that throws:** the engine logs `Script exception`, skips that one module, and makes the others.
- **A module's `Save` that throws** is caught by the game mode.

When the scripts compile on a build they were not tested on, hwplib tells the player once
per build. It compares `Network::GetBuildVersion()` with `HWP::Guards::TESTED_BUILD` in
`mods/hwplib/scripts/HWP/Core/Guard.as`.

## Checklist after a patch

1. **Look at the pin.** `python tools/pin_build.py --show` exits 3 when the installed build is not the pinned one, and GameLab refuses to run until it matches.
2. **Re-dump the game.** Copy `gamecode/` aside, then run `python tools/bootstrap.py --force`. Diffing the two dumps lists what the patch touched; `docs/updates/` keeps one such list per patch. `tools/build_diff.py` exists only on the unmerged snapshot commit 6ee00a1.
3. **Check the overrides.** Run `python tools/build.py --check`. It names every wholesale override (a `.orig` next to the file) whose base file changed. Merge the game's change into our copy, then refresh the `.orig`. These 33 files are the most fragile part of HammerwatchPlus, because a patch to one is silently undone by our copy:

   | files | mods |
   |---|---|
   | 9 | hwplib |
   | 4 | architect |
   | 3 | holylocal |
   | 2 each | tavern, hwplib-luck, firearms, droptrade, campaign |
   | 1 each | stash, specs, puzzles, keys, hwplib-classui, goldworth, farming |

4. **Compile everything.** `python -m gamelab run mod-all --mode lab` boots every mod. A compile error fails the boot, and the run's log names the file and line.
5. **Run each package as it ships.** Run every `gamelab/scenarios/pkg-*.json`, and the suites of the mods whose code the patch touched.
6. **Re-pin.** Run `python tools/pin_build.py --reason "<patch>"`, then set `HWP::Guards::TESTED_BUILD` to the new build number. `tests/test_guard.py` fails until the two agree.

## Writing code that survives a patch

- **Prefer hooks, modules and class swaps to wholesale overrides** (docs/modules.md, rule 1). A hook calls the game's current code; an override freezes a copy of it.
- **New module entry points get a guard.** Run `python tools/guard_modules.py`; `tests/test_guard.py` fails while one is missing.
- **Check what the game hands back.** `Resources::GetUnitProducer`, `Item::Get`, `Equipment::BaseItem::Get` and friends return null when a patch renames a resource. `HWP::CheckUnits` and its siblings in `Log.as` log every missing one at boot.
- **Don't catch and hide errors in gameplay code.** A caught exception is silent: `getExceptionInfo` is not registered, so the script can't read the message. Let the guard log it.
