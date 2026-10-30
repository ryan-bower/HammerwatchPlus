# fishing

Fishing along the town's coast, a pirate who sells bait, rods and fish traps,
fishing spots in the water of run floors' potion wells (always one in a boss room),
and fish that sell for the Gambler's bet tokens (for gold without the gambler) or fight as swords. With the
keys module, a catch can bring up a key of any tier, ace keys included.

- **Coast spots.** Six `doodads/hwp/fishing_spot.unit` along the town's west
  coast (the `water_coastline` pieces of `prefabs/town/segments/base.lvl`).
  Every machine spawns its own copies (`netsync="none"`), so each player fishes
  locally. A spot shows only its two swimming fish; the rod sprite that stood on
  the sand went on 2026-10-22 (the user's call), the rod stays as the interact
  icon. Interacting opens the minigame: **Cast** (costs one of the bait on
  your hook; the **Bait** button cycles the kinds you have), wait
  0.8-3 s for a bite, then press **Reel** (button, Enter or gamepad confirm)
  while the sweeping marker is inside the green zone. The zone shrinks and the
  marker speeds up with the fish tier: 40 / 26 / 16 / 10 px of the 240 px
  bar, 0.18 / 0.23 / 0.28 / 0.34 px per ms; the marker counts as soon as it
  touches the zone. **A bite takes several hits** (issue #32): 2 for a 1-star
  fish (tiers 1-2), 3 for 2-star, 4 for 3-star (`REEL_HITS`). After each hit but
  the last the fish fights: the zone jumps at least 24 px clear of the marker,
  the marker gets 15 % faster and the 2.5 s window starts again. A miss, or a
  window running out, at any hit loses the fish ("It fought free and got away").
  The speed-up stops where one ~33 ms game tick would carry the marker past
  90 % of the zone plus its own width: Reel reads the marker where the last
  tick left it, so a faster marker could step over the zone on every pass. The
  3-star fish is already there (11 px a tick past a 10 px zone), so it gets
  only x1.04; the fewer, harder hits are its challenge. Each hit logs
  `reel: hit H of N (tier T), zone to X, marker xM` and the end `reel:
  landed|missed|too slow at hit H of N (tier T)`. `fishing.reel_hits` 1-4
  sets one count for every fish (1 is the old single press). It is drawn every frame between game ticks at sub-pixel
  positions, so it glides instead of stepping. The window pauses the game, and
  a paused game renders every frame with a sub-tick time of 0
  (`AGameplayGameMode.RenderFrame`), so until 2026-10-25 the marker only moved
  once per ~33 ms game tick (11 px at a time for a 3-star fish, worst in boss
  rooms where every fish is one). No script clock runs while paused, so the
  frames the previous tick got stand in: the k-th frame of a tick draws the
  marker k / (frames last tick) of the way to its next position, and the real
  sub-tick time is used whenever the engine gives one. `hwp fishing smooth`
  reports the last bite's motion per frame (frames, ticks, mean step, its
  coefficient of variation, the share of frames it stood still, bounce frames
  skipped); `hwp fishing tier <n>` (debug) forces the coast's next bite tier.
  Luck (hwplib-luck `HWP::Luck::OpenerFactor`, 1 + luck/100, as the fisher's machine
  reported it) widens the 2- and 3-star bands of every roll (coast, traps, holes). The
  party's average Luck multiplies a floor's hole chance (`HWP::Luck::FloorFactor`; log
  `[HWP:fishing] run hole chance C% (B% at party Luck x<f>): ...`).
- **Fish are swords.** The catch goes into your bag (or drops at your feet when
  the bag is full) as `hwp_fish_<id>` from `tweak/hwp/fishing_items.sval`: a
  main-hand weapon that swings like the longsword (`attack_swing_longsword`,
  Perch 28-34 up to Abyssal Eel 50-60 physical), excluded from random loot.
  It carries the `mods_weapon_mainhand(_melee)` tags, so the enchanter can
  upgrade it (commons) and enchant it (uncommon and rare fish) like any
  weapon. A 2-star (uncommon) fish is caught with one modifier and a 3-star
  (rare) one with two, rolled like dropped gear of that quality and level
  (`Equipment::Generator.GenerateItemMods`); the enchanter needs them (it reads
  the quality's modifier slots and broke on a 2/3-star fish without any).
  1-star fish have none. Its **item level** is set where it was caught: town
  fish are ilvl 1 / 5 / 10 / 15 by tier (1-star fish 1-5); a run catch uses the
  floor's drop level (`g_diffLevel`, which includes NG+, +-1, capped at your
  drop level cap), like gear.
- **Stars and bet tokens.** Fish are 1, 2 or 3 star (tiers 1-2, 3, 4) and sell
  for 1 / 3 / 5 **bet tokens** (`HWP::Market` token price; the pirate's Sell
  button, `hwp fishing sell`, the Gambler's Sell button or `hwp sell`). The tokens are the
  gambler's (hwplib's market currency); without the gambler each fish sells for its own gold
  price (`AddFish`) and the pirate says so. Only
  unworked fish in the bag sell: each catch stores its signature (base id,
  item level, quality, modifiers in order) in your HWP save data
  (`market_sigs`, hwplib `HWP::Market::Remember`); enchanting, upgrading or
  rerolling a fish changes it, so it stays in the bag as gear. 1-star fish with
  no modifiers always count. Older saves: 2/3-star fish caught without
  modifiers get them rolled (and stay wares) the first time you are in town.
  The Gambler rerolls gear for 1 token per 5 item levels. Town water only has
  1-star fish; star fish (2+) bite only in the second half of a run's floors,
  and boss rooms have only 3-star fish. The host announces each catch.
- **Keys.** With the keys module a catch can bring a key up with the fish:
  `tweak/hwp/fishing_keys.sval` (read with `Resources::GetSValue`, built-in
  fallback in `FishingModule.as`) gives the chance per catch by fish tier,
  20 / 40 / 80 / 150 per mille (tiers 1-4), and the key's tier shares per fish
  tier, bronze / silver / gold / ace per mille: 850/130/18/2 (tier 1),
  700/240/50/10 (tier 2), 450/380/140/30 (tier 3), 200/400/300/100 (tier 4): a
  boss-room catch is a key 15 % of the time and one key in ten there is an ace.
  Luck multiplies the chance and the gold and ace shares. A coast catch or a
  trap fish rolls on the fisher's machine and the key goes into the character's
  own keys (the record's `keys`, stored like the keys module does; the keys HUD
  picks it up within half a second); a hole catch rolls on the host, which drops
  the keys module's pickup at the fisher's feet (global + secure: picked once,
  into the party pool) and tells the catcher. Without the keys module no key
  unit exists and nothing is rolled. `fishing.keys 0` turns it off;
  `fishing.key_chance <0-1000>` overrides the chance for every catch and
  `fishing.key_tier <1-4>` forces the tier (tests); `hwp fishing keys` shows
  the odds and your own keys.
- **A hole's loot is the fisher's alone.** `Item::LootTable.SpawnLoot` drops
  every instanced entry (gear, trinkets) once per player in the lobby, as a
  chest does, so until 2026-10-25 one player's catch gave everyone gear.
  `HWP::Fishing::SpawnCatchLoot` rolls the table through
  `HWP::Luck::SpawnLootFor(..., personal)` at factor 1 and spawns each rolled
  entry for the catcher only: gear and trinkets owned by them (an owned
  `Item::DropItem`, sent to a client catcher the way chests do), gold,
  valuables and pickups a shared pile at their feet. Shared entries drop
  through the host's own record, since vanilla drops a shared item only for a
  local looter on the server (until 2026-10-26 a client's catch lost them). Logged as `caught tier N (M casts
  left): loot for them alone, K drop(s)`.
- **Fish traps.** The pirate sells up to 3 (500 / 1000 / 2000 g). They sit in
  the water off three of the coast spots (`fish_trap.unit`, `fish_trap_full.unit` with a fish
  and a map icon once something is inside). The time you spend on a run is
  counted (`fishing.run_ms`, flushed every 5 s); back in town every 10 minutes
  of it gives each trap a 50 % chance of +1 fish, up to 3 per trap. Walk up
  to a trap to empty it into your bag; each fish taken out rolls for a key like
  a coast catch. `hwp fishing traps` lists them.
- **Rods.** Per character (`fishing.rod` in your HWP save data). Every
  character starts with the Driftwood Rod: the first look at a character's
  save data (`fishing.rod_v` below 2, so a new character, or one saved before
  2026-10-25 whether it had a rod or not) puts it there once and logs
  `starts with the Driftwood Rod`; `hwp fishing rod 0` (debug) is the only way
  to have none, then the slot is empty and Cast says to buy one. The pirate
  sells the next rod: Sturdy 1000 g, Sea 5000 g, Captain's 25000 g (until
  2026-10-25 Driftwood 100, Sturdy 400, Sea 1200, Captain's 3000; Driftwood is
  free now and never offered unless the debug command took it away).
  Each tier past Driftwood widens the catch
  zone by 20 %, slows the marker by 10 % and raises the odds of rare and epic
  fish. The rod shows in the character screen's gear grid (hwplib
  `hwp-gear-rod` slot) with its bonuses and your bait, in its tier's colour
  (`gui/hwp/rods.png`: grey driftwood, brown sturdy, teal sea, gold and red
  captain's). Debug: `hwp fishing rod <tier>`.
- **The pirate fisherman** (`doodads/hwp/pirate_fisher.unit`, interact class
  `HWPPirateShop`) sits on the half-buried boat next to the trading post's
  "Trade materials" NPC and talks like a pirate. He sells worms (5 for 50 g,
  20 for 180 g), shrimp (5 for 400 g), glow squid (3 for 900 g) and the next
  rod (Sturdy, Sea, Captain's). The bait decides the coast's star range: worms 1-2, shrimp 2-3, squid
  3-4 (`BAIT_MIN_TIER`/`BAIT_MAX_TIER`); the rod's bonuses roll within it.
  Each kind is a cell in the materials tab's Supplies section (hwplib `HWP::Materials`
  section a, after the gambler's tokens) with a tooltip.
  At trading post tier 3 (its last) the wreck becomes a whole boat and he stands
  in it (`ON_BOAT_X/Y`, 2 px below the boat's origin in that tier's prefab: the hull is
  drawn sorted by that origin and would hide him any higher up). His
  spot is taken from the material trader's position; a building upgrade rebuilds the
  town and removes him, so the coast is placed again within a second.
  `hwp set fishing.pirate_x/y` put him anywhere. He has an anchor merchant
  icon on the map (`gui/hwp/map_pirate.png`).
- **Run spots.** On `fishing.run_chance` % of floors (default 30) the host
  places `fishing_hole_well.unit` on one of the floor's potion-refill wells,
  with its fish swimming in the well's water (levels have no reachable open
  water). Only a well with room to stand beside it is used. The unit has one
  scene per well kind (`WELL_KIND`: well, dark halls, barrel, crypt, fountain).
  While the well can still refill potions, using it refills first
  (`HWPFishingHoleNPC` usable priority 1). Its water stays in the spot once the
  well is drained. A boss room always gets one: at its well, or a fishing bucket
  (`fishing_bucket.unit`, a small fish in the bucket) beside the host when it
  has none. Once a player has used all their casts on the floor, the spot shows
  no fish and its map icon greys out, as a used well's does. Each machine does
  this for its own player, `WatchHoles`. No bait is needed. Each player gets `fishing.run_casts`
  (3) casts per floor: casting asks the host (`fishing.cast` with the rod
  tier), who counts the cast, rolls the tier within the floor's star range and
  answers `fishing.bite` or `fishing.denied`. Reeling in sends
  `fishing.catch`: the host spawns `hwp_fishing_run_<tier>` loot for the catcher
  alone (`SpawnCatchLoot`), maybe a key pickup, and sends the catcher
  `fishing.landed` (fish + item level + key tier) for the fish itself.
- Fishing spots, holes and full traps show a fish icon on the minimap
  (`gui/hwp/map_icons.png` from hwplib, made by `tools/make_map_icons.py`).
- `fishing.*` settings are host-synced; `fishing.coast 0` removes the coast
  spots and the pirate. `hwp fishing buy bait|bait20|shrimp|squid|rod|trap` buys from the
  console; `hwp fishing keys` and `hwp fishing smooth` report (above). With `fishing.debug 1`: `hwp fishing hole` (host), `hwp fishing wells`
  (host, in a run: every well kind with a spot in it, plus a bucket), `hwp fishing
  catch [tier]` (rolls a key too: own key in town, a pickup on a run when host), `hwp fishing bait <worm|shrimp|squid> [n]`, `hwp fishing traps <minutes>` (fill
  the traps as if back from a run that long), `hwp fishing tier <n>` (the coast's next bite tier).

- **Eat** (hwplib item action `EatAction`, order 20): a fish in the bag shows **`[F] Eat`**; F or a
  click eats it (100 health per star, town or run, the fish is used up). The key is each player's
  own, rebound on the Plus tab (**Eat fish key**, option `eatkey`, setting `fishing.eat_key`, SDL
  scancode, default 9 = F). It was a fixed E before 2026-10-28, which is also the menu's Destroy key.
- **Luck from a meal.** Eating a fish (`EatFish`: the bag's Eat hint, `hwp fish eat`)
  also gives the Luck buff (hwplib-luck) for 10 minutes, +5 Luck a star
  (`HWP::Luck::GiveBuff`, `docs/design/luck.md`), refreshed by the next meal. Log:
  `[HWP:luck] buff +N for 600000 ms (ate <fish>)`.

## Settings

On the HammerwatchPlus tab of the player menu (`config` in module.json), host-synced:
`fishing.enabled` (the module), `fishing.coast`, `fishing.run_chance` (from the next
level), `fishing.run_casts`, `fishing.reel_hits` (hits to land: 0 by fish, 2-4; or 1-4 for
every fish), `fishing.keys`.

`fishing.enabled 0` takes effect at once: the coast spots, the crab traps and the pirate
go away in town, and on a run the host removes the holes and buckets. Casting, catches,
eating a fish and the `hwp fishing` commands stop (the status line, `smooth` and `keys`
still answer). From the next level the rod slot and the bait cells are hidden. The rod,
bait, traps and fish stay in the save data. Turning it back on in town lays the coast out
again.

## Test checklist

1. `python -m gamelab run mod-fishing --mode lab`: `[HWP:fishing] self-check done: 8 fish, 0 missing items`, no
   script issues.
2. Town: six rod + fish spots along the west beach, the pirate on the boat by
   the trading post. `hwp fishing` shows the spot count and his position.
3. Pirate: greeting in pirate speak, buy bait (gold drops, bait rises), buy a
   rod with too little gold (refused), then with enough. Status updates live.
4. Coast cast without bait: refused. The Bait button cycles worms / shrimp /
   squid (only kinds you have); squid catches only 3-4 star fish. With bait: the marker sweeps the bar
   (it moves), a hit puts the fish in your bag, a miss says "It got away"; each
   cast costs one bait. Full bag: the fish drops on the ground.
5. Equip a fish: it swings like a sword; its tooltip shows the item level.
   Take an uncommon fish to the enchanter: upgrade and enchant work (Enchant
   lists the modifiers your town has blueprints for), also on a fresh 2/3-star
   fish. Sell fish at the pirate, the Gambler and with `hwp sell`: they leave
   the bag and the bet tokens rise by 1 / 3 / 5 per star; an enchanted or
   upgraded fish stays.
6. Character screen: the rod slot (bottom left of the 3x3 gear grid) shows the
   rod's name, bonuses and bait in its tooltip. A brand-new character already
   has the Driftwood Rod there (`fix-fishing-starter-rod`: the status line, the
   `starts with the Driftwood Rod` log line, the pirate's Sturdy 1000 / Sea
   5000 / Captain's 25000 g captions and the gold a purchase takes).
7. 2-player lobby: both see their own spots and pirate; a catch is announced
   to the other player. **Manual (cannot be automated solo):** on a run both
   players stand at one hole; one reels a 3-star catch (boss room, or
   `fishing.key_chance 1000` and a well spot). Only the catcher sees the gear
   drop and only they can pick it up; the other player gets nothing on the
   ground (before 2026-10-25 both got a piece). A client catcher gets their gear
   too (the host drops it owned by them). A key pickup from a hole can be
   taken by either and lands in the party pool (`hwp keys`).
8. Run: a fishing spot in a well's water on some floors (fish icon on the map);
   catch 3 times -> loot and a fish of the floor's item level, the 4th cast is
   refused. First-half floors give 1-star fish only, boss rooms 3-star only
   (at the well or a bucket). A client gets the refusal as a chat line. Once
   the casts are used up, the spot has no fish and its map icon is greyed.
   `hwp fishing wells`: a fish sits in each kind of well's water and in the
   bucket. `mod-fishing-spots` measures this, and the pirate on the wreck at
   trading post tier 1 and in the boat at tier 3.
9. Traps: buy 1-3 at the pirate (prices rise, 4th refused); after a run of
   20+ minutes some traps show a fish; walk up to one: its fish go to the bag.
   `fishing.debug 1`, `hwp fishing traps 60` fills them without a run.
10. `hwp set fishing.enabled 0` in town: the coast spots, traps and pirate go
    (`turned off` in the log), `hwp fishing buy bait` says fishing is off; on a
    run the host's holes and buckets go. `hwp set fishing.enabled 1`: the coast
    is back, and so are the rod and bait after the next level.
11. Keys (`fix-fishing-keys`, mods hwplib, hwplib-luck, fishing, keys): `hwp fishing keys`
    lists the odds from `fishing_keys.sval`; with `fishing.key_chance 1000` and
    `fishing.key_tier 4` a debug catch in town adds an ace key to your own keys
    (`keys: ... ace 1`, the keys HUD shows it); with `key_tier 0` twenty catches
    give twenty keys over the four tiers; a filled trap's fish give keys when
    collected; on a run the host's catch drops a key pickup
    (`items/hwp/keys/key_*.unit` near the player) and logs `key: a <tier> key`.
12. Marker smoothness (`fix-fishing-smooth`): a forced 3-star coast bite left
    to run out; `hwp fishing smooth` reports at least 20 frames, a stall share
    under 25 % and a step coefficient of variation under 0.5. The lab renders at
    about one frame per game tick, where even the old code never stalled, so the
    bound is only discriminating where the frame rate exceeds the tick rate; the
    eye test is the user's game (fast fish, boss room).
13. Personal loot (`fix-fishing-personal-loot`, solo): a hole catch logs `loot
    for them alone, K drop(s)` with K equal to the table's pool count and
    exactly those item units appear near the player. The co-op half is step 7.
14. Several hits (`fix-fishing-reel-hits`): forced coast bites reeled through the
    window's own bar (gl sweepclick reading the `marker` widget): tier 4 lands on
    the 4th click, tier 1 on the 2nd, tier 3 on the 3rd with the marker x1.15
    then x1.32 and the zone moved each time; the 3-star fish stays at x1.04; a
    miss at the 2nd of 3 loses it; `fishing.reel_hits 1` lands on one click. By
    hand: a 3-star fish in a boss room should feel hard but fair.
