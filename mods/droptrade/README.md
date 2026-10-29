# droptrade

Lets players trade equipment. Hovering an inventory item, the key hints at the
bottom read `Equip`, `Compare`, `Destroy`, **`[Q] Drop`**: Drop puts the item on
the ground at your feet for anyone to pick up, with no dialog; Destroy is
vanilla (asks first). The Destroy and Drop hints are also clickable buttons.

Dropping uses `Item::DropItem`, which on a client sends the item to the host;
the host spawns it and replicates it, exactly like loot. The item is removed
from the dropper's inventory right away.

Drop is an hwplib item action (`HWP::ItemActions`, `DropAction`, order 10): hwplib's
inventory shows its hint and polls its key, a raw SDL scancode (default 20 = Q; the
player menu has no free action binding), only while the inventory tab is open and on
top (not behind the destroy confirm) and no text input or chat has the keyboard. The
item leaves the bag before it is dropped, so a stale hover can never spawn a copy.
`hwp dropkey` shows the key, `hwp dropkey 10 G` changes it (per machine).

Other modules' item actions follow Drop, each with its own hint and key: fishing's
**`[F] Eat`** on a fish, the pets' **`[H] Send home`** in a run. Until 2026-10-28 this
mod owned the hints and showed only the first such action, on a fixed E, which is also
the menu's own Destroy key, so one E press ate the fish and opened the destroy dialog.

**Pickup first** (`scripts/HWP/DropTrade/PickupFirst.as`, `HWP::PickupFirst`): the use key
picks up a dropped item before it talks to an NPC or opens a shop, chest or shrine
underfoot. The local player's usables are re-sorted every frame, with items between -1
(revives, exits) and 0 (vanilla puts items at 1, last); `[HWP:droptrade] pickup first`
logs it.

## Settings

On the HammerwatchPlus tab of the player menu:

- **Drop trade** on/off, `droptrade.enabled` (host, default on). Off: no Drop hint or
  key and no pickup first; the other item actions (Eat, Send home) keep working, their
  hints right after Destroy.
- **Drop item key** (option `dropkey`, each player's own): click, then press the key.
  Stored as `droptrade.key` (SDL scancode, default 20 = Q), as `hwp dropkey` does.
- **Pickup first**, `droptrade.pickup_first` (each player's own, default on).

## Overrides

None since 2026-10-28. The inventory's `Character.as` and `EquipmentItemWidget.as`
overrides moved to hwplib (see its README), so every package that registers an item
action has the hints, not only one that carries this mod. `HWP::DropTrade::g_tab`,
`NavText`, `ActionNavText` and `MakeButton` stay for an older package's code.

## Test checklist

1. `python -m gamelab run mod-droptrade --mode lab`: no script errors; the log names the menu's destroy key
   (`[HWP:droptrade] menu destroy key ...`), which must not be Q.
2. Solo: hover an inventory item: hints read Equip / Compare / Destroy / [Q] Drop.
   Q drops it at your feet at once; picking it back up works. Clicking "Drop"
   in the hint bar does the same; clicking "Destroy" opens the vanilla confirm.
3. Co-op: a client drops an item, the host and other clients see it and can
   pick it up; the host drops, clients see it. Equipped items cannot be dropped
   (inventory only, as before).
4. `hwp dropkey 10 G`: the hint reads [G] Drop and G drops.
5. `python -m gamelab run mod-droptrade-pickup --mode lab`: with a Skill Trainer and a
   dropped rifle underfoot, the item is the top usable and Use picks it up.
