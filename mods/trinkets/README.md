# Trinkets: NG+ scaling and the HoH1 trinkets

## NG+ scaling

Flat trinket bonuses grow with the run's NG+ level (`g_ngp`, the loadout's NG+ picker):
each NG+ level adds a fixed amount. An attuned trinket gets twice that where attuning
doubles the flat number. Where attuning changes something else (a shorter cooldown, a
higher chance), the attuned trinket gets the same amount. Tooltips show the scaled numbers.
The amounts come from the Trinket Map verdicts (2026-10-26).

| Trinket | Per NG+ level | Attuned |
|---|---|---|
| `amulet_health` | health +5 | health +10 |
| `amulet_mana` | mana +5 | mana +10 |
| `amulet_vigor_greater` | health +10, mana +10 | health +20, mana +20 |
| `apothecarys_antidote` | poison +5 | same |
| `apothecarys_flask` | charges 2 from NG+ 4 | charges 4 from NG+ 4 |
| `apothecarys_tincture` | buff 5000 ms +1000 ms | same |
| `arctic_step` | frost damage +10 on 30 | same |
| `book_attacks` | attack-power +5 | attack-power +10 |
| `book_spells` | spell-power +5 | spell-power +10 |
| `caltrops` | proc damage +5 on 25 | same |
| `cauldron` | proc damage +10 on 30 | same |
| `chain_undershirt` | armor +10 | armor +20 |
| `chaos_orb` | poison +10, fire +10, ice +10, lightning +10 | same |
| `chicken_feet` | mana +0.25 | same |
| `closed_circuit` | lightning +2, proc damage +10 on 50, proc damage +10 on 50 (attuned too) | lightning +4 |
| `codex_power` | attack-power +10, spell-power +10 | attack-power +20, spell-power +20 |
| `coiled_serpent` | poison +2, proc damage +5 on 30, proc damage +5 on 30 (attuned too) | poison +4 |
| `decaying_hand` | mul +1 | same |
| `dragon_heart` | health +20, health-regen +5 | same |
| `dragon_scale_blue` | armor +10, ice +10 | same |
| `dragon_scale_red` | armor +10, fire +10 | same |
| `ectoplasm` | ice +2, proc damage +5 on 10, proc damage +5 on 10 (attuned too) | ice +4 |
| `fiddle` | physical +10 | same |
| `fire_salts` | fire +2, proc damage +10 on 30, proc damage +10 on 30 (attuned too) | fire +4 |
| `gambeson` | armor +5 | armor +10 |
| `gemstone_fire` | fire +5 | fire +10 |
| `gemstone_ice` | ice +5 | ice +10 |
| `gemstone_lightning` | lightning +5 | lightning +10 |
| `gemstone_poison` | poison +5 | poison +10 |
| `life_stone` | heal +2 | heal +4 |
| `maggot_gland` | proc damage +10 on 40, proc damage +10 on 40 (attuned too) | same |
| `mana_stone` | mana +3 | mana +6 |
| `markhams_amulet` | mul +1, mul +1 | same |
| `markhams_mace` | mul +1 | same |
| `markhams_purse` | gold-mul +0.01 | same |
| `markhams_stone` | wood-mul +0.01, stone-mul +0.01, iron-mul +0.01 | same |
| `markhams_wand` | mul +1 | same |
| `moonstone_pendant` | any +10 | same |
| `orb_of_restoration` | mana-regen +1 | same |
| `pickled_eye` | mul +1 | same |
| `razor_amulet` | attack-power +5, thorns +5 | attack-power +10, thorns +10 |
| `ring_health` | health-regen +0.25 | health-regen +0.5 |
| `ring_mana` | mana-regen +0.25 | mana-regen +0.5 |
| `ring_rejuvenation` | health-regen +0.2, mana-regen +0.2 | health-regen +0.4, mana-regen +0.4 |
| `ring_rejuvenation_greater` | health-regen +0.5, mana-regen +0.5 | health-regen +1, mana-regen +1 |
| `ring_resistances` | fire +5, ice +5, lightning +5, poison +5 | fire +10, ice +10, lightning +10, poison +10 |
| `ring_resistances_greater` | fire +5, ice +5, lightning +5, poison +5 | fire +10, ice +10, lightning +10, poison +10 |
| `rosethorn_wand` | spell-power +5, thorns +5 | spell-power +10, thorns +10 |
| `scroll_earth` | proc damage +10 on 50 | same |
| `scroll_hellfire` | proc damage +20 on 100 | same |
| `scroll_magic_missile` | proc damage +10 on 40, proc damage +10 on 40 (attuned too) | same |
| `scroll_meteor` | proc damage +20 on 100 | same |
| `searing_torch` | proc damage +10 on 50, proc damage +10 on 50 (attuned too) | same |
| `spiked_collar` | thorns +10 | thorns +20 |
| `spiked_pauldrons` | armor +5, thorns +5 | armor +10, thorns +10 |
| `thunderbird_feather` | proc damage +20 on 100 | same |
| `hwp_judgement` | physical +1 | physical +2 |
| `hwp_talisman_of_conflagration` | fire +10 on 40 | same |

"Proc damage +a on b" scales a proc whose damage lives in a projectile or unit file: its
effects get an `intensity-mul` of (b + a x NG) / b, with b the tooltip's damage.

### How
- No overrides. `HWP/Trinkets/NGScaling.as` reads each listed trinket's dict from
  `tweak/trinkets/*.sval`, copies it with the numbers patched and loads its modifiers again
  (`Modifiers::LoadIModifiers` with `SyncVerb::Trinket`, as `Item::Trinket` does). Then it
  rebuilds every player's modifiers. NG+ 0 restores the arrays the game loaded.
- Arctic Step's frost buff is applied by `HWPTrinketNGBuff`, a `Modifiers::Buff` that
  passes an intensity.
- The setting `trinkets.ngp_scaling` (default on) turns it off.
- `hwp trinkets` shows the status; `hwp trinkets show <id>` shows a trinket's tooltips,
  modifier counts and the local max health. `hwp trinkets ng <n>` sets the NG+ level
  (cheats on).

## The HoH1 trinkets (2026-10-26)

37 trinkets from Heroes of Hammerwatch, built from the Trinket Map's "add" verdicts. Ids are
`hwp_<name>`, so `cht_give_specific_trinket hwp_lucky_hat` gives one. Icons are vanilla
`icons_trinkets.png` cells for now. Prices: common 200, uncommon 750, rare 3000, epic 6000.

| Trinket | Quality | Effect | Attuned |
|---|---|---|---|
| Cape of Withdrawal | common | taking damage: +33% move speed for 3 s | 6 s |
| Coated Arrow | common | weapon hits: 20% chance of 15 poison | 40% |
| Defender's Halberd | common | the enemy that hurt you is lightly disarmed (1 s cooldown) | disarmed |
| Gladiator's Net | common | weapon hits: 10% chance to disarm | 20% |
| Lesser Sphere of Time | common | Combo lasts 0.5 s longer | 1 s |
| Pot Helm | common | 10% chance to block a projectile from any side | 20% |
| Circlet of Willpower | uncommon | skills cost 25% less mana below half health | 50% |
| Greaves of the Barbarian | uncommon | a kill: +20% move speed for 3 s | +40% |
| Apothecary's Mortar & Pestle | uncommon | a potion: +50% armor and resistances for 5 s | 10 s |
| Apothecary's Satchel | uncommon | potions heal 50% more | 100% |
| Apothecary's Sphere | uncommon | a potion starts a Combo | and Combo lasts 1 s longer |
| Blowgun | uncommon | casting a spell shoots 3 darts at random enemies (1 s cooldown) | 0.5 s |
| Fancy Plume | uncommon | the dungeon trinket shop stocks 2 more trinkets | and lets you buy 1 more |
| Frying Pan | uncommon | blocks projectiles in a 90 degree arc behind you | 180 degrees |
| Key Ring | uncommon | 50% chance of an extra key with each key found | 100% |
| Lucky Horseshoe | uncommon | +10 Luck, +5% move speed | +20, +10% |
| Pendant of Penance | uncommon | +50% damage while you have a debuff | +100% |
| Seal of the Martyr | uncommon | up to +100% damage the lower your health | +200% |
| Seal of Souls | uncommon | up to +50% damage the lower your mana | +100% |
| Sphere of Time | uncommon | Combo lasts 1 s longer | 2 s |
| Sphere of Warriors | uncommon | Combo needs 2 fewer kills | 4 |
| Talisman of Decay | uncommon | nearby enemies take more damage | the greater aura |
| Elven Ruby | rare | a spell: +50% damage for 3 s (7 s cooldown) | 5 s cooldown |
| Amulet of Vengeance | rare | taking damage: 10% chance to start a Combo | 20% |
| Bloodthirst Ring | rare | weapon damage leeches 2.5% | 5% |
| Golden Lamp | rare | picking up mana summons a Nimbus that zaps enemies for 8 s (8 s cooldown) | 4 s, 2 at once |
| Greater Sphere of Regeneration | rare | +50% health and +75% mana regen in Combo | +100%, +150% |
| Guardian Figurine | rare | hurt below 2/3 health: a guardian appears (12 s cooldown; shares Necromantic Focus's limit of 1) | 8 s |
| Judgement | rare | +12 physical weapon damage; every 7th hit deals 2.5% of the enemy's current health | +24, 5% |
| Seal of Rage | rare | up to +50% attack speed the lower your health | +100% |
| Spreading Corruption | rare | weapon hits corrupt (+30% damage taken, 2.5 s); a corrupted enemy's death corrupts another | +60% |
| Talisman of Conflagration | rare | a kill: 25% chance of a 40 fire explosion | 50% |
| Lucky Hat | rare | +20 Luck | +40 |
| Boots of Freedom | epic | immune to slow | and to immobilize |
| Ring of Arcane Powers | epic | skills cost 25% less mana; a spell has a 10% chance to refill your mana (2 s cooldown) | 20% |
| Sphere of Champions | epic | +30% damage in Combo | +60% |
| Wylmir's Wand | epic | +20% skill speed, no slowdown while casting | +40% |

### Sets

New sets (`tweak/hwp/trinket_sets_hoh1.sval`):

| Set | Pieces | Bonuses |
|---|---|---|
| Charms of Fortune | Lucky Hat, Lucky Horseshoe, Key Ring, Fancy Plume | 2: +5 Luck; 3: +50% all materials; 4: +15 more Luck |
| Disarmament | Defender's Halberd, Gladiator's Net, Frying Pan, Pot Helm | 2: +20% damage to disarmed enemies; 3: +15% parry; 4: block projectiles behind you |
| Plague Doctor | Coated Arrow, Blowgun, Talisman of Decay, Spreading Corruption | 2: +15% poison damage; 3: poisoned enemies near you slowed; 4: and take +10% damage |
| Pyromancer | Talisman of Conflagration, Fire Salts, Cauldron, Searing Torch | 2: +20 fire resistance; 3: burning enemies near you take +10% damage; 4: +10% fire penetration |
| Spheres of Power | the four spheres, Greater Sphere of Regeneration, Amulet of Vengeance | 2: a Combo releases a lesser nova; 3: +25% damage in Combo; 4: a full nova; 5: Combo lasts 1 s longer; 6: you cannot die in Combo |
| Seals of Torment | the three seals | 3: up to +50% skill speed the lower your health |
| Arcanist's Regalia | Circlet of Willpower, Ring of Arcane Powers, Wylmir's Wand | 2: skills cost 10% less; 3: +15% skill speed |
| Conjurer's Relics | Golden Lamp, Guardian Figurine, Necromantic Focus | 2: +20% summon damage; 3: +1 to every summon limit |

Vanilla sets changed (`tweak/hwp/trinket_sets_vanilla.sval`, applied by `HoH1.as` at load):
- Emblems of Hermes gains Cape of Withdrawal and Greaves of the Barbarian: 4 pieces add
  immunity to slow, 5 raise the move speed to +20%.
- Apothecary's Supplies gains the Mortar & Pestle, Satchel and Sphere: 5 pieces give +1
  potion charge, 7 give the Mortar's armor and resistance buff on every potion.
- Trader's Coin also makes the dungeon trinket shop 25% cheaper (50% attuned). The town
  General Merchant sells before a run, where trinkets aren't worn, so it isn't discounted.

### How
- `tweak/hwp/trinkets_hoh1.sval` loads the trinkets (`Item::Trinket::LoadMultiple`) and
  `buffs_trinkets_hoh1.sval` their buffs. `players/hwp/nimbus.unit` is the Golden Lamp's
  Nimbus (a lightning beam, from the priest's celestial light).
- Every set tier lists all of its modifiers, with `merge-set-bonuses` off. The vanilla merge
  copies the already merged lists, so a set with 3 or more tiers would get its lower tiers
  twice.
- `HoH1.as` patches the vanilla sets once at load: `add-items` points the trinkets at the
  set, and tiers are rebuilt with `LoadIModifiers` (`SyncVerb::TrinketSet`).
- Script classes: `HWPTrinketComboKills` (fewer kills for a Combo),
  `HWPTrinketMissingHealthSpeed` (speed from missing health) and `HWPTrinketShopContent`
  (class swap of `TrinketShopShopContent`: Fancy Plume's stock and buys, Trader's Coin's
  prices, 25% at the least). The Key Ring is read by `mods/keys` (`HWPGiveKey.as`).
- `hwp trinkets hoh1` shows the count, the vanilla changes and the local shop and key
  stats; `hwp trinkets set <id>` shows a set's pieces and tiers.

GameLab: `mod-trinkets` (`gamelab/bots/fix_trinkets.py`, sections `trinkets` and `hoh1`).
