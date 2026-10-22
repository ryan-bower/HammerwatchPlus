# Audio: the six 4th specializations (mods/specs)

Every moment below plays (or could play) a sound. All options are vanilla FMOD events, so
nothing new needs recording. **Now** is what the mod plays (the user's picks, 2026-10-21; none: silent).
Pick in the audio picker: `python tools/audio_pick/build.py` renders every option with the
game's own FMOD (read only, from the install) into `tools/audio_pick/out/picker.html`, which
is published as an artifact with a shared store; the picks are read back from it and wired
in at the hook named. Options are in `tools/audio_pick/slots.py`.

## Deadeye

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `ran_ec_shot` | **Lightning Arrow: the shot**<br>The fan of three arrows leaving the bow. | stormbringer/electric_circuit.sval (PlaySound) | `actors/undead/court/court_sniper/court_sniper_bow_arrow_lightning` | a: `player/attacks/twohanded/shortbow_charged_shot`<br>b: `actors/undead/court/court_sniper/court_sniper_bow_arrow_lightning`<br>c: `player/classes/ranger/marked_shot/marked_shot_cast` |
| `ran_ec_strike` | **Lightning Arrow: lightning strike**<br>An arrow's hit calling lightning onto an enemy nearby (up to 2 a hit: plays often). | stormbringer/circuit.unit (PlaySound) | `player/classes/sorcerer/static_discharge/static_discharge_hit` | a: `player/attacks/mainhand/lightning_bolt_zap`<br>b: `player/classes/sorcerer/static_discharge/static_discharge_hit`<br>c: `actors/bosses/boss_totempole/lightning/lightning_strike/lightning_strike_strike` |

## Aerotheurge

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `wiz_tt_cast` | **Thunder Orb: cast**<br>Throwing the lightning orb. | invocation/tempest_torrent.sval (PlaySound) | `player/classes/sorcerer/lightning_ball/lightning_ball_cast` | a: `player/classes/sorcerer/lightning_ball/lightning_ball_cast`<br>b: `player/classes/sorcerer/elemental_orb/elemental_orb_cast_lightning`<br>c: `actors/bosses/boss_totempole/lightning/lightning_ball/lightning_ball_cast` |
| `wiz_tt_loop` | **Thunder Orb: the orb (loop)**<br>The orb crackling while it drifts (2-5 s; a loop, cut at 3 s here). | invocation/torrent.unit (new: a looping sound on the unit) | `player/classes/sorcerer/lightning_ball/lightning_ball_static_loop` | a: `player/classes/sorcerer/lightning_ball/lightning_ball_static_loop`<br>b: `player/classes/sorcerer/elemental_orb/elemental_orb_loop_lightning`<br>c: `actors/bosses/boss_totempole/lightning/lightning_ball/lightning_ball_loop` |
| `wiz_tt_zap` | **Thunder Orb: a zap**<br>One zap from the orb (3 every 250 ms: wants to be short and quiet). | scripts/HWP/Specs/Invocation.as HWPSpecsZap (new) | `player/classes/rogue/artificer_suit/artificer_suit_zap` | a: `player/classes/sorcerer/lightning_ball/lightning_ball_static_zap`<br>b: `player/attacks/mainhand/lightning_bolt_zap`<br>c: `player/classes/rogue/artificer_suit/artificer_suit_zap` |
| `wiz_sc_release` | **Static Charge: release**<br>Five stacks released as three strikes on the next spell. | scripts/HWP/Specs/Invocation.as HWPSpecsStaticRelease (new) | `player/classes/ranger/rain_of_arrows/rain_of_arrows_thunder` | a: `player/classes/sorcerer/static_discharge/static_discharge_cast`<br>b: `player/classes/paladin/judgement/judgement_lightning`<br>c: `player/classes/ranger/rain_of_arrows/rain_of_arrows_thunder` |
| `wiz_tt_thunderclap` | **Thunderclap (orb)**<br>The orb bursting when it expires. | scripts/HWP/Specs/Invocation.as (new) | `player/attacks/twohanded/lightning_blast` | a: `player/attacks/twohanded/lightning_blast`<br>b: `actors/bosses/boss_judges/caster/boss_judges_caster_lightning_blast_explode`<br>c: `doodads/thunderbird/thunderbird_lightning` |

## Winddancer

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `rog_pg_cast` | **Protective Gale: cast**<br>The gust wrapping the rogue and teammates. | winddancer/protective_gale.sval (PlaySound) | `player/classes/wizard/haste/haste` | a: `player/classes/wizard/haste/haste`<br>b: `player/classes/paladin/divine_protection/divine_protection`<br>c: `player/classes/wizard/barrier/barrier_gain` |
| `rog_sw_gust` | **Second Wind: healing gust**<br>An evade releasing the healing gust (at most every 4 s). | winddancer/second_wind.sval and buffs_specs.sval gale_share (PlaySound) | `player/classes/ranger/wind_weaver/wind_weaver_hit` | a: `player/classes/priest/consecrated_ground/consecrated_ground_heal`<br>b: `player/classes/paladin/lay_on_hands/lay_on_hands`<br>c: `player/classes/ranger/wind_weaver/wind_weaver_hit` |

## Bannerlord

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `war_bs_raise` | **Battlefield Standard: raise**<br>Raising the standard. | bannerlord/battlefield_standard.sval (PlaySound) | `player/classes/warrior/war_cry/war_cry` | a: `player/classes/warrior/war_cry/war_cry`<br>b: `actors/beasts/trolls/troll_ruler/troll_ruler_warcry`<br>c: `player/classes/paladin/armored_knight/armored_knight_wrath` |
| `war_bs_plant` | **Battlefield Standard: plant**<br>Driving the standard into the ground. | scripts/HWP/Specs/Bannerlord.as (new) | `player/classes/priest/holy_banner/holy_banner` | a: `player/classes/warrior/leap/leap_impact`<br>b: `player/classes/warrior/tremor_strikes/tremor_strikes`<br>c: `player/classes/ranger/trap/trap_set`<br>d: `player/classes/priest/holy_banner/holy_banner` |
| `war_bs_end` | **Battlefield Standard: ends**<br>The standard running out. | scripts/HWP/Specs/Bannerlord.as (new) | `player/classes/priest/holy_banner/holy_banner_end` | a: `player/classes/priest/holy_banner/holy_banner_end`<br>b: `player/classes/priest/consecrated_ground/consecrated_ground_end`<br>c: `player/cooldown` |

## Branding

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `wlk_pb_brand` | **Pyrebrand: brand**<br>The sigil searing onto an enemy. | branding/pyrebrand.sval (PlaySound) | `player/shadow_curse` | a: `player/classes/ranger/marked_shot/marked_shot_hit`<br>b: `actors/bosses/boss_warrior_spirit/marked_prey/marked_prey_cast`<br>c: `player/shadow_curse` |
| `wlk_pb_claw` | **Pyrebrand: Hellfire Claw**<br>The claw erupting under the branded enemy. | scripts/HWP/Specs/Branding.as (PlaySound3D) | `actors/aberrations/wisps/wisp_fire/wisp_fire_explode` | a: `trinkets/scroll_hellfire/scroll_hellfire_impact`<br>b: `player/classes/warlock/demons_tail/demons_tail_fiery_impact`<br>c: `player/classes/warlock/summon_fiends/summon_fiends_cast_impact`<br>d: `trinkets/scroll_meteor/scroll_meteor_impact`<br>e: `player/classes/warlock/dark_ritual/dark_ritual_explode`<br>f: `player/classes/warlock/summon_fiends/summon_fiends_explode`<br>g: `player/attacks/twohanded/fire_blast`<br>h: `actors/aberrations/wisps/wisp_fire/wisp_fire_explode`<br>i: `player/classes/wizard/animated_sword/animated_sword_fire_explode`<br>j: `actors/bosses/boss_serpent/boss_serpent_falling_bomb_explode`<br>k: `actors/bosses/boss_warrior_spirit/rain_of_swords/rain_of_swords_fire_impact`<br>l: `actors/aberrations/phantoms/warlock/phantom_warlock_ritual_bomb_explode` |

## Arcane

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `sor_bl_out` | **Blink: vanish**<br>Where the sorcerer disappears. | scripts/HWP/Specs/Arcane.as HWPSpecsBlink (PlaySound3D) | `actors/undead/shade/shade/shade_blink_out` | a: `actors/undead/shade/shade/shade_blink_out`<br>b: `actors/bosses/boss_avatar/boss_avatar_blink_out_stormstart`<br>c: `actors/bosses/boss_warrior_spirit/marked_prey/marked_prey_charge` |
| `sor_bl_in` | **Blink: reappear**<br>Where the sorcerer lands (the damage burst). | scripts/HWP/Specs/Arcane.as HWPSpecsBlink (PlaySound3D) | `actors/undead/shade/shade/shade_blink_in` | a: `actors/undead/shade/shade/shade_blink_in`<br>b: `actors/bosses/boss_warrior_spirit/marked_prey/marked_prey_teleport_end`<br>c: `player/classes/wizard/magic_missiles/magic_missiles_hit` |
| `sor_vb_save` | **Void Barrier: saved**<br>A hit that would have killed, stopped at 1 mana. | scripts/HWP/Specs/Arcane.as LivingHit (new) | none | a: `player/classes/wizard/barrier/barrier_impact`<br>b: `player/classes/paladin/armored_knight/armored_knight_block`<br>c: `player/parry`<br>d: `player/revived`<br>e: `actors/bosses/boss_wraith/wraith_bell`<br>f: `actors/bosses/boss_avatar/boss_avatar_phase_2`<br>g: `actors/humans/cultists/cultist_acolyte/cultist_acolyte_shadow_bomb_explode`<br>h: `actors/undead/shade/shade_lesser/shade_lesser_shadow_ball_hit`<br>i: `player/classes/sorcerer/ice_mastery/ice_mastery_shatter`<br>j: `actors/bosses/boss_warrior_spirit/halo/halo_close`<br>k: `actors/bosses/boss_warrior_spirit/glory_to_the_goddess/glory_to_the_goddess_impulse` |

Left without a sound by choice: stack gains (Tailwind, Static Charge, Essence), the arrow
catch, a brand passing on, Arcane Feedback banking, Mana Conduit. Vanilla stacks are silent too.
