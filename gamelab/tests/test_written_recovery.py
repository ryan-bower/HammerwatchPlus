"""Journal interruption/retry controls; temporary files only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gamelab.runner import remember_written, restore_written


class WrittenRecovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-written-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.results = self.root / "results"
        self.results.mkdir()

    def two_files(self):
        files = [self.root / name for name in ("first.cfg", "second.cfg")]
        for i, file in enumerate(files):
            file.write_bytes(b"original-" + bytes([i]))
            remember_written(self.results, file)
            file.write_bytes(b"edited")
        return files

    def fail_second(self, files):
        original_write = Path.write_bytes

        def write(path, data):
            if path == files[1]:
                raise PermissionError("one-shot second restoration failure")
            return original_write(path, data)

        with patch.object(Path, "write_bytes", write):
            with self.assertRaises(PermissionError):
                restore_written(self.results)

    def test_partial_restoration_preserves_every_backup_until_all_files_restored(self):
        files = self.two_files()
        entries = json.loads((self.results / "written.json").read_text())
        self.fail_second(files)
        self.assertTrue(all(Path(row["orig"]).is_file() for row in entries))
        restore_written(self.results)
        for i, file in enumerate(files):
            self.assertEqual(file.read_bytes(), b"original-" + bytes([i]))
        self.assertEqual(restore_written(self.results), [])

    def test_partial_restoration_can_be_retried_without_missing_original(self):
        files = self.two_files()
        self.fail_second(files)
        restore_written(self.results)
        self.assertEqual(files[1].read_bytes(), b"original-\x01")
        self.assertFalse((self.results / "written.json").exists())

    def test_failed_new_journal_write_preserves_existing_recovery_entries(self):
        first = self.root / "first.cfg"
        first.write_bytes(b"first-original")
        remember_written(self.results, first)
        first.write_bytes(b"first-edited")
        journal = self.results / "written.json"
        previous = journal.read_bytes()
        second = self.root / "second.cfg"
        second.write_bytes(b"second-original")
        original_write = Path.write_text

        def fail_journal(path, text, *args, **kwargs):
            if '"path":' in text and '"orig":' in text:
                original_write(path, "{", *args, **kwargs)
                raise OSError("interrupted journal write")
            return original_write(path, text, *args, **kwargs)

        with patch.object(Path, "write_text", fail_journal):
            with self.assertRaises(OSError):
                remember_written(self.results, second)
        self.assertEqual(journal.read_bytes(), previous)
        restore_written(self.results)
        self.assertEqual(first.read_bytes(), b"first-original")
        self.assertEqual(second.read_bytes(), b"second-original")


if __name__ == "__main__":
    unittest.main()
