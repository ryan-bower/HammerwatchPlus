"""tools/run.py: the plan and the guards, without a game, a build or a launch.

    python -m unittest tools.test_run -q
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402


class RunPlan(unittest.TestCase):
    def test_release_mods_come_from_environments(self):
        mods = run.release_mods()
        self.assertIn("core", mods)
        self.assertFalse(any(m.startswith("gamelab-") for m in mods))
        decl = json.loads(run.ENVIRONMENTS.read_text(encoding="utf-8"))["modded-prod"]
        self.assertEqual(mods, decl["mods"])

    def test_dry_run_plans_every_step_without_running_anything(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append([str(c) for c in cmd])
            return mock.Mock(returncode=0, stdout="", stderr="")

        out = io.StringIO()
        with mock.patch.object(run.subprocess, "run", fake_run), \
                mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run.os, "startfile", side_effect=AssertionError("launched"), create=True), \
                redirect_stdout(out):
            code = run.main(["--dry-run"])
        text = out.getvalue()
        self.assertEqual(code, 0, text)
        self.assertIn("run: setup: would run -m gamelab doctor --fix --no-smoke", text)
        self.assertIn("run: build:", text)
        self.assertIn("run: launch: would open steam://rungameid/619820", text)
        # the only subprocess a dry run starts is deploy.py's own --dry-run
        self.assertEqual(len(calls), 1, calls)
        self.assertIn("--dry-run", calls[0])
        self.assertIn("modded-prod", calls[0])
        self.assertEqual("--with-local" in calls[0], run.CAMPAIGN_MARKER.is_file())

    def test_refuses_while_the_game_runs(self):
        out = io.StringIO()
        with mock.patch.object(run, "game_running", return_value=True), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                redirect_stdout(out):
            code = run.main([])
        self.assertEqual(code, 3)
        self.assertIn("close Heroes of Hammerwatch II", out.getvalue())

    def test_setup_tolerates_only_the_hoh1_question(self):
        def doctor(cmd, **kw):
            return mock.Mock(returncode=2, stderr="",
                             stdout="  [NO] HoH1 install (optional) -- ASK THE USER\ndoctor: NOT ready: HoH1 install (optional)\n")

        with mock.patch.object(run.subprocess, "run", doctor), redirect_stdout(io.StringIO()):
            self.assertEqual(run.setup(False), (0, True))

        def doctor_bad(cmd, **kw):
            return mock.Mock(returncode=2, stderr="", stdout="doctor: NOT ready: Steam running, HoH1 install (optional)\n")

        with mock.patch.object(run.subprocess, "run", doctor_bad), redirect_stdout(io.StringIO()):
            self.assertEqual(run.setup(False)[0], 2)

    def test_new_modules_are_named_for_the_resource_mods_menu(self):
        with mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run, "deployed_ids", return_value={"core"}), \
                mock.patch.object(run, "build_and_deploy", return_value=0):
            out = io.StringIO()
            with redirect_stdout(out):
                code = run.main(["--no-setup", "--no-launch", "--mods", "core", "fishing"])
        self.assertEqual(code, 0)
        self.assertIn("HWP-fishing", out.getvalue())
        self.assertNotIn("HWP-core,", out.getvalue())


if __name__ == "__main__":
    unittest.main()
