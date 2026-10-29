# Publishing to the Steam Workshop

HammerwatchPlus ships as twelve packages that each work alone, plus the all-in-one pack
**HammerwatchPlus: All** (`HammerwatchPlus-All`), which holds every package. A player
subscribes to the ones they want. A player who already has some single packages can keep them
enabled beside the All pack, because every package of one build carries the same library
files (`pkg-all-every`). The packages are listed in `packages.json`, and `docs/modules.md`
(Packages) explains how they share the library.

## 1. Make the upload kit

```
python tools/workshop.py
```

This builds every package (`tools/build.py --workshop`) and writes one folder per Workshop
item to `dist/workshop/`:

| File | Goes into the uploader's |
|---|---|
| `HWP-<id>.bin` / `HammerwatchPlus-All.bin` | File to upload |
| `preview.png` (1440x810, under the uploader's 1 MB limit; see The cards) | Preview Image |
| `gallery/NN-<id>.png` (the All pack only: each published package's card) | the page's additional pictures |
| `title.txt` | Title |
| `description.txt` (Steam BBCode: multiplayer and what it needs first, then each module, install, settings, and a link to the All pack) | Description |
| `changenote.txt` (version, commit, date) | change note, for an update |

`dist/workshop/UPLOAD.txt` lists each item as NEW, UPDATE (with its Workshop link) or HOLD,
based on `workshop.json`.

The texts come from the repo, so fix them there, not in the kit:

- Each module's line is `TERSE` in `tools/workshop.py`: a few words a player needs, or a
  short list for a one-module package (the Firearms kit, the eight specs). Keep it in step
  with the module's README row.
- The All pack's line for a one-module package is `ONE_LINE`.
- What needs a DLC is `DLC` (today only the Priest's 4th specialization, the Devil
  Forgemaster: Celestial Ruins). The page's Requires line and its install steps say "only if
  you want to use" it; the card's red footer has its short name.
- The Heroes of Hammerwatch 1 notes come from each module's `HWP::HoH1::Report` lang
  string, the same text the game shows the player (`QUIET_STANDINS` leaves out the ones whose
  line never claims the HoH1 content).

`python tools/workshop.py --check` (also in the test suite) fails when a module has no README
row or `TERSE` line, an item has no `workshop.json` entry, or a page names a repo path.

## 2. Publish

```
python tools/workshop_publish.py --dry-run
python tools/workshop_publish.py
```

`tools/workshop_publish.py` publishes the kit as the Steam user logged in to the running Steam
client. It makes the same Workshop calls (ISteamUGC v015) as the game's packager, through the
game's own `steam_api64.dll`, so it needs no password, only Steam running and logged in, with
the game closed. For each item in `workshop.json` that is not on hold, it:

- creates the item when it has no `item_id`, and writes the new id into `workshop.json` at
  once (commit it);
- uploads the content (a folder holding only the `.bin`, as a subscriber's
  `steamapps/workshop/content/619820/<id>/` holds it), the title, description, preview, tags
  (`workshop.json` `tags`) and visibility (`--visibility`, default public), with
  `changenote.txt` as the change note;
- replaces the page's additional pictures with the kit's `gallery/*.png` (the All pack),
  after the main update: one submit removes the old ones, then each new picture goes in a
  submit of its own. Then it reads the gallery back (a UGC details query with the additional
  previews) and checks that every picture has an image URL; if one hasn't, it redoes the
  gallery, up to three times. One submit that removed and added eleven pictures left six of
  them without an image, and the page showed only the other five. `--dry-run` prints both
  counts.

`--dry-run` checks Steam, the login and the kit and uploads nothing. `--only HWP-qol,HWP-pets`
publishes some items. `--delete HWP-<id>` deletes an item from the Workshop for good (its page
goes and subscribers lose it); `workshop.json` keeps the old id under `removed`, and the
publisher skips the entry from then on.

Steam asks every Workshop author to accept the Workshop legal agreement once
(steamcommunity.com/sharedfiles/workshoplegalagreement). Until then the items stay hidden, and
the script says so.

### By hand, in the game's packager

The same upload is in the game's own `PACKAGER.exe` (in the Heroes of Hammerwatch 2 folder):

1. Start Steam, then `PACKAGER.exe`.
2. Choose **Steam Workshop manager** on the toolbar.
3. For a NEW item, open the **Upload new** tab: the folder's `.bin` as the file,
   `preview.png`, `title.txt` as the title, `description.txt` as the description, and a
   visibility.
4. Press **Upload**, then copy the number after `?id=` in the item page's URL into
   `workshop.json` under that item (`"item_id": "<number>"`) and commit it.
5. For an UPDATE, the manager lists your published items. Pick the item, choose the new `.bin`,
   and paste `changenote.txt` as the change note.
   The packager has no field for the additional pictures; add the All pack's `gallery/`
   images on its Workshop page (Owner Controls > Add/edit images & videos).

**Publish every package of one build together.** They share the library, and each package
checks that the library it finds is from its own build. When it isn't, the player gets one
chat line (`hwp.packages.mismatch`). Upload or update all of them from the same
`tools/workshop.py` run.

## 3. After publishing

- **Subscribe and play.** Subscribe to the item on a clean profile, or with the
  `mods/` copies removed, and play. The game logs
  `Resource mod: <file>: <name> (<id>)` at startup for a Workshop item
  (`docs/MODDING_NOTES.md`).
- **Turn the mods on.** Mods are enabled per save, in that save's mod list, so a player
  ticks the packages there.
- **Optional dependencies.** On each single package's Workshop page you can link the All
  pack (and the reverse) as related items. No package requires another.

## Held back, and not on the Workshop

`workshop.json` marks an item `hold` with the reason, and the publisher skips it. At the
moment that is **HoH1 Classes** (`HWP-classes`): the Thief, Gladiator and Witch Hunter are
parked (hidden from character creation), so its page would describe classes a player can't
pick, and the package would only add the Skill 4-6 keys. The All pack still carries it (the
Skill 4-6 keys), but its page and cover don't name it. Remove the `hold` when the classes come
back.

A package with `"workshop": false` in `packages.json` is not on the Workshop at all: it gets no
kit folder, and `tools/build.py --workshop` (which `tools/workshop.py` runs) leaves it out of
the All pack too. Your own build (`tools/build.py`, `/run`) still has it in the All pack. At the
moment that is **The Forsaken Tower** (`campaign`): Steam hid its item (EResult 15 on every
update, no reason given through the API), so it was deleted on 2026-10-28
(`workshop.json` `removed`: item 3828529832).

## The page texts

Every page opens with **Multiplayer supported**, what it requires (Heroes of Hammerwatch II,
any DLC, and that Heroes of Hammerwatch 1 is not needed, with the Workshop stand-ins), then each
module in a line, install steps that repeat the requirements, where the settings are (player
menu > Plus tab), and last a link to the All pack. The All pack's page lists the packages
(each linked to its own page), then install, settings and how to switch modules off.
`tests/test_workshop.py` checks that shape, and that no page names a repo path or developer
step (`DEV_TEXT`).

## The cards

`tools/workshop_art.py` draws each item's picture from the game's own art, so the cards
look like the game and like each other:

- **The frame and fonts.** The gold knotwork frame is the game's panel style
  (`gui/panelstyles.png`); names and notes are the game's pixel fonts (`gui/fonts/empire_*`,
  no smoothing, 1 px outline). Each card is drawn at 480x270 and scaled 3x, nearest
  neighbour.
- **The wordmark.** "HammerwatchPlus" is set in UnifrakturMaguntia, a blackletter face under
  the SIL Open Font License (`tools/fonts/`, licence beside it).
- **The symbols.** Every module has a symbol (`SYMBOLS`): game sprites, or the module's own
  art, several where one doesn't say it (farming's crops and herb, keys' three tiers).
  `python tools/workshop_art.py --sheet` draws them all with their ids, for checking a
  sprite box.
- **The layouts.** Firearms shows every skill with its orbs, by specialization. The specs
  card shows each spec's two skills and their orbs. The Pets card shows every pet the game's Pet Shop sells, by its own shop icon
  (`tweak/pets.sval`), with the features as text under them. A package of up to eight entries gets
  large framed symbols with a note under each name; Quality of Life gets a compact grid. The
  All pack's cover lists every package.

The cards are never committed: the game's art stays in `gamecode/` (gitignored) and the
cards land in `dist/` (`python tools/workshop_art.py` writes `dist/workshop-art/`). Only
Steam gets them, as each item's pictures. Without `gamecode/`, `tools/workshop.py` stops and
says so (`python -m gamelab doctor --fix` makes it). `tests/test_workshop_art.py` checks that
every card lays out and fits under 1 MB.
