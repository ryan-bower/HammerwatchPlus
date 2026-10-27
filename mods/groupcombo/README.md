# groupcombo

Combo together, get stronger together.

| Players in combo | Buff | Effect |
|---|---|---|
| 2 | Group Combo | +5% damage, +5% move speed, combo sustain +1 s |
| 3 | Group Combo II | +10% / +10% / +2 s |
| 4+ | Group Combo III | +15% / +15% / +3 s |
| everyone alive (2+) | **Group Unity** | 2 s of no damage taken, 30 s cooldown, chat announce |

- Host-only logic in `HWPGroupComboModule`: every 500 ms it counts living
  players with `PlayerBase.m_comboActive` (synced by the game) and re-applies
  the matching buff (`tweak/hwp/buffs_groupcombo.sval`, 1.5 s duration so it is
  continuous while the condition holds).
- Delivery: the host's own actor gets a real `ActorBuff`; remote players are
  husks on the host, so they get the vanilla `UnitBuffed` message and apply it
  themselves (same path as server-side shrine/effect buffs).
- `hwp groupcombo` prints the current count; `hwp set groupcombo.enabled
  false` turns it off (host setting).
- Numbers are a first guess for the morning: `tweak/hwp/buffs_groupcombo.sval`
  and the constants at the top of `GroupComboModule.as`.

## Settings

On the HammerwatchPlus tab of the player menu (host settings, they apply at once):

- **Group combo** on/off, `groupcombo.enabled` (default on). Off: no group buffs, no
  Group Unity and no combo orbs; a buff already up fades within 1.5 s.
- **Combo orb chance**, `groupcombo.orb.permille`: Off, 0.1 % (default), 0.2 %, 0.5 %, 1 %.
- **Orb chance cap**, `groupcombo.orb.max_permille`: 0.5 %, 1 % (default), 2 %, 5 %.

## Combo orb

Boxes, crates, barrels, sacks and vases drop a combo orb 0.1 % of the time (the
purple orb of the vanilla skill point pickup). The Luck of the player who broke it
raises that (times 1 + Luck / 100) up to 1 %, reached at 900 Luck; the party's Luck
plays no part. Everyone whose combo is unlocked
gets their own orb at the break spot; walking over it puts you in combo at once.
While you are already in combo it stays on the floor for later. Pets never fetch
it, and nobody can pick up another player's orb.

- `ComboOrb.as`: a `ComboOrbPool` (an `Item::LootTablePool` subclass) appended to
  the `barrel_wood_normal`, `barrel_wood_poor`, `sack`, `vase` and `vase_small`
  tables (`tweak/loot/containers.sval`). `LootTable.SpawnLoot` hands each pool the
  breaker's record (a pool's entries only see the host's), so the pool rolls once
  per break at that player's Luck (`HWP::Luck::OpenerLuck`, what their machine
  reported). A break with no attacker counts as the host's. A hit broadcasts
  `groupcombo.orb`; each machine
  spawns a local `items/hwp/combo_orb.unit` (netsync none) for its own player when
  `currStats.ComboCountMax > 0`.
- The orb is a plain `Pickup`: player-only (pets and other players' husks are not
  the local `Player`) and without a `pickup-trigger`, so `MiniPet.IsPickupOkay`
  ignores it. Its effect `HWPComboOrb` calls `Player.GiveCombo`.
- `hwp set groupcombo.orb.permille <0-1000>` (host, default 1) sets the base chance
  and `groupcombo.orb.max_permille` (default 10) the most Luck can raise it to; a
  base above the max is used as is. `hwp comboorb` shows both and your own chance at
  your Luck; with `e_cheats 1` the host can `hwp comboorb drop` (an
  orb for everyone, 40 px right) or `hwp comboorb break [radius]` (break the
  nearest box or vase).

## Test checklist

1. `python -m gamelab run mod-groupcombo --mode lab`: no script errors, no `[HWP:groupcombo] cannot load` line.
2. Co-op (2 players, host + client): both build a combo. Both see the "Group
   Combo" buff icon; the host log says `2/2 players in combo`; the chat shows
   the GROUP UNITY line and both take no damage for ~2 s. No second unity for
   30 s.
3. One player drops combo: the buff fades within ~1.5 s on both.
4. Solo: nothing happens (needs 2).
5. `hwp set groupcombo.enabled false` on the host: no buffs.
6. `python -m gamelab run fix-combo-orb --mode lab`: your chance at 0, 500 and 2000
   Luck (0.10, 0.60, 1.00 %), a vase break rolled at the breaker's 900 Luck; with the
   chance at 1000, no
   orb while combo is locked, an orb at a broken vase once it is unlocked, combo
   on when picked up, an orb left alone while in combo and taken after.
7. Co-op: break a vase with `hwp set groupcombo.orb.permille 1000`; each player
   with combo unlocked sees one orb and picking it up starts only their combo; a
   player without combo sees none.
