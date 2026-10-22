"""Negative controls for the read-only install resource manifest (fake trees only)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from gamelab import env


class _DirectorySize:
    def __init__(self, original, size):
        self._original = original
        self.st_size = size

    def __getattr__(self, name):
        return getattr(self._original, name)


class ResourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.cache = (env.REPO / "gamelab/fixtures/cache/res-snapshot-selftest").resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.temp = Path(tempfile.mkdtemp(prefix="case-", dir=self.cache)).resolve()
        self.root = self.temp / "res"
        self.root.mkdir()
        self.links: list[tuple[Path, bool]] = []

    def tearDown(self):
        # Detach links explicitly so recursive cleanup can never enter their targets.
        for path, junction in reversed(self.links):
            if os.path.lexists(path):
                if junction:
                    os.rmdir(path)
                else:
                    path.unlink()
        resolved = self.temp.resolve()
        self.assertTrue(resolved.is_relative_to(self.cache))
        self.assertNotEqual(resolved, self.cache)
        shutil.rmtree(resolved)

    def write(self, name="nested/value.bin", content=b"abcd"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def snapshot(self):
        return env._res_tree_snapshot(self.root)

    def link(self, path, target, junction=False):
        if junction:
            env.make_junction(path, target)
        else:
            try:
                path.symlink_to(target, target_is_directory=target.is_dir())
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314 or exc.errno in (1, 13):
                    self.skipTest(f"symlink creation not permitted: {exc}")
                raise
        self.links.append((path, junction))

    def test_complete_manifest_stable_and_read_only(self):
        path = self.write()
        before = {p: (p.stat().st_mtime_ns, p.read_bytes())
                  for p in self.root.rglob("*") if p.is_file()}
        first = self.snapshot()
        self.assertEqual(first, self.snapshot())
        self.assertEqual(set(first), {".", "nested", "nested/value.bin"})
        self.assertEqual(first["nested/value.bin"], {
            "type": "file", "mtime_ns": path.stat().st_mtime_ns,
            "size": 4, "sha256": hashlib.sha256(b"abcd").hexdigest(),
        })
        for key in (".", "nested"):
            self.assertEqual(set(first[key]), {"type", "mtime_ns"})
        self.assertEqual(before, {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in before})

    def test_nested_add_remove_and_empty_directory_changes(self):
        self.write()
        baseline = self.snapshot()
        added = self.write("nested/added.bin", b"1234")
        self.assertNotEqual(baseline, self.snapshot())
        added.unlink()
        without_added = self.snapshot()
        (self.root / "nested/empty").mkdir()
        with_directory = self.snapshot()
        self.assertIn("nested/empty", with_directory)
        self.assertNotEqual(without_added, with_directory)
        (self.root / "nested/empty").rmdir()
        self.assertNotIn("nested/empty", self.snapshot())
        (self.root / "nested/value.bin").unlink()
        self.assertNotIn("nested/value.bin", self.snapshot())

    def test_same_size_same_mtime_content_change_detected(self):
        path = self.write()
        before = path.stat()
        first = self.snapshot()
        path.write_bytes(b"wxyz")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        second = self.snapshot()
        self.assertEqual(first["nested/value.bin"]["size"], second["nested/value.bin"]["size"])
        self.assertEqual(first["nested/value.bin"]["mtime_ns"], second["nested/value.bin"]["mtime_ns"])
        self.assertNotEqual(first["nested/value.bin"]["sha256"], second["nested/value.bin"]["sha256"])

    def test_undefined_directory_size_jitter_is_ignored(self):
        self.write()
        original_stat = os.stat
        original_lstat = os.lstat

        def sized(original, size):
            def observe(*args, **kwargs):
                result = original(*args, **kwargs)
                return _DirectorySize(result, size) if stat.S_ISDIR(result.st_mode) else result
            return observe

        with mock.patch.object(env.os, "stat", side_effect=sized(original_stat, 4096)), \
                mock.patch.object(env.os, "lstat", side_effect=sized(original_lstat, 4096)):
            first = self.snapshot()
        with mock.patch.object(env.os, "stat", side_effect=sized(original_stat, 0)), \
                mock.patch.object(env.os, "lstat", side_effect=sized(original_lstat, 0)):
            second = self.snapshot()
        self.assertEqual(first, second)
        self.assertTrue(all("size" not in row for row in first.values() if row["type"] == "dir"))

    def test_file_change_during_hash_fails_closed(self):
        path = self.write()
        original_hash = hashlib.sha256
        changed = False

        def mutate():
            nonlocal changed
            if not changed:
                changed = True
                path.write_bytes(b"changed-length")
            return original_hash()

        with mock.patch.object(env.hashlib, "sha256", side_effect=mutate):
            with self.assertRaisesRegex(OSError, "changed while snapshotting"):
                self.snapshot()

    def test_directory_membership_race_fails_even_with_restored_mtime(self):
        self.write("value.bin")
        old = self.root.stat()
        original_hash = hashlib.sha256
        changed = False

        def mutate():
            nonlocal changed
            if not changed:
                changed = True
                (self.root / "new.bin").write_bytes(b"new")
                os.utime(self.root, ns=(old.st_atime_ns, old.st_mtime_ns))
            return original_hash()

        with mock.patch.object(env.hashlib, "sha256", side_effect=mutate):
            with self.assertRaisesRegex(OSError, "directory changed while snapshotting"):
                self.snapshot()

    def test_unreadable_and_disappearing_entries_fail_closed(self):
        path = self.write()
        original_stat = os.stat
        original_lstat = os.lstat
        for failure in (PermissionError("denied"), FileNotFoundError("disappeared")):
            def failing(original):
                def observe(candidate, *args, **kwargs):
                    if Path(candidate) == path:
                        raise failure
                    return original(candidate, *args, **kwargs)
                return observe
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(env.os, "stat", side_effect=failing(original_stat)), \
                        mock.patch.object(env.os, "lstat", side_effect=failing(original_lstat)):
                    with self.assertRaises(OSError):
                        self.snapshot()

    def check_link_target_and_cycle(self, junction):
        target = self.temp / "target"
        target.mkdir()
        content = target / "linked.bin"
        content.write_bytes(b"abcd")
        link = self.root / "linked"
        self.link(link, target, junction)
        first = self.snapshot()
        self.assertEqual(first["linked"]["link_target"], os.readlink(link))
        self.assertEqual(first["linked"]["link_mtime_ns"], link.lstat().st_mtime_ns)
        self.assertEqual(first["linked/linked.bin"]["sha256"], hashlib.sha256(b"abcd").hexdigest())
        old = content.stat()
        content.write_bytes(b"wxyz")
        os.utime(content, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertNotEqual(first["linked/linked.bin"], self.snapshot()["linked/linked.bin"])
        self.link(self.root / "loop", self.root, junction)
        looped = self.snapshot()
        self.assertTrue(looped["loop"]["cycle"])
        self.assertFalse(any(key.startswith("loop/") for key in looped))
        self.assertEqual(len(looped), 4)

    def test_directory_symlink_target_and_cycle(self):
        self.check_link_target_and_cycle(False)

    @unittest.skipUnless(os.name == "nt", "Windows junction negative control")
    def test_directory_junction_target_and_cycle(self):
        self.check_link_target_and_cycle(True)

    @unittest.skipUnless(os.name == "nt", "Windows junction topology negative control")
    def test_junction_retarget_is_detected(self):
        first_target = self.temp / "first"
        second_target = self.temp / "second"
        for target in (first_target, second_target):
            target.mkdir()
            (target / "same.bin").write_bytes(b"same")
        link = self.root / "linked"
        self.link(link, first_target, True)
        first = self.snapshot()
        os.rmdir(link)
        env.make_junction(link, second_target)
        second = self.snapshot()
        self.assertNotEqual(first["linked"]["link_target"], second["linked"]["link_target"])
        self.assertEqual(first["linked/same.bin"]["sha256"], second["linked/same.bin"]["sha256"])

    def test_link_retarget_is_detected(self):
        first_target = self.temp / "first.bin"
        second_target = self.temp / "second.bin"
        first_target.write_bytes(b"same")
        second_target.write_bytes(b"same")
        link = self.root / "linked.bin"
        self.link(link, first_target)
        first = self.snapshot()
        link.unlink()
        link.symlink_to(second_target)
        second = self.snapshot()
        self.assertNotEqual(first["linked.bin"]["link_target"], second["linked.bin"]["link_target"])
        self.assertEqual(first["linked.bin"]["sha256"], second["linked.bin"]["sha256"])


if __name__ == "__main__":
    unittest.main()
