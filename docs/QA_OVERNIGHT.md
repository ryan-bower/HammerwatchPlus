# Overnight QA and repair ledger

> Current status: **paused at the user-requested PR boundary; full sweep incomplete**. Historical tables below are superseded by `docs/generated/qa_pr_checkpoint.json` and the final wrap entry.

## Run contract

- Started: 2026-10-22 00:20:52 America/Chicago (05:20:52 UTC).
- Original overnight deadline: 2026-10-22 10:20:52 America/Chicago (15:20:52 UTC).
- Current scope: user resumed the FULL sweep with no time limit on 2026-10-22. The original deadline is historical; per-scenario timeouts and all isolation/refusal gates still apply.
- Original final-hour reservation: historical. The resumed sweep has no wall-clock cutoff; final regression follows completion of repairs.
- Goal: the full user attachment `pasted-text-1.txt` from this thread. This ledger
  checkpoints coverage; time exhaustion never means the goal is verified complete.
- Runtime owner: root, one GameLab run at a time, always `--mode lab` using
  `.venv/Scripts/python.exe`. Approved access outside the sandbox is needed for
  Windows process visibility and isolated game launches. No real input or focus changes.
- Existing setup edits are the starting worktree: README.md, docs/RE_NOTES.md,
  gamelab/doctor.py, tools/bootstrap.py, tools/gamepaths.py, tools/compiler_selftest.py.
  Preserve these and all unrelated user edits.
- Starting HEAD: `4ed9c7a55db06e14314b8c895c147f9d90ccb052` (plus the setup edits above).
- Parallel ownership: audit_verification = specs and spec bots/scenarios;
  audit_scope = classes and class bots/scenarios; firearms_qa = firearms and its
  bots/scenarios. Root owns shared harness/core, runtime, other modules and this ledger.
- Expected behavior comes from current built data, planner records and recent owner
  decisions. Newer explicit owner decisions override stale checklists. Do not redesign
  balance or implement parked content.

## Coverage status and evidence rules

Runtime states: PASS, FAIL, BLOCKED, UNTESTED, N/A. Source review is recorded separately
and cannot substitute for runtime effects. Each case must identify feature/class,
skill/orb/rank, expected behavior/source, setup, actual result, run ID and code revision
or working-tree fingerprint. Acknowledgements, binding values and debug counters alone
do not prove effects. God-mode and forced-state measurements do not prove normal play.
Retain all flaky outcomes and bounded trial counts. Restart after script changes.

## Prioritized queue

1. Inventory actual module manifests, built skills/orbs and scenario assertions; run
   doctor and the corrected exact31-module full-stack smoke including specs.
2. Baseline existing specs, Firearms and HoH1 runtime scenarios, then all-module breadth.
3. Extend every built fourth-spec skill/orb/rank and priority legal combination; focus
   Tailwind Catch flakiness, Static Charge first crit, Lightning Rod target count/radius,
   actual action speed, targeting, resources and stack expiry.
4. Firearms base kit, all four specs/orbs, guns, ammo/reload/cancellation and gadgets.
5. Three HoH1 ports: all base/mastery skills and ranks, ordinary HoH2 fights, floors,
   bosses, rewards, town return, death, persistence and summons. Keep classes hidden.
6. Every content module independently with dependencies and together: effects, UI,
   settings, persistence, failure paths and interactions; fix reproducible bugs and
   verify each reproduction plus affected neighbors.
7. Final code: build/package checks, complete mod-all stack, affected regressions,
   diff review, README and RE_NOTES updates, coverage counts and next commands.

## Explicit scope boundaries

- N/A: unbuilt Paladin/Priest fourth specs, Echoes fifth specs and six planner-only
  original HoH1 classes; do not restore removed fake HoH1 masteries.
- HoH1 ports have no built orb data; do not invent it.
- BLOCKED pending appropriate evidence: real co-op/second-client behavior, audible
  sound quality (GameLab is muted), unavailable conditional/DLC assets. Keep exact
  prerequisites and source-only findings distinct from verified play.

## Runtime batches

| Area | Current scoped evidence | Remaining limits |
| --- | --- | --- |
| Doctor and full31 stack | Native-visibility final doctor is green. Full31 mod-all 100827 passes. All14 required repaired-behavior/control scopes pass at their recorded fingerprints. Later Probe E68E adds only read-only dead-player mana precision; full31 compile and all four changed modules' standalone dependency/load checks pass afterward. | Regression scope completion is separate from the incomplete overnight goal. Final14 metadata identifies the later QA-only change and unchanged relevant production sources; do not claim one common fingerprint for all14. |
| Six built fourth specs |60 skill-rank rows:55 scopedPASS,5 LivingMana PARTIAL.65 orb-quality rows:47 scopedPASS,3PARTIAL,11UNTESTED,4allyBLOCKED. Fresh Pyrebrand/Essence, Font/Conduit, Provisions and Feedback native effects pass. | Ward2 qualities prove whole-HP DR/expiry but not settled exact intensity; native refresh averages old/new intensity. Barrier1 proves protection/drain/expiry death but its precise dead mana assertion remains unverified. Branding/Gale geometry fails before effects. Other cadence, combination, lifecycle and co-op gaps remain. |
| Firearms |60 skill-rank rows:10 scopedPASS,10PARTIAL,40UNTESTED.75 orb-quality rows:42 scopedPASS,32UNTESTED,1co-opBLOCKED. Final Shotgun 085158, Grenades 085345, Missiles 090522, magazine 093247 and Hoarder 093432 pass; Elements 095401 adds five base ranks and twelve weighted qualities, with native-function scope explicit. Arm 100414 and standalone 100507 pass. | Frag's cooling-refusal test waited past expiry; Focus's additive-chance oracle ignored native complementary-probability stacking. Both sets of five remainPARTIAL with original suiteFAILs retained. Full ranks/affixes/combinations and orb-specific natural damage/frequency remain incomplete. |
| Three hidden HoH1 ports | Four of39 skills and14 of191 positive-rank slots have scopedPASS: Shadow/Riposte ranks1/5, plus Bloodlust/Judgement all5 via controlled real kill hooks 095729. Final Shadow 093637/Riposte 093528 pass. All3 ordinary full31 cases complete two real floor transitions. | All3 full runs remainFAIL before final boss: native floor3 encounter/unlock objective is absent from driver. Boss/reward/natural-town/reward-persistence,9mastery saves and35 other skills remain unverified. Controlled kill hooks do not prove ordinary attack kills. |
| Other content modules | All31 standalone dependency/load cases pass. UI/settings and two-tab stash save/restart 095605, Architect picker/pricing 100154, Strongbox/Abyss controlled no-reward timeouts 100238/100326 and town object rebuilding 100615 pass their declared scopes. | Individual functional/UI/settings/persistence/failure/interaction axes remain incomplete. The module inventory records narrow evidence and partial axes; successful event rewards, full UI/tooltips and real co-op are unverified. |

## Findings and fixes

- Confirmed coverage gap: mod-all omitted specs from its 30-module list. Added specs;
  fresh manifest comparison is exactly 31/31 and corrected mod-all passed. This is a test-gate repair,
  not evidence of ability/orb correctness.

## Historical checkpoint (09:10 Central; completed evidence, not goal completion)

Eight scoped gameplay repairs have passing reproductions at their recorded working-tree
fingerprints: Shadow Strike, Riposte, per-hand magazine crit, Hoarder HUD, Static
first-crit attribution, returning arrows, Stash family ordering, and Dragon's Breath
owned-area replacement. Dragon 085158 preserves all12 actual authored ground areas,
checks native initialized TTL/countdown/owner/producer-exemption state and actual
HP effects. The native producer exemption preserves ownership, binds and authored
expiry. Grenades 085345 also passes all9 qualities after stronger read-only native
TTL observation; its observer/oracle corrections are not a ninth gameplay repair.
OriginalFAILs, fixture/oracle failures, bounded flaky trials and historicalINVALIDs
remain retained. These separate fingerprints do not establish final-code regression.

| Built spec | Skill-rank rows (10 each) | Orb-quality rows | Observed scope and remaining gaps |
| --- | --- | --- | --- |
| Deadeye |10 scopedPASS|6 scopedPASS;4UNTESTED|065727: actual full outgoing+return damage at all5 ranks, Boomerang2/StormArrow3 combined effects,25 real kills earn5 stacks and live speed factors/expiry.044257:3ordinary+3close6x catches. Gale/Ward original setup/precision failures are retained; corrected normal-walk/fan probes and native intensity readback await retest. |
| Winddancer |10 scopedPASS|9 scopedPASS;1allyBLOCKED|050230: Gale all5 native lifetime/evasion. SecondWind all5 actual heals/lock/recovery.031218: Lasting3/Tailwind3/Breeze3 scoped effects/expiry. SharedBreath true ally remainsBLOCKED; full cast/attack cadence is unproved. |
| Arcane |5 scopedPASS;5PARTIAL|3 scopedPASS;4UNTESTED;3allyBLOCKED|065457: Blink5 damage/distance/radius and FarStep3 distance. LivingMana conversion/recovery/mirror is observed; exact rank regen coefficients remainPARTIAL. Barrier setup failed; Feedback bank/cap/multiplier state passed but its actual cast/damage measurement did not. Corrected native-input/fresh-target and normal-walk setup are pending. Conduit3 true alliesBLOCKED. |
| Branding |10UNTESTED|2 scopedPASS;9UNTESTED|083312: both Released qualities,10 native recast-claw kill controls/trials, actual ordinary/elite/boss-tag payouts3/6, cap and Combustion spend-before-payout. ControlledHP1 is not a full boss fight. Original rank/rate sweeps retain heterogeneous-target/Fire-pool/brand-expiry measurement failures; new source-predicted homogeneous-target and ice-wand native-input measurements await retest. Wide-orb original failure attempted zero qualities; bounded ordinary walking preserves the full footprint for its retest. |
| Bannerlord |10 scopedPASS|9 scopedPASS;3UNTESTED|040543/040406: Standard selfDR and Righteous duration/selfmove/main-speed. Crest3 actual target vulnerability/attack damage, Martyr3 bearerDR-loss, Drum3 native tier/cap/expiry pass 084110/084439/084314. Stronger Martyr allyDR remainsBLOCKED; Drum actual enemy outgoing damage isUNTESTED. Provisions original counts/CD oracle failed; natural fixture expiry and source12000ms CD-delta correction awaits retest. |
| Aerotheurge |10 scopedPASS|8 scopedPASS;4UNTESTED|080551: TT/Static all5 actual rank damage, real5-cast charge/release and Rod3 target counts/radii.081952: FocalTWO qualities with3trials each plus3controls; ThunderclapONE quality with3trials.033415: Lingering2 native lifetime/HP. Font/Conduit each have2qualities plus zero-orb controls; corrected native cast/payment/timeline observation awaits retest. Generic delayed non-TT critical attribution remains unresolved. |

Totals are45 scopedPASS+5PARTIAL+10UNTESTED skill-rank rows and37 scopedPASS+
24UNTESTED+4allyBLOCKED orb-quality rows. A scopedPASS means the stated native
measurement passed, not that every mechanic or quality-specific ally value did.
The12skills/27orbs and exact per-row limits are in
`docs/generated/qa_specs_inventory.json`. Source review, debug acknowledgements and
prepared cases never count as runtime effects. No built HoH1 orb data exists.

Native cast observation now retains actual input, targetHP, first-impact, later mana
payment/cooldown and bounded cast-timeline events. Earlier SC release can precede the
spell cost; that setup timing is not an ability failure. Native Damage uses whole-HP
rounding, and Fire/Poison create independently scheduled bonus pools. Exact caster
fields and fully settled native HP replace invalid finite-time damage ratios. These
measurement repairs preserve original failures and require their own fresh runtime.

Firearms Missile's current retest and the reviewed corrected Specs cases remain
UNTESTED until terminal raw evidence is reconciled. Normal-walk fine-grid/body paths,
coarse frontier guidance and final fine/native ray recertification do not teleport
or relax the requested footprints. Final regression metadata plans the original11
cases plus Dragon/Shotgun, Grenades and Missiles (14required scopes); no planned row
is marked final-codePASS merely because an earlier fingerprint passed. Optional
plan-specs remains a separate budget-dependent integration neighbor.

The three ordinary HoH1 full-runFAILs retain real two-floor transitions. Keep3 needs
the native Bandit encounter objective before unlock_exit; the driver omits that step.
This is an ordinary-driver coverage gap, not a class gameplay bug verdict. Natural
boss/reward/return completion remains unverified. Trident 064644 is23/24 actualHP hits.
All31 standalone loads do not prove each module's functional/persistence/UI effects.

Root remains the sole serial runtime owner. Do not infer completion from this
checkpoint, queued scenarios, packaging, source review or time exhaustion. Final
regression/handoff begins09:20:52 Central; the deadline remains10:20:52.

## Historical checkpoint (04:55 Central)

- Valid scoped fixes: Shadow 030624, Riposte 021550, Firearms magazine 030332,
  Hoarder 030527, Thunder-Orb-to-MagicMissile first-crit attribution 042809, and
  returning arrows 044257. Original FAILs, bounded trials and042925INVALID remain.
- Original corrected Static 042233 failed ONLY all3 old-orb bonus assertions; native
  setup/crit/HP/retention passed. Original same-TT overlap 042350 failed ONLY all3
  independent-first-crit bonuses; both actual casts and each orb's real crits passed.
  Installed shared per-actual-TT-cast tokens, preserving native damage/CriticalHit.
  Delayed non-TT projectile attribution remains an explicit unverified gap.
- Return repair preserves collision damage, handles duplicate wall callbacks and
  oblique reflection, and tests only true returning movement for swept catches.
  Valid 044257 passes all3 ordinary +all3 coarse6x stress trials, outgoing and return
  damage and actual3 Tailwind stacks.042925 had the same behavioral observations
  but is INVALID due installres/editor metadata and earns no validPASS credit.
- Investigated that isolation failure with no game/editor process remaining and
  five matching read-only directory/content snapshots. Historical before/after
  metadata was not recorded, so its cause remains unknown. Added exact pre/post
  isolation-res.json diagnostics, preserving the same equality assertion. One
  bounded diagnostic repeat 044257 passed with identical full res dictionaries;
  later runs retain all original config/save/res/focus/build/lock gates.
- Native Wizard first-impact helper installed and143verbs generated; source-reviewed
 1x Wizard ranks replace fractional-timescale console polling. Compile gate running.
- Broad-m35344 is the sole live serial runtime. Its56-case ordered queue is retained
  in gamelab/results/qa-20261022-broad-m-queue.json; stop on any refusal/runtime error/
  INVALID/unclean teardown or failed modall/crit/overlap/Gale prerequisite. All installed
  AS and queued Python/JSON are frozen. Disjoint new cases may be prepared. Existing
  source hashes checkpointed in qa-20261022-broad-m-frozen-sources.json.
- New Branding tests cover all5 real claw/store ranks,9 independent orb ranks,
  actual Empowerment HP damage, and max legal four-orb/two-transferred-brand shared
  Essence effects. Native Essence-rate observers check all5 ranks and doubled gains
  at actual wand hit timestamps; finer unobserved timing and Released Essence elite/
  boss rank payouts remain separate. New tests are UNTESTED until fresh runtime.
- Remaining priority work is still broad: full Firearms arsenal/ranks/orbs/transitions,
  HoH1 ordinary matched-level boss/reward/town/death/save runs, missing HoH1 effects,
  and module functional/UI/settings/persistence/failure interactions. Final hour starts
 09:20:52; deadline10:20:52. Time exhaustion will not be called full completion.

## Historical checkpoint (03:55 Central)

- Breadth-g session4126 is terminal, exit1, all36 teardowns clean: 34PASS and
  twoFAIL (Static/Return). Full mod-all 032859 and global-zero crit contract 032933
  pass. All31 individual modules pass; do not infer full module effect coverage.
- Static 033017 retains valid native phase events in all three trials: TT first
  crit grants2 stacks and actual11HP target damage; later TT crits stay2. After
  actual noncritical MagicMissile input, old TT crits raise stacks to4 instead
  of3. Its final aggregate exceeds the native15000-character print limit, so
  source-reviewed gameplay and bounded observation repairs are being staged.
- Return 033153 repeats ordinary2/3 catches and close6x1/3 outcomes (earlier 024139 close trials were0/3; retain both runs).
  Tracks identify an outer fan arrow terminating at its first wall before the
 600ms turn. The other two arrows return, and the center deals both27HP hits.
  Diagnose native duplicate-wall-callback ordering before changing collision code.
- Lingering Tempest 033415 passes actual target HP/lifetime observations at
  no-orb/rank1/rank2. Wind rank 030837 passed all five Second Wind heal/lockout/
  recovery observations; Gale failed invalid ready==0 and Sidestep setup assumptions.
  Corrected test awaits a fresh result; no Gale gameplay change was made.
- Four scoped gameplay repairs now have passing reproductions: Shadow Strike,
  Riposte, per-hand magazine crit and Hoarder HUD. Their earlier FAILs remain.
- Normalized54 legacy scenarios whose old29-module stack omitted specs and valuables
  to the complete31-module manifest set, preserving steps and assertions. Fingerprint
  scope since contract-d is mods+gamelab+tools-v2; disjoint new test files can change
  aggregate hashes while installed gameplay and queued bots are frozen.
- Pilot-h session18141 runs corrected Wind ranks, ordinary Thief integration and
  magazine edges serially. All installed AS is frozen until its terminal boundary.
- Added explicit native resume choice/readback support to restart, preserving all
  recipe probes, exact enabled-mod, profile/mute and launcher isolation gates.
  Structured selection is retained. Unit and native resume verification pending.

## Historical checkpoint (02:30 Central)

- repair-c session 79996 is terminal; all ten runs have clean teardown and isolation.
  The exact outcomes and pre/post source fingerprints are retained in
  `gamelab/results/qa-20261022-repair-c.jsonl`. New disjoint test files changed the
  aggregate fingerprint during some runs; queued test/gameplay sources were frozen.
- VERIFIED Riposte repair: `20261022-021550-qa-classes-riposte-lab` passes all 18
  rank 0/1/5 x incoming melee/ranged/spell x damage 2/5 observations. Only melee
  returns fixed physical 10/50; normalized-to-HP readback retains the <0.2 HP oracle.
  Neighbor `20261022-022350-plan-classesb-a-lab` also passes.
- Confirmed Firearms gameplay FAILs on original source, valid common ilvl-1 guns:
  `20261022-021701-qa-firearms-magazine-crit-lab`: solo 14/15 adds +0.28 crit
  damage, dual 28/30 adds +0.56 instead of the same +0.28 per gun. Actual shots
  damage the target and live gun skills/positive clip are verified.
  `20261022-021848-qa-firearms-hoarder-unequip-lab`: switching to flamer removes
  GL, but shown charges remain 2 with bank 1; re-equipping GL preserves the bank.
  Focused Firearms edits were released only after Firearms-enabled neighbors ended.
- Shadow Strike `021514` fails its open-floor prerequisite before any damage/stun
  observation. Candidate landing-target repair remains UNTESTED. Trident `021944`
  retains all 12 trials: fresh-input hits 2/3, settled input 350/500ms and direct
  activation all 0/3 against frozen brutes. ClassA `022117` passes its Trident check
  but hound follow fails (player walked 97px, summon moved 8px, final gap 95px).
  Diagnose native follow threshold/path and frozen target behavior before fixes.
- Strongbox `022608` and Abyss `022636` timeout cases both fail the open-floor
  prerequisite. Neither proves an expiry defect; replace the fixture navigation
  with a verified connected lane without changing the timeout/no-reward oracle.
- Next: 1x crit-helper contract, corrected geometry, bounded Return/Static checks,
  all 31 standalone module baselines, rank/orb suites and ordinary HoH1 integration.
  The final-hour boundary remains 09:20:52 Central. Slow-console malformed command
  evidence is a transport failure; no shared console retry/timing change is applied.
- Starting with contract-d, fingerprints use `mods+gamelab+tools-v2` and include
  shared GameLab Python code. Earlier hashes cover mods, bots, scenarios and tools;
  do not compare hashes across these two scopes as if the inputs were identical.

## Baseline checkpoint

- Runtime inventories: docs/generated/qa_specs_inventory.json (12 skills / 60 skill-rank
  rows, 27 orbs / 65 orb-rank rows); qa_classes_inventory.json (39 effective skills,
  three classes / nine masteries); qa_firearms_inventory.json (12 skills / 60 ranks,
  33 orbs / 75 ranks, 15 visible guns plus six hidden hand twins). These are coverage
  inventories with source expectations, not evidence that each case has passed.
- Existing gameplay sources remain unchanged during the original-code baseline. New
  QA-only files and the isolated Branding bot repair can change the aggregate source
  fingerprint; each journal records pre/post fingerprints. Do not mistake these for
  gameplay changes or combine passes from different code into a final-code claim.
- Baseline session 65278 is terminal: 12 cases, 10 PASS and two FAIL; all nine Firearms
  cases passed. Repro-a session 32943 and repro-b session 64857 are also terminal with
  clean teardown. There is no authorized reason to reset an active lock.
- Next: class owner applies the confirmed Shadow Strike and Riposte repairs plus the
  read-only actor stack/HP probe; root adds precise same-frame attacker HP units.
  Recompile, rerun both focused regressions and class neighbors, rerun corrected
  Firearms fixtures, then Static Charge, rank suites, ordinary integration and module
  breadth. Return transport failure must be diagnosed before another bounded run.
- Current goal turn: progress (inventories, focused reproductions, helpers, scheduling
  error gate and timeout scenarios), with verified waits on the named live sessions.
  Goal remains active; final-hour boundary and full scope are unchanged.

## Reproduction interpretation (01:55 Central checkpoint)

- Confirmed gameplay FAIL: Shadow Strike, `20261022-014720-qa-classes-shadow-strike-lab`.
  Ranks 1 and 5 activate and move 59.5 px; the target ends 12.34 px away, but its HP
  stays 1.0 and four landing samples show no stun. The existing preview radius is 40.
  Minimal data repair is queued: native Explode supplies per-enemy targets to the
  existing landing damage/stun effects. No new radius or damage design is required.
- Confirmed gameplay FAIL: Riposte, `20261022-014811-qa-classes-riposte-lab`. All 18
  controlled same-frame observations are retained. Rank 0 reflects nothing. At rank 1,
  incoming melee damage 2/5 reflects about 20/50 instead of flat 10; ranged and spell
  hits also reflect. Rank 5 reflects about 100/250 instead of flat 50. Native AddThorns
  provides the intended fixed physical return on melee only; data repair is queued.
  Fractional JSON health rounding is a separate measurement limitation: added HP-unit
  readbacks preserve the original <0.2-HP assertion without widening it.
- Fixture FAIL, gameplay unverified: magazine crit `20261022-014454` has clip maximum
  zero and no actual damage; Hoarder `20261022-014633` never removes the GL skill after
  a refused gear swap. Requirements override was reset on floor load while its cvar
  remained set. New bots must equip in the proper context, retain replies and verify
  live attacks/positive clip before any crit/HUD assertion. Firearms source is unchanged.
- Fixture FAIL, cause still unresolved: Trident diagnostic `20261022-014921` confirms
  loaded attack and 22 main-hand physical damage, but finds no 64px open floor within
  its initial search and executes no hit trials. Preserve this outcome; navigate to a
  verified attack lane before attributing the original classA miss to gameplay.
- Runtime/transport FAIL: return regression `20261022-014953` loses the reply to
  `gl c78 timescale 1` and exits cleanly. Inspect retained logs/telemetry/screenshots;
  do not label the 16x stress failure a catch defect or repeat unchanged setup blindly.
  Static Charge was not started because the serial error gate stopped the queue.
- Harness setup FAILs only: repro-a runs `20261022-013353`, `013514`, `013634`, `013754`
  fail before gameplay because the new crit helper called ModifySkills on ModifierList.
  The correct native receiver is record.modifiers (Player.as:1024). Corrected full-stack
  load `20261022-014418-mod-all-lab` PASS; the helper's functional override/restore cycle
  and actual crit behavior remain untested until qa-specs-static. All failed artifacts
  remain. Two temporarily held scenario JSONs were restored after the queue stopped;
  no game process was killed or active lock reset. The serial driver now stops on any
  run error and supports a per-batch .stop request checked between cases.
- New root-owned qa-strongbox-timeout / qa-abyss-timeout scenarios are syntax/JSON
  checked, UNTESTED. They measure actual event disappearance, living pack members,
  scene-clock duration and no new loot in standalone dependency sets. Accelerated
  clocks/god/cull make them controlled failure-path measurements, not ordinary play.

- Runtime batch baseline: **FAIL** plan-specs, run `20261022-003808-plan-specs-lab`, 472.6 s, source SHA256 `54e931c158e5f5c0bca4be1813a56a196972030fd7b67205c93bb56f59cc35ee`; 17 assertions, 1 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **FAIL** plan-classesa, run `20261022-004605-plan-classesa-lab`, 155.7 s, source SHA256 `f61c2e5f4c6b5e6ddcc1b40ded4811b620c893efe12a7335b684c61d5ed69082`; 14 assertions, 1 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-classesb-a, run `20261022-004840-plan-classesb-a-lab`, 143.7 s, source SHA256 `8013eaaaae042c6baead6705ac090540419803b3e948e89c84f547b69a718081`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-a, run `20261022-005105-plan-firearms-a-lab`, 139.8 s, source SHA256 `68b149186b641504dc5f8ce21b3a0bb5d6d16a6df5637d01d62e6389243d1ed9`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-b, run `20261022-005325-plan-firearms-b-lab`, 234.9 s, source SHA256 `71e53163cc974e659d618c5019cc3ea165e1d4284b9eb989f2faa59169b8fe05`; 15 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-orbs, run `20261022-005720-plan-firearms-orbs-lab`, 171.3 s, source SHA256 `ba52e691b5a4ef09a834957f9803e71bee5cd7d8cede7a514d1f99b130abdf40`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-orbs2, run `20261022-010012-plan-firearms-orbs2-lab`, 330.2 s, source SHA256 `a2f58468aeee06bddb318c6fb5bd9474b6049c8519a2d85eeee187cf6e431d21`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-guns, run `20261022-010542-plan-firearms-guns-lab`, 85.5 s, source SHA256 `3b839834dc261966541a61a2dfe1e0782fe5563a6256eff56c24ee08f894010b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-cannon, run `20261022-010708-plan-firearms-cannon-lab`, 130.6 s, source SHA256 `8913f94d0717c59d680268c287de7aedb09dc174890c00cd668430cebb799035`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-arm, run `20261022-010919-plan-firearms-arm-lab`, 54.7 s, source SHA256 `006ada47056e90d93f5f6ff8d1489f5f99e98c9e76a84ee3a34afebc21987a46`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-firearms-reload-cut, run `20261022-011014-plan-firearms-reload-cut-lab`, 141.1 s, source SHA256 `006ada47056e90d93f5f6ff8d1489f5f99e98c9e76a84ee3a34afebc21987a46`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch baseline: **PASS** plan-t14, run `20261022-011235-plan-t14-lab`, 95.5 s, source SHA256 `c2522e373c0b0793183265d053e73ece4ddfcfa487ebb138e31620e51453c47d`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-baseline.jsonl`.

- Runtime batch repro-a: **FAIL** mod-all, run `20261022-013353-mod-all-lab`, 81.3 s, source SHA256 `ff5a065d16fb6332820c7f6aa2ed8da63fdc1d93fbbc5cab3c295b7c2defa2d7`; 7 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repro-a.jsonl`.

- Runtime batch repro-a: **FAIL** qa-firearms-magazine-crit, run `20261022-013514-qa-firearms-magazine-crit-lab`, 79.6 s, source SHA256 `5cc4d2a5b69713f88dc17250a6427665b133bd87787671ea9096a7ae601f55e1`; 7 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repro-a.jsonl`.

- Runtime batch repro-a: **FAIL** qa-firearms-hoarder-unequip, run `20261022-013634-qa-firearms-hoarder-unequip-lab`, 79.2 s, source SHA256 `d8468239a24c1561419674be720dd9ff71d538a2e857ff43db0cd9f8ab849ca3`; 7 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repro-a.jsonl`.

- Runtime batch repro-a: **FAIL** qa-classes-shadow-strike, run `20261022-013754-qa-classes-shadow-strike-lab`, 80.0 s, source SHA256 `d8468239a24c1561419674be720dd9ff71d538a2e857ff43db0cd9f8ab849ca3`; 7 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repro-a.jsonl`.

- Runtime batch repro-b: **PASS** mod-all, run `20261022-014418-mod-all-lab`, 35.8 s, source SHA256 `bcb8d1610dfc9e5f6bf88a756d947badf468c8a4989b127cd7bc2f4f5a0a02d7`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repro-b: **FAIL** qa-firearms-magazine-crit, run `20261022-014454-qa-firearms-magazine-crit-lab`, 98.4 s, source SHA256 `bcb8d1610dfc9e5f6bf88a756d947badf468c8a4989b127cd7bc2f4f5a0a02d7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repro-b: **FAIL** qa-firearms-hoarder-unequip, run `20261022-014633-qa-firearms-hoarder-unequip-lab`, 46.7 s, source SHA256 `bcb8d1610dfc9e5f6bf88a756d947badf468c8a4989b127cd7bc2f4f5a0a02d7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repro-b: **FAIL** qa-classes-shadow-strike, run `20261022-014720-qa-classes-shadow-strike-lab`, 51.1 s, source SHA256 `bcb8d1610dfc9e5f6bf88a756d947badf468c8a4989b127cd7bc2f4f5a0a02d7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repro-b: **FAIL** qa-classes-riposte, run `20261022-014811-qa-classes-riposte-lab`, 69.5 s, source SHA256 `bcb8d1610dfc9e5f6bf88a756d947badf468c8a4989b127cd7bc2f4f5a0a02d7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repro-b: **FAIL** qa-classes-trident, run `20261022-014921-qa-classes-trident-lab`, 30.7 s, source SHA256 `bcb8d1610dfc9e5f6bf88a756d947badf468c8a4989b127cd7bc2f4f5a0a02d7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repro-b: **FAIL** qa-specs-return, run `20261022-014953-qa-specs-return-lab`, 112.0 s, source SHA256 `e6dd57f9685361588a5248748e87414b95f67ba9408a067aa7beefdd0cf97e1b`; 9 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repro-b.jsonl`.

- Runtime batch repair-c: **PASS** mod-all, run `20261022-021439-mod-all-lab`, 35.2 s, source SHA256 `c0c1d51ae7065626588726d6d359b9003dcf681d207b3a3a3539365e5b524cf1`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** qa-classes-shadow-strike, run `20261022-021514-qa-classes-shadow-strike-lab`, 35.3 s, source SHA256 `c0c1d51ae7065626588726d6d359b9003dcf681d207b3a3a3539365e5b524cf1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **PASS** qa-classes-riposte, run `20261022-021550-qa-classes-riposte-lab`, 70.1 s, source SHA256 `9177af82614c887e6792424781188ac0b6e8777a71f4316dfa585c72bd744b94`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** qa-firearms-magazine-crit, run `20261022-021701-qa-firearms-magazine-crit-lab`, 107.5 s, source SHA256 `ab5085de59e0882500205442e67c76961449b991be07a378b9e3d7eff4bafba5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** qa-firearms-hoarder-unequip, run `20261022-021848-qa-firearms-hoarder-unequip-lab`, 55.1 s, source SHA256 `ab5085de59e0882500205442e67c76961449b991be07a378b9e3d7eff4bafba5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** qa-classes-trident, run `20261022-021944-qa-classes-trident-lab`, 93.0 s, source SHA256 `ab5085de59e0882500205442e67c76961449b991be07a378b9e3d7eff4bafba5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** plan-classesa, run `20261022-022117-plan-classesa-lab`, 152.5 s, source SHA256 `aed0b46111b030a0e7e3311eef38110dd93e8b97e4d6e821dec36388bbb59485`; 14 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **PASS** plan-classesb-a, run `20261022-022350-plan-classesb-a-lab`, 137.8 s, source SHA256 `d3c2840ca585b5ca1b1fc8e45ec9415d6258fe1bcdacd074629afa738efaa4f4`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** qa-strongbox-timeout, run `20261022-022608-qa-strongbox-timeout-lab`, 28.2 s, source SHA256 `d0ec4a24a5c2992d7e0b74beb9cb125587ca46c80774e0f0bde1d46010482676`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch repair-c: **FAIL** qa-abyss-timeout, run `20261022-022636-qa-abyss-timeout-lab`, 29.1 s, source SHA256 `d0ec4a24a5c2992d7e0b74beb9cb125587ca46c80774e0f0bde1d46010482676`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-c.jsonl`.

- Runtime batch contract-d: **PASS** qa-specs-crit-contract, run `20261022-023122-qa-specs-crit-contract-lab`, 44.2 s, source SHA256 `52dc16935c6715754a87070ae6179e85edd98a9712ef9318c262a6cd2110dc7c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-contract-d.jsonl`.

- Runtime batch specs-e: **PASS** plan-specs, run `20261022-023342-plan-specs-lab`, 476.5 s, source SHA256 `b64600f53a85642d12122ecd06456deeb019619aa95afa6ed7d5e74942cf567d`; 17 assertions, 0 failed. Details: `gamelab\results\qa-20261022-specs-e.jsonl`.

- Runtime batch specs-e: **FAIL** qa-specs-return, run `20261022-024139-qa-specs-return-lab`, 143.8 s, source SHA256 `6a7eaa9826f3d13727817012d39cb75cd6f44ad1d4895155d4078b32280f0dc7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-e.jsonl`.

- Runtime batch gate-f: **PASS** mod-all, run `20261022-030204-mod-all-lab`, 36.0 s, source SHA256 `d9f8ecf22d486bb8995dbe2db78bf8e74668eb2d5a1aecd6b494131946f37447`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **FAIL** qa-specs-static-native, run `20261022-030240-qa-specs-static-native-lab`, 51.9 s, source SHA256 `d9f8ecf22d486bb8995dbe2db78bf8e74668eb2d5a1aecd6b494131946f37447`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **PASS** qa-firearms-magazine-crit, run `20261022-030332-qa-firearms-magazine-crit-lab`, 114.9 s, source SHA256 `d9f8ecf22d486bb8995dbe2db78bf8e74668eb2d5a1aecd6b494131946f37447`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **PASS** qa-firearms-hoarder-unequip, run `20261022-030527-qa-firearms-hoarder-unequip-lab`, 56.8 s, source SHA256 `a74940967b07ff1ae07c8385dd21b878ccc128f15fbdb31fdcd7cbe028f0a461`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **PASS** qa-classes-shadow-strike, run `20261022-030624-qa-classes-shadow-strike-lab`, 52.0 s, source SHA256 `a74940967b07ff1ae07c8385dd21b878ccc128f15fbdb31fdcd7cbe028f0a461`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **FAIL** qa-specs-lingering, run `20261022-030716-qa-specs-lingering-lab`, 80.7 s, source SHA256 `b2faae0213011dd65cf1a95bbe63990e403786bf36d79d19840878c06a4bb70f`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **FAIL** qa-specs-winddancer-ranks, run `20261022-030837-qa-specs-winddancer-ranks-lab`, 220.4 s, source SHA256 `c8d86d269de70ab75d92303ab4514c550683fc27236ea823a410a68dd3701031`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch gate-f: **PASS** qa-specs-winddancer-orbs, run `20261022-031218-qa-specs-winddancer-orbs-lab`, 182.7 s, source SHA256 `b89fba34f70a0dd0c4f95a02240d663d3f17f24ca2d82925ccb43a16919097f5`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-gate-f.jsonl`.

- Runtime batch breadth-g: **PASS** mod-all, run `20261022-032859-mod-all-lab`, 33.2 s, source SHA256 `ae213dd2c83088d4f0d4e849bc9948fcc56d72afcc4960f90ffa29a67044f734`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** qa-specs-crit-contract, run `20261022-032933-qa-specs-crit-contract-lab`, 44.2 s, source SHA256 `ae213dd2c83088d4f0d4e849bc9948fcc56d72afcc4960f90ffa29a67044f734`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **FAIL** qa-specs-static-native, run `20261022-033017-qa-specs-static-native-lab`, 96.3 s, source SHA256 `77aee82f96b259534d7e42cec8133741a760104cad7b54e45010c46b4818ccc5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **FAIL** qa-specs-return, run `20261022-033153-qa-specs-return-lab`, 141.4 s, source SHA256 `77aee82f96b259534d7e42cec8133741a760104cad7b54e45010c46b4818ccc5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** qa-specs-lingering, run `20261022-033415-qa-specs-lingering-lab`, 82.1 s, source SHA256 `cae8e513c637d94182d488f924722ecb7087fffb4afe21d61af60c1c51570b29`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-core, run `20261022-033538-mod-core-lab`, 12.4 s, source SHA256 `30fbebc88ff5eddcf494693afd0a0e0bf4511930bf1ea4466ad9ba092220e1b5`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-abyss, run `20261022-033550-mod-abyss-lab`, 13.2 s, source SHA256 `30fbebc88ff5eddcf494693afd0a0e0bf4511930bf1ea4466ad9ba092220e1b5`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-architect, run `20261022-033604-mod-architect-lab`, 14.4 s, source SHA256 `82e2e684208d9ba028619f817db432b91a29a01d04b1f6fa8b97ce22eeb3f67e`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-bufftips, run `20261022-033619-mod-bufftips-lab`, 12.9 s, source SHA256 `38ff5a86ead0df82f72b489d7b25945f1d762b8701cef05ce2e0e1cf077a1199`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-campaign, run `20261022-033632-mod-campaign-lab`, 12.9 s, source SHA256 `38ff5a86ead0df82f72b489d7b25945f1d762b8701cef05ce2e0e1cf077a1199`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-chatlinks, run `20261022-033645-mod-chatlinks-lab`, 12.4 s, source SHA256 `38ff5a86ead0df82f72b489d7b25945f1d762b8701cef05ce2e0e1cf077a1199`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-classes, run `20261022-033658-mod-classes-lab`, 13.0 s, source SHA256 `38ff5a86ead0df82f72b489d7b25945f1d762b8701cef05ce2e0e1cf077a1199`; 15 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-colors, run `20261022-033711-mod-colors-lab`, 16.0 s, source SHA256 `38ff5a86ead0df82f72b489d7b25945f1d762b8701cef05ce2e0e1cf077a1199`; 15 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-deathrecap, run `20261022-033728-mod-deathrecap-lab`, 12.7 s, source SHA256 `1161daad9a47accb4cd13e4938045123f774dc6dd9bafeb2dcf15b68f67fa17e`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-droptrade, run `20261022-033741-mod-droptrade-lab`, 12.7 s, source SHA256 `1161daad9a47accb4cd13e4938045123f774dc6dd9bafeb2dcf15b68f67fa17e`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-farming, run `20261022-033754-mod-farming-lab`, 12.7 s, source SHA256 `1161daad9a47accb4cd13e4938045123f774dc6dd9bafeb2dcf15b68f67fa17e`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-firearms, run `20261022-033807-mod-firearms-lab`, 12.9 s, source SHA256 `1161daad9a47accb4cd13e4938045123f774dc6dd9bafeb2dcf15b68f67fa17e`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-fishing, run `20261022-033820-mod-fishing-lab`, 12.5 s, source SHA256 `4779861174a6e05aa1a7fad91cf08d1344f3831dd5ae02c440fb34f9fe51cef3`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-gambler, run `20261022-033833-mod-gambler-lab`, 33.2 s, source SHA256 `fcc05aee3c465677d6e2c6614de024a59ae807658106021f80bac12859e727c7`; 17 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-goldpet, run `20261022-033906-mod-goldpet-lab`, 12.7 s, source SHA256 `fcc05aee3c465677d6e2c6614de024a59ae807658106021f80bac12859e727c7`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-groupcombo, run `20261022-033919-mod-groupcombo-lab`, 12.7 s, source SHA256 `536990260469d5067642e7ca8366971c5a9c1ded9aed34202a0715e3e17d6708`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-keys, run `20261022-033932-mod-keys-lab`, 12.9 s, source SHA256 `536990260469d5067642e7ca8366971c5a9c1ded9aed34202a0715e3e17d6708`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-laststats, run `20261022-033946-mod-laststats-lab`, 32.2 s, source SHA256 `8416927d2eb51a2f9a3538f53a20e8b7f6a54a6562da3673946df7a66f2b983f`; 15 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-legacy, run `20261022-034018-mod-legacy-lab`, 12.4 s, source SHA256 `8416927d2eb51a2f9a3538f53a20e8b7f6a54a6562da3673946df7a66f2b983f`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-maps, run `20261022-034031-mod-maps-lab`, 13.6 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-mercenary, run `20261022-034045-mod-mercenary-lab`, 51.2 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 29 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-pets, run `20261022-034136-mod-pets-lab`, 12.7 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-puzzles, run `20261022-034149-mod-puzzles-lab`, 36.9 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 80 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-specs, run `20261022-034227-mod-specs-lab`, 12.6 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-stash, run `20261022-034239-mod-stash-lab`, 19.4 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 20 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-strongbox, run `20261022-034259-mod-strongbox-lab`, 12.7 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-summons, run `20261022-034312-mod-summons-lab`, 12.7 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-valuables, run `20261022-034325-mod-valuables-lab`, 29.4 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 21 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-wavemode, run `20261022-034355-mod-wavemode-lab`, 13.8 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-weapons, run `20261022-034409-mod-weapons-lab`, 12.9 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch breadth-g: **PASS** mod-weaponswap, run `20261022-034422-mod-weaponswap-lab`, 12.7 s, source SHA256 `bebf4df8c9bc5272a07bb29db558ea8399140e36afc055c31c221bea598fc6e4`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-g.jsonl`.

- Runtime batch pilot-h: **FAIL** qa-specs-winddancer-ranks, run `20261022-035035-qa-specs-winddancer-ranks-lab`, 223.1 s, source SHA256 `4b6a613671a5e368b008399675a5e273ebe5be1edfed32db9b8db8b094bb20bc`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-pilot-h.jsonl`.

- Runtime batch pilot-h: **FAIL** qa-classes-thief-integration, run `20261022-035418-qa-classes-thief-integration-lab`, 35.6 s, source SHA256 `d4ce7c1795df665d0bcb9194826221dc844583ed73e9abb4295534f33b672686`; 14 assertions, 1 failed. Details: `gamelab\results\qa-20261022-pilot-h.jsonl`.

- Runtime batch pilot-i: **PASS** qa-firearms-magazine-edges, run `20261022-040044-qa-firearms-magazine-edges-lab`, 201.7 s, source SHA256 `00e84789d2924f02dc364cbe4b775f9b0affdcb203fc5413ca3ebbd33b775350`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-pilot-i.jsonl`.

- Runtime batch pilot-i: **PASS** qa-specs-righteous-ranks, run `20261022-040406-qa-specs-righteous-ranks-lab`, 96.5 s, source SHA256 `246b70810e30acaafe0dff48b880980251a7a8d383729e4202c04100ba4a697e`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-pilot-i.jsonl`.

- Runtime batch pilot-i: **PASS** qa-specs-banner-ranks, run `20261022-040543-qa-specs-banner-ranks-lab`, 99.1 s, source SHA256 `246b70810e30acaafe0dff48b880980251a7a8d383729e4202c04100ba4a697e`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-pilot-i.jsonl`.

- Pilot-i is terminal, all3 PASS/clean: MagazineEdges 040044; Righteous 040406 all5 native8.8?12s durations, move+.1 and raw benchstats attack+.2 with natural reversion; Standard 040543 all5 actual carried/planted damage ratios and expiry/free plant. Full bot results and post-hoc native attack oracle retained in qa-20261022-banner-rank-evidence.json. Ally/orb effects remain separate.
- Shared restart selftest: all7 cases PASS, preserving defaulttown and explicitresume identity/probe/exactmods/mutedprofile checks and rejecting missingrun/invalidchoice. Pilot-h Thief failure was an unchanged fixture readback after character replacement, not a gameplay defect; class agent correcting scenario expectations. Gale 035035 all5 evasion amounts/reversions PASS; rank1 lifetime unresolved due a2805ms observation gap, not a measured lifetime defect.

- Runtime batch native-j: **PASS** mod-all, run `20261022-042115-mod-all-lab`, 32.2 s, source SHA256 `000f6afc8b0d53a8b7d9bcd8d5c1409be64b94dba5f0ccc053ae56e66d4e2961`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-native-j.jsonl`.

- Runtime batch native-j: **PASS** qa-specs-crit-contract, run `20261022-042147-qa-specs-crit-contract-lab`, 45.1 s, source SHA256 `000f6afc8b0d53a8b7d9bcd8d5c1409be64b94dba5f0ccc053ae56e66d4e2961`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-native-j.jsonl`.

- Runtime batch native-j: **FAIL** qa-specs-static-native, run `20261022-042233-qa-specs-static-native-lab`, 76.7 s, source SHA256 `1ad78c2f887da47f4daf1d4f1595bc141783d3bed2b1f62f8271d2827b1a9c48`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-native-j.jsonl`.

- Runtime batch native-j: **FAIL** qa-specs-static-overlap, run `20261022-042350-qa-specs-static-overlap-lab`, 80.8 s, source SHA256 `f528c5da0a3975c67b1159caba6dd94585187b1f2a00b92135c25d031bcce1e6`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-native-j.jsonl`.

- Runtime batch repair-k: **PASS** mod-all, run `20261022-042709-mod-all-lab`, 15.5 s, source SHA256 `e7d34fab24350769b355891b4455dd94d1342fd2057c61a5d013ddc3b5eb7896`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repair-k.jsonl`.

- Runtime batch repair-k: **PASS** qa-specs-crit-contract, run `20261022-042725-qa-specs-crit-contract-lab`, 43.8 s, source SHA256 `53f664e894ed0deddd9d2121a4855d527ec833c4af38dd24d2a3c0520cd45da1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repair-k.jsonl`.

- Runtime batch repair-k: **PASS** qa-specs-static-native, run `20261022-042809-qa-specs-static-native-lab`, 75.7 s, source SHA256 `53f664e894ed0deddd9d2121a4855d527ec833c4af38dd24d2a3c0520cd45da1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-repair-k.jsonl`.

- Runtime batch repair-k: **INVALID** qa-specs-return, run `20261022-042925-qa-specs-return-lab`, 143.1 s, source SHA256 `53f664e894ed0deddd9d2121a4855d527ec833c4af38dd24d2a3c0520cd45da1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-repair-k.jsonl`.

- Repair-k46031 terminal: valid Static 042809 PASS all3 TT?MM regressions; full stack 042709/critcontract 042725 PASS. Return 042925 behavioral checks allPASS but overallINVALID5 solely installres/editor metadata; do not credit runtimePASS. Userconfig/saves/focus unchanged and teardownclean. No live game/editor process found afterward; five read-only snapshots retain editor dir(size4096,mtime1767921281376516100) and25 identical file hashes. Exact historical before/after values were not recorded. Added isolation-res.json before/after metadata retention without changing the equality gate; one bounded diagnostic-l Return repeat is running. No reset or install/config/save writes.
- Branding source review fixed untested oracle issues: generic observer target_hpExact field, native QueryCircle circle5 outer margins+8, and3.2s actual branded wand input for repeated2s-cooldown gains with brand-claw exclusion. Five native-rate synthetic positive/negative controls pass; new3 scenarios remain UNTESTED.

- Runtime batch diagnostic-l: **PASS** qa-specs-return, run `20261022-044257-qa-specs-return-lab`, 145.7 s, source SHA256 `79d2877a570f940e022a6314e4e4d0a52bc0839e167a3680aaee749e1a98c141`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-diagnostic-l.jsonl`.

- Runtime batch broad-m: **PASS** mod-all, run `20261022-045250-mod-all-lab`, 35.1 s, source SHA256 `3e0f4a56e87a8a6b5eb249f72ae6ac4a460c19470fe64d383e711360a824cd54`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-m.jsonl`.

- Runtime batch broad-m: **PASS** qa-specs-crit-contract, run `20261022-045326-qa-specs-crit-contract-lab`, 42.8 s, source SHA256 `7f08cefc00dbc5dc4fee4d88f76123fa90482b86e9f40d28a43db741c9733d8c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-m.jsonl`.

- Runtime batch broad-m: **FAIL** qa-specs-static-overlap, run `20261022-045409-qa-specs-static-overlap-lab`, 80.4 s, source SHA256 `645d410d47fc86da0efec27fbd7407b5bfb07010e8ec25cae0f8119dcd1a4ad7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-broad-m.jsonl`.

- Runtime batch broad-n: **PASS** qa-specs-winddancer-ranks, run `20261022-050230-qa-specs-winddancer-ranks-lab`, 228.5 s, source SHA256 `4a5169b7f05d9116cf03ecba3b1da940f28e9199e655b900f09ab1068ee9d4a6`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-n.jsonl`.

- Runtime batch broad-n: **FAIL** qa-specs-arcane-ranks, run `20261022-050619-qa-specs-arcane-ranks-lab`, 150.4 s, source SHA256 `243bbd9d5cde09b15257e677d279a38e61e223c45eed01483b49d9caadcd1f36`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-broad-n.jsonl`.

- Runtime batch broad-n: **FAIL** qa-specs-deadeye, run `20261022-050849-qa-specs-deadeye-lab`, 151.0 s, source SHA256 `d9456f01b3a83d3183c6bda3594a182d31238984c651620b3803b6f25984e1c4`; 9 assertions, 1 failed. Details: `gamelab\results\qa-20261022-broad-n.jsonl`.

- Broad-m is terminal after 3 cases: full stack and crit contract PASS; overlap 045409 FAIL retains actual final4 stacks in all3 trials but fails strict newer-orb-outside85px isolation (both orbs trapped near the same wall). No renewed token-bug claim from this geometry failure. The remaining53 planned cases did not run. The test-only lane correction retains the strict isolation/damage oracle and awaits native calibration.
- Broad-n is terminal after 3 cases: Gale 050230 PASS; Arcane 050619 FAIL; Deadeye 050849 FAIL with dirty teardown. Later9 cases did not run. Gale all5 ranks have complete native observer events (5stored/5seen,0dropped) with on/off6006 scene-ms apart for6000ms buffs and exact evade reversion. Arcane plain Blink+Living Mana all5 ranks pass; Far Step endpoints are clipped by the fixture geometry, so radius/distance failure is not yet a production defect. Preserve the original result and certify the destination before recalibration.
- Deadeye 050849 root cause: native log c42 `spawn gamelab/qa_specs_fragile_target_dummy.unit` reports missing texture `gamelab/target_dummy.png`; the spawn no-reply is masked by a finally cleanup restore no-reply. Harness killed the stalled lab process after30s, exit1, dirty teardown. Userconfig/res/saves/focus guards PASS. Root verified no HWR2/HWR/PACKAGER processes remain; no reset/run launched before cause inspection. Correcting only the new QA asset before one documented lab reset. No evidence for a Deadeye gameplay defect from this run.
- After the confirmed QA asset cause, one documented GameLab reset completed (killed nothing; only lab saves/appdata scratch cleared). The corrected fragile fixture uses rooted pinned-native textures/materials and preserves HP1, collision, native damage/death and kill-credit fields; optional QA cosmetic dependencies removed. First-error checkpoints prevent finally cleanup from hiding the original error. Corrected Deadeye remains UNTESTED.
- Pilot-o052354 is terminal **INVALID**, clean teardown, user config/saves/focus unchanged: matched preparation rejected the back-slot requirement; a separate ordinary diagnostic died on floor0; the controlled death menu accepted Enter before its native1500ms input gate. The intended boss/reward coverage remains UNTESTED. Narrow fixture corrections use four rare20/twomod armor pieces, common20 class weapon and legal common back_2b10, preserve57 primary allocation, fail fast on invalid preparation, and honor the native DeathMenu input gate. Melee driver source review found ranged kite/reflex assumptions; class-only native attack adaptation is being prepared, without gameplay edits or ordinary-phase setters.
- Second isolation forensic now identifies the exact 052354 mismatch: ONLY directory `res/editor` size4096Ã¢â€ â€™0, identical mtime1767921281376516100. All25 file sizes/mtimes/hashes still match the earlier forensic; see `qa-20261022-res-editor-second-forensic.json`. Microsoft WIN32_FILE_ATTRIBUTE_DATA documents directory size fields as undefined: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-win32_file_attribute_data . Do not retroactively credit INVALID runs; the earlier 042925 exact values remain unknown.
- Strengthened `env.install_res_snapshot`: recursive file byte-SHA256/size/mtime and directory path/type/mtime, explicit link targets, bounded cycle traversal, fresh metadata and fail-closed read/race checks. Undefined directory size is excluded; file equality and the outer before/after equality assertion remain enforced. Three read-only full manifests are identical (132entries,0.21Ã¢â‚¬â€œ0.30s); artifact `qa-20261022-res-recursive-readonly.json`. Focused mutation/race/link negative tests are pending before resuming native launches. This is an isolation-harness repair, separate from the six runtime-reproduced gameplay fixes.

- Runtime batch pilot-o: **INVALID** qa-classes-thief-hoh2-run, run `20261022-052354-qa-classes-thief-hoh2-run-lab`, 321.0 s, source SHA256 `3221948728142f925a75007ce73c71239e70d4b61fd22d91fb9d7410f1180e5b`; 31 assertions, 4 failed. Details: `gamelab\results\qa-20261022-pilot-o.jsonl`.

- Runtime batch broad-p: **PASS** mod-all, run `20261022-054725-mod-all-lab`, 32.5 s, source SHA256 `ec303669338e442781d213fa73e1e59c34ea64fc18b646840efc14719adb3573`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-p.jsonl`.

- Runtime batch broad-p: **PASS** qa-firearms-magazine-real-damage, run `20261022-054758-qa-firearms-magazine-real-damage-lab`, 155.3 s, source SHA256 `ec303669338e442781d213fa73e1e59c34ea64fc18b646840efc14719adb3573`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-p.jsonl`.

- Runtime batch broad-p: **PASS** qa-firearms-magazine-continuity, run `20261022-055033-qa-firearms-magazine-continuity-lab`, 99.8 s, source SHA256 `1e317375a60c6a8e404625086cdb07caeae4e75877640037e5aca6942dfffbca`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-p.jsonl`.

- Runtime batch broad-p: **FAIL** qa-firearms-magazine-resume, run `20261022-055214-qa-firearms-magazine-resume-lab`, 20.4 s, source SHA256 `1e317375a60c6a8e404625086cdb07caeae4e75877640037e5aca6942dfffbca`; 7 assertions, 0 failed. Details: `gamelab\results\qa-20261022-broad-p.jsonl`.

- Runtime batch arsenal-q: **FAIL** qa-firearms-arsenal, run `20261022-055606-qa-firearms-arsenal-lab`, 992.0 s, source SHA256 `1e317375a60c6a8e404625086cdb07caeae4e75877640037e5aca6942dfffbca`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-arsenal-q.jsonl`.

- Runtime batch arsenal-q: **FAIL** qa-content-stash-families, run `20261022-061238-qa-content-stash-families-lab`, 23.1 s, source SHA256 `24ade13e6b64f5027c60c0f6ba3c8665a683970fadb8ee670973d0f573a23ec7`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-arsenal-q.jsonl`.

- Runtime batch class-r: **FAIL** qa-classes-thief-hoh2-run, run `20261022-061712-qa-classes-thief-hoh2-run-lab`, 97.9 s, source SHA256 `cbb0a9e0bcc92abdaf799ae0e162e73ee8c6820acd990254dc9acb1778d2dbd5`; 29 assertions, 2 failed. Details: `gamelab\results\qa-20261022-class-r.jsonl`.

- Runtime batch class-r: **FAIL** qa-classes-gladiator-hoh2-run, run `20261022-061850-qa-classes-gladiator-hoh2-run-lab`, 97.0 s, source SHA256 `b1417bb7f80392fb9537a476af8033219390ba2e6eb81c28d5ac87d6ebe46073`; 29 assertions, 2 failed. Details: `gamelab\results\qa-20261022-class-r.jsonl`.

- Runtime batch class-r: **FAIL** qa-classes-witchhunter-hoh2-run, run `20261022-062027-qa-classes-witchhunter-hoh2-run-lab`, 96.5 s, source SHA256 `b1417bb7f80392fb9537a476af8033219390ba2e6eb81c28d5ac87d6ebe46073`; 29 assertions, 2 failed. Details: `gamelab\results\qa-20261022-class-r.jsonl`.

- Runtime batch class-s: **PASS** mod-all, run `20261022-063532-mod-all-lab`, 34.5 s, source SHA256 `356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-class-s.jsonl`.

- Runtime batch class-s: **PASS** qa-content-stash-families, run `20261022-063606-qa-content-stash-families-lab`, 22.4 s, source SHA256 `356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-class-s.jsonl`.

- Runtime batch class-s: **PASS** qa-content-stash-neighbors, run `20261022-063629-qa-content-stash-neighbors-lab`, 24.3 s, source SHA256 `356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-class-s.jsonl`.

- Runtime batch class-s: **FAIL** qa-classes-thief-hoh2-run, run `20261022-063654-qa-classes-thief-hoh2-run-lab`, 147.5 s, source SHA256 `356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-class-s.jsonl`.

- Runtime batch class-s: **FAIL** qa-classes-gladiator-hoh2-run, run `20261022-063922-qa-classes-gladiator-hoh2-run-lab`, 183.5 s, source SHA256 `356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-class-s.jsonl`.

- Checkpoint after class-s startup: Stash original 061238 FAIL repaired with slot-matched typed HWP family parsing; original 063606 and eight-item neighbor 063629 PASS, all31 mod-all 063532 PASS, stable aggregate source356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52. Seven scoped gameplay repairs now have passing reproductions; full coverage remains open.
- Isolation manifest negative controls:9 PASS/2 symlink privilege SKIP, actual Windows junction/hash/retarget/cycle controls PASS; native subsequent isolation assertions PASS. Earlier 042925/052354 INVALID verdicts unchanged.
- Class-r three clean setup FAILs are caused by back_2b10 Vit11, native Equipment.as146; old Vit5 assumption corrected. class-s explicitly checks emptyback, four rare20/two-mod pieces, common20 classweapon,57 earned primary points. No ordinary/boss/reward credit from class-r; empty reward-set persistence is vacuous.
- Released Essence controlled10-trial suite staged actors installed at the clean boundary; strict native recast log plus HP death/complete stack observer required. Nonlethal tagged-target and unrelated post-Claw killer windows remain UNTESTED; no real boss/co-op claim.

- Runtime batch class-s: **FAIL** qa-classes-witchhunter-hoh2-run, run `20261022-064226-qa-classes-witchhunter-hoh2-run-lab`, 109.4 s, source SHA256 `356d1ce5873080a5123dae02f079e3eca103f7af03ba5f7bde6209c4fd846e52`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-class-s.jsonl`.

- Runtime batch breadth-t: **PASS** qa-classes-trident-targets, run `20261022-064644-qa-classes-trident-targets-lab`, 102.7 s, source SHA256 `a2b2bb661e73b696275cabcababe434b643ce7268640f645ceca375d12df9864`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-t.jsonl`.

- Runtime batch breadth-t: **PASS** qa-firearms-magazine-resume, run `20261022-064827-qa-firearms-magazine-resume-lab`, 132.8 s, source SHA256 `a2b2bb661e73b696275cabcababe434b643ce7268640f645ceca375d12df9864`; 20 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-t.jsonl`.

- Runtime batch breadth-t: **PASS** qa-firearms-arsenal-dense-subset, run `20261022-065040-qa-firearms-arsenal-dense-subset-lab`, 177.0 s, source SHA256 `a2b2bb661e73b696275cabcababe434b643ce7268640f645ceca375d12df9864`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-t.jsonl`.

- Runtime batch breadth-t: **PASS** qa-specs-static-overlap, run `20261022-065338-qa-specs-static-overlap-lab`, 79.5 s, source SHA256 `a2b2bb661e73b696275cabcababe434b643ce7268640f645ceca375d12df9864`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-t.jsonl`.

- Runtime batch breadth-t: **PASS** qa-specs-arcane-ranks, run `20261022-065457-qa-specs-arcane-ranks-lab`, 150.0 s, source SHA256 `a2b2bb661e73b696275cabcababe434b643ce7268640f645ceca375d12df9864`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-t.jsonl`.

- Runtime batch breadth-t: **PASS** qa-specs-deadeye, run `20261022-065727-qa-specs-deadeye-lab`, 289.9 s, source SHA256 `a2b2bb661e73b696275cabcababe434b643ce7268640f645ceca375d12df9864`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-t.jsonl`.

- Runtime batch class-u: **FAIL** qa-classes-thief-hoh2-run, run `20261022-070416-qa-classes-thief-hoh2-run-lab`, 188.3 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-class-u.jsonl`.

- Runtime batch class-u: **FAIL** qa-classes-gladiator-hoh2-run, run `20261022-070724-qa-classes-gladiator-hoh2-run-lab`, 181.5 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-class-u.jsonl`.

- Runtime batch class-u: **FAIL** qa-classes-witchhunter-hoh2-run, run `20261022-071026-qa-classes-witchhunter-hoh2-run-lab`, 178.6 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-class-u.jsonl`.

- Runtime batch priority-v: **PASS** qa-firearms-orb-reload-over, run `20261022-071705-qa-firearms-orb-reload-over-lab`, 175.1 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-priority-v.jsonl`.

- Runtime batch priority-v: **PASS** qa-firearms-orb-rider-duration, run `20261022-072000-qa-firearms-orb-rider-duration-lab`, 201.3 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-priority-v.jsonl`.

## Historical runtime checkpoint after 07:17 Central (incomplete)

The sole live serial queue is priority-v (root session63466), ordered by scenario
budget to retain time for longer native cases. Exact36 names and frozen metadata:
`gamelab/results/qa-20261022-firearms-specs-priority36.json` and `.meta.json`.
Source aggregate at start: `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`.
Installed mods and queued helpers/scenarios remain frozen; ignored-only new drafts
cannot be credited as runtime verification. Final hour09:20:52; deadline10:20:52.

Seven scoped gameplay repairs have valid passing reproductions, including the new
Stash fix (original061238FAIL, original063606PASS, eight-item neighbor063629PASS).
Full31mod load063532PASS is separate from functional coverage. Firearms native
cold-resume 064827 preserves exact7+5 counts/factors, next real burst5+4/111HP.
Arsenal 055606 retained68/72 damage paths and four misses; dense8 regression 065040
passes all four earlier misses plus four controls. Composite72 distinct paths is
54common+18legal-epic rifle-family cases across two target fixtures, not all
qualities/affixes and not a single72-case rerun. OverReload071705 now passes three
early controls and nine fixed gold-window trials, exact30 to35/40/45 ammo.

Static 065338 passes all three same-TT overlap trials with strict orb isolation,
fresh real crit/HP and complete native traces. Arcane 065457 passes Blink5/FarStep3
native damage/distance/radius checks; exact LivingMana regeneration remains partial.
Deadeye 065727 passes observed five-rank combined-flight damage, speed factors/expiry,
Boomerang2 and StormArrow3 scoped effects. These do not prove exact separate damage
components or action cadence. Before priority-v: Specs60rank rows are35scopedPASS,
5PARTIAL(LivingMana),20UNTESTED;65orb-quality rows are20scopedPASS,41UNTESTED,
4BLOCKED(real-ally SharedBreath1/ManaConduit3). Upcoming11Specs target33qualities;
eight other solo qualities require additional native proof. Inventory owns details.

Class-u070416/070724/071026 are cleanFAIL full runs, with verified ordinary
keep1-to2-to3 transitions on all three ports after the source-backed normal
UseTrigger/sensor adapter. Thief died onfloor3; Gladiator hit the correct locked
sensor route; WitchHunter died during retries. Native keep3 closed-exit prefab
requires the Bandit encounter objective; current driver does not handle it. This
is a harness objective gap, not a class gameplay bug verdict. Finalboss/reward/
natural town/acquired-reward persistence remain UNTESTED. Earlier base reload and
controlled death/town scopes stay separate. Trident 064644 core/classes diagnostic
passes23/24 actual HP trials; one immobilized-brute input26px/+12Y miss remains
retained despite pre-input ray overlap, with no unproved attack-source fix.

The recursive isolation manifest retains strict before/after equality with file
SHA256/size/mtime, directory names/type/mtime and explicit link targets; only
Windows-undefined directory size is excluded. Nine negative-control tests pass,
two symlink-privilege cases skip, actual junction tests pass. Later native runs
pass every user config/save/res/focus guard. Historical INVALID verdicts are retained.

Priority2 still has extensive HoH1 skill/mastery/summon/rank/save gaps; priority3
module functional/UI/settings/persistence/failure/interactions remain broad despite
31 standalone load passes. Prepared tests and source review never count as effects.

- Runtime batch priority-v: **FAIL** qa-firearms-orb-variants-grenades, run `20261022-072322-qa-firearms-orb-variants-grenades-lab`, 239.9 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-priority-v.jsonl`.

- Runtime batch priority-v: **FAIL** qa-firearms-orb-variants-missiles, run `20261022-072722-qa-firearms-orb-variants-missiles-lab`, 335.3 s, source SHA256 `f2c92c3c817ebd093dc5b94f9d415d6f8959db0ebb5db5fdc0cb2f8066f47bb2`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-priority-v.jsonl`.

- Runtime batch shotgun-w: **FAIL** qa-firearms-orb-variants-shotgun, run `20261022-074304-qa-firearms-orb-variants-shotgun-lab`, 88.7 s, source SHA256 `fa6636bc297540872e722f734c17ea7e14227d6a7f2c2dcf0303a701073f20e6`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-shotgun-w.jsonl`.

- Runtime batch breadth-x: **PASS** qa-firearms-orb-belt-feed, run `20261022-075433-qa-firearms-orb-belt-feed-lab`, 362.6 s, source SHA256 `fa6636bc297540872e722f734c17ea7e14227d6a7f2c2dcf0303a701073f20e6`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-breadth-x.jsonl`.

- Runtime batch priority-y: **PASS** qa-firearms-orb-engineer, run `20261022-080310-qa-firearms-orb-engineer-lab`, 161.2 s, source SHA256 `a6b19c08fa79542c7c131e682f56a928113c87671a5f272ee8851d068d546164`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-priority-y.jsonl`.

- Runtime batch priority-y: **PASS** qa-specs-wizard-ranks, run `20261022-080551-qa-specs-wizard-ranks-lab`, 250.6 s, source SHA256 `a6b19c08fa79542c7c131e682f56a928113c87671a5f272ee8851d068d546164`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-priority-y.jsonl`.

- Runtime batch priority-z: **FAIL** qa-firearms-orb-variants-shotgun, run `20261022-081400-qa-firearms-orb-variants-shotgun-lab`, 91.3 s, source SHA256 `e0e3a7db9dd835d397efddfabb4b9be2924f5e3529c8e36decf5ad89e316920e`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-priority-z.jsonl`.

- Runtime batch priority-z: **FAIL** qa-firearms-orb-variants-grenades, run `20261022-081531-qa-firearms-orb-variants-grenades-lab`, 259.3 s, source SHA256 `e0e3a7db9dd835d397efddfabb4b9be2924f5e3529c8e36decf5ad89e316920e`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-priority-z.jsonl`.

- Runtime batch priority-z: **PASS** qa-specs-wizard-orb-damage, run `20261022-081952-qa-specs-wizard-orb-damage-lab`, 204.4 s, source SHA256 `e0e3a7db9dd835d397efddfabb4b9be2924f5e3529c8e36decf5ad89e316920e`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-priority-z.jsonl`.

- Runtime batch priority-z: **FAIL** qa-specs-essence-rates, run `20261022-082316-qa-specs-essence-rates-lab`, 158.8 s, source SHA256 `e0e3a7db9dd835d397efddfabb4b9be2924f5e3529c8e36decf5ad89e316920e`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-priority-z.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-wizard-charge-orbs, run `20261022-082748-qa-specs-wizard-charge-orbs-lab`, 172.1 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 14 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-branding-ranks, run `20261022-083040-qa-specs-branding-ranks-lab`, 118.9 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-branding-orbs, run `20261022-083240-qa-specs-branding-orbs-lab`, 31.9 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **PASS** qa-specs-released-essence, run `20261022-083312-qa-specs-released-essence-lab`, 184.2 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-deadeye-gale, run `20261022-083617-qa-specs-deadeye-gale-lab`, 32.5 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-deadeye-ward, run `20261022-083649-qa-specs-deadeye-ward-lab`, 113.8 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-arcane-feedback, run `20261022-083844-qa-specs-arcane-feedback-lab`, 107.5 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-arcane-barrier, run `20261022-084031-qa-specs-arcane-barrier-lab`, 38.1 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **PASS** qa-specs-banner-crest, run `20261022-084110-qa-specs-banner-crest-lab`, 123.8 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **PASS** qa-specs-banner-drum, run `20261022-084314-qa-specs-banner-drum-lab`, 84.4 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **PASS** qa-specs-banner-martyr, run `20261022-084439-qa-specs-banner-martyr-lab`, 78.7 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch specs-aa: **FAIL** qa-specs-banner-provisions, run `20261022-084558-qa-specs-banner-provisions-lab`, 63.9 s, source SHA256 `51586f6c50f2fb7284f9214eb37051819090c121ccb4ba5918fd74340d89a2e5`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-specs-aa.jsonl`.

- Runtime batch final-ab: **PASS** qa-firearms-orb-variants-shotgun, run `20261022-085158-qa-firearms-orb-variants-shotgun-lab`, 107.4 s, source SHA256 `fd5f2ca3de02cba7f80a7a733e4fbfe1ace9348d3c4d41bac9b9704bba58744f`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ab.jsonl`.

- Runtime batch final-ab: **PASS** qa-firearms-orb-variants-grenades, run `20261022-085345-qa-firearms-orb-variants-grenades-lab`, 259.2 s, source SHA256 `fd5f2ca3de02cba7f80a7a733e4fbfe1ace9348d3c4d41bac9b9704bba58744f`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ab.jsonl`.


## Runtime checkpoint after 09:05 Central

- Final verification phase began early. Hard deadline remains 10:20:52 Central / 15:20:52 UTC. Native owner=root; all launches remain isolated GameLab lab mode.
- Eight scoped production repairs now have native passing reproductions. Dragon's Breath 085158 passes all12 patch timers/countdowns/owner/producer/radius/HP gates; original 074304 and first repair 081400 failures retained. Grenades 085345 passes all9 ranks with exact native TTL traces, actual HP/tags/expiry and CLIP conservation.
- Default build completed in6.2s at clean boundary. All32 release archives were verified against every source payload; All contains955 entries, SHA256 `8d42ca89b379f7bb4ada76085fa6cc1e5ec3c28d6aacbdd4970393c0ecf01274`. Exact artifact evidence: `gamelab/results/qa-20261022-dist-build-manifest.json`. No harness/local-only assets packaged.
- Native final-ab2107 is terminal and held before Missile. Sourcefd5f2ca3 was stable across both PASS runs. New final-ac12786 is the sole live native run: qa-firearms-orb-variants-missiles, launched about09:05, source2075a42408927587, explicit stop-before15:20:52UTC. Journal `gamelab/results/qa-20261022-final-ac.jsonl` appears at terminal.
- New test-only navigation/Branding/GaleWard and Provisions corrections are installed, source-reviewed and not yet credited as native PASS. Wizard bounded cast trace and9-decimal intensity serialization compiled in final-ab. All production archive sources remain unchanged.
- Pending next clean-boundary install: `qa-specs-drafts/qa_arcane_actual_input/install-manifest.json`, full Arc bot SHA57458e9084cef2ccfcc2eee11b8dfdca79f3d6e21e87fdaf1637d4da622f80fa, replaces source2d80a3a8; includes new navigation import and actual deferred SD button casting/fresh targets. Preserve all quality/cap/HP/expiry checks.
- Current granular Specs counts:45 scoped skill-rank PASS,5 LivingMana PARTIAL,10 Branding UNTESTED;37 scoped orb-quality PASS,24 UNTESTED,4 true-ally BLOCKED. Focal is2qualities/3fixedtrials each; Thunderclap is1quality/3fixedtrials. Trial counts are not quality counts. HoH1 full boss/reward/return gaps and all original failures remain explicit.
- Next priority after Missile: install Arc bot and final overview metadata, then full31 mod-all+crit prerequisites; remaining final7-repair reproductions; corrected Essence/Branding/Wizard/GaleWard/Arc/Provisions cases while their timeout*3+60 start gates fit15:20:52UTC. Never reuse batch journal labels. Finish source/diff/doctor checks and exact counts/handoff before deadline; do not call this complete while coverage remains open.

- Runtime batch final-ac: **PASS** qa-firearms-orb-variants-missiles, run `20261022-090522-qa-firearms-orb-variants-missiles-lab`, 505.1 s, source SHA256 `2075a42408927587cf682ed95763861e96d6980ff2d2e2631808f2415324c285`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ac.jsonl`.

- Runtime batch final-ad: **PASS** mod-all, run `20261022-091541-mod-all-lab`, 14.1 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ad.jsonl`.

- Runtime batch final-ad: **PASS** qa-specs-crit-contract, run `20261022-091556-qa-specs-crit-contract-lab`, 45.3 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ad.jsonl`.

- Runtime batch final-ad: **PASS** qa-specs-essence-rates, run `20261022-091641-qa-specs-essence-rates-lab`, 153.9 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ad.jsonl`.

- Runtime batch final-ad: **PASS** qa-specs-static-native, run `20261022-091916-qa-specs-static-native-lab`, 80.3 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ad.jsonl`.

- Runtime batch final-ad: **PASS** qa-specs-static-overlap, run `20261022-092036-qa-specs-static-overlap-lab`, 79.5 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ad.jsonl`.

- Runtime batch final-ad: **PASS** qa-specs-return, run `20261022-092156-qa-specs-return-lab`, 142.0 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ad.jsonl`.

- Runtime batch final-ae: **PASS** qa-content-stash-families, run `20261022-092457-qa-content-stash-families-lab`, 22.2 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ae.jsonl`.

- Runtime batch final-ae: **PASS** qa-content-stash-neighbors, run `20261022-092519-qa-content-stash-neighbors-lab`, 21.9 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ae.jsonl`.

- Runtime batch final-ae: **FAIL** qa-firearms-ranks-base, run `20261022-092541-qa-firearms-ranks-base-lab`, 232.4 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-ae.jsonl`.

- Runtime batch final-ae: **PASS** qa-specs-branding-ranks, run `20261022-092934-qa-specs-branding-ranks-lab`, 148.6 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ae.jsonl`.

- Runtime batch final-af: **PASS** qa-firearms-magazine-crit, run `20261022-093247-qa-firearms-magazine-crit-lab`, 105.6 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

## Final-regression checkpoint (09:36 Central; coverage incomplete)

The final-hour native queue is now `final-af` (root-owned session 28216), after
`final-ae` stopped cleanly at an explicit between-case marker. The four remaining
mandatory repaired-behavior cases run first: magazine crit, Hoarder unequip,
Riposte and Shadow Strike. Remaining prepared Specs cases follow. All launches
retain the 10:20:52 Central deadline gate; no case is started unless its full
three-times scenario budget plus a minute fits. Sources remain frozen at
`20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`.

Final manifest: 10/14 scoped reproductions passed at this checkpoint, including
all three Firearms variant sweeps, full31 stack, crit contract, both Static Charge
cases, Return and both Stash cases. The four remaining entries are queued, not
credited. Missile 090522 passed all nine rows/21 fixed trials with independent
native damage predictions, full settling and same-frame blindness sampling.
Final Static 091916/092036 and Return 092156 pass their retained bounded trials.
Stash 092457/092519 pass conservation, ordering, idempotence and neighbor controls.

Essence091641 and Pyrebrand 092934 now pass their respective five-rank scoped native
measurements. Rank-base Firearms 092541 retains its overall FAIL: five Reload rows
and all paid Frag/low-mana observations pass, but all five cooldown-refusal trials
were scheduled after the authored cooldown had expired. Exact command timestamps
and explicit pre-confirmation cooldown zero establish a test-timing defect; this
is no evidence of a gameplay cooldown bypass. Reload ranks receive scoped PASS;
Frag ranks remain PARTIAL with cooling refusal unverified. No game source was
changed to accommodate these outcomes, and all original results remain retained.

Post-freeze `tools/build.py --check`, `tools/list_verbs.py --check` and
`git diff --check` pass. The previously verified 32 release archives still match
the unchanged production source; Firearms payloads were independently re-read.
The per-feature inventories and final14 manifest are being updated from actual
terminal run data. This checkpoint does not establish full sweep completion.

- Runtime batch final-af: **PASS** qa-firearms-hoarder-unequip, run `20261022-093432-qa-firearms-hoarder-unequip-lab`, 54.7 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **PASS** qa-classes-riposte, run `20261022-093528-qa-classes-riposte-lab`, 69.6 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **PASS** qa-classes-shadow-strike, run `20261022-093637-qa-classes-shadow-strike-lab`, 51.6 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **PASS** qa-specs-wizard-charge-orbs, run `20261022-093729-qa-specs-wizard-charge-orbs-lab`, 154.3 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **PASS** qa-specs-banner-provisions, run `20261022-094004-qa-specs-banner-provisions-lab`, 93.5 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **FAIL** qa-specs-branding-orbs, run `20261022-094138-qa-specs-branding-orbs-lab`, 40.2 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **FAIL** qa-specs-deadeye-gale, run `20261022-094218-qa-specs-deadeye-gale-lab`, 35.8 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-af: **FAIL** qa-specs-deadeye-ward, run `20261022-094254-qa-specs-deadeye-ward-lab`, 131.4 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-af.jsonl`.

- Runtime batch final-ag: **PASS** qa-specs-arcane-feedback, run `20261022-094540-qa-specs-arcane-feedback-lab`, 112.0 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ag.jsonl`.

- Runtime batch final-ag: **FAIL** qa-specs-arcane-barrier, run `20261022-094732-qa-specs-arcane-barrier-lab`, 63.1 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-ag.jsonl`.

- Runtime batch final-ag: **FAIL** qa-firearms-passive-focus, run `20261022-094836-qa-firearms-passive-focus-lab`, 236.7 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-ag.jsonl`.

- Runtime batch final-ah: **PASS** qa-firearms-passive-elements, run `20261022-095401-qa-firearms-passive-elements-lab`, 123.7 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ah.jsonl`.

- Runtime batch final-ah: **PASS** plan-newa-a, run `20261022-095605-plan-newa-a-lab`, 83.4 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 24 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ah.jsonl`.

- Runtime batch final-ah: **PASS** qa-classes-kill-procs, run `20261022-095729-qa-classes-kill-procs-lab`, 73.1 s, source SHA256 `20e6e53aa41364dac51e57a6cfbad272c2a623089e56cbfd64df967868caa25c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ah.jsonl`.

- Runtime batch final-ai: **FAIL** qa-specs-arcane-barrier, run `20261022-100030-qa-specs-arcane-barrier-lab`, 83.1 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 14 assertions, 1 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** plan-runs-arch, run `20261022-100154-plan-runs-arch-lab`, 44.8 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** qa-strongbox-timeout, run `20261022-100238-qa-strongbox-timeout-lab`, 47.5 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** qa-abyss-timeout, run `20261022-100326-qa-abyss-timeout-lab`, 47.2 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** plan-firearms-arm, run `20261022-100414-plan-firearms-arm-lab`, 53.3 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** mod-firearms, run `20261022-100507-mod-firearms-lab`, 14.7 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** mod-specs, run `20261022-100522-mod-specs-lab`, 14.2 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** mod-classes, run `20261022-100537-mod-classes-lab`, 15.3 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 15 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** mod-stash, run `20261022-100552-mod-stash-lab`, 20.9 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 20 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-ai: **PASS** town-rebuild, run `20261022-100615-town-rebuild-lab`, 21.0 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 24 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ai.jsonl`.

- Runtime batch final-aj: **PASS** mod-all, run `20261022-100827-mod-all-lab`, 15.5 s, source SHA256 `d60d37c0dd92d0dab288dcaa0bf3b70e2c7e6998f5b7b046752e1fbdc5b44792`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-aj.jsonl`.

- Runtime batch final-ak: **PASS** qa-dead-state-precision, run `20261022-101134-qa-dead-state-precision-lab`, 25.1 s, source SHA256 `85b04b38bdbd5b565c86bc880e571a48f03557fdd71709356d76ea8961a69739`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-final-ak.jsonl`.

## Handoff prepared before the 10:20:52 Central deadline

The sweep is INCOMPLETE. Native runtime ended cleanly at10:11:59; the final focused
case 101134 passes all8 precise-dead-state gates and12 runner assertions. Live and
actually dead/unspawned manaExact are both12.375, independent damageme raw mana is
12.375, integer mana is12, and MaxMana is preserved. This verifies only the new
read-only telemetry branch; it does not convert Barrier's geometry failure into
an ability pass. Fresh final mod-all 100827 passes14 guards with all31 modules.
Production source and the verified32 release archives remain unchanged.

The final source fingerprint is85b04b38bdbd5b565c86bc880e571a48f03557fdd71709356d76ea8961a69739
(1167 tracked/unignored mods+gamelab+tools files). The last delta after Probe E68E
is its two focused QA regression files. Required final14 scopes retain their actual
per-run fingerprints; the manifest explicitly records the unchanged-production basis.

Final matrix counts: Specs55PASS/5PARTIAL skill ranks;47PASS/3PARTIAL/11UNTESTED/
4allyBLOCKED orb qualities. Firearms10PASS/10PARTIAL/40UNTESTED skill ranks;
42PASS/32UNTESTED/1co-opBLOCKED orb qualities. HoH1 ports4/39 scoped skills and
14/191 scoped positive-rank slots;9mastery saves untested. Module axes217 total:
31standalonePASS,23functionalPARTIAL,163UNTESTED;9 narrow native-feature PASS
records are separate from whole-axis completion. Granular source/actual limits
remain authoritative. No additional production bug is inferred from test setup,
integer serialization, native refresh blending or a wrong chance-combination model.

Resume in a new authorized budget, with a single native-run owner. Do not reuse the
expired overnight batch wrapper deadline. First run the read-only doctor, then fix
and peer-review the measurement setup before repeating its affected case; preserve
all historical outcomes and all assertions' precision/collision requirements.

```powershell
& .venv/Scripts/python.exe -m gamelab doctor
# After source-grounded fixture/oracle repairs:
& .venv/Scripts/python.exe -m gamelab run qa-firearms-ranks-base --mode lab
& .venv/Scripts/python.exe -m gamelab run qa-firearms-passive-focus --mode lab
& .venv/Scripts/python.exe -m gamelab run qa-specs-branding-orbs --mode lab
& .venv/Scripts/python.exe -m gamelab run qa-specs-deadeye-gale --mode lab
& .venv/Scripts/python.exe -m gamelab run qa-specs-deadeye-ward --mode lab
& .venv/Scripts/python.exe -m gamelab run qa-specs-arcane-barrier --mode lab
# Prepared broader HoH1 rank/stat case, separate from ordinary-play proof:
& .venv/Scripts/python.exe -m gamelab run qa-classes-stats --mode lab
```

Prioritize same-frame cooling refusal, native complementary chance composition,
settled Ward intensity within all5 stack lifetimes, and conservative-grid recovery
from legal positions without relaxing the requested geometry. Then complete remaining
Firearms/HoH1 ranks and legal combinations. Teach the ordinary driver the native
keep3 Bandit encounter/unlock objective before repeating all3 boss/reward/town runs.
Finish the module axes and true co-op/audio prerequisites separately. Do not implement
parked designs, change balance, reset active locks or bypass native isolation gates.

Machine-readable handoff: docs/generated/qa_overnight_summary.json. All32 archive
hashes: gamelab/results/qa-20261022-dist-build-manifest.json. Precision-only evidence:
docs/generated/qa_dead_state_precision.json. Exact per-run source/build/isolation/
cleanup proofs remain in the final batch journals and native run directories.

- Runtime batch resume-a: **PASS** qa-classes-thief-mastery-save, run `20261022-104320-qa-classes-thief-mastery-save-lab`, 106.2 s, source SHA256 `85b04b38bdbd5b565c86bc880e571a48f03557fdd71709356d76ea8961a69739`; 30 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-a.jsonl`.

- Runtime batch resume-a: **PASS** qa-classes-gladiator-mastery-save, run `20261022-104507-qa-classes-gladiator-mastery-save-lab`, 99.9 s, source SHA256 `85b04b38bdbd5b565c86bc880e571a48f03557fdd71709356d76ea8961a69739`; 30 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-a.jsonl`.

- Runtime batch resume-a: **PASS** qa-classes-witchhunter-mastery-save, run `20261022-104647-qa-classes-witchhunter-mastery-save-lab`, 99.7 s, source SHA256 `85b04b38bdbd5b565c86bc880e571a48f03557fdd71709356d76ea8961a69739`; 30 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-a.jsonl`.

- Runtime batch resume-b: **PASS** qa-firearms-passive-focus, run `20261022-105134-qa-firearms-passive-focus-lab`, 234.0 s, source SHA256 `e458afe77471f5bb1d42b60979393f6d53b5e01388af4a59c9dd14d1fa4ca69b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-b.jsonl`.

- Runtime batch resume-c: **PASS** qa-specs-deadeye-ward-settled, run `20261022-105904-qa-specs-deadeye-ward-settled-lab`, 123.8 s, source SHA256 `bb30951db16e8e4f421288233ade894264bed1dff2aa321a3da054414f0ba47b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-c.jsonl`.

- Runtime batch resume-c: **FAIL** qa-specs-branding-orbs, run `20261022-110109-qa-specs-branding-orbs-lab`, 73.9 s, source SHA256 `bb30951db16e8e4f421288233ade894264bed1dff2aa321a3da054414f0ba47b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-c.jsonl`.

- Runtime batch resume-d: **PASS** qa-classes-stats, run `20261022-110550-qa-classes-stats-lab`, 108.3 s, source SHA256 `bb30951db16e8e4f421288233ade894264bed1dff2aa321a3da054414f0ba47b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-d.jsonl`.

- Runtime batch resume-e: **PASS** mod-all, run `20261022-111422-mod-all-lab`, 32.6 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-e: **PASS** null-payload, run `20261022-111454-null-payload-lab`, 14.2 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-e: **PASS** qa-firearms-ranks-base, run `20261022-111509-qa-firearms-ranks-base-lab`, 201.4 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-e: **PASS** qa-specs-living-mana-coefficients, run `20261022-111830-qa-specs-living-mana-coefficients-lab`, 117.4 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-e: **FAIL** qa-classes-gladiator-hoh2-run, run `20261022-112028-qa-classes-gladiator-hoh2-run-lab`, 177.0 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 29 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-e: **FAIL** qa-content-weapons-native, run `20261022-112325-qa-content-weapons-native-lab`, 61.6 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-e: **FAIL** qa-content-dirk-defense, run `20261022-112427-qa-content-dirk-defense-lab`, 48.2 s, source SHA256 `2828ef249347d88dd38e0ee757c133b68556ec4598ed5369e24b18c7973e123c`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-e.jsonl`.

- Runtime batch resume-f: **FAIL** qa-specs-branding-orbs, run `20261022-113033-qa-specs-branding-orbs-lab`, 162.2 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-f.jsonl`.

- Runtime batch resume-g: **PASS** qa-firearms-ranks-marksman, run `20261022-113425-qa-firearms-ranks-marksman-lab`, 129.6 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** qa-firearms-ranks-demo, run `20261022-113634-qa-firearms-ranks-demo-lab`, 150.6 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.


## Resumed full sweep ? no time limit (2026-10-22)

The user removed the original overnight deadline and activated the goal again. Work remains in progress; the original deadline/final-hour notes below are historical. Verified scoped coverage now includes60/60 fourth-spec rank cases,49/65orb qualities (nine fresh Branding qualities awaiting granular audit; maximum combo failed),20/60 Firearms ranks,42/75orb qualities,62/191HoH1positive ranks and9/9mastery save/reload combinations. Native stat-only scopes remain separate from combat/cadence/mitigation.

Fresh full-stack `mod-all 20261022-111422` and minimal `null-payload 111454` compile/load checks passed with the read-only per-frame resource observer. `qa-firearms-ranks-base 111509` and `qa-specs-living-mana-coefficients 111830` passed; exact per-run hashes are in the ledger/journals. `qa-specs-branding-orbs 113033` now obtains strict fine-grid/native-ray geometry through normal walking but fails the maximum-combination check. `qa-classes-gladiator-hoh2-run 112028` reached Keep3 and died during objective travel; no class/encounter bug is inferred. Controlled endgame weapon tests 112325/112427 failed native equip requirements before attack/parry testing: ilvl35 requirements use unbounded vector interpolation at34/9, not the high endpoint at level10. A QA fixture correction is staged; no production change is inferred from these setup failures.

The source is frozen during each serial GameLab batch. Remaining ranks/orbs, legal interactions, ordinary run lifecycles, UI/acquisition and module functional/persistence/failure paths remain required. See `docs/QA_OVERNIGHT.md` and `docs/generated/qa_overnight_summary.json`; previous repair regressions and all failures are retained.

Current serial queue: resume-g, no wall-clock cutoff. App goal status is active.

- Runtime batch resume-g: **PASS** qa-firearms-ranks-assault, run `20261022-113905-qa-firearms-ranks-assault-lab`, 137.1 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** qa-firearms-ranks-engineer, run `20261022-114123-qa-firearms-ranks-engineer-lab`, 201.2 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** plan-t8, run `20261022-114444-plan-t8-lab`, 261.3 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 15 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** plan-t9, run `20261022-114906-plan-t9-lab`, 113.0 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** qa-classes-selfbuff-slice, run `20261022-115059-qa-classes-selfbuff-slice-lab`, 100.8 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **FAIL** qa-classes-selfbuff-cloak, run `20261022-115240-qa-classes-selfbuff-cloak-lab`, 85.9 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **FAIL** qa-classes-selfbuff-shield-wall, run `20261022-115407-qa-classes-selfbuff-shield-wall-lab`, 106.1 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** qa-classes-selfbuff-immolation, run `20261022-115553-qa-classes-selfbuff-immolation-lab`, 110.5 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** qa-classes-riposte-all-ranks, run `20261022-115744-qa-classes-riposte-all-ranks-lab`, 104.7 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Module functional audit: plan-t8 `20261022-114444` all55rawflags true; plan-t9 `20261022-114906` all31true, no hiddenfalse/crashes. Fourteen narrow native-feature records added, with source fingerprints and explicit weak-oracle/remaining limits. Quality axes {'PASS': 31, 'PARTIAL': 48, 'UNTESTED': 138}; no whole-module completion inferred.

- Runtime batch resume-g: **PASS** qa-classes-cinders, run `20261022-115929-qa-classes-cinders-lab`, 278.5 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-g: **PASS** qa-classes-vanish, run `20261022-120408-qa-classes-vanish-lab`, 130.4 s, source SHA256 `be2714f7d6d3d4b7671df4faf291591bbcb2fa4b9a6da929cdfba39bd5e52e98`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-g.jsonl`.

- Runtime batch resume-h: **PASS** mod-all, run `20261022-121944-mod-all-lab`, 33.2 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** null-payload, run `20261022-122017-null-payload-lab`, 14.2 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** qa-classes-bench-radius, run `20261022-122032-qa-classes-bench-radius-lab`, 40.0 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** qa-classes-selfbuff-cloak, run `20261022-122112-qa-classes-selfbuff-cloak-lab`, 86.4 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** qa-classes-selfbuff-shield-wall, run `20261022-122239-qa-classes-selfbuff-shield-wall-lab`, 106.2 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** qa-specs-deadeye-gale, run `20261022-122425-qa-specs-deadeye-gale-lab`, 95.6 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** qa-specs-arcane-barrier, run `20261022-122602-qa-specs-arcane-barrier-lab`, 53.1 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **FAIL** qa-firearms-orb-dodge-skip, run `20261022-122655-qa-firearms-orb-dodge-skip-lab`, 65.4 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **FAIL** qa-firearms-orb-rocket-jump, run `20261022-122800-qa-firearms-orb-rocket-jump-lab`, 89.6 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **FAIL** qa-firearms-orb-blinding-poison, run `20261022-122930-qa-firearms-orb-blinding-poison-lab`, 57.1 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **FAIL** qa-firearms-orb-slowing-freeze, run `20261022-123028-qa-firearms-orb-slowing-freeze-lab`, 59.9 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-h: **PASS** qa-classes-backstab-all-ranks, run `20261022-123128-qa-classes-backstab-all-ranks-lab`, 94.6 s, source SHA256 `a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-h.jsonl`.

- Runtime batch resume-i: **PASS** mod-all, run `20261022-123441-mod-all-lab`, 14.1 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **PASS** null-payload, run `20261022-123456-null-payload-lab`, 14.0 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-specs-branding-native-combo, run `20261022-123510-qa-specs-branding-native-combo-lab`, 137.0 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-classes-thief-base-ranks, run `20261022-123727-qa-classes-thief-base-ranks-lab`, 84.7 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-classes-gladiator-base-ranks, run `20261022-123852-qa-classes-gladiator-base-ranks-lab`, 85.5 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-classes-witchhunter-base-ranks, run `20261022-124018-qa-classes-witchhunter-base-ranks-lab`, 98.1 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

### Resumed checkpoint: reviewed harness and native radius gate (resume-h)

At 2026-10-22T17:44:14.217794+00:00 the unlimited sweep remains active. Resume-h completed12native cases:8PASS and4retained orb fixture failures; every teardown clean and source stable a3f53e9005b08fffd4174556f0468104a1f09be8419fe433299c961e569a6c9b. Compile/startup, exact-radius isolated bench, Cloak/Shield, Gale/Barrier and all-rank Backstab passed. DodgeSkip/Rocket lane/charge and Blind/Slow missing calibration target setups require corrected fixtures; none establishes a new production bug. Stop request was observed only between cases, after Backstab123128. Resume-i installed22independently reviewed QA files and is running on de80c5d1ff63d4c0; Branding 123510 failed geometry before any trial, class base failures are under raw audit. Scoped counts now Specs60/60rank,58/65qualityPASS(3PARTIAL,4allyBLOCKED); HoH120/39skills,91/191ranks; Firearms40/60ranks and42/75qualities, with20ranks/32qualities still untested and1allyblocked. These counters do not establish all mechanics, normal acquisition or ordinary lifecycle completion.

- Runtime batch resume-i: **PASS** qa-firearms-passive-steady, run `20261022-124157-qa-firearms-passive-steady-lab`, 436.6 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **PASS** qa-firearms-passive-hoarder, run `20261022-124913-qa-firearms-passive-hoarder-lab`, 147.7 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-firearms-passive-myturret, run `20261022-125142-qa-firearms-passive-myturret-lab`, 196.8 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-firearms-passive-adrenaline, run `20261022-125459-qa-firearms-passive-adrenaline-lab`, 285.5 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **FAIL** qa-content-weapons-native, run `20261022-125945-qa-content-weapons-native-lab`, 108.7 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **PASS** qa-content-dirk-defense, run `20261022-130134-qa-content-dirk-defense-lab`, 61.6 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-i: **PASS** plan-ui-a, run `20261022-130236-plan-ui-a-lab`, 88.0 s, source SHA256 `de80c5d1ff63d4c0696e108b5ea9bffb4384f3141d0b4d10716ba53018fc43a0`; 17 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-i.jsonl`.

- Runtime batch resume-j: **PASS** mod-all, run `20261022-130805-mod-all-lab`, 32.1 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** null-payload, run `20261022-130838-null-payload-lab`, 13.9 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** mod-firearms, run `20261022-130852-mod-firearms-lab`, 13.3 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-input-sequence, run `20261022-130906-qa-firearms-input-sequence-lab`, 68.3 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **FAIL** qa-specs-branding-native-combo, run `20261022-131014-qa-specs-branding-native-combo-lab`, 206.7 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-dodge-skip, run `20261022-131341-qa-firearms-orb-dodge-skip-lab`, 121.1 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-rocket-jump, run `20261022-131542-qa-firearms-orb-rocket-jump-lab`, 108.8 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **FAIL** qa-firearms-orb-blinding-poison, run `20261022-131732-qa-firearms-orb-blinding-poison-lab`, 107.2 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **FAIL** qa-firearms-orb-slowing-freeze, run `20261022-131919-qa-firearms-orb-slowing-freeze-lab`, 107.2 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-ranks-marksman, run `20261022-132107-qa-firearms-orb-ranks-marksman-lab`, 206.5 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-ranks-demolitionist, run `20261022-132434-qa-firearms-orb-ranks-demolitionist-lab`, 196.6 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-ranks-exposure, run `20261022-132751-qa-firearms-orb-ranks-exposure-lab`, 145.8 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-effects-cartridge, run `20261022-133017-qa-firearms-orb-effects-cartridge-lab`, 77.4 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-effects-assault, run `20261022-133135-qa-firearms-orb-effects-assault-lab`, 120.1 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-firearms-orb-frag-shrapnel, run `20261022-133335-qa-firearms-orb-frag-shrapnel-lab`, 213.7 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **FAIL** qa-firearms-orb-reload-explosive, run `20261022-133709-qa-firearms-orb-reload-explosive-lab`, 89.7 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-keys-native-payload-standalone, run `20261022-133840-qa-keys-native-payload-standalone-lab`, 73.8 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-keys-native-payload-all, run `20261022-133954-qa-keys-native-payload-all-lab`, 75.0 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** plan-ui-b, run `20261022-134109-plan-ui-b-lab`, 69.1 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-module-gambler-standalone, run `20261022-134219-qa-module-gambler-standalone-lab`, 83.4 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j: **PASS** qa-module-keys-standalone, run `20261022-134342-qa-module-keys-standalone-lab`, 95.6 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j.jsonl`.

- Runtime batch resume-j2: **FAIL** qa-module-farming-standalone, run `20261022-135031-qa-module-farming-standalone-lab`, 144.4 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-fishing-traps-standalone, run `20261022-135256-qa-module-fishing-traps-standalone-lab`, 24.3 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-pets-standalone, run `20261022-135321-qa-module-pets-standalone-lab`, 50.1 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-goldpet-standalone, run `20261022-135411-qa-module-goldpet-standalone-lab`, 51.4 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-campaign-portal-standalone, run `20261022-135503-qa-module-campaign-portal-standalone-lab`, 20.2 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-wave-standalone, run `20261022-135524-qa-module-wave-standalone-lab`, 81.3 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-summons-standalone, run `20261022-135645-qa-module-summons-standalone-lab`, 52.9 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-j2: **PASS** qa-module-groupcombo-solo-standalone, run `20261022-135738-qa-module-groupcombo-solo-standalone-lab`, 33.9 s, source SHA256 `4b884e9e7983038f460853e0f4c06343ab04cc43467eb8c1b4ad4707358dcca1`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-j2.jsonl`.

- Runtime batch resume-k: **PASS** mod-all, run `20261022-140648-mod-all-lab`, 32.9 s, source SHA256 `24204c9cefd5511b0fcf88062cc3bb7df320ded8bb6fc9db20aad1d2f97e0415`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-k.jsonl`.

- Runtime batch resume-k: **PASS** null-payload, run `20261022-140721-null-payload-lab`, 14.3 s, source SHA256 `24204c9cefd5511b0fcf88062cc3bb7df320ded8bb6fc9db20aad1d2f97e0415`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-k.jsonl`.

- Runtime batch resume-k: **PASS** mod-firearms, run `20261022-140735-mod-firearms-lab`, 13.7 s, source SHA256 `24204c9cefd5511b0fcf88062cc3bb7df320ded8bb6fc9db20aad1d2f97e0415`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-k.jsonl`.

- Runtime batch resume-k: **FAIL** qa-specs-branding-native-combo, run `20261022-140751-qa-specs-branding-native-combo-lab`, 161.6 s, source SHA256 `24204c9cefd5511b0fcf88062cc3bb7df320ded8bb6fc9db20aad1d2f97e0415`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-k.jsonl`.

- Runtime batch resume-k: **FAIL** qa-classes-gladius-collision, run `20261022-141031-qa-classes-gladius-collision-lab`, 56.7 s, source SHA256 `24204c9cefd5511b0fcf88062cc3bb7df320ded8bb6fc9db20aad1d2f97e0415`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-k.jsonl`.

- Runtime batch resume-k: **PASS** qa-classes-poisoned-blades-all-ranks, run `20261022-141128-qa-classes-poisoned-blades-all-ranks-lab`, 235.8 s, source SHA256 `24204c9cefd5511b0fcf88062cc3bb7df320ded8bb6fc9db20aad1d2f97e0415`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-k.jsonl`.

- Runtime batch resume-l: **PASS** mod-all, run `20261022-142448-mod-all-lab`, 14.5 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.

- Runtime batch resume-l: **PASS** null-payload, run `20261022-142504-null-payload-lab`, 14.2 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.

- Runtime batch resume-l: **PASS** qa-specs-branding-native-combo, run `20261022-142518-qa-specs-branding-native-combo-lab`, 163.4 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.

- Runtime batch resume-l: **PASS** qa-specs-branding-ranks, run `20261022-142802-qa-specs-branding-ranks-lab`, 149.6 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.

- Runtime batch resume-l: **PASS** qa-specs-branding-orbs, run `20261022-143032-qa-specs-branding-orbs-lab`, 206.0 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.

- Runtime batch resume-l: **PASS** qa-specs-released-essence, run `20261022-143358-qa-specs-released-essence-lab`, 185.0 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.

- Runtime batch resume-l: **PASS** qa-specs-essence-rates, run `20261022-143704-qa-specs-essence-rates-lab`, 151.3 s, source SHA256 `bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-l.jsonl`.


Resume-l checkpoint 2026-10-22T19:48:33.174029+00:00

Branding stale EssenceFire cache fix verified: identical normal-input regression secondhit81->62 after10Essence consumed; first113 unchanged. All7 required load/rank/orb/Essence regressions PASS, stable1243-file source bd82865baecab25c5c9cfdc8a4b050d4190763050a6cf0848d1099131b9faf7d, clean teardown. Exact installer/unchanged harness pins in gamelab/results/qa-20261022-resume-l-branding-install.json. Gladius remains confirmedzeroHP original 141031 pending reviewed five-rank repair. Root audited native Colors/Deuteranopia and Hazards DeathRecap UIb 134109; exact RGB/text/readbacks and visually reviewed limits in docs/generated/qa_modules_colors_recap_native.json. Full sweep remains ACTIVE_NO_TIME_LIMIT; broad module axes {'PASS': 31, 'PARTIAL': 78, 'UNTESTED': 108}. Historical archives now need rebuilding after gameplay repairs.

- Runtime batch resume-m: **PASS** mod-all, run `20261022-145021-mod-all-lab`, 33.5 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** null-payload, run `20261022-145054-null-payload-lab`, 14.2 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** mod-firearms, run `20261022-145108-mod-firearms-lab`, 13.9 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-classes-gladius-collision, run `20261022-145123-qa-classes-gladius-collision-lab`, 86.2 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-firearms-passive-myturret-native, run `20261022-145249-qa-firearms-passive-myturret-native-lab`, 200.3 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-firearms-passive-adrenaline-native, run `20261022-145610-qa-firearms-passive-adrenaline-native-lab`, 516.1 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-firearms-orb-blinding-poison, run `20261022-150446-qa-firearms-orb-blinding-poison-lab`, 107.2 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-firearms-orb-slowing-freeze, run `20261022-150634-qa-firearms-orb-slowing-freeze-lab`, 107.2 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **FAIL** qa-firearms-orb-reload-explosive-aim, run `20261022-150821-qa-firearms-orb-reload-explosive-aim-lab`, 97.0 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Gladius repair verified 20261022-145123-qa-classes-gladius-collision-lab: all5ranks actual normalcast/owned projectile/first-only contact/payload/preciseHP predictions PASS. Original 141031 zeroHP failure retained; new class-local nativeaxe PlayerDamage uses authored120..200%hand. Source f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b; independent raw Scope audit. No exact8mana/CDduration/laterhitgrowth/ordinaryboss claim. M continues on frozen source.

- Runtime batch resume-m: **FAIL** qa-content-weapons-native-standalone, run `20261022-150959-qa-content-weapons-native-standalone-lab`, 114.1 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **FAIL** qa-content-weapons-native, run `20261022-151154-qa-content-weapons-native-lab`, 115.0 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-module-farming-standalone, run `20261022-151349-qa-module-farming-standalone-lab`, 40.4 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-module-farming-cycle-standalone, run `20261022-151429-qa-module-farming-cycle-standalone-lab`, 119.3 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-classes-pyre-all-ranks, run `20261022-151629-qa-classes-pyre-all-ranks-lab`, 145.6 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-classes-torch-all-ranks, run `20261022-151855-qa-classes-torch-all-ranks-lab`, 202.4 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-classes-planned-attack-all-ranks, run `20261022-152218-qa-classes-planned-attack-all-ranks-lab`, 104.8 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c3-e3, run `20261022-152403-qa-specs-branding-pair-c3-e3-lab`, 164.2 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c1-e3, run `20261022-152648-qa-specs-branding-pair-c1-e3-lab`, 160.5 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c2-e3, run `20261022-152928-qa-specs-branding-pair-c2-e3-lab`, 163.3 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Resumed native module audit 2026-10-22T20:33:10.808095+00:00: freshFarmingbasic151349PASS12/12 andfreshgrowth151429PASS6/6; actualaborted0growth/failed1growth/dry2andwatered1ready, no cropstate setters. Scopedfarmer-spawn/control/nativeAPI/pixel/reload limits in docs/generated/qa_farming_fresh_growth_native.json. M source remainsfrozen; all originalReload andGrimoire failures retained pending reviewed QA corrections.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c1-e1, run `20261022-153212-qa-specs-branding-pair-c1-e1-lab`, 215.4 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c1-e2, run `20261022-153548-qa-specs-branding-pair-c1-e2-lab`, 160.1 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c2-e1, run `20261022-153828-qa-specs-branding-pair-c2-e1-lab`, 197.0 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **FAIL** qa-specs-branding-pair-c2-e2, run `20261022-154146-qa-specs-branding-pair-c2-e2-lab`, 203.9 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **PASS** qa-specs-branding-pair-c3-e1, run `20261022-154510-qa-specs-branding-pair-c3-e1-lab`, 188.9 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **FAIL** qa-specs-branding-pair-c3-e2, run `20261022-154819-qa-specs-branding-pair-c3-e2-lab`, 52.3 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.

- Runtime batch resume-m: **FAIL** qa-specs-ui-sphere-contract, run `20261022-154912-qa-specs-ui-sphere-contract-lab`, 31.1 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-m.jsonl`.


### Resume M terminal checkpoint

All26 cases terminated with20 PASS/6 FAIL; every teardown is clean and all1268 source files retain fingerprint f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b. Required Sphere contract 154912 failed native acquisition, so its six dependent quality sweeps remain gated. Other failures: Reload idle-timer guard, two Grimoire target-distance fixtures and two Branding clear-lane setups. Original results remain; no completion or blanket gameplay failure claim.

- Runtime batch resume-maps: **PASS** qa-content-maps-high-court, run `20261022-155154-qa-content-maps-high-court-lab`, 131.1 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-maps.jsonl`.

- Runtime batch resume-maps: **PASS** qa-content-maps-sunken-dungeon, run `20261022-155405-qa-content-maps-sunken-dungeon-lab`, 127.5 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-maps.jsonl`.

- Runtime batch resume-maps: **PASS** qa-content-maps-goblin-warrens, run `20261022-155613-qa-content-maps-goblin-warrens-lab`, 125.8 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-maps.jsonl`.

- Runtime batch resume-hoh1-a: **PASS** qa-classes-shadow-strike-all-ranks, run `20261022-155959-qa-classes-shadow-strike-all-ranks-lab`, 85.4 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-hoh1-a.jsonl`.


### Added maps native generation

High Court 155154, Sunken Dungeon 155405 and Goblin Warrens 155613 pass at unchanged f8b0 source, with clean isolated teardown. Independent source/native-reply audit matches all12 authored floor identities, live-hostile and enabled-exit presence on nine procedural floors, and allthree exact boss scenes. The32-hostile scan cap limits this to presence. Directmission/god-protected observer does not establish natural drops/unlock, path reachability/traversal, boss combat/rewards, UI or persistence. Evidence: docs/generated/qa_maps_floor_generation_native.json.

- Runtime batch resume-hoh1-a: **FAIL** qa-classes-caltrops-all-ranks, run `20261022-160125-qa-classes-caltrops-all-ranks-lab`, 90.7 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-hoh1-a.jsonl`.

- Runtime batch resume-hoh1-a: **PASS** qa-classes-barbed-net-all-ranks, run `20261022-160256-qa-classes-barbed-net-all-ranks-lab`, 134.7 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-hoh1-a.jsonl`.

- Runtime batch resume-hoh1-a: **FAIL** qa-classes-whirl-all-ranks, run `20261022-160511-qa-classes-whirl-all-ranks-lab`, 82.4 s, source SHA256 `f8b0ed7e57fb4ebf8055c650c7ec4c1fadb0b26bf402b870602a99e61929b00b`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-hoh1-a.jsonl`.

- Runtime batch resume-n-prereq: **FAIL** mod-all, run `20261022-161802-mod-all-lab`, 81.6 s, source SHA256 `279d5559f076b453acbf4634f2f0308560b136f6d70db4795d00adf3937f23ff`; 7 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-prereq.jsonl`.


### N prerequisite compiler failure retained

Root installed32 reviewed QA files from frozen N v2 plan26f770, plus one source-reviewed Sphere sensor-contact consumer54485. Verb index154 and diff checks passed. Native mod-all 161802 halted the prerequisite queue on the new QA Static-MM helper121:73 unsupported vector opNeg; all teardown/isolation/source-stability guards pass at279d5559 (1287files). No ability trial or other prerequisite ran. A minimal source-supported operator correction is under review. At this clean/drained boundary root separately installed finite exact-HP comparison39823; original Caltrops 160125/Whirl 160511 failures remain. Native reruns required.

- Runtime batch resume-n-prereq2: **PASS** mod-all, run `20261022-162545-mod-all-lab`, 33.3 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 16 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-prereq2.jsonl`.

- Runtime batch resume-n-prereq2: **PASS** null-payload, run `20261022-162619-null-payload-lab`, 14.5 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 13 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-prereq2.jsonl`.

- Runtime batch resume-n-prereq2: **PASS** mod-firearms, run `20261022-162634-mod-firearms-lab`, 13.4 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-prereq2.jsonl`.

- Runtime batch resume-n-prereq2: **PASS** qa-firearms-input-sequence, run `20261022-162648-qa-firearms-input-sequence-lab`, 65.2 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-prereq2.jsonl`.

- Runtime batch resume-n-prereq2: **FAIL** qa-classes-input-target-contract, run `20261022-162753-qa-classes-input-target-contract-lab`, 122.8 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-n-prereq2.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-specs-ui-sphere-contract, run `20261022-163415-qa-specs-ui-sphere-contract-lab`, 50.6 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.


### Corrected N load/input gates and independent continuation

Root replaced only unsupported Static-MM vector unary negation with vec2 component construction54d44?5713f07c; original 161802 compiler failure remains. The exact1290-file e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0 epoch includes finite HP comparison39823, peer-reviewed chat consumer a8a091 and source-reviewed Sphere physical contact54485. Native mod-all 162545, null 162619, Firearms 162634 and inputsequence162648 pass cleanly. New inputtarget contract 162753 fails122.8s before valid native cast/payment/effect; geometry/rank/binding/readbacks/release pass. Scope owns first causal protocol audit; no production inference or identical retry. Independent Sphere/originalc657 Firearms/precision/LastStats/weapons/chat/StaticMM/EE/Gladiator pilot cases continue as17-case resume-n-main; installed source frozen throughout.

- Runtime batch resume-n-main: **PASS** qa-firearms-orb-reload-explosive-aim, run `20261022-163506-qa-firearms-orb-reload-explosive-aim-lab`, 97.9 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-firearms-burst-cancel, run `20261022-163644-qa-firearms-burst-cancel-lab`, 198.8 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-firearms-burst-exact-amplitude, run `20261022-164004-qa-firearms-burst-exact-amplitude-lab`, 213.2 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-classes-caltrops-all-ranks, run `20261022-164337-qa-classes-caltrops-all-ranks-lab`, 159.2 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-classes-whirl-all-ranks, run `20261022-164617-qa-classes-whirl-all-ranks-lab`, 74.9 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-classes-shadow-strike-all-ranks, run `20261022-164732-qa-classes-shadow-strike-all-ranks-lab`, 84.4 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-classes-barbed-net-all-ranks, run `20261022-164857-qa-classes-barbed-net-all-ranks-lab`, 90.6 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-module-laststats-native-standalone, run `20261022-165028-qa-module-laststats-native-standalone-lab`, 45.2 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 17 assertions, 2 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-module-laststats-native-full, run `20261022-165114-qa-module-laststats-native-full-lab`, 47.6 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 17 assertions, 2 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-content-weapons-native-standalone, run `20261022-165202-qa-content-weapons-native-standalone-lab`, 113.9 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **PASS** qa-content-weapons-native, run `20261022-165356-qa-content-weapons-native-lab`, 117.0 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-module-chatlinks-native-standalone, run `20261022-165553-qa-module-chatlinks-native-standalone-lab`, 19.7 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-module-chatlinks-native-full, run `20261022-165613-qa-module-chatlinks-native-full-lab`, 20.6 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 12 assertions, 1 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.

- Runtime batch resume-n-main: **FAIL** qa-specs-static-mm-neighbor, run `20261022-165634-qa-specs-static-mm-neighbor-lab`, 98.8 s, source SHA256 `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0`; 9 assertions, 0 failed. Details: `gamelab\results\qa-20261022-resume-n-main.jsonl`.


## User-requested PR wrap (2026-10-22)

The user requested a natural stopping point for a large remote PR; the goal is paused, not complete. Native batch `resume-n-main` terminated cleanly after15of17cases:8PASS/7FAIL, source `e58285ce6d1c63ff3490096f91047b5e255453981589d8078a5a10f15f8f20c0` unchanged across every case. Essence cadence and the corrected ordinary Gladiator pilot never started. LastStats/ChatLinks failed fixture prerequisites, Burst/Shadow failed fixture return/landing control, and Static-MM exceeded a parent path-query timeout before a gameplay trial. All original outcomes remain recorded.

Authoritative scoped totals: fourthspec60/60ranks and61/65orb qualities (4trueallyblocked); Firearms60/60ranks and74/75orb qualities (1co-opblocked); HoH1 29/39 skills, 136/191 positive ranks, 9/9 selected-mastery saves. Ordinary own-active/boss/reward/town/death/save coverage, acquisition/UI, exact remaining mechanics/interactions and broad31-module behavior remain open.

The reviewed21-file O-v2 QA bundle is deliberately UNAPPLIED. Its manifest/payloads plus deferred observer/design work are preserved in an ignored local recovery archive indexed by `docs/generated/qa_deferred_work.json`; they are not installed source or runtime passes. Both essential production additions, `mods/classes/players/hwp/gladiator/projectiles/gladius.unit` and `mods/firearms/scripts/HWP/Firearms/Magazine.as`, must accompany the tracked edits.

Current normal packaging now passes:32archives,956all-in-one entries, everydecoded payload equals current source inputs, no localimports or devharness. All-in-one SHA256 `87bcb72411b57255c616a905a041464601022f2de75b4b6b170b7befce48d419`. This supersedes the earlier archive manifest only for package integrity; it is not a packed-game boot or full-sweep PASS. See `docs/generated/qa_pr_archive_manifest.json`, `qa_pr_validation.json` and `qa_pr_checkpoint.json`. The old14-case final-regression checkpoint retains its historical source/coverage limits.

- Runtime batch pr-wrap-load: **FAIL** mod-all, run `20261022-175056-mod-all-lab`, 34.5 s, source SHA256 `f242a80b25e8c4bdbd048ccf40f0fd7c97a7ce46bdc482c86a6508785878fe19`; 16 assertions, 1 failed. Details: `gamelab\results\qa-20261022-pr-wrap-load.jsonl`.

- Runtime batch pr-wrap-load-after-reset: **PASS** mod-all, run `20261022-175415-mod-all-lab`, 13.9 s, source SHA256 `f242a80b25e8c4bdbd048ccf40f0fd7c97a7ce46bdc482c86a6508785878fe19`; 14 assertions, 0 failed. Details: `gamelab\results\qa-20261022-pr-wrap-load-after-reset.jsonl`.


Final PR verification: full-stack `20261022-175415-mod-all-lab` passes all 14 assertions at source `f242a80b25e8c4bdbd048ccf40f0fd7c97a7ce46bdc482c86a6508785878fe19` with clean teardown. The preceding `175056` bootstrap-shutdown access violation is retained; only isolated GameLab saves/appdata were reset before the successful recheck. Nine new source files received formatting-only cleanup, with native tokens/scalars or Python AST preserved. Final normal packaging verifies all 32 archives and 956 all-in-one payloads at this source; SHA256 `87bcb72411b57255c616a905a041464601022f2de75b4b6b170b7befce48d419`. Historical patch contents are preserved byte-for-byte in `docs/generated/qa_historical_patch_artifacts.json`. This adds no ability-coverage credit and does not complete the paused sweep.
