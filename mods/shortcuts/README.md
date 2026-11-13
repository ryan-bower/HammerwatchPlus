# Dark Citadel candles

Extends the existing Dark Citadel shortcut challenge, not the town run-start menu.
Light candles before starting the fight, defeat all the shades, then use the portal:

| Lit candles | Destination |
|---|---|
| 0 to 3 | Dungeon, as in vanilla |
| 4 | Barracks, as in vanilla |
| 5 | High Courts, floor 1 |
| 6 | Dark Halls, floor 1 |
| 7 | HoH1 Battlements, floor 1 |

The three new candles sit west, north and east of the original four. Each adds the
same shades on each of the challenge's four waves as an original candle. They can
be extinguished before starting, but cannot be changed once the fight starts.
Every lit candle, including the three added ones, adds one skill sphere and three
trinket rolls to the challenge's baseline of one sphere and nine trinket rolls.
Five, six and seven candles therefore award six, seven and eight spheres and
24, 27 and 30 trinket rolls respectively, using vanilla's rarity settings.

The extra candles require the same shortcut unlock as vanilla's four-candle
Barracks skip (shortcut 3, checked at the current NG+). Before that, vanilla's
random pair of candles remains. No unlock flags, saves, NG+ rules or mission
definitions are changed. Normal exits and the final boss's victory logic are unchanged.
Six candles enter `dark_halls_1`, followed by Dark Halls 2 on the expanded route.
Seven enter `hwp_battlements_1`, followed by Battlements 2 and then the Avatar.
Neither count jumps directly to the boss. Dark Halls 2 has no separate candle
threshold. Without the campaign import or a matching HoH1 import on every peer,
the seven-candle exit warns the party and goes to Dark Halls 1 instead. This also
keeps the Quality of Life package usable on its own: an unknown mission floor id
would otherwise end the mission as a success.

This is a level-data override plus a guarded Battlements exit in Quality of Life,
with no in-game toggle. All peers
should use the same package build. Disable the package to restore the vanilla level.

Regenerate with `python tools/generate/make_shortcut_candles.py`; the pristine
`.lvl.orig` is the input. To update it after a reviewed game update, supply the
unpacked game's level with `--source` (the generator refuses to replace a different
pristine file automatically). `--check` and `tests/test_shortcut_candles.py` run offline.

## In-game checks still required

On the pinned build, test all eight candle counts, turning a candle back off,
repeated Use, and attempts to change candles after starting. Confirm four waves,
no early portal, one destination, the increasing loot payout, the next floor after each
skip, and victory after the Avatar. Repeat locked/unlocked at NG0 and NG+ and on a
real host/client pair. Check all three new candles are visible and reachable and
that reloading a saved challenge keeps its state. Host-side graph tests are not
evidence of these live behaviors.
Check seven candles with the matching campaign import, with HoH1 disabled, with a
mismatched client, and with Quality of Life alone: the last three must warn and
enter Dark Halls 1, never end the mission or load missing HoH1 assets.
