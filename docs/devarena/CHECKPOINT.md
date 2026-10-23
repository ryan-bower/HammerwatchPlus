# Dev Arena: resume checkpoint

The goal is `docs/devarena/GOAL.md` and the spec is `docs/devarena/SPEC.md` (build order and
"Decided during build"). The branch is `dev-arena` in worktree `C:\FastProjects\HammerwatchPlus-devarena`.

## Done (verified)

| Build step | State | Evidence |
|---|---|---|
| 1. Spikes | done, commit `4554b9f` | `docs/RE_NOTES.md` 2026-10-20 "Dev Arena spikes" |
| 2. Tuner | done, commit `1fe8875` | tuner-dock 20261020-225735, export-boot 20261020-230402 |
| 3. Loadouts | done | loadout-all 20261020-233249, loadout-dock 20261020-232844, `tests/test_make_presets.py`, `tools/devarena/tooltip_lint.py` (vanilla 0 stale) |
| 4. Arena + golem | done | arena-dock 20261020-235731, golem-room 20261020-235415 |
| 5. Bench | done (panels deferred) | bench-dock 20261021-004821, hp2-golem-tuning 20261021-003613, hp3-loadout-compare 20261021-003510, `tests/test_devarena_bench.py` |
| 7a. Composer | done, commit `d3f3ff2` | hp4-compose 20261021-011713 |
| 7b. Spec clone | done, commit `10e2291` | spec-clone 20261021-011648, `mods/spec-ranger-test/` |
| HP1 feel | done, commit `bcd5dc7` | hp1-feel 20261021-012123 |
| HP5 relaunch | done, commit `7ebc171` | hp5-relaunch 20261021-013132 |
| HP6 ship | done, commit `50d2f77` | hp6-ship 20261021-014726, `docs/devarena/ship/ranger_test.md` |
| HP7 auto-tuner | done, commit `465e852` | hp7-autotune 20261021-015752, `docs/devarena/proposals/` |
| Acceptance | `gamelab/scenarios/devarena/acceptance.json` (DoD 1-8 in one run), PASS | acceptance 20261021-020844 (first run 20261021-020414 failed: Skill2 pressed for slot 2, and the spec class logged `apply failed` for ranger_nature edits, now `apply skipped`) |
| Review fixes | D1 hp5 filter step, D2 int32 range, D3 field limit 160 + refuse on overflow, D4 castpoint keeps timeline[0], D5 bench clears lingering units, N1 negative times refused | edge 20261021-025759, hp5-relaunch 20261021-025859, bench-bleed 20261021-025945 (first review: acceptance 024505 PASS, hp1 024929 PASS, hp5 024847 FAIL) |
| Review 2 fixes | B1 castpoint move skips only the "start" entry, B2 a click commits the typed field before the button acts, Compose int32, overflow flag clears on Backspace | edge 20261021-031450, acceptance 20261021-031536, hp1 031919, hp4 031943 (review 2: acceptance 030146, hp1 030856, hp4 030920, hp5 031210 PASS; rev2 edge runs FAIL on B1/B2) |
| Review 3 fix | a click that commits a field is bound to the button drawn under it (a filter/search reflow no longer redirects it) | edge 20261021-032945, acceptance 033037, hp1 033421, hp4 033445, hp3 033550 (review 3: acceptance 032125 PASS, rev3-b2 032601 FAIL) |
| Review 4 fix | a growth click while typing flushes the typed edit first; growth is refused while an edit waits on a cast | edge 20261021-034903, hp1 034957, hp4 035022, acceptance 035128 (review 4: acceptance 033739, hp3 034401 PASS, rev4-commit 034134 FAIL) |
| Review 5 fix | a preset that changes class restores the old class's defs and re-applies the live version to the new one | class-switch 20261021-040406, edge 040436, hp1 040524, hp3 040549, hp4 040649, hp5 040755, acceptance 040842 (review 5: rev5-class 040148 showed the stale/vanilla values) |
| Review 6 fixes | the tuner state rides the town save across a level change (fingerprinted to the boot file); clone_spec takes the compose-dict of the version it ships | tuner-reload 20261021-042320, edge 042401, class-switch 042450, arena-dock 042513, hp1 042546, hp2 043403, hp3 042611, hp4 042711, hp5 042816, hp6 042902, hp7 043621, acceptance 043001 (review 6: rev6-reload 041452 lost v1; clone_spec on 041840's log shipped B's dict for A) |
| Review 7 | no blocking defects; non-blocking items in `docs/RE_NOTES.md` "Seventh review" | rev7-levels 20261021-044701 (reviewer's scenario, deleted afterwards) |

## Next

6. Panels (deferred by the user, 2026-10-21: skill design, UI and happy paths first).
9. End validation per GOAL.md: the 1920x1080 and 2560x1440 visual runs are done (res 20261021-022008); bench-baseline ran (20261021-022359, 72 rows); seven adversarial reviews ran; review 7 on `ab2388c` (rev7-levels 20261021-044701) ended "VERDICT: no blocking defects". End validation is complete.

## Launch (a human)

`python -m gamelab run devarena/arena --mode watch`

## How to run

- `python -m gamelab run devarena/<name> --mode lab --wait 600`, with an outer `timeout 900`.
- Exit 4 after a compile error: fix it, then `python -m gamelab reset`.
- `python tools/devarena/run_export_boot.py` writes its input files and restores them afterwards.
- `uv run pytest`. One failure is pre-existing and not ours:
  `test_pilot_combat_loot.py::test_use_walks_straight_in_when_no_route_starts_near_the_target`.
- `python tools/list_verbs.py --check` (regenerate it after adding verbs).
- `python tools/make_presets.py --check` and `python tools/devarena/tooltip_lint.py`.
- AngelScript refuses `string &inout`; use `&in` + `&out`.
- Heredocs eat backslashes. Write JSON with regex patterns using the Write tool.

## Watch-mode input (2026-10-21, after the goal)

The mouse in watch mode works again: the shim hand-off and the TrackMouseEvent hook are covered in
`docs/RE_NOTES.md` "watch-mode mouse". The e2e is `gamelab/scenarios/devarena/watch-input.json`
(`python -m gamelab run devarena/watch-input --mode watch`). Its `da-inputlog on reset` is a test
cheat (infinite mana, no cooldowns) and shows a red banner while on. Open: the `v` (skill3 second
press) assertion and a clean watch run with nobody in the window.
