# HammerwatchPlus agent instructions

These rules apply to every coding agent. Start with the [GameLab quickstart](gamelab/README.md)
for setup and commands, and the [regression guide](docs/qa/REGRESSIONS.md) for choosing
cases, interpreting failures, and continuing the recorded QA work. The detailed
[GameLab skill](.claude/skills/gamelab/SKILL.md) is ordinary Markdown and can be read by
any agent; it does not require Claude.

## Safety and coordination

- Run the game only through `python -m gamelab run <scenario> --mode lab`, using the
  project environment described in the quickstart. The CLI defaults to visible `watch`
  mode, so always supply `--mode lab`. Check `doctor` before using a new machine/session.
- Never launch the user's install directly or modify its config, Steam/local saves,
  `%LOCALAPPDATA%/HeroesofHammerwatch2`, or install `res/`, unless the user explicitly
  requests that action. Keep all launcher isolation checks enabled.
- No real input or focus changes: no `SendInput`, `keybd_event`, `mouse_event`,
  `SetCursorPos`, `SetForegroundWindow`, or `bring_to_front`. Use GameLab's posted-input
  and in-engine command APIs.
- One runtime owner and one GameLab run at a time, machine-wide. The lock protects game
  lifetime, not source files. Freeze gameplay, harness, bot, scenario, and tool sources
  during a native run/serial queue. Stage drafts under ignored `gamelab/results/` and
  apply reviewed changes only at a clean boundary. Deliberate scenario-owned
  `write_*_file` tests are the documented, restored exception.
- Respect refusals: exit 2 is preflight, 3 build mismatch, 4 held lock/dirty teardown,
  5 INVALID, and 6 TIMEOUT. Diagnose the cause; do not bypass gates to obtain a pass.
  Reset only after accounting for the owner and cause. Never reset another agent's run.
- Do not re-pin a changed game build or restore real saves as a routine test fix.
  Follow the quickstart's build/save decision rules and existing user authorization.

## Changes and evidence

- Preserve unrelated user edits and authored balance/owner decisions. Source review,
  setup acknowledgements, forced-state measurements, and ordinary gameplay are distinct
  evidence scopes; label them accurately.
- Read `run.json` verdict, assertions, error, and teardown before interpreting results.
  A failed setup/contract does not establish a gameplay defect. Inspect actual screenshots
  before describing them. Retain failed/flaky trials and their bounded trial counts.
- Cite the pinned build, run ID, expected source, observed effect, and tested source
  revision/fingerprint. A historical pass is not automatically a current-source pass.
  The regression guide explains the raw files and portable committed evidence.
- After adding/changing verbs, regenerate `docs/generated/verbs.md` with
  `python tools/list_verbs.py` and check it with `--check`.
- Update `README.md` and `docs/RE_NOTES.md` at the end of each work session. Keep current
  checkpoints separate from historical ledger entries and state unfinished work plainly.

Game scripts/data are generated under `gamecode/`; player modules live in `mods/`.
See [module conventions](docs/modules.md), [hooks](docs/hooks.md), and the
[planner](planner/README.md) for their respective source contracts.
