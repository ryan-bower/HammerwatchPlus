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
  - **The vault is drawn as the floor's own room** (issue #26). Its cells are
    `PlaceFloor` / `PlaceWall` (commands 06 / 05 in
    `tweak/hwp/objectives_prefabs.sval`), like vanilla's rooms that carry no
    art of their own, and the carved corridor is `PlaceFloor` too. They stay
    consumed through the generation commands. The brush's build turns them into
    plain Floor and Wall before it paints, so the vault gets the floor's tiles,
    spots and trim, and the theme's walls and torches. `HWPObjectivePainter`,
    added last to the brush's painting list, then consumes the floor cells
    again, so the enemy spots placed after the build stay out of the vault and
    off the lever patches. It logs `painted: N floor cell(s) of M, ring W wall
    cell(s) of 28, switches hidden|marked on <level>`.
- **Units** (`Units.as`). The door is a vanilla-art door whose `locked` scene
  has a static, nav-blocking collision (nothing walks, shoots or paths
  through) and the map's `info_poi` icon; `open` plays the vanilla opening
  animation and has no collision. The levers are `IUsable`s like a chest
  (sensor circle, use key, `UsableIcon::Button`). Like vanilla's levers, they
  have no map icon (issue #26), unless the Architect alteration **Marked
  Switches** (`hwp_objectives_marked_switches`, 1000 gold and 5 wood,
  `tweak/hwp/objectives_architect.sval`) is picked: then an unused lever's
  scene is `marked`, which adds the `info_poi` icon. Both register in `HWP::Objectives::g_doors/g_switches` on
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
  "exits sealed after start". A client retries its own seal for 3 s too
  when the host's state arrives before the exit part. A client sends
  `objectives.hello` at start and gets `objectives.state` (every vault and
  the exit with their opened flags), applied silently.
- **Preloaded floors** (issue #27). The game generates the next floor ahead,
  in a separate script context, while the party is still on the floor above
  (`[preload]` in the log). Taking the exit loads that floor whole, so the
  generation's records (`g_vaults`, the exit switch) never reach the context
  the floor is played in. The units do. So on a floor its own context didn't
  generate (also a floor loaded from a save), the host rebuilds the records
  from the units at Start (`AdoptFromUnits`): each door is a vault, each vault
  gets the farthest lever left, and the exit lever is the exit switch. It logs
  `floor not generated here (preloaded or from a save): N vault(s) and exit
  switch yes ... taken from the units, vault 0 door x,y switch x,y`.
- **HUD** (`gui/hwp_objectives.gui`, `HWPObjectivesHUD`): a line under the
  region banner, "Find the switch to open the way down" until the exit lever
  is used, then "The way down is open" for 6 s; a second line "Vaults: n/m".
  Hidden on floors without objectives.
- Commands: `hwp objectives` (status, each vault's position and state, the
  exit switch, and how many levers are on the map: `switch units: N, on the
  map: M (Marked Switches picked|not picked)`); `hwp objectives open` (host, debug: opens everything through
  the same broadcast). Settings: below.
- Language: `res/language/english/hwp_objectives.lang` (`hwp.objectives.*`).

## Settings

On the HammerwatchPlus tab of the player menu (host, synced by the host; next floor),
or `hwp set`:

- `objectives.enabled` (on): off places no vault, no switch and no exit seal on the
  floors generated after it (`objectives.enabled is off: nothing placed`). Turned off on
  a sealed floor, the host opens the way down at once (`exit opened: objectives.enabled
  is off`); a locked vault stays locked until its lever.
- `objectives.vaults` (1; 0, 1 or 2): vaults per floor.
- `objectives.exit` (on): the exit switch and the sealed way down.

The Architect's **Marked Switches** alteration (any player's Architect picks, vanilla's
picker) shows the levers on the map for that run.

Known limits (lab run `fix-objectives`, 2026-10-26, keep floor 1):

- Measured: the locked door stops the player's walk at the doorway and the
  open door lets the walk into the room (the bot's `walk_in`). The engine
  pathfinder (`gl pathfind`, `gl reachmap`) answered empty from every cell of
  the carved corridor, sealed or open, while the room's own cells path fine.
  Since the vault is drawn as the floor's own room (2026-10-29, a 9-cell
  corridor), 38 of the 70 cells around the sealed corridor's end are reached,
  but with the door open the corridor answers empty again. So enemies and pets
  may not follow a player into a vault. Not fixed.
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
2b. `python -m gamelab run fix-objectives-vault-art --mode lab` (passes; mods
   core + architect + objectives): on a keep and a temple floor every vault
   floor cell is painted as Floor and the 28 ring cells as walls, no lever is
   on the map, and shots from the door, inside and inside unlit; then with
   `hwp architect try hwp_objectives_marked_switches` both levers are.
3. By hand: walk to the vault; the door blocks you and your shots; find the
   lever (no map icon), press it: sound, "A vault opened", the door animates
   open. The vault's floor, walls and torches look like the rest of the floor.
   With Marked Switches picked at the Architect, both levers show on the map. Walk onto the exit before the exit switch: no use prompt. Press the
   exit switch: the exit works.
4. `hwp set objectives.vaults 2`, new floor: two vaults, each with its own
   lever. `hwp set objectives.vaults 0`, `hwp set objectives.exit 0`: a plain
   floor, no HUD line. `hwp set objectives.enabled 0` on a sealed floor: the exits
   open at once; the next floor is plain.
5. Boss floor and town: nothing placed, no HUD line.
6. Co-op: the client sees the same door closed and the same levers; either
   player's press opens for both; a client joining after a vault was opened
   sees it open and the exit sealed/open as on the host (`state from host`).
   On the second floor and later (preloaded floors), `state from host` names
   the vault and `exit switch sealed`, and the client's exits are sealed too.
7. `python -m gamelab run fix-objectives-preloaded --mode lab` (passes): keep 1,
   then down the exit to keep 2, which was generated in the preload context.
   The host logs the floor taken from the units, seals the exits, and both
   levers work (the vault opens, the exits enable); no lever line says it
   matches no vault. Shot `keep2-after-levers`.
