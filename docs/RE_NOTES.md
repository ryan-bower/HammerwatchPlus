# RE notes: Heroes of Hammerwatch II

Dated findings log. Each entry says how it was measured; "assumed" marks anything not yet
measured. Newest entries at the bottom of each date.

NOTE: PATHS/ENV SPECIFIC NOTES ONLY APPLY TO A SINGLE DEVELOPERS SETUP, OTHER DEVS MAY HAVE
DIFFERENT SETUPS OR INSTALL LOCATIONS.

## 2026-10-17: recon (P1)

**Install.** `C:\Program Files (x86)\Steam\steamapps\common\Heroes of Hammerwatch 2`
(found through the Steam registry key and `libraryfolders.vdf`; `tools/gamepaths.py`).

**Ids and version.** Steam app id `619820`. Build id `25509441`
(`steamapps/appmanifest_619820.acf::buildid`). The game logs
`Build 170: ARCH_64 USING_STEAM RELEASE FINAL` as its second line (`HWR2.exe.log`), and the
window title is `Heroes of Hammerwatch II - B170`. `HWR2.exe` sha256 `6ddd9e7d8fe3â€¦`,
PE timestamp 1790265044. Pinned in `gamelab/build_id.json`; `tools/pin_build.py --show`
compares live to pin, and every GameLab launch refuses with exit 3 on mismatch.

**Engine.** Crackshell's own C++ engine: `HWR2.exe`, `PACKAGER.exe`, `EDITOR.exe`,
`HWR2Toolkit.exe`, all game content in `res/assets.bin`, AngelScript game scripts inside the
archive (extracted to `gamecode/sdk/hoh2/scripts/`). Libraries by file version: SDL2
2.30.7, FMOD / FMOD Studio 2.2.11 (build 130436), steam_api64 1.0.0.1, ozz-animation,
libde265, TinyTIFF. Renderer from the log: `Starting BGFX renderer OpenGL 3.2`.

**Anti-cheat.** None. No `EasyAntiCheat/`, `BattlEye/` or other anti-cheat directory or
launcher wrapper in the install; the only third-party runtime is `steam_api64.dll`.
Consequence: in-process DLL injection is usable (GameLab injects
`tools/bin/hwr2_capture.dll`, below), and scripted mods are the game's own supported path.

**Logs.** `<exe dir>/HWR2.exe.log`, rotated into `<exe dir>/logs/HWR2.exe_<date>_<time>.log`
at the next start. Crash dumps: `<exe dir>/HWR2_<build>_crash_<date>_T<time>__<n>.mdmp`.
Script `print()` goes to the same log.

## 2026-10-17: isolation (P6 item 9)

All measured with copies of the game run from a scratch directory, the user's saves backed
up first (`tools/saves.py backup`) and compared after every run.

- **The exe's directory is the user-data root.** HWR2.exe reads `HWR2.exe.cfg`, writes
  `HWR2.exe.log`, and keeps local saves in `saves/` next to the exe it was started from,
  not the working directory and not the install. A copy of `HWR2.exe` and its DLLs in
  another directory, with the install's `res/` linked in, runs as a fully separate
  install. The log line `Launch options: 1: <exe path>` names the exe that ran.
  First probe, launched from the install exe with a different cwd: it read the install's
  cfg and overwrote the install's `HWR2.exe.log` (no save writes, checked by mtime).
- **Launching the exe directly does not relaunch through Steam.** The game stays a direct
  child of the launcher (Steam already running), so the hidden desktop and job object reach it.
- **`g_save_slot_cloud 0`** keeps saves off Steam Remote Storage. The real cloud saves are
  `Steam\userdata\<account>\619820\remote\saves\`.
- **Save backups leak to the user's profile.** On each save the game also writes
  `%LOCALAPPDATA%\HeroesofHammerwatch2\save_backups\slot_<n>_<date>.hps` (throttled: not on
  every save). It resolves the folder with `shell32!SHGetKnownFolderPath`
  (FOLDERID_LocalAppData), not the `LOCALAPPDATA` environment variable: the exe imports
  `SHGetKnownFolderPath` and contains no `LOCALAPPDATA` string, and a run with
  `LOCALAPPDATA` overridden still wrote to the real folder. One probe file leaked there:
  `slot_7_2026_10_17_T05_58_31.hps` (a lab profile, never the user's data; the user
  decides whether to delete it). Fix: `hwr2_capture.dll` replaces the exe's
  `SHGetKnownFolderPath` import and answers FOLDERID_LocalAppData with
  `GAMELAB_LOCALAPPDATA`. The exe starts suspended, the DLL is injected through
  `CreateRemoteThread(LoadLibraryW)`, and then the process resumes (`NtResumeProcess`).
  Verified: the backup then landed in `<game dir>/appdata/HeroesofHammerwatch2/save_backups/`
  and the real folder was unchanged.
- **`res/controls.cfg` is written into `res/`.** The exe has `res/controls.cfg` and
  `res/controls_default.cfg` strings and a "Saved controls config" message; the log shows
  `Loading control bindings from 'res/controls_default.cfg'`. The install has no
  `controls.cfg`, so nothing has been written there yet. Because a junctioned `res/`
  would carry that write into the install, the GameLab `res/` is a real directory:
  `assets.bin` is hard-linked (`os.path.samefile`), small files are sha256-verified
  copies, and subdirectories are junctions. Every run asserts the install's `res/` is
  unchanged.
- **Workshop subscriptions are still listed** in GameLab runs (`Workshop: Subscribed
  items: 1`, `Resource mod: drop_me.bin`). They are listed but never enabled: mods are
  enabled per save, and the GameLab profile enables exactly the GameLab set (asserted by
  the `mods` probe every run).

## 2026-10-17: windows, input, capture (P3 topology, P6 items 2 and 8)

- **Window topology.** One visible top-level `SDL_app` window titled
  `Heroes of Hammerwatch II - B170`, plus `__wglDummyWindowFodder` and IME windows.
  `v_fullscreen false` opens it windowed at the configured size.
- **`v_resolution` is `WxH`** (`GUI/Options/ResolutionsWindow.as`). `v_resolution 800 450`
  crashed the game with 0xC0000005; `640x360` works (GameLab lab profile).
- **Focus-free input works.** `PostMessage` of `WM_KEYDOWN`/`WM_KEYUP` to the `SDL_app`
  window on a hidden desktop:
  - **Enter** at the main menu starts Singleplayer/Continue;
  - **VK 0xC0** opens the console, `WM_CHAR` types into it, and Enter runs the line (the log echoes `> <line>`);
  - **F** (the default `Use` binding, `res/controls_default.cfg`) opens a chest.

  All of it also works with the window minimized (`ShowWindow(SW_SHOWMINNOACTIVE)`):
  scenario `open-chest-minimized` passed. The real foreground window was sampled every
  50 ms through every run and never changed.
- **PrintWindow returns a blank image** for the OpenGL window on a hidden desktop (no
  compositor). Frame capture is in-process instead: `hwr2_capture.dll` replaces the exe's
  `gdi32!SwapBuffers` import, and on a request file reads `GL_BACK` with `glReadPixels`
  just before the swap (`tools/capture_shim/hwr2_capture.c`). It produced correct 640x360
  and 1024x768 frames.
- ~~Mods do not run in the main menu.~~ **Corrected the same day, see "mod lifecycle"
  below.** Mod modules are constructed at the menu, but nothing ticks there. The front door
  (main menu to session) is still the Enter key, and everything after it goes through the
  `gl` console command.

## 2026-10-17: saves and mods (P6 item 3)

- **`HashString` is MurmurHash3_x86_32, seed `0xf808409c`.** It was read from HWR2.exe build
  25509441 as follows:
  1. The script declaration `uint HashString(const string &in str)` is registered next to a
     function pointer `0x1401b4560`.
  2. That native gets the string and calls `0x1400176f0`.
  3. `0x1400176f0` is the MurmurHash3 x86_32 body with `r8d = 0xf808409c` as the seed
     (`C:\tmp\claude\re\find_hashstring.py` and `disasm_at.py` were the scratch scripts).

  Checked against 57 mod-id/hash pairs the game printed: 57/57. `gamelab/hps.py hash <id>`
  computes it.
- **Mods are enabled per save.** The save header holds a list of `HashString(mod id)`
  (`gamelab/hps.py` documents the layout). The id of an unpacked mod is its folder name:
  the log shows `Adding unpacked mod 'gamelab-probe'`, and `PersistentSaves::IsModEnabled`
  is true after enabling that hash.
- **A graceful quit saves.** `WM_CLOSE` to the game window writes the profile
  (`Saving persistent data for profile <n> to file 'saves/<n>.hps'`) and the process exits 0.
  A brand-new profile after a null-save session is 1714 bytes, version 3, no characters.

## 2026-10-17: script API facts used by GameLab

- **Console commands from a module:** `AddFunction("gl", { cvar_type::String }, fn, 0, help)`.
  A one-string function receives the rest of the line.
- **Materials:** `PlayerRecord.GetMaterial(type)` reads the **town's** store
  (`g_myTownRecord`) while in town, and the character's own `materials[]` on a mission
  (`Behaviors/Actors/Player/PlayerRecord.as` `GiveMaterial`/`GetMaterial`). A probe
  reading `record.materials[]` in town sees zeros after looting (measured, open-chest run 1).
- **No generic reflective getter:** `Reflect::` has types, properties and
  `PropertyInfo.Set`, but no way to read an arbitrary property's value. The inspector must
  be code-generated from the class sources (P6, open).
- **Loot table `cache_wood` does not exist** in this build (`items/chests/cache_wood.unit`
  names it; no `tweak/loot/*.sval` defines it). GameLab uses `cache_bronze`.

## 2026-10-17: mod lifecycle (correction) and town saves

- **When mod code runs.** Measured on run `20261017-063419-mod-core-lab`, with a profile
  that enables `core` and the GameLab mods.
  - The engine logs `Adding unpacked mod '<id>'` at boot and again at `StartLoadMenu
    levels/town.lvl`. The main menu is the town level.
  - The module constructors run while the menu level loads (`Making Module ...`). The probe's
    `boot` event and `[HWP:core] module created` were both logged before `Started menu level`.
  - `UpdateFrame` ticks only once the gameplay session starts. The probe's first heartbeat
    follows `Starting session` (after the posted Enter).
  - An earlier note said mods do not run in the menu. That came from a profile with no mods
    enabled, and it is wrong: constructors run there, frames do not.
- **A fresh character's town has no save data.** On the `town-paladin` fixture the session
  logs `Started with null save`. `TownRecord.Load` returns before `Hooks::Call("TownRecordLoad")`
  when the save is null (`gamecode/sdk/hoh2/scripts/Town/TownRecord.as`). So core's
  `town record loaded` line cannot appear on that fixture. Assumed: it appears once a town
  save exists (after a run or a town save point); not measured yet.

- **`Modules::Module.Load` is gated on a session save.** `AGameplayGameMode.Start` calls
  `m_modules[i].Load(modData, sMode)` only when the session save is non-null and holds a
  dictionary under that module's `m_id` (`gamecode/sdk/hoh2/scripts/GameModes/AGameplayGameMode.as`,
  lines 143-154). A fresh town session logs `Started with null save`, so `Load` never runs.
  Consequence measured on `mod-campaign` (run `20261017-064110-mod-campaign-lab`):
  `mods/campaign` runs its self-check from `Load`, so on a fresh town it never logs
  `self-check done`. The same holds for any HWP self-check placed in `Load`.

## 2026-10-17: mod load checks (`gamelab/scenarios/mod-<id>.json`)

These replace `dev_check`. Each one boots one mod plus its `requires` on the
`town-paladin` fixture and asserts:
- the self-check lines its README names;
- still in town;
- no script errors in our files (`gamelab/logparse.py`).

The checks were validated against a deliberately broken mod: the run fails and names
`Broken.as:5:11 No matching symbol`.

- **PASS (20 of 26):** abyss, architect, bufftips, chatlinks, classes, colors, core, deathrecap,
  droptrade, farming, firearms, fishing, goldpet, groupcombo, keys, legacy, pets,
  strongbox, summons, weaponswap. The keys README named `Making Module hwp-keys`; the
  engine logs `Making Module HWPKeysModule`. README and scenario are fixed.
- **FAIL, self-check never fires on a fresh town (verified gate, see above):**
  - campaign, maps, weapons and wavemode run their self-check from `Module.Load`.
  - None of the 24 scenarios logged a script error. These four mods may well be fine,
    but they cannot report it on this fixture.
  - Fix options, the user's call: move the checks to the constructor, or add a fixture
    with a saved session.
- **FAIL, fixture content:** gambler spawns only when the town has a tavern
  (`GetVariationOnBuilding(HashString("tavern")) >= 0`). Assumed: the fresh fixture town
  has none, and that branch returns without a log line.
- **FAIL, unexplained:** laststats. `SpawnBoard` logs `spawned the notice board` 500 ms of
  frames after start when `g_inTown && Network::IsServer()`, and the line never appeared.
  Not diagnosed. Next step: probe `g_inTown` per heartbeat from tick one, rather than
  guess. Candidate: the first frames tick on `PickCharacterWindow` before town is set up.

## 2026-10-17: the Pilot, the pathfinder, the console channel

Verified means measured on the pinned build (run id or source line). Assumed is labelled.

**Input and the run loop**
- **The engine hands out more than one `GameInput`.** Measured `buffers: 2` with the
  `controller` verb. A hold written into one object kept moving the player whenever the
  other became current again (hands-release 20261017-150922..151323). gamelab-hands writes
  every object it has seen (`mods/gamelab-hands/scripts/GameLab/Input.as:55-60`).
- **The next floor is preloaded in its own script context, which constructs every mod
  module again.** Those log lines carry `[preload]` (pilot-consumables 20261017-152746),
  and `session.py` tags them so a preload `boot` is not read as the level change.
- **The game steps a fixed ~33 ms of scene time per frame, at ~30 frames a second in the
  lab box** (timescale 20261017-175222: 3663 scene ms over 111 frames), although
  `v_fps_limit` is 60.
- **`g_timescale` only changes with `e_cheats` on**, which the engine allows in modded
  games (timescale 20261017-175329: 4x gave 14.8 s of scene time in 3.7 s).
  - It is not a test accelerator. At 4x, game-ms timers ran 4x but the player moved no
    farther per frame (0.6-3.6 units, against ~3.2 at 1x): the exit intent timed out four
    times (floor-soak 20261017-175501).
  - The `timescale` verb stays, labelled measurement-only.
- **Setting `CVars::ChtGodmode` from a mod did not stop damage** (20261017-155134).
  Cause not diagnosed. Assumed: the mod's `CVars` namespace is a separate copy of the
  game's.

**Character facts used by the fixtures**
- **The level cap is 20**, reached at 1301032 xp (fixture-ranger 20261017-163304 reads
  back level 20).
- **Enemies scale with NG+ only, not with player level**
  (`Behaviors/Actors/Enemies/CompositeActorBehavior.as:335-337, 718-719`).
- **Potion charges come from the apothecary's `potion-charges` upgrade.** Steps 0-4 take
  the player from 1 charge to 5 (`Town/UpgradeShop.as:139-150`; fixture readback
  `potionCharges 5`).
- **`RollQuality` never rolls a quality on a mask without the Common bit.** It tests
  `mask & Common != 0`, which binds as `mask & (Common != 0)`
  (`EquipmentGenerator.as:15`). Measured: rare asked, quality 2 given
  (fixture-ranger 20261017-151727).
- **A refused `Equip` returns the item itself** (`MayEquip`: level or attribute
  requirements). The `equip` verb treats that as failure.

**Exits**
- **`LevelExitAreaNext` triggers only for a player inside one of its `Areas`.** Each area
  is a sensor (`:Physics_Circle`) offset from the exit unit. Measured offsets:
  - (-72,-120) on one exit (exit-areas 20261017-162406, -162451);
  - (+134,-74) on another (exit-probe 20261017-170654).

  So the offset depends on the exit's orientation. The unit's own position is not
  walkable. Standing in the sensor makes the exit the top usable, and Use loads the next
  floor.
- **Every floor sampled had exactly one enabled exit**, plus one disabled one
  (exit-probe 20261017-170654, -170727).

**The engine pathfinder (`g_scene.Pathfind`), synchronous**
- **No per-frame budget.** 2000 identical calls in one frame all answered, also after
  2000 failing far calls in the same frame (pathfind-budget 20261017-170150).
- **The diameter argument (0, 4, 8, 12, 24) changed no answer** (pathfind-budget
  20261017-170356). Neither did maxDistance or maxRange (pathfind-probe 20261017-153815).
- **Answers are geometric.** A target inside trees or water fails at any distance. A long
  route can fail although both of its halves answer (pathfind-probe 20261017-153509).
  The Pilot's `NavRoute` (A* over short Pathfind legs) covers that case.
- **The Pilot's planner routes from every physically free point it samples.** Measured
  on four layouts (route-sweep 20261017-180034, -180109, -180142, -180225). Points that
  overlap a solid body are skipped, since a player cannot stand there; unit-0 hits are
  level collision without a unit.
- **Two planner bugs were found and fixed:**
  - The search grid was too small for a 6850-unit spawn-to-exit distance
    (pilot-crosslevel 20261017-171409).
  - A player on a pond bank sat in a nav pocket (3 expansions), and stepped out of it
    (pilot-crosslevel 20261017-171446).
- **Mid-floor routing can fail after fights where it worked from the spawn.** In
  pilot-crosslevel 20261017-172902, spawn -> exit no longer routed and neither did
  here -> spawn. The same layout's answers held steady when idle for 30 s and after
  cull (nav-drift 20261017-173940).
  - Assumed cause: units standing in passages. Not verified.
  - Seen again in floor-soak 20261017-184334 sample 1. At (2042,617), 200 units south of
    the exit's stand point, nothing routed:
    - stand â†’ anywhere: 3 expansions;
    - spawn â†’ stand: failed;
    - here â†’ spawn: failed, along the way the player had just walked.
    No enemy was within kite range.
  - **What can change the graph (verified from data, not yet tied to a run):** a unit's
    `<collision static="true">` blocks nav unless it says `nav-block="false"`. In the
    hoh2 units, 1408 static collisions carry no nav-block attribute, 18 say false and 2
    say true. The exe also has a `dirty_nav_graph` string (`hwr2_api_strings.txt`).
  - Assumed: static-collision units that spawn or die mid-floor rebuild the graph. Not
    yet measured; floor_runner now records the units near the cut and waits 5 s
    between retries, to tell a pending rebuild from a lasting blocker.
  - The exit intent now walks to the reached point nearest the exit and plans again
    (partial routes).

**The console channel**
- **Every gl line goes through the console: open, type, Enter, close.**
  - The console key is read per frame. Opening, typing and closing inside one frame does
    nothing at all (console-bench 20261017-181238).
  - The console also slides shut over more than 70 ms (console-trace 20261017-183130).
    An opening key during the slide is lost: every second line vanished at 70 ms
    (console-bench 20261017-182614), none of 90 at 150 ms (-183226).
- **Timing now used:** two frames after opening and after Enter, and 150 ms before the
  next opening. That is 291 ms per line, against 770 ms with the old fixed sleeps.
- **The faster timing put the console into the screenshots.** The blind observer of
  open-chest 20261017-190827 read a console panel over the top fifth of `end.png`, which
  no probe reports.
  - Measured on top-band luminance: about 25 in every shot of that run, against 73-77 in
    the older runs (20261017-140030, -064949).
  - Two plain town frames 0.5 s apart "differed by 31%" in watch-overlays 20261017-190809
    for the same reason. That was the console, not the scene.
  - Fix: `Session.shot` waits 0.25 s after the last console close.
    - console-slide 20261017-191646: the panel is in a shot taken as the reply arrives
      (top band 26.5) and gone 100 ms later (77.6).
  200 lines, 0 lost (console-bench 20261017-183348).
- **A line typed while a level loads can vanish.** The game echoes every line it runs
  (`> gl <id> ...`), so `gl_cmd` retypes a line that went unechoed for two heartbeats.
  This happened once per mission re-entry and was recovered each time (-183348).
- **One typed line of 1985 characters ran whole** (console-bench 20261017-183645).
  The fixture readback now goes out as one `multi` line: 0.5 s, down from ~15 s.

## 2026-10-17 (evening): breakables, travel, death
- **Breakable debris closes passages.** Verified from source and telemetry:
  - `doodads/terrain/castle_debris_pile_wood_noloot.unit` has a `Breakable` behaviour. Each of its
    scenes has `<collision static="true">` with no `nav-block` opt-out, so it blocks nav.
  - `m_health` defaults to -1 (`Breakable.as:31`): one hit breaks it.
  - floor-soak 20261017-192513 sample 0: every route ended near -125,971. The `bodies` probe
    toward the exit found that debris pile at 0,904. Four 20 s kites and a far-enemy kite later the
    passage was still cut.
  - Change: `TargetGone` counts a live Breakable as a target, so `attack <unit>` smashes it. A new
    read-only verb `breakables [radius]` lists them, and floor_runner attacks the nearest three
    within 250 before kiting.
  - **Assumed, not yet verified:** that the ranger's projectile hits the debris (its circles are
    `aim-through="true"`). The next soak measures it (`retries[].broke`).
- **Idle packs cutting the graph: not supported.** The far-enemy kite killed its target
  (boar, sample 0) and the route stayed cut. Sample 3 of the same run: every far enemy was
  "unreachable (stuck at 290,329)". The beetle-pack hypothesis from floor-soak 20261017-191104
  is unconfirmed; the far kite remains as a fallback.
- **Travel graph.** `learned.json` is written only by `"explore": true` runs. pilot-explore
  20261017-191702 learned forest_1 -> forest_2 (graph 1511afe5 -> 199da2bc). Scenario runs
  report `new_edge` without writing (pilot-crosslevel 20261017-191834). An unknown transition
  is `no_route` in 19 s (20261017-190905).
- **Death.** `DeadMenu`'s MenuAccept (Return) calls `Revive`: ResetPlayerHealthMana, SpawnPlayer,
  AbortMission -> town (decompiled). floor-soak 20261017-192111 stopped with "no mission
  heartbeat" after a death because nothing pressed it. `floor_soak.enter()` now presses Return
  on DeadMenu. Not yet exercised: 192513 had no deaths.
- **Ruled out:** the loot toast missing from end frames. The probe reports two `loot_log`
  announces at the end of open-chest 20261017-192415, and the blind observer saw none. A crop
  shows a faint grey "Got" at the style's anchor (bottom-right, grey 0.5, 11 px). Low contrast,
  not absence.
- **Debris breaking verified** (supersedes "assumed" above). In floor-soak 20261017-193859 the
  ranger broke `castle_debris_pile_wood` and the route moved on (sample 1, 476,-1651 -> 730,-1722).
  The soak passed 3 of 4. Crates and chairs were mostly "unreachable", so debris is now tried
  first and failed units are skipped. pilot-floor 20261017-194552 PASS. The next soak
  (20261017-194740) was interrupted by the user, leaving a stale lock: no process was alive, so
  `gamelab reset`.
- **Mod load checks: 27 of 27 pass** (20261017-194937 â€¦ -195451). The six earlier failures pass
  with their self-check log lines present. Cause not traced.
- **P6b paused** at the user's request (2026-10-17), to be walked through together.

## 2026-10-17 (night): watch-mode focus (P6 items 1 and 1â€²)
- **Who took the foreground in 20261017-195821.** pid 25096 was `HWR2.exe` itself, the
  `harness.start` pid. The empty image name was a sampler bug: it resolved names at
  `report()` time, after the game had exited. `ForegroundSampler` now records at each switch
  the image, window class and title, wall-clock time, the window under the cursor and which
  mouse buttons are down.
- **The game makes no activating call after its window is shown.** HWR2.exe imports none of
  ShowWindow, SetWindowPos, SetForegroundWindow, SetActiveWindow, SetFocus or CreateWindowExW.
  SDL2.dll (2.30.7) imports all of them (`objdump -p`). The shim now hooks them in SDL2.dll's
  import table and logs each call with the foreground before and after.
  - In 20261017-200502 (logging only, old behaviour) SDL made exactly one activating-capable
    call: `ShowWindow(hwnd, SW_SHOW)` 0.5 s after injection. The foreground did not change,
    because this launcher (a non-foreground agent shell) has no foreground rights.
  - The only other call was `ShowWindow(0)` at exit.
  - In 195821 the two switches to the game came 15 ms and 31 ms after real input, at about
    +3 s and +12 s after injection. That is not when SDL's call happens.
  - The game log of 195821 shows the human drove the menu: `MainMenuGameMode::MenuBack` at
    19:58:37 and :45, then `Starting session` at :46. So the foreground went to the game
    through the user's own input to its window or taskbar button. Which input it was is
    inferred, not measured: the sampler did not record the cursor then.
- **Measured once the cursor was recorded: 20261017-200812.** At 20:08:27.323 there was a
  left click on `explorer.exe` (the taskbar) and the foreground went to 0. At 27.579 it became
  the game's `SDL_app`. No hooked call took the foreground. So the shell activated the
  window on a taskbar click, even though the window was already `WS_EX_NOACTIVATE`
  (with `WS_EX_APPWINDOW` added, which gave it a taskbar button).
- **Fix** (`tools/capture_shim/hwr2_capture.c`, `gamelab/session.py`, `gamelab/runner.py`,
  `gamelab/winproc.py`). Watch mode sets `GAMELAB_NO_ACTIVATE=1` for the game.
  - The shim gives SDL's top-level windows `WS_EX_NOACTIVATE`. With no `WS_EX_APPWINDOW`
    they get no taskbar button, so there is nothing for the shell to activate.
  - SDL then shows the window `SW_SHOWNOACTIVATE`: the shim log shows `ShowWindow(..., 4)`,
    where it was 5 before.
  - Whenever another process owns the foreground, the shim rewrites activating
    ShowWindow commands to their NOACTIVATE/NA forms, adds `SWP_NOACTIVATE` to SetWindowPos,
    and refuses SetForegroundWindow and SetActiveWindow. This covers foreground rights
    inherited from a console launch, and SDL raise calls later in the run.
  - At the first frame (the first heartbeat) the runner clears `WS_EX_NOACTIVATE` and adds the
    taskbar button with `ITaskbarList::AddTab`. Nothing is activated or raised
    (`harness.allow_activation`: `ex 0x8000110 -> 0x110`, `taskbar_button: true`).
  - Lab mode is unchanged (`no_activate=0`); the hooks only log there.
- **Runs.**
  - null-payload watch 20261017-201214 and -201234: PASS, zero foreground switches for the
    whole run, first frame at 9.8 s and 9.3 s.
  - null-payload lab 20261017-201253: PASS.
  - open-chest lab 20261017-201305: PASS.
- **Assumed:** a real click on the loading window does not activate it. That is the documented
  `WS_EX_NOACTIVATE` behaviour, untested here because GameLab sends no real input. Also
  assumed: the taskbar button appears after AddTab (it returned S_OK).
- **Posted Enter lost at the main menu.** Seen in 195821 and 200812, the two runs where the
  human was using other windows: no `Starting session` followed it, and 200812 failed
  "never reached phase town". Cause not established; assumed to be long frames while the
  window is occluded. `Runner.boot` now waits up to 5 s for `] Starting session` and re-sends
  Enter up to 3 times (`harness.enter_lost`). The retry has not fired in a run yet.

## 2026-10-17 (night): fresh-clone readiness (`python -m gamelab doctor`)

- **No managed code to decompile.** All 12 PE files in the install root (HWR2.exe,
  EDITOR.exe, HWR2Toolkit.exe, PACKAGER.exe and the DLLs) have an empty CLR data
  directory (pefile, `DATA_DIRECTORY[14]`), so they are native and ILSpy does not apply.
  The readable game logic is the AngelScript that `bootstrap.py` unpacks with the
  patched PACKAGER copy in `tools/bin/`.
- **The manifest no longer hashes the shim stamp.** `tools/bin/hwr2_capture.build.json`
  records the gcc version, so `bootstrap.py --verify` failed on any machine with a
  different gcc. It is now excluded from the hash, like the DLL. `--verify` instead checks
  that the stamp's `source_sha256` matches `tools/capture_shim/hwr2_capture.c`.
  `gamelab/manifest.json` was re-recorded: only the `tools/bin/.` group changed
  (10 to 9 files), build 25509441.
- **Save backups are confirmed per machine.** `saves.verify()` compares the real saves
  against the manifest and never re-reads the copies. The new `saves.intact()` re-hashes
  the copies; `restore` refuses a damaged backup. Confirming runs the following, then
  writes `saves-backup/confirmed.json`:
  - the sandboxed selftest;
  - a backup;
  - `intact` on that backup;
  - `verify` against the real saves.

  The launcher preflight and `deploy.py modded-prod` refuse until the stamp exists, the
  save dirs still resolve to the same paths and the stamped backup re-hashes.
  `tools/saves_selftest.py` covers all three cases. It also creates `C:\tmp\claude`,
  which it used to assume existed.
- **Confirmation is automatic unless it is ambiguous.** `doctor --fix` confirms by itself
  when `assess_saves()` finds nothing ambiguous:
  - files exist;
  - the dir the player's config writes (`g_save_slot_cloud`) has files;
  - no other Steam account holds HoH2 saves;
  - no unknown `save*` dir in the install holds files.

  Anything else prints `AMBIGUOUS:` and needs a person (`--confirm-saves`). A person
  asked on an unambiguous machine adds nothing and learns to click yes.
  - `tools/doctor_selftest.py` covers seven cases on a sandbox Steam root (20 checks,
    green). The new overrides `HWP_STEAM_DIR` and `HWP_LOCALAPPDATA` exist for it.
  - The install's empty `save/` dir is not ambiguous; it would be if it held files.
    Which dir the game uses with `g_save_slot_cloud 0` is still measured only for
    GameLab's own copy (`saves/`).
- **Hazards on a new machine, checked by doctor, assumed and not hit here.**
  - A repo on another drive from the Steam library: `os.link` of `res/assets.bin`
    fails across volumes.
  - Steam not running: the directly launched exe needs the client (see above).
  - Saves under a second Steam account on the same PC: only the install's LastOwner
    account is backed up. doctor lists the others as uncovered.

## 2026-10-17 (night): doctor makes the local content too (HoH1, class units)

- **HoH1 discovery goes further, then asks.** `gamepaths.find_hoh1()` order:
  `HWP_HOH1_DIR`, then the Steam appmanifest 677120 in any library, then the path the
  user gave (`tools/paths.local.json`, gitignored), then a sibling of the HoH2 install,
  then every library's `steamapps/common/`. Every candidate except the env override must
  have `HWR.exe` + `res/assets.bin`. bootstrap and import_hoh1 use the same function.
  On this PC HoH1 is in another library (`G:\SteamLibrary`) and is found by its
  appmanifest (verified: `python -m gamelab doctor`, real repo).
- **Not found and no answer means doctor is NOT green.** The HoH1 row says `ASK THE USER`
  and names the two answers: `doctor --hoh1 "<dir>"` (validated, persisted) or
  `doctor --no-hoh1` (persisted; HoH1 content is then reported as skipped).
- **`--fix` makes the gitignored content a fresh clone lacks.** It reruns bootstrap when
  HoH1 is known but `gamecode/sdk/hoh1/` is missing (`--verify` treats that tree as
  optional). It runs `tools/class_units.py` when a copy differs from what it would write.
  It runs `import_hoh1.py pets|levels|campaign|classes`, each only when its output files
  are missing and never with `--force`. The importers do not read each other's output.
  A `mods/campaign/hoh1/` without the `.hwp-generated` marker is reported and left alone.
- **Fixed: `import_hoh1.py levels` crashed on the PACKAGER base.** Its HoH2 probe level
  (`levels/boss_arista.lvl`) is SValue XML in the PACKAGER unpack, not binary
  (`unsupported SValue tag 0x3c at offset 8`). `decode_level` now parses XML when the
  data starts with `<`. Verified: 32 probe script types, 0 unresolved; the import writes
  48 files.
- **Verified on a fresh clone** (`C:\tmp\claude\doctor_e2e\run_e2e_hoh1.py`, 30/30
  checks). Setup: a sandbox Steam with no HoH1 appmanifest and no library list, the real
  HoH2 install, and copies of the saves.
  - `--fix` exits 2 with only the HoH1 question open (bootstrap and class_units ran).
  - `--hoh1 G:\...\Heroes of Hammerwatch` persists the path. `--hoh1 <HoH2 dir>` is
    rejected.
  - `--fix` exits 0 in 55 s: hoh1 extraction (10990 files, matches the manifest) and all
    four imports.
  - A second `--fix` changes none of the 29257 files.
  - Real saves, the real `tools/paths.local.json` and the HoH1 install are unchanged.
- `tools/doctor_selftest.py`: 40 checks, green (21 new HoH1 discovery checks, sandboxed
  through `HWP_PATHS_LOCAL`).
- **Independently re-verified, in the game** (`C:\tmp\claude\doctor_e2e\validate_hoh1.py`,
  34/34 checks). It used another fresh clone with the same sandbox setup and repeated the
  flow above. It then went further:
  - `--hoh1` with a missing dir or the HoH2 dir saves nothing.
  - The generated files are all gitignored.
  - The imported content loads in the game. mod-pets 20261017-215458, mod-campaign
    20261017-215510 and mod-classes 20261017-215522 all PASS in lab mode with the HoH1
    files in the mod folders. Their game logs have no error lines on `hoh1` or `hwp`
    paths. The runs were in the clone, which is deleted.
  - `build.py --with-local` packs `hoh1/` into HWP-campaign.bin,
    `players/pets/hwp/` into HWP-pets.bin and the class art into HWP-classes.bin.
  - The levels fix is equivalent to the binary path: `level_refs` of `boss_arista.lvl`
    decoded from the install's binary archive equals the result from the XML unpack
    (1441 placed, 112 scripts).
  - **Assumed:** the game *uses* each imported item. No scenario opens the Pet Shop or
    plays a HoH1 floor; the scenarios prove a clean load only.
- **Assumed, not tested:** the sibling and library searches against a real Steam layout
  (only sandboxed); a HoH1 version other than this machine's. Its `gamecode/sdk/hoh1`
  hash would differ from `gamelab/manifest.json`, so `bootstrap.py --verify` would fail
  there.
- ~~**Not covered:** `tools/make_pet_dyes.py` output~~: covered since, see the next section.

## 2026-10-17 (night): doctor makes the pet dyes and smoke-boots the machine

- **Pet dyes.** `tools/make_pet_dyes.py` now writes `dye/.hwp-generated.json` with its own
  sha256, the pets it made and the sha256 of every source unit and sheet. `--verify` (and
  `problems()`) reports missing copies, a changed generator, a changed source or a pet
  whose source appeared since (the HoH1 import adds 21). The dotfile never packs
  (`packable_files` skips dot-parts). doctor runs it after class_units and the HoH1
  imports, also when HoH1 is declined (the 7 vanilla pets only need `gamecode/sdk/hoh2`).
- **Smoke boot.** Once every non-content row is green, `doctor --fix` runs `null-payload`
  in lab mode (`--smoke` forces it). A pass goes to `gamelab/smoke.local.json` (gitignored)
  keyed by build id, shim source hash, `os.cpu_count()` and the display adapters
  (registry display class `DriverDesc`). A change to any of them asks for a new boot.
  `explain_smoke()` maps a failure to a plain cause: a refused shim (antivirus), the
  renderer not starting (log has `Opening SDL window`, no `BGFX initialized`), blank
  shots, a deadline (shown with "N of M cores"), a window leaking to the input desktop,
  no game log, the probe not booting, isolation checks, or user files changed.
- **A failed boot leaves the lock dirty.** Verified: with a garbage shim the game is
  killed and `teardown.json` records `pass 1 exited cleanly: exit code 1`, so the next run
  is refused with exit 4. doctor records the failed run in the smoke stamp. Before its
  next boot it runs `python -m gamelab reset` only if the dirty teardown is that same run
  and no lock is held. Any other dirty teardown is still left for a person.
- **Verified on a fresh clone** (`C:\tmp\claude\doctor_e2e\run_e2e_smoke_dyes.py`, 28/28;
  sandbox Steam with copies of the saves; the first attempt, 23/27, found the two bugs
  fixed above: the dye row hid its reason, and the dirty teardown blocked every later boot):
  - `--fix` with HoH1 unanswered: dyes for 7 pets, smoke PASS in 14 s on the hidden desktop
    (run 20261017-222209: focus and no-leak assertions and `shot town` pass).
  - `--hoh1` + `--fix`: dyes regenerated for 28 pets, no second boot; a second `--fix`
    rewrites nothing and boots nothing; generated files all gitignored.
  - An edited HoH1 pet unit: plain doctor says `1 sources changed`, `--fix` remakes them.
  - A garbage `hwr2_capture.dll`: `--smoke` reports the refused shim and names antivirus
    and the dll. Shim restored, `--fix` resets its own dirty teardown and passes.
  - A scenario with an already-passed deadline: reported as too slow, "gets 14 of 16 cores".
  - Real saves byte-identical, HoH1 install and the real repo's stamp unchanged.
- `tools/doctor_selftest.py`: 78 checks, green (every `explain_smoke` branch, the stamp,
  the gating, the reset rule, the dye staleness cases on a sandbox).
- **Assumed, not tested:** the GPU branches (no-GL, blank frames) and the window-leak
  branch on a machine that actually fails them. The causes are mapped from the log lines
  and assertions a passing run shows, plus the selftest. The real antivirus case
  (a refused LoadLibraryW) was reproduced only through a broken dll.

## Merge of main into gamelab-pilot (2026-10-17): what GameLab caught

- **A non-power-of-two GUI texture is fatal at boot.** Verified (run
  20261017-225009-mod-fishing-lab, `pass1.HWR2.exe.log`): `gui/hwp/bait.png (class
  TextureLoader): Texture sizes (48x16) should be power of two`, then `main menu never
  loaded`. Fixed by padding right/bottom with transparency so sprite rects are unchanged:
  `mods/fishing/gui/hwp/bait.png` 48x16 -> 64x16, `mods/farming/gui/hwp_seeds.png`
  117x13 -> 128x16. Both PASS afterwards (225242 fishing, 225254 farming).
- **Malformed `.gui` XML is fatal too.** Verified (run 20261017-224728-mod-fishing-lab):
  `gui/hwp_pirate.gui (class GUILoader): XML error! invalid closing tag name`. main had a
  stale copy of the old button layout plus an extra `</panel>` after the new one; removed.
- `mods/colors/gui/options/game.gui` has a duplicate attribute on one `entry-selector`
  (a strict XML parser rejects it); the game's loader accepts it (mod-colors PASS, 225344).
- New `mod-all` scenario: all 26 content mods together in town, clean log. PASS
  (20261017-225415-mod-all-lab). Run it before merging to main.
- **Second merge (ddf944c, pirate follows trading post).** Checked against the pinned
  prefabs: `trading_post.sval` uses `tier_0.pfb` as `unbuilt-prefab` (variation -1) and
  `tier_N.pfb` for variation N-1, so `GetVariationOnBuilding + 1` is the prefab tier.
  `tier_0`-`tier_2` have `boat_small_wreck` at 320,-112; `tier_3`+ have none. The
  material trader is at ~380,-66.8 in `tier_1`-`tier_5` (absent from `tier_0`, where the
  code falls back to the plot origin). In run 20261017-230737-mod-fishing-lab the
  unbuilt fixture town puts the pirate at -1222,142 = plot + (314,-114), on the wreck.
  **Assumed, not tested:** the re-place after an upgrade (`WatchCoast`), since no fixture builds
  the trading post. `import_hoh1.py pets --force` produced the candle body
  (flame origin y +9, lights -9); mod-pets and mod-all PASS (230749, 230812).

## 2026-10-18: test-plan pass findings

- **A new profile's town is not saved, and HWP settings with it.** `TownRecord.Save`
  returns false when the town has no buildings, no town flags and no materials
  (`scripts/Town/TownRecord.as:333`), so `SavePlayerAndTown` writes no town and the
  `TownRecordSave` hook never runs. Measured on `plan-t2` (20261018-033859): a preset set
  in town was gone on the first floor, and `deathrecap.chat` was unset after a restart.
  Core now writes settings through `HWP::SaveData::MyTownForWrite()`, which sets an
  `hwp_town_data` town flag first (not net-synced; vanilla never reads it). After the fix
  both survive (20261018-034519).
- **Posted mouse messages do not reach the game.** A posted `WM_MOUSEMOVE` and click
  left `GameInput` unchanged: aim, mouse position and the death recap's hover test all
  stayed the same (probe 20261018-034929). The engine reads the cursor itself. Steps that
  need a hover or a click therefore stay manual.
- **`dictionary.set` keeps a temporary by reference.** Measured with a probe on
  `plan-t4` (20261018-035113): `d.set(key, a + b)` or `d.set(key, true)` stores a value that
  later reads as garbage (a key count of 322810098 after "+2 gold"), while
  `int n = a + b; d.set(key, n);` stores 2 and survives function calls. Vanilla
  `PlayerRecord.AddKeys` does `keys.set(key, currNum + num)`, so every vanilla key change
  (`Chest::Use`, the `GiveKey` effect) corrupts the count. The keys module has its own
  `HWP::Keys::AddKeys`/`SetKeys` with named locals, and resets corrupt counts at level
  start. Summons and GoldPet were changed to the same pattern. Vanilla `Save`/`Load` use
  named locals and are unaffected.
- **A run's end state is gone by the time Start runs.** Back in town the order is:
  - module constructors, before the character loads;
  - `PlayerRecord.Load` sets `currMissionState` (~line 902) and `statsRun` (1288), then
    calls `Hooks::Call("PlayerRecordLoad")` (1299);
  - `TownGameMode.PostStart` builds `MissionEndMenu`, whose constructor sets
    `currMissionState` to None and calls `ResetForNewMission`;
  - `GameModeStart`, where HWP's `ModuleStart.Start` runs.

  So only `PlayerRecordLoad` sees how the run ended. Before this was found, a failed run
  gave no laststats snapshot, and farming logged "the run was not finished (state 0)".
  laststats, farming and mercenary now read the state there. A revive from the death
  menu ends the run with `AbortMission(Failed)`.
- **SValue compact tags 0x67/0x68 are true/false** (fixed in faaddf2; they were swapped).
  Converted HoH1 levels made before that fix had every boolean inverted.
  `hwr_archive.CONVERTER_VERSION` (now 2) is stamped on each `import_hoh1.py` output
  (`hoh1_import/stamps/`). An import over older output regenerates it, and `build.py`
  warns about stale imports.
- **The mission defs and their level generators are rebuilt on every level load**,
  before any module constructor. A command added to `m_genCommands` in a ctor is
  therefore gone on the next level and must be added again; it never piles up.
  `DungeonGenerator` calls `randf()` once per command (against `m_execChance`), so
  inserting a command shifts every later roll and changes the level vanilla makes for a
  seed. The architect's `ChallengeSetup` wraps an unconditional command instead of
  inserting one.
- **`Item::GetRandomTrinket` sets `m_seen` on the trinket it returns**
  (`scripts/Items/Trinkets.as:46`), and later rolls treat seen trinkets as duplicates.
  Vanilla shops and the sarcophagus clear it again for picks nobody took. The General
  Merchant's trinket stock roll saves every trinket's `m_seen` and restores it afterwards.
  Assumed, not measured: whether `Trinket` instances reload per level, which would reset
  it anyway.
- **Escape on the character picker closes it.** `WindowManager.Back` closes the top
  window when its `Back()` returns true, and `PickCharacterWindow.Back` always does (only
  setting the in-game menu when no class is picked). A forced picker therefore has to be
  reopened: mercenary reopens it after `PICKER_DELAY_MS` while a fallen mercenary is in
  town.
- **God mode lives in the `cht_god` cvar, not in `CVars::ChtGodmode`.** The vanilla
  `cht_god` is registered with `AddVar("cht_god", false, SetGodmodeCVar, Cheat |
  TriggerChanged)` (`scripts/Console/Cheats.as:22`), and `SetGodmodeCVar` copies it into
  `CVars::ChtGodmode`, which `Player.as` reads. Setting only `CVars::ChtGodmode` did not
  hold: in GameLab (probe-god) the player still took damage. HWP's `hwp god` therefore
  toggles the cvar with `SetVar("cht_god", on)` and reads it with `GetVarBool("cht_god")`.
  Verified: with the cvar set, HP stays full under damage. Assumed, not traced: what
  resets the script global (the cvar being re-applied on a level or script load).
- **A building upgrade destroys every unit a mod spawned in town.** `TownRecord.Refresh`
  (what runs when an upgrade's cutscene ends) does `QuickReloadLevel` and `SpawnTown` in
  the same scene, with no new module `Start`. Verified with `gl townrefresh`
  (mod-town-rebuild): before the fix, the gambler, the last-run board, the pet bowl and
  the pet vendor were gone afterwards. Modules that spawn once per load now keep the
  unit in `HWP::Town::Kept` and re-spawn it when it is invalid or destroyed (checked
  every `WATCH_MS`, in town only, host-only unless told otherwise). Placeable, fishing
  and farming already did this.
- **The vanilla close button is `<spritebutton spriteset="close">`**, with the sprites
  from `gui/closebutton_sprites.inc` (close, close-hover, close-down, close-disabled).
  `spriteset="close-button"` does not exist: the button draws nothing and the log says
  "Couldn't load SpriteRect, sval does not exist". Eight HWP windows had it. GameLab's
  `log_clean` now fails on that line.
- **`g_scene.FetchAllUnits` (GameLab `near`, `use`) misses units with no solid
  collision**, such as the campaign portal and the abyss crack (sensor only). Assumed
  from what `near` does and does not find, not traced in the engine. Scenarios find those
  units by their logged position (`log_capture`) instead.
- **The campaign needs the story flag `mission_story_intro_find_npcs`** (vanilla
  `cht_set_flag mission_story_intro_find_npcs 1 1`); `hwp unlockflags` does not set it.
- **Vanilla's `theme_prison` never generates.** Its only uses in `missions_story.sval`
  are commented out, and a floor using it loops forever on "Couldn't find two
  appropriate spots for prison_start, and prison_exit" (`DungeonGenerationCommands.as:146`),
  hanging the game. Verified in plan-t6c (Forsaken Tower floor 4). The campaign's Prison
  floors now use `theme_dungeon` with Dark Citadel's dungeon sizes.
- **`cht_kill_all` (GameLab `cull`) kills with no killer**, so `PlayerKilledActor`
  hooks, XP and kill stats do not run. `CompositeActorBehavior.Kill(killer, w)` calls
  `OnDeath`, which calls `killer.KilledActor`, so `gl cull mine` (the local player as
  killer) runs them. The survival arena's bar (`SurvivalMission.m_experienceC`) still
  counts culled kills, through `OnEventActorDestroyed`.
- **Escape with no window open opens the pause menu**, and a paused game does not run
  module `UpdateFrame`. A scenario that pressed Escape after a failed `gl use` stalled
  every timer behind it for 15 s.
- **Strongbox packs and abyss waves could hold unkillable members.** Both copy their
  enemy kinds from the live actors around them (`HWP::Spawner::SampleProducers`,
  `FetchActorsWithOtherTeam`). Farming's wild plot is an `HWPLocalNPC`
  (`CompositeActorBehaviorNPC`) on a non-player team, so it was sampled as a kind and
  spawned as onion plots. Nothing kills those (cull skips untargetable actors, and so
  does combat), so the strongbox never opened and the crack never reached wave 2.
  Verified in plan-t4 run 050719: every cull skipped `doodads/hwp/wild/onion.unit`
  copies around the box and the crack. This was also the "abyss wave stall" seen once
  in run 043107. `IsSpawnable` now takes only targetable, non-NPC actors whose unit is
  under `actors/`.
- **`SurvivalMission`'s `boss` must be a prefab.** `Missions/SurvivalMission.as` loads it
  with `Resources::GetPrefab` and, once the bar is full, fabricates it at the player's
  position + (0,-100). The heaven trials pass a spawner prefab
  (`prefabs/heaven/seg_heaven/boss_spawners/heaven_*_spawner.pfb`): an intro, a
  `SpawnUnit` of the boss, and a `BossDefeated` ScriptLink that unlocks the trial's
  achievement, sets its character flag and opens the exit. The wave arena passed
  `actors/hwp/wave_boss.unit`, so the prefab was null and filling the bar threw "Null
  pointer access" (`SurvivalMission.as:126`): the arena champion never spawned. Verified
  in plan-t6b run 051540. `tools/make_wave_boss_prefab.py` now writes a copy of the
  warrior spawner for the arena. Worldscript rows decode as `[type, id, pos, enabled,
  triggerTimes, ?, (comment), params, (links)]`; a ScriptLink's links are flat
  `id, delay` pairs.
- **The wave statue's old default (-1500,250) was on the beach**, inside the trading post's
  plot (-1536,256) and 64 px from coast fishing spot 3 (-1436,272). In plan-t6b run 052747
  a use there opened `HWPFishingMenu`, not the survival window. The statue now stands left of
  the chapel's Pyre slot (`HWP::Town::ChapelPyreSpot`, moved to core from the campaign):
  872,-232 with the Pyre unbuilt, 872,-160 once a built Pyre blocks that spot. Verified with
  the Pyre unbuilt and built (`gl build pyre` + `townrefresh`) in probe run 053923: use opens
  `WindowSurvivalMission` both times.
- **Survival spawn events sit at k/(n+1) of the bar** (`SurvivalMission.OnEventActorDestroyed`):
  with 4 events, at 20/40/60/80%. A kill past a checkpoint fires one event. Once the bar
  passes the goal the boss spawns and no more events fire, so jumping the bar straight to
  full skips all of them. `hwp wave goal 21` then one kill fired "Spawning Event 1" in
  plan-t6b run 052403.
- **Start gear goes through the normal equip checks.** `PlayerRecord` (~line 452) gives each
  `starting-equipment` id a Common roll at level 1 and calls `EquippedItems.Equip`, which
  starts with `MayEquip`: a stat requirement the fresh character can't meet makes it return
  null, and the item is simply lost (not put in the inventory). The Witch Hunter (5 STR) listed
  the vanilla `twohanded_crossbow_01` (ilvl 10, `req-str 10 25`) and started unarmed. Verified
  by decoding `gl inspect player equipped` in plan-t7 run 061824 (slot 0 null). It now starts
  with `hwp_crossbow_01` (ilvl 1, `req-dex 8 18`, DEX-scaled), and plan-t7 asserts slot 0 for
  all four HWP classes (run 062639: daggers, trident, crossbow, rifle).
- **Herbs need two watered runs.** A plot gets +2 growth per run when watered, +1 when not
  (`CountRun`); food crops are ripe at 2, herbs at 4. plan-t7 waters and grows twice before the
  Lucky Leaf harvest.
- **The Pilot's `use` reach.** A solid target (a chest) can't be walked onto, so walking to
  within a few px of its centre never ends. `use` now stops once the target is the player's
  top usable (`GetTopUsable().GetUseUnit()`), and the stuck check treats an approaching `use`
  as moving. A path from inside an obstacle's footprint (where an opened chest stood) comes
  back empty; `Repath` then retries from eight points 24 px out. Verified in plan-t7 run
  061824 (two chests opened in a row).
- **The Pilot finds no route from the town arrival point (1984,598) into town.** Both
  `Pathfind` and the partial `NavRoute` end in the forest. Town scenarios teleport near the
  target first. Not traced further.
- **`Scene.FetchAllUnits(mask, center, radius)` doesn't bound what it returns by the radius.**
  First seen as "`near <r> <filter>` ignores the radius"; it was the same without a filter
  (`near 60` in town: 764 units, plan-t8 075319), so every `near` count was the whole level.
  `near` now drops units past the radius itself. mod-puzzle-rooms' reward check counted the
  whole level that way and now counts `near 6000 items/`; the other 14 scenarios that use
  `near` pass unchanged (081413-082914).
- **The dark column over a window in the lower-left is the in-game chat history panel**
  (x 19-250, y 136-360 at 640x360). It shows while recent chat lines are up (any `[HWP]`
  message) and fades with them. It isn't part of the HWP window under it (probe 063142).
- **A town rebuild reuses unit ids.** `TownRecord.Refresh` reloads the level in the same
  scene, and the new level's units get the old ids back. A `UnitPtr` kept from before then
  reads `IsValid()` and not `IsDestroyed()`, but names a different unit. Measured in
  mod-town-rebuild run 064132: id 923 (the notice board) came back as `tree_oak.unit` and
  924 (the gambler) as `beetle_green_small.unit`, so neither was spawned again (run 063819
  failed on both). The pet bowl's id happened not to be reused. Core now has
  `HWP::Town::Ours(u)` (live, and the unit file is an HWP one), `Kept.Set` remembers the
  producer, and `Placeable` compares the unit path. Every destroy or "still there" check
  on a kept town unit (gambler, board, bowl, pet vendor, pirate, coast spots, traps, farm
  plots, visuals, well, hidden crops, dye markers) goes through them. Assumed, not
  measured: before this, a rebuild could make `ClearLocal`, `ClearVisuals` or
  `Placeable.Spawn` destroy (or `SetCropsHidden` hide) whatever vanilla unit took the id.
- **The Gambler's result line was overwritten right away.** `UpdateUI()` sets the line to
  the bet prompt (no hand) or the last hand's result, and the sell and reroll handlers
  call it after writing their message, so "Rerolled ...", "Not enough gold ..." and "Sold
  your wares ..." were never on screen (plan-t8 070630: the line read "Place your bet and
  draw!" after every press). They now go to `m_notice`, which `UpdateUI` shows until the
  next hand or bet. The reroll buttons are never disabled; the refusal is that line.
- **A low item level has a small modifier pool.** A rare mace at ilvl 3 rerolled to the
  same modifier it had (plan-t8 072725: token spent, item unchanged), and the same few
  modifier ids came up across runs. A reroll now rolls up to 8 times for a set the item
  didn't have.
- **GameLab's `widgets` dump can't read a button's caption.** `ScalableSpriteButtonWidget`
  text is a `BitmapString`; only `TextWidget.m_str` is dumped. The dump now also gives
  `enabled` for `AInteractableWidget`s.
- **GameLab `pathfind` answers `nodes: 0` both for "no path" and for some straight lines.**
  A chest at +90,0 from the Bandit Keep start answered 0 in one run and 2 in the next, and
  opened both times. `plan_checks.chest_spot` prefers `nodes > 0` spots.
- **Bot timing.** The weapon swap has a 1 s cooldown, so a check that presses X again
  sooner sees nothing (072156). A posted console line once arrived as "`hwp bag" (stray
  backtick) and did nothing; `plan_checks.hwp(..., until=)` resends once when the reply
  doesn't come. The Bandit Keep's bandits killed the player during the third chest, so the
  chest checks `cull` first.
- **A log line over 16 KB looks fatal.** The game exited with 0xE06D7363 right after printing
  a 16,401-char `widgets` reply (plan-t8 074605); no earlier reply was over 14,596. Assumed
  from that one case, not reproduced. GameLab's `Emit` now replaces a reply over 15,000 chars
  with a short failure that keeps its id, and `widgets` stops at 13,000 chars of nodes.
- **A tabbed window's open tab is its own window object.** `PlayerMenu`, `GuildHall`,
  `WindowOptionsMenu` and `CreateCharacterWindow` keep their tabs in a `MenuTabSystem`; each
  `MenuTab` is an `AWindowObject` whose widget tree isn't under the window's, and its own
  `m_tabSystem` is the one it sits in. `widgets` now dumps the open tab as a root named
  `PlayerMenu:PlayerMenuCharacterTab`, which is where the gear and alt-weapon slots are.
- **A locked chest is not usable without its key.** Vanilla `Chest.CanUse` is false while
  `GetKeys(m_key) <= 0`, so a use attempt finds the chest as the top usable but can't use it
  (the Pilot reports "top usable is not the target"). With the key it opens (plan-t8 081413).
- **open-chest and open-chest-minimized fail before and after this session's probe changes**
  (081200 with the old probe): the "f" key press doesn't open the spawned cache. Those are
  GameLab self-tests of real key input, not HWP features; not traced.
- **`WindowManager.CloseWindow` doesn't set `m_closing`; `Back()` / Escape does.** An NPC
  window (`AShopContent.IsDone()`) only counts as done once `m_window.m_closing` is set, and
  vanilla `NPCSharedBehavior.Use` closes the open window instead of interacting while
  `m_current` is set. So after an HWP window closed itself with `CloseWindow(this)`, the next
  use of that NPC or object did nothing: planting at a farm plot then using it again to water
  needed two uses (plan-t9, 2026-10-18 morning). Seven HWP windows close themselves (farm,
  pet bowl, pet dye, fishing, pirate, pet vendor, last-stats board); each now sets
  `m_closing = true` first. The watering check passes on the first use since.
- **`Town::Ours` alone can be fooled by an id reused for another HWP unit.** After a town
  rebuild, the gold pet vendor's old id came back as a different `/hwp` unit, so "still
  ours" was true and the vendor wasn't spawned again (plan-t10, fixed). `HWP::Town::Is(u,
  unitPath)` also compares the producer; the vendor, well, bowl and pirate checks use it.
  mod-town-rebuild and plan-t10 pass with it (090120, 090404).
- **Re-running `import_hoh1.py pets` put the HoH1 pets back on the vanilla classes.** The
  importer wrote `MiniPetWalking`/`MiniPetFlying`, and only `make_pet_dyes.py` (run by
  doctor) rewrote them to the HWP classes. After a re-import at 04:06 all 22 HoH1 pet units
  were vanilla again: no pickup toggles (vanilla always passes 319), no Fetch, skills,
  dyes or puzzle-room waiting. `gl near` showed `behavior: MiniPetWalking`, and the Elf
  Imp fetched gold with Gold off (plan-t9 090855-091950). Earlier "off" passes were drops
  the pet happened not to reach. The importer now applies the pets module's `class_swaps`
  itself, and `make_pet_dyes.py --verify` (doctor) reports any HoH1 unit still on a
  vanilla class. plan-t9 092312: `HWPMiniPetWalking`, Gold off leaves the drop, on fetches it.
- **A gold drop the pathfinder reaches can still be one the pet won't fetch.** A drop at
  (150, 0) from the Bandit Keep start stayed put while (Â±106, 106) and (0, 150) were
  fetched. `plan_checks.gold_drop` now wants a near-straight path (length â‰¤ 1.25 Ã— the
  distance), tries the diagonals first, and moves to the next direction when a drop isn't
  fetched within 8 s.
- **`Material::DropMaterial(type, amount, pos, shared, dropAnim)`** gives a pickup that
  carries its amount. `gl spawn items/materials/gold.unit` gives one worth 0 (its behaviour
  is never `Initialize`d). GameLab's new `drop` verb uses DropMaterial with no drop animation.
- **`array.sort(callback)` on an empty array throws "Index out of bounds"** (reported on
  the sort line). `MissionShopContent.GetItems` sorts its missions, and
  `MissionDef::FetchMissionsFromSet` returns none while the set's conditionals fail (the
  campaign set needs `mission_story_intro_find_npcs`, unset on a fresh character), so using
  the town portal threw before any window opened (plan-t11 094100). `HWPCampaignShopContent`
  says the portal is dormant instead and sorts only lists longer than one. plan-t11 094708:
  dormant first, then two missions after `cht_set_flag mission_story_intro_find_npcs 1 0`.
- **Escape with no window open opens the pause menu**, and a paused game ignores the next
  steps (the wave statue run sat in the pause menu after a failed portal use). Bots only
  press Escape when `state.window` is set.
- **The game carries a player's summons through a floor change** (with their HP): the
  record keeps each summon's `SaveUnit` data and `Player`'s constructor produces them on
  the new floor. GameLab probe-summons-off 095747: with mods/summons off, 2 damaged
  crusaders came through. The summons module produced its own snapshot on top, so 2 went
  in and 3 came out (plan-t12 095531). It now produces only what is missing per kind.
  Call Crusaders is a passive skill: below its cap it summons one about 1 s after a level
  loads (town too) and at once when its 15 s timer has already run out.
- **Kills without a killer run no kill hooks.** `cht_killall` (and `hwp killall`) calls
  `Kill(null, 0)`; only `Kill(player, ...)` reaches `OnDeath` -> `KilledActor` ->
  `PlayerKilledActor`, so key drops, XP and kill stats need the player as the killer
  (GameLab `kill <r> <filter> me`). Elites are their own units (`bandit_brute_elite.unit`
  etc., tag `elite`), not a modifier on normal ones; a Bandit Keep floor 1 had none (probe-keys
  102702). Boss floors spawn the boss from an encounter, so it isn't there on arrival.
- **A `gl` line typed while the next level preloads can find the probe's verb registry
  null** (Script exception at Probe.as `RunVerb`, probe-keys2 103121, during a Dark Citadel
  load). ConsoleGl now catches it and fails the command so the caller polls again.
- **Combo needs a combo skill.** `PlayerStats.ComboCountMax` is 0 until a combo skill
  (`combo_kills` / `combo_dash` / `combo_parry`, tier 1, cost 0) is picked through
  `SkillUp(id, true)`; until then `Player.GiveCombo` does nothing.

## Skill aim follows the mouse after the emulated input ends (2026-10-18)
- `gl input` sets `GameInput.AimDir` only while held. A skill with `update-aim 0 N` keeps
  re-reading the aim until N ms; released earlier, the aim falls back to the real mouse
  cursor, and the round flies there. The firearms aimed shot (castpoint 420) missed every
  target with a 60-300 ms press and hit three brutes in a line with a 500 ms hold
  (plan-t14 20261018-114725). Verified.
- One `gl` command per ~0.3 s: three spawns plus a shot gave the brutes time to walk in and
  steer around each other; `gl multi` puts them in one frame. Verified.
- `cht_plr_hidden` only hides the player unit; enemies still aggro. Goblin totems took no
  projectile hits. Verified (plan-t14 runs 111904, 113007).
- Player mana costs: `Player.UsePoints` takes flat cost x `GetModifiers().SkillCostMul` off a
  float mana; `CurrentMana()` truncates, so integer read-backs alternate 1/0 for a 1-mana
  shot under regen. The probe now reports `manaExact` and `manaCostMul`. Verified.

## Enchanter assumes quality-matching mods (2026-10-18)
- `Town/EquipmentEnchantShopContent.as`: the Enchant view (`EnchantEquipmentWindow.Refresh`)
  shows `modifier-1` for quality >= Uncommon and `modifier-2` for Rare, and reads
  `mods[GetCurrEncSlotIdx(shop, 0|1)]` for their text; the list entries and the `modify`
  func index the same way. `GetCurrEncSlotIdx` looks for a Common-quality mod (slot 0) or a
  Rare one / a second Common one (slot 1) and returns -1 when there is none, so an
  uncommon or rare item without its modifiers throws "Index out of bounds" (inside a
  `gl pressin` the probe reports `exception in verb 'pressin'` and the heartbeat's
  exceptions count rises; no "Script exception" line). Vanilla items always have them:
  `Generator.GenerateItemMods` gives `EquipmentModifiersPerQuality` (0 / 1 / 2 / 3 / 4)
  mods, the first from the Common pool (no vanilla mod is Uncommon quality). Fishing built
  fish items directly with none; fixed by rolling them at the catch. Verified for the
  crash (plan-fishing-a 20261018-121447: fresh Salmon, heartbeat exceptions 0 -> 1); the
  fix not yet run.
- The Enchant list only shows modifiers whose blueprint the town owns
  (`GetItems`: `m_blueprintHash != 0 && !HasBlueprint` skips it). Every mod in
  `tweak/items/modifiers_equipment*.sval` has one (`blueprint` defaults true), so a
  fresh town lists none for any item ("Num item mods: 8" printed, 0 shown). GameLab:
  `cht_add_all_blueprints` (cheat). Verified (same run).
- `Generator.ModifyItem` (the enchanter's Upgrade) calls `GenerateItemMods`, which keeps
  `mods[n]` only when its quality is `IndexToQuality(n + 2)` (Uncommon for the first);
  the first mod is always Common quality, so an upgrade rerolls every modifier.
  From source; assumed.

## Three skill buttons; extra skill keys (2026-10-18)
- **The engine has only Skill1-3.** `GameInput` exposes `Skill1`, `Skill2`, `Skill3`
  (`hwr2_api_strings.txt` has no `Skill4`; the editor stub `system/engine.as` lists one, but
  it is stale). `PlayerTargetingHelper.GetSkillInput` (PlayerTargetingHelper.as:713-750)
  counts the non-passive `Spell` skills from `m_skills[1]` and returns `Skill3` for the 3rd
  and every later one, and `CheckUseSkill` (515) activates every skill whose button is
  Pressed, so a 4th active fires together with the 3rd. Verified in game by the main
  session (GameLab, firearms and classes plans, 2026-10-18). Vanilla keyboard defaults
  (`res/controls_default.cfg`): Skill1 = 1, Q, mouse 4; Skill2 = 2, E, mouse 5; Skill3 = 3, V;
  free digits 4-0. Gamepad: RB, LB, Y. `RadialMenuController` has a skill wheel
  (`ExpandPlayerSkill` -> `TryUseSkill`), but `RadialMenu` only adds emotes and the ping, so
  a gamepad has no way to a 4th active; the extra keys are keyboard only. From source.
- **Fix (core `SkillKeys.as`):** `Player.m_targetHelper` is a public `PlayerTargetingHelper@`
  and script methods are virtual, so core swaps the local player's helper for a subclass,
  `HWPSkillKeysHelper`, from a module `UpdateFrame` (only when no targeting is open). Its
  `GetSkillInput` override takes the vanilla answer and, for the 4th-6th active, rewrites
  `Down` / `Pressed` / `Released` of that `ButtonState` copy from a raw-key poll
  (`Platform::IsKeyDown`, scancodes from the Plus tab, default 4/5/6), sampled once per
  player frame in an `Update` override. Every other path (targeting modes, input buffer,
  `GetSkillCanceledInput`, quickcast) is vanilla and reads the new keys through the
  override. Assumed until measured: a `ButtonState` local copy is writable
  (gamelab-hands already writes `gi.Skill3.Down`, verified) and `Base::Method()` calls from an
  override compile here as they do for HWP widgets.
- **HUD:** `HUDPlayer` (player_info.gui) has backgrounds for 2-4 skills. Core replaces it in
  `HUDConstructor` with `HWPSkillKeysHUDPlayer`, which widens the 4-skill group in place
  (a `skill-mid` sprite and a `skill-slot` rect per extra skill, end cap moved 31 px) before
  the vanilla `RefreshSkills`, then writes the key name into the extra skills' unused
  `binding` text, moved above the slot. Assumed until a screenshot.
- **Subclass picker** (`Town/SubclassPickShopContent.as:96-102`) shows `m_skillDefs[len-2]` as
  the spec's active and `[len-1]` as its passive. Sniper (snipe, flashbang, decoy) and
  Demolitions (tube, rpg, jetpack) have three actives, so the picker shows flashbang / rpg as
  "active" and decoy / jetpack as "passive", and never snipe / tube. Display only; from source.
  Fixed in core (`HWP/Core/SubclassPick.as`): no window hook exists (`OpenShopWindow` adds the
  window straight to the `WindowManager`) and the shop content class is named in the vanilla
  NPC unit, so the open vanilla window is patched in place. Module `UpdateFrame` runs after
  `BaseGameMode.UpdateFrame`'s window-manager update, paused or not
  (`AGameplayGameMode.as:319/333`), so the patch lands before that frame is drawn. The row
  shows the spec's own defs (not in the parent class), actives then passives, each labelled
  by type, spread over up to four slots (copies of
  slot 0, ids `hwp-pick-name<i>` / `hwp-pick-skill<i>`, labels `hwp-pick-label<i>`). It
  relays out when the shown class changes or when `SetCurrSubclass` rewrites slots 0/1 (on
  a pick), seen as a skill id change. Vanilla specs (one active + one passive at the end)
  look exactly as before. Gotcha: `Widget.CloneInto` value-copies the fields, so a cloned
  `TextWidget` shares the original's `BitmapString`, and its `SetText` would `Cleanup()` the
  original's text; the copy's `m_text` is nulled first (same for `SkillWidget.m_cost`).
  Assumed until a run: the layout and the label spacing (105 px for three slots).
- **A def's type does not say passive.** `PlayerSkillDef` turns an untyped def into `Spell`
  (`PlayerClass.as:91-92`), so every class skill def, passives included, has `m_type` 4
  (measured: `gl classskills hwp_priest_hoh1` gave Last Rites type 4, run
  20261018-125750-plan-classesb-b). Passive is the skill's `GetTargetingMode()` ==
  `TargetingMode::Passive` (the default of `Skill.as:83`, which `PassiveSkill` keeps), the
  test `GetSkillInput` and `HUDPlayer` make: those skills get no button (`gl skills` button
  ""). The picker row and `gl classskills` (`mode`, `passive`) classify by a temp skill
  built as `MakeSkillTemp` builds one. The vanilla row's labels are static gui text
  (Active under slot 0, Passive under slot 1); a first version of the fix set them from
  `m_type` and so labelled every passive Active, the vanilla specs' included.
- **GameLab:** `gl input` takes `hwp_skill4`..`hwp_skill6`; gamelab-hands writes the held
  ones to `GlobalCache` `hwp_skillkeys_held` ("4,5") and core's poll ORs them in (no shared
  symbol, so hands still loads without core). `gl skills` / `gl skillbar` report the
  extra key once the helper is installed (`Reflect::GetTypeName` of `m_targetHelper`).

## Test-plan rounds 2-6 (2026-10-18)

- **`ParseColorRGBA` returns linear colour.** A dye's sval hex (sRGB) comes back
  linearised, so writing `m_colors[i]` straight into a `\c` text code shows it darker
  (Midnight 222270 showed as 040429). `PetDye.Hex2` encodes back to sRGB (measured: the
  round trip gives the authored hex, plan-pets-a 20261018-141404).
- **HoH1 level script rows are `[type, id, pos, Enabled, TriggerTimes, ExecuteOnStart, ...]`.**
  Checked against vanilla HoH2 `boss_arista.lvl` (index 3 true on nearly every script,
  index 5 only on PlayMusic). `hoh1_convert.py` used to clear index 3 on level exits,
  which disabled both Battlements 1 exits and boss_archives exit 4949. The rule now
  clears index 5 (no HoH1 exit sets it). Re-import the HoH1 levels to pick this up.
- **HoH1 `SpawnEnemyGroup` is how the Battlements get their enemies** (53 points on floor
  1, 60 on floor 2; the levels place none). HoH1 called the generator's
  `EnemyPlacement.PlaceGroup`; the port now spawns `int(2*PI*Radius/40*0.5)` ice trolls
  plus one shaman per group at weight 0.8 (measured: 19 trolls, 4 shamans on floor 1,
  plan-runs-d 20261018-141935). The ice trolls are on the NG+ map too (below).
- **The Warden's bomb fan and the Vampire Lord's Bat Spray are NG+ attacks.** The base
  units leave them out (warden.unit defines NORMAL and the fan is `%if !NORMAL`;
  vampire.unit has `BATCHARGES 0`), and HoH1 swaps each boss for a tier copy by NG+ level
  (`tweak/dungeons/unitmap_base.sval`: `_t2` at NG+1, `_t3` at 3, `_t4` at 5, `_t5` at 10;
  warden_t2 sets `WHIRLBOMBS 4`, vampire_t2..t5 1/3/5/7 bat charges). The Golem and the
  three Wraiths get the same swap. (An earlier version of this note called the attacks off
  at any NG: wrong, the tier files were missed.)
- **HoH1's NG+ swap is in its spawners, and the port does it the same way (2026-10-18).**
  HoH1 `UnitMap::Replace` runs inside SpawnUnit, SpawnUnitWithEffect, SpawnDropUnit and
  EnemyPlacement, not on placed units; every mapped unit in our levels comes from the first
  three (76 SpawnUnit, 20 SpawnDropUnit, 9 SpawnUnitWithEffect references). `import_hoh1.py
  campaign` now imports the tier copies of the 21 mapped units the levels reach and writes
  the map, without HoH1's loader, to `hoh1/tweak/hwp_unitmap.sval`;
  `HWP/Campaign/HoH1/UnitMap.as` rewrites those scripts' `UnitType` once per level by
  `g_ngp`, the thresholds HoH1 uses. Verified, plan-runs-ng 20261018-171057: NG+1 spawns
  warden_t2, whose whirlwind threw 80 bombs and whose ballista shot; NG+2 spawns
  vampire_t2, whose Bat Spray (needs NG+2, under 20% health, within 120 px; HoH2's
  conditionals handle `ngp`) fired 11 bats. GameLab's `mission` verb takes an `ngp`.
- **HoH2's `CompositeActorBurstSkill` never fires without an `anim-begin`.** HoH2 added
  `if (m_restrictions.AttemptUse()) { cooldown; return; }` to the no-begin path, and
  AttemptUse is true unless the fail-chance roll hits, so the burst is skipped every time
  (HoH1's version has no such check). Vanilla's two burst skills both have an anim-begin;
  HoH1's six (ice troll melee, ice elemental ranged, both ballista towers, the big arrow
  turret, the Warden's NG+ club and ballista) do not, so none of them attacked. The import
  maps them to `HoH1BurstSkill`, which inverts the fail chance when there is no begin
  anim. Verified: warden_t2 clubs and shoots (plan-runs-ng 20261018-171057, 'attack-2' and
  'shoot-4' scenes); plan-runs-b and plan-runs-d still pass. A burst skill also restarts
  its cooldown at every check out of range, so a fast boss that closes in rarely shoots
  (HoH1 does the same).
- **The firearms decoy taunts through `AlertActors make-aggro`**: `SetTarget(decoy, -1,
  true)`, and aggro < 0 always replaces the target unless the enemy is mid-attack
  (`CompositeActorBehavior.SetTarget`). Measured: all three brutes targeted it and two
  beat it to 19 % hp (plan-firearms-a 20261018-140742). A first failure was the test:
  brutes spawned behind a wall never saw anything.
- **`deploy.py modded-prod` never rebuilds `dist/HammerwatchPlus-All.bin`** (it calls
  build.py with `--no-all` and a module list). Copying the All bin after a deploy shipped
  the 2026-10-18 02:20 build until 17:20 that day; run `tools/build.py` (no arguments, no
  `--with-local`) first, then copy.
- **GameLab gotchas:**
  - A `[GL]` line over 15000 chars is dropped (Json.as EMIT_MAX). `trail` now sends its
    report in parts ("part"/"parts") and keeps up to 128 units; the NG+1 Warden's bombs
    overflowed both the old single event and the old 32-unit cap.
  - `e_cheats` is per process: after a scenario's `restart` step every `cht_*` command
    is refused ("can only be executed with e_cheats = 1") until it is set again.
  - When the console misses a line, the typed characters and Enter go to the game as
    hotkeys and can close an open menu; bots that use a window reopen it and retry.
  - `use npc_dyer` needs the town flag `mission_story_unlocked_dyer`; without it the
    unit's conditionals destroy a spawned dyer.
  - The Three Councilors' scythe casts whenever the player is within 100 px and then
    stands still; a node-to-node test keeps the player away from it.

## Pet follow, cat targets, Morale foes (2026-10-18)

- **Vanilla walking pets idle inside `range-idle` (100 px) and only chase past the
  `leash-range` (350 px).** An Idle pet whose pathfind fails picks a new idle target and
  never falls back to a straight walk (only `MovingToPlayer` does, and a failed search in
  that state puts the pet on the owner). PetWait parks the pet on the owner's last
  puzzle-free spot, often a corner of their path against a wall, where the pet's own
  search can fail: after the wait it stood 200 px off for 9 s (plan-pets-b
  20261018-144852). `PetWait::Rejoin` now sends it off in `MovingToPlayer` when a wait or
  a candle hover ends. Verified over 8 later pets-b runs.
- **The Gold Collector cat took the nearest pickup even when unreachable** and stood still
  on it, hiding every other pickup. Reproduced: gold dropped on a point with no route,
  nearer than the wood, and the old code never fetched the wood (pets-c 154346, 154624).
  A target it gets no closer to in 1.5 s is now skipped for 10 s (same decoy, 3/3 pass).
- **The farming wild plots are actors on another team** (`HWPLocalNPC`, `targetable
  false`). Morale counted any live other-team actor as combat, so a plot near the owner
  kept it off (pets-b 155331; reproduced with a plot spawned 70 px off, 160733). Morale
  and Stun now take only targetable, live, non-hazard actors within the radius
  (`Pets::Foe`, the same filter as vanilla `RandomEnemyApplyEffects`).
- **GameLab:** an object spawned on the player is gone at once (the smash pot landed on
  the player when the pet stood 24 px to its left); `pathfind ... nodes 0` does not always
  mean the cat cannot get there.
- **GameLab, unexplained:** a `teleport` onto the onion field's left groove (x -374) is
  followed by about 1.5 s of movement by (+52, -112) from every start point on it, with no
  pilot intent running and nothing in our scripts moving the player. The farming bot now
  tries the groove's plot units until a stand holds (plan-farming-a 163358, 163815,
  164143). Not seen with a walking player; not explained.

## Review fixes after the NG+ port (2026-10-18)

A /code-review xhigh on the work since 28b14c8 gave 15 findings, all fixed:

- **A reloaded town reuses unit ids, so a list of town units can point at another
  unit.** `HWP::Town::Units` keeps each unit's producer from when it was added, and
  `Live(i)` checks that the unit still has it. It replaces bare `Ours()` checks in the
  map markers, farming's plot visuals and fishing's traps. `Kept.Due` and `Placeable`
  accept a unit with no producer (a prefab child holding the id) without a null deref.
- **The pet bowl's `Kept` was `Set` every frame,** so it took on whatever unit held the
  id and `Due` never fired. It is now set only when `SpawnBowl` makes a new unit.
- **`Kept.Set` of an invalid unit** (the unit file is missing) now marks it failed. `Due`
  stays quiet until `Reset`, so the board isn't respawned and logged every 500 ms. The
  pet vendor has the same flag.
- **NG+ tiers:** `SpawnEnemyGroup` (the troll groups) now goes through
  `HoH1::TierFor` like the other spawners. NG+ is rounded with `int(g_ngp + 0.5f)`, as the
  game rounds it.
- **`Spawner::IsSpawnable` rejected `hoh1/actors/...`,** so strongboxes and abyss
  cracks on HoH1 floors found no pack members. The `hoh1/` prefix is now stripped before
  the checks.
- **Gold Collector cat:** moving more than 4 px also counts as progress. A path around
  a wall leads away from the target for a while, and the old check (distance only)
  skipped targets the cat was reaching.
- **Wave statue spot:** the clear-spot check ignores actors, pets and pickups. They move
  around, so each machine could pick a different spot.
- **`Market::Migrate`** marks worn items dirty and calls `SyncEquipment` when it rolls
  their modifiers. Fishing remembers a fish's signature only when the fish goes into the
  bag or is dropped for you.
- **Extra skill keys:** rebinding sets the key's held state from the keyboard, so there
  is no phantom Released.
- **GameLab:** `Emit` reads a too-long reply's id up to its closing quote, since an id
  may hold a comma. The `cursor` verb's local is renamed off `set`. `docs/generated/verbs.md` is regenerated.

- Verified in GameLab after the fixes (20261018): mod-all 175043, mod-core 175056,
  mod-wavemode 175108, mod-goldpet 175121, mod-fishing 175133, plan-pets-a 175146,
  plan-pets-c 175727, plan-farming-a 175932, plan-farming-b 180259, plan-fishing-a 180605,
  plan-fishing-d 180735, plan-runs-ng 183037, plan-runs-d 183341, plan-pets-b 183535,
  plan-runs-b 183829. Two first tries failed on bot geometry, not on the fixes, and passed
  on retry: in pets-b 175413 the pet followed (2.5 px off) but no clear 150 px walk was
  found; in runs-b 183228 every spike hit the player or timed out before a wall.
- **Trinket map web app** (https://claude.ai/artifact/5BP7XozLjkK9N445LKCYw9, built from
  scratchpad files outside the repo) was reviewed too. Its data was clean: no duplicate ids,
  set items all resolve, and every grouping set exists. Four page bugs were fixed and checked
  in jsdom against the old build. (1) Another viewer's verdicts were dropped while you typed
  a note. (2) Two quick edits lost the first one. (3) A partial saved filter in localStorage
  left the page empty. (4) Without the shared store, the verdict dropdown dropped changes
  silently. Orb of Restoration is now flagged as flat (+10 mana regen).
- **Trinket map, second review** (`/code-review xhigh`, 15 findings, all fixed; page version 3).
  Verdict writes now run one at a time per trinket, so a Reset can no longer race a change.
  A change that fails to save is rolled back instead of staying on screen. Live updates
  wait while a pointer is down or a note is being typed, and focus returns to the rebuilt
  control. Saved filters accept only known keys. Notes are capped at 2000 characters and
  flattened to one line in the copied to-do. A failed copy is reported. The "Note added" label
  shows only when there is a note. Three HoH1 set pieces with no HoH2 trinket (Circlet of
  Willpower, Wizard's Wand, Steady Greaves) now sit under their HoH1 set, not under
  "Missing, no set". Markham's Amulet/Mace/Wand, Decaying Hand and Pickled Eye are now
  flagged flat (52 HoH2 trinkets with flat values). The lang files now decode strictly
  (no U+FFFD patching), with identical output. 43 jsdom checks pass on the new build.

## Firearms clip and guns (2026-10-18)

Built the firearms clip, the reload rework, the rifle rework and the pistols
(`mods/firearms/README.md`, design in `docs/design/firearms.md`). Facts found on the way:

- **An item's `ModifyStack` never applies; a buff's does.** `PlayerRecord.RefreshModifiers`
  runs `modList.ModifyStacks(player)` (PlayerRecord.as:1886) after buffs, stacks and skills
  are in the list but before the equipment loop. A gun therefore grants a marker buff
  (`Modifiers::Buff`, freq 250) that carries the `add-max`. Verified: the rifle clip reads
  30/30 and the pistols 12, 24 dual (GameLab `plan-firearms-guns`, 20261018-181338).
- **`ActorBuffStacked` keeps the def it was built with** (ActorBuff.as:466). The modified
  def must exist before the first stack is made. The Reload skill carries a
  `ModifyStack add-max 0 0` for that.
- **Lose-effects at 0 stacks run at intensity 0, and `AddStacks.Apply` returns false at
  intensity â‰¤ 0** (AddStacks.as:59). Before the fix, an empty clip never started its reload.
  An effect-list dict `<vec2 name="intensity-set">1 1</vec2>` placed first fixes it
  (verified, `plan-t14`).
- **`conditionals` is an OR of groups; the tokens of one `conditional` array are ANDed**
  (Conditional.as:770-795, `CheckConditionals` returns true on the first passing group).
  A two-group "has marker" + "clip ge 1" gate fired whatever the marker said: 4 rounds a
  cycle instead of 2. Flattened into one array, it measures 2.
- **Dash restarts a stack timer.** A `TriggerEffect` with `trigger: dash` on the
  Reloading buff adds a stack at max. With `add-reset` that restarts the 1.6 s timer.
  Measured: refill 1.75 s without a dodge, 2.92 s with a dodge 0.9 s in (`plan-t14`).
- **`dbg_cht_ignore_equipment_requirements` doesn't survive a level load.** The cvar
  still reads 1, but the script global it sets (`g_dbg_ignore_equipment_requirements`,
  EquippedItems.as:1) is back to false, so `equip` refused a shield. Set it after the level
  loads, 0 then 1 so the callback runs (verified: set at scenario start, it refused;
  set this way on the floor, it took).
- **`equip <id> 1` gave GenerateItem null for `offhand_lantern_01`.** Pass the quality
  by name (`common`), as the other checks do.
- **GameLab latency:** one `gl` call takes about 0.3 s. Clip checks hold the trigger
  briefly and poll; one-frame checks use `gl multi`.
- **Flaky checks, not regressions:** one t14 read of a no-dodge reload took 3.61 s
  (beside 1.75 s), so the check now compares medians of 3 trials. `plan-firearms-a/b`
  failed once on the decoy pull, the jetpack landing (22 px off, beside a wall) and one
  missed frag damage text. They had failed the same way before this work (13:09, 13:11,
  13:48 runs) and passed on rerun (20261018-182344, -182615).
- **Assumed, not measured:** the shot spread (only rounds were counted), how often the
  "cant" voice plays when holding fire on an empty clip, and how the clip's HUD icon looks.
- **Purple orbs are skill spheres** (Behaviors/SkillSphere.as, GUI/Menus/GiveSkillSphereMenu.as;
  read from source, not run). A sphere offers 3 picks from the `modifier-skills` of learned
  skills, each at its next level, and no two share a parent. A reroll costs Shadow Curse
  `min(100, ScaleShadowCurse(12 + 7 Ã— rerolls used))`. Across all 196 vanilla orbs the
  levels are Uncommon or Rare, never Epic (counted from the class data by the planner seed
  script). So a new orb only enters the pool once its parent skill is learned.
- **The class planner** (https://claude.ai/artifact/GUXggQqycAoQRiJ6G1Nwv3) now holds every
  vanilla class's kit and orbs, read from `gamecode/datatables`: 198 orbs, 499 orb levels and
  400 skill levels, each with its quality and `description-params` values. Each class also gets a draft
  4th spec with 2 orbs, all at status "idea". Nine skill files no class lists are cut content
  (see `docs/design/firearms.md`).
- **How orb levels read** (PlayerClass.as LoadParams and LoadSkillDescriptionParams, from
  source). A level with no `quality` takes the orb's own `quality` (default common), not the
  level before it. A `description-params` entry is `[key, (formatting bool), label, v1, v2â€¦]`.
  Level L shows `v[min(L, n) - 1]` (Modifications.as AppendSkillDesc). Two entries can share
  a key: the label list shows both, and the `%key%` in the text gets the last.

## Firearms specializations (2026-10-19)

Built the Marksman and Demolitionist specializations and the base kit's orbs from the
planner's records (`mods/firearms/README.md`). The two base passives are left to the owner.
Checks: `plan-firearms-a` 20261019-020024, `-b` 20261019-015752, `-orbs` 20261019-015546,
`-guns` 20261019-020328, `plan-t14` 20261019-020430, `mod-firearms` 20261019-020613, all PASS.

- **Textures must be power-of-two** (verified). A 216x24 icon atlas logged
  `[ERR] Texture sizes (216x24) should be power of two`, and the game then hung after script
  compile: no main menu, exit 1, no crash dump (run 20261019-010915). Padded to 256x128 and
  256x32, it passed (20261019-011513). `tools/make_firearms_icons.py` pads every atlas.
- **Skill tag bits are below 31** (verified, the module logs them): `hwp_firearm` and
  `hwp_explosive` are bits 21 and 22 with the plan scenarios' mods, 18 and 19 with
  `mod-firearms`'s. The bit depends on which mods are loaded.
- **`castat` doesn't aim a skill with `update-aim`.** `PlayerSkillDirectional.Update`
  re-reads the player's aim every frame up to the castpoint, so the shot leaves along the
  idle aim. Run 20261019-013119: `castat` Snipe hit nothing; a held skill3 press hit the same
  dummy (106). With the aim held by `gl input` (no button), `castat` still missed
  (20261019-013510, cause not found). The bot presses the skill's button instead
  (`aimed_cast`). The same applies to a press shorter than the castpoint: the rifle's 80 ms
  castpoint against a 60 ms press sent the round the wrong way (Focus never rose).
- **A projectile thrown along a direction lands 100 out** (IProjectile.as:49-57: GetTargetPos
  is from + dir Ã— 100, which GroundBouncing `hit-target` flies to). Explosive Reload's
  magazine missed a dummy at 45 with its 48 radius; one at 100 is hit.
- **A round that stops at its first hit stops on anything between.** The old Snipe pierced
  6, the new one 0 without its orb. On one floor it hit nothing on a wall-free line, so the
  bot's `clear_dir` now also rejects a line with a `Breakable` or actor within 12 of it
  (gl `near`). The `shootproj` bisect (20261019-012906) showed the round itself was fine.
- **Over-Reload bug, fixed.** A perfect is judged when the Reload cast starts, while the clip
  is still empty, and the dry-clip clear removed the bonus on the next frame. Before: clip
  30/30 after a logged perfect; after: 36/36 (`-orbs` runs 014544 and 015016).
- **Shared unit regression, fixed.** Assault's Stun Grenade fired `grenade_stun.unit`, which
  had become the Frag Stun orb's include and lost its damage. The Frag orb now has
  `grenade_frag_stun.unit` and Assault's file is back as it was (`-b` PASS).
- **Timing in checks:** a level 1 stun lasts 1 s from the landing, about 0.8 s after the throw.
  Reading the dummy's buffs from about 1.5 s saw nothing; watching from 0.2 s sees stun and
  slow.
- **New verb** `gl orb <orbId> [times|down]`: the skill sphere's `SkillTempUp` /
  `SkillTempDown` (Verbs_firearms.as). `SkillTempUp` ignores `blocked-by-skills`, so the bot
  takes each grenade orb back down before the next one.
- **Interpretations to confirm with the owner** (the planner left these open):
  - The rocket costs 6 mana, no rounds.
  - Quad means 4 missiles in quick succession at a fraction of the damage and radius.
  - Over-Reload on a manual Reload (owner, 2026-10-19): see the follow-up below.
  - Headshot keys on a global "next hit" flag set by the Snipe round.
  - Elemental Shrapnel is a custom stat that every explosive reads, but not the magazine:
    penetration scales with intensity, and the magazine's intensity is its round count.
  - Ordinance Hoarder: cooldowns run 1/(1+x) faster. It banks a charge per full cooldown
    while the skill is ready.
  - Gas is ignited by fire.
  - The Stun grenade stuns and slows (bosses immune to stun are still slowed).
  - Overpacked's planner record repeats an uncommon level.
  - Magic Missile reuses the ice and fire effects; there is no blue-fire asset.
  - Dual pistols throw the two magazines one after the other (owner, 2026-10-19), half
    the rounds each.
  - The old doctrine skill files (flashbang, decoy, tube, jetpack) stayed on disk, unlisted.
    Removed after the review below.
- **Assumed, not measured:** how Focus and Hoarder charges look on the HUD, and how the
  Over-Reload ring reads at a glance (only its log lines were checked).

### Follow-up: manual Over-Reload, dual magazine throw (2026-10-19)
The owner asked for Over-Reload on a manual Reload too, capped at what a perfect reload of an
empty clip gives, and for dual pistols to throw their magazines one after the other.
- **Manual Over-Reload.** A Reload cast that starts outside the automatic reload is itself the
  timed reload: a 200 ms window in the second half of its castpoint (550 ms), on the same
  ring. A second press inside it is perfect and jumps the cast to its castpoint
  (`m_castingT = m_castpoint - 1`, so the cast lands the next frame). A press outside it, or
  no second press, is not perfect and clears any bonus. The bonus buff replaces the one held,
  so the clip max stays magazine + 6/9/12 (measured: 36/36 after two perfects in a row).
- **A press during a cast never reaches the skill** (`PlayerTargetingHelper.as`: an active
  skill returns before `Activate`). So the module reads the button itself:
  `Player.m_targetHelper.GetSkillInput(skill).Down`, edge-detected, since `Pressed` lasts one
  frame and gamelab-hands writes input from its own `UpdateFrame`. Verified: the bot's second
  `gl input ... skill1` lands as "manual perfect at 462/550 ms".
- **Fixed:** after Reload was pressed during the automatic reload, the ring reopened with a
  new window until the cast landed (the reloading stack drops at the castpoint, not at the
  cast's start). The window no longer opens while a Reload cast is under way.
- **Dual magazines in turn.** The Reload timeline has a second entry, `650 cast2`, holding
  a `HWPFirearmsThrowMag` with `second`. The cast throws the main hand's magazine and keeps
  the other half of the rounds per owner unit for it; the two land 8Â° either side of the aim.
  Measured gap: 99 ms (scene 26136 â†’ 26235 ms).
- Runs, all PASS: plan-firearms-orbs 20261019-091445 (new flags
  `explosive_reload_dual_in_turn`, `over_reload_manual_perfect`, `over_reload_capped`,
  `over_reload_plain_clears`), plan-t14 20261019-091715.
- **Pistol magazine 12 â†’ 10** (owner, 2026-10-19): `GunMarker glock_main/glock_off 10` in
  buffs_firearms.sval, so dual pistols share 20. plan-firearms-guns 20261019-095245 PASS
  (clip max 10 / 20 / 10, rifle 30); the planner's weapon records are updated to match.

### Code review fixes (2026-10-19, /code-review high on all the firearms work)
- **Over-Reload gave Explosive Reload a free magazine.** A perfect on the automatic reload
  topped the clip up two frames after the Reload cast started, so the magazine thrown at
  the castpoint held a full clip. Now every perfect jumps the cast to its castpoint
  (`OverReloadState.Perfect`), so the cast's list (the throw first) reads the clip before the
  top-up. New flag `over_reload_no_free_mag`: no magazine thrown by a perfect auto-reload
  with Explosive Reload on (plan-firearms-orbs 20261019-102349).
- **Critical Aim lost Focus on a blocked round.** `NewProjectile.HitUnit` destroys a round an
  actor's `BlockProjectile` stops without `OnHit`, so counting every hitless `OnDestroyed` as
  a miss wiped Focus. Focus is now lost only on `OnMiss` (range out) and `OnCollide` (a
  non-actor). **Ordering found in the fix:** a range-out runs `m_unit.Destroy()`, and so
  `OnDestroyed`, *before* the `OnMiss` loop (NewProjectile.Update), so `OnDestroyed` must not
  mark the round done. The first try did, and `focus_lost_on_miss` failed (run
  20261019-101136); fixed, PASS 20261019-101525.
- **The Over-Reload bonus expired after 120 s.** A buff always counts down (ActorBuff.Update
  `m_duration -= dt`), so `perfect_reload_N` now lasts 2 000 000 000 ms (about 23 days).
- The per-frame ClearPerfect on an empty clip is gone: the clip's lose-effects already remove
  the bonus (`over_reload_lost_when_dry` still PASS). Marker and skill ids are hashed once.
- `gl targets` reports `count` (all matches) and `truncated`, as CLAUDE.md asks.
- Bot: log waits read from a byte offset and sleep 20 ms between polls instead of re-reading
  the whole log in a busy loop; the automatic-reload press no longer subtracts the elapsed
  time twice; the frag test picks its second spot as far round as the open directions allow
  (the blast is 128, not 56); a duplicate dummy clear and a crash on an empty cost list fixed.
- **Removed** the unused Flashbang, Decoy, Jetpack and Grenade Tube skills, their units
  (`decoy.unit`, `grenade_flash.unit`, `tube_shell.unit`), lang strings and icon entries;
  `info.xml` describes the current specs. They remain in git history (a8d9803).
- Not changed: stack defs are still looked up by path each frame (cheap next to the buff
  scan that was removed).
- Runs, all PASS: mod-firearms 20261019-101106, plan-firearms-a 20261019-101525, -b
  20261019-102052, -orbs 20261019-102349, -guns 20261019-102615, plan-t14 20261019-102717.

## Re-pin to 25932569; firearms bullets and the clip across floors (2026-10-19)

- **Steam updated HoH2 to build 25932569.** Re-pinned at the owner's request
  (`tools/pin_build.py --reason`), `bootstrap.py --force`, then `bootstrap.py --record` to
  rewrite `gamelab/manifest.json` (the verify step fails on every changed tree until then),
  `env_link.py`. Doctor green; smoke null-payload 20261019-121048 and mod-firearms
  20261019-121105 PASS on the new build. Verified: `GameModeSpawnPlayer` unchanged
  (`AGameplayGameMode.as:1079`).
- **A texture that isn't a power of two hangs the boot.** A 6x6 `bullet.png` logged
  `Texture sizes (6x6) should be power of two` and the game never reached the main menu
  (look-firearms-anims 20261019-122919, `main menu never loaded`). 8x8 boots.
- **Effect params named `r`/`g`/`b` don't work as sprite colors.** `color-r="r"` rendered the
  slug cyan (red 0, look-firearms-anims 20261019-124336); renamed `colr`/`colg`/`colb`, brass
  as intended (20261019-124614). `tr`/`tg`/`tb` worked for the trail. A projectile passes
  params to its effect through the behavior's `effect-params` dict.
- **Player buff stacks carry across floors.** Going from floor 1 to 2 of `dark_citadel`
  (`hwp finishlevel`) the new player unit already held the clip's 25 stacks
  (mod-firearms-clip 20261019-124230: `clip kept 25/30 (had 25, level 2)`). So the old
  fill-on-every-spawn was a free reload per floor. The module now fills only in the village
  and on the first spawn of a run's first floor (`MissionManager::GetCurrentLevelNum() == 1`,
  `g_inTown`), else keeps the count.
- **The spawn hook missed a new character's town spawn.** After `gl char hwp_firearms` in
  town no fill was logged and the clip read 0/30 (look-firearms-anims 20261019-123319). A
  unit-id watch also missed it (the new unit took the old id, mod-firearms-clip
  20261019-123825); watching the `PlayerBase` handle plus the record's class id catches it
  (20261019-124230: `clip filled 30/30 (had 0, level town)`). Assumed, not measured: at the
  new unit's first frame the record still names the old class.
- **A failed `log_has`/`log_lacks` step doesn't stop a scenario**, and both scan the whole
  pass log, so `log_lacks` after an earlier legitimate match fails. A watch run's long
  `sleep` doesn't notice the game closing; stop the runner and `gamelab reset`.
- Instant shots: `PlayerSkillDirectional` fires timeline events at 0 ms on the first update
  (`PlayerSkillDirectional.as:88-97`); every gun's castpoint and first timeline entry are 0.
- Reload's mana cost is 0 in data and measured: `mana 60/60` before and after a Reload cast.
- **Sound events: names in the data aren't proof they exist.** Seven of 28 candidate firing
  sounds named in the game's own files did not resolve (`Resources::GetSoundEvent` returned
  null), every one an uppercase `event:/SFX/...` path (e.g. `SFX/Character/Classes/rogue/flashbang`,
  `SFX/UI/UI_Click`); the lowercase `event:/sfx/...` ones did (mod-firearms-sound
  20261019-125628, then all 28 after the swap in 20261019-125819). A mod can't add a sound
  (no FMOD banks in the unpack), so `hwp firearms sound` (cheat) plays the candidates as a
  three-shot burst in watch mode for picking by ear; lab mode is muted.
- **Assault's Stun Grenade removed.** The reworked Assault is Double Barrel Burst plus
  Adrenaline; the old stun grenade was still in the subclass list, a fourth active on the bar.
  plan-firearms-b 20261019-130113: Assault's actives are reload, frag and burst. Frag's Stun
  Grenade orb keeps the stun buffs and `grenade_stun_flash.unit`.
- **No pitch control for a sound.** `SoundInstance` exposes Play, PlayTracked, Stop,
  SetPosition, SetVolume, SetParameter, SetPaused, SetLooped and SetTimelinePosition, and
  nothing else (`gamecode/assets/hwr2_api_strings.txt`), so a mod can't pitch a game sound down.
  SetParameter only drives the parameters an event was authored with (assumed: none checked).
- **Gun sounds are the user's picks** from the game's banks (heard on a web page of the
  decoded samples): rifle and Burst `bandit_rogue_bomb_bounce`, pistols `grenade_bounce`,
  grenade launcher `grenade_throw`, sniper `ballista_shoot_hit`, launcher `fire_ball_cast` (Quad:
  `magic_missiles_cast` on each of its 4 timeline casts), rocket blasts `fire_ball_explode`,
  Fat Boy `fire_blast`, round hits `item_metal_small_2`. All resolve (mod-firearms-sound
  20261019-134648). Reload sounds are script (`Combat.as` ReloadSounds): `doors/unlock` when a
  reload starts (the reloading stack or a Reload cast short of its castpoint), then
  `buttons/lever_on` 250 ms before it ends, held back while an Over-Reload window is still to
  come, or `buttons/lever_off` on a perfect reload and no lever on. Measured in
  plan-firearms-orbs 20261019-134726: every reload logged an unlock and then one lever, off for
  each of the 3 perfects, on for the misses and plain reloads, including Dodge Reload Skip.
- **More picks (2026-10-19, from the sound page):** EpiPen plays `rogue/grenade/grenade_fuse`,
  full for 1 s, faded to 0 by 2 s and stopped (`Combat.as` StartEpipenSound; the fuse runs 3.9 s);
  the Frag Grenade throws with `bandit_rogue_throw_bomb` (its old `throwing_knives_throw` is not
  in the bank's event list, so it was likely silent: assumed, from the list, not heard); placing
  a turret plays `ui/build`. The fade is measured: the hiss stopped at 2013 ms
  (plan-firearms-orbs2 20261019-205713). All three events are in the bank's event list; none was heard in game. Still Claude's picks, not the user's: the
  grenade, Explosive Reload and shell blasts, the incendiary fire, the frag bounce, the gas loop,
  the turret's shot (the rifle's sound).

## Firearms Engineer, Assault checks, the pistol arm (2026-10-19)

- **The Engineer subclass** (`hwp_firearms_engineer`): Deploy Turret (`engineer_turret.sval`,
  `Skills::PlayerSkillPosition`, a TargetAOE cast that spawns `units/turret.unit` where aimed)
  and My Turret! (`engineer_myturret.sval`, passive). The turret is `HWPFirearmsTurret`
  (`Turret.as`, a `PlayerOwnedActor`): it wears down over `decay` (30 s for the whole bar),
  and the owner within 10 m repairs it, raises its damage and feeds it elemental rounds
  (Elemental Belt-Feed), with a `turret_glow` buff as the look.
- **A summon reads its owner's skill binds through `-bind` keys.** `PlayerOwnedActor.FetchData`
  goes to the owner after `PrepareSkillFetchData(weaponInfo)` (the crusader's `hp-bind` does
  the same). Verified: the turret logged `100 hp`, `a shot every 600 ms` from Deploy Turret's
  binds (plan-firearms-b 20261019-144539).
- **One summon of a kind unless a modifier says more.** `Player.Update` resets
  `m_maxSummons = 1` for each unit producer every frame, then destroys the oldest above the
  cap. `Modifiers::ModifySummons` (`unit`, `add-max-num`) raises it: Second Turret keeps two,
  and a third placement replaces the oldest (plan-firearms-b 20261019-144539).
- **`CompositeActorBehavior.m_hp` is a fraction (0..1)**, and its `Damage()` calls
  `dmg.Attacker.DamageActor(this, dmg)`. `PlayerOwnedActorImpl.DamageActor` forwards to the
  player and skips the buff `DamageMul`, so the turret's boost scales its own damage in a
  `DamageActor` override.
- **`AnimationLoopType::Hold` at the end of a shot is the rest pose.** The wand shot
  (`attack_wand.anim`, 0.45 s, read from the ozz header) has the arm out on its first frame
  and down by its last. Holding the end looked the same as lowered (plan-firearms-arm
  20261019-143933 frames). `PlayAnimation3D` takes a trailing `animSpeedScale`, so the hold now
  replays the shot from its start at speed 0.0001: the arm stays up, and comes down by playing
  on at full speed (plan-firearms-arm 20261019-144417, the "arm held" and "arm lowered" frames differ:
  gun raised vs at the side). Assumed: the off-hand's `attack_offhand_handcrossbow.anim`
  (0.6 s) also starts arm-out; only the main hand was looked at.
- **The pistol arm comes down** 2.0 s after the last shot, at once on a dodge (logged
  `skill 1404514473`) or a reload (plan-firearms-arm 20261019-144417).
- **Bots: hold a press past the timeline.** Burst's second shell aims at 200 ms, where the
  press points; a 121 ms press sent it nowhere (plan-firearms-b 20261019-143401). The bot holds
  for max(castpoint, last timeline entry) + 120 ms. Deploy Turret's 50 mana regenerates at
  1.1/s, so the bot gives mana (`cht_give_mana`) between placements.
- **`actorbuffs` gives no name for a buff without one**; the turret glow is found as the
  300 ms buff.
- Assumed, not measured: 1 m = 16 px; the turret's base 100 hp, 0.6 of the rifle round's
  damage, armor 20 and 200 px range; NEAR = 10 m. Our Turret! (any player near) needs a
  second player and is not run.
- **Over-Reload is now +5/+10/+15 rounds** (the planner's numbers; it was +6/+9/+12). The
  bot still expected +6 and plan-firearms-orbs 20261019-145155 failed on 35/35; the game was
  right and the bot was fixed (plan-firearms-orbs 20261019-145513 PASS).
- Runs on this work: mod-firearms 20261019-144527, plan-firearms-a 20261019-144935 (the
  picker shows four doctrines), plan-firearms-b 20261019-144539 (Engineer, Assault: two
  shells at x1.2 within 80 px, Triple Barrel three, Dragon's Breath ground, a kill gives
  Adrenaline), plan-firearms-guns 20261019-145404, plan-firearms-arm 20261019-144417.
- Against a fresh planner dump after the user's orb-level changes: every
  firearms orb's level qualities match the svals (`orb_levels` check against a fresh
  dump), and Assault is Double Barrel Burst (2 shells, 200 each, +20..100% within
  5/5/7/7/10 m, 5/5/6/6/7 mana, 5 s) plus Adrenaline.

## Firearms reload rework, faster rounds, drops in the demo (2026-10-19)

- **The Reload cast is now the reload.** Before, it refilled at a 550 ms castpoint and the
  2 s cooldown came afterwards. The user wanted the whole recharge to pass before the refill,
  a dodge to cancel the reload, and no reload on a full mag. `fs_reload.sval` is now
  `HWPFirearmsReload` (Combat.as), a `PlayerSkillDirectional` subclass:
  - The castpoint is the level's recharge, 2000/1800/1600/1400/1200 ms.
  - Each upgrade sets castpoint, blocking, update-aim and timeline to match.
  - The cast list, Explosive Reload's throw and then the refill, lands at the castpoint;
    the dual Glocks' second magazine follows 100 ms later.
  - While the cast runs, `m_cooldownC` holds the time left, so the HUD icon sweeps over the
    reload. Any end of the cast sets it to 0.
- **Skill facts this rests on** (decompiled source):
  - `PlayerSkillDirectional.Deactivate` starts the cooldown only when the castpoint was
    reached, so a cancelled cast sets none.
  - `PlayerSkill.m_cooldown` is not clamped to the castpoint; `ActiveSkill.Initialize` is the
    one that does `max(castpoint, cooldown)`.
  - The dash has `ignore-blocking` (`players/attacks/dash.sval`).
    `PlayerTargetingHelper.CheckUseSkill` activates it, then `CancelOther` calls
    `Deactivate()` on every other active skill. That is how a dodge cancels the Reload cast.
  - `ActiveSkill.Activate` sets `m_castingC` (at least 1) before `CancelOther` runs. So when
    the Reload's `Deactivate` sees a casting skill of type Dash, the cancel came from a dodge.
  - Skill upgrades are per-level param layers (`PlayerClass.as`, `m_levelParams`).
- **Dodge rules:**
  - A dodge during a manual Reload cancels it and leaves the clip as it was.
  - With Dodge Reload Skip, the dodge runs the rest of the timeline (`m_timeline.Update(GetLength() + 1)`)
    and refills at once.
  - An empty clip's automatic reload (the `reloading` stack, 1.6 s) still restarts on a
    dodge. That is the planner's "if you are out of bullets, it will automatically start
    reloading again".
- **No Reload on a full clip:** `CanActivate` refuses when the clip is at its modified max,
  and plays the class's `cant` voice line.
  - It also refuses during the automatic reload unless Over-Reload is learned. Then the
    press is that reload's timing try. A missed try now ends the cast, because the full-length
    cast would outlast the automatic reload.
  - Assumed, not measured: cooldown reduction (`m_modCooldownMul`) no longer shortens the
    reload. Skill and cast speed do, because the castpoint is in skill time.
- **Bullets fly 2x as fast, same range.** Every gun round has its speed doubled and its ttl
  halved: rifle 52/240, pistol 44/180, sniper 64/300, turret 52/240, shotgun pellet 40/132,
  and the 24 elemental rounds through `%block Round`. Hits were checked at 50-90 px and by
  the turret (plan-firearms-a 20261019-152511, plan-firearms-b 20261019-152730 PASS).
- **The rounds have no trail now** (`tools/make_bullet_art.py`). Missiles and the GL shell
  keep theirs.
- **Console item cheats can't give mod items.** `cht_spawn_specific_equipment` runs in the
  [menu] script context, where there is no player and the mod's BaseItems are not loaded.
  Character creation also resets `e_cheats`. The demo therefore turns cheats on after
  `wait_phase`. It drops every firearms gun with the new `gl dropitem <baseItemId> <quality> [dx dy]`
  verb (gamelab-hands, `Item::DropItem` on an `Equipment::Generator` item).
- **The earlier demo's setup silently did nothing:** level-up, materials and spare guns all
  ran with cheats off.
- **A castpoint of 0 skips the mana cost.** `PlayerSkillDirectional.Update` calls
  `UsePoints` only when `m_castingT` moves from below the castpoint to at or above it. A cast
  starts at 0, so with castpoint 0 that never happens, while the timeline still fires its
  entry at 0. The rifle launchers had been firing free since 68551d8 ("instant shots").
  - plan-t14's `launcher_costs_mana` caught it (20261019-153855 and 20261019-154500).
  - A probe with only the launcher kept mana at 60.000, both on HEAD and with the new work
    (probe-launcher 20261019-155204, 20261019-155045).
  - The launchers now use castpoint 1: 60.000 -> 56.436 after a press (probe-launcher 20261019-155332).
  - The other castpoint-0 firearms skills cost no mana.
- **Bot lesson:** a gl call sent right after an `hwp` console line can take about 3 s. The
  manual Dodge Reload Skip check now reads the clip max first, and passes on the game's
  `reload: dodge at N/M ms finishes it` line.

## One pistol for either hand, the reload icon, quiet held trigger (2026-10-19)

- **An item's slot is its base item's.** `Equipment::Item.GetSlot()` is `baseItem.slot`
  (Items/Equipment.as:145), and the bag click equips by that slot
  (EquipmentInventoryWidget.OnClick -> EquippedItems.Equip(item), EquippedItems.as:161-190).
  No slot means "either hand". So the off-hand pistols `hwp_glock_oh_0N` stay, as twins
  that never drop or sell: spawn-chance 0, ilvl 999-999 (GenerateBaseItem filters on ilvl,
  EquipmentGenerator.as:197), no `armory` tag. `gl equip` still makes them
  (Generator.GenerateItem skips both filters).
  - A bag click runs core's new `HWP::Bag::OnEquip` callbacks first (BagSlots.as,
    `HWPEquipmentInventoryWidget.OnClick`). Firearms swaps `item.baseItem` for the twin
    when the main hand is full and not two-handed and the off hand is free.
  - The swap is safe after Finalize. `GetModifiers` picks an item mod's main- or
    off-hand list from `baseItem.slot` on every call (Equipment.as:147-161), and
    `ItemModifier` loads both lists for any handed mod (Equipment.as:540-551).
  - Back in the bag, a twin turns into the main-hand pistol (Pistols.as, 4 times a
    second). That covers an unequip and a two-hander bumping it off.
  - Verified: mod-firearms-pistols 20261019-162530. Two pistols clicked in the bag went
    rifle -> main hand -> off hand (`hwp_attack_glock` + `_off`). Unequipped, the off-hand
    one came back as `hwp_glock_mh_01` and went back on the off hand.
- **Equipping is a menu accept on the bag slot.** The Equip hint isn't clickable
  (`navbar` clickable `[true,false,...]`). A bot hovers `equipment-inventory <i>` and
  posts Enter. A slot's index is its place in `EquipmentInventory.m_items`, and an
  unequipped item is appended.
- **The automatic reload's look for the Reload cast.** The HUD sweep on the reloading
  icon is the stack's `display-timer-radius`: `GetBuffIconDuration` = `m_timerTickC`,
  max = `m_defMod.m_timerTime` (ActorBuff.as:811-823). The new `reload_cast` stack uses
  the same icon. HWPFirearmsReload holds one stack while it casts and sets `m_timerTickC`
  to the time left each frame, with `m_defMod` pointed at its own copy whose timer is the
  whole cast. Verified: "cast icon on, 1967/2000 ms" and the HUD frame (mod-firearms-pistols
  20261019-162257, shot reload_icon).
- **Why a held trigger said "cant".** A repeating attack held down calls
  `skill.Activate` every frame (PlayerTargetingHelper.as:631-645). Activate calls
  `CanActivate()` with warn on (PlayerSkillDirectional.as:49), and the clip conditional's
  failure plays "cant" (PlayerSkill.as:344-349). `HWPFirearmsGun` (the 4 gun attacks)
  warns only while armed. It arms whenever the button is up (`GetSkillInput(this).Down`
  false, in Update) and disarms at the first warned check, shot or warning. Verified:
  7 s held through the clip running dry and the reload gave no warning, and a fresh click
  during a reload warned once (mod-firearms-pistols 20261019-162530).
- **Muzzles.** The pistols sit about 5-6 px either side of the unit's position, the main
  hand on the right (look-firearms-muzzles 20261019-161736, zoomed frames, six aims).
  `rotate-offset` turns (0, +y) to the aim's right (ShootProjectile.as:96-97:
  `addrot(offset, aim angle)`). So main-hand rounds use (0 6) and off-hand rounds (0 -6).
  The old offsets were Â±2 and had the main hand's rounds on the left.
- **Gun sounds with a volume.** `HWPFirearmsSound` is a PlaySound whose instance
  (`SoundEvent.PlayTracked`) gets `SetVolume`. The pistols now use the rifle's
  `bandit_rogue_bomb_bounce` at 1. The rifle is at 1.4. Assumed, not measured: FMOD
  treats an instance volume above 1 as gain (the lab is muted).
- **The lab town has no Skill Trainer.** Skills are learned at its `npc_skill_trainer.unit`
  (Town/SkillTrainer.as:19, `SkillUp`). Without one, a new Sniper's Sniper Shot can't be
  learned in the demo. The demo spawns the trainer next to the Subclass Picker. Verified:
  it opens with all six Marksman skills (probe-subclass 20261019-162631). Through `gl skill`,
  Sniper Shot lands on skill key 2 (probe-subclass 20261019-161323).
- **Demo:** watch mode is 2560x1440 now (`gamelab/env/settings/watch/HWR2.exe.cfg`). The demo
  also has five training dummies (normal x2, armored, magic, breakable) and two of each
  pistol tier.
- **A one-off crash on quit.** mod-firearms 20261019-162710 passed every step, then the
  game exited with 0xC0000005 while saving on quit. That left a dirty teardown. The same
  code then passed 3 times with clean exits (20261019-162913, -162925, -162937). One
  earlier run had the same exit code, with no firearms code involved (plan-pets-b
  20261018-132915). Treated as an intermittent engine crash at shutdown, not a bug in the mod.

## Items before vendors, the demo in one command (2026-10-19)

- **Why a vendor blocked a pickup.** `Player.GetTopUsable` returns the first usable in
  `m_usables` that CanUse. `AddUsable` keeps that list sorted by `UsePriority`, lowest first
  (Behaviors/Actors/Player/Player.as:135-167). A dropped item is 1 (Items/UnitBehavior.as:299),
  while NPCs, shops, chests, shrines and wells are 0. Revives and level exits are -1, and pyres
  and beacons are -5. So with a vendor and an item both underfoot, Use always talked to the vendor.
- **Fix: core reorders, no class swap.** `HWP::PickupFirst` (mods/core/scripts/HWP/Core/PickupFirst.as,
  run from CoreModule.UpdateFrame) re-sorts the local player's list each frame. It uses a stable
  sort that ranks an item between -1 and 0. A subclass of `Item::UnitBehavior` would not work:
  vanilla pets find items with `FetchUnitsWithBehavior("Item::UnitBehavior", ...)`, and that
  call's `includeInherited` defaults to false (api strings, MiniPet.as:284).
  - The same default means `mods/pets`' `FetchUnitsWithBehavior("Chest", ...)` (Pets.as:993)
    misses keys' `HWPChest`. Assumed, not yet measured.
  - Verified: mod-core-pickup 20261019-163842. With a Skill Trainer and a dropped rifle at the
    player's feet, `usables` listed `items/base.unit` on top, ahead of the
    `CompositeActorBehaviorNPC`. Use put the rifle in the bag and opened no window.
- **The demo setup is one typed command.** Typed console lines garble when the player presses
  keys while the harness types (demo-firearms 20261019-163131: `.unit` arrived as `.sunist`, then
  every line had a stray leading backtick, "No such cvar: `gl"). The runner gave up on a line
  with no reply and closed the game. The script API has no way to run a console line, so
  gamelab-hands has new verbs:
  - `setup <file>` runs every line of an sval array of verb lines in one frame
    (`gamelab/setup_demo_firearms.sval`, 27 lines). It replies with `failed` and the failed lines.
    The probe's `Fail()` counts failures (`g_fails`).
  - `cheats`, `levelup` and `points <skill|stat>` mirror core's `hwp` cheats.
  - `material all <n>` gives n of each material.
  - Verified: mod-core-pickup 20261019-163842 (`failed` 0). demo-firearms 20261019-163941
    (watch, 27 lines, 0 failed).
- `hwp levelup 20` from level 1 gives level 20, not 21. The old demo's "level 21" was wrong
  (its 16:31:48 log line says "now level 20").
- **Dummies hidden in the barricade.** The demo's dummies at dy -80..-100 stood inside the log
  barricade north of the lab-town start (mod-core-pickup 20261019-163842, shot after_use). They
  now stand in a row on the open road east of it, dx 110..230 (20261019-164119, shot after_use).
- **Rounds start at the gun tip.** ShootProjectile starts a round at
  `pos + dir * dist + offset` and clamps it to the first wall on the way (`RaycastClosest`,
  ShootProjectile.as:121-128). The guns' `dist` was 5, the body. Measured from frames, the
  rifle's tip is about 13 px ahead of the player's centre, the pistols' about 8-9 px, and both
  are held about 10-12 px up (look-firearms-muzzles 20261019-161736, look-firearms-tips
  20261019-164426).
  - First values: the rifle, its launcher, Burst and Snipe dist 14, the pistols 9. Every gun
    round's `effect-params height` is 11, up from 8.
  - Assumed, not seen: the frames show the guns, but every round had already left the frame
    by the time it was taken, even at timescale 0.1.
  - The rifle's round still looked as if it started too close in play. The round sprite is centred
    on its spawn point (rifle round origin "9 3.5", about 10 px long), so half of it was drawn
    behind the tip. Now: the rifle, its launcher, Burst and Snipe use dist 22, the pistols 12.
    `HWPFirearmsGunShot.ProduceProjectile` (Elemental.as) records where the last round started,
    relative to the aim, and `hwp firearms muzzle` prints it. Measured: rifle 22.0 ahead, pistols
    12.0 ahead and 5.2 to the side (look-firearms-tips 20261019-165353). Verified.
- **Snipe uses mana, not rounds.** sniper_snipe.sval lost its clip conditional and its
  `AddStacks -10`; it still costs 30/30/40/40/50 mana. Measured: clip 27 before and after one
  Snipe, mana 60 to 32 (look-firearms-tips 20261019-165353). Verified.
- **Snipe's laser dot.** Snipe is a PlayerSkillDirectional whose castpoint (650 ms) is the
  charge. `HWPFirearmsSnipe` (Combat.as) overrides `Update`: while `0 <= m_castingT < m_castpoint`
  it raycasts (`RaycastType::Shot`) from the player along `m_timeline.m_dirTarget`, up to
  `SNIPE_REACH` 300, and keeps `effects/laser_dot.effect` at the hit point or the end of
  reach. It destroys the dot when the cast ends and in `Deactivate`.
  - The texture is vanilla's 64x1 `player_white_singlepixel_gradient.png`, whose pixels 0-1 are
    only 15% opaque (alpha 38), so the dot was invisible until its frame moved to x 32.
  - Measured: "snipe: laser dot on, 199.5 out (hit)", and the frame shows a red dot on the tree
    trunk that the aim line hits (look-firearms-tips 20261019-165939). Verified.
  - Assumed: 300 is about the rifle round's range. The range record stayed 0.0 because every
    round in the measurement hit something.

## Gun hold, even pistols, turret radius, Hoarder HUD, demo orb and trainer (2026-10-19)

Status: measured where a run is cited; the rest says which run checks it.

- **The game's metre is 6 px** (`Tweak::PixelsPerMeter`, Data/Misc.as:15; `formatMeters`
  divides by it, Utils/Functions.as:777). The firearms notes assumed 16 px. That is wrong, so
  "10 m" was 160 px, about 27 m.
  - My Turret!'s `NEAR` is now 60 px, a true 10 m. The user saw the boost stay on after walking
    away. The demo's log shows it did switch off ("turret: unboosted" at 17:05:08, 17:05:14 and
    17:05:27, demo-firearms 20261019-170119), just far out.
  - plan-firearms-b's `myturret_only_near` places a turret 120 px out, sees no boost, then walks
    up and sees one (20261019-191214 PASS). Walking off at once failed (20261019-183730): no
    "unboosted" within 2 s of a 1.5 s walk, so the check now walks in.
  - Double Barrel Burst's close ranges (80/112/160 px, labelled 5/7/10 m) are left as tuned.
- **The arm hold covers every gun.** `AimHold` (Combat.as) only listed the two pistol attacks,
  so the rifle lowered after each shot. `GUNS` now lists the rifle, the epic rifle, both grenade
  launchers and both pistols, and `HOLD_MS` is 1000.
  - The rifle's `crossbow-2h` set plays `attack_2h_crossbow.anim`. Assumed: its first frame has
    the rifle up, as the wand shot has the arm out. plan-firearms-arm takes frames for both guns.
- **A held repeating attack drops the overshoot.** PlayerSkillDirectional.Update deactivates
  at `m_castingT >= m_skillLen` (:99), and the next activation starts at 0. So the cycle runs up to
  a frame long, and the right gun's gap back to the left one is longer than left to right.
  - Measured before the fix: gaps alternated 264/330 ms (look-firearms-batch 20261019-183547).
    PlayerTargetingHelper's restart of a held repeating skill (:629-646) comes a frame after the
    deactivation, so the shot at 0 fired a frame late.
  - `HWPFirearmsGun.Update` now restarts the held skill itself, in the same frame it ends. It
    carries the overshoot, capped at 100 ms (`CARRY_MAX`), into `NetActivate`, then calls
    `CancelOther`, `TriggerModifierEffects` and `m_timeline.Update` as the helper does. A `const`
    class property doesn't compile in AngelScript, so `CARRY_MAX` is a plain `int`.
  - The pistol cycle is now 600 ms, with shots at 0 and 300; it was 520 and 260.
  - `hwp firearms shots` prints the gaps between the local player's last 16 rounds. After the fix:
    `264 297 297 297 297 264 297 297 297 297 297` (look-firearms-batch 20261019-190049). Mostly
    18 frames, with a 16-frame gap about one in five, where it used to alternate 16 and 20.
- **Ordinance Hoarder on the HUD.**
  - SkillWidget dims the icon whenever its frame ring shows a cooldown (:333), and draws the
    whole ring when the skill is ready (:362).
  - `HWPFirearmsChargeHUD` (ChargeHUD.as, added by a `HUDConstructor` hook and drawn after
    HUDPlayer with its transform) darkens the part of the ring not banked yet. It uses the
    two-ended `DrawSpriteRadial(pos, sprite, time, a, b, color)` (the engine's API strings),
    from `HoardedSkill.m_progress`.
  - The charges' icon is now `<id>_shown`: every use ready, the stored charges plus one when the
    skill is off cooldown, removed at 0. `<id>` keeps the store with no icon.
  - Measured: plan-firearms-b `hoarder_icon_counts_all` (icon 2 ready, 0 on cooldown,
    20261019-191214). In look-firearms-batch 20261019-191742 the icon goes 2 -> 1 when a rocket
    spends the stored charge, and the ring starts banking ("slot ring shows a charge banking, 0%").
    Frame `ring_banking` (640x360) shows the rocket slot's ring dark with its icon bright; frame
    `ring_full` shows the whole ring.
- **Demo orb** (verified: two picks from one sphere, look-firearms-batch 20261019-183547 frame
  `orb_second`). `GameLabEndlessSphere` (gamelab-hands DemoSphere.as) is a SkillSphere whose
  `PickedSkill` clears the rolled picks and returns true instead of hiding the sphere.
  GiveSkillSphereMenu grants the orb only when it returns true (:266-287).
  The unit is gamelab/skill_sphere_endless.unit.
- **A spawned Skill Trainer sells tier 0 only.** NPCs get `ShopLevel` (an `[Editable]` field,
  NPCBehavior.as:244/431) from their town building, and the trainer opens tiers up to it
  (WindowSkillTrainer.as:192/255; tiers 0-4). The new verb `shoplevel <filter> <level>` sets it;
  the demo setup sets 4. Frame `trainer` (look-firearms-batch 20261019-183547) shows no locked tier.
- **Double Barrel Burst's close bonus** is now x1.5/2/2.5/3/3.5, up from x1.2-2.0, because the
  user asked for much more. It is still a step at close-range.
- **A unit spawned on a standing player is not a usable** until a collision starts: usables are
  added in the unit's `Collide` (SkillSphere.as:6-17, NPCBehavior.as:341) and dropped by the
  player's 250 ms `IsInside` sentinel (Player.as:1009-1019). After the demo setup, a trainer and
  a rifle dropped at the player's feet gave `usables []` until the player stepped off and back
  (diag-usables 20261019-185932). mod-core-pickup now takes that step (20261019-190009 PASS).
- **`hwp levelup` and `hwp skillpoints` need `e_cheats 1`** ("cheats are off",
  look-firearms-batch 20261019-190049); `gl setup`'s `cheats on` line is what the demo uses.
- **The demo's watch run ends after its 3600 s sleep** (demo-firearms 20261019-170119, 3638 s).
  The game closes then, even mid-play.

## Firearms class showcase (2026-10-20)

- **The class list draws one 32x32 figure per class** from the class's `class_showcase.png`
  (vanilla packs all classes in one 128x128 sheet of 32x32 cells, each a figure facing the
  camera on a 16x16 shadow disc of (0,0,0,126), feet at y 30). The Firearms one was a gun in a
  ring; it is now the starting outfit with a pistol.
- **The character screen's paperdoll is close to 2x** in a 640x360 lab shot (2x2 blocks agree
  about 80 %), so a 2x2 mode downsample gives a 12x23 figure, the size of vanilla's. The town
  view is too small to use (look-firearms-showcase 20261020-001654, frames `charscreen`,
  `town_down`).
- **The create-character window opens from town** through `HWR2GameMode.OpenCreateCharWindow()`
  (HWR2GameMode.as:260), what PickCharacterWindow's new-character button calls (:261). The new
  gamelab-hands verb `charcreate` calls it. look-class-list 20261020-002117 frame `classlist`
  shows the Firearms Specialist selected among the vanilla figures, the same size as theirs.

## Party key pool and floor key budget (2026-10-20)

- **Found keys go into one party pool on the host** (`HWP::Keys::g_pool`), kept in the host
  record's bag (`keys.pool`, plus `keys.pool_run` = `m_missionRewardSeed`, so a new run or
  town clears it) and broadcast as the `keys.pool` event. Clients ask for it at level start
  (`keys.pool_get`) and ask the host to spend one (`keys.pool_spend`) when they open a chest
  with it. Bought keys stay on the buyer's record, as in vanilla.
- **The budget is per floor and per tier:** `floor(locked Ã— share)` plus the fraction rounded by
  a hash roll, minus the party keys of that tier held when the floor started, where share =
  `keys.budget_share` 0.5 + `keys.budget_per_player` 0.1 Ã— (players âˆ’ 1), at most 0.95. The
  floor's locked chests are counted as `HWPChest` locks them (`g_lockedTier`).
- **mod-keys-pool 20261020-003440 (bandit_keep floor 1, solo):** 3 locked bronze chests, budget
  bronze 2. With `keys.accept 1`, culling the floor dropped exactly 2 bronze keys, then no more
  (budget 0/2). A key from `hwp keydrop` went into the pool (record bronze 0, pool bronze 1),
  and opening a bronze chest took the pool key and left the 2 bought gold keys alone. Shots
  `hud` and `hud_after` show the key icons left of the skill bar (bronze 1 and gold 2, then
  gold 2).

## Abyss rewards by run progress, elites by party size (2026-10-20)

- **`g_diffLevel` is the floor's level including new game+:** MissionGameMode.LoadDifficulty
  (MissionGameMode.as:153-161) takes the level's `diff-level` (or `diff-level-ngp` in new game+)
  and adds `g_ngp Ã— Tweak::LevelCapNGPAdd` (5, Player.as:73). The Dark Citadel's floors are
  2..22, the side missions 10..15, and new game+ floor 1 is 13 + 5 = 18.
- **The old single payout beat a vanilla platinum chest** (chests.sval `chest_platinum`: 200-400
  gold, an epic trinket, a rare item ilvl +1-3) on every floor. It is now three tables on the key
  tiers' breakpoints (diff up to 7, up to 13, above), about a silver chest, a gold chest and a
  little more than a platinum one.
- **mod-abyss-tiers 20261020-003934 PASS:** Dark Citadel floor 1 (`hwp abyss`: "reward tier 1
  here") logged `payout hwp_abyss_reward_1`; the same floor in new game+ (`mission dark_citadel
  0 1`) logged `payout hwp_abyss_reward_3`. Each payout dropped gold and three items.

## Valuables at double gold (2026-10-20)

- **A valuable pays its price, once, at pickup:** PlayerRecord.as:2141-2146 casts the picked item
  to `Item::Valuable` and gives `GiveMaterial(Gold, valuable.GetPrice())`; `GetPrice()` is the
  item's `m_price` (`tweak/items/items_valuables.sval`, 26 valuables, 30 to 800 gold). The pickup
  is paid by the picker's own record, so every machine needs the change, not just the host.
- **Setting `m_price` is enough:** mods/valuables keeps each valuable's vanilla price and sets
  `m_price = vanilla Ã— valuables.gold_mult`, so changing the setting never compounds.
- **mod-valuables 20261020-021120 PASS:** boot self-check "26 valuables at 2x"; `hwp valuables`
  "150 -> 300" for the ceramic vase; a dropped vase is "worth 300"; picking it up took the
  character's gold from 0 (`gl inv` c6) to 300 (c9), asserted in the rerun 20261020-021931 PASS; `gold_mult 1` gives 150 -> 150 and 2 gives
  300 again.

## Puzzle rooms on most floors: forced onto the outskirts (2026-10-20)

- **Why a whole run could show none:** the old command rolled 33 % a floor and only went to
  generators whose theme has a `<biome>_puzzle` set, so the forest, heaven and cave_spider floors
  never had a chance. A rolled room also needs vanilla `PrefabPlacement.PlacePrefabs` to find a
  spot whose cells already match its pattern (a solid wall block, `Pattern::Wall` frame, with a
  corridor end at its door). At 100 % diag-puzzle-rooms 20261020-021148 found one on the
  cave_dark and temple floors, but not on every attempt (the keep's first attempt in
  20261020-021658 logged "no free wall block on the outskirts" even for forcing). Architect's
  ChallengeSetup also skips SpawnPrefabSet commands (noted before); that was only about which
  command it wraps, and challenge floors do get rooms (see "Outdoor floors" below).
- **Forcing:** `MissionPrefabDef::GetPossiblePrefabs` refuses a def once `PlacePrefabs` failed
  on it (`m_foundNoPlacement`), so the module walks `MissionPrefabDef::Instances` for the set
  itself. A free block is one whose cells are all unconsumed Wall/Nothing/Cliff (summed-area
  table); the door is the def's first `m_junctions*` entry (ivec3 x, y, width); the corridor runs
  straight out until the door-wide strip is Floor/Breakables/Bridge. `PlacePrefabAt` runs the
  prefab's grid commands (PlaceWall 05, Reserve 01...) and adds its point of interest; the
  pattern's Walkable cells and the corridor are then set to Floor, which DungeonBrush paints.
- **Which floors can't:** `ForestBrush.Build` (ForestBrush.as) only spawns the points of interest
  and runs the painting list; it paints no tiles from the cells, so a carved corridor would not
  exist on a forest or heaven floor. The keep is an `OutdoorGenerator` too (themes_keep.sval
  `gen-class`), but its `DungeonInstanceBrush` paints from the cells. The test is the brush, not
  the generator (`cast<ForestBrush>(gen.m_brush)`).
- **Outdoor floors get a clearing instead (2026-10-20):** a ForestBrush grid starts all Floor
  (`ForestBrush.Initialize`) and the base level prefab is copied in by `CopyPrefabTo`; the
  forest's own specials (`forest_special.sval`: well, shrine, cook) are open prefabs that carry
  their own tiles, matched on Walkable (pattern 7) with ReserveFloor (command 3). The
  Constellation is units and worldscripts only, so a MissionPrefabDef of it (set
  `hwp_puzzle_open`, 10x14 cells, origin at 5,8) placed the same way works on grass and on heaven
  ground. Inserted right after the first `*_special*` command, before the edges/fillers.
  mod-puzzle-rooms-outdoor 20261020-124846 PASS: placed, walked to, solved and rewarded on a
  dark_citadel forest floor and a heaven_test floor. Architect: `ChallengeSetup` (Challenges.as:156)
  wraps a non-SpawnPrefabSet command, so a challenge floor keeps its room:
  mod-puzzle-rooms-challenges 20261020-125015 PASS (bandit_keep with Crowded + Champions).
- **mod-puzzle-rooms-forced 20261020-021658 PASS:** with `puzzles.debug_force 1` the keep floor
  logged `forced prefabs/keep/special/puzzle_room_w_16x18_a.pfb at 1,2 of 96x96, corridor 16`;
  `gl goto` walked into it, the Constellation solved and its reward spawned. diag-puzzle-rooms
  20261020-021827 forced cave_dark rooms at 6,150 (corridor 35) and 1,25 (corridor 9) of 175x175
  and a temple room at 24,168 of 187x187. mod-puzzle-rooms 20261020-021747 PASS (unforced). Default chance is now 60 %.

## Firearms, fishing, farming and core fixes from the play-test list (2026-10-20)

The play-test list's bugs and features that are not keys, abyss, valuables or puzzles (those
are above). Measured on build 25932569 unless marked assumed.

- **Rifle and pistols.** The rifle fires a 3-round burst per pull and no longer pierces; a lone
  pistol fires single rounds every 300 ms (only a dual pair alternates); the last 3 rounds (6
  dual) click (`HWPFirearmsLowClick`, `event:/sfx/doodads/buttons/button_metal`; GameLab is muted, so the sound itself is unheard here). Damage was brought to the bow and crossbow's range with
  the burst and the dual pair counted in: rifle Ã—0.52 (epic 0.65), pistols Ã—0.8, from
  bench-weapons 20261020-003538 (a solo dummy; the dual DPS is measured on the small dummy only,
  assumed to hold on bigger targets). Frag Grenade radius 64 (half). New characters start with
  `hwp_glock_mh_01` (Service Pistol). Measured: plan-t14, plan-firearms-guns, mod-firearms-pistols
  (runs listed at the end).
- **Over-Reload is a bar above the health bar** (Combat.as `OverReloadState`), white sweep for
  every reload, a gold window only with the orb. A miss turns the sweep red and greys the window,
  with no second try; left click counts as well as the Reload key. Visually verified in
  plan-firearms-orbs 20261020-025020 shots `reload-bar-missed`, `reload-bar-plain`,
  `reload-bar-manual`: each shot is taken before the `bar()` read, since every `gl` command opens the console
  over the frame.
- **Weapon swap is a 2 s rooted channel** (`buffs_weaponswap.sval`), cancelled by X again or a
  dodge. plan-t8 20261020-025317: `swap_channel_rooted` moved 0.0, `swap_cancel_key` and
  `swap_cancel_dodge` logged their cancel, the swap lands after the channel.
- **The generator picks the first base item when every weight is 0.** EquipmentGenerator.as
  `GenerateBaseItem` (:216-227) does `r = randf() Ã— sum` then `r -= rarity; if (r <= 0) return`,
  so with a sum of 0 the first candidate always wins. Joints have spawn-chance 0, and chests in
  plan-t8 20261020-023506 rolled them ("Generated 'hwp_joint_lucky_leaf_5' equipment with too few
  modifiers"). `equipment_joints.sval` now carries a conditional on a flag nobody sets
  (`hwp_joint_never_drops`), which `VerifyItem` (:367 `CheckGlobalConditionals`) refuses before
  the pick, and `Joint.as MakeJointById` builds the item itself instead of `GenerateItem`. So
  `gl equip` can't give a joint (it goes through VerifyItem); tests use `gl wield`. A spawn-chance
  0 *modifier* is fine: EquipmentGenerator.as:445 skips 0-chance mods (the Mm-hmm! bonus).
- **A duplicate NPC unit destroys itself.** `CompositeActorBehaviorNPC.CheckForExistance`
  (NPCBehavior.as:283, run from :280) fetches every unit of its producer and destroys the newer
  ones unless the editor-only `AllowDuplicates` is set, so the second fishing spot a floor spawned
  removed the first. `HWPFishingHoleNPC` overrides it empty, as core Town.as:366 does.
- **Unit and texture rules met on the way:** a GUI/doodad texture must be power-of-two
  (`fish_small.png` is padded to 64Ã—32 by `tools/make_small_fish.py`), and a scene can hold one
  `<collision>`: UnitLoader refuses a second ("A scene can only contain a single collision
  definition", the menu crashed), so the bucket's solid rect and sensor share one.
- **Fish in the wells.** The spot sits on the potion well's water, one scene per well kind, and
  greys on the map once this player has no casts left. mod-fishing-spots 20261020-024404: every
  spot within 2 px of its well (well 96,-92, spot 96,-91), 8 of 8 greyed when fished out. The
  vanilla pond fish are blue (54,122,221) and vanish in the wells' blue water, so the wells and the
  bucket use a small orange koi (`make_small_fish.py`, hue 24Â°); placement in each well's basin
  was checked on offline renders of the well unit with the spot over it (crypt moved to the
  left pool, -12,-10).
- **In a run the fishing window pauses the game,** and the pilot with it, so a pilot `use` that
  opens it never reports done until the window closes. The test treats "window open" as reached.
- **The trading post has three built tiers:** `tweak/town/buildings/trading_post.sval` has the
  unbuilt prefab (tier 0) plus tiers 1 to 3 (`trading_post_tier_1..3.pfb`); the 4 and 5 prefabs
  exist but are never used. The pirate sits on the wreck at tiers 0-2 and stands in the rowing
  boat (272,-124 of the plot) at tier 3.
- **A doodad hides a unit north of its origin.** `boat_small.unit`'s se sprite (origin 30 37 of a
  58Ã—61 frame) is drawn sorted by the boat's origin, so the pirate placed 6 px north of it was
  logged in the boat (mod-fishing-spots 20261020-032028: -1269,125) yet the hull covered him
  entirely (shot `coast-2`: an empty boat). He now stands 2 px south of the origin. The wreck's
  sprite is `layer="-1"`, under everything, so it never hid him. From 40 px south of the wreck
  the pilot's walk to him goes round the cliff and takes about 46 s (11 waypoints, 024404).
- **Eating fish:** 100 HP per star, capped at max health, in town and in runs (plan-fishing-a
  20261020-022944: town hp 33 -> 134; the run gain capped at the room left). No starting rod or
  can; the empty slots draw nothing.
- **Farming:** a plot yields as many as it draws (plan-farming-a 20261020-022552,
  plan-farming-b 20261020-024058); Gambler's Gold is gone (saves holding it get Lucky Leaf); a
  herb buff lasts 10 floors counting bosses. Joints: rolled from one herb, 5 puffs, each a stage
  of art, taken by a player with a free off hand (relayed by the host; one machine here, so the
  hand-over between two players is assumed from the code), a haze per puff in town buildings and
  run rooms.
- **Core:** Materials > Plants & Herbs, 8 boxes across; the orb warning ("Makes unavailable" plus
  the closed-off orbs' icons) in the in-run orb picker (mod-orbwarn 20261020-020301); the Mm-hmm!
  hat bonus on rare and better head items, 25 % of them, no cooldown, played for everyone through
  a network event (mod-mmhmm 20261020-022353; GameLab is muted and solo, so whether others hear it
  is assumed from the code).
- **Runs for this section (all PASS):** mod-all 20261020-030139, plan-t14 20261020-030347,
  plan-firearms-guns 20261020-030522, plan-firearms-a 20261020-030642, plan-firearms-orbs
  20261020-031302, mod-firearms-clip 20261020-030152, mod-firearms-pistols 20261020-030247,
  plan-t8 20261020-031550, mod-weaponswap 20261020-030334, mod-options-tab 20261020-030918,
  mod-farming 20261020-022540, plan-farming-a 20261020-025744, plan-farming-b 20261020-024058,
  plan-fishing-a 20261020-022944, mod-fishing-spots 20261020-032728, mod-fishing
  20261020-030948, mod-droptrade 20261020-030906, plan-gear-a 20261020-023920.
- **Not measurable solo, assumed from the code:** the joint hand-over and the Mm-hmm! sound on
  other machines (one game, muted); per-machine run spots in co-op. (The Ember Kush
  flicker was listed here too; it is verified now, see "Ember Kush flicker, measured" below.)

## Review fixes: keys in co-op, forced puzzle rooms' limits (2026-10-20)

From the peer's /code-review high of 20c32a1 and a8d146e (read from source; GameLab runs one
machine, so the client paths below are checked against the vanilla code, not in a run). Single-player
runs after the fixes: mod-keys 20261020-041212, mod-keys-pool 041225, mod-puzzle-rooms-forced
041304, mod-puzzle-rooms 041408, all PASS.
- **A secure pickup's effects run on the picker's machine only:** Pickup.Collide on a client
  sends `UnitPickSecure`; the host's UnitHandler.UnitPickSecure echoes `UnitPicked` to all and
  calls NetPicked, whose Picked() sees the client's actor as a husk and skips ApplyEffects
  (Pickup.as:88-93); the client's own NetPicked runs them. So a key a client picked up reached
  `GiveFoundKey` on the client only, where the old host-only check dropped it. It now calls
  `PoolAdd` on any machine (a client's add is a `keys.pool_add` request).
- **A client's chest open runs Use twice, once per side:** Player.Update sends `UseUnitSecure`;
  the host's PlayerHandler.UseUnitSecure checks CanUse(husk), echoes `UseUnit` to all and runs
  NetUse(husk) -> Use (PlayerHandler.as:519-536), and the client's UseUnit handler runs Use for
  its local player. The host's Use already took the party key, and the client's
  `keys.pool_spend` request took a second. Now only the host takes it (`PoolTake`, which also
  decides party vs. own key) and sends `keys.chest_paid { tier, party }` to a remote opener; the
  opener guesses from its copy of the pool (the host's `keys.pool` broadcasts are sent before
  the `UseUnit` echo) and corrects its own key count if the host's answer differs.
  `keys.pool_spend` is gone (the 2026-10-20 pool notes above still name it).
- **`hwp keydrop` on a client** sent `boss=1`, which used up the floor's once-per-lobby boss key.
  It now sends `debug=1`: the host drops that tier only with its own `keys.debug` on, outside the
  budget and the boss key.
- **Forced puzzle rooms respect the set's limits:** `ForcePlace` takes only defs whose `CanGet()`
  allows them (max count, conditionals, run-unique flags), with the failed PlacePrefabs'
  `m_foundNoPlacement` cleared just for that check, and tries the defs' best spots best first,
  so a def `UsePrefab()` turns down passes to the next.

### Review fixes: joints across levels, the relay, buff lists, dual spread (2026-10-20)

/code-review high over 7555534..HEAD found ten issues. The five in keys and puzzles are fixed in
898b1f8 (section above). The five in this section's code:

- **A puff just before a level change lost its stage.** Script globals reset with every level
  (docs/modules.md:44-48), so the pending burn in `g_burnPlayer` vanished and the joint kept its
  puff. The pending burn is now also kept in the player's save bag (`farm.joint_burn`, the puffed
  joint's id), and `Start` burns that stage if the same joint is still in hand. A second puff
  before the tip cooled now burns the first stage before it starts the next one. plan-farming-a
  20261020-041947 `s7_joint_burns_across_levels`: puffed 5/5, a floor started within 0.4 s, 4/5
  in the run.
- **The host relayed any joint hand-over a peer sent.** The host now relays a take only when the
  holder has a joint and is within 2Ã— the take range (equipment syncs to every machine:
  EquippedItems.as:152, PlayerHandler.as:771). It relays a give only for a take it checked, with a
  valid joint id and 1-5 puffs. Assumed from the code: one machine can't send another peer's
  messages.
- **`auto buffs = plr.m_buffs.m_buffs` copies the array**, so `removeAt` took the cleared buff out
  of the copy only and left it in the player's real list. Now `auto@` in WeaponSwapModule.as and firearms Combat.as
  `ClearPerfect`. Re-run: mod-weaponswap 20261020-041528, plan-t8 20261020-041540,
  plan-firearms-guns 20261020-042359.
- **Materials' compact boxes could read past their source sprite** when a box was bigger than the
  sprite. The source rects are now clamped (mod-all 20261020-041515).
- **Dual pistols missed with their spread.** A spread dict's `min` is added to every round with
  a random sign (ShootProjectile.as:56-67 `GetShootDir`; the `time` ramp at :100-103 only moves it
  toward `max`), so every dual round left at least 4Â° off the aim line. A plain `spread` of 5 (Â±2.5Â°)
  takes dual pistols on left click from 38/75 to 87/129 per second at L1/L12, the rifle's 88/129 and
  inside the bows' 83-99/119-142 (bench-weapons 20261020-042519 against 20261020-003538).

## Firearms balance pass: skills and mana, not the guns (2026-10-20)

The class bench (gamelab/bots/bench.py, `bench-<class>` scenarios) builds every spec and weapon build
at levels 1, 12, 20 and 25 (NG+ 1). It benches each at the start of a run and late in one (skill
orbs and trinkets: 3/5/6 at L12/20/25), against a pack of target dummies. The ratios below are to
the median of the 15 vanilla damage specializations (ranger, rogue, sorcerer, wizard, warlock) at
the same checkpoint. Vanilla's own spec averages run from 0.62x (warlock chaos) to 2.05x (wizard
conjuration) single target.

**The gun damage is unchanged** (rifle 52 %, epic 65 %, pistols 80 % per round): the user set it to
match the bow and crossbow, and said a higher setting was "way too strong" (bench-weapons). All of
the gain comes from the skills and the mana pool.

Bench fixes first (a4c72d3, 6258dc9):
- **L25 was a level 20 character for every class.** The cap is 20 + 5 per NG+
  (PlayerRecord.GetLevelCap) and the bench never set NG+. The new verb `ngp` sets it.
- **Rolled gear made about Â±20 % noise** between two runs of one build. `kit ... seed=N` now rolls
  EquipmentGenerator's choices on a seeded generator: the same kit every run and every class.
- **A weapon the character can't wear was skipped silently**, e.g. hwp_rifle_03 at ilvl 25 needs
  about 73 dex. `kit_weapons` now steps the ilvl down until the weapon goes on and records
  `weapon_ilvl`.
- The turret fired once per vanilla attack scene instead of at its rate (6258dc9): 7-9 hits in
  15 s, now 28-41.

Findings:
- **Firearms' mana pool was the bottleneck.** It was 30 + 1 a level with 0.5 regen. Every vanilla
  class has 70-120 + 2-5 with 1 regen. Sniper, Engineer and Demolitions sat at empty mana for
  1.5-8 s of every 15 s bench, and with the grenade launcher's 4 mana a shot, Deploy Turret (50)
  was never cast in the off-hand bench. Now **60 + 2 a level, 1 regen**: about warrior's 70 + 2,
  under ranger's 80 + 3.
- The bench placed the turret at the pack, 80+ px away, so My Turret! (60 px) never applied. The
  bench now puts it 30 px in front of the player, which is how the passive asks an Engineer to play.

Skill changes:
- **Snipe:** 200-600 % â†’ 300/400/500/600/750 % weapon damage, mana 30-50 â†’ 20/20/25/25/30.
- **Rocket Launcher:** 150-300 â†’ 200/240/280/330/400 fire.
- **Double Barrel Burst:** 200 â†’ 150 physical a shell (Assault was 1.5-1.8x at L12).
- **Deploy Turret:** rounds at 0.6x â†’ 1x weapon damage.

Runs: HEAD bench-firearms 20261020-074134; skills only 20261020-082101; this commit
20261020-102050; vanilla ranger 090017, rogue 091548, sorcerer 093114, wizard 094648, warlock
100215 (all seeded, all PASS).

Spec averages over the L12-L25 checkpoints, single / pack: assault 1.41/1.45 â†’ 1.32/1.43,
demolitions 0.69/0.91 â†’ 0.88/1.33, engineer 0.58/0.61 â†’ 1.07/0.96, sniper 0.70/0.57 â†’ 1.03/0.75.

single target, x the vanilla median (HEAD a4c72d3 â†’ this commit)

| build | L1 start | L1 run | L12 start | L12 run | L20 start | L20 run | L25 start | L25 run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vanilla median | 133 | 139 | 275 | 478 | 497 | 1062 | 596 | 1210 |
| (level 1) rifle | 0.83 â†’ 0.92 | 0.82 â†’ 0.99 |  |  |  |  |  |  |
| (level 1) pistols | 0.70 â†’ 0.66 | 0.73 â†’ 0.94 |  |  |  |  |  |  |
| sniper rifle |  |  | 0.83 â†’ 0.91 | 0.68 â†’ 0.98 | 0.70 â†’ 0.94 | 0.59 â†’ 0.80 | 0.63 â†’ 0.82 | 0.57 â†’ 0.95 |
| sniper pistols |  |  | 0.74 â†’ 1.18 | 0.63 â†’ 1.29 | 0.74 â†’ 1.11 | 0.70 â†’ 1.17 | 0.79 â†’ 1.02 | 0.77 â†’ 1.20 |
| demolitions rifle |  |  | 0.83 â†’ 1.02 | 0.59 â†’ 0.89 | 0.77 â†’ 0.92 | 0.48 â†’ 0.74 | 0.71 â†’ 0.86 | 0.77 â†’ 0.85 |
| demolitions pistols |  |  | 0.83 â†’ 1.05 | 0.67 â†’ 0.84 | 0.91 â†’ 0.96 | 0.47 â†’ 0.66 | 0.76 â†’ 0.85 | 0.48 â†’ 0.86 |
| assault rifle |  |  | 1.48 â†’ 1.41 | 1.65 â†’ 1.56 | 1.51 â†’ 1.15 | 1.15 â†’ 1.15 | 1.09 â†’ 1.03 | 1.40 â†’ 1.37 |
| assault pistols |  |  | 1.53 â†’ 1.75 | 1.80 â†’ 1.64 | 1.57 â†’ 1.24 | 1.32 â†’ 1.15 | 1.19 â†’ 1.14 | 1.29 â†’ 1.23 |
| engineer rifle |  |  | 0.71 â†’ 1.50 | 0.60 â†’ 1.22 | 0.69 â†’ 1.30 | 0.51 â†’ 0.91 | 0.54 â†’ 1.25 | 0.41 â†’ 0.89 |
| engineer pistols |  |  | 0.68 â†’ 1.22 | 0.52 â†’ 0.88 | 0.59 â†’ 1.08 | 0.48 â†’ 0.86 | 0.71 â†’ 1.04 | 0.50 â†’ 0.73 |

pack target, x the vanilla median (HEAD a4c72d3 â†’ this commit)

| build | L1 start | L1 run | L12 start | L12 run | L20 start | L20 run | L25 start | L25 run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vanilla median | 268 | 276 | 731 | 1077 | 1145 | 2455 | 1480 | 3118 |
| (level 1) rifle | 1.18 â†’ 1.39 | 1.18 â†’ 1.44 |  |  |  |  |  |  |
| (level 1) pistols | 0.89 â†’ 0.99 | 0.89 â†’ 1.11 |  |  |  |  |  |  |
| sniper rifle |  |  | 0.62 â†’ 0.83 | 0.56 â†’ 0.60 | 0.55 â†’ 0.91 | 0.54 â†’ 0.65 | 0.67 â†’ 0.80 | 0.57 â†’ 0.55 |
| sniper pistols |  |  | 0.54 â†’ 0.73 | 0.51 â†’ 0.83 | 0.65 â†’ 0.85 | 0.51 â†’ 0.74 | 0.63 â†’ 0.80 | 0.51 â†’ 0.72 |
| demolitions rifle |  |  | 0.85 â†’ 1.30 | 0.86 â†’ 1.49 | 1.16 â†’ 1.45 | 0.78 â†’ 1.09 | 0.83 â†’ 1.28 | 0.84 â†’ 1.38 |
| demolitions pistols |  |  | 0.93 â†’ 1.25 | 1.02 â†’ 1.51 | 1.06 â†’ 1.48 | 0.83 â†’ 1.13 | 0.92 â†’ 1.22 | 0.87 â†’ 1.35 |
| assault rifle |  |  | 1.28 â†’ 1.45 | 1.77 â†’ 1.86 | 1.62 â†’ 1.44 | 1.30 â†’ 1.32 | 1.24 â†’ 1.27 | 1.42 â†’ 1.40 |
| assault pistols |  |  | 1.51 â†’ 1.53 | 1.97 â†’ 1.86 | 1.56 â†’ 1.43 | 1.35 â†’ 1.24 | 1.11 â†’ 1.22 | 1.32 â†’ 1.19 |
| engineer rifle |  |  | 0.73 â†’ 1.17 | 0.71 â†’ 1.07 | 0.75 â†’ 1.23 | 0.56 â†’ 0.87 | 0.70 â†’ 1.13 | 0.47 â†’ 0.85 |
| engineer pistols |  |  | 0.51 â†’ 0.97 | 0.54 â†’ 0.83 | 0.73 â†’ 1.00 | 0.50 â†’ 0.70 | 0.68 â†’ 1.02 | 0.48 â†’ 0.63 |

Left as is: Engineer late in a run (0.73-0.91 single) and Demolitions' single target at L20 late
(0.66-0.74; its pack number is 1.1). Both sit inside the vanilla spread. Bench limits: the dummies
neither move nor fight back, each bench is 15 s from full mana and cooldowns, and the off-hand bench
holds the off hand all the time (so a grenade launcher spends mana a player would keep for a skill).

## Grenade launcher point-blank: a slug, not a blast (2026-10-20)

The user's call for the rifle's under-barrel launcher at close range: "It should still hit the
first enemy it contacts and deal half damage as a slug that stuns them for .5 seconds". The shell
(rifle_gl_shell.unit) now carries `Projectile::HWPFirearmsArm` (scripts/HWP/Firearms/Launcher.as).
Until the shell has flown arm-dist (40 px; it leaves 22 px in front of the player), the modifier
swaps the projectile's hit effects for its slug-effects: PlayerDamage 0.6x and the 0.5 s stun
stun_gl (buffs_firearms.sval). After that it puts the 1.2x blast back. NewProjectile raycasts a
move before it runs the modifiers' Update (NewProjectile.as:1464-1485), so a hit on the frame that
crosses 40 px is still the slug. A wall uses the collide effects (NewProjectile.as:1157-1160), which
stay the blast, so a point-blank wall shot still explodes.

The new `offonly` flag makes the bench verb hold the off hand alone. With both buttons held for a
short bench, the rifle burst's blocking keeps the launcher from firing.
mod-firearms-gl-slug 20261020-112608 (gamelab/bots/gl_slug_check.py, three shots each): 28 damage
and a stun on a dummy 30 px away, against 57 and no stun at 100 px, one hit each time. A target
dummy's buff reads with an empty `m_name` in `actorbuffs`, so the check reads the tags.

## Abilities cut a reload; saved ranks after the rank-1 start; review round 2 (2026-10-20)

User asks: an ability stops a reload, and so does the weapon swap (X). An empty clip or
another Reload press starts it again as usual. Then the second `/code-review high`
(83c04fe..a4fd756) findings in my files.

- **An ability cuts a Reload cast (verified, plan-firearms-reload-cut 20261020-113916).**
  - `HWPFirearmsReload.IsBlocking` is false now. With it true (its `blocking` 0..2100), no
    other skill could start during the cast.
  - A skill thrown from its keys then cancels the Reload itself. PlayerTargetingHelper
    activates it, then `CancelOther` Deactivates every other active skill
    (PlayerTargetingHelper.as:291-293, 423-447; from source). It's the same path a dodge
    takes. In the run, the clip stayed at 20/30 2.4 s after a Reload that a Frag cut, and
    a second Reload filled it.
  - A cast that skips the helper is caught by `HWP::Firearms::Interrupting` (Combat.as).
    That covers `castat`, an AI-style cast, and the weapon swap's `swapping` buff. It runs
    each frame in OverReloadState.Update: a Reload cast short of its castpoint is
    Deactivated, and the log says "reload: an ability at X/Y ms cancels it".
  - The guns still wait for a Reload cast: `HWPFirearmsGun.CanActivate` refuses while
    it runs. A trigger held through it fired nothing (20 -> 20 -> 30/30).
- **The automatic reload is held, then starts over (verified, same run).**
  - While an ability or the swap channel runs, the Reloading stack's timer is put back to
    full each frame and the bar is hidden.
  - When it ends, the reload runs from the start: "holds the automatic reload at its
    start" and then "starts over".
  - Measured: a Frag cast 0.6 s into the reload, and the clip refilled 2.8 s after
    emptying (1.6 s without it). With the swap channel up the clip was still 0 at 1.9 s,
    and refilled about 1.0 s after the cancel (the 0.3 s of channel, then the reload).
- **Saved ranks after the rank-1 start (finding 2, from source; the run is cited in the
  third-round notes below).**
  - Since 499f1d7, Frag and the eight doctrine skills have `starting-level` 1. A save keeps
    a picked rank relative to it: `PlayerRecord.GetSkillLevel` adds `m_startingLevel`
    (PlayerRecord.as:1336-1352).
  - Points are counted from the starting level too (`GetSkillPointsSpentOnSkills`,
    PlayerRecord.as:1355-1377). So an older save with N picked loads exactly as a new
    character that picked N: the free rank on top, at the same cost when a skill's costs are
    even.
  - Only a save at the old max goes over: `SkillUp` stops at
    `m_startingLevel + saved == m_levelParams.length()` (PlayerRecord.as:1584).
  - A first version took a rank off every unmarked character once. That also took a paid
    rank from characters made after 499f1d7 (third review). It is now `ClampStartRanks`
    (FirearmsModule.as): each level start pulls a saved rank past the max back to it and
    touches nothing else.
  - `hwp firearms startranks [run|set id n]` shows saved/loaded/max. `run` and `set` are
    cheats; `set` writes a rank past the max, as an old save at max is.
  - Remote players' records get the change through `PlayerSyncSkillLevel` (assumed; one
    player in the lab).
- **Turret rate (finding 9).** The logged shot interval used to add a hard-coded 200 ms.
  It now reads the length of the turret's attack scene (`GetUnitScene(...).Length()`, as
  DashStrike.as does), so it can't drift from `turret_attack.effect`. Run: plan-firearms-b 20261020-113527 logs "a shot every 600 ms", as before.
- **Joint hand-over (finding 1; co-op, not measurable with one player).**
  - Before, a second take overwrote the first one pending on the host. The holder lets go
    before the host checks the give, so the refused give destroyed the joint.
  - Now the first take wins, and a pending take expires after 5 s.
  - A give whose take was replaced goes back to its holder instead of vanishing.
  - Compiles and passes plan-farming-a 20261020-114231. The relay itself needs two players.
- **Findings sent to the peer** (3 Available's stale flag, 4 UsePrefab variations, 5 a
  client's POOL_ADD, 6 bench.py losing rows, 7 verbs.md, 8 KitRng, 10 BENCH_TURRET):
  0f25738.
- **The HoH1 classes in the class planner**
  (https://claude.ai/artifact/GUXggQqycAoQRiJ6G1Nwv3). It now lists the Thief, Gladiator and
  Witch Hunter, read-only and marked "HoH1 port". Each has its base kit, three
  masteries and a note on how the HoH1 kit was split. The Priest's Smiter and the Paladin's
  Holy Storm show as a 4th, ported spec. The records come from the game's own parse of the
  mod's svals (export-classes-svals 20261020-114205), the icons from the local HoH1 art
  (`hoh1art/`). The ported skills have no orbs: none of the mod's skill svals has
  `modifier-skills`.
- **"Costs {mana-cost} mana." removed from 8 HoH1 skill descriptions** (hwp_classes.lang).
  The tooltip fills the description from its `description-params` by name
  (`AppendSkillDesc`, Modifications.as:1027-1080), which the lang writes as `%key%`. No
  vanilla or HoH1 string uses `{...}`. Vanilla skills show mana as the "Mana Cost" param
  line, which all 8 have. So the braces most likely showed raw (assumed; not seen in a
  frame), and the sentence repeated the param line anyway. mod-classes 20261020-121429
  passes with the change.

## Third code review (a4fd756..HEAD plus the working tree, 2026-10-20)

- **Start ranks (mine).** The once-per-character migration also took a paid rank from
  characters made after 499f1d7, and the mark could not tell them apart. It is now the max
  clamp described above (`ClampStartRanks`). plan-firearms-reload-cut 20261020-120412: a
  new character (Frag saved 0, loaded 1, max saved 4) and a picked Frag (1/2) are kept
  through a level start; a save written past the max (5/6) is pulled back to 4/5 and logged;
  a second pass changes nothing.
- **Joint hand-over (mine).** The pending takes outlived their level, and a new level's
  clock could reach an old timestamp and refuse a take. `ClearJoints` (each level start)
  now empties them. plan-farming-a 20261020-121019 passes (the relay itself needs two
  players).
- **Turret rate (mine).** When the attack scene doesn't resolve, the log says "unknown"
  instead of a rate short by the scene. plan-firearms-b 20261020-121820 (600 ms, as before).
  Its turret_shoots check missed once (20261020-120630): open_dirs gave a diagonal, and the
  brute took no damage in 3 s, as in the earlier out-of-sight cases. The rerun passed.
- **export-classes-svals (mine)** wrote into this session's temp folder. It now writes to
  `gamelab/results/export-classes-svals/`, and `runner.py` resolves a relative `sval`
  dest against the repo. export-classes-svals 20261020-121442.
- **Not changed (mine):** `Interrupting` and `ReloadCasting` walk the player's skills
  (about ten) once a frame and on each gun CanActivate, as vanilla's `CancelOther` does
  (PlayerTargetingHelper.as:423-447). A cached handle would go stale when `LoadSkills`
  rebuilds `m_skills`.
- **The peer's:** ForcePlace using up a room whose variation has no spot, the launcher
  slug without shrapnel penetration, a client logging a false key rate limit, icon_art
  reloading its atlas per icon, and a failed bench save hiding the bench error: 0f25738 (mod-firearms-gl-slug 20261020-121546,
  mod-puzzle-rooms-forced 121622, mod-keys-pool 121711, bench-smoke 115652).

## Ember Kush flicker, measured (2026-10-20)

- `look-ember-kush` spawns five wild Ember Kush plots beside the player in town and takes 12
  frames in a row (the comparison is a scratchpad script over the shots, around four of the
  plots; the fifth is under the pet).
- **Before the fix** (the unit from 1a41acc^, put back for one run, then restored):
  20261020-125520. Each plot changed 20-100 pixels between most frame pairs. In the frames the
  plants drop behind the planter box: the three plant sprites and the box share one depth, so
  their draw order changes from frame to frame.
- **With the fix** (a `ulayer` per plant sprite, 1a41acc): 20261020-125428. 0 changed pixels
  in every plot across all 11 frame pairs, while the frames themselves differed by
  7,000-14,000 pixels (foliage sway). All three plants are drawn in every frame.

## The class planner moves into the repo (2026-10-20)

- **Was:** a claude.ai artifact (https://claude.ai/artifact/GUXggQqycAoQRiJ6G1Nwv3) with its
  records in the artifact's database, private to the owner. **Now:** `planner/`, a local
  web app. `python -m planner` (or double-click `planner.cmd`) serves `planner/web/` on
  127.0.0.1:8737 and opens the browser; standard library only, so it needs nothing but
  Python. Each record is `planner/data/<collection>/<id>.json` (sorted keys, 2-space
  indent); a Save writes the file, and the page polls every 2 s, so a `git pull` shows up.
  The artifact is left as it was; the repo copy is the live one from here.
- **Copied:** all 8 collections as of the artifact's version 1792511098-3a67 (12 classes,
  13 doctrines, 28 skills, 49 orbs, 4 weapons, 2 stacks, 6 attributes, 1 reference), then:
  - **Removed, at the owner's request:** the drafted 4th spec of each vanilla class (8
    doctrines, their 16 skills and 16 orbs, all status "idea" and never edited), and the
    page's "Brainstorm with Claude" card that drafted them. The Firearms Specialist's
    doctrines are untouched.
  - **Added:** a placeholder 4th spec (`<cls>-spec4`, "Placeholder", with a "Placeholder
    Active" and "Placeholder Passive") for the 8 vanilla classes and the 3 HoH1 classes.
    The Priest and Paladin keep their ported HoH1 mastery as well, as the page already
    showed them (base kit, vanilla specs, ported mastery, then the 4th).
- **Icons:** `tools/icon_art/planner_icons.py` now reads `planner/data/`, also cuts the HoH1
  classes' icons (mods/classes svals), and writes `planner/web/icons.png` and `icons.json`.
  The committed sheet uses the committed placeholder atlases; with the HoH1 art imported
  (`mods/classes/hoh1art/`) it also writes the git-ignored `icons.local.png`, which the
  server sends for `icons.png`. The generated ids match the artifact's sheet, less the 32
  idea icons.
- **Fixed on the way:** the page reset the remembered class to Firearms on its first render,
  before the data had loaded. `#<class id>` in the address now opens that class.
- Checked: the API (read, write, delete; a bad collection, an id with `../`, a cross-site
  Origin and a non-object body are refused with 400) and headless Edge renders of the
  Firearms, Priest, Ranger, Thief and Paladin pages, each placeholder spec in place.

## README cleanup (2026-10-20)

- `README.md` rewritten as a player-facing overview. The modules are grouped (classes and
  combat, HoH1, runs and dungeons, town, co-op and QoL), one short row each; the Firearms
  row points to `mods/firearms/README.md` for the details. The changelog that had grown in
  the GameLab section moved out: this file already holds it, and the README keeps a short
  Status list (test-plan state, the co-op limit, the pinned build, what Firearms still lacks).
- Corrected on the way: `summons` (the game already carries Crusaders through a floor
  change; the module tops up a shortfall, `mods/summons/README.md`), the Mm-hmm! hats (25 %
  of rare and epic hats), and Installing (no release is published yet, so it says to build
  with `tools/build.py`). A Class planner section says how to open it on Windows and Linux
  and who is designing which 4th spec.
- Stale lines fixed: `docs/design/firearms.md` listed the turret doctrine and Assault's orbs as
  not built (both are, `plan-firearms-b` 20261020-121820 PASS), and `mods/firearms/README.md`
  pointed at the old planner artifact.
- Firearms checks' latest runs, all PASS: plan-t14 20261020-030347, plan-firearms-a
  20261020-110341, -b 20261020-121820, -orbs 20261020-113012, -guns 20261020-113307,
  -reload-cut 20261020-120412, -arm 20261019-183638.

## The Priest's and Paladin's "HoH1" specs, pictured and traced (2026-10-20)

- **Pictures:** new `look-hoh1specs` scenario (`gamelab/bots/look_hoh1specs.py`, look only):
  the Subclass Picker on Smiter and Holy Storm, then each skill at rank 5 cast at target
  dummies on a cleared Bandit Keep floor at timescale 0.25. look-hoh1specs 20261020-152149 PASS,
  37 shots. Seen: Smite's thrust and holy impact, Divine Hammer thrown and curving back,
  Holy Storm's ring of blades out and back, Zealous Charge's leap, and a kill healing a hurt
  Priest (Last Rites). Shield of Faith shows only a faint ground ring on cast.
- **Origin, checked against the HoH1 data** (`gamecode/sdk/hoh1/players/{priest,paladin}`,
  `language/english.lang`): only Smite is a HoH1 Priest skill (the class's primary attack
  there). Divine Hammer is a HoH1 chapel upgrade's name (`tweak/shops/chapel.sval`); Last Rites,
  Holy Storm and Shield of Faith exist nowhere in HoH1; Zealous Charge is the name of an unused
  HoH2 dash (`players/paladin/skills/charge.sval`), ours a leap. `mods/classes/README.md` had
  said the HoH1 Priest had "Holy Beam" (it is Holy Light) and that HoH2 ships the HoH1
  Paladin's Charge (only the unused Zealous Charge); corrected.

## The Priest's and Paladin's "HoH1" specs removed (2026-10-20)

- At the owner's request, after the trace above: `mods/classes/players/hwp/hoh1specs/` (the
  Smiter and Holy Storm subclasses and their 6 skills), their lang strings, the
  `hwp_pal_shield_of_faith` buff and the module's mastery self-check are gone. So are the
  `plan-classesb-b` scenario (test step classes.s6) with its bot sections, and
  `look-hoh1specs`.
- Class planner: the ported spec is off the Priest and Paladin records; their placeholder
  4th spec (`priest-spec4`, `paladin-spec4`, no owner yet) is now the 4th slot. The icon sheet
  was regenerated (362 icons, none missing).
- Saves: `PlayerRecord.Load` sets the class from `PlayerClass::Get` and returns false when it
  is null (PlayerRecord.as:958, 1308), so a character on a removed subclass fails to load
  rather than crashing (from source; not run). No release shipped these subclasses.
- Runs: mod-classes 20261020-153330 PASS (`self-check done: 3/3 classes`), mod-all
  20261020-153342 PASS.

## HoH1 Remastered specs: the HoH1 abilities HoH2 lacks, and their art (2026-10-20)

- Planned: a 5th spec, tagged "(HoH1 Remastered)", for each vanilla class HoH1 also has
  (Paladin, Priest, Ranger, Sorcerer, Warlock, Wizard), made of that class's HoH1 abilities
  HoH2 lacks. The owner is picking which. Rogue and Warrior have no HoH1 class.
- The list, from HoH1's class svals against HoH2's skill svals (source, not run): Paladin
  Charge, Whirlwind, Shield, Stunning Blows (close: Flames of Devotion, an HoH2 orb name);
  Priest Smite, Remedy (close: Aura of Purification); Ranger Flurry of Arrows, Powershot, On
  the Prowl, Twinned Arrows (close: Grasping Roots, Marked Prey); Sorcerer Frost Shard, Comet,
  Ice Barrier (close: Biting Chill); Warlock Soul Dagger, Lightning Bolt, Extended Domain, Soul
  Cleaver, Stormlash (close: Summon Gargoyle, Eye of the Storm); Wizard Fire Breath, Blast
  Wave, Combustion, Scorched Earth.
- Holy Blast and ally healing: `pri_holy_blast.sval` has only damage effects, and
  ShootChargedBeam.as:149 skips team members, so on the pinned build it does not heal allies
  (source, not run). The owner says it heals; not yet measured in GameLab.
- Art: `HOH1_REMASTERED_ICONS` in `tools/import_hoh1.py` holds each ability's rect in HoH1's
  `gui/icons_skills.png` (29 cells). `import_hoh1.py classes` copies that sheet whole to
  `mods/classes/hoh1art/players/hwp/remastered/icons.png`; the committed placeholder at
  `players/hwp/remastered/icons.png` is made by `tools/make_remastered_icons.py`. Doctor's
  classes row now also wants the sheet, so `doctor --fix` writes it on an existing clone
  (checked: with the file moved away, `import_missing('classes')` lists it, and the importer
  rewrites it byte-identical). Default build packs the placeholder (2608 B), `--with-local`
  HoH1's sheet (39326 B). Nothing in game uses it yet.
- Runs: mod-classes 20261020-160710 PASS, mod-all 20261020-160722 PASS.
- Picks, now in the planner (design only, HoH1's numbers, nothing built): Paladin Zealous
  Charge (HoH2's unused `players/paladin/skills/charge.sval`, with its Bull Rush orb) + Shield;
  Priest Smite + Remedy; Ranger Flurry of Arrows + On the Prowl; Sorcerer Frost Shard + Ice
  Barrier; Warlock Soul Dagger + Soul Cleaver; Wizard Blast Wave + Scorched Earth; Rogue (from
  the HoH1 Thief) Grappling Hook (HoH2 has an unused `rog_grappling_hook.sval`) + Vicious Cuts;
  Warrior (from the HoH1 Gladiator) Trident, reworked for the Warrior, with Planned Attack as an
  orb on it, + Riposte. `HOH1_REMASTERED_ICONS` gains the Rogue's and Warrior's 5 cells (34).
- Records: `doctrines/<cls>-hoh1.json` (`remastered: true`, order 5), 16 skills
  `skills/<cls>-hoh1-<skill>.json`, 2 orbs in `mods/`. All are new files with a `-hoh1` prefix
  the planner's own id scheme (`slug(name)`) never makes, so friends adding 4th specs can't
  collide; no existing record changed. The page tells the 4th from the 5th by `remastered`
  (purple "5th: HoH1 Remastered" box; an All classes column). `planner_icons.py` cuts
  `hoh1_icon` records from the Remastered sheet: 380 wanted, 380 found. Checked by headless
  Edge screenshots of the Warrior specs, Paladin orbs and All classes tabs.

## Firearms: Hand Cannon, Flamethrower Rifle, the Grenade Launching Rifle rename (2026-10-20)

- Hand Cannon (`hwp_hcannon_mh_0N`, off-hand twin `hwp_hcannon_oh_0N`, the pistols' hand
  swap): 6 rounds (assumed), a round worth 1.5 pistol rounds (projectile `mul` 1.2 against the
  pistol's 0.8, same weapon damage), half the rate (600 ms alone). With a pistol in the other
  hand, left click is pistol, cannon, pistol at 0/100/200 of a 500 ms cycle (the lone pistol's
  300 ms between bursts), from whichever hand holds the pistol. plan-firearms-cannon
  20261020-170919 PASS, 19 flags; gaps 99/99/297 both ways, 561-594 alone and for two cannons.
- `HWPFirearmsGun` gains `hwp-mixed-with/-length/-blocking` (a third cycle while the other
  hand's marker is the other gun kind) and logs `<skill>: cycle N ms` when its cycle changes.
- Engine fact (source, then measured): `PlayerSkillDirectional::Update` sets
  `m_skillLen = max(m_animLen, m_timeline.GetLength())` every frame (PlayerSkillDirectional.as:107),
  so a cycle shorter than the timeline's last entry is stretched to it. The cannon's 500 ms mixed
  cycle ran 600 (its right-hand round is at 600; 20261020-170115: gaps 99/99/396). The gun now
  resets `m_skillLen = m_animLen` after the base Update; entries past the cycle never fire.
- Engine fact (source, then measured): `anim-length` and `blocking` are read in
  `PlayerSkill::Initialize` (PlayerSkill.as:207-211), not the constructor. `HWPFirearmsGun`
  copied them in its constructor, so `m_fullLen` and `m_fullBlocking` were always 0: a paired
  gun ran the attack scene's own length (two cannons logged `cycle 0 ms` and fired both muzzles
  together every 600 ms, 20261020-170639), and paired pistols' blocking ended at 0. They are now
  copied in an `Initialize` override. The paired pistols had looked right because the wand
  attack scene is about 600 ms, their own anim-length.
- Flamethrower Rifle (`hwp_flamerifle_0N`): the rifle's burst on left click; right click is
  `hwp_attack_flamer`, a `PlayerSkillDirectionalChannelling` (cooldown 0, castpoint 100,
  `mana-cost` 1 per `cost-interval` 100) that shoots `projectiles/flame.unit` every 100 ms from
  `timelines-looping`. flame.unit is the bandit flame spray's RayProjectile (speed 4.5, ttl 500,
  about 68 px, through 3) dealing 25 % weapon damage as fire (assumed numbers). Measured: no
  rounds spent; mana 90 to 73.4 over a 2 s hold (the 20 less regen), and 0.95 left after 9 s.
- The rifles are renamed Grenade Launching Rifle (Field, Marksman's); ids unchanged.
- `LauncherHUD.as` shows the flamethrower's close-up on the off-hand slot for a flame rifle.
- Regression after the Initialize fix, all PASS: plan-firearms-guns 20261020-171120,
  mod-firearms-pistols 20261020-171243, mod-firearms 20261020-171330, mod-firearms-clip
  20261020-171342, plan-firearms-arm 20261020-171438, plan-firearms-reload-cut 20261020-171528.
- bench-weapons 20261020-171745 (15 s, one dummy at 80 px, L1): pistol 24 a hit, two cannons 36
  a hit (1.5x, verified), 57.2 dps against the lone pistol's 60.3. Pistol + cannon either way
  round 120 dps (64 hits, 28 a hit: two pistol rounds and a cannon round every 500 ms), about
  twice the lone pistol and 1.7x dual pistols (70.2): the burst the owner asked for is the
  strongest one-hand loadout. Flamer 114.7 dps (rifle 87.7) until the mana ran out (low for 5.1
  s of 15); 1384 of its 1723 from the flames, the rest burning. The "cannon" row there was not
  a lone cannon: `gl kit` leaves an unnamed slot as it was, so it kept the pistols row's off-hand
  pistol (64 hits, the mixed burst's numbers). The row now names a shield.
- Full Auto Rifle (`hwp_autorifle_0N`): the rifle's burst on left click; right click is
  `hwp_attack_autofire`, an `HWPFirearmsGun` on a 100 ms cycle firing one rifle round (52 %)
  with `spread` 40 (ShootProjectile.as:60: (randf()-0.5)*spread, so +-20 degrees; the burst's
  is 2). Rate, spread and damage are assumed picks. Measured, plan-firearms-cannon
  20261020-173547 PASS (25 flags): gaps 99 ms, 16 rounds over a 1.5 s hold, no mana; the rounds'
  headings (`gl track`, the player to each round's last sight) spanned 35.5 degrees over 11
  rounds, all within +-20, against the burst's 1.5 over 6. A wide round often leaves the probe's
  400 px radius after one sample, so a first-to-last heading drops exactly the wide ones.
- Art (the pixel-art agent): held models `hwp_hcannon_mh/oh`, `hwp_flamerifle`,
  `hwp_autorifle.model` (new `tools/make_gun_models.py`, an ozz mesh reader/writer: all 158
  models round-trip byte-identical), icons and close-ups (`tools/icon_art/fa_guns.py`), drops
  (new `tools/make_firearms_drops.py`, sheet now 128x64), cannon rounds and `flame_jet.effect`
  (`tools/make_bullet_art.py`, rounds.png now 128x128). flame.unit now draws flame_jet.
  mod-all 20261020-174139 PASS. look-firearms-cannon 20261020-173754 PASS: the held guns, the flame and full-auto rounds in
  flight, the item icons, and the skill bar's flamethrower and full-auto close-ups (logged
  "flamethrower close-up ... tier 2", "full-auto close-up ... tier 3"). Judged by eye.

## Sorcerer fourth-spec design: Arcane (2026-10-20)

- Zak's design is recorded in `planner/data/`: **Arcane**, with **Blink** as the active
  and **Living Mana** (first drafted as Arcane Vessel) as the passive.
- Blink teleports a dodge distance and deals 25-50 Pure damage around the arrival point
  (6 s cooldown, 20-30 mana). Pure ignores armor and every resistance
  (CompositeActorBehavior.as:721), hence the low numbers. With a dash charge, Blink
  spends it to recast your last elemental spell from where you left, regardless of its
  cooldown or mana cost (the cost is still paid, down to 1 mana), and restarts that
  spell's cooldown countdown from the start;
  players start with 1 dash charge (`MaxDashes`, Modifiers.as:287).
- Living Mana converts the health pool, maximum-health bonuses and health restoration
  into mana. Incoming damage drains mana; reaching zero kills you. Spell costs leave at
  least one mana. Mana regeneration rises as mana runs low, up to +50-150% at empty.
- Passive orbs: **Mana Conduit** restores 33/66/100% of mana lost to damage to the other
  players, as one total split evenly between them; spell costs do not trigger it.
  **Arcane Feedback** empowers the next spell based on mana lost to enemy damage, capped
  at 50/80/120 mana, consumed on casting.
- Blink orbs: **Void Barrier** (replacing Aftershock): for 1 s after Blink you cannot
  take lethal damage. The engine has an unused `Modifiers::UnlethalDamage` that caps a
  hit at current health - 1 (Player.as:475). **Far Step** adds 15/25/35% Blink range.
- Scope: planner design records. Gameplay implementation and GameLab verification remain
  for the in-game work; these mechanics are design intent rather than verified behavior.
- Verified locally: all planner JSON loaded, the design has one active and one passive
  with two orbs each (one to three levels), and the planner HTTP page and data API
  returned successfully. No game was launched.

## Rogue fourth-spec design: Winddancer (2026-10-20)

- Zak chose a survival-focused support Rogue: **Winddancer**. Its active,
  **Protective Gale**, grants increased Evasion to the Rogue and nearby teammates. The
  buff stays with each player as they move. **Second Wind**, the passive, releases a
  healing gust on a successful evade, healing the Rogue and nearby teammates with a
  short cooldown. This is intended to work with the base kit's Sidestep.
- Protective Gale orbs: **Tailwind** adds Movement Speed; **Lasting Gale** extends the
  whole buff's duration. Both have three levels with increasing bonuses.
- Second Wind orbs: **Shared Breath** lets teammates affected by Protective Gale trigger
  healing gusts from their positions when they evade. Those gusts share the Rogue's
  Second Wind cooldown and apply its other orbs. **Lingering Breeze** adds brief Health
  Regeneration after each healing gust. Shared Breath has one level; Lingering Breeze
  has three levels with increasing regeneration strength.
- Evasion, speed, duration, healing, regeneration, radius, mana cost and cooldown values
  remain for tuning. This is a planner design, awaiting gameplay implementation and
  GameLab verification.
- Verified locally: both Winddancer and Arcane load through the planner JSON loader and
  HTTP data API, each with one active, one passive and two orbs per skill (one to three
  levels). The planner page responds successfully. No game was launched.

## The six 4th specializations built: `mods/specs` (2026-10-21)

- The planner designs became a mod, `mods/specs` (requires `core`): six subclasses
  registered by `players/hwp/specs/class_specs.sval` (written by
  `tools/make_specs_classes.py`), one active and one passive each, two or three orbs per
  skill. Commits: a517a8e (the mod, Bannerlord, Winddancer), 290453d (Invocation),
  1f96d2c (Stormbringer), acd02c4 (Branding), ca1cc08 (Arcane).
- Verified: `plan-specs` passes all six sections, 78 checks, in run
  `20261021-163852-plan-specs-lab` (387 s). The section-by-section checks are in
  `gamelab/bots/plan_specs.py`.
- Not verified (need a second player, which GameLab cannot run): teammates in Protective
  Gale and Shared Breath, the Battlefield Standard's ally numbers and Martyr's Banner, and
  Mana Conduit's host relay. Numbers the designs left open were picked and are marked
  assumed in each sval header and on the planner record.
- Icons are placeholders (tinted vanilla icons, `tools/make_specs_icons.py`). The art
  requests went to the pixel-art agent (`art/specs/REQUESTS.md`). Effects are recoloured
  vanilla ones (`tools/make_specs_fx.py`) or vanilla effects as they are.

### Engine facts measured or read for the specs (build 25932569)

- `Player.Damage` (Player.as ~381-630) returns early under `CVars::ChtGodmode`;
  `modifiers.NonLethalDamage` caps the hit at current health - 1; the modifiers'
  `DamageTaken(player, attacker, dmg)` runs before the health is reduced, then death
  below 0.
- A buff's damage over time takes health directly in `m_buffs.Update` (Player.as
  ~1085-1115), bypassing `Damage()` and its modifiers. Living Mana catches it as a health
  change on the next frame instead.
- `Heal.CanApply` refuses at full health (`GetHealth() >= 1.0`).
- Regeneration (Player.as 1241-1248): mana is `ManaRegen x regenMul x ManaGain / Mana`
  a second, health is `HealthRegen x HealthGain` after the regen delay.
- Dash charges: one comes back every `Tweak::BaseDashRechargeTime` (5000 ms) x
  `DashRechargeMul` (Player.as 1254-1265); `GiveDashCharges(n)` clamps and needs
  `PlayerSyncDashes` sent. The dodge is 90 units (players/attacks/dash.sval).
- `Teleport.DoTeleport` (Behaviors/Effects/Teleport.as) raycasts and keeps 0.95 of the
  distance: a 90 unit Blink measured 85.5 px.
- `EffectTrigger::CastSpell` fires only from the targeting-helper input path, not from
  `Skill.Activate`; the specs detect a cast by `m_castingT` leaving -1.
- A `Modifiers::SkillModifier` runs in `ModifySkills`, which resets `m_modDamageMul` to 1
  first; `PlayerRecord.RefreshModifiers()` reapplies them. Arcane Feedback uses this
  (measured: x1.2 at 40 banked mana, run above).
- `tweak/buffs/status_effects.sval:stun_greater` stuns a bandit brute elite (measured,
  `gl buffnear`).

### Arcane details (run `20261021-163852-plan-specs-lab`)

- Max mana 265 + max health 148 = 413 with Living Mana. Health follows the mana fraction.
- A real 30 pure hit drains 30 mana and leaves the health fraction at the mana's. A health
  loss outside `Damage()` (a buff's damage over time) drains 14 of 14.8.
- Blink moves 85.5 px and hits a dummy in range (hp 1.0 to 0.934). With a dash charge it
  replays Static Discharge from the start point and the charges go 1 to 0; without one it
  only teleports. Far Step at 35% moves 115.4 px.
- A recast costing more than the mana left stops at 1 mana (the `floored` counter rises).
  A plain cast can never reach the floor: `Skill.Activate` refuses a cast it can't pay
  for, so the floor only matters for Blink's recast.
- Void Barrier: a 500 pure hit right after a Blink leaves the sorcerer alive at 1 mana.
  Without it, a 300 pure hit from 20 mana kills.
- Regeneration is +15.0 in 4 s at 90% mana and +20.7 at 5% (Living Mana level 1, +50%
  at empty).
- New verbs: `gl damageme <amount> [dot]` (a pure hit through `Player.Damage`), and
  `buffnear`, `dmgmuls` for Branding. `docs/generated/verbs.md` has all of them.

### Planner, audio

- Planner: all 46 records of the six specs carry their in-game id, the game's numbers and
  a status (9f6aa43): tested where `plan-specs` measured the behaviour, built where only the
  orb's numbers are checked or a second player is needed. `planner_icons.py` reads the
  specs' icon sheet.
- Audio (4f7d229): `tools/audio_pick` renders vanilla FMOD events offline with the game's
  own `fmodstudio.dll` 2.2.11 (banks read from the install's `res/assets/sound`, nothing
  written there; the NRT WAV writer, so nothing plays). 17 sound slots, 3-4 options each,
  listed in `art/specs/AUDIO.md`; the picker page is a private artifact,
  https://claude.ai/artifact/5u7FtTXXPVJk6hixoda7Ux, whose `picks` collection is read
  back to wire the sounds in.
- FMOD gotchas measured: samples load asynchronously, so an event started straight after
  `GetEvent` renders silent until `LoadSampleData` reports loaded; in NRT mode each
  Studio update mixes exactly one DSP block (1024 samples here), so one long WAV can be
  cut per event by counting updates (the frames came out at exactly blocks x 1024).

### Review fixes and the world sprites (run `20261021-172656-plan-specs-lab`, 80 checks)

A `/code-review high` of 1bff319..HEAD found ten issues, all read off the diff and not run;
these were fixed, and the run above passes with two new checks:
- Arcane's recast ran only `PlayerSkillDirectional`. `Timeline()` now covers DirectionalCharged,
  Position and Automatic too, and only a skill with a timeline becomes the last spell. In the
  shipped kit this never mattered: the Arcane subclass's only spells are Static Discharge and
  the Elemental Orb (`class_specs.sval`), both Directional, so it is a guard (there is no test
  for it; a learn of `lightning_ball` is refused, "no skill lightning_ball in hwp_sorcerer_arcane").
- Arcane Feedback's bank now goes only to an elemental spell, never to Blink (`arc_feedback_blink`:
  used 1 -> 1 after a Blink -> 2 after Static Discharge).
- The cost of Blink's recast and of Pyrebrand's refund is `Specs::ManaCost`, worked out the
  way `Player.UsePoints` does it (Player.as 776-790): the max and current percentages, flat,
  `SkillCostMul`, the multiplier and the modifiers' `UsePoints` (pure: `UsePointsCost.as`).
- Pyrebrand: a brand that ends without a claw (its victim dies with nobody within 100) now
  starts the full cooldown (`brand_lone_cd`: 7912 ms left). Brands that run out in the same
  frame all come off before any of them claws, so one claw cannot feed the next.
- Released Essence: the claw's elite and boss victims are watched for 1 s, since the host
  decides the kill and a client sees it frames later. A death in that second gives the stacks.
- Mana Conduit: shares add up and go out every 250 ms; the host splits a float and the
  teammate keeps the fractions until they make a whole point. This is still unverified with
  two players.
- The Battlefield Standard's plant keeps the skill's conditionals (only the cooldown and cost
  are skipped).
- Living Mana's binds are read every 250 ms, not every frame.
- Not changed: the read-only verbs `hasbuff`, `bind` and `dmgmuls` stay in `gamelab-hands`
  (`Verbs_specs.as`), as the read-only verbs of the other plans do (Verbs_bench, classesa/b,
  farming, firearms).

World sprites: the pixel-art agent drew the four strips in `art/specs/fx` (`tools/icon_art/sp_fx.py`).
`tools/make_specs_fx.py` packs them into `effects/fx.png` (256x128: sigil 0,0; orb 96,0; claw
0,24; standard 0,72). They are used by:
- `branded_sigil.effect`: the sigil above a branded enemy, seen in run `20261021-171214`;
- `claw.effect`: the claw, with the vanilla fire impact (`pyrebrand.sval claw-effects`);
- `orb.effect`: the orb, over a smaller vanilla lightning ball (`torrent.unit`);
- `standard.effect`: the standard's flag, carried in frames 0-1 and planted in 2-3.

The claw and the orb draw, but at 640x360 the shots don't show them clearly.

Measured: an effect whose longest sprite is short can stop drawing altogether. The standard,
with the vanilla flag's 32 x 125 ms frames gone (about 1 s left), showed nothing, not even
its ring (tmp runs `20261021-172055` and `-172204`). The vanilla effect minus only the shadow
still drew (`-172421`). An invisible 4000 ms sprite brought back both the ring and the flag
(`-172522`), so `make_specs_fx.py` writes one.

## Deadeye and Aerotheurge: Noah's PR #4 version in game (2026-10-21)

The Ranger's and Wizard's 4th specs now follow the planner after Noah's PR #4 answers. Only the names and
lang keys changed: the skill, orb and subclass ids are kept (`hwp_ranger_stormbringer`,
`hwp_wiz_tempest_torrent`, ...) so saves still load. Run `20261021-212606-plan-specs-lab`
passes, 17 checks.

- **Gathering Winds** now gains its stacks from kills. A `Modifiers::TriggerEffect` with
  `trigger "kill"` fires from `Player.KilledActor` on the killer's own client. The gl verb `kill <r> <filter> me`
  makes the local player the killer, which is how the lab tests it. Every 5th kill
  (`HWPSpecsKillTailwind`) adds a stack. Noah wants each stack to expire on its own, 4 s after its kill,
  so `Stormbringer.as` keeps one expiry per stack. The stack def's 4100 ms timer is only a backstop.
  - Verified: `storm_gw_stack` (stack 0 after 4 kills, 1 after 5).
  - Verified: `storm_gw_expiry` (two stacks 2 s apart: 1 left at 4.4 s, 0 at 6.6 s).
  - Verified: `storm_gw_cap` (35 kills stop at 5 stacks).
- **Level-scaled Action Speed** follows the Conduit pattern: 25 buffs `tailwind_<lvl>_<n>` in
  category `hwp_tailwind`, each with category-level n and SpeedMul on move, attack and cast speed of
  1 + pct x n. The buff is re-applied every 250 ms for 600 ms. Verified: `tailwind_2_5` is on
  at 5 stacks.
- **Static Charge** gains a stack on every spell cast, via the `castspell` trigger, which runs before the cost.
  A cast counter limits the crit's extra stack to once per cast (`HWPSpecsStaticCrit`).
  The 10 s timer is reset by each new stack.
  - Verified: `inv_sc_cast` (two casts give 1, then 2).
  - Verified: `inv_sc_timer` (three stacks held 11.5 s after the second cast, all gone 10.5 s after the third).
  - Assumed, not tested: the crit stack, because the lab can't force a crit.
- **Lightning Rod** (`hwp_wiz_tt_lightning_rod`): the torrent's zap count and radius now come from
  binds (`targets-bind tt-zaps`, `radius-bind tt-radius`, base 3 and 70). Thunderclap's radius uses the
  same bind. At rare, the orb sets 5 zaps within 95. Verified: `inv_orb_binds`.

## 4th-spec icons picked (2026-10-21)

The user picked all 49 spec icons over two rounds of the picker
(https://claude.ai/artifact/PSk1d9NwASasB5zqmnccNq, db collection `picks`; round 1 ids are `specs.<name>`,
round 2 ids `specs2.<name>`). Round 2 redid the 13 picks that had notes, every Deadeye icon and
every Aerotheurge icon. Three picks were "keep" (the round-1 icon stays): Gathering Winds, Wind
Ward, Mana Conduit. `make_specs_icons.py` now paints all 49 with no placeholders. The atlas cells
are unchanged, so no new run was made; the icons are not yet seen in game.

## 4th-spec sounds wired, icon round 3 (2026-10-21)

Icon round 3 (`tools/icon_art/sp_r3.py`, picker ids `specs3.<name>`) redid the 24 icons that
were not unique: the six spec emblems (still placeholders) and 18 recolours, shrunken copies or
reused motifs. The user took 6 new ones (the Deadeye, Winddancer, Bannerlord and Branding
emblems, Lightning Rod, Feared Crest) and kept the rest, the Arcane and Aerotheurge emblems'
placeholders included.

Sounds: the user's 17 picks from the audio picker (https://claude.ai/artifact/5u7FtTXXPVJk6hixoda7Ux)
are wired, every event checked against the banks' own list (`fmod.py list`):
- Swapped in place: the sval and unit PlaySounds, and Branding.as's claw (`wisp_fire_explode`).
- Thunder Orb: `Projectile::AttachedLoopingSound` (vanilla, NewProjectile.as:849) for the
  loop; HWPSpecsZap takes a `sound` param played once per apply that zaps anything (the
  tick's zap; Thunderclap's burst on the way out, so only with the orb); HWPSpecsStaticRelease
  takes one for the release.
- Battlefield Standard: the sound moved out of the skill's `cast` actions, since the plant is a
  recast of the same skill and would have played the raise sound too. Bannerlord.as plays the
  war cry on a raise, holy_banner on the plant and holy_banner_end when it ends.
- Blink's vanish plays through `SoundEvent.PlayTracked` with `SetVolume(2.0)`, as the user asked
  for it twice as loud. Assumed, not measured: FMOD treats an instance volume above 1 as gain.
- Void Barrier's save: silent, by choice.
- Measured: `out` is an AngelScript keyword. A local named `out` failed to compile
  (`Expected expression value`, run `20261021-224619`).
- The lab is muted, so a run only shows that nothing errors, not how anything sounds.

## Essence Extraction reworked to the planner (2026-10-21)

The planner's warlock-spec4-passive (the user's edit, b081110): "Magic weapon attacks now also
count towards gaining stacks of Essence, with 2 second cooldown. Essence stacks gained from
branded enemies have their effects trigger twice." Built in `branding/essence_extraction.sval`
and `Branding.as` (HWPSpecsEssenceHit, GainEssence). Passed in run `20261021-232748`.
- Vanilla Drain Essence (`players/warlock/skills/drain_essence.sval`): a SkillTriggerEffect
  on hit and spellhit with skill-tags melee and timeout 250. Its effects are the stack, the Drain
  Blood bleed (bleeding-stacks, bleeding-chance), the PlaySound, `gain_essence.effect`,
  HPBasedHeal (drain-life-amount x max HP) and GivePercentageMana (drain-energy-amount x max mana).
  Binds belong to their own skill, so GainEssence reads Drain Essence's through BindF and BindI
  (`PrepareSkillFetchData`) and does the same things in script.
- Magic weapons: every arcane-tagged weapon attack (`players/attacks/*.sval`). That is staff,
  wand and tome (fire, ice or lightning), plus the Holy DLC scepter and lantern (`holy_weapon`).
  No melee, ranged or shield attack has the tag. The class check in `EquippedItems.as` MayEquip
  is commented out, so any class equips any of them.
  - Holy DLC gear has the conditional `dlc has holy`. GenerateItem returns null for it in the lab
    (`equip mainhand_scepter_01`, run `20261021-230738`).
  - The hit trigger is weapon damage only, main and off hand (`PlayerBase.as:869/881`).
  - The warlock's off-hand tome casts a glyph at its own feet (SpawnUnit, no target), so a dummy
    away from it is never hit.
- TriggerEffect starts its timeout on every matching hit, whether or not the effect then applies
  (`TriggerEffect.as:157-169`). So the melee trigger with the same tags and the same 250 ms
  timeout fires on the same hits as Drain Essence's own.
- "Trigger twice" is read as two gains (assumed). The project-plan session asked the user and got
  no detail. Measured: 4 Demon's Tails on a branded elite gave 4 second gains and 8 Essence. Wand
  hits gave 2 gains in 3.3 s at ee-cd 1750, and 2 gains on a branded dummy gave 4 Essence. The max
  stays 10.
- Test fallout: with the doubled Essence, the old Released Essence step's elite died to the
  tails' own brand claw early (Essence Empowerment +24% fire; run `20261021-230738`), so the step
  now spawns a fresh elite. Proliferation's 3 s brand ran out inside the 2 s of wand hits, so it is
  taken off first.
- Lightning Arrow's Tailwind Catch is flaky: catches out of 3 returning arrows were 1, 3, 2, 0 and 3.
  `storm_catch` also read the catches and the Tailwind count in two status reads a second apart,
  which can straddle the 4 s expiry; it now takes one read. A swept-segment catch test
  (from-to segment within 12 px) caught 3 of 3, but the back hits went from 1 to 0, so it was
  reverted. The cause is not understood yet.

## GameLab setup and portable compiler discovery (2026-10-21)

Prepared this checkout for the overnight QA sweep. `doctor --fix` installed the locked
Python dependencies in `.venv`, found both games through Steam, verified the existing
HoH2 build pin (25932569), backed up the saves, generated the isolated lab environment,
extracted both games, imported the HoH1 pets/levels/campaign/class art, generated 208
class-swapped units, and generated the pet dye copies. No build re-pin was needed.

- The original sandboxed Steam check said stopped because `tasklist` returned Access
  denied. The reviewed command outside the sandbox correctly detected the running
  client; no Steam process was started and no readiness gate was bypassed.
- Installed the portable x86_64 GCC 16.2.0 / MinGW-w64 14.0.0 UCRT compiler from the
  [official WinLibs r1 release](https://github.com/brechtsanders/winlibs_mingw/releases/tag/16.2.0posix-14.0.0-ucrt-r1)
  into `gamelab/fixtures/cache/toolchain/mingw64/` (gitignored). The downloaded ZIP's
  SHA256 matched the release sidecar:
  `c1f52294597c0b73786b2a78eb5d176d89226d2f21875eab75e783a8b1cefcc4`.
- `gamepaths.find_gcc()` keeps an existing PATH compiler first, then finds local
  `mingw64` or `w64devkit` copies. Doctor and bootstrap use the same discovery and
  add the compiler bin directory only to compiler child environments. System PATH,
  compiler architecture checks, build checks and save confirmation gates are unchanged.
- `export-datatables` PASS, run `20261021-234735-export-datatables-lab`: all 326/326
  sval files exported; generated trees match the manifest, including the HoH1 tree.
- `null-payload` PASS in 13 s, run `20261021-235153-null-payload-lab`: probe, frame,
  isolation and clean teardown assertions passed. User saves/config, install resources
  and foreground focus remained unchanged.
- A fresh `.\.venv\Scripts\python.exe -m gamelab doctor`, with no compiler PATH
  override, reports **green**. Use that interpreter or `uv run python` for GameLab;
  the system Python does not contain all project dependencies.
- Verification: `tools/compiler_selftest.py` passed 7 tests (discovery precedence,
  local fallbacks and child environments); `tools/doctor_selftest.py` passed 78
  checks for save gates, HoH1 discovery/imports, smoke diagnostics and pet dyes.

The 44 real save files were copied and re-hashed into
`saves-backup/2026-10-21T23-41-09/`. Recovery command, only if a restore is wanted:
`.\.venv\Scripts\python.exe tools/saves.py restore --from 2026-10-21T23-41-09`.
The overnight mod QA sweep has not been started by this setup session.

## Overnight QA baseline and coverage inventory (2026-10-22, in progress)

The sweep began at 00:20:52 Central with a 10:20:52 deadline and the final hour reserved
for regression and handoff. `docs/QA_OVERNIGHT.md` is the resumable ledger; the four
`docs/generated/qa_*_inventory.json` files track priority skill/orb/rank expectations and
all 31 module dependency sets. Inventory rows remain UNTESTED unless fresh runtime
behavior proves their specific expectation. A load or bind check is not an effect check.

- Corrected `mod-all`: its old list omitted `specs`; the new list exactly equals the 31
  module manifests. Run `20261022-003459-mod-all-lab` passed town load, clean teardown
  and all isolation checks. This does not prove every module's gameplay behavior.
- Original-code `plan-specs` run `20261022-003808-plan-specs-lab` failed the Branding
  doubled-Essence equality. Logs identify test contamination: Proliferation shortened
  the brand and Released Essence paid out when the elite died during the hit loop.
  The measurement setup is being isolated without changing gameplay or widening the
  equality assertion; the original failure remains in the ledger and artifacts.
- Original-code `plan-classesa` run `20261022-004605-plan-classesa-lab` failed
  `trident_thrust_hits` (front and side target HP unchanged). Cause is unresolved;
  a bounded activation/settled-target diagnostic is prepared before any source repair.
  `plan-classesb-a` run `20261022-004840-plan-classesb-a-lab` passed its existing checks.
- Existing Firearms A/B, both orb suites, guns, cannon, arm and reload-cut baselines
  passed so far. Each exact run ID and source fingerprint is in the ledger and serial
  JSONL journal. New per-magazine crit, Hoarder unequip, rank and arsenal checks are
  not covered by those historical assertions and are queued separately.

No gameplay-source repair or full-coverage claim has been made at this checkpoint.


## Overnight QA checkpoint (2026-10-22, 04:00 Central; still in progress)

Four gameplay repairs now pass their retained reproductions: Shadow Strike uses the
native landing explosion for damage/stun (030624); Riposte uses flat melee-only
AddThorns instead of scaling reflection (021550, 18 control/rank cases); Steady
Hands/Cool Head uses each gun's own remaining magazine for gun crit damage (030332);
and Ordinance Hoarder's charge HUD clears while its launcher skill is absent,
preserving the bank (030527). Original failures and exact source fingerprints remain
in docs/QA_OVERNIGHT.md and the per-batch JSONL journals. These scoped passes do not
prove the outstanding middle ranks, new arsenal/orb cases or save transitions.

Full mod-all 032859 and all31 individual mod-ID cases pass, mostly load/self-check
scope. Expanded54 legacy all-content scenarios from the old29-module set to all31,
including specs and valuables, without removing assertions. Global/per-skill zero
crit control 032933 passes, and Lingering Tempest 033415 passes native HP/lifetime
observations. All three Lasting Gale, Tailwind and Lingering Breeze ranks 031218 pass
their observed duration/movement/expiry effects. Shared Breath ally behavior remains
blocked without a second real client.

Return 033153 still loses an outer fan arrow at a wall before its turn, consistently
in all3 ordinary trials. Static 033017 native phase events show an old Thunder Orb
critical hit adding an extra stack after a new noncritical MagicMissile cast. Its
15745-character final event exceeds GameLab's15000-character print limit; retained
phase events establish gameplay independently. Repairs are staged pending the next
serial runtime boundary. Gale's prior failure was invalid readiness/Sidestep test
setup; its corrected rank sweep and ordinary HoH1 integration are in progress.

Added optional restart town/resume selection with explicit merged state readback;
recipe probes, exact enabled mods, muted profile and all launcher isolation gates
remain active. Native unequal-hand Firearms save/resume is still untested. No user
installation/config/save files were changed, no parked class status was changed,
and no full-sweep completion is claimed. See the ledger for the remaining queue.


## Overnight QA checkpoint (2026-10-22, 04:55 Central; incomplete)

Thunder Orb now keeps a shared token for each actual cast, including periodic and
destroyed effects, so a newer spell cannot rearm an older orb or consume another
orb's first-critical bonus. Native DamageActor/CriticalHit paths remain intact;
release damage retains Static Charge attribution/exclusion. Original 042233 and
042350 preserve valid TT?MM and TT?TT failures. Scoped TT?MM repair 042809 passes;
its same-TT neighbor is queued. Non-TT delayed projectile attribution is unverified.

Returning arrows now protect the first wall turn from duplicate native callbacks,
undo oblique projectile reflection through the same normal, and sweep only actual
returning movement for the catch. Valid 044257 passes all3 ordinary and all3 coarse6x
stress cases with damage and actual3 Tailwind stacks. Earlier 042925 remains INVALID
because res/editor metadata differed; its historical before/after values are unknown.
Five later directory/content snapshots were stable, and the bounded diagnostic run
retains identical full res dictionaries. Added exact isolation-res.json diagnostics;
no isolation comparison or other gate was relaxed and no installation file was edited.

All5 Standard self-DR/free-plant/expiry ranks 040543 and Righteous self-duration/
movement/attack/reversion ranks 040406 pass. Firearms magazine edge 040044 passes23
retained bot rows (21 unique, repeated controls preserved). Native save/resume,
arsenal and wider rank/orb cases remain pending. Seven shared restart tests pass.

Broad-m's56-case serial queue and frozen source hashes are retained under results;
143verbs are current after adding the bounded native Wizard first-impact observer.
New Branding rank/orb/rate cases are prepared and source-reviewed, with no runtime
claim yet. Full31-module smoke evidence does not stand for remaining functional,
UI/settings, persistence, failure or multiplayer coverage. The full goal remains active.

## Overnight QA checkpoint (2026-10-22, after 06:35 Central; incomplete)

Stash sorting mixed Frostbrand and Warhammer by item level because both custom IDs
were classified as `mh`. The original four-item failure 061238 is retained. A narrow
slot-matched `hwp_mh_`/`hwp_oh_`/`hwp_2h_` family correction passes the original
reproduction 063606 and an eight-item vanilla/Firearms/custom neighbor 063629,
including item conservation and repeated-sort idempotence. Untyped IDs retain their
old family rule. Complete31-module load063532 passes on the same source fingerprint.

The resource isolation investigation captured editor directory size4096 to0 with
unchanged mtime and25 unchanged file hashes. Windows documents directory size as
undefined (WIN32_FILE_ATTRIBUTE_DATA). The new read-only manifest compares recursive
file bytes/SHA256/size/mtime, directory paths/types/mtime, and explicit reparse targets,
failing closed on unreadable entries or observed races. It excludes only undefined
directory size; the outer equality gate remains. Negative controls pass9 tests with2
symlink-privilege skips; actual Windows junction traversal, retarget and cycle tests
pass. Earlier INVALID runs retain that verdict. Later native runs pass all isolation
checks. This is a harness repair, separate from the seven gameplay repairs.

Firearms 054758 passes actual own-hand critical damage controls and 055033 passes
unequal magazine/factor preservation across a native floor transition. Resume 055214
failed fixture materialization because its recipe used nonnative mod aliases; the
corrected fixture is queued. Arsenal 055606 completed all72 cases:68 damage paths
passed and4 dealt zero target damage despite valid equipment/ammo. A bounded eight
path regression uses denser target geometry; all original outcomes remain. No weapon
gameplay fix is inferred from the four misses yet.

Gale 050230 verifies all5 ranks with complete native timed observations. Arcane 050619
verifies plain Blink at all5 ranks; Far Step clipping required a certified destination
fixture, and Living Mana coefficient coverage remains partial. Deadeye 050849 stalled
on a missing QA texture; that fixture dependency and masked-first-error cleanup were
corrected after cause inspection and one isolated lab reset. Corrected cases remain
unverified until their new native runs finish.

Class runs 061712/061850/062027 cleanly rejected the same invalid cloak fixture before
ordinary combat. Native Equipment.as computes back_2b10's requirement as Vit11,
not the previously assumed5. The corrected matched fixture explicitly checks an empty
back, four legal seeded rare20 armor pieces, common20 class weapon and57 earned
primary points. Controlled death/town return and exact base save/load passed within
the failed setup runs; boss/reward/ordinary survival and acquired-reward persistence
receive no credit from them. The new ordinary three-class batch is running.

The final-hour reservation and10:20:52 Central deadline remain unchanged. The ledger
and granular inventories distinguish prepared cases from measured behavior; extensive
skill/orb, module functional, transition and multiplayer coverage remains open.

## Overnight native checkpoint (2026-10-22, after07:17 Central; incomplete)

Cold Firearms resume 064827 and dense eight-path arsenal 065040 pass their scoped native effects; original failures remain. Static same-TT 065338, corrected Arcane 065457 and Deadeye 065727 pass their declared cases with exact coefficient/cadence/lifecycle gaps retained in the granular Specs inventory.

Class 070416/070724/071026 each validates two ordinary native floor transitions with normal path/use. Full runs remain FAIL: floor3 mandatory Bandit encounter/closed-door objective is not handled by the driver; death/no-route outcomes do not establish a class defect. Boss/reward/town completion remains unverified. The Python-only exit adapter derives prefab rotation, verifies the actual unique physics sensor and native top usable, then requires a real live-floor change; it never executes the exit script or sets transition flags.

Priority-v runs36 prepared Firearms/Specs cases serially under unchanged isolation gates and frozen queued source. No full-coverage completion is claimed; see QA_OVERNIGHT and the four inventories for exact scopes, fingerprints, gaps and the deadline.

## Overnight build and native checkpoint (2026-10-22, 09:10 Central; incomplete)

Eight scoped gameplay repairs now have passing reproductions: Shadow Strike,
Riposte, per-gun magazine crit, Hoarder HUD cleanup, Thunder Orb cast attribution,
returning-arrow catches, custom weapon-family stash sorting and Dragon's Breath
patch persistence. Historical failures, invalid runs and fixture/oracle failures
remain retained. The final native regression set and newly corrected measurement
fixtures are pending, so these separate passes do not establish final-code or
full-sweep completion.

Dragon's Breath had lost five of its six authored cone patches per shell to the
native ordinary summon cap of one. The new subtype retains DangerAreaBehaviorP
and exempts only its own producer through the native infiniteSummons list; damage,
TTL binds, six-patch geometry and ownership remain unchanged. Run 085158 passes
both qualities with two shells and twelve patches each: actual target losses
1037.121 and 2656.579 HP, exact initial TTL 1000/3000 ms, 500 ms frequency, positive
countdowns, subsequent cadence, terminal expiry and an absence tail. No trace is
truncated. Grenades 085345 also passes all nine rank-quality cases using native
countdown observations. Earlier wall-span and censored observations retain their
original verdicts.

The current granular inventories record 45 scoped PASS, 5 PARTIAL and 10 UNTESTED of
60 built fourth-spec skill-rank rows, plus 37 scoped PASS, 24 UNTESTED and 4 ally BLOCKED
of 65 orb-quality rows. The partial skill rows retain Living Mana's exact-regeneration
coefficient gap. Firearms records 26 of 75 orb-quality rows with scoped passes; its
new 60-row skill-rank matrix remains UNTESTED, separate from existing baseline and
focused gun/ammo/persistence observations. True co-op and broader legal combinations
remain unverified. Debug counters and source review do not add runtime credit.

The three hidden HoH1 ports remain hidden. Their full 31-module ordinary cases each
complete two native floor transitions, but all three full runs still fail before
the final boss; the driver omits floor 3's mandatory Bandit encounter/unlock objective.
Boss/reward completion, natural town return and acquired-reward persistence receive
no credit. Of 39 effective skills, only Shadow Strike and Riposte have scoped granular
passes, at ranks 1/5 with their retained controls; the other 37 skills and intermediate
rank effects remain open. Nine selected-mastery save/reload combinations are untested.
Controlled base-save/death/town-return evidence stays separate. There are no built
HoH1 orbs, and parked or planner-only content remains excluded.

At the clean native boundary, `.venv/Scripts/python.exe -B tools/build.py` completed
with exit 0 and generated all release assets. The 32 `dist/` archives comprise 31
individual modules plus `HammerwatchPlus-All.bin`. Readback verified every header,
metadata record, unique path set and decompressed payload against current release
entries; All contains their exact 955-entry union, with no GameLab/local-only paths.
All-in-one SHA256:
`8d42ca89b379f7bb4ada76085fa6cc1e5ec3c28d6aacbdd4970393c0ecf01274`.
The complete 32-file hash manifest is retained at
`gamelab/results/qa-20261022-dist-build-manifest.json`. Post-build
`tools/build.py --check`, `tools/list_verbs.py --check` and `git diff --check` pass.
Packaging verification does not replace the pending final native regressions.

## Overnight regression and handoff checkpoint (2026-10-22; incomplete)

Eight gameplay repairs retain passing native reproductions: Shadow Strike, Riposte,
per-hand magazine crit, Hoarder HUD cleanup, Static Charge cast attribution,
returning-arrow catches, typed weapon-family Stash sorting and Dragon's Breath
patch persistence. The required final14 regression scopes all passed at their
recorded fingerprints. Final magazine 093247, Hoarder 093432, Riposte 093528 and
Shadow 093637 join the final native Static/Return/Stash/variant proofs. Later changes
only extend read-only GameLab dead-player mana telemetry; relevant production and
release payloads remain unchanged. The manifest explicitly separates these epochs.

Granular fourth-spec coverage is55/60 scoped skill-rank PASS and5 LivingMana PARTIAL.
Orb qualities are47 PASS,3 PARTIAL,11 UNTESTED and4 ally BLOCKED out of65. Font/Conduit
093729 passes independent primary/cast timelines and exact mana refunds; Provisions
094004 passes earned caps, exclusions, source-CD deltas and expiry; Feedback 094540
passes all9 real-input casts, bank caps, consumption, multipliers and reversion.
Ward proves actual185/170 incoming HP loss and expiry200, but native Refresh averages
old/new intensities while stacks ramp, so exact settled coefficients remain PARTIAL.
Barrier proves protection, mana drain and expiry death in 094732, but its precise
post-death assertion was unavailable. The new read-only field compiled in 100030;
that fresh Barrier run failed geometry before any effect trial and grants no credit.
Branding/Gale lane failures likewise executed zero ability trials. All originals stay.

Firearms has10/60 skill ranks scoped PASS,10 PARTIAL and40 UNTESTED; orb qualities
are42/75 scoped PASS,32 UNTESTED and1 true-co-op BLOCKED. Elements 095401 retains
340000 native distribution rolls across five base ranks and12 weighted qualities,
plus real gunfire/HP at every base rank. Orb-specific natural projectile frequencies
and damage amplitude are separate gaps. Frag cooling-refusal trials were issued
only after native cooldown zero; Focus's additive chance expectation contradicted
native complementary-probability stacking. Both five-rank sets stay PARTIAL with
all raw FAILs retained. They are not additional gameplay defects or balance changes.

Bloodlust/Judgement 095729 adds all10 controlled native kill-hook rank effects:
health gains10/20/30/40/50 and mana3/4/5/6/7. The HoH1 matrix is now4/39 skills and
14/191 positive-rank slots scoped PASS;35 skills,177 rank slots and9 selected-mastery
save combinations remain untested. Every ordinary full31 class run still fails
before the final boss after two actual floor transitions. Implementing the driver's
floor3 Bandit encounter/unlock objective remains necessary before claiming ordinary
boss, reward, natural town-return or acquired-reward persistence coverage.

Additional functional scopes pass: settings search and two-tab stash save/restart
095605 (24 runner assertions), Architect native picker/pricing 100154, controlled
Strongbox/Abyss no-reward timeouts 100238/100326, gun-arm 100414 and native town object
rebuilding 100615. Fresh standalone dependency/load cases 100507/100522/100537/100552
pass for all four repaired modules. Module axes retain uncovered UI/tooltips,
settings, successful rewards, persistence, interactions and true-co-op limits.

Native-visibility final doctor is green, including Steam, HoH1 imports, pinned build
25932569 and backup gates. The sandboxed report's Steam visibility refusal is retained
separately; it did not change setup. Post-build override/verb/diff checks pass. All32
release archives remain verified against actual production sources; the all-in-one
contains exactly955 release entries and has SHA256
8d42ca89b379f7bb4ada76085fa6cc1e5ec3c28d6aacbdd4970393c0ecf01274.
The durable package manifest is gamelab/results/qa-20261022-dist-build-manifest.json.
Native isolation guards preserve user config, saves, install assets and input focus.
No parked classes, planner-only designs, IDs or balance contracts were changed.

The complete sweep is not achieved. QA_OVERNIGHT and the four granular inventories
are the resumable record; time exhaustion is a stop condition, not completion.

Final native mod-all 100827 passes the exact31 stack after the read-only Probe change.
The focused101134 case then verifies fractional dead mana12.375 against independent
raw record telemetry and integer12; all8 gates/12 runner assertions pass. This adds
no Barrier ability credit. Module inventory now retains217 axes:31standalonePASS,
23functionalPARTIAL and163UNTESTED, plus9 scoped native-feature PASS records. The
complete sweep remains incomplete at its10-hour limit. Resume commands, unresolved
fixture/oracle causes and required next coverage are in QA_OVERNIGHT; machine-readable
counts and the32-archive hash are in docs/generated/qa_overnight_summary.json.


## Resumed full sweep ? no time limit (2026-10-22)

The user removed the original overnight deadline and activated the goal again. Work remains in progress; the original deadline/final-hour notes below are historical. Verified scoped coverage now includes60/60 fourth-spec rank cases,49/65orb qualities (nine fresh Branding qualities awaiting granular audit; maximum combo failed),20/60 Firearms ranks,42/75orb qualities,62/191HoH1positive ranks and9/9mastery save/reload combinations. Native stat-only scopes remain separate from combat/cadence/mitigation.

Fresh full-stack `mod-all 20261022-111422` and minimal `null-payload 111454` compile/load checks passed with the read-only per-frame resource observer. `qa-firearms-ranks-base 111509` and `qa-specs-living-mana-coefficients 111830` passed; exact per-run hashes are in the ledger/journals. `qa-specs-branding-orbs 113033` now obtains strict fine-grid/native-ray geometry through normal walking but fails the maximum-combination check. `qa-classes-gladiator-hoh2-run 112028` reached Keep3 and died during objective travel; no class/encounter bug is inferred. Controlled endgame weapon tests 112325/112427 failed native equip requirements before attack/parry testing: ilvl35 requirements use unbounded vector interpolation at34/9, not the high endpoint at level10. A QA fixture correction is staged; no production change is inferred from these setup failures.

The source is frozen during each serial GameLab batch. Remaining ranks/orbs, legal interactions, ordinary run lifecycles, UI/acquisition and module functional/persistence/failure paths remain required. See `docs/QA_OVERNIGHT.md` and `docs/generated/qa_overnight_summary.json`; previous repair regressions and all failures are retained.


## Resumed sweep checkpoint (2026-10-22; still active)

The full sweep has no time limit. Scoped native coverage is 60/60 fourth-spec rank rows and 61/65 orb-quality rows (four require true co-op), 60/60 Firearms rank rows and 71/75 orb-quality rows (three Reload rows await a corrected idle-timer test; one requires co-op), and 118/191 positive HoH1 ranks across 26/39 abilities. All nine selected-mastery save/reload combinations pass. These counts cover the recorded effects, not every amplitude, boundary, interaction, UI or ordinary lifecycle requirement.

Two additional gameplay repairs are verified: Branding no longer retains the Essence damage bonus after consumption, and Gladius now deals native weapon-scaled damage instead of zero. Gladius first-contact damage passes at all five ranks in `qa-classes-gladius-collision 20261022-145123`. Current full-stack load passes in `mod-all 145021`; all 31 modules also have standalone load evidence. Full module functionality remains incomplete.

The current serial batch is finishing Branding quality combinations and Sphere acquisition/UI prerequisites. Reload's expired negative input timer and Grimoire's stationary-glyph target distance are source-reviewed QA corrections awaiting native reruns. A Branding combination failed its clear-lane setup before any combat trial; it remains recorded and under investigation. Ordinary runs also need a source-correct reward-window input flow before boss/reward/save coverage can be claimed.

The earlier 32-archive package verification predates the Branding and Gladius repairs. Those archives are historical; current-source packaging and final regressions remain required. The detailed source epochs, original failures and remaining work are retained in `docs/QA_OVERNIGHT.md` and the generated inventories.


## User-requested PR wrap (2026-10-22)

The user requested a natural stopping point for a large remote PR; the goal is paused, not complete. Native batch `resume-n-main` terminated cleanly after15of17cases:8PASS/7FAIL, source `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0` unchanged across every case. Essence cadence and the corrected ordinary Gladiator pilot never started. LastStats/ChatLinks failed fixture prerequisites, Burst/Shadow failed fixture return/landing control, and Static-MM exceeded a parent path-query timeout before a gameplay trial. All original outcomes remain recorded.

Authoritative scoped totals: fourthspec60/60ranks and61/65orb qualities (4trueallyblocked); Firearms60/60ranks and74/75orb qualities (1co-opblocked); HoH1 29/39 skills, 136/191 positive ranks, 9/9 selected-mastery saves. Ordinary own-active/boss/reward/town/death/save coverage, acquisition/UI, exact remaining mechanics/interactions and broad31-module behavior remain open.

The reviewed21-file O-v2 QA bundle is deliberately UNAPPLIED. Its manifest/payloads plus deferred observer/design work are preserved in an ignored local recovery archive indexed by `docs/generated/qa_deferred_work.json`; they are not installed source or runtime passes. Both essential production additions, `mods/classes/players/hwp/gladiator/projectiles/gladius.unit` and `mods/firearms/scripts/HWP/Firearms/Magazine.as`, must accompany the tracked edits.

Current normal packaging now passes:32archives,956all-in-one entries, everydecoded payload equals current source inputs, no localimports or devharness. All-in-one SHA256 `87bcb72411b57255c616a905a041464601022f2de75b4b6b170b7befce48d419`. This supersedes the earlier archive manifest only for package integrity; it is not a packed-game boot or full-sweep PASS. See `docs/generated/qa_pr_archive_manifest.json`, `qa_pr_validation.json` and `qa_pr_checkpoint.json`. The old14-case final-regression checkpoint retains its historical source/coverage limits.


Final PR verification: full-stack `20261022-175415-mod-all-lab` passes all 14 assertions at source `f242a80b25e8c4bdbd048ccf40f0fd7c97a7ce46bdc482c86a6508785878fe19` with clean teardown. The preceding `175056` bootstrap-shutdown access violation is retained; only isolated GameLab saves/appdata were reset before the successful recheck. Nine new source files received formatting-only cleanup, with native tokens/scalars or Python AST preserved. Final normal packaging verifies all 32 archives and 956 all-in-one payloads at this source; SHA256 `87bcb72411b57255c616a905a041464601022f2de75b4b6b170b7befce48d419`. Historical patch contents are preserved byte-for-byte in `docs/generated/qa_historical_patch_artifacts.json`. This adds no ability-coverage credit and does not complete the paused sweep.

## Devil Forgemaster: Penance as an alternate form, icon ideas (2026-10-22)

Planner only, nothing built:
- Sacrificial Penance has its own record (`planner/data/skills/priest-spec4-penance.json`) with
  `alt_of: priest-spec4-active` and `alt_when`. `mine("skills")` leaves alternate forms out, so
  the spec still counts 1 active and 1 passive; the page draws the form inside Necrotic
  Resurrection's card (checked in a headless Edge screenshot of `#priest`). Necrotic
  Resurrection's levels no longer carry the Penance numbers; Penance's own levels do (1/1/2/2/3).
- Icon ideas (`tools/icon_art/sp_pri.py`, picker ids `specsP.<name>`, published to the picker
  https://claude.ai/artifact/PSk1d9NwASasB5zqmnccNq): Necrotic Resurrection, Sacrificial
  Penance, Call of Heresy (24x24) and the Heresy stack below 5 and at 5+ (14x14). Below 5 is
  purple; 5+ is red hot, each idea the same letter's motif gone too far, so the two read apart.
  The planner shows no icon for them until they are built (`planner_icons.py` cuts icons from
  the game's atlases only).
- The 5+ icon swaps on the one Heresy stack (the user's call: not two stacks). How to swap a
  buff's icon in script is not checked against the engine yet.
- Penance (the user's rules): mana 50, no cooldown of its own. It shares Necrotic Resurrection's,
  so it can't be used while that is on cooldown. Using it consumes your Divine Favor and starts no
  cooldown, so the skill is Necrotic Resurrection again, ready to cast.
- Round 2 (`tools/icon_art/sp_pri2.py`, ids `specsP2.<name>`, same picker). The user's round-1
  picks were Necrotic Resurrection a, Sacrificial Penance a, Call of Heresy c ("but replace the
  sigil with an eye") and Heresy b at both levels. This round has three refinements of each pick,
  with the pick beside them, plus first ideas for the six icons round 1 left out: the spec emblem
  (`pri_class`), the four orbs (Ravenous Lunge, Rot Bloom, Pyre Sacrifice, Deeper Depravity) and
  `hud_devouring`, the status shown during the 3 s lunge-and-eat channel.
- Round 3 (`tools/icon_art/sp_pri3.py`, ids `specsP3.<name>`, same picker). These six were settled
  in round 2 and are in `art/specs/override/` (`sp_pri3.py --finals`): Necrotic Resurrection
  (round-1 a), Sacrificial Penance (round-2 c), the emblem (c), Deeper Depravity (a), Ravenous
  Lunge (b) and Rot Bloom (a). Round 3 redoes five of them per the user's notes: Call of Heresy and
  Pyre Sacrifice in necrotic green, both Heresy eyes green (below 5 from round-2 a, 5+ from the
  kept round-1 pick), and the eating status's maw with defined teeth and lips. The icons go into
  the specs sheet when the spec is built (`tools/make_specs_icons.py` has no Priest row yet).
- Round 3's picks: Call of Heresy a, Pyre Sacrifice b, Heresy below 5 a and the eating status b,
  now in `art/specs/override/` (`sp_pri4.py --finals`). Round 4 (`sp_pri4.py`, ids
  `specsP4.<name>`) is only the Heresy 5+ status: the kept round-1 pick with the eye's purple
  round swapped for the green, at three shades; the user took b. All 11 icons are settled.
- They are in the planner: records name them with `icon_art` (the emblem, the three skills, the
  four orbs) and Call of Heresy's `hud_art` (the three statuses), which `planner_icons.py` cuts
  from `art/specs/override/` (14x14 ones centred in the 24x24 cell). Checked in a headless Edge
  screenshot of `#priest`.

## Devil Forgemaster: what building the risen taught (2026-10-22)

The Priest's 4th spec is in `mods/specs` (`scripts/HWP/Specs/Forgemaster.as`, the units made by
`tools/make_forgemaster_risen.py`). Facts measured on the pinned build while building it, each with
its run (`plan-forgemaster-smoke` and `plan-forgemaster`, `gamelab/results/`):

- **`="./x"` resource paths resolve against the unit being loaded, not the file that says it.**
  An enemy's `.inc` (horde_soldier.inc: `./horde_soldier/...`) copied into another folder needs
  the paths absolute, so the generator inlines the `%include "actors/..."` lines and rewrites
  `="./` to the enemy's folder. One include left un-inlined (the generator's regex wanted a
  newline after it and a file ended on its include line) **hung the game at boot** after the
  script compile, with no `[ERR]` line: the harness killed it at 120 s (smoke `20261022-020916`).
- **Effect expressions have no `%` operator**: `pos-y="...%..."` gives
  `[ERR] Effect expression error: Unknown identifier: %` (same run). `rand(i)`, `sin`, `t`, `l`,
  `i` are what the sparkle effects use (`body_glow.effect` is written with them).
- **`ActorBuffList.HasBuff(uint)` matches the def's `m_pathHash`**, not a name hash: the raise
  channel's "is the raising buff still on" check cancelled at once until it passed
  `Buff("raising").m_pathHash` (smoke `20261022-021542`, "channel cancelled: the raising buff ended
  early"; `20261022-021807` after).
- **`PlayerSkillDirectional.Deactivate` starts the cooldown only when the cast passed its
  castpoint** (`m_castingT >= m_castpoint`). A buff with `silence` applied by the cast itself ends
  the cast before that (PlayerTargetingHelper.as:464), so a skill that silences its caster must set
  `m_cooldownC` itself in `NetActivate` (smoke `20261022-021807`: cooldown left 0 after the raise;
  `plan-forgemaster 20261022-022037`: 12116 ms left once set there).
- **Vanilla Divine Protection ships a null aura.** `pri_divine_protection.sval` has a
  `Modifiers::Aura` with `aura-buff` "null" and `aura-range` 1 at its base rank (an upgrade fills
  them in). `Aura::Update` applies `ActorBuff(player, null, ...)` to every friendly actor within 1 of
  the priest, and `CompositeActorBehavior::ApplyBuff` reads `buff.m_def.m_tags` (line 514):
  `Script exception: Null pointer access`. A vanilla priest never has a friendly actor on its own
  position; a summon that has just leash-teleported onto it does, so every leash teleport of a risen
  threw once (`20261022-022037`, "Last script exception repeated" 1-10, each right after a
  `teleport` back). The risen classes override `ApplyBuff` and drop a buff with no def.
- **A unit the XML parser rejects crashes the game.** `Failed to parse XML tree: invalid closing tag
  name, near "</scene>"` on loading a body unit, then the process exited with code 1 (no further log
  line; `20261022-022037`, the raise_all table died at its 4th unit). The cause was in the generator:
  `phantom_rogue.unit` has a commented-out `<!-- <behavior class="StateActorBehavior"> -->` before
  the real one, which the class detection and the body's behavior swap matched, leaving an unclosed
  comment that swallowed the next 10 lines. The generator now strips XML comments first and refuses
  to write when a unit's tags do not nest (`well_formed`: `%defblock` bodies pasted at their `%block`
  lines, every other `%` line dropped, the game's lenient attributes allowed). 237 of 282 units fail
  a strict XML parse for reasons the game accepts: a bare `&` in `effect?a=1&b=2` paths, attributes
  with no space between them (`origin="55 52"layer="-10"`), a repeated attribute (boss_face's
  `face_spawn=` twice) and `%%PARAM%%` in block bodies.
- **Boss skills are gated on level flags.** The `flag is X` skill conditional is `CondFlag`
  (Utils/Conditional.as:398): `g_flags.IsSet(name)`, the floor's flags, which the arena's script
  sets with `SetFlag` effects (`g_flags.Set(name, FlagState::Level)`, Behaviors/Effects/SetFlag.as)
  and a floor change clears. The Face's skills want `boss_skills`, the totem poles' `totem_skills`,
  the Bandit King's last room `room_4`; the Harbingers, Arista and the Bone Serpent run on `isnt
  disable_*` flags and states alone. Until 2026-10-22 a risen boss set those three flags itself every
  second on every peer (`FightFlags`/`RisenFlags`), a floor-wide side effect for the sake of one
  summon; now the generator drops the `flag is boss_skills|totem_skills|room_4` conditional lines
  from the risen's skills (`ARENA_FLAG_RE`: the 11 Face skills, 12 totem pole skills and the Bandit
  King's three dash attacks), and the risen asserts nothing. `SetFlag` is no longer stripped from a
  risen's skills (a boss's phase flags, `stage2`, `stage5`, `boss_dead`, are level flags its own
  skills set and read, and stay); `TargetRandomPlayer` (an IEffect that retargets the actor at a
  random player) is, since on a summon it aims the boss at its owner.
- **`StateActorBehavior` picks its state every 150-300 ms** (StateActorBehavior.as:252): the first
  state in file order whose `transitions` and `target-` conditionals pass wins; a state with
  `state-charges` 0 is skipped (`m_charges == 0`), one on its `state-cooldown` too. The totem pole's
  `state_start`, `state_inactive_*` and `state_*_fall` all have charges 0, so a totem reaches
  `state_active` 200 ms after it spawns on its own; the arena drives the inactive states through
  `SetActorState` effects.
- **The lunge roll at exactly the range.** `distsq <= LUNGE_RANGE^2` includes a body spawned 40
  away, which is where the test bot put every body: at high Heresy the roll ate the Harbinger
  heavy's body before the raise (24% at Heresy 12, `20261022-022037`), and the elite's in the
  Penance test. The bot now spawns test bodies at 60-70 and resets Heresy before each.
- **A skill spends its mana at its castpoint, not when it activates.** `PlayerSkillDirectional::Update`
  calls `UsePoints(true, ...)` the frame `m_castingT` crosses `castpoint` (PlayerSkillDirectional.as:95);
  `CanActivate` only checks it can be paid (`UsePoints(false, ...)`, PlayerSkill.as:352). A cast the
  player's own buff silences before that frame is free: Necrotic Resurrection's raising buff did exactly
  that, so raises and Penances cost nothing with god mode off too (`plan-forgemaster-bosses
  20261022-052506`, pen_mana "226 -> 226"; the earlier "spent 0" of `20261022-022037` was blamed on
  god mode). The skill spent `GetCost()` itself in `NetActivate` from then; since the review of
  2026-10-22 the channel spends it when it completes (`CompleteChannel`), so a cancelled channel costs
  nothing, and a raise's cooldown starts there too (`StartRaiseCooldown`).
- **Divine Favor loses a stack every 5 s.** `stacks_priest.sval`'s DivineFavor block has a `timer`
  of 5000 ms with `add-stack -1`, reset by any gain. A test that sets 5 stacks with `givestacks` and
  then spends 5 s on setup casts a raise, not a Penance (`20261022-052506`: "raise channel", favor 3
  by the status). The bot sets the stacks last, right before the press.
- **31 enemy attack skills in 15 units aim only at a player-tagged target** (`target-conditional`
  `tag has player`: the Face's spews, the Bandit King's, the Judges', the Spider Queen's, the horde
  necromancer's and sorcerer's, the doomsayer's, the boars', the troll ruler's). A risen's targets are
  enemies, which never carry `player`, so the risen Face kept its target and never attacked
  (`20261022-052506`, boss_face "lost 0.0, target 27577"). The generator rewrites those to `hasnt
  player` (anything that isn't a player); the vanilla `hasnt player` conditionals (the retargeting
  skills) stay as they are, with their `TargetRandomPlayer` gone.
- **`DebugLog` prints nothing in the shipped game.** The `DebugLog` action every boss skill carries
  (`PrintTrace("DebugLog: ...")`, Behaviors/Effects/DebugLog.as:39) never reaches the log, so skill
  activity is invisible. The risen have their own trace instead: `hwp forge trace on` logs
  `risen <id> casts skill <i> <class>` the frame a skill's `IsCasting()` turns on, and every 2 s a line
  of each skill's class, `m_restrictions.IsAvailable()` and `m_cooldownC` (`RisenTrace`, read through
  `CompositeActorBehavior.m_skills`). It showed that a boss that "did nothing" for 15 s was casting:
  the fire totem's `ChannelingSweepSpewSkill` fired twice and swept past a lone brute 102 away, Arista
  cast her spike fans and seeds at a brute 16 away, the Face its eye lasers at one 7 away, while the
  Judge caster killed its brute with the dark orb (`plan-forgemaster-bosses 20261022-062616`). The
  test counts a cast attack skill (any class but Utility, Friendly and Triggered) as attacking and
  records the damage separately; the brute is a real enemy and fights back (a risen Face lost 60% of
  its health to one in 15 s). A brute that vanishes from `near` is a kill: nothing else removes one
  from the emptied arena, and the wisps' spew, the court elites' bolts and the Judge caster's dark orb
  one-shot it before the first 1 s sample (`plan-forgemaster 20261022-064242`).
- **The test arena's origin must not drift.** The first full table (`plan-forgemaster
  20261022-064242`) froze from its 47th unit to its 101st: fifty risen of every kind sat 13 px above
  the body spot with no target for the whole window while the brute hugged the god-mode priest at full
  health, then the undead worked again. Not a targeting bug: the bot re-read the priest's position
  before every unit, the walk and the teleport back moved it a pixel or two each time, and after 46
  units the body spot 60 px to the right had wandered 24 px down onto a level pillar. The risen spawned
  on it was pushed off, and its must-see aim ray to the brute hit the pillar first
  (`CompositeActorBehavior::TargetValue`, RaycastType::Aim): the trace's `foes:` field, which lists
  each enemy within 300 and what the ray hits, showed a fire tower's ray stopped at 8% by a level unit
  4 px away (`plan-forgemaster-occlude 20261022-083736`, section now named `near_priest`); the
  `terrain` grid at the mission start has a 10 px block 40 px right of the player, nothing else within
  110 (`plan-forgemaster-bosses 20261022-084131`). The bot now puts the priest back on the mission
  start before every unit and logs the grid once per table. An enemy standing on the priest is found
  and fought by a risen beside them (the wolf and the cult brother at 083736), and `must-see-target`
  stays on as in the vanilla summons (crusader_pikeman.unit, spider_hatchling_player.unit).
- **`Session.read_log()` returns one string, not lines.** The first cast counting sliced it and joined
  the characters with newlines, so no `casts skill` line ever matched and every row said `casts []`
  although the log had them (`20261022-064242`). `errors_since` had it right (`splitlines`).
- **A weak risen dies to the brute before a leash check that follows the fight.** Bats (50 health),
  beetles (20-40), goblins and the horde crawler (100) were at 8% after 3 s against the brute and dead
  before the leash teleport, so 12 of them "failed" the leash at `20261022-064242`; two more were
  risen bandit brutes that the cleanup's `kill 600 bandit_brute` killed, its filter being a substring
  of the risen's path too. The leash and the walk now come first, while the risen is whole, and the
  brute filter is the vanilla unit's full path (`actors/humans/bandits/bandit_brute.unit`).
- **Four units have nothing to attack with.** The bannermen's skills are a `CompositeActorTriggeredSkill`
  and a `CompositeActorAuraSkill` each (the banner's aura is the whole unit); a risen bannerman
  follows and buffs and never casts at the brute. The table lists a unit whose skills are all Utility,
  Friendly, Triggered or Aura as support instead of failing it.
- **A summon that cannot move must not have a minimum range.** The heavy ballista's one shot wants
  its target 30+ away (`min-range` 30); the brute walked up to the risen ballista and stood at 16, so
  the skill was never available while the ballista lost a quarter of its health to it
  (`plan-forgemaster 20261022-085643`, the trace's `no cd -13`). The generator now drops `min-range`
  from a risen whose only movement is `PassiveMovement` (the ballista is the one such unit that had
  any); the shades and the followers keep theirs. The risen ballista fired twice and took 54% off the
  brute at `plan-forgemaster-units 20261022-101700`.
- **A 60-health risen is a body for nothing.** The yellow jacket (60 health at rank 5's 100%) died to
  the brute two seconds after it spawned, before its sting came off cooldown (`20261022-085643`). A
  risen now has at least `RISEN_MIN_HP` 120 health (times the summon health stats; bosses excepted),
  and the table writes the risen's health fraction back to 1 every second of the attack window (`kill
  600 forgemaster/risen 1.0`), since the question there is whether it attacks; the decay section
  measures health on its own.
- **The full table passes; two chance steps did not.** `plan-forgemaster 20261022-102006` (73 min): all 141
  raisable units raised, attacked (the seven support units listed, not failed), teleported after the
  priest and walked with it, no script errors. The same run's lunge step saw 0 lunges in 25 bodies at
  16% and its bosses step saw no spew from the risen Face within 15 s, so the scenario as a whole
  reads FAIL; the two are below.
- **The lunge die is fair; 25 bodies were too few.** Three runs gave 2, 3 and 0 lunges in 25 bodies at
  16% (064242, 085643, 102006): 5 of 75 where 12 were expected, about a 2% event, enough to check the
  die. `hwp forge roll <n> <chance>` throws `randf()` n times in one frame: 0.1626 and 0.1627 of 20000
  throws landed under 0.16 (`plan-forgemaster-bosses 20261022-114918` and `20261022-120742`, both
  INVALID under the focus rule, below: measured, not citable), so `randf() < chance` is a fair roll and
  every body rolls exactly once (the `lunge roll on` lines). The step now checks the die (14-18% of
  20000) and walks 40 bodies (none in 40 at 16%: 0.09%); those two runs lunged 5 and 9 of 40.
- **The risen Face needs more than 15 s.** The brute spawns after the leash and the walk, so the Face
  (immobile, spew cooldown 6-8 s) found it 10 s after the raise in both runs, at the same 22, 6 and 8
  px (the brute walks the same path onto it), and spewed 3 s later at 084131 but not within the window
  at 102006. The boss attack window is 25 s now (the other units keep 6 s); the Face spewed three times
  from 13 s after the raise at 114918 and from 8 s at 120742 (the two INVALID runs below).
- **A notification window invalidates a run, whatever passed.** `plan-forgemaster-bosses
  20261022-114918` and `20261022-120742` passed every step (lunge 5 and 9 of 40, die 0.1626 and
  0.1627, all ten bosses within 25 s) and are INVALID: in each, Razer Synapse's `RazerAppEngine.exe`
  `Notification-manager` window took the foreground once, after about 60 s of user idle (`cause:
  unexplained`). The user's own switches to the terminal, Discord and the browser are `cause: user` and
  do not count. Neither run is cited as verified; a valid re-run is pending (quiet Razer's
  notifications while the lab runs).

## Devil Forgemaster: review fixes, the eating stance; firearms shops (2026-10-22, later)

- **The valid bosses re-run.** `plan-forgemaster-bosses 20261022-144616` is not INVALID (Razer's
  notifications quiet): Penance, Heresy, the lunge (5 of 40 bodies at 16%, die 0.16 of 20000), all ten
  bosses raised, attacking within 25 s, following and leash-teleporting, no script errors, the 10 s
  boss channel. Its one failed flag was `pen_mana`, a measurement: the review moved the Penance's 50
  mana to the channel's end and the bot still read mana 0.3 s after the cast with god mode back on.
  The bot now keeps god mode off through the channel and reads the drop across the frame the raising
  buff ends (`plan-forgemaster-eat 20261022-154317`).
- **`/code-review medium` on the Forgemaster, 10 findings, all fixed** (`plan-forgemaster-smoke
  20261022-144455`, the bosses run above): Heresy for a raise is added on the host's answer
  (`specs.raised` / `specs.raise_denied`, `HWP::Net::Send` to the caster; the denied answer gives the
  cooldown back), not on the client that asked; the cost and cooldown are spent when the channel
  completes; `OnRaise` reads the body id once and answers "denied" when the body is gone or no risen
  unit exists for it; `RisenUnits`/`DestroyRisen` replace four copies of the owned-unit walk;
  `FightFlags`/`RisenFlags` are gone (the generator strips the arena flag conditionals, above); the
  bot's `risen_rels` fails loudly on a missing body unit; `make_specs_icons.py --check` fails when
  a vec4 the code reads has moved (`CODE_RECTS`). The lunge hit check uses a breakable target dummy
  30 px past the body instead of a walking brute, which once stood 140 px away when the lunge landed
  (`20261022-122738`, "hitting for 60" with nothing in reach).
- **The eating stance (the user's words: the dodge animation towards the body, standing just below it
  facing up, bobbing 1 px, blood flying out; the Penance the same with no bob and a golden light
  brighter as it channels).** `Lunge` and a Penance's first `UpdateChannel` frame call `DodgeTo`: the
  player's own `dash_skill` (`Skills::Charge`) with `m_dist` set to the distance to the spot 10 px
  under the body for that one `Activate(dir, 1.0f)` (restored right after: `NetDoActivate` has copied
  it into `m_distC`), so every peer sees the dodge animation, its dust and sound through
  `PlayerActiveSkillActivate`. `ActiveSkill.Activate` checks only the cooldown and the dash charge
  (ActiveSkill.as:139-150), not silence: the silence check is the input path's
  (PlayerTargetingHelper.as:464), so a dash under the devouring or raising buff goes; `Charge.DoUpdate`
  runs from `ActiveSkill.Update` unconditionally and `GetMoveDir` carries the player under
  lock-movement. No charge, or under 2 px to go: the priest is put on the spot. The landing (dash
  `m_distC <= 0`, or 600 ms) snaps to the spot and `SetAngle(-PI/2)`; `devouring` and the new
  `penance_stance` buff have `lock-rotation` (Player.as:1213 keeps `m_dirAngle` as the aim then), so
  the priest keeps facing the body. Eating: `SetPosition` 1 px up and back every 250 ms,
  `effects/gore/blood/hit_blood.effect` (scale 0.8) at the body every 300 ms, the body kept until the
  devouring buff ends (then `RequestBodyGone`); a lunge roll waits while one is eaten. Penance: no
  bob, `penance_light.effect` (new, `scale` param, a gold sparkle over a warm light, 270 ms) at the
  body every 150 ms with scale 0.3 → 1.5 over the channel, so the overlapping pulses grow. `hwp forge`
  reports `eat`, `bobs`, `bloods`, `lights`, `angle` (degrees, up is -90) and `dy`. Measured by
  `plan-forgemaster-eat 20261022-154317` (shots `eating` and `penance_light`): lunge_jump (the priest from -240,-48 to -120,-38, the body at +120), lunge_faces_up (facing -90 at every bob), lunge_bobs 11, lunge_blood 10, lunge_lift 0, lunge_body_eaten (bodies 0 after the devouring), lunge_hit (the dummy), pen_faces_up (facing -90, 5 px beside and 7 px under the body at the pulses), pen_light 21 pulses over the 3 s, pen_mana 48 (spent at the channel's end).
- **A skill with castpoint 0 still activates a frame late.** `ActiveSkill.Activate` sets `m_castingC =
  max(1, castpoint)` and `DoActivate` (for the dash, `NetDoActivate`: `m_distC = m_dist`) runs in the
  next `Update` when it reaches 0 (ActiveSkill.as:159-160, 292-308). A dodge that borrowed the dash by
  setting `m_dist` and restoring it right after `Activate` ran the dash's own 90 px, and a "done" check
  on `m_distC <= 0` passed before the dash had begun, so the landing snapped the priest to the spot and
  the dash then carried it 90 px past it (`plan-forgemaster-eat 20261022-152706`: the Penance stance
  102 px beside the body; the eating hid it because every bob re-snaps the position). The borrowed
  `m_dist` now stays until the landing (`g_dashKeep`), done is `m_castingC <= 0 && m_distC <= 0`, and
  the landing cancels a dash still running.
- **A bot's two reads are two frames.** The Penance's mana was read 0.3 s after the cast (the cost now
  lands at the channel's end, `20261022-144616` pen_mana "226 -> 226"), then across the channel's end
  with "is the raising buff still on" read before the mana, which let the completion fall between the
  two round trips (`20261022-151923`, "spent -2"). Mana first, then the buff: the mana read while the
  buff was still on is the pre-completion value. And the stance's facing and offsets are recorded by
  the mod at each bob and light pulse (`hwp forge`: `facing`, `shine`, `beside`, `under`) because a
  screenshot takes long enough that the status read after it came after the 3 s eating or channel had
  ended, with the counters cleared and the rotation lock lapsed (`20261022-150819`).
- **Firearms: the seller sells guns to a Firearms Specialist** (`mod-firearms-shop 20261022-143058`,
  `mods/firearms/README.md` for the offers): the Paladin gets no gun in 8 offers, a fresh Specialist's
  weapons are all guns and a gun is back after buying them out. `gl shop` reports gear `base`, `slot`,
  `ilvl` and `tags` now. The gun arm stays pinned while shooting (`plan-firearms-arm 20261022-142503`,
  8/8); `mod-firearms 20261022-142427` and `mod-fishing 20261022-143232` (no rod sprites on the beach)
  pass. The Firearms class-picker showcase PNG is in place but not seen in a shot (assumed).
- **The beta build: the Priest without the Celestial Ruins DLC.** `mods/holylocal` (local_only,
  `beta_into: "core"`) holds the class and its weapon tables with the one `dlc has holy` conditional
  removed. `tools/build.py --beta` (and `deploy.py modded-prod --beta`) folds its three files into
  HWP-core.bin, so a tester enables only HWP-core and HWP-specs; a plain build never carries them
  (`build.py --no-all core`: no `players/priest/class_priest.sval` in the bin; `--beta`: 44 files, the
  packed class has no `dlc` conditional; naming holylocal as well as `--beta` is refused). Verified in
  the lab, whose game has no Celestial Ruins DLC: with core+holylocal the create-character class list
  is warrior, wizard, paladin, priest, ranger, `func select priest` shows the title "Priest" and `func
  name-random` + `func create` makes a level 1 Priest standing in town (`mod-holylocal-priest
  20261022-163957`, shots `with_priest_selected`, `with_priest_in_town`); with core alone the list is
  warrior, wizard, paladin, ranger (`mod-holylocal-priest-control 20261022-164029`). The bot
  (`gamelab/bots/holylocal_priest.py`) reads the list as the children of the `class-list` widget,
  whose ids are the class ids (`CreateCharacterClass.as`). holylocal is for the private beta only,
  with the dev team's permission; remove it before publishing.
- **The install still showed the Thief, Gladiator and Witch Hunter and the old Firearms class
  figure: a stale deploy, not the code.** The install's `mods/HWP-core.bin`, `HWP-classes.bin` and
  `HWP-firearms.bin` were dated 2026-10-19 20:56, before the hide (f32dfe8, 10-21) and the showcase
  figure (f97a942, 10-20); read back with `tools/hwr_archive.py`, the deployed core's
  `CreateCharacterClass.as` has no `IsClassHidden`, the deployed classes module no `HideClass`, and the
  deployed `class_showcase.png` entry is the 237-byte ring (dist's is the 682-byte figure).
  `HammerwatchPlus-All.bin` in the install is 10-19 as well and `deploy.py modded-prod` never rebuilds
  it, so it must not be the enabled one. Only `HWP-specs.bin` and `HWP-holylocal.bin` were deployed on
  10-22. The user redeploys (`deploy.py modded-prod --beta`); not re-run here (the user asked for no
  GameLab runs on the character creation).
- **Raw `%damage%` tokens in the create-character skill tooltips (main menu).** The skill tooltip ends
  in `AppendSkillDesc` (GUI/PlayerMenu/Modifications.as:1028), which fills the description's `%param%`
  tokens from `description-params` only through the unit overload of `Resources::GetString` when the
  record has a live actor; with no player (the main menu's create-character window, record null or not
  yet spawned) it appends the bare string. Vanilla descriptions carry no tokens (the params are listed
  under the text), so only the HWP ones (Firearms, the HoH1 classes: 43 strings) showed it, and only
  there: in town a player exists, which is why the lab's from-town `charcreate` never showed it. Core
  now overrides `Modifications.as` with one line in that branch: `GetString(m_description,
  g_bookColors, descParams)` (the `(string, dictionary, dictionary)` overload is in the API strings;
  `descParams` already holds the level 1 value per token). Assumed, not run: the user asked for no
  GameLab runs here; a script error in that file would show in the game log as `Modifications.as`.
  Compiled since: `mod-all 20261022-193227` (below) loads core with the override and reports no
  script errors; the tooltip's text itself is still unseen.

## PR #9 merged with main: the QA sweep's fixes on top of the Forgemaster (2026-10-22, evening)

- **The merge** (`0f22a6a` on `qa/native-sweep-fixes-20261022`): three textual conflicts, all in
  files both branches appended to. README's specs status line keeps the sweep's crit note and
  main's "the Priest's 4th spec is built"; RE_NOTES keeps both branches' sections; runner.py keeps
  both bot-result writers (`bot-results.jsonl` from the sweep, `bot-<name>.json` from main). The
  AngelScript merged without conflicts (SpecsModule.as, Combat.as, Hands.as auto-merged).
- **Verified on the merged tree:** `mod-all 20261022-193227` PASS, all 31 modules enabled, town
  reached, no script errors in our files, clean teardown; the sweep's Python tests (57 passed,
  2 skipped: `gamelab/tests`, `test_res_snapshot.py`, `test_runner_restart.py`,
  `tools/compiler_selftest.py`); `build.py --check`, `list_verbs.py --check`. Not re-run here: the
  sweep's gameplay reproductions (its own run ids are in `docs/QA_OVERNIGHT.md`).
- **Review of the gameplay changes (read against the decompiled source):** `riposte.sval`'s old
  `Modifiers::Thorns` does not exist in the game (no such class in StatModifier.as), so Riposte
  had no thorns at all; `Modifiers::AddThorns` with `thorns-bind` is the real class (its
  `thorns` vec2 resolves through the `-bind` convention like Damage's `physical`). Shadow Strike's
  landing goes through `Explode` (Actions/Explode.as params `min-radius`, `dist-scaling`,
  `hit-*`), the way the Warrior's charge lands. The Firearms rounds' `off-hand` flags agree with
  the `_off` name test `HWPFirearmsGunShot` uses for the magazine debit (`glock_round_dual` is
  the main pistol's round in both the main attack's mixes and the off-hand attack's burst).
  `HWPFirearmsBreathArea` appends the patch producer to the game's global `infiniteSummons`
  (Player.as:1), the list the mercenaries use, so `Player.Update` caps those areas at 1000
  instead of 1. `HWPFirearmsMagazineCrit : CritDamage` uses CritDamage's `m_role`,
  `m_attackCritDmg`, `m_spellCritDmg`. The magazine split (`Magazine.as`) is bonus-only state
  in core's save bag (`firearms.mag.*`) and never touches the native clip.
- **Left as is, flagged:** `docs/generated/qa_*.json` adds about 4.5 MB of QA evidence to the
  repo (the five largest 260 KB to 940 KB); the sweep's notes glued run times to the word before
  them ("Dragon085158"), fixed here by inserting the space (46 in RE_NOTES, 92 in QA_OVERNIGHT);
  "all12", "Full31"-style glued counts remain. The new res/ isolation snapshot hashes every file
  under the install's `res/` (118 files) before and after each run, a second or so each.


## Agent-compatible QA handoff (2026-10-22)

AGENTS.md now leads to the GameLab quickstart, regression selection/known-failure
map and detailed skill. CLAUDE.md delegates to the same committed instructions.
The skill documents completed bot returns, partial/outer verdict checks and the
separate source-fingerprint journal. `tools/qa_batch.py` replaces reliance on the
local date-specific queue wrapper with a portable, fail-fast serial CLI and dry-run.
The 49 deferred text drafts/control/plan files are committed in a hash-indexed,
unapplied bundle; old installers must be rebased/reviewed before use. README/ledger
historical sections are clearly separated from current status. No gameplay source
or native-coverage claim changes in this follow-up.

## PR #9's code review, applied after the merge (2026-10-22, night)

The `/code-review medium` of PR #9 reported after the PR was merged (`2f61d64`), so its ten
findings are fixed on `qa-review-fixes` off main. Eight changed code, two are declined with a
measurement.

- **Off-hand rounds are flagged, not named** (Elemental.as, attacks_firearms.sval).
  `HWPFirearmsGunShot` used to decide which magazine a round debits by `"_off"` appearing in the
  projectile path; a renamed unit would have flipped a round to the other gun silently. Every
  off-hand shot now carries `<bool name="off-hand">true</bool>`, the param name vanilla
  `Damage.as` uses for the same thing: a `ShotOff` block beside `Shot` for the eleven macro calls
  (`hcannon_round_off`, `glock_round_off`) and the bool on the four inline `glock_round_off` dicts.
  `GetParamBool("off-hand", ...)` is read first; the name test remains only as the default for a
  round without the param. `glock_round_dual` stays a main-hand round (it is the main pistol's
  shot in both attacks' mixes).
- **Extended Clip Crit with no actor** (Magazine.as `HWPFirearmsMagazineCrit`). `rec.actor` can be
  null (a stat sheet from a menu, a record whose actor is gone); `MagazineRounds(null)` returned 0,
  so the modifier gave no attack crit at all there. With no actor both hands now use the shared
  clip (`intensity`), as `CritDamage` itself does.
- **One list of the rifle's cartridge skills** (Magazine.as `IsRifleRound`, used by Combat.as's
  stack-crit). The review asked why `hwp_attack_flamer` was missing from the hard-coded trio
  (`rifle`, `rifle_epic`, `autofire`): the flame rifle's attack is a mana channel and the grenade
  launcher spends no clip either (attacks_firearms.sval, no `clip` keyword in those skills), so
  both keep the shared-clip bonus by design. The reason now sits with the list.
- **`di.Weapon` overwrite, kept and documented** (Magazine.as `HWPFirearmsGunDamage`). Setting
  the damage's weapon to the firing gun's own attack skill reaches every reader: per-weapon damage
  statistics (Player.as `DamagedActor`), lifesteal and the `PlayerDamageActor` hook (PlayerBase.as),
  kill-trigger orbs (Player.as `KilledActor`), the `PlayerDamaged`/`PlayerDied` messages. All
  resolve `GetSkill()` to a skill the player has, and crediting the round to the gun that fired it
  is the intent. The comment on the class lists them.
- **Stash families of typed ids** (StashSort.as `Family`). `hwp_mh_<family>` in an unexpected slot
  fell through to `parts[1]` and sorted as a family called "mh". The slot token is never a family:
  a typed id now returns its family whatever slot the item sits in.
- **Launcher never leaves a dirty lock over an unreadable res/** (launcher.py). `install_res_snapshot`
  raises `OSError` when a file changes under it or cannot be read; before the run that is now a
  `PREFLIGHT` refusal (exit 2, the empty results dir removed); after the run the failure is recorded
  as a differing "after" snapshot, so the `install res/ unchanged` assertion fails and the verdict is
  INVALID, with the error in `isolation-res.json`.
- **Bot results that are not JSON** (runner.py). The `bot-results.jsonl` line now serializes with
  `default=str` inside a try, like the `bot-<name>.json` writer: a bot returning a `Path` or a set no
  longer fails its own step after the game work is done.
- **`restart` with `choice: "town"`** (runner.py `enter_fixture`). An explicit "town" raised when
  the game went straight to town with no character-selection window, while the default (no
  choice) passed; "town" is the default and is now treated the same. Only an explicit "resume"
  still needs the window. Two tests added (`test_runner_restart.py`).
- **Tests under `gamelab/tests/`**: `test_res_snapshot.py` and `test_runner_restart.py` moved there
  from `gamelab/` (`git mv`); 52 passed, 2 skipped from `python -m pytest gamelab/tests`, the same
  count from the repo root.
- **Declined: the res/ snapshot's cost.** The review flagged hashing ~296 MB twice per run. Measured
  here: `install_res_snapshot()` over 133 entries takes 0.2 s with a warm file cache (a cold one a
  few seconds), against runs of 13 s and up; the before/after hash is the isolation evidence the
  INVALID verdict rests on, so it stays.
- **Verified:** `mod-all 20261022-194902` PASS (all modules compiled with the new Elemental.as,
  Magazine.as, Combat.as, StashSort.as and the regenerated attack table; no script errors in our
  files). `qa-firearms-magazine-crit 20261022-194932` PASS (12 assertions: the per-gun split with the explicit flags). `qa-content-stash-families 20261022-195143` PASS (the typed ids still group by family). `build.py --check`, `list_verbs.py --check`, pytest as above.

## 2026-10-18 (afternoon): reproducible generated floors (`mission ... seed=N`)

- **The generator's RNG is the engine's global one, and it is shared.** Every draw in
  `Generators/*.as` is `randi`/`randf`/`randdir`/`roll_round` (no `RandomSequence`, no script
  `srand`). `srand(seed)` does drive `randi()` (rand-check 20261018-161345, verified), but:
  - the engine draws from it every frame: srand, then a draw one frame later, differs; in the
    same frame it matches (rand-frames 20261018-161957, verified);
  - inside `MissionGameMode::Generate` another thread draws concurrently: srand, a CPU-only
    spin, then `randi()` gave a different value on each load (seed-repeat 20261018-162919,
    verified). Reseeding after every `PreloaderYield` was not enough (seed-repeat 20261018-162502).
- **Script globals do not survive `ChangeLevel`** (seed-repeat 20261018-160442: a global set by
  the verb read 0 on the new floor, verified). Generate and Start of one level share globals.
- **What works:** gamelab-hands overrides the 11 drawing `Generators/*.as` files (made by
  `tools/make_seeded_generators.py`, `.orig` beside each, `--check` for drift) with the draws
  routed through `GameLab::GenRand*`: a private `RandomSequence` while a seeded floor builds,
  the vanilla calls otherwise. The seed rides in the town save (TownRecordSave hook, read by
  the TownRecordLoad that `Generate` fires at MissionGameMode.as:434, before the generator at
  :456); GameModeStart srands the global RNG for the Start draws and re-saves the town without
  it; the module's first UpdateFrame ends the private sequence.
  - seed-repeat 20261018-163350 and 20261018-163508: PASS. Seed 12345 from town gives the same
    floor before and after a restart, and across the two runs: spawn (-16,-352), secret walls,
    chests, piles, reward spots, 173234 generator draws each time. Seed 777 differs.
  - Same-seed re-entry from a floor of the same run is NOT the same floor: Run flags pick
    run-unique set pieces (MissionPrefabDef.as:83) and are only cleared in town
    (TownGameMode.as:33) or by the loadout menu (MissionLoadoutMenu.as:209), which `mission`
    skips. Enter from town to compare.
  - Assumed, not measured: `randi(lo, hi)` taken as inclusive (one 1-unit jitter), `randdir(false)`
    as a point in the unit disc; draws outside `Generators/` during Start (RewardSpot,
    post-gen commands) are seeded only through the shared global RNG, yet matched in both runs.

## 2026-10-18 (evening): watch-mode input without focus; chest-watch clean

- **Watch input goes through the shim, not the window.** With `GAMELAB_SHIM_INPUT=1` (set by
  watch mode) the capture shim opens mailslot `gamelab_input_<pid>` and hands keys/text to the
  game from its `SDL_PollEvent` hook. The user's real input and foreground are untouched.
  Verified: a `gl ping` typed into a live watch game with the window unfocused (user saw the console).
- **Focus belief** (shim input only): one `FOCUS_GAINED` injected, `FOCUS_LOST`/`LEAVE` dropped,
  `SDL_GetWindowFlags` carries input+mouse focus, `SDL_GetMouseFocus` falls back to the game window.
  Needed for keys to be taken (chest-watch 20261018-170421 failed without the mouse-focus part; -170545 worked).
- **Why Enter was lost on the main menu:** any mouse-position change puts the menu in mouse mode
  (`GUI/WindowInput.as:84-91`), where MenuForward clicks only the hovered widget
  (`GUI/WindowObject.as:96-113`), so nothing. Watch 20261018-172146 lost three Enters after the
  user's pointer crossed the window; lab -172828 reproduced it with one posted WM_MOUSEMOVE
  (`GAMELAB_SIM_BLUR=1`). Fix: with shim input the shim drops SDL mouse events 0x400-0x403 and
  `SDL_GetMouseState` answers 0,0 with no buttons. Verified: lab -173744 (same repro) PASS, watch
  -174021 PASS (session on the first Enter). `gl pointer` writes the engine MousePos and is unaffected.
- `menu-continue` (native `ContinueGame()` from a gl line) replies ok but starts nothing (lab
  -172530); kept only as a measured dead end.
- **Unit ids are reused.** Gold 8740 taken at one trinket chest, then the other chest's Infused
  Amethyst spawned as 8740 and was skipped as already tried (lab -173358). Pilot's tried set and
  chest-drop diff now key on the unit's identity (`LootKey`: debug name + item name).
- **Kiting through walls:** threats are fought only if engageable (clear shot or a route within
  half kite range, cached 5 s); fire needs `ClearShot`; the strafe side flips when stuck. Lab -171345:
  61 fights, 0 timeouts, 0 stuck.
- **Far walls no longer beat near loot:** the quarter-distance pull of a secret wall with a pending
  reward applies only within `WALL_PULL_R` 200. Watch -174021 walked to wall 13007 (335 away,
  counted 84) past the just-released chest 8704 (130); lab -174309 looted the first room first.
- Hidden units (blueprints with no factory) are skipped as loot targets (lab -164438).

## 2026-10-20 (night): Dev Arena spikes (docs/devarena/SPEC.md build order 1)
All on the pinned build, scenarios in `gamelab/scenarios/devarena/`, code in `mods/devarena/`.
- **A skill rebuild applies live.** Patching a skill's sval and calling `LoadSkills()` on the
  frame no class skill is casting changes the next cast: cooldown 20000 to 3000 ms, area damage
  60 to 99, and the second cast came 4026 ms after the first (spike-rebuild 20261020-222102).
  The deferred apply (queue, then flush when nothing is casting) holds an edit made mid-cast
  until the cast ends (spike-deferred 20261020-222134).
- **A buff retune hits new instances only.** dodge_roll duration 2000 to 6000: the instance
  already running kept 2 s, and a new one ran 6 s (spike-buff 20261020-222307).
- **Freezing mobs takes three locks.** `m_frozen` plus a code-built lock-movement buff still let
  mobs drift 3.8 and 3.9 px in 10 s (spike-freeze 20261020-222234 and -222411, even with the
  velocity zeroed). With a third lock, a static body pinned every frame to its frozen position,
  maxMoved was 0.0 and hpLost 0. The unfrozen control moved 79.7 px and dealt 233 damage
  (20261020-222630).
- **The RNG cannot be pinned for a bench.** Probes taken the same frame after `srand` repeat
  ([735,559,771,...]), but probes 5 or 60 frames later do not (spike-rng 20261020-222444 and
  -222702). Something else draws from the stream every frame. So the bench compares by
  statistics, never by a fixed seed.
- **A mod class loads through the engine's action loader.** Setting a skill action's `class` to
  `HWP::DevArena::ProbeAction` and rebuilding built it once (Actions/IAction.as:282
  InstantiateClass), and one cast fired it once: log `[HWP:devarena] probe action
  'entangle-start' fired (1)` (spike-class 20261020-222728).
- **A non-pausing dock with mouse capture.** The dock draws from the module's `RenderWidgets`
  (hw8 font, UI units) and not as a window, so the game keeps running (paused false).
  - With the pointer over it, the dock takes `Focus::Obtain(Focus::PLAYERMENU)`, as an open
    window does, and the player then takes no attack, skill or move input: a Skill2 press over
    the dock did not cast. Off the dock, focus stays 1, keys move the player and Skill2 casts.
  - Clicks arrive as `MenuInput.Forward` (mouse_left is MenuForward, controls_default.cfg:31).
  - F1 to F12 are unbound in the lab's `res/controls_default.cfg`. F1 is polled with
    `Platform::IsKeyDown(Keyboard, 0, 58)`.
  - The lab window is 640x360 px, which is 768x432 UI units at scale 0.833. At that size the
    dock starts at px 416 (spike-dock 20261020-223329; the first run, 223151, failed only on an
    over-tight px assert).
  - Assumed until the end-of-goal visual run: the layout holds at 1080p and 1440p.
- **The dock takes typed text without a window.** It uses the chat's mechanism
  (GUI/Menus/InGameChat.as).
  - A click on the field calls `ControlBindings.ExpectTextInput()` and
    `m_windowManager.LockInput(true)`. The field then reads the frame's
    `GameInput.GetTextInput(i)` events (spike-text 20261020-224031).
  - Typed text lands in the field. Bound keys pressed while typing type their letters as well:
    a posted d, m and i added "dmi". They do nothing else: the player did not move, and no
    window opened (`gl ui` windows []).
  - Backspace, Enter (Submit) and Escape (Cancel) each arrive as their own event.
  - The window manager's input lock spends Escape (GUI/WindowManager.as Back), so no pause menu
    opened.
  - After `StopExpectTextInput` the keys move the player again.
  - GameLab's inbox frames (`!gl ...~`) come through the same events, so the field skips them.
    As a result "!" and "~" cannot be typed into dock fields.
  - The first run, 20261020-223947, asserted the text without the bound keys' letters.

## 2026-10-20 (night): Dev Arena tuner (docs/devarena/SPEC.md build order 2)
- **The Tune tab works end to end as a player uses it** (tuner-dock 20261020-225735, every
  input posted to the window, buttons aimed by id through `gl da-dock`):
  - F1 opens the dock. A click picks Entangle.
  - Typing 99 into the L5 area-dmg cell made v1 in slot B. It went live, and the skill read 99.
  - The growth [+] stepper made v2: growth 15.2 put L2-L5 on 35/50/66/81 with the base kept
    at 20. The vanilla curve is 20/25/35/45/60, a fitted growth of 9.
  - Ctrl+Z and Ctrl+Y stepped B between v1 and v2.
  - F2 swapped to A and the skill read vanilla 60, then swapped back.
  - Castpoint 150 -> 100 moved the timeline's cast time to 100 as well (v3).
  - Pin mode pinned L3 without making a version. Focus never left the user's window.
- **Ctrl and Shift chords reach the game through PostMessage** (`gamelab/winproc.py` mods,
  `{"do":"key","key":"ctrl+z"}`). The module saw them through `Platform::IsKeyDown` scancodes
  224 (LCtrl), 29 (Z) and 28 (Y) (same run).
- **The tuner state survives a restart.** The override file written by
  `tools/devarena/overrides.py` from that run's last override line was read at boot. The tuner
  came back on v3 in B with its pin, and Entangle was castpoint 100 with L5 area-dmg 81 before
  any input (export-boot 20261020-230402).
- **A runtime-patch mod changes vanilla skills without shadowing files.** `vanilla-tuning` with
  two rows (ran_mark cooldown 1234, castpoint 77) logged `patched 1 skill defs (2 edits applied,
  0 failed)` on the first frame with a player, and `da-skill ran_mark` read both values (same run).

## 2026-10-20 (night): Dev Arena loadouts (docs/devarena/SPEC.md build order 3)
- **All 74 presets apply on a live floor and read back** (loadout-all 20261020-233249): class,
  level, picks, stats, gear base id with quality and ilvl per slot, trinkets, and budgets not
  overspent. 76 applies, 0 mismatches, 0 new log errors.
- **`ChangeClass` works mid-floor without a reload.** paladin_divine/end applied from a
  ranger: `da-loadout` read class paladin_divine level 20, the HUD skill bar showed the paladin
  skills, and `state` still read phase mission (same run). The re-skinned sprite is assumed.
- **The Loadout tab works as a player uses it** (loadout-dock 20261020-232844, all input
  posted, buttons aimed by id):
  - Class and subclass chips, then one click applied paladin_divine/early.
  - A star logged the favorite. Two compare ticks.
  - str [+] was refused with `no stat points`, because a preset spends every point. level [+]
    and then str [+] landed, and `da-loadout` read `edited` true at level 6.
  - Save variant logged str 9 at level 6. Revert re-applied the preset (`edited` false, level 5).
  - The favorites row re-applied it in one click from the ranger.
  - The mini HUD showed `DEV | paladin_divine/early` with the dock closed.
- **A skill level reads one upgrade over the base; upgrades do not stack.** `AddPlayerSkill`
  builds `{ m_levelParams[lvl-1], m_levelParams[0] }` (PlayerBase.as:179-187), so an edit to
  upgrade k only reaches level k+1. tools/devarena/tooltip_lint.py models it that way.
- **Tooltip numbers are text, not field reads** (`LoadSkillDescriptionParams`,
  PlayerClass.as:212-238). A tuner edit therefore leaves the tooltip stale, and the lint
  reports it.
- AngelScript: `string &inout` is refused on a non-handle type ("Only object types that support
  object handles can use &inout"). Use `&in` plus `&out`.

## 2026-10-20 (night): Dev Arena arena and golem (docs/devarena/SPEC.md build order 4)
- **The Arena tab works as a player uses it** (arena-dock 20261020-235731, all input posted,
  buttons by id): god/nocd/mana chips set `CVars::ChtGodmode`/`ChtNoCooldowns` (read back by
  `da-arena`), a footman pack armed and placed with `pointer 150 180 mclick` (4 units, 205 units
  left of the player), Cull ended the encounter (`clear 2112 ms taken 0 deaths 0`), F6 paused
  and resumed, Esc disarmed without the pause menu, F3 reset, Reload regenerated floor 13 from
  seed 4242 at the same start (928,112) with the toggles restored from the town save.
- **A level change in the middle of an emulated click leaves `MenuInput.Forward.Pressed` set.**
  The dock re-opened on the new floor and took it as a fresh click every frame: a reload loop
  (arena-dock 20261020-235104). Reload now waits 10 frames, and a new floor ignores dock clicks
  for 10 frames and clears the press.
- **Esc reaches `g_gameMode.MenuBack()` before the pause menu.** The HUD asks its components in
  order (HUD.as:538-547); one that returns true keeps the menu shut (20261020-235519 without,
  20261020-235731 with).
- **The golem pull measures** (golem-room 20261020-235415): F4 in, footman elite 1M at
  armor 60 res 30, the ranger's main attack held 4 s north, `golem-pull` dps 441 / 28 hits,
  breakdown attributes all of it (unattributed 0). Profile, NG+, pool and debuff chips each
  respawned it as asked (`golem spawn dummy ngp 1 hp 4000000`), F4 out.
- Golem damage feeds the game's statistics: the pull unlocked the "Heavy Hitters I"
  accomplishment (shot `pulling`).
- AngelScript: `out` is a keyword; a local named `out` fails with "Expected '('".
- **Wall pieces produced at run time block and render** (golem-room 20261021-000718):
  `Resources::GetUnitProducer("doodads/walls/barracks/v_32.unit").Produce(...)` on a
  dark_citadel floor stood in the corridor and stopped the player 6 units short of it.
- **A float round trip through `dictionary` is not reliable**: per-skill damage stored with
  `set(k, float)` and read with `get(k, float &out)` came back as INT_MIN (cast to int) in one
  of two identical runs (golem-room 20261021-000549). Parallel arrays replace it.
- While the dock is hovered it eats movement: an `input` walk with the mouse left over a chip
  did not move the player. Park the pointer off the dock first.

## 2026-10-21: Dev Arena composer, HPs, acceptance

Verified on the pinned build unless marked; run ids are `gamelab/results/<id>-<scenario>-lab/`.

- **`ButtonState` is a value type** (no `@` handles; Bench.as:239 keeps them by value).
- **A gl reply must not carry an `"of"` key**: `gamelab/session.py:465` reads it as a chunked
  reply and waits for the rest.
- **Entangle's per-pull damage swings 75 to 2490** on the same golem and loadout (bench-dock
  20261021-002300, -002422, -002810, -004957). Benches need several pulls and a noise verdict.
- **Some presses never take**: paladin_divine/early's skill2 reads CanActivate but casts
  nothing (76 presses a pull). Bench.as:835-855 backs a press that is still ready 400 ms on off
  for 2 s and logs `bench-stuck` once per bench.
- **A typed dock field holds `Focus::Obtain(PLAYERMENU)`** (Dock.as:515), so no skill casts
  while typing; edits are deferred to the next frame (spike-deferred 20261020-222134).
- **Composing a skill goes through `AddPlayerSkill`**, which stacks level dicts on the base
  (PlayerBase.as:189-215). `GetSkillLevel` is 1-based; the values index is `level - 1`
  (PlayerBase.as:187).
- **`PlayerSkillDef.m_name` is resolved text**, not a string key
  (Behaviors/Actors/Player/PlayerClass.as:69, 145).
- **SValue dict key order is not preserved** in log output; log regexes must not assume it.
- **gl replies contain `lastError`**: a `log_lacks` regex for errors needs `\b(error|...)\b`.
- **MissionEndMenu clears the run's trinkets** (`ResetForNewMission`, GUI/MissionEndMenu.as:428;
  hp5-relaunch 20261021-012907).
- **A fresh town has no buildings**; the Subclass Picker stands in guild hall tier 3 (the second
  upgrade, variation 2). Its index wraps: `(index + numPicks) % numPicks`
  (SubclassPickShopContent.as:70).
- `da-skill` returns bind values as strings (compare `"99"`, not `99`).
- HP runs: hp1-feel 20261021-012123, hp2-golem-tuning 20261021-003613, hp3-loadout-compare
  20261021-003510, hp4-compose 20261021-011713, spec-clone 20261021-011648, hp5-relaunch
  20261021-013132, hp6-ship 20261021-014726, hp7-autotune 20261021-015752.
- **UI units by resolution** (ui_scale default): 1920x1080 is 960x540 at `m_wndScale` 2,
  2560x1440 is 854x480 at 3 (res 20261021-022008, `gl da-res`). `SetVar("v_resolution")` resizes
  the window live within 2 s (the options window's path, GUI/Options/ResolutionsWindow.as:44).
- **The HUD's bottom bar draws over a mod's GUI** (res 20261021-021235: the dock footer under the
  pet icons). Measured bar: centred, about 142 UI units each side, 30 tall.
- **Adversarial review, fixed** (edge 20261021-025759, hp5-relaunch 20261021-025859, bench-bleed
  20261021-025945): AngelScript `parseInt` wraps past int32 (4294967396 landed as 100), so int
  leaves now check the range; a typed field past its limit is refused, not committed cut off
  (164 vanilla string binds are over the old 48-char limit, now 160); a castpoint edit no longer
  moves timeline entry 0; negative castpoint/cooldown are refused. **A pull's area units and
  projectiles outlive it** and hit the next pull's golem (A after a strong B: 190346 damage):
  `FetchUnitsWithBehavior("IProjectile"/"IOwnedUnit", ...)` takes interface names; each reset
  clears the player's projectiles and owned non-actor units (3 per pull here), and A then read
  798/625/760 dps.
- **Second review** (acceptance 20261021-030146, hp1 030856, hp4 030920 PASS; its own edge runs
  failed): 30 of 47 vanilla skills with a castpoint open their timeline on the cast
  (`[100,"cast"]`, Trap), so the castpoint move now skips only an entry followed by `"start"`.
  **The dock's layout pass runs the clicked button before the field commits**, so a castpoint
  typed on Entangle went onto Trap when the Trap chip was the click (and onto the other A/B
  slot via the swap); the press now commits first, against last pass's field rect. Compose's
  int fields check int32 too. Known: the NUMBERS castpoint cell doesn't move the timeline
  (only FEEL does). edge 20261021-031450 covers all of it.
- **Third review** (acceptance 20261021-032125 PASS): committing first reflowed a filter or
  search under the pointer, so the click went to a row never drawn there (lsearch "paladin" +
  a click on ranger_nature/end applied paladin_divine/end). The press is now bound to the
  button drawn under it in the last pass (`Ui.targeted`/`target`). Known, non-blocking: a
  `[0,"pre",X,"cast"]` timeline (warcry, pal_judgement, ...) still moves its "pre" entry when
  the castpoint was 0; a castpoint past later events leaves the timeline unsorted
  (rog_grappling_hook); flame_step's castpoint (100) matches no timeline entry, so it moves
  nothing. edge 20261021-032945.
- **Fourth review** (acceptance 20261021-033739, hp3 034401 PASS; its rev4-commit 034134 FAIL):
  a growth +/- clicked while a cell was still being typed fitted the curve to the old values.
  The commit only queues the edit and Flush runs next frame, so area-ttl L1=5000 plus grow+
  wrote [5000,8350,9700,11050,12400] (base 7000, step 5% of 7000). TickDock now calls Flush()
  right after that pre-commit, and ApplyGrowth refuses while an edit is pending (a cast in
  flight), with "growth refused <path>: edit pending" in the log and the footer. Measured: the
  same clicks give growth 1916.667 (fit 1666.667 + step 250) and [5000,6917,8833,10750,12667]
  (edge 20261021-034903). Known, non-blocking: a click on a row the commit moves is dropped
  (the user clicks again), not misdirected.
- **Fifth review** (its rev5-class 20261021-040148): every class builds its own skill defs
  (`PlayerClass.as:452`), so `ran_trap` on ranger_nature and on ranger_beasts are different
  objects, and the tuner edits only the current class's. A preset that changed class left the
  new class vanilla under "live v1" (ran_trap cooldown 2000 instead of 7777), and switching back
  put the old class's stale version live. ApplyPreset now restores the old class's defs and
  drops the snapshots before `ChangeClass`, then forces a Flush of `g_want` onto the new class
  ("class <id>: re-applying v<n>"). class-switch 20261021-040406 measures nature v1 7777 ->
  beasts 7777 -> beasts v2 5555 -> nature 5555 -> Ctrl+Z 7777. TuneSubmit's "same as live, skip"
  shortcut is now skipped while an edit is pending (read in code, not measured). Known,
  non-blocking (read in code): Ctrl+Z after A/B swaps walks the global version list; the Compose
  source field can commit its placeholder; ComposeSubmit drops `;`, `=` and `|` silently;
  re-applying a compose draft replaces that skill's Tune edits; the bench's variant swap doesn't
  rewrite the override file until the next change.
- **Sixth review** (rev6-reload 20261021-041452, rev6-compose 041840):
  - Reload floor reset the tuner to the boot file. Script globals die with the level, and the
    module re-reads `devarena_overrides.sval` as cached at boot, so v1 was gone and the next edit's
    override line no longer held it. The tuner (versions, slots, live, pins, needs-relaunch) now
    rides the town save with the arena toggles (`SaveTuner`/`LoadTuner` in Overrides.as).
  - That save is stamped with `HashString(OverrideJson())` of the file as read at boot. It is taken
    back only while the process still sees that file, so a relaunch after `overrides.py sync`
    (or a hand-emptied file) reads the file. TownRecordLoad runs twice per level; the load is idempotent.
    tuner-reload 20261021-042320 measures v1 7777 through a reload and a v2 line holding both edits.
  - `clone_spec.py --version a|b|N` took each slot's last `compose-dict` line in the log, which can
    belong to another version (A shipped B's 9000 cooldown under A's name). It now takes the
    compose-dicts logged just before that version's last `live vN (` line, and refuses a composed
    version that was never live in the log. Re-run offline on 041840's log: `--version a` gives 3000.
  - Known, non-blocking: `da-set` drops arguments past the 4th (values with spaces); a class change
    not made by a preset (the Subclass Picker NPC) is not followed until the next level; the
    Compose CHECK cache key can show a stale result across a class change (display only).
- **Seventh review** (rev7-levels 20261021-044701, 50 of 51 assertions; the one failure was the
  reviewer's own click on a control a projectile draft doesn't offer): **no blocking defects**.
  Measured: a compose v1 + Tune v2 survive a floor change with A live ("tuner from the town save:
  2 versions, live v0, A v0, B v2, slot A"), F2 brings back cooldown 4444 and "Thorn Volley"; a
  ranger_beasts preset then a floor change then back to nature keeps v2; Ctrl+Z after the reloads
  gives v1. clone_spec `--version 2|1|b|live|a` on that log each baked the right version's
  compose-dict. Known, non-blocking: the Compose form shows the default draft after a level change
  until a preset reloads it (the live skill and the version are right; a re-compose from the blank
  form would overwrite the draft); `overrides.py` has `sync` and `show`, no `clear`; the preload
  module logs a stale "tuner from the town save: 0 versions" before the real level (harmless).

## 2026-10-21: watch-mode mouse, the shim hand-off, the input e2e

User report: in `devarena/arena --mode watch` the mouse did nothing. Verified from the shim log of
the user's run 20261021-061402-arena-watch: with GAMELAB_SHIM_INPUT=1 and GAMELAB_NO_ACTIVATE=1
(`gamelab/session.py` start) the shim drops SDL mouse events 0x400-0x403, freezes
SDL_GetMouseState at 0,0 and fakes focus for the whole run, including the human's `play` step.
Those are hidden-desktop requirements, not watch-mode ones.

- **Hand-off** (`tools/capture_shim/hwr2_capture.c`, mailslot message `GAMELAB_HANDOFF` 0x7F00,
  `winproc.shim_handoff`): the `play`/`handoff` step stops the shim's lies. Without
  `keep_focus` the mouse, focus and window events pass and focus is answered truthfully (log:
  "input handed to the player: SDL mouse, focus and window events pass through"). With
  `keep_focus` (the e2e: a player who clicked in) only the mouse is freed and SDL still sees focus.
- **TrackMouseEvent**: SDL 2.30.7 tracks mouse-leave on each move; with the real cursor outside
  the window WM_MOUSELEAVE comes back at once and SDL resets to the real cursor position, so a
  posted WM_MOUSEMOVE never shows in GameInput.MousePos (lab 20261021-155630). The shim hooks
  TrackMouseEvent in SDL2.dll and skips it only in the keep_focus hand-off. Lab mode has no shim
  input path, so the four mouse-aim assertions of watch-input fail there by design.
- **End shot**: after the player closes the window the runner no longer calls
  `winproc.restore_noactivate` on the dead window (`closed_by_player`).
- **TargetAOE skills** (ran_mark): the press shows the marker and MainHandAttack.Pressed places
  it; OffHand/Skill1 cancel it (PlayerTargetingHelper.as:280). While aiming, other skills report
  m_wasBlocked, which is the game's behaviour, not an input loss.
- **`da-inputlog on reset` is a test cheat**: mana refilled and cooldowns zeroed every frame so
  the e2e can press every binding back to back. `devarena/arena` never turns it on. Since the user
  saw "instant mana" in a test window and asked for it to be obvious, the mod draws a red banner
  "GAMELAB TEST ENVIRONMENT: INFINITE MANA, NO COOLDOWNS" at the top of the screen while it is on
  (arial14_bold), and logs and chats an all-caps `input-warn` line on "on", every 15 s, and on
  "off". The chat itself only shows in a lobby or after the menu script's `show_chat` (a console
  function that mods can't reach, core Commands.as:13), so the banner is what a single player sees.
  Verified in lab 20261021-161444: `input-log off (168 lines) banner 2762`, and the banner is
  readable in `shots/after-inputs.png`.
- Open (assumed, not chased): in the same lab run the second skill3 press (`v`) reached the game
  (`input-btn skill3 down`) but nature_entangle stayed `input-skill-blocked`, so it didn't cast.
  The first press (`3`) did. Watch run 20261021-160710 also missed later presses while the user
  was interacting with the window; rerun it with nobody in the window.

## The deploy list was missing three modules (2026-10-22, night)

Reading the install's `mods/` back after `deploy.py modded-prod --beta` (29 bins identical to
`dist/`, core 45 files with the Priest tables, firearms with the `off-hand` param) showed no
`HWP-mercenary.bin`, `HWP-puzzles.bin` or `HWP-stash.bin`. The three modules landed on 2026-10-18
(`bdeaec5`, `3139744`, `5450408`) but were never appended to the `modded-prod` list in
`gamelab/env/environments.json`, which is what `deploy.py` builds and copies (and refuses a module
not on it). `mod-all` loads all 31 modules, so the lab never noticed. The list now has all 31;
`HWP-petwait.bin` in `dist/` is a stale 2026-10-16 artifact of a module that no longer exists.

## The rifle arm pumped through a burst in the real game (2026-10-22, night)

- **Report:** "the rifle flickers while shooting, looks like gun is going up and down during
  burst fire" (the user, playing the deployed build). The real game's log shows the hold itself
  working at its coarse level (`gun arm: held` / `lowered (1000 ms without a shot)` /
  `lowered (reloading)` pairs around every burst), so the pumping is inside a held cycle.
- **Mechanism (read from the decompiled source):** `PlayerSkillDirectional.Update` calls
  `m_owner.SetUnitScene(m_animation, false)` on every frame of a cast (:103), after `:60`'s reset
  at each cycle's start, and `SetUnitTimeScale(...)` with it. `PlayerBase.SetUnitScene` is
  `PlayAnimation3D(..., layer 1, resetTime, m_looping)` at the default speed 1.0. So the game plays
  the shot animation on at full speed every frame, and `AimHold`'s frozen first frame
  (`PlayAnimation3D(..., Hold, 0.0001)`) only held while the module's `UpdateFrame` happened to run
  after the actor update in a frame. `AimHold.Pin()` now reasserts the frozen frame right after
  the base update in `HWPFirearmsGun.Update` (the gun's own class, so nothing native runs on
  layer 1 after it in that update) and again from the module's `PreRenderFrame` (the last script
  before the frame is drawn; `Modules::Module.PreRenderFrame(int idt)`, called from
  `AGameplayGameMode.PreRenderFrame` after every update). The local player is the `Player`
  (peers are `PlayerHusk`), so `cast<Player>(m_owner) !is null` is the local check.
- **Not reproduced in the lab.** `plan-firearms-arm-burst` (new: hold the trigger through three
  cycles at timescale 0.2 and take twelve frames) shows twelve identical raised poses with the
  fix (`20261022-203557` PASS, a bullet crossing frame 8 the only change) and without it
  (`20261022-203713`, INVALID: the user's own slot-7 saves changed during the run, they were
  playing; the frames are the same). The lab renders at 60 fps on a slowed clock, where one
  frame of full-speed play is a few milliseconds of the animation; the real game's frame
  pacing differs. The fix is therefore reasoned, and the user's game is the test.
- **Regression:** `plan-firearms-arm 20261022-203851` PASS (held, lowers after 1 s, on a dodge,
  on a reload, rifle and pistol). `mod-all 20261022-203531` PASS compiled it.

## Bug list 10.22.26: sixteen commits, each with a lab scenario (2026-10-25 to 2026-10-26)

The user's list (`temp/bugs 10.22.26.txt`, kept out of git) was worked in priority order,
bugs first, then the four big features (Battlements floors in HoH2 runs, floor objectives as
their own module, Luck, the Arcane pooled bar), one agent at a time once the user asked for
that. Every area got a `fix-*` scenario (`gamelab/scenarios`, bots in `gamelab/bots/fix_*.py`)
that passes in lab mode; the commit messages (35ead89..bcd12bc) carry the run ids. The final
gates: `mod-all` with all 32 content modules `20261026-084909` PASS; `fix-objectives`
`20261026-084617` PASS; `plan-t9` (31 modules, the plan_checks bot) `20261026-084939` PASS;
`mod-town-rebuild` `20261026-085151` PASS.

### Engine and lab facts measured this session

- **A .pfb unit entry with no params must be the flat form** `<array name="x.unit"><vec2>..</vec2><int>id</int></array>`.
  The nested `<array><vec2/><int/></array>` form is only valid with a third `<dict>` of
  params; without it the engine reads past the array and the game dies with exit
  3221225477 (0xC0000005) at floor start, after "Executing scripts on start" /
  "MissionGameMode::LoadDifficulty: true", with nothing in the log. Found by bisecting the
  campaign's trap prefabs; generation prefabs carry no `special/_origin.unit` and need no
  `tiles`.
- **Textures must be power-of-two**: the engine refuses a 24x24 dead-core texture at boot;
  the Forgemaster's body core is 32x32 (0aa229e).
- **The keep's exit is a `LevelExitNext` world script fired by a `UseTrigger`**
  (`prefabs/keep/level_exit_part_*.pfb`), picked by a PrefabPicker in `level_exit.pfb` that
  fabricates after a module's `Start`; the cave and citadel exits are `LevelExitAreaNext`.
  A disabled world script does not execute (vanilla `ToggleScripts` pattern), so
  `SetEnabled(false)` seals both kinds. The objectives module retries its seal for 3 s and
  logs "exits sealed after start" when the keep's part arrives late.
- **The next floor preloads while the current one runs** and logs its own generation lines
  tagged `[preload]`; a bot reading placement lines must skip them.
- **The pathfinder ignores generator-carved corridors**: `gl pathfind` / `gl reachmap`
  answer empty from every cell of the objectives vault's corridor (sealed or open, and
  even 64 px into the floor it meets), while the prefab room's own cells path fine
  (`20261026-084617`, notes in `bot-results.jsonl`). The player walks it. The puzzles
  module's corridors are carved the same way. Doors are therefore tested by walking the
  player into them (`fix_objectives.walk_in`): the locked door's static collision stops the
  walk at the doorway, the open scene lets it through.
- **`gl usables` never lists a static sensor after a teleport** (no overlap begin), but
  `gl use <filter>` acts on the nearest match from anywhere; `gl hurt <fraction>` sets the
  hp fraction (1.0 heals); `hwp god` needs `e_cheats 1`. A level-1 Paladin dies in about a
  second on spikes or fire or among enemies: heal and god before measuring traps.
- **The player menu's Map tab cannot open in the lab**: vanilla `MapWidget::NavigationBarText`
  reads `GetInput().GetCurrentMap()`, null without a real input device
  (`BaseGameMode::UsingMouseLook`). `fix-map-colors` shoots the minimap and the overlay map
  instead; the tab is a hand check.
- **Bash heredocs halve backslashes** on this machine: a JSON `\\d` written through a
  heredoc arrives as `\d`. Regex patterns in scenarios and bots go through the Edit tool.

### What landed, by area

- Firearms (5167447, bbcc5e1): rounds from the gun to the cursor point, the reload bar in
  the world, gun poses, Snipe aim time per rank (650..325 ms), armor penetration
  30/35/45/50/60, the Recoil Roll orb (`HWPFirearmsSnipeRecoil` starts the player's own dash
  backwards along the shot).
- Specs (445bde7, f70c7fc, 0aa229e): Blink along a Shot-type ray at 112 px with effects,
  Thunder Orb 2.0 speed / 3 px body, Living Mana as one blue bar; the Forgemaster's pyres
  take Heresy, channel lock with beam and bar, boss bodies always orb; the risen run,
  summon-green with an elite ring in the summon bar's orange (255,84,0), bodies grey and
  shoot-through, a floor safety net in `summons`.
- Town (baf4dea, 8a82745, 1ca404e, 0f39987): fishing keys and personal hole loot, the
  starter rod; outdoor hotboxing, dual joints on left and right click, wild plots for
  clients; pet training at the keeper and the pet level in the character tab; the run-start
  screen's presets, NG+ row and non-host leave.
- Runs (80d69f4, 7fa662f, 06d1a0c): puzzle room check and repair, summons held at the
  door; Luck (`docs/design/luck.md`); the boss recap and the one-page last-run board.
- Campaign (7bfa624): the portal offers the HoH1 version, Dark Citadel as two Dark Halls and
  two Battlements floors, HoH1 traps and a teleporter per generated floor, Confusion.
- Co-op map (bcd12bc): per-player map colours and names, the trapped-chest banner, and the
  `objectives` module (locked vaults, a sealed way down). `docs/modules.md` has the rows.

Open from the list: enemies and pets may not follow into a vault (the corridor is off the
nav graph, above); co-op behaviour of the objectives sync, the map colours of other players
and the trapped banner on clients need a two-machine lobby; the vault room has no light.

## The bug-list branch's code review, applied (2026-10-26)

A high-effort review of the 17 commits above found ten problems; all ten are fixed, and Luck
got a place on the character sheet. Batch `review-fixes-003` re-ran every affected `fix-*`
scenario: all nine PASS: `fix-fishing-personal-loot` 20261026-094048, `fix-core-luck` 20261026-094252 (and 20261026-095714 with the character-tab step), `fix-puzzles-room-integrity` 20261026-094344, `fix-puzzles-summon-hold` 20261026-094455, `fix-objectives` 20261026-094545, `fix-recaps` 20261026-094637, `fix-forgemaster-channels` 20261026-094735, `fix-specs-arcane` 20261026-095343, `fix-map-colors` 20261026-095602; `mod-all` 20261026-095829 PASS with the same engine errors as 20261026-084909.

### Engine facts found by the review

- **A brush's points of interest are stored at the top-left plus the def's `m_gridOffset`**
  (`CellGrid` brush POIs), so a room's cell is `poi.m_pos - type.m_gridOffset`. The puzzle
  room check read them raw and checked a cell offset from the room.
- **Shared and quest loot drops only on the server, for the local looter**: vanilla
  `LootItem.SpawnLoot` returns early unless `Network::IsServer() && looter.local`, and
  `CanBeInstanced()` is `!m_shared`. A per-player roll that is "personal" must hand any
  shared entry to the local record (`HWP::Luck::SpawnLootFor(..., personal = true)`), or a
  client's fishing catch lost its shared entries.
- **`ActorBuffList.Add` with a running def calls `ActorBuff.Refresh`**, which averages the two
  intensities and keeps the longer duration (and sends it to peers). A weaker Luck buff
  after a stronger one used to halve the difference; `GiveBuff` now passes
  `2 * keep - running` so the average comes out at the stronger value.
- **Affliction pools tick with no hook**: `CompositeActorBehavior.Damage` fires
  `PlayerDamagedActor` only for non-DoT damage on the attacker's machine, and the pools
  (`ActorBuffList.Update`) deal their ticks as DoT afterwards, recording only
  `m_affectionAttacker`. The boss recap now polls the pool sum and books the drop as
  "Afflictions" to the last attacker. Effects with `dot=true` (three vanilla files) are still
  not counted.
- **Equipped gear that fails its requirements adds no modifiers**:
  `PlayerRecord.RefreshModifiers` skips any item `MayEquip` rejects, even when
  `g_dbg_ignore_equipment_requirements` let it be equipped. `hwp luck item <tier>` generated
  `chest_dex_t1a` on a paladin about half the time and the Luck never counted; it now
  generates until the base passes `MayEquip`.
- **`LootUnit.SpawnLoot` returns -1** (gold, pickups) and the item entries 1 or 0, so a sum of
  the returns is no count of drops; the personal walk counts each rolled entry, as the old
  fishing loop did (`review-fixes-002` caught a catch that dropped two units logged as 0).
- **`RaycastType::Shot` passes over shoot-through rails into the void**: Blink checks
  `g_scene.FetchTilesets(at)` past the rail and refuses a spot with no floor tiles.

### The ten fixes

1. Puzzles: rooms are recorded at `poi - m_gridOffset` (a `puzzle_room_e_20x18_a` was
   208x256 px off), so the summon hold and `hwp puzzles check` use the room's real cells.
2. Fishing: a client's catch keeps its shared entries (above).
3. Luck buffs: a weaker source no longer lowers a stronger one (above).
4. Map colours: `playercolors.names 0` hides only the far-player names, not the dots on the
   minimap, the Tab overlay and the Map tab; the HUD labels follow `ui_hud_visible`.
5. Forgemaster channel: `UnpinDash` gives back the dash cooldown the pin overrode, minus the
   time it held, instead of zeroing any cooldown under `m_left + DASH_PIN_MS`.
6. Pyre Heresy needs the Pyre Sacrifice orb (`ps-reduce > 0`); without it the pyre was spent
   for nothing.
7. Luck `RollPool`: the chance a pool pays anything stays vanilla (factor 2 had lowered a
   chest pool's no-drop share from 85% to about 81%); only the pick among entries is weighted.
8. Boss recap: affliction pool damage counted (above); reports keyed by peer id, not name.
9. Arcane Blink: no landing past a rail where there is no floor (above).
10. One copy of the room carving (`HWP::Carve`, `mods/core/scripts/HWP/Core/Carve.as`,
    bounds-checked) for puzzles and objectives, the vault asking for its south door first;
    fishing's hand-written pool walk is `HWP::Luck::SpawnLootFor`.

### Luck on the character sheet

The character tab's stat bar has a sixth cell after movement speed: the vanilla `icon-luck`
sprite and a `hwp-luck-stat` widget (registered through `LoadWidgetProducers`) that reads
the local Luck each frame and rewrites its button's tooltip with the factor and the party
factor. The bar's padding and spacing went from 24 / 8 to 6 / 7 to fit. The Mods tab's Luck
row uses the `icn-luck` glyph and the same tooltip (`.hwp.luck.stat.tip`). `fix-core-luck` opens
the tab (`gl menu character - hwp-luck-stat`) and shoots it (`character-tab.png`).

Still open: `dot=true` effects are not in the boss recap; a peer whose copy of a Luck buff is
out of step can see the refresh overshoot until the next sync; Blink keeps vanilla Teleport
rules where no floor tileset is found.

## 2026-10-26: Luck in co-op and on generated floors

Design and the site table: `docs/design/luck.md`.

### Engine facts

- **A vanilla loot roll is already shared.** `LootTablePool::SpawnLoot` picks one entry
  per pool. A shared entry spawns once, and an instanced entry (gear, trinkets) spawns once
  per player, generated per player at the picked tier. So "the same tier for everyone" was
  already true; the change is only whose Luck the roll uses.
- **Stats are per machine.** `PlayerRecord.RefreshModifiers` runs on the record's own
  machine. The host's copy of a client's record need not carry the client's Luck (buffs,
  the cheat), so each machine now reports its own (`hwp.luck.report`).
- **The next floor is generated in another script context** (the "[preload]" one). It
  constructs every module again with fresh globals (`g_cheat` is 0 there) and has no lobby
  records worth reading. `MissionGameMode.Generate(save)` calls `LoadFlags(save, true)`,
  which loads `g_scalars`, the float run scalars that `AGameplayGameMode.Save` writes. A
  scalar is the channel into generation: the host keeps `hwp_luck_party` set to the
  party's average. `ScalarBank.Set(name, 0)` deletes the scalar, which `IsSet` then
  reports as unset.
- **Timing on a new floor.** `RewardSpot::SpawnRewards` runs on the host in
  `MissionGameMode.Start`, before the first `UpdateFrame`. The fishing module's
  `SetupRun` runs about 1 s after the floor starts, and by then the per-frame scalar
  refresh had already replaced the carried value with the new context's view (the cheat
  lost, x1). The fix is a snapshot on the first frame (`SnapFloorLuck`), taken before the
  refresh.
- **Secret rooms.** Every theme has a `SpawnPrefabSet` whose set ends in `_secrets`
  (`keep_secrets` min 1 max 1; barracks and cave max 2; crypt, courts and temple max 1).
  `PlacePrefabs` places up to the max where the patterns match and removes overlapping
  spots. On the first bandit keep floor at 75 % the extra room rolled (max 2) but one was
  placed: the five matching spots were on one wall and overlapped. The keep's secret defs
  have no max-num, so this is a real lack of space, not a limit.
- **Floor rewards.** RewardSpot's `intensity` (0..1, from depth and the spot's Quality)
  picks the tiers of exp scrolls, valuables, trinket and equipment chests, caches, health
  food (apple, orange, fish, meat) and mana pickups. Each count is
  `roll_round(lerp(min, max, randf()))`, and blueprints are `roll_round(0.25)` behind the
  `blueprint_cooldown` scalar.
- **Blueprints.** `BlueprintBehavior` is built per machine and picks a factory (Tavern food
  and drink, EquipmentModifier enchantments, Trinket). Each factory picks with `randi`
  among the candidates its buildings unlock. The lab town has none of those buildings
  ("No blueprint factory able to produce blueprint! 3 factories"), so the quality pick is
  sampled with `hwp luck roll quality` instead.
- **Dyes** are chest and cache loot only. The pinned SDK references the dye bucket units
  (`items/dyes/dye_bucket_*.unit`) in ten tables in `tweak/loot/chests.sval` (the
  `chest_*` and `cache_*` ones) and nowhere else: not in a prefab, a level, a theme or a
  script. `probe-dyes-floor` 20261026-104054 counted every dye bucket unit on two fresh
  floors (`querycmp` levelType, nothing opened): 0 on the first bandit keep floor (5 chests
  and caches) and 0 on the temple floor (3). Dyes seen lying on a floor are spilled from an
  opened cache or chest. In the chest tables they are a pool of their own (bronze trinket
  4 x 150, 60 % pays; silver and gold 40 %; equipment chests one bucket at 20-25 %), where
  `RollPool`'s weighting does nothing (equal weights), so `DyePool` multiplies their pay
  share instead (fix-core-luck 20261026-104254: none 1214 of 3000 at Luck 0, 0 at 500).
- **The imp** is a per-theme `*_imp` SpawnPrefabSet with `exec-chance 0.1` (barracks,
  cave_dark, courts, crypt, dark_halls, dungeon, forest, temple; not the keep), each prefab
  with a `run-unique-flag`. `DungeonGenerator` rolls `randf() > m_execChance` before it
  calls `Execute`, so a Luck chance has to be rolled inside `Execute` with the command's
  own chance set to 1. The crypt mission's floor 0 is the temple theme (`temple_imp`).
- **Clients and floor values.** Per-floor values reach a client only by message: a chest's
  lock and ace roll is a hash every machine computes itself, so the host broadcasts its
  floor Luck (`hwp.luck.floor`) and a client's `HWPChest` waits for it (10 s, like the
  settings sync).

### Built

- Chests, caches and strongboxes roll at the opener's Luck (`OpenerFactor`, log suffix
  `(opener <name>, Luck <n>)`), and so does a fish's loot. Abyss cracks and the key accept
  roll use the party average.
- `LuckFloors.as`, with these overrides: `WorldScript/RewardSpot.as` and `BlueprintBank.as`
  (vanilla copies in `.orig`, changes marked `// HWP`); the fishing hole chance.
- Keys: the floor's key budget share and its tier pick, and a gold chest's ace chance
  (at most 50 %), at the floor factor. The imp's room at 10 % x the floor factor.
- `hwp luck roll quality|secret|count <n> [luck]`.

### Tests

- Scenarios: `fix-core-luck` 20261026-102311 (quality picks: common 1533 and rare 718 at
  Luck 0, common 465 and rare 1280 at Luck 500; extra secret rooms 0 and 2276 of 3000;
  count means 494 and 855 per mille), `fix-luck-floors` 20261026-103349 (a gold chest
  rolled ace at 50 %, the key budget at x6), `fix-luck-imp` 20261026-103414 (not rolled) and
  20261026-103556 (rolled, placed 1); `mod-keys`, `mod-strongbox`, `mod-all`,
  `mod-abyss`, `mod-fishing`, `mod-fishing-spots`, `fix-fishing-personal-loot` pass.
- Not run on two machines: the client reports reaching the host.

## 2026-10-26: the combo orb, and chest art for the alt-art chests

### Engine facts

- **Breakable loot.** `Breakable.DamageEffects` rolls `m_lootTable.SpawnLoot(attacker, pos)`
  on the host only and never in town. The tables are `Item::GetLootTable(id)` objects shared
  by every unit that names them (`loot` param), so a pool appended to one reaches every box,
  vase or barrel using it. Boxes, crates and barrels use `barrel_wood_normal` and
  `barrel_wood_poor`, sacks `sack`, big vases and urns `vase`, small vases `vase_small`
  (`tweak/loot/containers.sval`); 53 other breakables (furniture and the like) have no table.
  Tables are rebuilt per script context, so the module appends its pool again each time
  ("(5 new)" on every load).
- **A script loot entry.** `Item::LootEntry` subclasses work in a table:
  `LootTablePool.SpawnLoot` rolls `randi(1000)` against the entries' `m_chance`, then calls
  the picked entry once per player, or only for the local (host) record when
  `CanBeInstanced()` is false, with the break position.
- **A local pickup.** A `netsync="none"` unit with a `Pickup` works per machine: `Picked`
  applies the effects for the local Player (not a husk), hides it and destroys it, with no
  message. `player-only` (the default) takes only a `Player`, which pets and husks are not.
  `MiniPet.IsPickupOkay` takes a plain `Pickup` only for the health, mana and experience
  pickup triggers, so a pickup without `pickup-trigger` is never fetched by a pet (the pets
  module calls the same check).
- **Can it be picked up.** `CanApplyEffects` is true when any effect but `ShowFloatingText`
  can apply, so a `PlaySound` effect would make anything pickable; the orb plays its sound
  through the Pickup's own `sound`. `Player.GiveCombo` does nothing when
  `currStats.ComboCountMax <= 0` (combo not unlocked) or combo is already on.
- **Who broke it.** `Breakable.DamageEffects` passes its attacker to
  `LootTable.SpawnLoot(Actor@)`, which hands every pool that player's record (null: the
  local, host, record). A client's hit arrives on the host as `NetDamage` with the client's
  husk as attacker, so the record is the client's.
- **The orb art** is `items/misc/base.png` 0 96 16 16, the vanilla skill point pickup
  (`items/misc/upgrade_skill.unit`), which no level or loot table places.

### Built

- `mods/groupcombo/scripts/HWP/GroupCombo/ComboOrb.as`: a `ComboOrbPool` (a
  `LootTablePool` subclass; its `SpawnLoot` override is called) appended to the five
  container tables. It rolls once per break at the breaker's own Luck:
  `groupcombo.orb.permille` (default 1, 0.1 %) times `1 + Luck / 100`, at most
  `groupcombo.orb.max_permille` (default 10, 1 %, at 900 Luck). The first version was a
  one-entry `LootEntry` pool at 1 %; an entry cannot see the breaker, because
  `LootTablePool.SpawnLoot` replaces `looter` with each player in turn (the local one for a
  not-instanced entry), so the roll moved up to the pool, which still gets the breaker from
  `LootTable.SpawnLootPlr`. The host broadcasts `groupcombo.orb` with the
  position; every machine gives its own player a local `items/hwp/combo_orb.unit` there if
  that player has combo unlocked. `HWPComboOrb` (global, the unit's effect) calls
  `GiveCombo`; while combo is on the orb stays on the floor. `hwp comboorb [drop|break
  [radius]]` (drop and break are host cheats; `break` is the game's `Breakable.Damage` on the
  nearest breakable with loot).
- The **Chest Art Picker** page (https://claude.ai/artifact/CVPvFos2M39nHRdkMWL6qH, source
  `.screenshots/chest-art/chest-art-picker.html`, git-ignored): every chest in
  `items/misc/base.png`, each with a chest type (bronze, silver, gold, ace, platinum) and
  areas 1 to 8. Used (8): the equipment chests at 100 0/18/36/54 (16 x 18), the trinket
  chests at 134 0/18/36 (12 x 18), the map reward chest at 171 0 (18 x 19,
  `items/equipment_map_reward.unit`). Unused (17): the trinket chest at 134 54, and a 4 x 4
  block at 32-84 x 0-72, rows bronze, silver, blue steel and gold (18 px each), columns at
  x 32 and 44 (12 px, trinket size: plain, strapped) and 56 and 70 (14 px: rimmed, the gold
  one with a red lid; large and ornate). The chests in the block touch, so the columns were
  found from their bright 2 px side rims (32-33 ... 42-43, 44-45 ... 54-55, 56-57 ... 68-69,
  70-71 ... 82-83; 76-77 is the large chest's middle strap, not an edge). The first cuts
  took 56 and 68 as 12 and 16 px, which clipped the rimmed chests' right rim and gave the
  large ones that rim on their left.
  The picks are in its database (`picks/main`); the alt-art chests are built from them.
  The frames at 116 0 and 84 0 in base.png are chest shadows, not chests.

### Tests

- `fix-combo-orb` 20261026-115538 (solo, bandit keep floor 0): the chance at 0, 500 and 2000
  Luck reads 0.10, 0.60 and 1.00 %; with base 100 and max 1000 per mille a vase broken at
  900 Luck logs `combo orb rolled for Pilot (Luck 900, chance 100.00 %)`. Then at chance
  1000 (as 20261026-113813 did for the first version): the status line,
  no orb while combo is locked ("none for us, combo is locked"), an orb at the broken vase
  once `combo_kills` is learned with combo still off, combo on after stepping on it and the
  orb gone, a second orb left alone while in combo, taken once combo lapsed.
- `mod-groupcombo` 20261026-113919 and `mod-all` 20261026-113935 pass.
- Not run on two machines: each player getting their own orb.

## 2026-10-26: alt-art chests by area, and the red skull ace key

### Engine facts

- **Areas are acts.** `MissionLevel.m_actNameBase` is the level's `act-name`, from the level
  dict or its theme (`tweak/missions/themes_*.sval`: `.location.act.forest`, ...); boss and
  some story levels set their own, a few have none. The game shows it as the region banner
  (`MissionGameMode`, `AddAnnounce(m_actName, m_levelName, "region_enter")`). Counting act
  changes along `MissionDef.m_levels` gives Dark Citadel 9 areas (forest, dark caves, forest
  again, temple, crypt, dungeon, barracks, courts, dark halls; the shortcut level after them
  is a 10th), the story missions up to 8, Bandit Keep 1. The level being played is
  `cast<MissionGameModeBase>(g_gameMode).m_missionLevel` on every machine (set from the
  level's save data), and its `m_mission.m_levels` index matches the gamelab `mission`
  verb's floor index.
- **A unit can carry art variants as named scenes** and switch with
  `UnitPtr.SetUnitScene(name, false)`; collision, lights and minimap sprite come with the
  scene, so each variant is a full copy. `<scenes start="vanilla">` keeps the original as
  the start scene (the attribute vanilla's `items/equipment_map_reward.unit` uses).
- **The items material draws an occluded item as a magenta silhouette** (`items/items.mats`
  `item`: `<xray value="255 0 255 255">`). A key dropped behind a wall top looks magenta;
  that is not a missing texture.
- **Gold pickups already scale their sprite by amount.** `Material::MaterialPickup.Initialize`
  picks the scene from the unit's `sets` (`items/materials/gold.unit`: 1g, several (2-5
  coins), 10g, 50g, 250g, the highest set at or below the amount) when the drop is made, so
  the amount is known before anyone picks it up. Unused gold art in `items/misc/base.png`:
  the pile at 80 112 (between the 10g and 50g piles) and four HoH1 coin-stack sprites at
  0 0, 16 0, 0 16 and 16 16.

### Built

- `mods/keys/tweak/hwp/chest_art.sval`: the Chest Art Picker's picks (`picks/main`, read
  2026-10-26) plus the user's notes: trinket chests plain (1-3), vanilla (4-5), strapped
  (6-8); cursed chests blue steel rimmed (1-4) and large (5-8); ace trinket chests gold
  rimmed (1-5) and gold large (6-8); ace equipment chests the map reward chest; equipment
  and platinum chests unchanged; areas past 8 use 8. The picker's platinum trinket picks
  (steel plain 1-2, the unused platinum trinket chest 3-4, steel strapped 5-8) have no chest
  to go on: the game has no platinum trinket chest.
- `tools/class_units.py`: module.json `scene_art` adds one scene per sprite to the generated
  class-swap copies (the floor sprite swapped, kept bottom-centred); `tools/build.py`
  documents the key.
- `mods/keys/scripts/HWP/Keys/ChestArt.as` (area count, table, `hwp chestart [area <n>|off]`)
  and `HWPChest.ApplyArt`: the area's scene on the first tick, the ace scene once a gold chest
  rolls ace (the red tint only when there is no ace art).
- The ace key is the vanilla skull key (`items/special/keys.unit:key_skull`, base.png 48 0)
  multiplied by (1, 0.25, 0.2): `mods/keys/items/hwp/keys/key_ace.png`, used by
  `key_ace.unit`, the HUD (`gui/hwp_keys.gui`) and the merchant (`KeyIconTexture`). The ace
  key's default price is 20000 (was 50000).

### Tests

- `fix-chest-art` 20261026-124741 (and 20261026-124547, whose first two screenshots failed
  to save: a colon in the shot name): area 1 on bandit keep floor 0, area 5 on Dark Citadel
  index 7 (crypt_1), area 9 on index 19 (dark_halls_1), whose own floor chests logged the
  area 8 art; spawned chests at override areas 1, 4, 6 and 9 took the expected scenes; ace
  chests at 3 and 7 took gold rimmed / gold large and the map reward chest; the ace key
  dropped as `items/hwp/keys/key_ace.unit` and shows red in the HUD.
- `mod-keys` 20261026-124945 and `mod-all` 20261026-125000 pass.
- Not checked in game: the merchant's ace key price and icon (data only), two machines
  (each counts the area itself, nothing is sent).

## 2026-10-26: gold pickups show their amount with 15 coin sprites

Engine facts:

- Gold gain is applied at pickup, not at the drop. `MaterialPickup` takes
  `player.m_record.GetMaterialModifier(m_type)` when the gold is collected
  (`Behaviors/Objects/MaterialPickup.as:262`). That is `(MaterialGainMul +
  g_ngp * Tweak::NGPMaterialGain) * MaterialGainMulMul` (`PlayerRecord.as:2558`; trinkets
  and gear add `gold-mul` 1.1-2). So the scene, picked in `Initialize` from the amount
  passed to `DropMaterial`, shows the base amount. Our Luck does not change gold amounts
  either: it changes which loot entries roll and how often, and a `LootMaterial` rolls
  `randi(max - min) + min` (`Items/LootTable.as`).
- A floor reward spot of gold (`WorldScript/RewardSpot.as:196-219`) is
  `75 * lerp(0.5, 3, intensity) * (0.5 + randf())`, at most about 337. Up to three extra
  piles drop at 25-66 % of that.
- `UnitPtr.GetCurrentUnitScene().GetName()` gives a unit's current scene name (vanilla
  `ShadowWall.as:18`).

Built: core overrides `items/materials/gold.unit` (with a pristine `.orig`). The behavior
and the `shared` scene are vanilla. The `sets` are 1/5/10/15/20 bronze coin and piles,
25/50/75/100/150 silver, and 200/250/300/350/400 gold (frames bronze 32 96, 64-112 80;
silver 48 96, 64-112 96; gold 48 112, 64-112 112). The biggest pile of each metal has
vanilla 250g's two glints. Silver uses the white `material_reflection.effect` at 0.8 the
alpha; the rest use `gold_reflection.effect`. The `several` scene set and vanilla scene
names are gone; nothing in the scripts refers to them. The silver piles are the art of
Avarice's fool's gold (`u_fools_gold_*`); the user is fine with that. The thresholds were
lowered from the user's first idea (silver at 100, gold at 1000) because no single drop
reaches 1000 (survey above and in the core README); the largest are 200-450.

`gl near` now reports each unit's `scene` and a material pickup's `amount`.

Tests: `fix-gold-sprites` 20261026-131823 passed. All 15 thresholds took their scene with
the right amount. The amounts just under them (4, 9, 24, 49, 149, 199, 399) took the tier
below, and 1000 and 5000 stayed on gold_5. Walking onto the 300 pile paid gold (0 to
725 with neighbours). The screenshots show three rows: bronze, silver, gold. `mod-all`
20261026-131915 passed; `build.py --check` and `list_verbs.py --check` are OK. Not seen:
how it reads at full resolution (the lab renders 640x360).

## 2026-10-26: the October work merged with main's Dev Arena (branch features-20261026)

The 28 commits from 2026-10-22 to 10-26 sat on a base older than main's Dev Arena merge
(PRs #10-#12), so origin/main was merged into the branch. Conflicts were in RE_NOTES (both
sides appended sessions: main's 10-18 to 10-21 come first), `docs/modules.md` (the campaign
row from here; devarena and vanilla-tuning from main), the mission-ranger fixture's `about`
(main's Warden build plus the note on the dropped dash-charges probe) and the generated
verb list (regenerated).

Main's GameLab sends a scenario's `hwp <rest>` line as `setvar hwp_line <rest>` through the
inbox (`gamelab/session.py` console_verb). That needs core's `hwp_line` cvar
(`Commands.as` OnHwpLine, `cvar_flags::TriggerChanged`), which was only in the dev-arena
WIP snapshot 6ee00a1 and never reached core on main: every `hwp` line failed with
"setvar: no cvar hwp_line of a settable type (type 10)" (fix-chest-art 20261026-132440).
It is ported unchanged from 6ee00a1; fix-chest-art and mod-core then passed (132631,
132724).

The merged tree's first batch passed 29 of 38 scenarios. The other nine came from main's
GameLab changes meeting this branch's bots, not from the mods:
- **sval `file:entry`.** Main's probe split the path at `.sval:` before the lookup, but a file
  of named roots (`fishing_keys.sval`, `<svals><dict name="keys">`) resolves only as the
  whole `file:entry` path. SvalDump now tries the whole path first and splits only when that
  fails (fix-fishing-keys).
- **The widgets dump truncates.** Main's dump carries every node's screen position and fills
  its byte cap before the HUD's components. `plan_checks.widget()` now retries one root at a
  time when the dump says `truncated` (fix-objectives).
- **Cheat mirrors.** The inbox sends a CHEAT_FUNCS name as `cheat <fn>`, and gamelab-hands
  needs a mirror for each one. Added cht_give_health, cht_damage, cht_give_mana,
  cht_clear_trinkets, cht_give_specific_trinket, cht_spawn_specific_equipment,
  cht_add_blueprint and cht_add_all_blueprints (fix-firearms-snipe).
- **The inbox types into a focused field.** The inbox's text frames also reach a focused text
  field: "!gl c33 state~" landed in the character-name field. fix_runstart clears the field
  before typing.
- **Inbox latency.** Round trips are slower, so three bots changed. fix-farming-hotbox waits
  1.5 s after `gl wield`. fix-firearms-poses checks that the rifle is down on dodge without a
  time limit (the elapsed time goes in the note). fix-puzzles-summon-hold leaves the room
  with `gl teleport`, because the `_b` rooms have puzzle units by the door.
- fix-combo-orb and fix-firearms-aim-diagonal failed once and passed on rerun.

With these, all 38 pass on the merged tree (last reruns 20261026-135938 to -141120).

## 2026-10-26: tavern levels 4-6, and trinkets that scale with NG+

### Engine facts
- **The loadout's tavern row needs a guild hall.** `tweak/town/loadouts.sval` gives the
  `tavern` loadout the conditional `town building guild_hall ge 0`. Without it,
  MissionLoadoutMenu skips the row and never calls `BuildGUI`. `gl func tavern open` still
  reaches `MissionLoadout::Get("tavern")`, so a picker opens over a loadout with no row.
  Its Apply then hits a null `m_groupW` in `UpdateIcons` (vanilla code; run
  20261026-141417). A fresh lab town has no guild hall. The mod now returns early when
  there is no row, and fix_tavern builds the guild hall first.
- **A fresh town offers no Simple Broth.** The `tavern_simple_broth` checkbox is missing from
  the picker; hearty, elemental breakfast, beasts and foragers' feast are there.
- **Trinket modifiers can be rebuilt live.** `Item::Trinket.m_modifiers` and `m_modifiers2`
  (the attuned set) are public arrays. `Modifiers::LoadIModifiers(u, dict, Role::Both,
  "" / "attune-", SyncVerb::Trinket, m_idHash)` builds them again from any dict. Then
  `PlayerRecord.RefreshModifiers()` and `RefreshStats()` apply them. Max health followed in
  the same frame (190 to 205 at NG+ 3 with the Amulet of Health).
- **An attuned trinket uses only `m_modifiers2`.** A trinket whose attuned set changes only a
  cooldown still needs its numbers patched in both sets.
- **`intensity-mul` in a trigger's effects.** A class-less dict in an effects array is an
  EffectListMod (`LoadEffect`, IEffect.as:117-133). Its `intensity-mul` vec2 scales every
  effect after it. TriggerEffect loads its list through `LoadEffects`, so one entry put first
  scales proc damage that lives in a projectile or unit file.
- **`Modifiers::Buff` hard-codes intensity 1** (`ActorBuff(player, m_buff, 1.0f, false)`).
  Arctic Step's frost gets its intensity through a subclass.
- `Resources::GetString` fills `%param%` from the `?a=1&b=2` query of the key, so a patched
  `desc` string gives the scaled tooltip.

### Built
- `tavern`: the README row, and `docs/modules.md` rows for tavern and trinkets.
- `trinkets` (new mod, no overrides): `HWP/Trinkets/NGScaling.as` has the spec table of 56
  trinkets from the Trinket Map verdicts. It patches a copy of each trinket's sval dict per
  NG+ level (`int(g_ngp + 0.5)`) and checks the level every frame, so the loadout's NG+
  picker takes effect at once. It also has `HWPTrinketNGBuff`, the setting
  `trinkets.ngp_scaling`, and `hwp trinkets [show <id> | ng <n>]`.
- Assumptions: "+5 res" on the books is read as +5 attack or spell power. The Chicken Feet
  amount is per 500 ms tick (+0.25), which shows as +0.5 mana per second. Apothecary's
  Flask is 2 charges (4 attuned) from NG+ 4.

### Tests
- mod-tavern PASS (20261026-144247): slots per level, a full pick of 4 foods (the oldest
  drops) and 6 drinks, the picks kept, and a run started with 3 foods and 5 drinks.
- mod-trinkets PASS (20261026-143558): all 56 found. Amulet of Health at NG+ 3 shows +45
  (attuned +90) and max health is 15 higher. Searing Torch 80 with its 2 s cooldown kept,
  Chicken Feet 3.5, Arctic Step 60, Tincture 8 s, Flask +2/+4 at NG+ 4, and NG+ 0 restores
  the originals.

## 2026-10-26: Way Gates (teleporters across town)

### Engine facts
- **Every vanilla town building is plotless.** None of the 16 building svals names a plot.
  `TownRecord.m_plots` is empty in the lab town. `gl build` adds the building with
  `plotHash 0`. The base town segment (`tweak/town/prefabs_segments.sval`, set
  `town_segment_base`) places each building prefab at a fixed cell. `PlaceTownPlacedPrefab`
  matches the prefab to its BuildingDef (`GetBuildingDef`, any tier or the unbuilt
  prefab). Nested prefabs (chapel, guild hall, magic shop) carry the apothecary, enchanter,
  pyre and treasury. The cells are: tavern (-4,-11), guild hall (-53,4), blacksmith
  (-30,28), general store (-40,28), magic shop (-64,28), chapel (40,0), library (36,22),
  hunter's cabin (66,48), architect (9,67), tailor (-9,33), trading post (-96,16), training
  grounds (-47,-35), apothecary (-66,48), enchanter (-55,34), pyre (61,-15), treasury
  (-49,-18). Core's pyre lookup (`Town.as`) already walks the same table.
- **Building variations carry no `grid-pos` or `grid-size`.** There is no footprint to aim
  at, and the cell is the prefab's origin (inside the walk-in buildings).
- **Vanilla keeps one NPC per unit type on the host.** `CompositeActorBehaviorNPC.
  CheckForExistance` removes the others. With three gates, two died within a second and
  were respawned every second. Core's `HWPLocalNPC` (an empty `CheckForExistance`) fixes
  it.
- **A cloned widget needs `m_idHash`.** `Widget.GetWidgetById` matches children by
  `m_idHash` (`GetWidgetByIdImpl`), so setting only `m_id` on a `Clone()` leaves `gl press`
  (and any lookup) unable to find it.
- **`array.sort` with a callback throws "Index out of bounds" on an empty array.**
- **The lab player drifts after any teleport,** at about 90 px/s. The direction differs
  each time. There is no stick input and the Pilot is idle (`gl controller`,
  `gl pilot status`); the cause is unknown. Read the position at once after a teleport.
- `Scene.QueryRect(..., RaycastType::Any)` returns the walls of town buildings as
  `:Physics_Rectangle` and `:Physics_Freeform` units, alongside furniture and actors.

### Built
- `waygates` (new mod, no overrides): `HWP/WayGates/WayGatesModule.as` (gate list, spawns,
  the town-reload watch, `Go`) and `WayGateShop.as` (`HWPWayGateShop` and
  `HWPWayGateMenu`, one cloned button per gate, the current one disabled).
  `doodads/hwp/hwp_waygate.unit` uses the teleport beacon's lit pad sprite.
  `gui/hwp_waygates.gui`, lang, settings `waygates.enabled` and `waygates.square_x/_y`,
  and `hwp waygates [go <n>]`.
- Where the gates go: the building's cell plus three cells south, then the nearest spot with
  nothing solid in a 20x20 box. Actors are ignored, so the spots come out the same on
  every machine and every reload. At every building's last tier, each gate lands within
  about 150 px of the building's vendor.

### Tests
- mod-waygates PASS (20261026-150438). It builds a guild hall and a tavern in the fixture
  town and reloads it. Then 3 gates are listed (square first), with a unit at each spot.
  The square's gate opens HWPWayGateMenu with 3 buttons, the square's disabled. Pressing
  the tavern's button puts the player on the tavern gate. After a guild hall upgrade
  reloads the town, the gates are back.

## 2026-10-26: the HoH1 trinkets, new trinket sets, and vanilla set changes

### Engine facts
- `Item::TrinketSet` with `merge-set-bonuses` true appends each lower tier's merged list to
  the next. A set with 3 or more tiers therefore gets its lower tiers more than once (tier 3
  gets tier 1 twice). New sets list every tier's modifiers by hand with the merge off.
  `GetModifiers(num)` returns the highest tier with `m_num <= num`.
- The bonus loop in `TrinketSet` only reads keys 1..`items.length()`, so a tier can't be
  past the piece count. Patching a set at run time (`HoH1.as`): set `trinket.m_set`,
  `set.m_totItems++`, then rebuild `m_bonuses` with `LoadIModifiers(..., SyncVerb::TrinketSet,
  set.m_idHash)`. Netsync matches the modifier's index within one list, so cumulative tiers
  keep the indices unique.
- Modifier conditionals on functions that take a second `Actor@` (`DamageMul`,
  `NonLethalDamage`) test `m_condTargetOther ? enemy : player`. Self conditions on those
  (Pendant of Penance, the 6-piece Spheres) need `cond-target-self` true.
  `CheckConditionals(null)` is false.
- `HitscanRandomEnemy` and `ShootRandomEnemy` are `IEffect` only, not `IAction`, so a unit's
  `CompositeActorSkill` can't use them. The Nimbus uses a `ChannelingBeamSkill` instead.
  `Nova` is both.
- `Player.Update` calls `RefreshStats()` every frame, so a stat modifier that reads missing
  health stays current without a trigger.
- The trinket shop is `TrinketShopShopContent` (`m_toBuy` 2, `priceRate` 1 + 0.2 x shop
  level). A class swap can add picks in `GetItems` and rebuild the items at a new price
  rate; save the "picked already" flag with the shop.

### Built
- `mods/trinkets`: 37 trinkets (`tweak/hwp/trinkets_hoh1.sval`), 10 buffs, the Nimbus unit,
  8 sets, the Emblems of Hermes, Apothecary's Supplies and Trader's Coin changes, and 134
  strings. `HoH1.as` holds the set patching, `HWPTrinketComboKills`,
  `HWPTrinketMissingHealthSpeed`, `HWPTrinketShopContent`, `hwp trinkets hoh1` and
  `hwp trinkets set <id>`. NG+ scaling covers Judgement and the Talisman of Conflagration
  (58 trinkets).
- `mods/keys` `HWPGiveKey.as`: the Key Ring's `hwp-key-ring` stat gives a chance of a second
  key (tier 1/2/3 at 60/30/10).
- Tuned from the plan: Spreading Corruption is +30% damage taken (+60% attuned), not x3.
  Talisman of Decay's attuned aura is the vanilla greater vulnerability (x1.3). Charms of
  Fortune's Luck uses the x5 HoH1 scale (+5, then +20 in all). Elven Ruby is a rare with no
  set (its note), though its verdict says remove.

### Tests
- `mod-trinkets` (lab) PASS: `gamelab/results/20261026-163716-mod-trinkets-lab`. All 37
  load. Apothecary's 4-piece tier holds 3 modifiers (no merge duplicate). Spheres of Power
  has tiers 2-6. Lucky Hat + Lucky Horseshoe + the Charms 2-piece read Luck 35. Trader's
  Coin, Fancy Plume and Key Ring read shop price x0.75, stock +2 and key ring 50%.
  Judgement reads 12, then 14 at NG+ 2.
- Not run in a dungeon yet: the procs in combat, the Nimbus, the guardian, the trinket
  shop's extra stock and the key ring's extra key.

### HoH1 trinket icons (local import)
- HoH1 item icons are 12x12 cells of `items/items.png`, named in `items/<quality>.sval`
  (`<array name="icon">` texture, frame count, rect). All 37 of ours are there under the
  HoH1 id (`hwp_` dropped, `_` to `-`).
- `tools/import_hoh1.py trinkets` puts each one in the middle of a 16x16 cell of
  `mods/trinkets/gui/hwp/icons_trinkets_hoh1.png`. `hwp_trinkets_hoh1art.lang` lists the
  ids in sheet order (`.hwp.trinkets.hoh1art`). Both are the module's `local` files and
  gitignored. At load, `HoH1.as` checks `Resources::HasString` for that string and sets
  `Item::Trinket.m_icon` to a `ScriptSprite` on the sheet. The inventory, shop and tooltip
  read `GetIcon()` each time, so nothing else is needed. Without the import: placeholders.
- `mod-trinkets` (lab) PASS: `20261026-165100-mod-trinkets-lab`, "HoH1 icons: 37 of 37",
  bot flag `h1_icons`. `shots/trinket-inventory.png` shows the Lucky Hat, Horseshoe,
  Fancy Plume and Key Ring with their HoH1 icons in the trinket inventory.

## 2026-10-26: Roulette

### Engine facts
- **`HWP::Net::Broadcast` runs the host's own handler synchronously,** inside the call
  (`Net.as` `DispatchEvent` after `SendToAll`). Host code that broadcasts its state and
  also reacts to that event in the handler sees the change before the broadcast returns.
  The roulette host keeps its round in separate `h_*` variables and every machine,
  the host included, changes the shared `g_*` view only in `OnState`.
- **A tavern table's food is its unit scene.** The `table_wood_*` units start in scenes
  like `food1`, `food_less1` or `feast1`; `UnitPtr.SetUnitScene("default", true)` shows the
  bare table. Each tier lays its tables out differently (tier 1 has six, tier 3 adds the
  back room's feast tables at y -304 and -339). A table right behind the tavern's front
  wall (tier 1's `table_wood_poor_v` at -82,-132) is mostly hidden by the wall.
- `AInteractableWidget` has no `Update` of its own: a subclass that overrides `Update`
  calls `Widget::Update(dt)`.
- A 768x22 sprite sheet was refused at boot (power of two, as noted before). The wheel's
  24 frames sit on a 256x128 grid.

### Built
- `roulette` (new mod, no overrides): `HWP/Roulette/RouletteTable.as` (the 157 bets, the
  host's rounds, settlement, refunds, `hwp roulette`), `RouletteMenu.as`
  (`HWPRouletteShop`, `HWPRouletteMenu`, the board widget with edge and corner hit-testing,
  the scrolling number strip) and `RouletteModule.as` (the wheel on the table).
  `doodads/hwp/hwp_roulette_wheel.unit` (`HWPLocalNPC`, scenes `idle` and `spin`),
  `roulette_wheel.png` from `tools/make_roulette_art.py`, `gui/hwp_roulette.gui`, lang,
  setting `roulette.max_stake`.
- The payout is stake + stake x odds x (1 + Luck/100 + gold find), where gold find is the
  record's `MaterialGainMul * MaterialGainMulMul` minus 1, without the NG+ material bonus.
- The wheel goes on the main-hall table nearest (-165,-210) with y between -280 and -150:
  tier 1 `table_wood_poor_round` (-168,-224), tier 2 `table_wood_common_round` (-167,-218),
  tier 3 `table_wood_common_v` (-200,-152). It falls back to the table nearest the
  gambler's spot.

### Tests
- mod-roulette PASS (20261026-172759). With Luck 20, 1000 each on s:17, c:13, odd and
  red and a forced 17: gold 200000 -> 196000 -> 251800, paid 55800 (35000, 8000 and 1000
  won, each x1.2, plus the stakes). The wheel shows `spin` while the ball runs and `idle`
  after. Cleared chips come back in full; the eleventh 100K chip is refused. After
  upgrades to tiers 2 and 3 the one wheel is back on a hall table.

## 2026-10-26: Auto Aim

### Engine facts
- **An AOE skill's reticle comes from two helper methods.** `PlayerTargetingHelper.Update`
  takes the TargetAOE target from `CalcGamepadTargetPos` (the stick: `m_gamepadRelTarget`,
  moved by the stick each frame, starting 150 px out along the aim) or
  `CalcMouseTargetPos(ToWorldspace(input.MousePos))`. It then activates on
  `MainHandAttack.Pressed`, or on the skill button's release with `g_quickcast`. Both
  methods are script methods, so a subclass can override them. A gamepad override should
  also set `m_gamepadRelTarget`, or the next frame's stick input starts from the old spot.
- `GameInput.UsingGamepad` is false in the lab (no pad). `gl mouse` pins only the UI
  cursor (the game mode's), not `GameInput.MousePos`; `gl inputtarget` writes the world
  cursor every frame.
- The settings-search checks in plan-newa-a fail with or without this session's changes
  (20261026-174622, core changes stashed): the GameLab command text ("!gl c14 menu
  hwp_options -") lands in the focused search field. Their last pass was 20261018-132014.
  Not fixed here.

### Built
- Core: `scripts/HWP/Core/Aim.as` (`HWP::Aim::OnAdjust`, `OnPreUpdate`, `FireTargeted`).
  `HWPSkillKeysHelper` overrides `CalcGamepadTargetPos` and `CalcMouseTargetPos` to pass
  the vanilla reticle through the adjusters, and runs the pre-update hooks before the
  vanilla `Update`. The Plus tab gets four rows (`autoaim`, `aimcone`, `autofire`,
  `autoskill`); all rows are now 22 px high so nine fit above the hint.
- `autoaim` (new mod, no overrides), a remake of Workshop 3732392493.
  - Target: the enemy nearest the vanilla reticle, among targetable, living
    `FetchActorsWithOtherTeam` actors within range (`rangeMax` plus half the reticle,
    the spot clamped to `rangeMax`). It must be inside the cone around the reticle's
    direction and in plain sight (the ShootRandomEnemy Shot raycast).
  - Auto fire: the snap recorded by the adjuster fires on the next frame's pre-update.
  - Auto skill: the first ready TargetAOE spell, with mana at or over the share, at most
    once every `autoaim.skill_buffer_ms`.
  - Modes: 0 off, 1 controller (the default), 2 controller and mouse.

### Tests
- mod-autoaim PASS (20261026-174359): a town ranger and a target dummy 80 px south, mode 2.
  - Holding Skill 1 fires Marked Shot at the dummy (auto fire).
  - With auto fire off, the reticle snaps to the dummy's spot and nothing fires.
  - A 90 degree cone does not pick the dummy with the cursor north, and does with it south.
  - Unpressed, Marked Shot casts itself at the dummy (auto skill).
  - Mode off does neither.
  - The four Plus tab rows show next to colors and weaponswap, and the mode row cycles.
- The gamepad path was not exercised; the lab has no pad.
- mod-all PASS (20261026-174550).

## 2026-10-26: Code review fixes (69ba108..e1f1fc7)

A /code-review high over the commits since the last review (tavern levels 4 to 6, Way Gates,
roulette, Auto Aim, trinket NG+ scaling, the trinket map, the HoH1 trinkets and the Luck rule
of e1f1fc7). Ten findings, all fixed.

### Engine facts
- `CondTownBuilding` "my town building guild_hall ge N" compares the building's variation
  (`GetVariationOnBuilding`): -1 unbuilt, 0 to 7 for guild hall levels 1 to 8. `ge 8` can
  never hold; vanilla's highest condition is `ge 7`.
- `PlayerRecord.GiveMaterial` / `GetMaterial` go to `g_myTownRecord` (the town's gold) only
  while a `TownGameMode` is running. Out of town they use the record's own `materials`, the
  run's gold. Gold taken in town has to be paid back with `g_myTownRecord.GiveMaterial`, or a
  refund in a run lands in the run's gold.
- Script globals reset with every level, before any module's `Start`, so state that has to
  outlive a level change goes in a save bag (`HWP::SaveData`) or GlobalCache.

### Findings and fixes
1. Tavern level 6 needed `guild_hall ge 8`: never true. Now `ge 7`, the same top guild hall as
   level 5 (`mods/tavern/tweak/town/buildings/tavern.sval`; the README table gives the
   in-game guild hall levels).
2. Roulette chips on the table were lost when a run started. `Owe()` keeps the local
   player's stake in the town's save (`roulette.owed`) after every bet and clear;
   `RefundOwed()` pays it back to `g_myTownRecord` on the next level's Start (or the first
   frame with a town record) when no round holds the stake.
3. A client's Way Gate list went stale after a building upgrade (only the host's watch
   rebuilt it). The gate's menu now rebuilds the list when it opens.
4. Auto Aim wrote `m_gamepadRelTarget`, so the pad's aim itself locked onto the nearest enemy.
   Only the shown reticle moves now.
5. Auto skill fired without `SetSkill`, skipping vanilla's StartCharge. It now calls
   `helper.SetSkill(skill)` and then `HWP::Aim::FireTargeted`, which returns whether the skill
   activated; returning true matches vanilla's own activation frame.
6. `BlueprintBank.as` logged the picked blueprint before its null check (food and drink,
   enchantments, trinkets), and the quality loops did not skip null entries.
7. The trinket strings used `hwp.trinket.` beside `hwp.trinkets.`; all are `hwp.trinkets.` now
   (lang, svals, `HoH1.as`, `tools/import_hoh1.py`).
8. A roulette payout could overflow `int`. It is computed in `double` and capped at
   2,000,000,000; `roulette.max_stake` is capped at 10,000,000.
9. The auto skill scan ran every frame; it runs at most every 150 ms now.
10. The custom stat lookup was copied in Luck, Keys, Trinkets and Firearms, each copying
    `m_customStats`. One core helper, `HWP::CustomStat(rec, id)` (`HWP/Core/CustomStats.as`),
    reads it in place.

### Tests
- mod-roulette PASS (20261026-181251) with a new `leave` section: 7000 on black, then
  `gl mission bandit_keep` before the result. The log shows "7000 back (left on the table at a
  level change)", the run's gold stays 0, and after `gl abort` the town's gold is back to the
  gold before the bet. Its first try (20261026-181101) found the refund landing in the run's
  gold (the GiveMaterial fact above).
- mod-all PASS (20261026-181551) after the town-gold refund.
- PASS before the leave check: mod-all (20261026-180630), mod-roulette (180646), mod-autoaim
  (180728), mod-tavern (180808), mod-waygates (180907), mod-trinkets (180934).
- Not covered: Auto Aim's gamepad path (the lab has no pad). plan-newa-a's settings-search
  failure predates this work.

## 2026-10-26: Skill 4-6 keys move to classes; doctor scene_art; valuables kept at 2x

- **Who needs Skill 4-6.** Counting the active spells after `m_skills[0]` in every class
  and spec the mods add: only the HoH1 thief's Assassin and Shadow (4), Trickster (5) and
  the gladiator's Retiarius (4) have more than three. Firearms has 2 base actives plus 1
  per spec (3). So `SkillKeys.as` and `SkillKeysHUD.as` moved from core to
  `mods/classes/scripts/HWP/Classes/`, with the `hwp.skillkeys.option` string.
- **Core keeps the helper.** Auto Aim still needs the swapped targeting helper, so core
  has `HWPTargetingHelper` (`HWP/Core/TargetHelper.as`, replacing `HWPSkillKeysHelper`),
  which does nothing itself. `HWP::TargetHelper::OnUpdate` callbacks run first in every
  frame of player control, `OnSkillInput` callbacks rewrite the `ButtonState` vanilla
  `GetSkillInput` returns (an engine value type; the funcdef takes and returns it by
  value), and then the aim hooks run. gamelab-hands' `SpellButton` gives a 4th to 6th
  spell its own key only while GlobalCache `hwp_skillkeys_on` is "1" (set by the classes
  module's Start). Passing: mod-classes (20261026-212624), plan-classesb-a (212733:
  slice and cloak on `hwp_skill4`), mod-autoaim (212922), mod-all (213022).
- **Doctor false positive.** `class_units_problems` rebuilt each unit's expected text
  without the keys module's `scene_art` scenes, so the five chests with area art always
  read as stale, and `doctor --fix` ended "NOT ready" right after `class_units.py` wrote
  them. Both now use `class_units.expected(cfg)`; doctor is green.
- **Valuables and NG+.** Vanilla already adds `Tweak::NGPMaterialGain` (0.2) per NG+ level
  to every material gain (`PlayerRecord.GetMaterialModifier`), valuables included; a vase
  at NG+2 under a 1 + NG+ multiplier paid 150 x 3 x 1.4 = 630. Since vanilla already
  scales it, the mod stays at a flat 2x (6a4836c reverted by 22fce28). mod-valuables can
  flake when another valuable lies within 200 px of the drop (20261026-213539 picked up
  250); its rerun passed (213621).
- **Hero titles are vanilla** (`tweak/town/hero_titles.sval`, Guild Hall > Titles). The
  class mods add one title file each; `legacy` only presents them (the crown buff and the
  full list).

## 2026-10-26: goldpet removed; goldworth and mmhmm split out of core

- **goldpet removed.** Vanilla pets already collect gold, valuables and materials
  (`petOptions`), so the mod, its four scenarios, the pets mod's external-pet API
  (`RegisterExternal`) and the hunters' cabin vendor steps went; 173 scenarios dropped it
  from their mods list (a minimal text edit: a json.dumps rewrite reformatted them).
  Passing: mod-all (20261026-214721), mod-pets (214802), mod-town-rebuild (214816).
- **goldworth.** core's `items/materials/gold.unit` override (15 coin and pile looks) is
  its own module; fix-gold-sprites passes with it (215240).
- **mmhmm.** MmHmm.as and its modifier left core. The non-crit moments have no vanilla
  hook, so they are polled from what the game already counts:
  - wells and secret rooms: the run stats `wells-used` (Well.as Use) and `secrets-found`
    (SecretFound.as, on every peer), read with `statsRun.GetStatCurr(HashString(id))`;
  - trinket sets: owned trinkets per `m_set` against `m_totItems`;
  - the last orb: a `pickedTempSkills` entry reaching the tree's `m_levelParams` length,
    skipped when the tree has one orb;
  - Ace chests: vanilla's `chest-unlocked-ace` and keys' `hwp-chest-unlocked-*` stats are
    not defined, so `Stats::Add` books nothing for them (the keys ones were a latent
    no-op). keys now counts the opener's Ace chests in GlobalCache `hwp_keys_aces_opened`;
  - revives: class swap `PlayerCorpse` -> `HWPMmHmmCorpse`, whose `NetRevive` runs on every
    peer with both records. The swap needs `tools/class_units.py` to write the unit into
    the mod (GameLab does not generate it).
  A moment goes to the host (`mmhmm.say`), which drops the same key within 1.5 s and
  broadcasts it. The first poll of a level only seeds the counts.
- **Lab findings.** A Firearms gun aims at the mouse cursor (`Combat.as AimAtCursor`), so a
  bench without `gl cursor` toward the dummy deals no damage. `gl near` fails while the
  player is dead (no spawned local player); the corpse check reads its log line instead.
  New gamelab-hands verb `statadd <stat> [n]` (`Stats::Add`). AngelScript rejects
  `int &inout` parameters. A chest opened by the pilot's walk-up can lose to another
  usable; `gl use <filter>` opens it in place.
- Passing: mod-mmhmm (20261026-222000: single orb quiet, last orb, well, ace, secret,
  trinket set, corpse swapped, self revive quiet, needs hat), mod-all (222221),
  mod-keys (222237). A real two-player revive is untested.

## 2026-10-26: the Forgemaster's eating heals 30% of max health a second

- The devouring buff (Call of Heresy's lunge) gave `Modifiers::AttribAdd` health-regen 50.
  No vanilla modifier adds regeneration as a share of max health, so the specs module has
  `HWPSpecsMaxHealthRegen` (Forgemaster.as, pct 0.3): `stats.HealthRegen += stats.Health *
  pct` at `ModifierOrdering::Post`, where `stats.Health` is the final maximum. Player.Update
  regenerates `HealthRegen x HealthGain / Health` of the bar a second, so it is 30% a second
  (90% over the 3 s eat) unless healing is reduced.
- plan-forgemaster-eat's new `lunge_heal` (`gl hurt 0.05` once the eating starts, the bar
  read over 1 s) measured 0.30 a second (20261026-223750, all flags). The check runs after
  the lunge's pose reads: placed before them it delayed `lunge_lift` until the brute had
  pushed the priest 3 px. The Penance section's last raise now gets 500 mana first (five
  Penances left 35, under the raise's 70: 222826). `pen_faces_up` once read the priest
  12 px beside the body (223301) and passed on the next run.

## 2026-10-26: orb warnings, pickup-first and bet tokens leave core

- **orbwarn** is a module of its own (`mods/orbwarn`, requires core): OrbWarn.as moved as it
  was, with its `hwp.orbwarn.closes` line. **PickupFirst.as** moved to droptrade, whose
  UpdateFrame calls it after its own poll; the log tag is `[HWP:droptrade] pickup first`.
- **Bet tokens** moved to the gambler (`Tokens.as`, the same per-character `bet_tokens`
  key, and the `hwp tokens` cheat). Core's market keeps a generic second currency:
  `HWP::Market::Currency` (Held, Add, Amount, Status), which a module registers with
  `SetCurrency`. A ware with a token price sells for gold when none is registered, so
  fishing without the gambler sells fish for gold and says so (`*_gold` lang lines).
  Modules compile into one script set, so the hook is how core reaches a module's code
  without requiring it.
- **Materials tab:** core's character.gui keeps two untitled sections, `hwp-materials-a`
  (8 cells) and `hwp-materials-b` (16). A cell must exist when the menu collects its
  interactables, so the cells are static and generic: `HWP::Materials::Register(section,
  order, id, material)` fills them in order, and each cell takes its entry's id at refresh
  (`Widget.SetID` sets the hash `GetWidgetById` matches). `Title(section, key)` names a
  section (the first module wins); a section with no shown cell stays hidden. The gambler
  and fishing title section a "Supplies", farming titles section b "Plants & Herbs" (its
  Eat and Roll actions were already farming's).
- Gear slots (`GearSlots.as`, the rod and can frames in core's gui) follow the same
  pattern and stay in core for now.
- mod-orbwarn's `gl skill` step expected level 1, but Firearms actives start at rank 1 since
  23d8f08 (`RANK1_SKILLS`, so the raise gives 2); it expects `raised: 1`. mod-droptrade-pickup
  walked off (200 ms) and back. That needs the step off to leave the trainer's use radius,
  and 27 px does not (230213: back within 8 px, only the rifle usable); the walk back once
  took 1 s of wall time for its 7 frames and overshot by 21 px (225001: no usables), and a
  `gl teleport` back starts no collision from 58 px out (230300). The trainer and the rifle
  now spawn 40 px ahead and the player walks onto them (300 ms), which starts both
  collisions: 230401 passes, the rifle on top at 4 px, the trainer second.
- plan-farming-a fails s2 (the walk onto the onion groove ends 40-100 px off, so the
  cabbage goes on plot 16), s8 (it waters that groove) and s7's puff count (5/5 read
  first, 1/5 last) on two runs (225133, 225726). The farming diff here only changes the
  Materials registration, and the Plants & Herbs check passes; the last earlier run was
  20261020, so they most likely came in between (unconfirmed: no run on the previous commit).
- mod-all now lists orbwarn. Passing: mod-orbwarn (225637), mod-droptrade-pickup (230401),
  mod-supplies-tokens (225023), plan-fishing-e (225039), mod-all with orbwarn (230506).

## 2026-10-26: one path, two mods

Measured to decide how packages share code (probe mods `gamelab-dup-a`, `gamelab-dup-b`;
scenarios `dup-path-ab`, `dup-path-ba`, `dup-path-a`). Both mods ship
`scripts/HWPDup/Shared.as` with a different `const string WHO`, an identical `Same.as`
class, and `res/language/english/hwp_dup.lang` with different text.

- **It loads, with one logged ERR per shared script path.** Two enabled mods with a file at
  the same path compile and load in either order: the game keeps one file per path, scripts
  and lang files alike, and an identical class in both is one class. The engine logs it,
  though: unpacked, `[ERR] Resource name hash conflict between 'scripts/HWPDup/Same.as' and
  'scripts/HWPDup/Same.as'!` once per shared `.as` (2 lines in 230644 and 230659, none for
  the lang file, none with dup-a alone); packed, `[ERR] Resource name hash conflict in package
  'mods/HWP-keys.bin' for file '<path>'` once per shared file of the later package, any kind
  (37 for HWP-qol + HWP-keys, the hwplib files). Nothing shows on screen and no script error
  follows.
- **The first mod added wins.** For unpacked mods that is the folder order of the boot's
  `Adding unpacked mod` lines (alphabetical), not the save's list order: a+b and b+a both
  logged `WHO=a lang=lang-a same=1` (230644, 230659). dup-a alone works (230714).
- So a library can be copied into every package at the same paths: with identical bytes it
  does not matter whose copy wins. Packed mods load the same way.
- **Packages measured** (built .bin files, `tools/make_package_scenarios.py`): every package
  alone and the all-in-one pack pass (pkg-qol 233210; coop 233246, autoaim 233303, firearms
  233320, specs 233337, classes 233355, keys 233412, campaign 233429, modes 233446, dungeon
  233503, town 233520, pets 233540, all 233601): library booted, stamp check, the Luck cell
  shown only with `hwplib-luck`, the bag command only with keys, each package's own command.
  The pairs qol+keys, town+dungeon, all+qol and firearms+classes first failed only on the
  conflict ERRs above (233621, 233638, 233700, 233719); with `log_clean` allowing the packed
  conflict line, which the stamp check vouches for (one build ships one byte-identical copy
  of every shared path), all four pass (233832, 233850, 233912, 233931).
- So a player who enables two packages gets a few dozen of those ERR lines in the log per
  extra package. That is the price of packages that stand alone; the alternative, a required
  library mod, is the core mod this replaced.

## 2026-10-27: the Paladin of Generosity

Measured while building `Generosity.as` (scenarios `plan-generosity*`, bot
`gamelab/bots/plan_generosity.py`).

- **Finding a boss spirit:** the boss spirits (Arcane, Avarice, the Hunt, the Warrior,
  Benevolence) have sensor, aim-through bodies, and `g_scene.QueryCircle(pos, r, ~0,
  RaycastType::Any, true)` does not return them (plan-generosity-bosses 20261027-013518: four
  spirits read "no target" under the reticle). `g_scene.FetchActorsWithOtherTeam(team, pos,
  r)` does, so the Fury's pick merges both lists.
- **The gl `near` verb is capped.** The Spider Queen's spiderlings pushed her out of the
  list, so the bot hit a spiderling (one beam, a 30 s cooldown). The bot now passes the
  unit's name as the filter.
- **The vanilla stun does not stop every cast.** A `CompositeActorSkill` with neither
  `m_restrictions.m_isAttack` nor `m_isSpell` keeps casting under it (Arista, the Spider
  Queen, Dace Arden). The hold now cancels every casting skill whose type name has neither
  "Triggered" nor "Aura" in it (`Reflect::GetTypeName`), each frame.
- **A stunned unit with no body crashes its movement.** A boss spirit's dive runs a scene
  with no collision (`GetPhysicsBody()` is null), and the Serpent tunnels with none.
  `MeleeMovement::IdleUpdate`, which the stun's zero speed sends a unit to, then calls
  `m_unit.GetPhysicsBody().SetLinearVelocity` on a null body (MeleeMovement.as:162, a null
  pointer access: Benevolence in 015348, Arcane in 021003). `MeleeMovement::Update` (line 231)
  and `RangedMovement::Update` return early when `!m_enabled`, so the hold sets `m_movement.m_enabled
  = false` while the body is gone and back after (`MoveGuard`), and `CutCasting` skips a
  bodiless unit. A Fury on a unit that has no body when cast is refused, "out of reach"
  (a held tunnelling Serpent kept its skill in 021403). 021757 had no script exceptions.
- **A real press below the cost never warned.** `PlayerTargetingHelper.CheckQueued` asks
  `CanActivate(false)` while the input is buffered and `CanActivate(true)` only once
  `SkillInputBufferFrames` (3) runs out, which a press refused on every frame never reached
  (plan-generosity 20261027-015913: no refusal, no "cant" sound). The Fury now refuses on
  the press frame too (`m_targetHelper.GetSkillInput(this).Pressed`), once per 300 ms.
- **A TargetAOE skill aims at the real mouse.** Its reticle reads `input.MousePos`, not the
  emulated aim, so a bot's button press casts wherever the real mouse is. The tests aim the
  Fury through `hwp gen fury <dx> <dy>`, and the button test passes on a cast or a refusal.
- **The farming trait** reads the party's classes (`g_players[i].peer != 255` and
  `playerClass.m_id`), so it holds whichever player is the paladin; plan-generosity-farm
  20261027-015840 doubles the wild chance (35% to 70%) and grows a cabbage two stages in one
  run.
- **Runs:** plan-generosity 20261027-020522, plan-generosity-farm 20261027-015840 and
  plan-generosity-bosses 20261027-022232 (16 of 18 bosses held, the Serpent and the Shadow Face refused by design) pass. The boss spirits move off between the cast and its
  castpoint, so the bot finds the boss again before each retry (021757 reused a stale aim).

## 2026-10-27: Code review fixes (1c5335c..def346d)

`/code-review high` over the core removal, the packages, the vanilla-tuning removal, the
goldworth and Mm-hmm! split, the Forgemaster's eating and Generosity found ten problems.
Fixed:

- **The Dev Arena scenarios still listed `core`** (35 of them), so preflight refused every
  one ("mods/core has no info.xml"). They list `hwplib` now; `env.expand_mods` adds the rest of
  devarena's `requires`. That then showed a runner bug the core removal brought in: devarena
  requires `gamelab-probe` and `gamelab-hands`, which the fixture already enables, so the
  wanted list held them twice and "enabled mods are exactly the fixture's + the scenario's"
  failed (spike-class 20261027-024616). The runner now drops the fixture's own mods from the
  expanded list (spike-class 024802 passes). `tests/test_devarena_clone.py` still expected
  `requires == ["core"]` for a cloned spec; it expects `hwplib, hwplib-classui`.
- **`tools/devarena/export.py` baked vanilla paladin edits into Generosity's copies.**
  `make_specs_classes.py` copies Lay on Hands and Conviction with their vanilla ids, so an
  edit to `pal_lay_on_hands` found that file instead of being refused as vanilla, and the next
  regenerate would have dropped it. `skill_files` now skips those generated copies (a test
  covers it).
- **Holy Sacrifice paid out on any end of the target**, a despawn or a boss swapping its unit
  included. It now needs the target's `IsDead()` (CompositeActorBehavior reads `m_hp` and
  `m_dead`, so it answers on a destroyed unit's behavior too); otherwise the hold just ends
  ("the target is gone"). plan-generosity 024132 passes.
- **`build.py all qol` wrote all twelve packages**, and `build.py --no-all all` built nothing
  and exited 0. Only the packages named (every one when none is) and the pack are written
  now, and `--no-all all` is an error. pkg-pair-all-qol 025050 passes, writing only
  `HWP-qol.bin` and the pack.
- **A package's closure listed a library part before its base** when the base was reached
  only through the part. The walk now adds each module after what it requires.
- **`env.link` in check mode** called a previous `pkg-*` scenario's package copy a problem
  but let a previous scenario's mod junction pass; it tolerates both now, and hashes each
  package once a side instead of up to four times.
- **The specs texts said seven specs** (`packages.json`, `mods/specs/info.xml`, which also
  still used the old Stormbringer and Invocation names); they say eight and name Generosity.
- `make_package_scenarios.requires_closure` is `env.expand_mods` now, and `run.mod_id` is
  `env.package_file(p).stem`.

Not changed: a `pkg-*` preflight still rebuilds the packages each run. Skipping it when
`dist/` looks current would need every input of a build tracked, and a stale package in a
test is worse than a rebuild. export-boot was not rerun: its wrapper needs a tuner-dock run's
log and none is kept in `gamelab/results/`.

## 2026-10-27: Script errors and game updates

The question: can a game update that breaks a script crash the game for players, and can
the scripts protect themselves? Measured on Build 176 with four probe mods (each a GameLab
mod, never deployed to play).

**A compile error stops everything** (`compile-err` 20261027-025559, `gamelab-compile-err`
calls a function that does not exist). The mod scripts and the base scripts compile as one
module, so nothing runs:

- The log has `ERR : <file>`, then `SE : No matching symbol`, then `[ERR] Please correct the
  errors in the script and try again.`
- The engine compiles twice, then sits on the main menu with an empty grey box.
- The window ignores WM_CLOSE; the harness kills it after 30 s.

The runner now treats a scenario with `"compile_error": true` as measuring this: it takes a
shot, records the errors and passes.

**`try`/`catch` works, and a caught exception is silent** (`throw` 20261027-030133,
`gamelab-throw`). `getExceptionInfo()` is not registered ("No matching symbol", 030042), so a
script cannot read what it caught. The engine logs an uncaught exception once with its stack
trace, then `Last script exception repeated N times` up to 10, then nothing. The module
exception that followed the hook's was never logged.

**Hooks are isolated; modules are not.** A screen shake entry, which
`AGameplayGameMode::UpdateFrame` ages after its module loop (lines 335-340), was read 120
frames after it was added in each phase:

| phase | ms aged in 120 frames |
|---|---|
| quiet | 4059 |
| a `[Hook] GameModeUpdate` throwing every frame | 3960 |
| a module's `UpdateFrame` throwing every frame | 0 |

A throwing hook loses only its own call. A throwing module aborts the rest of
`AGameplayGameMode::UpdateFrame` (line 333 onward) on every frame: the later modules, screen
shake, `g_scene.Ping`, spectating and `HWR2GameMode`'s death check that opens the DeadMenu.
Vanilla wraps only module `Save` in a try (line 706).

**A throwing module constructor is contained** (`throw-ctor` 20261027-031426,
`gamelab-throwctor`). `InstantiateClass` logs `Script exception: Null pointer access` with no
stack, returns null, and `MakeModules` goes on with the next type: 21 modules were made, and
hwplib's core ran. Only the module that threw is missing.

`Modules::MakeModules` instantiates only direct subclasses of `Modules::Module`
(`GetBaseType() !is modType`), so the guard cannot live in a shared base class. Instead each
entry point is wrapped where it is declared.

**`HWP::Guard`** (`mods/hwplib/scripts/HWP/Core/Guard.as`, applied to all 45 entry points by
`tools/guard_modules.py`). `guard` 20261027-031629, with `gamelab-guard`'s body throwing every
frame from frame 300:

- The first failure is logged as `[HWP:guard] <Class>.<Entry> threw a script exception`.
- The next call runs unguarded once, so the engine logs the stack trace, which names
  `GuardedUpdateFrame` line 44.
- 29 more failures in a row turn the entry point off (`turned off until the next level after
  30 script exception(s), 30 in a row`), and the chat gets `hwp.guard.tripped`.
- The body stopped at frame 330.
- The shake aged 3993 ms both while the body failed and after the trip.
- `hwp guard` listed `GameLabGuardModule.UpdateFrame: 30 error(s), turned off 1 time(s)`.

The setting `guard.off` runs every body unguarded, for debugging.

**`Network::GetBuildVersion()` returns 176** on Build 176, the number in the log's
`Build 176:` line. hwplib logs it at boot beside `HWP::TESTED_BUILD`, and the first town tick
on another build sends `hwp.guard.new_build` once per build (the setting `guard.told_build`).
The guard scenario stands in a different tested build with the setting
`guard.tested_build 175` and `hwp guard build`; the second check stays quiet.
`tests/test_guard.py` keeps `TESTED_BUILD` equal to `gamelab/build_id.json`.

There is no script preprocessor to fall back on: no `#if` anywhere in the base scripts. A
compile error therefore cannot be guarded in script. `docs/GAME_UPDATES.md` is the checklist
that catches one before players do, and the 33 wholesale overrides are the most exposed part.

## 2026-10-27: Packages on their own, HoH1 stand-ins, mixed builds

**Every feature scenario against the built packages.** `tools/make_package_scenarios.py`
writes `gamelab/scenarios/pkgfeat/pf-<scenario>.json` for each feature scenario. The copy
loads the packages that ship the scenario's mods (at most three) in place of the source
folders, and keeps only the gamelab probe mods. Looks, benchmarks, probes and the
`needs_hoh1` scenarios are skipped.

The first suite (`suite-20261027-032903-pkgfeat`) passed 134 of 167. Each failure was rerun
as a package, and the never-run ones also from source (`suite-20261027-073231-_triage`,
`suite-20261027-081834-_triage`). None failed only as a package:

| class | scenarios |
|---|---|
| passed on a rerun | abyss-tiers, droptrade-pickup, valuables, waygates, qa-module-pets-standalone, qa-classes-gladiator-actives, qa-specs-wizard-charge-orbs, qa-content-weapons-native-standalone (its first failure was `native_frame_continuity: false`, an observer gap) |
| HoH1 content a release never has | fix-campaign-battlements, -portal-version, -traps, mod-trinkets, qa-module-campaign-portal-standalone (now `needs_hoh1`) |
| a test fault, fixed | plan-forgemaster-units: `errors_since` counted the vanilla `[WRN] SValue param error: missing string 'description' (file: tweak/pets.sval)` because "error" was in its first 40 characters. mod-mercenary: `cht_damage 999999` sometimes does not kill (blocked or during invulnerability), and after it does, the next one fails with "no local player"; one `ply_kill` instead (083709). plan-runs-arch: the loadout list scrolls, so 3 of the 7 red challenge rows are listed, not 7 (083623). |
| fails from source the same way, open | fix-specs-arcane (blink 92 of 112 px, "nudged"), mod-options-tab (the inbox transport's `!gl c17 ...` text lands in the focused search field), mod-puzzle-rooms-outdoor (no constellation found), plan-forgemaster and -bosses (failing since 20261022), and 12 qa-* scenarios from d9d96f8 with no run on this machine before: gladiator/thief/witchhunter integration (the bot dies on floor 0), vanish, chatlinks-native (`chat_empty_off_fixture`), laststats-native, summons (`no_summons_in_town`), specs arcane-ranks, branding-orbs, deadeye-ward, static and static-overlap (the static controls want 0 spell crit, and a level-20 wizard has 3%) |

**The pets package carried HoH1 files.** `HWP-pets.bin` and the all-in-one pack held the 216
pet units, sprites and the `pets_hoh1.sval` that `tools/import_hoh1.py` had cut from this
machine's HoH1 install. They are gitignored but were not in the module's `local` list. The
list now names them. `tests/test_release_files.py` asks `git check-ignore` about every file a
release package carries and fails on any ignored one, except the generated blocks in the
HoH2-base `.gitignore`s. Nothing had been uploaded.

**HoH1 stand-ins** (`HWP::HoH1`, hwplib `HoH1.as`). Four modules report once they have looked:
- campaign: the HoH1 mission def;
- classes: the string `hwp.classes.hoh1art`, which `import_hoh1.py classes` now writes beside
  the art it cuts;
- pets: the HoH1 pets it imported;
- trinkets: the art ids string.

The core module waits for the town's 60th gameplay tick, after every self-check. Without HoH1
(`hoh1-standins` 20261027-082947, packages campaign, classes, dungeon and pets) it logged
`[HWP:hoh1] on stand-ins: campaign,classes,pets,trinkets` and sent one chat line naming what
each keeps instead. The setting `hoh1.told` holds the reported set, so the line comes again
only when the set changes. With this machine's import (`hoh1-installed` 082930) nothing was
said, and `hwp hoh1` named each installed feature.

**Mixed builds.** The check module `build.py` generates now also calls
`HWP::Packages::Mismatch("HWP-<id>")`, and the player gets one chat line in town
(`pkg-mismatch` 083609: the probe `gamelab-stampfake` carries a check made with stamp
`000000000000` beside `HWP-qol`). An older package whose library copy wins makes a newer
package's calls to newer library code fail to compile, so `Mismatch` and `LIB_STAMP` are
frozen (`docs/modules.md`, Packages). The all-in-one pack with all twelve packages beside it
(`pkg-all-every` 083528): 12 stamp checks passed, no mismatch, a clean log.

**Small finds.**
- The Witch Hunter's Pyre (`pyre.sval`) is a `Skills::SpawnUnit : ActiveSkill`, which reads
  `blocking` as a bool (ActiveSkill.as 73). Its `ivec2` was ignored with a warning on every
  load; it is now `false`, the value it had.
- In `pf-qa-classes-witchhunter-integration` (both runs, pass 2) a vanilla
  `players/ranger/units/wolf.unit` threw `Null pointer access` in
  `PlayerOwnedActor::GetMaxHp` ten times as the town loaded: a Hound wolf with no owner yet.
  Not seen from source; open.
- `HWP::Guard` records are per level (script globals reset), so `hwp guard` now says
  "on this level".
