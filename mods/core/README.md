# core

Shared library every other HammerwatchPlus module depends on. It adds no gameplay.

| File | Provides |
|---|---|
| `scripts/HWP/Core/Log.as` | `HWP::Log(module, msg)` / `HWP::LogError`, `HWP::VERSION` |
| `scripts/HWP/Core/Net.as` | `HWP::Net` request/event bus (`OnRequest`, `OnEvent`, `Request`, `Broadcast`, `Send`) |
| `scripts/HWP/Core/SaveData.as` | `HWP::SaveData::Player/Local/Town/MyTown()` data bags saved under the record's `hwp` key; a bag lives in the record's `userdata`, so it dies with the record |
| `scripts/HWP/Core/Settings.as` | `HWP::Settings::Get*/Set*` local preferences, stored in `g_myTownRecord` (the only town record the game saves; clients only get a copy of the host's `g_currTownRecord`) |
| `scripts/HWP/Core/Commands.as` | `HWP::Commands`: the `hwp` console command. `hwp help`, `hwp version`, `hwp settings`, `hwp get <key>`, `hwp set <key> <value>`; modules add their own with `Register(name, help, handler)` and listen for setting changes with `OnSettingChanged` |
| `scripts/HWP/Core/GearSlots.as` + `gui/playermenu/character.gui` | `HWP::Gear`: extra gear slots in the character screen. The vanilla equipment is a 3x3 grid (main hand, head, off hand / hands, chest, back / rod, feet, can), with the bottom corners and the alt-weapon pair as `hwp-gear-slot` widgets; a module registers a `HWP::Gear::Slot` provider by widget id (`Register`), slots without a provider are hidden. Providers call `Changed()` when what they show changes (a level load does too); the slots reload only then |
| `scripts/HWP/Core/Town.as` | `HWP::Town::Placeable` (a settings-backed town doodad the host spawns; optional `m_locate` finds its spot in this town on every machine, it is placed again after a town rebuild, `Reset()` drops the saved spot), `HWP::Town::ChapelPyreSpot` (the chapel Pyre slot, where the campaign portal and the wave statue stand), `HWP::Town::Kept` (a once-per-load unit to spawn again after a rebuild; `Set(unit)` remembers its producer), `HWP::Town::Ours(u)` (a kept pointer still names a live HWP unit: a rebuild reuses unit ids, so check this before trusting or destroying one), `HWP::Town::PayGold`, and `HWPLocalNPC`, the behaviour of town units every machine spawns for itself (fishing spots, the pirate, farm plots, the well) |
| `scripts/HWP/Core/PickupFirst.as` | `HWP::PickupFirst`: the use key picks up a dropped item before it talks to an NPC or opens a shop, chest or shrine underfoot. The local player's usables are re-sorted every frame with items between -1 (revives, exits) and 0 (vanilla puts items at 1, last) |
| `scripts/HWP/Core/BagSlots.as` | `HWP::Bag`: bought equipment bag slots, 24 + up to 8 per character (`bag.extra` in the HWP data; 1000 g rising to 20000 g, sold by the keys module's exit guard shop or `hwp bag buy`). The character screen's `<hwp-equipmentinventory>` draws every slot you can fill. `HWP::Bag::OnEquip(f)` runs `f(record, item)` before a bag click equips the item (firearms uses it to put a pistol in the off hand) |
| `system/messages.net` | base file + `HWPRequest` / `HWPEvent` messages (declared override, see `module.json`) |
| `scripts/HWP/Core/Cheats.as` | `hwp unlockflags`, `material`, `levelup`, `xp`, `statpoints`, `skillpoints`, `equip`, `spawnmaps`, `finishlevel`, `boss`, `killall`, `god`, `tokens` (bet tokens): copies of the vanilla `cht_*` cheats that work in a level (need `e_cheats 1`) |
| `scripts/HWP/Core/Generator.as` | `HWPOutdoorGenerator`: vanilla `OutdoorGenerator` that picks its base level again on every retry and sets aside a base that failed 10 times in a row (see below) |
| `scripts/HWP/Core/Market.as` | `HWP::Market`: wares (crops, herbs, fish) registered by modules, counted from your HWP data and bag items, sold for gold or **bet tokens** (`bet_tokens` per character; `Tokens`, `AddTokens`, `SpendTokens`, `Sell`, `Price`); `hwp wares`, `hwp sell` |
| `scripts/HWP/Core/MapIcons.as` + `gui/hwp/map_icons.png` | Minimap icons: a dye-pot marker over every dye bucket of a floor (`mapicons.dyes`, default on); the sheet also has the fish and crop icons the fishing and farming units use (`tools/make_map_icons.py`; textures must be power-of-two sized) |
| `scripts/HWP/Core/Materials.as` + `gui/playermenu/character.gui` | `HWP::Materials`: sections in the materials tab for things a module keeps per character, each under the one before: **Supplies** (gambler bet tokens, the fishing baits) and **Plants & Herbs** (farming seeds and the harvested crops and herbs, 8 cells across). Cells are `hwp-material` widgets inside a section's wrapping grid (it grows to as many rows as it needs); a module registers a `HWP::Materials::Material` (icon, count, tooltip title and text, `Click()`) by cell id. Cells without one, or with none in stock, are hidden, and a section without any hides; hovering a cell shows its tooltip at the mouse (the player menu's tooltip anchor would put it top centre); clicking one calls its `Click()` (farming: a herb offers to roll a joint) |
| `scripts/HWP/Core/ItemActions.as` | `HWP::ItemActions`: a module registers an `Action` for some bag items (`Label`, `Do`); droptrade shows it as an `[E] <label>` hint and the E key runs it. The fishing mod's **Eat** (100 health per star) is the one today |
| `scripts/HWP/Core/OrbWarn.as` | **Orb warning.** Some orbs are mutually exclusive (`blocked-by-skills`: the Firearms grenade types, the RPG's warheads, vanilla ones too) and the vanilla picker never says so. While an orb picker (`GiveSkillSphereMenu`) is open, each pick that would close others gets a red row under its description: "Makes unavailable:" and every orb it closes, icon and name (icons only when the names don't fit); `[HWP:orbwarn]` logs it. Only the in-run picker, not the Sarcophagus or mission sphere selectors |
| `scripts/HWP/Core/Options.as` + `gui/hwp/options.gui` + `gui/playermenu/playermenu.gui` | `HWP::Options`: the player menu's **Plus** tab, our settings screen. `playermenu.gui` (declared override) adds the tab button (tab padding 12 -> 8 so four fit) and an `hwp-options-hook` widget that adds `HWPOptionsTab` to the PlayerMenu on its first update. The tab has a row per option id (`hwp-opt-<id>`); a module registers an `HWP::Options::Option` (title, value, `Next()` on click) or a `KeyOption` (click: an `HWPKeyCaptureWindow` (`gui/hwp/keycapture.gui`) goes over the menu, so the menu gets no input, and binds the next key pressed; Esc cancels) under that id, and rows without one hide. A search field at the top filters the rows by title or value as you type (Esc clears it; the console key's ` and ~ are refused). `HWP::Options::TabOpen()` is true while the tab (or a capture) is up: a module polling a raw key skips it then. Tab id `HashString("hwp_options")`. Rows now: `colors`, `swapkey`, `skill4`-`skill6` |
| `scripts/HWP/Core/SubclassPick.as` | **Subclass Picker skill row by type.** The vanilla picker shows a spec's last two skill defs as "Active" and "Passive", wrong for the HWP specs (Sniper's Flashbang and Decoy are both actives, Snipe never shows). Core patches the open picker in place each time it shows another class: the spec's own skills (those its parent class lacks), actives first then passives, each labelled by its real type, up to four slots across the row. Vanilla specs look the same as before. GameLab: slots are `skill-active-name`, `skill-passive-name`, `hwp-pick-name2`..; labels `hwp-pick-label0`..; `gl classskills <classId>` lists the defs it is checked against |
| `scripts/HWP/Core/TargetHelper.as` | **Targeting helper.** Core swaps the local player's `PlayerTargetingHelper` for `HWPTargetingHelper` on every spawn. It changes nothing itself: `HWP::TargetHelper::OnUpdate` callbacks run first in every frame of player control, `OnSkillInput` callbacks rewrite the `ButtonState` vanilla `GetSkillInput` gives a skill, and it calls the aim hooks (`Aim.as`). Used by the classes module's Skill 4-6 keys and by `mods/autoaim`. |
| `scripts/HWP/Core/Aim.as` | **Aim hooks.** `HWPTargetingHelper` (TargetHelper.as) passes the reticle vanilla worked out (`CalcGamepadTargetPos`, `CalcMouseTargetPos`) through `HWP::Aim::OnAdjust` callbacks and runs `HWP::Aim::OnPreUpdate` callbacks before the vanilla targeting step (true skips this frame's skill input). `HWP::Aim::FireTargeted` fires the targeted skill the way vanilla's activating press does. Used by `mods/autoaim`. |
| `scripts/HWP/Core/CoreModule.as` | boot self-checks; prints every mod id's save hash for `gamelab/hps.py` |
| `scripts/HWP/Core/CustomStats.as` | `HWP::CustomStat(rec, id)`: a custom player stat's value (`PlayerStats.m_customStats`), 0 when absent; read by Luck, Firearms' elemental stats, the keys module's key ring and the trinkets module's stats |
| `scripts/HWP/Core/Carve.as` | `HWP::Carve`: places a prefab room into a generated floor's solid wall with a straight corridor from its doorway to the nearest floor (`GetDoor`, `BlockedSums`, `BestSpot`); used by `puzzles` (forced rooms) and `objectives` (vaults) |
| `scripts/HWP/Core/Luck.as` + `tweak/hwp/modifiers_luck.sval`, `trinkets_luck.sval`, `buffs_luck.sval` | `HWP::Luck`: the **Luck** stat (below, and `docs/design/luck.md`): `Of`, `Factor` (1 + luck/100), `OpenerFactor` (the Luck the player's own machine reported), `PartyFactor` (the average), `Chance`, `TierUpChance`, `RollPool` / `SpawnLoot` / `SpawnLootFor` (a luck-weighted loot table roll; personal: for one player), `GiveBuff` (the timed Luck buff), `LogRoll`; the Luck reports (`hwp.luck.report`); `hwp luck` |
| `scripts/HWP/Core/LuckFloors.as` + `scripts/WorldScript/RewardSpot.as`, `scripts/BlueprintBank.as` (declared overrides, `.orig` beside them, changes marked `// HWP`) | the party's average Luck on generated floors: `FloorFactor` (the run scalar `hwp_luck_party` the host keeps, carried into the generation context by the save), an extra secret room (`HWPLuckSecretSpawn` for every `*_secrets` set), the imp's room at its chance times the factor (`HWPLuckChanceSpawn` for every `*_imp` set), the floor value broadcast to clients (`hwp.luck.floor`, `FloorReady`), reward counts leaning to their vanilla maximum and reward tiers toward the top, the blueprint chance multiplied and rarer recipes weighed up (`docs/design/luck.md`) |

## Why character.gui is overridden

The gear grid needs new widgets in the character screen, and a gui file cannot
be merged. Core owns `gui/playermenu/character.gui` (declared in
`module.json`): the vanilla file with the equipment moved into a 3x3 grid and
four `hwp-gear-slot` widgets added (`hwp-gear-rod`, `hwp-gear-can` below the
gloves and the cape, `hwp-alt-main`/`hwp-alt-off` for the other weapon set).
They sit outside `<equipment>` because `EquipmentWidget.DoLayout` fills every
item slot inside it by id. `hwp-gear-label` text widgets (`HWP::Gear::RegisterLabel`) caption the
other set. The file also drops the "Inventory" title bar, moving the tabs up,
and gives the bag view a fourth row (every grid height +27; the window had
22 px spare); a materials-tab Supplies row (`hwp-materials`). Providers: fishing (rod), farming (watering can),
weaponswap (the other set); Supplies: gambler (bet tokens), fishing (bait), farming (seeds). Each module still works without the others; its
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
the core module ships a copy with two generic messages appended. `tools/build.py
--check` flags the day a game update changes the original.

## Luck

A custom stat (`hwp-luck`, `Modifiers::CustomStat`) summed by the vanilla modifier
pass, so anything with modifiers gives it: the rolled "of Fortune" armour affixes
(`hwp_mod_luck_1..3`: +5 uncommon, +10 rare, +20 epic, one per generator slot, one
exclusive group), the Rabbit's Foot trinket (`hwp_trinket_rabbit_foot`, +10, attuned
+20), and the 10-minute buff `tweak/hwp/buffs_luck.sval:hwp_luck_charm` that herbs
(farming), fish (fishing) and `hwp luck buff` apply through `HWP::Luck::GiveBuff`. The
character sheet's Mods tab lists it after Thorns (row `hwp-luck`, "N Luck", the vanilla
luck glyph and a tooltip), and the character (inventory) tab's stat bar shows it after
movement speed (`icon-luck`, button `hwp-luck-stat`, text widget `hwp-luck-stat` id
`hwp-luck-text`, hover tooltip with your factor and the party's).

`Factor = 1 + luck / 100` is what a drop site multiplies its rarer outcomes by:
`SpawnLoot` rolls a loot table with every entry lighter than the pool's heaviest one
weighted by the factor (the empty share keeps its weight: Luck changes what drops, not
how often, except a pool of dye buckets only, which pays at its share times the factor), `Chance` scales a plain chance capped at 1, `TierUpChance` is 25 % per +1.0
of factor capped at 75 %. A shared drop rolls once on the host and everyone gets what
it picked. An opened one (chest, cache, strongbox, a catch's loot) rolls at the opener's
Luck (`OpenerFactor`, as their machine reported it), so the luckiest player opening a chest
makes it lucky for the party; one nobody opens (an abyss crack, the keys budget's accept
roll) at `PartyFactor()`, the lobby's average; a kill's key chance at the killer's own.
Generated floors use the party's average (`FloorFactor`, `LuckFloors.as`): one secret room
more at 50 % per +1.0 of factor (cap 75 %), every reward count between its vanilla minimum
and maximum leaning to the maximum (`1 - (1 - u)^factor`), each reward spot's quality gap
divided by the factor, the 25 % blueprint chance multiplied, blueprint recipes rarer than
the commonest on offer weighed by the factor, the imp's 10 % and the fishing hole chance
multiplied, and (keys module) the key budget, its tiers and the ace chest chance. Each site logs
`[HWP:<module>] luck x<factor> <what>` before it rolls.

Cheats (`e_cheats 1`): `hwp luck <n>` (an exact modifier on the local record),
`hwp luck buff [n] [ms]`, `hwp luck item <tier>` (a chest piece with only that affix,
equipped), `hwp luck roll <table|chance <pct>|tier|quality|secret|count> <n> [luck]` (n rolls, no
spawning, counts per entry; `quality` a blueprint pick among two commons, an uncommon and
a rare, `secret` the extra room, `count` a reward count's mean lean). `hwp luck` alone: `Luck: N (factor F; party factor P; cheat C)`.
Scenarios: `fix-core-luck` (`gamelab/bots/fix_luck.py`), `fix-luck-floors`, `fix-luck-imp`.

## Testing

`python -m gamelab run mod-core --mode lab` (`gamelab/scenarios/mod-core.json`) boots
core in town on the `town-paladin` fixture. It asserts these lines and no script errors
in our files:

- `[HWP:core] module created, version ...`
- `[HWP:core] lang check: HammerwatchPlus language file loaded` (not the raw key)
- `[HWP:core] modhash 'core' <n> enabled unpacked`. One `modhash` line is logged per installed mod.
- `[HWP:core] gameplay started; server=yes town=yes ...`

Not asserted yet: `[HWP:core] town record loaded, N hwp key(s)`. The fixture's town has
no save data, so `TownRecordLoad` never fires (`docs/RE_NOTES.md`, 2026-10-17). It needs
a fixture with a saved town.

Targeting helper:

- `[HWP:core] targeting helper installed` on every spawn of the local player. The extra
  skill keys it serves moved to the classes module (its README).

Subclass Picker skill row (plan checks): `picker_skill_labels` (plan_firearms.py, the three
doctrines) and `<class>_picker_skill_labels` (plan_classesb.py: thief, gladiator,
witchhunter, and the priest / paladin 4th spec) read the row from `gl widgets` and compare
it with `gl classskills` (gamelab/bots/picker_skills.py).
