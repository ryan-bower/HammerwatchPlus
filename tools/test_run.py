"""tools/run.py: the plan and the guards, without a game, a build or a launch.

    python -m unittest tools.test_run -q
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout, nullcontext
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402


class RunPlan(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(run, "runtime_lock", side_effect=lambda dry: nullcontext())
        patcher.start()
        self.addCleanup(patcher.stop)
        chooser = mock.patch.object(run, "choose_save", return_value=run.save_builder.Plan(starting_gold=0))
        chooser.start()
        self.addCleanup(chooser.stop)

    def test_release_packages_come_from_environments(self):
        packages = run.release_packages()
        self.assertEqual(packages, ["all"])
        self.assertEqual(run.mod_id("all"), "HammerwatchPlus-All")
        decl = json.loads(run.ENVIRONMENTS.read_text(encoding="utf-8"))["modded-prod"]
        self.assertEqual(packages, decl["packages"])

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
        # deploy.py decides about the HoH1 content (it packs every import there is)
        self.assertNotIn("--with-local", calls[0])

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

    def test_profile_is_prepared_before_launch_and_only_after_deploy(self):
        calls = []
        with mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run, "build_and_deploy", side_effect=lambda *a: calls.append("deploy") or 0), \
                mock.patch.object(run, "prepare_profile", side_effect=lambda *a: calls.append("profile") or 0), \
                mock.patch.object(run, "launch", side_effect=lambda *a: calls.append("launch") or 0):
            out = io.StringIO()
            with redirect_stdout(out):
                code = run.main(["--no-setup"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["deploy", "profile", "launch"])

    def test_failed_deploy_never_creates_a_profile_or_launches(self):
        with mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run, "build_and_deploy", return_value=3), \
                mock.patch.object(run, "prepare_profile") as profile, \
                mock.patch.object(run, "launch") as launch, redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(["--no-setup"]), 3)
        profile.assert_not_called()
        launch.assert_not_called()

    def test_failed_save_backup_never_creates_a_profile(self):
        with mock.patch.object(run.saves, "confirmation_problems", return_value=[]), \
                mock.patch.object(run.pin_build, "mismatch", return_value=[]), \
                mock.patch.object(run.saves, "backup", return_value=4), \
                mock.patch.object(run.play_profile, "create") as create:
            self.assertEqual(run.prepare_profile(Path("fake"), ["all"], False, None), 4)
        create.assert_not_called()

    def test_cancel_builder_never_runs_setup_or_deploy(self):
        with mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run, "choose_save", return_value=None), \
                mock.patch.object(run, "setup") as setup, \
                mock.patch.object(run, "build_and_deploy") as deploy, redirect_stdout(io.StringIO()):
            self.assertEqual(run.main([]), 0)
        setup.assert_not_called()
        deploy.assert_not_called()

    def test_native_preparation_failure_never_writes_real_profile(self):
        plan = run.save_builder.Plan(characters=[run.save_builder.Character("sorcerer", 15, "TestSorc")])
        with mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run, "choose_save", return_value=plan), \
                mock.patch.object(run, "build_and_deploy", return_value=0), \
                mock.patch.object(run.profile_seed, "generate", side_effect=RuntimeError("INVALID")), \
                mock.patch.object(run, "prepare_profile") as profile, redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(["--no-setup"]), 2)
        profile.assert_not_called()

    def test_gold_without_characters_still_uses_verified_native_preparation(self):
        plan = run.save_builder.Plan(starting_gold=1_000_000)
        with mock.patch.object(run, "game_running", return_value=False), \
                mock.patch.object(run.gamepaths, "hoh2_dir", return_value=Path("C:/fake/HoH2")), \
                mock.patch.object(run, "choose_save", return_value=plan), \
                mock.patch.object(run, "build_and_deploy", return_value=0), \
                mock.patch.object(run.profile_seed, "generate", return_value=(b"native", "seed-run")) as generate, \
                mock.patch.object(run, "prepare_profile", return_value=0) as profile, redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(["--no-setup", "--no-launch"]), 0)
        generate.assert_called_once_with(plan, ["all"])
        self.assertEqual(profile.call_args.args[4:], (b"native", "seed-run"))

    def test_deployed_ids_are_the_package_file_stems(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            mods = Path(d) / "mods"
            mods.mkdir()
            for n in ["HWP-core.bin", "HammerwatchPlus-All.bin", "other.bin"]:
                (mods / n).write_bytes(b"")
            self.assertEqual(run.deployed_ids(Path(d)), {"HWP-core", "HammerwatchPlus-All"})


class RuntimeGuard(unittest.TestCase):
    def test_held_lock_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            held = Path(temp) / "held.lock"
            held.write_text('{"pid": 123, "scenario": "someone-else"}')
            with mock.patch.object(run.lock, "LOCK", held):
                with self.assertRaisesRegex(RuntimeError, "runtime lock held"):
                    with run.runtime_lock(False):
                        self.fail("entered held runtime")
            self.assertEqual(held.read_text(), '{"pid": 123, "scenario": "someone-else"}')

    def test_dirty_teardown_is_preserved_and_own_lock_released(self):
        with tempfile.TemporaryDirectory() as temp:
            held = Path(temp) / "held.lock"
            teardown = Path(temp) / "teardown.json"
            teardown.write_text('{"clean": false, "run": "failed-run"}')
            with mock.patch.object(run.lock, "LOCK", held), mock.patch.object(run.lock, "TEARDOWN", teardown):
                with self.assertRaisesRegex(RuntimeError, "dirty"):
                    with run.runtime_lock(False):
                        self.fail("entered dirty runtime")
            self.assertFalse(held.exists())
            self.assertFalse(json.loads(teardown.read_text())["clean"])


if __name__ == "__main__":
    unittest.main()
