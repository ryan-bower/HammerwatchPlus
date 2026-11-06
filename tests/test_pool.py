"""Pool scheduling and evidence controls: fake CLI handles, no native launches."""
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gamelab import pool


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class PoolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hwp-pool-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.results = self.root / "results"
        self.scenarios = self.root / "scenarios"
        self.scenarios.mkdir()
        self.addCleanup(patch.stopall)
        for name, value in (("ROOT", self.root), ("RESULTS", self.results), ("SCENARIOS", self.scenarios),
                            ("POOL_CACHE", self.root / "pool-cache"), ("DEFAULT_CATALOG", self.root / "default-catalog.json")):
            patch.object(pool, name, value).start()
        patch.object(pool, "_runtime_catalog", return_value=None).start()
        patch.dict(pool.AUDITED_SCENARIOS, {}, clear=True).start()
        self.name = "null-payload"
        self.scenario()
        self.source = {"head": "fake", "source_sha256": "a" * 64, "files": 1,
                       "fingerprint_scope": "mods+gamelab+tools-v2"}
        self.fingerprint = patch.object(pool, "_fingerprint", return_value=self.source).start()
        self.lock_path = self.root / "machine.lock"
        self.releases = []
        self.lock = SimpleNamespace(LOCK=self.lock_path, acquire=self.acquire, release=self.release,
                                    game_processes=lambda: [])
        self.runtime = SimpleNamespace(current=lambda: None, create_pool=self.create_pool,
                                       child_env=self.child_env, registered_games_absent=lambda manifest: True,
                                       close_pool=self.close_pool)
        patch.object(pool, "_backend", return_value=(self.lock, self.runtime)).start()
        self.jobs = patch.object(pool, "_named_jobs_empty", side_effect=lambda manifest: {
            slot["job_name"]: True for slot in manifest["slots"]}).start()
        self.running = self.maximum = 0
        self.processes = []
        self.modes = []
        self.manifest = None
        patch.object(pool.subprocess, "Popen", side_effect=self.spawn).start()
        patch.object(pool.time, "sleep", return_value=None).start()
        self.seed = patch.object(pool, "_seed_caches", side_effect=self.no_live_cache).start()
        self.promote = patch.object(pool, "_promote_caches", side_effect=self.no_live_cache).start()

    def scenario(self, **changes):
        value = {"name": self.name, "fixture": "town-paladin", "timeout": 1,
                 "steps": [{"do": "gl", "verb": "ping"}]}
        value.update(changes)
        path = self.scenarios / (self.name + ".json")
        write_json(path, value)
        pool.AUDITED_SCENARIOS[self.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return value

    def test_probe_pair_admission_refuses_missing_mixed_or_serial_peer_before_lease(self):
        with patch.object(pool, "validate_scenario", return_value={}):
            for names, workers in ((["qa-runtime-slot-a"], 2),
                                   (["qa-runtime-slot-a", "mod-all"], 2),
                                   (["qa-runtime-slot-a", "qa-runtime-slot-b"], 1),
                                   (["qa-runtime-slot-timeout", "qa-runtime-slot-b"], 2)):
                with self.subTest(names=names, workers=workers), self.assertRaises(ValueError):
                    pool.run_pool(names, label="invalid-pair", workers=workers)
        self.assertFalse(self.lock_path.exists())
        self.assertEqual(self.processes, [])

    def test_exact_probe_pair_is_dry_run_admissible_without_acquiring_runtime(self):
        with patch.object(pool, "validate_scenario", return_value={}):
            for names in (["qa-runtime-slot-a", "qa-runtime-slot-b"],
                          ["qa-runtime-slot-timeout", "qa-runtime-slot-survivor"]):
                self.assertTrue(pool.run_pool(names, label="pair-preview", workers=2, dry_run=True)["ok"])
        self.assertFalse(self.lock_path.exists())

    def acquire(self, *args):
        self.assertFalse(self.lock_path.exists())
        write_json(self.lock_path, {"pid": 12345, "token": "a" * 32})

    def release(self, name, reasons):
        self.releases.append(list(reasons))
        self.lock_path.unlink()
        return {"run": name, "clean": not reasons, "reasons": reasons}

    def create_pool(self, root, lease, source, slot_count, catalog=None):
        self.assertEqual(slot_count, 2)
        self.assertEqual(source, self.source)
        root.mkdir(parents=True)
        slots = []
        for index in range(2):
            slot = {"slot_id": f"worker-{index + 1}", "game_dir": str(root / str(index) / "game"),
                    "cache_dir": str(root / str(index) / "cache"),
                    "results": str(self.results / "workers" / root.name / str(index)),
                    "job_name": f"job-{index}", "desktop_name": f"desktop-{index}"}
            for key in ("game_dir", "cache_dir", "results"):
                Path(slot[key]).mkdir(parents=True)
            slots.append(slot)
        self.manifest = {"pool_id": root.name, "manifest_path": str(root / "pool.json"),
                         "closed": False, "slots": slots}
        if catalog is not None:
            self.manifest["catalog"] = catalog
        write_json(root / "pool.json", self.manifest)
        return self.manifest

    def child_env(self, manifest, slot, results):
        self.assertFalse(Path(results).exists())
        self.assertTrue(Path(results).is_relative_to(Path(manifest["slots"][slot]["results"])))
        return {"POOL_TEST_SLOT": str(slot), "POOL_TEST_RESULTS": str(results)}

    def close_pool(self, manifest):
        self.assertEqual(self.running, 0)
        write_json(Path(manifest["manifest_path"]), dict(manifest, closed=True))

    def no_live_cache(self, *args):
        self.assertEqual(self.running, 0, "cache publication must not overlap a child")

    def spawn(self, argv, **kwargs):
        self.assertEqual(argv, [sys.executable, "-m", "gamelab", "run", self.name, "--mode", "lab"])
        self.assertFalse(kwargs["shell"])
        mode = self.modes.pop(0) if self.modes else "pass"
        if mode == "spawn-error":
            raise OSError("fake owned spawn refusal")
        case = self

        class Process:
            def __init__(self):
                self.pid = 1000 + len(case.processes)
                self.returncode = None
                self.left = 0 if mode.startswith("fast-") else 4
                self.killed = False

            def finish(self):
                if self.returncode is not None:
                    return self.returncode
                case.running -= 1
                self.returncode = -9 if self.killed else 1 if mode == "fast-fail" else 0
                if self.killed:
                    return self.returncode
                slot = case.manifest["slots"][int(kwargs["env"]["POOL_TEST_SLOT"])]
                directory = Path(kwargs["env"]["POOL_TEST_RESULTS"])
                directory.mkdir()
                assertions = [{"name": "native pass", "ok": mode != "fast-fail"}]
                live = [{"owned_job": True, "registered_slot": True}]
                inner = {"scenario": case.name, "mode": "lab", "partial": False,
                         "assertions": assertions, "live": live, "fixture": {"cache": "hit"}}
                teardown = {"run": directory.name, "clean": True, "reasons": []}
                outer = dict(inner, environment="gamelab", verdict="FAIL" if self.returncode else "PASS",
                             build_drift=False, error=None, teardown=teardown,
                             runtime_slot={key: slot[key] for key in ("slot_id", "game_dir", "desktop_name", "job_name")})
                outer["runtime_slot"]["pool_id"] = case.manifest["pool_id"]
                write_json(directory / "run.json", outer)
                if mode != "fast-missing-inner":
                    write_json(directory / "inner.json", inner)
                if hasattr(case, "bot_raw"):
                    (directory / "bot-results.jsonl").write_bytes(case.bot_raw)
                elif hasattr(case, "bot_records"):
                    (directory / "bot-results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in case.bot_records), encoding="utf-8")
                write_json(Path(slot["game_dir"]).parent / "teardown.json", teardown)
                if getattr(case, "on_finish", None) is not None:
                    case.on_finish()
                return self.returncode

            def poll(self):
                if mode != "hang" and self.returncode is None:
                    self.left -= 1
                    if self.left <= 0:
                        self.finish()
                return self.returncode

            def kill(self):
                self.killed = True

            def wait(self, timeout):
                if mode == "hang" and not self.killed:
                    raise subprocess.TimeoutExpired(argv, timeout)
                return self.finish()

        process = Process()
        self.processes.append(process)
        self.running += 1
        self.maximum = max(self.maximum, self.running)
        return process

    def test_pair_waves_reuse_slots_but_never_results_or_live_cache_publication(self):
        result = pool.run_pool([self.name] * 4, label="pair")
        self.assertTrue(result["ok"], result["problems"])
        self.assertEqual(self.maximum, 2)
        self.assertEqual(len({row["results"] for row in result["children"]}), 4)
        self.assertEqual([row["slot_index"] for row in result["children"]], [0, 1, 0, 1])
        self.assertEqual(len(self.releases), 1)
        self.assertTrue(result["pool_closed"])
        self.assertTrue(result["all_cli_handles_terminal"])
        for row in result["children"]:
            self.assertEqual(json.loads(Path(row["teardown_copy"]).read_bytes()), row["result"]["teardown"])

    def test_workers_one_still_checks_same_context_and_runs_serially(self):
        result = pool.run_pool([self.name] * 3, label="serial", workers=1)
        self.assertTrue(result["ok"])
        self.assertEqual(self.maximum, 1)

    def test_fast_nonpass_stops_dispatch_without_killing_unrelated_children(self):
        self.modes = ["fast-fail"]
        result = pool.run_pool([self.name] * 3, label="fail")
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(self.releases, [[]])
        self.assertFalse(self.processes[0].killed)

    def test_fast_exit_zero_with_missing_inner_cannot_dispatch_the_next_case(self):
        self.modes = ["fast-missing-inner"]
        result = pool.run_pool([self.name] * 3, label="missing")
        self.assertEqual(len(self.processes), 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["children"][0]["exit"], 0)

    def test_parent_timeout_retains_machine_lease_even_after_known_handle_exit(self):
        self.modes = ["hang"]
        ticks = iter(range(0, 10000, 100))
        with patch.object(pool.time, "monotonic", side_effect=lambda: next(ticks)):
            result = pool.run_pool([self.name], label="timeout")
        self.assertEqual(result["exit_code"], 4)
        self.assertTrue(result["lease_retained"])
        self.assertTrue(result["requires_owned_descendant_audit"])
        self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.releases)

    def test_source_drift_stops_new_wave_and_marks_global_teardown_dirty(self):
        changed = dict(self.source, source_sha256="b" * 64)
        self.fingerprint.side_effect = [self.source, self.source, changed, changed]
        result = pool.run_pool([self.name] * 3, label="drift")
        self.assertEqual(len(self.processes), 2)
        self.assertFalse(result["source_stable"])
        self.assertEqual(result["exit_code"], 4)
        self.assertTrue(self.releases[0])

    def test_spawn_uncertainty_and_live_slot_refusal_keep_the_legacy_fence(self):
        self.modes = ["spawn-error"]
        result = pool.run_pool([self.name], label="spawn")
        self.assertEqual(result["exit_code"], 4)
        self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.releases)

    def test_dry_run_has_no_lease_cache_output_or_runtime_side_effects(self):
        with patch.object(pool, "_backend", side_effect=AssertionError("runtime forbidden")):
            result = pool.run_pool([self.name], label="preview", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.results.exists())
        self.seed.assert_not_called()

    def test_changed_or_filepath_scenario_and_unsafe_audited_content_refuse(self):
        path = self.scenarios / (self.name + ".json")
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "changed since audit"):
            pool.validate_scenario(self.name)
        with self.assertRaises(ValueError):
            pool.validate_scenario(str(path))
        for key in ("plan", "explore", "packages", "export_profile"):
            with self.subTest(key=key):
                self.scenario(**{key: False})
                with self.assertRaises(ValueError):
                    pool.validate_scenario(self.name)
        self.scenario(steps=[{"do": "write_text_file"}])
        with self.assertRaises(ValueError):
            pool.validate_scenario(self.name)

    def test_main_preserves_typed_lock_refusal_exit_four(self):
        class Refused(Exception):
            pass
        with patch.dict(sys.modules, {"gamelab.lock": SimpleNamespace(Refused=Refused)}), \
                patch.object(pool, "run_pool", side_effect=Refused("held by another owner")), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(pool.main(["--label", "held", self.name]), 4)
        self.assertEqual(json.loads(output.getvalue())["exit_code"], 4)

    def catalog_fixture(self):
        """Small API double: catalog's own tests cover its review/closure schema."""
        path = self.root / "reviewed-catalog.json"
        admission = {"id": self.name, "task": "TASK", "check": "contract", "scope": "native",
                     "expected": "ping succeeds", "predicates": [{"step": 0, "expect": {"ok": True}}],
                     "lifecycle": "independent", "private_writes": [],
                     "consumers": [],
                     "review": {"reviewer": "independent", "verdict": "accepted", "sha256": "b" * 64},
                     "closure_sha256": "c" * 64, "files": {f"gamelab/scenarios/{self.name}.json": pool.AUDITED_SCENARIOS[self.name]}}
        write_json(path, {"reviewed": True, "admission": admission})
        digest = pool._sha(path)

        def load_catalog(path, expected_sha256=None):
            value = json.loads(Path(path).read_bytes())
            actual = pool._sha(path)
            if expected_sha256 is not None and actual != expected_sha256:
                raise ValueError("catalog SHA mismatch")
            if value.get("reviewed") is not True:
                raise ValueError("catalog entry is not reviewed")
            return dict(value, metadata={"path": str(Path(path).absolute()), "sha256": actual})

        def validate_case(catalog, name):
            value = catalog["admission"]
            if name != value["id"]:
                raise ValueError("unknown case")
            for source, expected in value["files"].items():
                path = self.scenarios / Path(source).name if source.startswith("gamelab/scenarios/") else self.root / source
                if pool._sha(path) != expected:
                    raise ValueError("closure changed")
            scenario = json.loads((self.scenarios / (name + ".json")).read_bytes())
            return {"scenario": scenario,
                    "admission": dict(value, catalog_sha256=catalog["metadata"]["sha256"])}

        api = SimpleNamespace(load_catalog=load_catalog, validate_case=validate_case)
        patch.object(pool, "_catalog_api", return_value=api).start()
        self.consumer = Mock(return_value={"valid": True, "errors": [], "checks": []})
        patch.dict(sys.modules, {"gamelab.consumer_evidence": SimpleNamespace(validate_consumers=self.consumer)}).start()
        return path, digest, api

    def test_catalog_snapshot_is_exact_authenticated_and_retains_case_contract(self):
        path, digest, _ = self.catalog_fixture()
        raw = path.read_bytes()
        result = pool.run_pool([self.name] * 3, label="catalog", catalog=path, catalog_sha256=digest)
        self.assertTrue(result["ok"], result["problems"])
        binding = result["catalog"]
        self.assertEqual(Path(binding["snapshot"]["path"]).read_bytes(), raw)
        self.assertEqual(self.manifest["catalog"], binding["snapshot"])
        self.assertTrue(binding["stable"])
        self.assertTrue(result["closure_stable"])
        self.assertTrue(all(item["valid"] for item in result["closure_validation"]))
        self.assertTrue(result["mechanical_admission"]["valid"])
        self.assertEqual(result["mechanical_admission"]["catalog_sha256"], digest)
        for row in result["children"]:
            self.assertEqual(row["admission"], binding["admissions"][row["index"] - 1])
            self.assertEqual(row["admission"]["task"], "TASK")
            self.assertEqual(row["admission"]["predicates"], [{"step": 0, "expect": {"ok": True}}])
            self.assertEqual(Path(row["scenario_copy"]).read_bytes(), (self.scenarios / (self.name + ".json")).read_bytes())
            self.assertEqual(row["scenario_sha256"], row["admission"]["files"][f"gamelab/scenarios/{self.name}.json"])
            self.assertTrue(row["consumer_validation"]["valid"])
            self.assertIsNone(row["bot_results_sha256"])
            self.assertGreaterEqual(row["spawn_seconds"], 0)
        self.assertEqual(set(result["phase_seconds"]), {"lease_acquire", "pool_create", "cache_seed", "cache_promote", "admission_validation"})

    def test_catalog_digest_review_and_closure_refuse_before_machine_lease(self):
        path, digest, _ = self.catalog_fixture()
        for expected in (None, "f" * 64):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                pool.run_pool([self.name], label="bad-catalog", catalog=path, catalog_sha256=expected)
        raw = path.read_bytes()
        value = json.loads(raw)
        value["reviewed"] = False
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, "not reviewed"):
            pool.run_pool([self.name], label="unreviewed", catalog=path, catalog_sha256=pool._sha(path))
        path.write_bytes(raw)
        source = self.scenarios / (self.name + ".json")
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "closure changed"):
            pool.run_pool([self.name], label="changed-closure", catalog=path, catalog_sha256=digest)
        self.assertFalse(self.lock_path.exists())
        self.assertEqual(self.processes, [])

    def test_catalog_input_or_snapshot_drift_invalidates_queue_and_stops_next_wave(self):
        path, digest, _ = self.catalog_fixture()
        raw = path.read_bytes()
        original_promote = self.promote.side_effect
        for target in ("input", "snapshot"):
            with self.subTest(target=target):
                path.write_bytes(raw)
                label = "catalog-drift-" + target
                def mutate(*args):
                    original_promote(*args)
                    changed = path if target == "input" else self.results / ("pool-" + label) / "catalog.snapshot.json"
                    changed.write_bytes(changed.read_bytes() + b"\n")
                self.promote.side_effect = mutate
                result = pool.run_pool([self.name] * 3, label=label, catalog=path, catalog_sha256=digest)
                self.assertEqual(result["dispatched"], 2)
                self.assertFalse(result["catalog"]["stable"])
                self.assertTrue(result["source_stable"])
                self.assertEqual(result["exit_code"], 4)
                self.assertTrue(self.releases[-1])
        self.assertEqual(len(self.processes), 4)

    def test_child_uses_authenticated_snapshot_and_rechecks_selected_closure(self):
        path, digest, _ = self.catalog_fixture()
        with patch.object(pool, "_runtime_catalog", return_value={"path": str(path), "sha256": digest}):
            # Child admission must not fall back to builtin pins, even if they disagree.
            pool.AUDITED_SCENARIOS[self.name] = "f" * 64
            self.assertEqual(pool.validate_scenario(self.name)["name"], self.name)
            source = self.scenarios / (self.name + ".json")
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "closure changed"):
                pool.validate_scenario(self.name)

    def test_ignored_consumed_input_drift_refuses_before_wave_during_wave_and_final(self):
        path, _, _ = self.catalog_fixture()
        relative = "mods/feature/generated/ignored.bin"
        consumed = self.root / relative
        consumed.parent.mkdir(parents=True)
        consumed.write_bytes(b"reviewed consumed bytes")
        value = json.loads(path.read_bytes())
        value["admission"]["files"][relative] = pool._sha(consumed)
        write_json(path, value)
        digest = pool._sha(path)
        raw = consumed.read_bytes()
        original_create = self.runtime.create_pool
        for phase in ("before-wave", "after-wave", "final"):
            with self.subTest(phase=phase):
                consumed.write_bytes(raw)
                self.on_finish = None
                self.promote.side_effect = self.no_live_cache
                def mutate():
                    consumed.write_bytes(b"unreviewed ignored input")
                def create(*args, **kwargs):
                    manifest = original_create(*args, **kwargs)
                    if phase == "before-wave":
                        mutate()
                    return manifest
                self.runtime.create_pool = create
                if phase == "after-wave":
                    self.on_finish = mutate
                if phase == "final":
                    def promote(*args):
                        self.no_live_cache(*args)
                        mutate()
                    self.promote.side_effect = promote
                count = 2 if phase == "final" else 3
                result = pool.run_pool([self.name] * count, label="ignored-" + phase, catalog=path, catalog_sha256=digest)
                self.assertFalse(result["ok"])
                self.assertTrue(result["source_stable"], "Git source fingerprint deliberately stays unchanged")
                self.assertTrue(result["catalog"]["stable"], "catalog bytes deliberately stay unchanged")
                self.assertFalse(result["closure_stable"])
                self.assertTrue(result["closure_errors"])
                self.assertFalse(next(item for item in result["closure_validation"] if item["phase"] == phase)["valid"])
                self.assertEqual(result["dispatched"], 0 if phase == "before-wave" else 2)
                self.assertEqual(result["exit_code"], 2 if phase == "before-wave" else 4)
                self.assertEqual(bool(self.releases[-1]), phase != "before-wave")
                self.assertGreater(result["phase_seconds"]["admission_validation"], 0)

    def test_default_catalog_and_cli_flags_use_same_admission_without_materializing_dry_run(self):
        path, digest, _ = self.catalog_fixture()
        with patch.object(pool, "DEFAULT_CATALOG", path):
            result = pool.run_pool([self.name], label="default", dry_run=True)
        self.assertEqual(result["catalog"]["sha256"], digest)
        self.assertFalse(self.results.exists())
        with patch.object(pool, "run_pool", return_value={"exit_code": 0}) as run, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(pool.main(["--label", "cli", "--catalog", str(path), "--catalog-sha256", digest, self.name]), 0)
        self.assertEqual(run.call_args.kwargs["catalog"], path)
        self.assertEqual(run.call_args.kwargs["catalog_sha256"], digest)

    def test_catalog_bot_stream_is_hashed_and_failed_consumer_stops_dispatch(self):
        self.scenario(steps=[{"do": "bot", "bot": "reviewed_bot", "expect": {"ok": True}}])
        path, digest, _ = self.catalog_fixture()
        self.bot_records = [{"bot": "reviewed_bot", "result": {"ok": False}}]
        self.consumer.return_value = {"valid": False, "errors": ["consumer row failed"], "checks": [{"ok": False}]}
        self.modes = ["fast-pass"]
        result = pool.run_pool([self.name] * 3, label="consumer-refusal", catalog=path, catalog_sha256=digest)
        self.assertEqual(result["dispatched"], 1)
        row = result["children"][0]
        self.assertEqual(row["bot_results_sha256"], pool._sha(row["bot_results"]))
        self.assertFalse(row["consumer_validation"]["valid"])
        self.assertEqual(self.consumer.call_args.args, (row["admission"], json.loads(Path(row["scenario_copy"]).read_bytes()), self.bot_records))
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 1)

    def test_catalog_bot_step_missing_stream_refuses_even_with_cli_outer_and_inner_pass(self):
        self.scenario(steps=[{"do": "bot", "bot": "reviewed_bot"}])
        path, digest, _ = self.catalog_fixture()
        result = pool.run_pool([self.name], label="missing-bot-stream", catalog=path, catalog_sha256=digest)
        self.assertFalse(result["ok"])
        self.assertEqual(result["children"][0]["exit"], 0)
        self.assertFalse(result["children"][0]["consumer_validation"]["valid"])
        self.consumer.assert_not_called()

    def test_malformed_bot_streams_are_retained_and_cannot_be_scored_as_consumer_pass(self):
        self.scenario(steps=[{"do": "bot", "bot": "reviewed_bot"}])
        path, digest, _ = self.catalog_fixture()
        for index, raw in enumerate((b"{}\n\n", b'{"pass":1,"pass":2}\n', b'{"value":NaN}\n', b"[]\n")):
            with self.subTest(raw=raw):
                self.bot_raw = raw
                result = pool.run_pool([self.name], label=f"bad-bot-{index}", catalog=path, catalog_sha256=digest)
                row = result["children"][0]
                self.assertEqual(row["exit"], 0)
                self.assertFalse(row["consumer_validation"]["valid"])
                self.assertEqual(Path(row["bot_results"]).read_bytes(), raw)
                self.assertEqual(row["bot_results_sha256"], hashlib.sha256(raw).hexdigest())
        self.consumer.assert_not_called()

    def test_catalog_cannot_admit_unknown_pairing_contract_as_an_independent_wave(self):
        path, _, _ = self.catalog_fixture()
        value = json.loads(path.read_bytes())
        value["admission"]["lifecycle"] = "paired-probe"
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, "pairing contract"):
            pool.run_pool([self.name], label="unknown-pair", catalog=path, catalog_sha256=pool._sha(path))
        self.assertFalse(self.lock_path.exists())

    def test_real_catalog_api_snapshot_and_child_admission_work_without_native_backend(self):
        from gamelab import catalog
        self.scenarios = self.root / "gamelab/scenarios"
        with patch.object(pool, "SCENARIOS", self.scenarios), patch.object(catalog, "ROOT", self.root):
            self.scenario(steps=[{"do": "gl", "verb": "ping", "expect": {"ok": True}}])
            fixture = self.root / "gamelab/fixtures/town-paladin.json"
            review = self.root / "docs/review.json"
            write_json(fixture, {"name": "town-paladin", "binary_edits": {}})
            write_json(review, {"review": "temporary API fixture"})
            paths = [f"gamelab/scenarios/{self.name}.json", "gamelab/fixtures/town-paladin.json"]
            entry = {"id": self.name, "status": "reviewed", "scenario": paths[0], "task": "TEST-POOL",
                     "check": self.name, "scope": "controlled-native", "expected": "Temporary fixture only",
                     "predicates": [{"step": 0, "expect": {"ok": True}}], "lifecycle": "independent",
                     "private_writes": ["slot-game", "slot-results"],
                     "review": {"reviewer": "fixture", "verdict": "accepted", "artifact": "docs/review.json",
                                "sha256": pool._sha(review), "closure_complete": True},
                     "closure": {"files": catalog.hash_reviewed_files(paths), "bots": [],
                                 "fixture": "town-paladin", "modules": []}}
            path = self.root / "docs/catalog.json"
            write_json(path, {"schema_version": 1, "catalog_id": "pool-fixture", "cases": [entry]})
            result = pool.run_pool([self.name], label="real-api", catalog=path, catalog_sha256=pool._sha(path))
            self.assertTrue(result["ok"], result["problems"])
            self.assertEqual(result["children"][0]["admission"]["files"], entry["closure"]["files"])
            with patch.object(pool, "_runtime_catalog", return_value=self.manifest["catalog"]):
                self.assertEqual(pool.validate_scenario(self.name)["name"], self.name)


class CacheTests(unittest.TestCase):
    def setUp(self):
        from gamelab import runner
        temporary = tempfile.TemporaryDirectory(prefix="hwp-pool-cache-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(runner, "REPO", self.root).start()
        patch.object(pool, "POOL_CACHE", self.root / "store").start()
        pool.POOL_CACHE.mkdir()
        self.identity = "a" * 64
        self.source = self.root / ("town.build.v2." + self.identity[:8])
        self.source.mkdir()
        body = b"H2SV\x03\0\0\0" + struct.pack("<Q", 1) + b"synthetic profile"
        save = body + hashlib.md5(body).digest()[:4]
        (self.source / "0.hps").write_bytes(save)
        self.metadata = {"version": 2, "cache_key": self.source.name, "input_sha256": self.identity,
                         "creator_run": "nested", "clean_passes": [1, 2],
                         "files": {"0.hps": hashlib.sha256(save).hexdigest()}}
        write_json(self.source / pool.CACHE_META, self.metadata)

    def test_copy_verifies_bytes_and_never_overwrites_existing_attested_cache(self):
        self.assertTrue(pool._copy_cache(self.source, pool.POOL_CACHE))
        target = pool.POOL_CACHE / self.source.name
        before = (target / "0.hps").read_bytes()
        self.assertFalse(pool._copy_cache(self.source, pool.POOL_CACHE))
        self.assertEqual((target / "0.hps").read_bytes(), before)
        (target / "0.hps").write_bytes(b"corrupted")
        with self.assertRaises(Exception):
            pool._copy_cache(self.source, pool.POOL_CACHE)
        self.assertEqual((target / "0.hps").read_bytes(), b"corrupted")

    def test_partial_publication_refuses_instead_of_falling_back_to_another_cache(self):
        (pool.POOL_CACHE / ".pending-abandoned").mkdir()
        with self.assertRaisesRegex(ValueError, "incomplete cache publication"):
            pool._cache_entries(pool.POOL_CACHE, [])

    def test_only_clean_pass_cold_creator_is_promoted_with_exact_run_origin(self):
        row = {"ok": True, "slot_index": 0, "run_id": "nested", "results": "owned/results/nested",
               "run_sha256": "b" * 64, "result": {"fixture": {"cache": "miss", "cache_key": self.source.name}}}
        manifest = {"slots": [{"cache_dir": str(self.root)}]}
        pool._promote_caches([dict(row, ok=False)], manifest, [])
        self.assertFalse((pool.POOL_CACHE / self.source.name).exists())
        pool._promote_caches([row], manifest, [])
        origin = json.loads((pool.POOL_CACHE / "origins.jsonl").read_text())
        self.assertEqual(origin["run"], row["results"])
        self.assertEqual(origin["metadata"], self.metadata)


if __name__ == "__main__":
    unittest.main()
