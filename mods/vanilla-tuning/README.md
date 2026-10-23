# vanilla-tuning

One Dev Arena tuner version (`mods/devarena`, Tune tab), shipped as a play mod. It changes
numbers on vanilla class skills: damage, cooldowns, cast points, level curves.

- `tweak/hwp/vanilla_tuning.sval` holds the version's edits. Each row is
  `[skill id, level index, path, value]`, where level 0 is the base `skill` dict and k is
  `upgrades[k-1]`. The committed file is v0 (no edits), so the mod does nothing until you export.
- `scripts/HWP/VanillaTuning/Apply.as`: while a local player exists, every skill def the edits
  name gets copy-on-write patches, once per def, followed by one `PlayerBase.LoadSkills`. No
  base file is shadowed.
- `scripts/HWP/VanillaTuning/Patch.as` is GENERATED from the Dev Arena's `Patch.as`. Don't
  edit it. `tests/test_devarena_tools.py` fails when it is stale.
- Don't enable this mod together with `devarena`. The tuner would snapshot the already-tuned
  defs as "vanilla".
- Multiplayer (assumed, not measured): every peer needs the same file, because each patches
  its own defs.

## Export

```
python tools/devarena/overrides.py sync              # last tuner state -> devarena's override file
python tools/devarena/export.py --version live       # or N, a, b; --log LOG reads a log directly
python tools/devarena/export.py --patch              # only regenerate Patch.as
```

## Test checklist

1. Export a version that has edits, enable the mod on a save, and start a run. The log shows
   `[HWP:vanilla-tuning] loaded N edits` at the menu and `patched K skill defs (N edits
   applied, 0 failed)` once in a run.
2. The skill's tooltip and its hits use the new numbers.
3. Switch class in town. The new class's defs are patched when it first shows up.
