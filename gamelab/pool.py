"""Two lab children under one legacy machine lease; no retries or gate bypasses."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "gamelab/scenarios"
RESULTS = ROOT / "gamelab/results"
POOL_CACHE = ROOT / "gamelab/env/userdata/pool-cache"
DEFAULT_CATALOG = ROOT / "docs/qa/swarm/case_catalog.json"
AUDITED_SCENARIOS = {
    "null-payload": "034284a2e69e3c2c170465eb1d537bd4b24e5f37b80d4f2f50d770ab80492ec3",
    "mod-all": "9298cd10205a06edcc9071e57d77c827e118f06ba69f6ebd4ffa426abc29acc1",
    "qa-firearms-input-sequence": "e936ebafbb828e0bd2cc17239d0d2f393d1c501ac5ebb535628d076872600f74",
    "qa-specs-crit-contract": "db5451375736cf5d4c890a1409254641e61b5c09fa191f38f58c16731b04ef08",
    "qa-runtime-slot-a": "80d1196e09add4b228b9a5993af0e261b08349fb98b65eef5b03dad1bc39e977",
    "qa-runtime-slot-b": "8be28988d22cb094044d9f51913b32ca552bcc6a5a24b450592511f8fba80671",
    "qa-runtime-slot-timeout": "2b51a6528cef5aa9b473c7945169405accd569f79a86741c3834f2eafda3e2c6",
    "qa-runtime-slot-survivor": "697667d2ea1fee6cfd4d566c093c903095a66fd451cd685caf5b023f9553c783",
}
AUDITED_BOTS = {
    "qa_firearms_input_sequence": "1fbdb9a378c09dc1b6a15ac9e8656930822ec010b9768931ca5726e986b2d15a",
    "qa_specs_static": "81cad52723d7991f822e7421335e04aeda75bae304dc6a7e78d96bf6f6669f05",
    "qa_runtime_slots": "e4ade8739baab3407619bbca208f6f12175988aa62cbdf5a292ae20e585f88e0",
}
SAFE_STEPS = {"gl", "console", "sleep", "shot", "log_has", "log_lacks", "log_clean", "bot"}
CACHE_META = ".gamelab-fixture.json"


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_nlink != 1:
        raise ValueError(f"nonordinary artifact: {path}")
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError(f"artifact too large: {path}")
    return raw


def _json(path):
    raw = _artifact(path)
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value, raw


def _put(path, value):
    path = Path(path)
    pending = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with pending.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def _catalog_api():
    from gamelab import catalog
    return catalog


def _load_catalog(path, expected_sha256=None):
    """Bind the loader's validation to the exact ordinary bytes we will retain."""
    path = Path(path).absolute()
    _, raw = _json(path)
    digest = hashlib.sha256(raw).hexdigest()
    value = _catalog_api().load_catalog(path, expected_sha256=expected_sha256)
    if value["metadata"] != {"path": str(path), "sha256": digest} or _json(path)[1] != raw:
        raise ValueError("catalog changed while loading")
    return value, raw


def _runtime_catalog():
    from gamelab import runtime
    context = runtime.current()
    if context is None:
        return None
    return context.manifest.get("catalog")


def validate_scenario(name):
    """Validate a child's authenticated catalog closure, or the builtin audit."""
    reference = _runtime_catalog()
    if reference is not None:
        catalog, _ = _load_catalog(reference["path"], reference["sha256"])
        return _catalog_api().validate_case(catalog, name)["scenario"]
    return _validate_builtin(name)


def _validate_builtin(name):
    """Compatibility for the original exact stock/probe audits only."""
    if type(name) is not str or name not in AUDITED_SCENARIOS:
        raise ValueError(f"scenario has no pool audit: {name!r}")
    path = SCENARIOS / (name + ".json")
    scenario, raw = _json(path)
    if hashlib.sha256(raw).hexdigest() != AUDITED_SCENARIOS[name]:
        raise ValueError(f"pool scenario changed since audit: {name}")
    if scenario.get("name") != name or not isinstance(scenario.get("fixture"), str):
        raise ValueError("pool scenarios require their exact name and a named fixture")
    if any(key in scenario for key in ("plan", "explore", "packages", "profile_export", "export_profile", "exports")):
        raise ValueError("plans, exploration, packages and shared exports are not pool eligible")
    for key in ("timeout", "outer_timeout"):
        number = scenario.get(key, 300)
        if type(number) not in (int, float) or not math.isfinite(number) or not 0 < number <= 3600:
            raise ValueError(f"invalid bounded pool {key}")
    steps = scenario.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("pool steps must be a nonempty list")
    for step in steps:
        if not isinstance(step, dict) or step.get("do") not in SAFE_STEPS:
            raise ValueError("source-writing, relaunch and unaudited steps are refused")
        if step["do"] == "bot":
            bot = step.get("bot")
            if bot not in AUDITED_BOTS or _sha(ROOT / "gamelab/bots" / (bot + ".py")) != AUDITED_BOTS[bot]:
                raise ValueError(f"bot has no current pool audit: {bot!r}")
    return scenario


def _catalog_stable(binding):
    return all(hashlib.sha256(_json(binding[key]["path"])[1]).hexdigest() == binding[key]["sha256"]
               for key in ("input", "snapshot"))


def _selected_closure_stable(record, names, scenarios, admissions, phase):
    """Recheck ignored consumed inputs too; the Git source fingerprint omits them."""
    started = time.monotonic()
    errors = []
    try:
        reference = record["catalog"]["snapshot"]
        frozen, _ = _load_catalog(reference["path"], reference["sha256"])
        for name, scenario, admission in zip(names, scenarios, admissions):
            actual = _catalog_api().validate_case(frozen, name)
            if actual != {"scenario": scenario, "admission": admission}:
                raise ValueError(f"selected catalog admission changed: {name}")
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
        record["closure_stable"] = False
        record["closure_errors"].extend(errors)
    finally:
        record["phase_seconds"]["admission_validation"] += time.monotonic() - started
    record["closure_validation"].append({"phase": phase, "valid": not errors, "errors": errors})
    return not errors


def _scenario_snapshot(row, scenario, output):
    """Retain the exact reviewed input, independent of later working-tree bytes."""
    parsed, raw = _json(SCENARIOS / (row["scenario"] + ".json"))
    digest = hashlib.sha256(raw).hexdigest()
    expected = row["admission"]["files"][f"gamelab/scenarios/{row['scenario']}.json"]
    if digest != expected or parsed != scenario:
        raise ValueError("scenario changed before child snapshot")
    target = output / f"child-{row['index']:04d}.scenario.json"
    with target.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    row.update(scenario_copy=str(target), scenario_sha256=digest)


def _consumer_result(row):
    from gamelab.consumer_evidence import validate_consumers
    scenario, raw = _json(row["scenario_copy"])
    expected = row["admission"]["files"][f"gamelab/scenarios/{row['scenario']}.json"]
    if hashlib.sha256(raw).hexdigest() != row["scenario_sha256"] or row["scenario_sha256"] != expected:
        raise ValueError("retained scenario no longer matches catalog admission")
    records = []
    row.update(bot_results=None, bot_results_sha256=None)
    bot_file = Path(row["results"]) / "bot-results.jsonl"
    required = any(step["do"] == "bot" for step in scenario["steps"])
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate bot result key: {key}")
            value[key] = item
        return value
    if required or os.path.lexists(bot_file):
        raw = _artifact(bot_file)
        row.update(bot_results=str(bot_file), bot_results_sha256=hashlib.sha256(raw).hexdigest())
        for line in raw.decode("utf-8-sig").splitlines():
            if not line.strip():
                raise ValueError("blank bot result record")
            value = json.loads(line, object_pairs_hook=unique_pairs)
            if type(value) is not dict:
                raise ValueError("bot result must be a JSON object")
            json.dumps(value, allow_nan=False)
            records.append(value)
    row["consumer_validation"] = validate_consumers(row["admission"], scenario, records)
    if row["consumer_validation"].get("valid") is not True:
        raise ValueError("completed bot results do not satisfy the catalog consumer contract")


def _backend():
    from gamelab import lock, runtime
    return lock, runtime


def _named_jobs_empty(manifest):
    from tools.hidden_desktop import job_empty
    return {slot["job_name"]: job_empty(slot["job_name"]) for slot in manifest["slots"]}


def _fingerprint():
    from tools.qa_batch import fingerprint
    return fingerprint()


def _cache_verify(path):
    from gamelab.runner import verified_fixture_cache
    metadata, _ = _json(Path(path) / CACHE_META)
    identity = metadata.get("input_sha256")
    if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise ValueError("cache has no exact input identity")
    return verified_fixture_cache(Path(path), identity)


def _cache_entries(root, events):
    if not root.exists():
        return []
    if root.is_symlink() or getattr(root.lstat(), "st_file_attributes", 0) & 0x400:
        raise ValueError(f"cache root is redirected: {root}")
    found = []
    for path in sorted(root.iterdir()):
        if path.name.startswith(".pending-"):
            raise ValueError(f"incomplete cache publication retained: {path}")
        if not path.is_dir() or ".v2." not in path.name:
            if path.name != "origins.jsonl":
                events.append({"ignored_legacy_cache": str(path)})
            continue
        _cache_verify(path)  # malformed v2 entries refuse, never fall back silently
        found.append(path)
    return found


def _copy_cache(source, destination_root):
    metadata = _cache_verify(source)
    destination = destination_root / source.name
    if os.path.lexists(destination):
        existing = _cache_verify(destination)
        if existing["input_sha256"] != metadata["input_sha256"]:
            raise ValueError("cache-key collision")
        return False  # independent clean creators can have different save bytes
    pending = destination_root / (".pending-" + uuid.uuid4().hex)
    pending.mkdir()
    staged = pending / source.name
    shutil.copytree(source, staged)
    if _cache_verify(staged) != metadata:
        raise ValueError("copied cache failed exact readback; partial copy retained")
    staged.rename(destination)  # no replacement of an existing cache
    pending.rmdir()
    return True


def _seed_caches(manifest, events):
    POOL_CACHE.mkdir(parents=True, exist_ok=True)
    sources = _cache_entries(POOL_CACHE, events) + _cache_entries(ROOT / "gamelab/fixtures/cache", events)
    for slot in manifest["slots"]:
        for source in sources:
            copied = _copy_cache(source, Path(slot["cache_dir"]))
            events.append({"seed": str(source), "slot": slot["slot_id"], "copied": copied})


def _promote_caches(rows, manifest, events):
    for row in rows:
        if not row["ok"]:
            continue
        fixture = row["result"].get("fixture") or {}
        if fixture.get("cache") != "miss":
            continue
        key = fixture.get("cache_key")
        if not isinstance(key, str) or Path(key).name != key or ".v2." not in key:
            raise ValueError("successful cold fixture has no safe v2 cache key")
        source = Path(manifest["slots"][row["slot_index"]]["cache_dir"]) / key
        metadata = _cache_verify(source)
        if metadata["creator_run"] != row["run_id"]:
            raise ValueError("cold cache creator does not identify this successful nested run")
        if _copy_cache(source, POOL_CACHE):
            origin = {"cache_key": key, "run": row["results"], "run_sha256": row["run_sha256"],
                      "metadata": metadata, "at": time.time()}
            with (POOL_CACHE / "origins.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(origin) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            events.append({"promoted": key, "origin": row["results"]})


def _result(row, slot, manifest, output):
    from tools.qa_batch import successful, inner_matches_outer
    directory = Path(row["results"])
    record, _ = _json(directory / "run.json")
    inner, _ = _json(directory / "inner.json")
    teardown, raw = _json(Path(slot["game_dir"]).parent / "teardown.json")
    copy = output / (f"child-{row['index']:04d}.teardown.json")
    with copy.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    row.update(result=record, run_id=directory.name, run_sha256=_sha(directory / "run.json"),
               inner_sha256=_sha(directory / "inner.json"), teardown=teardown,
               teardown_copy=str(copy), teardown_sha256=hashlib.sha256(raw).hexdigest())
    expected = {key: slot[key] for key in ("slot_id", "game_dir", "desktop_name", "job_name")}
    expected["pool_id"] = manifest["pool_id"]
    if record.get("runtime_slot") != expected:
        raise ValueError("run does not identify its exact admitted runtime slot")
    if teardown != record.get("teardown") or teardown.get("run") != directory.name or teardown.get("clean") is not True:
        raise ValueError("slot teardown is missing, dirty or belongs to a different run")
    if row["exit"] != 0 or not successful(record, row["scenario"]) or not inner_matches_outer(record, inner, row["scenario"]):
        raise ValueError("child exit, outer PASS and final inner result do not agree")
    if row.get("admission") is not None:
        try:
            _consumer_result(row)
        except (OSError, ValueError) as error:
            row.setdefault("consumer_validation", {"valid": False, "errors": [str(error)], "checks": []})
            raise
    live = record.get("live")
    if not isinstance(live, list) or not live or not all(item.get("owned_job") is True and item.get("registered_slot") is True for item in live):
        raise ValueError("missing owned-job/registered-slot live evidence")


def run_pool(names, *, label, workers=2, dry_run=False, catalog=None, catalog_sha256=None):
    """Run bounded pair waves, stopping dispatch after any failure; retain all artifacts."""
    if type(workers) is not int or workers not in (1, 2):
        raise ValueError("workers must be 1 or 2")
    if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", label):
        raise ValueError("label must be 1-80 filename characters")
    names = list(names) if not isinstance(names, str) else []
    if not 0 < len(names) <= 128:
        raise ValueError("provide 1-128 audited scenario names")
    if catalog is not None and catalog_sha256 is None:
        raise ValueError("an explicit catalog requires --catalog-sha256")
    catalog_path = Path(catalog) if catalog is not None else DEFAULT_CATALOG if os.path.lexists(DEFAULT_CATALOG) else None
    if catalog_sha256 is not None and catalog_path is None:
        raise ValueError("--catalog-sha256 requires a catalog")
    catalog_value = catalog_raw = None
    admissions = [None] * len(names)
    if catalog_path is not None:
        catalog_value, catalog_raw = _load_catalog(catalog_path, catalog_sha256)
        selected = [_catalog_api().validate_case(catalog_value, name) for name in names]
        scenarios = [case["scenario"] for case in selected]
        admissions = [case["admission"] for case in selected]
    else:
        scenarios = [validate_scenario(name) for name in names]
    probe_families = ({"qa-runtime-slot-a", "qa-runtime-slot-b"},
                      {"qa-runtime-slot-timeout", "qa-runtime-slot-survivor"})
    known_probes = set().union(*probe_families)
    if any(admission is not None and admission["lifecycle"] == "paired-probe" and name not in known_probes
           for name, admission in zip(names, admissions)):
        raise ValueError("only the exact runtime acceptance probe pairs have a pool pairing contract")
    if any(set(names) & family for family in probe_families):
        if workers != 2 or len(names) != 2 or not any(set(names) == family for family in probe_families):
            raise ValueError("runtime acceptance probes require their exact two-role pair and --workers 2")
    commands = [[sys.executable, "-m", "gamelab", "run", name, "--mode", "lab"] for name in names]
    if dry_run:
        return {"ok": True, "exit_code": 0, "dry_run": True, "workers": workers,
                "commands": commands, "source": _fingerprint(), "admissions": admissions,
                "catalog": catalog_value["metadata"] if catalog_value is not None else None}
    output = RESULTS / ("pool-" + label)
    if os.path.lexists(output):
        raise ValueError("pool label already exists; preserve it and choose a new label")
    lock, runtime = _backend()
    if runtime.current() is not None:
        raise ValueError("nested pools are refused")
    lease_started = time.monotonic()
    lock.acquire("pool-" + label, "lab")
    record = {"label": label, "workers": workers, "output": str(output), "started": time.time(), "children": [],
              "cache": [], "problems": [], "lease_retained": True, "ok": False, "exit_code": 1,
              "catalog": None, "closure_stable": None, "closure_errors": [], "closure_validation": [],
              "phase_seconds": {"lease_acquire": time.monotonic() - lease_started, "admission_validation": 0}}
    manifest = None
    active = []
    unsafe = False
    dirty = []
    try:
        RESULTS.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        record["source_before"] = _fingerprint()
        catalog_reference = None
        if catalog_value is not None:
            snapshot = output / "catalog.snapshot.json"
            with snapshot.open("xb") as stream:
                stream.write(catalog_raw)
                stream.flush()
                os.fsync(stream.fileno())
            digest = catalog_value["metadata"]["sha256"]
            catalog_reference = {"path": str(snapshot.absolute()), "sha256": digest}
            record["catalog"] = {"input": catalog_value["metadata"], "snapshot": catalog_reference,
                                 "admissions": admissions, "stable": True}
            record["closure_stable"] = True
            if not _selected_closure_stable(record, names, scenarios, admissions, "freeze"):
                record["preflight_refused"] = True
                raise ValueError("selected closure changed before queue freeze")
            record["mechanical_admission"] = {
                "valid": True, "catalog_sha256": digest,
                "checks": [{"scenario": name, "closure_sha256": admission["closure_sha256"],
                            "review_and_closure_current": True} for name, admission in zip(names, admissions)]}
            if not _catalog_stable(record["catalog"]):
                raise ValueError("catalog changed before queue freeze")
        lease, _ = _json(lock.LOCK)
        pool_started = time.monotonic()
        catalog_options = {"catalog": catalog_reference} if catalog_reference is not None else {}
        manifest = runtime.create_pool(ROOT / "gamelab/env/userdata/workers" / ("p" + uuid.uuid4().hex),
                                       lease, record["source_before"], slot_count=2, **catalog_options)
        record["phase_seconds"]["pool_create"] = time.monotonic() - pool_started
        record["pool"] = manifest
        _put(output / "pool.json", record)
        start = 0
        while start < len(names):
            if record["problems"]:
                break
            if (output / "STOP").exists() or (RESULTS / ("qa-batch-" + label + ".stop")).exists():
                record["problems"].append("stop requested between waves")
                break
            if _fingerprint() != record["source_before"]:
                dirty.append("frozen source changed before dispatch")
                raise ValueError(dirty[-1])
            if record["catalog"] is not None and not _catalog_stable(record["catalog"]):
                dirty.append("frozen catalog changed before dispatch")
                raise ValueError(dirty[-1])
            if record["catalog"] is not None and not _selected_closure_stable(record, names, scenarios, admissions, "before-wave"):
                if record["children"]:
                    dirty.append("selected closure changed between waves")
                else:
                    record["preflight_refused"] = True
                raise ValueError("selected closure changed before dispatch")
            cache_started = time.monotonic()
            _seed_caches(manifest, record["cache"])
            record["phase_seconds"]["cache_seed"] = record["phase_seconds"].get("cache_seed", 0) + time.monotonic() - cache_started
            wave = []
            for offset in range(min(workers, len(names) - start)):
                # Interpret an already finished child before dispatching more,
                # including exit0 children whose result may be missing/invalid.
                if any(item["process"].poll() is not None for item in active):
                    break
                index = start
                slot = manifest["slots"][offset]
                results = Path(slot["results"]) / f"case-{index + 1:04d}-{names[index]}-lab"
                overrides = runtime.child_env(manifest, offset, results=results)
                row = {"index": index + 1, "scenario": names[index], "slot_index": offset,
                       "results": str(results), "command": commands[index], "pid": None, "exit": None,
                       "terminal": False, "timed_out": False, "ok": False, "problems": [],
                       "source_before": record["source_before"], "started": time.time(),
                       "admission": admissions[index]}
                if row["admission"] is not None:
                    _scenario_snapshot(row, scenarios[index], output)
                record["children"].append(row)
                stdout = (output / f"child-{index + 1:04d}.stdout").open("xb")
                stderr = (output / f"child-{index + 1:04d}.stderr").open("xb")
                try:
                    spawn_started = time.monotonic()
                    process = subprocess.Popen(commands[index], cwd=ROOT, stdin=subprocess.DEVNULL,
                                               stdout=stdout, stderr=stderr, env=dict(os.environ, **overrides), shell=False,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except BaseException:
                    stdout.close(); stderr.close()
                    unsafe = True  # no invented process finality after a failed spawn
                    raise
                limit = scenarios[index].get("outer_timeout", scenarios[index].get("timeout", 300) * 3) + 60
                row.update(pid=process.pid, timeout_seconds=limit, spawn_seconds=time.monotonic() - spawn_started)
                item = {"process": process, "row": row, "slot": slot, "stdout": stdout, "stderr": stderr,
                        "deadline": time.monotonic() + limit, "started": time.monotonic()}
                active.append(item); wave.append(row)
                start += 1
                _put(output / "pool.json", record)
            while active:
                for item in list(active):
                    process, row = item["process"], item["row"]
                    code = process.poll()
                    if code is None and time.monotonic() >= item["deadline"]:
                        row["timed_out"] = unsafe = True
                        process.kill()  # held handle only; never claim descendant death
                        try: code = process.wait(timeout=5)
                        except subprocess.TimeoutExpired: code = None
                        row["problems"].append("parent deadline; owned descendant accounting required")
                    if code is None and not row["timed_out"]:
                        continue
                    row.update(exit=code, terminal=type(code) is int, seconds=time.monotonic() - item["started"])
                    item["stdout"].close(); item["stderr"].close()
                    try:
                        _result(row, item["slot"], manifest, output)
                        row["ok"] = not row["problems"] and not row["timed_out"]
                    except Exception as error:
                        row["problems"].append(f"{type(error).__name__}: {error}")
                        if (row.get("teardown") or {}).get("clean") is not True:
                            dirty.append("child has no verified clean teardown")
                    for suffix in ("stdout", "stderr"):
                        row[suffix + "_sha256"] = _sha(output / f"child-{row['index']:04d}.{suffix}")
                    if not row["ok"]:
                        record["problems"].append(f"child {row['index']} did not pass")
                    active.remove(item)
                    _put(output / "pool.json", record)
                if active:
                    time.sleep(0.05)
            after = _fingerprint()
            for row in wave: row["source_after"] = after
            if after != record["source_before"]:
                dirty.append("frozen source changed during wave")
                raise ValueError(dirty[-1])
            if record["catalog"] is not None and not _catalog_stable(record["catalog"]):
                dirty.append("frozen catalog changed during wave")
                raise ValueError(dirty[-1])
            if record["catalog"] is not None and not _selected_closure_stable(record, names, scenarios, admissions, "after-wave"):
                dirty.append("selected closure changed during wave")
                raise ValueError(dirty[-1])
            if not runtime.registered_games_absent(manifest) or lock.game_processes():
                unsafe = True
                raise ValueError("registered or unknown game remains; do not dispatch or release")
            if not all(value is True for value in _named_jobs_empty(manifest).values()):
                unsafe = True
                raise ValueError("owned named job remains; no cache publication or dispatch")
            cache_started = time.monotonic()
            _promote_caches(wave, manifest, record["cache"])
            record["phase_seconds"]["cache_promote"] = record["phase_seconds"].get("cache_promote", 0) + time.monotonic() - cache_started
    except (Exception, KeyboardInterrupt) as error:
        record["problems"].append(f"{type(error).__name__}: {error}")
    finally:
        for item in active:
            unsafe = True
            try:
                item["process"].kill()
                item["row"]["exit"] = item["process"].wait(timeout=5)
                item["row"]["terminal"] = True
            except Exception as error:
                item["row"]["problems"].append(f"cleanup: {error}")
            item["stdout"].close(); item["stderr"].close()
        try:
            record["source_after"] = _fingerprint()
            if record.get("source_before") != record["source_after"]:
                dirty.append("frozen source changed or unavailable")
            if record["catalog"] is not None:
                try:
                    record["catalog"]["stable"] = _catalog_stable(record["catalog"])
                except (OSError, ValueError) as error:
                    record["catalog"]["stable"] = False
                    record["problems"].append(f"catalog finality: {type(error).__name__}: {error}")
                if not record["catalog"]["stable"]:
                    dirty.append("frozen catalog changed or unavailable")
                if not _selected_closure_stable(record, names, scenarios, admissions, "final") or record["closure_stable"] is not True:
                    if record["children"]:
                        dirty.append("selected closure changed or unavailable")
                    else:
                        record["preflight_refused"] = True
            record["games_after"] = [(pid, str(path)) for pid, path in lock.game_processes()]
            record["global_games_absent"] = not record["games_after"]
            record["registered_games_absent"] = manifest is None or runtime.registered_games_absent(manifest)
            record["all_cli_handles_terminal"] = all(row["terminal"] for row in record["children"])
            record["pool_closed"] = record["slot_leases_absent"] = False
            if record["games_after"] or not record["registered_games_absent"]:
                raise ValueError("game absence not established")
            if manifest:
                record["named_jobs_empty"] = _named_jobs_empty(manifest)
                if not all(value is True for value in record["named_jobs_empty"].values()):
                    raise ValueError("owned named jobs are not empty")
                runtime.close_pool(manifest)
                record["pool_closed"] = record["slot_leases_absent"] = True
                record["pool_manifest_after_sha256"] = _sha(manifest["manifest_path"])
            if not unsafe:
                record["teardown"] = lock.release("pool-" + label, dirty)
                record["lease_retained"] = False
        except Exception as error:
            record["problems"].append(f"finality: {type(error).__name__}: {error}")
            unsafe = True
        record.update(ended=time.time(), dispatched=len(record["children"]), requested=len(names),
                      requires_owned_descendant_audit=unsafe,
                      source_stable=record.get("source_before") is not None and record.get("source_before") == record.get("source_after"))
        record["ok"] = (not record["problems"] and not dirty and not record["lease_retained"]
                        and len(record["children"]) == len(names) and all(row["ok"] for row in record["children"]))
        record["exit_code"] = 0 if record["ok"] else 4 if record["lease_retained"] or dirty else 2 if record.get("preflight_refused") else 1
        if output.is_dir(): _put(output / "pool.json", record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--mode", choices=("lab",), default="lab")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--catalog-sha256")
    parser.add_argument("scenarios", nargs="+")
    args = parser.parse_args(argv)
    try:
        record = run_pool(args.scenarios, label=args.label, workers=args.workers, dry_run=args.dry_run,
                          catalog=args.catalog, catalog_sha256=args.catalog_sha256)
    except Exception as error:
        refused = getattr(sys.modules.get("gamelab.lock"), "Refused", ())
        if isinstance(error, refused):
            code = 4
        elif isinstance(error, (OSError, ValueError, RuntimeError)):
            code = 2
        else:
            raise
        print(json.dumps({"ok": False, "exit_code": code, "error": str(error)}), flush=True)
        return code
    print(json.dumps(record), flush=True)
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
