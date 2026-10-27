# orbwarn

**Orb warning.** Some orbs are mutually exclusive (`blocked-by-skills`: the Firearms grenade
types, the RPG's warheads, vanilla ones too) and the vanilla picker never says so. While an
orb picker (`GiveSkillSphereMenu`) is open, each pick that would close others gets a red row
under its description: "Makes unavailable:" and every orb it closes, icon and name (icons
only when the names don't fit). `[HWP:orbwarn]` logs each pick. Only the in-run picker, not
the Sarcophagus or mission sphere selectors.

`scripts/HWP/OrbWarn/OrbWarn.as` (`HWPOrbWarnModule`) checks the open picker every frame; no
base file is overridden. The text is `hwp.orbwarn.closes` in
`res/language/english/hwp_orbwarn.lang`. Requires hwplib.

## Test checklist

1. `python -m gamelab run mod-orbwarn --mode lab`: a Firearms Specialist with Frag Grenade
   gets fixed picks: Stun Grenade lists Incendiary and Gas, Shrapnel lists nothing; once
   Stun is owned, its next level closes nothing more.
