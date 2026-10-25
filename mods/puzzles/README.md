# puzzles

Puzzle rooms back in the dungeons, plus Heroes of Hammerwatch 1's Constellation.

- **Puzzle rooms.** HoH2 ships 88 puzzle rooms (`prefabs/<biome>/special/puzzle_room_*`,
  theme `<biome>_puzzle` in `tweak/missions/prefabs/<biome>_special.sval`), but no
  level theme places them: temple and crypt have the SpawnPrefabSet commented out,
  cave_dark and barracks ask for `<biome>_puzzles` (a set no prefab is in) and the
  other biomes never mention them. The module ctor adds one
  `HWP::Puzzles::PuzzleRoomSpawn` (a `SpawnPrefabSet`) to every mission level
  generator. Biomes with puzzle rooms use their own (barracks, cave_dark,
  cave_light, cave_light_inhabited, courts, crypt, dark_halls, dungeon, keep,
  prison, temple); cave_spider borrows cave_dark's. It is placed after the shrine
  and skill rooms, so a puzzle room never takes the space a mandatory room needs,
  places at most one room, and is skipped on `no_special` floors.
  The chance is `puzzles.room_chance` percent a floor (default 60). It is rolled in
  `Execute`, because the setting lives in the town record, which
  `MissionGameMode.Generate` loads after the module ctor has run.
  The mission defs, and with them the generators, are rebuilt on every level load,
  so the ctor adds the command again each time.
- **Forced onto the outskirts.** A room first tries the vanilla way: a spot whose
  cells already match its pattern (a solid wall block with a corridor end at its
  door). Most floors have no such spot, which is why vanilla's own puzzle sets
  would rarely place. So when that fails the room is forced: of every free block of
  solid wall big enough for one of the biome's rooms, the one farthest from the
  middle of the map whose door reaches the level by a straight corridor through
  wall (at most 40 cells) gets it, and the corridor is carved. DungeonBrush paints
  tiles from the cells, so the corridor and the room's frame look like the rest of
  the floor. The log says which happened (`[HWP:puzzles] ... rolled (60%): placed
  in a matching spot` or `forced <room> at x,y of WxH, corridor N (door dx,dy width w
  out ox,oy; world X,Y WxH) on keep_2`; every placement line ends with the mission
  level id, so a test can pin a line to its floor).
- **Rooms stay whole (2026-10-25).** Rooms came out partly covered or walled off:
  the door was derived from the prefab's junction, whose centre `SVO_Init_Post`
  shifts, so the keep's corridor was carved two rows below the real doorway (part of
  the door faced wall, the corridor's lower rows hit the room's frame); a forced room
  could sit on `Nothing`/`Cliff` cells (the black `Nothing` blocks spill a cell past
  their own); and the carved doorway and corridor stayed unconsumed, so later
  commands (dead-end fills, the wall/trap/deco sets, crates, enemy spots) could fill
  or furnish the way in. Now the door is the run of `Walkable` cells on one edge of
  the room's pattern; a forced room takes plain `Wall` only, with a one-cell wall rim,
  3 cells off every grid edge (the padding blocks cover the bottom 24 px); doorway
  and corridor cells are consumed once carved. Every placed room (forced, or matched:
  read from the set's new points of interest) is recorded (`HWP::Puzzles::Room`: cells,
  doorway, corridor, world rect) and `hwp puzzles check` walks them with the scene's
  point query: `room <id> (forced|matched) world X,Y WxH: door a/b open, corridor c/d
  open, interior e/f open, n puzzle unit(s) ok|PROBLEM`, then `check done: N room(s),
  M problem(s)` (`hwp puzzles rooms` lists them).
- **Summons wait outside (2026-10-25).** `scripts/HWP/Puzzles/SummonHold.as`: on the
  host, every unit a player owns through `PlayerRecord.summons` (Crusaders, wolves,
  the Forgemaster's risen, anything `RegisterSummon` took; no per-class list) is held
  while its owner is inside a recorded room's rect or within
  `puzzles.summon_hold_radius` px (120) of a puzzle unit (buttons, levers, braziers,
  constellation dots: the matched rooms and the outdoor Constellation). Held: its
  movement disabled (`ActorMovement.m_enabled`), target cleared, position pinned every
  frame to the owner's last puzzle-free spot in a small ring (the 350 px teleport leash
  would otherwise drag them in). Released when the owner leaves. Logged:
  `summons of <name> held outside <room|puzzle units>: n unit(s) at x,y` and
  `summons of <name> released: n unit(s)`. Off with `puzzles.summon_hold 0`.
  Pets wait on their own (`pets`, PetWait.as).
- **Outdoors the Constellation yields (2026-10-25).** Its set used to run right after the
  first special set; on the small encounter bases (forest_2, `forest_enclevel`) it took
  the clearing `forest_well` or a glade needed and the floor failed generation on every
  try (then the run-unique bases ran out and the generator spun). It now runs after the
  last set with `min > 0` and before the edges and fillers: a spare clearing or none.
- **Outdoor floors** (the forest and heaven themes, whose brush is `ForestBrush`)
  are one authored level prefab and paint nothing from the cells, so there is no
  wall to carve a room into. They get the Constellation in an open clearing
  instead: the set `hwp_puzzle_open` (`tweak/missions/hwp_puzzles_open.sval`, a
  10x14-cell spot that is walkable all over, reserved as floor), placed the vanilla
  way right after the floor's first special set, before the edges and fillers take
  the open ground (logged as `hwp_puzzle_open rolled (60%): placed in a clearing`,
  or `no open clearing`). The keep is an `OutdoorGenerator` too, but its
  `DungeonInstanceBrush` paints from the cells, so it gets rooms like a dungeon.
- **Architect challenge floors** get rooms like any other: Architect's
  `ChallengeSetup` wraps a command that is not a `SpawnPrefabSet`.
- **Constellation.** `prefabs/puzzles/hwp/puzzle_constellation.pfb`, generated by
  `tools/make_constellation.py` (`--check` fails while it is stale). It uses HoH1's
  eight class patterns on a 5x5 star field. A 5x5 chart of dots above the field
  shows the picked shape, since HoH2 has no HoH1 sigil art. Press exactly the
  pattern's stars:
  - a wrong star fails and locks the puzzle;
  - pressing all the pattern's stars solves it and drops the room reward (a forced,
    high-quality RewardSpot with no materials or pickups).
  Everything is vanilla worldscripts, so co-op sync and the use prompt are the
  engine's own.
- **Where it appears.** `scripts/WorldScript/Prefabs/PrefabPicker.as` overrides
  the vanilla picker (`.orig` = base copy). A picker that offers one of the large
  vanilla puzzles (`HWP::Puzzles::BIG`: chance, maze path, big memory, big lights
  out) has the floor space for it, so the Constellation joins its candidates with
  weight `puzzles.constellation` (default 10, the vanilla weight of each candidate;
  0 turns it off). At most one Constellation per floor (a level flag, like the
  vanilla picks' own).

Settings (host, saved with the town): `hwp set puzzles.room_chance <0-100>`,
`hwp set puzzles.constellation <weight>`, `hwp set puzzles.summon_hold 0|1`,
`hwp set puzzles.summon_hold_radius <px>`, `hwp set puzzles.debug_grid 1` (logs each
floor's cell grid before the room is placed), `hwp set puzzles.debug_force 1` (skips
the vanilla spot search, so every rolled room is forced; for tests).
Commands: `hwp puzzles check`, `hwp puzzles rooms`.

Pets already wait outside puzzle rooms (`pets`: unit paths containing `puzzle`).

Tests: `gamelab/scenarios/mod-puzzles.json` (Constellation fabricated in town and on
a mission floor: a wrong star fails, the right ones solve) and
`mod-puzzle-rooms.json` (a real keep floor places a puzzle room, its picker picks
the Constellation, it solves, and the reward spawns), `mod-puzzle-rooms-forced.json`
(the same with the room forced onto the outskirts: the bot walks in through the carved
corridor), `diag-puzzle-rooms.json` (a Dark Citadel run, forced rooms and cell grids
in the log), `fix-puzzles-room-integrity.json` (five generated floors: keep forced twice and
matched once, the dark cave forced (Dark Citadel floor index 2), the forest's
Constellation (floor index 0): the forced line's pattern-derived doorway, `hwp puzzles
check` with 0 problems on each, a shot of each forced room; not forest_2, the encounter
floor whose two run-unique bases a repeated entry uses up) and
`fix-puzzles-summon-hold.json` (fixture `town-ranger`, Beastmaster subclass, Wolf
Companion: bot `fix_puzzles_summon_hold` parks the player at the forced room's doorway,
steps in, and the wolf stays outside the room's rect while the hold and release lines
appear; the Priest's crusaders would take the same path, but that class is DLC-gated and
unavailable in the lab).

## Test checklist

1. `fix-puzzles-room-integrity`: every `check done` line has 0 problems; the shots show
   whole rooms with an open doorway.
2. `fix-puzzles-summon-hold`: `summons_out`, `summons_outside_room`, `hold_logged`,
   `release_logged`, `summons_rejoin` all true.
3. By hand: a Crusader Priest walks into a puzzle room; the crusaders stop at the
   doorway, the chat/log says `held outside`, they follow again on the way out. The
   same with a Ranger's wolves or the Forgemaster's risen (no per-class code).
