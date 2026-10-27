# Way Gates

A remake of Tyraen's "Teleport in City" (Steam Workshop 3737378330): teleport gates across
the town. There is one gate in the town square and one at every building you have built.
Use a gate (the vanilla teleport beacon's lit pad, with a blue glow) to get a list of the
town's gates. Pick one and you step out of it, with a puff of smoke at both ends. The gate
you are standing at is greyed.

- The host spawns the gates 800 ms after the town loads. When a building upgrade reloads
  the town, the host spawns them again. Every machine builds the same list, so the menu
  matches on clients.
- Each gate sits at the building's own cell, three cells south of where the town's base
  segment placed it. These are the cells `TownRecord.SpawnTown` uses. Vanilla buildings
  are all plotless and carry no footprint size, so in the walk-in buildings the gate is
  near the vendor. A building on a plot with a footprint gets the middle of the
  footprint's bottom edge instead. Either way the gate moves to the nearest free spot
  (no furniture or wall in a 20x20 box).
- The gates are hwplib's `HWPLocalNPC` units. Vanilla keeps one NPC of a unit type on the
  host and removes the rest.

| Setting | Default | |
|---|---|---|
| `waygates.enabled` | on | gates spawn and can be used. Off: they can't be used at once, and the host takes them away within a second; on again, the host places them |
| `waygates.square_x`, `waygates.square_y` | -504, 196 | the town square gate |

`waygates.enabled` is on the HammerwatchPlus tab of the player menu (Quality of Life >
Way gates); the host's value rules in a lobby. The square's position is not on the tab.

Commands: `hwp waygates` lists the gates and their positions. `hwp waygates go <n>` takes
gate n (cheats only).
