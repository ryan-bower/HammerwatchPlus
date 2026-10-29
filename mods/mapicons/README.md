# mapicons

Module id `mapicons` (Quality of Life package). A dye-pot marker on the minimap over every
dye bucket of a floor. Setting `mapicons.dyes` (default on; `hwp set mapicons.dyes false`).
Requires `hwplib`, whose `gui/hwp/map_icons.png` sheet holds the icon
(`tools/make_map_icons.py`).

| File | Provides |
|---|---|
| `scripts/HWP/MapIcons/MapIcons.as` | marks each dye bucket once the floor is generated |
| `doodads/hwp/map_icon_dye.unit` | the marker unit (the dye pot frame of the sheet) |

Scenarios that load it: `fix-specs-risen-look`, `plan-farming-b`, `plan-fishing-d`,
`plan-ui-a`, `mod-all`.

## Settings

On the HammerwatchPlus tab of the player menu (Quality of Life > Map icons), each player's
own:

- **On/off** `mapicons.enabled` (default on). Off: no markers; the floor's markers go
  within a second.
- **Dye pots** `mapicons.dyes` (default on).
