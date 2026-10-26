# Luck: design

Luck is a core attribute (`mods/core/scripts/HWP/Core/Luck.as`, namespace `HWP::Luck`)
that makes the rarer outcome of a drop roll more likely. It never adds drops: a pool that
pays nothing some of the time pays nothing just as often, what changes is which entry
comes up when it does pay. This file holds the settled decisions and where each is built.

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
  - `float PartyLuck()` and `PartyFactor()`: the average Luck of everyone in the lobby
    (`g_players`, peer 255 skipped; the local record when the list is empty). Average,
    not maximum: a shared drop is as lucky as the party is, one player stacking Luck
    helps a four-player lobby a quarter as much.
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
- **Plain chances** (`Chance`): the chance times the factor, capped at 1 (keys).
- **Tiers** (`TierUpChance`): 25 % per +1.0 of factor, at most 75 % (abyss).

## Where it applies

| Site | Luck used | Built |
|---|---|---|
| Reward chests, caches, puzzle room rewards (any `Chest` unit, which the keys module swaps for `HWPChest`; a puzzle room's reward is a RewardSpot that spawns a chest) | party factor on the chest's table | `mods/keys/scripts/HWP/Keys/HWPChest.as` `Use`: the table is taken off the behaviour around `Chest::Use` and rolled by `SpawnLoot`; log `[HWP:keys] luck x<f> chest <key|open> loot` |
| Strongbox payout | party factor | `mods/strongbox/.../Strongbox.as` `HWPStrongbox::Pay`; log `[HWP:strongbox] luck x<f> payout` |
| Abyss crack payout | party factor: tier-up roll, then the table | `mods/abyss/.../Abyss.as` `Finish`; log `[HWP:abyss] luck x<f> payout hwp_abyss_reward_<t>[ (tier up)]` |
| Key drops | killer's factor on the boss chance and the normal-kill candidate share; party factor on the host's accept roll | `mods/keys/.../KeysModule.as` `OnKill`, `OnDropRequest`; logs `[HWP:keys] luck x<f> boss key roll / <elite|normal> kill drop candidate / candidate accept roll` |
| Fishing (bite tier bands, key chance and tier shares) | the fisher's factor | `mods/fishing/.../FishingModule.as` `LuckOf` (the fishing module's own wiring) |

Without the keys module a vanilla `Chest` pays its vanilla roll: Luck then reaches chests
only through the modules above.

## Testing

`gamelab/scenarios/fix-core-luck.json` with `gamelab/bots/fix_luck.py` (town, host): the
status line after `hwp luck 50`, the sheet row, the affix item (`hwp luck item 2` adds 10),
the buff (`hwp luck buff 25 4000` is on, adds 25, is gone 5 s later), the no-spawn rolls
(`hwp luck roll hwp_strongbox 3000 0` vs `500`: more epics; `roll chance 40` and
`roll tier`), and two live drop sites: a spawned strongbox opened in town (no enemies to
sample, so it pays at once) and a spawned resource cache, each logging its factor and
`[HWP:luck] loot <what> factor <f> picks ...`.
