"""Runtime lifecycle interleavings against fake locks, processes and save trees."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gamelab import launcher, lock
from tools import run as play_run


class NoSampler:
    t0 = 0.0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def report(self):
        return {"switches": [], "unexplained": [], "window_scans": 1,
                "game_windows_on_input_desktop": []}


class RuntimeOwnership(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-ownership-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.held = self.root / "runtime.lock"
        self.teardown = self.root / "teardown.json"
        self.teardown.write_text('{"clean": true, "run": "previous"}')
        self.foreign = '{"pid": 987654, "token": "other-owner", "scenario": "other"}'
        self.original_kill = lock.kill
        self.patches = [patch.object(lock, "LOCK", self.held),
                        patch.object(lock, "TEARDOWN", self.teardown),
                        patch.object(lock.env, "GAME", self.game),
                        patch.object(lock, "player_processes", return_value=[]),
                        patch.object(lock, "lab_processes", return_value=[]),
                        patch.object(lock, "pid_alive", return_value=False),
                        patch.object(lock, "kill"),
                        patch.object(lock, "process_image", return_value="C:/fake/python.exe")]
        self.mocks = [p.start() for p in self.patches]
        for p in self.patches:
            self.addCleanup(p.stop)

    def acquire(self):
        lock.acquire("test", "lab")

    def test_release_refuses_foreign_owner_before_scans_or_writes(self):
        self.acquire()
        self.held.write_text(self.foreign)
        before = self.teardown.read_bytes()
        self.mocks[4].reset_mock()
        with self.assertRaises(lock.Refused):
            lock.release("test", [])
        self.assertEqual(self.held.read_text(), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), before)
        self.mocks[4].assert_not_called()
        self.mocks[6].assert_not_called()

    def test_acquire_second_scan_failure_preserves_scratch_and_drops_own_lock(self):
        saves = self.game / "saves"
        saves.mkdir()
        sentinel = saves / "sentinel.hps"
        sentinel.write_bytes(b"unchanged")
        self.mocks[4].side_effect = lock.Refused("unknown second scan")
        with self.assertRaises(lock.Refused):
            self.acquire()
        self.assertFalse(self.held.exists())
        self.assertEqual(sentinel.read_bytes(), b"unchanged")

    def test_release_unknown_scan_never_writes_a_clean_teardown(self):
        self.acquire()
        before = self.teardown.read_bytes()
        self.mocks[4].side_effect = lock.Refused("unknown visibility")
        with self.assertRaises(lock.Refused):
            lock.release("test", [])
        self.assertTrue(self.held.exists())
        self.assertEqual(self.teardown.read_bytes(), before)
        self.mocks[6].assert_not_called()

    def test_snapshot_refusal_releases_only_unused_own_lock(self):
        self.acquire()
        config = self.root / "config.cfg"
        config.write_text("private test config")
        before = self.teardown.read_bytes()
        with patch.object(launcher, "REPO", self.root), \
                patch.object(launcher, "RESULTS", self.root / "results"), \
                patch.object(launcher.gamepaths, "real_config", return_value=config), \
                patch.object(launcher.env, "install_res_snapshot", side_effect=PermissionError("fake denied")), \
                patch.object(launcher.hidden_desktop, "run") as run:
            self.assertEqual(launcher._run(self.root / "s.json", "s", {}, "lab", []), 2)
        self.assertFalse(self.held.exists())
        self.assertEqual(self.teardown.read_bytes(), before)
        run.assert_not_called()

    def test_reset_excludes_new_acquisition_during_cleanup(self):
        entered = []

        def scan():
            with patch.object(lock, "lab_processes", return_value=[]):
                try:
                    lock.acquire("new-owner", "lab")
                except lock.Refused:
                    entered.append(False)
                else:
                    entered.append(True)
            return []

        self.mocks[4].side_effect = scan
        self.assertEqual(lock.reset(), 0)
        self.assertEqual(entered, [False])
        self.assertFalse(self.held.exists())

    def test_reset_preserves_live_owner_and_scratch(self):
        self.held.write_text(self.foreign)
        self.mocks[5].return_value = True
        before = self.teardown.read_bytes()
        self.assertEqual(lock.reset(), 4)
        self.assertEqual(self.held.read_text(), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), before)
        self.mocks[4].assert_not_called()
        self.mocks[6].assert_not_called()

    def test_exception_cleanup_preserves_replacement_owner(self):
        scenario = self.root / "s.json"
        scenario.write_text('{"steps": []}')

        def fail(*args):
            self.held.write_text(self.foreign)
            raise OSError("fake late failure")

        with patch.object(launcher, "hoh1_missing", return_value=[]), \
                patch.object(launcher, "preflight", return_value=([], [])), \
                patch.object(launcher, "_run", side_effect=fail):
            with self.assertRaisesRegex(OSError, "fake late failure"):
                launcher.run(str(scenario), "lab")
        self.assertTrue(self.held.exists())
        self.assertEqual(self.held.read_text(), self.foreign)
        self.mocks[6].assert_not_called()

    def test_result_output_is_written_while_ownership_is_held(self):
        config = self.root / "config.cfg"
        config.write_text("private test config")
        scenario = self.root / "s.json"
        scenario.write_text('{"steps": [], "timeout": 1}')
        held_during_output = []
        original_write = Path.write_text

        def fake_run(command, **kwargs):
            results = Path(command[4])
            (results / "inner.json").write_text(json.dumps({"assertions": [], "partial": False}))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        def fail_output(path, text, *args, **kwargs):
            if path.name == "run.json":
                held_during_output.append(self.held.exists())
                if not self.held.exists():
                    original_write(self.held, self.foreign)
                raise OSError("fake result-write failure")
            return original_write(path, text, *args, **kwargs)

        with patch.object(launcher, "REPO", self.root), \
                patch.object(launcher, "RESULTS", self.root / "results"), \
                patch.object(launcher, "hoh1_missing", return_value=[]), \
                patch.object(launcher, "preflight", return_value=([], [])), \
                patch.object(launcher.gamepaths, "real_config", return_value=config), \
                patch.object(launcher.env, "install_res_snapshot", return_value={}), \
                patch.object(launcher.saves, "snapshot", return_value={}), \
                patch.object(launcher.saves, "diff", return_value=[]), \
                patch.object(launcher.pin_build, "pinned", return_value={}), \
                patch.object(launcher.pin_build, "live", return_value={}), \
                patch.object(launcher, "mods_version", return_value={}), \
                patch.object(launcher.winproc, "ForegroundSampler", return_value=NoSampler()), \
                patch.object(launcher.hidden_desktop, "run", side_effect=fake_run), \
                patch.dict(sys.modules, {"run_summary": Mock(write=Mock(return_value={}))}), \
                patch.object(Path, "write_text", fail_output):
            with self.assertRaisesRegex(OSError, "fake result-write failure"):
                launcher.run(str(scenario), "lab")
        self.assertEqual(held_during_output, [True])
        self.assertFalse(self.held.exists())
        self.assertFalse(json.loads(self.teardown.read_text())["clean"])

    def test_play_context_refuses_to_unlink_replacement_owner(self):
        with self.assertRaises(RuntimeError):
            with play_run.runtime_lock(False):
                self.held.write_text(self.foreign)
        self.assertEqual(self.held.read_text(), self.foreign)

    def test_kill_rechecks_exact_identity_before_taskkill(self):
        self.acquire()
        # The public cleanup primitive is under test; bypass only setUp's fake
        # kill, while every underlying OS call remains mocked.
        with patch.object(lock, "process_image", return_value=str(self.root / "outside/HWR2.exe")), \
                patch.object(lock.subprocess, "run", return_value=Mock(returncode=0)) as taskkill:
            with self.assertRaises(lock.Refused):
                self.original_kill([10])
        taskkill.assert_not_called()

    def test_reset_refuses_uninspectable_owner_still_present_in_pid_scan(self):
        self.held.write_text(self.foreign)
        before = self.teardown.read_bytes()
        scan = Mock(returncode=0, stdout='"python.exe","987654"')
        with patch.object(lock.subprocess, "run", return_value=scan):
            self.assertEqual(lock.reset(), 4)
        self.assertEqual(self.held.read_text(), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), before)
        self.mocks[4].assert_not_called()
        self.mocks[6].assert_not_called()

    def test_reset_refuses_failed_owner_visibility_scan(self):
        self.held.write_text(self.foreign)
        before = self.teardown.read_bytes()
        with patch.object(lock.subprocess, "run", return_value=Mock(returncode=1, stdout="", stderr="denied")):
            self.assertEqual(lock.reset(), 4)
        self.assertEqual(self.held.read_text(), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), before)
        self.mocks[4].assert_not_called()

    def test_reset_can_clear_a_proven_absent_owner(self):
        self.held.write_text(self.foreign)
        with patch.object(lock.subprocess, "run", return_value=Mock(returncode=0, stdout="INFO: No matching tasks")):
            self.assertEqual(lock.reset(), 0)
        self.assertFalse(self.held.exists())
        self.assertTrue(json.loads(self.teardown.read_text())["clean"])


if __name__ == "__main__":
    unittest.main()
