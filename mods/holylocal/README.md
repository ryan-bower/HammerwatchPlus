# holylocal: the Priest without the Celestial Ruins DLC, for the beta testers

**Remove this module before the mods are posted.** It is in the repo only while the repo is private
(made private on 2026-10-22 for the beta), so approved testers can play the Devil Forgemaster. Used with
the dev team's permission.

The Priest class (`players/priest/class_priest.sval`) and its scepters and lanterns
(`tweak/items/equipment/equipment_weapons_{mainhand,offhand}.sval`) carry the conditional
`dlc has holy`: the Celestial Ruins DLC. These three overrides are the base files with that one
conditional removed, nothing else (the `.orig` copies are the pristine base files, for
`tools/build.py --check`). After a game update, re-make them: copy the three base files from
`gamecode/sdk/hoh2/`, delete the `<array name="conditionals">` block that holds only
`<a><s>dlc</s><s>has</s><s>holy</s></a>` (one in the class, four in each weapon table), and refresh the
`.orig` copies.

It is `local_only` with `beta_into: "core"` (module.json): a beta build folds its three files into
HWP-core.bin, so a tester enables only HWP-core and HWP-specs as usual, and a build without `--beta`
never carries them (`tools/build.py` refuses to build it by name without `--with-local`, and it is never
in the all-in-one package).

    python tools/deploy.py modded-prod --beta      # build.py --beta, then the .bin files into <install>/mods
    python tools/build.py --beta --no-all core      # just the bin: "beta: HWP-core.bin carries holylocal"

Other `dlc has holy` gates (the chapel boons, the holy pets and trinkets, the heaven mission set, which
`MissionGameMode` checks in code) are left alone. Verified in the lab, whose game has no Celestial Ruins
DLC: with holylocal the create-character list offers the Priest, "select priest" shows its title and
"create" makes a Priest standing in town (`mod-holylocal-priest`); with core alone the list has no
Priest (`mod-holylocal-priest-control`). The run ids are in `docs/RE_NOTES.md`.
