# GameLab: start here

GameLab is a Windows CLI harness for testing mods against the installed HoH2 game.
Scenarios are JSON, bots are Python, and verdicts/measurements are JSON or JSONL.
An agent with filesystem and process access can use it without this chat history.

Read [AGENTS.md](../AGENTS.md) first. This is the short operational guide; the
[detailed skill](../.claude/skills/gamelab/SKILL.md) documents scenario steps,
fixtures, bot authoring and troubleshooting.

## First session or fresh clone

Use Windows with HoH2 installed and Steam running. Python 3.10+, uv, a supported
GPU and a mingw-w64 x86_64 compiler are required. Doctor checks prerequisites and
supports the local compiler locations documented in the root README. Native runs
need Windows process visibility; a restricted sandbox may need execution access
outside that sandbox. Preserve all isolation checks when resolving a refusal.

From the repository root in PowerShell:

```powershell
uv sync
uv run python -m gamelab doctor
# Read doctor's report before applying fixable missing setup:
uv run python -m gamelab doctor --fix
```

Doctor prepares ignored game dumps, tools, environment links, fixtures and
Forgemaster risen/body units (`tools/make_forgemaster_risen.py`). Its
save-backup and optional HoH1 choices are explained in the detailed skill. Respect
existing machine-local answers. Ask only for an unanswered HoH1 choice or ambiguous
saves; do not invent paths, skip an owned install, manually write confirmation
stamps or restore real saves. A doctor smoke is setup evidence only.

After setup, use `uv run python` or `.venv/Scripts/python.exe` consistently.
Regenerate ignored setup on another machine. Never commit imported game assets,
personal saves or machine-local settings.

## Discover and run

```powershell
uv run python -m gamelab list
uv run python tools/qa_batch.py --fingerprint
uv run python tools/qa_batch.py --label smoke-001 --dry-run null-payload mod-all
uv run python tools/qa_batch.py --label smoke-001 null-payload mod-all
```

Use a new label for each actual batch. Dry-run validates all scenario names and
prints ordered commands/source without launching or writing results. Direct runs
are supported too:

```powershell
uv run python -m gamelab run mod-all --mode lab
```

Always pass `--mode lab`: the direct CLI defaults to visible watch mode. One native
run at a time across all agents/terminals. Freeze `mods/`, `gamelab/` and `tools/`
during a batch; prepare proposed edits elsewhere. The batch helper records source
before/after each case and stops on failures, missing results, dirty teardown,
errors, partial results, build drift or source changes. It never resets, retries
or re-pins automatically. Its `--help` describes local journal and stop-file paths.
Stop files are honored between cases; an unfinished queue returns nonzero.

Select checks using [the regression map](../docs/qa/REGRESSIONS.md). Some `qa-*`
scenarios are investigations with known setup failures; running all of them is
not a defined green regression suite. Scenario `timeout` is a budget, not the
wall-clock cap: the launcher uses `outer_timeout` or normally three times `timeout`.

## Read the result before making a claim

Each native run writes `gamelab/results/<timestamp>-<scenario>-lab/`:

| File | Use |
|---|---|
| `run.json` | Final launcher verdict, assertions, errors, partial/drift flags and teardown/isolation result |
| `inner.json` | Inner runner observations and assertions, saved progressively; does not replace outer guards |
| `bot-results.jsonl` | Completed bot returns, controls and measurements, when bots ran |
| `bot-<name>.json` | Optional latest snapshot named from the sanitized bot step; JSONL preserves per-invocation results |
| `gl.jsonl` | In-engine command/reply telemetry |
| `runner.out.txt`, `logs/` | Tracebacks and native logs, including earlier fixture passes |
| `shots/` | Captured frames; inspect an image before describing it |

Each bot-results line has `bot`, `kwargs`, `pass`, `assertion_index` and `result`.
The runner preserves the completed return before expected-value scoring and adds
`result.intents`. A crashing bot may have no completed return.

Require exit 0, outer PASS, no failed assertions/error, clean teardown,
`partial=false` and no build drift. Inspect each aggregate bot `ok` result's rows.
A binding, acknowledgement or counter alone does not prove damage, payment,
targeting, expiry or persistence. Forced-state measurements do not establish an
ordinary run; compilation/load does not establish every module's behavior. Keep
failed attempts even when a corrected test later passes.

Neither `run.json` nor `inner.json` contains a global source fingerprint. The
batch JSONL records HEAD and the raw working-tree fingerprint before/after each
case, plus exit, run ID and failures. Its scope is `mods+gamelab+tools-v2`; docs
outside those directories are excluded. Line-ending edits can change this raw-byte
hash. Keep historical hashes attached to their own runs. A direct single run
needs separately recorded before/after source if it is used as source-pinned proof.

Exit 1 is a failed test to investigate. Exits 2/3/4/5/6 indicate preflight failure,
build mismatch, lock/dirty state, invalid run or timeout respectively. Read the
last result and detailed skill before acting. Wait for an active owner; reset only
after diagnosing stale/dirty state. Re-pinning a changed game build is a team
decision. Never bypass guards or start the install directly to resolve a refusal.

## Continue the paused sweep

Read the [checkpoint](../docs/generated/qa_pr_checkpoint.json), then the
[regression map and known failures](../docs/qa/REGRESSIONS.md). Family inventories
hold granular evidence limits for the original sweep. Later main adds Priest
Forgemaster and a merged-tree review in RE_NOTES; the old six-spec matrices do not
cover that new spec. The long [ledger](../docs/QA_OVERNIGHT.md) preserves
history; old tables are not the current queue. The full sweep remains paused
until requested. Handle one bounded reproduction and affected neighbors at a time;
after a recurring setup failure, record its cause and defer it instead of retrying
unchanged or expanding the harness indefinitely.

Deferred source drafts are available in fresh clones through the
[portable bundle](../docs/qa/deferred/README.md). They remain unapplied/unverified.
Raw historical logs/screenshots remain local: a fresh clone has committed summaries
and can generate new evidence, but cannot recover absent raw logs.

To extend the harness, copy a relevant scenario and inspect its bot/expected rows.
Follow the detailed skill's authoring instructions and the generated
[verb reference](../docs/generated/verbs.md). Regenerate it with
`uv run python tools/list_verbs.py` when registrations change. Hand off the exact
reproduction, source, evidence and limits, and update root README and RE_NOTES.
