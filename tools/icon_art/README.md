# icon_art: skill and orb icon ideas in the vanilla style

Generators for 24x24 skill icons painted the way the vanilla HoH2 skill icons are: no
outlines, 4-6 step ramps lit from the upper left, a bright rim and a dark core shadow,
big cropped subjects, glowing energy with a white-hot core, near-black tinted grounds
(vpaint.py's docstring has the full list). Each icon function returns three ideas,
A (the gear up close), B (the moment it happens) and C (an abstract mark), for the user
to pick from; nothing here writes to a mod. A picked Firearms icon goes into the game
through `art/firearms/override/` and `tools/make_firearms_icons.py`.

| file | what |
|---|---|
| vpaint.py | the painter: ramps, SDF shapes, grounds, glows, `sheet()` |
| motifs.py | Firearms objects: guns, rounds, mags, rockets, turrets |
| vm.py | vanilla-class objects: blades, shields, bows, books, elements, bodies |
| fa.py, fa2.py, fa3.py | the Firearms Specialist's icons (skills, orbs, attacks, HUD) |
| fa_r2.py | round 2 of those: three ideas per icon built on the round-1 pick and note (`out/picks_r1.json`); the 14x14 buff-bar icons at their own size |
| vo_<class>.py | each vanilla class's orb icons |
| sp.py | the six 4th specializations' icons (`art/specs/REQUESTS.md`): three ideas each, their picker page, and `--pick` to write the chosen ones to `art/specs/override/` |
| sp_r2.py | round 2 of those: three ideas per noted round-1 pick (`out/specs/picks_r1.json`) and for every Deadeye and Aerotheurge icon, with the pick beside them, and their picker (ids `specs2.<name>`) |
| sp_r3.py | round 3: three new designs each for the six spec emblems and the 18 icons that were recolours, shrunken copies or reused another icon's motif, with the icon in game beside them, and their picker (ids `specs3.<name>`) |
| sp_pri.py | the Priest's 4th spec (Devil Forgemaster): three ideas each for its two skills, Sacrificial Penance and the Heresy stack below 5 and at 5+, and their picker (ids `specsP.<name>`) |
| sp_pri2.py | its round 2: three refinements of each round-1 pick (the pick beside them) and first ideas for the emblem, the four orbs and the eating status (ids `specsP2.<name>`) |
| sp_fx.py | their four world sprites: frame strips on a transparent ground to `art/specs/fx/`, 4x GIF previews in `out/specs/fx/` |
| planner_icons.py | the class planner's icon sheet (`planner/web/`), cut from the game's atlases |
| orb_groups.py | the picker's per-class orb lists, from the planner's data |
| render.py, rorb.py | write the ideas and comparison sheets |
| picker.py, picker_tpl.html | the picker page (every idea, the current icon beside it) |
| grid.py | a labelled review grid of any icons |

Everything is written under `tools/icon_art/out/` (git-ignored):

```
python tools/icon_art/render.py all            # Firearms ideas -> out/firearms/, out/sheet_all_*.png
python tools/icon_art/fa_r2.py                 # round 2 -> out/firearms_r2/, out/sheet_r2_*.png
python tools/icon_art/planner_icons.py         # planner/web/icons.png (also the "now" column)
python tools/icon_art/rorb.py warrior          # one class's orb ideas -> out/orbs/warrior/
python tools/icon_art/orb_groups.py           # out/orbs/<cls>.json
python tools/icon_art/picker.py [r1]           # out/picker.html (Firearms round 2, or round 1 with r1)
python tools/icon_art/sp.py --picker           # the 4th specs' ideas -> out/specs/, sheet_<spec>.png, picker.html
python tools/icon_art/sp.py --pick picks.json  # the chosen ones -> art/specs/override/<name>.png
python tools/icon_art/sp_r2.py --picker        # round 2 -> out/specs/r2/, sheet_<spec>.png, picker.html
python tools/icon_art/sp_r3.py --picker        # round 3 -> out/specs/r3/, sheet_<spec>.png, picker.html
python tools/icon_art/sp_pri.py --picker       # the Priest's 4th spec -> out/specs/pri/, sheet_priest.png, picker.html
python tools/icon_art/sp_pri2.py --picker      # its round 2 -> out/specs/pri2/
python tools/icon_art/sp_fx.py                 # the world sprite strips -> art/specs/fx/, previews out/specs/fx/
```

planner_icons.py and orb_groups.py read the class planner's records in `planner/data/`
(another folder of the same layout can be passed as the first argument). Needs Pillow, and
`gamecode/` for the vanilla atlases.
