# hwplib-classui

The class screens part of the HammerwatchPlus library. Not a mod players install: the
packages that add classes or specializations carry it (Firearms, Specs, HoH1 Classes;
`packages.json`). Requires `hwplib`.

| File | Provides |
|---|---|
| `scripts/HWP/Core/HiddenClasses.as` + `scripts/GUI/CreateCharacter/CreateCharacterClass.as` (declared override, `.orig` beside it) | `HWP::HideClass(id)`: a class left out of the create-character list (a parked class). The list is fitted to 7 classes across so the added ones show |
| `scripts/HWP/Core/SubclassPick.as` | **Subclass Picker skill row by type.** The vanilla picker shows a spec's last two skill defs as "Active" and "Passive", wrong for the HWP specs (Sniper's Flashbang and Decoy are both actives, Snipe never shows). This part patches the open picker in place each time it shows another class: the spec's own skills (those its parent class lacks), actives first then passives, each labelled by its real type, up to four slots across the row. Vanilla specs look the same as before. GameLab: slots are `skill-active-name`, `skill-passive-name`, `hwp-pick-name2`..; labels `hwp-pick-label0`..; `gl classskills <classId>` lists the defs it is checked against |

Subclass Picker skill row (plan checks): `picker_skill_labels` (plan_firearms.py, the three
doctrines) and `<class>_picker_skill_labels` (plan_classesb.py: thief, gladiator,
witchhunter, and the priest / paladin 4th spec) read the row from `gl widgets` and compare
it with `gl classskills` (gamelab/bots/picker_skills.py).
