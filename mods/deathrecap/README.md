# deathrecap

League-style death recap. While you are dead a panel at the top middle
(moved below the boss bar while one is up) shows, first, the total damage of
the last ten seconds with the physical / elemental split, then the five
biggest sources. Collapsed ([-] on the title row) it keeps the total line.
The party sees a one-line summary in chat.

- `[Hook] PlayerDamageTaken(Player@, DamageInfo@)` (fires after mitigation)
  appends to a ring buffer for the **local** player only: source name,
  post-mitigation amount, and a physical/elemental split derived from the
  pre-mitigation components of `DamageInfo`.
- Source names: a player's name for player damage, otherwise the attacker
  unit's producer path prettified (`actors/undead/lich_king.unit` -> `Lich
  King`); no attacker (traps, lava, DoT without owner) -> "Hazards".
- `HWPDeathRecapModule` implements `IEventPlayerDied`; on the local player's
  death it aggregates, fills `HWPDeathRecapHUD` (added through
  `[Hook] HUDConstructor`, visible while `record.IsDead()`), stores the
  summary in the player record (`deathrecap.last`) and sends
  `deathrecap.announce` to the host, which broadcasts `deathrecap.show`; every
  machine prints "<name> was killed by A 60%, B 30%, C 10%" unless
  `hwp set deathrecap.chat false`.
- Clicking the panel's title row collapses / expands it (HUD components get
  no mouse input, so `HWPDeathRecapHUD.Update` hit-tests the cursor against
  the title row on a menu Forward press); the choice is the setting
  `deathrecap.collapsed`.
- `hwp recap` reprints your last recap.

## Boss-fight recap (`BossRecap.as`, 2026-10-25)

When a boss fight ends, a second panel (top middle, below the death recap's spot)
lists every player's damage in it, most first: a header line in the player's
colour ("Name  12,345 dealt (45%)  -  1,234 taken") and up to five source
lines (skill name, amount, share). It stays `deathrecap.boss_seconds` (15)
seconds or until the title row is clicked; `deathrecap.boss false` turns the
panel and the chat lines off. Every machine also prints one chat line per
player ("Name dealt 12,345 to Bandit Lord (45%): Skill 40%, Skill 30% - took
1,234") and logs `[HWP:deathrecap] boss recap <boss>: <name> dealt N (P%) took
T: <source> <amount>, ...`. `hwp bossrecap` reprints the last fight (kept in
the player record, `deathrecap.boss_last`) and logs `boss panel shown: N lines`
/ `boss panel hidden`.

- Recording is per machine, for its own player: `PlayerDamagedActor` fires only
  on the attacker's machine (`CompositeActorBehavior.Damage` calls the local
  attacker's `DamagedActor`; the others get a `UnitDamaged` message and no hook),
  so a client records its hits on boss-tagged actors (`Tags` has the `boss`
  actor tag, as `gl kill tag:boss` tests) by skill (`PlayerBase.GetSkill(di.Weapon)`,
  "Other" without one) and the damage it took while a hit boss was alive
  (`PlayerDamageTaken`), counted once however many boss units are up.
- Burn, poison and bleed skip `DamagedActor`: they are the boss's affliction
  pools, filled by hits on the machine that dealt them (`AddAffliction`, right
  after the hook) and ticked as DoT with no hook. Each fight keeps the pools'
  total as it has counted it: a hit adds what `AddAffliction` will add (the
  same arithmetic), and each frame the drop since the last look is counted as
  "Afflictions" (times `AfflictionDamageTakenMul`) when the local player filled
  the pools last (`m_affectionAttacker`). The pools are tracked per boss unit. Effects marked `dot` (three vanilla
  files) are still not counted.
- A fight is the whole encounter, not one boss unit (issue #33). Every
  boss-tagged actor the player hits joins the open fight (log `... joins, N units
  hit`), and the fight lasts while any of them is alive or the HUD still shows an
  undefeated boss bar. That is vanilla's own encounter: `HUDBossBar` stacks one bar
  per `bossbar` actor and clears them once all are down. So one of the four Serpents
  of Demise (boss-tagged `TransferDamageActor`s feeding one health unit with the
  bar), a Bandit Lord's mirror image or a spawned ghost going down logs `... down,
  N hit units alive, B boss bars up` and nothing else. The fight is named after the
  bar ("Serpents of Demise", "Bandit Lord"), else the first boss unit hit. A boss
  bar already up for a boss elsewhere on the floor also keeps the fight open (none
  of vanilla's boss floors does that).
- When it ends (polled each frame: `IsDead` is set everywhere by `UnitKilled`)
  the machine sends `bossrecap.report` to the host, which gathers the party's
  reports for 1 s per fight name (the bar's name is the same on every machine)
  and broadcasts `bossrecap.show`; everyone shows / prints / logs the same list.
  The host keeps one report per peer (two players may share a display name).
- A player who never hit the boss is not listed.

## Settings

On the HammerwatchPlus tab of the player menu (Quality of Life > Death recap), per player:

| Setting | Default | |
|---|---|---|
| `deathrecap.enabled` | on | off: no death panel, no recap chat lines, no boss panel; open panels close at once. Your share of a boss fight is still recorded and sent, so the party's boss recap stays whole, and `hwp recap` / `hwp bossrecap` still answer |
| `deathrecap.chat` | on | the chat lines (deaths and boss kills) |
| `deathrecap.boss` | on | the boss recap panel and its chat lines |
| `deathrecap.boss_seconds` | 15 | how long the boss panel stays up (5, 10, 15, 30, 60) |
| `deathrecap.collapsed` | off | the death panel shows only its total line (also set by clicking its title) |

## Test checklist

1. `python -m gamelab run mod-deathrecap --mode lab`: no script errors.
2. Solo: let a few enemy types hit you, die. The panel lists them with
   plausible percentages; log line `[HWP:deathrecap] <name> died: ...`. Panel
   disappears when you are back in town. `hwp recap` prints the summary.
   Clicking the title row collapses and expands it.
3. Stand in a trap / poison cloud: the source reads "Hazards".
4. Co-op: the other player sees the chat line in your player colour; their own
   death shows their panel only on their screen.
5. `hwp set deathrecap.chat false`: no chat line on the next death.
6. `python -m gamelab run fix-recaps --mode lab` (section `boss` of
   `gamelab/bots/fix_recaps.py`): Bandit Keep floor 0, the Bandit boss spawned
   beside the ranger, shot for a few seconds, then `kill tag:boss me`: the log
   line `boss recap Bandit Lord: Pilot dealt N (100%) took T: ...` with N > 0
   and a named source, `hwp bossrecap` -> `boss panel shown: N lines`, shot
   `boss-recap` (the panel, by eye). Co-op (manual): both players appear on
   both machines, in their colours, with their own skills.
7. Several boss units, one fight (`fix-boss-recap-encounter`, issue #33): the
   Bandit Lord and its mirror image both hit are one fight; the mirror's death
   logs `down` and no recap; the Lord's gives one recap of 2 units. Then the
   Serpents of Demise on their own floor (dark_citadel 18, the level's
   `BossStart` script): a serpent killed logs `down` with the bar still up and no
   recap; the rest and the health unit give one recap. By hand: the real
   serpent fight shows one recap, at the end.
