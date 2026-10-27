# objectives

Floor objectives for generated dungeon floors (bugs 10.22.26 line 46): locked
loot vaults opened by a switch elsewhere on the floor, and the way down sealed
until the floor's exit switch is pressed. Requires `hwplib`. Never on boss
floors or in town: those levels are authored (no `DungeonGenerator`), and the
generation command only runs on indoor generated floors (forest brushes are
skipped).

## How it works

- **Generation** (`scripts/HWP/Objectives/Generation.as`). The module
  constructor adds `HWPObjectiveSpawn`, a `DungeonGenerationCommands`, to
  every indoor `DungeonGenerator` right after its shrine/skill
  `SpawnPrefabSet` (idempotent; `[HWP:objectives] generator command on N
  indoor floor(s)`). On the host it runs once per floor:
  - `objectives.vaults` (0-2, default 1) vaults: `prefabs/hwp/objectives/vault_s.pfb`
    (9x8 cells: a walled room, two chests, `doodads/hwp/objective_door.unit`
    in the south doorway) is placed on an unconsumed wall block on the
    floor's outskirts with a straight corridor carved to the nearest floor
    (the puzzles module's spot search, copied). Its lever
    (`vault_switch.pfb`, `objective_switch.unit`, kind `vault`) goes on a 3x3
    floor block far from the vault. If no floor block is left, the vault
    opens from the start (logged as an error line).
  - `objectives.exit` (default on): the exit lever (`exit_switch.pfb`,
    `objective_exit_switch.unit`, kind `exit`) on a 3x3 floor block far from
    the floor's exit prefab.
  - Every placement is logged with cell and world positions
    (`vault 0 at cell x,y of WxH, corridor N, world x,y 144x128, door x,y,
    switch x,y`, `exit switch at cell x,y world x,y`, `placed N vault(s), exit
    switch yes|no`), which the lab bot reads back.
- **Units** (`Units.as`). The door is a vanilla-art door whose `locked` scene
  has a static, nav-blocking collision (nothing walks, shoots or paths
  through) and the map's `info_poi` icon; `open` plays the vanilla opening
  animation and has no collision. The levers are `IUsable`s like a chest
  (sensor circle, use key, `UsableIcon::Button`), with the map icon while
  unused. Both register in `HWP::Objectives::g_doors/g_switches` on
  construction and are found again by position.
- **Authority and sync** (`ObjectivesModule.as`). A lever use goes through
  the vanilla use path: the host runs `Use`, a client's press reaches the
  host as `UseUnitSecure` and only the host acts (`HostSwitchUsed`). The host
  broadcasts `objectives.opened` (kind, switch position, door positions);
  every machine flips the lever, opens the doors it finds at those positions,
  plays the quest-complete sound, shows the "A vault opened" announce or
  re-enables the exits, and refreshes the HUD. The exits are sealed by
  `SetEnabled(false)` on every `LevelExitAreaNext`/`LevelExitAreaJump` world
  script (`CanUse` checks `IsEnabled`) and every `LevelExitNext`/`LevelExitJump`
  (the keep's exit: a `UseTrigger` fires it, and a disabled script does not
  execute), on the host at level start and on a client when the host's state
  says so. The keep's `level_exit.pfb` is a PrefabPicker whose part fabricates
  after the module's Start, so the host retries the seal for 3 s and logs
  "exits sealed after start". A client sends `objectives.hello` at
  start and gets `objectives.state` (every vault and the exit with their
  opened flags), applied silently.
- **HUD** (`gui/hwp_objectives.gui`, `HWPObjectivesHUD`): a line under the
  region banner, "Find the switch to open the way down" until the exit lever
  is used, then "The way down is open" for 6 s; a second line "Vaults: n/m".
  Hidden on floors without objectives.
- Commands: `hwp objectives` (status, each vault's position and state, the
  exit switch); `hwp objectives open` (host, debug: opens everything through
  the same broadcast). Settings: `objectives.vaults`, `objectives.exit`
  (`hwp set`, synced by the host).
- Language: `res/language/english/hwp_objectives.lang` (`hwp.objectives.*`).

Known limits (lab run `fix-objectives`, 2026-10-26, keep floor 1):

- Measured: the locked door stops the player's walk at the doorway and the
  open door lets the walk into the room (the bot's `walk_in`). The engine
  pathfinder (`gl pathfind`, `gl reachmap`) answers empty from every cell of
  the carved corridor, sealed or open, while the room's own cells path fine:
  the corridor is off the nav graph as the puzzles module's corridors are,
  so enemies and pets may not follow a player into a vault. Not fixed.
- Prefab units placed by the generator should replicate to clients like
  every other generated prefab unit; `objectives.state` only flips them.
  Co-op is untested in the lab (one machine).
- Chests inside a vault are ordinary reward chests: with the keys module
  they also need a key. The vault has no light of its own.
- On a floor without a free wall block the vault is skipped (logged); a
  floor without a 3x3 floor block gets no exit switch and stays open.

## Test checklist

1. `.venv/Scripts/python.exe tools/build.py --check` passes with the module
   in the build list.
2. `python -m gamelab run fix-objectives --mode lab` (passes): a keep floor
   logs the vault, its switch and the exit switch; the bot's walk up the
   corridor stops at the locked door, two chests inside, the exits disabled
   and the HUD line; the vault lever opens the door (the walk reaches the
   room, Vaults 1/1, a second use does nothing);
   the exit lever enables the exits, the HUD says the way down is open and
   clears; `hwp objectives` reports 1 vault open and the exit switch pressed.
   Shots `floor-start-hud`, `vault-door-sealed`, `vault-door-open` and
   `after-switches`; the pathfinder's answers are in the bot's notes.
3. By hand: walk to the vault; the door blocks you and your shots; find the
   lever (map icon), press it: sound, "A vault opened", the door animates
   open. Walk onto the exit before the exit switch: no use prompt. Press the
   exit switch: the exit works.
4. `hwp set objectives.vaults 2`, new floor: two vaults, each with its own
   lever. `hwp set objectives.vaults 0`, `hwp set objectives.exit 0`: a plain
   floor, no HUD line.
5. Boss floor and town: nothing placed, no HUD line.
6. Co-op: the client sees the same door closed and the same levers; either
   player's press opens for both; a client joining after a vault was opened
   sees it open and the exit sealed/open as on the host (`state from host`).
