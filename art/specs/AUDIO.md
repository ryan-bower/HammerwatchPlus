# Audio: the six 4th specializations (mods/specs)

Every moment below plays (or could play) a sound. All options are vanilla FMOD events, so
nothing new needs recording. **Now** is the mod's placeholder today (none: silent so far).
Pick in the audio picker: `python tools/audio_pick/build.py` renders every option with the
game's own FMOD (read only, from the install) into `tools/audio_pick/out/picker.html`, which
is published as an artifact with a shared store; the picks are read back from it and wired
in at the hook named. Options are in `tools/audio_pick/slots.py`.

## Stormbringer

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `ran_ec_shot` | **Electric Circuit: the shot**<br>The fan of three arrows leaving the bow. | stormbringer/electric_circuit.sval (PlaySound) | `player/attacks/twohanded/shortbow_quick_shot` | a: `player/attacks/twohanded/shortbow_charged_shot`<br>b: `actors/undead/court/court_sniper/court_sniper_bow_arrow_lightning`<br>c: `player/classes/ranger/marked_shot/marked_shot_cast` |
| `ran_ec_strike` | **Electric Circuit: lightning strike**<br>An arrow's hit calling lightning onto an enemy nearby (up to 2 a hit: plays often). | stormbringer/circuit.unit (PlaySound) | `player/classes/ranger/rain_of_arrows/rain_of_arrows_lightning` | a: `player/attacks/mainhand/lightning_bolt_zap`<br>b: `player/classes/sorcerer/static_discharge/static_discharge_hit`<br>c: `actors/bosses/boss_totempole/lightning/lightning_strike/lightning_strike_strike` |

## Invocation

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `wiz_tt_cast` | **Tempest Torrent: cast**<br>Throwing the lightning orb. | invocation/tempest_torrent.sval (PlaySound) | `player/classes/wizard/magic_missiles/magic_missiles_cast` | a: `player/classes/sorcerer/lightning_ball/lightning_ball_cast`<br>b: `player/classes/sorcerer/elemental_orb/elemental_orb_cast_lightning`<br>c: `actors/bosses/boss_totempole/lightning/lightning_ball/lightning_ball_cast` |
| `wiz_tt_loop` | **Tempest Torrent: the orb (loop)**<br>The orb crackling while it drifts (2-5 s; a loop, cut at 3 s here). | invocation/torrent.unit (new: a looping sound on the unit) | none | a: `player/classes/sorcerer/lightning_ball/lightning_ball_static_loop`<br>b: `player/classes/sorcerer/elemental_orb/elemental_orb_loop_lightning`<br>c: `actors/bosses/boss_totempole/lightning/lightning_ball/lightning_ball_loop` |
| `wiz_tt_zap` | **Tempest Torrent: a zap**<br>One zap from the orb (3 every 250 ms: wants to be short and quiet). | scripts/HWP/Specs/Invocation.as HWPSpecsZap (new) | none | a: `player/classes/sorcerer/lightning_ball/lightning_ball_static_zap`<br>b: `player/attacks/mainhand/lightning_bolt_zap`<br>c: `player/classes/rogue/artificer_suit/artificer_suit_zap` |
| `wiz_sc_release` | **Static Charge: release**<br>Five stacks released as three strikes on the next spell. | scripts/HWP/Specs/Invocation.as HWPSpecsStaticRelease (new) | none | a: `player/classes/sorcerer/static_discharge/static_discharge_cast`<br>b: `player/classes/paladin/judgement/judgement_lightning`<br>c: `player/classes/ranger/rain_of_arrows/rain_of_arrows_thunder` |
| `wiz_tt_thunderclap` | **Thunderclap (orb)**<br>The orb bursting when it expires. | scripts/HWP/Specs/Invocation.as (new) | none | a: `player/attacks/twohanded/lightning_blast`<br>b: `actors/bosses/boss_judges/caster/boss_judges_caster_lightning_blast_explode`<br>c: `doodads/thunderbird/thunderbird_lightning` |

## Winddancer

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `rog_pg_cast` | **Protective Gale: cast**<br>The gust wrapping the rogue and teammates. | winddancer/protective_gale.sval (PlaySound) | `player/classes/ranger/wind_weaver/wind_weaver_cast` | a: `player/classes/wizard/haste/haste`<br>b: `player/classes/paladin/divine_protection/divine_protection`<br>c: `player/classes/wizard/barrier/barrier_gain` |
| `rog_sw_gust` | **Second Wind: healing gust**<br>An evade releasing the healing gust (at most every 4 s). | winddancer/second_wind.sval and buffs_specs.sval gale_share (PlaySound) | `actors/bosses/boss_warrior_spirit/dive_attack/dive_attack_healing_wave` | a: `player/classes/priest/consecrated_ground/consecrated_ground_heal`<br>b: `player/classes/paladin/lay_on_hands/lay_on_hands`<br>c: `player/classes/ranger/wind_weaver/wind_weaver_hit` |

## Bannerlord

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `war_bs_raise` | **Battlefield Standard: raise**<br>Raising the standard. | bannerlord/battlefield_standard.sval (PlaySound) | `player/classes/priest/holy_banner/holy_banner` | a: `player/classes/warrior/war_cry/war_cry`<br>b: `actors/beasts/trolls/troll_ruler/troll_ruler_warcry`<br>c: `player/classes/paladin/armored_knight/armored_knight_wrath` |
| `war_bs_plant` | **Battlefield Standard: plant**<br>Driving the standard into the ground. | scripts/HWP/Specs/Bannerlord.as (new) | none | a: `player/classes/warrior/leap/leap_impact`<br>b: `player/classes/warrior/tremor_strikes/tremor_strikes`<br>c: `player/classes/ranger/trap/trap_set`<br>d: `player/classes/priest/holy_banner/holy_banner` |
| `war_bs_end` | **Battlefield Standard: ends**<br>The standard running out. | scripts/HWP/Specs/Bannerlord.as (new) | none | a: `player/classes/priest/holy_banner/holy_banner_end`<br>b: `player/classes/priest/consecrated_ground/consecrated_ground_end`<br>c: `player/cooldown` |

## Branding

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `wlk_pb_brand` | **Pyrebrand: brand**<br>The sigil searing onto an enemy. | branding/pyrebrand.sval (PlaySound) | `player/classes/warlock/dark_ritual/dark_ritual_cast` | a: `player/classes/ranger/marked_shot/marked_shot_hit`<br>b: `actors/bosses/boss_warrior_spirit/marked_prey/marked_prey_cast`<br>c: `player/shadow_curse` |
| `wlk_pb_claw` | **Pyrebrand: Hellfire Claw**<br>The claw erupting under the branded enemy. | scripts/HWP/Specs/Branding.as (PlaySound3D) | `player/classes/warlock/dark_ritual/dark_ritual_fire_explode` | a: `trinkets/scroll_hellfire/scroll_hellfire_impact`<br>b: `player/classes/warlock/demons_tail/demons_tail_fiery_impact`<br>c: `player/classes/warlock/summon_fiends/summon_fiends_cast_impact` |

## Arcane

| slot | moment | hook | now | options |
|---|---|---|---|---|
| `sor_bl_out` | **Blink: vanish**<br>Where the sorcerer disappears. | scripts/HWP/Specs/Arcane.as HWPSpecsBlink (PlaySound3D) | `actors/bosses/boss_avatar/boss_avatar_blink_out` | a: `actors/undead/shade/shade/shade_blink_out`<br>b: `actors/bosses/boss_avatar/boss_avatar_blink_out_stormstart`<br>c: `actors/bosses/boss_warrior_spirit/marked_prey/marked_prey_charge` |
| `sor_bl_in` | **Blink: reappear**<br>Where the sorcerer lands (the damage burst). | scripts/HWP/Specs/Arcane.as HWPSpecsBlink (PlaySound3D) | `actors/bosses/boss_avatar/boss_avatar_blink_in` | a: `actors/undead/shade/shade/shade_blink_in`<br>b: `actors/bosses/boss_warrior_spirit/marked_prey/marked_prey_teleport_end`<br>c: `player/classes/wizard/magic_missiles/magic_missiles_hit` |
| `sor_vb_save` | **Void Barrier: saved**<br>A hit that would have killed, stopped at 1 mana. | scripts/HWP/Specs/Arcane.as LivingHit (new) | none | a: `player/classes/wizard/barrier/barrier_impact`<br>b: `player/classes/paladin/armored_knight/armored_knight_block`<br>c: `player/parry` |

Left without a sound by choice: stack gains (Tailwind, Static Charge, Essence), the arrow
catch, a brand passing on, Arcane Feedback banking, Mana Conduit. Vanilla stacks are silent too.
