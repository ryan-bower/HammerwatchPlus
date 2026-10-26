# laststats

Keeps the end-of-run statistics screen around after you are back in town, for
everyone in the party, on a **notice board** next to the town fountain.

- A `PlayerRecordLoad` hook snapshots the local player's `statsRun` when a
  town loads the character with a finished mission state (Succeeded / Failed /
  Aborted). The module's `Start` stores the snapshot. That hook is the only point
  that sees the result: module constructors run before the character loads, and
  `PostStart` opens the vanilla `MissionEndMenu`, which resets the state and
  `statsRun` before any `Start` (docs/RE_NOTES.md). (`Module::Load` only runs when a
  level is restored from a save, so it can't be used.)
- The snapshot (mission, result, every visible non-zero stat, pre-formatted)
  lives in the player record under the `hwp` bag, key `laststats.mine`, and is
  sent to the host (`laststats.report`) two seconds after load. The host keeps
  one snapshot per player name and rebroadcasts the list (`laststats.sync`).
- The board (`doodads/hwp/laststats_board.unit`, reuses the base
  `mission_board.png`) is produced by the host when a town loads, at world
  (-440, 110); move it with `hwp set laststats.board_x <n>` and `board_y`
  until the spot is right. Interact opens `HWPLastStatsMenu`
  (`gui/hwp_laststats.gui`): **one page for the whole party** (2026-10-25). A
  legend of coloured player names (player colour = `GetPlayerColor(peer)`, the
  run's result in brackets), then every stat of every snapshot (union, in
  StatDef order, grouped by the mission-end categories `.menu.stats.cat.*`) as
  a row: the stat name, and under it one horizontal bar per player (the
  player's colour, width = value / the row's biggest value x 150, the formatted
  value as its label; "-" and no bar for a player without that stat). The
  **search field** above the list filters rows by stat name as you type
  (`func-edit` "search"; `x` / Escape clears; the console key's char is
  forbidden in the field). Rows are built once and only shown / hidden, so
  typing never rebuilds the list under the field's focus. Each filter change
  logs `[HWP:laststats] board: S of T stats shown, P players, filter "q"`.
  The window's `OnFunc` also takes `search <text>` (what `gl func search gold`
  sends) and `search-clear`.
- Snapshot lines carry `value` (the raw stat, for the bars) since 2026-10-25;
  older saved snapshots show their text with no bar.
- `hwp laststats` prints what is stored. `hwp laststats board` logs what the
  open window shows (`board open: S of T stats, P players, B bars, filter "q",
  typing 0/1, input "...", rows: ...`). `hwp laststats sample [n]` (test aid)
  puts n (2, max 4) deterministic made-up snapshots on the board (the local
  player's name first, then "Sample 2".., the 2nd skipping every 5th stat), in
  memory only, synced to the party by the host.

Not in the snapshot: per-skill damage lines (they need the player actor, which
does not exist at Load time) and the death recap (the `deathrecap` module keeps
its own).

- The board comes back after a building upgrade, which rebuilds the town and
  destroys it; the host notices within a second and spawns it again
  (`HWP::Town::Kept`; test: `mod-town-rebuild`).

## Test checklist

1. `python -m gamelab run mod-laststats --mode lab`: no script errors; `[HWP:laststats] spawned the notice board`
   when entering the town as host.
2. Solo: run any mission, die or abandon it, return to town. Log shows
   `snapshot of <name>: N stats, Defeated`. The board by the fountain opens a
   window listing the same categories/values the mission-end screen showed.
3. Reload the save: the board still shows the run (bag persisted).
4. Co-op: after a run both players appear on the board on both machines; a
   player joining later gets the list once their own report triggers a sync.
5. Fresh save: the board shows the "No run recorded yet" text.
6. `python -m gamelab run fix-recaps --mode lab` (section `board` of
   `gamelab/bots/fix_recaps.py`): after a failed run, `hwp laststats sample 2`,
   `gl use laststats_board`; `hwp laststats board` and `gl wtext` prove 2
   players in the legend and on row 0 (`bar-name-0-0` "Pilot", `bar-name-0-1`
   "Sample 2", values present), more bars than stats, `gl func search gold`
   leaves only rows whose title holds "gold" (and the field reads "gold"),
   `search-clear` shows all again; the typed route (`gl press search`, then
   the `type` step's WM_CHARs) is recorded as `board_typed`, not asserted.
   Shots `board` (bars, by eye) and `board-search`.
