# gamelab-pilot

The in-engine side of GameLab's Pilot bot (`gamelab/pilot.py`): `Pilot.as` registers the `pilot`
verb and its intents (move, path_to, attack, kite, use, potion, wait, exit), plus scan,
pathfind, reachmap, exitareas, routesweep, bodies, breakables, exitprobe, pfsweep and pfbench.
`reflex` takes only `potion=` and `fire=`.

## Not in this repo
These parts of the Python client have no in-engine side here:
- `Pilot.loot()` and `Pilot.lootmap()` (no loot intent, no `lootmap` verb).
- `Pilot.reflex(dodge=..., traps=...)`.
- Plan scenarios (a top-level `"plan"` key): `gamelab/runner.py` writes `PlanData.as`
  (`PLAN_LINES`), but no `Plan.as` reads it.

The client fails fast: those Pilot calls raise `NotImplementedError` and a plan scenario ends
with a `GameError`, both before anything is sent to the game. Nothing was deleted, so the
features can be restored if the in-engine code returns.
