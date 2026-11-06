"""Draft target planner/test_stamp.py: no server, browser, game or authored writes."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from planner import __main__ as planner


class PlannerStampTests(unittest.TestCase):
    created_roots = []

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="stamp-", dir=os.environ.get("PLANNER_TEST_TMP_PARENT"))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.created_roots.append(self.root)
        self.data = self.root / "data"
        self.data.mkdir()
        for collection in planner.COLLECTIONS:
            (self.data / collection).mkdir()
        self.first = self.data / "skills" / "alpha.json"
        self.second = self.data / "skills" / "beta.json"
        self.first.write_bytes(b'{"name":"alpha"}\n')
        self.second.write_bytes(b'{"name":"bravo"}\n')
        self.sentinel = self.root / "untouched-sentinel"
        self.sentinel.write_bytes(b"outside the fake DATA tree")
        patcher = mock.patch.object(planner, "DATA", self.data)
        patcher.start()
        self.addCleanup(patcher.stop)

    def future_max(self):
        future = time.time_ns() + 86_400 * 1_000_000_000
        os.utime(self.first, ns=(future, future))
        self.assertGreater(self.first.stat().st_mtime_ns, self.second.stat().st_mtime_ns)

    def test_future_record_does_not_mask_another_record_edit(self):
        self.future_max()
        before = planner.stamp()
        self.second.write_bytes(b'{"name":"delta"}\n')
        self.assertGreater(self.first.stat().st_mtime_ns, self.second.stat().st_mtime_ns)
        self.assertEqual(self.second.read_bytes(), b'{"name":"delta"}\n')
        self.assertNotEqual(planner.stamp(), before)

    def test_content_edit_with_preserved_size_and_mtime_is_detected(self):
        prior = self.second.stat()
        before = planner.stamp()
        self.second.write_bytes(b'{"name":"delta"}\n')
        os.utime(self.second, ns=(prior.st_atime_ns, prior.st_mtime_ns))
        self.assertEqual(self.second.stat().st_size, prior.st_size)
        self.assertEqual(self.second.stat().st_mtime_ns, prior.st_mtime_ns)
        self.assertNotEqual(planner.stamp(), before)

    def test_rename_changes_record_identity_without_count_change(self):
        self.future_max()
        before = planner.stamp()
        self.second.rename(self.second.with_name("renamed.json"))
        self.assertEqual(len(list((self.data / "skills").glob("*.json"))), 2)
        self.assertNotEqual(planner.stamp(), before)

    def test_collection_move_changes_record_identity_without_count_change(self):
        self.future_max()
        before = planner.stamp()
        self.second.rename(self.data / "mods" / self.second.name)
        self.assertEqual(len(list(self.data.glob("*/*.json"))), 2)
        self.assertNotEqual(planner.stamp(), before)

    def test_contents_remain_bound_to_their_record_ids(self):
        self.future_max()
        first_stat, second_stat = self.first.stat(), self.second.stat()
        first_bytes, second_bytes = self.first.read_bytes(), self.second.read_bytes()
        before = planner.stamp()
        self.first.write_bytes(second_bytes)
        self.second.write_bytes(first_bytes)
        os.utime(self.first, ns=(first_stat.st_atime_ns, first_stat.st_mtime_ns))
        os.utime(self.second, ns=(second_stat.st_atime_ns, second_stat.st_mtime_ns))
        self.assertEqual(sorted([self.first.read_bytes(), self.second.read_bytes()]), sorted([first_bytes, second_bytes]))
        self.assertNotEqual(planner.stamp(), before)

    def test_add_remove_changes_token_and_restores_original_content_token(self):
        before = planner.stamp()
        added = self.data / "mods" / "added.json"
        added.write_bytes(b'{"name":"new"}\n')
        self.assertNotEqual(planner.stamp(), before)
        added.unlink()
        self.assertEqual(planner.stamp(), before)

    def test_staged_or_unrelated_files_do_not_trigger_reload(self):
        before = planner.stamp()
        (self.data / "skills" / ".planner-stage.tmp").write_bytes(b"staged contents")
        (self.data / "unlisted-collection").mkdir()
        (self.data / "unlisted-collection" / "record.json").write_bytes(b"not a collection")
        self.assertEqual(planner.stamp(), before)
        self.assertEqual(self.sentinel.read_bytes(), b"outside the fake DATA tree")

    def test_changed_invalid_json_bytes_still_trigger_data_reload(self):
        self.second.write_bytes(b"\xff")
        self.future_max()
        before = planner.stamp()
        self.second.write_bytes(b"\xfe")
        self.assertNotEqual(planner.stamp(), before)

    def test_embedded_record_delimiters_cannot_hide_a_record_split(self):
        self.first.write_bytes(b"x\0skills/beta.json\0y")
        self.second.unlink()
        before = planner.stamp()
        self.first.write_bytes(b"x")
        self.second.write_bytes(b"y")
        self.assertNotEqual(planner.stamp(), before)

    def test_unchanged_tree_is_stable_and_read_only(self):
        before = {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.root.rglob("*") if path.is_file()}
        token = planner.stamp()
        self.assertIsInstance(token, str)
        self.assertTrue(token)
        self.assertEqual(planner.stamp(), token)
        after = {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
