# goldworth

Gold on the floor shows what it is worth: the bronze, silver and gold coins and piles of
`items/misc/base.png`, by amount. Data only (one override, no scripts).

## How it works

A gold pickup (`items/materials/gold.unit`, `Material::MaterialPickup`) picks its look

from the unit's `sets` array when it is dropped: the last entry whose amount is at most

the pickup's. Vanilla has five looks (one coin, 2-5 coins, and three gold piles). This

module's copy uses all 15 coin sprites of `items/misc/base.png`, so the floor shows what a pickup

is worth:



| Metal | Coin | Pile 1 | Pile 2 | Pile 3 | Pile 4 |

|---|---|---|---|---|---|

| Bronze | 1-4 | 5-9 | 10-14 | 15-19 | 20-24 |

| Silver | 25-49 | 50-74 | 75-99 | 100-149 | 150-199 |

| Gold | 200-249 | 250-299 | 300-349 | 350-399 | 400+ |



Silver glints white (`material_reflection.effect`, at 0.8 the strength of the gold glint

because the white flare reads brighter); bronze and gold glint orange as vanilla. The

amount is the dropped one: gold gain (trinkets, gear, NG+) is applied when the gold is

picked up, so it never moves the sprite. The thresholds sit where real drops land: one

wall-pile piece is mostly 1-12 (up to 375 on the biggest expert piles), boxes and barrels

5-35, chests 20-300, platinum chests 200-400, a floor reward of gold up to about 340, and

the modded strongbox and abyss drops up to 450. Nothing drops 1000 at once, which is why

silver and gold start at 25 and 200. To change them, edit the `sets` array (and keep the

scene names). `gold.unit.orig` is the base file for `build.py --check`.

`gamelab/scenarios/fix-gold-sprites.json` drops each threshold and the amounts just under

them and checks the scene (`gl near` reports a unit's scene and a pickup's amount).

## Settings

None, and no on/off switch on the settings page: the module is data only (the gold pickup's
looks), so it is on whenever it is installed.

## Test checklist

1. `python -m gamelab run fix-gold-sprites --mode lab`: each of the 15 thresholds shows its
   scene, amounts just under one take the tier below, a pickup still pays.
2. In a run, smash a wall pile (bronze), open a chest (silver) and a platinum chest (gold).
