"""Publish the Workshop kit (tools/workshop.py) to the Steam Workshop as the Steam user who is
logged in to the running Steam client: the same ISteamUGC calls the game's PACKAGER.exe makes
(STEAMUGC_INTERFACE_VERSION015, through the game's own steam_api64.dll), without its window.

    python tools/workshop_publish.py --dry-run     check Steam, the login and the kit; upload nothing
    python tools/workshop_publish.py               create the new items, update the published ones
    python tools/workshop_publish.py --only HWP-qol,HWP-pets
    python tools/workshop_publish.py --visibility friends    (public, friends, private, unlisted)

Run tools/workshop.py first: this publishes dist/workshop/<item>/ as it is. Each item gets:
its content (a folder holding only the .bin, as a subscriber's
steamapps/workshop/content/619820/<id>/ holds it), title, description, preview, the kit's
gallery/*.png as the page's additional pictures (replacing the ones it has), tags
(workshop.json `tags`), visibility and the kit's change note. An item with no `item_id` in
workshop.json is created first, and its new id is written to workshop.json at once, so a
failure later never leaves an item nobody knows about. Items marked `hold` are skipped.

Steam asks every Workshop author to accept the Workshop legal agreement once; until then the
items stay hidden. The script says so when Steam reports it."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import gamepaths  # noqa: E402

KIT = REPO / "dist" / "workshop"
CONTENT = REPO / "dist" / "workshop-content"
LEDGER = REPO / "workshop.json"
APP_ID = 619820
VISIBILITY = {"public": 0, "friends": 1, "private": 2, "unlisted": 3}  # ERemoteStoragePublishedFileVisibility
FILE_TYPE_COMMUNITY = 0                                                # EWorkshopFileType
RESULT_OK = 1                                                          # EResult
CB_QUERY, CB_CREATE, CB_SUBMIT = 3401, 3403, 3404                      # k_iSteamUGCCallbacks + 1, + 3, + 4
PREVIEW_IMAGE = 0                                                      # EItemPreviewType
LEGAL_URL = "https://steamcommunity.com/sharedfiles/workshoplegalagreement"
PAGE_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={}"
UPDATE_STATUS = {0: "invalid", 1: "preparing config", 2: "preparing content", 3: "uploading content",
                 4: "uploading preview", 5: "committing"}


class CreateItemResult(ctypes.Structure):     # isteamugc.h CreateItemResult_t (pack 8)
    _fields_ = [("result", ctypes.c_int), ("id", ctypes.c_uint64), ("legal", ctypes.c_bool)]


class SubmitItemUpdateResult(ctypes.Structure):  # isteamugc.h SubmitItemUpdateResult_t (pack 8)
    _fields_ = [("result", ctypes.c_int), ("legal", ctypes.c_bool), ("id", ctypes.c_uint64)]


class SteamUGCQueryCompleted(ctypes.Structure):  # isteamugc.h SteamUGCQueryCompleted_t (pack 8)
    _fields_ = [("handle", ctypes.c_uint64), ("result", ctypes.c_int), ("returned", ctypes.c_uint32),
                ("total", ctypes.c_uint32), ("cached", ctypes.c_bool), ("cursor", ctypes.c_char * 256)]


class SteamParamStringArray(ctypes.Structure):
    _fields_ = [("strings", ctypes.POINTER(ctypes.c_char_p)), ("count", ctypes.c_int32)]


class Steam:
    """The flat Steamworks API of the game's steam_api64.dll, as app 619820."""

    def __init__(self):
        dll_path = gamepaths.hoh2_dir() / "steam_api64.dll"
        os.environ["SteamAppId"] = str(APP_ID)   # instead of a steam_appid.txt in the install
        os.environ["SteamGameId"] = str(APP_ID)
        d = self.dll = ctypes.CDLL(str(dll_path))
        u64, vp, b, i, s = ctypes.c_uint64, ctypes.c_void_p, ctypes.c_bool, ctypes.c_int, ctypes.c_char_p
        sig = {
            "SteamAPI_Init": (b, []), "SteamAPI_Shutdown": (None, []), "SteamAPI_RunCallbacks": (None, []),
            "SteamAPI_SteamUGC_v015": (vp, []), "SteamAPI_SteamUtils_v010": (vp, []),
            "SteamAPI_SteamUser_v021": (vp, []),
            "SteamAPI_ISteamUser_BLoggedOn": (b, [vp]), "SteamAPI_ISteamUser_GetSteamID": (u64, [vp]),
            "SteamAPI_ISteamUGC_CreateItem": (u64, [vp, ctypes.c_uint32, i]),
            "SteamAPI_ISteamUGC_StartItemUpdate": (u64, [vp, ctypes.c_uint32, u64]),
            "SteamAPI_ISteamUGC_SetItemTitle": (b, [vp, u64, s]),
            "SteamAPI_ISteamUGC_SetItemDescription": (b, [vp, u64, s]),
            "SteamAPI_ISteamUGC_SetItemVisibility": (b, [vp, u64, i]),
            "SteamAPI_ISteamUGC_SetItemTags": (b, [vp, u64, ctypes.POINTER(SteamParamStringArray)]),
            "SteamAPI_ISteamUGC_SetItemContent": (b, [vp, u64, s]),
            "SteamAPI_ISteamUGC_SetItemPreview": (b, [vp, u64, s]),
            "SteamAPI_ISteamUGC_SubmitItemUpdate": (u64, [vp, u64, s]),
            "SteamAPI_ISteamUGC_AddItemPreviewFile": (b, [vp, u64, s, i]),
            "SteamAPI_ISteamUGC_RemoveItemPreview": (b, [vp, u64, ctypes.c_uint32]),
            "SteamAPI_ISteamUGC_CreateQueryUGCDetailsRequest": (u64, [vp, ctypes.POINTER(u64), ctypes.c_uint32]),
            "SteamAPI_ISteamUGC_SetReturnAdditionalPreviews": (b, [vp, u64, b]),
            "SteamAPI_ISteamUGC_SendQueryUGCRequest": (u64, [vp, u64]),
            "SteamAPI_ISteamUGC_GetQueryUGCNumAdditionalPreviews": (ctypes.c_uint32, [vp, u64, ctypes.c_uint32]),
            "SteamAPI_ISteamUGC_ReleaseQueryUGCRequest": (b, [vp, u64]),
            "SteamAPI_ISteamUGC_GetItemUpdateProgress": (i, [vp, u64, ctypes.POINTER(u64), ctypes.POINTER(u64)]),
            "SteamAPI_ISteamUtils_IsAPICallCompleted": (b, [vp, u64, ctypes.POINTER(b)]),
            "SteamAPI_ISteamUtils_GetAPICallResult": (b, [vp, u64, vp, i, i, ctypes.POINTER(b)]),
        }
        for name, (res, args) in sig.items():
            f = getattr(d, name)
            f.restype, f.argtypes = res, args
        if not d.SteamAPI_Init():
            sys.exit("Steam did not start the API: is the Steam client running and logged in, "
                     "and does this account own Heroes of Hammerwatch II?")
        self.ugc = d.SteamAPI_SteamUGC_v015()
        self.utils = d.SteamAPI_SteamUtils_v010()
        user = d.SteamAPI_SteamUser_v021()
        if not (self.ugc and self.utils and user):
            sys.exit("Steam returned no Workshop interface (ISteamUGC v015)")
        self.logged_on = d.SteamAPI_ISteamUser_BLoggedOn(user)
        self.steam_id = d.SteamAPI_ISteamUser_GetSteamID(user)

    def close(self):
        self.dll.SteamAPI_Shutdown()

    def wait(self, call, struct, callback, progress=None, timeout=1800):
        """Pump callbacks until the API call completes; its result struct, or None."""
        failed = ctypes.c_bool(False)
        end = time.time() + timeout
        last = None
        while time.time() < end:
            self.dll.SteamAPI_RunCallbacks()
            if self.dll.SteamAPI_ISteamUtils_IsAPICallCompleted(self.utils, call, ctypes.byref(failed)):
                out = struct()
                ok = self.dll.SteamAPI_ISteamUtils_GetAPICallResult(
                    self.utils, call, ctypes.byref(out), ctypes.sizeof(out), callback, ctypes.byref(failed))
                return out if ok and not failed.value else None
            if progress:
                last = progress(last)
            time.sleep(0.2)
        return None

    def create(self):
        call = self.dll.SteamAPI_ISteamUGC_CreateItem(self.ugc, APP_ID, FILE_TYPE_COMMUNITY)
        return self.wait(call, CreateItemResult, CB_CREATE, timeout=120) if call else None

    def extra_previews(self, item_id):
        """How many additional pictures the published item has (its gallery), or None."""
        d, ugc = self.dll, self.ugc
        ids = (ctypes.c_uint64 * 1)(item_id)
        q = d.SteamAPI_ISteamUGC_CreateQueryUGCDetailsRequest(ugc, ids, 1)
        try:
            d.SteamAPI_ISteamUGC_SetReturnAdditionalPreviews(ugc, q, True)
            r = self.wait(d.SteamAPI_ISteamUGC_SendQueryUGCRequest(ugc, q), SteamUGCQueryCompleted, CB_QUERY,
                          timeout=60)
            if r is None or r.result != RESULT_OK or r.returned < 1:
                return None
            return d.SteamAPI_ISteamUGC_GetQueryUGCNumAdditionalPreviews(ugc, q, 0)
        finally:
            d.SteamAPI_ISteamUGC_ReleaseQueryUGCRequest(ugc, q)

    def update(self, item_id, title, description, tags, content, preview, visibility, note,
               gallery=(), old_gallery=0):
        """gallery: the item's additional pictures, replacing the old_gallery ones it has."""
        d, ugc = self.dll, self.ugc
        h = d.SteamAPI_ISteamUGC_StartItemUpdate(ugc, APP_ID, item_id)
        arr = (ctypes.c_char_p * len(tags))(*[t.encode() for t in tags])
        steps = {
            "title": d.SteamAPI_ISteamUGC_SetItemTitle(ugc, h, title.encode()),
            "description": d.SteamAPI_ISteamUGC_SetItemDescription(ugc, h, description.encode()),
            "visibility": d.SteamAPI_ISteamUGC_SetItemVisibility(ugc, h, visibility),
            "tags": d.SteamAPI_ISteamUGC_SetItemTags(ugc, h, ctypes.byref(SteamParamStringArray(arr, len(tags)))),
            "content": d.SteamAPI_ISteamUGC_SetItemContent(ugc, h, str(content).encode()),
            "preview": d.SteamAPI_ISteamUGC_SetItemPreview(ugc, h, str(preview).encode()),
        }
        for n in reversed(range(old_gallery)):
            steps[f"removal of old picture {n}"] = d.SteamAPI_ISteamUGC_RemoveItemPreview(ugc, h, n)
        for g in gallery:
            steps[f"picture {g.name}"] = d.SteamAPI_ISteamUGC_AddItemPreviewFile(
                ugc, h, str(g).encode(), PREVIEW_IMAGE)
        bad = [k for k, v in steps.items() if not v]
        if bad:
            return None, f"Steam refused the {', '.join(bad)}"
        call = d.SteamAPI_ISteamUGC_SubmitItemUpdate(ugc, h, note.encode())

        def progress(last):
            done, total = ctypes.c_uint64(), ctypes.c_uint64()
            st = d.SteamAPI_ISteamUGC_GetItemUpdateProgress(ugc, h, ctypes.byref(done), ctypes.byref(total))
            now = (st, done.value * 100 // total.value if total.value else 0)
            if now != last and st:
                print(f"    {UPDATE_STATUS.get(st, st)} {now[1]}%", flush=True)
            return now
        return self.wait(call, SubmitItemUpdateResult, CB_SUBMIT, progress), None


def load_ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def save_ledger(led):
    LEDGER.write_text(json.dumps(led, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def kit_items(led, only):
    """(name, entry, folder) per ledger item to publish, after checking each kit folder."""
    out, problems = [], []
    for name, entry in led["items"].items():
        if only and name not in only:
            continue
        if entry.get("hold"):
            print(f"HOLD   {name}: {entry['hold']}")
            continue
        d = KIT / name
        need = [d / f"{name}.bin", d / "title.txt", d / "description.txt", d / "preview.png", d / "changenote.txt"]
        missing = [p.name for p in need if not p.is_file()]
        if missing:
            problems.append(f"{name}: {', '.join(missing)} missing in {d} (run tools/workshop.py)")
        elif any(f.stat().st_size >= 1024 * 1024 for f in [d / "preview.png", *gallery(d)]):
            problems.append(f"{name}: a picture is 1 MB or more")
        elif not entry.get("tags"):
            problems.append(f"{name}: no tags in workshop.json")
        out.append((name, entry, d))
    if only - set(led["items"]):
        problems.append(f"not in workshop.json: {sorted(only - set(led['items']))}")
    return out, problems


def gallery(d: Path) -> list[Path]:
    """The kit's additional pictures (the All pack's package cards), in order."""
    return sorted((d / "gallery").glob("*.png")) if (d / "gallery").is_dir() else []


def game_running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq HWR2.exe", "/NH"], capture_output=True, text=True)
    return "HWR2.exe" in r.stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="check Steam, the login and the kit; upload nothing")
    ap.add_argument("--only", default="", help="comma-separated item names (workshop.json keys)")
    ap.add_argument("--visibility", choices=sorted(VISIBILITY), default="public")
    args = ap.parse_args(argv)
    led = load_ledger()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    todo, problems = kit_items(led, only)
    if problems:
        for p in problems:
            print("workshop_publish:", p, file=sys.stderr)
        return 1
    if game_running():
        print("workshop_publish: Heroes of Hammerwatch II is running; close it first", file=sys.stderr)
        return 1
    stamp = (KIT / "UPLOAD.txt").read_text(encoding="utf-8").splitlines()[0] if (KIT / "UPLOAD.txt").is_file() else "?"
    print(f"kit: {stamp}")

    steam = Steam()
    try:
        if not steam.logged_on:
            print("workshop_publish: the Steam client is not logged on", file=sys.stderr)
            return 1
        print(f"Steam user {steam.steam_id}, app {APP_ID}, visibility {args.visibility}")
        for name, entry, d in todo:
            what = f"UPDATE {entry['item_id']}" if entry.get("item_id") else "NEW"
            print(f"{what:<17} {name}: {(d / 'title.txt').read_text(encoding='utf-8').strip()}, tags {entry['tags']}")
            if gallery(d):
                old = steam.extra_previews(int(entry["item_id"])) if entry.get("item_id") else 0
                print(f"{'':<17} {len(gallery(d))} gallery pictures, replacing "
                      f"{'?' if old is None else old} on the page")
        if args.dry_run:
            print("dry run: nothing uploaded")
            return 0

        failed = []
        need_legal = False
        for name, entry, d in todo:
            title = (d / "title.txt").read_text(encoding="utf-8").strip()
            if not entry.get("item_id"):
                r = steam.create()
                if r is None or r.result != RESULT_OK:
                    failed.append(f"{name}: create failed (EResult {getattr(r, 'result', None)})")
                    print(f"FAILED {name}: create, EResult {getattr(r, 'result', None)}", flush=True)
                    continue
                entry["item_id"] = str(r.id)
                need_legal |= bool(r.legal)
                save_ledger(led)
                print(f"created {name}: {r.id}", flush=True)
            # the content folder: only the .bin, as a subscriber's workshop folder holds it
            content = CONTENT / name
            if content.exists():
                shutil.rmtree(content)
            content.mkdir(parents=True)
            shutil.copy2(d / f"{name}.bin", content / f"{name}.bin")
            old = steam.extra_previews(int(entry["item_id"])) if gallery(d) else 0
            if old is None:
                failed.append(f"{name}: Steam did not say how many gallery pictures the item has")
                print(f"FAILED {name}: {failed[-1]}", flush=True)
                continue
            print(f"uploading {name} ({entry['item_id']})", flush=True)
            r, why = steam.update(int(entry["item_id"]), title, (d / "description.txt").read_text(encoding="utf-8"),
                                  entry["tags"], content.resolve(), (d / "preview.png").resolve(),
                                  VISIBILITY[args.visibility], (d / "changenote.txt").read_text(encoding="utf-8").strip(),
                                  [g.resolve() for g in gallery(d)], old)
            if r is None or r.result != RESULT_OK:
                code = getattr(r, "result", None)
                failed.append(f"{name}: {why or f'submit failed (EResult {code})'}")
                print(f"FAILED {name}: {failed[-1]}", flush=True)
                continue
            need_legal |= bool(r.legal)
            print(f"published {name}: {PAGE_URL.format(entry['item_id'])}", flush=True)
        if need_legal:
            print(f"\nSteam says this account has not accepted the Workshop legal agreement: the items stay "
                  f"hidden until it is accepted at {LEGAL_URL}")
        for f in failed:
            print("workshop_publish:", f, file=sys.stderr)
        return 1 if failed else 0
    finally:
        steam.close()


if __name__ == "__main__":
    sys.exit(main())
