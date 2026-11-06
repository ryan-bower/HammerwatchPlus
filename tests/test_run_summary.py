"""CLI/import fake-artifact checks only; never import GameLab runtime modules."""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/run_summary.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("selected_run_summary", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report_block():
    tree = ast.parse((ROOT / "gamelab/launcher.py").read_text(encoding="utf-8"))
    block = next(node for node in ast.walk(tree) if isinstance(node, ast.Try)
                 and any(isinstance(child, ast.Import) and any(item.name == "run_summary" for item in child.names)
                         for child in ast.walk(node)))
    function = ast.FunctionDef(name="report", args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="results")],
        kwonlyargs=[], kw_defaults=[], defaults=[]), body=[block], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {"sys": sys, "REPO": ROOT}
    exec(compile(module, "actual_launcher_optional_report", "exec"), namespace)
    return namespace["report"], block


class RunSummaryTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get("HWP_RUN_SUMMARY_TEST_TMP", str(ROOT / "gamelab/results/run-summary-tests")))
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="run-summary-", dir=scratch)
        self.addCleanup(temp.cleanup)
        self.run = Path(temp.name) / "fake-completed-run"
        self.run.mkdir()
        (self.run / "logs").mkdir()
        self.record = dict(scenario="fake", mode="lab", environment="gamelab", verdict="PASS", seconds=12,
            error=None, partial=False, build_drift=False, assertions=[dict(name="fake assertion", ok=True)],
            teardown=dict(clean=True), build=dict(build_id="fake", exe_sha256="a"*64))
        (self.run / "run.json").write_text(json.dumps(self.record))
        (self.run / "inner.json").write_text(json.dumps(dict(scenario="fake", mode="lab", partial=False,
                                                           assertions=self.record["assertions"])))
        self.events = [
            dict(ev="boot", level="town", _t=0, _lvl=1, _place="town/main"),
            dict(ev="hb", phase="town", _t=1, _lvl=1, _place="town/main"),
            dict(ev="boot", level="keep", _t=2, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="hit", landed=True, dmg=10, kind="physical", src="fake-source", _t=3, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="hit", landed=False, dmg=2.5, kind="fire", src="fake-source", _t=4, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="loot_visit", id="visit1", unit=42, type="item", name="fake item", result="picked", ms=100, _t=5, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="loot_visit", id="visit1", unit=42, type="item", name="fake item", result="picked", ms=150, _t=6, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="loot_pick", outcome="picked", type="item", rej=dict(full=1), carpetChecks=4, _t=7, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="harness.stall", s=8, after="frame continued", _t=8, _lvl=2, _place="bandit_keep/keep_1"),
            dict(ev="pilot", intent="loot", result="done", id="loop1", ms=120, gains=["fake gold"], _t=12, _lvl=2, _place="bandit_keep/keep_1"),
        ]
        self.write_events()

    def write_events(self):
        (self.run / "gl.jsonl").write_text("".join(json.dumps(row) + "\n" for row in self.events))

    def primary(self):
        return {name: (self.run / name).read_bytes() for name in ("run.json", "inner.json", "gl.jsonl") if (self.run / name).exists()}

    def cli(self, *arguments):
        return subprocess.run([sys.executable, "-B", str(TOOL), *map(str, arguments)], cwd=ROOT,
                              capture_output=True, text=True, timeout=10)

    def test_cli_help_is_a_real_entrypoint_and_writes_nothing(self):
        before = self.primary()
        done = self.cli("--help")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("--print", done.stdout)
        self.assertEqual(self.primary(), before)
        self.assertFalse((self.run / "summary.json").exists())

    def test_actual_launcher_reporting_import_writes_reports_without_touching_verdict(self):
        before = self.primary()
        function, block = report_block()
        self.assertTrue(any(isinstance(handler.type, ast.Name) and handler.type.id == "Exception" for handler in block.handlers))
        old_path = list(sys.path)
        output = io.StringIO()
        try:
            with patch.dict(sys.modules), contextlib.redirect_stdout(output):
                sys.modules.pop("run_summary", None)
                function(self.run)
        finally:
            sys.path[:] = old_path
        self.assertNotIn("summary failed:", output.getvalue())
        self.assertIn("stalled frames: 8", output.getvalue())
        self.assertEqual(json.loads((self.run / "summary.json").read_text())["verdict"], "PASS")
        self.assertEqual(self.primary(), before)

    def test_cli_prints_markdown_and_creates_only_explicit_run_outputs(self):
        before = self.primary()
        done = self.cli(self.run, "--print")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("# fake-completed-run", done.stdout)
        self.assertIn("verdict **PASS**", done.stdout)
        self.assertEqual(done.stdout, (self.run / "summary.md").read_text())
        self.assertEqual(self.primary(), before)
        self.assertEqual(set(p.name for p in self.run.iterdir()), {"run.json", "inner.json", "gl.jsonl", "logs", "summary.json", "summary.md"})

    def test_current_event_schema_metrics_and_repeated_writes_are_consistent(self):
        helper = load_helper()
        before = self.primary()
        result = helper.write(self.run)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["stall_s"], 8)
        self.assertFalse(result["stalls_rebuilt"])
        self.assertEqual([row["place"] for row in result["places"]], ["town/main", "bandit_keep/keep_1"])
        place = result["places"][1]
        self.assertEqual((place["wall_s"], place["hits"], place["landed"], place["dmg"]), (10, 2, 1, 12.5))
        self.assertEqual(place["loot_ms_max"], 150)
        self.assertEqual(place["visits"], {"item picked": 2})
        self.assertEqual(place["units"], [[42, 2, "item fake item"]])
        first = {name: (self.run/name).read_bytes() for name in ("summary.json", "summary.md")}
        helper.write(self.run)
        self.assertEqual({name: (self.run/name).read_bytes() for name in first}, first)
        self.assertEqual(self.primary(), before)

    def test_malformed_json_line_is_visible_as_anomaly(self):
        with (self.run / "gl.jsonl").open("a") as stream:
            stream.write("{not-json\n")
        before = self.primary()
        result = load_helper().write(self.run)
        self.assertEqual(result["anomalies"]["bad_json_line"], 1)
        self.assertIn("bad_json_line", (self.run / "summary.md").read_text())
        self.assertEqual(self.primary(), before)

    def test_legacy_midnight_stall_reconstruction_has_explicit_provenance(self):
        self.events = [row for row in self.events if row["ev"] != "harness.stall"]
        self.write_events()
        (self.run / "logs/pass1.HWR2.exe.log").write_text(
            '[NFO] [23:59:58] [GL] {"ev":"hb","phase":"town"}\n'
            '[NFO] [00:00:05] [GL] {"ev":"hb","phase":"town"}\n')
        result = load_helper().write(self.run)
        self.assertEqual(result["stall_s"], 7)
        self.assertTrue(result["stalls_rebuilt"])

    def test_hardlinked_derived_leaves_never_truncate_primary_artifacts(self):
        helper = load_helper()
        os.link(self.run / "run.json", self.run / "summary.json")
        os.link(self.run / "gl.jsonl", self.run / "summary.md")
        self.assertTrue(os.path.samefile(self.run / "run.json", self.run / "summary.json"))
        self.assertTrue(os.path.samefile(self.run / "gl.jsonl", self.run / "summary.md"))
        before = self.primary()
        helper.write(self.run)
        self.assertEqual(self.primary(), before)
        self.assertFalse(os.path.samefile(self.run / "run.json", self.run / "summary.json"))
        self.assertFalse(os.path.samefile(self.run / "gl.jsonl", self.run / "summary.md"))
        self.assertEqual(json.loads((self.run / "summary.json").read_text())["verdict"], "PASS")
        self.assertIn("# fake-completed-run", (self.run / "summary.md").read_text())

    def test_replace_refusal_keeps_existing_outputs_and_removes_only_owned_temps(self):
        helper = load_helper()
        (self.run / "summary.json").write_text("old json report")
        (self.run / "summary.md").write_text("old markdown report")
        before = {path.name: path.read_bytes() for path in self.run.iterdir() if path.is_file()}
        with patch.object(helper.os, "replace", side_effect=OSError("fake replace refusal")):
            with self.assertRaisesRegex(OSError, "fake replace refusal"):
                helper.write(self.run)
        self.assertEqual({path.name: path.read_bytes() for path in self.run.iterdir() if path.is_file()}, before)
        self.assertFalse(list(self.run.glob(".summary.*.tmp")))

    def test_second_replace_refusal_preserves_primaries_without_pair_atomicity_claim(self):
        helper = load_helper()
        os.link(self.run / "run.json", self.run / "summary.json")
        os.link(self.run / "gl.jsonl", self.run / "summary.md")
        before = self.primary()
        real_replace, calls = helper.os.replace, []
        def replace_once(source, destination):
            calls.append(Path(destination).name)
            if len(calls) == 2:
                raise OSError("fake second replace refusal")
            return real_replace(source, destination)
        with patch.object(helper.os, "replace", side_effect=replace_once):
            with self.assertRaisesRegex(OSError, "fake second replace refusal"):
                helper.write(self.run)
        self.assertEqual(calls, ["summary.json", "summary.md"])
        self.assertEqual(self.primary(), before)
        self.assertEqual(json.loads((self.run / "summary.json").read_text())["verdict"], "PASS")
        self.assertTrue(os.path.samefile(self.run / "gl.jsonl", self.run / "summary.md"))
        self.assertFalse(list(self.run.glob(".summary.*.tmp")))

    def test_missing_telemetry_cli_failure_preserves_primary_verdict(self):
        (self.run / "gl.jsonl").unlink()
        before = self.primary()
        done = self.cli(self.run)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("gl.jsonl", done.stderr)
        self.assertFalse((self.run / "summary.json").exists())
        self.assertFalse((self.run / "summary.md").exists())
        self.assertEqual(self.primary(), before)
        self.assertEqual(json.loads((self.run / "run.json").read_text())["verdict"], "PASS")

    def test_optional_writer_error_remains_non_gating(self):
        function, _ = report_block()
        before = self.primary()
        output = io.StringIO()
        old_path = list(sys.path)
        try:
            with patch.dict(sys.modules, {"run_summary": Mock(write=Mock(side_effect=OSError("fake report error")))}), contextlib.redirect_stdout(output):
                function(self.run)
        finally:
            sys.path[:] = old_path
        self.assertIn("summary failed: OSError: fake report error", output.getvalue())
        self.assertEqual(self.primary(), before)


if __name__ == "__main__":
    unittest.main()
