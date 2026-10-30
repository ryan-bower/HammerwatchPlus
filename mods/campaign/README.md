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
  "The Forsaken Tower (HoH1 levels)": HoH1's own 23 floors (`tweak/dungeons/base.sval`),
  the nine hand-made levels as HoH1 ships them and the fourteen act floors built by
  HoH1's own floor generator, all taken from the player's own HoH1 install by
  `tools/import_hoh1.py campaign` (see "HoH1 tower" below). Without the import only the
  mission above exists.
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
  it (`HWP::Town::Placeable` in hwplib) 0.6 s after the town loads, **in the
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
roaming, eye wisps) goes to the clients over the hwplib `HWP::Net` bus
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
- **Minibosses** are plain `CompositeActorBehavior`. HoH1's overhead miniboss bar was
  only on DLC minibosses, none of them in the tower. HoH2's own small bar shows over
  any damaged enemy. `CompositeActorBehaviorNoNGPScale` (the dragon's ice
  block) scales with NG+ like everything else.
- **Bat toss** "on-target" speed is our own formula (slow enough to land on
  the aimed spot within its time to live).
- Wraith statues (`TransferDamageActor`) get one empty state injected; HoH2
  requires a "states" list.

## HoH1 tower (`hwp_forsaken_tower_hoh1`)

The mission is HoH1's tower as its dungeon file lists it, difficulty 5 to 22:

| Act | Floors |
|---|---|
| Mines | mines_1-3 (generated), mines_boss (Stone Guardian) |
| Prison | prison_1-3 (generated), prison_boss (the Warden) |
| Armory | armory_1-3 (generated), armory_boss (the Three Councilors) |
| Archives | archives_1-3 (generated), archives_boss (the Watcher) |
| Chambers | chambers_1-2 (generated), chambers_boss (the Vampire Lord) |
| Battlements | battlements_1, battlements_2, bridge, battlements_boss (Thundersnow) |

- **Generated floors** run HoH1's generator scripts, copied out of the player's install at
  import time into the local `scripts/HWP/Campaign/HoH1Gen/` behind the committed
  `HWPHoH1Generator`; the log says `HoH1 floor generated: N prefabs, start at X,Y`.
- **Level scripts.** HoH1 world scripts whose HoH2 namesake reads other param names are
  renamed on import (`hoh1_convert.SCRIPT_PARAMS`: ChangeVariables, RandomChance,
  DestroyUnitCount, DamageUnits, DangerArea, AnnounceText, CheckTimeOfDay). The ones HoH2
  lacks or does differently are ours in `WorldScripts.as`: `HoH1ShowSpeechBubble` (HoH1's
  bubble style files, title, one player), `HoH1LevelExitNext` (keeps the exit's StartID:
  battlements_1's left and right exits), CreateBossBar, SetBossKilled and the rest.
- **Magical damage** (HoH1's armor-ignoring `magical`) goes to the element its source
  names: fire, ice, poison, or lightning (`hoh1_convert.MAGIC_ELEMENTS`).
- **Texts.** The import reads HoH1's `res/language/english.lang` and writes the strings
  the levels use, as `hoh1.<key>`, into the local `res/language/english/hwp_campaign_hoh1.lang`
  (announcements, speech bubbles, NPC names), plus `hoh1.bosses.<unit>` from HoH1's
  bestiary for the boss bars: HoH1's bar has no name, HoH2's has a name plate.
- **Tests.** `python -m gamelab run tower-floors --mode lab` (about 3 min) loads all 23
  floors: clean log, generated floors built and the player at their start, enemies around,
  a screenshot each. `python -m gamelab run tower-bosses --mode lab` (about 4 min) plays
  each boss floor the way its scripts run: the trigger met, the bosses spawned and
  fighting a god-mode player for 15 s, the boss bar titled with the boss's HoH1 name,
  each boss killed until SetBossKilled logs `HoH1 boss N killed`, then the exit it opens
  used to load the next floor; on the armory floor the painting's speech bubble is read
  back too. `plan-generosity-hoh1` and `plan-forgemaster-hoh1` hold every tower boss with
  the Paladin's Generosity Fury and raise every tower boss body with the Devil
  Forgemaster. `tower-run` (about an hour) plays floor 1 to the end through each floor's
  own exit: the enemies cleared, the traps toured until they fire, chests, doors, levers,
  shrines and pickups used, each boss fought, and the character's level and xp kept from
  floor to floor (20261028-190322, 16 min). `tower-interfaces` bets at a gambler room
  fabricated on floor 1 and takes the end window's CONTINUE after Thundersnow. All of them
  need the import.
- **The gambler and the end window.** HoH1's `ItemDealer` and `EndOfGame` interfaces are
  ported in `Interfaces.as` on HoH1's own .gui files. The gambler bets HoH2 trinkets
  (cursed, quest and unique ones are left out) at HoH1's points and odds, one gamble per
  gambler. The end window's CONTINUE ends the mission as a success. HoH1's `scrollrect` and
  `scrollbar` are ported as `hoh1-scrollrect` and `hoh1-scrollbar`, and the import renames
  the tags in HoH1's .gui files (`hoh1_convert.GUI_TAGS`).
- **The bridge's exit** is a plain LevelExit to boss_dragon.lvl in HoH1. The import turns it
  into `HoH1LevelExitNext`, so the mission's floor follows (`hoh1_convert.MISSION_EXITS`).
- **The vampire's crosses.** As in HoH1, a cross picked up on the chambers floors keeps the
  Vampire Lord asleep until the crosses are placed on the boss room's altars.
- **AddNotification.** HoH2's is a stub that logs an error. The import maps it to
  `HoH1AddNotification`, which shows the text through HoH2's announcer, with no icon
  (the town-unlock notices).

## HoH1 traps, Confusion and teleporters in HoH2 runs

HoH2 runs and the campaign floors get three HoH1 mechanics, built from HoH2 units
(`Traps.as`, `Confusion.as`, `Teleporters.as`). They are placed by the dungeon
generator: `Traps::Install` appends one `HWPTrapSpawn` generation command to every
indoor `DungeonGenerator` (outdoor `ForestBrush` floors are skipped) and the command
places prefab set `hwp_traps` (`tweak/hwp/campaign_prefabs.sval`,
`prefabs/hwp/traps/*.pfb`: 3x3 walkable-floor patterns, a wall cell and three floor
cells for the wall shooters) then one `hwp_teleporters` pad, host side like every
prefab. The log says `traps: theme T (group): family weight, ...` (the kinds this floor
can roll), `traps: placed N/M on a WxH floor (C floor cells, density D%, mission X)` and
then `traps: kinds plate_spikes_1 3, shooter_arrow_s 1, ...`.

The traps go on one map, not everywhere (issue #30): the floors of the HoH2 mission set
by `campaign.trap_map` (the Crypt by default: its crypt and temple floors suit them),
plus the Forsaken Tower's floors, HoH1's own trap tower, always. `campaign.trap_map` 4
("Every map") puts them on every indoor floor as before. On other maps the log line ends
`not a trap map: campaign.trap_map is crypt`. The teleporter pad still goes on every
indoor floor.

Each trap is rolled on its own (`PlacePrefabs(set, 1, 1.0, 1)` once per trap): one
call for all of them let vanilla's `PrefabPlacement` fill the floor with whichever type
it rolled first, up to its type-min-limit, and `spikes_1` had no `max-num`, so a floor
was often nothing but spike floors. Now a floor gets a mix, each type within its
`max-num` (2 to 6).

**All of HoH1's traps (issue #37).** HoH1's traps are a few families of unit that its
level scripts switch on and off; HoH2's generated floors have no level scripts, so one
behaviour, `HWPTrap` (`scripts/HWP/Campaign/TrapBehavior.as`, a `DangerAreaBehavior`),
is the script: off, then (on a timer, or when a player comes within `sense` px) a
**warn** scene, then on (its effects every `freq` ms in `radius` px, or once; projectiles
from `shoot`), then off again, re-armed, or spent. Every kind telegraphs before it hurts
(issue #38): HoH2's red area warning on a plate for a second, a glyph lighting up, a
stalactite's growing shadow while it falls. Every machine runs every trap by itself, as
vanilla floor traps do (an effect only sticks to a player on that player's machine and to
an enemy on the host; the projectiles are local units), so nothing goes over the network.
The kinds are unit files on HoH2 art written by `tools/make_hwp_traps.py` (`--check` in
the tests), with HoH2's own trap numbers where HoH2 has the trap and HoH1's otherwise.

Which kinds a floor gets is the kind table in `Traps.as` (`WEIGHTS`): each family's
weight per theme group, from the floor's `DungeonBrush` theme: cave (`cave_*`), crypt
(crypt, temple), barracks (barracks, keep), halls (courts, dark halls), dungeon (dungeon,
prison), other. 0 means never on that theme (stalactites only in caves, no shooters in
caves, drain plates and curse glyphs in crypts and halls), as HoH1's acts had them. A
family's weight is shared by its prefabs (the three facings of a shooter come up as often
together as one plate).

| Trap | Unit | Numbers | Themes |
|---|---|---|---|
| Spike plate, plate row | `hwp_plate_spikes.unit` (vanilla spike art) | 2.5 s down, 1 s warning, 1.5 s up; 25 physical + 10% current health every 0.5 s | all, few in caves |
| Pressure spikes | `hwp_pressure_spikes.unit` (vanilla pressure plate) | stepped on: click, 0.5 s warning, 1.2 s up, 20% current health a tick | all |
| Flame jet | vanilla `doodads/traps/floors/floor_fire.unit` (proximity) | HoH2's | not caves |
| Poison plate | `hwp_plate_poison.unit` | 3 s off, 1 s warning, 2 s on: 8 poison a tick + `hwp_trap_poison` (4 s, 16 poison/s, 70% speed: HoH1's poison_strong) | caves, dungeons |
| Drain plate | `hwp_plate_drain.unit` (vanilla curse floor) | 5% of max mana a tick + `hwp_trap_darkness` (2.5 s) | crypts, halls |
| Frost plate | `hwp_plate_frost.unit` | 6 ice + HoH2's `slow_area` every 0.25 s (HoH1's freezing_short) | caves |
| Confusion plate | `hwp_plate_confusion.unit` | `hwp_trap_confusion` (1 s) every 0.5 s while it glows | halls, crypts |
| Bomb glyph | `hwp_glyph_bomb.unit` (`TripMine`, shows at 48 px, triggers at 24, 1.1 s fuse, fire + lightning blast, re-arms after 8 s) | | all |
| Dart glyph | `hwp_glyph_dart.unit` (fan of 8 vanilla arrows after 0.2 s, re-arms after 5 s) | | not caves |
| Confusion glyph | `hwp_glyph_confusion.unit` (1 s Confused on everyone in 40 px) | | crypts, halls |
| Frost glyph | `hwp_glyph_frost.unit` | within 20 px: 1 s warning, burst 32 px: 20 ice + 10%, frozen 1 s; 6 s re-arm | caves, crypts, halls |
| Curse glyph | vanilla `doodads/traps/mines/glyph_shadow.unit` | HoH2's | halls, crypts |
| Arrow / poison arrow / fire ball / blade shooter | `hwp_shooter_{arrow,poison,fire,blade}_{s,e,w}.unit` (vanilla wall shooter art, on the wall) | with a player within 200 px: one of HoH2's trap projectiles every 1.5 / 2 / 2.5 / 2 s | barracks, dungeons, crypts |
| Arrow turret | `hwp_turret_arrows.unit` (vanilla turret art) | sees a player within 220 px: 0.5 s, turns, fan of 3 arrows (30 degrees), every 2.5 s | barracks, dungeons |
| Flame gargoyle | vanilla `haunted_gargoyle_s.unit` | HoH2's | crypts, halls |
| Stalactite | `hwp_dropper_stalactite.unit` | within 20 px: falls 0.9 s with a growing shadow, 20 physical + 20% in 18 px; regrows in 5 s | caves only |
| Falling bricks | `hwp_crusher_bricks.unit` | within 40 px: dust and warning 1 s, 30 physical + 20% in 16 px; 3 s | not caves |
| Bear trap | `hwp_bear_trap.unit` (the ranger's trap art) | snaps within 10 px: 30 physical, immobilized 2 s; stays sprung | caves, dungeons, barracks |

Left out, with reasons: HoH1's rolling boulders and beam nodes need a track or a pair of
nodes laid out by hand (a generated floor has no such layout), the pillar spikes are the
pressure spikes' art in HoH1's tileset, and the explosive barrels are breakables, not
traps (HoH2 has its own).

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
| `campaign.traps` | true | HoH1 traps on the trap map's and the Forsaken Tower's indoor floors |
| `campaign.trap_map` | 0 | the map with traps: 0 Crypt, 1 Bandit Keep, 2 Dark Citadel, 3 Spider Caves, 4 every map |
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

## Settings

On the HammerwatchPlus tab of the player menu (`hwp set <key> <value>`; `module.json`
`config`). All host-authoritative.

- `campaign.enabled` (on): the switch. Off: the town portal is not placed (next town load),
  generated floors get no traps or teleporter (next level), pads already placed do nothing
  and nothing confuses. A tower run already under way plays on, and the Dark Citadel keeps
  its extra floors (`Citadel::Fix`): changing them under a run would move its floors.
- `campaign.portal_both`, `campaign.traps`, `campaign.trap_map`, `campaign.trap_density`, `campaign.teleporters`,
  `campaign.confusion`, `campaign.confusion_eye_chance` (the table above). Not on the page:
  `campaign.portal_x/y` (`hwp campaign here`).

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
   `python -m gamelab run fix-campaign-portal-version` (hwplib + campaign, about 3 min)
   checks the portal version in the log and the dialog, `hwp campaign citadel` =
   dark_halls_1, dark_halls_2, hwp_battlements_1, hwp_battlements_2, dark_halls_boss,
   and the Confusion cheat (buff on, right moves left, expiry, glyph applies it).
   Every HoH1 tower floor and boss: `tower-floors` and `tower-bosses`, and the playthrough
   `tower-run` ("HoH1 tower" above).
8. `python -m gamelab run fix-campaign-battlements` (about 3 min): `gl mission
   dark_citadel <index of hwp_battlements_1>` loads `hoh1/levels/battlements_1.lvl`
   with no script exception, screenshot `battlements-1`.
9. `python -m gamelab run fix-campaign-traps` (about 4 min): the indoor Dark Citadel
   floor (`gl mission dark_citadel 2`, retried on another seed) logs `traps: placed N/M`,
   `gl unitsof` finds the trap units, standing on spikes / a bomb blast costs health,
   the generator's teleporter pad moves the player to the logged destination and to the
   same spot on a second use; screenshot `traps-floor`. Without the import the same
   scenario still passes (traps and pads need no HoH1 file; the HoH1 teleport effect
   falls back to the vanilla smoke puff). It sets `campaign.trap_map` 2 (Dark Citadel)
   first. The second use is checked by the logged destination: the player can be
   pushed a few px in the second after landing.
10. `python -m gamelab run fix-campaign-trap-map` (about 30 s): Bandit Keep floor 0 has
   no traps (`not a trap map`) but a teleporter; Crypt floor 0 and Forsaken Tower floor 0
   have traps, a mix (`traps: kinds`, at least 3 kinds, none over its max-num);
   `hwp set campaign.trap_map 4` and the Bandit Keep has them too.
7. Play each HoH1 boss once, solo and in co-op: the Stone Guardian's ground
   spikes, the Warden's whirlwind and bombs, the councilors teleporting
   between nodes (client sees the same node), the Watcher's wisps circling
   each player, the Vampire Lord roaming / transforming and his bats,
   Thundersnow on top of the Battlements.
