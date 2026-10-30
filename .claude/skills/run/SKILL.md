---
name: run
description: Set up, rebuild and deploy HammerwatchPlus, create a fresh local profile with every deployed mod enabled, make it the default, and launch the real Heroes of Hammerwatch II install through Steam for the user to play. Use for /run, running the game with the latest mods, or a fresh all-mods profile. Use GameLab instead for tests.
---

# run

From the repository root, make **one call**:

```powershell
.venv\Scripts\python.exe tools\run.py
```

If the project environment does not exist yet, use `uv run python tools\run.py`
instead. `run.cmd` is the double-click entry point to the same script.

The default call opens a small desktop save builder. The user can add several named
characters, choose classes and levels 1–20, configure **Starting gold** (default
**1,000,000**, shared by the new profile), and click **Build save & launch**, or
choose **No preset characters** while keeping the chosen gold. Set gold to 0 for
an unfunded profile. Closing/cancelling makes no setup, deploy or profile changes.
Let the user operate this UI; do not automate it or ask them to run commands.

`tools/run.py` owns the entire workflow: the builder, runtime guards, doctor/setup, current-source
build with available HoH1 imports, deploy with Workshop collision handling, save/config
backups, isolated native character preparation when requested, a new local profile with all deployed mods enabled, default selection, Steam
launch, and waiting for the main menu with the deployed pack loaded. Do not run these
steps separately or add a preliminary doctor/build/deploy call on a normal `/run`.

The request authorizes this real play workflow. Every invocation creates a fresh
profile; existing profile files are preserved. "Latest" means the current checkout,
without automatically pulling Git changes. Prepared characters have normal starting
gear and their earned skill/attribute points unspent. The builder does not grant NG+.

Pass optional user preferences through to the same call:

- `--profile-name "Name"`: name the new profile.
- `--character sorc:15:TestSorc`: prepare a level-15 Sorcerer and bypass the UI;
  repeat for multiple characters. Canonical class IDs also work. Names have no spaces.
- `--no-ui`: bypass the builder without preset characters, unless `--character`
  is supplied; the chosen starting gold still applies.
- `--gold 2500000`: starting gold for the new profile; default 1,000,000.
  Applies with or without preset characters; `--gold 0` starts unfunded.
- `--packages town keys`: selected packages instead of all; never combine `all` with them.
- `--no-launch`: prepare mods and the new default profile without starting the game.
- `--dry-run`: show the plan without writes or a launch.

Character preparation uses `python -m gamelab run <generated-request.json> --mode lab`
internally and checks verdict, assertions, error, teardown, source fingerprints and
the persisted roster and exact gold balance before importing the save into a new play slot. Native fixture
creation and levelups generate the records; the lab-only save-write guard stays intact.
This may take a few minutes. A failed preparation never selects a new real profile.

Read the script's `run:` output. Report the selected profile, prepared characters, starting gold, enabled pack and menu
readiness; no Resource Mods ticking or restart is needed. `run: backup:` identifies
the config backup and receipt. Exit 1 means launch/compile/menu readiness failed,
2 means setup/profile/lock refusal, and 3 means a game is already running. Other
nonzero codes can propagate from a failed child step; report that step's cause.

Only investigate separately when the script fails or requests missing information.
Respect save/HoH1 decisions, runtime locks and dirty teardown; never reset another
owner's run, weaken `gamelab/hps.py`'s write guard, re-pin builds as a routine fix,
or launch the real executable directly. See the [quickstart](../../../gamelab/README.md)
for recovery. For tests, use GameLab with `--mode lab`; a play launch is not a
gameplay regression pass.
