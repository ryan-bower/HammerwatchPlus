"""Mocked safety checks only: never start GameLab or the game."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_batch

REAL_FINGERPRINT = qa_batch.fingerprint


class BatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hwp-qa-batch-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.results = self.root / "gamelab" / "results"
        self.scenarios = self.root / "gamelab" / "scenarios"
        self.scenarios.mkdir(parents=True)
        for name in ("first", "second"):
            (self.scenarios / (name + ".json")).write_text(
                json.dumps({"name": name, "steps": [], "timeout": 123, "outer_timeout": 456}),
                encoding="utf-8")
        self.addCleanup(patch.stopall)
        patch.object(qa_batch, "ROOT", self.root).start()
        self.source = {"head": "head-a", "source_sha256": "source-a", "files": 3,
                       "fingerprint_scope": "mods+gamelab+tools-v2"}
        self.fingerprint = patch.object(qa_batch, "fingerprint", return_value=self.source).start()
        self.launch = patch.object(qa_batch.subprocess, "run", side_effect=self.launch_ok).start()
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

    def main(self, *arguments):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            return qa_batch.main(list(arguments))

    def launch_ok(self, argv, **kwargs):
        name = argv[4]
        directory = self.results / ("20000101-000000-" + name + "-lab")
        directory.mkdir()
        record = {"scenario": name, "mode": "lab", "environment": "gamelab", "verdict": "PASS",
                  "partial": False, "build_drift": False, "error": None,
                  "assertions": [{"name": "native check", "ok": True}], "teardown": {"clean": True}}
        (directory / "run.json").write_text(json.dumps(record), encoding="utf-8")
        (directory / "inner.json").write_text(json.dumps({"scenario": name, "mode": "lab", "partial": False}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)

    def rows(self, label="trial"):
        return [json.loads(line) for line in (self.results / ("qa-batch-" + label + ".jsonl")).read_text().splitlines()]

    def test_two_cases_are_serial_lab_with_launcher_timeout_ownership(self):
        self.assertEqual(self.main("--label", "trial", "first", "second"), 0)
        self.assertEqual(self.launch.call_count, 2)
        for name, call in zip(("first", "second"), self.launch.call_args_list):
            self.assertEqual(call.args[0], [sys.executable, "-m", "gamelab", "run", name, "--mode", "lab"])
            self.assertNotIn("timeout", call.kwargs)
            self.assertEqual(call.kwargs["cwd"], self.root)
        self.assertEqual([row["scenario"] for row in self.rows()], ["first", "second"])
        self.assertTrue(all(row["ok"] for row in self.rows()))
        self.assertEqual(self.fingerprint.call_count, 5)
        self.assertFalse((self.results / "qa-batch.lock").exists())

    def test_dry_run_and_fingerprint_write_nothing_and_launch_nothing(self):
        before = set(self.root.rglob("*"))
        self.assertEqual(self.main("--label", "dry", "--dry-run", "first", "second"), 0)
        self.assertEqual(set(self.root.rglob("*")), before)
        self.assertIn('"command":', self.stdout.getvalue())
        self.stdout.seek(0)
        self.stdout.truncate()
        self.assertEqual(self.main("--fingerprint"), 0)
        self.assertEqual(json.loads(self.stdout.getvalue()), self.source)
        self.assertEqual(set(self.root.rglob("*")), before)
        self.launch.assert_not_called()

    def test_entire_queue_validation_precedes_writes_or_launches(self):
        for name in ("../escape", "nested/name", r"nested\name", "first.json", "first*", "missing"):
            with self.subTest(name=name):
                self.assertEqual(self.main("--label", "trial", "first", name), 1)
                self.assertFalse(self.results.exists())
        self.fingerprint.assert_not_called()
        self.launch.assert_not_called()

    def test_bad_json_steps_and_timeout_refuse_before_launch(self):
        path = self.scenarios / "second.json"
        for contents in ("{", "[]", '{"steps":{}}', '{"steps":[],"timeout":false}',
                         '{"steps":[],"outer_timeout":-1}', '{"steps":[],"timeout":NaN}'):
            with self.subTest(contents=contents):
                path.write_text(contents, encoding="utf-8")
                self.assertEqual(self.main("--label", "trial", "first", "second"), 1)
                self.assertFalse(self.results.exists())
        self.launch.assert_not_called()

    def test_label_is_sanitized_and_journal_reuse_refused(self):
        self.assertEqual(self.main("--label", "../ night / trial", "first"), 0)
        journal = self.results / "qa-batch-night-trial.jsonl"
        original = journal.read_bytes()
        self.assertEqual(self.main("--label", "night-trial", "second"), 1)
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(self.launch.call_count, 1)

    def test_other_batch_lock_is_never_reset(self):
        self.results.mkdir()
        lock = self.results / "qa-batch.lock"
        lock.write_text("another owner", encoding="utf-8")
        self.assertEqual(self.main("--label", "trial", "first"), 1)
        self.assertEqual(lock.read_text(), "another owner")
        self.assertFalse((self.results / "qa-batch-trial.jsonl").exists())
        self.launch.assert_not_called()

    def test_stop_file_honored_between_cases_with_nonzero_incomplete_receipt(self):
        def launch_and_stop(*args, **kwargs):
            process = self.launch_ok(*args, **kwargs)
            (self.results / "qa-batch-trial.stop").touch()
            return process
        self.launch.side_effect = launch_and_stop
        self.assertEqual(self.main("--label", "trial", "first", "second"), 2)
        self.assertEqual(self.launch.call_count, 1)
        self.assertTrue(self.rows()[0]["ok"])
        self.assertEqual(self.rows()[1]["event"], "STOP_REQUESTED")
        self.assertEqual(self.rows()[1]["next"], "second")

    def test_preexisting_stop_never_launches(self):
        self.results.mkdir()
        (self.results / "qa-batch-trial.stop").touch()
        self.assertEqual(self.main("--label", "trial", "first"), 2)
        self.launch.assert_not_called()
        self.assertEqual(self.rows()[0]["completed"], 0)

    def test_every_nonzero_exit_stops_even_when_result_says_pass(self):
        for code in (1, 2, 3, 4, 5, 6, 99):
            with self.subTest(code=code):
                def fail(argv, **kwargs):
                    self.launch_ok(argv, **kwargs)
                    return subprocess.CompletedProcess(argv, code)
                self.launch.side_effect = fail
                self.launch.reset_mock()
                label = "exit" + str(code)
                # Each trial must make a fresh directory rather than reuse another trial's result.
                for directory in self.results.glob("*-first-lab"):
                    for path in directory.iterdir():
                        path.unlink()
                    directory.rmdir()
                self.assertEqual(self.main("--label", label, "first", "second"), 1)
                self.assertEqual(self.launch.call_count, 1)
                self.assertEqual(self.rows(label)[0]["exit"], code)
                self.assertFalse(self.rows(label)[0]["ok"])

    def test_unsafe_or_inconsistent_native_result_stops(self):
        mutations = ({"verdict": "FAIL"}, {"error": "native error"}, {"partial": True},
                     {"build_drift": True}, {"teardown": {"clean": False}},
                     {"assertions": [{"ok": False}]}, {"assertions": []},
                     {"scenario": "different"}, {"mode": "watch"}, {"environment": "install"})
        for index, change in enumerate(mutations):
            with self.subTest(change=change):
                def unsafe(argv, **kwargs):
                    result = self.launch_ok(argv, **kwargs)
                    path = next(self.results.glob("*-first-lab")) / "run.json"
                    record = json.loads(path.read_text())
                    record.update(change)
                    path.write_text(json.dumps(record), encoding="utf-8")
                    return result
                self.launch.side_effect = unsafe
                self.launch.reset_mock()
                for directory in self.results.glob("*-first-lab"):
                    for path in directory.iterdir():
                        path.unlink()
                    directory.rmdir()
                label = "unsafe" + str(index)
                self.assertEqual(self.main("--label", label, "first", "second"), 1)
                self.assertEqual(self.launch.call_count, 1)
                self.assertFalse(self.rows(label)[0]["ok"])

    def test_no_result_and_launch_error_are_journaled_without_reusing_old_result(self):
        self.results.mkdir()
        self.launch_ok(qa_batch.command("first"))  # Old PASS cannot satisfy this invocation.
        for label, effect in (("missing", lambda *a, **k: subprocess.CompletedProcess(a[0], 2)),
                              ("exception", OSError("launcher unavailable"))):
            with self.subTest(label=label):
                self.launch.side_effect = effect
                self.assertEqual(self.main("--label", label, "first", "second"), 1)
                row = self.rows(label)[0]
                self.assertEqual(row["verdict"], "NO_RESULT")
                self.assertIsNone(row["run_id"])
                self.assertIsNone(row["result"])
                self.assertTrue(row["problems"])

    def test_missing_partial_or_mismatched_inner_record_stops(self):
        for index, contents in enumerate((None, "{", '{"scenario":"first","mode":"lab","partial":true}',
                                           '{"scenario":"other","mode":"lab","partial":false}',
                                           '{"scenario":"first","mode":"lab"}',
                                           '{"scenario":"first","mode":"lab","partial":null}',
                                           '{"scenario":"first","mode":"lab","partial":0}')):
            with self.subTest(contents=contents):
                def bad_inner(argv, **kwargs):
                    result = self.launch_ok(argv, **kwargs)
                    path = next(self.results.glob("*-first-lab")) / "inner.json"
                    if contents is None:
                        path.unlink()
                    else:
                        path.write_text(contents, encoding="utf-8")
                    return result
                self.launch.side_effect = bad_inner
                for directory in self.results.glob("*-first-lab"):
                    for path in directory.iterdir():
                        path.unlink()
                    directory.rmdir()
                self.assertEqual(self.main("--label", "inner" + str(index), "first", "second"), 1)

    def test_source_drift_during_and_between_cases_never_re_pins(self):
        changed = copy.deepcopy(self.source)
        changed["head"] = "head-b"
        self.fingerprint.side_effect = [self.source, self.source, changed]
        self.assertEqual(self.main("--label", "during", "first", "second"), 1)
        self.assertEqual(self.launch.call_count, 1)
        self.assertIn("source drift", " ".join(self.rows("during")[0]["problems"]))
        self.fingerprint.side_effect = [self.source, self.source, self.source, changed, changed]
        self.launch.reset_mock()
        for path in (self.results / "20000101-000000-first-lab").iterdir():
            path.unlink()
        (self.results / "20000101-000000-first-lab").rmdir()
        self.assertEqual(self.main("--label", "between", "first", "second"), 1)
        self.assertEqual(self.launch.call_count, 1)
        self.assertIn("before launch", " ".join(self.rows("between")[1]["problems"]))


class FingerprintTests(unittest.TestCase):
    def test_head_paths_content_and_missing_sources_are_observable(self):
        with tempfile.TemporaryDirectory(prefix="hwp-qa-fingerprint-test-") as temporary:
            root = Path(temporary)
            (root / "mods").mkdir()
            source = root / "mods" / "source.as"
            source.write_bytes(b"original")
            listing = b"mods/source.as\0tools/missing.py\0"
            with patch.object(qa_batch, "ROOT", root), patch.object(
                    qa_batch.subprocess, "check_output", side_effect=[listing, "head-a"] * 3 + [listing, "head-b"]) as git:
                original = REAL_FINGERPRINT()
                source.write_bytes(b"changed")
                changed = REAL_FINGERPRINT()
                source.unlink()
                missing = REAL_FINGERPRINT()
                new_head = REAL_FINGERPRINT()
            self.assertEqual(original["files"], 2)
            self.assertNotEqual(original["source_sha256"], changed["source_sha256"])
            self.assertNotEqual(changed["source_sha256"], missing["source_sha256"])
            self.assertNotEqual(missing, new_head)
            self.assertEqual(missing["source_sha256"], new_head["source_sha256"])
            self.assertEqual(git.call_args_list[0].args[0], [
                "git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                "--", "mods", "gamelab", "tools"])


if __name__ == "__main__":
    unittest.main()
