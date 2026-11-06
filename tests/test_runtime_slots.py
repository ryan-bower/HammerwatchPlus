"""Worker-context ownership and confinement against fake identities/private trees."""
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gamelab import runtime


class RuntimeSlots(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-runtime-slots-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workers = self.root / "workers"
        self.results = self.root / "results"
        self.machine = self.root / "legacy/gamelab.lock"
        self.machine.parent.mkdir()
        self.pid = os.getpid()
        self.info = {self.pid: (10001, str(self.root / "python.exe"))}
        self.lease = {"pid": self.pid, "token": "a" * 32, "scenario": "pool", "mode": "lab"}
        self.machine.write_text(json.dumps(self.lease))
        self.source = {"head": "b" * 40, "source_sha256": "c" * 64,
                       "files": 123, "fingerprint_scope": "mods+gamelab+tools-v2"}
        for p in (patch.object(runtime, "WORKERS", self.workers),
                  patch.object(runtime, "RESULTS", self.results),
                  patch.object(runtime, "MACHINE_LOCK", self.machine),
                  patch.object(runtime.os, "cpu_count", return_value=8),
                  patch.object(runtime, "process_info", side_effect=lambda pid: self.info.get(pid)),
                  patch.dict(os.environ, {}, clear=True)):
            p.start()
            self.addCleanup(p.stop)
        self.pool = runtime.create_pool(self.workers / "pool-one", self.lease, self.source)

    @contextmanager
    def slot(self, number=0):
        with patch.dict(os.environ, runtime.child_env(self.pool, number), clear=True):
            yield runtime.current()

    def slot_lease(self, ctx, token="d" * 32):
        path = ctx.game_dir.parent / "gamelab.lock"
        path.write_text(json.dumps({"pid": self.pid, "token": token}))
        return path

    def game(self, ctx, pid=43210, created=20001):
        self.info[pid] = (created, str(ctx.game_dir / "HWR2.exe"))
        return pid

    def mutate_manifest(self, mutate):
        path = Path(self.pool["manifest_path"])
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value))

    def test_no_context_preserves_serial_and_preparation_has_no_writes(self):
        self.assertIsNone(runtime.current())
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        with runtime.preparation_guard():
            pass
        self.assertEqual(before, sorted(p.relative_to(self.root) for p in self.root.rglob("*")))
        self.assertFalse(runtime.is_registered_process(43210, self.root / "other.exe"))

    def test_context_roots_resources_and_secrets_are_distinct(self):
        a, b = self.pool["slots"]
        self.assertNotEqual(a["token"], b["token"])
        self.assertNotEqual(a["game_dir"], b["game_dir"])
        self.assertNotEqual(a["desktop_name"], b["desktop_name"])
        self.assertNotEqual(a["job_name"], b["job_name"])
        self.assertEqual(a["affinity_mask"] & b["affinity_mask"], 0)
        self.assertEqual((a["memory_mb"], b["memory_mb"]), (4096, 4096))
        with self.slot() as ctx:
            self.assertEqual(ctx.pool_id, "pool-one")
            self.assertEqual(ctx.slot_id, "worker-1")
            self.assertEqual(ctx.game_dir, self.workers / "pool-one/worker-1/game")
            self.assertEqual(ctx.module_root.parent, ctx.game_dir.parent)
            self.assertEqual(ctx.cache_dir.parent, ctx.game_dir.parent)

    def test_partial_or_wrong_secret_context_refuses(self):
        with self.assertRaises(runtime.RuntimeError):
            runtime.current({runtime.ENV_KEYS[0]: self.pool["manifest_path"]})
        env = runtime.child_env(self.pool, 0)
        env[runtime.ENV_KEYS[2]] = "e" * 32
        with self.assertRaises(runtime.RuntimeError):
            runtime.current(env)

    def test_arbitrary_pool_root_traversal_reserved_names_and_reuse_refuse(self):
        for root in (self.root / "escape", self.workers / ".." / "escape", self.workers / "con"):
            with self.subTest(root=root), self.assertRaises(runtime.RuntimeError):
                runtime.create_pool(root, self.lease, self.source)
        with self.assertRaises(FileExistsError):
            runtime.create_pool(self.workers / "pool-one", self.lease, self.source)

    def test_prefixed_uuid_pool_name_is_supported(self):
        pool = runtime.create_pool(self.workers / ("p" + "1" * 32), self.lease, self.source)
        self.assertEqual(pool["pool_id"], "p" + "1" * 32)
        self.assertTrue(runtime.child_env(pool, 0))

    def catalog_snapshot(self):
        path = self.root / "pool-admission/catalog.snapshot.json"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'{"schema_version":1}\n')
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_catalog_snapshot_is_authenticated_in_child_context(self):
        pin = self.catalog_snapshot()
        pool = runtime.create_pool(self.workers / "pool-catalog", self.lease, self.source, catalog=pin)
        with patch.dict(os.environ, runtime.child_env(pool, 0), clear=True):
            self.assertEqual(runtime.current().manifest["catalog"], pin)
            Path(pin["path"]).write_bytes(b'{"schema_version":2}\n')
            with self.assertRaisesRegex(runtime.RuntimeError, "snapshot changed"):
                runtime.current()

    def test_catalog_bad_hash_or_path_refuses_before_pool_publication(self):
        pin = self.catalog_snapshot()
        for descriptor in ({**pin, "sha256": "0" * 64},
                           {**pin, "path": str(self.root / "catalog.snapshot.json")},
                           {**pin, "unexpected": True}):
            with self.subTest(descriptor=descriptor), self.assertRaises(runtime.RuntimeError):
                runtime.create_pool(self.workers / "pool-rejected", self.lease, self.source, catalog=descriptor)
            self.assertFalse((self.workers / "pool-rejected").exists())

    def test_malformed_source_and_slot_list_are_refusals(self):
        path = Path(self.pool["manifest_path"])
        original = path.read_bytes()
        for key, value in (("source", None), ("slots", None), ("machine_lease", None)):
            path.write_bytes(original)
            self.mutate_manifest(lambda m: m.__setitem__(key, value))
            with self.subTest(key=key), self.assertRaises(runtime.RuntimeError):
                runtime.child_env(self.pool, 0)

    def test_results_cannot_escape_slot_or_use_other_slot_root(self):
        for dest in (self.root / "escape", Path(self.pool["slots"][1]["results"]) / "run", Path(self.pool["slots"][0]["results"])):
            with self.subTest(dest=dest), self.assertRaises(runtime.RuntimeError):
                runtime.child_env(self.pool, 0, dest)

    def test_coordinator_absence_and_pid_reuse_refuse(self):
        for state in (None, (10002, str(self.root / "python.exe"))):
            self.info[self.pid] = state
            with self.subTest(state=state), self.assertRaises(runtime.RuntimeError):
                runtime.child_env(self.pool, 0)

    def test_changed_machine_lease_refuses_without_touching_it(self):
        foreign = dict(self.lease, token="f" * 32)
        self.machine.write_text(json.dumps(foreign))
        with self.assertRaises(runtime.RuntimeError):
            runtime.child_env(self.pool, 0)
        self.assertEqual(json.loads(self.machine.read_text()), foreign)

    def test_changed_root_desktop_job_affinity_or_memory_refuses(self):
        path = Path(self.pool["manifest_path"])
        original = path.read_bytes()
        changes = {"game_dir": str(self.root / "outside"), "desktop_name": "foreign",
                   "job_name": "foreign", "affinity_mask": True, "memory_mb": 2048}
        for key, value in changes.items():
            path.write_bytes(original)
            self.mutate_manifest(lambda m: m["slots"][0].__setitem__(key, value))
            with self.subTest(key=key), self.assertRaises(runtime.RuntimeError):
                runtime.current(runtime.child_env(self.pool, 0))

    def test_reparse_ancestor_refuses_even_when_exists_masks_it(self):
        target = self.workers
        original = Path.lstat
        reached = []

        def metadata(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == target:
                reached.append(path)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info

        with patch.object(Path, "lstat", metadata), patch.object(Path, "exists", return_value=False):
            with self.assertRaises(runtime.RuntimeError):
                runtime.child_env(self.pool, 0)
        self.assertTrue(reached)

    def test_dangling_result_reparse_is_not_treated_as_absent(self):
        target = Path(self.pool["slots"][0]["results"]) / "dangling"
        original = Path.lstat

        def metadata(path, *args, **kwargs):
            if path == target:
                return SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", metadata), patch.object(Path, "exists", return_value=False):
            with self.assertRaises(runtime.RuntimeError):
                runtime.child_env(self.pool, 0, target)

    def test_register_own_game_then_recognize_sibling_without_owning_it(self):
        with self.slot(1) as sibling:
            self.slot_lease(sibling)
            pid = self.game(sibling)
            runtime.register_game(pid)
            self.assertTrue(runtime.owned_game(pid, self.info[pid][1]))
        with self.slot(0):
            self.assertTrue(runtime.is_registered_process(pid, self.info[pid][1]))
            self.assertFalse(runtime.owned_game(pid, self.info[pid][1]))
        self.assertFalse(runtime.registered_games_absent(self.pool))

    def test_unregistered_or_wrong_image_game_is_not_a_sibling(self):
        with self.slot() as ctx:
            self.slot_lease(ctx)
            pid = self.game(ctx)
            self.assertFalse(runtime.is_registered_process(pid, self.info[pid][1]))
            self.info[pid] = (20001, str(self.root / "real-user/HWR2.exe"))
            with self.assertRaises(runtime.RuntimeError):
                runtime.register_game(pid)
            self.assertFalse((ctx.game_dir.parent / "game.json").exists())

    def test_register_needs_slot_lease_and_correct_creation(self):
        with self.slot() as ctx:
            pid = self.game(ctx)
            with self.assertRaises(FileNotFoundError):
                runtime.register_game(pid)
            self.slot_lease(ctx)
            with self.assertRaises(runtime.RuntimeError):
                runtime.register_game(pid, creation=20002)
            runtime.register_game(pid, creation=20001)

    def test_live_game_registration_is_not_replaced(self):
        with self.slot() as ctx:
            self.slot_lease(ctx)
            pid = self.game(ctx)
            runtime.register_game(pid)
            before = (ctx.game_dir.parent / "game.json").read_bytes()
            other = self.game(ctx, pid=43211)
            with self.assertRaises(runtime.RuntimeError):
                runtime.register_game(other)
            self.assertEqual((ctx.game_dir.parent / "game.json").read_bytes(), before)

    def test_pid_reuse_never_authorizes_cleanup_but_allows_new_pass(self):
        with self.slot() as ctx:
            self.slot_lease(ctx)
            pid = self.game(ctx)
            runtime.register_game(pid)
            self.info[pid] = (20002, str(ctx.game_dir / "HWR2.exe"))
            self.assertFalse(runtime.owned_game(pid, self.info[pid][1]))
            runtime.register_game(pid, creation=20002)
            self.assertTrue(runtime.owned_game(pid, self.info[pid][1]))

    def test_changed_slot_lease_never_authorizes_old_game_cleanup(self):
        with self.slot() as ctx:
            self.slot_lease(ctx)
            pid = self.game(ctx)
            runtime.register_game(pid)
            self.slot_lease(ctx, token="f" * 32)
            self.assertFalse(runtime.owned_game(pid, self.info[pid][1]))

    def test_unknown_process_visibility_does_not_become_absence(self):
        with self.slot() as ctx:
            self.slot_lease(ctx)
            pid = self.game(ctx)
            runtime.register_game(pid)
        probe = runtime.process_info.side_effect

        def denied(value):
            if value == pid:
                raise runtime.RuntimeError("fake access denied")
            return probe(value)

        with patch.object(runtime, "process_info", side_effect=denied):
            with self.assertRaises(runtime.RuntimeError):
                runtime.registered_games_absent(self.pool)
        self.assertFalse(json.loads(Path(self.pool["manifest_path"]).read_text())["closed"])

    def test_preparation_guard_excludes_other_preflight_without_removing_owner(self):
        with self.slot():
            path = Path(self.pool["manifest_path"]).with_name("preparation.lock")
            with runtime.preparation_guard():
                before = path.read_bytes()
                with self.assertRaises(runtime.RuntimeError):
                    with runtime.preparation_guard(timeout=0):
                        self.fail("second preparation entered")
                self.assertEqual(path.read_bytes(), before)
            self.assertFalse(path.exists())

    def test_preparation_foreign_owner_change_is_preserved(self):
        with self.slot():
            path = Path(self.pool["manifest_path"]).with_name("preparation.lock")
            with self.assertRaises(runtime.RuntimeError):
                with runtime.preparation_guard():
                    value = json.loads(path.read_text())
                    value["token"] = "f" * 32
                    path.write_text(json.dumps(value))
            self.assertTrue(path.exists())

    def test_stale_preparation_is_retained_without_automatic_recovery(self):
        with self.slot():
            path = Path(self.pool["manifest_path"]).with_name("preparation.lock")
            held = {"pid": 65432, "created": 12345, "token": "f" * 32,
                    "pool_token": self.pool["token"]}
            path.write_text(json.dumps(held))
            with self.assertRaises(runtime.RuntimeError):
                with runtime.preparation_guard(timeout=0):
                    self.fail("stale guard admitted")
            self.assertEqual(json.loads(path.read_text()), held)

    def test_pool_close_refuses_live_games_and_any_slot_lease(self):
        with self.slot() as ctx:
            lease = self.slot_lease(ctx)
            pid = self.game(ctx)
            runtime.register_game(pid)
        with self.assertRaises(runtime.RuntimeError):
            runtime.close_pool(self.pool)
        del self.info[pid]
        with self.assertRaises(runtime.RuntimeError):
            runtime.close_pool(self.pool)
        lease.unlink()
        runtime.close_pool(self.pool)
        with self.assertRaises(runtime.RuntimeError):
            runtime.child_env(self.pool, 0)

    def test_pool_close_cannot_be_done_by_child(self):
        self.info[54321] = (30001, str(self.root / "python.exe"))
        with patch.object(runtime.os, "getpid", return_value=54321):
            with self.assertRaises(runtime.RuntimeError):
                runtime.close_pool(self.pool)

    def termination_kernel(self, ctx, created=20001, image=None):
        handle, job = 0x123456789ABC, 0x23456789ABCD
        closed = []

        def code(h, out):
            self.assertEqual(h, handle); out._obj.value = 259; return 1

        def times(h, c, *rest):
            self.assertEqual(h, handle)
            c._obj.dwHighDateTime = created >> 32; c._obj.dwLowDateTime = created & 0xffffffff
            return 1

        def name(h, flags, text, size):
            self.assertEqual(h, handle); text.value = str(image or ctx.game_dir / "HWR2.exe"); return 1

        def belongs(h, j, out):
            self.assertEqual((h, j), (handle, job)); out._obj.value = 1; return 1

        kernel = SimpleNamespace(OpenProcess=Mock(return_value=handle), GetExitCodeProcess=Mock(side_effect=code),
                                 GetProcessTimes=Mock(side_effect=times), QueryFullProcessImageNameW=Mock(side_effect=name),
                                 OpenJobObjectW=Mock(return_value=job), IsProcessInJob=Mock(side_effect=belongs),
                                 TerminateProcess=Mock(return_value=1), WaitForSingleObject=Mock(return_value=0),
                                 CloseHandle=Mock(side_effect=closed.append))
        return kernel, handle, job, closed

    def test_termination_uses_same_held_handle_identity_named_job_and_bounded_wait(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            kernel, handle, job, closed = self.termination_kernel(ctx)
            with patch.object(runtime, "_kernel", return_value=kernel):
                self.assertTrue(runtime.terminate_owned_game(pid, self.info[pid][1], timeout=1.25))
            kernel.OpenProcess.assert_called_once_with(0x101001, False, pid)
            kernel.OpenJobObjectW.assert_called_once_with(4, False, ctx.job_name)
            kernel.TerminateProcess.assert_called_once_with(handle, 1)
            kernel.WaitForSingleObject.assert_called_once_with(handle, 1250)
            self.assertEqual(closed, [job, handle])
            from ctypes import wintypes
            for name in ("IsProcessInJob", "TerminateProcess", "WaitForSingleObject"):
                self.assertIs(getattr(kernel, name).argtypes[0], wintypes.HANDLE)

    def test_termination_refuses_pid_reuse_detected_on_held_handle(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            kernel, handle, _, closed = self.termination_kernel(ctx, created=20002)
            with patch.object(runtime, "_kernel", return_value=kernel), self.assertRaises(runtime.RuntimeError):
                runtime.terminate_owned_game(pid, self.info[pid][1])
            kernel.TerminateProcess.assert_not_called()
            kernel.OpenJobObjectW.assert_not_called()
            self.assertEqual(closed, [handle])

    def test_termination_cannot_be_redirected_by_a_later_numeric_pid_lookup(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            kernel, handle, job, closed = self.termination_kernel(ctx)
            image = self.info[pid][1]

            def opened(*args):
                self.info[pid] = (99999, str(self.root / "foreign.exe"))
                return handle

            kernel.OpenProcess.side_effect = opened
            with patch.object(runtime, "_kernel", return_value=kernel):
                self.assertTrue(runtime.terminate_owned_game(pid, image))
            kernel.TerminateProcess.assert_called_once_with(handle, 1)
            self.assertEqual(closed, [job, handle])

    def test_termination_refuses_foreign_image_from_held_handle(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            kernel, handle, _, closed = self.termination_kernel(ctx, image=self.root / "foreign/HWR2.exe")
            with patch.object(runtime, "_kernel", return_value=kernel), self.assertRaises(runtime.RuntimeError):
                runtime.terminate_owned_game(pid, self.info[pid][1])
            kernel.TerminateProcess.assert_not_called()
            self.assertEqual(closed, [handle])

    def test_termination_requires_queryable_exact_job_membership(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            for mode in ("unavailable", "query-failed", "foreign-job"):
                kernel, handle, job, closed = self.termination_kernel(ctx)
                if mode == "unavailable":
                    kernel.OpenJobObjectW.return_value = 0
                elif mode == "query-failed":
                    kernel.IsProcessInJob.side_effect = None; kernel.IsProcessInJob.return_value = 0
                else:
                    kernel.IsProcessInJob.side_effect = lambda h, j, out: 1  # false BOOL output
                with self.subTest(mode=mode), patch.object(runtime, "_kernel", return_value=kernel), self.assertRaises(runtime.RuntimeError):
                    runtime.terminate_owned_game(pid, self.info[pid][1])
                kernel.TerminateProcess.assert_not_called()
                self.assertEqual(closed, [handle] if mode == "unavailable" else [job, handle])

    def test_termination_refuses_unreadable_identity_failed_terminate_and_wait_timeout(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            registration = (ctx.game_dir.parent / "game.json").read_bytes()
            for mode in ("identity", "terminate", "wait"):
                kernel, handle, job, closed = self.termination_kernel(ctx)
                if mode == "identity":
                    kernel.GetProcessTimes.side_effect = None; kernel.GetProcessTimes.return_value = 0
                elif mode == "terminate":
                    kernel.TerminateProcess.return_value = 0
                else:
                    kernel.WaitForSingleObject.return_value = 258
                with self.subTest(mode=mode), patch.object(runtime, "_kernel", return_value=kernel), self.assertRaises(runtime.RuntimeError):
                    runtime.terminate_owned_game(pid, self.info[pid][1], timeout=0.1)
                self.assertEqual(closed, [handle] if mode == "identity" else [job, handle])
                self.assertEqual((ctx.game_dir.parent / "game.json").read_bytes(), registration)
                if mode == "identity": kernel.TerminateProcess.assert_not_called()
                if mode != "wait": kernel.WaitForSingleObject.assert_not_called()

    def test_termination_rechecks_slot_lease_after_identity_and_membership(self):
        with self.slot() as ctx:
            self.slot_lease(ctx); pid = self.game(ctx); runtime.register_game(pid)
            kernel, handle, job, closed = self.termination_kernel(ctx)

            def takeover(h, j, out):
                out._obj.value = 1
                self.slot_lease(ctx, token="f" * 32)
                return 1

            kernel.IsProcessInJob.side_effect = takeover
            with patch.object(runtime, "_kernel", return_value=kernel), self.assertRaises(runtime.RuntimeError):
                runtime.terminate_owned_game(pid, self.info[pid][1])
            kernel.TerminateProcess.assert_not_called()
            self.assertEqual(closed, [job, handle])

    def test_termination_refuses_serial_context_and_invalid_timeout_without_kernel(self):
        with patch.object(runtime, "_kernel") as kernel:
            with self.assertRaises(runtime.RuntimeError):
                runtime.terminate_owned_game(43210, self.root / "game/HWR2.exe")
            for timeout in (True, 0, -1, float("nan"), float("inf"), 61):
                with self.subTest(timeout=timeout), self.assertRaises(runtime.RuntimeError):
                    runtime.terminate_owned_game(43210, self.root / "game/HWR2.exe", timeout)
            kernel.assert_not_called()


class WindowsIdentityABI(unittest.TestCase):
    def test_handle_arguments_are_pointer_sized_for_every_kernel_query(self):
        from ctypes import wintypes

        class Function:
            def __init__(self, fn): self.fn = fn
            def __call__(self, *args): return self.fn(*args)

        handle = 0x123456789ABC
        seen = []

        def code(h, out):
            self.assertEqual(h, handle); out._obj.value = 259; return 1

        def times(h, created, *rest):
            self.assertEqual(h, handle)
            created._obj.dwHighDateTime = 2; created._obj.dwLowDateTime = 3
            return 1

        def image(h, flags, text, size):
            self.assertEqual(h, handle); text.value = "C:/fake/python.exe"; return 1

        kernel = SimpleNamespace(OpenProcess=Function(lambda *a: handle),
                                 GetExitCodeProcess=Function(code), GetProcessTimes=Function(times),
                                 QueryFullProcessImageNameW=Function(image), CloseHandle=Function(lambda h: seen.append(h)))
        with patch.object(runtime.os, "name", "nt"), patch.object(runtime.ctypes, "WinDLL", return_value=kernel, create=True):
            self.assertEqual(runtime.process_info(123), ((2 << 32) | 3, "C:/fake/python.exe"))
            def exited(h, created, ended, *rest):
                ended._obj.dwLowDateTime = 1
                return times(h, created, ended, *rest)
            kernel.GetProcessTimes.fn = exited
            self.assertIsNone(runtime.process_info(123))  # exited with code259 is not a live owner
        for name in ("GetExitCodeProcess", "GetProcessTimes", "QueryFullProcessImageNameW", "CloseHandle"):
            self.assertIs(getattr(kernel, name).argtypes[0], wintypes.HANDLE)
        self.assertEqual(seen, [handle, handle])


if __name__ == "__main__":
    unittest.main()
