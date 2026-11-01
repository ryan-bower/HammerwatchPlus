"""Materialization must fail closed before another pass or trusted cache publication."""
import hashlib
import json
import stat
import struct
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gamelab import runner
from gamelab.tests.test_runner_restart import FakeGame

META = ".gamelab-fixture.json"


def profile(number):
    body = b"H2SV\x03\x00\x00\x00" + struct.pack("<Q", number) + b"synthetic profile"
    return body + hashlib.md5(body).digest()[:4]


class MaterializeGame(FakeGame):
    def __init__(self, case, number):
        super().__init__("town")
        self.case, self.number = case, number
        self.game_dir = case.game_dir
        self.log_path = case.root / f"native-pass{number}.log"
        self.log_path.write_text(f"synthetic pass {number}\n", encoding="utf-8")
        self.inbox_sent = self.inbox_resends = self.console_typed = 0
        self.transport = "inbox"
        self.closed = False

    def stop(self):
        (self.game_dir / "saves/0.hps").write_bytes(profile(self.number))
        return self.case.exits[self.number - 1]

    def close(self):
        self.closed = True

    def gl_cmd(self, verb, *args):
        self.commands.append((verb, *args))
        if verb == "setup":
            if self.case.setup_assertion:
                self.case.run.assert_("fixture setup acknowledgement", False, "synthetic failed readback")
            return {"ok": self.case.setup_ok}
        if verb in ("char", "save"):
            return {"ok": True}
        return super().gl_cmd(verb, *args)


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fixture-trust-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game_dir = self.root / "lab"
        (self.game_dir / "saves").mkdir(parents=True)
        (self.game_dir / "saves/0.hps").write_bytes(profile(99))
        self.results = self.root / "result"
        self.results.mkdir()
        self.caches = self.root / "cache"
        self.caches.mkdir()
        self.recipe = {"name": "control", "slot": 0, "binary_edits": {"enable_mods": []},
                       "character": {"class": "paladin", "name": "Fixture"}}
        self.identity = hashlib.sha256(json.dumps(self.recipe, sort_keys=True).encode()).hexdigest()
        self.cache = self.caches / f"control.fake-build.v2.{self.identity[:8]}"
        self.legacy = self.caches / f"control.fake-build.{self.identity[:8]}"
        self.exits = [0, 0]
        self.bad_console = set()
        self.setup_ok, self.setup_assertion = True, False
        self.addCleanup(patch.stopall)
        patch.object(runner, "REPO", self.root).start()
        patch.object(runner, "CACHE", self.caches).start()
        patch.object(runner, "FIXTURES", self.root / "fixtures").start()
        patch.object(runner.env, "GAME", self.game_dir).start()
        patch.object(runner.pin_build, "live", return_value={"build_id": "fake-build"}).start()
        self.enable = patch.object(runner.hps, "enable").start()
        patch.object(runner.Game, "start", side_effect=AssertionError("No native game is authorized")).start()
        patch.object(subprocess, "Popen", side_effect=AssertionError("No process is authorized")).start()
        patch.object(subprocess, "run", side_effect=AssertionError("No child command is authorized")).start()
        self.run = self.new_run()

    def new_run(self):
        run = runner.Run({}, self.results, "lab")

        def boot(expect_mods):
            run.passes += 1
            (self.game_dir / "saves").mkdir(exist_ok=True)
            (self.game_dir / "saves/0.hps").write_bytes(profile(run.passes))
            game = MaterializeGame(self, run.passes)
            run.game = game
            return game

        original_console = run.check_console

        def console(game):
            if game.number in self.bad_console:
                run.assert_(f"pass {game.number}: nothing typed into the game console in session", False, "synthetic line")
            else:
                original_console(game)

        run.boot = Mock(side_effect=boot)
        run.check_console = console
        return run

    @staticmethod
    def files(root):
        return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    def seed_cache(self):
        self.cache.mkdir(exist_ok=True)
        data = profile(2)
        (self.cache / "0.hps").write_bytes(data)
        value = {"version": 2, "cache_key": self.cache.name, "input_sha256": self.identity,
                 "creator_run": "clean-unit-fixture", "clean_passes": [1, 2],
                 "files": {"0.hps": hashlib.sha256(data).hexdigest()}}
        (self.cache / META).write_text(json.dumps(value), encoding="utf-8")
        return value

    def test_finish_returns_true_only_for_clean_exit_and_assertions(self):
        for code, console, wanted in ((0, False, True), (3221225477, False, False), (None, False, False), (0, True, False)):
            with self.subTest(code=code, bad_console=console):
                self.exits[0] = code
                self.bad_console = {1} if console else set()
                self.run = self.new_run()
                game = self.run.boot(False)
                self.assertIs(self.run.finish(game), wanted)
                self.assertTrue(game.closed)
                self.assertIsNone(self.run.game)
                self.assertTrue((self.results / "logs/pass1.HWR2.exe.log").is_file())

    def test_pass1_failure_stops_before_enable_next_boot_and_cache(self):
        for code, console in ((3221225477, False), (None, False), (0, True)):
            with self.subTest(code=code, bad_console=console):
                self.exits = [code, 0]
                self.bad_console = {1} if console else set()
                self.run = self.new_run()
                self.enable.reset_mock()
                with self.assertRaises(runner.GameError):
                    self.run.materialize(self.recipe)
                self.assertEqual(self.run.boot.call_count, 1)
                self.enable.assert_not_called()
                self.assertFalse(self.cache.exists())
                self.assertFalse(self.legacy.exists())
                self.assertTrue(any(a["ok"] is False for a in self.run.assertions))
                self.assertTrue((self.results / "logs/pass1.HWR2.exe.log").is_file())

    def test_pass2_failure_cannot_publish_cache(self):
        for code, console in ((3221225477, False), (None, False), (0, True)):
            with self.subTest(code=code, bad_console=console):
                self.exits = [0, code]
                self.bad_console = {2} if console else set()
                self.run = self.new_run()
                with self.assertRaises(runner.GameError):
                    self.run.materialize(self.recipe)
                self.assertEqual(self.run.boot.call_count, 2)
                self.assertFalse(self.cache.exists())
                self.assertFalse(self.legacy.exists())

    def test_setup_reply_or_recorded_assertion_failure_cannot_publish(self):
        for reply, recorded in ((False, False), (True, True)):
            with self.subTest(reply_ok=reply, recorded_failure=recorded):
                self.setup_ok, self.setup_assertion = reply, recorded
                self.run = self.new_run()
                recipe = {**self.recipe, "setup": [{"verb": "setup", "expect": {"ok": True}}]}
                with self.assertRaises(runner.GameError):
                    self.run.materialize(recipe)
                self.assertEqual(list(self.caches.iterdir()), [])

    def test_clean_preparation_publishes_attested_bytes_then_cache_hit(self):
        self.caches.rmdir()  # Genuine absent parent is allowed, unlike inaccessible/reparse.
        info = self.run.materialize(self.recipe)
        self.assertEqual(info["cache"], "miss")
        self.assertEqual(info["cache_key"], self.cache.name)
        self.assertTrue((self.cache / META).is_file())
        value = json.loads((self.cache / META).read_text())
        self.assertEqual(value["clean_passes"], [1, 2])
        self.assertEqual(value["input_sha256"], self.identity)
        self.assertEqual(value["files"], {"0.hps": hashlib.sha256(profile(2)).hexdigest()})
        expected = {"0.hps": profile(2)}
        self.run = self.new_run()
        self.enable.reset_mock()
        self.assertEqual(self.run.materialize(self.recipe)["cache"], "hit")
        self.run.boot.assert_not_called()
        self.enable.assert_not_called()
        self.assertEqual(self.files(self.game_dir / "saves"), expected)

    def test_legacy_namespace_is_preserved_and_never_silently_reused(self):
        self.legacy.mkdir()
        (self.legacy / "0.hps").write_bytes(profile(77))
        before = self.files(self.legacy)
        self.assertEqual(self.run.materialize(self.recipe)["cache"], "miss")
        self.assertEqual(self.run.boot.call_count, 2)
        self.assertEqual(self.files(self.legacy), before)
        self.assertTrue((self.cache / META).is_file())

    def test_bad_current_cache_refuses_before_boot_or_current_save_mutation(self):
        for fault in ("missing-meta", "bad-json", "version", "identity", "pass", "tamper", "extra", "pending"):
            with self.subTest(fault=fault):
                if self.cache.exists():
                    runner.shutil.rmtree(self.cache)
                value = self.seed_cache()
                if fault == "missing-meta":
                    (self.cache / META).unlink()
                elif fault == "bad-json":
                    (self.cache / META).write_text("{", encoding="utf-8")
                elif fault in ("version", "identity", "pass"):
                    key = {"version": "version", "identity": "input_sha256", "pass": "clean_passes"}[fault]
                    value[key] = {"version": 1, "identity": "0" * 64, "pass": [1, False]}[fault]
                    (self.cache / META).write_text(json.dumps(value), encoding="utf-8")
                elif fault == "tamper":
                    (self.cache / "0.hps").write_bytes(profile(88))
                elif fault == "extra":
                    (self.cache / "1.hps").write_bytes(profile(88))
                else:
                    (self.cache / (META + ".tmp")).write_text("interrupted", encoding="utf-8")
                before_saves, before_cache = self.files(self.game_dir / "saves"), self.files(self.cache)
                self.run = self.new_run()
                with self.assertRaises(runner.GameError):
                    self.run.materialize(self.recipe)
                self.run.boot.assert_not_called()
                self.assertEqual(self.files(self.game_dir / "saves"), before_saves)
                self.assertEqual(self.files(self.cache), before_cache)

    def test_copy_corruption_leaves_unattested_cache_and_no_reuse(self):
        original = runner.shutil.copytree
        reached = []

        def corrupt(source, destination, *args, **kwargs):
            result = original(source, destination, *args, **kwargs)
            if Path(destination) == self.cache:
                reached.append(True)
                (self.cache / "0.hps").write_bytes(profile(88))
            return result

        with patch.object(runner.shutil, "copytree", corrupt), self.assertRaises(runner.GameError):
            self.run.materialize(self.recipe)
        self.assertTrue(reached)
        self.assertFalse((self.cache / META).exists())
        before = self.files(self.cache)
        self.run = self.new_run()
        with self.assertRaises(runner.GameError):
            self.run.materialize(self.recipe)
        self.run.boot.assert_not_called()
        self.assertEqual(self.files(self.cache), before)

    def test_silent_metadata_write_corruption_never_commits_provenance(self):
        original = Path.write_text
        reached = []

        def corrupt(path, data, *args, **kwargs):
            if path == self.cache / (META + ".tmp"):
                reached.append(True)
                data = "{"
            return original(path, data, *args, **kwargs)

        with patch.object(Path, "write_text", corrupt), self.assertRaises(runner.GameError):
            self.run.materialize(self.recipe)
        self.assertTrue(reached)
        self.assertFalse((self.cache / META).exists())

    def test_cache_restore_copy_corruption_refuses_without_boot(self):
        self.seed_cache()
        original = runner.shutil.copytree
        reached = []

        def corrupt(source, destination, *args, **kwargs):
            result = original(source, destination, *args, **kwargs)
            if Path(destination) == self.game_dir / "saves":
                reached.append(True)
                (Path(destination) / "0.hps").write_bytes(profile(88))
            return result

        with patch.object(runner.shutil, "copytree", corrupt), self.assertRaises(runner.GameError):
            self.run.materialize(self.recipe)
        self.assertTrue(reached)
        self.run.boot.assert_not_called()

    def test_reparse_cache_root_or_leaf_refuses_from_lstat_contract(self):
        self.seed_cache()
        original = Path.lstat
        for target in (self.cache, self.cache / "0.hps", self.cache / META):
            with self.subTest(target=target):
                def reparse(path, *args, **kwargs):
                    if path == target:
                        return types.SimpleNamespace(st_mode=stat.S_IFDIR if path == self.cache else stat.S_IFREG,
                                                     st_file_attributes=0x400)
                    return original(path, *args, **kwargs)

                self.run = self.new_run()
                with patch.object(Path, "lstat", reparse), self.assertRaises(runner.GameError):
                    self.run.materialize(self.recipe)
                self.run.boot.assert_not_called()

    def test_dangling_reparse_dispatch_refuses_before_any_mutation(self):
        original_exists, original_link, original_stat = Path.exists, Path.is_symlink, Path.lstat
        for target in (self.cache, self.caches):
            with self.subTest(target=target):
                if self.cache.exists():
                    runner.shutil.rmtree(self.cache)
                if target == self.cache:
                    self.seed_cache()
                before_saves, before_cache = self.files(self.game_dir / "saves"), self.files(self.caches)
                reached = []

                def exists(path, *args, **kwargs):
                    return False if path == target else original_exists(path, *args, **kwargs)

                def is_link(path, *args, **kwargs):
                    return False if path == target else original_link(path, *args, **kwargs)

                def reparse(path, *args, **kwargs):
                    if path == target:
                        reached.append(True)
                        return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                    return original_stat(path, *args, **kwargs)

                self.run = self.new_run()
                self.enable.reset_mock()
                with patch.object(Path, "exists", exists), patch.object(Path, "is_symlink", is_link), \
                        patch.object(Path, "lstat", reparse), self.assertRaises(runner.GameError):
                    self.run.materialize(self.recipe)
                self.assertTrue(reached, "The no-follow preflight must inspect the masked reparse path")
                self.run.boot.assert_not_called()
                self.enable.assert_not_called()
                self.assertEqual(self.files(self.game_dir / "saves"), before_saves)
                self.assertEqual(self.files(self.caches), before_cache)

    def test_inaccessible_cache_or_parent_refuses_before_any_mutation(self):
        original_exists, original_link, original_stat = Path.exists, Path.is_symlink, Path.lstat
        for target in (self.cache, self.caches):
            with self.subTest(target=target):
                if self.cache.exists():
                    runner.shutil.rmtree(self.cache)
                if target == self.cache:
                    self.seed_cache()
                before_saves, before_cache = self.files(self.game_dir / "saves"), self.files(self.caches)
                reached = []

                def exists(path, *args, **kwargs):
                    return False if path == target else original_exists(path, *args, **kwargs)

                def is_link(path, *args, **kwargs):
                    return False if path == target else original_link(path, *args, **kwargs)

                def inaccessible(path, *args, **kwargs):
                    if path == target:
                        reached.append(True)
                        raise PermissionError("synthetic lstat denial")
                    return original_stat(path, *args, **kwargs)

                self.run = self.new_run()
                self.enable.reset_mock()
                with patch.object(Path, "exists", exists), patch.object(Path, "is_symlink", is_link), \
                        patch.object(Path, "lstat", inaccessible), self.assertRaises(runner.GameError):
                    self.run.materialize(self.recipe)
                self.assertTrue(reached, "Access denial must not be treated as an absent cache")
                self.run.boot.assert_not_called()
                self.enable.assert_not_called()
                self.assertEqual(self.files(self.game_dir / "saves"), before_saves)
                self.assertEqual(self.files(self.caches), before_cache)


if __name__ == "__main__":
    unittest.main()
