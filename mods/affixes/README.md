# affixes

Rare and Epic items can roll a second suffix, and Epic items a second prefix (issue #17).

- **How vanilla rolls mods.** An item's modifiers come in tiers, one per quality
  step (`Equipment::Generator.GenerateItemMods`): an Uncommon item gets one from
  the common pool (a stat mod), a Rare one also one from the rare pool
  (`tweak/items/modifiers_equipment_rare.sval`, 58 mods, every one a suffix:
  "of Vengeance"), an Epic one also one from the epic pool
  (`modifiers_equipment_epic.sval`, 27 mods, every one a prefix: "Purging").
  So an item never has two suffixes or two prefixes. Legendary items keep no
  modifiers at all (`Item.Finalize`).
- **What changes.** After a Rare or Epic item's vanilla tiers are rolled, the
  rare tier and the epic tier each roll a second mod, `affixes.chance` (25)
  percent each. A Rare item can get a second suffix; an Epic one a second
  suffix, a second prefix, or both (up to 5 mods). The extra comes from the
  same pool with the same weights, item level and exclusive groups, never a mod
  the item already has, and never a second skill.
- **Where.** Every generated item: drops, chests, shop stock, quest rewards,
  rerolls. The module overrides `scripts/Items/EquipmentGenerator.as` (three
  lines, marked `HWP affixes`), since the generator has no hook. An item that
  already has its mods (a saved one) is left alone.
- **What stays vanilla.** The item's name shows one prefix and one suffix as
  before; the extras are in its tooltip. They are ordinary modifiers: saved
  with the item, counted in its price, and kept when the module is turned off
  or removed.

`hwp affixes` shows the setting and this session's counts; `hwp affixes roll
<n> [rare|epic] [ilvl]` rolls n items through the generator and counts what
they got (nothing is kept); `hwp affixes bag` lists your worn and carried
items' tiers; `hwp affixes give` (cheats) puts an Epic chest piece with both
extras in the bag.

## Settings

On the HammerwatchPlus tab of the player menu (host, host-synced), or `hwp set`:

- `affixes.enabled` (on): off rolls vanilla items from then on. Items that
  already have extras keep them.
- `affixes.chance` (25; the page offers 10, 25, 50, 75, 100; `hwp set` takes
  0-100): the chance per tier.

## Test checklist

1. `python -m gamelab run mod-affixes --mode lab`: `[HWP:affixes] self-check
   done: on, 25% per tier`; 400 Epic items at item level 30 get about 100
   second suffixes and 100 second prefixes, 400 Rare about 100 suffixes and no
   prefix, no item has a mod twice, a tier over two or two skills; at 100%
   every Epic gets both (also at item level 1); off gives vanilla items (3
   mods at most); `give` adds a 5-mod Epic chest piece whose tooltip lists all
   five; after a save and restart it still has 2 suffixes and 2 prefixes.
2. In a run, open Rare and Epic loot: about one in four shows an extra line in
   the tooltip, and the shop's Rare and Epic stock too.
3. Turn the module off: those items keep their extras.
