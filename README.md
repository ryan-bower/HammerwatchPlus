# HammerwatchPlus

Co-op mods for **Heroes of Hammerwatch II**: a new class, the Heroes of Hammerwatch 1 classes and
campaign, new dungeon finds, fishing and farming, and co-op fixes.

**Documentation:** [docs](docs/README.md) · **Features:** [docs/features.md](docs/features.md) ·
**Status:** [docs/status.md](docs/status.md)

## Packages

Twelve packages, each working alone, plus `HammerwatchPlus-All`:
Quality of Life · Co-op Play · Auto Aim · Firearms Specialist · Fourth Specializations ·
HoH1 Classes · Keys and Ace Chests · The Forsaken Tower · Challenge Modes ·
Dungeon Loot and Encounters · Town Life · Pets.

Every module can be switched off in game, on the player menu's **Plus** tab.

## Install

Double-click `run.cmd`. It builds every package, deploys it and starts the game through Steam.
More in [docs/install.md](docs/install.md).

## Develop

```
uv sync
uv run python -m gamelab doctor --fix
uv run python scripts/test.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. Game assets belong to Crackshell.
