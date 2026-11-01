# Installing

No releases are published yet; until then the repo builds and installs everything for you:

`tools/run.py` is the single entry point for agents: `/run` makes one call and the
script handles setup through main-menu readiness. `run.cmd` wraps it for double-click use.

1. Double-click `run.cmd` (or ask an agent for `/run`, or `python tools/run.py`). It sets the
   machine up, builds every module (with your own HoH1 content when Heroes of Hammerwatch 1
   is installed), copies the `.bin` files into your Steam install's `mods/` folder and starts
   the game through Steam. First, a small **save builder** lets you add named characters
   with a class and level (1–20), and configure **Starting gold** (default **1,000,000**
   shared by the new profile), then **Build save & launch**. **No preset characters**
   keeps the chosen gold and lets you create characters in game; choose 0 gold for
   a completely fresh start.
   Cancelling leaves setup, deployment and profiles unchanged.
   **Each run creates a new local profile**, enables the deployed
   mods and makes it the default. Existing characters stay in their existing profiles;
   saves and config are backed up first. Use `--profile-name "Name"` to name the new profile.
2. Choose your prepared character, or create one if you started empty. Prepared characters
   have normal starting gear and their earned skill/attribute points unspent. The game
   prepares characters and gold in an isolated GameLab session first; this may take a few
   minutes. Resource Mods is already configured;
   no ticking or restart is needed. `--no-launch` prepares the profile without starting the
   game; `--dry-run` only shows the plan. Builds use the current local checkout, without a
   Git pull. Everyone in a lobby needs matching mods.
3. In game, open the console (the key left of 1) and type `hwp help` for the commands and settings.

For a direct level-15 Sorcerer without the UI:

```powershell
.venv\Scripts\python.exe tools\run.py --character sorc:15:TestSorc --gold 1000000
```

Repeat `--character CLASS:LEVEL:NAME` for more characters; names have no spaces.
`--gold AMOUNT` configures starting gold without the UI, including 0. `--no-ui`
starts without preset characters, retaining the chosen gold (1,000,000 by default).
Class choices follow the selected packages.
The launcher and GameLab coordinate runtime ownership; an open play session blocks
native lab runs until the game is closed.
Launcher, lab and documentation edits leave the multiplayer build label unchanged;
`+` marks changes to shipped mod inputs, including package/module metadata.

Subscribed to HammerwatchPlus on the Steam Workshop as well? `/run` deploys a separate
`-local` mod ID when a Workshop copy would shadow the build, and enables that local ID in
the new profile. Subscriptions stay unchanged. A plain `deploy.py modded-prod` keeps the
release IDs; pass `--avoid-workshop` for the same collision handling.

Without Heroes of Hammerwatch 1 every module still works: the campaign runs on HoH2 tiles,
the HoH1 classes and trinkets show placeholder icons and the HoH1 pets stay out of the Pet
Shop, and the game says so once in chat (`hwp hoh1` lists them). If `run` asks
where HoH1 is, answer with `python -m gamelab doctor --hoh1 "<folder>"` (or `--no-hoh1`) once.
Sharing the packages by hand still works: `dist/HWP-<package>.bin` (or
`HammerwatchPlus-All.bin`) into `<Steam>/steamapps/common/Heroes of Hammerwatch 2/mods/`.
`python tools/build.py` makes every package and the all-in-one pack without your local
content. `python tools/workshop.py` turns them into a Workshop upload kit (`dist/workshop/`:
each item's .bin, preview image, title, description and change note); the upload itself is
done by hand in the game's `PACKAGER.exe` > Steam Workshop manager, as
[docs/WORKSHOP.md](WORKSHOP.md) describes.
