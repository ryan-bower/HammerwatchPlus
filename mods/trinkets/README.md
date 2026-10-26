# Trinket NG+ Scaling

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

"Proc damage +a on b" scales a proc whose damage lives in a projectile or unit file: its
effects get an `intensity-mul` of (b + a x NG) / b, with b the tooltip's damage.

## How
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

GameLab: `mod-trinkets` (`gamelab/bots/fix_trinkets.py`).
