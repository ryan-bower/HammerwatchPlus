"""Prelaunch baseline failures: fake discovery/files/locks/processes only."""
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


class LauncherPreflight(unittest.TestCase):
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

    def test_discovery_manifest_read_error_refuses_once_before_snapshots(self):
        manifest = self.root / "appmanifest.acf"
        manifest.write_text('"installdir" "Fake Game"')
        original = Path.read_text
        reads = []

        def read(path, *args, **kwargs):
            if path == manifest:
                reads.append(path)
                raise PermissionError("fake manifest denied")
            return original(path, *args, **kwargs)

        self.mocks["config"].side_effect = lambda: launcher.gamepaths.acf_value(manifest, "installdir")
        with patch.object(Path, "read_text", read):
            self.assert_preflight_refusal()
        self.assertEqual(reads, [manifest])
        self.mocks["resources"].assert_not_called()
        self.mocks["saves"].assert_not_called()

    def test_config_read_error_refuses_without_retry(self):
        original = Path.read_bytes
        reads = []

        def read(path):
            if path == self.config:
                reads.append(path)
                raise PermissionError("fake config denied")
            return original(path)

        with patch.object(Path, "read_bytes", read):
            self.assert_preflight_refusal()
        self.assertEqual(reads, [self.config])
        self.mocks["resources"].assert_not_called()

    def test_unavailable_config_metadata_does_not_masquerade_as_missing(self):
        original_file = Path.is_file
        original_read = Path.read_bytes

        def is_file(path):
            return False if path == self.config else original_file(path)

        def read(path):
            if path == self.config:
                raise PermissionError("fake metadata/read denial")
            return original_read(path)

        with patch.object(Path, "is_file", is_file), patch.object(Path, "read_bytes", read):
            self.assert_preflight_refusal()

    def test_config_directory_is_a_preflight_refusal(self):
        self.config.unlink()
        self.config.mkdir()
        self.assert_preflight_refusal()

    def test_missing_optional_config_still_has_an_explicit_absent_baseline(self):
        self.config.unlink()
        self.assertIsNone(launcher.sha(self.config))
        self.mocks["resources"].side_effect = PermissionError("fake resource denied")
        self.assert_preflight_refusal()

    def test_resource_baseline_read_error_still_refuses(self):
        self.mocks["resources"].side_effect = PermissionError("fake resource denied")
        self.assert_preflight_refusal()
        self.assertEqual(self.mocks["resources"].call_count, 1)

    def test_save_baseline_read_error_refuses_without_retry(self):
        self.mocks["saves"].side_effect = PermissionError("fake saves denied")
        self.assert_preflight_refusal()
        self.assertEqual(self.mocks["saves"].call_count, 1)

    def test_result_creation_error_refuses_without_dirty_teardown(self):
        original = Path.mkdir

        def mkdir(path, *args, **kwargs):
            if path.parent == self.results:
                raise PermissionError("fake result path denied")
            return original(path, *args, **kwargs)

        with patch.object(Path, "mkdir", mkdir):
            self.assert_preflight_refusal()

    def test_existing_result_directory_is_never_deleted_or_overwritten(self):
        previous = self.results / "fixed-s-lab"
        previous.mkdir(parents=True)
        sentinel = previous / "previous-result.json"
        sentinel.write_bytes(b"preserve previous evidence")
        with patch.object(launcher.time, "strftime", return_value="fixed"):
            self.assert_preflight_refusal()
        self.assertEqual(sentinel.read_bytes(), b"preserve previous evidence")

    def test_baseline_artifact_write_error_is_preflight_not_game_failure(self):
        original = Path.write_text

        def write(path, text, *args, **kwargs):
            if path.name == "isolation-res.json":
                raise PermissionError("fake baseline artifact denied")
            return original(path, text, *args, **kwargs)

        with patch.object(Path, "write_text", write):
            self.assert_preflight_refusal()

    def test_replaced_runtime_owner_is_preserved_and_refuses_cleanup(self):
        def discovery():
            self.held.write_text(json.dumps(self.foreign))
            raise PermissionError("fake discovery failure after ownership change")

        self.mocks["config"].side_effect = discovery
        self.assertEqual(self.run_case(), 4)
        self.assertEqual(json.loads(self.held.read_text()), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), self.previous)
        self.mocks["runner"].assert_not_called()
        self.mocks["kill"].assert_not_called()

    def test_foreign_lifecycle_guard_is_preserved_if_unused_lease_cannot_release(self):
        def discovery():
            self.guard.write_text(json.dumps(self.foreign))
            raise PermissionError("fake discovery failure during lifecycle contention")

        self.mocks["config"].side_effect = discovery
        self.assertEqual(self.run_case(), 4)
        self.assertTrue(self.held.exists())
        self.assertEqual(json.loads(self.guard.read_text()), self.foreign)
        self.assertEqual(self.teardown.read_bytes(), self.previous)
        self.mocks["runner"].assert_not_called()
        self.mocks["kill"].assert_not_called()

    def allow_fake_runner(self):
        self.mocks["sampler"].side_effect = None
        self.mocks["sampler"].return_value = NoSampler()

        def run(command, **kwargs):
            (Path(command[4]) / "inner.json").write_text(json.dumps({"partial": False, "assertions": []}))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        self.mocks["runner"].side_effect = run

    def test_postlaunch_save_read_error_is_not_reclassified_as_preflight(self):
        self.allow_fake_runner()
        self.mocks["saves"].side_effect = [{}, PermissionError("fake postlaunch save denial")]
        with self.assertRaises(PermissionError):
            self.run_case()
        self.assertEqual(self.mocks["runner"].call_count, 1)
        self.assertFalse(self.held.exists())
        self.assertFalse(json.loads(self.teardown.read_text())["clean"])

    def test_postlaunch_resource_read_error_remains_invalid(self):
        self.allow_fake_runner()
        self.mocks["resources"].side_effect = [{}, PermissionError("fake postlaunch resource denial")]
        with patch.dict(sys.modules, {"run_summary": Mock(write=Mock(return_value={}))}):
            self.assertEqual(self.run_case(), 5)
        self.assertEqual(self.mocks["runner"].call_count, 1)
        report = json.loads(next(self.results.glob("*/run.json")).read_text())
        self.assertEqual(report["verdict"], "INVALID")
        self.assertFalse(self.held.exists())


if __name__ == "__main__":
    unittest.main()
