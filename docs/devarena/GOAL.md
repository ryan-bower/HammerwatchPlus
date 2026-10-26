# Goal prompt: build the Dev Arena

Paste everything below the line into a fresh session started in
`C:\FastProjects\HammerwatchPlus-devarena` (or hand it to `/loop`).

---

You are building the **Dev Arena** for HammerwatchPlus: a GameLab-booted dev build of Heroes of
Hammerwatch II for building, tuning and benchmarking elite specs (subclasses). The full agreed
design is `docs/devarena/SPEC.md`. It is the contract: decisions table, UX section, happy paths
HP1-HP7, definition of done. Read it first, then `CLAUDE.md`, `.claude/skills/gamelab/SKILL.md`,
`docs/modules.md`, `docs/hooks.md`, and the memory index. The user's decisions in SPEC.md override
any recommendation of yours or a subagent's. If the spec is silent, pick the conventional option,
write it into SPEC.md under "Decided during build" with a one-line reason, and keep going. Only
stop to ask when a choice would contradict SPEC.md or is irreversible.

## Working rules (non-negotiable)

- Work only in the `dev-arena` worktree, `C:\FastProjects\HammerwatchPlus-devarena`. Commit
  6ee00a1 is a snapshot of another agent's WIP. Don't edit their files beyond small additive hooks.
  Put our code in new files: `mods/devarena/`, `mods/spec-*/`, `mods/vanilla-tuning/`,
  `tools/devarena/`, `tools/make_presets.py`, `gamelab/scenarios/devarena/`, `tests/`.
- Boot the game only via `python -m gamelab run <scenario> --mode lab --wait 1800`. Follow every
  CLAUDE.md hard rule: no real input, the exit codes are refusals, never touch the user's install,
  cfg or saves.
- Tail the game log for every run. Kill every watcher you start (and your subagents') when the
  run ends. Put a timeout on every wait.
- In-engine tools use at most one console command. Arena actions are hotkeys and in-engine calls,
  not gl verbs. Read-only gl probes for scenarios are fine (re-run `tools/list_verbs.py`).
- Python for all tooling (uv project). Use Edit/Write for anything with backslashes.
- Label every claim **verified** (a GameLab run id, a log line, or file:line in decompiled source)
  or **assumed**. Never credit a feature you have not seen work in a run.
- Commit at each milestone on `dev-arena` with the attribution trailer. Never push.

## Build order and gates

Do these in order. A milestone is not started until the previous gate is green.

1. **Spikes** (each is a scenario with a pass/fail assertion in `run.json`):
   - live skill rebuild: field + bind damage read back on the live skill, and two casts at the
     new cooldown;
   - deferred apply between casts;
   - freeze by stun: 0 movement and 0 damage over 10 s;
   - a non-pausing dock with mouse capture: heartbeat `paused` stays false and posted keys still
     move the player;
   - in-session text input (fallback: sliders and steppers);
   - a mod class through `InstantiateClass`;
   - buff `LoadParams` retune;
   - RNG reseed for a fixed-seed bench.

   A spike that fails takes the fallback the spec names. Record the measured result in
   `docs/RE_NOTES.md` with its run id.
2. **Tuner:** override file as the source of truth, curve editor, versions + undo, A/B (F2),
   mini HUD, Tune tab.
3. **Loadouts:**
   - `tools/make_presets.py`: 24 vanilla subclasses x early/mid/end, trinkets tag-scored, combo
     by tag, named variants from the override file;
   - headless validation;
   - Loadout tab (favorites, browser, sheet, compare);
   - the tooltip lint.
4. **Arena + golem:** dev-arena scenario on the seeded floor, walled golem section, F3/F4/F6,
   brush spawning, mob toggles, golem unit + profiles + debuffs + player buffs.
5. **Bench:**
   - stats and fixed-seed modes;
   - rotation priority lists, record/replay, hands-off A/B interleave with abort on input;
   - breakdown with an unattributed row, procs, mana;
   - sibling and all-24 verdicts with a cached vanilla baseline;
   - champion/challenger, history, CSV to `gamelab/results/bench/`, promote to `docs/bench/`.
6. **Panels:** cast timeline, slow-mo, proc inspector, resource/survivability, encounter set.
7. **Compose + new spec:** templates over a raw tree (schema scraped from `GetParam*`), existing
   assets only, validation before apply, slot replacement, the subclass clone script writing
   `mods/spec-<id>/` (lang placeholders, parent icons), star-budget check.
8. **Relaunch (HP5), ship check (HP6), auto-tuner with feel locks and pending proposals (HP7).**

If context runs low, write `docs/devarena/CHECKPOINT.md`: what is done (with run ids), what is
next, and open risks. Then continue from it.

## End validation clause (the goal is NOT done until every item holds)

Run all of these on the pinned build, from a clean `python -m gamelab reset`, in the worktree:

1. `gamelab/scenarios/devarena/acceptance.json` runs SPEC.md's definition-of-done steps 1-8 in
   one GameLab run and exits 0 with verdict PASS. Every step is an assertion in `run.json`, not
   just a log line.
2. One scenario per happy path, HP1-HP7, each exits 0 with PASS. HP2 and HP3 produce bench CSV
   rows carrying preset, variant, version, RNG mode, n and spread. HP5 asserts that preset, A/B
   slots, position, golem settings and the open tab survive the relaunch.
3. All 72 presets plus every named variant apply and read back in game (exit 0). Headless preset
   validation and the tooltip lint pass.
4. `python tools/list_verbs.py --check` passes. `uv run pytest` passes with new tests for
   make_presets, the override-file round trip, the curve math, the bench stats and the composer
   validation. The game log of every validation run has no new error lines from `hwp`,
   `devarena` or `spec-` paths.
5. Focus and input safety: in the acceptance run, the foreground window never changed (sampled
   every 50 ms), and no forbidden input API was used.
   5a. Resolution: one end-of-goal visual run at 1920x1080 and one at 2560x1440 (lab window
   size, hidden desktop), dock open on each tab. Text is readable, nothing is clipped or
   off-screen, and the dock keeps its share of the screen (SPEC "Decided during build" 1a).
   This is the heavy check, so run it last, with the acceptance run.
6. Docs are updated: `docs/modules.md` (devarena, spec-*, vanilla-tuning), `docs/RE_NOTES.md`
   (every spike result with a run id), `docs/generated/verbs.md`, and a `mods/devarena/README.md`
   user guide covering the hotkeys and each happy path. Update README.md only if the user asked
   (see memory).
7. **Independent verification:** launch a fresh adversarial subagent that did not write the
   code. Give it SPEC.md and the run ids only. It re-runs the acceptance scenario and two happy
   paths of its choosing, spot-checks 10 claims in the final report against code or runs, and
   tries to break HP1, HP2 and HP5 with edge inputs: max/min values, cooldown < castpoint, a
   sub-skill-masked field, an apply mid-channel. Every defect it finds gets fixed and
   re-verified. The goal is done only when its verdict is "no blocking defects".
8. Final report to the user, under 40 lines:
   - each happy path with its run id;
   - every spike outcome (verified or fallback taken);
   - everything still **assumed**;
   - the exact command to launch the arena.

If any item cannot be met, the goal is not done. Do not soften the criteria. Say which item
failed, why, and what is needed from the user, and leave a CHECKPOINT.md.
