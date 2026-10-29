# hwplib

The base of the HammerwatchPlus library. It is not a mod players install: every Workshop
package carries a copy (`packages.json`, `docs/modules.md` Packages), and the game keeps one
copy of each file when several packages are enabled. It adds no gameplay. Two more library
parts sit beside it: `mods/hwplib-luck` (the Luck stat) and `mods/hwplib-classui` (the
create-character class list and the Subclass Picker's skill row).

| File | Provides |
|---|---|
| `scripts/HWP/Core/Log.as` | `HWP::Log(module, msg)` / `HWP::LogError`, `HWP::VERSION` |
| `scripts/HWP/Core/Net.as` | `HWP::Net` request/event bus (`OnRequest`, `OnEvent`, `Request`, `Broadcast`, `Send`) |
| `scripts/HWP/Core/SaveData.as` | `HWP::SaveData::Player/Local/Town/MyTown()` data bags saved under the record's `hwp` key; a bag lives in the record's `userdata`, so it dies with the record |
| `scripts/HWP/Core/Settings.as` | `HWP::Settings::Get*/Set*` local preferences, stored in `g_myTownRecord` (the only town record the game saves; clients only get a copy of the host's `g_currTownRecord`) |
| `scripts/HWP/Core/Commands.as` | `HWP::Commands`: the `hwp` console command. `hwp help`, `hwp version`, `hwp settings`, `hwp get <key>`, `hwp set <key> <value>`; modules add their own with `Register(name, help, handler)` and listen for setting changes with `OnSettingChanged` |
| `scripts/HWP/Core/GearSlots.as` + `gui/playermenu/character.gui` | `HWP::Gear`: extra gear slots in the character screen. The vanilla equipment is a 3x3 grid (main hand, head, off hand / hands, chest, back / rod, feet, can), with the bottom corners and the alt-weapon pair as `hwp-gear-slot` widgets; a module registers a `HWP::Gear::Slot` provider by widget id (`Register`), slots without a provider are hidden. Providers call `Changed()` when what they show changes (a level load does too); the slots reload only then |
| `scripts/HWP/Core/Town.as` | `HWP::Town::Placeable` (a settings-backed town doodad the host spawns; optional `m_locate` finds its spot in this town on every machine, it is placed again after a town rebuild, `Reset()` drops the saved spot), `HWP::Town::ChapelPyreSpot` (the chapel Pyre slot, where the campaign portal and the wave statue stand), `HWP::Town::Kept` (a once-per-load unit to spawn again after a rebuild; `Set(unit)` remembers its producer), `HWP::Town::Ours(u)` (a kept pointer still names a live HWP unit: a rebuild reuses unit ids, so check this before trusting or destroying one), `HWP::Town::PayGold`, and `HWPLocalNPC`, the behaviour of town units every machine spawns for itself (fishing spots, the pirate, farm plots, the well) |
| `scripts/HWP/Core/BagSlots.as` | `HWP::Bag`: bought equipment bag slots, 24 + up to 8 per character (`bag.extra` in the HWP data). The slots are sold by the keys module (`HWP::BagShop`, the exit guard shop and `hwp bag buy`); without it the bag is the vanilla 24. The character screen's `<hwp-equipmentinventory>` draws every slot you can fill. `HWP::Bag::OnEquip(f)` runs `f(record, item)` before a bag click equips the item (firearms uses it to put a pistol in the off hand) |
| `system/messages.net` | base file + `HWPRequest` / `HWPEvent` messages (declared override, see `module.json`) |
| `scripts/HWP/Core/Cheats.as` | `hwp unlockflags`, `material`, `levelup`, `xp`, `statpoints`, `skillpoints`, `equip`, `spawnmaps`, `finishlevel`, `boss`, `killall`, `god`: copies of the vanilla `cht_*` cheats that work in a level (need `e_cheats 1`) |
| `scripts/HWP/Core/Generator.as` | `HWPOutdoorGenerator`: vanilla `OutdoorGenerator` that picks its base level again on every retry and sets aside a base that failed 10 times in a row (see below) |
| `scripts/HWP/Core/Market.as` | `HWP::Market`: wares (crops, herbs, fish) registered by modules, counted from your HWP data and bag items, sold for gold or a second currency a module registers (`Currency`: `Held`, `Add`, `Amount`, `Status`; `SetCurrency`, `HasCurrency`; the gambler's bet tokens). A ware priced in it sells for gold when no module registered one (`PaysCurrency`); `Sell`, `Price`, `hwp wares`, `hwp sell` |
| `gui/hwp/map_icons.png` | The minimap icon sheet: the dye pot (`mods/mapicons`) and the fish and crop icons the fishing and farming units use (`tools/make_map_icons.py`; textures must be power-of-two sized) |
| `scripts/HWP/Core/LuckView.as` | `HWP::LuckView`: what the character screen shows of Luck, through a `Provider` (`OfRecord`, `PartyFactor`, `Fmt`, `TooltipText`) that `hwplib-luck` registers with `Set`. The stat bar's `hwp-luck-stat` cell and the Mods tab's Luck row read it; without a provider the cell hides and the row is skipped. The interface keeps these four methods for good (a package of an older build may call them) |
| `scripts/HWP/Core/Materials.as` + `gui/playermenu/character.gui` | `HWP::Materials`: two untitled sections in the materials tab, each under the one before, for things a module keeps per character: `hwp-materials-a` (8 cells, 29x26) and `hwp-materials-b` (16 cells, 28x24, 8 across). A module titles a section (`Title(section, langKey)`, the first one wins) and registers a `HWP::Materials::Material` (icon, count, tooltip title and text, `Click()`) with `Register(section, order, id, material)`; the cells take the entries in order and each takes its entry's id. The gui must hold the cells when the menu collects its interactables, so they are static and generic. Cells without an entry, or with none in stock, are hidden, and a section without any hides; hovering a cell shows its tooltip at the mouse; clicking one calls its `Click()`. Today: section a is **Supplies** (gambler bet tokens, fishing baits), section b **Plants & Herbs** (farming) |
| `scripts/HWP/Core/ItemActions.as` | `HWP::ItemActions`: a module registers an `Action` for some bag items (`Label`, `Do`); droptrade shows it as an `[E] <label>` hint and the E key runs it. The fishing mod's **Eat** (100 health per star) is the one today |
| `scripts/HWP/Core/Options.as` + `gui/hwp/options.gui` + `gui/playermenu/playermenu.gui` | `HWP::Options`: the player menu's **Plus** tab, our settings screen. `playermenu.gui` (declared override) adds the tab button (tab padding 12 -> 8 so four fit) and an `hwp-options-hook` widget that adds `HWPOptionsTab` to the PlayerMenu on its first update. The tab has a row per option id (`hwp-opt-<id>`); a module registers an `HWP::Options::Option` (title, value, `Next()` on click) or a `KeyOption` (click: an `HWPKeyCaptureWindow` (`gui/hwp/keycapture.gui`) goes over the menu, so the menu gets no input, and binds the next key pressed, by position with text input off; Esc cancels) under that id, and rows without one hide. A search field at the top filters the rows by title or value as you type (Esc clears it; the console key's ` and ~ are refused). `HWP::Options::TabOpen()` is true while the tab (or a capture) is up: a module polling a raw key skips it then. Tab id `HashString("hwp_options")`. Rows now: `colors`, `swapkey`, `dropkey`, `actionkey`, `skill4`-`skill6`, the Dev Arena hotkeys. **Key names:** a bind is one press: click the row, press the key, and it binds when the key comes up. Keys are polled by SDL scancode (position) and named as printed on a US keyboard, as the vanilla Controls window does (`KeyName`/`ShortKeyName`; `FitKeyName` in a row's value: the short name past 9 characters; search still matches the full name). Not localised: the engine gives scripts no key names, so on AZERTY the key at Q still reads Q. **Game keys** (`GameKeys.as`, group row `hwp-pkg-gamekeys`, rows `hwp-opt-game-<id>`): 27 of the game's own keyboard binds (move, attack, skills, dash, potion, use, menus...) rebound in game through the `kbm` ControlMap staging API and saved to `res/controls.cfg` (global, like the Options menu); a bind replaces the action's keyboard keys and keeps its mouse buttons. Esc's MenuBack/MenuToggle are not offered. A hint names the other options on the same key |
| `scripts/HWP/Core/TargetHelper.as` | **Targeting helper.** hwplib swaps the local player's `PlayerTargetingHelper` for `HWPTargetingHelper` on every spawn. It changes nothing itself: `HWP::TargetHelper::OnUpdate` callbacks run first in every frame of player control, `OnSkillInput` callbacks rewrite the `ButtonState` vanilla `GetSkillInput` gives a skill, and it calls the aim hooks (`Aim.as`). Used by the classes module's Skill 4-6 keys and by `mods/autoaim`. |
| `scripts/HWP/Core/Aim.as` | **Aim hooks.** `HWPTargetingHelper` (TargetHelper.as) passes the reticle vanilla worked out (`CalcGamepadTargetPos`, `CalcMouseTargetPos`) through `HWP::Aim::OnAdjust` callbacks and runs `HWP::Aim::OnPreUpdate` callbacks before the vanilla targeting step (true skips this frame's skill input). `HWP::Aim::FireTargeted` fires the targeted skill the way vanilla's activating press does. Used by `mods/autoaim`. |
| `scripts/HWP/Core/CoreModule.as` | boot self-checks; prints every mod id's save hash for `gamelab/hps.py` |
| `scripts/HWP/Core/CustomStats.as` | `HWP::CustomStat(rec, id)`: a custom player stat's value (`PlayerStats.m_customStats`), 0 when absent; read by Luck (`hwplib-luck`), Firearms' elemental stats, the keys module's key ring and the trinkets module's stats |
| `scripts/HWP/Core/Carve.as` | `HWP::Carve`: places a prefab room into a generated floor's solid wall with a straight corridor from its doorway to the nearest floor (`GetDoor`, `BlockedSums`, `BestSpot`); used by `puzzles` (forced rooms) and `objectives` (vaults) |

## Why character.gui is overridden

The gear grid needs new widgets in the character screen, and a gui file cannot
be merged. hwplib owns `gui/playermenu/character.gui` (declared in
`module.json`): the vanilla file with the equipment moved into a 3x3 grid and
four `hwp-gear-slot` widgets added (`hwp-gear-rod`, `hwp-gear-can` below the
gloves and the cape, `hwp-alt-main`/`hwp-alt-off` for the other weapon set).
They sit outside `<equipment>` because `EquipmentWidget.DoLayout` fills every
item slot inside it by id. `hwp-gear-label` text widgets (`HWP::Gear::RegisterLabel`) caption the
other set. The file also drops the "Inventory" title bar, moving the tabs up,
and gives the bag view a fourth row (every grid height +27; the window had
22 px spare); the two materials-tab sections (`hwp-materials-a`, `-b`). Providers: fishing (rod), farming (watering can),
weaponswap (the other set); section a: gambler (bet tokens), fishing (bait); section b: farming (seeds, crops, herbs). Each module still works without the others; its
slot just stays hidden.

## Settings: the Plus tab and the console

The game's Options menu (main menu and pause menu) runs in the menu script,
which never loads mod scripts or mod gui files, so a mod cannot add to it
(GameLab `probe-options-menu`: a `gui/options/game.gui` override never shows),
and its Controls list is a fixed action table in the exe. Settings with a
row in the player menu's Plus tab (`Options.as`) are changed there; the rest
by console. `hwp set <key> <value>` writes a
`HWP::Settings` value (`true`/`false` -> bool, number -> int, else string) and
notifies every listener, so modules pick the change up live. Replies print
to the console prefixed `[HWP]` (and to the chat log, which shows in a lobby).

Why the console and not `/hwp` in chat: the in-game chat and the pause menu
run in the main menu's script, which loads only the unmodded base scripts and
has no town or players. The console calls `hwp` in the game's script, and a
one-string console function receives the whole rest of the line. The vanilla
`cht_*` cheats are registered by both scripts and the console runs the menu's
copy, which is why `cht_give_material` and friends fail with a null pointer in
a level; `Cheats.as` has working copies.

## Why the outdoor themes are overridden

Vanilla `OutdoorGenerator` picks the base level prefab once and keeps it across
"Failed generation commands, retrying from scratch". When a required prefab set
can never fit on that base (seen: `forest_2` on `base_levels/level_6.pfb` with
`forest_skill`), the game retries the same layout forever until the lobby times
out. `gen-class` is created with `InstantiateClass`, which ignores info.xml
classmaps, so `tweak/missions/themes_{forest,heaven,keep,prison}.sval` and
`themes_heaven.inc` are copied with only `gen-class` changed to
`HWPOutdoorGenerator` (the `.orig` copies are the base files for `build.py --check`).
The boot log shows `generator safety net: HWPOutdoorGenerator`.

## Why messages.net is overridden

HoH2 declares all network messages in one file. There is no merge mechanism, so
hwplib ships a copy with two generic messages appended. `tools/build.py
--check` flags the day a game update changes the original.

## Library rules

- **It only grows.** Never remove or change the signature of a function, class, interface
  method, setting key or lang key here: a published package of an older build may call it.
  Add a new one beside it.
- **Every package is published from one build.** `tools/build.py` stamps the library
  (`HWP::LIB_STAMP` in the generated `scripts/HWP/Core/LibStamp.as`), and each package's
  check module logs `[HWP:core] package HWP-<id>, library <stamp>`, or an error naming both
  stamps when another build's library won.
- **A part reaches another only through an interface it registers** (`HWP::LuckView`), so
  each part works without the ones after it.

## Testing

`python -m gamelab run mod-core --mode lab` (`gamelab/scenarios/mod-core.json`) boots
the library (hwplib, hwplib-luck, hwplib-classui) in town on the `town-paladin` fixture.
It asserts these lines and no script errors in our files:

- `[HWP:core] module created, version ...`
- `[HWP:core] lang check: HammerwatchPlus language file loaded` (not the raw key)
- `[HWP:core] modhash 'hwplib' <n> enabled unpacked`. One `modhash` line is logged per installed mod.
- `[HWP:core] gameplay started; server=yes town=yes ...`

`mod-core-town-save` (fixture `town-tavern`) asserts `[HWP:core] town record loaded, N hwp
key(s)` before and after a save and load. The built packages: `pkg-<id>`, `pkg-all`,
`pkg-pair-*` (`tools/make_package_scenarios.py`).
Targeting helper:

- `[HWP:core] targeting helper installed` on every spawn of the local player. The extra
  skill keys it serves moved to the classes module (its README).
