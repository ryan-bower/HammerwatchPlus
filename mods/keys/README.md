# keys

HoH1-style locked chests, keys, the exit guard's General Merchant (keys, bag
slots, trinkets for the next run) and red legendaries.

- **Locked chests.** `Chest` is swapped for `HWPChest` (module.json `class_swaps`: `tools/class_units.py` copies the chest units with our class). Every reward chest
  (`items/chests/chest_<bronze|silver|gold>_<trinket|equipment>.unit`, and the
  treasury rooms' `chest_platinum`, which takes a gold key) locks on its first
  tick and needs a key of its own tier; without one it shows a cross and a
  "Needs a Bronze Key" tooltip and does not open. Cursed chests and resource
  caches need no key. A locked chest shows a padlock tinted by tier and pays
  its own vanilla loot. `keys.lock_chance` (default 1) can make it a share;
  the roll is a hash of the chest's position, the mission reward seed and the
  level index, so host and clients agree without a message.
- **"The chest was trapped!!"** (bugs 10.22.26 line 41, `Trapped.as`).
  `HWPChest::Use` calls `HWP::Keys::Trapped::OnChestUse` before the vanilla
  `Chest::Use` destroys the unit: on the host, a cursed chest
  (`items/chests/*cursed*`, the ones whose loot is an ambush) logs
  `trapped chest opened by <name> at x,y` and broadcasts `keys.trapped` with
  the position; every machine within 900 px shows the `hwp_trapped` announce
  (`tweak/hwp/announce_keys.sval`: arial24, mid-screen, 2 s, trip-wire alert
  sound, lang `hwp.keys.trapped`) and logs `trapped chest banner at x,y`;
  farther away it logs `out of range`. If the style failed to load it falls
  back to the vanilla `region_enter` style and logs an error.
- **Ace chests.** 15 % of gold chests (`keys.ace_chance`) become ace chests
  (the art below; red-tinted where there is none) and need an ace key, the
  vanilla skull key tinted red (`items/hwp/keys/key_ace.png`, on the floor, in
  the HUD and at the merchant). Opening one spawns the chest's own loot plus, 50/50
  (`keys.legendary_chance`), either an epic equipment drop or one red
  legendary **per player in the lobby** (instanced through `Item::DropItem`;
  tables in `tweak/hwp/loot_chests_ace.sval`).
  The opener's machine counts its Ace chests in GlobalCache `hwp_keys_aces_opened`
  (it outlives the level; vanilla's `chest-unlocked-<key>` stat is not defined for
  "ace", so `Stats::Add` books nothing), which mods/mmhmm reads.
- **Chest art by area** (`ChestArt.as`, `tweak/hwp/chest_art.sval`, picked in the
  Chest Art Picker). An area is an act of the mission: it changes where a floor's
  act-name (the region banner) changes, so Dark Citadel's forest, dark caves,
  forest, temple, crypt, dungeon, barracks, courts and dark halls are areas 1-9;
  past area 8 the area 8 art is used. Trinket chests (bronze, silver, gold) are the
  plain unused chests in areas 1-3, their own art in 4-5 and the strapped ones
  from 6; cursed chests the blue steel rimmed chest in 1-4 and the large one from
  5; ace trinket chests the gold chest with the red lid in 1-5 and the red and gold
  large one from 6; ace equipment chests the map reward chest. Equipment and
  platinum chests keep their art. `tools/class_units.py` (module.json `scene_art`)
  gives the generated chest units one scene per sprite; `HWPChest` switches to the
  area's on its first tick (log `chest art <unit>: <scene> (area n)`) and to the ace
  one when the chest rolls ace. Every machine counts the area from the mission
  definition, so nothing is sent. `hwp chestart` shows the floor's area; with
  `keys.debug`, `hwp chestart area <n>|off` sets it for chests made afterwards.
- **Party key pool.** Keys found in a run (drops, the imp's offer) go into
  one pool for the whole party, held by the host (`HWP::Keys::g_pool`, kept on
  the host's record so it outlives the level, broadcast as `keys.pool`). Every
  player sees the same counts and anyone can open a chest with them. A new run
  starts with an empty pool, so unspent found keys don't pile up across runs.
- **Own keys.** Keys bought from the General Merchant are the buyer's:
  vanilla `PlayerRecord.GetKeys` and the record's `keys` dictionary, changed
  only through `HWP::Keys::AddKeys/SetKeys`. Vanilla `AddKeys` stores a
  temporary in the dictionary, which the engine keeps by reference, so its
  counts turn to garbage (docs/RE_NOTES.md). A chest takes a party key first,
  then the opener's own; it puts the count back after `Chest::Use` spends the
  key, and level start resets counts outside 0-999.
- **Key budget per floor.** A floor drops fewer keys than its locked chests
  need: per tier, `keys.budget_share` (0.5) of its locked chests, plus
  `keys.budget_per_player` (0.1) per extra player (at most 0.95), the
  fraction rounded by a hash roll, minus the party keys of that tier held when
  the floor started. The killer's machine (`PlayerKilledActor` is local-only)
  sends every elite kill and `keys.normal_try` (4 %) of normal kills as
  candidates (`keys.drop`, flood-guarded at 10 per peer per 10 s); the host
  drops a key for `keys.accept` (40 %) of them while the budget lasts, elites
  taking the highest tier left. The first boss-tagged kill on a level has a
  20 % (`keys.boss_chance`) key drop outside the budget; its tier follows the
  floor's diff-level (up to 7 bronze, up to 13 silver, then gold), and from
  the mission's second-to-last boss on it is an ace key (Bone Serpent and
  Avatar in the Dark Citadel). `hwp keys` shows the pool, the floor's locked
  chests and the budget left per tier.
- **Luck on the floor.** The party's floor Luck (hwplib-luck `HWP::Luck::FloorFactor`)
  multiplies the budget share (still at most 95 %), weighs the budget's higher tiers up
  and multiplies the ace chance (at most 50 %, `HWP::Luck::AceChance`). A client's chest
  waits for the host's floor value (`hwp.luck.floor`) before it rolls its lock. Log
  `[HWP:keys] luck x<f> chest lock <tier>[ (ace chance C%: ace|gold)]`; `hwp keys` shows
  `floor Luck x<f>` after the budget.
- **Imp offer.** `HWPImpKeyEffect` adds "a key" to the vanilla imp's random
  offers (`ImpEffect`), the tier scaled by the floor the same way.
- **General Merchant.** The exit guard by the run start (our copy of
  `actors/npcs/town/npc_misc_guard_exit.unit`, a declared override) opens the
  shop first (`HWPGeneralMerchant`, `HWPMerchantWindow`: the stock
  `ShopWindow` on `gui/hwp_merchant.gui`, with a Keys & Bags / Trinkets tab
  row: click a tab, or press the previous / next tab binding, a gamepad's
  bumpers or Tab on a keyboard, shown beside the row); when it closes,
  NPCBehavior moves on to his vanilla speech bubble. Each key lists the loot
  quality of its chests. Prices `keys.price_<tier>` (500 / 2000 / 8000 /
  20000); only one ace key can be held at a time.
  He also sells **bag slots** (`HWP::BagShop` in this module; the bag size is hwplib's `HWP::Bag`): one more equipment bag slot
  per purchase for the buyer's character, 1000 g rising to 20000 g, up to a
  full extra row (32 slots).
- **Trinkets tab.** Six trinkets per character (2 common, 2 uncommon, 2 rare;
  `Item::GetRandomTrinket`, no repeats; the roll puts back the `m_seen` flags it
  sets) at a run trinket shop's price
  (`GetPrice()` x 1.2, the ShopLevel 1 the dungeon shop rooms use: 240 /
  900 / 3600 g at base prices). A bought trinket is *packed*: the run's setup
  (`ResetForNewMission`) empties the trinket bag, so packed trinkets are
  handed over when the next run's first level starts: straight into the trinket
  bag, locally like every vanilla trinket shop. They don't go through `GiveItem`,
  which would count them in the trinket-found statistics. The stock rerolls after every run; the
  footer shows how many are packed. Stock and packed list are the buyer's own
  HWP save data (`keys.trinket_stock`, `keys.trinket_packed`,
  `keys.trinket_stale`).
- **Legendaries.** `tweak/hwp/legendaries.sval` ports the seven HoH1 red items
  with HoH2 modifiers (meteor on hit, gold and damage bonuses, a slowing gaze
  with melee retaliation, an attack-triggered fireball, invulnerability on
  hurt, kill-same-type, and periodic magic bolts),
  quality `Legendary`, drop-rate 0 so they only come from ace chests.
- All `keys.*` settings are host-authoritative: clients read the host's
  values (hwplib `settings.sync`), so every machine rolls the same locks.
- HUD: left of the bottom bar, one key icon per tier you can use (party pool
  plus your own) with its count, while you can use any.
- Commands: `hwp keys` (counts + settings), `hwp chestart`, `hwp keygive <tier> [n]`,
  `hwp keydrop <tier>` and `hwp chestart area <n>|off` when `keys.debug` is on.

Open decisions: the budget share (`keys.budget_share`), legendary balance and slots,
whether resource caches should want keys too.

- **Luck** (hwplib-luck `HWP::Luck`, `docs/design/luck.md`). `HWPChest::Use` rolls the
  chest's table through `HWP::Luck::SpawnLoot` at the opener's factor, once for the party (the rarer
  entries of each pool weigh more; the table is taken off the behaviour around
  `Chest::Use` and put back), which covers every reward chest, cache and puzzle
  room reward. A kill's boss key chance and the normal-kill candidate share use the
  killer's factor, the host's accept roll the party's (`HWP::Luck::Chance`, capped
  at 1). Logs: `[HWP:keys] luck x<f> chest <key|open> loot`, `... boss key roll`,
  `... <elite|normal> kill drop candidate`, `... candidate accept roll`.

## Settings

On the HammerwatchPlus tab of the player menu (`hwp set <key> <value>`; `module.json`
`config`). All host-authoritative.

- `keys.enabled` (on): the switch. Off: chests don't lock and keep their vanilla art (from
  the next level: a chest decides when it first ticks), no key drops or imp keys, no
  trapped-chest banner, the exit guard only talks (`HWPGeneralMerchant.CanInteract`), no
  `hwp bag buy`, and the key HUD hides (unless a chest on this floor locked while it was
  on; such a chest still opens with a key). Keys, the party pool, bag slots and packed
  trinkets stay as they are; packed trinkets are still handed over at the next run.
- `keys.lock_chance` (1), `keys.budget_share` (0.5), `keys.ace_chance` (0.15),
  `keys.legendary_chance` (0.5), `keys.boss_chance` (0.2).
- `keys.price_bronze`/`_silver`/`_gold`/`_ace` (500 / 2000 / 8000 / 20000 g).
- Not on the page: `keys.budget_per_player`, `keys.normal_try`, `keys.accept` (tuning) and
  `keys.debug`.

## Test checklist

1. `python -m gamelab run mod-keys --mode lab`: no script errors, `Making Module hwp-keys`, lang check OK.
2. Town: talking to the exit guard by the run start opens the key shop: four
   keys, each subtitled with its loot quality; buying a bronze key deducts
   gold, logs the pickup and a bronze key icon appears left of the bottom bar. Closing the shop
   shows his speech bubble.
   The fifth entry, Bag Slot, shows your bag size; buying it adds an empty
   slot (the fourth inventory row fills) and the price rises; at 32 slots it
   is greyed out. `hwp bag` shows the same.
   `python -m gamelab run mod-merchant-trinkets --mode lab` covers the tabs:
   Trinkets lists 6 (2/2/2), two bought are packed (not in the run bag in
   town), both are in the run bag on the first floor, and after the run the
   stock rerolls to 6. `fix-merchant-controller-tabs` switches the tabs with a
   gamepad's bumpers (GameLab's `menubutton`) and the real Tab key, buys a
   trinket with A, and still clicks a tab with the mouse.
3. `hwp set keys.debug 1`, `hwp keygive gold 2`, `hwp keygive ace`: HUD
   updates; `hwp keydrop silver` drops a pickup that, walked over in a run,
   adds a silver key to the party pool (host and client see it).
   `python -m gamelab run mod-keys-pool --mode lab` covers the pool, the
   budget report and a chest opened with a party key.
4. Run: every reward chest has a padlock; without the key the use icon is a
   cross, the tooltip names the key and the chest does not open; with the key
   the padlock vanishes, the key count drops, the chest's own loot spawns.
   Cursed chests and caches open without a key.
5. `hwp set keys.ace_chance 1`: gold chests are red; opening with an ace key
   gives everyone a legendary or an epic; the legendary tooltip is red.
6. Kill elites: keys drop until the floor's budget (`hwp keys`) is spent. `hwp set keys.boss_chance 1`, kill a
   boss: one key of the floor's tier (ace on the Bone Serpent / Avatar).
   Talk to imps until one hands over a key of the floor's tier.
7. Co-op: the client sees the same chests locked as the host; client kills
   drop keys the host spawned into the shared pool; either player can open a
   chest with a party key, and the client with their own bought key.
8. Disable the module: vanilla saves still load, keys remain in the record.
9. `python -m gamelab run fix-map-trapped --mode lab`: a cursed chest beside the
   player logs the opening and the banner (shot `trapped-banner`), one 1500 px
   away logs `out of range` without a banner, a plain chest logs nothing.
   Co-op: the client near the chest sees the banner too.
10. `python -m gamelab run fix-core-luck --mode lab`: a spawned cache used at 60 Luck
   logs `[HWP:keys] luck x1.6 chest open loot` and `[HWP:luck] loot chest factor 1.6`.
