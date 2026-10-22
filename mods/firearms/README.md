# firearms

A new class, the **Firearms Specialist**. Pure data (`PlayerClass`,
`ItemSkillDef`, `BaseItem`, `PlayerPortraitPiece`, `HeroTitle` loaders) plus a
tiny module that self-checks the loaders and answers `hwp firearms`.

- **The clip** (`players/hwp/firearms/stacks_firearms.sval`): a stack counted
  down from full, Warlock essence in reverse. Its `max` is 0; each gun adds its
  magazine through a marker buff (`buffs_firearms.sval`, re-applied every
  250 ms by the item's `Modifiers::Buff`) that carries `ModifyStack add-max`.
  An item can't carry the `ModifyStack` itself: `PlayerRecord.RefreshModifiers`
  applies stack modifiers before it adds equipment. The module fills the clip
  on spawn. Gun shots take rounds and no mana.
  At 0 rounds the **Reloading** stack starts (1.6 s timer; a dodge restarts it)
  and refills the clip when it ends. **Reload** (a starting skill, as are Frag and each doctrine's two) is a cast of
  2.0 s down to 1.2 s that refills when it ends, with the automatic reload's
  icon sweep. A dodge, any other ability or the weapon swap (X) cancels it with
  the clip as it was, and Reload starts a new one; a full clip refuses it. The
  guns don't fire while it casts. An ability or a swap during the automatic
  reload holds it at its start, and it runs again from the beginning once the
  ability is done (`HWP::Firearms::Interrupting`, Combat.as; `plan-firearms-reload-cut`).
  A held trigger only says "cant" on a fresh click (`HWPFirearmsGun`).
  Mana pays for gadgets: the grenade launcher, grenades, rockets, bursts.
  The pool is 60 + 2 a level, 1 a second (docs/RE_NOTES.md, the Firearms balance pass).
  The last rounds of a clip click (3 or fewer, 6 or fewer with dual pistols):
  a dry metal click after the shot (`HWPFirearmsLowClick`, Audition.as; the
  game's `button_metal`, since a mod can't add a sound).
- **Grenade Launching Rifles** `hwp_rifle_01/02/03` (`tweak/hwp/equipment_firearms.sval`;
  "Flintlock/Field/Marksman's Rifle" until 2026-10-20): two-handed, 30 rounds, a three-round burst (rounds at 0/100/200 ms of an
  800 ms cycle, 52 % each; epic 65 %), no piercing.
  The secondary is an under-barrel grenade launcher: 4 mana, 1.5 s cooldown,
  no rounds. Its shell arms after 40 px of flight (`Launcher.as`
  `HWPFirearmsArm`): point-blank it hits the first enemy as a slug for half
  damage and a 0.5 s stun, with no blast; a wall sets it off either way. On the
  skill bar the off-hand slot shows the launcher close-up of the rifle's tier,
  unmirrored, in place of the mirrored rifle (`LauncherHUD.as`; the inventory
  keeps the rifle's icon). Dex-gated, crossbow anim set, tag `hwp_firearm`. The t1
  rifle sits in the armory pool. A new character starts with one Service
  Pistol (`hwp_glock_mh_01`) in the main hand. Every weapon type is allowed.
- **Shops** (`scripts/HWP/Firearms/Shops.as`; overrides of the town equipment
  seller `Town/EquipmentSeller.as` and the wagon's "Buy new equipment"
  `ShopContent/EquipmentShopShopContent.as`, the added lines marked HWP): both
  roll their stock by slot and the buyer's stats, so a Specialist was offered
  bows and crossbows and a Ranger could draw a rifle. Now a Firearms Specialist's
  weapon offers are guns only, the stock always holds at least one gun (a saved
  stock gets one in place of its last non-weapon offer when the shop opens), and
  no other class is offered a gun. The armory list is untouched. Measured by
  `mod-firearms-shop 20261022-143058` (the `firearms_shop` bot): the fixture's
  Paladin got 8 offers and no gun; a fresh Specialist got 8 offers whose two
  weapons were a Service Pistol and a rifle, and after she bought both out the
  reopened stock held a Full Auto Rifle in place of a non-weapon offer. The
  wagon's `EquipmentShopShopContent` has no unit in the base game's data
  (`grep` of `gamecode/sdk/hoh2`), so that override waits for a level that uses it.
- **Flamethrower Rifles** `hwp_flamerifle_01/02/03`: the same rifle (30 rounds,
  the three-round burst) with a flamethrower under the barrel in place of the
  launcher (`hwp_attack_flamer`, the game's `PlayerSkillDirectionalChannelling`).
  Held, it sprays a flame every 100 ms (`projectiles/flame.unit`: vanilla's
  bandit flame-spray ray, 25 % weapon damage as fire, through 3 enemies, about
  68 px out) and pays 1 mana every 100 ms (`cost-interval`); it stops when the
  mana runs out. No cooldown, no rounds. The off-hand slot shows the
  flamethrower close-up (`flamerifle_nozzle_0N`, `LauncherHUD.as`). The t1 is in
  the armory pool.
- **Full Auto Rifles** `hwp_autorifle_01/02/03`: the same rifle (30 rounds, the
  three-round burst on left click) with full auto on right click in place of the
  launcher (`hwp_attack_autofire`, an `HWPFirearmsGun` on a 100 ms cycle): held,
  a rifle round every 100 ms with a 40 degree spread (the burst's is 2). Rounds,
  no mana, no cooldown; a full clip lasts 3 s. The off-hand slot shows the
  full-auto close-up (`autorifle_mode_0N`). The t1 is in the armory pool.
- **Pistols:** `hwp_glock_mh_01/02/03`, one item for either hand, 10 rounds each.
  Clicked in the bag, a pistol goes to the main hand; with the main hand full
  (and not two-handed) and the off hand free, it goes to the off hand. There it
  is its off-hand twin `hwp_glock_oh_0N` (hand-crossbow anim, never dropped or
  sold), which turns back into the main-hand pistol in the bag
  (`scripts/HWP/Firearms/Pistols.as`, core's `HWP::Bag::OnEquip`). Each hand's
  pistol grants a marker buff the other pistol's attack checks for.
  - A main-hand pistol with any other off hand fires one accurate round every
    300 ms (`hwp-solo-length`), 80 % weapon damage.
  - Dual pistols share a 20-round clip. Left click alternates muzzles with a
    small spread (±2.5°), one round every 300 ms (a 600 ms cycle; a held trigger
    restarts it in the same frame, so the gaps are even); right click fires both at once with a wide spread (2
    rounds when available; the last single shared round still fires). Every round is
    80 % of its own gun's damage.
  - Pistol rounds leave the gun 6 px off the aim line and are angled to cross it
    100 px out (`converge`); parallel, a lone pistol hit a target dummy with 8 of
    ~26 rounds (probe-pistol 20261020-002514), 22 after.
- **Damage against the bow and crossbow** (`bench-weapons`, the same Firearms
  Specialist, main attack held on one dummy for 15 s, reloads included):
  rifle 130/184 per second at level 1/12 before, against shortbow 84/127,
  longbow 99/144, crossbow 96/115 (bench-weapons 20261020-003002). After:
  rifle 87/127, lone pistol 61/87, bows 85-99/123-149 (bench-weapons
  20261020-003538): the rifle is about a bow, a pistol about two thirds of one
  (the off hand stays free). Dual pistols on left click measured 38/75 there:
  their spread dict's `min` of 4° is added to every round (ShootProjectile.as
  `GetShootDir`), so each one left at least 4° off the aim line and many missed
  the dummy (radius 4). With a plain ±2.5° spread they measure 87/129, the
  rifle's rate (88/129) with two guns' affixes (bench-weapons
  20261020-042519, where the rifle and lone pistol repeat their 003538 numbers);
  right click fires about 15 % more.
  - An off-hand pistol with another main-hand weapon fires one round on right
    click.
  - While a rifle, pistol or cannon fires the gun is pinned at the shot
    animation's first frame (arm out), and it stays raised until 1 s without a
    shot, or a dodge or a reload, then comes down (`Combat.as` AimHold). Until
    2026-10-22 only the pause after a shot was held, so the gun came down and up
    again with every burst (the user). Rifle and pistols held, down after 1 s,
    on a dodge and on a reload: `plan-firearms-arm 20261022-142503`.
- **Hand Cannons** `hwp_hcannon_mh_01/02/03` (off-hand twins `hwp_hcannon_oh_0N`,
  the same hand swap as the pistols, `Pistols.as`), 6 rounds each. Each round is
  1.5 times a pistol round (`hcannon_round*.unit`, mul 1.2 against the
  pistol's 0.8, on the same weapon damage) at half the rate:
  - Alone (a shield, any other off hand): one round every 600 ms.
  - With a pistol in the other hand, either way round (16 rounds): left click
    fires pistol, cannon, pistol 100 ms apart, then waits the lone pistol's
    300 ms before the next burst (a 500 ms cycle; `hwp-mixed-with`/`-length` on
    `HWPFirearmsGun`, the `mix1-3` lists). Right click fires both at once at the
    cannon's rate (1040 ms).
  - Two cannons (12 rounds): left click alternates muzzles every 600 ms; right
    click fires both at once.
  - An off-hand cannon with another main-hand weapon fires one round on right
    click.
  - Measured: plan-firearms-cannon 20261020-170919 and 20261020-173547 PASS (gaps 561-594 alone,
    99/99/297 in either mixed pair, 561-594 between the two cannons' muzzles; the
    flamer took 90 to 73.4 mana over a 2 s hold, its 20 less the regen).
- **Base kit:** Reload and the Frag Grenade (targeted lob, `GroundBouncing` +
  `Explode` on landing, armor penetration, radius 64: half the old 128, and
  the Incendiary and Gas areas match it). **Elemental Bullets** (the Scavenger ID)
  gives each gun shot a 10-50 % chance to deal its weapon damage as an element.
  **Extended Clip Crit** (the Steady Hands ID) adds 10-50 % magazine capacity and
  2 % crit damage per round remaining in each gun's own magazine. The native ammo
  pool stays shared; unequal pistol/cannon firing retains separate bonus counts.
  - Reload orbs: **Dodge Reload Skip** (a dodge during the automatic reload
    finishes it), **Explosive Reload** (the old magazine is thrown 100 out and
    blows up for 5/8/12 per round left; dual pistols throw one magazine,
    then the other 100 ms later),
    **Over-Reload** (a 200 ms gold window on the reload bar. Every reload,
    with or without the orb, shows a white bar filling just above the HUD's
    health bar; with Over-Reload the gold sits at a random point in its
    second half. One try a reload: Reload or a fresh left click while the
    bar is in the gold. A hit finishes the reload at once and gives
    +5/10/15 rounds, never stacking, until the clip runs dry or a reload
    isn't perfect; a miss turns the white red until the reload ends).
  - Frag orbs, mutually exclusive: **Stun Grenade** (lightning, stun and slow
    1/2/3 s), **Incendiary** (a burning, blinding fire patch), **Gas** (a
    poison cloud that fire ignites).
- **Marksman:** **Snipe** (both hands' damage, 300-750 %, armor penetration,
  20-30 mana, no rounds; a red laser dot marks the aim while it charges) and **Critical Aim** (passive: a gun round that
  hits gives Focus, crit chance and damage per stack; one that hits nothing
  loses it all). Orbs: Headshot (the first enemy a Snipe hits is crit),
  Piercing Bullet (2/4/6 more enemies), BOOM Headshot! and Elemental Exposure.
- **Demolitionist:** the **Rocket Launcher** (200-400 fire blast, 6 mana, no rounds) and
  **Ordinance Hoarder** (passive: Frag and the rocket recharge faster and bank
  charges while ready; a charge clears the cooldown after a cast). Its buff icon
  counts every use ready (stored charges plus the skill when off cooldown) and
  goes at 0; while a charge banks, the skill slot's ring fills around a bright
  icon (`scripts/HWP/Firearms/ChargeHUD.as`). Orbs: Fat
  Boy (slow heavy rocket, poison, blind), Magic Missile (ice then fire), Quad
  Missile Chambers (4 small missiles), Elemental Shrapnel, Overpacked.
- **Assault:** Double Barrel Burst (two shotgun shells of 150 physical: x1.5/2/2.5/3/3.5
  damage up close), Adrenaline (kills build stacks; taking damage spends them to
  restore health); orbs include
  Triple Barrel and Dragon's Breath.
- **Engineer:** Deploy Turret (placed where aimed, rounds at 1x weapon damage every 0.6-0.2 s,
  wears down over 30 s; orbs
  Second Turret, Reinforced Turret) and My Turret! (passive: within 60 px, 10 m
  at the game's 6 px a metre, the turret is repaired and boosted; Belt Feed adds
  an elemental chance).
- The orb scripts (Focus, Headshot, Exposure, Hoarder charges, the reload
  bar and Over-Reload, the magazine throw) are in `scripts/HWP/Firearms/Combat.as`.
- **Art:** portrait piece and hero title reuse the ranger assets. The
  character-select figure (`players/hwp/firearms/class_showcase.png`, 32x32) is
  the vanilla Ranger figure with the bow taken out and the t1 rifle held at port
  arms, made by `tools/icon_art/firearms_showcase.py` (a normal character with a
  gun, the user's call on 2026-10-22, in place of the hooded figure).
  - Held guns: voxel meshes in `players/models/equipment/` (`hwp_rifle`, with
    the under-barrel launcher; `hwp_glock_mh` on the right hand bone,
    `hwp_glock_oh` on the left). They sample vanilla `character.tif`: the
    item's `color` dye is the rifle's wood and the pistol's slide, and
    `color-secondary` is the rifle's metal.
  - Rounds and missiles in flight: `tools/make_bullet_art.py` draws
    `projectiles/rounds.png` and writes one effect per sprite. The rifle/turret
    round is `round_rifle`; the pistol round is the same idea a little smaller,
    `round_pistol`. Each comes in `_fire`, `_ice`, `_lightning` and `_poison`
    variants used by Elemental Bullets' built projectile units. The rest are
    `gl_shell` (the launcher's 40 mm shell) and `missile_rocket`, `_fatboy`,
    `_magic` and `_quad`. Edit the tool, not its output.
  - Ground sprites: `items/hwp/firearms_drops.unit`, one scene per gun and tier
    (`rifle_0N`, `glock_0N`), in `items/hwp/firearms_drops.png`.
  - Class icon: `players/hwp/firearms/class_showcase.png`, 32x32 like a cell of
    vanilla `players/class_showcase.png`: the starting outfit (chest and feet
    dex t1a) facing the camera on vanilla's shadow disc, a Service Pistol in
    hand. Taken from the character screen (look-firearms-showcase); the class
    list shows it in look-class-list.
  - Icons are built by `tools/make_firearms_icons.py` into
    `players/hwp/firearms/icons.png` (skills, orbs, attacks) and
    `items/hwp/firearms_items.png`. The items atlas has the guns in row 0 and
    the launcher close-ups `rifle_gl_0N`, the skill bar's off-hand slot, in
    row 1. Hand-drawn art in `art/firearms/override/` wins over the
    `art/firearms/sprites.txt` placeholders; a preview of both sheets goes in
    `art/firearms/preview.png`. To hand-draw one, save a 24x24 PNG
  as `art/firearms/override/<name>.png` (Aseprite, LibreSprite or Pixelorama)
  and re-run the tool. Atlases must be power-of-two sized: the game hangs on
  load otherwise.
  - `tools/icon_art/` paints icon ideas in the vanilla skill-icon style, three
    for each skill, orb, attack and HUD icon here and for the vanilla classes'
    orbs, plus a picker page that shows them beside the current icon. A picked
    one goes into `art/firearms/override/` (tools/icon_art/README.md).

The class planner (`python -m planner`, `planner/README.md`) records the skill
design. Final icons remain an art task. See `docs/design/firearms.md`.

## Test checklist

1. `python -m gamelab run mod-firearms --mode lab`: `[HWP:firearms] class registered with 4 subclass(es)`, no
   "missing item/unit" lines, no script or sval errors.
2. Create a character: Firearms Specialist is in the class list with the
   round icon; the character spawns with a Service Pistol in the main hand.
3. Clip: `python -m gamelab run plan-t14 --mode lab`. Covers the 30-round
   spawn fill, 1 round and no mana per shot, the launcher's mana cost, the empty
   clip (Reloading, won't fire, refills), the dodge restart and Reload.
4. Guns: `python -m gamelab run plan-firearms-guns --mode lab`. Covers
   magazines 10/20/30 and the rounds each loadout's clicks take.
   `plan-firearms-cannon`: the Hand Cannon alone, mixed with a pistol either
   way round, paired, in the off hand, the Flamethrower Rifle's mana drain and the
   Full Auto Rifle's rate and spread. `look-firearms-cannon` pictures their models,
   rounds, flame and icons.
5. Frag grenade lands where aimed and explodes; damage numbers appear.
6. Specializations and orbs: `plan-firearms-a` (Frag, the picker, Marksman),
   `plan-firearms-b` (Demolitionist, Assault) and `plan-firearms-orbs` (the
   Reload and Frag orbs). Orbs are taken with `gl orb <id>` (the sphere's
   SkillTempUp). `plan-firearms-reload-cut`: an ability or the swap cuts a
   reload, and the saved-rank move for skills that start at rank 1
   (`hwp firearms startranks`).
7. Over-Reload by hand: empty the clip, watch the bar above the health bar,
   press Reload (or left click) in the gold; rank 1 adds 5 rounds. Then Reload
   with rounds left and press Reload again in the gold: the bonus stays +5.
   Miss it: the white turns red and a second press does nothing. Without the
   orb the white bar still fills on every reload.
8. Ordinance Hoarder by hand: wait 8 s with the rocket ready, fire twice in a
   row.
9. Co-op: a client sees the host's bullets, grenades and rockets, and the
   other way round.
