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

## Linux

Package building runs natively on Linux; Wine, Steam and the Windows GameLab setup are not
needed. Install [uv](https://docs.astral.sh/uv/) (recommended), or Python 3.10+ with
`venv`/`pip` (`sudo apt install python3 python3-venv python3-pip` on Debian/Ubuntu), then:

```console
$ ./build.sh                       # all packages and dist/HammerwatchPlus-All.bin
$ ./build.sh HWP-firearms --no-all # one package
$ ./build.sh --with-local          # include your imported HoH1 assets; do not publish
```

`build.sh` installs its dependencies into an isolated environment and forwards every
argument to `tools/build.py`; it runs from any directory. It does not run bootstrap, import
game assets, launch the game or touch saves. The builder refuses packages that need
base-generated content (class-swap units, pet dyes, Forgemaster bodies) while
`gamecode/sdk/hoh2/` is missing: copy that ignored tree from a prepared checkout, or let the
Linux GameLab bridge bootstrap it. HoH1 asset discovery accepts both `HWR.exe` and the native
Linux `HWR`; its game archive is required either way.

GameLab on x86-64 Linux is an experimental, pinned Proton/Xvfb bridge: `./gamelab.sh setup`,
`./gamelab.sh doctor --fix`, then `./gamelab.sh run <scenario> --mode lab`. It never uses the
player's Proton prefix or display, and no isolation check is bypassed. See
[docs/gamelab-linux.md](docs/gamelab-linux.md).

## Where to look

- Mods: `mods/<id>/`, conventions in [docs/modules.md](docs/modules.md).
- Tools: `tools/` (build, deploy, saves, release), `tools/generate/` (content generators),
  `tools/hoh1/` (HoH1 importer), `tools/art/`.
- Everything else: [docs/README.md](docs/README.md).

HoH1 assets are never committed: each player imports their own.
