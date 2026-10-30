"""Create a NEW local play profile; never patch an existing player save.

The empty H2SV body is a null town section and zero characters. The mod header,
HashString and MD5 trailer use the format documented in gamelab/hps.py. That
module's lab-only write guard stays intact; only its pure encoding is reused.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import tempfile
import time
from pathlib import Path

from gamelab import hps


def empty_profile(ids: list[str], name: str, *, saved_ms: int | None = None) -> bytes:
    encoded_name = name.encode("utf-8")
    if not encoded_name or b"\0" in encoded_name or len(encoded_name) > 240:
        raise ValueError("profile name must be 1-240 UTF-8 bytes without NUL")
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("a fresh modded profile needs distinct mod ids")
    body = struct.pack("<II", 0, 0)  # null town, no characters
    seed = hps.MAGIC + b"\x03\0\0\0" + struct.pack("<Q", saved_ms or int(time.time() * 1000)) + body
    header = hps.Header(seed)
    header.mods = [hps.hash_string(i) for i in ids]
    header.mod_name = encoded_name
    data = header.encode() + body
    return data + hashlib.md5(data).digest()[:4]


def select_local_profile(config: bytes, slot: int) -> bytes:
    """Preserve all unrelated config bytes, including CRLF and a possible UTF-8 BOM."""
    newline = b"\r\n" if b"\r\n" in config else b"\n"
    for key, value in ((b"g_save_slot", str(slot).encode()), (b"g_save_slot_cloud", b"0")):
        pattern = rb"(?m)^((?:\xef\xbb\xbf)?[ \t]*" + key + rb")[ \t]+[^\r\n]*"
        if re.search(pattern, config):
            config = re.sub(pattern, lambda m: m[1] + b" " + value, config)
        else:
            if config and not config.endswith(b"\n"):
                config += newline
            config += key + b" " + value + newline
    return config


def unused_slot(saves: Path) -> int:
    # Rotations count even if <slot>.hps is absent. Never overwrite any slot.
    used = set()
    for file in saves.glob("*.hps"):
        match = re.fullmatch(r"(\d+)(?:_\d+)?", file.stem)
        if match:
            used.add(int(match[1]))
    slot = 0
    while slot in used:
        slot += 1
    return slot


def _profile_records(data: bytes) -> tuple[dict | None, list[dict]]:
    """Read persisted character identities from a fresh native town profile.

    Refuse resumable runs and unknown layouts; preparation exports town-only saves.
    No player record, equipment or compressed section is rewritten here.
    """
    from tools import hwr_archive as hwr

    if not hps.trailer_ok(data):
        raise ValueError("Native profile checksum does not match")
    pos = hps.Header(data).body_offset

    def integer():
        nonlocal pos
        if pos + 4 > len(data) - 4:
            raise ValueError("Truncated native profile")
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return value

    def section():
        nonlocal pos
        raw = integer()
        if not raw:
            return None
        compressed = integer()
        if not 0 < compressed <= raw <= 64 * 1024 * 1024 or pos + compressed > len(data) - 4:
            raise ValueError("Invalid native profile section")
        value, end = hwr.decode_svalue(hwr.lz4_decompress(data[pos:pos + compressed], raw))
        pos += compressed
        if end != raw:
            raise ValueError("Unexpected native profile section tail")
        return value

    town = section()
    count = integer()
    if count > 100:
        raise ValueError("Unexpected character count")
    characters = []
    for _ in range(count):
        key = integer()
        record = section()
        if integer():
            raise ValueError("A prepared profile must not contain an active dungeon run")
        if key:
            if not isinstance(record, dict) or not all(k in record for k in ("class", "level", "name")):
                raise ValueError("Incomplete native character record")
            characters.append({k: record[k] for k in ("class", "level", "name")})
    if pos != len(data) - 4:
        raise ValueError("Unexpected native profile trailer position")
    return town, characters


def characters_in(data: bytes) -> list[dict]:
    return _profile_records(data)[1]


def gold_in(data: bytes) -> int:
    town, _ = _profile_records(data)
    if town is None:
        return 0
    materials = town.get("materials") if isinstance(town, dict) else None
    if (not isinstance(materials, list) or not materials or not isinstance(materials[0], int)
            or isinstance(materials[0], bool) or not 0 <= materials[0] <= 2_147_483_647):
        raise ValueError("Native profile has no valid saved town gold balance")
    return int(materials[0])


def from_native(data: bytes, ids: list[str], name: str) -> bytes:
    characters_in(data)
    # Reuse validated identity encoding; preserve the game's body byte-for-byte.
    fresh = hps.Header(empty_profile(ids, name))
    original = hps.Header(data)
    result = fresh.encode() + data[original.body_offset:-4]
    return result + hashlib.md5(result).digest()[:4]


def create(install: Path, ids: list[str], backup_root: Path, name: str | None = None,
           native_data: bytes | None = None) -> dict:
    """Caller owns the runtime lock, has checked the build and backed up real saves.

    Keep a config backup and receipt before changing the default. Creation uses
    exclusive mode so even an unexpected slot collision cannot replace a save.
    """
    config_path = install / "HWR2.exe.cfg"
    config = config_path.read_bytes() if config_path.exists() else b""
    saves = install / "saves"
    slot = unused_slot(saves)
    name = name or f"HammerwatchPlus {time.strftime('%Y-%m-%d %H:%M:%S')}"
    data = from_native(native_data, ids, name) if native_data is not None else empty_profile(ids, name)
    selected = select_local_profile(config, slot)
    backup = backup_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns()}"
    backup.mkdir(parents=True)
    (backup / "HWR2.exe.cfg.before").write_bytes(config)
    receipt = {"slot": slot, "cloud": False, "name": name, "mods": ids,
               "save": str(saves / f"{slot}.hps"), "config": str(config_path),
               "config_existed": config_path.exists(), "backup": str(backup),
               "characters": characters_in(data), "starting_gold": gold_in(data)}
    (backup / "profile.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    saves.mkdir(exist_ok=True)
    path = saves / f"{slot}.hps"
    with path.open("xb") as file:
        file.write(data)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=install, prefix="HWR2.cfg-", delete=False) as file:
            pending = Path(file.name)
            file.write(selected)
        pending.replace(config_path)
    except OSError:
        # Only our new file is removed; an existing profile is never rewritten.
        path.unlink()
        raise
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return receipt
