# Contributing

Read [CLAUDE.md](CLAUDE.md) first: the rules for running the game and for claiming a fix works.

## Requirements

- Windows, with Steam and Heroes of Hammerwatch II.
- [uv](https://docs.astral.sh/uv/) (brings Python 3.14).
- gcc from mingw-w64 (x86_64) on PATH; `doctor` checks it.
- Optional: Heroes of Hammerwatch 1, for its content.

## Setup

```console
$ uv run python -m gamelab doctor         # what's missing
$ uv run python -m gamelab doctor --fix   # set it up: game files, tools, save backup
```

## Work

```console
$ uv run python tools/run.py              # build, deploy and play
$ uv run python tools/build.py            # build the packages into dist/
$ uv run python scripts/test.py           # offline tests; CI runs the same
$ uv run python scripts/lint.py           # ruff (optional; not in CI yet)
```

Before merging, boot every mod together: `uv run python -m gamelab run mod-all --mode lab`
([GameLab quickstart](gamelab/README.md)).

A change ends with a dated entry in [docs/status.md](docs/status.md) and its notes in
[docs/RE_NOTES.md](docs/RE_NOTES.md).

## Where to look

- Mods: `mods/<id>/`, conventions in [docs/modules.md](docs/modules.md).
- Tools: `tools/` (build, deploy, saves, release), `tools/generate/` (content generators),
  `tools/hoh1/` (HoH1 importer), `tools/art/`.
- Everything else: [docs/README.md](docs/README.md).

HoH1 assets are never committed: each player imports their own.
