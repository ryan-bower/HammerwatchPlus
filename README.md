# HammerwatchPlus

> **QA checkpoint (2026-10-22): paused at the user-requested PR boundary.** The full sweep is incomplete. Recorded original-sweep passes: six original fourth specs60/60 rank cases and61/65 orb-quality cases; Firearms60/60 ranks and74/75 orb qualities; HoH1 imports29/39 skills and136/191 ranks;9/9 selected-mastery saves. Five orb cases need real co-op. All 31 normal-release modules have load evidence, with broader feature/lifecycle work open. Earlier QA summaries below are historical snapshots. See [the authoritative checkpoint](docs/generated/qa_pr_checkpoint.json) and [QA ledger](docs/QA_OVERNIGHT.md).


A modular co-op mod for **Heroes of Hammerwatch II**: a new class (the Firearms Specialist)
and the three HoH1 classes HoH2 lacks, Heroes of Hammerwatch 1 content (the Forsaken Tower
campaign, keys and ace chests, legendaries, mercenaries, titles, pets), new things to find in
the dungeons, fishing and farming in town, and co-op and quality-of-life fixes.

The modules ship as twelve Steam Workshop packages, each of which works alone, plus an
all-in-one pack (`packages.json`; `docs/modules.md`, Packages):

| Package | Modules |
|---|---|
| `HWP-qol` Quality of Life | bufftips, chatlinks, stash, deathrecap, laststats, colors, waygates, weaponswap, summons, petrooms, legacy, goldworth, mmhmm, orbwarn, mapicons, attrclick |
| `HWP-coop` Co-op Play | groupcombo, architect, droptrade |
| `HWP-autoaim` Auto Aim | autoaim |
| `HWP-firearms` Firearms Specialist | firearms |
| `HWP-specs` Fourth Specializations | specs |
| `HWP-classes` HoH1 Classes | classes |
| `HWP-keys` Keys and Ace Chests | keys |
| `HWP-campaign` The Forsaken Tower | campaign |
| `HWP-modes` Challenge Modes | mercenary, wavemode |
| `HWP-dungeon` Dungeon Loot and Encounters | puzzles, objectives, strongbox, abyss, maps, weapons, trinkets, valuables, affixes |
| `HWP-town` Town Life | fishing, farming, gambler, roulette, tavern |
| `HWP-pets` Pets | pets (and petrooms, shared with Quality of Life) |
| `HammerwatchPlus-All` | every package |

There is no core mod to install. The shared code is a library (`mods/hwplib`, and the parts
`hwplib-luck` and `hwplib-classui`) that every package carries its own copy of; the game keeps
one copy of each file, so packages work alone and together. Everyone in a lobby should run the
same version of the same packages.

Every module can be turned off, and its settings changed, in game: open the player menu (inventory)
and go to the **Plus** tab. Key binds and the projectile colours (accessibility) are at the top;
below them each installed package is a row that opens to its modules, each with an On/Off switch
and its settings (2x valuables back to vanilla, fishing off, and so on). The search field at the top
finds any setting by a few letters of its name, value or description. Settings that change the game
for everyone are the host's in a lobby. The full list is generated in
[docs/generated/settings.md](docs/generated/settings.md); `hwp set <key> <value>` sets any of them
from the console. Two lab scenarios check the page: `mod-settings-sweep` clicks every row with
every module loaded, and `mod-settings-off` turns each module off and on again and checks what it
does in game. The HoH1 classes' switch has no effect while those classes are parked.

## Modules

### Classes and combat

| Module | What it does |
|---|---|
| `firearms` | The **Firearms Specialist**, a new class. Guns fire from a clip that counts down per shot and reloads (automatically at 0, or with the Reload skill, which a dodge cancels; the reload bar sits over the player); mana pays for gadgets. Rounds leave the gun for the point under the cursor, so diagonal shots land on the crosshair, and the gun model changes pose as you idle, fire, reload or use a gadget. A rifle (30 rounds, 3-round bursts; the Grenade Launching Rifle has an under-barrel grenade launcher, the Flamethrower Rifle a mana-fed flamethrower held on right click, the Full Auto Rifle a wild full-auto spray) or pistols, one or two (10 rounds each, 20 dual), or Hand Cannons (half a pistol's rate, 1.5 times its damage, 6 rounds; with a pistol, a pistol-cannon-pistol burst). Base kit: Reload and Frag Grenade, whose orbs give Explosive Reload, Over-Reload's timed perfect reload, and Stun, Incendiary or Gas grenades. Four specializations, each with orbs: **Marksman** (Snipe, whose aim time shortens per rank and whose Recoil Roll orb dashes you back along the shot; Critical Aim), **Demolitionist** (Rocket Launcher, Ordinance Hoarder), **Assault** (Double Barrel Burst, Adrenaline) and **Engineer** (Deploy Turret, My Turret!). New characters start with a Service Pistol. Details: `mods/firearms/README.md`; design: `docs/design/firearms.md`. |
| `specs` | A **4th specialization** for eight vanilla classes, one active and one passive each, with orbs: **Deadeye** Ranger (Lightning Arrow, Gathering Winds), **Aerotheurge** Wizard (Thunder Orb, Static Charge), **Arcane** Sorcerer (Blink, which crosses ledges and stairs; Living Mana, one pooled blue bar for health and mana), **Winddancer** Rogue (Protective Gale, Second Wind), **Bannerlord** Warrior (Battlefield Standard, Righteous Crusade), **Branding** Warlock (Pyrebrand, Essence Extraction) and the **Devil Forgemaster** Priest (Necrotic Resurrection, Call of Heresy: raise the enemies that fall with their body intact, bosses included, as summons that keep their own skills and run with you; the raise and Sacrificial Penance channels lock you in place with a beam; braziers and pyres burn off Heresy) and the **Generosity** Paladin (Pelor's Fury, Pelor's Blessing: Lay on Hands, Blessed Strike kills and Conviction build up to 10 stacks that strengthen all three; at 10 the Fury holds any one enemy, bosses included, in beams of light: stunned, its casts cut, armor and resistances 0, taking more damage; a Fury that can't take hold spends nothing; crops grow twice as fast and wild plots turn up twice as often while a Paladin of Generosity is in the party). Icons and sounds are the user's picks (`art/specs/`). The Forgemaster's risen and body units are generated from the base game by `tools/make_forgemaster_risen.py` (gitignored; `doctor --fix` makes them). |
| `classes` | The HoH1 classes HoH2 lacks: **Thief**, **Gladiator** and **Witch Hunter**, three masteries each. The Thief's extra actives cast on core's Skill 4 key. The real HoH1 art comes from your own HoH1 install (`tools/import_hoh1.py classes`). |
| `weapons` | Twelve new endgame weapons (ilvl 35, four per slot) with new modifier profiles on vanilla visuals and attacks. |
| `weaponswap` | A second weapon set on a hotkey (default X) or a controller button (default D-pad left): a 2 s channel standing still, cancelled by a dodge or a second press. |
| `autoaim` | Auto aim for the skills you aim with a reticle (Marked Shot, Leap, Firewall): it snaps to a nearby enemy in your aim cone and can fire by itself, and ready AOE skills can cast themselves when your mana allows. On for controllers by default, an option for mouse play; settings on the character menu's Plus tab (a remake of kearneyTim's controller auto aim). |
| `summons` | Summons come through a floor change with the HP they had. The game already carries the Priest's Crusaders; this tops up any that go missing, and the `summons.all` setting covers every summon (wolves, Warlock minions). |
| `petrooms` | Pets keep out of puzzle and trap rooms: while you are in one, your pet walks back along the way you came to the last clear spot and waits there; a pet that ends up in one walks back out and waits until you move on; one following you after a wait may cross a room to reach you. A puzzle unit, or traps on three spots (a glyph and its blast are one), within the room distance (`petwait.radius`, 120 px) make a room. Works for vanilla pets and for the Pets package's; a shared module, carried by both Quality of Life and Pets. |

### Heroes of Hammerwatch 1

| Module | What it does |
|---|---|
| `campaign` | **The Forsaken Tower**: the HoH1 campaign (Mines to Battlements, 18 floors, 6 bosses), started from a portal in town. NG+ swaps in HoH1's NG+ bosses and enemies. With HoH1 installed, the portal offers HoH1's own tower instead (`tools/import_hoh1.py campaign`): all 23 floors as HoH1 has them, the act floors built by HoH1's own floor generator, HoH1's boss rooms, level scripts and texts, for HoH2's classes; the Dark Citadel gains two Dark Halls and the two Battlements floors. HoH1's traps (spike, pressure, poison, frost, drain and confusion plates, flame jets, five kinds of glyph, wall shooters, arrow turrets, flame gargoyles, stalactites, falling bricks and bear traps, each with a warning first and picked by the floor's theme) and one teleporter pad per floor appear on generated floors, and the Dark Halls eyes confuse again. |
| `keys` | HoH1-style keys: every chest but the cursed ones needs a key of its tier. Keys drop in runs (a party can share a key pool), and the exit guard's General Merchant sells keys, bag slots and six trinkets to take into your next run. Also ace chests (opened with the red skull ace key), seven red legendaries, and a banner for everyone when a chest turns out to be trapped. Trinket, cursed and ace chests look grander the deeper the run goes, with unused chest art from the game's own sprite sheet. |
| `mercenary` | HoH1's mercenary mode: once a class has a level-20 hero, a fresh character of it can enlist (`hwp merc enlist`), climb the ranks from Private to General for more gold and experience, and die for good. |
| `legacy` | HoH1-style class titles: your best hero of each class buffs every character. One "Title Bonuses" buff lists them, and Guild Hall > Titles shows every class. |
| `pets` | Pets level up (from kills, pickups, and farm crops) and learn utility skills; the Pet Shop keeper trains them and the character tab shows the pet's level. In a run your pet can carry bag items home to your town stash (**Send home**, H, in the inventory; one item per trip, more as it levels). Per-pet pickup toggles, pet dyes at the tailor, pets keep out of puzzle and trap rooms (`petrooms`, which the Pets package carries too), and every HoH1 pet is in the Pet Shop (imported from your own HoH1 install). |

### Runs and dungeons

| Module | What it does |
|---|---|
| `puzzles` | Puzzle rooms are back on most floors (HoH2 ships 88 but never places them), checked and repaired after generation, and HoH1's Constellation puzzle is one they can roll, also in a clearing on forest and heaven floors. Summons wait at the door while you solve. |
| `objectives` | Floor objectives on generated floors: a locked loot vault (two chests behind a door) opened by a lever somewhere else on the floor, and the way down sealed until the floor's exit lever is pressed. The HUD says what is left to find. |
| `strongbox` | Path of Exile-style strongboxes: open one, a pack of the floor's enemies spawns (elites possible), clear it for the box's loot. |
| `abyss` | Abyss cracks: step close and waves crawl out, ending in elites (more in a bigger party). Clear them for a reward that grows the deeper the run goes. |
| `maps` | Three new layouts for the equipment-map drops: Goblin Warrens, Sunken Dungeon, The High Court. |
| `affixes` | Rare and Epic items can roll a second suffix, and Epic items a second prefix: 25% each, so a few items carry five modifiers instead of three. |
| `valuables` | Valuables (vases, chalices, gems, furs, scales: the pickups that turn straight into gold) are worth twice their vanilla gold. |
| `trinkets` | Trinkets keep up in NG+: flat bonuses (health, mana, armor, power, regen, resistances, thorns, proc damage) grow by a fixed amount per NG+ level, twice as much on an attuned trinket when attuning doubles the number. Tooltips show the scaled numbers. Also 37 trinkets from Heroes of Hammerwatch (Lucky Hat, the spheres, the seals, Golden Lamp, Judgement and more), eight new trinket sets (Spheres of Power, Charms of Fortune, Disarmament, Plague Doctor, Pyromancer, Seals of Torment, Arcanist's Regalia, Conjurer's Relics), Emblems of Hermes and Apothecary's Supplies with more pieces and tiers, and a Trader's Coin that also discounts the dungeon trinket shop. |
| `wavemode` | **Wave Arena**: a survival arena started from a statue in town; every boss kill raises your arena rank, which is the arena's NG+ level next time. |

### Town

| Module | What it does |
|---|---|
| `fishing` | Six fishing spots on the town coast (a timing minigame: two to four hits in the green to land a fish), more in the water of run floors' potion wells (always one in a boss room), greyed on the map once fished out. A pirate sells bait, rods (priced per tier; new characters start with the wooden rod) and fish traps from the trading post's wreck, later its boat. Fish are swords, sell for the gambler's bet tokens (for gold without the gambler) and can be eaten from the bag (**Eat**, F; 100 HP per star, plus Luck). Catches can hold keys and ace keys, and a hole's loot goes to whoever caught it. |
| `farming` | The town's field grooves become farm plots: food crops and four Holy Herb strains grow with each completed run, faster when watered (the farmer sells the can and seeds; the well refills it). Smoke a herb for a buff that lasts 10 floors (hotboxing works outdoors too), or roll it into a joint: an off-hand with 5 puffs that a friend can take from you, with smoke that fills the room; a second joint goes in the main hand, left and right click puffing each. |
| `gambler` | A gambler in the tavern plays Higher/Lower for gold. He buys crops and herbs for gold and fish for bet tokens, and rerolls equipped gear for 2000 gold × item level, or 1 bet token per 5 item levels. Bet tokens are this module's: they show in the Materials tab, and without it fish sell for gold. |
| `tavern` | Three more tavern levels (from guild hall levels 7 and 8, the top one): a run can start with up to 3 foods and 5 drinks. |
| `waygates` | Way Gates: teleport gates in the town square and at every building you have built. Use one and pick where to go (a remake of Tyraen's Teleport in City). |
| `roulette` | A roulette wheel on a table in the tavern: one single-zero table for the whole lobby with all 157 bets at true odds (click near an edge or a corner for splits and corners), a remake of the Workshop roulette table. Luck and gold find raise the winnings by their percentage, so a smoked herb tips the odds your way. |
| `stash` | A Sort button on the town stash: by class, then weapon type, then item level. |
| `laststats` | The last run's stats for the whole party, on a notice board by the town fountain: every player on one page as bars per stat, with a search field. |

### Co-op and quality of life

| Module | What it does |
|---|---|
| `groupcombo` | A party-wide combo bonus that grows with how many players are in combo, and brief invulnerability when everyone is. Boxes, barrels, sacks and vases also drop a rare **combo orb** (0.1 %, up to 1 % with the Luck of whoever breaks them): everyone with combo unlocked gets their own, and picking it up puts you in combo at once (pets leave it alone). |
| `architect` | Any player can pick and pay for Architect alterations; the host's picks are split across the party. Seven HoH1 challenges discount them, down to free. The run-start screen keeps three named presets of picks and NG+ level per character, shows NG+ last with the start hint, and lets a non-host leave. |
| `droptrade` | Drop equipment on the ground for friends: a Drop button (Q) next to Destroy in the inventory (each player can rebind it on the Plus tab). The use key picks up a dropped item before it talks to an NPC or opens a shop, chest or shrine underfoot. |
| `attrclick` | At the Attribute Trainer, Shift+Click places 20 attribute points and Ctrl+Click 5 (never more than you have); the costs show the amount while the key is held. |
| `orbwarn` | The orb picker says which orbs a pick would make unavailable (mutually exclusive orbs such as the Firearms grenades), with their icons and names. |
| `deathrecap` | Who killed you: the top damage sources of the last 10 s, on screen and in chat. After a boss fight, a recap of everyone's damage by skill and damage taken (one per fight, however many boss units it has). |
| `bufftips` | Hover a buff icon to see what it does and how many seconds it has left. Class buffs the game leaves off the buff bar, like War Cry, get an icon. |
| `chatlinks` | Linked items stay in chat with their slot and item level; `hwp link` links an equipped item. |
| `colors` | Colour-blind and high-contrast tints for enemy and friendly projectiles, with a ring in the team's colour around each (player menu > Plus tab), and each player in their own colour on the minimap and the overlay map, with names for players far away. |
| `goldworth` | Gold on the floor shows what it is worth: 15 coin and pile looks, from a bronze coin to a big pile of gold. |
| `mmhmm` | **Mm-hmm!** A quarter of rare and epic hats carry the Mm-hmm! bonus: the wearer says a village woman's "mm-hmm!", heard from where they stand and one at a time, on every crit, when the wearer revives someone or is revived, drinks from a pool, completes a trinket set, takes the last orb of an orb tree (trees with more than one orb), opens an Ace chest or opens a secret room. |
| `mapicons` | A dye-pot marker on the minimap over every dye bucket of a floor (setting `mapicons.dyes`). |
| `hwplib` | The library every package carries (not a mod of its own): settings (the Plus tab and the `hwp` console command), save data and networking, and the plumbing other modules fill: the targeting and aim hooks, a wares market, untitled Materials tab sections, gear slot frames and the bag size. |
| `hwplib-luck` | The library part the packages that read Luck carry (Co-op, Keys, Dungeon, Town): **Luck**, a stat from gear affixes of Fortune, the Rabbit's Foot trinket and timed buffs from herbs and fish, which weights chest, strongbox, abyss and key drops towards the rarer results (a chest at its opener's Luck) and gives the party's average to generated floors (secret rooms, the imp, floor rewards, blueprints, fishing holes, keys and ace chests). Without it the Luck stat is hidden. |
| `hwplib-classui` | The library part the class packages carry (Firearms, Specs, Classes): the create-character class list that fits more classes and leaves parked ones out, and the Subclass Picker's skill row by skill type. |

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

No releases are published yet; until then the repo builds and installs everything for you:

1. Double-click `run.cmd` (or type `/run` to Claude, or `python tools/run.py`). It sets the
   machine up, builds every module (with your own HoH1 content when Heroes of Hammerwatch 1
   is installed), copies the `.bin` files into your Steam install's `mods/` folder and starts
   the game through Steam. Read its `run:` lines: the last one says which modules are new.
2. The first time only: in the game, open **Resource Mods**, tick the entry it named
   (`HammerwatchPlus-All` by default) and restart. The game remembers the set per save, so
   later redeploys stay enabled. Everyone in the lobby does the same.
3. In game, open the console (the key left of 1) and type `hwp help` for the commands and settings.

Subscribed to HammerwatchPlus on the Steam Workshop as well? Then the game finds two mods with
the same id, loads both, and keeps the Workshop copy's file wherever they overlap. You would
play a mix of the two builds, or the scripts fail to compile. Use one or the other: unsubscribe
while you play your own build (`run` warns: `run: workshop: ...`), or remove the `.bin` from
`mods/` to play the published one.

Without Heroes of Hammerwatch 1 every module still works: the campaign runs on HoH2 tiles,
the HoH1 classes and trinkets show placeholder icons and the HoH1 pets stay out of the Pet
Shop, and the game says so once in chat (`hwp hoh1` lists them). If `run` asks
where HoH1 is, answer with `python -m gamelab doctor --hoh1 "<folder>"` (or `--no-hoh1`) once.
Sharing the packages by hand still works: `dist/HWP-<package>.bin` (or
`HammerwatchPlus-All.bin`) into `<Steam>/steamapps/common/Heroes of Hammerwatch 2/mods/`.
`python tools/build.py` makes every package and the all-in-one pack without your local
content. `python tools/workshop.py` turns them into a Workshop upload kit (`dist/workshop/`:
each item's .bin, preview image, title, description and change note); the upload itself is
done by hand in the game's `PACKAGER.exe` > Steam Workshop manager, as
[docs/WORKSHOP.md](docs/WORKSHOP.md) describes.

## Class planner

The class designs live in a local web page: every class's kit, specs and orbs from the game
data, the Firearms Specialist's full design, and a 4th specialization for each of the other
classes (Rogue and Sorcerer: Zak; Warrior and Warlock: Colin; Ranger and Wizard: Noah). Seven
of them are built in `mods/specs`, and their planner records show the in-game numbers and
whether each skill and orb is built or tested. The Paladin's remains a design.

It needs only Python 3 (no game, no packages):
- **Windows:** double-click `planner.cmd`.
- **Linux / macOS:** `./planner.sh`.
- **Anywhere:** `python -m planner` (or `python3`) from the repo root.

Edits are saved as JSON files under `planner/data/`; commit and push them. More in
`planner/README.md`.


## Status

2026-10-29, confusion traps you can dodge (#38). The confusion glyph went off 0.15 s after a
player came near, out of sight until then. Now it, and the dart glyph that had the same
problem, show on the floor all the time, light up with a red warning for a second, and only
then go off. A dart glyph no longer hits a player standing on it with all eight arrows. The
Confusion setting now also turns confusion glyphs and plates off, as its text always said.

2026-10-29, all of HoH1's traps (#37). On top of spikes, flame jets and glyphs, generated
floors now get HoH1's poison, frost, drain and confusion plates, pressure spikes, frost and
curse glyphs, arrow, poison, fire and blade shooters in the walls, arrow turrets, flame
gargoyles, falling stalactites and bricks, and bear traps, each on HoH2's art. Every one
warns before it hurts (a red warning on a plate, a glyph lighting up, a stalactite's shadow).
Which ones a floor gets follows its theme, as HoH1's acts did: stalactites only in caves,
shooters and turrets in barracks and dungeons, drain plates and curse glyphs in crypts and
halls.

2026-10-29, projectile colours you can see (#36). The colour presets did tint every shot, but
a tint can only darken a sprite, and the shots that matter are bright fire or dark bolts, so
nothing seemed to change. Every tinted shot now also gets a ring in its team's colour (setting
`colors.markers`, on by default). `fix-colors` checks both sides' shots in flight in each preset
and the rings on screen (20261029-062340).

2026-10-29, Pyrebrand is a nuke (#35). The brand now charges as it burns, and the Hellfire
Claw pays up to 100/150/250/350/500% of the damage that fed it (rank 1-5): all of it when the
brand runs out, less on an early recast. Before, it paid 10-50% whenever it went off. At rank 5
a full brand's claw took 7.4x the damage that fed it from a test dummy, where the old one would
have taken about 0.9x.

2026-10-29, Pelor's Fury works on the Serpents of Demise (#34). A serpent is mostly body, and
its body is a trail of untargetable boss parts. Aimed at the body, the Fury picked one of those
parts and refused nearly every time. Now any part of a serpent counts as the serpent: the
Fury holds its head when the head is above ground, and says why not when it is underground. A
body part over a surfaced head no longer steals the pick either.

2026-10-29, one boss recap per boss fight (#33). The Serpents of Demise showed a damage
recap each time one of their serpents went down, because the recap followed each
boss-tagged unit on its own. A fight is now the whole encounter: every boss unit you hit
joins it, and it ends when they are all down and no boss health bar is left, the way the
game's own boss bar sees it. The same fix covers the Bandit Lord's mirror images, the
Harbingers and spawned ghosts. Damage taken is no longer counted twice when two boss
units are up, and the recap is named after the boss bar ("Serpents of Demise").

2026-10-29, fishing is harder (#32). A bite now takes several hits in the green: two for a
1-star fish, three for 2-star, four for 3-star. After each hit the fish fights back: the
green zone jumps away, the marker speeds up and the timer restarts, and one miss loses the
fish. The fastest fish keep their speed, so their tiny zone can't be skipped over between
game ticks. A "Hits to land" setting picks one count for every fish (1 is the old single
press).

2026-10-29, Mm-hmm! from the wearer (#31). The hat's voice is now a village woman's "mm-hmm!"
(the Equipment Buyer's, Enchanter's and Mystic's voice) in place of the Material Trader's.
It comes from the wearer's body, so others hear it from where that player stands and
fainter far away, instead of from nowhere at full volume. Each one plays to the end before
the wearer says it again: a burst of crits no longer stacks it.

2026-10-29, traps on one map (#30). The HoH1 traps were on every floor of every map, and
mostly spike floors. Now they go on one map, the Crypt by default (a "Trap map" setting picks
another, or every map), and always in the Forsaken Tower, HoH1's own trap tower. Each trap is
rolled on its own, so a floor gets a mix of spikes, flame jets and the three glyphs instead
of a floor full of spikes. The teleporter pad is still on every floor.

2026-10-29, War Cry shows on the buff bar (#28). The game gives almost none of the class
skills' buffs an icon, so War Cry, Power Surge, Hot Pursuit and others worked but never
showed. The buff tooltips mod (`bufftips`) now gives 13 of them an icon cut from the skill's
own art, with a name and a short description for the tooltip. A setting turns it off.
Untried in co-op: an ally hit by War Cry should see it on their own bar too.

2026-10-29, the levers work past the first floor (#27). From the second floor of a run on,
the vault and exit levers did nothing and the way down was never sealed. The game builds the
next floor ahead of time, in a separate part of the game's scripting, and the mod's notes on
where it put the vault and the levers stayed there. The mod now reads the vault and the
levers off the floor itself when it starts, and a co-op client keeps trying to seal its exits
for a few seconds, as the host does.

2026-10-29, bonus vaults look like the floor they're on (#26). The vaults behind levers had
a bare floor and no walls of their own: their cells were reserved the way a prefab with its
own art reserves them, so the game painted neither walls nor the floor's decoration there,
and on the Bandit Keep the room sat in the dark of the wall block it was carved from. Now
the game paints the vault like its own rooms, with the floor's tiles, walls and torches. The
levers no longer show on the map; the new Architect alteration **Marked Switches** puts
them back for a run.

2026-10-29, notices name the HammerwatchPlus updates (#24). The game's join check compares mod
ids, not their contents, so friends with different updates got into one lobby and things
quietly broke: on 2026-10-28 a client on per-module packages from before 2026-10-26 joined a
newer host, and only the log said `no handler for event` for four of the host's events. Every
package now carries its update (the commit's date and hash). In town, a client and the host
compare theirs, and both are told which packages differ, which side is older and who should
update. Packages of different updates in one game are named with their updates too, and `hwp
version` lists them. The Workshop change note shows the same update.

2026-10-29, the General Merchant's tabs work with a controller (`keys`, #23). The Keys & Bags
and Trinkets tabs switched only with a mouse click. Now a gamepad's bumpers (and Tab on a
keyboard) switch them, as in the player menu and the stash, and the bindings show beside the
tab row. GameLab gained `menubutton`, which presses a menu button as a gamepad does, so
controller paths in windows can be tested without a controller.

2026-10-29, Shift+Click places 20 attribute points at the Attribute Trainer, Ctrl+Click 5
(`attrclick`, #22). Vanilla places one a click, and every level and NG+ level adds more to
place. The cost on each stat shows the amount while the key is held. A gamepad keeps the
vanilla hold-to-repeat.

2026-10-29, items with two suffixes or two prefixes (`affixes`, #17). Vanilla gives a Rare item
one suffix and an Epic one a suffix and a prefix, each from its own pool. Now each of those
tiers may roll a second mod, 25% each (`affixes.chance`), from the same pool and never the same
mod twice. The extras show in the tooltip, save with the item and stay when the module is off.

2026-10-29, guns work for every class (#16, #29). A Ranger's pistol never fired: a gun
shoots from its clip, and the clip was filled and reloaded only for the Firearms Specialist.
The clip, its reloads and how a gun handles now go with the gun, so a Ranger with a pistol
and a hand crossbow shoots both, and the clip shows on the HUD. The class keeps its skills and
the shops' guns.

2026-10-29, Lightning Kush (#15), a fourth Holy Herb strain: violet, +20 % lightning damage,
Ember Kush's counterpart. Each strain had been copied by hand into seven files and three
sprite sheets indexed by seed order, and the harvest sheet was full. So now one table makes
them all: `tools/make_herbs.py` writes the buffs, joints, names, seed lines, units and art,
and a test fails when a file is out of date. Adding the strain also showed that the
materials tab's Plants & Herbs grid had only 16 cells for 18 seeds and harvests: the last
two would never have shown. The grid now has 24 cells, 9 across, and hwplib logs an error
when a section has more providers than cells.

2026-10-29, weapon swap on a controller (#14): D-pad left swaps, the one button vanilla's
gamepad map leaves free in gameplay, and the Plus tab binds another (press it). The hints show
the button while you play on a controller. Behind it, hwplib gains `HWP::Input`, so a mod's
hotkey can read a controller button. Until now every HWP hotkey read the keyboard only. Skill
4-6 and the bag item actions are still keyboard-only and can use it next.

2026-10-28, the pet courier (issue #13). In a run, hover a bag item and press H (or click
**Send home**): your pet takes it to your town stash, in a tab called "Pet deliveries". The
item is in the stash and saved the moment you hand it over, so dying or leaving on the way
can't lose it. The pet leaves when you close the menu and comes back after the trip (60 s by
default, shorter with Fetch ranks). It carries one item a trip, plus one every 5 pet levels.
The bigger problem it turned up: bag item actions lived in droptrade, only the first one ever
showed, and it was bound to a fixed E, which is also the menu's Destroy key, so eating a fish
opened the destroy dialog too. hwplib now owns the inventory hints. Each action gets its own
hint and key: Drop Q, Eat F, Send home H, each rebindable on the Plus tab, and the log flags
an action key the menu also binds. `fix-item-actions-eat`, `fix-pets-courier`, their package
variants, `plan-gear-b` (droptrade) and the package scenarios pass.

2026-10-28, the Forsaken Tower from HoH1 itself (`campaign`, "HoH1 tower" in its README).
With HoH1 installed, the import builds HoH1's tower from the player's own install: 23 floors,
the nine hand-made levels as HoH1 ships them and fourteen act floors from HoH1's own generator
scripts. HoH1 world scripts whose HoH2 namesakes read other param names are renamed (436
RandomChance rows had never run; the Councilors' deaths never reached SetBossKilled). HoH1's
`magical` damage goes to an element, speech bubbles use HoH1's styles, exits keep their start,
and HoH1's texts and boss names are imported from its language file. `tower-floors` loads all
23 floors clean (20261028-163319); `tower-bosses` fights all six bosses the way their levels
start them, checks each titled boss bar, kills them as the player and takes each exit
(20261028-163821). GameLab fix: `hps.current_save` read the save header's timestamp as a float
and picked the wrong rotation file once its low word passed bit 31, so a rebuilt fixture lost
the scenario's mods. HoH2 classes on HoH1's bosses: the Paladin's Generosity holds all eight
boss units (`plan-generosity-hoh1`, 20261028-170027). Two fixes made that work: the Councilors'
attack no longer casts through the hold, and a held Councilor or Vampire Lord stands solid and
targetable. The Devil Forgemaster raises every HoH1 elite, miniboss and boss, including each
tower boss from its body on its own floor (`plan-forgemaster-hoh1`, 20261028-170645). The
dragon is the exception, unraisable as designed.

2026-10-28, GameLab tests the build under test even when you are subscribed to the
published one. With the All pack published, this machine's Steam account subscribed to it
(Workshop item 3828529950). The lab game loads subscriptions too, so `pkg-all` and
`pkg-all-every` enabled two `HammerwatchPlus-All` mods. The game keeps the first copy of each
path, which was the Workshop's: 153 of 170 scripts came from the published build, and the new
code failed to compile against its older library. A mix that happened to compile would have
passed while testing the wrong code. A package whose id a subscription has now goes into the
lab as `<id>-gamelab`, a boot error names any mod found twice, and every run asserts none
was. `run` warns about the same mix in your own install (`run: workshop:`).

2026-10-28, the Quality of Life card no longer overlaps: a tile on a card drops its extra
symbols when its name would run into the next column ("Improved behavior" ran into the hat).
Only the QoL card changed. Quality of Life, Pets and the All pack are republished on the
Workshop, carrying the shorter "Wep. swap" and "Improved behavior" labels too.

2026-10-28, the Forsaken Tower played from floor 1 to the end (`tower-run`, 20261028-190322,
pass in 16 min). The run used every floor's own exit for all 23 floors. On the way it cleared
657 enemies, used 55 level triggers and the chests, doors, shrines and wells, and fought all
six bosses. Traps fired in all five acts. Only archives_3's puzzle traps stayed silent, because
a player who doesn't make a wrong move never sets them off. The fixes it took:
- The vampire wakes once the crosses found on the chambers floors are placed on the altars,
  as in HoH1, and the bot places them.
- The bridge's exit to the dragon now runs through the mission. It used to leave the mission's
  floor on the bridge.
- HoH1's gambler (ItemDealer) and end window (EndOfGame) are ported on HoH1's own .gui files,
  with HoH1's scroll widgets. The gambler bets HoH2 trinkets, one gamble per gambler, and the
  end window's CONTINUE goes back to town (`tower-interfaces`, 20261028-182126).
- AddNotification shows its text through HoH2's announcer.

2026-10-28, pets keep out of trap rooms as well as puzzle rooms, and walk back out of one
they end up in. This is the new shared module `petrooms`: it is listed in Quality of Life,
and the Pets package and the All pack carry it too. It drives vanilla pets as well as the
Pets package's. A room is one puzzle unit, or traps on three spots (units within 12 px are one
spot, so a campaign glyph and its blast count once), within `petwait.radius`. A pet following
its owner back after a wait may cross a room for 5 s, so an owner who crossed a trap room is
followed through it. `plan-pets-b` (pet skills, puzzle and trap rooms), `plan-petrooms-vanilla`
(a vanilla pet, QoL alone) and `pf-plan-petrooms-vanilla` (the built QoL package) pass
(20261028-141504, -141825, -142113).

2026-10-27, every package on its own and together. `tools/make_package_scenarios.py` now
also writes `gamelab/scenarios/pkgfeat/`: each feature scenario run against the built
packages that ship its mods instead of the source folders (162 scenarios). The first pass
found the pets package and the all-in-one pack carrying 216 HoH1 pet files cut from this
machine's HoH1 install. Nothing had been uploaded; the pets module now lists them as `local`,
and `tests/test_release_files.py` fails if a release package would carry any ignored file.
Every other failure turned out to be one of these:
- a flake that passed on a rerun;
- HoH1 content a release package never has (now `needs_hoh1`);
- a scenario that fails the same way from the source folders.
None failed only as a package. Without HoH1, the campaign, classes, pets and trinkets features
keep their stand-ins, and the player gets one chat line naming them (`hoh1-standins`; with
HoH1, `hoh1-installed` stays quiet). A package from another build now tells the player as
well as the log (`pkg-mismatch`). The all-in-one pack with all twelve single packages enabled
beside it passes every check (`pkg-all-every`). Still open: 17 scenarios that fail from the
source folders too (`docs/RE_NOTES.md`, "Packages on their own").

2026-10-27, script safety against game updates: every HWP module entry point (45 of them)
now runs inside `HWP::Guard` (hwplib `Guard.as`, applied by `tools/guard_modules.py`, which
`tests/test_guard.py` enforces). Before this, one module's script exception stopped the game
mode's frame update after the module loop, every frame (no screen shake, pings or death
check). Now the guard logs the error with its stack trace, the frame goes on, and after 30
errors in a row that entry point turns off until the next level, with one chat line;
`hwp guard` lists what failed. hwplib also names the game build at boot and tells the player
once when it is not the build HammerwatchPlus was tested on (176). A compile error still
stops the game on an empty main menu, since nothing compiles; `docs/GAME_UPDATES.md` is the
checklist that catches one before players do. Measured: `compile-err` (025559), `throw`
(030133), `throw-ctor` (031426), `guard` (031629); `mod-all`, `pkg-all` and
`pkg-pair-all-qol` pass with the guards in.

2026-10-27, code review fixes (fe617b8..3a6e9f9): ten fixes.
- The guard's unguarded trace run happens once per game process, and its throw is counted.
- `TESTED_BUILD` lives in `Guard.as`, so a mixed set of packages still compiles.
- A `compile_error` scenario fails if the scripts compile.
- `needs_hoh1` scenarios are skipped (exit 7) on a machine without the HoH1 import.

Tested: `guard` (103129), `compile-err` (103302), `hoh1-standins` (103355) and
`plan-runs-arch` (103410). Details are in `docs/RE_NOTES.md` ("code review fixes
(fe617b8..3a6e9f9)").

2026-10-27, the Paladin of Generosity: the eighth 4th spec (`mods/specs`, `Generosity.as`):
Pelor's Blessing stacks from Lay on Hands, Blessed Strike kills and Conviction, and at 10
stacks Pelor's Fury holds one enemy in beams of light (stunned, casts cut, armor and
resistances 0, more damage taken). A Fury that cannot hold spends nothing. Its four orbs are
built, and the farming module adds Pelor's favour (crops grow twice as fast and wild plots
turn up twice as often with a Paladin of Generosity in the party). Tested: `plan-generosity`
(020522), `plan-generosity-farm` (015840), and `plan-generosity-bosses` (022232): 16 of 18
bosses held mid-attack with their casts cut; the Serpent while untargetable and the Shadow
Face (immune to buffs) are refused by design and keep the stacks. The engine facts behind it
(spirits' sensor bodies, unflagged boss skills, a stunned bodiless unit's null body, the
buffered press) are in `docs/RE_NOTES.md` ("the Paladin of Generosity"). Display of Generosity
needs a party to check. The icons are final: the user's round-4 picks, with Holy Sacrifice
from round 2 (`look-generosity-icons`, 101621).
A code review of 1c5335c..def346d found ten problems; the fixes include the 35 Dev Arena
scenarios that still listed the removed core mod, an export that would bake vanilla paladin edits
into Generosity's copies, Holy Sacrifice paying out on a despawn, and `build.py all qol` writing
every package (`docs/RE_NOTES.md`, "Code review fixes (1c5335c..def346d)").

2026-10-26, packages: there is no core mod any more. The modules ship as twelve Steam
Workshop packages that each work alone, plus `HammerwatchPlus-All` (`packages.json`,
`tools/build.py`). The shared code is a library split into `hwplib`, `hwplib-luck` and
`hwplib-classui`, and every package carries a copy of the parts it needs. The dye-pot
minimap markers became the `mapicons` module (Quality of Life), and buying bag slots moved
to the keys module. Every package alone, the all pack and four pairs pass in GameLab
(`pkg-*`, `docs/RE_NOTES.md` "one path, two mods"). The engine logs one harmless
`Resource name hash conflict` error per shared file when two packages are enabled.
`run.py` and `deploy.py modded-prod` now deploy the all pack and remove the old
`HWP-<module>.bin` files, so a save ticks `HammerwatchPlus-All` once. The Workshop upload kit is
`tools/workshop.py` ([docs/WORKSHOP.md](docs/WORKSHOP.md), 2026-10-27).

2026-10-28, Workshop pages v2 (368480f): every page opens with "Multiplayer supported" and what it needs, lists each module in a line, and ends with install, settings and a link to the All pack. Each picture is a card drawn from the game's art (`tools/workshop_art.py`), and the All pack's gallery shows every package's card. Ten packages and the All pack are updated. The Forsaken Tower was hidden by Steam (EResult 15 on every update).

2026-10-28, Workshop pages v3: **The Forsaken Tower is off the Workshop.** Its item (3828529832) is deleted, and the Workshop's All pack no longer carries it (`packages.json` `"workshop": false`, `tools/build.py --workshop`); your own build and `/run` still have it. The cards use the game's real art: the map drop's sea chart, the strongbox, the ace chest (the red-lidded gold chest), the waygate, the dye map icon, the skill orb, the watering can and game crops, two HoH1 trinkets (frying pan, lucky hat), and the town's exit guard, coloured as the game colours him. Generosity's card shows only its own skills. The All pack's cover shows every package with a few of its icons, and its page no longer names the HoH1 Classes. The Fourth Specializations pages say the Celestial Ruins DLC is needed only to use the Priest's 4th specialization. The All pack's gallery is uploaded one picture per submit and read back until each has an image.

2026-10-27, on the Steam Workshop: the twelve packages and the All pack are public, published
with `tools/workshop_publish.py` from 34d91f0. The All pack is
https://steamcommunity.com/sharedfiles/filedetails/?id=3828529950, and every item's id is in
`workshop.json`. HoH1 Classes is held back while those classes are parked.

2026-10-25 to 2026-10-26: the bug and feature list of 2026-10-22 (`temp/bugs 10.22.26.txt`) landed in 16 commits,
each with its own lab scenario (`gamelab/scenarios/fix-*.json`, all passing): Firearms feel and Snipe,
Arcane and Aerotheurge, the Forgemaster's risen and channels, fishing, farming, puzzles, pets, the run-start
screen, Luck, the boss and last-run recaps, the HoH1 campaign version with Battlements, traps and teleporters,
per-player map colours, the trapped-chest banner and the new `objectives` module. `mod-all` (32 modules)
and `plan-t9` are the integration gates; the session's notes are in `docs/RE_NOTES.md`
("Bug list 10.22.26").
A code review of those commits found ten problems (puzzle room offsets, client fishing loot, Luck buff
refreshes, map dots hidden with names, the Forgemaster's dash cooldown, pyre Heresy without the orb,
Luck raising drop rates, DoT missing from the boss recap, Blink past rails, duplicated carving code);
all are fixed and the nine affected scenarios pass again (batch `review-fixes-003`). Luck now has a
cell on the character tab's stat bar with a tooltip giving its factor ("code review, applied" in
`docs/RE_NOTES.md`).
In co-op a chest or strongbox now rolls at the Luck of whoever opens it and the whole party
gets what it rolled; an abyss crack rolls at the party's average. The party's average Luck
also reaches generated floors: an extra secret room, more and better floor rewards within
the vanilla ranges (food, mana, chests, caches, scrolls, valuables, the blueprint chance),
rarer blueprint recipes, more fishing holes, a likelier imp, more and higher keys and
more ace chests (`docs/design/luck.md`, `fix-luck-floors`, `fix-luck-imp`).

A second code review (69ba108..e1f1fc7: tavern levels, Way Gates, roulette, Auto Aim, the trinket
work) found ten more problems, all fixed: the sixth tavern level could never be built (it asked for a
guild hall level past the top); roulette chips on the table were lost when a run started (they now go
back to the town's gold from the town's save); a client's Way Gate list went stale after a building
upgrade; Auto Aim moved the gamepad's own aim, skipped vanilla's SetSkill for auto skill and scanned
every frame; a null blueprint check came after its use; trinket strings used a second prefix; a big
roulette payout could overflow (the stake setting is now capped at 10,000,000); and the custom stat
lookup was copied four times (now `HWP::CustomStat`, core `CustomStats.as`). mod-all, mod-roulette
(with a new leave check), mod-autoaim, mod-tavern, mod-waygates and mod-trinkets pass
("Code review fixes (69ba108..e1f1fc7)" in `docs/RE_NOTES.md`).

The Skill 4-6 keys now live in `classes`, since only the HoH1 Assassin, Shadow, Trickster
and Retiarius have more than three actives. Core keeps a hook-only targeting helper
(`TargetHelper.as`) for them and for Auto Aim.

The Gold Collector pet mod is gone (vanilla pets already pick up gold). The gold-worth looks moved
out of core into `goldworth`, and Mm-hmm! is its own `mmhmm` module: besides crits, the hat now voices
revives, wells, secret rooms, completed trinket sets, the last orb of a multi-orb tree and Ace chests
(mod-mmhmm, mod-all, mod-keys, fix-gold-sprites pass; a real two-player revive is untested). The Devil Forgemaster's eating now heals
30% of max health a second instead of +50 regeneration (plan-forgemaster-eat).

Core is plumbing only now: the orb warning is its own `orbwarn` module, the use key's
pickup-first order belongs to `droptrade`, and the bet tokens belong to `gambler`, which
registers them as the market's second currency (without it, fish sell for gold). The
materials tab has two untitled sections the modules title and fill: Supplies (gambler,
fishing) and Plants & Herbs (farming).

The full QA sweep is paused and incomplete. The [current checkpoint](docs/generated/qa_pr_checkpoint.json)
records 10 gameplay repairs and scoped passing coverage for the six original
fourth specs: 60/60 rank rows and 61/65 orb qualities; Firearms 60/60 rank rows and 74/75 orb qualities;
HoH1 imports 29/39 skills and 136/191 positive ranks; 9/9 selected-mastery saves.
The later Priest Forgemaster work is outside those original matrix counts.
These counts do not establish complete mechanics, UI, interactions or ordinary
run lifecycle coverage. Five orb-quality cases require real co-op.

Agents and contributors: start with [AGENTS.md](AGENTS.md), the
[GameLab quickstart](gamelab/README.md), and the
[regression/known-failure map](docs/qa/REGRESSIONS.md). Deferred QA drafts are
[committed for fresh-clone recovery](docs/qa/deferred/README.md), still unapplied.
Historical native/package results retain their original source epochs; this
handoff update adds documentation and a batch helper, not native coverage.

<details>
<summary>Historical feature and QA checkpoints</summary>


- 2026-10-22 overnight QA remains incomplete. Eight scoped
  gameplay repairs have passing reproductions: Shadow Strike, Riposte, per-gun magazine
  crit, Hoarder HUD cleanup, Thunder Orb cast attribution, returning-arrow catches,
  custom weapon-family stash sorting and Dragon's Breath patch persistence
  (`20261022-085158`). All 14 required regression scopes passed at their recorded
  fingerprints; later changes only extend read-only QA telemetry. Production sources
  and release payloads remain unchanged after those passes;
  exact evidence and limits are in `docs/QA_OVERNIGHT.md` and `docs/generated/qa_*_inventory.json`.
- 2026-10-22 night: PR #9's code review applied after its merge (explicit `off-hand` flags on
  the gun rounds, Extended Clip Crit with no actor, typed stash ids in any slot, launcher and
  runner guards; `docs/RE_NOTES.md`, "PR #9's code review, applied after the merge").
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
  The Paladin's 4th spec is still being designed.
- 2026-10-21: the Warlock's **Essence Extraction** now matches the planner (the user's version of
  Colin's design). Magic weapon hits (every arcane-tagged weapon) gain Essence once per 2 to 1 s, and
  Essence from a Pyrebranded enemy counts twice (two stacks; Drain Essence's bleed, health and mana
  twice). The old +max Essence and the melee-on-branded-elites gain are gone. Reading "trigger twice"
  that way is assumed. `plan-specs` passes (run `20261021-232748`). Original flakiness: Lightning Arrow's
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
  attack, follow and leash). The fair-die check, the 40 bodies and the 25 s boss window pass in the
  valid re-run `20261022-144616` (after a `/code-review medium`: Heresy and the cooldown come with
  the host's answer to a raise, the cost is spent when the channel completes). The lunge now dodges
  (the Dash skill) to just under the body, faces up and eats it bobbing 1 px with blood flying out;
  a Penance dodges there too and a golden light grows out of the body as it channels
  (`plan-forgemaster-eat 20261022-154317`). Balance is a first pass.
- 2026-10-22: the **beta build** for testers without the Celestial Ruins DLC:
  `python tools/deploy.py modded-prod --beta` folds `mods/holylocal` (the Priest and its weapons
  with the `dlc has holy` conditional removed, local_only, used with the dev team's permission)
  into HWP-core.bin, so only HWP-core and HWP-specs are enabled (since the packages: every package
  that carries hwplib). A plain build never carries it.
  Verified: with it the create-character list offers the Priest and "create" makes one
  (`mod-holylocal-priest 20261022-163957`); without it there is no Priest
  (`mod-holylocal-priest-control 20261022-164029`). **Remove `mods/holylocal/` before publishing.**
- 2026-10-22: core overrides `GUI/PlayerMenu/Modifications.as` (one line) so the HWP skill
  descriptions' `%param%` tokens are filled in the main menu's create-character tooltips, where
  no player actor exists yet (assumed from the code, not run). The install's hidden-classes and
  Firearms-figure complaints were a stale 10-19 deploy: redeploy with `deploy.py modded-prod --beta`.
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


</details>

## GameLab

GameLab is the test harness: it boots a sandboxed copy of the game hidden and muted,
drives it through its own scripts (no real input, no focus steals, never touching your
config or saves), and scores what happened. Start with the [quickstart](gamelab/README.md)
and [regression map](docs/qa/REGRESSIONS.md); the [detailed skill](.claude/skills/gamelab/SKILL.md)
covers authoring and troubleshooting.
Before merging to main, run `python -m gamelab run mod-all --mode lab` (every content
mod loaded together; GUI textures must be power-of-two sized or the game won't boot).
The lab game also loads your Steam account's Workshop subscriptions (the game asks Steam,
with no switch to turn that off). A built package whose id a subscription has goes into
the lab as `<id>-gamelab` (the run records `workshop_shadowed`), and every run asserts that
no enabled mod was found twice.

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
python tools/run.py                   # everything below that a play session needs, then launch (run.cmd; flags: --no-launch --dry-run)
python -m gamelab doctor              # first thing on a new clone: checks every prerequisite
python -m gamelab doctor --fix        # uv sync, back up + verify your saves, bootstrap.py (gamecode/, tools/bin/),
                                      # env_link.py, class_units.py, the HoH1 imports when HoH1 is found,
                                      # make_pet_dyes.py, then one smoke boot (null-payload, hidden)
python -m gamelab doctor --confirm-saves   # only if --fix printed AMBIGUOUS save lines and the backup is still what you want
python -m gamelab doctor --hoh1 "D:\Games\Heroes of Hammerwatch" --fix   # HoH1 not found automatically: say where it is
python -m gamelab doctor --no-hoh1    # you don't own HoH1: skip its content, stop asking
python -m gamelab doctor --smoke      # boot null-payload again; a failure names its cause (antivirus, GPU, cores)
python tools/build.py                 # pack dist/HWP-<module>.bin + dist/HammerwatchPlus-All.bin
python tools/make_herbs.py            # farming's Holy Herb strains from one table: buffs, joints, lang, art (--check)
python tools/hwr_archive.py --help    # low-level archive tool (list/extract/pack HW2R and HWRR)
python tools/icon_art/render.py all   # skill icon ideas in the vanilla style (tools/icon_art/README.md)
python -m planner                     # the class planner in your browser (or planner.cmd / ./planner.sh; planner/README.md)
python tools/import_hoh1.py pets|levels|campaign|classes   # HoH1 content by hand (doctor --fix runs all four)
```

Mods live in `mods/<id>/`. Conventions are in `docs/modules.md`, the archive format in
`docs/archive-format.md`, the script hooks in `docs/hooks.md`. What to do when the game
updates is in `docs/GAME_UPDATES.md`.

HoH1 assets are never committed. `tools/import_hoh1.py` writes into gitignored
`hoh1_import/`, and `build.py` leaves it out of packages unless `--with-local`, so each
player imports it themselves.

## License

MIT. Game assets belong to Crackshell.


## Resumed full sweep (historical snapshot) ? no time limit (2026-10-22)

The user removed the original overnight deadline and activated the goal again. Work remains in progress; the original deadline/final-hour notes below are historical. Verified scoped coverage now includes60/60 fourth-spec rank cases,49/65orb qualities (nine fresh Branding qualities awaiting granular audit; maximum combo failed),20/60 Firearms ranks,42/75orb qualities,62/191HoH1positive ranks and9/9mastery save/reload combinations. Native stat-only scopes remain separate from combat/cadence/mitigation.

Fresh full-stack `mod-all 20261022-111422` and minimal `null-payload 111454` compile/load checks passed with the read-only per-frame resource observer. `qa-firearms-ranks-base 111509` and `qa-specs-living-mana-coefficients 111830` passed; exact per-run hashes are in the ledger/journals. `qa-specs-branding-orbs 113033` now obtains strict fine-grid/native-ray geometry through normal walking but fails the maximum-combination check. `qa-classes-gladiator-hoh2-run 112028` reached Keep3 and died during objective travel; no class/encounter bug is inferred. Controlled endgame weapon tests112325/112427 failed native equip requirements before attack/parry testing: ilvl35 requirements use unbounded vector interpolation at34/9, not the high endpoint at level10. A QA fixture correction is staged; no production change is inferred from these setup failures.

The source is frozen during each serial GameLab batch. Remaining ranks/orbs, legal interactions, ordinary run lifecycles, UI/acquisition and module functional/persistence/failure paths remain required. See `docs/QA_OVERNIGHT.md` and `docs/generated/qa_overnight_summary.json`; previous repair regressions and all failures are retained.


## Historical resumed sweep checkpoint (2026-10-22; superseded above)

The full sweep has no time limit. Scoped native coverage is 60/60 fourth-spec rank rows and 61/65 orb-quality rows (four require true co-op), 60/60 Firearms rank rows and 71/75 orb-quality rows (three Reload rows await a corrected idle-timer test; one requires co-op), and 118/191 positive HoH1 ranks across 26/39 abilities. All nine selected-mastery save/reload combinations pass. These counts cover the recorded effects, not every amplitude, boundary, interaction, UI or ordinary lifecycle requirement.

Two additional gameplay repairs are verified: Branding no longer retains the Essence damage bonus after consumption, and Gladius now deals native weapon-scaled damage instead of zero. Gladius first-contact damage passes at all five ranks in `qa-classes-gladius-collision 20261022-145123`. Current full-stack load passes in `mod-all 145021`; all 31 modules also have standalone load evidence. Full module functionality remains incomplete.

The current serial batch is finishing Branding quality combinations and Sphere acquisition/UI prerequisites. Reload's expired negative input timer and Grimoire's stationary-glyph target distance are source-reviewed QA corrections awaiting native reruns. A Branding combination failed its clear-lane setup before any combat trial; it remains recorded and under investigation. Ordinary runs also need a source-correct reward-window input flow before boss/reward/save coverage can be claimed.

The earlier 32-archive package verification predates the Branding and Gladius repairs. Those archives are historical; current-source packaging and final regressions remain required. The detailed source epochs, original failures and remaining work are retained in `docs/QA_OVERNIGHT.md` and the generated inventories.
