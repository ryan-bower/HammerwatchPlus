# Luck: design

Luck is a core attribute (`mods/core/scripts/HWP/Core/Luck.as`, namespace `HWP::Luck`)
that makes the rarer outcome of a drop roll more likely. On a drop roll it never adds
drops: a pool that pays nothing some of the time pays nothing just as often, what changes
is which entry comes up when it does pay. On a generated floor the party's Luck also leans
the floor's reward counts toward their vanilla maximum and raises a few spawn chances
(below). This file holds the settled decisions and where each is built.

## Who rolls in co-op

A shared drop rolls once, on the host, and every player gets what it picked (vanilla's
rule: shared entries spawn once, instanced entries such as gear and trinkets spawn once
per player at the picked tier). The question is only whose Luck the roll uses:

- **Opened drops** (chests, caches, puzzle room chests, strongboxes, a fish's loot): the
  opener's Luck (`OpenerFactor`). The luckiest player opening the chest makes the whole
  party's chest lucky.
- **Drops nobody opens** (an abyss crack's payout, the key drop's host accept roll): the
  party's average (`PartyFactor`).
- **Generated floors** (secret rooms, the imp, reward spots, blueprints, fishing holes,
  the key budget, ace chests): the party's average as of the save the floor came from
  (`FloorFactor`, below). The host broadcasts it (`hwp.luck.floor`, every 3 s) so a roll
  every machine makes from a hash (a chest's ace lock) uses the same value; a client's
  chest waits for it as it waits for the host's settings (`FloorReady`).

A record's stats are computed on its own machine, so each machine reports its local
player's Luck to the host (`hwp.luck.report` through `HWP::Net::Request`, on change and
every 5 s); the host reads a remote player's Luck from the last report and falls back to
its own copy of the record until the first one arrives.

## The stat

- **Storage.** A vanilla custom stat named `hwp-luck` (`Modifiers::CustomStat`), so every
  carrier of modifiers can give it: rolled gear affixes, trinkets, mission buffs, actor
  buffs, the cheat. `PlayerRecord.RefreshModifiers` sums them; `HWP::Luck::OfRecord(rec)`
  reads `currStats.m_customStats`. Use `add` only: the engine's custom-stat maths is
  `val * (mul + mulSum)` with `mul` starting at 1 and multiplied by the param (default 0)
  and `mulSum` starting at 1, so a plain `add` reads back exactly as its sum.
- **API** (stable, the fishing module already calls it):
  - `float Of(PlayerBase@)` and `OfRecord(PlayerRecord@)`: total Luck points, 0 for null.
  - `float Factor(PlayerBase@)` and `FactorRecord(PlayerRecord@)`: `1 + luck / 100`
    (1.0 for null or no luck; never below 0).
  - `float OpenerLuck(PlayerRecord@)` and `OpenerFactor(PlayerRecord@)`: that player's
    Luck as their own machine reported it (the host's copy of the record for the local
    player or before a report); `OpenerNote(rec)` is the log suffix
    ` (opener <name>, Luck <n>)`.
  - `float PartyLuck()` and `PartyFactor()`: the average reported Luck of everyone in
    the lobby (`g_players`, peer 255 skipped; the local record when the list is empty).
    Average, not maximum: a drop nobody opens is as lucky as the party is, one player
    stacking Luck helps a four-player lobby a quarter as much.
  - `float FloorLuck()` and `FloorFactor()` (`LuckFloors.as`): the party's average for
    the current floor. The host keeps `PartyLuck` (rounded to 0.1) in the run scalar
    `hwp_luck_party`; the level's save carries it into the next floor's generation
    context (a separate script context with no lobby records, `docs/RE_NOTES.md`) and
    into the level. Each floor snapshots it on its first frame, before the host refreshes
    it, so rolls made after the start (the fishing hole) count the same Luck as the
    generation. Without the scalar (a client, a fresh context) it falls back to
    `PartyLuck`.
  - `float Chance(base, factor)`: `base * factor` capped at 1; `bool Roll(base, factor)`.
  - `float TierUpChance(factor)`: `(factor - 1) * 0.25` capped at 0.75 (the abyss).
  - `int RollPool(Item::LootTablePool@, factor)` and
    `int SpawnLoot(Item::LootTable@, PlayerBase@ looter, vec3, factor, what)`: the
    luck-weighted loot table roll (below). `SpawnLoot` is the vanilla
    `LootTablePool::SpawnLoot` (conditionals, spread, raycast, one spawn per player for
    instanced entries, shared entries once) with `RollPool` as the pick; server only.
  - `bool GiveBuff(PlayerBase@, float points, int durationMs = -1, why)`: the timed Luck
    buff (`tweak/hwp/buffs_luck.sval:hwp_luck_charm`, 10 minutes by default); points up
    to 100 (the buff's `add` is `0 100` lerped by intensity). Applying it again refreshes
    the running one to the longer duration and the stronger of the two strengths, so a
    weaker source never lowers it (`ActorBuffList.Add` averages a same-def refresh, so
    the new application is sent at `2 * stronger - running`).
  - `void LogRoll(module, what, factor)`: the one log line per roll,
    `[HWP:<module>] luck x<factor> <what>`, so a test can read the factor a site used.
- **Where Luck comes from.**
  - Gear affixes `hwp_mod_luck_1..3` ("of Fortune", `tweak/hwp/modifiers_luck.sval`):
    +5 uncommon, +10 rare, +20 epic, on head, chest, feet, hands and back, one exclusive
    group so a piece carries one. The vanilla generator draws its first modifier slot
    from the common + uncommon pool, the second from the rare pool and the third from the
    epic pool, spawn-chance 1 like any vanilla affix. The tooltip lists "+N Luck".
  - The Rabbit's Foot trinket (`hwp_trinket_rabbit_foot`, `tweak/hwp/trinkets_luck.sval`):
    uncommon, +10, attuned +20; drops and sells like any uncommon trinket.
  - Buffs: a puff of any herb +10, Lucky Leaf +25 (farming `ApplyHerb`); eating a fish
    +5 a star (fishing `EatFish`); `hwp luck buff [n] [ms]`. All the same 10-minute buff,
    refreshed by the next (the stronger strength stays); whether a timed actor buff survives a floor change is the
    engine's rule for actor buffs (untested here).
  - The cheat `hwp luck <n>` (needs `e_cheats 1`): an exact modifier on the local record
    through the `PlayerRecordRefreshModifiers` hook.
- **Shown.** The character sheet's stats list (the Mods tab, utility section, after
  Thorns) has a "Luck" row, widget id `hwp-luck`, lang `stat.custom.hwpluck` (the
  `AddStat` helper forces the `stat.custom.` prefix; every other key is `hwp.luck.*`), with
  the vanilla `icn-luck` glyph and a tooltip (`hwp.luck.stat.tip`: your factor, the
  party's). The character (inventory) tab's stat bar has a sixth cell after movement speed:
  `icon-luck` and the value (`HWPLuckStatWidget`, widget `hwp-luck-stat`, id
  `hwp-luck-text`, read each frame), same tooltip on hover.
  `hwp luck` prints `Luck: N (factor F; party factor P; cheat C)` to chat and the log.

## The formulas

- **Loot tables** (`RollPool`). Vanilla rolls `randi(1000)` against the entries' chances;
  a pool whose chances sum below 1000 pays nothing the rest of the time. With Luck every
  entry lighter than the pool's heaviest entry has its chance multiplied by the factor
  and the heaviest entry keeps its vanilla weight. The pool first pays nothing at its
  vanilla odds (the empty share of 1000), so Luck changes which entry drops, never how
  often one does. In a 700 rare / 300
  epic trinket pool, factor 1.5 gives 700 : 450 (39 % epic instead of 30 %), factor 6
  (500 Luck) 700 : 1800 (72 %). A one-entry pool is unchanged.
- **Dyes** (`DyePool`): the one exception to "never more often". A pool whose entries are all
  dye buckets (`items/dyes/`) pays at its vanilla share times the factor: the bronze trinket
  chest's 60 % dye pool pays every time at factor 2 or more. The cache pools mix their dyes
  with a heavier entry, so there the dyes come up more often through the pick instead. A
  dye's quality follows the chest's tier (bronze common, silver uncommon, gold rare), which
  the floor's Luck raises.
- **Plain chances** (`Chance`): the chance times the factor, capped at 1 (keys).
- **Tiers** (`TierUpChance`): 25 % per +1.0 of factor, at most 75 % (abyss).
- **Secret rooms** (`SecretRoomChance`): one room more than the theme's `*_secrets` set
  allows, 50 % per +1.0 of factor, at most 75 %. The room still needs a spot its pattern
  matches (the first bandit keep floor often has none left).
- **Floor reward counts** (`LuckyRandf`): vanilla rolls each count as
  `lerp(min, max, randf())`; Luck uses `1 - (1 - u)^factor` for the `randf`, so the count
  never leaves the vanilla range but leans to its top (mean 1/2 at factor 1, 2/3 at 2,
  6/7 at 6).
- **Reward quality** (`LuckyIntensity`): a reward spot's intensity (0..1, from depth and
  the spot's Quality; it picks the food, mana, chest, cache, scroll and valuable tiers)
  has its gap to 1 divided by the factor (factor 2: 0.5 becomes 0.75).
- **The imp** (`HWPLuckChanceSpawn`): every theme's `*_imp` set (exec-chance 0.1) runs at
  that chance times the factor (60 % at factor 6). The generator rolls `exec-chance` before
  `Execute`, so the swapped command sets it to 1 and rolls inside `Execute`.
- **Keys and ace chests** (keys module): the floor's key budget share
  (`keys.budget_share` + per extra player) times the factor, still at most 95 % of the
  locked chests; the budget's tier pick weighs every tier above the lowest one left by the
  factor; a gold chest's ace chance (`keys.ace_chance`, 15 %) times the factor, at most 50 %
  (`AceChance`).
- **Blueprint picks** (`PickByQuality`): vanilla picks a recipe uniformly; Luck weighs
  every candidate rarer than the commonest quality on offer by the factor (the RollPool
  rule). Among two commons, an uncommon and a rare, factor 6 picks a rare 43 % of the
  time instead of 25 %.

## Where it applies

| Site | Luck used | Built |
|---|---|---|
| Reward chests, caches, puzzle room rewards (any `Chest` unit, which the keys module swaps for `HWPChest`; a puzzle room's reward is a RewardSpot that spawns a chest). Dyes are chest and cache loot only (no dye unit is placed on a floor; `probe-dyes-floor`), so they ride on this | the opener's factor on the chest's table | `mods/keys/scripts/HWP/Keys/HWPChest.as` `Use`: the table is taken off the behaviour around `Chest::Use` and rolled by `SpawnLoot`; log `[HWP:keys] luck x<f> chest <key\|open> loot (opener <name>, Luck <n>)` |
| Strongbox payout | the opener's factor (who paid) | `mods/strongbox/.../Strongbox.as` `HWPStrongbox::Pay`; log `[HWP:strongbox] luck x<f> payout (opener ...)` |
| Abyss crack payout | party factor: tier-up roll, then the table | `mods/abyss/.../Abyss.as` `Finish`; log `[HWP:abyss] luck x<f> payout hwp_abyss_reward_<t>[ (tier up)]` |
| Key drops | killer's factor on the boss chance and the normal-kill candidate share; party factor on the host's accept roll | `mods/keys/.../KeysModule.as` `OnKill`, `OnDropRequest`; logs `[HWP:keys] luck x<f> boss key roll / <elite\|normal> kill drop candidate / candidate accept roll` |
| Fishing (bite tier bands, key chance and tier shares, catch loot) | the fisher's reported factor | `mods/fishing/.../FishingModule.as` `LuckOf` |
| Secret rooms per floor | floor factor | `HWPLuckSecretSpawn` (`LuckFloors.as`), swapped in for every `*_secrets` `SpawnPrefabSet` by the module constructor; log `[HWP:luck] secrets <set> on <level>: party Luck N, extra room chance C%: rolled\|not rolled, max M, placed P` |
| Floor rewards: the counts of trinket picks, trinkets, equipment chests, caches, exp scrolls, valuables, health food and mana pickups; their tiers; the blueprint chance (25 % x factor) | floor factor | core's `WorldScript/RewardSpot.as` override (vanilla in `.orig` beside it, changes marked `// HWP`); log `[HWP:luck] floor rewards at party Luck x<f>: blueprint chance C% -> N, ...`. Skill spheres and material piles stay vanilla |
| Blueprint recipes (food and drink, enchantments, trinkets) | floor factor | core's `BlueprintBank.as` override (`.orig` beside it); log `[HWP:luck] blueprint <kind> picked of <n> at x<f>: quality <q>` |
| The imp's room | floor factor on the `*_imp` set's exec-chance | `HWPLuckChanceSpawn` (`LuckFloors.as`); log `[HWP:luck] chance set <set> on <level>: party Luck N, chance C% (10% vanilla): rolled\|not rolled, placed P` |
| Key budget per floor, its tiers, ace chests | floor factor | `KeysModule.as` `BudgetTotal`, `PickBudgetTier`; `HWPChest.as` `Decide`; log `[HWP:keys] luck x<f> chest lock <tier>[ (ace chance C%: ace\|gold)]`, `hwp keys` shows `floor Luck x<f>` |
| Fishing holes per floor | floor factor on the run chance (30 % x factor) | `FishingModule.as` `SetupRun`; log `[HWP:fishing] run hole chance C% (B% at party Luck x<f>): rolled\|not rolled\|boss room` |

Chest counts and their bronze, silver and gold tiers come from the reward spots above.
Not Luck-driven (vanilla or module odds): puzzle room, shrine, shop, strongbox and abyss
crack spawn chances, skill spheres, gold and material piles.

Without the keys module a vanilla `Chest` pays its vanilla roll: Luck then reaches chests
only through the modules above.

## Testing

`gamelab/scenarios/fix-core-luck.json` with `gamelab/bots/fix_luck.py` (town, host): the
status line after `hwp luck 50`, the sheet row, the affix item (`hwp luck item 2` adds 10),
the buff (`hwp luck buff 25 4000` is on, adds 25, is gone 5 s later), the no-spawn rolls
(`hwp luck roll hwp_strongbox 3000 0` vs `500`: more epics; `roll chance 40` and
`roll tier`), and two live drop sites: a spawned strongbox opened in town (no enemies to
sample, so it pays at once) and a spawned resource cache, each logging the opener's
factor and `[HWP:luck] loot <what> factor <f> picks ...`. The floor formulas are sampled
there too (`roll quality`, `roll secret`, `roll count`): the lab town has no tavern,
enchanter or library, so no blueprint factory can produce one in a test.

`gamelab/scenarios/fix-luck-floors.json` (town, then the first bandit keep floor at
`hwp luck 500`): the scalar reaches generation and the level, the keep's secret set rolls
at 75 %, the reward spots at a 100 % blueprint chance, the fishing hole at 100 %, each
locked chest at x6 (a gold one at a 50 % ace chance), the key budget at x6.
`gamelab/scenarios/fix-luck-imp.json` (the crypt mission's first floor, temple theme):
`temple_imp` at 60 %.

Not tested on two machines: the clients' Luck reports reaching the host, and a client's
own view of the floor (a client without the scalar uses its own `PartyLuck`, which only
matters for client-side rolls, of which there are none on floors today).
