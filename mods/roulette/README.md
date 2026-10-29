# Roulette

A remake of the lobby-wide roulette table from Steam Workshop 3787654264, played at a
wheel on a table in the tavern's main hall. The wheel turns slowly while betting is open
and fast while the ball runs. Use it to open the table.

- One single-zero table for the whole lobby. The host runs the rounds: 20 s of betting,
  5 s of spin, 5 s showing the result. Everyone sees the same countdown, number and
  history.
- All 157 bets, paid at true odds: the 37 straight numbers, splits, streets, corners, six
  lines, the two trios and the first four with zero, dozens, columns, red/black, odd/even and
  low/high. Click a number for a straight. Click near an edge between two numbers for a
  split, near a corner for a corner, and on the outer edge of a row for a street or six
  line. The hover line says what a click would bet on.
- Chips of 100, 1K, 10K and 100K gold, from your own gold (the town's store in town).
  Clear takes back this round's chips. Chips still on the table when you leave the town
  come back to you.
- **Gamba perks raise the winnings.** Luck (+1% a point: the Fortune affixes, the Rabbit's
  Foot, the Lucky Hat and Horseshoe, a smoked herb, fish) and gold find both add their percentage to
  the winnings, not to the stake. A lost bet is lost in full. The zero gives the house
  2.7%, so a bonus of about 3% makes straight bets even, and one smoked herb (+10% Luck)
  already favours the player.
- The table limit is `roulette.max_stake` per player per round.

| Setting | Default | |
|---|---|---|
| `roulette.enabled` | on | the table; off refunds the chips on it and the host takes the wheel away at once |
| `roulette.max_stake` | 1000000 | the most gold one player can have on the table in a round (at most 10000000) |

Both are host-synced and on the HammerwatchPlus tab of the player menu.

Commands: `hwp roulette` prints the round, phase, your bets, your bonus and the history.
`hwp roulette bet <key> <gold>` places a chip (keys like `s:17`, `sp:17-20`, `c:13`,
`d:1`, `red`); `hwp roulette clear` takes this round's chips back. `hwp roulette spin <n>`
(host, cheats) ends betting now and lands the ball on n.

The wheel art (`doodads/hwp/roulette_wheel.png`) is original, drawn by
`tools/make_roulette_art.py`.
