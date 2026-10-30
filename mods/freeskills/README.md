# freeskills

A respec at the Skill Trainer unlearns the skills a class starts with too, and the trainer
sells them back for free (issue #78).

- **Vanilla.** A class starts with some skills already learned: each one's sval has
  `starting-level` 1. That covers the vanilla first skill and passive (the Paladin's Blessed
  Strikes and Armor), the HWP classes' starting skills (Gladiator, Thief, Witch Hunter), the
  Firearms Specialist's Reload, Frag and doctrine skills, and each specialization's two. The
  game stores a skill's level as the levels bought (`pickedSkills`) plus `m_startingLevel`.
  A respec (`WindowSkillTrainer`, "respec-skills yes") clears the levels bought, so these
  skills stayed at level 1. You couldn't drop one to put its points elsewhere.
- **Now.** After a respec these skills are at level 0, not learned. The trainer shows 0 on
  their first level, and learning one takes no skill points, even with none left. The rest
  of the respec is vanilla: its cost, and every point back.
- **How.** A class swap (module.json `class_swaps`) points the trainer unit at
  `HWPSkillTrainerContent`:
  - **Respec.** Its window, `HWPSkillTrainerWindow`, runs the vanilla respec. It then saves
    each starting skill as bought `-starting-level` (level 0) and tells the other players
    (`PlayerResetPickedSkills`, then one `PlayerSyncSkillLevel` per skill). Vanilla's respec
    never told them.
  - **Buying back.** Points spent only count levels from `starting-level` up, so a negative
    pick costs nothing. `Buy` takes it up one level itself, because `SkillUp` would check the
    level's sval cost against the free points. `GetItems` marks that level cost 0 and
    buyable.
  - **The cost shown.** The window reads costs from the skill's level costs, so while it
    draws, the free levels read 0.
  - **Saves.** A save keeps the negative pick, but `PlayerRecord.Load` clamps it to 0, so the
    `PlayerRecordLoad` hook puts it back.
  - **Without the mod.** With the mod removed, the skills load learned, as vanilla has them.
- **Divine Favor.** The Forgemaster's free Divine Favor (`specs`) is a bonus skill point, not
  a starting level. The respec takes the Favor level back and the point stays, so learning it
  again still costs nothing in the end.

`hwp freeskills` lists the class's starting skills as `id pick/level` (pick -1 is unlearned)
and the free and spent skill points.

## Settings

On the HammerwatchPlus tab of the player menu (your own), or `hwp set`:

- `freeskills.enabled` (on): off is the vanilla respec, with the starting skills learned
  again. A skill already unlearned stays free to learn.

## Test checklist

1. `python -m gamelab run mod-freeskills --mode lab`: `[HWP:freeskills] self-check done: on`.
   - A Paladin buys Lay on Hands 1 and respecs.
   - Blessed Strikes and Armor go to pick -1, level 0, with every point back.
   - The trainer lists both at level 1 for free. Blessed Strikes is learned again with the
     free points unchanged.
   - After a save and a restart, Armor is still unlearned and is learned again for free.
   - Off, the respec is vanilla: both are learned.
   - The shot `freeskills-after-respec` shows 0 under both first levels and 3 under the
     others.
2. `pkgfeat/pf-mod-freeskills`: the same, against the built Quality of Life package.
3. By hand, in co-op: respec on a client. The host's player menu shows the client's starting
   skills at level 0. Learn one back and it shows level 1.
