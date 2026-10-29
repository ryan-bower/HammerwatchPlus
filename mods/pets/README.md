# pets

Pet progression, pet skills, per-pet pickup toggles and every Heroes of
Hammerwatch 1 pet skin in the HoH2 Pet Shop. Pets keep out of puzzle and trap
rooms through `mods/petrooms` (a shared module: this package carries it, and so
does Quality of Life); the pet classes here are `HWP::PetWait::Owned` and run its
Watcher in their own Update.

- **Pet classes.** `module.json` `class_swaps` puts `HWPMiniPetWalking` and
  `HWPMiniPetFlying` (`scripts/HWP/Pets/PetClasses.as`) into copies of the
  vanilla pet units (`tools/class_units.py`; the engine ignores info.xml
  classmaps), and `tools/import_hoh1.py pets` (and again `tools/make_pet_dyes.py`,
  whose `--verify` flags a HoH1 unit left on a vanilla class) into the HoH1 pet units, so
  every vanilla and imported pet gets the wait watcher, the owner's pickup
  toggles, the Fetch passives, the skill runner and XP per pickup. Pets are not
  netsynced: like vanilla, only the owner's copy picks up or acts.
- **HoH1 pets.** `python tools/import_hoh1.py pets` reads the player's own HoH1
  install and writes (gitignored) `players/pets/hwp/*.unit|.png`,
  `gui/hwp/icons_pets_hoh1.png` and `tweak/hwp/pets_hoh1.sval` (22 `PetDef`s,
  ids `hwp_pet_<skin>`, costs 2500-15000 like vanilla pets). The vanilla Pet
  Shop lists every `PetDef`, so they are bought and selected there. Units are
  rewritten for HoH2 (texture paths, pickup ranges, 1.4x speed; the living
  flame's missing textures are substituted). Names live in `hwp_pets.lang`.
- **Progress** is per pet definition in the owner's own PlayerRecord
  (`HWP::SaveData::Player`, keys `pets.<petId>.xp|lvl|<skill>`). XP: owner's
  kills (hook `PlayerKilledActor`: 5, elite 25, boss 150), pet pickups (2),
  feeding food crops at the **Pet Shop keeper** (2026-10-25: class swap
  `PetsShopContent` -> `HWPPetShopContent`, `actors/npcs/town/npc_pets.unit`
  via `tools/class_units.py`). With a pet out the keeper asks **Buy a pet /
  Train your pet** (`gui/hwp_pet_shop_choice.gui`, the pet's status on it);
  Train opens the progression menu (`gui/hwp_pets.gui`: skills, feeding, pickup
  toggles) that used to be the feeding bowl's; without a pet the vanilla shop
  opens directly. The bowl doodad (`doodads/hwp/pet_bowl.unit`, class
  `HWPPetBowl`, same menu) is optional now: `pets.bowl` (default off) or
  `hwp pet here` on the host places it at `pets.bowl_x/y`. Level cap 20, one
  skill point per level past 1. Numbers: `tweak/hwp/pet_skills.sval`.
- **Pet level in the inventory** (2026-10-25, `scripts/HWP/Pets/PetLevelTab.as`):
  the character tab shows `pet lvl N (xx%)` just left of the character's own
  `lvl N (xx%)`. No override of `GUI/PlayerMenu/Character.as` (droptrade owns it):
  each frame the module finds the open `PlayerMenu` whose current tab is the
  character tab, clones its `player-level` text once as `hwp-pet-level` into the
  same row (its tooltip button hidden) and keeps text and offset current; hidden
  without a pet. `gl menu character - hwp-pet-level` reads it (the tab has its own
  widget tree; `gl wtext` sees only the window's).
- **Skills** (ranks 1-5, family 1-3): Hazard Clearer (vines), Smash
  (breakables), Stun (normal enemies only; stun_minor/stun/stun_greater),
  Mend (owner heal under 80 %), Fetch (passive ranges + speed, applied on
  respawn), Morale (owner speed buff out of combat,
  `tweak/hwp/buffs_pets.sval`), Family: wyrm fire breath on hazards, raven
  spots chests, scarab bonus gold per gold pickup, imp fire bolt on stunned
  targets, cat stronger Mend, dog stronger Morale, squire more Fetch, candle Secret
  Sense: each secret entrance (`_secret_dst_` wall tiles, grouped within 64 px)
  is rolled once per floor at 3/6/10% by rank; near a lit one the candle
  hovers by the wall and flickers (`effects/hwp/pet_secret.effect`; your own
  candle, on your screen; setting `pets.candle_chance` forces the % for tests).
  The wisp and the living flame count as wyrms. HoH1's living flame is a bare flame; the
  import stands it on the body of HoH2's own candle pet (the thin candle and
  melted wax of `players/pets/pet_candle.png`, a base game texture) to match its
  shop icon.
- **Authority.** Effects on shared state go `pets.act` to the host, which
  checks the peer's reported ranks (`pets.level`, sent on load and on every
  change), a per-skill cooldown and a 500 px range to the requester before
  damaging/stunning. Mend and Morale touch only the owner and run locally.
  No skill fires in town or while the pet waits outside a puzzle or trap room.
- **Pickup toggles** set `PlayerRecord.petOptions` (a vanilla field that is
  saved as `pet-options`); `ResetPet()` re-initialises the live pet. Bowl menu
  rows or `hwp pet gold|valuables|materials|caches|cursed|elixirs|xp on|off`.
  Pets never pick up health or mana (`NoHealthOrMana`): those are left to the players.
- **Pet dyes.** The tailor (class swap `EquipmentDyerShopContent` ->
  `HWPDyerShopContent`, `scripts/HWP/Pets/PetDye.as`) asks "Dye gear / Dye
  pet" when you have a pet out. The pet window lists every dye the town has
  unlocked (the gear dyes; blueprint-locked ones only once found) for 100 /
  250 / 500 / 1000 gold by quality, and a free "remove". Most pets have two
  sections, dyed separately like gear: body / eyes (cats, dogs, wyrms, parrot),
  feathers / beak (toucan), feathers / tail (magpie), shell / legs (beetles),
  clothes / rucksack (imps, squires; skin and hair keep their colours), fur /
  flames (the flaming dog and hound) and taco / fur (taco cat); a "Dyeing:"
  row switches the section. The dyes are per character and per pet
  (`pets.dye.<petId>`, `pets.dye2.<petId>`). `tools/make_pet_dyes.py` (run by
  `build.py`) writes dye-ready copies of those pets (`players/pets/hwp_dye/` for the vanilla pets, which ship; `players/pets/hwp/dye/` for the HoH1 ones, local like the rest of the import;
  gitignored: made from your HoH2 base and HoH1 import) whose sprite pixels are
  indexed for the engine's multicolour shader (`.tif` sheets: the shader only
  recolours `.tif` textures, and only in their packed form, so dye colours show
  in a built `HWP-pets.bin` but a dev-linked module draws them raw red); a dyed pet swaps itself for the
  copy matching its dyed sections (`_p`, `_s`, `_ps`), so an undyed section
  keeps its own colours. Pets without sections (wisp, candle, living flame) or
  without generated copies get the whole sprite tinted with `Colorize`. Each player sends their active pet's dye
  (`pets.dye` -> host -> `pets.dyed`) on every floor and on a change, so the
  others see it too.
- Settings: `pets.enabled`, `pets.debug` (`hwp pet xp <n>`), `pets.bowl`,
  `pets.bowl_x/y` (all host-synced). The HammerwatchPlus tab of the player menu
  shows `pets.enabled` and `pets.bowl` (`config` in module.json); `petwait.*` is
  petrooms'.
- `pets.enabled 0` takes effect at once: your pet is re-made as vanilla (no skills,
  pickup toggles, scarab gold or dye; it still keeps out of puzzle and trap rooms
  while `petwait.enabled` is on), it gains no XP, the keeper
  and the tailor open their vanilla shops, the bowl goes, and `hwp pet <cmd>` says
  it is off. Levels, points, options and dyes stay in the save data. The HoH1 pets
  stay in the Pet Shop (they are data, `tweak/hwp/pets_hoh1.sval`).

- The optional feeding bowl comes back after a building upgrade, which rebuilds
  the town and destroys it (`HWP::Town::Kept`, on every machine since the bowl is
  local; test: `mod-town-rebuild`, which turns it on with `hwp set pets.bowl 1`:
  the setting places or removes the bowl at once).

## Test checklist

1. `python -m gamelab run mod-pets --mode lab`: `self-check done: 7 skills, 5 foods`; after import
   `22 HoH1 pet(s) in the Pet Shop`; `pet class active: HWPMiniPet...` lines once a pet spawns.
2. Pet Shop lists the HoH1 pets with icons; buying one spawns it; it follows,
   picks up gold, waits outside puzzle and trap rooms.
3. `hwp set pets.debug true`, `hwp pet xp 500`: level-up chat line; the keeper's
   Train menu shows points; spend on Smash: pots near the pet break in a run.
   (`fix-pets-merchant`: bot `fix_pets` check merchant; `plan-t9`'s `petbowl`
   section opens the same menu through the keeper.)
4. Stun on a goblin, never on an elite; Mend heals below 80 %; Morale buff icon
   out of combat only.
5. Feed a cabbage from the farm: ware count drops, XP rises.
6. Toggle Gold off: the pet ignores gold; on again: picks it up.
7. Tailor with a pet out: the Gear / Pet choice; Gear opens the vanilla dyer.
   Pet: pick a dye -> gold drops, the pet is re-made in the dye's colours;
   "Remove" restores it. Without a pet the tailor opens the vanilla dyer
   directly. Co-op: the other player sees your pet's dye.
8. Co-op: client pet's Smash/Stun work (host log with `pets.debug`), client
   cannot spam (host cooldown), ranks survive a reconnect (`pets.level`).
9. Inventory: with a pet out, the character tab shows `pet lvl N (xx%)` beside
   the character level and it moves with `hwp pet xp 500`
   (`fix-pets-inventory-level`: bot `fix_pets` check inventory, shot
   `character-tab`).
