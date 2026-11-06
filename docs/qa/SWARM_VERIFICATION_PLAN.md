# HammerwatchPlus swarm verification and repair plan

Status: planned on 2026-10-29; execution active from 2026-10-30. Start from
`codex/run-save-builder-followup`, based on PR #83 head
`964e1b7e16d6221a1bdfd70fdb181f1f8a360446`. This plan does not resume the
historical evidence or add test coverage by itself. Actual execution status and
scoped evidence live in the tracker and current generated coverage inventory.

Execution scope update (2026-10-30): the user explicitly deferred genuine co-op
tests. Preserve their original definitions/history and record the deferred
disposition; do not count simulated peers or source review as multiplayer passes.
Source/network-contract review and all solo controlled, ordinary, lifecycle and
packed verification remain in scope. Mixed tasks retain their solo obligations;
the co-op deferral does not close those checks.

The [agent tracker protocol](SWARM_TRACKER.md) defines the persistent execution
interface. Start with `python tools/qa_swarm.py resume --owner <alias>` after every
compaction. The ledger is initialized with 27 queued bootstrap tasks; lane owners
add bounded feature/check/repair tasks as they inventory their scope. Bootstrap
completion alone cannot close this campaign.

Use 32 agents initially, including the coordinator, with a working ceiling of
48 when independent tasks justify expansion. The session limit is 100 total.
Parallelize investigation, isolated checks, test design, patch drafts, and evidence
review. One runtime owner runs every native test serially; one integrator applies
reviewed changes between frozen batches. Bugs found during verification remain in
the campaign until fixed and retested or explicitly deferred with a reason.

## Scope and current baseline

Cover shipped behavior and supporting code: all release modules and libraries,
Python tooling, GameLab and its oracles, generators/importers/archive formats,
packaging, planner server/data/browser behavior, and developer tools. Inventory
optional and benched code separately so it receives an explicit disposition.
Preserve authored balance, planner ownership, and unrelated user changes.

Current `packages.json` contains 12 packages and 42 distinct feature modules,
plus three library parts. `mod-all` includes those features. The historical
31-entry module inventory contains older module identities and cannot serve as
the current denominator. The original six-spec matrix also excludes both Priest
Forgemaster and Paladin Generosity; Branding has changed since that matrix.

The recorded build is 25932569 / B176. The runtime owner must check the actual
pin and doctor report before execution; a changed build is a decision item,
never permission to re-pin automatically. Existing PR save-preparation evidence
and old regression passes retain their recorded source revisions.

Read [AGENTS.md](../../AGENTS.md), the [quickstart](../../gamelab/README.md),
the [regression guide](REGRESSIONS.md), and the
[GameLab skill](../../.claude/skills/gamelab/SKILL.md) before execution.

## Agent allocation and ownership

The initial roster totals 32, including the root agent. Agents are ownership
roles, not 32 simultaneous test processes. Reuse an idle owner before spawning
another. Only the coordinator allocates additional agents; nested delegation
must appear in the same roster and count toward the session limit.

| Role | Slots | Responsibility |
| --- | ---: | --- |
| Coordinator | 1 | Inventory, priorities, task leases, freeze acknowledgements, status and unresolved decisions |
| Runtime owner | 1 | Doctor, the designated runtime checkout, every native launch, raw evidence and teardown |
| Integrator | 1 | Sole editor of installed source, shared-file changes, regeneration, builds and source epochs |
| Evidence steward | 1 | Coverage matrix, task/findings records, portable summaries and final claim audit |
| Domain owners | 24 | The lanes below; reviews, isolated checks, reproductions and proposed repairs |
| Independent reviewers | 4 | Rotate across runtime/save safety, combat oracles, state/economy/network, and release/planner/UI |
| Total | 32 | Expand toward 48 only for named, independent work |

Each domain owns the following scope. Shared files always go through the
integrator, even when a domain proposes their changes.

| Lane | Ownership | First verification targets |
| --- | --- | --- |
| H1 | Save creator, `save_builder.py`, `play_profile.py`, `profile_seed.py`, profile bot | Exact roster/gold after reload/export; corrupt input; fake-install transaction failures; preservation of existing files |
| H2 | Runtime isolation, launcher, `lock.py`, restart, resource snapshots and posted input | Active-player refusal, inaccessible process identity, cancellation, dirty/stale state, no other owner's lock deletion or real-input calls |
| H3 | Batch scheduling, GameLab Python oracles and observer contracts | Source drift, stale/partial/mismatched results, false aggregates, geometry/input/resource contracts, constituent effect rows |
| H4 | Doctor, save backups, bootstrap/path/compiler discovery | Ambiguous accounts, damaged backups, missing prerequisites, sandbox preservation and existing machine-local choices |
| B1 | Builds, release composition, generators, assets, HoH1 conversion/imports and archives | Dependency closure, decoded archive integrity, stale outputs, safe paths, personal/dev-content exclusion, corrupt-format handling |
| D1 | Developer tools, devarena, tuning/bench/clone helpers and remaining host utilities | Temporary-fixture tests, parser boundaries, reproducibility, abort/cleanup and release exclusion; label optional runtime scope |
| P1 | Planner server, inline JavaScript, data relations and icons | Temporary-data CRUD, invalid requests, all class views, budgets/status/alternate forms, polling and save errors |
| L1 | `hwplib`, `hwplib-luck`, `hwplib-classui`, hooks/settings/shared actions | Authority, record ownership, module disable/re-enable, persistence, cleanup, settings completeness and shared overrides |
| F1 | Firearms gun, magazine, reload, held model and pose state | Uneven hands, swap/unequip, interrupted reload, input release, floor/save continuity, actual per-gun critical damage |
| F2 | Firearms skills, projectiles, gadgets, turret and orbs | Damage/radius/timing/expiry, cost and cancellation, turret consumers, legal orb interactions and boundary exclusions |
| C1 | Thief | Knives, Grappling Hook, Smoke, Shadow Strike geometry, all ranks and actual passive procs |
| C2 | Gladiator | Pit Fighters, Beast, Pack Leader, summon ownership/attacks, Gladius, Riposte, Caltrops and Whirl |
| C3 | Witch Hunter | Hound, Ward, Crows, Pack, Net duration contract, Pyre ownership and natural-kill procs |
| S1 | Arcane and Winddancer | Unified resource bounds/death/healing, Blink geometry, barriers/feedback, orb consumers and transition cleanup |
| S2 | Aerotheurge and Deadeye | Per-cast critical attribution, delayed spell overlap, return/catch geometry, collision and outside-radius controls |
| S3 | Branding and Bannerlord | Current charged Pyrebrand, post-spend refresh, legal orb combinations, banner ownership/overlap/expiry |
| S4 | Forgemaster | Body families, bosses, interrupted channels/payment, Heresy thresholds, risen behavior and floor persistence |
| S5 | Generosity | Rank effects, stack spending/gain, refusal preservation, boss targeting, channel exit paths and farming interactions |
| M1 | Campaign, keys, maps and imported traps | Reachable generation, chest refusal/rewards, boss/progression paths, map traversal and HoH1 prerequisite distinctions |
| M2 | Puzzles, objectives, strongbox, abyss, weapons, trinkets, valuables and affixes | Successful clear/reward plus timeout, item effects, scaling, placement failure and bounded random sampling |
| M3 | Fishing, farming, gambler, roulette and tavern | Exact economy, insufficient funds, cap/overflow, cancel/abort, growth/harvest, trap payouts, Luck and market currencies |
| M4 | Pets, petrooms, summons, legacy, mercenary and wavemode | Courier conservation/restart, trap waiting, restoration without duplicates, title persistence, death/prestige and wave rewards |
| M5 | Stash, weaponswap, attrclick and other QoL modules | Inventory conservation, UI consumers, targeting, controller bindings, settings, full bags, display cleanup and persistence |
| M6 | Architect, groupcombo, droptrade and cross-module network authority | Charge/grant once, owner routing, pickup/drop consistency, host-synced settings and genuine client-delivery requirements |

M5 also inventories bufftips, chatlinks, deathrecap, laststats, colors, waygates,
goldworth, mmhmm, orbwarn, mapicons and autoaim. Shared item actions belong to L1;
M4 and M6 coordinate their courier/drop tests with M5. B1 is the first expansion
candidate: split release composition, generators/assets and archives/imports
when its inventory yields separate tasks. Split M5, S1 or a broad module lane
next if ready work exists. Extra reviewers attach to concrete risky patches.

Do not expand merely because slots are free. If native requests outgrow the next
two batches, shift workers toward reviewing results, offline checks and existing
fixes. More scenario drafts do not increase native throughput.

Dispatch is separate from message delivery. Before waiting for a reviewer or
worker, check the orchestration tool's actual agent state. A message queued to
an idle agent may not start a turn; explicitly resume that existing agent with
the concrete artifact paths and next action. Record the handoff in the tracker,
and use the returned task revision and attempt when the agent resumes. Do not
infer that review is running from a sent message or silence.

## Concurrency and source rules

Use this checkout as the sole runtime checkout. Worktree-local lock files do not
create independent machine capacity. Coordinate across every terminal/worktree,
respect the native locks, and never reset another owner's run.

| Operation | Scheduling rule |
| --- | --- |
| Source/oracle review and completed-evidence analysis | Parallel, read-only |
| New tests, scenarios and patch drafts | Parallel under distinct ignored task directories |
| Mocked or temporary-tree tests | Separate Python processes after auditing their writes |
| Checks reading repository/generated inputs | Parallel only while those inputs are stable |
| GameLab launch, fixture materialization and runtime relinking | Runtime owner only, one at a time |
| Actual generation/imports, setup fixes, builds and installed-source edits | Integrator/runtime coordination at an exclusive idle boundary |
| Git staging/commits and shared manifests | One owner, outside native queues |

Sync the environment once before workers; use `.venv/Scripts/python.exe` afterward
so simultaneous `uv run` calls do not sync it. Begin with at most four offline
test processes, adjusting from measured machine capacity. During native runs,
allow at most two light, audited processes and pause them if latency rises.
Builds and heavy scans wait for idle boundaries. Agent count and CPU concurrency
are separate limits.

During a native queue, freeze installed gameplay, harness, bots, scenarios, tools,
package inputs and each running case's consumed archives. All workers acknowledge the freeze before
the runtime owner starts. Draft only under
`gamelab/results/swarm/<campaign>/<task>/`; do not apply patches, regenerate files,
change the environment or commit until the owner releases the queue at clean
teardown. Completed result directories may be read; active results are provisional.
Do not run copied draft tools until their `__file__`-derived imports and output
paths have been audited or redirected to a complete temporary sandbox.

Pipeline evidence review with the next independent admitted case. The runtime
owner must first inspect the completed run's actual finality, teardown, isolation,
source/input stability and raw consumer predicates. A reviewer can then audit that
completed evidence while the owner runs the next self-contained case on the same
frozen inputs. The game still runs serially. Do not advance past an unresolved
prerequisite, refusal or dirty teardown; a valid consumer failure stops its
affected queue. Reviewers may record authorized evidence through task CAS while
the runtime owner retains launch/status authority. Checkpoint the next case and
remaining unrun cases so compaction cannot turn a completed trial into a retry.

Packed launches have an existing owner-controlled preflight build inside the
launcher, under its runtime lock. Keep that gate. Prepare and validate generated
assets at the prior idle boundary so this mandatory rebuild leaves source and
generated-input bytes unchanged. No independent build overlaps it. Hash the actual
archives produced for each case/mode after the rebuild; keep those output hashes
separate from frozen source/input hashes. Unexpected input drift stops the queue.
Scenario-owned restored writes, such as `reload-mark` and `pilot-revision`, need
their documented restoration audit and cannot authorize unrelated worker edits.

The existing batch fingerprint is `mods+gamelab+tools-v2`, not the whole project.
Record additional path/content hashes for `tests/`, `planner/`, package manifests,
project configuration and relevant ignored generated inputs/archives. Preserve
this supplementary manifest beside the native fingerprint; do not silently change
the meaning of historical fingerprints.

## Execution waves

### Establish the inventory and baseline

The coordinator records HEAD, dirty files, all tracked executable/data surfaces,
release membership, dependency edges, existing tests, scenario prerequisites and
historical gaps. Every tracked code surface gets an owner or an explicit
out-of-scope reason, including bench/local/developer code. Derive expected
settings and feature rows from current manifests/configuration.

The current `mod-settings-sweep` and `mod-settings-off` omit affixes, attrclick and
petrooms. Repair their coverage expectations before treating them as exhaustive;
modules without toggles need an explicit applicable contract. Historical inventory
files remain unchanged as history; create a separate campaign inventory.

The runtime owner reads doctor before setup changes. Resolve prerequisites through
the documented process, keep all isolation checks, preserve HoH1/save answers and
stop for actual unresolved build/save decisions. A running player game blocks
native work while independent read-only and sandbox work can continue.

```powershell
uv sync --dev
.venv/Scripts/python.exe -m gamelab doctor
.venv/Scripts/python.exe tools/qa_batch.py --fingerprint
.venv/Scripts/python.exe tools/qa_batch.py --label swarm-e001-smoke --dry-run null-payload mod-all
.venv/Scripts/python.exe tools/qa_batch.py --label swarm-e001-smoke null-payload mod-all
```

Use a unique label for each actual batch. Smoke proves setup and compile/load,
not module functionality. If setup requires mutators, finish them before freezing
and recording the epoch used for native claims.

### Run parallel source and offline verification

Each owner submits an explicit contract and targeted checks. Assign each existing
test once; avoid 24 overlapping full-suite runs. Audit temp roots, subprocesses,
import-time side effects and generated dependencies before admitting a shard.

Use boundary partitions and invariants rather than enumerating every possible
combination. Prioritize crashes/data loss/isolation, resource conservation and
authority, recent PR changes, historically untested identities, then lifecycle
and interactions. Targeted fault injection and generated input cases are useful
for parsers, saves and transactions. Do not add tests that merely copy the
implementation's constants or setters without checking a meaningful consumer.

For H1, cover zero/custom/maximum gold, empty/single/mixed/maximum rosters, level
and UTF-8 name boundaries, unavailable classes, duplicate identities, corrupt
profiles and failure at each transaction stage in a fake install. Do not form a
full Cartesian native matrix: choose representative native boundary cases after
cheap validation covers the partitions.

For P1, use a temporary data copy and free loopback port. Planner Save/Delete write
immediately. Verify CRUD/errors and browser behavior against the copy; preserve
authored records. The planner is Python plus inline JavaScript, with no existing
npm/TypeScript test pipeline.

### Reproduce and repair in source epochs

An epoch is a frozen set of source bytes and relevant generated inputs.

1. An owner reports a suspected defect with authoritative expected behavior,
   minimal reproduction, observed effect and negative control.
2. A reviewer distinguishes product defect, fixture/oracle defect, environment
   failure and ambiguous authored behavior. Balance decisions stay with their owner.
3. The owner drafts the smallest fix and a regression that detects the original
   failure. The reviewer checks that the assertion was not weakened to obtain green.
4. At a clean idle boundary, the integrator verifies base hashes, applies reviewed
   patches in dependency order and resolves shared files. Stale patches return to
   their owners. No unrelated cleanup is bundled into the repair.
5. Run relevant offline checks and required generation, record the next epoch,
   freeze again, then run compile/load before dependent gameplay tests.
6. Run the reproduction and affected neighbors. The evidence steward retains
   failure and repair trials and links the final-source result to the patch.

Only one integrator edits common module registration, `Common.as`, hooks, network
messages, inventory/UI overrides, settings/localization, GameLab commands,
fixtures/navigation, shared bots and generated manifests. Domain ownership does
not permit concurrent edits to these files.

Keep batches small: normally 3–8 related cases, with prerequisites before consumers.
Use measured case durations to keep integration boundaries practical. The runtime
owner runs a frozen batch while owners/reviewers analyze completed results and
prepare the next reviewed batch. Reuse fixtures only through existing validated
cache contracts; start fresh after source changes as required.

### Expand native behavior coverage

First establish reliable input/release, cursor projection, legal target geometry,
exact resources/cooldowns and observer/restoration contracts. Useful existing
candidates are `qa-firearms-input-sequence` and `qa-specs-crit-contract`. Known
unreliable setup cases remain a separate investigation queue, not a green suite.

Keep that broad expansion gate open when a prerequisite refuses. A separately
registered bounded diagnostic of an independent subsystem may proceed after
current load and applicable offline safety gates only when independent source
review traces its actual calls and confirms that it does not consume the refused
contract. Preserve the parent gate and its dependencies, failed trials and exact
forced-state scope. For example, direct buff activation and engine HUD-widget
hover can investigate bufftips without claiming that world-cursor projection or
native combat input works. Such a diagnostic does not close the broader UI,
gameplay or native-contract task.

The following are starting candidates to inspect, not predeclared passing cases:

| Priority family | Existing scenario candidates |
| --- | --- |
| Recent spec behavior | `plan-forgemaster-smoke`, `fix-forgemaster-channels`, `fix-specs-risen-speed`, `fix-specs-body-passthrough`, `fix-specs-risen-floors`, `plan-generosity-smoke`, `plan-generosity`, `plan-generosity-bosses`, `plan-generosity-farm`, `fix-pyrebrand-charge` |
| Previous combat repairs | `qa-specs-static-native`, `qa-specs-static-overlap`, `qa-specs-return`, `qa-specs-branding-native-combo`, `qa-firearms-magazine-crit`, `qa-firearms-hoarder-unequip`, `qa-firearms-orb-reload-explosive-aim`, `qa-firearms-burst-exact-amplitude` |
| HoH1 combat repairs | `qa-classes-shadow-strike`, `qa-classes-gladius-collision`, `qa-classes-riposte`, `qa-classes-caltrops-all-ranks`, `qa-classes-whirl-all-ranks`, `qa-classes-barbed-net-all-ranks` |
| Recent module/shared actions | `fix-item-actions-eat`, `fix-pets-courier`, `fix-weaponswap-pad`, `mod-attrclick`, `mod-affixes`, `qa-content-stash-families`, `qa-content-stash-neighbors` |

Fill the old gaps in Knives, Grappling Hook, Smoke, Pit Fighters, Beast, Pack
Leader, Hound, Ward, Crows and Pack, and refresh the rank/orb matrices from actual
current definitions. Test actual HP/status/healing/displacement/ammo/persistent
state, with costs, refusal/cancellation, wrong-owner or outside-range controls,
expiry and cleanup. A successful bind or forced-state setter supplies only its
own contract evidence.

For modules, cover positive completion as well as timeout: strongbox/abyss
rewards, fishing catches/traps, crop growth/harvest, seven legendary effects,
courier atomicity, summon shortfall restoration, map/campaign progression,
mercenary prestige/death and wave rewards. Give each feature applicable columns
for positive effect, refusal, boundary, off/on, transition/restart, standalone,
full stack, UI/acquisition and real co-op.

Select interactions from shared state and authority edges rather than all module
pairs. Start with inventory actions/stash/courier/drop; Firearms/weaponswap;
pets/petrooms/puzzles/summons/Forgemaster; town currencies/Luck/Generosity;
Architect/campaign/modes/run-start payment; and combat/recap/buff/UI cleanup.

Ordinary run evidence requires native progression, mandatory encounters, boss
reward, town return, death/abort where applicable and save/reload. Controlled
tests may establish separate mechanics while an ordinary driver is unfinished.
Do not use forced kills or transitions to claim ordinary completion.

The [deferred bundle](deferred/README.md) is a source of candidate repairs, not an
installer to run wholesale. Reconcile a selected draft with current code, review
it and pass its prerequisite/consumer checks before crediting it.

### Verify release artifacts and the final candidate

B1 prepares builds at an idle boundary. A normal build writes generated assets
and potentially committed pet script data under `mods/`, as well as archives under
`dist/`. Preserve a manifest for each build mode
before another mode overwrites the same archive names. Check decoded entries,
library closure/stamps, conflicts, imports, personal/local/dev-content exclusions,
resource references, icons and language keys. Normal, Workshop and local/beta
composition are separate test partitions; no live Workshop publishing is included.

Run each package's packed load gate, `pkg-all`, selected high-risk pairings and
`pkg-all-every` when prerequisites hold. Existing pairings include
`pkg-pair-qol-keys`, `pkg-pair-town-dungeon` and `pkg-pair-firearms-classes`.
Use affected `pkgfeat` counterparts to check fixed consumers inside real archives.
`pkg-mismatch` exercises synthetic library-stamp mismatch modules; inspect its
expected refusal before scheduling it.
Archive integrity and loose-module passes do not establish packed runtime effects.

The current batch helper accepts only top-level stems. Nested `it/...` and
`pkgfeat/...` paths require the runtime owner's direct command with separately
retained before/after fingerprints and the same verdict audit. `pkgfeat` exists
now; `it/...` is supported syntax for future cases, not a current suite directory:

```powershell
.venv/Scripts/python.exe tools/qa_batch.py --fingerprint
.venv/Scripts/python.exe -m gamelab run pkgfeat/pf-fix-firearms-snipe --mode lab
.venv/Scripts/python.exe tools/qa_batch.py --fingerprint
```

After the last repair, freeze a final candidate. Run one consolidated offline
suite, all selected required native regressions, changed-feature consumers and
affected packed checks on that candidate. Library/harness changes widen the
affected set. Do not label earlier-epoch results as a final-source full-suite pass.
Record unrun historical candidates and remaining feature gaps explicitly.

## Offline command inventory

These are source-inspected starting commands, not results. Use the pinned project
environment. The coordinator partitions them without overlap and checks missing
asset prerequisites. Final consolidation replaces repeated lane discovery runs.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_run.py tests/test_play_profile.py tests/test_save_builder.py tests/test_qa_batch.py tests/test_build_update.py tests/test_make_forgemaster_risen.py -q
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe tools/compiler_selftest.py
.venv/Scripts/python.exe tools/saves_selftest.py
.venv/Scripts/python.exe tools/doctor_selftest.py

.venv/Scripts/python.exe tools/build.py --check
.venv/Scripts/python.exe tools/workshop.py --check
.venv/Scripts/python.exe tools/list_verbs.py --check
.venv/Scripts/python.exe tools/generate/make_config.py --check
.venv/Scripts/python.exe tools/generate/make_herbs.py --check
.venv/Scripts/python.exe tools/generate/make_hwp_traps.py --check
.venv/Scripts/python.exe tools/generate/make_package_scenarios.py --check
.venv/Scripts/python.exe tools/generate/make_specs_classes.py --check
.venv/Scripts/python.exe tools/generate/make_seeded_generators.py --check
.venv/Scripts/python.exe tools/generate/make_forgemaster_risen.py --check
.venv/Scripts/python.exe tools/generate/make_pet_dyes.py --verify
```

Every test lives in `tests/` (the repo reorganisation moved `tools/test_*.py` and
`gamelab/tests/` there); the first command is a focused shard, not exhaustive
discovery. The restart/resource tests are `tests/test_runner_restart.py` and
`tests/test_res_snapshot.py`.

Save/doctor selftests use redirected sandbox trees under `C:\tmp\claude` and may
need permissions outside this worktree. Audit that redirection first and honor
sandbox review. Resource snapshot tests use unique ignored fixture-cache trees.
Missing dumps/imports or junction permissions can cause skips: count and explain
them. Actual `tools/run.py`, including `--no-launch`, can deploy/create a real
profile; verify orchestration with mocks and native preparation through lab-only
scenarios/export instead. Test publisher decisions with mocks, without Steam
publishing or upload-kit side effects.

Regenerate changed verbs with `tools/list_verbs.py`, then use `--check`. Generator
writes and release preparation occur before the relevant source freeze; packed
launches retain their mandatory preflight rebuild as described above. Pet dyes
use `--verify` for a read-only check: that tool's `--check` still writes, including
potentially committed generated script data. Use
`git diff --check` for the working patch and `git diff --cached --check` if staged.

## Task and evidence contract

Store local drafts and raw work products under
`gamelab/results/swarm/<campaign>/<task>/`. Each task carries:

- ID, owner and independent reviewer; owned paths; shared-file dependencies;
  allowed operations and whether native execution is required.
- Baseline commit, expected touched-file hashes, feature contract/source anchor,
  prerequisites, test command/scenario, controls and predicted observations.
- Reproduction, proposed patch, meaningful regression, affected neighbors,
  bounded trial policy, observed results and unresolved limitations.

Use task states `queued`, `reviewing`, `reproduced`, `harness-blocked`,
`fix-drafted`, `reviewed`, `integrated`, `verified` and `deferred`. A source review
alone does not put a behavior in `verified`. Each finding records severity,
product/harness/environment/design classification and the final disposition.

The authoritative task ledger is `docs/qa/swarm/state.json`, updated atomically
through `tools/qa_swarm.py`. Metadata-only tracker writes may continue during a
native freeze; installed inputs and Git staging/commits remain frozen. The
evidence steward maintains portable findings/coverage summaries under
`docs/generated/` at integration boundaries. Proposed names are
`qa_swarm_manifest.json`, `qa_swarm_findings.json` and `qa_swarm_coverage.json`.
These files start with actual inventory and observations during execution;
planned cases are never prefilled as passes. Keep raw game-derived or personal
artifacts ignored and write compact portable evidence summaries.

Every native claim records pinned build, run ID, source commit and before/after
fingerprints, expected-source anchor, actual consumer observations, command/exit,
assertions, error, partial/drift flags and teardown. Inspect `run.json` first,
then final `inner.json`, relevant `bot-results.jsonl` rows and logs. Inspect actual
screenshots before describing them. Require exit 0, outer PASS, no failed
assertions/error, no partial output/build drift and clean teardown.

Track coverage by behavior and evidence scope: source reviewed, mocked/offline,
load, controlled native effect, ordinary lifecycle, visual/UI, packed runtime and
real co-op. Keep covered, failed, blocked, skipped and deferred counts separate.
Python line/branch coverage may help find unexecuted host code, but it does not
measure AngelScript/native behavior; do not use it as a whole-project percentage.

Use bounded repeated transitions and save/reload cycles to check leaks, duplicate
handlers/grants and accumulating state. Record baseline and post-fix runtime or
frame observations under the same build/source/load when investigating latency;
avoid timing assertions made unstable by background workers. The outstanding
multiplayer stutter investigation needs its own reproducible setup and evidence,
including real participants where needed.

## Failure handling and stopping rules

Preserve every failed/flaky attempt. Default to one initial trial and one trial
after a documented relevant change. Repeated unchanged setup failures are
deferred with their cause; no open-ended retries. Randomized/probability tests
declare seeds, sample count, tolerance and uncertainty before execution.

Exit 1 needs failure analysis. Exits 2/3/4/5/6 mean preflight/build mismatch/
lock or dirty state/INVALID/TIMEOUT: diagnose the cause and stop the dependent
queue. No automatic reset, re-pin, drift acceptance, assertion weakening or
fallback direct launch. A clean harness failure can leave unrelated offline work
running. Stop requests use the documented batch stop file between cases.

A suspected real-save/config/install modification stops native work immediately;
preserve evidence and report it. Never restore player saves as a test fix. Keep
all real input/focus changes prohibited. A second local worktree or synthetic
peer is not a real co-op test. Client delivery, ownership, shared buffs and
join/leave behavior need a second real participant on another machine; list
those gates until a supported setup exists.

## Completion and handoff

A lane completes when its current inventory has a disposition for every behavior,
selected checks have source-pinned evidence, confirmed repairs pass their
reproduction and affected neighbors, and independent review accepts its oracle
and claims. Record unresolved mechanics, missing assets, ordinary-run gaps,
manual/visual work and real-co-op requirements plainly.

The campaign completes when every lane meets that standard, the agreed final
suite and release checks pass on the final candidate, and the evidence audit
reconciles all failures/skips/deferrals. Completion does not mean all conceivable
states are proven. Any confirmed severe unfixed defect keeps the candidate from
being described as ready. Lower-priority or externally blocked work remains a
named handoff item with its reproduction and next prerequisite.

Update README and RE_NOTES with the latest checkpoint after each work session.
Deliver the patch set, exact validation summary, archive manifests where relevant,
coverage by scope and remaining decisions. Do not merge PR #83, publish packages,
deploy to the player's install or modify real profiles as part of this campaign.
