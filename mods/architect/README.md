# architect

Architect alterations for the whole party.

- **Everyone can pick.** The Architect row in the run-start loadout is enabled
  for every player (vanilla: host only). Picks go to the host
  (`architect.pick`), which keeps one merged list with the payer of each pick
  and syncs it to everyone (`architect.sync`); the list shows `- name (payer)`
  and only the payer can remove their own pick.
- **Who pays what** (`SelectArchitectLoadout.CalcMyCost`): a sponsor pays the
  full price of their picks; the host's picks are **split evenly** (rounded
  up) across all players when the host setting `architect.split` is on
  (default). The vanilla cost multiplier counts every pick regardless of payer.
  `GetCost()` now returns the local share on clients too, so a player who
  cannot afford their share cannot ready up, and the share is deducted on each
  machine when the host starts (`OnPlay`).
- Override: `scripts/Missions/MissionArchitect.as` (declared in
  `module.json`, pristine `.orig` next to it, every change marked `HWP`).
  Vanilla's `SyncMissionLoadoutArchitect` message keeps working (host pays).
- **Challenges** (HoH1's fountain "bad wishes"): seven free alterations in the
  Architect list (`tweak/hwp/architect_challenges.sval`). Each one takes a fixed
  amount of gold and one material off the bill of whoever pays for its slot (the
  split pool for the host's picks), after vanilla's cost curve, which challenges
  don't count toward. Its picker row shows the discount in red ("-1.5k gold -10
  stone"; full numbers run off the row). A material stops at 0, so a run can become
  free, but challenges never pay out (`HWP::Architect::ChallengeDiscount`, in
  `scripts/HWP/Architect/Challenges.as`; `CalcMyCost` in the override):

  | Challenge | HoH1 wish | Effect | Discount |
  |---|---|---|---|
  | Crowded Halls | more_enemies | enemy density x1.35 | -1500 gold, -10 stone |
  | Champions | more_elites, minibosses_everywhere | elites and minibosses allowed on every floor | -1500 gold, -10 wood |
  | Lean Pickups | bad_pickups | health/mana pickups x0.5 | -1000 gold, -5 wood |
  | Bitter Draughts | potion_confuse | drinking a potion confuses you (5 s) | -1000 gold, -5 stone |
  | Glass Bones | 1_hp | damage taken x1.4 | -2500 gold, -15 stone |
  | Sharpened Traps | more_trap_damage | trap damage x2 (`Modifiers::HWPTrapDamage`) | -1000 gold, -5 wood |
  | Slim Pickings | no_ore | wood/stone/iron/crystals/dust/ore x0.5 | -1500 gold, -10 wood |

  Crowded Halls and Champions change the level. `ChallengeSetup` is a generation
  command the module ctor wraps around the first unconditional command of every
  dungeon generator; it runs that command after its own work, and only generators
  without one get it inserted first. The generator rolls `randf()` once per
  command, so wrapping leaves vanilla's level for a seed unchanged. It sets the
  enemy placer from the generator's own values each time it runs, because Generate
  retries from scratch. Bitter Draughts uses a trigger chance of 1000000:
  `roll_chance` scales the chance down under negative luck, so 1 would sometimes
  miss. The others are modifiers on the mission buff; like every
  architect pick, the host's apply to the whole party.
  The other HoH1 wishes (no shops, wells, secrets, elevators or loot drops; faster
  enemies; titles off; less luck) have no clean HoH2 hook and are left out.
- Commands: `hwp architect` (list picks + payers), `hwp set architect.split
  false` (host only; rebroadcast immediately), `hwp architect challenges [id...]` (the
  challenges and the cost multiplier of a pick list), `hwp architect try <id...>`
  (cheats, host: these picks for the next level).

- **Run-start screen** (overrides `scripts/GUI/MissionLoadoutMenu.as`,
  `scripts/Town/MissionShopContent.as` and `gui/mission_loadout.gui`, each with its
  pristine `.orig`; memory in `scripts/HWP/Architect/Memory.as`):
  - **Clients can leave.** Vanilla's `Back()` returned false on a client, which kept it
    in the window until the host started or closed it. Now Escape / Back closes the
    client's own window (its status goes to None, so the host's ready count and start
    skip it, and the architect module drops its picks). While the host's setup is still
    open, picking any mission on the mission board reopens the client's window
    (`HWP::Architect::RejoinLoadout`, `MissionShopContent.Buy`); a chat line says so.
  - **Remembered picks and NG+.** Every change of your own picks is stored on your
    player record (`architect.last`, under the hwp key) and the host's New Game+ level
    too (`architect.ngp`); they follow the character, not the town, because the picks
    are per player and the NG+ level is capped by the character's own. When the setup
    opens with none of your picks in the party list, the remembered ones (those the
    character may still pick) are sent as a pick; the NG+ arrows start on the remembered
    level (clamped to the character's). `hwp architect` lists both.
  - **Presets.** The picker has a row of three slots under its list: the slot button
    loads the preset (your picks become its picks; on the host the NG+ level follows),
    its `S` button asks for a name (the game's input dialog) and saves your current picks
    and NG+ level. `hwp architect preset [save <n> [name] | load <n> | clear <n>]` does
    the same from the console. Stored as `architect.preset1..3` on the player record.
  - **New Game+ row.** The `< Starting on New Game+ N >` row sits as the last row of the
    options, right above the Start line, instead of vanilla's arrow row at the top; the
    host's Start hint reads `Start NG+ N`, and pressing Start at NG+ 1 or higher asks
    `Start this run on New Game+ N?` (the force-start question carries the line too).
    `hwp set architect.confirm_ngp false` turns the question off.
  - **Fits the screen.** The window is centred and its key hints are drawn 20 px under
    it, so a tall loadout (every town building, farming's herb line, the NG+ row) pushed
    Start and the hints off a 360-unit screen. `HWPFitToScreen` drops the decorative
    bridges when the window would not leave 22 px above and below, then moves the window
    to the top edge when it still would not; the `[HWP:architect] run-start layout:`
    line says what it did. Farming's herb line is a 14 px row for the same reason.

Morning decisions:
- The **town fountain** as a second entry point for sponsoring (open the
  picker in town, outside the loadout screen). The well/fountain unit sits at
  local offset (104,16) of the `town_square_*` prefabs (square 4 is at world
  -608,128); it needs an interact behaviour added by code or a classmap on the
  well unit. Not done yet.
- "Host approval required" mode and refunds on cancel (currently nothing is
  charged until the run actually starts, so cancel costs nothing).

## Test checklist

1. `python -m gamelab run mod-architect --mode lab`: no script errors; `python tools/build.py --check` reports the
   override as `OK`.
2. Solo (Dark Citadel / Mega Dungeon board): architect row is clickable, picks
   work, cost and multiplier match vanilla, gold is deducted on start.
3. Co-op: client opens its loadout, sees the architect row enabled, picks an
   alteration; both see `- name (client)` in the list. Host picks one; both
   see `(host)` and the client's cost shows half of the host's pick plus the
   client's full pick. Start: each pays their share (check gold before/after).
4. Client tries to unselect the host's pick: nothing happens; unselecting its
   own pick works and the host's list updates.
5. `hwp set architect.split false` on the host: the client's cost drops to its
   own picks only.
6. `python -m gamelab run fix-architect-runstart --mode lab`: the NG+ row is the last
   options row and reads "Starting on New Game+ 2", the Start hint "Start NG+ 2", the
   window bottom + 20 px within the screen, two picks remembered, preset 1 saved through
   the name dialog ("Tanky") and preset 2 through the command, preset 1 loaded back,
   Escape closes the setup, it reopens with the same picks and NG+ 1, Start asks "Start
   this run on New Game+ 1?" and the run starts at NG+ 1. Shots runstart-window,
   runstart-picker, runstart-confirm.
7. Co-op (manual): a client presses Escape in the run-start setup: its window closes, the
   host's ready count drops it; the client picks any mission on the board: its window is
   back with the party's picks. The host's remembered NG+ comes back on the next setup.
8. By eye: with a smoked herb, the herb line is one text row and Start plus the key hints
   stay on screen at the default resolution.
