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
  (`gui/hwp_laststats.gui`): the whole party in one window (2026-10-25). A
  legend of coloured player names (player colour = `GetPlayerColor(peer)`, the
  run's result in brackets), then every stat of every snapshot (union, in
  StatDef order) as a row: the stat name, and under it one horizontal bar per
  player (the player's colour, width = value / the row's biggest value x 150,
  the formatted value as its label; "-" and no bar for a player without that
  stat).
- **One tab per category** (issue #98, 2026-11-06): the mission-end categories
  (`.menu.stats.cat.*`) that have a row become tabs above the list, in StatDef
  order, with the vanilla tab look (`MenuTabGroupWidget` / `MenuTabWidget`, font
  `sub-header`, the `tab-checked` marker of the guild hall's player menu). The
  first is open; a click, or the previous / next tab bindings (`MenuPreviousTab` /
  `MenuNextTab`, shown beside the row, ignored while typing), opens another and
  scrolls to the top. A tab shows only its own rows, without the category header.
- The **search field** above the tabs searches **every tab**, by stat name, as you
  type (`func-edit` "search"; `x` / Escape clears; the console key's char is
  forbidden in the field). While it holds text the matching rows of all tabs show
  under their category headers, each tab's label carries its match count
  ("Combat (2)") and no tab is marked. Clearing the search returns to the open tab;
  opening a tab clears the search. Rows are built once and only shown / hidden, so
  typing never rebuilds the list under the field's focus. Each change logs
  `[HWP:laststats] board: S of T stats shown, P players, tab "cat", filter "q"`.
  The window's `OnFunc` also takes `search <text>` (what `gl func search damage`
  sends), `search-clear` and `tab <cat>` (what a tab click sends: `gl func tab combat`).
- Snapshot lines carry `value` (the raw stat, for the bars) since 2026-10-25;
  older saved snapshots show their text with no bar.
- `hwp laststats` prints what is stored. `hwp laststats board` logs what the
  open window shows (`board open: S of T stats, P players, B bars, tab "cat" i/N,
  filter "q", typing 0/1, input "...", rows: ...`; S, B and rows are what is shown).
  `hwp laststats sample [n]` (test aid) puts n (2, max 4) deterministic made-up
  snapshots on the board (the local player's name first, then "Sample 2".., the 2nd
  skipping every 5th stat; up to 8 stats per category, so several tabs fill), in
  memory only, synced to the party by the host.

## Secrets found: the opener's (issue #98)

Vanilla's `WorldScript/Player/SecretFound.as` runs on every machine and adds
`secrets-found` to each machine's own player, so the whole party got every secret.
The module overrides it (and `Behaviors/Objects/Breakable.as`, one line), so only the
player who opened the secret counts it in their run and character stats:

- A secret room (`prefabs/<theme>/secret_small_*.pfb`) opens when its breakable wall
  (`doodads/walls/<theme>/_secret_dst_*.unit`) is destroyed; a host-only
  `UnitDestroyedTrigger` then runs `SecretFound`. The host's `Breakable.DamageEffects`
  knows who struck the breaking hit (its own player, or a client's through
  `UnitDamagedByMe` / `UnitDamagedByPlayer`): `HWP::LastStats::NoteBreak` keeps that
  player's peer for a secret wall (`_secret_dst_`, not `_corpse`) just before it is destroyed.
- `SecretFound.ServerExecute` (host) takes that peer if the wall broke in the last 2 s;
  a hit with no player behind it (a summon's) goes to the living player nearest the
  wall, and without a wall to the one nearest the script. It logs
  `[HWP:laststats] secret found: peer N (broke the wall | nearest the wall | nearest the secret)`
  and returns `{peer}` to every client's `ClientExecute`.
- Each machine: the opener's books `Stats::Add(secrets-found, 1, its record)` (town,
  character and run, as vanilla); the others `Stats::Add(secrets-found, 1, null)`, which
  counts only the town's total, so the guild's Secrets Found accomplishment (and its
  attribute rewards) still counts every secret the party opens, as before. Peer -1 (no
  living player) credits everyone, as vanilla did.
- Every machine also counts the party's secrets in GlobalCache `hwp_secrets_opened`,
  which `mods/mmhmm` reads so its secret-room moment stays a party moment.
- Not tied to `laststats.enabled` (that switch is the board's): with the module loaded the
  stat is always the opener's.

Not in the snapshot: per-skill damage lines (they need the player actor, which
does not exist at Load time) and the death recap (the `deathrecap` module keeps
its own).

- The board comes back after a building upgrade, which rebuilds the town and
  destroys it; the host notices within a second and spawns it again
  (`HWP::Town::Kept`; test: `mod-town-rebuild`).

## Settings

On the HammerwatchPlus tab of the player menu (Quality of Life > Last run stats); the host's value rules in a lobby:

- `laststats.enabled` (on): off, the host places no notice board, and one that
  stands is taken away within a second (turned back on, it comes back the same
  way). Snapshots are still taken and kept, so the board shows the last run again.
- `laststats.board_x` / `board_y` (above) are for placing the board, not on the tab.

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
   "Sample 2", values present), several tabs with the first open and showing only
   its rows (`board_tabs`), more bars than shown stats, `gl func search damage`
   leaves only rows whose title holds "damage", from every tab (and the field reads
   "damage"), `search-clear` returns to the open tab, `gl func tab combat` (or
   `adventuring`) opens another tab with other rows (`board_tab_switch`); the typed
   route (`gl press search`, then the `type` step's WM_CHARs) is recorded as
   `board_typed`, not asserted. Shots `board` (bars, tabs, by eye), `board-search`
   and `board-tab`. The tabs are not run in the game yet (2026-11-06).
7. Co-op secrets (manual, not run yet): two players, one breaks a secret wall. The host log
   shows `secret found: peer <opener> (broke the wall)`; after the run only the opener's
   end-of-run stats and board bars list Secrets Found, the other player's guild statistics
   still count it.
