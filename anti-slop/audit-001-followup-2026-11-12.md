# Audit 001 follow-up: approved finding 2

The user approved the proposed all-favorite empty-state correction. Only finding
2 was addressed; finding 1's runtime gates were not changed or bypassed.

## Result

The buyer now displays:

> All your bag equipment is favorited and protected from selling. Unfavorite an
> item in your inventory to sell it.

The message is selected only when favorites are enabled and every non-null bag
item is protected. Genuinely empty bags, mixed bags, disabled favorites and an
unopened buyer retain the vanilla text. The new text is localized through
`.hwp.favorites.empty`; no artwork, layout, colors or controls changed.

## Evidence and gate

- R-27 PASS (source): the empty state explains both the reason and next action.
- R-02/R-16 PASS: literal, actionable text, no em dash or marketing claims.
- R-35 BLOCKED: the existing Steam/save-path readiness refusals still prevent
  live compilation, input, screenshot and restart checks. No click-through or
  runtime pass is claimed. The delivery gate remains withheld, not passed.
- 47 focused tests pass through `scripts/test.py`, including the new source/text
  regression and existing package, settings, Workshop and serialization checks.
- The test-only engine scenario now declares 19 checks, adding five checks for
  all-favorite, mixed, disabled, empty and unopened-buyer text. Both the loose and
  packaged scenarios are updated but remain unrun.
- Quality of Life builds: library `20ba6f4bda7c`, 319 files, 473,141 bytes.
- Generated verb/settings checks and `git diff --check` pass.

The original audit's layout, typography and motion decisions remain unchanged.
No additional audit findings were fixed without approval.
