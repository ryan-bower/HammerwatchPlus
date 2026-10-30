# salvage

Destroy becomes Salvage (issue #66). Destroying a piece of gear used to give nothing.
Now it gives the Enchanter's materials, more the higher the item's level, and the confirm
says how many.

- **Where:** the bag in the character screen (third hint, MenuAdditional), and the town
  stash's worn, bag and stashed items. Both go through hwplib's
  `HWP::ItemActions::DestroyHandler`. hwplib overrides `PlayerStashWindow.as` and
  `StashItemWidget.as` for the stash.
- **Material:** Crystals for Common and Uncommon gear, Dust for Rare and up. That is the
  split the Enchanter uses: Crystals upgrade Common gear, Dust everything else.
- **Amount:** a base of Common 1 Crystal, Uncommon 3, Rare 1 Dust, Epic 3, Legendary and
  Unique 5. The base is the vanilla trinket conversion at a mission's end. It is multiplied
  by `1 + item level / 10` (upgrades count) and by `salvage.yield`%, then rounded, with a
  minimum of 1.
  - Examples: a Common ilvl 1 gives 1 Crystal, a Rare ilvl 20 gives 3 Dust, and an Epic
    ilvl 30 gives 12 Dust.
  - A Rare ilvl 20 gives about a quarter of the 11 Dust the Enchanter asks to raise its
    quality.
- **Where the materials go:** in town they go straight to the town. In a run they are
  carried like picked-up materials: banked at the mission's end, with part of them lost
  on a failed run (`PlayerRecord.GiveMaterial`). Gain modifiers don't apply, so the
  amount is what the confirm says.
- `hwp salvage` lists what each bag item salvages into, plus your Crystals and Dust.

## Settings

On the HammerwatchPlus tab (Quality of Life > Salvage), host:

- `salvage.enabled` (on): off brings back the vanilla Destroy, which gives nothing.
  Applies at once.
- `salvage.yield` (100%): 50, 75, 100, 150 or 200% of the amounts above.

## Test checklist

1. `python -m gamelab run fix-salvage --mode lab` (bag, settings and stash), and
   `pkgfeat/pf-fix-salvage` against the built qol package.
2. In town, open the character screen. A bag item's hint reads Salvage, and the confirm
   names the yield. Yes removes the item, and the town's Crystals or Dust go up by that
   amount.
3. In a run, salvage an item. A pickup text shows the yield, and it is banked at the
   mission's end.
