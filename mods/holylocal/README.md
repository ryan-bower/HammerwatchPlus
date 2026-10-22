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

It is `local_only` (module.json): `tools/build.py` skips it unless it is named with `--with-local`,
and it is never part of the all-in-one package, so a release build cannot carry it by accident.

    python tools/build.py --with-local holylocal
    copy dist\HWP-holylocal.bin "<install>\mods\"

Enable HWP-holylocal with HWP-core and HWP-specs on the save. Other `dlc has holy` gates (the chapel
boons, the holy pets and trinkets, the heaven mission set, which `MissionGameMode` checks in code) are
left alone. Not yet booted in the lab: the override check passes (`tools/build.py --check`), the
in-game effect is assumed until a tester reports.
