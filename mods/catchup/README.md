# catchup - Catch-up experience (Co-op package)

Issue #73, the owner's spec: "Don't base it on the teammates' XP level, rather the NG+ level.
If you are under the cap for that new game plus level minus a level, i.e. NG+ below 20 or
NG++ below 25, you should get 50% increased XP. Add a buff to your screen for this effect,
call it something thematic."

In a run at NG+ n (n >= 1), a player whose level is below the level cap of NG+ (n - 1) gets
50% more experience. While it applies, the buff bar shows **Late Bloomer** with the vanilla
shrine experience blessing's icon; the hover text with `bufftips` reads "+50% experience while
below level 25 (NG+ 2)", with no countdown.

| Run | Bonus below level |
|---|---|
| NG+0 | none |
| NG+1 | 20 |
| NG+2 | 25 |
| NG+3 | 30 |
| NG+4 | 35 |

## How it works

- **The threshold** is vanilla's own cap formula one NG+ level down:
  `PlayerRecord.GetLevelCap()` is `Tweak::LevelCap` (20) + `ngp` x `Tweak::LevelCapNGPAdd` (5)
  (`Data/Player.as`), so the threshold at NG+ n is 20 + 5(n - 1). The module computes it from
  the same two constants, so a game update that changes them moves it too.
- **The run's NG+** is `g_ngp`, the difficulty the run was started at (`HWR2GameMode` loads it
  from the level save on every machine; the tab overlay shows it). It is not the character's
  own `ngp` (the highest NG+ they have unlocked) and not the teammates' levels.
- **A player at their own character's cap** gets no buff: `GiveExperience` stops at
  `GetLevelCap()`, so a level-20 character who never cleared NG+0, carried into an NG+2 run,
  could gain nothing from it.
- **The +50% is a buff.** `tweak/hwp/buffs_catchup.sval:hwp_catchup` has `experience-mul` 1.5.
  `PlayerRecord.GiveExperience` multiplies every gain by `ActorBuffList.ExperienceMul()` (the
  path the vanilla shrine experience blessing takes), so it covers kill experience
  (`Player.NetShareExperience`, from `PlayerShareExperience` on every machine) and mission
  rewards (`MissionManager.NetSetMissionState`, booked in the run before the level change).
  It stacks multiplicatively with the blessing, gear and the level difference scaling.
  Gains the game gives with `skipGainMod` (Experience-on-quantity trinket effects) are not
  boosted, as no buff boosts them.
- **Co-op.** Each machine books its own local player's experience: the killer's machine sends
  the kill's experience to all (`PlayerShareExperience`) and each applies it to its own
  player. So the buff is added locally (husk, not networked) to the local player only, as
  `outofcombat`'s and `legacy`'s are. Each player gets it for their own level; the setting is
  the host's. Other players don't see your icon.
- **The timer stays short.** The module resets the buff's timer to 5 s every frame while the
  bonus applies and sets it to 0 when it stops. A player's buffs are saved with the record
  (`PlayerRecord.Save`, `actor-save`) and carry over a level change, into a saved character
  and onto the host's networked copy, so a long timer would outlive the condition (see
  `outofcombat`). Extra icons of ours that are not the current actor's buff are hidden.

## When it stops

Within a frame of: reaching the threshold (or the character's own cap), going to town,
dying, or switching it off. A new floor starts it again while it still applies. The log has
`[HWP:catchup] bonus on: level 17 < 20 at NG+1` and `bonus off: level 20 >= 20`.

## Settings

On the Plus tab of the player menu (Co-op Play > Catch-up experience), the host's:

- **On/off** `catchup.enabled` (on). Off: the buff goes within a frame.

`hwp catchup` prints the run's NG+, the threshold, your level and whether the bonus applies
(and if not, why). `hwp catchup ngp <n>` checks against NG+ n instead of the run's until the
level ends (for testing; it changes nothing else), `hwp catchup ngp off` undoes it.

## Test checklist

Not tested in game yet (source review and pytest only).

1. Solo, NG+0 run: no buff; `hwp catchup` says "no (NG+0)".
2. Same run, `hwp catchup ngp 1` with a character below 20 (and below its own cap): the Late
   Bloomer icon shows; hover (with `bufftips`): "+50% experience while below level 20
   (NG+ 1)". Kill an enemy and compare the XP floater with the buff off (`hwp set
   catchup.enabled false`): 1.5 times as much (rounded).
3. Level to 20 with the buff on: the icon goes at the level-up; log `bonus off: level 20 >= 20`.
4. Town: no icon. Change floors: never two icons.
5. Two players (host and client) in an NG+2 run, one at level 22, one at 26: only the first
   sees the icon and gets 1.5 times the shared kill XP. The host switches it off: the
   client's icon goes.
