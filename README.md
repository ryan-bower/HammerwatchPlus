# HammerwatchPlus

> **QA checkpoint (2026-10-22): paused at the user-requested PR boundary.** The full sweep is incomplete. Scoped passes: fourth specs60/60 rank cases and61/65 orb-quality cases; Firearms60/60 ranks and74/75 orb qualities; HoH1 imports29/39 skills and136/191 ranks;9/9 selected-mastery saves. Five orb cases need real co-op. All31modules have load evidence, with broader feature/lifecycle work open. Earlier QA summaries below are historical snapshots. See [the authoritative checkpoint](docs/generated/qa_pr_checkpoint.json) and [QA ledger](docs/QA_OVERNIGHT.md).


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
| `specs` | A **4th specialization** for six vanilla classes, one active and one passive each, with orbs: **Deadeye** Ranger (Lightning Arrow, Gathering Winds), **Aerotheurge** Wizard (Thunder Orb, Static Charge), **Arcane** Sorcerer (Blink, Living Mana), **Winddancer** Rogue (Protective Gale, Second Wind), **Bannerlord** Warrior (Battlefield Standard, Righteous Crusade) and **Branding** Warlock (Pyrebrand, Essence Extraction). Icons and sounds are the user's picks (`art/specs/`). |
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
| `gambler` | A gambler in the tavern plays Higher/Lower for gold. He buys crops and herbs for gold and fish for bet tokens, and rerolls equipped gear for 2000 gold Ã— item level, or 1 bet token per 5 item levels. |
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

- 2026-10-22 overnight QA remains incomplete. Eight scoped
  gameplay repairs have passing reproductions: Shadow Strike, Riposte, per-gun magazine
  crit, Hoarder HUD cleanup, Thunder Orb cast attribution, returning-arrow catches,
  custom weapon-family stash sorting and Dragon's Breath patch persistence
  (`20261022-085158`). All 14 required regression scopes passed at their recorded
  fingerprints; later changes only extend read-only QA telemetry. Production sources
  and release payloads remain unchanged after those passes;
  exact evidence and limits are in `docs/QA_OVERNIGHT.md` and `docs/generated/qa_*_inventory.json`.
- Current granular coverage: the six built fourth specs have 55 of 60 skill-rank rows
  with scoped passes and 5 partial; their 65 orb-quality rows have 47 scoped
  passes, 3 partial, 11 untested and 4 blocked on real allies. Firearms has 42 of 75
  orb-quality rows with scoped passes, 32 untested and 1 blocked; its 60 skill-rank
  rows have 10 scoped passes, 10 partial and 40 untested. The three hidden
  HoH1 ports each completed two ordinary floor transitions, but full boss/reward runs
  remain unverified; 4 of their 39 skills have scoped granular passes at 14 of 191
  positive-rank slots. These counts
  preserve the narrower effects measured in each row; they do not establish full coverage.
- The default build produced and verified all 32 archives in `dist/`: 31 content modules
  and `HammerwatchPlus-All.bin`, whose 955 entries exactly match their union. All-in-one
  SHA256: `8d42ca89b379f7bb4ada76085fa6cc1e5ec3c28d6aacbdd4970393c0ecf01274`.
  Every archive's metadata and decompressed payload were checked. The complete 31-module
  stack, UI/settings search, stash save/reload, Architect pricing and controlled event
  timeouts also have scoped passes. Older scenario passes below remain historical evidence.
- Every solo step of the in-game test plan has a `gamelab/scenarios/plan-*.json` scenario.
  As of 2026-10-18 they all pass in GameLab except Weapon Swap's "only you can pick it up",
  which needs a real lobby. The Firearms Specialist's checks (`plan-t14`, `plan-firearms-*`)
  last passed on 2026-10-19 and 2026-10-20.
- The co-op steps need two players: GameLab runs one game, and HoH2 only connects through
  Steam/GOG lobbies.
- GameLab is pinned to build 25932569 (since 2026-10-19).
- 2026-10-21: doctor and bootstrap also find a portable compiler in the ignored local
  toolchain cache, without changing the system PATH. Fresh-command doctor is green;
  the hidden smoke passed (`20261021-235153-null-payload-lab`). Setup details and checks
  are in `docs/RE_NOTES.md`.
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
  tested at that checkpoint; the overnight sweep now has native critical-hit regressions.
  The Paladin's and Priest's 4th specs are still being designed.
- 2026-10-21: the Warlock's **Essence Extraction** now matches the planner (the user's version of
  Colin's design). Magic weapon hits (every arcane-tagged weapon) gain Essence once per 2 to 1 s, and
  Essence from a Pyrebranded enemy counts twice (two stacks; Drain Essence's bleed, health and mana
  twice). The old +max Essence and the melee-on-branded-elites gain are gone. Reading "trigger twice"
  that way is assumed. `plan-specs` passes (run `20261021-232748`). Original flakiness: Lightning Arrow's
  Tailwind Catch caught 0 to 3 of 3 returning arrows across five runs (`storm_catch` failed twice).
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
- gcc from mingw-w64 (x86_64), which builds the GameLab capture shim. It can be on PATH,
  or extracted under `gamelab/fixtures/cache/toolchain/` as `mingw64/bin/gcc.exe` or
  `w64devkit/bin/gcc.exe`. Doctor and bootstrap prefer PATH, then those local copies;
  only compiler child processes get the compiler's bin directory added to PATH.
- HoH2 installed.
- HoH1 optional: with it, doctor imports the HoH1 content (pets, levels, campaign, class art).

After setup creates `.venv`, use `uv run python` in place of `python` below, or run
`.\.venv\Scripts\python.exe` directly, so GameLab uses the installed project dependencies.

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


## Resumed full sweep ? no time limit (2026-10-22)

The user removed the original overnight deadline and activated the goal again. Work remains in progress; the original deadline/final-hour notes below are historical. Verified scoped coverage now includes60/60 fourth-spec rank cases,49/65orb qualities (nine fresh Branding qualities awaiting granular audit; maximum combo failed),20/60 Firearms ranks,42/75orb qualities,62/191HoH1positive ranks and9/9mastery save/reload combinations. Native stat-only scopes remain separate from combat/cadence/mitigation.

Fresh full-stack `mod-all 20261022-111422` and minimal `null-payload 111454` compile/load checks passed with the read-only per-frame resource observer. `qa-firearms-ranks-base 111509` and `qa-specs-living-mana-coefficients 111830` passed; exact per-run hashes are in the ledger/journals. `qa-specs-branding-orbs 113033` now obtains strict fine-grid/native-ray geometry through normal walking but fails the maximum-combination check. `qa-classes-gladiator-hoh2-run 112028` reached Keep3 and died during objective travel; no class/encounter bug is inferred. Controlled endgame weapon tests112325/112427 failed native equip requirements before attack/parry testing: ilvl35 requirements use unbounded vector interpolation at34/9, not the high endpoint at level10. A QA fixture correction is staged; no production change is inferred from these setup failures.

The source is frozen during each serial GameLab batch. Remaining ranks/orbs, legal interactions, ordinary run lifecycles, UI/acquisition and module functional/persistence/failure paths remain required. See `docs/QA_OVERNIGHT.md` and `docs/generated/qa_overnight_summary.json`; previous repair regressions and all failures are retained.


## Historical resumed sweep checkpoint (2026-10-22; superseded above)

The full sweep has no time limit. Scoped native coverage is 60/60 fourth-spec rank rows and 61/65 orb-quality rows (four require true co-op), 60/60 Firearms rank rows and 71/75 orb-quality rows (three Reload rows await a corrected idle-timer test; one requires co-op), and 118/191 positive HoH1 ranks across 26/39 abilities. All nine selected-mastery save/reload combinations pass. These counts cover the recorded effects, not every amplitude, boundary, interaction, UI or ordinary lifecycle requirement.

Two additional gameplay repairs are verified: Branding no longer retains the Essence damage bonus after consumption, and Gladius now deals native weapon-scaled damage instead of zero. Gladius first-contact damage passes at all five ranks in `qa-classes-gladius-collision 20261022-145123`. Current full-stack load passes in `mod-all 145021`; all 31 modules also have standalone load evidence. Full module functionality remains incomplete.

The current serial batch is finishing Branding quality combinations and Sphere acquisition/UI prerequisites. Reload's expired negative input timer and Grimoire's stationary-glyph target distance are source-reviewed QA corrections awaiting native reruns. A Branding combination failed its clear-lane setup before any combat trial; it remains recorded and under investigation. Ordinary runs also need a source-correct reward-window input flow before boss/reward/save coverage can be claimed.

The earlier 32-archive package verification predates the Branding and Gladius repairs. Those archives are historical; current-source packaging and final regressions remain required. The detailed source epochs, original failures and remaining work are retained in `docs/QA_OVERNIGHT.md` and the generated inventories.
