# orbreroll

Orb rerolls are per orb, not per run.

- **Vanilla:** the orb picker's reroll (the Menu Additional key) has a pool for the whole
  run, as many charges as the accomplishment rewards give (`m_rRerolls`), counted in
  `PlayerRecord.rerollsUsed`. Each reroll costs shadow curse, 12 + 7 per reroll used so far
  this run (scaled by `ScaleShadowCurse`, at most 100). The trinket picker spends from the
  same pool.
- **With this module:** every orb you pick up gets the whole allowance. The picker shows
  "used/max" for that orb, and the cost starts at 12 again on each orb (12 + 7 per reroll of
  that orb). Orb rerolls no longer spend the run's pool, so the trinket picker keeps all of it.
  With no reroll accomplishments (allowance 0) there is still no reroll.
- Closing and reopening the picker keeps the orb's three picks and its count, so it never
  gives a reroll back.
- Override: `scripts/GUI/Menus/GiveSkillSphereMenu.as` (pristine `.orig` next to it, every
  change marked `HWP (orbreroll)`). The global `GetRerollCharges`, `GetRerollShadowCurseCost`
  and `GetRerollNavText` stay vanilla, since the trinket picker calls them; the picker uses its
  own `HWPRerollCharges`, `HWPRerollCost` and `HWPRerollNavText`. The per-orb count is in
  `scripts/HWP/OrbReroll/OrbReroll.as`, keyed by the orb's `SkillSphere`, and resets with the
  level (as the orb's picks do; vanilla saves only whether an orb was used).
- Setting `orbreroll.enabled` (host, default on): off is vanilla's run-wide pool.

## Test

1. A character with at least one reroll accomplishment: start a run, pick up an orb, reroll
   it until the charges run out (the nav bar hides the reroll), note the shadow curse.
2. Pick up the next orb: the reroll is offered again, its question says 0/max used, and the
   cost is back at the first reroll's.
3. Close the picker after a reroll and open the same orb again: same picks, same count.
4. A trinket picker in the same run still has every run reroll.
5. `hwp set orbreroll.enabled false`: the next orb uses the run's pool as in vanilla.
