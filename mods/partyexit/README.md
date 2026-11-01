# Party exit (`partyexit`, Co-op package)

Issue #75. Vanilla loads the next floor only when every living player stands in the exit's
area (`WorldScript::LevelExitAreaNext.Use`, ".exit.notall": "You must gather your party before
venturing forth!"). With this mod the exit opens once `partyexit.share` percent of the living
party is there, rounded up:

| living players | Half (50) | Two thirds (66, default) | Three quarters (75) |
|---|---|---|---|
| 1 | 1 | 1 | 1 |
| 2 | 1 | 2 | 2 |
| 3 | 2 | 2 | 3 |
| 4 | 2 | 3 | 3 |

Players left behind go to the next floor with the rest, like dead players do in vanilla.
Too few at the exit: the announce names how many are needed ("Gather your party: 3 of 4 must
stand at the exit, 2 there now"). `partyexit.enabled` off is the vanilla rule.

- Override: `scripts/WorldScript/Missions/LevelExitAreaNext.as` (`.orig` beside it); `Use`
  asks `HWP::PartyExit::Refusal`. `LevelExitAreaJump` inherits it. A player counts as at the
  exit when inside any of its areas (vanilla needed each of them).
- Settings: `partyexit.enabled`, `partyexit.share` (host).
- `hwp partyexit [phantom <outside> [inside]]`: the share and what 1-4 players need. `phantom`
  adds living players to the count (outside / at the exit) so a solo game can test a party's
  exit; it resets with the level.
- Log: `[HWP:partyexit] exit refused: 1 of 3 at the exit, 2 needed`, `exit opens: ...`.
- Test: `python -m gamelab run fix-party-exit --mode lab`.
