# HammerwatchPlus

A modular co-op mod for **Heroes of Hammerwatch II**: a new class (the Firearms Specialist)
and the three HoH1 classes HoH2 lacks, Heroes of Hammerwatch 1 content (the Forsaken Tower
campaign, keys and ace chests, legendaries, mercenaries, titles, pets), new things to find in
the dungeons, fishing and farming in town, and co-op and quality-of-life fixes.

Every module ships as its own mod package, plus an all-in-one build. Everyone in a lobby
should run the same version of the same modules. Every module needs `core`; `goldpet` also
needs `pets`.

## Modules

### Classes and combat

| Module | What it does |
|---|---|
| `firearms` | The **Firearms Specialist**, a new class. Guns fire from a clip that counts down per shot and reloads (automatically at 0, or with the Reload skill, which a dodge cancels); mana pays for gadgets. A rifle (30 rounds, 3-round bursts; the Grenade Launching Rifle has an under-barrel grenade launcher, the Flamethrower Rifle a mana-fed flamethrower held on right click, the Full Auto Rifle a wild full-auto spray) or pistols, one or two (10 rounds each, 20 dual), or Hand Cannons (half a pistol's rate, 1.5 times its damage, 6 rounds; with a pistol, a pistol-cannon-pistol burst). Base kit: Reload and Frag Grenade, whose orbs give Explosive Reload, Over-Reload's timed perfect reload, and Stun, Incendiary or Gas grenades. Four specializations, each with orbs: **Marksman** (Snipe, Critical Aim), **Demolitionist** (Rocket Launcher, Ordinance Hoarder), **Assault** (Double Barrel Burst, Adrenaline) and **Engineer** (Deploy Turret, My Turret!). New characters start with a Service Pistol. Details: `mods/firearms/README.md`; design: `docs/design/firearms.md`. |
| `specs` | A **4th specialization** for six vanilla classes, one active and one passive each, with orbs: **Deadeye** Ranger (Lightning Arrow, Gathering Winds), **Aerotheurge** Wizard (Thunder Orb, Static Charge), **Arcane** Sorcerer (Blink, Living Mana), **Winddancer** Rogue (Protective Gale, Second Wind), **Bannerlord** Warrior (Battlefield Standard, Righteous Crusade), **Branding** Warlock (Pyrebrand, Essence Extraction) and the **Devil Forgemaster** Priest (Necrotic Resurrection, Call of Heresy: raise the enemies that fall with their body intact, bosses included, as summons that keep their own skills; Sacrificial Penance at max Divine Favor). Icons and sounds are the user's picks (`art/specs/`). The Forgemaster's risen and body units are generated from the base game by `tools/make_forgemaster_risen.py` (gitignored; `doctor --fix` makes them). |
| `classes` | The HoH1 classes HoH2 lacks: **Thief**, **Gladiator** and **Witch Hunter**, three masteries each. The Thief's extra actives cast on core's Skill 4 key. The real HoH1 art comes from your own HoH1 install (`tools/import_hoh1.py classes`). |
| `weapons` | Twelve new endgame weapons (ilvl 35, four per slot) with new modifier profiles on vanilla visuals and attacks. |
| `weaponswap` | A second weapon set on a hotkey (default X): a 2 s channel standing still, cancelled by a dodge or a second press. |
| `summons` | Summons come through a floor change with the HP they had. The game already carries the Priest's Crusaders; this tops up any that go missing, and the `summons.all` setting covers every summon (wolves, Warlock minions). |

### Heroes of Hammerwatch 1

| Module | What it does |
|---|---|
| `campaign` | **The Forsaken Tower**: the HoH1 campaign (Mines to Battlements, 18 floors, 6 bosses), started from a portal in town. NG+ swaps in HoH1's NG+ bosses and enemies. With HoH1 installed, a second version plays the real HoH1 boss rooms and Battlements (`tools/import_hoh1.py campaign`). |
| `keys` | HoH1-style keys: every chest but the cursed ones needs a key of its tier. Keys drop in runs (a party can share a key pool), and the exit guard's General Merchant sells keys, bag slots and six trinkets to take into your next run. Also ace chests and seven red legendaries. |
| `mercenary` | HoH1's mercenary mode: once a class has a level-20 hero, a fresh character of it can enlist (`hwp merc enlist`), climb the ranks from Private to General for more gold and experience, and die for good. |
| `legacy` | HoH1-style class titles: your best hero of each class buffs every character. One "Title Bonuses" buff lists them, and Guild Hall > Titles shows every class. |
| `pets` | Pets level up (from kills, pickups, and farm crops at the feeding bowl) and learn utility skills. Per-pet pickup toggles, pet dyes at the tailor, pets wait outside puzzle rooms, and every HoH1 pet is in the Pet Shop (imported from your own HoH1 install). |

### Runs and dungeons

| Module | What it does |
|---|---|
| `puzzles` | Puzzle rooms are back on most floors (HoH2 ships 88 but never places them), and HoH1's Constellation puzzle is one they can roll, also in a clearing on forest and heaven floors. |
| `strongbox` | Path of Exile-style strongboxes: open one, a pack of the floor's enemies spawns (elites possible), clear it for the box's loot. |
| `abyss` | Abyss cracks: step close and waves crawl out, ending in elites (more in a bigger party). Clear them for a reward that grows the deeper the run goes. |
| `maps` | Three new layouts for the equipment-map drops: Goblin Warrens, Sunken Dungeon, The High Court. |
| `valuables` | Valuables (vases, chalices, gems, furs, scales: the pickups that turn straight into gold) are worth twice their vanilla gold. |
| `wavemode` | **Wave Arena**: a survival arena started from a statue in town; every boss kill raises your arena rank, which is the arena's NG+ level next time. |

### Town

| Module | What it does |
|---|---|
| `fishing` | Six fishing spots on the town coast (a timing minigame), more in the water of run floors' potion wells (always one in a boss room), greyed on the map once fished out. A pirate sells bait, rods and fish traps from the trading post's wreck, later its boat. Fish are swords, sell for bet tokens and can be eaten (100 HP per star). |
| `farming` | The town's field grooves become farm plots: food crops and four Holy Herb strains grow with each completed run, faster when watered (the farmer sells the can and seeds; the well refills it). Smoke a herb for a buff that lasts 10 floors, or roll it into a joint: an off-hand with 5 puffs that a friend can take from you, with smoke that fills the room. |
| `gambler` | A gambler in the tavern plays Higher/Lower for gold. He buys crops and herbs for gold and fish for bet tokens, and rerolls equipped gear for 2000 gold × item level, or 1 bet token per 5 item levels. |
| `goldpet` | A pet vendor in the Hunter's Lodge sells the Gold Collector cat, with two upgrades (materials and scrolls, then valuables). |
| `stash` | A Sort button on the town stash: by class, then weapon type, then item level. |
| `laststats` | The last run's stats for the whole party, on a notice board by the town fountain. |

### Co-op and quality of life

| Module | What it does |
|---|---|
| `groupcombo` | A party-wide combo bonus that grows with how many players are in combo, and brief invulnerability when everyone is. |
| `architect` | Any player can pick and pay for Architect alterations; the host's picks are split across the party. Seven HoH1 challenges discount them, down to free. |
| `droptrade` | Drop equipment on the ground for friends: a Drop button (Q) next to Destroy in the inventory. |
| `deathrecap` | Who killed you: the top damage sources of the last 10 s, on screen and in chat. |
| `bufftips` | Hover a buff icon to see what it does and how many seconds it has left. |
| `chatlinks` | Linked items stay in chat with their slot and item level; `hwp link` links an equipped item. |
| `colors` | Colour-blind and high-contrast tints for enemy and friendly projectiles (player menu > Plus tab). |
| `core` | Required by every module: settings (the Plus tab and the `hwp` console command), save data and networking. It also adds keys 4, 5 and 6 for a class's 4th to 6th active skill, a Plants & Herbs section in the Materials tab with Eat and Roll actions, a warning on orbs that close off other orbs, the use key picking up a dropped item before it talks to an NPC, and "Mm-hmm!" hats (a quarter of rare and epic hats play the Material Trader's "mm-hmm" on every crit, for everyone). |

Each module's full spec and test checklist is in `mods/<id>/README.md`.

`mods/gamelab-*` are GameLab test harnesses, not player content. `build.py` never packs
them; they are only linked into the GameLab environment.

| Harness | What it does |
|---|---|
| `gamelab-probe` | The `gl` console command channel, read-only state probes, heartbeat. |
| `gamelab-hands` | Action verbs for the `gl` channel (start a mission floor, ...). Requires probe. |
| `gamelab-pilot` | Bot API for the Pilot. Requires probe and hands. |
| `gamelab-reload` | Logs a mark from its constructor, so the `reload-mark` scenario can tell whether an edited script was picked up without a restart. |

## Installing (players)

No releases are published yet; until then, build the packages yourself (see Developing,
`python tools/build.py`).

1. Take the `.bin` files you want from `dist/` (or `HammerwatchPlus-All.bin` for everything).
2. Drop them into `<Steam>/steamapps/common/Heroes of Hammerwatch 2/mods/`.
3. Start the game, open **Resource Mods** and enable them. Everyone in the lobby does the same.
4. In game, open the console (the key left of 1) and type `hwp help` for the commands and settings.

Workshop uploads will follow once the modules settle.

## Class planner

The class designs live in a local web page: every class's kit, specs and orbs from the game
data, the Firearms Specialist's full design, and a 4th specialization for each of the other
classes (Rogue and Sorcerer: Zak; Warrior and Warlock: Colin; Ranger and Wizard: Noah). Six
of them are built in `mods/specs`, and their planner records show the in-game numbers and
whether each skill and orb is built or tested. The Paladin's and Priest's are still designs.

It needs only Python 3 (no game, no packages):
- **Windows:** double-click `planner.cmd`.
- **Linux / macOS:** `./planner.sh`.
- **Anywhere:** `python -m planner` (or `python3`) from the repo root.

Edits are saved as JSON files under `planner/data/`; commit and push them. More in
`planner/README.md`.


## Status

- Every solo step of the in-game test plan has a `gamelab/scenarios/plan-*.json` scenario.
  As of 2026-10-18 they all pass in GameLab except Weapon Swap's "only you can pick it up",
  which needs a real lobby. The Firearms Specialist's checks (`plan-t14`, `plan-firearms-*`)
  last passed on 2026-10-19 and 2026-10-20.
- The co-op steps need two players: GameLab runs one game, and HoH2 only connects through
  Steam/GOG lobbies.
- GameLab is pinned to build 25932569 (since 2026-10-19).
- Firearms still to do: the two base passives (the old Scavenger and Steady Hands stand in)
  and final icons (the current ones are placeholders from `tools/make_firearms_icons.py`).
- Firearms gained the Hand Cannon, the Flamethrower Rifle and the Full Auto Rifle on
  2026-10-20 (`plan-firearms-cannon`); the rifle is now the Grenade Launching Rifle.
- Built on 2026-10-21: the 4th specs of the Ranger, Wizard, Sorcerer, Rogue, Warrior and
  Warlock (`mods/specs`). `plan-specs` passes all six (80 checks, after the code review's fixes). Not yet tested: what
  needs a second player (teammates in Protective Gale and Shared Breath, the standard's
  allies, Martyr's Banner, Mana Conduit). The world sprites (brand sigil, Hellfire Claw, the standard, the
  Tempest orb) are in. The icons are the user's picks over three rounds (`art/specs/override/`, `tools/icon_art/sp.py`,
  `sp_r2.py`, `sp_r3.py`); the Arcane and Aerotheurge emblems keep their placeholders by choice. The
  sounds are the user's picks too (`art/specs/AUDIO.md`; Void Barrier's save silent). Still to do: balance (pick them in the audio picker, `art/specs/AUDIO.md`).
- 2026-10-21: the Ranger's and Wizard's 4th specs now match Noah's PR #4 version in the planner:
  **Deadeye** (Lightning Arrow; Gathering Winds gives a Tailwind stack every 5 kills, each lasting
  4 s on its own, +2-4% Action Speed a stack) and **Aerotheurge** (Thunder Orb; Static Charge gains
  a stack per spell cast, plus one on its first crit, and a new Lightning Rod orb). The ids are kept, so
  saves still work. `plan-specs` passes (run `20261021-212606`, 17 checks). The crit stack is not
  tested, because the lab can't force a crit.
  The Paladin's 4th spec is still being designed.
- 2026-10-21: the Warlock's **Essence Extraction** now matches the planner (the user's version of
  Colin's design). Magic weapon hits (every arcane-tagged weapon) gain Essence once per 2 to 1 s, and
  Essence from a Pyrebranded enemy counts twice (two stacks; Drain Essence's bleed, health and mana
  twice). The old +max Essence and the melee-on-branded-elites gain are gone. Reading "trigger twice"
  that way is assumed. `plan-specs` passes (run `20261021-232748`). Known flaky: Lightning Arrow's
  Tailwind Catch caught 0 to 3 of 3 returning arrows across five runs (`storm_catch` failed twice).
- 2026-10-22: the Priest's 4th spec, the **Devil Forgemaster**, is fully designed in the planner
  (Necrotic Resurrection, Call of Heresy, Heresy as its own stack, which bosses can be raised).
  Sacrificial Penance, the form Necrotic Resurrection takes at max Divine Favor, has its own
  planner entry (new `alt_of` field): mana 50, sharing Necrotic Resurrection's cooldown. Its
  icons are in the picker (`tools/icon_art/sp_pri.py`, then `sp_pri2.py`): the second pass on
  the user's picks, plus the emblem, four orbs and the eating status; all 11 settled in
  `art/specs/override/`, and shown in the planner). Penance consumes the Favor.
- 2026-10-22: the **Devil Forgemaster** is built (`mods/specs`, `Forgemaster.as`). Any enemy death on
  the floor rolls an intact body (green glow on the Forgemaster's own screen); Necrotic Resurrection
  channels on it (3 s, 5 s elite, 10 s boss) and raises a copy of that enemy on your team with its own
  skills at 50-100% health and damage (at least 120 health), up to 2-4 at once, decaying and never
  healing, leash-teleporting
  like other summons. Heresy +1/+2/+3 per raise, refused at 5; at max Divine Favor the same key is
  Sacrificial Penance (50 mana, removes the level's 1-3 plus 1 for an elite body and 2 for a boss body).
  The four orbs are in. The risen come from `tools/make_forgemaster_risen.py`: one risen and one body
  unit per raisable enemy of the base game (141 units, the 10 non-final bosses included, at 3000-8000
  health with their arena-only skills stripped and their player-only targeting opened up), checked for
  well-formed XML and regenerated by `doctor --fix`. Tested by `plan-forgemaster` (run `20261022-102006`:
  all 141 units raised, attack, follow and leash-teleport, seven of them support units that only buff;
  the forge, Penance, Heresy and decay steps pass; that run's lunge and bosses steps failed on chance,
  0 lunges in 25 bodies at 16% and the Face's first spew after its 15 s window) and
  `plan-forgemaster-bosses` (run `20261022-084131`: Penance, Heresy, the lunge, all ten bosses raised,
  attack, follow and leash). The later fair-die check, the 40 bodies and the 25 s boss window passed in
  runs `20261022-114918` and `20261022-120742`, both INVALID under the focus rule (a Razer notification
  window took the foreground), so they are measured but not citable; a valid re-run is pending. Balance
  is a first pass.
- Designed in the planner, not built, and parked for later: an "Echoes of Hammerwatch I"
  (formerly "HoH1 Remastered") 5th spec for every vanilla class (the Rogue's from the HoH1
  Thief, the Warrior's from the Gladiator), one active and one passive of HoH1's that HoH2
  lacks. The icons are wired up (`tools/import_hoh1.py classes`).
- Parked on 2026-10-21: the Thief, Gladiator and Witch Hunter are hidden from character
  creation (`HWP::HideClass`, run `mod-classes-hidden`). The planner shows them on a second
  "HoH1" row with the six original HoH1 classes, whose kits are the HoH1 ones
  (`tools/planner_hoh1.py`), with armor-only gear and orbs still to design.
- What each session changed, with the GameLab run behind every claim, is in
  `docs/RE_NOTES.md`. The HoH1-to-HoH2 trinket comparison is a private web app outside the
  repo; its link is there too.

## GameLab

GameLab is the test harness: it boots a sandboxed copy of the game hidden and muted,
drives it through its own scripts (no real input, no focus steals, never touching your
config or saves), and scores what happened. Use the `gamelab` skill to run it.
Before merging to main, run `python -m gamelab run mod-all --mode lab` (every content
mod loaded together; GUI textures must be power-of-two sized or the game won't boot).

## Developing

Requirements:
- Windows, with Steam running.
- Python 3.10+ with [uv](https://docs.astral.sh/uv/).
- gcc from mingw-w64 (x86_64), which builds the GameLab capture shim.
- HoH2 installed.
- HoH1 optional: with it, doctor imports the HoH1 content (pets, levels, campaign, class art).

```
python -m gamelab doctor              # first thing on a new clone: checks every prerequisite
python -m gamelab doctor --fix        # uv sync, back up + verify your saves, bootstrap.py (gamecode/, tools/bin/),
                                      # env_link.py, class_units.py, the HoH1 imports when HoH1 is found,
                                      # make_pet_dyes.py, then one smoke boot (null-payload, hidden)
python -m gamelab doctor --confirm-saves   # only if --fix printed AMBIGUOUS save lines and the backup is still what you want
python -m gamelab doctor --hoh1 "D:\Games\Heroes of Hammerwatch" --fix   # HoH1 not found automatically: say where it is
python -m gamelab doctor --no-hoh1    # you don't own HoH1: skip its content, stop asking
python -m gamelab doctor --smoke      # boot null-payload again; a failure names its cause (antivirus, GPU, cores)
python tools/build.py                 # pack dist/HWP-<module>.bin + dist/HammerwatchPlus-All.bin
python tools/hwr_archive.py --help    # low-level archive tool (list/extract/pack HW2R and HWRR)
python tools/icon_art/render.py all   # skill icon ideas in the vanilla style (tools/icon_art/README.md)
python -m planner                     # the class planner in your browser (or planner.cmd / ./planner.sh; planner/README.md)
python tools/import_hoh1.py pets|levels|campaign|classes   # HoH1 content by hand (doctor --fix runs all four)
```

Mods live in `mods/<id>/`. Conventions are in `docs/modules.md`, the archive format in
`docs/archive-format.md`, the script hooks in `docs/hooks.md`.

HoH1 assets are never committed. `tools/import_hoh1.py` writes into gitignored
`hoh1_import/`, and `build.py` leaves it out of packages unless `--with-local`, so each
player imports it themselves.

## License

MIT. Game assets belong to Crackshell.
