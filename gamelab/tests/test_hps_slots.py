"""HPS mutations stay inside disposable authenticated-slot stand-ins."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gamelab import runtime


SOURCE = Path(__file__).resolve().parents[1] / "hps.py"


def load_hps(context):
    spec = importlib.util.spec_from_file_location("hps_slot_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    with patch.object(runtime, "current", return_value=context):
        spec.loader.exec_module(module)
    return module


def save_bytes():
    raw = b"H2SV\x03\x00\x00\x00" + struct.pack("<QII", 1234, 0, 0)
    return raw + hashlib.md5(raw).digest()[:4]


class HpsSlotsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hps-slots-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.slots = []
        for slot_id in ("worker-1", "worker-2"):
            game = self.root / "pool" / slot_id / "game"
            (game / "saves").mkdir(parents=True)
            self.slots.append(SimpleNamespace(pool_id="pool", slot_id=slot_id, game_dir=game,
                                              manifest={"manifest_path": str(self.root / "pool/pool.json"),
                                                        "token": "authenticated-test-token"}))
        self.context = self.slots[0]
        self.hps = load_hps(self.context)
        self.current = patch.object(runtime, "current", return_value=self.context).start()
        self.addCleanup(patch.stopall)
        patch("subprocess.Popen", side_effect=AssertionError("no process allowed")).start()
        self.path = self.context.game_dir / "saves/0.hps"
        self.path.write_bytes(save_bytes())

    def test_slot_roots_bound_at_import_and_legacy_paths_preserved(self):
        self.assertEqual(self.hps.USERDATA, self.context.game_dir.parent)
        self.assertEqual(self.hps.SAVES, self.context.game_dir / "saves")
        self.assertEqual(self.hps.BACKUP_DIR, self.context.game_dir / "hps_backups")
        legacy = load_hps(None)
        self.assertEqual(legacy.USERDATA, legacy.REPO / "gamelab/env/userdata")
        self.assertEqual(legacy.SAVES, legacy.USERDATA / "game/saves")
        self.assertEqual(legacy.BACKUP_DIR, legacy.USERDATA / "hps_backups")

    def test_context_authentication_failure_at_import_never_falls_back_to_legacy(self):
        with patch.object(runtime, "current", side_effect=ValueError("uninspectable lease")):
            spec = importlib.util.spec_from_file_location("hps_refused_test", SOURCE)
            with self.assertRaisesRegex(ValueError, "uninspectable lease"):
                spec.loader.exec_module(importlib.util.module_from_spec(spec))

    def test_legacy_writes_keep_existing_userdata_scope_and_backup_location(self):
        legacy = load_hps(None)
        legacy.USERDATA = self.root / "serial"
        legacy.SAVES = legacy.USERDATA / "game/saves"
        legacy.BACKUP_DIR = legacy.USERDATA / "hps_backups"
        legacy.SAVES.mkdir(parents=True)
        path = legacy.SAVES / "0.hps"
        path.write_bytes(save_bytes())
        with patch.object(runtime, "current", return_value=None):
            legacy.enable(path, ["legacy"])
        self.assertEqual(legacy.Header(path.read_bytes()).mods, [legacy.hash_string("legacy")])
        self.assertEqual(next(legacy.BACKUP_DIR.glob("*.hps")).read_bytes(), save_bytes())

    def test_serial_module_cannot_be_reused_after_slot_context_is_added(self):
        legacy = load_hps(None)
        legacy.USERDATA = self.root
        with self.assertRaises(SystemExit):
            legacy.enable(self.path, ["forbidden"])
        self.assertEqual(self.path.read_bytes(), save_bytes())

    def test_enable_edits_own_save_with_original_bytes_in_private_backup(self):
        original = self.path.read_bytes()
        hashes = self.hps.enable(self.path, ["gamelab-probe", "stash"])
        self.assertEqual(hashes, [self.hps.hash_string("gamelab-probe"), self.hps.hash_string("stash")])
        self.assertEqual(self.hps.Header(self.path.read_bytes()).mods, hashes)
        self.assertTrue(self.hps.trailer_ok(self.path.read_bytes()))
        backups = list(self.hps.BACKUP_DIR.glob("*.hps"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertFalse((self.root / "pool/worker-2/game/hps_backups").exists())
        self.assertFalse((self.root / "pool/worker-1/hps_backups").exists())

    def test_two_contexts_use_disjoint_primary_and_backup_paths(self):
        other = load_hps(self.slots[1])
        other_path = other.SAVES / "0.hps"
        other_path.write_bytes(save_bytes())
        with patch.object(runtime, "current", return_value=self.slots[0]):
            self.hps.enable(self.path, ["first"])
        with patch.object(runtime, "current", return_value=self.slots[1]):
            other.enable(other_path, ["second"])
        self.assertNotEqual(self.hps.BACKUP_DIR, other.BACKUP_DIR)
        self.assertEqual(self.hps.Header(self.path.read_bytes()).mods, [self.hps.hash_string("first")])
        self.assertEqual(other.Header(other_path.read_bytes()).mods, [other.hash_string("second")])
        self.assertEqual(len(list(self.hps.BACKUP_DIR.glob("*.hps"))), 1)
        self.assertEqual(len(list(other.BACKUP_DIR.glob("*.hps"))), 1)

    def test_sibling_save_refused_before_backup_or_source_mutation(self):
        sibling = self.slots[1].game_dir / "saves/0.hps"
        sibling.write_bytes(save_bytes())
        original = sibling.read_bytes()
        with self.assertRaises(SystemExit):
            self.hps.enable(sibling, ["forbidden"])
        self.assertEqual(sibling.read_bytes(), original)
        self.assertFalse(self.hps.BACKUP_DIR.exists())

    def test_serial_and_non_save_paths_refused_in_slot_mode(self):
        for target in (self.root / "legacy/game/saves/0.hps", self.context.game_dir / "other.hps"):
            with self.subTest(path=target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(save_bytes())
                with self.assertRaises(SystemExit):
                    self.hps.enable(target, ["forbidden"])
                self.assertEqual(target.read_bytes(), save_bytes())

    def test_changed_or_missing_context_refuses_cached_module_writes(self):
        for value in (None, self.slots[1]):
            with self.subTest(context=value), patch.object(runtime, "current", return_value=value):
                with self.assertRaises(SystemExit):
                    self.hps.enable(self.path, ["forbidden"])
        self.assertEqual(self.path.read_bytes(), save_bytes())
        self.assertFalse(self.hps.BACKUP_DIR.exists())

    def test_uninspectable_current_lease_refuses_before_backup(self):
        with patch.object(runtime, "current", side_effect=ValueError("lease denied")):
            with self.assertRaisesRegex(ValueError, "lease denied"):
                self.hps.enable(self.path, ["forbidden"])
        self.assertFalse(self.hps.BACKUP_DIR.exists())

    def test_backup_root_cannot_be_rebound_to_sibling_or_legacy(self):
        for target in (self.slots[1].game_dir / "hps_backups", self.root / "legacy/hps_backups"):
            with self.subTest(path=target), patch.object(self.hps, "BACKUP_DIR", target):
                with self.assertRaises(SystemExit):
                    self.hps.enable(self.path, ["forbidden"])
                self.assertFalse(target.exists())
                self.assertEqual(self.path.read_bytes(), save_bytes())

    def test_root_globals_cannot_be_rebound_to_expand_save_scope(self):
        with patch.object(self.hps, "SAVES", self.slots[1].game_dir / "saves"):
            with self.assertRaises(SystemExit):
                self.hps.enable(self.path, ["forbidden"])

    def test_reparse_save_ancestor_refuses_without_following_exists(self):
        original_lstat = Path.lstat
        def redirected(path, *args, **kwargs):
            if path == self.hps.SAVES:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_nlink=1, st_file_attributes=0x400)
            return original_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", redirected):
            with self.assertRaises(SystemExit):
                self.hps.enable(self.path, ["forbidden"])
        self.assertEqual(self.path.read_bytes(), save_bytes())
        self.assertFalse(self.hps.BACKUP_DIR.exists())

    def test_reparse_backup_directory_refuses_before_save_mutation(self):
        self.hps.BACKUP_DIR.mkdir()
        original_lstat = Path.lstat
        def redirected(path, *args, **kwargs):
            if path == self.hps.BACKUP_DIR:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_nlink=1, st_file_attributes=0x400)
            return original_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", redirected):
            with self.assertRaises(SystemExit):
                self.hps.enable(self.path, ["forbidden"])
        self.assertEqual(self.path.read_bytes(), save_bytes())

    def test_save_hardlink_alias_refuses(self):
        os.link(self.path, self.root / "alias.hps")
        with self.assertRaises(SystemExit):
            self.hps.enable(self.path, ["forbidden"])
        self.assertFalse(self.hps.BACKUP_DIR.exists())

    def test_same_second_backups_are_distinct_and_restore_recognizes_new_names(self):
        with patch.object(self.hps.time, "strftime", return_value="20261031_123456"):
            self.hps.enable(self.path, ["first"])
            first_edit = self.path.read_bytes()
            self.hps.enable(self.path, ["second"])
        backups = list(self.hps.BACKUP_DIR.glob("*.hps"))
        self.assertEqual(len(backups), 2)
        self.assertEqual(len({path.name for path in backups}), 2)
        second_backup = next(path for path in backups if path.read_bytes() == first_edit)
        os.utime(second_backup, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))
        self.hps.cmd_restore(SimpleNamespace(slot=0, save=None))
        self.assertEqual(self.path.read_bytes(), first_edit)

    def test_exclusive_backup_collision_preserves_existing_backup_and_source(self):
        self.hps.BACKUP_DIR.mkdir()
        existing = self.hps.BACKUP_DIR / ("0_20261031_123456_" + "a" * 32 + ".hps")
        existing.write_bytes(b"existing-backup")
        with patch.object(self.hps.time, "strftime", return_value="20261031_123456"), \
                patch.object(self.hps.uuid, "uuid4", return_value=SimpleNamespace(hex="a" * 32)):
            with self.assertRaises(FileExistsError):
                self.hps.enable(self.path, ["forbidden"])
        self.assertEqual(existing.read_bytes(), b"existing-backup")
        self.assertEqual(self.path.read_bytes(), save_bytes())

    def test_backup_copy_error_preserves_source_and_does_not_publish_partial(self):
        def broken(source, destination):
            destination.write(b"partial")
            raise OSError("backup copy failed")
        with patch.object(self.hps.shutil, "copyfileobj", side_effect=broken):
            with self.assertRaisesRegex(OSError, "backup copy failed"):
                self.hps.enable(self.path, ["forbidden"])
        self.assertEqual(self.path.read_bytes(), save_bytes())
        self.assertEqual(list(self.hps.BACKUP_DIR.glob("*.hps")), [])

    def test_backup_fsync_error_preserves_original_save(self):
        with patch.object(self.hps.os, "fsync", side_effect=OSError("backup fsync failed")):
            with self.assertRaisesRegex(OSError, "backup fsync failed"):
                self.hps.enable(self.path, ["forbidden"])
        self.assertEqual(self.path.read_bytes(), save_bytes())
        self.assertEqual(list(self.hps.BACKUP_DIR.glob("*.hps")), [])

    def test_restore_rejects_aliased_backup_before_replacing_destination(self):
        self.hps.BACKUP_DIR.mkdir()
        backup = self.hps.BACKUP_DIR / "0_20261031_123456.hps"
        backup.write_bytes(b"alias-content")
        os.link(backup, self.root / "backup-alias.hps")
        with self.assertRaises(SystemExit):
            self.hps.cmd_restore(SimpleNamespace(slot=0, save=None))
        self.assertEqual(self.path.read_bytes(), save_bytes())

    def test_legacy_backup_name_still_restores_in_private_slot(self):
        self.hps.BACKUP_DIR.mkdir()
        original = save_bytes()
        (self.hps.BACKUP_DIR / "0_20261031_123456.hps").write_bytes(original)
        self.path.write_bytes(b"modified")
        self.hps.cmd_restore(SimpleNamespace(slot=0, save=None))
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
