# bosses

**Tougher bosses** (issue #96): every boss has `bosses.toughness` % (default 25) more armor
and more fire, ice, lightning and poison resistance than in vanilla. Health is untouched.

- **A boss** is an actor with the `boss` actor tag: the flag vanilla, Pelor's Fury (specs), the
  boss recap (deathrecap) and the Wave Arena (wavemode) go by. That is every vanilla boss
  (the Bandit Lord, Arista, the Totems, the Harbingers, the Serpents, the Spider Queen, Dace
  Arden, the Face, the Avatar, the Celestial Ruins spirits), the Forsaken Tower's (vanilla
  boss units on its boss floors) and the Wave Arena's champion (`actors/hwp/wave_boss.unit`,
  a copy of the valor spirit). The Serpents' and Harbingers' shared health units carry the
  boss bar but no tag and no armor; their visible bodies (tagged) take the hits first.
- **How**: armor and resistances are flat numbers on each unit's own `ActorProperties`
  (`m_armor`, `m_resistanceFire/Ice/Lightning/Poison`; one object per spawned unit, one per
  state of a `StateActorBehavior`). `CompositeActorBehavior.Damage` reads them on whichever
  machine works the hit out (the attacker's), so every machine scales its own copy, from the
  host's setting (`scope` host, `HWP::Settings::Sync("bosses.")`). The module's `UpdateFrame`
  scans `g_scene.FetchAllActorsWithOtherTeam(g_team_player)` every 500 ms on run floors (not
  in town) and scales each boss's properties object once, keeping the vanilla values beside
  it. A buff (`armor-mul`, `resistance-mul`) was the other way, networked for free, but the
  Avatar and the Face are `no-buffs` units that `ApplyBuff` refuses.
- **The numbers**: a value above 0 becomes `round(value * (100 + pct) / 100)`; 0 stays 0 and a
  negative one (no boss has one) stays as it is, so a weakness never gets deeper. There is no
  cap to pass: `ApplyArmor`'s reduction is `a / (1 + a)`, below 100 % at any value. The
  vanilla NG+ multipliers (`Tweak::EnemyNGPArmorMul`, `EnemyNGPResistanceMul`) apply on top,
  as before. Example: the Bandit Lord's armor 50 and resistances 25 become 63 and 31.
- **Pelor's Fury still wins**: its `pelors_fury` buff has `armor-mul` and `resistance-mul`
  0 0, and the buffs' `ArmorMul()` multiplies the scaled value, so it is 0 while held.
- **Changes**: a new percentage applies within half a second to every boss already scaled
  (from the kept vanilla values); 0 or the switch off puts the vanilla values back. A boss
  that turns to the player's team gets its vanilla values back.
- Each scaled unit logs `[HWP:bosses] <unit> +25%: armor 50 -> 63, res 25/25/25/25 -> 31/31/31/31`.
  `hwp bosses` lists the bosses held now with their values (vanilla in brackets).

## Settings

On the HammerwatchPlus tab of the player menu (Dungeon Loot and Encounters > Tougher bosses);
the host's value rules in a lobby:

- `bosses.enabled` (on): off, every boss has its vanilla armor and resistances.
- `bosses.toughness` (25): 0, 10, 25, 50, 75 or 100 % more armor and resistances. 0: vanilla.

## Test checklist

Not run in game yet (written 2026-11-06 by source review).

1. Load a boss floor (`gl mission ...` / `hwp` floor loader), log shows
   `[HWP:bosses] <boss unit> +25%: armor A -> B, res ...` for each boss unit, B = round(A * 1.25);
   `hwp bosses` lists them.
2. `hwp set bosses.toughness 0`: within 0.5 s a `+0%` line per boss with the vanilla values;
   `hwp set bosses.toughness 50`: `+50%`.
3. A Paladin of Generosity holds the boss with Pelor's Fury: the `hwp gen` status line
   reads `armormul 0 resmul 0`, and hits do full damage (as before).
4. Co-op: the client's `hwp bosses` shows the same values as the host's; with the host's
   `bosses.toughness` changed, the client follows.
5. The Avatar (Dark Citadel) and the Face (no-buffs bosses) are scaled too.
