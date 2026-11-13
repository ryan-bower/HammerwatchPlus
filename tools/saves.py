#!/usr/bin/env python3
"""saves.py - back up, restore and verify the player's real HoH2 saves.

    saves.py backup                 # copy every real save dir to saves-backup/<ts>/ if anything changed
    saves.py restore [--from TS]    # put the newest (or named) backup back, backing up the current state first
    saves.py verify                 # exit 1 unless the real saves hash-match the newest backup
    saves.py list

The real save dirs come from tools/gamepaths.real_save_dirs() (Steam cloud, the
install's local saves/, the game's own save_backups/). saves-backup/ is gitignored
(personal data) and capped at CAP_MB: past the cap `backup` refuses and says so, and the
user prunes.

saves-backup/confirmed.json is written by `python -m gamelab doctor --fix` (or --confirm-saves)
once a backup of this machine's saves is taken, re-hashed and restorable. The launcher
and `install.py modded-prod` refuse while confirmation_problems() is non-empty.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import uuid
import re
import stat
import shutil
import sys
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gamepaths  # noqa: E402

CAP_MB = 200          # declared in README.md; change both together
MANIFEST = "manifest.json"
CONFIRMED = "confirmed.json"
EXIT_CAP = 4


class MetadataError(ValueError):
    """Untrusted backup metadata or a linked path cannot authorize save writes."""


SAVE_KINDS = {"cloud", "local", "game_backups"}
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {f"{prefix}{n}" for prefix in ("COM", "LPT") for n in "123456789\u00b9\u00b2\u00b3"}


def _relative(value: str) -> list[str]:
    if not isinstance(value, str) or not value or "\\" in value or PureWindowsPath(value).drive:
        raise MetadataError("expected an ordinary relative save filename")
    parts = value.split("/")
    if PurePosixPath(value).is_absolute() or any(
            part in ("", ".", "..") or part.endswith((".", " "))
            or part.split(".", 1)[0].rstrip(" ").upper() in WINDOWS_RESERVED
            or any(ord(ch) < 32 or ch in '<>:"|?*' for ch in part) for part in parts):
        raise MetadataError("unsafe or aliased save filename")
    return parts


def _safe_join(root: Path, relative: str | None, *, independent: bool = False) -> Path:
    parts = [] if relative is None else _relative(relative)
    root = Path(root).absolute()
    path = root.joinpath(*parts)
    current = root
    checks = list(reversed(root.parents)) + [root]
    for part in parts:
        current = current / part
        checks.append(current)
    try:
        for entry in checks:
            try:
                info = entry.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise MetadataError("reparse/symlink save paths are not accepted")
            if independent and stat.S_ISREG(info.st_mode) and getattr(info, "st_nlink", 1) > 1:
                raise MetadataError("hardlinked backup metadata or restore target is not independent")
        if not path.resolve().is_relative_to(root.resolve()):
            raise MetadataError("save path escapes its declared directory")
    except OSError as error:
        raise MetadataError(f"cannot validate save path: {error}") from error
    return path


def _source_map(value) -> dict:
    if not isinstance(value, dict) or any(name not in SAVE_KINDS or not isinstance(path, str) or not path
                                          for name, path in value.items()):
        raise MetadataError("invalid backup source mapping")
    return value


def _read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MetadataError(f"unreadable backup JSON: {error}") from error
    if not isinstance(value, dict):
        raise MetadataError("backup JSON must be an object")
    return value


def _backup_ref(ref: Path) -> Path:
    root = Path(gamepaths.SAVES_BACKUP).absolute()
    try:
        relative = Path(ref).absolute().relative_to(root)
    except ValueError as error:
        raise MetadataError("backup reference escapes saves-backup") from error
    if len(relative.parts) != 1:
        raise MetadataError("backup reference must name one backup directory")
    return _safe_join(root, relative.as_posix())


def _load_manifest(ref: Path) -> dict:
    ref = _backup_ref(ref)
    meta = _read_object(_safe_join(ref, MANIFEST, independent=True))
    sources = _source_map(meta.get("sources"))
    files = meta.get("files")
    if not isinstance(files, dict) or set(files) != set(sources):
        raise MetadataError("manifest file families must match its source families")
    normalized = {}
    for name, entries in files.items():
        if not isinstance(entries, dict):
            raise MetadataError("manifest files must be filename/hash mappings")
        seen = set()
        normalized[name] = {}
        for relative, digest in entries.items():
            _relative(relative)
            alias = str(PureWindowsPath(relative)).casefold()
            if alias in seen:
                raise MetadataError("case-aliased manifest filenames")
            seen.add(alias)
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
                raise MetadataError("manifest file hash must be SHA256 hex")
            _safe_join(ref, f"{name}/{relative}", independent=True)
            normalized[name][relative] = digest.lower()
    return {**meta, "files": normalized}


def snapshot() -> dict[str, dict[str, str]]:
    return _snapshot_dirs(gamepaths.real_save_dirs())


def _snapshot_dirs(dirs: dict) -> dict[str, dict[str, str]]:
    """Hash declared save roots only after validating roots and every entry."""
    out = {}
    for name, directory in dirs.items():
        directory = _safe_join(directory, None)
        files = {}
        if directory.is_dir():
            for entry in sorted(directory.rglob("*")):
                relative = entry.relative_to(directory).as_posix()
                safe = _safe_join(directory, relative)
                if safe.is_file():
                    files[relative] = hashlib.sha256(safe.read_bytes()).hexdigest()
        out[name] = files
    return out


def backups() -> list[Path]:
    root = gamepaths.SAVES_BACKUP
    _safe_join(root, CONFIRMED)
    found = []
    if root.is_dir():
        for entry in root.iterdir():
            if entry.name.startswith(".pending-"):
                continue  # Unpublished private staging is never a committed backup.
            safe = _safe_join(root, entry.name)
            if safe.is_dir() and _safe_join(safe, MANIFEST, independent=True).is_file():
                found.append(safe)
    return sorted(found)


def dir_bytes(d: Path) -> int:
    directory = _safe_join(d, None)
    total = 0
    if directory.is_dir():
        for entry in directory.rglob("*"):
            safe = _safe_join(directory, entry.relative_to(directory).as_posix())
            if safe.is_file():
                total += safe.stat().st_size
    return total


def backup(quiet: bool = False) -> int:
    try:
        return _backup(quiet)
    except (MetadataError, OSError) as error:
        print(f"REFUSED: save backup failed: {error}")
        return 1


def _no_pending_restore() -> None:
    root = _safe_join(gamepaths.SAVES_BACKUP, None)
    if root.is_dir():
        for path in root.glob(".restore-*.json"):
            value = _read_object(_safe_join(root, path.name, independent=True))
            if value.get("status") not in ("committed", "rolled-back"):
                raise MetadataError(f"unfinished restore recovery retained at {path}; inspect before continuing")


def _remove_owned(path: Path, parent: Path, prefix: str) -> None:
    path = Path(path).absolute()
    if path.parent != Path(parent).absolute() or not path.name.startswith(prefix):
        raise MetadataError("refusing cleanup outside the owned staging directory")
    safe = _safe_join(parent, path.name)
    if safe.exists():
        shutil.rmtree(safe)


def _next_backup(root: Path, previous: list[Path]) -> Path:
    stem = time.strftime("%Y-%m-%dT%H-%M-%S")
    if previous and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}(?:-\d+)?", previous[-1].name):
        stem = max(stem, previous[-1].name[:19])
    for index in range(10000):
        name = stem if index == 0 else f"{stem}-{index:04d}"
        path = _safe_join(root, name)
        if not path.exists():
            return path
    raise MetadataError("backup name budget exhausted; no existing backup overwritten")


def _take_backup(quiet: bool = False, *, expected: dict | None = None,
                 expected_sources: dict | None = None) -> tuple[int, Path | None]:
    _no_pending_restore()
    dirs = gamepaths.real_save_dirs()
    sources = _source_map({name: str(path) for name, path in dirs.items()})
    snap = _snapshot_dirs(dirs)
    if expected is not None and (snap != expected or sources != expected_sources):
        raise MetadataError("current saves changed before preservation")
    previous = backups()
    if previous:
        meta = _load_manifest(previous[-1])
        if meta["files"] == snap and meta["sources"] == sources:
            damaged = intact(previous[-1])
            if damaged:
                raise MetadataError(f"latest matching backup is damaged: {damaged[:5]}")
            if {name: str(path) for name, path in gamepaths.real_save_dirs().items()} != sources \
                    or _snapshot_dirs(dirs) != snap:
                raise MetadataError("current saves changed while checking the existing backup")
            if not quiet:
                print(f"unchanged since {previous[-1].name}; verified backup copies")
            return 0, previous[-1]
    need = sum(dir_bytes(path) for path in dirs.values())
    have = dir_bytes(gamepaths.SAVES_BACKUP)
    if have + need > CAP_MB * 1024 * 1024:
        print(f"REFUSED: saves-backup/ is {have / 2**20:.1f} MB and this backup adds {need / 2**20:.1f} MB, "
              f"over the {CAP_MB} MB cap declared in README.md. Prune old backups, then run again.")
        return EXIT_CAP, None
    root = _safe_join(gamepaths.SAVES_BACKUP, None)
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
    try:
        for name, directory in dirs.items():
            if directory.is_dir():
                shutil.copytree(directory, stage / name, symlinks=True, copy_function=shutil.copy2)
        staged = {name: stage / name for name in dirs}
        if _snapshot_dirs(staged) != snap:
            raise MetadataError("copied backup bytes differ from the initial snapshot")
        if {name: str(path) for name, path in gamepaths.real_save_dirs().items()} != sources \
                or _snapshot_dirs(dirs) != snap:
            raise MetadataError("source saves changed while copying; no backup published")
        manifest = _safe_join(stage, MANIFEST, independent=True)
        manifest.write_text(json.dumps({"taken": time.strftime("%Y-%m-%dT%H-%M-%S"),
                                         "sources": sources, "files": snap}, indent=1), encoding="utf-8")
        with manifest.open("r+b") as stream:
            os.fsync(stream.fileno())
        damaged = intact(stage)
        if damaged:
            raise MetadataError(f"staged backup is damaged: {damaged[:5]}")
        destination = _next_backup(root, previous)
        if dir_bytes(root) > CAP_MB * 1024 * 1024:
            print(f"REFUSED: staged backup including metadata exceeds the {CAP_MB} MB cap; nothing published")
            return EXIT_CAP, None
        if {name: str(path) for name, path in gamepaths.real_save_dirs().items()} != sources \
                or _snapshot_dirs(dirs) != snap:
            raise MetadataError("source saves changed before publication; no backup published")
        os.rename(stage, destination)
        stage = None
        if not quiet:
            print(f"backed up {sum(len(value) for value in snap.values())} files to saves-backup/{destination.name}")
        return 0, destination
    finally:
        if stage is not None:
            _remove_owned(stage, root, ".pending-")


def _create_parents(parent: Path, created: list[Path]) -> None:
    missing = []
    current = _safe_join(parent, None)
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            raise MetadataError("restore target volume is unavailable")
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def _cleanup_parents(created: list[Path]) -> None:
    for directory in reversed(created):
        try:
            _safe_join(directory, None).rmdir()
        except OSError:
            pass  # Existing/nonempty parents, including concurrent data, are retained.


def _write_restore_journal(path: Path, state: dict, plan: list[dict]) -> None:
    value = {**state, "plan": [{key: str(item) if isinstance(item, Path) else item
                                for key, item in row.items()} for row in plan]}
    temporary = _safe_join(path.parent, path.name + ".tmp", independent=True)
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=1)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _staged_restore(src: Path, meta: dict) -> int:
    dirs = gamepaths.real_save_dirs()
    sources = _source_map({name: str(path) for name, path in dirs.items()})
    for name, directory in dirs.items():
        _safe_join(directory, None)
        for relative in meta["files"].get(name, {}):
            _safe_join(directory, relative, independent=True)
    before = _snapshot_dirs(dirs)
    code, preserved = _take_backup(quiet=True, expected=before, expected_sources=sources)
    if code:
        return code
    if intact(preserved):
        raise MetadataError("pre-restore preservation backup is not intact")
    token = uuid.uuid4().hex[:12]
    journal = _safe_join(gamepaths.SAVES_BACKUP, f".restore-{token}.json", independent=True)
    state = {"status": "preparing", "source_backup": str(src), "preserved_backup": str(preserved)}
    plan, created = [], []
    expected_after = dict(before)
    try:
        for name, directory in dirs.items():
            if name not in meta["files"]:
                continue
            _create_parents(directory.parent, created)
            stage = Path(tempfile.mkdtemp(prefix=f".rs-{token}-", dir=directory.parent))
            old = _safe_join(directory.parent, f".ro-{token}-{name}")
            if old.exists():
                raise MetadataError("restore recovery directory already exists")
            row = {"name": name, "target": directory, "stage": stage, "old": old,
                   "had_target": directory.exists(), "old_moved": False, "installed": False}
            plan.append(row)
            if directory.is_dir():
                shutil.copytree(directory, stage, symlinks=True, dirs_exist_ok=True, copy_function=shutil.copy2)
            for entry in stage.rglob("*"):
                relative = entry.relative_to(stage).as_posix()
                safe = _safe_join(stage, relative)
                if safe.is_file() and relative not in meta["files"][name]:
                    safe.unlink()
            for relative in meta["files"][name]:
                destination = _safe_join(stage, relative, independent=True)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_safe_join(src, f"{name}/{relative}", independent=True), destination)
            if _snapshot_dirs({name: stage})[name] != meta["files"][name]:
                raise MetadataError("prepared restore bytes differ from the source backup")
            expected_after[name] = meta["files"][name]
        if {name: str(path) for name, path in gamepaths.real_save_dirs().items()} != sources \
                or _snapshot_dirs(dirs) != before or intact(src):
            raise MetadataError("current saves or source backup changed before restore commit")
        state["status"] = "committing"
        _write_restore_journal(journal, state, plan)
        for row in plan:
            if row["had_target"]:
                os.replace(row["target"], row["old"])
                row["old_moved"] = True
                _write_restore_journal(journal, state, plan)
            os.replace(row["stage"], row["target"])
            row["installed"] = True
            _write_restore_journal(journal, state, plan)
        if _snapshot_dirs(dirs) != expected_after or intact(src) or verify(src):
            raise MetadataError("committed restore readback or source integrity failed")
        state["status"] = "committed"
        _write_restore_journal(journal, state, plan)
    except (OSError, MetadataError) as error:
        failures = []
        for row in reversed(plan):
            try:
                if row["installed"]:
                    os.replace(row["target"], row["stage"])
                    row["installed"] = False
                if row["old_moved"]:
                    os.replace(row["old"], row["target"])
                    row["old_moved"] = False
            except OSError as rollback_error:
                failures.append(str(rollback_error))
        if not failures:
            for row in plan:
                if row["stage"].exists() and _snapshot_dirs({row["name"]: row["stage"]})[row["name"]] != meta["files"][row["name"]]:
                    # Preparation failures may leave partial private bytes, but no
                    # current root was installed yet; those are safe to clean.
                    if journal.exists():
                        failures.append("replacement data changed during rollback; retained for inspection")
        state["status"] = "recovery-required" if failures else "rolled-back"
        state["error"] = str(error)
        state["rollback_errors"] = failures
        if journal.exists() or failures:
            try:
                _write_restore_journal(journal, state, plan)
            except OSError as journal_error:
                print(f"recovery journal update failed; earlier journal/material retained: {journal_error}")
        if not failures:
            for row in plan:
                _remove_owned(row["stage"], row["target"].parent, ".rs-")
            _cleanup_parents(created)
            if journal.exists():
                journal.unlink()
        print(f"REFUSED: restore failed: {error}" + (f"; recovery retained at {journal}" if failures else "; current roots rolled back"))
        return 1
    # An interruption BaseException deliberately leaves journal, stages and old
    # roots available; the next backup/restore refuses pending recovery.
    cleanup_errors = []
    for row in plan:
        try:
            _remove_owned(row["old"], row["target"].parent, ".ro-")
        except (OSError, MetadataError) as error:
            cleanup_errors.append(str(error))
            print(f"restore committed; old recovery directory retained: {error}")
    try:
        _cleanup_parents(created)
    except (OSError, MetadataError) as error:
        cleanup_errors.append(str(error))
    if cleanup_errors:
        state["cleanup_errors"] = cleanup_errors
        try:
            _write_restore_journal(journal, state, plan)
        except (OSError, MetadataError) as error:
            print(f"restore committed; existing journal retained after cleanup update failure: {error}")
    else:
        try:
            journal.unlink()
        except OSError as error:
            print(f"restore committed; completed journal retained: {error}")
    print(f"restored {src.name}")
    return 0


def _backup(quiet: bool = False) -> int:
    code, _ = _take_backup(quiet)
    return code


def diff(a: dict, b: dict) -> list[str]:
    """Files added, removed or changed between two snapshot() results."""
    return sorted(f"{d}/{f}" for d in set(a) | set(b)
                  for f in set(a.get(d, {})) | set(b.get(d, {})) if a.get(d, {}).get(f) != b.get(d, {}).get(f))


def verify(against: Path | None = None) -> int:
    try:
        return _verify(against)
    except MetadataError as error:
        print(f"REFUSED: invalid save metadata/path: {error}")
        return 1


def _verify(against: Path | None = None) -> int:
    """Real saves vs a backup: the newest by default, or `against` (restore checks its source)."""
    prev = backups()
    ref = against or (prev[-1] if prev else None)
    if ref is None:
        print("no backup to verify against")
        return 1
    want = _load_manifest(ref)["files"]
    bad = diff(want, snapshot())
    if bad:
        print(f"real saves differ from {ref.name}: {sorted(bad)[:20]}")
        return 1
    print(f"real saves match {ref.name}")
    return 0


def intact(ref: Path) -> list[str]:
    """Rehash ordinary independent copies; malformed metadata is a refusal."""
    try:
        want = _load_manifest(ref)["files"]
        bad = []
        for name, files in want.items():
            for relative, digest in files.items():
                path = _safe_join(ref, f"{name}/{relative}", independent=True)
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    bad.append(f"{name}/{relative}")
        return sorted(bad)
    except (MetadataError, OSError) as error:
        return [f"invalid backup metadata/path: {error}"]


def confirmation_problems() -> list[str]:
    """Confirmed source mapping and independently intact backup, failing closed."""
    try:
        _no_pending_restore()
        stamp = _safe_join(gamepaths.SAVES_BACKUP, CONFIRMED, independent=True)
        if not stamp.is_file():
            return ["save backups not confirmed on this machine: run `python -m gamelab doctor --fix` "
                    "(it confirms by itself unless something is ambiguous)"]
        value = _read_object(stamp)
        sources = _source_map(value.get("sources"))
        backup_name = value.get("backup")
        if len(_relative(backup_name)) != 1:
            raise MetadataError("confirmation must name one backup directory")
        ref = _safe_join(gamepaths.SAVES_BACKUP, backup_name)
        now = {name: str(path) for name, path in gamepaths.real_save_dirs().items()}
        out = []
        if sources != now:
            out.append(f"the real save dirs changed since confirmation ({sources} -> {now}); re-confirm")
        if not _safe_join(ref, MANIFEST, independent=True).is_file():
            out.append(f"the confirmed backup saves-backup/{backup_name} is gone; re-confirm")
        else:
            out += [f"confirmed backup copy damaged: {bad}" for bad in intact(ref)[:10]]
        return out
    except (MetadataError, OSError) as error:
        return [f"invalid save confirmation: {error}"]


def restore(ts: str | None) -> int:
    try:
        return _restore(ts)
    except (MetadataError, OSError) as error:
        print(f"REFUSED: save restore failed: {error}")
        return 1


def _restore(ts: str | None) -> int:
    _no_pending_restore()
    previous = backups()
    src = next((path for path in previous if path.name == ts), None) if ts else (previous[-1] if previous else None)
    if src is None:
        print(f"no backup {ts or ''}")
        return 1
    damaged = intact(src)
    if damaged:
        print(f"REFUSED: backup {src.name} is damaged, restoring it would lose data: {damaged[:20]}")
        return 1
    return _staged_restore(src, _load_manifest(src))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup")
    sub.add_parser("verify")
    sub.add_parser("list")
    r = sub.add_parser("restore")
    r.add_argument("--from", dest="ts")
    a = ap.parse_args(argv)
    if a.cmd == "backup":
        return backup()
    if a.cmd == "verify":
        return verify()
    if a.cmd == "restore":
        return restore(a.ts)
    for p in backups():
        print(p.name, f"{dir_bytes(p) / 2**20:.2f} MB")
    print(f"total {dir_bytes(gamepaths.SAVES_BACKUP) / 2**20:.2f} MB of {CAP_MB} MB cap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
