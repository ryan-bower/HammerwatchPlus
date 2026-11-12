# Favorite gear (#61)

Part of Quality of Life. Hover a piece of gear in the character screen's bag and
press **F**, or click its **[F] Favorite** hint. The hint becomes **Unfavorite**;
the item's corner shows **F** while sale protection is on. Rebind the key under
Plus > Quality of Life > Favorite gear.

Favorites are absent from the equipment buyer's list. The buyer also checks again
before removing an item or paying gold, so an old shop row cannot sell a favorite
or pay for an item that has already left the bag. Unfavorite it to sell it.
An all-favorite bag explains that favorites are protected and must be unfavorited
in the inventory before selling. An empty bag keeps the buyer's vanilla message.

This protects **selling only**. Equip, unequip, stash, weapon swap, drop and
deliberate Destroy/Salvage retain their existing behavior. Trinkets and materials
are not equipment-buyer items and have no Favorite action.

## Storage

`hwplib` keeps `Item::Item.m_hwpFavorite` on each owned object. Rolled gear and unique
copies are independent, even with identical stats. Vanilla unique definitions are
shared: the library makes an owned copy at `Item::Get` and when a shared definition
enters `EquipmentInventory.Add`. Existing owned objects are not recopied on moves.

SaveData updates `favorites.bag`, `favorites.worn`, and `favorites.stash.<tab>` under
the player/town record's `hwp` dictionary before writing it. Each entry pairs a
slot with its serialized item snapshot. Restoration checks the slot and snapshot
before marking it. Vanilla item payloads are unchanged. Weapon Swap keeps a
separate `<weaponswap.main/off>.favorite` boolean alongside each stored weapon.

Turning the feature off suspends the hints, marker and sale protection, not saved
favorites. Turning it back on restores protection. Removing every HWP package
leaves the items readable in vanilla; vanilla does not retain HWP sidecars when
it rewrites a save. Favorites are local character preferences, not networked item
attributes: a traded item's recipient chooses their own favorites.

## Verification

Source/package contracts: `python -m pytest tests/test_favorites.py`.
These inspect source and metadata, not AngelScript execution.

Controlled engine checks, **not yet run**:

```sh
./gamelab.sh run fix-favorites --mode lab
./gamelab.sh run pkgfeat/pf-fix-favorites --mode lab
./gamelab.sh run mod-all --mode lab
./gamelab.sh run look-favorites --mode lab  # PR screenshot, after readiness passes
```

`fix-favorites` runs 19 assertions through a test-only module: identical rolled and
unique copies, action label, buyer filtering, refused favorite/stale sale without
payment, bag/worn/stash sidecars, disabling, unfavoriting, missing saved slots, and
empty-state text for all-favorite, mixed, empty, disabled and unopened buyers.
It is controlled setup, not UI input or ordinary gameplay evidence.

Live checklist, solo and as each player in a two-player lobby:

- Favorite one of two identical pieces; only the selected piece gets the marker.
- Click Favorite and Unfavorite; press/release F and hold it (one toggle per press).
  Rebind it; typing in chat or the Plus search must not toggle an item.
- Sell an ordinary item: it leaves the bag and pays once. A favorite stays absent
  from the sale list; unfavoriting restores it. Check the all-favorite empty list.
- Equip/unequip, dye, upgrade, reroll, move through stash tabs, sort the stash, swap
  weapons and return the other set to the bag. Save, restart, change floors and
  check the same pieces remain favorites. Check both ordinary and unique gear.
- Disable/re-enable the feature and verify saved flags survive.
- With every item-action module enabled, check the hint bar at the smallest
  supported game resolution. Check keyboard navigation and mouse clicks.

Current blockers: earlier GameLab doctor checks reported Steam not running and
refused symlinked save paths; the latest PR screenshot attempt times out in the
private Wine runtime before doctor completes (180 seconds). `look-favorites`
prepares a bag item and activates the real hint handler before capturing it.
It is written but unrun. Do not bypass readiness gates. No current AngelScript
compile/load, screenshot, click-through, restart or multiplayer pass is claimed.
