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

This builds every package (`tools/build.py`) and writes one folder per Workshop item to
`dist/workshop/`:

| File | Goes into the uploader's |
|---|---|
| `HWP-<id>.bin` / `HammerwatchPlus-All.bin` | File to upload |
| `preview.png` (640x360, under the uploader's 1 MB limit) | Preview Image |
| `title.txt` | Title |
| `description.txt` (Steam BBCode: the package, its modules, the HoH1 stand-ins, settings, co-op) | Description |
| `changenote.txt` (version, commit, date) | change note, for an update |

`dist/workshop/UPLOAD.txt` lists each item as NEW, UPDATE (with its Workshop link) or HOLD,
based on `workshop.json`.

The texts come from the repo, so fix them there, not in the kit:

- The package line comes from `packages.json` `description`.
- Each module's line comes from its row in README.md's module tables.
- The Heroes of Hammerwatch 1 notes come from each module's `HWP::HoH1::Report` lang
  string, the same text the game shows the player.

`python tools/workshop.py --check` (also in the test suite) fails when a module has no README
line or an item has no `workshop.json` entry.

## 2. Upload, in the game's packager

The Workshop upload is in the game's own `PACKAGER.exe` (in the Heroes of Hammerwatch 2 folder).
It needs your Steam login, and it has no command line, so this step is done by hand:

1. Start Steam, then `PACKAGER.exe`.
2. Choose **Steam Workshop manager** on the toolbar.
3. For a NEW item, open the **Upload new** tab:
   - File to upload: the folder's `.bin`.
   - Preview Image: `preview.png`.
   - Title: paste `title.txt`.
   - Description: paste `description.txt`.
   - Visibility: start with **Hidden** or **Friends only** to check the page, then make it
     Public.
4. Press **Upload**. The first time, Steam may ask you to accept the Workshop legal agreement
   (steamcommunity.com/sharedfiles/workshoplegalagreement). Accept it and upload again.
5. Open the item's Workshop page. Copy the number after `?id=` in its URL into
   `workshop.json` under that item (`"item_id": "<number>"`) and commit it. The next
   `tools/workshop.py` then lists the item as UPDATE.
6. For an UPDATE, the manager lists your published items. Pick the item, choose the new
   `.bin` (and the image and texts if they changed), and paste `changenote.txt` as the change
   note.

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

## Held back

`workshop.json` marks an item `hold` with the reason. At the moment that is **HoH1 Classes**
(`HWP-classes`): the Thief, Gladiator and Witch Hunter are parked (hidden from character
creation), so the package would only add the Skill 4-6 keys. The All pack still carries it,
which is harmless. Remove the `hold` when the classes come back.
