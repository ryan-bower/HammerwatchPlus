"""Doctor smoke evidence must agree before a reusable pass stamp is written.

All runtime files live in TemporaryDirectory; game launches and resets are mocked.
Imports resolve from this committed test's repository location.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
from gamelab import doctor, lock  # noqa: E402

BUILD = {"build_id": "25932569", "exe_sha256": "232cfb7a784c4851618afae1f9b7481deb60e1b46e7e4fcae79c4b4c35751100"}
KEY = {"build": BUILD["build_id"], "cores": 16, "gpus": ["fake-adapter"], "shim_source_sha256": "0" * 64}
COMPLETE = {"verdict": "PASS", "scenario": "null-payload", "mode": "lab", "environment": "gamelab",
            "build": BUILD, "error": None, "partial": False, "build_drift": False,
            "teardown": {"clean": True, "reasons": []}, "assertions": [{"name": "safe control", "ok": True}]}
INNER = {"scenario": "null-payload", "mode": "lab", "partial": False,
         "assertions": [{"name": "safe control", "ok": True}]}


class SmokeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hwp-doctor-smoke-")
        self.addCleanup(self.temp.cleanup)
        self.fake_repo = Path(self.temp.name).resolve()
        self.stamp = self.fake_repo / "gamelab/smoke.local.json"
        self.stamp.parent.mkdir(parents=True)
        self.run_dir = self.fake_repo / "gamelab/results/1-null-payload-lab"
        self.output = io.StringIO()
        self.addCleanup(patch.stopall)
        patch.object(doctor, "REPO", self.fake_repo).start()
        patch.object(doctor, "SMOKE_STAMP", self.stamp).start()
        patch.object(doctor, "gpus", return_value=["fake-adapter"]).start()
        patch.object(doctor, "remote_session", return_value=False).start()
        patch.object(doctor, "smoke_key", return_value=copy.deepcopy(KEY)).start()
        patch.object(doctor, "python", return_value=sys.executable).start()
        patch.object(doctor.pin_build, "pinned", return_value=copy.deepcopy(BUILD)).start()
        patch.object(lock, "LOCK", self.fake_repo / "gamelab/runtime.lock").start()
        patch.object(lock, "TEARDOWN", self.fake_repo / "gamelab/teardown.json").start()
        patch.object(doctor, "run_py", side_effect=AssertionError("No reset/tool process is allowed")).start()
        patch.dict(os.environ, {"HWP_SMOKE_SCENARIO": "null-payload"}).start()

    def invoke(self, record=COMPLETE, inner=INNER):
        def fake_launcher(command, *args, **kwargs):
            self.assertEqual(command, [sys.executable, "-m", "gamelab", "run", "null-payload", "--mode", "lab"])
            self.assertEqual(Path(kwargs["cwd"]), self.fake_repo)
            if record is not None:
                self.run_dir.mkdir(parents=True)
                serialized = record if isinstance(record, str) else json.dumps(record)
                (self.run_dir / "run.json").write_text(serialized, encoding="utf-8")
                if inner is not None:
                    (self.run_dir / "inner.json").write_text(json.dumps(inner), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "fake launcher exit 0\n", "")

        report = doctor.Report()
        with patch.object(doctor.subprocess, "run", side_effect=fake_launcher) as launch, contextlib.redirect_stdout(self.output):
            try:
                doctor.smoke(report, fix=True, force=True)
            except Exception as error:
                self.fail(f"Smoke must record an invalid-result refusal, not raise {type(error).__name__}: {error}")
        self.assertEqual(launch.call_count, 1)
        return report

    def assert_refused(self, record=COMPLETE, inner=INNER):
        report = self.invoke(record, inner)
        self.assertFalse(report.rows[-1][1], "Exit 0 alone must not mark invalid smoke evidence PASS")
        stamp = json.loads(self.stamp.read_text(encoding="utf-8")) if self.stamp.exists() else {}
        self.assertIn("failed", stamp, "Invalid smoke evidence must retain an explicit failed attempt")
        self.assertNotIn("key", stamp, "Invalid smoke evidence must never receive a reusable pass key")

    def test_valid_final_pass_is_stamped(self):
        report = self.invoke()
        self.assertTrue(report.rows[-1][1])
        stamp = json.loads(self.stamp.read_text(encoding="utf-8"))
        self.assertEqual(stamp["run"], self.run_dir.name)
        self.assertEqual(stamp["key"], KEY)
        self.assertNotIn("failed", stamp)

    def test_zero_exit_without_run_json_is_refused(self):
        self.assert_refused(record=None)

    def test_zero_exit_with_malformed_json_is_refused(self):
        self.assert_refused(record='{"verdict":')

    def test_zero_exit_with_nonobject_json_is_refused(self):
        self.assert_refused(record="[]")

    def test_zero_exit_with_unsafe_outer_record_is_refused(self):
        mutations = {
            "fail-verdict": {"verdict": "FAIL"},
            "invalid-verdict": {"verdict": "INVALID"},
            "partial": {"partial": True},
            "dirty-teardown": {"teardown": {"clean": False, "reasons": ["fake dirty child"]}},
            "build-drift": {"build_drift": True},
            "runner-error": {"error": "fake runner error"},
            "failed-assertion": {"assertions": [{"name": "safe control", "ok": False}]},
            "wrong-scenario": {"scenario": "different-scenario"},
            "wrong-mode": {"mode": "watch"},
            "wrong-build": {"build": {"build_id": "different-build", "exe_sha256": "f" * 64}},
        }
        for name, changed in mutations.items():
            with self.subTest(name=name):
                self.stamp.unlink(missing_ok=True)
                if self.run_dir.exists():
                    for file in self.run_dir.iterdir():
                        file.unlink()
                    self.run_dir.rmdir()
                self.assert_refused(record={**copy.deepcopy(COMPLETE), **changed})

    def test_zero_exit_without_final_inner_result_is_refused(self):
        self.assert_refused(inner=None)

    def test_zero_exit_with_partial_inner_result_is_refused(self):
        self.assert_refused(inner={**copy.deepcopy(INNER), "partial": True})

    def test_zero_exit_with_missing_inner_assertions_is_refused(self):
        inner = copy.deepcopy(INNER)
        inner.pop("assertions")
        self.assert_refused(inner=inner)

    def test_zero_exit_with_mismatched_inner_assertions_is_refused(self):
        self.assert_refused(inner={**copy.deepcopy(INNER), "assertions": [{"name": "safe control", "ok": False}]})

    def test_zero_exit_with_mismatched_inner_identity_is_refused(self):
        self.assert_refused(inner={**copy.deepcopy(INNER), "scenario": "different-scenario", "mode": "watch"})

    def test_zero_exit_with_present_inner_error_key_is_refused(self):
        # launcher verdict is FAIL even for an explicit null error key.
        self.assert_refused(inner={**copy.deepcopy(INNER), "error": None})


if __name__ == "__main__":
    unittest.main(verbosity=2)
