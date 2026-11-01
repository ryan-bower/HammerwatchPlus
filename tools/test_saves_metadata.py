"""Backup metadata boundaries using only explicitly fake save paths.

The target is the sibling saves.py in either tools/ or a complete ignored snapshot.
A fake gamepaths module is installed before target import, so no real discovery runs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).with_name("saves.py")


class FakeSaves:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m-", dir=os.environ.get("HWP_FAKE_SAVES_ROOT"))
        self.root = Path(self.temp.name).resolve()
        self.backups = self.root / "b"
        self.dirs = {name: self.root / "current" / name for name in ("cloud", "local", "game_backups")}
        for directory in self.dirs.values():
            directory.mkdir(parents=True)
        self.current = self.dirs["cloud"] / "slot.hps"
        self.current.write_bytes(b"current player state")
        (self.root / "sentinel").write_bytes(b"outside save dirs")
        (self.root / "answers.json").write_text('{"no_hoh1": true}', encoding="utf-8")
        fake = types.ModuleType("gamepaths")
        fake.SAVES_BACKUP = self.backups
        fake.real_save_dirs = lambda: dict(self.dirs)
        spec = importlib.util.spec_from_file_location("_isolated_saves_metadata", TARGET)
        self.saves = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"gamepaths": fake}), patch.object(sys, "path", sys.path.copy()):
            spec.loader.exec_module(self.saves)
        self.ref = self.backups / "2000-01-01T00-00-00"
        (self.ref / "cloud").mkdir(parents=True)
        self.copy = self.ref / "cloud" / "slot.hps"
        self.copy.write_bytes(b"backed up player state")
        self.meta = {"taken": self.ref.name, "sources": {key: str(value) for key, value in self.dirs.items()},
                     "files": {key: {} for key in self.dirs}}
        self.meta["files"]["cloud"]["slot.hps"] = self.digest(self.copy.read_bytes())
        self.write_manifest(self.meta)

    @staticmethod
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.temp.cleanup()

    def write_manifest(self, value):
        raw = value if isinstance(value, str) else json.dumps(value)
        (self.ref / "manifest.json").write_text(raw, encoding="utf-8")

    def stamp(self, value=None):
        value = value if value is not None else {"sources": self.meta["sources"], "backup": self.ref.name}
        raw = value if isinstance(value, str) else json.dumps(value)
        (self.backups / "confirmed.json").write_text(raw, encoding="utf-8")

    def state(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}


class SaveMetadataTests(unittest.TestCase):
    def unchanged(self, fixture, action, expect):
        before = fixture.state()
        error = None
        try:
            value = action()
        except Exception as caught:
            error = caught
        self.assertEqual(fixture.state(), before, "Refusal changed current saves, metadata or sentinels")
        if error is not None:
            self.fail(f"Invalid metadata must refuse safely, not raise {type(error).__name__}: {error}")
        self.assertTrue(expect(value), f"Invalid metadata was accepted: {value!r}")

    def test_valid_manifest_and_confirmation_control(self):
        with FakeSaves() as fixture:
            fixture.stamp()
            self.assertEqual(fixture.saves.intact(fixture.ref), [])
            self.assertEqual(fixture.saves.confirmation_problems(), [])
            self.assertEqual(fixture.saves.restore(fixture.ref.name), 0)
            self.assertEqual(fixture.current.read_bytes(), b"backed up player state")
            self.assertEqual((fixture.root / "sentinel").read_bytes(), b"outside save dirs")

    def test_confirmation_schema_errors_are_problems_without_writes(self):
        invalid = ("{", "[]", "null", {}, {"sources": [], "backup": "x"},
                   {"sources": {"cloud": 7}, "backup": "x"},
                   {"sources": {"unknown": "x"}, "backup": "x"},
                   {"sources": {}, "backup": ["x"]})
        for value in invalid:
            with self.subTest(value=value), FakeSaves() as fixture:
                fixture.stamp(value)
                self.unchanged(fixture, fixture.saves.confirmation_problems, lambda result: bool(result))

    def test_manifest_schema_errors_refuse_intact_restore_verify_and_backup(self):
        for label in ("truncated", "array", "missing-files", "list-files", "list-family", "integer-hash", "bad-hash", "unknown-family"):
            with self.subTest(label=label), FakeSaves() as fixture:
                value = json.loads(json.dumps(fixture.meta))
                if label == "truncated":
                    value = "{"
                elif label == "array":
                    value = "[]"
                elif label == "missing-files":
                    value.pop("files")
                elif label == "list-files":
                    value["files"] = []
                elif label == "list-family":
                    value["files"]["cloud"] = []
                elif label == "integer-hash":
                    value["files"]["cloud"]["slot.hps"] = 7
                elif label == "bad-hash":
                    value["files"]["cloud"]["slot.hps"] = "not a sha256"
                else:
                    value["files"]["unrecognized"] = {}
                fixture.write_manifest(value)
                for name, action, expect in (
                    ("intact", lambda: fixture.saves.intact(fixture.ref), lambda result: isinstance(result, list) and bool(result)),
                    ("restore", lambda: fixture.saves.restore(fixture.ref.name), lambda result: result != 0),
                    ("verify", lambda: fixture.saves.verify(fixture.ref), lambda result: result != 0),
                    ("backup", fixture.saves.backup, lambda result: result != 0),
                ):
                    with self.subTest(entrypoint=name):
                        self.unchanged(fixture, action, expect)

    def test_confirmation_cannot_reference_a_backup_outside_the_backup_root(self):
        for absolute in (False, True):
            with self.subTest(absolute=absolute), FakeSaves() as fixture:
                other = fixture.root / "other"
                (other / "cloud").mkdir(parents=True)
                (other / "cloud/slot.hps").write_bytes(fixture.copy.read_bytes())
                (other / "manifest.json").write_text(json.dumps(fixture.meta), encoding="utf-8")
                fixture.stamp({"sources": fixture.meta["sources"], "backup": str(other) if absolute else "../other"})
                self.unchanged(fixture, fixture.saves.confirmation_problems, lambda result: bool(result))

    def test_parent_escape_restore_preserves_current_files_and_external_sentinel(self):
        with FakeSaves() as fixture:
            payload = fixture.backups / "sentinel"
            payload.write_bytes(b"escaped payload")
            fixture.meta["files"]["cloud"] = {"../../sentinel": fixture.digest(payload.read_bytes())}
            fixture.write_manifest(fixture.meta)
            self.unchanged(fixture, lambda: fixture.saves.restore(fixture.ref.name), lambda result: result != 0)

    def test_absolute_path_manifest_refuses_before_any_current_file_is_deleted(self):
        with FakeSaves() as fixture:
            sentinel = fixture.root / "sentinel"
            fixture.meta["files"]["cloud"] = {str(sentinel): fixture.digest(sentinel.read_bytes())}
            fixture.write_manifest(fixture.meta)
            self.unchanged(fixture, lambda: fixture.saves.restore(fixture.ref.name), lambda result: result != 0)

    def test_invalid_windows_names_are_rejected_without_filesystem_probe(self):
        invalid = ("../slot.hps", "sub/../slot.hps", "./slot.hps", "sub//slot.hps", "sub\\slot.hps",
                   "Q:/outside.hps", "//server/share/slot.hps", "slot:stream", "NUL", "slot. ", "bad?.hps",
                   "CONIN$", "CONOUT$", "nul .txt",
                   *(prefix + chr(code) for prefix in ("COM", "LPT") for code in (185, 178, 179)))
        for relative in invalid:
            with self.subTest(relative=relative), FakeSaves() as fixture:
                fixture.meta["files"]["cloud"] = {relative: fixture.digest(b"irrelevant")}
                fixture.write_manifest(fixture.meta)
                unsafe = fixture.ref / "cloud" / relative
                original = Path.is_file
                original_lstat = Path.lstat

                def no_unsafe_probe(path, *args, **kwargs):
                    if str(path) == str(unsafe):
                        raise AssertionError("Unsafe manifest filename reached a filesystem probe")
                    return original(path, *args, **kwargs)

                def no_unsafe_lstat(path, *args, **kwargs):
                    if str(path) == str(unsafe):
                        raise AssertionError("Unsafe manifest filename reached lstat")
                    return original_lstat(path, *args, **kwargs)

                before = fixture.state()
                with patch.object(Path, "is_file", no_unsafe_probe), patch.object(Path, "lstat", no_unsafe_lstat):
                    try:
                        result = fixture.saves.intact(fixture.ref)
                    except Exception as error:
                        self.fail(f"Invalid path must refuse before filesystem probes: {error}")
                self.assertTrue(result)
                self.assertEqual(fixture.state(), before)

    def test_case_aliases_in_manifest_are_rejected(self):
        with FakeSaves() as fixture:
            fixture.meta["files"]["cloud"]["SLOT.HPS"] = fixture.meta["files"]["cloud"]["slot.hps"]
            fixture.write_manifest(fixture.meta)
            self.unchanged(fixture, lambda: fixture.saves.intact(fixture.ref), lambda result: bool(result))

    def test_reparse_backup_file_is_refused_from_stat_contract(self):
        with FakeSaves() as fixture:
            original = Path.lstat

            def reparse(path, *args, **kwargs):
                if path == fixture.copy:
                    return types.SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", reparse):
                self.unchanged(fixture, lambda: fixture.saves.intact(fixture.ref), lambda result: bool(result))

    def test_reparse_backup_ancestor_is_refused_from_stat_contract(self):
        with FakeSaves() as fixture:
            original = Path.lstat

            def reparse(path, *args, **kwargs):
                if path == fixture.ref / "cloud":
                    return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", reparse):
                self.unchanged(fixture, lambda: fixture.saves.intact(fixture.ref), lambda result: bool(result))

    def test_reparse_restore_target_is_refused_before_current_backup(self):
        with FakeSaves() as fixture:
            original = Path.lstat

            def reparse(path, *args, **kwargs):
                if path == fixture.current:
                    return types.SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", reparse):
                self.unchanged(fixture, lambda: fixture.saves.restore(fixture.ref.name), lambda result: result != 0)

    def test_hardlinked_restore_destination_cannot_truncate_external_peer(self):
        with FakeSaves() as fixture:
            fixture.current.unlink()
            try:
                os.link(fixture.root / "sentinel", fixture.current)
            except OSError as error:
                self.skipTest(f"Fake-tree hardlinks unavailable: {error}")
            self.unchanged(fixture, lambda: fixture.saves.restore(fixture.ref.name), lambda result: result != 0)

    def test_metadata_leaf_and_backup_root_reparse_bits_refuse(self):
        for label in ("manifest", "confirmation", "backup-root"):
            with self.subTest(label=label), FakeSaves() as fixture:
                fixture.stamp()
                target = {"manifest": fixture.ref / "manifest.json", "confirmation": fixture.backups / "confirmed.json",
                          "backup-root": fixture.backups}[label]
                original = Path.lstat

                def reparse(path, *args, **kwargs):
                    if path == target:
                        return types.SimpleNamespace(st_mode=stat.S_IFDIR if label == "backup-root" else stat.S_IFREG,
                                                     st_file_attributes=0x400)
                    return original(path, *args, **kwargs)

                with patch.object(Path, "lstat", reparse):
                    self.unchanged(fixture, fixture.saves.confirmation_problems, lambda result: bool(result))

    def test_hardlinked_metadata_leaf_refuses(self):
        for name in ("manifest.json", "confirmed.json"):
            with self.subTest(name=name), FakeSaves() as fixture:
                fixture.stamp()
                target = fixture.ref / name if name == "manifest.json" else fixture.backups / name
                peer = fixture.root / "metadata-peer"
                peer.write_bytes(target.read_bytes())
                target.unlink()
                try:
                    os.link(peer, target)
                except OSError as error:
                    self.skipTest(f"Fake-tree hardlinks unavailable: {error}")
                self.unchanged(fixture, fixture.saves.confirmation_problems, lambda result: bool(result))

    def test_extra_doctor_stamp_fields_remain_compatible(self):
        with FakeSaves() as fixture:
            fixture.stamp({"sources": fixture.meta["sources"], "backup": fixture.ref.name,
                           "confirmed_by": "doctor --fix", "files": {"cloud": 1, "local": 0, "game_backups": 0},
                           "no_saves_yet": False, "ambiguities_overridden": []})
            self.assertEqual(fixture.saves.confirmation_problems(), [])


    def test_empty_reparse_source_root_refuses_before_copytree(self):
        with FakeSaves() as fixture:
            target = fixture.dirs["local"]
            original = Path.lstat

            def reparse(path, *args, **kwargs):
                if path == target:
                    return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", reparse):
                self.unchanged(fixture, fixture.saves.backup, lambda result: result != 0)

    def test_empty_reparse_source_directory_refuses_before_copytree(self):
        with FakeSaves() as fixture:
            target = fixture.dirs["cloud"] / "empty"
            target.mkdir()
            original = Path.lstat

            def reparse(path, *args, **kwargs):
                if path == target:
                    return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", reparse):
                self.unchanged(fixture, fixture.saves.backup, lambda result: result != 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
