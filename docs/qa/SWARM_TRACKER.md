# Swarm tracker agent protocol

Use `tools/qa_swarm.py` as the persistent task ledger for the
[swarm plan](SWARM_VERIFICATION_PLAN.md). Start every resumed session or compaction
with `resume`; do not reconstruct status from chat history. The CLI uses Python
3.10+ and the standard library, plain files and JSON. It has no model, agent
framework, connector, browser or service dependency.

The canonical state is `docs/qa/swarm/state.json`. It is a portable, reviewable
JSON file intended to be committed with checkpoints at idle boundaries. Raw
evidence and draft patches stay under ignored `gamelab/results/swarm/`. A fresh
clone retains task history and evidence summaries, but may lack cited raw files.
Never initialize over existing state or edit the ledger by hand.

## Resume with minimal context

Run from the repository root, using the project interpreter when available:

```powershell
python tools/qa_swarm.py resume --owner H1 --limit 5
python tools/qa_swarm.py show H1-INVENTORY --owner H1
```

Choose the stable owner alias for your assignment: `coordinator`, `runtime`,
`integrator`, a lane such as `H1`, or a named independent reviewer. These are
coordination identities, not authentication. The root agent maps aliases to its
current subagents; no particular platform's agent IDs are required.

`resume` returns campaign/task revisions, source epoch, persistent freeze state,
your owned work, claim tokens, expiry/source-change warnings, next ready tasks,
blockers and exact claim argument arrays. Its suggested commands preserve the
chosen interpreter and `--state` path. Read only the relevant task, source and
artifact references next. `show` bounds evidence/history to five rows by default;
`--history-limit 100` increases that window. The full ledger retains all events.

`next`, `status` and `resume` return the same bounded packet, so agents need only
learn one response shape. Unclaimed intermediate repairs remain discoverable.
Deferred and harness-blocked work appears as an explicit blocker, not a pass or
an automatic retry. Empty ready work does not imply completion.

## Bounded response views and complete retrieval

The canonical state always keeps every task, evidence row and history event.
Response views are bounded for agent context. `resume`, `status` and `next` apply
`--limit` to owned, ready and blocked task lists independently. Each list has
`pagination` metadata with total/returned counts, offset, limit and `next_argv`.
Use `--owned-offset`, `--ready-offset` or `--blocked-offset` to select a page.
Returned task cards preserve revision, claim token/attempt/epoch, paths,
dependencies and exact next action. Tokens retain the existing owner redaction.

Task mutation receipts retain `data.result.id`, `revision`, `status` and all
other small task/control fields. By default their raw `evidence` and `history`
arrays are empty, with total counts and a concise `latest_evidence` summary.
Explicit retrieval argv lead to the stored detail; no evidence is discarded.
Clients that need rows immediately can request `--evidence-limit N` and/or
`--history-limit N` on task mutations (0..100, default0).

`show` preserves its legacy latest-five detail view. `--evidence-limit` can set
the evidence page independently; omitting it follows `--history-limit` as
before. Detail offsets skip the newest rows: each page remains chronological,
and its continuation retrieves older rows. Reverse the page order to rebuild
the full chronological sequence. Explicit limit0 returns counts/retrieval only.

Continuation argv include a read guard: campaign `--at-revision` for task lists,
or `--at-task-revision` for one task's evidence/history. If relevant state changes
between pages, `revision_conflict` refuses the read instead of silently skipping
or duplicating rows; start retrieval again from the first page. These guards
never mutate the ledger and do not replace mutation CAS or claim tokens.
Verification still reads all canonical evidence, including failures outside a
response page. `latest_evidence` summarizes one row, never aggregate success.
No list or page count implies feature coverage or completion.

## Machine interface

`python tools/qa_swarm.py schema` lists commands, states, operations, evidence
scopes and required fields. `--help` is available for each command. Normal
responses and expected errors are single JSON objects on stdout:

```json
{"schema_version": 1, "ok": false, "command": "claim", "error": {"code": "revision_conflict", "message": "reread task before updating", "details": {"expected": 0, "actual": 1}}}
```

Exit 0 means the tracker operation succeeded; exit 2 means refusal, invalid input
or unreadable state. These are tracker exit codes, separate from GameLab's codes.
Parse `ok` and `error.code`; avoid matching prose. Unknown schema versions and
corrupt JSON refuse mutation. JSON file inputs accept UTF-8 with or without BOM.
Command fields use argument arrays; the tracker never executes a stored command.
Global `--state PATH` precedes the subcommand and isolates temporary campaigns.

## Claim and checkpoint bounded tasks

The initial seed contains 27 queued tasks: a baseline, 24 lane inventories, smoke
and native prerequisite contracts. Inventory tasks require source review only.
They do not stand for completed feature testing. Each owner adds small follow-up
tasks with exact paths, checks, operation class and dependencies as it discovers
the work; keep one reproduction or closely related check group per task.

```powershell
python tools/qa_swarm.py claim H1-INVENTORY --owner H1 --expect 0
python tools/qa_swarm.py update H1-INVENTORY --expect 1 --token TOKEN --summary "Mapped parser contracts; corruption checks remain" --next-action "Add bounded corruption and transaction tasks"
```

Use the returned revision and token for the next mutation. Do not reuse the
example revisions after another update. Claims receive a unique attempt ID,
artifact-directory path, pinned epoch, dependency revisions and a two-hour lease.
`update`, `record-batch` and `record-pool` renew that lease; `--lease-minutes` accepts 1–1440.
Record concrete findings and the exact next action after meaningful progress and
before compaction or handoff. The file, not conversational memory, carries them.

Read the status returned by `claim`: only `queued` becomes `reviewing`;
claimed `harness-blocked`, `fix-drafted` or `reviewed` work keeps its status.
Follow legal transitions explicitly, for example
`harness-blocked` → `reviewing` → `reproduced`. Only verification automatically
releases a claim; other final dispositions still need an explicit `release`
before thawing a native queue.

An amendment requires idle phase and no claim, including an expired claim.
For offline work, use an eligible explicit reclaim or owner handoff, then
release before amendment; do not hand-edit claim fields. After a metadata
refusal, resume actual state and use fresh CAS revisions/tokens for the legal
continuation. Correct bookkeeping without rerunning completed tests or changing
source merely to recover from the refusal.

For an admitted copy/clone check, prefer a short, coordinator-approved owned
ignored execution root such as `gamelab/results/<epoch>-<task>-<trial>`.
Keep the durable attempt directory as the checkpoint/evidence location, with
pointer metadata to that resolved execution root, trial and pinned inputs/results.
Before copying, budget the resolved absolute root plus the longest copied suffix
and temporary/backup suffix headroom; the relative path alone is insufficient.
Do not change system long-path settings as a staging fix. Preserve a failed
stage: `WinError 206` before worker launch means staging failed with zero tests
executed, not that the planned 15-test suite failed.

To hand work off, `release` requires its latest revision/token plus `--summary`
and `--next-action`. Intermediate repair states remain ready for the next owner.
Blocked/deferred transitions also require both fields. Resuming blocked/deferred
work is a deliberate claim and state update after addressing the prerequisite.

An expired offline claim can be reclaimed with `claim --reclaim --reason TEXT`.
This creates a new token and attempt; the old owner cannot overwrite it. Existing
evidence stays historical until revalidated for the current attempt. Expired
native/integration claims require explicit owner release after diagnosing the
actual runtime/source boundary. Expiry never thaws the campaign or touches locks.

All writes hold a short exclusive tracker lock across read, revision/token checks,
validation and atomic replacement. Independent task updates use their task
revision, so unrelated updates do not cause revision conflicts. A competing writer
waits up to three seconds, then refuses. A leftover tracker lock is never deleted
automatically: inspect its PID and cause first. Do not confuse it with GameLab's
locks. No command in this tool resets any runtime or applies a source patch.

## Defer obsolete unclaimed work

The coordinator can explicitly defer an obsolete task at an idle boundary, even
when unmet prerequisites prevent anyone claiming it:

```powershell
python tools/qa_swarm.py defer H1-OBSOLETE --expect TASK_REVISION --actor coordinator --reason "Superseded by the replacement contract" --next-action "Retain historical evidence; continue the replacement task"
```

This command uses the task revision for compare-and-swap. It requires a nonempty
reason and next action, idle phase, no claim (including an expired claim), and a
nonverified task. An existing owner must explicitly release their claim first;
verified work must be explicitly reopened first. The command preserves all
dependencies, evidence and previous history, then records the coordinator's
disposition. It never satisfies prerequisites, changes the graph, acquires or
resets runtime locks, thaws a campaign, or establishes verification. Deferred
work remains discoverable with its original blockers and evidence.

## Add work from structured files

Write task definitions in your ignored attempt directory, then add them through
the CLI. `add`, `epoch` and `phase` use the campaign revision from `status`;
task updates use the task revision from `show`.

```json
{
  "id": "H1-CORRUPT-PROFILE",
  "title": "Reject truncated native profiles without writing output",
  "lane": "H1",
  "operation": "sandbox",
  "priority": 10,
  "paths": ["tools/save_builder.py", "tests/test_save_builder.py"],
  "depends_on": ["H1-INVENTORY"],
  "required_scopes": ["offline"],
  "checks": ["truncated-profile"],
  "next_action": "Inspect parser contract, reproduce with a temporary profile and add a failure-preservation regression."
}
```

```powershell
python tools/qa_swarm.py add --file TASK.json --expect CAMPAIGN_REVISION --actor H1
```

IDs use uppercase letters, digits, underscores and hyphens; the first character
is a letter. Dependencies must already exist. Missing/self/cyclic dependencies
and duplicate IDs refuse the whole write. Seed initialization validates the
complete graph before writing state. Use operations `review`, `draft`, `sandbox`,
`integration` or `native`. Paths declare intended ownership and are advisory;
they are not filesystem permissions. Inventory tasks have no edit authorization.

Only verified, current-epoch prerequisites satisfy readiness. A new epoch makes
older verification stale; reopening/revising a prerequisite also invalidates its
dependents. Claims and evidence retain dependency revisions so observations made
under an older prerequisite cannot be relabeled against a newer one.

## Strengthen an existing task definition

The coordinator can amend an existing task without rewriting the ledger by hand:

```powershell
python tools/qa_swarm.py show TARGET --owner coordinator
python tools/qa_swarm.py amend TARGET --file AMEND.json --expect TASK_REVISION --actor coordinator --reason "Discovered prerequisite" --next-action "Collect the strengthened evidence"
```

This is task-revision CAS, not campaign-revision CAS. It requires idle phase,
nonempty reason/next action and an unclaimed target, including expired claims.
An owner must release first; verified work must be explicitly reopened first.
The command is coordination bookkeeping and never acquires/resets runtime locks,
thaws a freeze, starts work, changes source epochs or establishes verification.

AMEND.json may contain only `paths`, `checks`, `required_scopes`, `depends_on` and
the optional `replace_deferred_dependencies` map. Supplied lists are complete
desired lists and must retain every existing obligation; omitted lists remain
unchanged. The command preserves existing order and appends newly supplied values.
For example, after reading the current task, retain all its existing dependencies
and append the newly discovered transport contract:

```json
{"depends_on":["EXISTING-CONTRACT","NEW-TRANSPORT-CONTRACT"]}
```

Unknown fields, invalid/duplicate/empty list values, unknown scopes, removed
obligations and semantic no-ops (including order-only changes) refuse atomically.
Task identity, title, lane, operation, priority, evidence and claim fields cannot
be edited. Missing/self/cyclic dependencies refuse before atomic replacement.

A narrow explicit replacement can remove an obsolete deferred prerequisite:

```json
{"replace_deferred_dependencies":{"OLD-DEFERRED":"NEW-CONTRACT"}}
```

The old ID must be a current dependency, deferred and unclaimed even if its claim
is expired. The new task must exist and preserve the old task's exact operation,
all named checks and all required evidence scopes. Neither task is modified.
Replacement targets cannot also be removed in the same request; chained maps
refuse. An already required stronger task may replace the deferred gate without
creating duplicate dependencies. If `depends_on` is also supplied, it must include
all resulting prerequisites and omit every replaced ID. Other dependencies may
only be added. These guards do not infer that the replacement is verified.

Successful amendments preserve all evidence and previous history, increment task
and campaign revisions, and record reason plus before/after definitions. Each
replacement also records old/new dependency definitions and revisions. Amended
nondeferred work returns to queued; deferred work remains deferred. Previous
verification metadata/evidence stays historical and cannot satisfy a new claim.
Descendants keep their old dependency revisions and become stale naturally;
their definitions/evidence are never silently rewritten or reverified.

Default amendment receipts use the existing bounded task result shape with no
raw evidence/history arrays. Retrieve the audit with `show TARGET --history-limit
1`; use its normal guarded pagination for older records. Schema version remains 1;
`schema` advertises the new command, allowed fields and replacement-map name.

## Source epochs and the native freeze

After setup and source stabilization, the coordinator/integrator records an epoch:

```powershell
python tools/qa_swarm.py epoch E001 --capture --expect CAMPAIGN_REVISION --actor coordinator
```

Capture only reads Git and the committed build pin. It records the existing
`mods+gamelab+tools-v2` fingerprint, additional tests/planner/package/project hashes
and build metadata. It does not establish doctor readiness, inspect the real
install, hash ignored generated assets or prove a test passed. Record generated
inputs and per-case archive hashes separately. `epoch E001 --file EPOCH.json`
accepts the same shape for externally prepared evidence. Epoch IDs are immutable.

Pin before claiming work that will be verified. If the epoch changes while you
hold a claim, checkpoint/release it, claim again and revalidate before completing.
During a final freeze, stale selected checks get explicit coordinator `reopen`
operations and fresh attempts. Reopening preserves all previous evidence and
requires a reason/next action. A new attempt cannot complete from old evidence.

The designated runtime owner records the freeze only after obtaining the plan's
actual source-freeze acknowledgements:

```powershell
python tools/qa_swarm.py phase frozen --expect CAMPAIGN_REVISION --actor runtime --reason "Writers acknowledged E001; runtime prerequisites checked"
```

An integration claim, even expired, prevents freezing. Only `runtime` can claim
native tasks, and only with a frozen pinned epoch. Only `integrator` can claim
integration tasks. Recording an `integrated` transition also requires that owner
and idle phase, including when the underlying task started as a review/draft.

Choose each claim owner from the task operation and the public schema/resume
role contract; coordinator bookkeeping privileges do not authorize integration
claims. Use the returned claim arguments rather than one owner for every step.

A refused public mutation is atomic, but earlier successful CAS commands in a
multi-step helper remain committed. After a partial helper failure, resume/show
actual state and reread current revisions/tokens before continuing. Make the
continuation idempotent: skip already-current accepted steps and do not duplicate
evidence or rerun completed tests to recover from a bookkeeping refusal. Stale
work still needs its declared revalidation; a skip is not automatic verification.

Tracker metadata updates may continue during a native queue because this ledger
is outside installed source and the batch fingerprint. Confined draft construction
and expressly admitted pure checks may use ignored results directories without
changing live sources or inputs. Installed source edits/generation, Git
staging/commits and consumed-input changes remain prohibited by AGENTS and the
plan. Owner-controlled launcher preflight rebuilds retain their existing gates.

After the real queue has cleanly ended, release native task claims, then record
`phase idle --reason TEXT`. The tracker refuses thaw while a native claim remains.
It never polls, kills, launches or resets the game, and it does not replace
GameLab's isolation or machine-wide coordination rules. A claim/freeze flag is
bookkeeping, never proof that the machine is safe to run or edit.

## Record evidence without inflating coverage

For source or offline evidence, create a JSON file and attach it with
`update --evidence FILE`. Failed, blocked and skipped observations are retained
alongside later passes. A source-review example is:

```json
{
  "scope": "source",
  "outcome": "pass",
  "epoch": "E001",
  "expected": "Every save-builder entry point has a contract and test disposition",
  "observed": "Reviewed the listed paths and created follow-up tasks for uncovered cases",
  "reviewer": "reviewer-safety",
  "artifacts": ["docs/generated/qa_swarm_inventory.json"]
}
```

Offline evidence additionally needs `command` argv and integer `exit`; a pass
requires an observed OS exit 0. A worker's internal success JSON or its parent's
exit 0 does not establish the worker's exit. Retain actual parent/child codes,
timeouts, stdout/stderr and named results separately. Missing/null child codes
are finality gaps; preserve that attempt before any reviewed capture correction.
Windows `Start-Process`/`WaitForExit` produced such a gap in this campaign;
bounded Python `subprocess` capture recorded the recovery's real return code.
Never convert a null code to zero.

Before the first CAS in an evidence-attachment sequence, prevalidate the full
set of evidence JSON, required fields and pinned artifact hashes. Every canonical
non-source row needs integer `exit`; `exit_code` alone is invalid. Retain a
metadata-only rejection and correct it in a distinct ignored amendment with
updated hashes, preserving the original. Resume actual state before continuing;
do not rerun a game or completed test solely to repair evidence schema.

For future admitted workers, a virtualenv launcher's `Popen.pid` can differ from
the actual worker PID. Retain supervisor/Popen identities and worker-reported
PID/PPID at start and terminal, then validate the owned direct or one-hop parent
relationship rather than assuming PID equality. Keep launcher-handle exit,
durable worker terminal, independent base-process OS exit and post-run absence
distinct; report which were observed. Unknown identity/finality or timeout means
STOP and account for the exact owned process before replacing it; never kill a
foreign process. These are prospective capture instructions: post-run absence
cannot reconstruct an unrecorded historical parent edge or strengthen retained
historical finality beyond its documented scope.

Retain the launcher's session handle even when stdout is empty. Record argv,
working directory, start time and, when available, PID plus creation time in the
attempt directory. Poll that handle to terminal completion or account for its
exact owned process before launching a replacement. Empty output and a finished
agent turn do not establish process exit. After compaction, reconcile unfinished
helpers from those records; never terminate an unrelated process. A historical
read-only extraction in this campaign lost its session handle and remained alive
using about 96 GB, eventually refusing a later native preflight. Its identity,
failed cleanup and successful exact-process cleanup are retained separately from
game trials. Resource recovery does not replace source/input or ownership gates.

`check` identifies a required named check. Native scopes are
`native-contract`, `load`, `controlled-native`, `ordinary`, `packed` and `coop`.
`visual` can describe inspected browser/game images without forcing a game build
onto a planner check. Keep scopes as narrow as the observed effects support.

Import native batch rows using their actual journal index:

```powershell
python tools/qa_swarm.py record-batch SMOKE --expect TASK_REVISION --token TOKEN --journal gamelab/results/qa-batch-LABEL.jsonl --index 1 --epoch E001 --scope load --expected "Minimal isolated lab boot" --observed "Inspected run, inner result, assertions and logs" --reviewer reviewer-safety
```

The importer reads the journal and actual `run.json`/`inner.json`, checks their
agreement, finality and guards, and records a failed attempt if the raw pass is
missing or unsafe. A native pass also requires before/after source equal to its
epoch and build ID/executable hash equal to the epoch's pin. A direct native-run
evidence file can be attached with all fields listed by `schema`; the same
structural guards apply. It needs the separately recorded source fingerprints.

The tracker validates structure and imported launcher verdicts. Reviewers still
inspect consumer rows, source expectations, screenshots and semantic scope. An
agent-supplied reviewer label is an auditable assertion, not authenticated review.
Citation paths for general evidence can survive without the original local files;
fresh-clone reviewers must distinguish portable summaries from available raw data.

For an audited isolated worker pool, import the actual child index from its
explicit receipt instead of treating it as a serial JSONL journal:

```powershell
python tools/qa_swarm.py record-pool SMOKE --expect TASK_REVISION --token TOKEN --receipt gamelab/results/pool-LABEL/pool.json --index 1 --epoch E001 --scope load --expected "Original assertions and exact slot isolation" --observed "Reviewed raw run, inner, slot teardown and parent finality" --reviewer reviewer-safety
```

`record-pool` rereads the nested raw results, immutable child teardown copy,
stream hashes, exact slot identity, source/build pins and closed parent manifest.
It requires recorded CLI terminal states, empty named jobs, absent game processes,
released leases and a clean coordinator teardown. A failed sibling is retained in
the evidence context; it cannot manufacture an individual PASS. Task claims still
belong to one runtime coordinator and do not authorize independent launches.
The coordinator holds the machine lease and source freeze until all children end.
Only reviewed, hash-pinned scenarios and bots are eligible for the current pool;
broader campaign cases need their own eligibility review before parallel admission.

For data-driven catalogs, `record-pool` also rereads the pinned catalog/scenario
snapshots and raw completed bot results. It reconciles declared consumer rows
without revalidating a later working tree as historical execution evidence.
Keep semantic and visual review scoped to what was actually inspected.

Generate a proposal from explicit frozen catalog bindings and current task
claims, then import multiple results in one transaction:

```powershell
python tools/qa_swarm.py --state PATH/state.json plan-pool-import --journal gamelab/results/pool-LABEL/pool.json --epoch E001 --reviewer ACTUAL_RESULT_REVIEWER --observed "Reviewed both raw feature results and finality" --verify-complete
python tools/qa_swarm.py --state PATH/state.json record-pool-bundle --bundle PATH/reviewed-import.json
```

Save the proposal JSON's `bundle` object as the reviewed import file. It carries
schema version1, `imports` with task/index/journal/epoch/scope/check/expected/
observed/reviewer/expect/token, and optional `verify_complete` task IDs. Planning
is read-only and the reviewer argument identifies the actual result reviewer,
not the catalog's earlier source reviewer. Claims and prerequisites must already
be current. Any stale CAS, changed dependency, tampered/missing raw result or
incomplete required check refuses the whole bundle without changing the ledger.
Successful bundles save once; optional verification uses the existing rules.

To finish, use `update --status verified` with the current claim/revision. It
requires all declared scopes and named checks, a reviewer different from the
claim owner, the current epoch, and the same attempt/dependency revisions. A
verified inventory means that inventory is reviewed; it does not mean its code
passed gameplay tests. Task counts are not code-coverage percentages.
The latest result for each scope/check must pass; an earlier success cannot hide
a later failure. Earlier trials remain in the ledger.

The tracker never infers campaign sign-off from an empty queue or 27 completed
bootstrap tasks. Owners must add the discovered verification/repair work, then
the coordinator must create and audit the final-source closeout tasks required
by the plan. `all_tasks_verified_current` describes ledger tasks only.

## Initialization and checkpointing

The repository ledger is initialized already. For a new separate campaign only:

```powershell
python tools/qa_swarm.py --state PATH/state.json init --seed docs/qa/swarm/seed.json
```

Initialization refuses an existing ledger, including a damaged one. Back up and
diagnose damaged files rather than initializing over them. Checkpoint state and
portable evidence with the source at idle boundaries; keep personal/raw assets
ignored. Update README and RE_NOTES per AGENTS. Resume from the saved ledger after
compaction, restart or handoff. No external task service is necessary.

Verify tracker changes without starting the campaign or game:

```powershell
python -m unittest tools.test_qa_swarm tools.test_qa_batch -q
```

These tests use temporary ledgers, fake native artifacts and competing CLI
processes; they never acquire GameLab's runtime lock or run the game.
