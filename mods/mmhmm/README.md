# mmhmm

**Mm-hmm!** A quarter of rare and epic hats carry a bonus modifier on top of their rolled
ones (never one of their slots): the Material Trader's "mm-hmm" (`interact_male_8`), for
everyone, at the wearer's best moments.

## When it plays

All of them only while the hat is on (`HWP::MmHmm::Wearing`).

| Moment | How it is noticed |
|---|---|
| Every critical hit | the modifier's own crit `TriggerEffect` (`tweak/hwp/modifiers_mmhmm.sval`), net-synced and 2D, no cooldown |
| You revive someone, or someone revives you | class swap `PlayerCorpse` -> `HWPMmHmmCorpse` (`Corpse.as`): `NetRevive` runs on every peer with both records; the machine of whichever wears the hat says it, once per revive when both do. Not `cht_revive` (no other reviver) |
| You drink from a well or fountain | run stat `wells-used` rose (`WorldScript/Well.as` Use) |
| A secret room opens | run stat `secrets-found` rose (`SecretFound.as`, on every peer: one voice for the party however many wear it). The few secret prefabs without `SecretFound` are missed |
| You complete a trinket set | the trinkets you own of a set reach its `m_totItems` (owning counts, as `PlayerRecord.RefreshModifiers` counts them) |
| You take the last orb of an orb tree | a `pickedTempSkills` entry reaches the tree's size; trees of one orb do not count |
| You open an Ace chest | `mods/keys` counts the local player's in GlobalCache `hwp_keys_aces_opened` (vanilla's `chest-unlocked-<key>` stat is not defined for "ace"); without keys there are no Ace chests |

The non-crit moments are polled twice a second (`Moments.as`); the first poll of a level
only takes the counts, so nothing fires for what the character already had. A moment goes
to the host (`mmhmm.say` request), which plays it on every peer (`mmhmm.say` event) and
drops the same key within 1.5 s. Each peer logs `[HWP:mmhmm] voice: <why>`.

## Which hats

Rare and epic head items, CHANCE (25) percent of them by a pure hash of the item (its base
item, level, quality and rolled modifiers), so a hat never flips and every machine agrees.
The generator has no hook: the local character's worn and bagged hats are checked twice a
second and a qualifying one gets the modifier added. A dropped or shop hat shows it once it
is yours. Legendary items keep no modifiers (Item.Finalize), so they never have it. The
modifier is never rolled (spawn-chance 0, quality "quest", which also keeps it out of the
enchanter's slots and out of an epic item's name).

`hwp mmhmm` reports the worn hat, whether it has the bonus or qualifies, and this session's
crits and moments; `hwp mmhmm give` (cheats) adds it to the worn hat.

## Settings

On the HammerwatchPlus tab of the player menu (Quality of Life > Mm-hmm! hats); the host's
values rule in a lobby:

- **On/off** `mmhmm.enabled` (default on). Off: no hat gets the bonus and no voice plays
  (the crit trigger's chance is set to 0, the moments are not polled, the host drops
  `mmhmm.say`). Hats that already have the bonus keep it, so turning it back on finds them
  as they were; the first poll after that only takes the counts.
- **Hats with it** `mmhmm.chance` (default 25, percent of rare and epic hats; 10, 25, 50,
  75, 100). A lower value never takes the bonus off a hat that has it.
- **On every crit** `mmhmm.crits` (default on): the crit voice; the other moments stay.

## Test checklist

1. `python -m gamelab run mod-mmhmm --mode lab` (check_mmhmm): rare hats get it exactly when
   they qualify, a common hat never; crits with it are counted; in a run with the hat, the
   last orb of a 3-orb tree, a well, a secret room, an Ace chest and the 4th Charms of
   Fortune piece play it once each, a 1-orb tree, a first orb and the 3rd piece do not,
   the corpse is `HWPMmHmmCorpse` and `cht_revive` stays quiet, and nothing plays once the
   hat is off. GameLab is muted, so the sound itself is not measured.
2. Co-op (two players, by hand): revive each other with and without the hat; both hear it
   once per revive while either wears it.
