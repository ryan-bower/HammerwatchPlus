"""Win32 wrapper regressions using fake DLLs: no real input or processes."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

import gamelab


class WineQueryTests(unittest.TestCase):
    def session(self, proton):
        winproc = types.ModuleType("gamelab.winproc")
        spec = importlib.util.spec_from_file_location("_session_test", Path(gamelab.__file__).parent / "session.py")
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"gamelab.winproc": winproc}), \
                mock.patch.object(gamelab, "winproc", winproc, create=True), \
                mock.patch.dict(os.environ, {"HWP_PROTON": "1" if proton else "0"}):
            spec.loader.exec_module(module)
        return module

    def test_job_query_uses_required_access_and_pointer_sized_handle(self):
        session = self.session(True)
        dll = mock.Mock()
        dll.OpenProcess.return_value = 0x100000001
        def query(process, job, result):
            self.assertEqual(process, 0x100000001)
            self.assertIsNone(job)
            result._obj.value = True
            return True
        dll.IsProcessInJob.side_effect = query
        with mock.patch.object(session.ctypes, "WinDLL", return_value=dll, create=True):
            self.assertTrue(session.in_job(123))
        dll.OpenProcess.assert_called_once_with(0x0400, False, 123)
        dll.CloseHandle.assert_called_once_with(0x100000001)

    def test_failed_job_query_is_still_rejected(self):
        session = self.session(True)
        dll = mock.Mock()
        dll.OpenProcess.return_value = 7
        dll.IsProcessInJob.return_value = False
        with mock.patch.object(session.ctypes, "WinDLL", return_value=dll, create=True):
            self.assertFalse(session.in_job(123))


if __name__ == "__main__":
    unittest.main()
