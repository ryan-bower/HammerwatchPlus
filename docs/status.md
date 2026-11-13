# Status

Running project status: the newest entries first, then the QA checkpoints and historical
sweeps. The engine and reverse-engineering notes behind each change are in
[RE_NOTES.md](RE_NOTES.md).

> **Tests stay parallel under a bare `python` (2026-11-12, on `main` `811a223e`).** `CLAUDE.md` says to run `python scripts/test.py`, but the system interpreter has no pytest-xdist, so the suite ran serially (111 s; an agent's 0.6 release check did exactly that). `scripts/test.py` now reruns itself with the project's `.venv` interpreter when one exists and it was started by another (`HWP_TEST_IN_VENV` stops a loop). CI (`uv run`) already runs in the venv and is unchanged. Bare `python scripts/test.py`: `-n 14`, 1361 passed, 28 skipped in 29 s. Three new cases in `tests/test_test_runner.py`. Host tests only, no game.

> **HoH1 end floors (2026-11-12, issue #123, PR #127, branch `fix/issue-123-hoh1-end-floors` from `7cb8c74b`).** The Dark Citadel's last floors were four Dark Halls floors plus the Avatar, because `hoh1.content` (off by default since game night 10.28.26) swapped the HoH1 Battlements for generated Dark Halls floors. Now `hoh1.content` is on by default and the host decides per lobby: `build.py` stamps the HoH1 import (`mods/hwplib/hoh1/hwp_import_stamp.sval`, a fingerprint of every imported file, local and gitignored), every client reports its stamp, and the HoH1 Battlements, the HoH1 tower and HoH1 pets play only when every player's stamp matches the host's. Otherwise the citadel goes Dark Halls 1 -> Avatar, the portal offers the HoH2 tower and HoH1 pets are put away, and everyone gets red chat lines: one per mismatched player on join, on dark_halls_1 and the Avatar, on the portal and on a pet put away. `hwp hoh1` shows the lobby and each peer, and `hwp hoh1 fake none|other|match|silent|clear` (host) adds a lab stand-in peer. Evidence: forced state (the fake peer), solo, build 25932569, uncommitted source on `7cb8c74b`, every run with `--beside-player` while the owner's game was open. Results: `fix-hoh1-lobby` 20261112-205711 PASS 21/21 (the Avatar screenshot viewed); `fix-campaign-battlements` 20261112-210058 PASS 24/24; `fix-campaign-portal-version` 20261112-210133 PASS 26/26; `hoh1-standins` 20261112-210221 PASS 24/24. `fix-hoh1-off` came back INVALID twice (20261112-205839, 20261112-210237): every gameplay check passed both times, and the only fail was "user saves unchanged" on the owner's own slot-2 autosaves, `2_6.hps` at 20:58:53 and `2_7.hps` at 21:02:45. That slot had been saving every few minutes since 20:35, and the lab saves only to `gamelab/env`. After the adversarial review's fixes (`a4f413b7`: the host counts the lobby's players before calling it known; join warnings once; fallback warnings only on a real mismatch; `hwp hoh1 fake` needs e_cheats) all five passed beside the owner's open game: `fix-hoh1-lobby` 20261112-214407 21/21, `fix-campaign-portal-version` 20261112-214538 26/26, `hoh1-standins` 20261112-214629 24/24, `fix-campaign-battlements` 20261112-214644 24/24, `fix-hoh1-off` 20261112-214720 33/33. The lobby-count guard can't be exercised solo. An earlier run, 20261112-203222, was stopped by hand; its one fail was the bot's own filter, since fixed. New GameLab flag: `run`/`suite --beside-player` (lab only) lifts only the "player game owns the runtime" refusal; cleanup still kills only the lab executable (`tests/test_player_runtime.py`). No real two-player lobby has run. A player joining mid-run while the lobby is on an HoH1 floor is out of scope. Every friend must re-run run.cmd so their pack carries the stamp; until they do, the lobby falls back and names them.

> **Faster offline tests (2026-11-12, PR #125, `perf/faster-tests` on `7cb8c74b`).** The pytest part of `scripts/test.py` went from 142-187 s to 6-7 s on an idle 16-core machine (about 15 s with the game running), with every test's outcome unchanged: main and the branch collect the same 1346 IDs and each passes or skips alike (1285 passed, 61 skipped, 986 subtests; 1310 passed with the 25 new runner tests). Most of the time was `os.fsync`, about 0.1 s per journal or manifest write on Windows. `tests/conftest.py` swaps it for a stand-in that refuses what the real call refuses (an invalid or closed descriptor and, on Windows, a read-only handle, checked by a zero-byte `WriteFile`) without flushing to disk; `tests/test_test_runner.py` compares the two. `tests/test_build_update.py` builds its baseline git repository once per class and copies it per test (the copy's index is stale by stat but `build.update_id` compares content, so every assertion keeps its meaning). `scripts/test.py` runs a full suite on pytest-xdist (new dev dependency, `uv sync`): every core on CI, all but two locally, at below-normal priority, with bytecode writing off because parallel workers left orphaned `*.pyc.<pid>` files on Windows (266 after one cold run). A narrowed run (a path or node ID, `-k`, `-s`, `--lf`, `--sw`) stays serial, as does a run where xdist is missing or disabled; `-n N` overrides. An adversarial review found no correctness or coverage loss. Host tests only, no game.

> **Dark Citadel candle skips (2026-11-12, `feat/dark-tower-level-skip`, based on `3dc29e56`).** New `shortcuts` level-data module in Quality of Life adds three candles to the existing challenge: five lit candles skip to High Courts, six to Dark Halls and seven to the Avatar. Extra candles use vanilla's wave spawns, add no challenge loot and keep the current-NG+ shortcut-3 unlock gate. Host-side evidence only: 29 focused tests pass, including all 128 candle subsets and level binary encoding; verb/config generation checks pass. Not verified in game: `./gamelab.sh doctor` refuses because Windows Python is absent; the worktree lacks generated game assets for a package build. Full `scripts/test.py` stops at 18 Windows-only `ctypes.WinDLL` collection errors on Linux. Candle placement, actual enemy tracking, co-op, save/reload and final-boss victory still need GameLab checks on pinned build 25932569. See `mods/shortcuts/README.md`.

> **Fewer vaults and sealed exits (2026-11-08, issue #67, branch `fix/issue-67-objective-chance`).** `objectives` no longer puts a vault and a sealed exit on every generated floor: two new host settings roll them per floor, `objectives.vault_chance` (25 %, once per vault slot) and `objectives.exit_chance` (15 %, once per floor while `objectives.exit` is on); values 0, 10, 15, 25, 50, 75, 100. Each roll is logged (`vault 0 roll 37 >= 25: skipped`). A skipped slot doesn't leave a gap in the vault numbers, and a floor without an exit lever is never sealed, preloaded floors included (`AdoptFromUnits` already handled it; no change needed beyond a comment). The `fix-objectives*` scenarios and their `pf-` copies now set both chances to 100. Source review and pytest only, not tested in game: no GameLab run, so the rolls, the open exit on an unsealed floor and the edited scenarios are unproven on build 25932569.

> **Pet level blanked the character level (2026-11-08, `fix/issue-79-pet-level` from `3dc29e56`, issue #79).** The pets module's `hwp-pet-level` line is a `Clone()` of the vanilla `player-level` text, and the clone shared its `BitmapString`, so the pet line's first `SetText` cleaned up the character's level text; vanilla rebuilds it only when the string changes, so the level stayed blank while a pet was shown. `PetLevelTab.as` now drops the clone's shared text and tooltip handles (fresh clone and one found by ID) and force-rebuilds the level once. The pet line also checks the player name: past it, it shortens to `pet lvl N` (new `hwp.pets.inv_level_short`), and hides if that doesn't fit either. No other mod clone has the bug (`SubclassPick.CloneText` already detached; the rest clone hidden templates). Source review and pytest only (`tests/test_pets_level_tab.py`), not tested in game; `fix-pets-inventory-level` hasn't been rerun.

> **Party frames (2026-11-06, branch `feat/party-frames` from `4cfbb3bf`).** New `partyframes` module in a new `interface` package replaces the co-op HUD with class-coloured Thick or Thin bars and Leading edge or Striped edge shields, and `HWP::AllyStatus` syncs ally shields and potion counts. Verified solo on build 25932569 with forced setup: `mod-partyframes` (6 clean runs, 20261106-200139 to -200808), `mod-partyframes-data` 20261106-200035, `pkg-interface` 20261106-200205, `mod-settings-sweep` 20261106-202656 PASS. Not done: no real two-player session has run, so the client path is unproven; Interface isn't published; `README.md:19` still says twelve packages. Open: two runs crashed at shutdown (`mod-all` 20261106-200219, `mod-settings-sweep` 20261106-211620), both after every check passed. That is 2 of 35 runs with `partyframes` loaded against 3 of 1,248 without it, so this branch is suspect until compared. Later the same day: potions moved beside Thick bars, Show level and Show class toggles added (off by default, bars widen), the Plus list's last rows made reachable, test-only `gamelab-fakecoop` added with `devarena/party`, and the owner chose the solid blue pool for Living Mana allies, checked on a real husk (`mod-partyframes-livingmana` 20261106-213408) (`mod-partyframes` 20261106-211509, `devarena/options-list` 20261106-211446, `mod-settings-sweep` 20261106-212346 PASS). The frames now start below the game's tutorial panel while it's up (`mod-partyframes-tutorial` 20261106-220546, `mod-partyframes` 20261106-220617, `mod-partyframes-livingmana` 20261106-220645 PASS: build 25932569, forced panel and fake allies, solo). `mod-settings-off` passes after fixing its test code (20261106-232113, 20261106-232722). See [RE_NOTES.md](RE_NOTES.md).
>
> **Party frames, later (2026-11-07, `feat/party-frames`, on top of `57e77449`).** A shield now only fills missing health, as WoW's frames do, and anything that doesn't fit is the glow at the bar's end; this replaces the earlier rule that it lay over the bar. The potion and its count sit straight on the game, with no background. A new Green health toggle (off by default) draws every ally's health in the green of Blizzard's raid frames over their dark backdrop; a Living Mana pool stays blue. Show level and Show class no longer resize a bar: a level tag and a three-letter class tag sit in Thick's corners beside the %, and on Thin in a column between the bar and the potion. Class colours are now WoW's retail colours (from AllTheThings, Eltruism and EllesmereUI; Blizzard's source doesn't hold them), and HoH's own classes borrow a WoW class's colour: Sorcerer Evoker, Gladiator Death Knight, Thief Monk, Witch Hunter Demon Hunter, Firearms Druid. `gamelab-fakecoop` gained `sim`, `hit`, `heal`, `shield` and `kill`. Forced setup, solo, build 25932569: `mod-partyframes` 20261107-013756, `mod-partyframes-livingmana` 20261107-013827, `devarena/party-sim` 20261107-013849 all pass. Two games in sequence, no Steam: the real reports `mod-partyframes-data` 20261107-015858 logged went through `hwp fakecoop wire` into `AllyStatus::OnReport` and the frames of a second game (draft scenario, 20261107-020021, pass). The harness carried them, so transport and a real client's sending are not covered, and the two-player session is still unproven.

> **Party frames, potion charges (2026-11-07, `feat/party-frames`, on top of `bc7c7f6d`).** The potion icon and count are replaced by a column of charges docked to the bar's right edge, with a new Potion style setting: Cut gems (default) or Hollow bars. Every charge in a column is the same height with the same gap; spent gems go dark and spent bars become outlines. A docked column uses the bar's edge as its own, so it never cuts the low-health border; on Thin with tags on it sits past the tags on its own black edge. Forced setup, solo, build 25932569: `mod-partyframes` 20261107-023814 pass, screenshots viewed on both sizes and styles with stub allies. Not done: both styles get cramped at 8 or more charges on Thin (1 px charges, gems become rectangles from 6); nothing past 10 charges on Thin or 16 on Thick is drawn.

> **Run copy flag (2026-11-05).** `tools/run.py --copy-slot N` copies a local profile into the new play profile, bypassing the save builder; it refuses an active dungeon run and never writes the source. Host tests only (`scripts/test.py`: 1246 passed, 28 skipped); no native GameLab run. Source at base `4cfbb3bf`.

> **PR publication checkpoint (2026-11-01).** The complete QA worktree is checkpointed on `codex/run-save-builder-followup` and integrated with upstream `e7d060f1` (including merged PRs83?86). The merged host suite passed **1,244 tests**, with three unavailable-symlink skips and1,269 subtests. See [the publication record](qa/swarm/pr_publication.json). Earlier native results below retain their exact execution revisions; no new native pass is claimed for this upstream integration. The broader campaign remains paused at r4847/E018. Historical scenario/catalog pins require current review before further native admission.

The [admission pipeline validation](qa/swarm/admission_pipeline_validation.json)
verifies reviewed feature cases through a data catalog, exact consumer checks and
atomic tracker import. Two isolated stash cases passed all ten consumer rows;
both were verified together in one ledger revision, and two broken bundles left
the ledger byte-for-byte unchanged. Private HPS backups and stale module-input
admission gaps were fixed. Final host tests:1240PASS/three unavailable-symlink skips,
1269 subtests. Native evidence remains pinned to executed source9884dd30; final
source9e92c11a differs only by the independently reviewed tracker CLI import fix
and its subprocess tests. The limited acceptance ledger is idle with three
verified tasks; the broad campaign remains paused at r4847/E018. Worker cap stays
two. Repeated closure validation consumed40.66s of the87.20s feature wave, a
measured optimization candidate before increasing workers.

> **Earlier isolation checkpoint (2026-10-31): two-worker GameLab isolation verified; broader campaign remains paused.** The [validation record](qa/swarm/multi_run_validation.json) records725 automated tests passing, paired native load/input/helper checks, independently routed commands/input/captures, and a contained intentional timeout whose sibling passed. One matched warm-cache four-case comparison took149.68s serial versus94.64s paired (1.58x; preliminary). The original failed clock-marker probe and expected timeout remain retained. The post-fault qa_batch recovery pair also passed; final coordinator teardown is clean. Parallel admission is limited to audited scenario/bot hashes; four-worker capacity and broader scenario eligibility remain future work.

> **Earlier campaign execution checkpoint (2026-10-31, E018).** Dated r4847: ROOT18 is integrated r6; installed core561 returned559PASS/two named WinError1314 skips and three metadata exits0. Independent result review is pending; no E018 AS/load/native result is recorded. Build25932569/B176; source `26acb452...`/2,226, inputs `feb56819...`/6,294, supplementary `cfc2c4db...`/270. Two reviewed files install unit-or-neutral pulse control and twelve passing pure models. Ownership, tiny precision budget, strict2px, route/hold/correction limits remain. Availability is unproved; intentional neutral commands may affect stuck/repath behavior. Source inventories/continuity renewals are underway. E017 history: core549=547PASS/two skips; separate direct selftests10methods+14save+78doctor assertions; seven native trials=sixPASS/oneposeFAIL. Merchant130213 and inventory130734 were independently accepted only at controlled UI scope; M4 parent queued16, Courier remains separate. Pose124559 materially refused X after26frames; F1HB56/released. All earlier failures remain. Browser cases are blocked/unrun; eight genuine co-op tasks user-deferred; boss/per-killer policy unchanged. [Resume the tracker](qa/SWARM_TRACKER.md) for live work. Portable E015/r4165 and actual E016Planner18 stay historical; no campaign completion or broad gameplay coverage is claimed.

Agents: resume from `python tools/qa_swarm.py resume --owner <alias>`. The
[tracker protocol](qa/SWARM_TRACKER.md) and persistent JSON ledger preserve
claims, next actions, dependencies and evidence across compactions. The initial
27 bootstrap tasks have expanded into bounded lane-owned verification and repair
tasks. Read the ledger for current counts and next actions.

> **Historical QA checkpoint (2026-10-22): paused at the user-requested PR boundary.** The original sweep was incomplete. Recorded original-sweep passes: six original fourth specs60/60 rank cases and61/65 orb-quality cases; Firearms60/60 ranks and74/75 orb qualities; HoH1 imports29/39 skills and136/191 ranks;9/9 selected-mastery saves. Five orb cases need real co-op. The then-current 31 normal-release modules had load evidence, with broader feature/lifecycle work open. Earlier QA summaries below are historical snapshots. See [the historical checkpoint](generated/qa_pr_checkpoint.json) and [QA ledger](QA_OVERNIGHT.md).


2026-11-12, Deadeye Tailwind (#77). Duration increased from 4 to 6 seconds; every gain
refreshes all existing stacks, including gains at the cap and Tailwind Catch. Updated
tooltip/planner and timing regressions. All 57 focused offline tests and both generated-file
checks pass. The full suite stops at 18 Windows-only import errors on Linux.
Native validation is pending: the new worktree's
GameLab doctor refused setup because its Windows Python runtime is missing.

2026-11-12, training dummy DPS CI fix (#119). Added the missing Workshop module
description and corrected the QoL cover count to 21 helpers. All 28 focused
Workshop/config/package/build tests pass locally; remote full-suite verification
is pending. No gameplay changes or test exemptions.

2026-11-12, training dummy DPS resumed on `feat/town-dummy-dps` at main `4cfbb3bf`.
Recovered the module and scenarios, reviewed the merged contents and cleared the
remaining Git conflict flags without dropping the saved stash. The meter supplements
native hit numbers with combined HP loss over the last five seconds. The QoL pack
builds and 21 focused offline tests pass. Current-source
live validation is blocked by Steam not running and a save-confirmation symlink
refusal; no safety checks were bypassed or player install deployed. The UI review
is in [audit-001](../anti-slop/audit-001-2026-11-12.md); historical passes below remain
historical, not evidence for this integration.

2026-11-08, Catch-up experience (`catchup`, #73), in the Co-op package. In a New Game+
run, a player below the level cap of the NG+ level before it gets 50% more experience: below
20 in NG+1, 25 in NG+2, 30 in NG+3 (vanilla's cap is 20 + 5 per NG+ level, so the threshold
is 15 + 5n), never in NG+0, and not for a character already at its own cap. It goes by the
run's NG+ (`g_ngp`), not the teammates' levels. The buff bar shows **Late Bloomer** (the
shrine experience blessing's icon) while it applies; the buff's `experience-mul` 1.5 goes
through `PlayerRecord.GiveExperience`, so kill and mission-reward experience are both
boosted. Each machine boosts its own player; the switch `catchup.enabled` is the host's.
`hwp catchup [ngp <n>|off]`. Source review and pytest only, not tested in game: no GameLab
scenario yet, and the README's checklist (solo and two players) is still to run.

2026-11-06, Magic Shop sphere picker takes E (#64). In the run-start Magic Shop picker,
pressing E over a sphere now picks it before the window closes; vanilla closed the window and
kept the old pick, for host and client alike. The fix is an architect override of
`MissionSkillSphere.as`. Source review, pytest and the override check only, not tested in game
(architect README item 9: host, client and gamepad).

2026-11-06, Magic Shop for a joined client (#64), diagnostics only. Source review found no
client-only block: the town Magic Shop NPCs and the run-start Magic Shop row have no host-only
check. The likeliest cause is the vanilla keys: on the run-start screen E is Ready for a
client, and in the sphere picker E applies without selecting the hovered sphere (open the row
with a click or Return, pick with a click). The run-start screen now logs which side opens a
row and when E is ignored. #64 stays open until a 2-player test (architect README check 8).

2026-11-06, Out of combat speed (`outofcombat`, #99). In a run, a player who hasn't hit an
enemy for 10 seconds moves twice as fast, with the shrine speed blessing icon in the buff bar,
until they hit one again. Taking damage doesn't end it, and it is off in town unless the host
turns that on. The host sets the speed (1.25x to 3x) and the wait (3 to 30 s); each machine
boosts its own player, so clients get it as the host does. Source review and pytest only,
not tested in game (`mod-outofcombat`, `pf-mod-outofcombat` and the README's two-player
checklist are still to run).

2026-11-06, Secrets Found per opener and recap board tabs (#98). Secrets Found now counts
only for the player who broke the secret wall (the nearest living player if a summon broke
it). The guild's town accomplishment still counts every secret, and mmhmm's secret-room line
still plays for the whole party. The last-run recap board has one tab per stat category; the
search looks through every tab and shows each tab's match count. Source review, pytest and
the override check only, not tested in game; co-op attribution and the tab layout need a run
(`fix-recaps`, laststats README item 7).

2026-11-06, Forgemaster summons and Resurrection aim (#98). The Devil Forge Priest's risen
no longer block other players: the generator gives every collision shape `ignore-player`, as
vanilla summons have it. Resurrection now raises the intact body nearest the mouse cursor
(within range); a gamepad keeps the aim-line pick. Source review and pytest only, not tested
in game.

2026-11-06, fishing spots twinkle. Every couple of seconds each town coast spot and each run well or
bucket shows a small star glint (vanilla's ground-loot glint, played once, faintly blue) at a random
point of its water. A run spot stops twinkling once you have fished it out, and the next floor's
spots twinkle again. Each player sees their own and can turn it off (`fishing.twinkle`). Source review
and offline tests only; how it looks and that it loads still need a GameLab run.

2026-11-06, winning a run, and tougher bosses (#96). When the party finishes a run (any vanilla run,
trial, map or the Forsaken Tower, not the Wave Arena), every player gets a big gold "Winner winner
chicken dinner!" banner and chat line in town once the run summary closes (`laststats`, each player's
own setting `laststats.winner`). A new `bosses` module (Dungeon package) gives every boss 25% more
armor and fire, ice, lightning and poison resistance; health is unchanged, the host picks 0 to 100%
(`bosses.toughness`) or turns it off, and Pelor's Fury still strips them to 0. Source review and
offline tests only, not yet run in game.

2026-11-06, back into the run-start setup, and last-used picks (#65, #96). A client who left the
host's run-start setup can get back in by using the town's exit door again (the game ignored a
client at the door, and the old "use the mission board" advice pointed at a board the released game
doesn't have); they rejoin with everyone's current ready state. The host sees a player who left as
"Name (left)", and starting without them asks the usual force-start question. The chapel, Magic
Shop, tavern and boon rows now remember each character's last picks and restore them when the setup
opens, skipping what the character can no longer pick or afford. #64 (a client can't select the
Magic Shop row) is still open: no host-only check exists in the game's code, and `hwp architect` now
lists the client's rows to pin it down. Source review and offline tests only, not tested in co-op.

2026-11-06, roulette: the table can't break, a dealer, and a winner's shout (#63, #96). The tavern
table under the wheel was a vanilla breakable, and when it broke the wheel jumped to a table hidden
by the front wall, so the roulette seemed to vanish. Every machine now keeps that table's health
topped up. A dealer stands behind the table facing the players (north of the round table on tavern
levels 1-2, west of the long table from level 3), and using him opens the table too. Winning a round
shows "Winner winner chicken dinner!" on the winner's screen, in the lobby's chat and over the
winner's head. Source review and offline tests only; the dealer's exact spot and the lobby messages
still need an in-game look.

2026-11-06, objective levers on any reachable wall (#74). Vault and exit levers used to go on the
floor block farthest from what they open, which was always a bottom corner by the bottom wall. Now a
lever is mounted on a north, east or west wall (vanilla's wall pull lever art), anywhere in the far half
of the floor, side picked at random, kept apart from the floor's other lever, never on floor cut off
from the rest and never under a torch. South walls are left out: from the game's camera their face is
hidden. A floor with no wall that fits gets the old floor lever, clear of the wall below when it can be
and against it when nothing else fits (2026-11-08 review fix, so the exit never stays open for want of a
spot). Source review and offline tests only
(`tests/test_objectives_levers.py`), not yet seen in game.

2026-11-06, orb rerolls per orb (new `orbreroll` module, Quality of Life). Every orb you pick up
can be rerolled as many times as your reroll accomplishments allow, instead of one pool for the
whole run, and the shadow curse cost starts over on each orb. Orb rerolls no longer spend the run's
pool, so the trinket picker keeps all of it. Host setting `orbreroll.enabled` (off: vanilla).
Overrides `GUI/Menus/GiveSkillSphereMenu.as`. Source review and offline tests only, not yet run in game.

2026-11-06, the disappearing-player glitch (#71), suspected cause fixed. A player snapped into a wall
or past a ledge rail by a collision-ignoring `SetPosition` sits hidden behind the wall sprites and boxed
in, still connected. Two mod paths could do that: the Devil Forgemaster's Heresy lunge and Penance
(the spot under a body across a wall or rail) and the Arcane Blink's no-room fallback (the spot it had
just refused). Now the lunge waits until the body can be reached, the Penance channels in place, and
Blink backs off or stays put. Source review only: the session log doesn't show who glitched, and the
wall-side lunge, ledge Penance and corner Blink repros have not been run.

2026-11-06, strongbox and abyss enemies no longer spawn inside walls (#80). The spawn check's
line of sight started a few pixels out from the box or crack, so beside a wall it began past the wall
and let enemies appear behind it, and the free-space check was smaller than most enemies' bodies. Now
a spot must fit the enemy's whole body and have a clear line from the box or crack and back; a box or
crack beside a wall spawns its pack on its open side or closer in, a member with no safe spot is
skipped, and an abyss wave with no room at its spread spot erupts at the crack. Source review and
offline tests only, not yet run in game.

2026-11-06, the Shady Trader's orb offers show the rank you'll get (#70). It was a vanilla bug: an
orb offered in a trade showed the rank you already have (name colour, values, highlighted rank). hwplib
now overrides `ShopContent/ShadyTrader.as`, so an offer shows the next rank and names it ("Fireball 3"
at rank 2), as the orb picker does; an orb taken as the cost still shows your current rank. Source
review and offline tests only, not yet run in game.

2026-11-05, Branding and Bannerlord rework (#95). Warlock proliferation/support perks and
Warrior shield/rally support, per [the design](design/branding-bannerlord-rework.md).
Source/data checks, a Linux GameLab full-mod compile/load and 16 focused solo gameplay
assertions pass. Remote-party/co-op validation is still pending.

2026-11-05, Linux (#94). Packages build natively on Linux (`./build.sh`), and GameLab has an
experimental, pinned Proton/Xvfb bridge (`./gamelab.sh`, [gamelab-linux.md](gamelab-linux.md));
Windows keeps its native backend. On the pinned Linux runtime `null-payload` and `mod-all`
pass with every isolation check on; that was against main `e7d060f1`, before the reorganisation
and the QA worker merge, so it is not yet re-run on current main. Details:
[RE_NOTES](RE_NOTES.md#current-linux-pr-integration-checkpoint-2026-11-05) and
[CONTRIBUTING.md](../CONTRIBUTING.md), Linux.

2026-10-31, the repo reorganised (FastAPI-style). README is a short front page; its module
tables are in [features.md](features.md), install steps in [install.md](install.md), this log
here, and setup in [CONTRIBUTING.md](../CONTRIBUTING.md). AGENTS.md is folded into CLAUDE.md.
`tools/` is grouped (`generate/` for the `make_*` generators, `hoh1/`, `art/`), every test is in
`tests/`, `python scripts/test.py` runs the offline checks and CI runs it on every PR. Python 3.14+
(3.15 waits on an lz4 wheel). Merged in first: #62, #66, #68, #72, #78.

2026-10-30, linking items in chat (#62). Right-click any item in the character screen, bag or
worn, or use its new "[L] Link in chat" hint (click it or press L, rebindable on the
HammerwatchPlus tab), to link it. The chat line is just your name and the item in its rarity
colour. Mods can't reach the chat box itself, so the last five links also show in a small panel
just above it for 30 s (`hwp links` brings it back); hover a link there for the item's full
tooltip, picture and all, as when hovering it in the inventory. Tested: `fix-chat-links`.
2026-10-30, gear salvages into materials (#66, new `salvage` module in Quality of Life). Destroy
in the bag and in the town stash is now Salvage: the item becomes Crystals (Common, Uncommon) or
Dust (Rare and up), more the higher its level, and the confirm names the amount. A Rare ilvl 20
gives 3 Dust and an Epic ilvl 30 gives 12. The host can turn it off (back to the vanilla Destroy)
or set the yield from 50% to 200%. Tested: `fix-salvage`, `pf-fix-salvage`.
2026-10-30, no Sacrificial Penance without Heresy (#68). The Devil Forgemaster's Necrotic
Resurrection only turns into Sacrificial Penance at max Divine Favor when there is at least 1
Heresy to wash away. With none, the key stays a raise (its icon, its cost, +Heresy) and the
Favor is kept, so the next cast after that raise is the Penance. Tested: `fix-penance-heresy`,
`plan-forgemaster`.
2026-10-30, fishing's second check can be hit (#72). A click on Reel counted twice: once on
the press and again on the release. The second count came the moment after the first hit,
so with a 2-hit fish it was always a miss ("fought free"), and a landing click cast again
straight away. Now a click is one reel, made on the press. Each check's time limit also
covers the marker's way to the zone plus 1.5 s (2.5 s at least), and running out of time
says "Too slow". Tested: `fix-fishing-reel-press`, `fix-fishing-reel-hits`.
2026-10-30, free skills after a respec (`freeskills`, #78). A class starts with some skills
learned, such as the first skill and passive or a specialization's two. A respec at the Skill
Trainer gave back every point but left these skills learned, so their slots couldn't go to
anything else. Now the respec unlearns them too. The trainer shows them at 0 and teaches them
again for no skill points, even with none left. They stay unlearned through a save. The
respec also tells the other players in a lobby now; vanilla's never did. Tested:
`mod-freeskills`, `pf-mod-freeskills`.

2026-10-30, Pelor's Fury on elites, and a death takes 5 Blessing stacks (#82). Pelor's Fury
on an elite now needs and spends only 3 stacks of Pelor's Blessing and keeps the rest; on
anything else, bosses included, it still takes all 10. A party member dying now takes 5 stacks
instead of all of them, and that includes the paladin's own death: the game used to clear the
stacks on the revive, so they are put back. Tested: `fix-fury-elite`, `plan-generosity`.

2026-10-29, confusion traps you can dodge (#38). The confusion glyph went off 0.15 s after a
player came near, out of sight until then. Now it, and the dart glyph that had the same
problem, show on the floor all the time, light up with a red warning for a second, and only
then go off. A dart glyph no longer hits a player standing on it with all eight arrows. The
Confusion setting now also turns confusion glyphs and plates off, as its text always said.

2026-10-29, all of HoH1's traps (#37). On top of spikes, flame jets and glyphs, generated
floors now get HoH1's poison, frost, drain and confusion plates, pressure spikes, frost and
curse glyphs, arrow, poison, fire and blade shooters in the walls, arrow turrets, flame
gargoyles, falling stalactites and bricks, and bear traps, each on HoH2's art. Every one
warns before it hurts (a red warning on a plate, a glyph lighting up, a stalactite's shadow).
Which ones a floor gets follows its theme, as HoH1's acts did: stalactites only in caves,
shooters and turrets in barracks and dungeons, drain plates and curse glyphs in crypts and
halls.

2026-10-29, projectile colours you can see (#36). The colour presets did tint every shot, but
a tint can only darken a sprite, and the shots that matter are bright fire or dark bolts, so
nothing seemed to change. Every tinted shot now also gets a ring in its team's colour (setting
`colors.markers`, on by default). `fix-colors` checks both sides' shots in flight in each preset
and the rings on screen (20261029-062340).

2026-10-29, Pyrebrand is a nuke (#35). The brand now charges as it burns, and the Hellfire
Claw pays up to 100/150/250/350/500% of the damage that fed it (rank 1-5): all of it when the
brand runs out, less on an early recast. Before, it paid 10-50% whenever it went off. At rank 5
a full brand's claw took 7.4x the damage that fed it from a test dummy, where the old one would
have taken about 0.9x.

2026-10-29, Pelor's Fury works on the Serpents of Demise (#34). A serpent is mostly body, and
its body is a trail of untargetable boss parts. Aimed at the body, the Fury picked one of those
parts and refused nearly every time. Now any part of a serpent counts as the serpent: the
Fury holds its head when the head is above ground, and says why not when it is underground. A
body part over a surfaced head no longer steals the pick either.

2026-10-29, one boss recap per boss fight (#33). The Serpents of Demise showed a damage
recap each time one of their serpents went down, because the recap followed each
boss-tagged unit on its own. A fight is now the whole encounter: every boss unit you hit
joins it, and it ends when they are all down and no boss health bar is left, the way the
game's own boss bar sees it. The same fix covers the Bandit Lord's mirror images, the
Harbingers and spawned ghosts. Damage taken is no longer counted twice when two boss
units are up, and the recap is named after the boss bar ("Serpents of Demise").

2026-10-29, fishing is harder (#32). A bite now takes several hits in the green: two for a
1-star fish, three for 2-star, four for 3-star. After each hit the fish fights back: the
green zone jumps away, the marker speeds up and the timer restarts, and one miss loses the
fish. The fastest fish keep their speed, so their tiny zone can't be skipped over between
game ticks. A "Hits to land" setting picks one count for every fish (1 is the old single
press).

2026-10-29, Mm-hmm! from the wearer (#31). The hat's voice is now a village woman's "mm-hmm!"
(the Equipment Buyer's, Enchanter's and Mystic's voice) in place of the Material Trader's.
It comes from the wearer's body, so others hear it from where that player stands and
fainter far away, instead of from nowhere at full volume. Each one plays to the end before
the wearer says it again: a burst of crits no longer stacks it.

2026-10-29, traps on one map (#30). The HoH1 traps were on every floor of every map, and
mostly spike floors. Now they go on one map, the Crypt by default (a "Trap map" setting picks
another, or every map), and always in the Forsaken Tower, HoH1's own trap tower. Each trap is
rolled on its own, so a floor gets a mix of spikes, flame jets and the three glyphs instead
of a floor full of spikes. The teleporter pad is still on every floor.

2026-10-29, War Cry shows on the buff bar (#28). The game gives almost none of the class
skills' buffs an icon, so War Cry, Power Surge, Hot Pursuit and others worked but never
showed. The buff tooltips mod (`bufftips`) now gives 13 of them an icon cut from the skill's
own art, with a name and a short description for the tooltip. A setting turns it off.
Untried in co-op: an ally hit by War Cry should see it on their own bar too.

2026-10-29, the levers work past the first floor (#27). From the second floor of a run on,
the vault and exit levers did nothing and the way down was never sealed. The game builds the
next floor ahead of time, in a separate part of the game's scripting, and the mod's notes on
where it put the vault and the levers stayed there. The mod now reads the vault and the
levers off the floor itself when it starts, and a co-op client keeps trying to seal its exits
for a few seconds, as the host does.

2026-10-29, bonus vaults look like the floor they're on (#26). The vaults behind levers had
a bare floor and no walls of their own: their cells were reserved the way a prefab with its
own art reserves them, so the game painted neither walls nor the floor's decoration there,
and on the Bandit Keep the room sat in the dark of the wall block it was carved from. Now
the game paints the vault like its own rooms, with the floor's tiles, walls and torches. The
levers no longer show on the map; the new Architect alteration **Marked Switches** puts
them back for a run.

2026-10-29, notices name the HammerwatchPlus updates (#24). The game's join check compares mod
ids, not their contents, so friends with different updates got into one lobby and things
quietly broke: on 2026-10-28 a client on per-module packages from before 2026-10-26 joined a
newer host, and only the log said `no handler for event` for four of the host's events. Every
package now carries its update (the commit's date and hash). In town, a client and the host
compare theirs, and both are told which packages differ, which side is older and who should
update. Packages of different updates in one game are named with their updates too, and `hwp
version` lists them. The Workshop change note shows the same update.

2026-10-29, the General Merchant's tabs work with a controller (`keys`, #23). The Keys & Bags
and Trinkets tabs switched only with a mouse click. Now a gamepad's bumpers (and Tab on a
keyboard) switch them, as in the player menu and the stash, and the bindings show beside the
tab row. GameLab gained `menubutton`, which presses a menu button as a gamepad does, so
controller paths in windows can be tested without a controller.

2026-10-29, Shift+Click places 20 attribute points at the Attribute Trainer, Ctrl+Click 5
(`attrclick`, #22). Vanilla places one a click, and every level and NG+ level adds more to
place. The cost on each stat shows the amount while the key is held. A gamepad keeps the
vanilla hold-to-repeat.

2026-10-29, items with two suffixes or two prefixes (`affixes`, #17). Vanilla gives a Rare item
one suffix and an Epic one a suffix and a prefix, each from its own pool. Now each of those
tiers may roll a second mod, 25% each (`affixes.chance`), from the same pool and never the same
mod twice. The extras show in the tooltip, save with the item and stay when the module is off.

2026-10-29, guns work for every class (#16, #29). A Ranger's pistol never fired: a gun
shoots from its clip, and the clip was filled and reloaded only for the Firearms Specialist.
The clip, its reloads and how a gun handles now go with the gun, so a Ranger with a pistol
and a hand crossbow shoots both, and the clip shows on the HUD. The class keeps its skills and
the shops' guns.

2026-10-29, Lightning Kush (#15), a fourth Holy Herb strain: violet, +20 % lightning damage,
Ember Kush's counterpart. Each strain had been copied by hand into seven files and three
sprite sheets indexed by seed order, and the harvest sheet was full. So now one table makes
them all: `tools/generate/make_herbs.py` writes the buffs, joints, names, seed lines, units and art,
and a test fails when a file is out of date. Adding the strain also showed that the
materials tab's Plants & Herbs grid had only 16 cells for 18 seeds and harvests: the last
two would never have shown. The grid now has 24 cells, 9 across, and hwplib logs an error
when a section has more providers than cells.

2026-10-29, weapon swap on a controller (#14): D-pad left swaps, the one button vanilla's
gamepad map leaves free in gameplay, and the Plus tab binds another (press it). The hints show
the button while you play on a controller. Behind it, hwplib gains `HWP::Input`, so a mod's
hotkey can read a controller button. Until now every HWP hotkey read the keyboard only. Skill
4-6 and the bag item actions are still keyboard-only and can use it next.

2026-10-28, the pet courier (issue #13). In a run, hover a bag item and press H (or click
**Send home**): your pet takes it to your town stash, in a tab called "Pet deliveries". The
item is in the stash and saved the moment you hand it over, so dying or leaving on the way
can't lose it. The pet leaves when you close the menu and comes back after the trip (60 s by
default, shorter with Fetch ranks). It carries one item a trip, plus one every 5 pet levels.
The bigger problem it turned up: bag item actions lived in droptrade, only the first one ever
showed, and it was bound to a fixed E, which is also the menu's Destroy key, so eating a fish
opened the destroy dialog too. hwplib now owns the inventory hints. Each action gets its own
hint and key: Drop Q, Eat F, Send home H, each rebindable on the Plus tab, and the log flags
an action key the menu also binds. `fix-item-actions-eat`, `fix-pets-courier`, their package
variants, `plan-gear-b` (droptrade) and the package scenarios pass.

2026-10-28, the Forsaken Tower from HoH1 itself (`campaign`, "HoH1 tower" in its README).
With HoH1 installed, the import builds HoH1's tower from the player's own install: 23 floors,
the nine hand-made levels as HoH1 ships them and fourteen act floors from HoH1's own generator
scripts. HoH1 world scripts whose HoH2 namesakes read other param names are renamed (436
RandomChance rows had never run; the Councilors' deaths never reached SetBossKilled). HoH1's
`magical` damage goes to an element, speech bubbles use HoH1's styles, exits keep their start,
and HoH1's texts and boss names are imported from its language file. `tower-floors` loads all
23 floors clean (20261028-163319); `tower-bosses` fights all six bosses the way their levels
start them, checks each titled boss bar, kills them as the player and takes each exit
(20261028-163821). GameLab fix: `hps.current_save` read the save header's timestamp as a float
and picked the wrong rotation file once its low word passed bit 31, so a rebuilt fixture lost
the scenario's mods. HoH2 classes on HoH1's bosses: the Paladin's Generosity holds all eight
boss units (`plan-generosity-hoh1`, 20261028-170027). Two fixes made that work: the Councilors'
attack no longer casts through the hold, and a held Councilor or Vampire Lord stands solid and
targetable. The Devil Forgemaster raises every HoH1 elite, miniboss and boss, including each
tower boss from its body on its own floor (`plan-forgemaster-hoh1`, 20261028-170645). The
dragon is the exception, unraisable as designed.

2026-10-28, GameLab tests the build under test even when you are subscribed to the
published one. With the All pack published, this machine's Steam account subscribed to it
(Workshop item 3828529950). The lab game loads subscriptions too, so `pkg-all` and
`pkg-all-every` enabled two `HammerwatchPlus-All` mods. The game keeps the first copy of each
path, which was the Workshop's: 153 of 170 scripts came from the published build, and the new
code failed to compile against its older library. A mix that happened to compile would have
passed while testing the wrong code. A package whose id a subscription has now goes into the
lab as `<id>-gamelab`, a boot error names any mod found twice, and every run asserts none
was. `run` warns about the same mix in your own install (`run: workshop:`).

2026-10-28, the Quality of Life card no longer overlaps: a tile on a card drops its extra
symbols when its name would run into the next column ("Improved behavior" ran into the hat).
Only the QoL card changed. Quality of Life, Pets and the All pack are republished on the
Workshop, carrying the shorter "Wep. swap" and "Improved behavior" labels too.

2026-10-28, the Forsaken Tower played from floor 1 to the end (`tower-run`, 20261028-190322,
pass in 16 min). The run used every floor's own exit for all 23 floors. On the way it cleared
657 enemies, used 55 level triggers and the chests, doors, shrines and wells, and fought all
six bosses. Traps fired in all five acts. Only archives_3's puzzle traps stayed silent, because
a player who doesn't make a wrong move never sets them off. The fixes it took:
- The vampire wakes once the crosses found on the chambers floors are placed on the altars,
  as in HoH1, and the bot places them.
- The bridge's exit to the dragon now runs through the mission. It used to leave the mission's
  floor on the bridge.
- HoH1's gambler (ItemDealer) and end window (EndOfGame) are ported on HoH1's own .gui files,
  with HoH1's scroll widgets. The gambler bets HoH2 trinkets, one gamble per gambler, and the
  end window's CONTINUE goes back to town (`tower-interfaces`, 20261028-182126).
- AddNotification shows its text through HoH2's announcer.

2026-10-28, pets keep out of trap rooms as well as puzzle rooms, and walk back out of one
they end up in. This is the new shared module `petrooms`: it is listed in Quality of Life,
and the Pets package and the All pack carry it too. It drives vanilla pets as well as the
Pets package's. A room is one puzzle unit, or traps on three spots (units within 12 px are one
spot, so a campaign glyph and its blast count once), within `petwait.radius`. A pet following
its owner back after a wait may cross a room for 5 s, so an owner who crossed a trap room is
followed through it. `plan-pets-b` (pet skills, puzzle and trap rooms), `plan-petrooms-vanilla`
(a vanilla pet, QoL alone) and `pf-plan-petrooms-vanilla` (the built QoL package) pass
(20261028-141504, -141825, -142113).

2026-10-27, every package on its own and together. `tools/generate/make_package_scenarios.py` now
also writes `gamelab/scenarios/pkgfeat/`: each feature scenario run against the built
packages that ship its mods instead of the source folders (162 scenarios). The first pass
found the pets package and the all-in-one pack carrying 216 HoH1 pet files cut from this
machine's HoH1 install. Nothing had been uploaded; the pets module now lists them as `local`,
and `tests/test_release_files.py` fails if a release package would carry any ignored file.
Every other failure turned out to be one of these:
- a flake that passed on a rerun;
- HoH1 content a release package never has (now `needs_hoh1`);
- a scenario that fails the same way from the source folders.
None failed only as a package. Without HoH1, the campaign, classes, pets and trinkets features
keep their stand-ins, and the player gets one chat line naming them (`hoh1-standins`; with
HoH1, `hoh1-installed` stays quiet). A package from another build now tells the player as
well as the log (`pkg-mismatch`). The all-in-one pack with all twelve single packages enabled
beside it passes every check (`pkg-all-every`). Still open: 17 scenarios that fail from the
source folders too (`docs/RE_NOTES.md`, "Packages on their own").

2026-10-27, script safety against game updates: every HWP module entry point (45 of them)
now runs inside `HWP::Guard` (hwplib `Guard.as`, applied by `tools/guard_modules.py`, which
`tests/test_guard.py` enforces). Before this, one module's script exception stopped the game
mode's frame update after the module loop, every frame (no screen shake, pings or death
check). Now the guard logs the error with its stack trace, the frame goes on, and after 30
errors in a row that entry point turns off until the next level, with one chat line;
`hwp guard` lists what failed. hwplib also names the game build at boot and tells the player
once when it is not the build HammerwatchPlus was tested on (176). A compile error still
stops the game on an empty main menu, since nothing compiles; `docs/GAME_UPDATES.md` is the
checklist that catches one before players do. Measured: `compile-err` (025559), `throw`
(030133), `throw-ctor` (031426), `guard` (031629); `mod-all`, `pkg-all` and
`pkg-pair-all-qol` pass with the guards in.

2026-10-27, code review fixes (fe617b8..3a6e9f9): ten fixes.
- The guard's unguarded trace run happens once per game process, and its throw is counted.
- `TESTED_BUILD` lives in `Guard.as`, so a mixed set of packages still compiles.
- A `compile_error` scenario fails if the scripts compile.
- `needs_hoh1` scenarios are skipped (exit 7) on a machine without the HoH1 import.

Tested: `guard` (103129), `compile-err` (103302), `hoh1-standins` (103355) and
`plan-runs-arch` (103410). Details are in `docs/RE_NOTES.md` ("code review fixes
(fe617b8..3a6e9f9)").

2026-10-27, the Paladin of Generosity: the eighth 4th spec (`mods/specs`, `Generosity.as`):
Pelor's Blessing stacks from Lay on Hands, Blessed Strike kills and Conviction, and at 10
stacks Pelor's Fury holds one enemy in beams of light (stunned, casts cut, armor and
resistances 0, more damage taken). A Fury that cannot hold spends nothing. Its four orbs are
built, and the farming module adds Pelor's favour (crops grow twice as fast and wild plots
turn up twice as often with a Paladin of Generosity in the party). Tested: `plan-generosity`
(020522), `plan-generosity-farm` (015840), and `plan-generosity-bosses` (022232): 16 of 18
bosses held mid-attack with their casts cut; the Serpent while untargetable and the Shadow
Face (immune to buffs) are refused by design and keep the stacks. The engine facts behind it
(spirits' sensor bodies, unflagged boss skills, a stunned bodiless unit's null body, the
buffered press) are in `docs/RE_NOTES.md` ("the Paladin of Generosity"). Display of Generosity
needs a party to check. The icons are final: the user's round-4 picks, with Holy Sacrifice
from round 2 (`look-generosity-icons`, 101621).
A code review of 1c5335c..def346d found ten problems; the fixes include the 35 Dev Arena
scenarios that still listed the removed core mod, an export that would bake vanilla paladin edits
into Generosity's copies, Holy Sacrifice paying out on a despawn, and `build.py all qol` writing
every package (`docs/RE_NOTES.md`, "Code review fixes (1c5335c..def346d)").

2026-10-26, packages: there is no core mod any more. The modules ship as twelve Steam
Workshop packages that each work alone, plus `HammerwatchPlus-All` (`packages.json`,
`tools/build.py`). The shared code is a library split into `hwplib`, `hwplib-luck` and
`hwplib-classui`, and every package carries a copy of the parts it needs. The dye-pot
minimap markers became the `mapicons` module (Quality of Life), and buying bag slots moved
to the keys module. Every package alone, the all pack and four pairs pass in GameLab
(`pkg-*`, `docs/RE_NOTES.md` "one path, two mods"). The engine logs one harmless
`Resource name hash conflict` error per shared file when two packages are enabled.
`run.py` and `deploy.py modded-prod` now deploy the all pack and remove the old
`HWP-<module>.bin` files, so a save ticks `HammerwatchPlus-All` once. The Workshop upload kit is
`tools/workshop.py` ([docs/WORKSHOP.md](WORKSHOP.md), 2026-10-27).

2026-10-28, Workshop pages v2 (368480f): every page opens with "Multiplayer supported" and what it needs, lists each module in a line, and ends with install, settings and a link to the All pack. Each picture is a card drawn from the game's art (`tools/workshop_art.py`), and the All pack's gallery shows every package's card. Ten packages and the All pack are updated. The Forsaken Tower was hidden by Steam (EResult 15 on every update).

2026-10-28, Workshop pages v3: **The Forsaken Tower is off the Workshop.** Its item (3828529832) is deleted, and the Workshop's All pack no longer carries it (`packages.json` `"workshop": false`, `tools/build.py --workshop`); your own build and `/run` still have it. The cards use the game's real art: the map drop's sea chart, the strongbox, the ace chest (the red-lidded gold chest), the waygate, the dye map icon, the skill orb, the watering can and game crops, two HoH1 trinkets (frying pan, lucky hat), and the town's exit guard, coloured as the game colours him. Generosity's card shows only its own skills. The All pack's cover shows every package with a few of its icons, and its page no longer names the HoH1 Classes. The Fourth Specializations pages say the Celestial Ruins DLC is needed only to use the Priest's 4th specialization. The All pack's gallery is uploaded one picture per submit and read back until each has an image.

2026-10-27, on the Steam Workshop: the twelve packages and the All pack are public, published
with `tools/workshop_publish.py` from 34d91f0. The All pack is
https://steamcommunity.com/sharedfiles/filedetails/?id=3828529950, and every item's id is in
`workshop.json`. HoH1 Classes is held back while those classes are parked.

2026-10-25 to 2026-10-26: the bug and feature list of 2026-10-22 (`temp/bugs 10.22.26.txt`) landed in 16 commits,
each with its own lab scenario (`gamelab/scenarios/fix-*.json`, all passing): Firearms feel and Snipe,
Arcane and Aerotheurge, the Forgemaster's risen and channels, fishing, farming, puzzles, pets, the run-start
screen, Luck, the boss and last-run recaps, the HoH1 campaign version with Battlements, traps and teleporters,
per-player map colours, the trapped-chest banner and the new `objectives` module. `mod-all` (32 modules)
and `plan-t9` are the integration gates; the session's notes are in `docs/RE_NOTES.md`
("Bug list 10.22.26").
A code review of those commits found ten problems (puzzle room offsets, client fishing loot, Luck buff
refreshes, map dots hidden with names, the Forgemaster's dash cooldown, pyre Heresy without the orb,
Luck raising drop rates, DoT missing from the boss recap, Blink past rails, duplicated carving code);
all are fixed and the nine affected scenarios pass again (batch `review-fixes-003`). Luck now has a
cell on the character tab's stat bar with a tooltip giving its factor ("code review, applied" in
`docs/RE_NOTES.md`).
In co-op a chest or strongbox now rolls at the Luck of whoever opens it and the whole party
gets what it rolled; an abyss crack rolls at the party's average. The party's average Luck
also reaches generated floors: an extra secret room, more and better floor rewards within
the vanilla ranges (food, mana, chests, caches, scrolls, valuables, the blueprint chance),
rarer blueprint recipes, more fishing holes, a likelier imp, more and higher keys and
more ace chests (`docs/design/luck.md`, `fix-luck-floors`, `fix-luck-imp`).

A second code review (69ba108..e1f1fc7: tavern levels, Way Gates, roulette, Auto Aim, the trinket
work) found ten more problems, all fixed: the sixth tavern level could never be built (it asked for a
guild hall level past the top); roulette chips on the table were lost when a run started (they now go
back to the town's gold from the town's save); a client's Way Gate list went stale after a building
upgrade; Auto Aim moved the gamepad's own aim, skipped vanilla's SetSkill for auto skill and scanned
every frame; a null blueprint check came after its use; trinket strings used a second prefix; a big
roulette payout could overflow (the stake setting is now capped at 10,000,000); and the custom stat
lookup was copied four times (now `HWP::CustomStat`, core `CustomStats.as`). mod-all, mod-roulette
(with a new leave check), mod-autoaim, mod-tavern, mod-waygates and mod-trinkets pass
("Code review fixes (69ba108..e1f1fc7)" in `docs/RE_NOTES.md`).

The Skill 4-6 keys now live in `classes`, since only the HoH1 Assassin, Shadow, Trickster
and Retiarius have more than three actives. Core keeps a hook-only targeting helper
(`TargetHelper.as`) for them and for Auto Aim.

The Gold Collector pet mod is gone (vanilla pets already pick up gold). The gold-worth looks moved
out of core into `goldworth`, and Mm-hmm! is its own `mmhmm` module: besides crits, the hat now voices
revives, wells, secret rooms, completed trinket sets, the last orb of a multi-orb tree and Ace chests
(mod-mmhmm, mod-all, mod-keys, fix-gold-sprites pass; a real two-player revive is untested). The Devil Forgemaster's eating now heals
30% of max health a second instead of +50 regeneration (plan-forgemaster-eat).

Core is plumbing only now: the orb warning is its own `orbwarn` module, the use key's
pickup-first order belongs to `droptrade`, and the bet tokens belong to `gambler`, which
registers them as the market's second currency (without it, fish sell for gold). The
materials tab has two untitled sections the modules title and fill: Supplies (gambler,
fishing) and Plants & Herbs (farming).

The full QA sweep is paused and incomplete. The [current checkpoint](generated/qa_pr_checkpoint.json)
records 10 gameplay repairs and scoped passing coverage for the six original
fourth specs: 60/60 rank rows and 61/65 orb qualities; Firearms 60/60 rank rows and 74/75 orb qualities;
HoH1 imports 29/39 skills and 136/191 positive ranks; 9/9 selected-mastery saves.
The later Priest Forgemaster work is outside those original matrix counts.
These counts do not establish complete mechanics, UI, interactions or ordinary
run lifecycle coverage. Five orb-quality cases require real co-op.

Agents and contributors: start with [CLAUDE.md](../CLAUDE.md), the
[GameLab quickstart](../gamelab/README.md), and the
[regression/known-failure map](qa/REGRESSIONS.md). Deferred QA drafts are
[committed for fresh-clone recovery](qa/deferred/README.md), still unapplied.
Historical native/package results retain their original source epochs; this
handoff update adds documentation and a batch helper, not native coverage.

<details>
<summary>Historical feature and QA checkpoints</summary>


- 2026-10-22 overnight QA remains incomplete. Eight scoped
  gameplay repairs have passing reproductions: Shadow Strike, Riposte, per-gun magazine
  crit, Hoarder HUD cleanup, Thunder Orb cast attribution, returning-arrow catches,
  custom weapon-family stash sorting and Dragon's Breath patch persistence
  (`20261022-085158`). All 14 required regression scopes passed at their recorded
  fingerprints; later changes only extend read-only QA telemetry. Production sources
  and release payloads remain unchanged after those passes;
  exact evidence and limits are in `docs/QA_OVERNIGHT.md` and `docs/generated/qa_*_inventory.json`.
- 2026-10-22 night: PR #9's code review applied after its merge (explicit `off-hand` flags on
  the gun rounds, Extended Clip Crit with no actor, typed stash ids in any slot, launcher and
  runner guards; `docs/RE_NOTES.md`, "PR #9's code review, applied after the merge").
- Current granular coverage: the six built fourth specs have 55 of 60 skill-rank rows
  with scoped passes and 5 partial; their 65 orb-quality rows have 47 scoped
  passes, 3 partial, 11 untested and 4 blocked on real allies. Firearms has 42 of 75
  orb-quality rows with scoped passes, 32 untested and 1 blocked; its 60 skill-rank
  rows have 10 scoped passes, 10 partial and 40 untested. The three hidden
  HoH1 ports each completed two ordinary floor transitions, but full boss/reward runs
  remain unverified; 4 of their 39 skills have scoped granular passes at 14 of 191
  positive-rank slots. These counts
  preserve the narrower effects measured in each row; they do not establish full coverage.
- The default build produced and verified all 32 archives in `dist/`: 31 content modules
  and `HammerwatchPlus-All.bin`, whose 955 entries exactly match their union. All-in-one
  SHA256: `8d42ca89b379f7bb4ada76085fa6cc1e5ec3c28d6aacbdd4970393c0ecf01274`.
  Every archive's metadata and decompressed payload were checked. The complete 31-module
  stack, UI/settings search, stash save/reload, Architect pricing and controlled event
  timeouts also have scoped passes. Older scenario passes below remain historical evidence.
- Every solo step of the in-game test plan has a `gamelab/scenarios/plan-*.json` scenario.
  As of 2026-10-18 they all pass in GameLab except Weapon Swap's "only you can pick it up",
  which needs a real lobby. The Firearms Specialist's checks (`plan-t14`, `plan-firearms-*`)
  last passed on 2026-10-19 and 2026-10-20.
- The co-op steps need two players: GameLab runs one game, and HoH2 only connects through
  Steam/GOG lobbies.
- GameLab is pinned to build 25932569 (since 2026-10-19).
- 2026-10-21: doctor and bootstrap also find a portable compiler in the ignored local
  toolchain cache, without changing the system PATH. Fresh-command doctor is green;
  the hidden smoke passed (`20261021-235153-null-payload-lab`). Setup details and checks
  are in `docs/RE_NOTES.md`.
- Firearms still to do: the two base passives (the old Scavenger and Steady Hands stand in)
  and final icons (the current ones are placeholders from `tools/generate/make_firearms_icons.py`).
- Firearms gained the Hand Cannon, the Flamethrower Rifle and the Full Auto Rifle on
  2026-10-20 (`plan-firearms-cannon`); the rifle is now the Grenade Launching Rifle.
- Built on 2026-10-21: the 4th specs of the Ranger, Wizard, Sorcerer, Rogue, Warrior and
  Warlock (`mods/specs`). `plan-specs` passes all six (80 checks, after the code review's fixes). Not yet tested: what
  needs a second player (teammates in Protective Gale and Shared Breath, the standard's
  allies, Martyr's Banner, Mana Conduit). The world sprites (brand sigil, Hellfire Claw, the standard, the
  Tempest orb) are in. The icons are the user's picks over three rounds (`art/specs/override/`, `tools/art/icon_art/sp.py`,
  `sp_r2.py`, `sp_r3.py`); the Arcane and Aerotheurge emblems keep their placeholders by choice. The
  sounds are the user's picks too (`art/specs/AUDIO.md`; Void Barrier's save silent). Still to do: balance (pick them in the audio picker, `art/specs/AUDIO.md`).
- 2026-10-21: the Ranger's and Wizard's 4th specs now match Noah's PR #4 version in the planner:
  **Deadeye** (Lightning Arrow; Gathering Winds gives a Tailwind stack every 5 kills, each lasting
  4 s on its own, +2-4% Action Speed a stack) and **Aerotheurge** (Thunder Orb; Static Charge gains
  a stack per spell cast, plus one on its first crit, and a new Lightning Rod orb). The ids are kept, so
  saves still work. `plan-specs` passes (run `20261021-212606`, 17 checks). The crit stack is not
  tested at that checkpoint; the overnight sweep now has native critical-hit regressions.
  The Paladin's 4th spec is still being designed.
- 2026-10-21: the Warlock's **Essence Extraction** now matches the planner (the user's version of
  Colin's design). Magic weapon hits (every arcane-tagged weapon) gain Essence once per 2 to 1 s, and
  Essence from a Pyrebranded enemy counts twice (two stacks; Drain Essence's bleed, health and mana
  twice). The old +max Essence and the melee-on-branded-elites gain are gone. Reading "trigger twice"
  that way is assumed. `plan-specs` passes (run `20261021-232748`). Original flakiness: Lightning Arrow's
  Tailwind Catch caught 0 to 3 of 3 returning arrows across five runs (`storm_catch` failed twice).
- 2026-10-22: the Priest's 4th spec, the **Devil Forgemaster**, is fully designed in the planner
  (Necrotic Resurrection, Call of Heresy, Heresy as its own stack, which bosses can be raised).
  Sacrificial Penance, the form Necrotic Resurrection takes at max Divine Favor, has its own
  planner entry (new `alt_of` field): mana 50, sharing Necrotic Resurrection's cooldown. Its
  icons are in the picker (`tools/art/icon_art/sp_pri.py`, then `sp_pri2.py`): the second pass on
  the user's picks, plus the emblem, four orbs and the eating status; all 11 settled in
  `art/specs/override/`, and shown in the planner). Penance consumes the Favor.
- 2026-10-22: the **Devil Forgemaster** is built (`mods/specs`, `Forgemaster.as`). Any enemy death on
  the floor rolls an intact body (green glow on the Forgemaster's own screen); Necrotic Resurrection
  channels on it (3 s, 5 s elite, 10 s boss) and raises a copy of that enemy on your team with its own
  skills at 50-100% health and damage (at least 120 health), up to 2-4 at once, decaying and never
  healing, leash-teleporting
  like other summons. Heresy +1/+2/+3 per raise, refused at 5; at max Divine Favor the same key is
  Sacrificial Penance (50 mana, removes the level's 1-3 plus 1 for an elite body and 2 for a boss body).
  The four orbs are in. The risen come from `tools/generate/make_forgemaster_risen.py`: one risen and one body
  unit per raisable enemy of the base game (141 units, the 10 non-final bosses included, at 3000-8000
  health with their arena-only skills stripped and their player-only targeting opened up), checked for
  well-formed XML and regenerated by `doctor --fix`. Tested by `plan-forgemaster` (run `20261022-102006`:
  all 141 units raised, attack, follow and leash-teleport, seven of them support units that only buff;
  the forge, Penance, Heresy and decay steps pass; that run's lunge and bosses steps failed on chance,
  0 lunges in 25 bodies at 16% and the Face's first spew after its 15 s window) and
  `plan-forgemaster-bosses` (run `20261022-084131`: Penance, Heresy, the lunge, all ten bosses raised,
  attack, follow and leash). The fair-die check, the 40 bodies and the 25 s boss window pass in the
  valid re-run `20261022-144616` (after a `/code-review medium`: Heresy and the cooldown come with
  the host's answer to a raise, the cost is spent when the channel completes). The lunge now dodges
  (the Dash skill) to just under the body, faces up and eats it bobbing 1 px with blood flying out;
  a Penance dodges there too and a golden light grows out of the body as it channels
  (`plan-forgemaster-eat 20261022-154317`). Balance is a first pass.
- 2026-10-22: the **beta build** for testers without the Celestial Ruins DLC:
  `python tools/deploy.py modded-prod --beta` folds `mods/holylocal` (the Priest and its weapons
  with the `dlc has holy` conditional removed, local_only, used with the dev team's permission)
  into HWP-core.bin, so only HWP-core and HWP-specs are enabled (since the packages: every package
  that carries hwplib). A plain build never carries it.
  Verified: with it the create-character list offers the Priest and "create" makes one
  (`mod-holylocal-priest 20261022-163957`); without it there is no Priest
  (`mod-holylocal-priest-control 20261022-164029`). **Remove `mods/holylocal/` before publishing.**
- 2026-10-22: core overrides `GUI/PlayerMenu/Modifications.as` (one line) so the HWP skill
  descriptions' `%param%` tokens are filled in the main menu's create-character tooltips, where
  no player actor exists yet (assumed from the code, not run). The install's hidden-classes and
  Firearms-figure complaints were a stale 10-19 deploy: redeploy with `deploy.py modded-prod --beta`.
- Designed in the planner, not built, and parked for later: an "Echoes of Hammerwatch I"
  (formerly "HoH1 Remastered") 5th spec for every vanilla class (the Rogue's from the HoH1
  Thief, the Warrior's from the Gladiator), one active and one passive of HoH1's that HoH2
  lacks. The icons are wired up (`tools/hoh1/import_hoh1.py classes`).
- Parked on 2026-10-21: the Thief, Gladiator and Witch Hunter are hidden from character
  creation (`HWP::HideClass`, run `mod-classes-hidden`). The planner shows them on a second
  "HoH1" row with the six original HoH1 classes, whose kits are the HoH1 ones
  (`tools/hoh1/planner_hoh1.py`), with armor-only gear and orbs still to design.
- What each session changed, with the GameLab run behind every claim, is in
  `docs/RE_NOTES.md`. The HoH1-to-HoH2 trinket comparison is a private web app outside the
  repo; its link is there too.


</details>


### Resumed full sweep (historical snapshot) ? no time limit (2026-10-22)

The user removed the original overnight deadline and activated the goal again. Work remains in progress; the original deadline/final-hour notes below are historical. Verified scoped coverage now includes60/60 fourth-spec rank cases,49/65orb qualities (nine fresh Branding qualities awaiting granular audit; maximum combo failed),20/60 Firearms ranks,42/75orb qualities,62/191HoH1positive ranks and9/9mastery save/reload combinations. Native stat-only scopes remain separate from combat/cadence/mitigation.

Fresh full-stack `mod-all 20261022-111422` and minimal `null-payload 111454` compile/load checks passed with the read-only per-frame resource observer. `qa-firearms-ranks-base 111509` and `qa-specs-living-mana-coefficients 111830` passed; exact per-run hashes are in the ledger/journals. `qa-specs-branding-orbs 113033` now obtains strict fine-grid/native-ray geometry through normal walking but fails the maximum-combination check. `qa-classes-gladiator-hoh2-run 112028` reached Keep3 and died during objective travel; no class/encounter bug is inferred. Controlled endgame weapon tests112325/112427 failed native equip requirements before attack/parry testing: ilvl35 requirements use unbounded vector interpolation at34/9, not the high endpoint at level10. A QA fixture correction is staged; no production change is inferred from these setup failures.

The source is frozen during each serial GameLab batch. Remaining ranks/orbs, legal interactions, ordinary run lifecycles, UI/acquisition and module functional/persistence/failure paths remain required. See `docs/QA_OVERNIGHT.md` and `docs/generated/qa_overnight_summary.json`; previous repair regressions and all failures are retained.


### Historical resumed sweep checkpoint (2026-10-22; superseded above)

The full sweep has no time limit. Scoped native coverage is 60/60 fourth-spec rank rows and 61/65 orb-quality rows (four require true co-op), 60/60 Firearms rank rows and 71/75 orb-quality rows (three Reload rows await a corrected idle-timer test; one requires co-op), and 118/191 positive HoH1 ranks across 26/39 abilities. All nine selected-mastery save/reload combinations pass. These counts cover the recorded effects, not every amplitude, boundary, interaction, UI or ordinary lifecycle requirement.

Two additional gameplay repairs are verified: Branding no longer retains the Essence damage bonus after consumption, and Gladius now deals native weapon-scaled damage instead of zero. Gladius first-contact damage passes at all five ranks in `qa-classes-gladius-collision 20261022-145123`. Current full-stack load passes in `mod-all 145021`; all 31 modules also have standalone load evidence. Full module functionality remains incomplete.

The current serial batch is finishing Branding quality combinations and Sphere acquisition/UI prerequisites. Reload's expired negative input timer and Grimoire's stationary-glyph target distance are source-reviewed QA corrections awaiting native reruns. A Branding combination failed its clear-lane setup before any combat trial; it remains recorded and under investigation. Ordinary runs also need a source-correct reward-window input flow before boss/reward/save coverage can be claimed.

The earlier 32-archive package verification predates the Branding and Gladius repairs. Those archives are historical; current-source packaging and final regressions remain required. The detailed source epochs, original failures and remaining work are retained in `docs/QA_OVERNIGHT.md` and the generated inventories.
