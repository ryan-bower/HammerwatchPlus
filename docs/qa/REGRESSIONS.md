# QA selection and continuation map

This map selects runnable checks; it does not declare the whole sweep green.
Read the [quickstart](../../gamelab/README.md) before native execution. The
[checkpoint](../generated/qa_pr_checkpoint.json) is authoritative for the paused
sweep and exact source pins. The [old 14-case manifest](../generated/qa_final_regression_manifest.json)
is historical evidence, not a current-epoch suite result.

## Initial gates

Run doctor first. Then run these serially using a unique label:

```powershell
uv run python tools/qa_batch.py --label smoke-001 --dry-run null-payload mod-all
uv run python tools/qa_batch.py --label smoke-001 null-payload mod-all
```

`null-payload` checks a minimal lab boot; `mod-all` checks all 31 normal-release modules
compile/load together. Neither proves full functionality. The original sweep
last recorded full-stack PASS is `20261022-175415-mod-all-lab` at `f242a80b...` (1,290 files).
The preceding `175056` bootstrap shutdown failed with `0xC0000005`; isolated lab
saves/appdata reset was followed by the clean run. Keep both outcomes. An upstream review after PR #9 integrated newer main records another full-stack
PASS, `20261022-193227`, on the merged tree (`0f22a6a`); see the
[merged-tree review in RE_NOTES](../RE_NOTES.md). Its gameplay reproductions were
not rerun there. The original sweep matrix covers six fourth specs and does not
include the subsequently built Priest Forgemaster. The earlier
null/Firearms/input-sequence gates are at the separate `e58285ce...` epoch, as recorded in the checkpoint.

## Select affected regression candidates

These scenarios have scoped historical passing evidence. Re-run applicable ones
after changes, inspect every relevant assertion/control, and record the new source.
A table row is not a promise that the current revision will pass. Execute with
`uv run python -m gamelab run <scenario> --mode lab` or pass the ordered names to
`tools/qa_batch.py --label <unique>` after smoke gates.

| Changed area | Scenario names | What their recorded evidence covers |
|---|---|---|
| Critical fixture/prerequisite | `qa-specs-crit-contract` | Query/rebuild/restore contract; 091556 at `20e6...`; not gameplay critical proof |
| Thunder Orb / Static Charge | `qa-specs-static-native`, `qa-specs-static-overlap` | Controlled cast identity and critical effects; 091916/092036 at `20e6...`; generic delayed non-Thunder-Orb attribution remains open |
| Tailwind return/catch | `qa-specs-return` | Native return/catch effects; 092156 at `20e6...` |
| Branding | `qa-specs-branding-native-combo` | Post-spend refresh and declared combo effects; inspect Branding evidence/inventory for each source qualification |
| HoH1 class repairs | `qa-classes-shadow-strike`, `qa-classes-riposte`, `qa-classes-gladius-collision` | Shadow endpoints and flat melee-only reflection, 093637/093528 at `20e6...`; Gladius first-contact damage all ranks, 145123 at `f8b0...` |
| Stash families/neighbors | `qa-content-stash-families`, `qa-content-stash-neighbors` | Typed family ordering, preservation and idempotence; 092457/092519 at `20e6...` |
| Magazine / Hoarder | `qa-firearms-magazine-crit`, `qa-firearms-hoarder-unequip` | Own-magazine crit damage and absent-gun HUD/bank preservation; 093247/093432 at `20e6...` |
| Firearms area/projectile neighbors | `qa-firearms-orb-variants-shotgun`, `qa-firearms-orb-variants-grenades`, `qa-firearms-orb-variants-missiles` | Family-scoped effects; 085158/085345/090522 at their recorded family source epochs |
| Reload / exact Burst amplitude | `qa-firearms-orb-reload-explosive-aim`, `qa-firearms-burst-exact-amplitude` | Scoped payment/ammo/damage/trajectory/expiry or exact amplitude; 163506/164004 at `e582...` |
| HoH1 Caltrops / Whirl / Net | `qa-classes-caltrops-all-ranks`, `qa-classes-whirl-all-ranks`, `qa-classes-barbed-net-all-ranks` | Recorded controlled rank effects; 164337/164617/164857 at `e582...`; Net authored-vs-tooltip duration remains a candidate |
| Weapon common actions | `qa-content-weapons-native-standalone`, `qa-content-weapons-native` | Native equips, common attack damage and Bulwark actions; 165202/165356 at `e582...`; exact modifiers/chance and ordinary lifecycle remain open |

Full fingerprints and detailed row limits live in the linked checkpoint and family
inventories below. Historical descriptions in the old manifest are not uniformly
precise: Riposte returns damage, magazine tests crit damage, and Hoarder tests HUD
hiding/bank preservation. Use current scenario assertions and source for the oracle.

## Known unreliable or unfinished cases

Keep these out of default green batches. Diagnose a specific cause before rerunning;
do not weaken an assertion merely to make the queue pass.

| Scenario(s) | Last relevant limitation / next prerequisite |
|---|---|
| `qa-classes-input-target-contract` | 162753 projection guard refused before input; establish the cursor projection contract before dependent cases |
| `qa-classes-shadow-strike-all-ranks` | 164732 ranks 4/5 target clipping; reviewed settled-origin correction remains unapplied |
| `qa-firearms-burst-cancel` | 163644 aggregate failed settled return outside 2px; cancellation/payment evidence is separate; return correction unapplied |
| `qa-specs-static-mm-neighbor` | 165634 native path-query RPC timeout before ability trials; route batching correction unapplied |
| `qa-specs-branding-pair-c2-e2`, `qa-specs-branding-pair-c3-e2` | Lane setup failures; other pair passes do not cover these combinations |
| `qa-module-laststats-native-standalone`, `qa-module-laststats-native-full` | Intro-town board route prerequisite failed; main-town fixture correction unapplied |
| `qa-module-chatlinks-native-standalone`, `qa-module-chatlinks-native-full` | Native equipment requirements refused setup; fixture correction unapplied |
| `qa-classes-thief-hoh2-run`, `qa-classes-gladiator-hoh2-run`, `qa-classes-witchhunter-hoh2-run` | Ordinary completion is unproved; corrected Gladiator pilot was unstarted |
| `qa-specs-essence-cadence` | Last planned continuation did not start; do not count planned work as a pass |

New Arcane/Branding boundary drafts, the damage observer and own-active ordinary
run design are preserved in the [deferred bundle](deferred/README.md), not installed
verified scenarios. Real ally/co-op cases need a second real participant. Native
input acknowledgements, forced kills, transitions or synthetic reward windows
alone do not prove an ordinary boss/reward/town/death/save lifecycle.

Controller pitfalls: `Pilot.use` can leave the game paused; confirm the phase and
open UI before waiting for timers. Do not press Escape after an uncertain use:
it can open the pause menu. Require legal target geometry, actual equipment/rank
readbacks, native input/release and consumer effects. Failure before those gates
supplies no downstream ability credit.

## Non-native checks and packaging

From the repository root, select checks for the edited surface:

| Surface | Command |
|---|---|
| Portable batch helper | `uv run python -m unittest tools.test_qa_batch -q` |
| QA oracle helpers | `uv run python -m unittest discover -s gamelab/tests -q` |
| Runner/restart/resource isolation | `uv run python -m unittest gamelab.test_runner_restart gamelab.test_res_snapshot -q` |
| Compiler discovery | `uv run python tools/compiler_selftest.py` |
| Save backup/doctor setup | `uv run python tools/saves_selftest.py`, `uv run python tools/doctor_selftest.py` |
| Registered verbs | `uv run python tools/list_verbs.py --check` |
| Module override consistency | `uv run python tools/build.py --check` |
| Complete staged patch | `git diff --cached --check` |
| Normal release build | `uv run python tools/build.py` |

Tests use their documented temporary fixtures; doctor/save self-tests may need
process/filesystem access outside a restricted sandbox. These tests do not authorize
restoring actual player saves. Existing [PR validation](../generated/qa_pr_validation.json)
records the previous commands, results and skips. The
[archive manifest](../generated/qa_pr_archive_manifest.json) records decoded
package/source integrity at its own source epoch; it does not establish a packed
runtime. Production builds exclude dev harness and local imports by default.

## Evidence and continuation order

1. Read [qa_pr_checkpoint.json](../generated/qa_pr_checkpoint.json) for paused
   status, last coverage batch, failures and latest separate load gate.
2. Choose the family inventory:
   [Specs](../generated/qa_specs_inventory.json),
   [Firearms](../generated/qa_firearms_inventory.json),
   [HoH1 classes](../generated/qa_classes_inventory.json),
   [modules](../generated/qa_modules_inventory.json).
3. Inspect the scenario and bot, reproduce one bounded issue, and distinguish a
   harness prerequisite from a gameplay defect. Preserve all failed attempts.
4. Fix confirmed behavior or a justified fixture/oracle issue, restart after script
   edits, and re-run the reproduction plus affected neighbors. Freeze sources while
   native cases execute. Record actual effects and each source epoch separately.
5. Update compact current evidence and the [historical ledger](../QA_OVERNIGHT.md).
   Counts describe scoped effects; preserve unresolved mechanics, combinations,
   acquisition/UI, ordinary lifecycle and real-co-op requirements.

The sweep remains paused/incomplete. This documentation and batch-helper follow-up
does not add native coverage or reinterpret old runs as tests of new helper code.
