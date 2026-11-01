"""Typed save validation at initial baseline; actual exception and fake paths only."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gamelab import launcher, lock


class NoSampler:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def report(self):
        return {"switches": [], "unexplained": [], "window_scans": 1,
                "game_windows_on_input_desktop": []}


class LauncherMetadataRefusals(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hwp-preflight-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.results = self.root / "results"
        self.held = self.root / "runtime.lock"
        self.guard = self.root / "runtime.lock.lifecycle"
        self.teardown = self.root / "teardown.json"
        self.previous = b'{"clean": true, "run": "previous-tested-source"}'
        self.teardown.write_bytes(self.previous)
        self.config = self.root / "HWR2.exe.cfg"
        self.config.write_bytes(b"private test config")
        self.scenario = self.root / "s.json"
        self.scenario.write_text('{"steps": [], "timeout": 1}')
        self.foreign = {"pid": 987654, "token": "b" * 32, "scenario": "foreign"}
        patches = {
            "repo": patch.object(launcher, "REPO", self.root),
            "results": patch.object(launcher, "RESULTS", self.results),
            "lock": patch.object(lock, "LOCK", self.held),
            "teardown": patch.object(lock, "TEARDOWN", self.teardown),
            "game": patch.object(lock.env, "GAME", self.game),
            "players": patch.object(lock, "player_processes", return_value=[]),
            "labs": patch.object(lock, "lab_processes", return_value=[]),
            "image": patch.object(lock, "process_image", return_value="C:/fake/python.exe"),
            "kill": patch.object(lock, "kill", side_effect=AssertionError("real cleanup forbidden")),
            "hoh1": patch.object(launcher, "hoh1_missing", return_value=[]),
            "mods": patch.object(launcher.env, "expand_mods", return_value=[]),
            "preflight": patch.object(launcher, "preflight", return_value=([], [])),
            "config": patch.object(launcher.gamepaths, "real_config", return_value=self.config),
            "resources": patch.object(launcher.env, "install_res_snapshot", return_value={}),
            "saves": patch.object(launcher.saves, "snapshot", return_value={}),
            "diff": patch.object(launcher.saves, "diff", return_value=[]),
            "sampler": patch.object(launcher.winproc, "ForegroundSampler", side_effect=AssertionError("sampling before a valid baseline")),
            "runner": patch.object(launcher.hidden_desktop, "run", side_effect=AssertionError("native launch forbidden")),
            "pinned": patch.object(launcher.pin_build, "pinned", return_value={}),
            "live": patch.object(launcher.pin_build, "live", return_value={}),
            "versions": patch.object(launcher, "mods_version", return_value={}),
            "restore": patch.object(launcher, "restore_written", return_value=[]),
        }
        self.actual_snapshot = launcher.saves.snapshot
        self.metadata_error = launcher.saves.MetadataError
        self.mocks = {key: p.start() for key, p in patches.items()}
        for p in patches.values():
            self.addCleanup(p.stop)

    def run_case(self):
        return launcher.run(str(self.scenario), "lab")

    def assert_preflight_refusal(self):
        self.assertEqual(self.run_case(), 2)
        self.assertFalse(self.held.exists())
        self.assertFalse(self.guard.exists())
        self.assertEqual(self.teardown.read_bytes(), self.previous)
        self.mocks["sampler"].assert_not_called()
        self.mocks["runner"].assert_not_called()
        self.mocks["kill"].assert_not_called()

    def test_actual_snapshot_stat_refusal_is_typed_and_abandoned_before_runner(self):
        import stat
        saves_root = self.root / "fake-user-saves"
        saves_root.mkdir()
        save = saves_root / "0.hps"
        save.write_bytes(b"preserve fake save")
        original_lstat = Path.lstat
        observations = []
        captured = []

        def lstat(path, *args, **kwargs):
            if path == saves_root:
                observations.append(path)
                raise PermissionError("fake late snapshot path refusal")
            if not path.is_relative_to(self.root):
                # _safe_join examines ancestors too; every ancestor snapshot
                # outside the fixture is fake rather than a real filesystem probe.
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0, st_nlink=1)
            return original_lstat(path, *args, **kwargs)

        def snapshot():
            try:
                return self.actual_snapshot()
            except self.metadata_error as error:
                captured.append(error)
                raise

        self.mocks["saves"].side_effect = snapshot
        with patch.object(launcher.saves.gamepaths, "real_save_dirs", return_value={"local": saves_root}), \
                patch.object(Path, "lstat", lstat):
            self.assert_preflight_refusal()
        self.assertEqual(observations, [saves_root])
        self.assertEqual(len(captured), 1)
        self.assertIs(type(captured[0]), launcher.saves.MetadataError)
        self.assertIsInstance(captured[0].__cause__, PermissionError)
        self.assertEqual(self.mocks["saves"].call_count, 1)
        self.assertEqual(save.read_bytes(), b"preserve fake save")

    def test_actual_metadata_validation_refusal_is_preflight_without_retry(self):
        self.mocks["saves"].side_effect = lambda: launcher.saves._relative("../unsafe.hps")
        self.assert_preflight_refusal()
        self.assertEqual(self.mocks["saves"].call_count, 1)

    def test_unrelated_value_error_is_not_swallowed_as_preflight(self):
        error = ValueError("unrelated snapshot programming failure")
        self.mocks["saves"].side_effect = error
        with self.assertRaises(ValueError) as caught:
            self.run_case()
        self.assertIs(caught.exception, error)
        self.assertIs(type(caught.exception), ValueError)
        self.assertFalse(self.held.exists())
        self.assertFalse(json.loads(self.teardown.read_text())["clean"])
        self.mocks["sampler"].assert_not_called()
        self.mocks["runner"].assert_not_called()
        self.mocks["kill"].assert_not_called()

    def allow_fake_runner(self):
        self.mocks["sampler"].side_effect = None
        self.mocks["sampler"].return_value = NoSampler()

        def run(command, **kwargs):
            (Path(command[4]) / "inner.json").write_text(json.dumps({"partial": False, "assertions": []}))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        self.mocks["runner"].side_effect = run

    def test_postlaunch_metadata_error_stays_nonpreflight_and_dirty(self):
        self.allow_fake_runner()
        error = self.metadata_error("fake postlaunch metadata refusal")
        self.mocks["saves"].side_effect = [{}, error]
        with self.assertRaises(self.metadata_error) as caught:
            self.run_case()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.mocks["runner"].call_count, 1)
        self.assertFalse(self.held.exists())
        self.assertFalse(json.loads(self.teardown.read_text())["clean"])
        self.mocks["kill"].assert_not_called()

    def test_metadata_refusal_preserves_replacement_runtime_owner(self):
        def snapshot():
            self.held.write_text(json.dumps(self.foreign))
            raise self.metadata_error("fake refusal after ownership changed")

        self.mocks["saves"].side_effect = snapshot
        self.assertEqual(self.run_case(), 4)
        self.assertEqual(json.loads(self.held.read_text()), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), self.previous)
        self.mocks["sampler"].assert_not_called()
        self.mocks["runner"].assert_not_called()
        self.mocks["kill"].assert_not_called()

    def test_metadata_refusal_preserves_foreign_lifecycle_fence(self):
        def snapshot():
            self.guard.write_text(json.dumps(self.foreign))
            raise self.metadata_error("fake refusal during lifecycle contention")

        self.mocks["saves"].side_effect = snapshot
        self.assertEqual(self.run_case(), 4)
        self.assertTrue(self.held.exists())
        self.assertEqual(json.loads(self.guard.read_text()), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), self.previous)
        self.mocks["sampler"].assert_not_called()
        self.mocks["runner"].assert_not_called()
        self.mocks["kill"].assert_not_called()

    def test_partial_preflight_evidence_is_retained_without_native_records(self):
        observed = []

        def snapshot():
            directory = next(self.results.glob("*-s-lab"))
            evidence = directory / "preflight-observation.txt"
            evidence.write_bytes(b"fake preflight observation only")
            observed.append(evidence)
            raise self.metadata_error("fake refusal after partial observation")

        self.mocks["saves"].side_effect = snapshot
        self.assert_preflight_refusal()
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].read_bytes(), b"fake preflight observation only")
        self.assertFalse((observed[0].parent / "run.json").exists())
        self.assertFalse((observed[0].parent / "inner.json").exists())


if __name__ == "__main__":
    unittest.main()
