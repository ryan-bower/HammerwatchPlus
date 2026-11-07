# Party frames

Replaces the top-left co-op list with raid frames: class-coloured health, % readout, mana strip,
a shield at the end of the health bar, and each ally's potion count. Allies under 30% health get
a red border. An Arcane Sorcerer, who has Living Mana, is one solid blue pool with no mana strip.

Settings (Plus tab, Interface): on or off, Thick or Thin bars, Leading edge or Striped edge
shields, and Show level and Show class beside each name (both off by default; the bars widen to
fit). All per machine. A party too tall for Thick bars drops to Thin on its own.

Shields and potion counts arrive through `HWP::AllyStatus` in hwplib. Any shield mod reports with
`HWP::AllyStatus::ReportShield(fraction)`, as `mods/specs/scripts/HWP/Specs/Support.as` does. The
Striped edge art comes from `tools/generate/make_partyframes_art.py`.

## Testing

1. `uv run python -m gamelab run mod-partyframes --mode lab` draws stub allies through both sizes
   and both shield styles, the fall back to Thin, and the toggle to vanilla.
   `mod-partyframes-tutorial` raises the game's tutorial panel, which draws over this corner in
   vanilla too: the frames start below it while it's up and return when it closes.
2. `hwp partyframes demo [count | off]` shows the stub allies; `hwp partyframes` prints each
   player's reported shield and potions.
3. GameLab can't run two clients, so a real session is needed for:
   - shields both ways, and a third player seeing both;
   - potion drink, well refill and partial refill;
   - death, leaving and joining late;
   - whether burning or poison show a debuff icon (afflictions are damage pools, not buffs).
