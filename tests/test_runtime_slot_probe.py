"""Adversarial protocol/deadline/routing predicates; no Win32 or native execution."""
from pathlib import Path
import unittest

from gamelab.bots import qa_runtime_slots as probe


class SlotProbeTests(unittest.TestCase):
    def setUp(self):
        self.own = {"pool_id": "pair", "slot_id": "worker-1", "game_pid": 101}
        self.slot = {"slot_id": "worker-2", "game_dir": str(Path.cwd() / "game2"),
                     "results": str(Path.cwd() / "results2")}
        self.peer = {"version": 1, "pool_id": "pair", "slot_id": "worker-2", "role": "b",
                     "phase": "ready", "game_pid": 202, "game_created": 12345,
                     "game_image": str(Path(self.slot["game_dir"]) / "HWR2.exe"),
                     "results": str(Path(self.slot["results"]) / "run-b"), "run_id": "run-b"}

    def test_cross_pool_slot_role_phase_and_shared_pid_refuse(self):
        self.assertEqual(probe.validate_peer(self.peer, self.own, self.slot, "b", "ready"), self.peer)
        for key, value in [("pool_id", "old"), ("slot_id", "worker-1"), ("role", "a"),
                           ("phase", "three"), ("game_pid", 101), ("game_created", True)]:
            with self.subTest(key=key):
                row = dict(self.peer, **{key: value})
                with self.assertRaises(ValueError):
                    probe.validate_peer(row, self.own, self.slot, "b", "ready")

    def test_results_escape_foreign_executable_and_wrong_run_refuse(self):
        for key, value in [("results", str(Path.cwd() / "foreign")),
                           ("results", str(Path(self.slot["results"]) / ".." / "foreign")),
                           ("game_image", str(Path.cwd() / "HWR2.exe")), ("run_id", "other")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.validate_peer(dict(self.peer, **{key: value}), self.own, self.slot, "b", "ready")

    def test_deadline_cannot_extend_under_unready_peer(self):
        now = [0.0]
        polls = []
        def sleep(seconds):
            now[0] += seconds
        def pending():
            polls.append(now[0])
            return None
        with self.assertRaises(ValueError):
            probe.wait_until(pending, .25, lambda: None, lambda: now[0], sleep)
        self.assertLessEqual(len(polls), 3)
        self.assertAlmostEqual(now[0], .25)

    def test_visibility_failure_is_not_success_or_absence(self):
        def denied():
            raise OSError("query visibility denied")
        with self.assertRaises(OSError):
            probe.wait_until(denied, 10, lambda: None, lambda: 0, lambda _: None)

    def test_cross_routed_scalar_tag_and_ui_each_fail_independently(self):
        good = {"marker_value": 57, "tag": "pair:a:one", "tag_ok": True, "phase": "town",
                "spawned": True, "menu_open": True}
        self.assertTrue(probe.assess_observation(good, 57, True, "pair:a:one"))
        for key, value in [("marker_value", 59), ("tag", "pair:b:one"), ("menu_open", False),
                           ("spawned", False), ("phase", "mission"), ("tag_ok", False)]:
            with self.subTest(key=key):
                self.assertFalse(probe.assess_observation(dict(good, **{key: value}), 57, True, "pair:a:one"))

    def test_marker_write_requires_immediate_ack_and_independent_readback(self):
        ack = {"ok": True, "name": "v_fps_limit", "value": 57}
        readback = {"ok": True, "cvars": {"v_fps_limit": 57}}
        self.assertTrue(probe.assess_marker_write(ack, readback, 57))
        # A callback-clamped setter must fail even if a later read happens to match.
        for bad in [{**ack, "value": 14}, {**ack, "ok": False},
                    {**ack, "value": "57"}, {**ack, "value": float("nan")},
                    {**ack, "name": "g_time_hour"}]:
            with self.subTest(ack=bad):
                self.assertFalse(probe.assess_marker_write(bad, readback, 57))
        for bad in [{"ok": True, "cvars": {"v_fps_limit": 14}},
                    {"ok": False, "cvars": {"v_fps_limit": 57}}, {"ok": True, "cvars": {}}]:
            with self.subTest(readback=bad):
                self.assertFalse(probe.assess_marker_write(ack, bad, 57))
        # Restoration uses the same independent acknowledgement/readback contract.
        self.assertTrue(probe.assess_marker_write({**ack, "value": 60},
                                                 {"ok": True, "cvars": {"v_fps_limit": 60}}, 60))

    def test_pid_reuse_means_old_identity_gone_not_permission_to_kill(self):
        self.assertTrue(probe.old_process_gone(None, 12345))
        self.assertTrue(probe.old_process_gone((54321, "new-owner.exe"), 12345))
        self.assertFalse(probe.old_process_gone((12345, "HWR2.exe"), 12345))

    def test_expired_or_nonfinite_budget_never_admits(self):
        for deadline, now in [(1, 1), (0, 2), (float("nan"), 0), (float("inf"), 0)]:
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                probe.remaining(deadline, now)


if __name__ == "__main__":
    unittest.main()
