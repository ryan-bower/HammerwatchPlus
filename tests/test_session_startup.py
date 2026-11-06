"""Startup isolation failure paths; fake process and Win32 APIs only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gamelab import session, winproc


class StartupIsolation(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-startup-test-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        game = root / "game"
        game.mkdir()
        results = root / "results"
        results.mkdir()
        self.proc = Mock(pid=12345, _handle=7)
        self.proc.poll.return_value = None
        self.proc.wait.return_value = 1
        self.patches = [
            patch.object(session.env, "GAME", game),
            patch.object(session.env, "write_profile"),
            patch.object(session.subprocess, "Popen", return_value=self.proc),
            patch.object(session.winproc, "inject", return_value=True),
            patch.object(session.winproc, "resume", return_value=True),
        ]
        self.mocks = [item.start() for item in self.patches]
        for item in self.patches:
            self.addCleanup(item.stop)
        self.game = session.Game(results, "lab")
        self.addCleanup(self.game.close)
        self.game.shim_log = Mock(return_value="injected; SwapBuffers hooked, SHGetKnownFolderPath hooked")

    def assert_cleaned(self):
        self.proc.kill.assert_called_once_with()
        self.proc.wait.assert_called_once()

    def test_failed_injection_never_resumes_and_cleans_suspended_child(self):
        self.mocks[3].return_value = False
        with self.assertRaises(session.GameError):
            self.game.start()
        self.mocks[4].assert_not_called()
        self.assert_cleaned()

    def test_missing_required_hook_never_resumes(self):
        self.game.shim_log.return_value = "injected; SwapBuffers hooked, SHGetKnownFolderPath ERR import not found"
        with self.assertRaises(session.GameError):
            self.game.start()
        self.mocks[4].assert_not_called()
        self.assert_cleaned()

    def test_missing_hook_log_never_resumes(self):
        self.game.shim_log.return_value = ""
        with self.assertRaises(session.GameError):
            self.game.start()
        self.mocks[4].assert_not_called()
        self.assert_cleaned()

    def test_failed_resume_cleans_child(self):
        self.mocks[4].return_value = False
        with self.assertRaises(session.GameError):
            self.game.start()
        self.assert_cleaned()

    def test_injection_exception_cleans_child_without_resume(self):
        self.mocks[3].side_effect = OSError("injected failure")
        with self.assertRaisesRegex(OSError, "injected failure"):
            self.game.start()
        self.mocks[4].assert_not_called()
        self.assert_cleaned()

    def test_cancelled_injection_cleans_child_without_resume(self):
        self.mocks[3].side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.game.start()
        self.mocks[4].assert_not_called()
        self.assert_cleaned()

    def test_successful_hooked_start_resumes_once(self):
        self.game.start()
        self.mocks[4].assert_called_once_with(self.proc)
        self.proc.kill.assert_not_called()
        self.proc.wait.assert_not_called()

    def redirect_with_units(self, units, nonbmp=False):
        leaf = "q" + ("\U0001f642" if nonbmp else "")
        initial = str((Path("C:/") / leaf / "appdata").resolve())
        leaf += "x" * (units - len(initial.encode("utf-16-le")) // 2)
        self.game.game_dir = Path("C:/") / leaf
        value = str((self.game.game_dir / "appdata").resolve())
        self.assertEqual(len(value.encode("utf-16-le")) // 2, units)
        return value

    def test_redirect_at_buffer_limit_is_absolute_and_preserved(self):
        value = self.redirect_with_units(259)
        with patch.object(Path, "mkdir"), patch.object(Path, "unlink"):
            self.game.start()
        actual = self.mocks[2].call_args.kwargs["env"]["GAMELAB_LOCALAPPDATA"]
        self.assertEqual(actual, value)
        self.assertTrue(Path(actual).is_absolute())

    def test_redirect_overflow_refuses_before_popen(self):
        self.redirect_with_units(260)
        with patch.object(Path, "mkdir"), patch.object(Path, "unlink"):
            with self.assertRaises(session.GameError):
                self.game.start()
        self.mocks[2].assert_not_called()
        self.mocks[4].assert_not_called()

    def test_redirect_counts_utf16_units_before_popen(self):
        value = self.redirect_with_units(260, nonbmp=True)
        self.assertLess(len(value), 260)
        with patch.object(Path, "mkdir"), patch.object(Path, "unlink"):
            with self.assertRaises(session.GameError):
                self.game.start()
        self.mocks[2].assert_not_called()
        self.mocks[4].assert_not_called()


class InjectionCompletion(unittest.TestCase):
    def fake(self, wait=0, exit_code=123, query_ok=True):
        kernel = Mock()
        kernel.VirtualAllocEx.return_value = 4096
        kernel.WriteProcessMemory.return_value = True
        kernel.GetModuleHandleW.return_value = 10
        kernel.GetProcAddress.return_value = 20
        kernel.CreateRemoteThread.return_value = 30
        kernel.WaitForSingleObject.return_value = wait

        def query(thread, result):
            result._obj.value = exit_code
            return query_ok

        kernel.GetExitCodeThread.side_effect = query
        return kernel

    def test_timeout_is_not_completed_injection(self):
        kernel = self.fake(wait=258, exit_code=259)
        with patch.object(winproc, "k32", kernel):
            self.assertFalse(winproc.inject(Mock(_handle=7), "fake.dll"))
        kernel.CloseHandle.assert_called_once_with(30)

    def test_failed_wait_is_not_completed_injection(self):
        kernel = self.fake(wait=0xFFFFFFFF, exit_code=123)
        with patch.object(winproc, "k32", kernel):
            self.assertFalse(winproc.inject(Mock(_handle=7), "fake.dll"))
        kernel.CloseHandle.assert_called_once_with(30)

    def test_failed_exit_query_is_not_success(self):
        kernel = self.fake(exit_code=123, query_ok=False)
        with patch.object(winproc, "k32", kernel):
            self.assertFalse(winproc.inject(Mock(_handle=7), "fake.dll"))
        kernel.CloseHandle.assert_called_once_with(30)

    def test_still_active_is_not_a_module(self):
        kernel = self.fake(exit_code=259)
        with patch.object(winproc, "k32", kernel):
            self.assertFalse(winproc.inject(Mock(_handle=7), "fake.dll"))
        kernel.CloseHandle.assert_called_once_with(30)

    def test_zero_module_is_a_failure(self):
        kernel = self.fake(exit_code=0)
        with patch.object(winproc, "k32", kernel):
            self.assertFalse(winproc.inject(Mock(_handle=7), "fake.dll"))
        kernel.CloseHandle.assert_called_once_with(30)

    def test_completed_nonzero_module_is_success(self):
        kernel = self.fake()
        with patch.object(winproc, "k32", kernel):
            self.assertTrue(winproc.inject(Mock(_handle=7), "fake.dll"))
        kernel.CloseHandle.assert_called_once_with(30)


if __name__ == "__main__":
    unittest.main()
