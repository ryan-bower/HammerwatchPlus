"""Backup/restore fault boundaries; only the sibling fake gamepaths fixture is used."""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("_metadata_fixture", Path(__file__).with_name("test_saves_metadata.py"))
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
FakeSaves = fixture_module.FakeSaves


class Interrupted(BaseException):
    pass


class SaveTransactionTests(unittest.TestCase):
    def setUp(self):
        self.f = FakeSaves()
        self.addCleanup(self.f.temp.cleanup)
        self.s = self.f.saves
        self.f.current.unlink()
        self.f.copy.unlink()
        self.f.meta["files"] = {name: {} for name in self.f.dirs}
        for name, filenames in {"cloud": ("a.hps", "b.hps"), "local": ("a.hps",), "game_backups": ("a.hps",)}.items():
            (self.f.ref / name).mkdir(exist_ok=True)
            for filename in filenames:
                old = f"old-{name}-{filename}".encode()
                (self.f.ref / name / filename).write_bytes(old)
                (self.f.dirs[name] / filename).write_bytes(f"new-{name}-{filename}".encode())
                self.f.meta["files"][name][filename] = self.f.digest(old)
        self.f.current = self.f.dirs["cloud"] / "a.hps"
        self.f.write_manifest(self.f.meta)
        self.prior = {path.relative_to(self.f.ref).as_posix(): path.read_bytes()
                      for path in self.f.ref.rglob("*") if path.is_file()}

    def current(self):
        out = {}
        for name, directory in self.f.dirs.items():
            out[name + "/"] = directory.exists()
            if directory.exists():
                for path in directory.rglob("*"):
                    out[name + "/" + path.relative_to(directory).as_posix()] = path.read_bytes() if path.is_file() else None
        out["sentinel"] = (self.f.root / "sentinel").read_bytes()
        out["answers"] = (self.f.root / "answers.json").read_bytes()
        return out

    def prior_unchanged(self):
        now = {path.relative_to(self.f.ref).as_posix(): path.read_bytes()
               for path in self.f.ref.rglob("*") if path.is_file()}
        self.assertEqual(now, self.prior, "A previously committed backup was changed")

    def call(self, action):
        try:
            return action()
        except Exception as error:
            self.fail(f"Save operation must return a bounded refusal, not {type(error).__name__}: {error}")

    def backup_refused(self, action, *, current_may_change=False):
        before = self.current()
        registered = [path.name for path in self.s.backups()]
        code = self.call(action)
        self.prior_unchanged()
        if not current_may_change:
            self.assertEqual(self.current(), before)
        self.assertNotEqual(code, 0)
        self.assertEqual([path.name for path in self.s.backups()], registered)

    def restore_refused(self, action):
        before = self.current()
        error = None
        try:
            code = action()
        except Exception as caught:
            error = caught
        self.assertEqual(self.current(), before, "Failed restore changed a declared current root or sentinel")
        self.prior_unchanged()
        if error is not None:
            self.fail(f"Restore must return a refusal, not {type(error).__name__}: {error}")
        self.assertNotEqual(code, 0)

    @contextlib.contextmanager
    def copy_hook(self, hook):
        # Windows CopyFile2 can bypass shutil.copyfile. Inject after the actual
        # copy2 and route only copytree's default copy transport through it.
        original_copy = self.s.shutil.copy2
        original_tree = self.s.shutil.copytree

        def copied(source, destination, *args, **kwargs):
            value = original_copy(source, destination, *args, **kwargs)
            hook(source, destination)
            return value

        def tree(source, destination, symlinks=False, ignore=None, copy_function=None,
                 ignore_dangling_symlinks=False, dirs_exist_ok=False):
            return original_tree(source, destination, symlinks=symlinks, ignore=ignore,
                                 copy_function=copied if copy_function is None else copy_function,
                                 ignore_dangling_symlinks=ignore_dangling_symlinks,
                                 dirs_exist_ok=dirs_exist_ok)

        with patch.object(self.s.shutil, "copy2", copied), patch.object(self.s.shutil, "copytree", tree):
            yield

    def test_healthy_backup_restore_control(self):
        self.assertEqual(self.call(self.s.backup), 0)
        self.assertEqual(self.call(lambda: self.s.restore(self.f.ref.name)), 0)
        for name, entries in self.f.meta["files"].items():
            for relative in entries:
                self.assertEqual((self.f.dirs[name] / relative).read_bytes(), (self.f.ref / name / relative).read_bytes())
        self.prior_unchanged()

    def test_same_second_changed_backups_have_distinct_ordered_names(self):
        with patch.object(self.s.time, "strftime", return_value="2001-01-01T00-00-00"):
            self.assertEqual(self.call(self.s.backup), 0)
            self.f.current.write_bytes(b"played again in the same second")
            self.assertEqual(self.call(self.s.backup), 0)
        refs = self.s.backups()
        self.assertEqual(len(refs), 3)
        self.assertEqual(len({path.name for path in refs}), 3)
        self.assertEqual([path.name for path in refs], sorted(path.name for path in refs))
        for ref in refs:
            self.assertEqual(self.s.intact(ref), [])
        self.prior_unchanged()

    def test_unchanged_intact_backup_deduplicates_without_new_commit(self):
        self.assertEqual(self.call(self.s.backup), 0)
        refs = [path.name for path in self.s.backups()]
        self.assertEqual(self.call(self.s.backup), 0)
        self.assertEqual([path.name for path in self.s.backups()], refs)
        for ref in self.s.backups():
            self.assertEqual(self.s.intact(ref), [])

    def test_backup_cap_refusal_does_not_modify_current_or_prior_backup(self):
        self.s.CAP_MB = 0
        before = self.current()
        refs = [path.name for path in self.s.backups()]
        self.assertEqual(self.call(self.s.backup), self.s.EXIT_CAP)
        self.assertEqual(self.current(), before)
        self.assertEqual([path.name for path in self.s.backups()], refs)
        self.prior_unchanged()

    def test_manifest_overhead_cannot_push_published_backup_past_cap(self):
        have = self.s.dir_bytes(self.f.backups)
        need = sum(self.s.dir_bytes(path) for path in self.f.dirs.values())
        self.s.CAP_MB = (have + need + 1) / (1024 * 1024)
        before = self.current()
        refs = [path.name for path in self.s.backups()]
        self.assertEqual(self.call(self.s.backup), self.s.EXIT_CAP)
        self.assertEqual(self.current(), before)
        self.assertEqual([path.name for path in self.s.backups()], refs)
        self.prior_unchanged()

    def test_corrupt_latest_manifest_cannot_deduplicate_without_copy_integrity(self):
        for name, entries in self.f.meta["files"].items():
            for relative in entries:
                (self.f.dirs[name] / relative).write_bytes((self.f.ref / name / relative).read_bytes())
        (self.f.ref / "cloud/a.hps").write_bytes(b"damaged preserved copy")
        self.prior = {path.relative_to(self.f.ref).as_posix(): path.read_bytes()
                      for path in self.f.ref.rglob("*") if path.is_file()}
        self.backup_refused(self.s.backup)

    def test_copyfile_failure_preserves_prior_commit_and_no_partial_commit(self):
        reached = []

        def fail(source, destination, *args, **kwargs):
            if not reached and Path(destination).is_relative_to(self.f.backups):
                reached.append(True)
                raise OSError("injected backup copy failure")
            return None

        with self.copy_hook(fail):
            self.backup_refused(self.s.backup)
        self.assertTrue(reached)

    def test_manifest_write_failure_preserves_prior_commit(self):
        reached = []
        original = Path.write_text

        def fail(path, data, *args, **kwargs):
            if path.name == "manifest.json" and path.parent != self.f.ref:
                reached.append(True)
                original(path, "{", *args, **kwargs)
                raise OSError("injected manifest write failure")
            return original(path, data, *args, **kwargs)

        with patch.object(Path, "write_text", fail):
            self.backup_refused(self.s.backup)
        self.assertTrue(reached)

    def test_copied_byte_corruption_is_not_committed(self):
        reached = []

        def corrupt(source, destination, *args, **kwargs):
            if not reached and Path(destination).is_relative_to(self.f.backups):
                reached.append(True)
                Path(destination).write_bytes(b"corrupted staged bytes")
            return None

        with self.copy_hook(corrupt):
            self.backup_refused(self.s.backup)
        self.assertTrue(reached)

    def test_source_mutation_after_copy_refuses_publication(self):
        reached = []

        def mutate(source, destination, *args, **kwargs):
            if not reached and Path(source) == self.f.current:
                reached.append(True)
                self.f.current.write_bytes(b"source changed during copy")
            return None

        with self.copy_hook(mutate):
            self.backup_refused(self.s.backup, current_may_change=True)
        self.assertTrue(reached)

    def test_written_staged_manifest_is_not_discoverable_as_a_commit(self):
        seen = []
        original = Path.write_text
        prior = [path.name for path in self.s.backups()]

        def inspect(path, data, *args, **kwargs):
            value = original(path, data, *args, **kwargs)
            if path.name == "manifest.json" and path.parent != self.f.ref:
                seen.append([ref.name for ref in self.s.backups()])
            return value

        with patch.object(Path, "write_text", inspect):
            self.assertEqual(self.call(self.s.backup), 0)
        self.assertTrue(seen)
        self.assertTrue(all(names == prior for names in seen), "Unpublished staging was listed as a committed backup")

    def test_source_mutation_during_manifest_write_refuses_publication(self):
        reached = []
        original = Path.write_text

        def mutate(path, data, *args, **kwargs):
            value = original(path, data, *args, **kwargs)
            if path.name == "manifest.json" and path.parent != self.f.ref:
                reached.append(True)
                self.f.current.write_bytes(b"source changed after initial copy checks")
            return value

        with patch.object(Path, "write_text", mutate):
            self.backup_refused(self.s.backup, current_may_change=True)
        self.assertTrue(reached)

    def test_pre_restore_backup_failure_leaves_all_current_roots_untouched(self):
        reached = []

        def fail(source, destination, *args, **kwargs):
            if Path(destination).is_relative_to(self.f.backups):
                reached.append(True)
                raise OSError("injected pre-restore preservation failure")
            return None

        with self.copy_hook(fail):
            self.restore_refused(lambda: self.s.restore(self.f.ref.name))
        self.assertTrue(reached)

    def test_restore_copy_failure_preserves_every_current_root(self):
        reached = []

        def fail(source, destination, *args, **kwargs):
            if Path(destination).is_relative_to(self.f.root / "current") and Path(destination).name == "b.hps":
                reached.append(True)
                raise OSError("injected replacement copy failure")
            return None

        with self.copy_hook(fail):
            self.restore_refused(lambda: self.s.restore(self.f.ref.name))
        self.assertTrue(reached)

    def test_corrupt_prepared_restore_bytes_refuse_before_any_current_rename(self):
        reached = []

        def corrupt(source, destination, *args, **kwargs):
            if not reached and Path(source).is_relative_to(self.f.ref) and Path(destination).is_relative_to(self.f.root / "current"):
                reached.append(True)
                Path(destination).write_bytes(b"corrupted replacement")
            return None

        with self.copy_hook(corrupt):
            self.restore_refused(lambda: self.s.restore(self.f.ref.name))
        self.assertTrue(reached)

    def test_second_root_commit_failure_rolls_back_all_current_roots(self):
        reached = []
        original = os.replace

        def fail(source, destination, *args, **kwargs):
            if not reached and Path(destination) == self.f.dirs["local"]:
                reached.append(True)
                raise OSError("injected second-root commit failure")
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "replace", fail):
            self.restore_refused(lambda: self.s.restore(self.f.ref.name))
        self.assertTrue(reached, "Commit failure hook must be reached")

    def test_failed_commit_preserves_absent_root_and_previously_missing_parents(self):
        old = self.f.dirs["game_backups"]
        for path in old.iterdir():
            path.unlink()
        old.rmdir()
        missing = self.f.root / "absent" / "nested" / "saves"
        self.f.dirs["game_backups"] = missing
        self.f.meta["sources"]["game_backups"] = str(missing)
        self.f.write_manifest(self.f.meta)
        self.prior = {path.relative_to(self.f.ref).as_posix(): path.read_bytes()
                      for path in self.f.ref.rglob("*") if path.is_file()}
        reached = []
        original = os.replace

        def fail(source, destination, *args, **kwargs):
            if not reached and Path(destination) == self.f.dirs["local"]:
                reached.append(True)
                raise OSError("injected commit failure after all roots were prepared")
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "replace", fail):
            self.restore_refused(lambda: self.s.restore(self.f.ref.name))
        self.assertTrue(reached)
        self.assertFalse(missing.exists())
        self.assertFalse((self.f.root / "absent").exists(), "Failed restore left newly created parents")

    def test_failed_rollback_retains_verified_prebackup_and_recovery_material(self):
        self.f.stamp()
        self.assertEqual(self.s.confirmation_problems(), [])
        commit, rollback = [], []
        original = os.replace

        def fail(source, destination, *args, **kwargs):
            source, destination = Path(source), Path(destination)
            if not commit and destination == self.f.dirs["local"]:
                commit.append(True)
                raise OSError("injected commit failure")
            if commit and not rollback and destination == self.f.dirs["cloud"] and (source / "a.hps").is_file() \
                    and (source / "a.hps").read_bytes() == b"new-cloud-a.hps":
                rollback.append(True)
                raise OSError("injected rollback failure")
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "replace", fail):
            self.assertNotEqual(self.call(lambda: self.s.restore(self.f.ref.name)), 0)
        self.assertTrue(commit and rollback)
        journals = list(self.f.backups.glob(".restore-*.json"))
        self.assertTrue(journals)
        self.assertTrue(any(json.loads(path.read_text())["status"] == "recovery-required" for path in journals))
        self.assertTrue(any(self.f.root.joinpath("current").glob(".ro-*")))
        for ref in self.s.backups():
            self.assertEqual(self.s.intact(ref), [])
        self.prior_unchanged()
        before = self.current()
        self.assertNotEqual(self.call(self.s.backup), 0)
        self.assertEqual(self.current(), before)
        self.assertTrue(self.s.confirmation_problems(), "Recovery must close the deployment confirmation gate too")

    def test_interruption_retains_journal_and_refuses_new_backup(self):
        self.f.stamp()
        self.assertEqual(self.s.confirmation_problems(), [])
        reached = []
        original = os.replace

        def stop(source, destination, *args, **kwargs):
            if not reached and Path(destination) == self.f.dirs["local"]:
                reached.append(True)
                raise Interrupted("simulated process interruption")
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "replace", stop), self.assertRaises(Interrupted):
            self.s.restore(self.f.ref.name)
        self.assertTrue(reached)
        self.assertTrue(list(self.f.backups.glob(".restore-*.json")))
        for ref in self.s.backups():
            self.assertEqual(self.s.intact(ref), [])
        self.prior_unchanged()
        before = self.current()
        self.assertNotEqual(self.call(self.s.backup), 0)
        self.assertEqual(self.current(), before)
        self.assertTrue(self.s.confirmation_problems())

    def test_unresolved_recovery_closes_backup_restore_and_confirmation_gates(self):
        self.f.stamp()
        self.assertEqual(self.s.confirmation_problems(), [])
        (self.f.backups / ".restore-fake.json").write_text('{"status": "recovery-required"}', encoding="utf-8")
        before = self.current()
        self.assertTrue(self.s.confirmation_problems())
        self.assertNotEqual(self.call(self.s.backup), 0)
        self.assertNotEqual(self.call(lambda: self.s.restore(self.f.ref.name)), 0)
        self.assertEqual(self.current(), before)
        self.prior_unchanged()

    def test_committed_journal_cleanup_denial_reports_committed_success(self):
        self.f.stamp()
        reached = []
        original = Path.unlink

        def fail(path, *args, **kwargs):
            if path.name.startswith(".restore-") and path.suffix == ".json":
                reached.append(True)
                raise PermissionError("injected committed-journal cleanup denial")
            return original(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail):
            self.assertEqual(self.call(lambda: self.s.restore(self.f.ref.name)), 0)
        self.assertTrue(reached)
        self.assertEqual(self.s.confirmation_problems(), [])
        journals = list(self.f.backups.glob(".restore-*.json"))
        self.assertTrue(journals)
        self.assertTrue(all(json.loads(path.read_text())["status"] == "committed" for path in journals))
        for name, entries in self.f.meta["files"].items():
            for relative in entries:
                self.assertEqual((self.f.dirs[name] / relative).read_bytes(), (self.f.ref / name / relative).read_bytes())
        self.prior_unchanged()

    def test_committed_old_directory_cleanup_denial_keeps_journal_and_success(self):
        reached = []
        original = self.s.shutil.rmtree

        def fail(path, *args, **kwargs):
            if Path(path).name.startswith(".ro-"):
                reached.append(True)
                raise PermissionError("injected committed-old-directory cleanup denial")
            return original(path, *args, **kwargs)

        with patch.object(self.s.shutil, "rmtree", fail):
            self.assertEqual(self.call(lambda: self.s.restore(self.f.ref.name)), 0)
        self.assertTrue(reached)
        journals = list(self.f.backups.glob(".restore-*.json"))
        self.assertTrue(journals)
        self.assertTrue(all(json.loads(path.read_text())["status"] == "committed" for path in journals))
        self.assertTrue(any(json.loads(path.read_text()).get("cleanup_errors") for path in journals))
        for name, entries in self.f.meta["files"].items():
            for relative in entries:
                self.assertEqual((self.f.dirs[name] / relative).read_bytes(), (self.f.ref / name / relative).read_bytes())
        self.prior_unchanged()


if __name__ == "__main__":
    unittest.main(verbosity=2)
