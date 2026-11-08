# outofcombat - Out of combat speed

Issue #99: "Out of combat speed boost x2 speed if you haven't attacked an enemy in the last
10 seconds".

In a run, a player who has not hit an enemy for 10 seconds moves twice as fast. The boost
ends the moment they hit one, and comes back 10 seconds after their last hit. A new floor
starts boosted, since nothing has been hit there yet. While it is on, the buff bar shows
the vanilla shrine speed blessing's icon, "Out of Combat" (the hover text with `bufftips`
says the speed and the wait, with no countdown).

## How it works

- **Speed: a buff.** `tweak/hwp/buffs_outofcombat.sval:hwp_outofcombat`, whose `speed-mul`
  the module sets from `outofcombat.speed`. `Player.Update` multiplies the move speed by
  `ActorBuffList.MoveSpeedMul` (`Player.as`, the Moving block), the way every vanilla speed
  buff works (the combo's bursting speed, Apothecary's Tincture), so it stacks with them and
  stops when the buff goes. The buff is added locally (husk, not networked), like
  `legacy`'s Title Bonuses buff. Its timer is reset to 5 seconds every frame while the boost
  is on. When the boost ends, the timer is set to 0 and the buff list drops the buff on its
  next update. The timer stays short because a player's buffs are saved with the record
  (`PlayerRecord.Save`, `actor-save`): they carry over a level change and into a saved
  character, and the host reloads them as networked buffs, so a long timer would outlive
  the boost on the other players' copy of the host.
- **Hits: the `PlayerDamagedActor` hook.** It fires on the attacker's own machine
  (`CompositeActorBehavior.Damage` calls `DamagedActor` on the local attacker), for a hit
  that did damage. It counts the local player's hits on an actor of another team. A summon's
  hits count too, since `PlayerOwnedActor.DamagedActor` goes through its owner. Burn, poison
  and bleed ticks don't count (no hook), and neither do pots and crates (not actors).
- **Co-op.** Each machine moves its own player, and the others only see the position, so
  each machine runs the timer and the buff for its own local player: a client is boosted
  exactly as the host is, and everyone sees the others move faster. The settings are the
  host's. Other players don't see your buff icon.

## Choices

- **Taking damage does not end it.** The issue asks for attacking only. A player running
  past enemies keeps the boost until they hit something.
- **Not in town** by default, since there is nothing to hit there and every walk would be
  boosted. `outofcombat.town` turns it on there too.
- **The game's top speed still applies.** `Player.Update` caps the move speed at
  `Tweak::PlayerSpeedMax` (8, or 2.22 times the base 3.6). With +20% movement speed from
  gear, 2x would be 2.4 times the base and is capped at 2.22. Vanilla's slow resistance also
  scales speed buffs (`MoveSpeedMul(slowScale)`), so a slow-resistance item makes the boost
  smaller, as it does for every vanilla speed buff.

## Settings

On the Plus tab of the player menu (Quality of Life > Out of combat speed), the host's:

- **On/off** `outofcombat.enabled` (on). Off: the buff goes within a frame.
- **Speed** `outofcombat.speed` (2x): 1.25x, 1.5x, 2x, 2.5x or 3x.
- **Time without a hit** `outofcombat.delay` (10 s): 3, 5, 10, 15, 20 or 30 s.
- **In town too** `outofcombat.town` (off).

`hwp outofcombat` prints the settings, the seconds since your last hit and whether you are
boosted; `hwp outofcombat hit` counts as hitting an enemy now (for testing).

## Test checklist

1. `python -m gamelab run mod-outofcombat --mode lab`: `[HWP:outofcombat] ready: buff
   loaded, 2x after 10 s`; no buff in town; on `bandit_keep` floor 0 the buff is on with a
   HUD icon; `hwp outofcombat hit` takes it off; with the delay at 3 s it is back 4.5 s after
   a hit; switched off, it goes.
2. `pkgfeat/pf-mod-outofcombat`: the same against the built Quality of Life package.
3. Manual, solo: start a run. The speed blessing icon is in the buff bar and you walk
   visibly faster than in town. Hit an enemy: the icon goes and you walk at your usual
   speed at once. Get hit without hitting back: the boost stays. Stop fighting: the icon
   is back 10 s after your last hit. Hover the icon (with `bufftips`): "2x movement speed",
   no countdown.
4. Manual, two players (host and client): both get the boost on their own and lose it on
   their own hits; on each screen the other player runs faster while boosted. The host sets
   the speed to 1.5x: the client's boost follows.
5. Die and get revived, change floors, enter town: never two icons; in town no icon (with
   `outofcombat.town` off).
