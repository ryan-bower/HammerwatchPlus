# hwplib-luck

The Luck part of the HammerwatchPlus library. Not a mod players install: the packages whose
mods read Luck carry it (Co-op, Keys, Dungeon, Town; `packages.json`). Requires `hwplib`.
Without this part the character screen hides the Luck stat (`HWP::LuckView` in hwplib has
no provider) and nothing rolls with Luck. Luck is for loot, reward rooms, fishing, chests
and gambling, never for effect chances.

| File | Provides |
|---|---|
| `scripts/HWP/Core/Luck.as` + `tweak/hwp/modifiers_luck.sval`, `trinkets_luck.sval`, `buffs_luck.sval` | `HWP::Luck`: the **Luck** stat (below, and `docs/design/luck.md`): `Of`, `Factor` (1 + luck/100), `OpenerFactor` (the Luck the player's own machine reported), `PartyFactor` (the average), `Chance`, `TierUpChance`, `RollPool` / `SpawnLoot` / `SpawnLootFor` (a luck-weighted loot table roll; personal: for one player), `GiveBuff` (the timed Luck buff), `LogRoll`; the Luck reports (`hwp.luck.report`); `hwp luck` |
| `scripts/HWP/Core/LuckFloors.as` + `scripts/WorldScript/RewardSpot.as`, `scripts/BlueprintBank.as` (declared overrides, `.orig` beside them, changes marked `// HWP`) | the party's average Luck on generated floors: `FloorFactor` (the run scalar `hwp_luck_party` the host keeps, carried into the generation context by the save), an extra secret room (`HWPLuckSecretSpawn` for every `*_secrets` set), the imp's room at its chance times the factor (`HWPLuckChanceSpawn` for every `*_imp` set), the floor value broadcast to clients (`hwp.luck.floor`, `FloorReady`), reward counts leaning to their vanilla maximum and reward tiers toward the top, the blueprint chance multiplied and rarer recipes weighed up (`docs/design/luck.md`) |
| `res/language/english/hwplib_luck.lang` | the `hwp.luck.*` strings (the stat's tooltip and `stat.custom.hwpluck` stay in hwplib, which shows the cell) |

`HWPLuckModule` registers `HWPLuckViewProvider` with `HWP::LuckView::Set` when it is created.

## The stat

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
