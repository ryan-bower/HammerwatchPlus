# Features

A modular co-op mod for **Heroes of Hammerwatch II**: a new class (the Firearms Specialist),
Heroes of Hammerwatch 1 content (the Forsaken Tower
campaign, keys and ace chests, legendaries, mercenaries, titles, pets), new things to find in
the dungeons, fishing and farming in town, and co-op and quality-of-life fixes.

The modules ship as twelve packages, each of which works alone, plus an all-in-one pack. Eleven
are on the Steam Workshop; The Forsaken Tower is local-build only.

| Package | Modules |
|---|---|
| `HWP-qol` Quality of Life | bufftips, chatlinks, stash, deathrecap, laststats, colors, waygates, weaponswap, summons, petrooms, legacy, goldworth, mmhmm, orbwarn, orbreroll, mapicons, attrclick, salvage, freeskills, outofcombat |
| `HWP-coop` Co-op Play | groupcombo, architect, droptrade, partyexit |
| `HWP-autoaim` Auto Aim | autoaim |
| `HWP-firearms` Firearms Specialist | firearms |
| `HWP-specs` Fourth Specializations | specs |
| `HWP-classes` HoH1 Classes | classes |
| `HWP-keys` Keys and Ace Chests | keys |
| `HWP-campaign` The Forsaken Tower | campaign |
| `HWP-modes` Challenge Modes | mercenary, wavemode |
| `HWP-dungeon` Dungeon Loot and Encounters | puzzles, objectives, strongbox, abyss, maps, weapons, trinkets, valuables, affixes, bosses |
| `HWP-town` Town Life | fishing, farming, gambler, roulette, tavern |
| `HWP-pets` Pets | pets (and petrooms, shared with Quality of Life) |
| `HammerwatchPlus-All` | every package |

Packages work alone or together. Everyone in a lobby needs the same packages.

Every module can be turned off, and its settings changed, in game: open the player menu (inventory)
and go to the **Plus** tab. Key binds and the projectile colours (accessibility) are at the top;
below them each installed package is a row that opens to its modules, each with an On/Off switch
and its settings (2x valuables back to vanilla, fishing off, and so on). The search field at the top
finds any setting by a few letters of its name, value or description. Settings that change the game
for everyone are the host's in a lobby. The full list is generated in
[docs/generated/settings.md](generated/settings.md); `hwp set <key> <value>` sets any of them
from the console.

What each module does: [mods/README.md](../mods/README.md).
