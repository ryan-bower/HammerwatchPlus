#!/usr/bin/env python3
"""
hps.py - read and patch the HoH2 persistent save header (saves/<slot>.hps) of the
GameLab game dir. It never writes outside gamelab/env/userdata/.

The game keeps the list of *enabled* resource mods in the save file header as
32-bit hashes of the mod ids, so GameLab enables its mods by patching the lab
save. Layout (little-endian):

    "H2SV" u8 version     3 = no mods enabled, 4 = header carries the mod block below
    u8[3] 0
    u64 saved_ms          when it was written, Unix time in ms; the game loads the slot's
                          rotation file (<slot>.hps / <slot>_N.hps) with the latest
                          (read as an f32 before 2026-10-28, which held only while bit 31
                          of the low word was clear: then the order flipped)
    [mod block, version 4 only]
        name + NUL, u8 (2*n + 1), u8 0, n x u32 modIdHash, u32 0
                          name: a zero-terminated string, empty in most saves
    town section: u32 raw, u32 comp, lz4 block (just u32 0 in a new profile)
    u32 characterCount, then per character: u32 hash, section, u32 hasRun, [run data]
    ...
    u32 trailer = first 4 bytes of MD5(file[:-4])

modIdHash = HashString(mod.ID) = MurmurHash3_x86_32(utf-8 id, seed 0xf808409c).
Read out of HWR2.exe build 25509441 (the native behind the script declaration
`uint HashString(const string &in str)`) and checked against 57 id/hash pairs the
game itself printed (docs/RE_NOTES.md 2026-10-17), so any id can be enabled
without first running the game with it.

    hps.py show                          # current rotation file, header, enabled mod hashes
    hps.py hash <id>...                  # print HashString(id)
    hps.py set gamelab-probe gamelab-hands   # enable exactly these ids
    hps.py add <id|0xhash>...            # enable in addition to the current list
    hps.py remove <id|0xhash>...
    hps.py clear
    hps.py restore                       # put back the newest backup made by this tool

Every write first copies the save to hps_backups/ in its GameLab userdata root
(the private worker root in slot mode).
Never run this while the GameLab game is open.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import struct
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Preserve direct ``python gamelab/hps.py`` use as well as package imports.
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO))
from gamelab import runtime

_SLOT = runtime.current()
USERDATA = _SLOT.game_dir.parent if _SLOT else REPO / "gamelab" / "env" / "userdata"
SAVES = _SLOT.game_dir / "saves" if _SLOT else USERDATA / "game" / "saves"
BACKUP_DIR = _SLOT.game_dir / "hps_backups" if _SLOT else USERDATA / "hps_backups"
MAGIC = b"H2SV"
HASH_SEED = 0xF808409C


def hash_string(s: str, seed: int = HASH_SEED) -> int:
    """The engine's HashString: MurmurHash3_x86_32 over the UTF-8 bytes."""
    data, m = s.encode("utf-8"), 0xFFFFFFFF
    c1, c2, h, n = 0xCC9E2D51, 0x1B873593, seed, len(s.encode("utf-8"))

    def rotl(x, r):
        return ((x << r) | (x >> (32 - r))) & m
    for i in range(0, n // 4 * 4, 4):
        k = rotl(struct.unpack_from("<I", data, i)[0] * c1 & m, 15) * c2 & m
        h = (rotl(h ^ k, 13) * 5 + 0xE6546B64) & m
    tail = data[n // 4 * 4:]
    if tail:
        k = int.from_bytes(tail, "little")
        h ^= rotl(k * c1 & m, 15) * c2 & m
    h ^= n
    h ^= h >> 16
    h = h * 0x85EBCA6B & m
    h ^= h >> 13
    h = h * 0xC2B2AE35 & m
    return h ^ (h >> 16)


class Header:
    def __init__(self, data: bytes):
        if data[:4] != MAGIC:
            raise ValueError("not an H2SV save")
        self.version = data[4]
        self.pad = data[5:8]
        self.saved_ms = struct.unpack_from("<Q", data, 8)[0]
        pos = 16
        self.mods: list[int] = []
        self.mod_name = b""
        # version 3 = plain header, version 4 = header followed by the enabled-mod block
        if self.version == 4:
            block = self._parse_mod_block(data, pos)
            if block is None:
                raise ValueError("version 4 save without a readable mod block")
            self.mods, self.mod_name, pos = block
        elif self.version != 3:
            raise ValueError(f"unsupported save version {self.version}")
        self.body_offset = pos
        if not self._section_at(data, pos):
            raise ValueError("town section not where expected; header layout changed?")

    @staticmethod
    def _section_at(data: bytes, pos: int) -> bool:
        """A town section starts at pos: u32 raw, u32 comp, block - or a lone u32 0
        when the profile has no town yet (a new profile before its first run)."""
        if pos + 8 > len(data):
            return False
        raw, comp = struct.unpack_from("<II", data, pos)
        if raw == 0:
            return True
        return 0 < comp <= raw < 64 * 1024 * 1024 and pos + 8 + comp <= len(data)

    @classmethod
    def _parse_mod_block(cls, data: bytes, pos: int):
        """Return (hashes, name, pos after block) when a well-formed mod block sits at pos."""
        nul = data.find(b"\0", pos, pos + 256)
        if nul < 0:
            return None
        name = data[pos:nul]
        pos = nul    # the block layout below starts at the name's terminator
        if pos + 7 > len(data) or data[pos + 2] != 0:
            return None
        count_byte = data[pos + 1]
        if count_byte % 2 == 0:
            return None
        n = (count_byte - 1) // 2
        end = pos + 3 + 4 * n + 4
        if end > len(data) or struct.unpack_from("<I", data, end - 4)[0] != 0:
            return None
        if not cls._section_at(data, end):
            return None
        return list(struct.unpack_from("<%dI" % n, data, pos + 3)), name, end

    def encode(self) -> bytes:
        version = 4 if self.mods else 3
        out = MAGIC + bytes([version]) + self.pad + struct.pack("<Q", self.saved_ms)
        if self.mods:
            if 2 * len(self.mods) + 1 > 255:
                raise ValueError("more mods than the one-byte count this tool understands")
            out += self.mod_name + bytes([0, 2 * len(self.mods) + 1, 0])
            out += struct.pack("<%dI" % len(self.mods), *self.mods)
            out += b"\0\0\0\0"
        return out


def trailer_ok(data: bytes) -> bool:
    return data[-4:] == hashlib.md5(data[:-4]).digest()[:4]


def read_save(path: Path) -> tuple[bytes, Header]:
    data = path.read_bytes()
    hdr = Header(data)
    if not trailer_ok(data):
        print(f"warning: {path} trailer does not match MD5; file may be damaged or the format changed", file=sys.stderr)
    return data, hdr


def _slot_root() -> Path:
    current = runtime.current()
    if (current is None or current.pool_id != _SLOT.pool_id or current.slot_id != _SLOT.slot_id
            or current.game_dir != _SLOT.game_dir or current.manifest != _SLOT.manifest):
        sys.exit("refusing HPS access: authenticated runtime slot changed")
    return _SLOT.game_dir.parent


def _ordinary_under(path: Path, root: Path, *, directory=False, missing=False) -> None:
    """Do not resolve through a link into another worker (or outside userdata)."""
    path, root = Path(path).absolute(), Path(root).absolute()
    try:
        relative = path.relative_to(root)
    except ValueError:
        sys.exit(f"refusing HPS path outside {root}: {path}")
    if any(part in (".", "..") for part in relative.parts):
        sys.exit(f"refusing unnormalized HPS path: {path}")
    current = root
    for part in (None, *relative.parts):
        if part is not None:
            current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing and current == path:
                return
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            sys.exit(f"refusing redirected HPS path: {current}")
        if current != path or directory:
            valid = stat.S_ISDIR(info.st_mode)
        else:
            valid = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        if not valid:
            sys.exit(f"refusing nonordinary HPS path: {current}")


def guard(path: Path) -> None:
    """Legacy userdata guard; slot writes are confined to authenticated own saves."""
    path = Path(path)
    if _SLOT:
        root = _slot_root()
        expected = _SLOT.game_dir / "saves"
        if SAVES != expected or USERDATA != root:
            sys.exit("refusing HPS access: private save roots changed")
        if expected.absolute() not in path.absolute().parents:
            sys.exit(f"refusing save outside current slot: {path}")
        _ordinary_under(path, root, missing=True)
    else:
        if runtime.current() is not None:
            sys.exit("refusing HPS access: serial module acquired a runtime slot")
        if USERDATA.resolve() not in path.resolve().parents:
            sys.exit(f"refusing to write {path}: hps.py only writes saves under {USERDATA}")


def _backups(*, create=False) -> Path:
    if _SLOT:
        root = _slot_root()
        if USERDATA != root or BACKUP_DIR != _SLOT.game_dir / "hps_backups":
            sys.exit("refusing HPS access: private backup root changed")
        _ordinary_under(BACKUP_DIR, root, directory=True, missing=True)
    if create:
        BACKUP_DIR.mkdir(parents=not bool(_SLOT), exist_ok=True)
        if _SLOT:
            _ordinary_under(BACKUP_DIR, root, directory=True)
    return BACKUP_DIR


def write_save(path: Path, data: bytes, hdr: Header) -> Path:
    guard(path)
    body = data[hdr.body_offset:-4]
    new = hdr.encode() + body
    new += hashlib.md5(new).digest()[:4]
    backup_root = _backups(create=True)
    backup = backup_root / f"{path.stem}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.hps"
    # Exclusive creation prevents two same-second edits from replacing a backup.
    with backup.open("xb") as target:
        try:
            with path.open("rb") as source:
                shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        except BaseException:
            target.close()
            try:
                backup.unlink()  # only this invocation's exclusively created file
            except OSError:
                pass  # retain the original copy/flush error; no save mutation
            raise
    path.write_bytes(new)
    return backup


def enable(path: Path, ids: list[str]) -> list[int]:
    """Library entry for the fixture recipes: enable exactly `ids` in the save at `path`."""
    data, hdr = read_save(path)
    hdr.mods = [hash_string(i) for i in ids]
    write_save(path, data, hdr)
    return hdr.mods


def resolve(tokens: list[str]) -> list[int]:
    return [int(t, 16) if re.fullmatch(r"0x[0-9a-fA-F]{1,8}", t) else hash_string(t) for t in tokens]


def slot_files(slot: int, saves: Path = SAVES) -> list[Path]:
    """All rotation files of a slot: <slot>.hps and <slot>_N.hps."""
    return sorted(p for p in saves.glob(f"{slot}*.hps") if re.fullmatch(rf"{slot}(_\d+)?", p.stem))


def current_save(slot: int, saves: Path = SAVES) -> Path | None:
    """The game loads the rotation file written last (the header's saved_ms, offset 8)."""
    best = None
    for p in slot_files(slot, saves):
        try:
            counter = struct.unpack_from("<Q", p.read_bytes(), 8)[0]
        except Exception:
            continue
        key = (counter, p.stat().st_mtime)
        if best is None or key > best[0]:
            best = (key, p)
    return best[1] if best else None


def save_path(args) -> Path:
    p = Path(args.save) if args.save else current_save(args.slot)
    if p is None or not p.is_file():
        sys.exit(f"no save for slot {args.slot} in {SAVES}" if p is None else f"save not found: {p}")
    return p


def cmd_show(args):
    path = save_path(args)
    data, hdr = read_save(path)
    print(f"{path}: version {hdr.version}, saved {hdr.saved_ms} ms, {len(data):,} bytes, trailer {'ok' if trailer_ok(data) else 'BAD'}")
    print(f"enabled mods ({len(hdr.mods)}):")
    names = {hash_string(i): i for i in args.ids or []}
    for h in hdr.mods:
        print(f"  {h:#010x}  {names.get(h, '')}")


def cmd_hash(args):
    for i in args.ids:
        print(f"{hash_string(i):#010x}  {i}")


def _apply(args, new_mods: list[int]):
    path = save_path(args)
    data, hdr = read_save(path)
    hdr.mods = new_mods
    backup = write_save(path, data, hdr)
    print(f"patched {path} (backup {backup}); enabled hashes: {[f'{h:#010x}' for h in new_mods]}")


def cmd_set(args):
    _apply(args, resolve(args.ids))


def cmd_add(args):
    _, hdr = read_save(save_path(args))
    mods = list(hdr.mods)
    mods += [h for h in resolve(args.ids) if h not in mods]
    _apply(args, mods)


def cmd_remove(args):
    _, hdr = read_save(save_path(args))
    drop = set(resolve(args.ids))
    _apply(args, [h for h in hdr.mods if h not in drop])


def cmd_clear(args):
    _apply(args, [])


BACKUP_NAME = re.compile(r"^(?P<stem>.+)_(?P<ts>\d{8}_\d{6})(?:_[0-9a-f]{32})?\.hps$")


def cmd_restore(args):
    """Copy the newest backup back over the rotation file it was taken from."""
    backups = []
    backup_root = _backups()
    for p in (backup_root.glob("*.hps") if backup_root.is_dir() else []):
        if _SLOT:
            _ordinary_under(p, _slot_root())
        m = BACKUP_NAME.match(p.name)
        if not m:
            continue
        if args.save is not None:
            wanted = Path(args.save).stem == m.group("stem")
        else:
            wanted = re.fullmatch(rf"{args.slot}(_\d+)?", m.group("stem")) is not None
        if wanted:
            backups.append((m.group("ts"), p.stat().st_mtime_ns, m.group("stem"), p))
    if not backups:
        sys.exit(f"no backups for slot {args.slot} in {BACKUP_DIR}")
    _, _, stem, src = max(backups)
    dst = SAVES / f"{stem}.hps"
    guard(dst)
    shutil.copy2(src, dst)
    print(f"restored {dst} from {src}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--save", help="explicit .hps path (default: the slot's newest rotation file in the GameLab game dir)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show"); p.add_argument("ids", nargs="*", help="ids to label in the listing"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("hash"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_hash)
    p = sub.add_parser("set"); p.add_argument("ids", nargs="*"); p.set_defaults(fn=cmd_set)
    p = sub.add_parser("add"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_add)
    p = sub.add_parser("remove"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_remove)
    sub.add_parser("clear").set_defaults(fn=cmd_clear)
    sub.add_parser("restore").set_defaults(fn=cmd_restore)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
