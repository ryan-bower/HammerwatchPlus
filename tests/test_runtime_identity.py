"""Exact runtime identity and desktop containment; no process/input APIs execute."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gamelab import lock, winproc


class RuntimeIdentity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-identity-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "game"
        self.patcher = patch.object(lock.env, "GAME", self.game)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_cleanup_only_matches_exact_lab_executable(self):
        output = '\n'.join('"HWR2.exe","%d"' % pid for pid in (10, 20, 30))
        images = {10: str(self.game / "HWR2.exe"),
                  20: str(self.root / "game-backup/HWR2.exe"),
                  30: str(self.root / "real/HWR2.exe")}
        with patch.object(lock.subprocess, "run", return_value=Mock(returncode=0, stdout=output)), \
                patch.object(lock, "process_image", side_effect=images.get):
            self.assertEqual(lock.lab_processes(), [10])
            self.assertEqual(lock.player_processes(), [20, 30])

    def test_failed_scan_refuses_cleanup(self):
        with patch.object(lock.subprocess, "run", return_value=Mock(returncode=1, stdout="", stderr="denied")):
            with self.assertRaises(lock.Refused):
                lock.lab_processes()

    def test_unreadable_identity_refuses_cleanup(self):
        with patch.object(lock.subprocess, "run", return_value=Mock(returncode=0, stdout='"HWR2.exe","10"')), \
                patch.object(lock, "process_image", return_value=""):
            with self.assertRaises(lock.Refused):
                lock.lab_processes()

    def test_desktop_observation_uses_directory_boundary(self):
        images = {10: str(self.game / "HWR2.exe"),
                  20: str(self.root / "game-backup/HWR2.exe"),
                  30: str(self.game / "helpers/dialog.exe")}

        def enumerate_windows(callback, parameter):
            for pid in images:
                callback(pid, parameter)
            return True

        def window_pid(hwnd, pointer):
            pointer._obj.value = hwnd
            return 1

        with patch.object(winproc.u32, "GetForegroundWindow", return_value=0), \
                patch.object(winproc.u32, "EnumWindows", side_effect=enumerate_windows), \
                patch.object(winproc.u32, "GetWindowThreadProcessId", side_effect=window_pid), \
                patch.object(winproc, "process_image", side_effect=images.get):
            sampler = winproc.ForegroundSampler(game_dir=str(self.game))
            sampler._scan_windows()
        self.assertEqual([row["pid"] for row in sampler.leaks], [10, 30])


if __name__ == "__main__":
    unittest.main()
