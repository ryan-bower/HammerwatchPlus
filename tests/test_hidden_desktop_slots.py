"""Slot desktop/job contracts using fake Win32 calls; never launch a child."""
import ctypes
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import hidden_desktop as hd


class EnvironmentContracts(unittest.TestCase):
    def test_named_job_absence_requires_exact_not_found(self):
        kernel = Mock()
        kernel.OpenJobObjectW.return_value = 0
        with patch.object(hd, "_k32", kernel), patch.object(ctypes, "get_last_error", return_value=2):
            self.assertTrue(hd.job_empty("owned-job"))
        with patch.object(hd, "_k32", kernel), patch.object(ctypes, "get_last_error", return_value=5):
            with self.assertRaises(OSError):
                hd.job_empty("owned-job")
        kernel.CloseHandle.assert_not_called()

    def test_named_job_nonempty_or_unknown_count_cannot_pass(self):
        kernel = Mock()
        kernel.OpenJobObjectW.return_value = 123
        with patch.object(hd, "_k32", kernel):
            for count, expected in ((0, True), (1, False)):
                with patch.object(hd, "_active_processes", return_value=count):
                    self.assertEqual(hd.job_empty("owned-job"), expected)
            with patch.object(hd, "_active_processes", return_value=-1):
                with self.assertRaises(OSError):
                    hd.job_empty("owned-job")
        self.assertEqual(kernel.CloseHandle.call_count, 3)

    def test_legacy_environment_is_inherited_without_a_new_block(self):
        self.assertIsNone(hd._environment(None, None))

    def test_named_job_environment_is_private_unicode_and_replaces_case_alias(self):
        original = {"Path": "fake-path", "gamelab_job_name": "foreign", "UNICODE": "\u03bb\U0001f680"}
        before = original.copy()
        block = hd._environment(original, "pool.slot.run-123")
        entries = block.raw.decode("utf-16le").rstrip("\0").split("\0")
        self.assertEqual(original, before)
        self.assertIn("GAMELAB_JOB_NAME=pool.slot.run-123", entries)
        self.assertIn("UNICODE=\u03bb\U0001f680", entries)
        self.assertFalse(any(v.startswith("gamelab_job_name=") for v in entries))

    def test_bad_names_and_environments_refuse_before_native_calls(self):
        for value in ("", "Global\\foreign", "WinSta0\\Default", "a/b", "\u03bb", "x" * 121, None):
            with self.subTest(name=value), self.assertRaises(ValueError):
                hd._object_name(value, "job")
        for value in ({"A": "x\0y"}, {"A=B": "x"}, {1: "x"}, {"A": 1}, {"PATH": "a", "path": "b"}):
            with self.subTest(env=value), self.assertRaises(ValueError):
                hd._environment(value, "owned")

    def test_visible_legacy_path_preserves_subprocess_contract(self):
        expected = subprocess.CompletedProcess(["fake"], 0, "out", "")
        with patch.object(hd.subprocess, "run", return_value=expected) as child:
            self.assertIs(hd.run(["fake"], cwd="owned", timeout=2, visible=True), expected)
        child.assert_called_once_with(["fake"], cwd="owned", capture_output=True, text=True, timeout=2)

    def test_visible_slot_controls_never_fall_back_to_unisolated_execution(self):
        with patch.object(hd.subprocess, "run") as child:
            for controls in ({"desktop_name": "slot-1"}, {"job_name": "job-1"},
                             {"affinity_mask": 3}, {"allow_breakaway": False}):
                with self.subTest(controls=controls), self.assertRaises(ValueError):
                    hd.run(["fake"], visible=True, **controls)
        child.assert_not_called()


@unittest.skipUnless(hd.WINDOWS, "Win32 structures exercised with mocked APIs on Windows")
class FakeWindowsSlots(unittest.TestCase):
    def setUp(self):
        results = Path(__file__).resolve().parents[1] / "gamelab" / "results"
        results.mkdir(parents=True, exist_ok=True)  # ignored, so absent in a fresh clone
        self.scratch = tempfile.TemporaryDirectory(prefix="hd-slots-", dir=results)
        self.addCleanup(self.scratch.cleanup)
        original_mkdtemp = tempfile.mkdtemp
        self.kernel, self.user = Mock(), Mock()
        for target, value in (("_k32", self.kernel), ("_u32", self.user)):
            p = patch.object(hd, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(hd.tempfile, "mkdtemp", side_effect=lambda **kw: original_mkdtemp(dir=self.scratch.name, **kw))
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(hd.os, "cpu_count", return_value=16)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(hd, "_win_error", side_effect=lambda call: OSError(call + " failed (fake)"))
        p.start()
        self.addCleanup(p.stop)
        self.calls = []
        self.environments = []
        self.desktops = []
        self.flags = []
        self.limits = None
        self.kernel.GetCurrentProcess.return_value = 700
        self.kernel.GetProcessAffinityMask.side_effect = self.affinity
        self.kernel.CreateJobObjectW.return_value = 101
        self.kernel.SetInformationJobObject.side_effect = self.set_limits
        self.kernel.QueryInformationJobObject.side_effect = self.query
        self.kernel.CreateFileW.side_effect = [301, 302, 303, 304]
        self.kernel.CreateProcessW.side_effect = self.create
        self.kernel.AssignProcessToJobObject.side_effect = lambda *args: self.record("assign")
        self.kernel.IsProcessInJob.side_effect = self.membership
        self.kernel.ResumeThread.side_effect = lambda *args: self.record("resume")
        self.kernel.WaitForSingleObject.return_value = 0
        self.kernel.GetExitCodeProcess.side_effect = self.exit_code
        self.user.CreateDesktopW.side_effect = self.desktop
        self.kernel.OpenJobObjectW.return_value = 501
        self.kernel.OpenProcess.return_value = 601

    def record(self, name):
        self.calls.append(name)
        return 1

    def affinity(self, process, mask, system):
        mask._obj.value = 0xFFFF
        system._obj.value = 0xFFFF
        return 1

    def set_limits(self, job, kind, info, size):
        self.limits = hd._JobExtendedLimits.from_buffer_copy(ctypes.string_at(info, size))
        return 1

    def query(self, job, kind, info, size, returned):
        if kind == hd.JobObjectBasicAccountingInformation:
            info._obj.ActiveProcesses = 0
            info._obj.TotalProcesses = 2
        else:
            ctypes.memmove(info, ctypes.byref(self.limits), size)
            info._obj.PeakJobMemoryUsed = 123456
            info._obj.PeakProcessMemoryUsed = 12345
        return 1

    def desktop(self, name, *args):
        self.desktops.append(name)
        return 201

    def create(self, app, line, psa, tsa, inherit, flags, env, cwd, startup, process):
        self.record("create")
        self.environments.append(None if env is None else env.raw.decode("utf-16le").rstrip("\0").split("\0"))
        self.desktops.append(startup._obj.lpDesktop)
        self.flags.append(flags)
        process._obj.hProcess = 401
        process._obj.hThread = 402
        process._obj.dwProcessId = 403
        return 1

    def membership(self, process, job, belongs):
        self.record("membership")
        belongs._obj.value = True
        return 1

    def exit_code(self, process, code):
        code._obj.value = 0
        return 1

    def run_slot(self, **kwargs):
        controls = {"desktop_name": "pool-slot1-run-123", "job_name": "job-slot1-run-123",
                    "affinity_mask": 0x30, "memory_mb": 768, "allow_breakaway": False,
                    "env": {"PATH": "fake"}}
        controls.update(kwargs)
        return hd.run(["never-executed.exe", "fake-argument"], **controls)

    def test_slot_limits_environment_assignment_order_and_scalar_telemetry(self):
        before = dict(os.environ)
        done = self.run_slot()
        self.assertEqual(done.returncode, 0)
        self.assertEqual(dict(os.environ), before)
        self.assertEqual(self.desktops, ["pool-slot1-run-123", "WinSta0\\pool-slot1-run-123"])
        self.kernel.CreateJobObjectW.assert_called_once_with(None, "job-slot1-run-123")
        self.assertEqual(self.calls[:4], ["create", "assign", "membership", "resume"])
        self.assertEqual(self.environments, [["GAMELAB_JOB_NAME=job-slot1-run-123", "PATH=fake"]])
        self.assertTrue(self.flags[0] & hd.CREATE_SUSPENDED)
        self.assertTrue(self.flags[0] & hd.CREATE_UNICODE_ENVIRONMENT)
        limits = self.limits.BasicLimitInformation
        self.assertEqual(limits.Affinity, 0x30)
        self.assertFalse(limits.LimitFlags & hd.JOB_OBJECT_LIMIT_BREAKAWAY_OK)
        self.assertTrue(limits.LimitFlags & hd.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        self.assertEqual(self.limits.JobMemoryLimit, 768 * 1024 * 1024)
        self.assertEqual(done.isolation["peak_job_memory_bytes"], 123456)
        self.assertEqual(done.isolation["peak_process_memory_bytes"], 12345)
        self.assertEqual(done.isolation["total_processes"], 2)
        self.assertTrue(done.isolation["tree_clean"])
        self.user.CloseDesktop.assert_called_once_with(201)
        self.assertFalse(any(call.args == (201,) for call in self.kernel.CloseHandle.call_args_list))
        self.assertEqual({call[0] for call in self.user.mock_calls}, {"CreateDesktopW", "CloseDesktop"})

    def test_legacy_defaults_retain_unnamed_job_shared_desktop_and_breakaway(self):
        done = hd.run(["never-executed.exe"])
        self.assertEqual(self.desktops, [hd.DESKTOP, "WinSta0\\" + hd.DESKTOP])
        self.kernel.CreateJobObjectW.assert_called_once_with(None, None)
        self.assertEqual(self.environments, [None])
        self.assertFalse(self.flags[0] & hd.CREATE_UNICODE_ENVIRONMENT)
        self.assertEqual(self.limits.BasicLimitInformation.Affinity, (1 << 14) - 1)
        self.assertEqual(self.limits.JobMemoryLimit, 4096 * 1024 * 1024)
        self.assertTrue(self.limits.BasicLimitInformation.LimitFlags & hd.JOB_OBJECT_LIMIT_BREAKAWAY_OK)
        self.assertIsNone(done.isolation["job_name"])

    def test_two_slots_keep_distinct_desktops_jobs_and_affinity(self):
        first = self.run_slot()
        second = self.run_slot(desktop_name="pool-slot2-run-456", job_name="job-slot2-run-456", affinity_mask=0xC0)
        self.assertNotEqual(first.isolation["desktop_name"], second.isolation["desktop_name"])
        self.assertNotEqual(first.isolation["job_name"], second.isolation["job_name"])
        self.assertEqual(first.isolation["affinity_mask"] & second.isolation["affinity_mask"], 0)

    def test_named_job_collision_never_mutates_or_terminates_foreign_job(self):
        def existing(*args):
            ctypes.set_last_error(hd.ERROR_ALREADY_EXISTS)
            return 909
        self.kernel.CreateJobObjectW.side_effect = existing
        with self.assertRaisesRegex(OSError, "already exists"):
            self.run_slot()
        self.kernel.CloseHandle.assert_called_once_with(909)
        self.kernel.SetInformationJobObject.assert_not_called()
        self.kernel.TerminateJobObject.assert_not_called()
        self.kernel.CreateProcessW.assert_not_called()
        self.user.CloseDesktop.assert_called_once_with(201)

    def test_invalid_or_unavailable_resource_controls_refuse_before_child(self):
        for options in ({"affinity_mask": 0}, {"affinity_mask": True}, {"affinity_mask": 1 << 16},
                        {"affinity_mask": -1}, {"cores": 2}, {"memory_mb": 0},
                        {"memory_mb": True}, {"memory_mb": 1.5}, {"allow_breakaway": "false"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_slot(**options)
        self.kernel.GetProcessAffinityMask.side_effect = lambda p, m, s: (setattr(m._obj, "value", 3) or 1)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.run_slot()
        self.kernel.CreateProcessW.assert_not_called()

    def test_affinity_query_failure_refuses_without_a_job_or_child(self):
        self.kernel.GetProcessAffinityMask.side_effect = None
        self.kernel.GetProcessAffinityMask.return_value = 0
        with self.assertRaisesRegex(OSError, "GetProcessAffinityMask"):
            self.run_slot()
        self.kernel.CreateJobObjectW.assert_not_called()
        self.kernel.CreateProcessW.assert_not_called()
        self.user.CloseDesktop.assert_called_once_with(201)

    def test_set_limits_failure_closes_only_owned_job_and_desktop(self):
        self.kernel.SetInformationJobObject.side_effect = None
        self.kernel.SetInformationJobObject.return_value = 0
        with self.assertRaisesRegex(OSError, "SetInformationJobObject"):
            self.run_slot()
        self.kernel.CloseHandle.assert_called_once_with(101)
        self.user.CloseDesktop.assert_called_once_with(201)
        self.kernel.CreateProcessW.assert_not_called()

    def test_unverified_suspended_membership_never_resumes(self):
        def foreign(process, job, belongs):
            belongs._obj.value = False
            return 1
        self.kernel.IsProcessInJob.side_effect = foreign
        with self.assertRaisesRegex(OSError, "exact owned job"):
            self.run_slot()
        self.kernel.ResumeThread.assert_not_called()
        self.kernel.TerminateJobObject.assert_called_once_with(101, 1)

    def test_assignment_failure_terminates_suspended_child_before_refusal(self):
        self.kernel.AssignProcessToJobObject.side_effect = None
        self.kernel.AssignProcessToJobObject.return_value = 0
        with self.assertRaisesRegex(OSError, "AssignProcessToJobObject"):
            self.run_slot()
        self.kernel.TerminateProcess.assert_called_once_with(401, 1)
        self.kernel.WaitForSingleObject.assert_called_once_with(401, 10000)
        self.kernel.ResumeThread.assert_not_called()

    def test_timeout_preserves_output_contract_and_job_accounting(self):
        self.kernel.WaitForSingleObject.return_value = hd.WAIT_TIMEOUT
        with patch.object(hd, "_read", side_effect=["partial-out", "partial-error"]), \
                patch.object(hd.time, "monotonic", side_effect=[0] + [2] * 10):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                self.run_slot(timeout=1)
        self.assertEqual(caught.exception.stdout, "partial-out")
        self.assertEqual(caught.exception.stderr, "partial-error")
        self.assertTrue(caught.exception.isolation["tree_clean"])
        self.kernel.TerminateJobObject.assert_called_once_with(101, hd.TIMEOUT_EXIT_CODE)

    def test_unknown_job_drain_cannot_return_slot_success(self):
        with patch.object(hd, "_kill_tree", return_value=False):
            with self.assertRaisesRegex(OSError, "observably empty"):
                self.run_slot()

    def test_failed_exit_query_cannot_fabricate_exit_zero(self):
        self.kernel.GetExitCodeProcess.side_effect = None
        self.kernel.GetExitCodeProcess.return_value = 0
        with self.assertRaisesRegex(OSError, "GetExitCodeProcess"):
            self.run_slot()
        self.user.CloseDesktop.assert_called_once_with(201)

    def test_failed_optional_telemetry_does_not_fabricate_zero_peaks(self):
        def without_limits(job, kind, info, size, returned):
            return 0 if kind == hd.JobObjectExtendedLimitInformation else self.query(job, kind, info, size, returned)
        self.kernel.QueryInformationJobObject.side_effect = without_limits
        done = self.run_slot()
        self.assertIsNone(done.isolation["peak_job_memory_bytes"])
        self.assertIsNone(done.isolation["memory_limit_bytes"])
        self.assertFalse(done.isolation["limits_query_ok"])
        self.assertTrue(done.isolation["tree_clean"])

    def test_exact_membership_opens_requested_job_and_closes_handles(self):
        self.assertTrue(hd.process_in_job(1234, "job-slot1-run-123"))
        self.kernel.OpenJobObjectW.assert_called_once_with(hd.JOB_OBJECT_QUERY, False, "job-slot1-run-123")
        self.kernel.OpenProcess.assert_called_once_with(hd.PROCESS_QUERY_LIMITED_INFORMATION, False, 1234)
        self.assertEqual(self.kernel.IsProcessInJob.call_args.args[:2], (601, 501))
        self.assertEqual([c.args for c in self.kernel.CloseHandle.call_args_list], [(601,), (501,)])

    def test_foreign_membership_returns_false_without_any_job_fallback(self):
        def foreign(process, job, belongs):
            belongs._obj.value = False
            return 1
        self.kernel.IsProcessInJob.side_effect = foreign
        self.assertFalse(hd.process_in_job(1234, "owned"))
        self.assertEqual(self.kernel.IsProcessInJob.call_args.args[:2], (601, 501))

    def test_unknown_membership_raises_and_closes_acquired_handles(self):
        for failure in ("OpenJobObjectW", "OpenProcess", "IsProcessInJob"):
            with self.subTest(failure=failure):
                self.kernel.OpenJobObjectW.return_value = 501
                self.kernel.OpenProcess.return_value = 601
                self.kernel.IsProcessInJob.side_effect = self.membership
                self.kernel.CloseHandle.reset_mock()
                target = getattr(self.kernel, failure)
                previous = target.side_effect
                target.side_effect = None
                target.return_value = 0
                with self.assertRaisesRegex(OSError, failure):
                    hd.process_in_job(1234, "owned")
                expected = [] if failure == "OpenJobObjectW" else [(501,)] if failure == "OpenProcess" else [(601,), (501,)]
                self.assertEqual([c.args for c in self.kernel.CloseHandle.call_args_list], expected)
                target.side_effect = previous


if __name__ == "__main__":
    unittest.main()
