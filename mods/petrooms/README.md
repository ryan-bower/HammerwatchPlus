# petrooms

Pets keep out of puzzle rooms and trap rooms. A shared module (`module.json`
`shared: true`): it is in the Quality of Life package, and the Pets package
carries it too (`pets` requires it), so either package, or the All pack, has it.

- **What is a room.** Around a position, within `petwait.radius` (default 120 px):
  one puzzle unit (`doodads/buttons/*`, anything with `puzzle` in its path), or
  trap units on three spots (anything under a `traps/` folder but
  `traps/projectiles/`: floor spikes, pressure plates, shooters, sawblades, statues,
  tripwires, mines, the campaign's `doodads/hwp/traps/*`); units within 12 px of each
  other are one spot, so a campaign glyph (the glyph and its `_explode` unit) is one.
  A glyph in a hallway is not a room; the campaign's three-spike row is a small one
  the pet waits out while you cross it.
  Units are fetched with `FetchAllUnits` (buttons have no collision, so
  `QueryCircle` never returns them) and the distance is checked.
- **Owner in a room.** The pet walks back along the owner's trail (a point every
  16 px of the owner's movement, 64 kept; a jump past 320 px starts it over) to the
  nearest point that is clear, and idles there: no pickups, no following, no skills.
  It rejoins when the owner leaves (`Rejoin`: straight to the owner).
- **Pet in a room, owner outside.** The pet walks out the same way and waits there
  until the owner has moved 96 px on, so it does not wander straight back in, or
  until the room is gone (its traps or buttons destroyed).
- **Crossing.** A pet going back to its owner after either wait may cross a room
  on the way, for up to 5 s or until it is within 48 px of them, so an owner who
  crossed a trap room is followed through it rather than waited for at its door.
- **Which pets.** The Pets package's classes (`HWPMiniPetWalking/Flying`) are
  `HWP::PetWait::Owned`: they run their Watcher in their own Update and skip it while
  parked. Every other pet (vanilla) is driven by `PetRooms.as`: while parked, the
  owner's own pet has no `m_owner` between frames, so its vanilla Update returns at
  once; each tick gives the owners back first and takes them again only after every
  Watcher has stepped. A husk pet (another player's) keeps its owner and has its
  target cleared.
- Settings: `petwait.enabled` (the module's toggle) and `petwait.radius`, host-synced.
- Summons waiting outside puzzle rooms are `mods/puzzles` (`SummonHold.as`).
