# Class planner

A local web page for designing the HammerwatchPlus classes: every vanilla class's base kit,
specs and orbs (read from the game data, with each level's quality and numbers), the three
ported HoH1 classes, the Firearms Specialist's full design (doctrines, orbs, grenade,
arsenal, clip and reload, gun attributes, budget), and a 4th specialization slot for every
other class.

## Open it

- **Windows:** double-click `planner.cmd` in the repo root.
- **Linux / macOS:** run `./planner.sh` from the repo root.
- **Anywhere:** from the repo root run:

```
python -m planner                 # opens http://127.0.0.1:8737/ in your browser (python3 on Linux)
python -m planner --port 9000     # another port (0 picks a free one)
python -m planner --no-browser
```

Python 3.10+ and nothing else: no packages, no game install, no `gamecode/`. Keep the
window open while you use the page; Ctrl+C (or closing it) stops the server.
`#<class id>` at the end of the address opens one class, for example `#ranger`.

## Where edits go

Every record is one file, `planner/data/<collection>/<id>.json`, and a Save in the page
writes it straight away. Commit those files like any other change, and pull to get other
people's. The page checks for changes every 2 s, so a `git pull` or a hand edit shows up
without a reload.

| Collection | Holds |
|---|---|
| `classes` | each class: stats, gear, base kit, specs and their orbs (read-only game data); the class notes field |
| `doctrines` | specializations you design: the Firearms doctrines and each class's 4th (`spec4: true`; `owner` is who is designing it) and its Echoes of Hammerwatch I 5th (`remastered: true`, files `<cls>-hoh1*`) |
| `skills` | skills in those specializations |
| `mods` | new orbs, on a new skill or on a vanilla one (`skill` is its id) |
| `weapons`, `stacks`, `attributes` | Firearms only: arsenal, clip and reload, gun attributes |
| `reference` | `vanilla`: the Firearms budget targets; `spec4-brief`: the brief shown on a class whose 4th spec has an owner |

A record with no `cls` belongs to the Firearms Specialist.

## The HoH1 row

The class bar's second row holds the parked HoH1 classes (`row: "hoh1"` on the class record):
the three ported ones (Thief, Gladiator, Witch Hunter, built in `mods/classes` but hidden from
character creation) and the six original HoH1 classes HoH2 remade, `hoh1_<cls>.json`. Those
six are written by `tools/planner_hoh1.py` from a local HoH1 install (read only; `--check`
reports drift): HoH1's attack, three actives and three passives with HoH1's numbers per
level and HoH1's stats, in our own words. HoH1 had no weapons and no orbs, so they start with
armor only, and their orbs are `mods` records on those skill ids.

HoH1's Mercenary mode sold one fixed version of a class's skill to a mercenary of any class;
each one that plays differently from the skill's top level is an orb idea,
`mods/hoh1-merc-<class>-<skill>.json`, with the HoH1 numbers and the top level's in its notes
(`hoh1_file` is the Mercenary sval). `mods/hoh1-cut-*.json` and `hoh2-cut-*.json` are versions
the games shipped commented out (Remedy's ally aura, Vicious Cuts on skill hits, Flurry of
Blades' extra strikes).

## Status and the class dots

A record's status runs idea, designed, built, tested, finished. The dot on a class's tab sums
up that class's own records (its 4th spec, skills and orbs; for Firearms also its weapons and
stacks; the ported and HoH1 classes also their class `status`), leaving out the parked Echoes
of Hammerwatch I specs:

- red: anything is still an idea or only designed, or a vanilla class has no 4th spec yet;
- yellow: everything is built or tested, but not yet balanced and signed off;
- green: everything is finished.

## Icons

`web/icons.png` and `web/icons.json` are the skill and orb icons, cut from the game's
atlases (vanilla, Firearms, and the HoH1 classes' committed placeholders) by
`tools/icon_art/planner_icons.py`, which needs `gamecode/`. With the HoH1 art imported
(`python -m gamelab doctor --fix`), it also writes the git-ignored `web/icons.local.png`,
which the server sends instead. A record with `hoh1_icon` (`"<cls>/<skill>"`, a key of
`HOH1_REMASTERED_ICONS` in `tools/import_hoh1.py`) takes its icon from the HoH1 Remastered (now Echoes of Hammerwatch I)
sheet, `mods/classes/players/hwp/remastered/icons.png`; `hoh1_file` names its HoH1 sval.
