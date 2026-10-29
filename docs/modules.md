# Module conventions

Each module is a folder `mods/<id>/` that is itself a valid unpacked HoH2
mod (`info.xml` at the root). Players get them as Steam Workshop packages, not one by one
(see Packages below).

```
mods/<id>/
  info.xml                      name / author / description
  module.json                   build metadata: library, requires, overrides, exclude, local, local_only
  README.md                     the feature spec: what it does, how to test it
  scripts/HWP/<Feature>/*.as    all code under scripts/HWP/ to avoid base collisions
  res/language/english/hwp_<id>.lang
  gui/hwp_<id>_*.gui
  tweak/hwp/<id>_*.sval
  actors/..., items/..., prefabs/...   new units/data, never same path as a base file
```

## Packages

There is no core mod. The shared code is a library in the repo, split into parts, and every
package carries a copy of the parts its mods need:

| Library part | Holds | Carried by |
|---|---|---|
| `hwplib` | the plumbing (log, net, save data, settings, the `hwp` command and cheats, town units, the wares market, materials sections, gear slots, item actions, the Plus tab, targeting and aim hooks, custom stats, room carving, the spawner), the generator safety net, the bag size (`HWP::Bag`, no shop), the Luck views (`HWP::LuckView`), `character.gui`, `playermenu.gui`, `Modifications.as`, `messages.net`, the theme overrides | every package |
| `hwplib-luck` | the Luck stat (`HWP::Luck`, `LuckFloors.as`, the `RewardSpot.as` and `BlueprintBank.as` overrides, the Luck gear affixes, trinket and buff) | packages whose mods read Luck: Co-op, Keys, Dungeon, Town |
| `hwplib-classui` | the create-character class list (`HWP::HideClass`, the `CreateCharacterClass.as` override) and the Subclass Picker's skill row (`HWP::SubclassPick`) | Firearms, Specs, Classes |

A library part has `"library": true` in `module.json` and is never a package of its own.
A shared module (`"shared": true`) is a feature module listed in one package that mods of
other packages may require, and so carry: `petrooms` is Quality of Life's, and Pets requires it
(pets keep out of puzzle and trap rooms with either package). The settings page lists it under
each package that carries it (`make_config.py`, `shared` in `config.sval`) and shows it once,
under the first package loaded by a module of its own.
A mod `requires` the parts it uses (and only mods of its own package); `tools/build.py` packs
`dist/HWP-<package>.bin` from the package's mods plus everything they require, transitively,
and stops when a package would need a mod of another package. `packages.json` (repo root)
lists the packages, their Workshop names and descriptions, the all-in-one pack
(`dist/HammerwatchPlus-All.bin`, every package) and the bench (modules never shipped).

Why copies work: the game keeps one file per path across all enabled mods, the first mod's,
and two mods shipping the same path load fine; the engine only logs one
`Resource name hash conflict` ERR per shared path (`docs/RE_NOTES.md`, "2026-10-26: one path,
two mods"; pair scenarios allow that line). Every package of one build carries byte-identical library files, so whichever
copy wins is the same code. Two rules keep packages of different builds working together:

- **The library only grows.** Never remove or change the signature of a library function,
  class, interface method or lang key a released package may call; add new ones beside it.
- **Publish every package together** from one build. Each package carries the library stamp
  (`HWP::LIB_STAMP`, a hash of all library parts, generated) and a check module that logs
  `[HWP:core] package HWP-<id>, library <stamp>`. When the loaded stamp is another build's,
  it logs an error and calls `HWP::Packages::Mismatch("HWP-<id>")`, and the player gets one
  chat line in town (`hwp.packages.mismatch`, `pkg-mismatch`).

The rule "only grows" covers an older package running on a newer library. The reverse can
still break: when an older package's library copy wins, a newer package that calls something
added since will not compile, and with it nothing compiles (`docs/GAME_UPDATES.md`). So
`HWP::Packages::Mismatch(const string &in)` and `HWP::LIB_STAMP` are frozen from the first
release on, since every generated check module calls them. Code that can run on an older
library goes through what that library already had. With the all-in-one pack and single
packages of the same build enabled together, every path is the same file and every check
passes (`pkg-all-every`).

**Heroes of Hammerwatch 1 content** is the player's own: `tools/import_hoh1.py` cuts it into
paths a module lists under `local` (or `local_overlay`), and only `build.py --with-local`
packs them, never a release build (`tests/test_release_files.py` fails on any ignored file
that a release package would carry). No package needs HoH1. A module with HoH1 features
calls `HWP::HoH1::Report(mod, present, ".lang.key")` after it has looked, where the key
names what the player gets instead. hwplib tells the player once per save and set
(`hwp.hoh1.missing`, the setting `hoh1.told`), and `hwp hoh1` lists the features
(`hoh1-standins`, `hoh1-installed`). Scenarios that read the local content are marked
`"needs_hoh1": true`: `tools/make_package_scenarios.py` keeps them out of `pkgfeat/`, and on a machine
without the HoH1 import their mods read, `gamelab run` exits 7 (SKIPPED) and a suite skips them.

A part reaches what another part holds only through an interface the other registers (the
character screen's Luck cell asks `HWP::LuckView`, which `hwplib-luck` fills; without it the
cell hides). GameLab scenarios list `packages` to load the built .bin files
(`pkg-<id>`, `pkg-all`, `pkg-pair-*`, written by `tools/make_package_scenarios.py`); a
scenario's `mods` get their required parts enabled with them.

## Rules

1. **Never shadow a base file unless declared.** A file at the same path as a
   base-game file replaces it wholesale. If a module must do that, list the
   path under `overrides` in `module.json`, keep a pristine copy next to it as
   `<path>.orig`, and `tools/build.py --check` will flag when a game update
   changes the original. One owner per overridden file across all modules.
2. **Prefer hooks, modules and class swaps** (module.json `class_swaps`; info.xml classmaps are ignored by the engine). See `docs/hooks.md`.
3. **Server authority.** Anything that changes shared state (gold, items,
   spawns) runs on the server (`Network::IsServer()`); clients request.
   Netsynced units can only be produced by the server.
4. **Save data** goes under the `hwp` key of the player or town record via the
   `PlayerRecordSave/Load` and `TownRecordSave/Load` hooks, so vanilla saves
   stay valid with the mod removed.
5. **Namespaces.** Script code lives in `namespace HWP` (or `HWP::<Feature>`);
   hooks live in `namespace HWP<Feature>` because the hook name must match the
   function name, not the namespace.
6. **Logging** goes through `HWP::Log("<module>", msg)` so lines are greppable
   as `[HWP:<module>]`.
7. **Language strings** use keys prefixed `hwp.<module>.`.
8. **IDs.** HashString ids, char flags and material keys are prefixed `hwp_`.
9. **Per-level setup** goes in `Start(StartMode)` of `HWP::ModuleStart`
   (`class X : Module, HWP::ModuleStart`), never in `Module::Load`: the engine
   skips `Load` whenever a level starts without a save (StartMode StartGame,
   e.g. a new profile's first town). hwplib's `GameModeStart` hook calls `Start`
   on every gameplay level, after the host spawned its players. Script
   globals reset with every level; what must happen before `PostStart` (or
   while the scene loads) goes in the module constructor, which runs once per
   level. State that must survive a level change lives in the player / town
   record (`HWP::SaveData`) or `GlobalCache`.
10. **Guarded entry points.** A module's `UpdateFrame`, `PreRenderFrame`, `RenderFrame`,
   `RenderWidgets` and `Load` run their body as `Guarded<Name>` behind an `HWP::Guard`
   (hwplib `Guard.as`), so a script error turns that one entry point off instead of
   stopping the game's frame. Write the method as usual and run
   `python tools/guard_modules.py` to wrap it; `tests/test_guard.py` fails while one is
   unwrapped. Edit the `Guarded<Name>` body afterwards, never the wrapper.
   (`docs/GAME_UPDATES.md`.)

## Settings

Every shipped module has a `config` block in its `module.json`: its row on the
HammerwatchPlus tab of the player menu (the Plus tab), its on/off switch and the settings a
player may change. The schema is the docstring of `tools/make_config.py`, which checks each
block against the code (a key's type and default must be how the module reads it) and writes
`mods/hwplib/tweak/hwp/config.sval`, the package titles, every module's own
`res/language/english/hwp_<id>_cfg.lang` and `docs/generated/settings.md`. Run it after a
change; `--check` fails when the files are stale (`tests/test_make_config.py`).

- **The switch** (`toggle`) is a bool setting read as `HWP::Settings::GetBool("<key>", true)`.
  Off stops what the player sees: hooks and `UpdateFrame` return early, data the module changed
  goes back, units it places are not placed. It never skips `Save`/`Load` or deletes saved
  data, so turning it back on finds everything as it was. A module that can only change on a
  level load says `"applies": "level"`; one that is only data has `"toggle": null` and says why
  in `always_on`. A class module hides its class at character creation (`HWP::HideClass`,
  `HWP::ShowClass`); characters made with it keep playing.
- **Scope.** `host` settings (the default: anything that changes gameplay) are host-synced by
  `HWP::Config` itself; a client sees the host's value and cannot change it. `local` ones are
  each player's (display, keys).
- **The page** (`HWPOptionsTab`, hwplib `Options.as`, `gui/hwp/options.gui`): the search
  field, then the top section (`packages.json` `settings_top`: key binds and accessibility),
  then one collapsible row per package with its loaded modules and their settings. A module
  shows when its generated lang file is loaded (`HWP::Config::Present`), so a package lists
  only what it carries. The search is fuzzy over titles (letters in order) and finds words in a
  row's text and value too, and opens the packages it finds rows in. Clicking a value cycles it
  and calls `HWP::Commands::NotifySettingChanged`, as `hwp set` does. Key binds and presets are
  `HWP::Options::Option`s a module registers in its constructor (`{"option": "<id>"}`).
- **Row ids** for GameLab: `hwp-opt-<option>`, `hwp-cfg-<key>`, `hwp-mod-<module>`,
  `hwp-pkg-<package>` (a second copy of a row gets `-2`). Funcs: `hwp-opt <id>`,
  `hwp-cfg <key>`, `hwp-mod <module>`, `hwp-pkg <package>` (toggles), `hwp-open` /
  `hwp-close <package>`. The tab logs `[HWP:options] <key> -> <value>`.

## Testing a module

GameLab replaced `dev_link.py` / `dev_check.py` (see README.md and `docs/MODDING_NOTES.md`).
A module is tested by a scenario under `gamelab/scenarios/`, run hidden and muted:

```
python -m gamelab run <scenario> --mode lab
```

- The fixture recipe (`gamelab/fixtures/<name>.json`) lists the mods to enable in
  `binary_edits.enable_mods`.
  - `gamelab/hps.py` writes them into the lab save as `HashString(id)`. No first-boot
    learning is needed: the hash is computed (`python gamelab/hps.py hash <id>`).
  - The lab game dir links every mod in `environments.json` `gamelab.mods`. A module
    joins by being added there and to a fixture.
- The run fails on a non-zero game exit or a failed assertion.
  - Scenario steps can assert on `[GL]` probe replies.
  - Script errors stay in `logs/pass<n>.HWR2.exe.log`; asserting on them is not
    automated yet.
- The old `dev_check --level` floor loader is replaced by the `gamelab-hands` verb
  `mission <id> [floor]`. `mods/devtools` was deleted at P7 (2026-10-17).
- Multiplayer behaviour still needs the manual checklist in the module's README, solo
  and in a 2-player lobby.

**Local content.** A module may hold files generated from the player's own
HoH1 install (`tools/import_hoh1.py`): they are listed under `local` in
`module.json`, gitignored, and `build.py` skips them unless `--with-local`
(for a personal build; never upload one). `import_hoh1.py campaign` deletes
and rebuilds its output folder on every run, but only when the folder carries
its `.hwp-generated` marker (or with `--force`).

A `local_overlay` prefix (`module.json`, e.g. the classes module's
`hoh1art/`) is local content that replaces committed placeholder files:
with `--with-local`, `hoh1art/players/hwp/thief/icons.png` is packed as
`players/hwp/thief/icons.png` instead of the committed placeholder. Without
it (and in unpacked dev links) the placeholders are used.

**Beta-only content.** A `local_only` module with `beta_into: "<host>"` (the
`holylocal` module, the Priest without the Celestial Ruins DLC, into `hwplib`)
is never built on its own: `build.py --beta` (`deploy.py modded-prod --beta`)
packs its files into every package that carries the host, so a beta tester enables only the
usual packages, and a build without `--beta` never carries them. Verified by
`mod-holylocal-priest` (the Priest offered, selected and created in character
creation with holylocal) and `mod-holylocal-priest-control` (no Priest without).

The main menu loads the town level and constructs every `Modules::Module` subclass,
but only gameplay modes tick `UpdateFrame` (measured 2026-10-17, `docs/RE_NOTES.md`).
Put boot-time self-checks in the module constructor; a `log_has` step sees them.
Anything that needs a player needs the manual checklist in the module's README, solo and
in a 2-player lobby for anything networked.

## Modules

| id | Feature | Notes |
|---|---|---|
| `hwplib` | library (see Packages): the `hwp` console command (and `hwp` copies of the vanilla cheats), host-synced settings (`HWP::Settings::Sync(prefix)`), wares registry (`HWP::Market`, `hwp wares`, `hwp sell`; a second currency a module registers with `SetCurrency`), two untitled materials-tab sections modules fill (`HWP::Materials::Title` / `Register(section, order, id, material)`), settings-backed town doodads (`HWP::Town::Placeable`), pack spawner (`HWP::Spawner`), level generation safety net (`HWPOutdoorGenerator`), the local player's targeting helper with skill input and aim hooks (`HWPTargetingHelper` swapped into `Player.m_targetHelper`, `HWP::TargetHelper`, `HWP::Aim`), the bag size (`HWP::Bag`) and the Luck views (`HWP::LuckView`) | overrides `gui/playermenu/character.gui`, `playermenu.gui`, `GUI/PlayerMenu/Modifications.as` (the Luck row through `HWP::LuckView`, and `AppendSkillDesc` filling a skill description's `%param%` tokens from the level 1 values when there is no player actor), `system/messages.net` and the five outdoor `tweak/missions/themes_*` files (one line each: `gen-class`) |
| `hwplib-luck` | library: the Luck stat (`HWP::Luck`), its floor effects (`LuckFloors.as`) | overrides `WorldScript/RewardSpot.as`, `BlueprintBank.as`; `tweak/hwp/*_luck.sval`; `hwp luck` |
| `hwplib-classui` | library: classes left out of the create-character list (`HWP::HideClass`), the class list fitted to 7, the Subclass Picker skill row by skill type (`HWP::SubclassPick`, the open vanilla window patched in place) | overrides `GUI/CreateCharacter/CreateCharacterClass.as` |
| `mapicons` | a dye-pot marker on the minimap over every dye bucket of a floor | `doodads/hwp/map_icon_dye.unit` (the icon is in hwplib's `gui/hwp/map_icons.png`); setting `mapicons.dyes` |
| `gambler` | Higher/Lower card game NPC, wares buyer, gear reroll (2000 g x ilvl, `Equipment::Generator::ModifyItem`), bet tokens (`Tokens.as`: per character `bet_tokens`, the market's currency, `hwp tokens` cheat) in the Supplies section | |
| `droptrade` | drop equipment for friends (Drop hint/button + raw Q key next to vanilla Destroy); the use key picks up a floor item before an NPC (`PickupFirst.as`: the local usables re-sorted every frame) | overrides `GUI/PlayerMenu/Character.as`, `GUI/Widgets/EquipmentItemWidget.as` |
| `laststats` | last run's stats on a town notice board: every player on one page, bars per stat, search field | `hwp laststats [sample|board]` |
| `deathrecap` | death recap panel + chat line; boss-fight recap (each machine's hits on boss-tagged actors by skill, one fight per encounter: while a hit boss unit lives or a HUD boss bar is up; gathered by the host at the end, `bossrecap.report/show`, `gui/hwp_bossrecap.gui`) | hooks `PlayerDamageTaken`, `HUDConstructor`; `hwp bossrecap` |
| `bufftips` | hover tooltips on the HUD buff icons (name, description, seconds left) | hooks `HUDConstructor`; hit-tests `HUDBuffs` icons itself |
| `legacy` | Title Bonuses: one buff listing every hero title bonus; Guild Hall > Titles lists every class | local husk buff kept up by script; rebuilds `GuildHallHeroTitlesTab` in place; `hwp legacy` |
| `pets` | pet XP + skill tree, feeding bowl, per-pet pickup toggles, HoH1 pets in the Pet Shop; requires `petrooms` (its pet classes are `HWP::PetWait::Owned`) | class swaps `MiniPetWalking`/`MiniPetFlying`/`EquipmentDyerShopContent`; `tools/import_hoh1.py pets`, `tools/make_pet_dyes.py`; `hwp pet` |
| `architect` | everyone can pick + pay architect buffs, host share split, 7 HoH1 challenges (free picks, % off, capped at free) | overrides `Missions/MissionArchitect.as` |
| `chatlinks` | linked items as persistent chat lines, `hwp link` | |
| `colors` | accessibility projectile tints; preset picker in the player menu's Plus tab; per-player colours on the minimap and overlay map with far-player names (`PlayerColors.as`, default and Okabe-Ito palettes) | class_swaps the three projectile classes (184 generated units); `hwp colors`, `hwp playercolors` |
| `goldworth` | gold pickups look like what they are worth (15 coin and pile scenes, bronze 1+, silver 25+, gold 200+) | data only: overrides `items/materials/gold.unit` (`gold.unit.orig` for `build.py --check`); scenario `fix-gold-sprites` |
| `orbwarn` | the orb picker says which orbs a pick closes (`blocked-by-skills`) | no hook: the open `GiveSkillSphereMenu` checked each frame, a red row under each pick's description |
| `mmhmm` | Mm-hmm! hats: 25 % of rare and epic hats play the Material Trader's voice for everyone on the wearer's crits, revives (given or received), well drinks, secret rooms, completed trinket sets, last orbs of multi-orb trees and Ace chests | modifier `hwp_mod_mmhmm` added on top of the rolled ones (`tweak/hwp/modifiers_mmhmm.sval`, crit `TriggerEffect`); class swap `PlayerCorpse` -> `HWPMmHmmCorpse`; other moments polled (`Moments.as`); `mmhmm.say` request/event; reads keys' GlobalCache `hwp_keys_aces_opened`; `hwp mmhmm [give]` |
| `groupcombo` | party-wide combo bonus + unity invulnerability; the combo orb drop from breakables | `tweak/hwp/buffs_groupcombo.sval`, `items/hwp/combo_orb.unit`, settings `groupcombo.orb.permille` (1) and `groupcombo.orb.max_permille` (10) |
| `weaponswap` | second weapon set on a hotkey (rebind in the player menu's Plus tab) | `hwp swap`, `hwp swapkey` |
| `puzzles` | puzzle rooms placed again (one `<biome>_puzzle` SpawnPrefabSet per dungeon generator, `puzzles.room_chance` %, default 60; forced onto the outskirts with a carved corridor when no spot matches; none on outdoor floors), HoH1 Constellation in the big rooms' picks (`puzzles.constellation` weight, default 10) | `HWP::Puzzles::PuzzleRoomSpawn : SpawnPrefabSet` added to `MissionDef` generators in the module ctor; overrides `WorldScript/Prefabs/PrefabPicker.as`; prefab generated by `tools/make_constellation.py` |
| `objectives` | floor objectives on generated indoor floors: a locked loot vault (`prefabs/hwp/objectives/vault_s.pfb`, carved into an outskirts wall block with a corridor, `doodads/hwp/objective_door.unit`) opened by a lever far away, the way down sealed (`SetEnabled(false)` on every `LevelExitArea*`/`LevelExit*` world script, retried 3 s on the keep) until the exit lever; HUD lines; `objectives.opened/state` sync | `HWPObjectiveSpawn : DungeonGenerationCommands` added after each generator's shrine set; settings `objectives.vaults` (0-2), `objectives.exit`; `hwp objectives [open]`; requires `hwplib` |
| `stash` | Sort button on the town stash (class > slot > weapon family > ilvl) | overrides `gui/player_stash/player_stash.gui`; widget producer `hwp-stash-sort` |
| `keys` | every chest locked (key per tier), ace chests, key drops, exit guard General Merchant (keys, bag slots, Trinkets tab: 6 trinkets packed for the next run), legendaries, "the chest was trapped" announce to everyone (`Trapped.as`, `tweak/hwp/announce_keys.sval`), alt-art chests by area (`ChestArt.as`) | class swap `Chest` -> `HWPChest`, `scene_art` `tweak/hwp/chest_art.sval` (art scenes in the generated chest units); `tweak/hwp/legendaries.sval`; `hwp keys`, `hwp chestart` |
| `firearms` | Firearms Specialist class (3 subclasses, rifles) | pure data via `PlayerClass`/`ItemSkillDef`/`BaseItem` loaders; `hwp firearms` |
| `fishing` | town fishing minigame, in-run fishing holes | `tweak/hwp/loot_fishing.sval`; wares via hwplib `HWP::Market` (fish sell for the gambler's tokens, or gold without it); bait in materials section a; `hwp fishing` |
| `farming` | plots on the town's onion / wheat field grooves, watering can + farm well (watered = 2x growth), farmer shop (can, upgrades, seeds), seeds back on harvest, Holy Herb strains + next-run buffs | host-owned state in the TownRecord, `farm.sync`; overrides `npc_misc_farmer_man.unit`; `tweak/hwp/buffs_herbs.sval`; `hwp farm`, `hwp smoke` |
| `weapons` | 12 new weapons via `Equipment::BaseItem::LoadMultiple` | `tweak/hwp/equipment_weapons_hwp.sval`; `hwp weapons` |
| `strongbox` | strongbox chests: pack spawns on open, loot on clear | `HWPStrongbox : Chest`, `HWP::Spawner` (hwplib); `tweak/hwp/loot_strongbox.sval`; `hwp strongbox` |
| `abyss` | abyss cracks: waves + elites by party size, reward on clear by floor diff-level (3 tiers) | `HWP::Spawner`; `tweak/hwp/loot_abyss.sval`; `hwp abyss` |
| `valuables` | valuables pay `valuables.gold_mult` (2) x their vanilla gold | sets `Item::Valuable.m_price` from the kept vanilla price; `hwp valuables [drop <id>]` |
| `trinkets` | NG+ scaling of flat trinket bonuses (the Trinket Map verdicts); 37 HoH1 trinkets, 8 new sets, bigger Emblems of Hermes and Apothecary sets, Trader's Coin shop discount (`HoH1.as`) | class swap `TrinketShopShopContent` -> `HWPTrinketShopContent`; `tweak/hwp/trinkets_hoh1.sval`, `buffs_trinkets_hoh1.sval`, `trinket_sets_hoh1.sval` (cumulative tiers, merge off), `trinket_sets_vanilla.sval` (patched into `Item::TrinketSet` at load); `hwp trinkets hoh1`, `hwp trinkets set <id>`; NG+ scaling: rebuilds `Item::Trinket.m_modifiers`/`m_modifiers2` from a patched copy of the trinket's sval dict when `int(g_ngp + 0.5)` changes (`LoadIModifiers`, SyncVerb::Trinket), patched `m_desc1`/`m_desc2`; proc damage in unit files scaled by an `intensity-mul` EffectListMod first in the trigger's effects; Arctic Step through `HWPTrinketNGBuff : Modifiers::Buff`; setting `trinkets.ngp_scaling`; `hwp trinkets [show <id> \| ng <n>]` |
| `tavern` | tavern levels 4-6 (1/4, 2/4, 3/5 food/drink slots) | overrides `tweak/town/buildings/tavern.sval`, `scripts/Missions/MissionFoods.as` (food list, save `foods` array) |
| `waygates` | Way Gates: a gate in the town square and one per built building, menu of every gate, teleport | no overrides; host spawns `doodads/hwp/hwp_waygate.unit` (`HWPLocalNPC`, interact `HWPWayGateShop`) 800 ms after town load and again after a town reload; building cells from the base segment's placed prefabs (the `SpawnTown` walk); `UnitTeleported`; settings `waygates.enabled`, `waygates.square_x/_y`; `hwp waygates [go <n>]` |
| `roulette` | lobby-wide single-zero roulette (157 bets, true odds, payout raised by Luck + gold find), wheel on a tavern hall table | no overrides; host runs the rounds (`roulette.state` broadcast, `roulette.stake`/`hello`/`spin` requests) and spawns `doodads/hwp/hwp_roulette_wheel.unit` (`HWPLocalNPC`, interact `HWPRouletteShop`) on the hall table, every machine bares that table (`SetUnitScene("default")`); widgets `hwp-roulette-board`, `hwp-roulette-strip`; setting `roulette.max_stake`; `hwp roulette [bet/clear/spin]` |
| `autoaim` | auto aim / auto fire / auto skill for TargetAOE skills; controller by default, mouse optional | no overrides; hwplib aim hooks `HWP::Aim::OnAdjust` (reticle) and `OnPreUpdate` (fires via `HWP::Aim::FireTargeted`) from `HWPTargetingHelper`; Plus tab rows `autoaim`, `aimcone`, `autofire`, `autoskill` (hwplib `gui/hwp/options.gui`); settings `autoaim.*`; `hwp autoaim` |
| `maps` | 3 extra `equipment_map` missions | `tweak/hwp/missions/*.sval` (`MissionDef::LoadSingle`); `hwp maps` |
| `mercenary` | HoH1 mercenary mode: `hwp merc enlist` (fresh level-1 character, a level-20 veteran of the class; starts at `mercenary.start_level`, default 10), HoH1 prestige (floors, boss floors, NG+²) and ranks (+15% gold and XP per rank), permadeath (on death, or on a failed run with `mercenary.revivable`), ledger of the fallen | `PlayerRecordRefreshModifiers` hook adds `Modifiers::MaterialGain` + `Modifiers::Experience`; fallen check in `ModuleStart`/`UpdateFrame`; picker via `GlobalCache main_pick_character`; `merc.fallen`/`merc.boss` host relays |
| `summons` | Crusaders persist across floors (snapshot `SaveUnit()`, re-produce on `GameModeSpawnPlayer`) | hooks `GameModeSpawnPlayer`; settings `summons.enabled/all`; `hwp summons` |
| `petrooms` | pets keep out of puzzle and trap rooms (one puzzle unit or three trap spots within `petwait.radius`; units within 12 px are one spot): the pet walks back along the owner's trail to the last clear point and waits; a pet inside a room walks out and waits until the owner moves on; a pet rejoining after a wait may cross a room for 5 s. `petwait.debug` logs each change. Shared module (`shared: true`): listed in Quality of Life, carried by Pets too | `HWP::PetWait::Watcher` (PetWait.as); vanilla pets driven by the module (PetRooms.as: the owner's own pet loses `m_owner` between frames while parked, so its Update returns at once); settings `petwait.enabled/radius` |
| `campaign` | Forsaken Tower mission (set `hwp_campaign`, 18 levels) + town portal doodad on the chapel courtyard campfire; the portal offers the HoH1 version alone when imported (`campaign.portal_both`); Dark Citadel = two Dark Halls + two Battlements (`Citadel.as`); HoH1 traps on generated floors (`Traps.as`, `HWPTrapSpawn` generator command, `prefabs/hwp/traps/*.pfb`, `campaign.traps`, `campaign.trap_density`); one teleporter pad per floor (`Teleporters.as`, `campaign.teleporters`); Dark Halls eyes and the confusion glyph confuse (`Confusion.as`) | `tweak/hwp/missions/missions_hwp_forsaken_tower.sval`; portal interact = vanilla `MissionShopContent`; settings `campaign.enabled/portal_x/portal_y`; `hwp campaign [here|reset|citadel|teleporter|confuse]`; overrides `prefabs/town/buildings/pyre/pyre_tier_0.pfb` (campfire as a unit); `tools/import_hoh1.py levels` (HoH1 level decode + gap report); `tools/import_hoh1.py campaign` (optional second mission on the real HoH1 boss / Battlements levels, local content; HoH1 classes in `scripts/HWP/Campaign/HoH1/`) |
| `devarena` | dev only, GameLab env: the Dev Arena overlay (F1 dock; Tune tab: per-level cells, growth curves, FEEL fields, A/B versions with undo, pins; Loadout tab: 74 presets applied in place, inline edits, variants, favorites; Arena tab: cheats, brush placement, encounters, reset/reload, state through the town save; Golem tab: F4 room, pulls with a per-skill breakdown; Bench tab: A/B pulls with a noise verdict and a CSV; Compose tab: new skills from existing actions; [Relaunch] for REFS edits; an auto-tuner that proposes values; spec clone to `mods/spec-*`) | `docs/devarena/SPEC.md`; override file `tweak/hwp/devarena_overrides.sval` via `tools/devarena/overrides.py`; presets `tweak/hwp/devarena_presets.sval` via `tools/make_presets.py`; hooks `PlayerDamagedActor`, `TownRecordSave`/`TownRecordLoad`; `da-*` verbs |
| `devtools` | dev only, never packaged: the old floor loader | superseded by `gamelab-hands` `mission` (`mission-enter` run 20261017-140945); deleted 2026-10-17 |
| `wavemode` | Wave Arena survival mission (vanilla `SurvivalMission` module) + town statue, arena rank | `HWPWaveShopContent : MissionSurvivalShopContent`; hooks `PlayerKilledActor`; net `wave.bosskill`/`wave.start`/`wave.awarded`; settings `wave.enabled/rank/statue_x/statue_y`; `hwp wave` |
| `classes` | Thief / Gladiator / Witch Hunter (3 subclasses each, 39 skills), Arena Trident, pyre unit | pure data via `PlayerClass`/`ItemSkillDef`/`BaseItem` loaders; `tweak/hwp/buffs_classes.sval`; `hwp classes`; extra skill keys 4-6 for the specs with more than three actives (`SkillKeys.as` on hwplib's `HWP::TargetHelper` hooks, `HWPSkillKeysHUDPlayer` in the HUD, Plus-tab rows `skill4`-`skill6`, `hwp skillkeys`) |
