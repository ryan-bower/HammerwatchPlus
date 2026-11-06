"""Bounded wait classification: temporary fence bytes, fake processes and clock."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gamelab import launcher, lock


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def read(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class LifecycleWait(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-wait-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.held = self.root / "runtime.lock"
        self.guard = self.root / "runtime.lock.lifecycle"
        self.owner = {"pid": 424242, "token": "b" * 32}
        self.guard.write_text(json.dumps(self.owner), encoding="utf-8")
        self.clock = Clock()
        self.patches = [patch.object(lock, "LOCK", self.held),
                        patch.object(lock, "process_image", return_value="C:/fake/python.exe"),
                        patch.object(launcher.time, "time", side_effect=self.clock.read),
                        patch.object(launcher.time, "monotonic", side_effect=self.clock.read),
                        patch.object(launcher.time, "sleep", side_effect=self.clock.sleep),
                        patch.object(lock, "player_processes", side_effect=AssertionError("real scan")),
                        patch.object(lock, "lab_processes", side_effect=AssertionError("real scan")),
                        patch.object(lock, "kill", side_effect=AssertionError("real cleanup"))]
        self.mocks = [p.start() for p in self.patches]
        for p in self.patches:
            self.addCleanup(p.stop)

    def collision(self):
        try:
            with lock.lifecycle_guard():
                self.fail("entered another owner's lifecycle fence")
        except lock.Refused as error:
            return error
        self.fail("collision did not refuse")

    def assert_fence_unchanged(self, expected=None):
        self.assertEqual(json.loads(self.guard.read_text()), expected or self.owner)
        self.assertFalse(self.held.exists())
        self.mocks[5].assert_not_called()
        self.mocks[6].assert_not_called()
        self.mocks[7].assert_not_called()

    def test_stable_live_lifecycle_owner_is_explicitly_waitable(self):
        error = self.collision()
        self.assertTrue(getattr(error, "waitable", False))
        self.assert_fence_unchanged()

    def test_transient_live_lifecycle_contention_retries_without_deleting_fence(self):
        error = self.collision()
        # The second mocked acquisition represents the owner finishing normally;
        # this test never removes a foreign fence to manufacture permission.
        acquire = Mock(side_effect=[error, None])
        with patch.object(lock, "acquire", acquire):
            launcher.acquire("test", "lab", wait=5)
        self.assertEqual(acquire.call_count, 2)
        self.assertEqual(self.clock.sleeps, [3])
        self.assert_fence_unchanged()

    def test_wait_deadline_never_sleeps_past_budget_or_attempts_after_it(self):
        self.held.write_text(json.dumps(self.owner), encoding="utf-8")
        with patch.object(lock, "pid_alive", return_value=True):
            with self.assertRaises(lock.Refused) as caught:
                lock.acquire("test", "lab")
        error = caught.exception
        acquire = Mock(side_effect=error)
        with patch.object(lock, "acquire", acquire):
            with self.assertRaises(lock.Refused):
                launcher.acquire("test", "lab", wait=0.25)
        self.assertEqual(self.clock.sleeps, [0.25])
        self.assertEqual(acquire.call_count, 1)
        self.assertEqual(self.clock.now, 0.25)
        self.assertEqual(json.loads(self.guard.read_text()), self.owner)
        self.assertEqual(json.loads(self.held.read_text()), self.owner)
        self.mocks[5].assert_not_called()
        self.mocks[6].assert_not_called()
        self.mocks[7].assert_not_called()

    def test_zero_wait_refuses_live_owner_without_polling(self):
        error = self.collision()
        with patch.object(lock, "acquire", side_effect=error) as acquire:
            with self.assertRaises(lock.Refused):
                launcher.acquire("test", "lab", wait=0)
        self.assertEqual(acquire.call_count, 1)
        self.assertEqual(self.clock.sleeps, [])
        self.assert_fence_unchanged()

    def test_dead_or_uninspectable_owner_is_never_waitable(self):
        self.mocks[1].return_value = ""
        error = self.collision()
        self.assertFalse(getattr(error, "waitable", False))
        with patch.object(lock, "acquire", side_effect=error):
            with self.assertRaises(lock.Refused):
                launcher.acquire("test", "lab", wait=30)
        self.assertEqual(self.clock.sleeps, [])
        self.assert_fence_unchanged()

    def test_visibility_error_refuses_without_waiting(self):
        self.mocks[1].side_effect = PermissionError("fake process visibility denied")
        error = self.collision()
        self.assertFalse(getattr(error, "waitable", False))
        with patch.object(lock, "acquire", side_effect=error):
            with self.assertRaises(lock.Refused):
                launcher.acquire("test", "lab", wait=30)
        self.assertEqual(self.clock.sleeps, [])
        self.assert_fence_unchanged()

    def test_malformed_or_incomplete_guard_is_never_waitable(self):
        bad = ["{", "[]", "null", json.dumps({"pid": True, "token": "b" * 32}),
               json.dumps({"pid": 0, "token": "b" * 32}), json.dumps({"pid": 42}),
               json.dumps({"pid": 42, "token": ""}), json.dumps({"pid": "42", "token": "b" * 32})]
        for value in bad:
            with self.subTest(value=value):
                self.guard.write_text(value, encoding="utf-8")
                error = self.collision()
                self.assertFalse(getattr(error, "waitable", False))
                self.assertEqual(self.guard.read_text(), value)
        self.mocks[1].assert_not_called()
        self.assertEqual(self.clock.sleeps, [])
        self.assertFalse(self.held.exists())

    def test_unreadable_guard_is_never_waitable(self):
        original = Path.read_bytes

        def read(path):
            if path == self.guard:
                raise PermissionError("fake unreadable fence")
            return original(path)

        with patch.object(Path, "read_bytes", read):
            error = self.collision()
        self.assertFalse(getattr(error, "waitable", False))
        self.mocks[1].assert_not_called()
        self.assert_fence_unchanged()

    def test_owner_change_during_visibility_check_refuses_without_waiting(self):
        replacement = {"pid": 434343, "token": "c" * 32}

        def change(pid):
            self.guard.write_text(json.dumps(replacement), encoding="utf-8")
            return "C:/fake/python.exe"

        self.mocks[1].side_effect = change
        error = self.collision()
        self.assertFalse(getattr(error, "waitable", False))
        self.assert_fence_unchanged(replacement)

    def test_unproven_refusal_text_cannot_grant_wait_permission(self):
        error = lock.Refused("another GameLab run holds the lock: unproven text")
        with patch.object(lock, "acquire", side_effect=error) as acquire:
            with self.assertRaises(lock.Refused):
                launcher.acquire("test", "lab", wait=0.5)
        self.assertEqual(acquire.call_count, 1)
        self.assertEqual(self.clock.sleeps, [])
        self.assert_fence_unchanged()

    def test_live_runtime_claim_is_still_waitable(self):
        self.held.write_text(json.dumps(self.owner), encoding="utf-8")
        with patch.object(lock, "pid_alive", return_value=True):
            with self.assertRaises(lock.Refused) as caught:
                lock.acquire("test", "lab")
        self.assertTrue(getattr(caught.exception, "waitable", False))
        self.assertEqual(json.loads(self.held.read_text()), self.owner)
        self.assertEqual(self.clock.sleeps, [])

    def runtime_collision(self, mode="lab"):
        with self.assertRaises(lock.Refused) as caught:
            if mode == "play":
                lock._claim_file("test", mode)
            else:
                lock.acquire("test", mode)
        return caught.exception

    def test_malformed_runtime_owner_is_never_waitable(self):
        records = [{"pid": True, "token": "b" * 32}, {"pid": 42},
                   {"pid": 42, "token": ""}, {"pid": "42", "token": "b" * 32}]
        for record in records:
            with self.subTest(record=record), patch.object(lock, "pid_alive", return_value=True):
                self.held.write_text(json.dumps(record), encoding="utf-8")
                error = self.runtime_collision()
                self.assertFalse(getattr(error, "waitable", False))
                self.assertEqual(json.loads(self.held.read_text()), record)
        self.mocks[1].assert_not_called()

    def test_runtime_owner_change_during_probe_is_never_waitable(self):
        self.held.write_text(json.dumps(self.owner), encoding="utf-8")
        replacement = {"pid": 434343, "token": "c" * 32}

        def change(pid):
            self.held.write_text(json.dumps(replacement), encoding="utf-8")
            return "C:/fake/python.exe"

        self.mocks[1].side_effect = change
        error = self.runtime_collision()
        self.assertFalse(getattr(error, "waitable", False))
        self.assertEqual(json.loads(self.held.read_text()), replacement)
        self.assertEqual(json.loads(self.guard.read_text()), self.owner)

    def test_runtime_uninspectable_owner_is_never_waitable(self):
        self.held.write_text(json.dumps(self.owner), encoding="utf-8")
        self.mocks[1].return_value = ""
        error = self.runtime_collision()
        self.assertFalse(getattr(error, "waitable", False))
        self.assertEqual(json.loads(self.held.read_text()), self.owner)

    def test_unreadable_runtime_owner_is_never_waitable(self):
        self.held.write_text(json.dumps(self.owner), encoding="utf-8")
        original = Path.read_bytes

        def read(path):
            if path == self.held:
                raise PermissionError("fake unreadable runtime record")
            return original(path)

        with patch.object(Path, "read_bytes", read):
            error = self.runtime_collision()
        self.assertFalse(getattr(error, "waitable", False))
        self.mocks[1].assert_not_called()
        self.assertEqual(json.loads(self.held.read_text()), self.owner)

    def test_play_collision_always_refuses_without_owner_probe(self):
        self.held.write_text(json.dumps(self.owner), encoding="utf-8")
        error = self.runtime_collision("play")
        self.assertFalse(getattr(error, "waitable", False))
        self.mocks[1].assert_not_called()
        self.assertEqual(json.loads(self.held.read_text()), self.owner)

    def test_retry_stops_if_owner_visibility_becomes_unknown(self):
        attempts = []

        def contend(*args):
            attempts.append(None)
            if len(attempts) == 2:
                self.mocks[1].return_value = ""
            raise self.collision()

        with patch.object(lock, "acquire", side_effect=contend):
            with self.assertRaises(lock.Refused):
                launcher.acquire("test", "lab", wait=20)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.clock.sleeps, [3])
        self.assert_fence_unchanged()

    def test_invalid_wait_budget_refuses_before_acquisition(self):
        for value in (-1, float("inf"), float("nan")):
            with self.subTest(value=value), patch.object(lock, "acquire") as acquire:
                with self.assertRaises(lock.Refused):
                    launcher.acquire("test", "lab", wait=value)
                acquire.assert_not_called()
        self.assertEqual(self.clock.sleeps, [])
        self.assert_fence_unchanged()

    def test_existing_runtime_probe_never_holds_waiter_sidecar(self):
        runtime = self.root / "existing.lock"
        lifecycle = self.root / "existing.lock.lifecycle"
        runtime.write_text(json.dumps(self.owner), encoding="utf-8")
        observed = []

        def probe(pid):
            observed.append(lifecycle.exists())
            # Model the rightful owner needing the sidecar while the waiter
            # observes it. Only a genuinely absent sidecar is acquired here.
            if not lifecycle.exists():
                with lock.lifecycle_guard():
                    self.assertTrue(lifecycle.exists())
            return "C:/fake/python.exe"

        with patch.object(lock, "LOCK", runtime), patch.object(lock, "process_image", side_effect=probe):
            with self.assertRaises(lock.Refused) as caught:
                lock.acquire("waiter", "lab")
        self.assertTrue(getattr(caught.exception, "waitable", False))
        self.assertEqual(observed, [False])
        self.assertFalse(lifecycle.exists())
        self.assertEqual(json.loads(runtime.read_text()), self.owner)
        self.mocks[5].assert_not_called()
        self.mocks[6].assert_not_called()

    def test_absent_runtime_claim_still_requires_guarded_atomic_creation(self):
        runtime = self.root / "fresh.lock"
        lifecycle = self.root / "fresh.lock.lifecycle"
        game = self.root / "fresh-game"
        observed = []

        def players():
            observed.append((lifecycle.exists(), runtime.exists()))
            return []

        with patch.object(lock, "LOCK", runtime), patch.object(lock.env, "GAME", game), \
                patch.object(lock, "TEARDOWN", self.root / "fresh-teardown.json"), \
                patch.object(lock, "player_processes", side_effect=players), \
                patch.object(lock, "lab_processes", return_value=[]):
            lock.acquire("fresh", "lab")
            self.assertTrue(lock.owned())
            self.assertEqual(observed, [(True, True)])
            record = json.loads(runtime.read_text())
            self.assertEqual(len(record["token"]), 32)
            self.assertFalse(lifecycle.exists())
            lock.abandon()  # Drop only the nonce-bearing acquisition made by this test.
        self.assertFalse(runtime.exists())
        self.assertFalse(lifecycle.exists())
        self.assertEqual(json.loads(self.guard.read_text()), self.owner)

    def test_runtime_appearing_after_precheck_is_probed_only_after_sidecar_release(self):
        runtime = self.root / "raced.lock"
        lifecycle = self.root / "raced.lock.lifecycle"
        original_open = lock.os.open
        observed = []

        def competing_open(path, flags, *args, **kwargs):
            if Path(path) == runtime:
                runtime.write_text(json.dumps(self.owner), encoding="utf-8")
            return original_open(path, flags, *args, **kwargs)

        def probe(pid):
            observed.append(lifecycle.exists())
            return "C:/fake/python.exe"

        with patch.object(lock, "LOCK", runtime), patch.object(lock.os, "open", side_effect=competing_open), \
                patch.object(lock, "process_image", side_effect=probe):
            with self.assertRaises(lock.Refused) as caught:
                lock.acquire("raced", "lab")
        self.assertTrue(getattr(caught.exception, "waitable", False))
        self.assertEqual(observed, [False])
        self.assertFalse(lifecycle.exists())
        self.assertEqual(json.loads(runtime.read_text()), self.owner)
        self.mocks[5].assert_not_called()
        self.mocks[6].assert_not_called()
        self.mocks[7].assert_not_called()

    def test_absent_runtime_never_bypasses_foreign_lifecycle_guard(self):
        with patch.object(lock, "_claim_file", side_effect=AssertionError("unguarded claim")) as claim:
            with self.assertRaises(lock.Refused) as caught:
                lock.acquire("guarded", "lab")
        self.assertTrue(getattr(caught.exception, "waitable", False))
        claim.assert_not_called()
        self.assert_fence_unchanged()

    def test_runtime_race_with_unknown_owner_preserves_fence_without_probe(self):
        runtime = self.root / "unknown-raced.lock"
        lifecycle = self.root / "unknown-raced.lock.lifecycle"
        foreign = {"pid": 434343}
        original_open = lock.os.open

        def competing_open(path, flags, *args, **kwargs):
            if Path(path) == runtime:
                runtime.write_text(json.dumps(foreign), encoding="utf-8")
            return original_open(path, flags, *args, **kwargs)

        with patch.object(lock, "LOCK", runtime), patch.object(lock.os, "open", side_effect=competing_open):
            with self.assertRaises(lock.Refused) as caught:
                lock.acquire("unknown-raced", "lab")
        self.assertFalse(getattr(caught.exception, "waitable", False))
        self.mocks[1].assert_not_called()
        self.assertFalse(lifecycle.exists())
        self.assertEqual(json.loads(runtime.read_text()), foreign)
        self.mocks[5].assert_not_called()
        self.mocks[6].assert_not_called()
        self.mocks[7].assert_not_called()


if __name__ == "__main__":
    unittest.main()
