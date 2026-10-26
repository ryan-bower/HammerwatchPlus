# Tavern

The tavern gets three more levels past the vanilla three. Each level raises how many foods
and drinks a run can start with:

| Level | Needs guild hall | Cost (wood / stone / ore) | Foods | Drinks |
|---|---|---|---|---|
| 1-3 (vanilla) | | | 1 | 1 / 2 / 3 |
| 4 | 6 | 150 / 30 / 10 | 1 | 4 |
| 5 | 7 | 200 / 45 / 20 | 2 | 4 |
| 6 | 8 | 300 / 60 / 30 | 3 | 5 |

The new levels reuse the tier 3 building art.

## Files
- `tweak/town/buildings/tavern.sval` overrides the vanilla file and adds the three upgrades.
- `scripts/Missions/MissionFoods.as` overrides the vanilla file:
  - The slot counts come from `TavernFoodSlots` and `TavernDrinkSlots`.
  - Foods are a list, like drinks.
  - The first food keeps the vanilla mission buff key (`<id>food`). The others use `<id>food1` and `<id>food2`.
  - The save keeps the vanilla `food` entry and adds a `foods` array, so a save stays readable without the mod.
- Each override has its pristine `.orig` beside it, for `tools/build.py --check`.

GameLab: `mod-tavern` (`gamelab/bots/fix_tavern.py`).
