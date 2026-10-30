# mmhmm

**Mm-hmm!** A quarter of rare and epic hats carry a bonus modifier on top of their rolled
ones (never one of their slots): a village woman's "mm-hmm!" (`interact_female_2`, the
Equipment Buyer's, Enchanter's and Mystic's voice), from the wearer's body, at their best
moments.

## The voice

- **From the wearer.** It is a 3D sound on the wearer's unit (`PlaySound3D`, it follows them),
  so everyone hears it, from where that player stands, fainter far away. Before issue #31 it
  was 2D: as loud for everyone, from nowhere.
- **Plays to the end.** A wearer's next voice waits `VOICE_MS` (500 ms) after the last; the
  longer take is 0.37 s. Crits closer together are held back, not stacked or cut short.
  Every machine gates each wearer on its own (the crit trigger is net-synced, the moments
  are broadcast), so all of them hold back the same voices. `SoundInstance` cannot report
  that an event has stopped, so the gate is a time.
- **Which voice.** `interact_female_2` has two takes, both a short nasal "mm-hmm!" (0.28 s
  and 0.37 s), and FMOD picks one per play; a script cannot pick the take. The other
  village women (`female_1`, `female_3`, `female_4`) mix theirs with other words.
  `female_5`..`female_10` are player voices (`players/voices.sval`). It is one constant
  (`SOUND` in `MmHmm.as`) if another voice is wanted.

## When it plays

All of them only while the hat is on (`HWP::MmHmm::Wearing`).

| Moment | How it is noticed |
|---|---|
| Every critical hit | the modifier's own crit `TriggerEffect` (`tweak/hwp/modifiers_mmhmm.sval`), net-synced; its effect `HWPMmHmmVoice` says it through `Voice` (held back while the last one plays) |
| You revive someone, or someone revives you | class swap `PlayerCorpse` -> `HWPMmHmmCorpse` (`Corpse.as`): `NetRevive` runs on every peer with both records; the machine of whichever wears the hat says it, once per revive when both do. Not `cht_revive` (no other reviver) |
| You drink from a well or fountain | run stat `wells-used` rose (`WorldScript/Well.as` Use) |
| A secret room opens | run stat `secrets-found` rose (`SecretFound.as`, on every peer: one voice for the party however many wear it). The few secret prefabs without `SecretFound` are missed |
| You complete a trinket set | the trinkets you own of a set reach its `m_totItems` (owning counts, as `PlayerRecord.RefreshModifiers` counts them) |
| You take the last orb of an orb tree | a `pickedTempSkills` entry reaches the tree's size; trees of one orb do not count |
| You open an Ace chest | `mods/keys` counts the local player's in GlobalCache `hwp_keys_aces_opened` (vanilla's `chest-unlocked-<key>` stat is not defined for "ace"); without keys there are no Ace chests |

The non-crit moments are polled twice a second (`Moments.as`); the first poll of a level
only takes the counts, so nothing fires for what the character already had. A moment goes
to the host (`mmhmm.say` request), which plays it on every peer (`mmhmm.say` event, with the
reporting peer, whose player is the wearer) and drops the same key within 1.5 s. Each peer
logs `[HWP:mmhmm] voice: <why> from <unit> at x,y` for every voice it plays (crits too).

## Which hats

Rare and epic head items, CHANCE (25) percent of them by a pure hash of the item (its base
item, level, quality and rolled modifiers), so a hat never flips and every machine agrees.
The generator has no hook: the local character's worn and bagged hats are checked twice a
second and a qualifying one gets the modifier added. A dropped or shop hat shows it once it
is yours. Legendary items keep no modifiers (Item.Finalize), so they never have it. The
modifier is never rolled (spawn-chance 0, quality "quest", which also keeps it out of the
enchanter's slots and out of an epic item's name).

`hwp mmhmm` reports the worn hat, whether it has the bonus or qualifies, and this session's
crits, moments, voices played and voices held back; `hwp mmhmm give` (cheats) adds it to the
worn hat; `hwp mmhmm voice [n]` (cheats) says it n times at once (one plays).

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
   hat is off. Each crit's voice logs `voice: crit from players/player.unit`; `hwp mmhmm
   voice 5` plays one and holds back four, logged at the player's own position, and one
   plays again 0.7 s later. GameLab is muted, so the sound itself is not measured.
2. Co-op (two players, by hand): revive each other with and without the hat; both hear it
   once per revive while either wears it, from the wearer.
3. By ear (not tried yet): a crit streak says "mm-hmm!" whole, never stacked or cut; walk
   away from a wearer and it fades.
