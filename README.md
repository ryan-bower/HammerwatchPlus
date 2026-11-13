<h1 align="center">HammerwatchPlus</h1>

<p align="center"><em>HammerwatchPlus for Heroes of Hammerwatch II, more classes, more dungeon, more town</em></p>

<p align="center">
<a href="https://github.com/ryan-bower/HammerwatchPlus/actions/workflows/test.yml"><img src="https://github.com/ryan-bower/HammerwatchPlus/actions/workflows/test.yml/badge.svg" alt="Test"></a>
<img src="https://img.shields.io/badge/python-3.14%2B-blue" alt="Python 3.14+">
<img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
</p>

---

**Documentation**: [docs/](docs/README.md)

**Source Code**: [github.com/ryan-bower/HammerwatchPlus](https://github.com/ryan-bower/HammerwatchPlus)

---

HammerwatchPlus is a set of twelve mod packages for Heroes of Hammerwatch II. Each works alone or
with the others.

The key features are:

- **A new class and new specs**: the Firearms Specialist, and a fourth specialization for eight
  vanilla classes.
- **The Forsaken Tower**: the HoH1 campaign, with keys, ace chests, legendaries and pets.
- **More dungeon**: puzzles, objectives, strongboxes, affixes, new weapons and trinkets, tougher bosses.
- **Town life**: fishing, farming, a gambler, roulette and a tavern.
- **Build benchmarks**: [five-second DPS above town training dummies](mods/dummydps/README.md),
  in Quality of Life; combined damage from all players and sources.
- **Co-op**: group combos, shared drops, party exits, and Architect alterations the whole party pays for.
- **All optional**: every module switches off in game, on the player menu's **Plus** tab.

Every module: [mods/README.md](mods/README.md).

## Requirements

- Windows, with Steam and Heroes of Hammerwatch II.
- [uv](https://docs.astral.sh/uv/), which brings Python 3.14.
- Optional: Heroes of Hammerwatch 1, for its original art and pets.

## Installation

To install a GitHub release without building (Python 3.11+ and `gh` required):

```console
python tools/install_release.py
```

This installs the latest stable release's verified all-in-one pack into the local Steam
HoH2 `mods/` directory, replacing old HWP binaries. Close the game first, then restart and
enable the pack in Resource Mods. See [releases](docs/releases.md) for tags and custom paths.

To build and launch the current source instead:

```console
$ git clone https://github.com/ryan-bower/HammerwatchPlus
$ cd HammerwatchPlus
$ run.cmd
```

`run.cmd` builds every package, starts the game in a new profile with them enabled, and backs up
your saves first. The first run also sets up the game files, which takes a few minutes. More in
[Installing](docs/install.md).

## Example

In game, open the console with <kbd>&#96;</kbd>:

```console
hwp help                      # every command and setting
hwp set salvage.yield 200     # salvaged gear gives double materials
```

Salvage a Rare item-level 20 sword, and the confirm now offers 6 Dust instead of 3.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the terms of the MIT license. Game assets belong to Crackshell.
