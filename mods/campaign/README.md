# campaign

**The Forsaken Tower**: the Heroes of Hammerwatch 1 campaign as a HoH2
mission, started from a portal in town. One `MissionDef` in its own set
(`hwp_campaign`), 18 floors from difficulty 5 to 22: each HoH1 act is two
generated floors in the closest HoH2 theme plus a vanilla boss level.

| HoH1 act | HoH2 theme | Boss level |
|---|---|---|
| Mines | theme_cave_dark | boss_totem_cave |
| Prison | theme_dungeon (vanilla's unused theme_prison never generates) | boss_arista |
| Armory | theme_barracks | boss_harbingers |
| Archives | theme_crypt | boss_wraith |
| Chambers | theme_courts | boss_bone_serpent |
| Battlements | theme_keep | boss_avatar |

- **The real HoH1 levels** are a second, optional mission in the same set,
  "The Forsaken Tower (HoH1 levels)": the same 18 floors, with the five act
  boss rooms, both Battlements levels and Thundersnow taken from the
  player's own HoH1 install by `tools/import_hoh1.py campaign` (see below).
  Without the import only the mission above exists. The generated act
  floors stay HoH2 themes: HoH1 builds those from 755 unit types HoH2 lacks
  (`tools/import_hoh1.py levels` reports them).
- **Portal.** `doodads/hwp/forsaken_portal.unit` is an NPC doodad whose
  interact is `HWPCampaignShopContent`, the vanilla `MissionShopContent` limited to set
  `hwp_campaign`, so the host picks the mission and the normal loadout menu opens.
  **Which version:** whenever the HoH1 mission (`hwp_forsaken_tower_hoh1`) exists at
  runtime, the portal offers it alone (`HWP::Campaign::PreferHoH1`, decided per
  interact, so a fresh import is picked up without a module change); without the
  import it offers the HoH2-theme mission. `campaign.portal_both` (default off) lists
  both. The log says what it offered (`portal: offering hwp_forsaken_tower_hoh1 (HoH1
  levels)`) and what the host started (`portal: starting <id> (<version>, N floors)`). The missions need the story intro flag
  (`mission_story_intro_find_npcs`), like the vanilla mission boards; before that the portal
  shows "The portal is dormant..." over the player instead of opening (vanilla would throw:
  sorting an empty array is an "Index out of bounds" in this engine). Clients see the host's portal (netsynced doodad). The host spawns
  it (`HWP::Town::Placeable` in core) 0.6 s after the town loads, **in the
  chapel courtyard in place of its campfire** (the unbuilt Pyre). Every
  machine computes that spot from the town layout data the way
  `TownRecord::SpawnTown` does (`PyreSpot`: the base segment's chapel cell +
  the chapel's `unbuilt-placed-prefabs` cell for `pyre_tier_0.pfb`, 16 px
  cells; (984,-232) on the current build) and hides the campfire there
  locally while the portal stands on it. Vanilla places that campfire as a
  prefab static, which no scene query returns and nothing can hide, so the
  module overrides `prefabs/town/buildings/pyre/pyre_tier_0.pfb` (`.orig`
  committed) with the campfire moved from statics to units.
  Once the Pyre is built (a real building: it lowers shadow-curse gain) it
  stays and the portal stands 72 px below it. After a building upgrade
  rebuilds the town, the portal is placed again within a second.
  `hwp campaign here` saves the spot where you stand instead (setting
  `campaign.portal_x/y`; the campfire shows again), `hwp campaign reset` goes
  back to the courtyard. Only when no chapel is found is it at the old fixed
  default -1700,250 (in the sea west of the coast). `campaign.enabled` turns
  it off.
- The mission is conditional on `mission_story_intro_find_npcs` like the
  vanilla boards. Every floor uses `diff-level-ngp` = diff + 8 like the
  vanilla tower chain.

## Real HoH1 boss levels (`tools/import_hoh1.py campaign`)

Converts `levels/boss_{mines,prison,armory,archives,chambers,dragon}.lvl` and
`battlements_1|2.lvl` with everything they reference (1410 files: units,
textures, effects, prefabs, tilesets) into `mods/campaign/hoh1/` (in-game
paths `hoh1/...`) and writes
`tweak/hwp/missions/missions_hwp_forsaken_tower_hoh1.sval`, plus
`tweak/missions/missions_dark_citadel.sval`: the main game's Dark Citadel as
**two Dark Halls floors (`dark_halls_1`, `dark_halls_2`: vanilla ships the second one
commented out) then both HoH1 Battlements floors (clouds, breaking bridges, glass
walkways, giants) before the Avatar**, every floor at diff 22 / NG+ 22 like the
surrounding floors; a declared override (`.orig` committed) that only the import
generates. `Citadel.as` repairs the list at runtime as well (`HWP::Campaign::Citadel::Fix`
on every level load): an import made before this change (doctor does not re-import an
existing one) gets `dark_halls_2` inserted and the Battlements raised to 22, and when the
import is absent the vanilla floors stay with the log line `vanilla Dark Citadel floors
(HoH1 import absent): ...`. `hwp campaign citadel` prints the floor list
(`N:id, ...`) and the `m_idNext` chain. A save in the middle of a Dark Citadel run shifts
by two floors when the import appears or goes away. All of them are
gitignored and only exist on a machine with HoH1 installed; `build.py`
leaves them out unless `--with-local`. The log is
`hoh1_import/campaign/convert.md` (every rewrite counted, plus the 14
references HoH1 itself does not ship).

The converter (`tools/hoh1_convert.py`) rewrites paths, materials, fonts and
classes; loose `.lvl`/`.pfb` are written as SValue XML (the engine reads loose
mod files as XML) and `build.py` compiles them back to binary when packing.
HoH1 classes HoH2 lacks are mapped by `CLASS_MAP` in `tools/import_hoh1.py`
to our own implementations under `scripts/HWP/Campaign/HoH1/`, written
against HoH2's base classes with HoH1's unit parameters:

| File | Classes |
|---|---|
| `Effects.as` | `HoH1GiveGold`, `HoH1GiveOre`, `HoH1Decimate` (the wraiths' % HP / mana drain), `HoH1AddCurse`, `HoH1InertEffect` |
| `Projectiles.as` | `HoH1Projectile`, `HoH1TossProjectile` (vampire bats), `HoH1LurkerProjectile` (golem / dragon / warden ground spikes) |
| `Skills.as` | `HoH1JumpStrike`, `HoH1ChargeStrike`, `HoH1SpewSkill`, `HoH1WhirlwindSkill`, `HoH1WhirlNovaSkill` |
| `Bosses.as` | `HoH1BossLich` (+ movement, random skill: the Three Councilors), `HoH1BossVampire` (+ movement), `HoH1BossEye` + `HoH1BossEyeWisp` (the Watcher) |
| `WorldScripts.as` | HoH1 level scripts by their HoH1 names: environment, boss bar, wind, lich / vampire nodes and room, eye wisp scripts, elevators, shops... |

Boss state the host decides (which node the councilors go to, vampire
roaming, eye wisps) goes to the clients over the core `HWP::Net` bus
(`hoh1.lich.node`, `hoh1.vampire.*`, `hoh1.eye.*`); skills use the usual
`NetSendUnitUseSkill` stages.

Design calls to look at:

- **Gold and ore** pickups credit the player who picks them up (HoH2
  materials). HoH1 shared gold across the party.
- **Elevators** (`StoreOre`) are scenery: HoH1 banked run gold and ore at
  home for a tax; HoH2 keeps what a run earns anyway.
- **Item forge** (`ShopArea`) is inert: HoH2 has none of HoH1's shop menus.
- **Shrine, blood altar, imp** rooms use HoH2's `Shrine` (random shrine
  buff; the blood altar too, HoH2 has no blood altar rewards) and `Imp`.
- **Lunar Shield block, Soul Dagger, Combustion** effects are inert
  (`HoH1InertEffect`) until there is a HoH2 equivalent.
- **Minibosses** are plain `CompositeActorBehavior`: HoH1's overhead
  miniboss bar is gone. `CompositeActorBehaviorNoNGPScale` (the dragon's ice
  block) scales with NG+ like everything else.
- **Bat toss** "on-target" speed is our own formula (slow enough to land on
  the aimed spot within its time to live).
- Wraith statues (`TransferDamageActor`) get one empty state injected; HoH2
  requires a "states" list.

## HoH1 traps, Confusion and teleporters in HoH2 runs

HoH2 runs and the campaign floors get three HoH1 mechanics, built from HoH2 units
(`Traps.as`, `Confusion.as`, `Teleporters.as`). They are placed by the dungeon
generator: `Traps::Install` appends one `HWPTrapSpawn` generation command to every
indoor `DungeonGenerator` (outdoor `ForestBrush` floors are skipped) and the command
places prefab set `hwp_traps` (`tweak/hwp/campaign_prefabs.sval`,
`prefabs/hwp/traps/*.pfb`, 3x3 walkable-floor patterns) then one `hwp_teleporters`
pad, host side like every prefab. The log says `traps: placed N/M on a WxH floor
(C floor cells, density D%)`.

| Trap | Unit | HoH1 feel |
|---|---|---|
| Spike floor, spike row | vanilla `doodads/traps/floors/floor_spikes.unit` (on) | the always-on spikes of the Mines |
| Flame jet | vanilla `doodads/traps/floors/floor_fire.unit` (proximity) | Armory floor burners |
| Bomb glyph | `doodads/hwp/traps/hwp_glyph_bomb.unit` (`TripMine`, shows at 48 px, triggers at 24, 1.1 s fuse, fire + lightning blast, re-arms after 8 s) | the Archives' exploding glyphs |
| Dart glyph | `hwp_glyph_dart.unit` (fan of 8 vanilla arrows after 0.2 s, re-arms after 5 s) | dart traps |
| Confusion glyph | `hwp_glyph_confusion.unit` (1 s Confused on everyone in 40 px) | the Chambers' confusion glyphs |

**Confusion** (`tweak/hwp/campaign_buffs.sval:hwp_confusion`, 2.5 s, engine `confuse`
flag: movement input inverted, with an icon and a purple pulsing screen tint while it
lasts; `hwp_trap_confusion` is the 1 s trap version). HoH2 has no enemy that applies it,
so the sources are HoH1's: the eyes (`actors/aberrations/eyes/*`, 35 % per hit,
`campaign.confusion_eye_chance`) through the `PlayerDamageTaken` hook, and the glyph.
`hwp campaign confuse [ms]` applies it (cheats on).

**Teleporters** (`doodads/hwp/teleport_pad.unit`, `HWPTeleportPad : IUsable`): a pad
with one fixed destination the player cannot see, the same on every use, like HoH1's
Archives pads. The generator picks it when it places the pad: the farthest trap, puzzle or
treasure point of interest on the floor (so it sometimes lands you in a trap room),
else the farthest floor cell, logged as `teleporter placed at X,Y (cell x,y) -> DX,DY
(cell x,y, why)`. The host moves the user (`UnitTeleported` message like a vanilla
teleport); a client's use reaches the host as `NetUse`. The destination survives a
save (`Save`/`Load`). `hwp campaign teleporter [dx dy]` spawns a pad next to the player
on the host and prints every pad with its destination.

| Setting | Default | What |
|---|---|---|
| `campaign.portal_both` | false | the portal lists both tower versions |
| `campaign.traps` | true | HoH1 traps on generated indoor floors |
| `campaign.trap_density` | 100 | % of one trap per 120 floor cells (0..400, 1..24 traps a floor) |
| `campaign.confusion` | true | Confusion from eyes and glyphs |
| `campaign.confusion_eye_chance` | 35 | % chance an eye's hit confuses |
| `campaign.teleporters` | true | one teleporter pad per indoor floor |

`hwp campaign traps` prints the settings and how many floors carry the command.

## HoH1 level import (`tools/import_hoh1.py levels`)

HoH1 and HoH2 share the level container: `.lvl` is 8 header bytes plus a
binary SValue dict (`tiles`, `game-mode`, `version`, `lighting`, `units`,
`scripts`, `prefabs`), `.pfb` the same dict at offset 0. The decoder in
`tools/hwr_archive.py` reads both games' files to end-of-file (every HoH2 and
HoH1 level and prefab, 6491 files). HoH1 acts are generated from prefabs
exactly like HoH2 themes; only the boss levels and the two Battlements
levels are hand-made.

The importer decodes the boss level + act prefabs per act and follows every
prefab they reference in other folders (chests, loot, boss rooms). It
writes `hoh1_import/campaign/levels/*.json`, `report.md|json` and the
referenced tilesets (textures as PNG), all gitignored, and warns about
references HoH1 itself does not ship. Unit types count both placed units and
the ones scripts spawn (`UnitType` params, spawners). Status on 2026-10-16:

| Act | files | tilesets (in HoH2) | unit types (in HoH2) | script types (unknown to HoH2) |
|---|---|---|---|---|
| Mines | 205 | 6 (1) | 154 (3) | 71 (14) |
| Prison | 195 | 4 (1) | 159 (3) | 72 (13) |
| Armory | 210 | 6 (1) | 225 (4) | 80 (16) |
| Archives | 198 | 4 (1) | 218 (4) | 90 (23) |
| Chambers | 209 | 5 (1) | 208 (3) | 78 (18) |
| Battlements | 82 | 5 (1) | 127 (3) | 58 (10) |

All acts together: 22 tilesets (1 in HoH2), 759 unit types (755 missing),
27 script types missing. HoH1 itself has broken references the port can
skip: Mines names `tilesets/anatolia_tile_inside_16 .tileset` (stray
space), Archives `prefabs/archives/maze_path_s_tele.pfb`, Chambers three
`prefabs/chambers/exit_*.pfb`.

What that means for a real port, in order:

1. **Tilesets** (22): same XML format, the textures convert with the
   existing texture tool. Tile layers: HoH1 stores `data` raw, HoH2
   `data-rle`; the RLE still needs decoding (HoH2 `.lvl` files are the
   reference).
2. **Level scripts**: HoH1 levels use 27 script types HoH2 lacks
   (`SpawnEnemyGroup`, `CreateBossBar`, `SetBossKilled`, `ShopArea`,
   `RandomLoot`, boss-specific nodes...). They are AngelScript `WorldScript` classes, so
   they can be written in the mod.
3. **Units** (755 types, the real cost): `doodads/walls/<act>/` wall sets,
   `doodads/generic/` traps and lamps, `actors/` enemies and spawners, the
   six bosses. Each is a HoH1 `.unit` XML whose behaviours only partly exist
   in HoH2; this is a per-enemy rebuild, not a conversion.

## Test checklist

1. `python -m gamelab run mod-campaign --mode lab`: `[HWP:campaign] self-check done: mission ok, N/N schemes`
   and no "missing unit" line for the portal.
2. Town: the log says `portal spot: the chapel campfire at X,Y`; a glowing
   portal stands in the chapel courtyard where the campfire was (no
   campfire under it), the minimap shows a portal pip. Upgrade any
   building: `the town was rebuilt, placing ... again` and the portal is
   back on the spot. Interact opens the mission picker with only
   "The Forsaken Tower" (18 floors, diff 5-22).
3. Start it: Mines floor 1 is a dark cave with goblins; the exit leads to
   floor 2, then the totem boss, then the Prison (cultists, bats)...
4. `hwp campaign` prints the mission, floors, span and the portal position;
   `hwp campaign here` moves the portal (the campfire shows again) and the
   new spot survives a restart (town record); `hwp campaign reset` puts it
   back on the campfire.
5. Co-op: a client sees the portal and can read the mission; only the host
   can start it (vanilla rule).
6. With HoH1 installed (`python -m gamelab doctor --fix` imports it), the
   portal offers the HoH1 mission alone and the self-check line reads
   "HoH1 floors installed, N trap prefabs, traps on N floors; Dark Citadel: ...".
   `python -m gamelab run fix-campaign-portal-version` (core + campaign, about 3 min)
   checks the portal version in the log and the dialog, `hwp campaign citadel` =
   dark_halls_1, dark_halls_2, hwp_battlements_1, hwp_battlements_2, dark_halls_boss,
   and the Confusion cheat (buff on, right moves left, expiry, glyph applies it).
   Loading each other HoH1 floor (mines_boss, prison_boss, armory_boss, archives_boss,
   chambers_boss, battlements_2, battlements_boss) is still to script with
   `gl mission <id> [floor]`.
8. `python -m gamelab run fix-campaign-battlements` (about 3 min): `gl mission
   dark_citadel <index of hwp_battlements_1>` loads `hoh1/levels/battlements_1.lvl`
   with no script exception, screenshot `battlements-1`.
9. `python -m gamelab run fix-campaign-traps` (about 4 min): the indoor Dark Citadel
   floor (`gl mission dark_citadel 2`, retried on another seed) logs `traps: placed N/M`,
   `gl unitsof` finds the trap units, standing on spikes / a bomb blast costs health,
   the generator's teleporter pad moves the player to the logged destination and to the
   same spot on a second use; screenshot `traps-floor`. Without the import the same
   scenario still passes (traps and pads need no HoH1 file; the HoH1 teleport effect
   falls back to the vanilla smoke puff).
7. Play each HoH1 boss once, solo and in co-op: the Stone Guardian's ground
   spikes, the Warden's whirlwind and bombs, the councilors teleporting
   between nodes (client sees the same node), the Watcher's wisps circling
   each player, the Vampire Lord roaming / transforming and his bats,
   Thundersnow on top of the Battlements.
