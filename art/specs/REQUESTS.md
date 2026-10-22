# Art requests: the six 4th specializations (mods/specs)

Every icon below is wanted in the vanilla HoH2 skill-icon style (`tools/icon_art/vpaint.py`'s
docstring: no outlines, 4-6 step ramps lit from the upper left, bright rim, dark core shadow,
big cropped subject, glowing energy with a white-hot core, near-black tinted ground).

**Delivery:** one PNG per icon at `art/specs/override/<name>.png`, RGBA, exactly the size
given. `tools/make_specs_icons.py` packs them into the game sheet
`mods/specs/players/hwp/specs/icons.png`. An override always wins over the placeholder that
tool makes (a tinted vanilla icon). Icon ideas for picking can go through the picker
(`tools/icon_art/picker.py`) the way the Firearms ones did: three ideas each, written to
`tools/icon_art/out/specs/`. Only the picked one goes to `override/`.

Sizes: **24x24** for skills and orbs (the skill bar, trainer and orb picker), **14x14** for
HUD status icons (the buff bar above the health bar).

Orb icons follow the vanilla rule: the orb shows its skill's subject with the change made
visible (a vanilla example: the Ranger's Marked Shot orbs).

## Ranger: Deadeye (wind and lightning archer; the ids keep stormbringer)

| name | size | what it is |
|---|---|---|
| `ran_electric_circuit` | 24 | Active. A V of three arrows crackling with lightning, flying out and curving back like a boomerang. |
| `ran_gathering_winds` | 24 | Passive. Wind gusting around a drawn bow; speed lines. |
| `ran_ec_boomerang` | 24 | Orb Boomerang: the returning arrow, brighter and charged, curved path. |
| `ran_ec_lightning_rod` | 24 | Orb Storm Arrow: an arrow calling several lightning bolts down around it. |
| `ran_ec_tailwind_catch` | 24 | Orb Tailwind Catch: a hand catching a returning arrow, wind swirl. |
| `ran_gw_gale_force` | 24 | Orb Gale Force: extra arrows fanning out of a gust. |
| `ran_gw_wind_ward` | 24 | Orb Wind Ward: a ring of wind deflecting a hit. |
| `hud_tailwind` | 14 | Status Tailwind (stacking speed): a small swirl of wind. |

## Wizard: Aerotheurge (lightning magus; the ids keep invocation)

| name | size | what it is |
|---|---|---|
| `wiz_tempest_torrent` | 24 | Active. A slow ball of lightning lashing out at targets with forked bolts. |
| `wiz_static_charge` | 24 | Passive. Static sparks gathering on fingertips. |
| `wiz_tt_overcharge` | 24 | Orb Focal Point: one bolt hitting the same point again and again, intensifying. |
| `wiz_tt_lingering_storm` | 24 | Orb Lingering Storm: the lightning orb with an hourglass / long trailing tail. |
| `wiz_tt_thunderclap` | 24 | Orb Thunderclap: the orb bursting in a ring of lightning. |
| `wiz_tt_lightning_rod` | 24 | Orb Lightning Rod (new; cell x 216): the orb zapping more enemies per tick over a longer range. |
| `wiz_sc_static_channel` | 24 | Orb Charged Font: a spark turning into blue mana. |
| `wiz_sc_conduit` | 24 | Orb Conduit: a charged hand with speed lines (faster casting). |
| `hud_static_charge` | 14 | Status Static Charge (stacks to 5): a tiny spark. |

## Sorcerer: Arcane (blink mage; mana is your life)

| name | size | what it is |
|---|---|---|
| `sor_blink` | 24 | Active. A figure vanishing in a violet arcane flash and reappearing; afterimage. |
| `sor_living_mana` | 24 | Passive. A heart filled with blue-violet mana instead of blood. |
| `sor_bl_void_barrier` | 24 | Orb Void Barrier: a dark violet shell around a blinking figure. |
| `sor_bl_far_step` | 24 | Orb Far Step: a long blink trail, footsteps far apart. |
| `sor_lm_arcane_feedback` | 24 | Orb Arcane Feedback: a hit turning into arcane power (a crack spilling violet energy). |
| `sor_lm_mana_conduit` | 24 | Orb Mana Conduit: mana flowing out to two allies. |
| `hud_void_barrier` | 14 | Status Void Barrier (cannot die for 1 s). |
| `hud_arcane_feedback` | 14 | Status Arcane Feedback (next spell empowered). |

## Rogue: Winddancer (evasive support)

| name | size | what it is |
|---|---|---|
| `rog_protective_gale` | 24 | Active. A swirling gale wrapped around several allies; pale green-white wind. |
| `rog_second_wind` | 24 | Passive. A dodge leaving behind a green healing gust. |
| `rog_pg_lasting_gale` | 24 | Orb Lasting Gale: the gale with a long, lingering tail. |
| `rog_pg_tailwind` | 24 | Orb Tailwind (movement speed): wind at running feet. |
| `rog_sw_lingering_breeze` | 24 | Orb Lingering Breeze: a soft green breeze with small healing motes. |
| `rog_sw_shared_breath` | 24 | Orb Shared Breath: one gust splitting to two allies. |
| `hud_protective_gale` | 14 | Status Protective Gale (evasion up). |
| `hud_lingering_breeze` | 14 | Status Lingering Breeze (health regeneration). |

## Warrior: Bannerlord (banner support)

| name | size | what it is |
|---|---|---|
| `war_battlefield_standard` | 24 | Active. A war banner held high, a shield crest on the cloth. |
| `war_righteous_crusade` | 24 | Passive. A banner with a sunburst (buffs last longer). |
| `war_bs_feared_crest` | 24 | Orb Feared Crest: the banner's crest glaring, a cowering enemy (Vulnerability). |
| `war_bs_martyrs_banner` | 24 | Orb Martyr's Banner: the banner over allies, the bearer bleeding. |
| `war_rc_war_drum` | 24 | Orb War Drum: a war drum with shock rings (Weakness on enemies). |
| `war_rc_shared_provisions` | 24 | Orb Shared Provisions: a supply sack and an hourglass (cooldowns). |
| `hud_standard_raised` | 14 | Status Battlefield Standard, carried (damage reduction). |
| `hud_standard_planted` | 14 | Status Battlefield Standard, planted (double damage reduction). |
| `hud_shared_provisions` | 14 | Status Shared Provisions (cooldown reduction). |

## Warlock: Branding (demonic brand)

| name | size | what it is |
|---|---|---|
| `wlk_pyrebrand` | 24 | Active. A burning demonic sigil seared onto an enemy. |
| `wlk_essence_extraction` | 24 | Passive. A dagger drawing a wisp of essence out of a branded foe. |
| `wlk_pb_combustion` | 24 | Orb Combustion: the hellfire claw erupting, fed by essence orbs. |
| `wlk_pb_proliferation` | 24 | Orb Proliferation: the sigil splitting onto several enemies. |
| `wlk_ee_essence_empowerment` | 24 | Orb Essence Empowerment: a weapon wreathed in fire fed by essence. |
| `wlk_ee_released_essence` | 24 | Orb Released Essence: a slain elite bursting into essence wisps. |
| `hud_pyrebrand` | 14 | Status Pyrebrand on an enemy: the branded sigil, small. |

## World sprites (done 2026-10-21: art/specs/fx, drawn by tools/icon_art/sp_fx.py, packed into effects/fx.png by tools/make_specs_fx.py)

| name | size | what it is |
|---|---|---|
| `fx_pyrebrand_sigil` | 4 frames, 24x24 each, a horizontal strip 96x24 | The branded sigil hovering over a branded enemy, a slow burning pulse. |
| `fx_hellfire_claw` | 6 frames, 32x48 each, strip 192x48 | A demonic claw tearing up out of the ground through the victim. |
| `fx_battlefield_standard` | 2 frames 24x40 (carried) + 2 frames 24x40 (planted) | The Bannerlord's standard: pole, crest cloth fluttering. |
| `fx_tempest_orb` | 4 frames, 24x24 each | The Thunder Orb orb: a crackling ball of lightning. |
