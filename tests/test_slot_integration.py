"""Slot consumer boundaries using temporary trees and fake process identities only.

These tests exercise the public runtime protocol together with the launcher,
session, lock and runner consumers. They never launch/query/kill a real process,
touch an installed game, or write the shared PlanData/fixture cache.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import gamelab
from gamelab import env, launcher, lock, runner, runtime, session


class SlotIntegration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hwp-slot-integration-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.processes = {os.getpid(): (101, str(self.repo / "python.exe"))}
        environment = patch.dict(os.environ, dict(os.environ), clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        for key in runtime.ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["GAMELAB_SIM_BLUR"] = "0"
        os.environ["GAMELAB_TRANSPORT"] = "inbox"
        for p in (
            patch.object(runtime, "WORKERS", self.repo / "workers"),
            patch.object(runtime, "RESULTS", self.repo / "results"),
            patch.object(runtime, "MACHINE_LOCK", self.repo / "machine.lock"),
            patch.object(runtime, "process_info", side_effect=self.processes.get),
            patch.object(runtime.os, "cpu_count", return_value=8),
        ):
            p.start()
            self.addCleanup(p.stop)
        lease = {"pid": os.getpid(), "token": "a" * 32}
        runtime.MACHINE_LOCK.write_text(json.dumps(lease), encoding="utf-8")
        source = {"head": "0" * 40, "fingerprint_scope": "mods+gamelab+tools-v2",
                  "source_sha256": "1" * 64, "files": 7}
        self.pool = runtime.create_pool(runtime.WORKERS / "integration", lease, source)
        self.contexts = [runtime.current(runtime.child_env(self.pool, i)) for i in (0, 1)]
        for ctx in self.contexts:
            (ctx.game_dir.parent / "gamelab.lock").write_text(
                json.dumps({"pid": os.getpid(), "token": ctx.slot["token"]}), encoding="utf-8")
        self.one, self.two = self.contexts
        self.settings = self.repo / "settings"
        (self.settings / "lab").mkdir(parents=True)
        self.profile = self.settings / "lab/HWR2.exe.cfg"
        self.profile.write_text("snd_volume 0\ng_save_slot_cloud 0\n", encoding="utf-8")

    @contextmanager
    def active(self, index=0):
        with patch.dict(os.environ, runtime.child_env(self.pool, index)):
            yield runtime.current()

    @contextmanager
    def preflight_fakes(self, ctx):
        with patch.object(env, "GAME", ctx.game_dir), \
                patch.object(env, "SETTINGS", self.settings), \
                patch.object(env, "environments", return_value={"gamelab": {
                    "user_data": str(self.repo / "legacy-userdata")}}), \
                patch.object(launcher.saves, "confirmation_problems", return_value=[]) as confirmed, \
                patch.object(launcher.saves, "backup", return_value=0) as backup, \
                patch.object(launcher.pin_build, "mismatch", return_value=[]) as build, \
                patch.object(env, "link", return_value=[]) as link:
            yield confirmed, backup, build, link

    def registered(self, index, pid, creation):
        ctx = self.contexts[index]
        self.processes[pid] = (creation, str(ctx.game_dir / "HWR2.exe"))
        with self.active(index):
            runtime.register_game(pid)
        return ctx.game_dir / "HWR2.exe"

    def game(self, ctx, pid=21001):
        ctx.results.mkdir(parents=True, exist_ok=True)
        with patch.object(env, "GAME", ctx.game_dir):
            game = session.Game(ctx.results, "lab")
        self.addCleanup(game.close)
        game.note = Mock()
        game.shim_log = Mock(return_value="SHGetKnownFolderPath hooked; SwapBuffers hooked")
        proc = Mock(pid=pid, _handle=7)
        proc.poll.return_value = None
        proc.wait.return_value = 1
        self.processes[pid] = (201, str(ctx.game_dir / "HWR2.exe"))
        proc.kill.side_effect = lambda: self.processes.pop(pid, None)
        return game, proc

    @contextmanager
    def source_copy(self, original):
        """Load process-local import constants without reloading shared modules."""
        name = "_slot_integration_" + original.__name__.replace(".", "_")
        spec = importlib.util.spec_from_file_location(name, original.__file__)
        module = importlib.util.module_from_spec(spec)
        before_path = sys.path[:]
        try:
            with patch.dict(sys.modules, {name: module}):
                spec.loader.exec_module(module)
                yield module
        finally:
            sys.path[:] = before_path

    @contextmanager
    def isolated_modules(self, ctx):
        with patch.object(runtime, "current", return_value=ctx):
            with self.source_copy(env) as private_env:
                private_env.REPO = self.repo
                with patch.object(gamelab, "env", private_env):
                    with self.source_copy(runner) as private_runner:
                        private_runner.REPO = self.repo
                        yield private_env, private_runner

    def trusted_cache(self, ctx, recipe, contents):
        identity = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
        cache = ctx.cache_dir / f"{recipe['name']}.fake-build.v2.{identity[:8]}"
        cache.mkdir()
        (cache / "0.hps").write_bytes(contents)
        metadata = {"version": 2, "cache_key": cache.name, "input_sha256": identity,
                    "creator_run": ctx.slot_id, "clean_passes": [1, 2],
                    "files": {"0.hps": hashlib.sha256(contents).hexdigest()}}
        (cache / runner.FIXTURE_CACHE_META).write_text(json.dumps(metadata), encoding="utf-8")
        return cache

    def test_no_runtime_environment_preserves_legacy_game_plan_and_cache(self):
        self.assertIsNone(runtime.current())
        with self.isolated_modules(None) as (default_env, default_runner):
            self.assertEqual(default_env.GAME, default_env.LEGACY_GAME)
            self.assertEqual(default_runner.CACHE, default_runner.FIXTURES / "cache")
            self.assertEqual(default_runner.PLAN_FILE,
                             self.repo / "mods/gamelab-pilot/scripts/GameLab/PlanData.as")
            with runtime.preparation_guard():
                pass
        self.assertFalse((runtime.WORKERS / "integration/preparation.lock").exists())

    def test_admitted_slot_keeps_save_backup_build_link_and_profile_gates(self):
        with self.active() as ctx, self.preflight_fakes(ctx) as gates:
            self.assertEqual(launcher.preflight("lab", mods=["gamelab-pilot"]), ([], []))
        confirmed, backup, build, link = gates
        confirmed.assert_called_once_with()
        backup.assert_called_once_with(quiet=True)
        build.assert_called_once_with()
        link.assert_called_once_with(fix=True, mods=["gamelab-pilot"], packages=None)

    def test_sibling_or_legacy_game_mismatch_refuses_before_any_mutation(self):
        for wrong in (self.two.game_dir, self.repo / "legacy-userdata/game"):
            with self.subTest(game=wrong), self.active() as ctx, self.preflight_fakes(ctx) as gates, \
                    patch.object(env, "GAME", wrong):
                errors, drift = launcher.preflight("lab")
                self.assertTrue(errors)
                self.assertEqual(drift, [])
                for gate in gates:
                    gate.assert_not_called()

    def test_slot_cannot_bypass_backup_confirmation_or_failed_backup(self):
        with self.active() as ctx, self.preflight_fakes(ctx) as gates:
            gates[0].return_value = ["unconfirmed machine backup"]
            self.assertTrue(launcher.preflight("lab")[0])
            gates[1].assert_not_called()
            gates[3].assert_not_called()
        with self.active() as ctx, self.preflight_fakes(ctx) as gates:
            gates[1].return_value = 1
            self.assertTrue(any("backup failed" in error for error in launcher.preflight("lab")[0]))

    def test_slot_build_mismatch_still_refuses_before_link(self):
        with self.active() as ctx, self.preflight_fakes(ctx) as gates:
            gates[2].return_value = ["wrong executable hash"]
            with self.assertRaises(SystemExit) as stopped:
                launcher.preflight("lab")
            self.assertEqual(stopped.exception.code, launcher.pin_build.EXIT_BUILD_MISMATCH)
            gates[3].assert_not_called()

    def test_slot_res_link_mute_and_cloud_isolation_failures_remain_visible(self):
        self.profile.write_text("snd_volume 1\ng_save_slot_cloud 1\n", encoding="utf-8")
        with self.active() as ctx, self.preflight_fakes(ctx) as gates:
            gates[3].return_value = ["res differs from declared install"]
            errors, _ = launcher.preflight("lab")
        self.assertTrue(any("env_link" in error for error in errors))
        self.assertTrue(any("not muted" in error for error in errors))
        self.assertTrue(any("cloud saves" in error for error in errors))

    def test_slot_watch_or_drift_request_never_acquires_or_runs(self):
        scenario = self.repo / "scenario.json"
        scenario.write_text('{"steps": []}', encoding="utf-8")
        for mode, drift in (("watch", False), ("lab", True)):
            with self.subTest(mode=mode, drift=drift), self.active(), \
                    patch.object(launcher, "acquire") as acquire, \
                    patch.object(launcher, "_run") as run:
                self.assertEqual(launcher.run(str(scenario), mode, accept_drift=drift), lock.EXIT_REFUSED)
                acquire.assert_not_called()
                run.assert_not_called()

    def test_launcher_holds_preparation_guard_for_admission_and_environment_link(self):
        from gamelab import pool

        scenario = self.repo / "scenario.json"
        scenario.write_text('{"steps": []}', encoding="utf-8")
        entered = []

        @contextmanager
        def guard():
            entered.append(True)
            try:
                yield
            finally:
                entered.pop()

        def guarded(*args, **kwargs):
            self.assertEqual(entered, [True])

        with self.active() as ctx, self.preflight_fakes(ctx) as gates, \
                patch.object(pool, "validate_scenario", return_value={"steps": []}), \
                patch.object(launcher, "SCENARIOS", self.repo), \
                patch.object(runtime, "preparation_guard", side_effect=guard), \
                patch.object(launcher, "acquire", side_effect=guarded) as acquire, \
                patch.object(launcher, "hoh1_missing", return_value=[]), \
                patch.object(env, "expand_mods", return_value=[]), \
                patch.object(launcher, "_run", return_value=0) as run:
            gates[3].side_effect = lambda **kwargs: (guarded(), [])[1]
            self.assertEqual(launcher.run(str(scenario), "lab"), 0)
        acquire.assert_called_once()
        run.assert_called_once()
        self.assertEqual(entered, [])

    def test_unaudited_slot_scenario_never_acquires_prepares_or_runs(self):
        from gamelab import pool

        scenario = self.repo / "scenario.json"
        scenario.write_text('{"steps": []}', encoding="utf-8")
        with self.active(), patch.object(pool, "validate_scenario", side_effect=ValueError("not audited")), \
                patch.object(runtime, "preparation_guard") as guard, \
                patch.object(launcher, "acquire") as acquire, \
                patch.object(launcher, "preflight") as preflight, \
                patch.object(launcher, "_run") as run:
            self.assertEqual(launcher.run(str(scenario), "lab"), lock.EXIT_REFUSED)
            guard.assert_not_called()
            acquire.assert_not_called()
            preflight.assert_not_called()
            run.assert_not_called()

    def test_suspended_game_is_registered_under_guard_before_injection_and_resume(self):
        game, proc = self.game(self.one)
        order = []

        def spawn(*args, **kwargs):
            self.assertEqual(kwargs["creationflags"], session.winproc.CREATE_SUSPENDED)
            self.assertEqual(kwargs["cwd"], str(self.one.game_dir))
            self.assertEqual(kwargs["env"]["GAMELAB_LOCALAPPDATA"], str((self.one.game_dir / "appdata").resolve()))
            self.assertTrue((Path(self.pool["manifest_path"]).parent / "preparation.lock").exists())
            order.append("suspended")
            return proc

        def inject(process, shim):
            self.assertTrue(runtime.owned_game(proc.pid, self.one.game_dir / "HWR2.exe"))
            self.assertTrue((Path(self.pool["manifest_path"]).parent / "preparation.lock").exists())
            order.append("registered-then-injected")
            return True

        def resume(process):
            self.assertEqual(order, ["suspended", "registered-then-injected"])
            order.append("resumed")
            return True

        with self.active(), patch.object(env, "write_profile"), \
                patch.object(session.subprocess, "Popen", side_effect=spawn), \
                patch.object(session.winproc, "inject", side_effect=inject), \
                patch.object(session.winproc, "resume", side_effect=resume):
            game.start()
        self.assertEqual(order, ["suspended", "registered-then-injected", "resumed"])
        proc.kill.assert_not_called()
        self.assertFalse((Path(self.pool["manifest_path"]).parent / "preparation.lock").exists())

    def test_registration_failure_kills_only_suspended_handle_without_inject_or_resume(self):
        game, proc = self.game(self.one)
        self.processes[proc.pid] = (201, str(self.two.game_dir / "HWR2.exe"))
        with self.active(), patch.object(env, "write_profile"), \
                patch.object(session.subprocess, "Popen", return_value=proc), \
                patch.object(session.winproc, "inject") as inject, \
                patch.object(session.winproc, "resume") as resume:
            with self.assertRaises(runtime.RuntimeError):
                game.start()
        inject.assert_not_called()
        resume.assert_not_called()
        proc.kill.assert_called_once_with()
        proc.wait.assert_called_once_with(10)
        self.assertFalse((self.one.game_dir.parent / "game.json").exists())

    def test_cancelled_registration_cannot_resume_a_suspended_child(self):
        game, proc = self.game(self.one)
        with self.active(), patch.object(env, "write_profile"), \
                patch.object(session.subprocess, "Popen", return_value=proc), \
                patch.object(runtime, "register_game", side_effect=KeyboardInterrupt), \
                patch.object(session.winproc, "inject") as inject, \
                patch.object(session.winproc, "resume") as resume:
            with self.assertRaises(KeyboardInterrupt):
                game.start()
        inject.assert_not_called()
        resume.assert_not_called()
        proc.kill.assert_called_once_with()

    def test_registered_game_with_missing_save_hook_is_never_resumed(self):
        game, proc = self.game(self.one)
        game.shim_log.return_value = "SwapBuffers hooked only"
        with self.active(), patch.object(env, "write_profile"), \
                patch.object(session.subprocess, "Popen", return_value=proc), \
                patch.object(session.winproc, "inject", return_value=True), \
                patch.object(session.winproc, "resume") as resume:
            with self.assertRaises(session.GameError):
                game.start()
            record = json.loads((self.one.game_dir.parent / "game.json").read_text(encoding="utf-8"))
            self.assertEqual(record["pid"], proc.pid)
            self.assertFalse(runtime.owned_game(proc.pid, self.one.game_dir / "HWR2.exe"))
        resume.assert_not_called()
        proc.kill.assert_called_once_with()

    def test_serial_game_start_keeps_hook_gates_without_slot_registration(self):
        game, proc = self.game(self.one)
        with patch.object(runtime, "current", return_value=None), \
                patch.object(runtime, "register_game") as register, \
                patch.object(env, "write_profile"), \
                patch.object(session.subprocess, "Popen", return_value=proc), \
                patch.object(session.winproc, "inject", return_value=True), \
                patch.object(session.winproc, "resume", return_value=True) as resume:
            game.start()
        register.assert_not_called()
        resume.assert_called_once_with(proc)

    def test_verify_live_checks_named_job_and_real_registration_not_any_job(self):
        import hidden_desktop

        game, proc = self.game(self.one)
        game.proc = proc
        self.registered(0, proc.pid, 201)
        game.read_log = Mock(return_value="Launch options: 1: private-game")
        with self.active(), patch.object(session, "process_image", return_value=str(self.one.game_dir / "HWR2.exe")), \
                patch.object(session, "in_job", return_value=True), \
                patch.object(session.winproc, "ancestors", return_value=[os.getpid()]), \
                patch.object(session.winproc, "process_started", return_value=201), \
                patch.object(hidden_desktop, "process_in_job", return_value=False) as named:
            live = game.verify_live()
            self.assertTrue(live["in_job"])
            self.assertTrue(live["registered_slot"])
            self.assertFalse(live["owned_job"])
            named.assert_called_once_with(proc.pid, self.one.job_name)
            named.return_value = True
            positive = game.verify_live()
            self.assertTrue(positive["owned_job"] and positive["registered_slot"])
            self.processes[proc.pid] = (202, str(self.one.game_dir / "HWR2.exe"))
            self.assertFalse(game.verify_live()["registered_slot"])

    def test_runner_live_gate_requires_both_owned_job_and_registered_slot(self):
        for owned_job, registered in ((False, True), (True, False), (False, False), (True, True)):
            with self.subTest(owned_job=owned_job, registered=registered):
                fake = Mock()
                fake.wait_log.return_value = True
                fake.read_log.return_value = "Started menu level\n[NFO] Starting session\n"
                fake.verify_live.return_value = {"image_in_gamelab": True, "known_folder_hooked": True,
                                                 "in_job": True, "child_of_runner": True,
                                                 "owned_job": owned_job, "registered_slot": registered}
                run = runner.Run({}, self.one.results, "lab")
                run.finish = Mock()
                with self.active(), patch.object(runner, "Game", return_value=fake), \
                        patch.object(runner.time, "sleep"):
                    if owned_job and registered:
                        self.assertIs(run.boot(False), fake)
                        run.finish.assert_not_called()
                    else:
                        with self.assertRaisesRegex(session.GameError, "runtime slot"):
                            run.boot(False)
                        run.finish.assert_called_once_with(fake)
                        fake.key.assert_not_called()

    def test_only_registered_sibling_is_excluded_from_player_processes(self):
        first = self.registered(0, 31001, 301)
        sibling = self.registered(1, 31002, 302)
        unknown, foreign = 31003, 31004
        self.processes[unknown] = (303, str(sibling))
        found = [(31001, first), (31002, sibling), (unknown, sibling),
                 (foreign, self.repo / "real-install/HWR2.exe")]
        with self.active(), patch.object(env, "GAME", self.one.game_dir), \
                patch.object(lock, "game_processes", return_value=found):
            self.assertEqual(lock.lab_processes(), [31001])
            self.assertEqual(lock.player_processes(), [unknown, foreign])
            self.processes[31002] = (999, str(sibling))
            self.assertEqual(lock.player_processes(), [31002, unknown, foreign])

    def test_unregistered_game_at_own_slot_path_is_not_cleanup_eligible(self):
        pid = 31005
        self.processes[pid] = (305, str(self.one.game_dir / "HWR2.exe"))
        with self.active(), patch.object(env, "GAME", self.one.game_dir), \
                patch.object(lock, "game_processes", return_value=[(pid, self.one.game_dir / "HWR2.exe")]):
            with self.assertRaises(lock.Refused):
                lock.lab_processes()

    def test_cleanup_refuses_foreign_image_reused_pid_or_changed_lease(self):
        image = self.registered(0, 32001, 401)
        lease = self.one.game_dir.parent / "gamelab.lock"
        original = lease.read_bytes()
        for fault in ("foreign-image", "reused-pid", "foreign-lease"):
            with self.subTest(fault=fault):
                lease.write_bytes(original)
                self.processes[32001] = (401, str(image))
                seen_image = image
                if fault == "foreign-image":
                    seen_image = self.two.game_dir / "HWR2.exe"
                elif fault == "reused-pid":
                    self.processes[32001] = (402, str(image))
                else:
                    lease.write_text(json.dumps({"pid": os.getpid(), "token": "f" * 32}), encoding="utf-8")
                with self.active(), patch.object(env, "GAME", self.one.game_dir), \
                        patch.object(lock, "LOCK", lease), \
                        patch.dict(lock._OWNERS, {str(lease.resolve()): self.one.slot["token"]}), \
                        patch.object(lock, "process_image", return_value=str(seen_image)), \
                        patch.object(runtime, "terminate_owned_game") as terminate, \
                        patch.object(lock.subprocess, "run") as kill:
                    with self.assertRaises(lock.Refused):
                        lock.kill([32001])
                    terminate.assert_not_called()
                    kill.assert_not_called()

    def test_owned_cleanup_never_targets_registered_sibling(self):
        image = self.registered(0, 32002, 411)
        self.registered(1, 32003, 412)
        lease = self.one.game_dir.parent / "gamelab.lock"
        sibling_record = (self.two.game_dir.parent / "game.json").read_bytes()
        with self.active(), patch.object(env, "GAME", self.one.game_dir), \
                patch.object(lock, "LOCK", lease), \
                patch.dict(lock._OWNERS, {str(lease.resolve()): self.one.slot["token"]}), \
                patch.object(lock, "process_image", return_value=str(image)), \
                patch.object(runtime, "terminate_owned_game") as terminate, \
                patch.object(lock.subprocess, "run", return_value=Mock(returncode=0)) as kill:
            lock.kill([32002])
        terminate.assert_called_once()
        self.assertEqual(terminate.call_args.args[0], 32002)
        self.assertEqual(Path(terminate.call_args.args[1]).resolve(), image.resolve())
        kill.assert_not_called()
        self.assertEqual((self.two.game_dir.parent / "game.json").read_bytes(), sibling_record)

    def test_slot_scan_skips_only_proved_exit_and_preserves_legacy_refusal(self):
        tasklist = Mock(returncode=0, stdout='"HWR2.exe","33001"\n', stderr="")
        with patch.object(lock.subprocess, "run", return_value=tasklist), \
                patch.object(lock, "process_image", return_value=""):
            with self.active():
                self.assertEqual(lock.game_processes(), [])
            with patch.object(runtime, "current", return_value=None):
                with self.assertRaises(lock.Refused):
                    lock.game_processes()

    def test_slot_scan_refuses_unknown_visibility_or_still_live_unreadable_image(self):
        for failure in (runtime.RuntimeError("visibility denied"), (501, str(self.two.game_dir / "HWR2.exe"))):
            with self.subTest(failure=type(failure).__name__):
                def query(pid):
                    if pid == 33002:
                        if isinstance(failure, Exception):
                            raise failure
                        return failure
                    return self.processes.get(pid)

                with self.active(), patch.object(runtime, "process_info", side_effect=query), \
                        patch.object(lock, "process_image", return_value=""), \
                        patch.object(lock.subprocess, "run", return_value=Mock(
                            returncode=0, stdout='"HWR2.exe","33002"\n', stderr="")):
                    with self.assertRaises(lock.Refused):
                        lock.game_processes()

    def test_slot_deployment_links_private_harness_and_unchanged_shared_product(self):
        for module in ("gamelab-pilot", "feature"):
            source = self.repo / "mods" / module
            source.mkdir(parents=True)
            (source / "info.xml").write_text("<mod/>", encoding="utf-8")
        links = {}

        def junction(destination, source, problems, fix):
            self.assertTrue(fix)
            destination.mkdir()
            links[destination] = source

        with self.active(), patch.object(env, "REPO", self.repo), \
                patch.object(env, "GAME", self.one.game_dir), \
                patch.object(env, "environments", return_value={"gamelab": {"mods": ["gamelab-pilot"]}}), \
                patch.object(env, "install", return_value=self.repo / "fake-install"), \
                patch.object(env, "ensure_res"), patch.object(env, "copied_files", return_value=[]), \
                patch.object(env, "workshop_ids", return_value={}), \
                patch.object(env, "ensure_junction", side_effect=junction), \
                patch.object(env, "link_target", side_effect=links.get):
            self.assertEqual(env.link(fix=True, mods=["feature"]), [])
        self.assertEqual(links[self.one.game_dir / "mods/gamelab-pilot"], self.one.module_root / "gamelab-pilot")
        self.assertNotEqual(links[self.one.game_dir / "mods/gamelab-pilot"], self.repo / "mods/gamelab-pilot")
        self.assertEqual(links[self.one.game_dir / "mods/feature"], self.repo / "mods/feature")
        self.assertTrue((self.one.module_root / "gamelab-pilot/info.xml").is_file())
        self.assertFalse((self.two.module_root / "gamelab-pilot").exists())

    def test_private_plan_and_cache_restore_preserve_sibling_and_shared_source(self):
        source = self.repo / "mods/gamelab-pilot/scripts/GameLab/PlanData.as"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"shared source plan")
        (source.parent / "Plan.as").write_bytes(b"shared harness code")
        recipe = {"name": "slot-fixture"}
        caches = [self.trusted_cache(ctx, recipe, data) for ctx, data in
                  ((self.one, b"slot-one-profile"), (self.two, b"slot-two-profile"))]
        for ctx in self.contexts:
            (ctx.game_dir / "saves").mkdir()
            (ctx.game_dir / "saves/0.hps").write_bytes(b"old-" + ctx.slot_id.encode())
        for index, ctx in enumerate(self.contexts):
            with self.isolated_modules(ctx) as (private_env, private_runner):
                private_env._prepare_private_module("gamelab-pilot")
                self.assertEqual(private_runner.CACHE, ctx.cache_dir)
                self.assertEqual(private_runner.PLAN_FILE,
                                 ctx.module_root / "gamelab-pilot/scripts/GameLab/PlanData.as")
                private_runner.write_plan(["mark " + ctx.slot_id])
                run = private_runner.Run({}, ctx.results, "lab")
                run.boot = Mock(side_effect=AssertionError("cache hit must not boot"))
                with patch.object(private_runner.pin_build, "live", return_value={"build_id": "fake-build"}), \
                        patch.object(private_runner.hps, "current_save", side_effect=lambda slot, root: root / "0.hps"):
                    self.assertEqual(run.materialize(recipe)["cache"], "hit")
                run.boot.assert_not_called()
            other = self.contexts[1 - index]
            expected = b"old-worker-2" if index == 0 else b"slot-one-profile"
            self.assertEqual((other.game_dir / "saves/0.hps").read_bytes(), expected)
        self.assertEqual(source.read_bytes(), b"shared source plan")
        for ctx, cache, data in zip(self.contexts, caches, (b"slot-one-profile", b"slot-two-profile")):
            self.assertEqual((ctx.game_dir / "saves/0.hps").read_bytes(), data)
            self.assertEqual((cache / "0.hps").read_bytes(), data)
            plan = ctx.module_root / "gamelab-pilot/scripts/GameLab/PlanData.as"
            self.assertIn("mark " + ctx.slot_id, plan.read_text(encoding="utf-8"))

    def test_bad_private_cache_cannot_erase_current_or_sibling_saves(self):
        recipe = {"name": "slot-fixture"}
        cache = self.trusted_cache(self.one, recipe, b"attested profile")
        (cache / "0.hps").write_bytes(b"tampered profile")
        for ctx in self.contexts:
            (ctx.game_dir / "saves").mkdir()
            (ctx.game_dir / "saves/0.hps").write_bytes(b"preserve-" + ctx.slot_id.encode())
        with self.isolated_modules(self.one) as (_, private_runner):
            run = private_runner.Run({}, self.one.results, "lab")
            run.boot = Mock(side_effect=AssertionError("untrusted cache cannot boot"))
            with patch.object(private_runner.pin_build, "live", return_value={"build_id": "fake-build"}), \
                    patch.object(private_runner.hps, "current_save", side_effect=lambda slot, root: root / "0.hps"):
                with self.assertRaisesRegex(session.GameError, "untrusted"):
                    run.materialize(recipe)
            run.boot.assert_not_called()
        for ctx in self.contexts:
            self.assertEqual((ctx.game_dir / "saves/0.hps").read_bytes(), b"preserve-" + ctx.slot_id.encode())


if __name__ == "__main__":
    unittest.main()
