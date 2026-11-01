#!/usr/bin/env python3
"""Agent-first durable QA bookkeeping. No game launches or source edits.

JSON stdout, versioned JSON storage, fenced claims, bounded resume packets.
Run `schema` for the machine contract; read docs/qa/SWARM_TRACKER.md for workflow.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
DEFAULT_STATE = ROOT / "docs/qa/swarm/state.json"
SCHEMA = 1
STATUSES = ("queued", "reviewing", "reproduced", "harness-blocked", "fix-drafted",
            "reviewed", "integrated", "verified", "deferred")
OPERATIONS = ("review", "draft", "sandbox", "integration", "native")
SCOPES = ("source", "offline", "native-contract", "load", "controlled-native", "ordinary", "visual", "packed", "coop")
NATIVE_SCOPES = {"native-contract", "load", "controlled-native", "ordinary", "packed", "coop"}
ID = re.compile(r"[A-Z][A-Z0-9_-]{0,79}\Z")
TRANSITIONS = {
    "queued": {"reviewing", "harness-blocked", "deferred"},
    "reviewing": set(STATUSES) - {"queued", "integrated"},
    "reproduced": {"fix-drafted", "harness-blocked", "deferred", "reviewing"},
    "harness-blocked": {"reviewing", "deferred"},
    "fix-drafted": {"reviewed", "reviewing", "harness-blocked", "deferred"},
    "reviewed": {"integrated", "verified", "reviewing", "deferred"},
    "integrated": {"verified", "reviewing", "harness-blocked", "deferred"},
    "deferred": {"reviewing"},
    "verified": set(),
}


class Refused(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def require(ok, code, message, **details):
    if not ok:
        raise Refused(code, message, **details)


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def text_field(value, name):
    require(isinstance(value, str) and bool(value.strip()), "invalid_record", f"{name} must be nonempty text")


def source_valid(source):
    require(isinstance(source, dict), "invalid_source", "source must be an object")
    for key, size in (("head", 40), ("source_sha256", 64)):
        require(isinstance(source.get(key), str) and re.fullmatch(f"[0-9a-f]{{{size}}}", source[key]),
                "invalid_source", f"invalid source.{key}")
    require(source.get("fingerprint_scope") == "mods+gamelab+tools-v2"
            and type(source.get("files")) is int and source["files"] >= 0,
            "invalid_source", "expected a qa_batch fingerprint with its original scope")


def task_valid(task):
    require(isinstance(task, dict) and isinstance(task.get("id"), str) and ID.fullmatch(task["id"]),
            "invalid_task", "task ID must match [A-Z][A-Z0-9_-]{0,79}")
    for key in ("title", "lane", "summary", "next_action"):
        text_field(task.get(key), key)
    require(task.get("operation") in OPERATIONS and task.get("status") in STATUSES,
            "invalid_task", "unknown operation or status", task=task["id"])
    for key in ("depends_on", "paths", "required_scopes", "checks", "evidence"):
        require(isinstance(task.get(key), list), "invalid_task", f"{key} must be a list")
    for key in ("depends_on", "paths", "checks"):
        require(all(isinstance(item, str) and item for item in task[key])
                and len(task[key]) == len(set(task[key])), "invalid_task", f"invalid/duplicate {key}")
    require(bool(task["required_scopes"]) and all(scope in SCOPES for scope in task["required_scopes"]),
            "invalid_task", "required_scopes must name evidence scopes")
    require(type(task.get("revision")) is int and task["revision"] >= 0,
            "invalid_task", "revision must be a nonnegative integer")
    claim = task.get("claim")
    if claim is not None:
        require(isinstance(claim, dict), "invalid_task", "claim must be an object or null")
        for key in ("owner", "token", "attempt", "artifacts"):
            text_field(claim.get(key), f"claim.{key}")
        require(type(claim.get("expires")) in (int, float) and math.isfinite(claim["expires"]),
                "invalid_task", "invalid lease expiry")


def validate(state):
    require(isinstance(state, dict) and type(state.get("schema_version")) is int and state["schema_version"] == SCHEMA,
            "schema_version", "unsupported or missing state schema_version")
    require(type(state.get("revision")) is int and state["revision"] >= 0,
            "invalid_state", "invalid campaign revision")
    require(isinstance(state.get("tasks"), dict) and isinstance(state.get("history"), list),
            "invalid_state", "tasks/history are required")
    require(all(isinstance(row, dict) for row in state["history"]), "invalid_state", "history entries must be objects")
    require(state.get("phase") in ("idle", "frozen") and isinstance(state.get("epochs"), dict),
            "invalid_state", "invalid phase/epochs")
    for key in ("campaign", "runtime_owner", "integrator"):
        text_field(state.get(key), key)
    require(re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", state["campaign"]),
            "invalid_state", "unsafe campaign identifier")
    for key, epoch in state["epochs"].items():
        require(ID.fullmatch(key), "invalid_source", "invalid epoch ID")
        source_valid(epoch["native"])
    require(state.get("current_epoch") is None or state["current_epoch"] in state["epochs"],
            "invalid_source", "current epoch is missing")
    for key, task in state["tasks"].items():
        task_valid(task)
        require(key == task["id"], "invalid_task", "task key and ID differ")
        for evidence in task["evidence"]:
            evidence_valid(evidence, state)
        if task["status"] == "verified":
            require(task.get("verified_epoch") in state["epochs"] and task["claim"] is None
                    and isinstance(task.get("verified_dependencies"), dict),
                    "invalid_task", "verified task is missing its terminal provenance")
    visiting, visited = set(), set()

    def visit(key):
        require(key in state["tasks"], "dependency_missing", "unknown dependency", task=key)
        require(key not in visiting, "dependency_cycle", "dependency cycle", task=key)
        if key in visited:
            return
        visiting.add(key)
        for dependency in state["tasks"][key]["depends_on"]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in state["tasks"]:
        visit(key)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = self.path.with_suffix(self.path.suffix + ".lock")

    def load(self):
        require(self.path.is_file(), "not_initialized", "initialize the tracker from seed first",
                path=str(self.path))
        state = read_json(self.path)
        validate(state)
        return state

    @contextmanager
    def writer(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 3
        while True:
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                require(time.monotonic() < deadline, "writer_locked",
                        "tracker writer lock is held; inspect owner, never auto-delete a stale lock",
                        lock=str(self.lock))
                time.sleep(0.025)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"pid": os.getpid(), "created": stamp(), "store": str(self.path)}, stream)
            yield
        finally:
            self.lock.unlink()

    def save(self, state):
        validate(state)
        payload = json.dumps(state, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                             prefix=self.path.name + ".", suffix=".tmp",
                                             dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def new_task(record):
    task = dict(record)
    task.update(revision=0, status="queued", claim=None, evidence=[])
    task.setdefault("depends_on", [])
    task.setdefault("paths", [])
    task.setdefault("checks", [])
    task.setdefault("required_scopes", ["source"])
    task.setdefault("summary", "Not started; no coverage claimed.")
    task_valid(task)
    return task


AMEND_FIELDS = ("paths", "checks", "required_scopes", "depends_on")


def task_definition(task):
    keys = ("id", "title", "lane", "operation", "priority", *AMEND_FIELDS, "summary", "next_action")
    return {key: copy.deepcopy(task[key]) for key in keys if key in task}


def amend_definition(state, task, record):
    require(isinstance(record, dict) and not (set(record) - set(AMEND_FIELDS) - {"replace_deferred_dependencies"}),
            "invalid_amendment", "amendment must contain only allowed definition fields")
    replacements = record.get("replace_deferred_dependencies", {})
    require(isinstance(replacements, dict) and all(isinstance(value, str) and value.strip() for value in replacements.values()),
            "invalid_amendment", "dependency replacements must map old IDs to new IDs")
    require(not set(replacements).intersection(replacements.values()), "invalid_amendment",
            "a replacement target cannot also be removed by this amendment")
    replacement_history = []
    for old_id, new_id in replacements.items():
        require(old_id in task["depends_on"] and old_id != new_id, "invalid_amendment",
                "replacement must name a current dependency and a different task")
        require(new_id in state["tasks"], "dependency_missing", "unknown replacement dependency", task=new_id)
        require(new_id != task["id"], "dependency_cycle", "task cannot depend on itself")
        old, new = state["tasks"][old_id], state["tasks"][new_id]
        require(old["status"] == "deferred" and old["claim"] is None, "replacement_refused",
                "only an unclaimed deferred dependency may be replaced")
        require(new["operation"] == old["operation"]
                and set(old["checks"]) <= set(new["checks"])
                and set(old["required_scopes"]) <= set(new["required_scopes"]),
                "definition_weakening", "replacement must preserve operation, checks and scopes")
        replacement_history.append({"old_id": old_id, "new_id": new_id,
                                    "old_revision": old["revision"], "new_revision": new["revision"],
                                    "old_definition": task_definition(old), "new_definition": task_definition(new)})
    updated = {key: list(task[key]) for key in AMEND_FIELDS}
    updated["depends_on"] = list(dict.fromkeys(replacements.get(key, key) for key in task["depends_on"]))
    for key in AMEND_FIELDS:
        if key not in record:
            continue
        values = record[key]
        require(isinstance(values, list) and all(isinstance(value, str) and value.strip() for value in values)
                and len(values) == len(set(values)), "invalid_amendment", "definition fields must be unique nonempty text lists")
        require(key != "required_scopes" or all(value in SCOPES for value in values),
                "invalid_amendment", "unknown evidence scope")
        require(set(updated[key]) <= set(values), "definition_weakening", "amendment cannot remove existing obligations", field=key)
        require(key != "depends_on" or not set(replacements).intersection(values),
                "invalid_amendment", "replaced dependencies must be absent from the final definition")
        updated[key].extend(value for value in values if value not in updated[key])
    require(task["id"] not in updated["depends_on"], "dependency_cycle", "task cannot depend on itself")
    require(any(updated[key] != task[key] for key in AMEND_FIELDS), "no_op", "amendment makes no definition change")
    task.update(updated)
    return replacement_history


def blockers(state, task):
    reasons = ["dependency:" + key for key in task["depends_on"]
               if not fresh_verified(state, state["tasks"][key])]
    if task["operation"] == "integration" and state["phase"] != "idle":
        reasons.append("source_frozen")
    if task["operation"] == "native" and (state["phase"] != "frozen" or not state["current_epoch"]):
        reasons.append("runtime_owner_must_freeze_pinned_epoch")
    return reasons


def fresh_verified(state, task):
    return (task["status"] == "verified" and task.get("verified_epoch") == state["current_epoch"]
            and task.get("verified_dependencies", {}) == {
                key: state["tasks"][key]["revision"] for key in task["depends_on"]}
            and all(fresh_verified(state, state["tasks"][key]) for key in task["depends_on"]))


def card(state, task, owner=None, state_path=DEFAULT_STATE):
    result = {key: copy.deepcopy(task[key]) for key in
              ("id", "title", "lane", "operation", "status", "revision", "summary", "next_action",
               "paths", "depends_on", "required_scopes", "checks")}
    result["blockers"] = blockers(state, task)
    result["fresh_verified"] = fresh_verified(state, task)
    if task["claim"]:
        result["claim"] = dict(task["claim"])
        result["claim"]["expired"] = task["claim"]["expires"] <= time.time()
        result["claim"]["epoch_changed"] = task["claim"]["epoch"] != state["current_epoch"]
        if owner != task["claim"]["owner"]:
            result["claim"].pop("token", None)
    elif owner and task["status"] != "verified" and not result["blockers"]:
        result["claim_argv"] = [sys.executable, str(Path(__file__).resolve()), "--state", str(Path(state_path).resolve()), "claim", task["id"],
                                "--owner", owner, "--expect", str(task["revision"])]
    return result


def command_argv(state_path, *arguments):
    return [sys.executable, str(Path(__file__).resolve()), "--state", str(Path(state_path).resolve()),
            *map(str, arguments)]


def page(items, limit, offset=0, latest=False):
    """Offsets skip rows from the selected end; each returned page is ordered."""
    total = len(items)
    if latest:
        end = max(0, total - offset)
        rows = items[max(0, end - limit):end] if limit else []
    else:
        rows = items[offset:offset + limit]
    return rows, {"total": total, "returned": len(rows), "offset": offset, "limit": limit,
                  "order": "latest-pages-chronological-within-page" if latest else "priority-id",
                  "next_argv": None}


def detail_pages(state, task, owner, state_path, evidence_limit=5, evidence_offset=0,
                 history_limit=5, history_offset=0):
    evidence = task["evidence"]
    history = [row for row in state["history"] if row.get("task") == task["id"]]
    result, pagination = {}, {}
    for key, values, limit, offset in (("evidence", evidence, evidence_limit, evidence_offset),
                                       ("history", history, history_limit, history_offset)):
        rows, info = page(values, limit, offset, latest=True)
        result[key], result[key + "_count"] = copy.deepcopy(rows), len(values)
        info["task_revision"] = task["revision"]
        if offset + len(rows) < len(values):
            # A compact limit0 receipt gives an explicit first-page retrieval.
            next_offset, next_limit = offset + len(rows), limit or 5
            arguments = ["show", task["id"], "--at-task-revision", task["revision"],
                         "--evidence-limit", next_limit if key == "evidence" else 0,
                         "--history-limit", next_limit if key == "history" else 0,
                         "--evidence-offset", next_offset if key == "evidence" else 0,
                         "--history-offset", next_offset if key == "history" else 0]
            if owner:
                arguments += ["--owner", owner]
            info["next_argv"] = command_argv(state_path, *arguments)
        pagination[key] = info
    last = evidence[-1] if evidence else None
    result["latest_evidence"] = ({key: copy.deepcopy(last[key]) for key in
        ("scope", "check", "outcome", "epoch", "reviewer", "recorded_at", "attempt", "dependencies") if key in last}
        if last else None)
    result["pagination"] = pagination
    return result


def mutation_task_view(state, task, owner, state_path, args):
    # Retain small task/control fields and terminal provenance, including the
    # exact claim token/attempt/epoch/dependencies. Only raw detail is paged.
    result = {key: copy.deepcopy(value) for key, value in task.items() if key != "evidence"}
    result.update(detail_pages(state, task, owner, state_path,
                  getattr(args, "evidence_limit", 0), getattr(args, "evidence_offset", 0),
                  getattr(args, "history_limit", 0), getattr(args, "history_offset", 0)))
    return result


def packet(state, owner, limit, state_path=DEFAULT_STATE, *, command="resume",
           owned_offset=0, ready_offset=0, blocked_offset=0):
    tasks = sorted(state["tasks"].values(), key=lambda item: (item.get("priority", 50), item["id"]))
    actionable = {"queued", "reviewing", "reproduced", "fix-drafted", "reviewed", "integrated"}
    ready = [task for task in tasks if task["status"] in actionable and not task["claim"]
             and not blockers(state, task)]
    if owner:
        ready = [task for task in ready if task["operation"] not in ("native", "integration")
                 or owner == state["runtime_owner" if task["operation"] == "native" else "integrator"]]
        ready.sort(key=lambda task: (task["lane"] != owner, task.get("priority", 50), task["id"]))
    active = [task for task in tasks if task["claim"] and (not owner or task["claim"]["owner"] == owner)]
    blocked = [task for task in tasks if task["status"] in ("harness-blocked", "deferred")
               or task["status"] == "queued" and blockers(state, task)]
    lists, pagination = {}, {}
    offsets = {"owned_tasks": owned_offset, "next_tasks": ready_offset, "blocked_tasks": blocked_offset}
    flags = {"owned_tasks": "--owned-offset", "next_tasks": "--ready-offset", "blocked_tasks": "--blocked-offset"}
    for key, values in (("owned_tasks", active), ("next_tasks", ready), ("blocked_tasks", blocked)):
        rows, info = page(values, limit, offsets[key])
        lists[key] = ([{"id": task["id"], "status": task["status"], "summary": task["summary"],
                        "blockers": blockers(state, task)} for task in rows] if key == "blocked_tasks" else
                      [card(state, task, owner, state_path) for task in rows])
        info["campaign_revision"] = state["revision"]
        if offsets[key] + len(rows) < len(values):
            next_offsets = dict(offsets)
            next_offsets[key] += len(rows)
            arguments = [command, "--limit", limit, "--at-revision", state["revision"]]
            if owner:
                arguments += ["--owner", owner]
            for name, value in next_offsets.items():
                arguments += [flags[name], value]
            info["next_argv"] = command_argv(state_path, *arguments)
        pagination[key] = info
    stale = [task["id"] for task in tasks if task["status"] == "verified" and not fresh_verified(state, task)]
    return {"campaign": state["campaign"], "revision": state["revision"], "phase": state["phase"],
            "freeze": state.get("freeze"), "current_epoch": state["current_epoch"],
            "counts": dict(sorted(Counter(task["status"] for task in tasks).items())),
            "total_tasks": len(tasks), "ready_count": len(ready), "stale_verification": stale,
            "automatic_campaign_signoff": False,
            "all_tasks_verified_current": bool(tasks) and all(fresh_verified(state, task) for task in tasks),
            "agent_limits": state.get("agent_limits", {"initial": 32, "working_max": 48, "hard_max": 100}),
            "completion_note": "Task counts are bookkeeping, not code coverage or campaign sign-off.",
            **lists, "pagination": pagination,
            "warnings": (["No source epoch pinned. Capture one before claiming validation."]
                         if not state["current_epoch"] else [])}


def authorized(task, args, allow_expired=False):
    require(task["revision"] == args.expect, "revision_conflict", "reread task before updating",
            expected=args.expect, actual=task["revision"])
    claim = task["claim"]
    require(claim is not None and claim["token"] == args.token, "claim_conflict", "claim token does not match")
    require(allow_expired or claim["expires"] > time.time(), "lease_expired",
            "lease expired; reclaim offline work explicitly, never infer runtime permission")
    return claim


def evidence_valid(evidence, state):
    require(isinstance(evidence, dict) and evidence.get("scope") in SCOPES
            and evidence.get("outcome") in ("pass", "fail", "blocked", "skip"),
            "invalid_evidence", "evidence requires scope and outcome")
    for key in ("expected", "observed", "reviewer"):
        text_field(evidence.get(key), key)
    require(evidence.get("epoch") in state["epochs"], "invalid_evidence", "evidence epoch must exist")
    require(isinstance(evidence.get("artifacts"), list) and evidence["artifacts"]
            and all(isinstance(path, str) and path for path in evidence["artifacts"]),
            "invalid_evidence", "evidence must cite artifact paths")
    if evidence["scope"] != "source":
        require(isinstance(evidence.get("command"), list) and bool(evidence["command"]),
                "invalid_evidence", "non-review evidence needs command argv")
        require(all(isinstance(part, str) and part for part in evidence["command"]),
                "invalid_evidence", "command argv entries must be nonempty strings")
        require(type(evidence.get("exit")) is int, "invalid_evidence", "evidence needs integer exit")
        if evidence["outcome"] == "pass":
            require(evidence["exit"] == 0, "invalid_evidence", "PASS cannot have nonzero exit")
    if evidence["scope"] in NATIVE_SCOPES:
        for key in ("run_id", "scenario"):
            require(bool(evidence.get(key)), "invalid_evidence", f"native evidence needs {key}")
        if evidence["outcome"] == "pass":
            build = evidence.get("build")
            pin = state["epochs"][evidence["epoch"]].get("build")
            require(isinstance(build, dict) and isinstance(pin, dict) and bool(pin.get("build_id"))
                    and isinstance(pin.get("exe_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", pin["exe_sha256"])
                    and all(build.get(key) == pin[key] for key in ("build_id", "exe_sha256")),
                    "invalid_evidence", "native PASS requires the epoch's actual pinned build ID and executable hash")
            expected = state["epochs"][evidence["epoch"]]["native"]
            require(evidence.get("source_before") == expected == evidence.get("source_after")
                    and evidence.get("verdict") == "PASS" and evidence.get("partial") is False
                    and evidence.get("build_drift") is False and evidence.get("error") is None
                    and evidence.get("teardown_clean") is True and evidence.get("assertions_ok") is True,
                    "invalid_evidence", "native PASS requires matching epoch, verdict, guards and assertions")


def verification_ready(task, state):
    require(state["current_epoch"] is not None, "epoch_required", "pin a source epoch before verification")
    require(task["claim"]["epoch"] == state["current_epoch"], "claim_epoch_changed",
            "source epoch changed since claim; release, claim again and revalidate")
    dependencies = {key: state["tasks"][key]["revision"] for key in task["depends_on"]}
    require(task["claim"].get("dependencies") == dependencies, "dependencies_changed",
            "prerequisite revisions changed since claim; release and revalidate")
    latest = {}
    for row in task["evidence"]:
        if (row["epoch"] == state["current_epoch"] and row.get("attempt") == task["claim"]["attempt"]
                and row.get("dependencies") == dependencies):
            latest[(row["scope"], row.get("check"))] = row
    require(all(row["outcome"] == "pass" for row in latest.values()), "unresolved_evidence",
            "latest evidence includes failed, blocked or skipped checks; retain and resolve their disposition")
    evidence = [row for row in latest.values() if row["reviewer"] != task["claim"]["owner"]]
    require(set(task["required_scopes"]) <= {row["scope"] for row in evidence},
            "evidence_required", "missing current-epoch evidence accepted by an independent reviewer",
            required_scopes=task["required_scopes"])
    require(set(task["checks"]) <= {row.get("check") for row in evidence},
            "checks_required", "missing required named checks", checks=task["checks"])
    require(not blockers(state, task), "dependencies_blocked", "task still has blockers",
            blockers=blockers(state, task))


def capture_epoch():
    if __package__:
        from . import qa_batch
    else:
        import qa_batch
    source = qa_batch.fingerprint()
    paths = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                                     "--", "tests", "planner", "packages.json", "pyproject.toml", "uv.lock"], cwd=ROOT)
    hashes = {}
    for raw in sorted(set(paths.split(b"\0")) - {b""}):
        relative = raw.decode("utf-8")
        path = ROOT / relative
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
    pin = ROOT / "gamelab/build_id.json"
    return {"native": source, "supplementary": hashes, "build": read_json(pin) if pin.is_file() else None,
            "limitations": "Ignored generated inputs/archives require separate per-case hashes."}


def batch_evidence(args, state):
    if __package__:
        from . import qa_batch
    else:
        import qa_batch
    rows = [json.loads(line) for line in Path(args.journal).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    require(all(isinstance(row, dict) for row in rows), "invalid_journal", "journal rows must be objects")
    matches = [row for row in rows if row.get("index") == args.index]
    require(len(matches) == 1, "invalid_journal", "need exactly one indexed batch row")
    row = matches[0]
    record = row.get("result") or {}
    require(isinstance(record, dict), "invalid_journal", "result must be an object")
    require(isinstance(record.get("teardown", {}), dict) and isinstance(record.get("assertions", []), list)
            and all(isinstance(item, dict) for item in record.get("assertions", [])),
            "invalid_journal", "malformed teardown/assertions")
    run_id = row.get("run_id") or "NO_RESULT"
    require(re.fullmatch(r"[A-Za-z0-9_-]+", run_id), "invalid_journal", "unsafe run ID")
    directory = ROOT / "gamelab/results" / run_id
    inner_ok = False
    if (directory / "run.json").is_file() and (directory / "inner.json").is_file():
        inner = read_json(directory / "inner.json")
        require(isinstance(inner, dict), "invalid_journal", "inner result must be an object")
        inner_ok = (read_json(directory / "run.json") == record
                    and qa_batch.inner_matches_outer(record, inner, row.get("scenario")))
    passed = (row.get("ok") is True and row.get("exit") == 0 and not row.get("problems")
              and qa_batch.successful(record, row.get("scenario")) and inner_ok)
    return {"scope": args.scope, "outcome": "pass" if passed else "fail", "epoch": args.epoch,
            "expected": args.expected, "observed": args.observed, "reviewer": args.reviewer,
            "artifacts": [str(args.journal), str(directory / "run.json"), str(directory / "inner.json")],
            "command": ["python", "-m", "gamelab", "run", row.get("scenario"), "--mode", "lab"],
            "exit": row.get("exit", -1) if type(row.get("exit")) is int else -1,
            "build": record.get("build"), "run_id": run_id, "scenario": row.get("scenario") or "unknown",
            "check": row.get("scenario"), "source_before": row.get("source_before"), "source_after": row.get("source_after"),
            "verdict": record.get("verdict"), "error": record.get("error"), "partial": record.get("partial"),
            "build_drift": record.get("build_drift"), "teardown_clean": record.get("teardown", {}).get("clean"),
            "assertions_ok": bool(record.get("assertions")) and all(item.get("ok") is True for item in record.get("assertions", [])),
            "problems": row.get("problems", []), "raw_result_checked": inner_ok}


def pool_evidence(args, state):
    """Read a final pool child from its explicit slot tree, never embedded PASS alone."""
    if __package__:
        from . import qa_batch
    else:
        import qa_batch

    read_hashes = {}

    def path(value):
        require(isinstance(value, (str, Path)) and bool(str(value)), "invalid_pool", "missing artifact path")
        candidate = Path(value)
        candidate = candidate if candidate.is_absolute() else ROOT / candidate
        require(".." not in candidate.parts and candidate.is_relative_to(ROOT), "invalid_pool", "artifact escapes repository")
        for item in (candidate, *candidate.parents):
            info = item.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                    "invalid_pool", "redirected pool artifact")
            if item == ROOT:
                break
        require(candidate == candidate.resolve(), "invalid_pool", "aliased pool artifact")
        return candidate

    def artifact(value, wanted=None):
        target = path(value)
        info = target.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 16 * 1024 * 1024,
                "invalid_pool", "pool artifact is not a bounded independent regular file")
        raw = target.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(str(target) not in read_hashes or read_hashes[str(target)] == digest,
                "invalid_pool", "pool artifact changed during read")
        read_hashes[str(target)] = digest
        if wanted is not None:
            require(isinstance(wanted, str) and re.fullmatch(r"[0-9a-f]{64}", wanted)
                    and hashlib.sha256(raw).hexdigest() == wanted, "invalid_pool", "pool artifact hash changed")
        return target, raw

    def strict_json(raw):
        def pairs(items):
            result = {}
            for key, value in items:
                require(key not in result, "invalid_pool", "duplicate JSON key")
                result[key] = value
            return result
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        json.dumps(value, allow_nan=False)
        return value

    def object_at(value, wanted=None):
        target, raw = artifact(value, wanted)
        value = strict_json(raw.decode("utf-8-sig"))
        require(isinstance(value, dict), "invalid_pool", "pool artifact must be a JSON object")
        return target, value

    def pinned(value):
        require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid_pool", "missing artifact hash")
        return value

    receipt_path, parent = object_at(args.journal)
    label = parent.get("label")
    require(isinstance(label, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", label)
            and receipt_path == ROOT / "gamelab/results" / ("pool-" + label) / "pool.json",
            "invalid_pool", "receipt must identify its exact pool output")
    children = parent.get("children")
    require(isinstance(children, list) and 0 < len(children) <= 128 and all(isinstance(row, dict) for row in children),
            "invalid_pool", "missing pool children")
    indices = [row.get("index") for row in children]
    require(all(type(index) is int and index > 0 for index in indices) and len(set(indices)) == len(indices),
            "invalid_pool", "duplicate/invalid child index")
    matches = [row for row in children if row["index"] == args.index]
    require(len(matches) == 1, "invalid_pool", "need exactly one indexed pool child")
    row = matches[0]
    require(args.epoch in state["epochs"], "invalid_pool", "unknown evidence epoch")
    expected_source = state["epochs"][args.epoch]["native"]
    require(parent.get("source_before") == expected_source == parent.get("source_after")
            and row.get("source_before") == expected_source == row.get("source_after")
            and parent.get("source_stable") is True, "invalid_pool", "pool/child source pins do not match epoch")
    require(parent.get("games_after") == [] and parent.get("global_games_absent") is True
            and parent.get("registered_games_absent") is True and parent.get("all_cli_handles_terminal") is True
            and parent.get("slot_leases_absent") is True and parent.get("pool_closed") is True
            and parent.get("lease_retained") is False and parent.get("requires_owned_descendant_audit") is False
            and isinstance(parent.get("teardown"), dict) and parent["teardown"].get("clean") is True,
            "invalid_pool", "parent lifetime/source finality is incomplete")
    manifest = parent.get("pool")
    require(isinstance(manifest, dict) and manifest.get("version") == 1 and manifest.get("closed") is False,
            "invalid_pool", "missing initial pool manifest")
    pool_id, token = manifest.get("pool_id"), manifest.get("token")
    require(isinstance(pool_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", pool_id)
            and isinstance(token, str) and re.fullmatch(r"[0-9a-f]{32}", token), "invalid_pool", "invalid pool identity")
    pool_root = ROOT / "gamelab/env/userdata/workers" / pool_id
    require(Path(manifest["manifest_path"]) == pool_root / "pool.json" and manifest.get("source") == expected_source,
            "invalid_pool", "pool manifest root/source mismatch")
    manifest_path, closed = object_at(manifest["manifest_path"], pinned(parent.get("pool_manifest_after_sha256")))
    require(closed == dict(manifest, closed=True), "invalid_pool", "final pool manifest is not the exact closed identity")
    slots = manifest.get("slots")
    require(isinstance(slots, list) and len(slots) == 2 and all(isinstance(slot, dict) for slot in slots),
            "invalid_pool", "pool must identify two slots")
    jobs = parent.get("named_jobs_empty")
    require(isinstance(jobs, dict) and set(jobs) == {slot.get("job_name") for slot in slots}
            and all(value is True for value in jobs.values()), "invalid_pool", "named owned jobs are not final")
    for index, slot in enumerate(slots, 1):
        sid = f"worker-{index}"
        require(slot.get("slot_id") == sid and Path(slot["game_dir"]) == pool_root / sid / "game"
                and Path(slot["results"]) == ROOT / "gamelab/results/workers" / pool_id / sid
                and slot.get("desktop_name") == f"gamelab_{pool_id}_{index}_{token[:8]}"
                and slot.get("job_name") == f"gamelab_job_{pool_id}_{index}_{token[:8]}",
                "invalid_pool", "slot roots/desktop/job identity mismatch")
    require(type(row.get("slot_index")) is int and row["slot_index"] in (0, 1), "invalid_pool", "invalid slot index")
    slot = slots[row["slot_index"]]
    run_id, scenario = row.get("run_id"), row.get("scenario")
    require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", run_id)
            and isinstance(scenario, str) and re.fullmatch(r"[A-Za-z0-9_-]+", scenario), "invalid_pool", "unsafe run/scenario identity")
    directory = path(row.get("results"))
    require(directory.parent == Path(slot["results"]) and directory.name == run_id
            and run_id == f"case-{args.index:04d}-{scenario}-lab", "invalid_pool", "child results do not identify the indexed slot run")
    run_path, record = object_at(directory / "run.json", pinned(row.get("run_sha256")))
    inner_path, inner = object_at(directory / "inner.json", pinned(row.get("inner_sha256")))
    teardown_path = receipt_path.parent / f"child-{args.index:04d}.teardown.json"
    require(Path(row.get("teardown_copy", "")) == teardown_path, "invalid_pool", "wrong immutable slot teardown copy")
    teardown_path, teardown = object_at(teardown_path, pinned(row.get("teardown_sha256")))
    expected_slot = {key: slot[key] for key in ("slot_id", "game_dir", "desktop_name", "job_name")}
    expected_slot["pool_id"] = pool_id
    require(record == row.get("result") and record.get("runtime_slot") == expected_slot
            and record.get("scenario") == scenario and teardown == record.get("teardown") == row.get("teardown")
            and teardown.get("run") == run_id, "invalid_pool", "raw child/runtime slot/teardown identity mismatch")
    logs = []
    for suffix in ("stdout", "stderr"):
        log, _ = artifact(receipt_path.parent / f"child-{args.index:04d}.{suffix}", pinned(row.get(suffix + "_sha256")))
        logs.append(str(log))
    consumer = None
    admission = row.get("admission")
    if parent.get("catalog") is not None or admission is not None:
        from gamelab.catalog import load_catalog
        from gamelab.consumer_evidence import validate_consumers
        catalog = parent.get("catalog")
        require(isinstance(catalog, dict) and catalog.get("stable") is True and parent.get("closure_stable") is True
                and manifest.get("catalog") == catalog.get("snapshot"), "invalid_pool", "catalog snapshot identity mismatch")
        snapshot = catalog["snapshot"]
        snapshot_path, _ = object_at(snapshot["path"], pinned(snapshot.get("sha256")))
        require(snapshot_path.parent == receipt_path.parent, "invalid_pool", "catalog snapshot outside pool output")
        descriptor = load_catalog(snapshot_path, snapshot["sha256"])
        entries = [entry for entry in descriptor["cases"] if entry["id"] == scenario]
        require(len(entries) == 1, "invalid_pool", "scenario absent/duplicated in frozen catalog")
        entry = entries[0]
        expected_admission = {key: entry[key] for key in ("id", "task", "check", "scope", "expected", "predicates", "lifecycle", "private_writes", "review")}
        closure_sha = hashlib.sha256(json.dumps(entry["closure"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        expected_admission.update(schema_version=descriptor["schema_version"], catalog_id=descriptor["catalog_id"],
                                  catalog_sha256=snapshot["sha256"], closure_sha256=closure_sha,
                                  files=entry["closure"]["files"], consumers=entry.get("consumers", []))
        require(admission == expected_admission and entry["status"] == "reviewed" and entry["lifecycle"] != "exclusive",
                "invalid_pool", "child admission differs from frozen catalog")
        mechanical = parent.get("mechanical_admission")
        require(admission in catalog.get("admissions", []) and isinstance(mechanical, dict)
                and mechanical.get("valid") is True and mechanical.get("catalog_sha256") == snapshot["sha256"]
                and {"scenario": scenario, "closure_sha256": closure_sha, "review_and_closure_current": True}
                in mechanical.get("checks", []), "invalid_pool", "missing original catalog admission context")
        scenario_path = receipt_path.parent / f"child-{args.index:04d}.scenario.json"
        require(Path(row.get("scenario_copy", "")) == scenario_path and row.get("scenario_sha256") == admission["files"].get(entry["scenario"]),
                "invalid_pool", "frozen scenario identity mismatch")
        _, scenario_data = object_at(scenario_path, pinned(row.get("scenario_sha256")))
        require(scenario_data.get("name") == scenario and scenario_data.get("fixture") == entry["closure"]["fixture"],
                "invalid_pool", "frozen scenario name/fixture mismatch")
        steps = scenario_data.get("steps")
        require(isinstance(steps, list) and all(isinstance(step, dict) for step in steps), "invalid_pool", "malformed scenario steps")
        require([{ "step": i, "expect": step["expect"]} for i, step in enumerate(steps) if "expect" in step]
                == admission["predicates"], "invalid_pool", "frozen scenario predicate mismatch")
        bot_records = []
        require(row.get("bot_results") is not None or
                (not any(step.get("do") == "bot" for step in steps) and row.get("bot_results_sha256") is None),
                "invalid_pool", "missing completed bot results")
        if row.get("bot_results") is not None:
            bot_path = directory / "bot-results.jsonl"
            require(Path(row["bot_results"]) == bot_path, "invalid_pool", "bot result path outside indexed run")
            _, bot_raw = artifact(bot_path, pinned(row.get("bot_results_sha256")))
            lines = bot_raw.decode("utf-8-sig").splitlines()
            require(all(line.strip() for line in lines), "invalid_pool", "blank bot result record")
            bot_records = [strict_json(line) for line in lines]
            require(all(isinstance(item, dict) for item in bot_records), "invalid_pool", "malformed bot result rows")
        consumer = validate_consumers(admission, scenario_data, bot_records)
        require(row.get("consumer_validation") == consumer, "invalid_pool", "stored consumer validation differs from raw rows")
    inner_ok = qa_batch.inner_matches_outer(record, inner, scenario)
    live = record.get("live")
    passed = (row.get("ok") is True and type(row.get("exit")) is int and row["exit"] == 0
              and row.get("terminal") is True and row.get("timed_out") is False and row.get("problems") == []
              and teardown.get("clean") is True and qa_batch.successful(record, scenario) and inner_ok
              and isinstance(live, list) and bool(live)
              and (consumer is None or consumer.get("valid") is True)
              and all(isinstance(item, dict) and item.get("owned_job") is True and item.get("registered_slot") is True for item in live))
    return {"scope": args.scope, "outcome": "pass" if passed else "fail", "epoch": args.epoch,
            "expected": args.expected, "observed": args.observed, "reviewer": args.reviewer,
            "artifacts": [str(receipt_path), str(manifest_path), str(run_path), str(inner_path), str(teardown_path), *logs],
            "command": ["python", "-m", "gamelab", "run", scenario, "--mode", "lab"],
            "exit": row["exit"] if type(row.get("exit")) is int else -1, "build": record.get("build"),
            "run_id": run_id, "scenario": scenario, "check": scenario, "source_before": row["source_before"],
            "source_after": row["source_after"], "verdict": record.get("verdict"), "error": record.get("error"),
            "partial": record.get("partial"), "build_drift": record.get("build_drift"),
            "teardown_clean": teardown.get("clean"), "assertions_ok": bool(record.get("assertions")) and all(isinstance(item, dict) and item.get("ok") is True for item in record.get("assertions", [])),
            "raw_result_checked": inner_ok, "runtime_slot": expected_slot, "pool_child_index": args.index,
            "parent_pool_ok": parent.get("ok"), "parent_pool_exit": parent.get("exit_code"),
            "parent_pool_problems": parent.get("problems"), "parent_finality_checked": True,
            "catalog_admission": admission, "consumer_validation": consumer, "artifact_sha256": read_hashes}


def pool_import_spec(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        info = item.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "invalid_bundle", "redirected bundle path")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 16 * 1024 * 1024,
            "invalid_bundle", "bundle must be a bounded independent regular file")
    raw = path.read_bytes()
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "invalid_bundle", "duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    json.dumps(value, allow_nan=False)
    return path, hashlib.sha256(raw).hexdigest(), value


def stage_pool_import(state, spec, verify_all=False):
    require(isinstance(spec, dict) and set(spec) <= {"schema_version", "imports", "verify_complete"}
            and type(spec.get("schema_version")) is int and spec["schema_version"] == 1,
            "invalid_bundle", "unsupported bundle schema")
    rows = spec.get("imports")
    require(isinstance(rows, list) and 0 < len(rows) <= 128, "invalid_bundle", "bundle requires 1..128 imports")
    staged, pins, seen = [], {}, set()
    required = {"task", "journal", "index", "epoch", "scope", "check", "expected", "observed", "reviewer", "expect", "token"}
    for row in rows:
        require(isinstance(row, dict) and required <= set(row) <= required | {"scenario"}, "invalid_bundle", "incomplete/unknown import fields")
        for key in required - {"index", "expect"}:
            text_field(row[key], key)
        require(type(row["index"]) is int and 1 <= row["index"] <= 128, "invalid_bundle", "invalid child index")
        require(row["task"] in state["tasks"], "unknown_task", "unknown import task")
        task = state["tasks"][row["task"]]
        require(type(row["expect"]) is int and isinstance(row["token"], str), "invalid_bundle", "task CAS/token required")
        args = argparse.Namespace(**row)
        claim = authorized(task, args)
        deps = {name: state["tasks"][name]["revision"] for name in task["depends_on"]}
        require(claim.get("dependencies") == deps and not blockers(state, task), "dependencies_changed", "import prerequisites changed or are unmet")
        require(row["scope"] in NATIVE_SCOPES and row["scope"] in task["required_scopes"]
                and row["check"] in task["checks"], "invalid_bundle", "import scope/check not declared by task")
        key = (row["task"], str(Path(row["journal"]).absolute()), row["index"], row["epoch"], row["scope"], row["check"])
        require(key not in seen, "invalid_bundle", "duplicate import")
        seen.add(key)
        identity = (row["expect"], row["token"])
        require(row["task"] not in pins or pins[row["task"]] == identity, "invalid_bundle", "inconsistent task CAS pins")
        pins[row["task"]] = identity
        evidence = pool_evidence(args, state)
        require(evidence["scenario"] == row.get("scenario", row["check"]), "invalid_bundle", "actual scenario differs from explicit mapping")
        admission = evidence.get("catalog_admission")
        if admission is not None:
            require(all(row[key] == admission[key] for key in ("task", "check", "scope")),
                    "invalid_bundle", "import labels differ from catalog admission")
        evidence["check"] = row["check"]
        evidence_valid(evidence, state)
        staged.append((args, evidence))
    verify = spec.get("verify_complete", [])
    require(isinstance(verify, list) and all(isinstance(name, str) for name in verify)
            and len(verify) == len(set(verify)) and set(verify) <= set(pins), "invalid_bundle", "verification must name unique imported tasks")
    return staged, set(pins) if verify_all else set(verify)


def record_pool_bundle(store, args):
    bundle_path, bundle_sha, spec = pool_import_spec(args.bundle)
    staged, verify = stage_pool_import(store.load(), spec, args.verify_complete)
    with store.writer():
        state = store.load()
        require(pool_import_spec(bundle_path)[1] == bundle_sha, "invalid_bundle", "bundle changed after staging")
        current, current_verify = stage_pool_import(state, spec, args.verify_complete)
        require(current_verify == verify and [value for _, value in current] == [value for _, value in staged],
                "invalid_bundle", "raw pool evidence changed after staging")
        owners, counts = {}, Counter()
        for item, evidence in current:
            task = state["tasks"][item.task]
            claim = task["claim"]
            owners[item.task] = claim["owner"]
            task["evidence"].append(dict(evidence, recorded_at=stamp(), attempt=claim["attempt"],
                                         dependencies=dict(claim["dependencies"]), bundle=str(bundle_path), bundle_sha256=bundle_sha))
            counts[item.task] += 1
        for name in sorted(verify):
            task = state["tasks"][name]
            require("verified" in TRANSITIONS[task["status"]], "invalid_transition", "task cannot verify from its current status")
            verification_ready(task, state)
            task.update(status="verified", verified_epoch=state["current_epoch"],
                        verified_dependencies={key: state["tasks"][key]["revision"] for key in task["depends_on"]}, claim=None)
        state["revision"] += 1
        for name in counts:
            task = state["tasks"][name]
            task["revision"] += 1
            state["history"].append(dict(command="record-pool-bundle", task=name, actor=owners[name],
                                         at=stamp(), revision=state["revision"], imports=counts[name], verified=name in verify,
                                         bundle=str(bundle_path), bundle_sha256=bundle_sha))
        store.save(state)
        return {"campaign_revision": state["revision"], "result": {"imported": len(current), "verified": sorted(verify),
                "tasks": [mutation_task_view(state, state["tasks"][name], owners[name], store.path, args) for name in counts]}}


def plan_pool_import(store, args):
    """Propose labels from frozen admissions; actual-result reviewer text is explicit."""
    journal, _, pool = pool_import_spec(args.journal)
    require(isinstance(pool, dict) and isinstance(pool.get("children"), list)
            and all(isinstance(row, dict) for row in pool["children"]), "invalid_bundle", "pool receipt required")
    selected = args.index or [row.get("index") for row in pool["children"]]
    require(selected and len(selected) == len(set(selected)), "invalid_bundle", "select unique pool indexes")
    state = store.load()
    imports = []
    for index in selected:
        rows = [row for row in pool["children"] if row.get("index") == index]
        require(len(rows) == 1 and isinstance(rows[0].get("admission"), dict), "invalid_bundle", "explicit catalog admission required for planning")
        row, admission = rows[0], rows[0]["admission"]
        require(admission.get("task") in state["tasks"], "unknown_task", "catalog task must already exist")
        task = state["tasks"][admission["task"]]
        require(task.get("claim") is not None, "claim_conflict", "claim catalog task explicitly before planning")
        imports.append(dict(task=task["id"], journal=str(journal), index=index, scenario=row["scenario"], epoch=args.epoch,
                            check=admission["check"], scope=admission["scope"], expected=admission["expected"],
                            observed=args.observed, reviewer=args.reviewer, expect=task["revision"], token=task["claim"]["token"]))
    spec = {"schema_version": 1, "imports": imports,
            "verify_complete": sorted({row["task"] for row in imports}) if args.verify_complete else []}
    stage_pool_import(state, spec)
    return {"read_only": True, "requires_semantic_review": True, "bundle": spec}


def mutate(store, args):
    with store.writer():
        if args.command == "init":
            require(not store.path.exists(), "already_initialized", "init never replaces existing state")
            seed = read_json(args.seed)
            tasks = [new_task(row) for row in seed["tasks"]]
            require(len({task["id"] for task in tasks}) == len(tasks), "duplicate_task", "duplicate seed IDs")
            state = {"schema_version": SCHEMA, "campaign": seed["campaign"], "revision": 0,
                     "runtime_owner": seed.get("runtime_owner", "runtime"), "integrator": seed.get("integrator", "integrator"),
                     "phase": "idle", "freeze": None, "current_epoch": None, "epochs": {},
                     "agent_limits": seed.get("agent_limits", {"initial": 32, "working_max": 48, "hard_max": 100}),
                     "tasks": {task["id"]: task for task in tasks}, "history": []}
            event = {"action": "init", "actor": "coordinator"}
            result = {"campaign": state["campaign"], "tasks": len(tasks)}
        else:
            state = store.load()
            event = {"action": args.command}
            if args.command in ("add", "epoch", "phase"):
                require(args.expect == state["revision"], "revision_conflict", "reread campaign before updating",
                        expected=args.expect, actual=state["revision"])
                event["actor"] = args.actor
                if args.command == "add":
                    task = new_task(read_json(args.file))
                    require(task["id"] not in state["tasks"], "duplicate_task", "task already exists")
                    state["tasks"][task["id"]] = task
                    result = task
                elif args.command == "epoch":
                    require(state["phase"] == "idle", "source_frozen", "cannot change epoch while frozen")
                    require(args.id not in state["epochs"], "epoch_exists", "epoch IDs are immutable")
                    require(ID.fullmatch(args.id), "invalid_source", "invalid epoch ID")
                    epoch = read_json(args.file) if args.file else capture_epoch()
                    source_valid(epoch["native"])
                    state["epochs"][args.id] = dict(epoch, recorded_at=stamp(), actor=args.actor)
                    state["current_epoch"] = args.id
                    result = {"epoch": args.id, "source": epoch}
                else:
                    require(args.actor == state["runtime_owner"], "runtime_owner", "only the designated runtime owner records freeze changes")
                    if args.value == "frozen":
                        require(state["phase"] == "idle" and state["current_epoch"], "phase_conflict", "freeze requires idle phase and pinned epoch")
                        require(not any(task["claim"] and task["operation"] == "integration" for task in state["tasks"].values()),
                                "writer_active", "integration claims must be released before freezing, including expired claims")
                        state["freeze"] = {"owner": args.actor, "reason": args.reason, "epoch": state["current_epoch"], "at": stamp()}
                    else:
                        require(state["phase"] == "frozen", "phase_conflict", "tracker is not frozen")
                        require(not any(task["claim"] and task["operation"] == "native" for task in state["tasks"].values()),
                                "runtime_active", "release native task claims after diagnosing clean teardown first")
                        state["freeze"] = None
                    state["phase"] = args.value
                    event["reason"] = args.reason
                    result = {"phase": state["phase"], "freeze": state["freeze"]}
            else:
                require(args.id in state["tasks"], "unknown_task", "unknown task ID", task=args.id)
                task = state["tasks"][args.id]
                require(args.expect == task["revision"], "revision_conflict", "reread task before updating",
                        expected=args.expect, actual=task["revision"])
                event["task"] = task["id"]
                if args.command == "reopen":
                    require(args.actor == "coordinator", "wrong_role", "only coordinator explicitly reopens completed work")
                    require(task["status"] == "verified" and state["phase"] == "idle", "reopen_refused",
                            "reopen requires verified task and idle phase; retained evidence is historical")
                    task["status"] = "queued"
                    task["summary"], task["next_action"] = args.reason, args.next_action
                    event.update(actor=args.actor, reason=args.reason)
                elif args.command == "amend":
                    require(args.actor == "coordinator", "wrong_role", "only coordinator amends task definitions")
                    require(state["phase"] == "idle", "source_frozen", "definition amendment requires an idle campaign")
                    require(task["claim"] is None, "already_claimed", "owner must release the task claim first, including expired claims")
                    require(task["status"] != "verified", "terminal_task", "verified work requires explicit reopen before amendment")
                    text_field(args.reason, "reason")
                    text_field(args.next_action, "next_action")
                    before = task_definition(task)
                    replacements = amend_definition(state, task, read_json(args.file))
                    if task["status"] != "deferred":
                        task["status"] = "queued"
                    task["summary"], task["next_action"] = args.reason, args.next_action
                    event.update(actor=args.actor, reason=args.reason, before_definition=before,
                                 after_definition=task_definition(task), replaced_dependencies=replacements)
                elif args.command == "defer":
                    require(args.actor == "coordinator", "wrong_role", "only coordinator administratively defers unclaimed work")
                    require(state["phase"] == "idle", "source_frozen", "administrative deferral requires an idle campaign")
                    require(task["claim"] is None, "already_claimed", "owner must release the task claim first, including expired claims")
                    require(task["status"] != "verified", "terminal_task", "verified work requires explicit reopen before deferral")
                    text_field(args.reason, "reason")
                    text_field(args.next_action, "next_action")
                    task["status"] = "deferred"
                    task["summary"], task["next_action"] = args.reason, args.next_action
                    event.update(actor=args.actor, reason=args.reason)
                elif args.command == "claim":
                    require(task["status"] != "verified", "terminal_task", "verified tasks are immutable; add a new retest task")
                    require(not blockers(state, task), "dependencies_blocked", "task has unresolved blockers", blockers=blockers(state, task))
                    role = {"native": state["runtime_owner"], "integration": state["integrator"]}.get(task["operation"])
                    require(not role or role == args.owner, "wrong_role", f"operation requires owner {role}")
                    if task["claim"]:
                        require(task["claim"]["expires"] <= time.time(), "already_claimed", "task has a live claim")
                        require(args.reclaim and args.reason and task["operation"] not in ("native", "integration"),
                                "explicit_handoff", "expired offline claims need --reclaim --reason; native/integration require explicit owner release")
                        event["previous_claim"] = task["claim"]
                    attempt = uuid.uuid4().hex
                    task["claim"] = {"owner": args.owner, "token": uuid.uuid4().hex, "attempt": attempt,
                                     "expires": time.time() + args.lease_minutes * 60,
                                     "epoch": state["current_epoch"],
                                     "dependencies": {key: state["tasks"][key]["revision"] for key in task["depends_on"]},
                                     "artifacts": f"gamelab/results/swarm/{state['campaign']}/{task['id']}/{attempt}/"}
                    if task["status"] == "queued":
                        task["status"] = "reviewing"
                    event.update(actor=args.owner, reason=args.reason)
                else:
                    claim = authorized(task, args, allow_expired=args.command == "release")
                    event["actor"] = claim["owner"]
                    if args.command == "release":
                        task["claim"] = None
                        task["summary"], task["next_action"] = args.summary, args.next_action
                        if task["status"] == "reviewing":
                            task["status"] = "queued"
                    else:
                        evidence = pool_evidence(args, state) if args.command == "record-pool" else batch_evidence(args, state) if args.command == "record-batch" else (
                            read_json(args.evidence) if args.evidence else None)
                        if evidence is not None:
                            evidence_valid(evidence, state)
                            task["evidence"].append(dict(evidence, recorded_at=stamp(), attempt=claim["attempt"],
                                                        dependencies=dict(claim["dependencies"])))
                        if args.command == "update":
                            if args.summary:
                                task["summary"] = args.summary
                            if args.next_action:
                                task["next_action"] = args.next_action
                            if args.status and args.status != task["status"]:
                                require(args.status in TRANSITIONS[task["status"]], "invalid_transition", "invalid task transition")
                                if args.status == "verified":
                                    verification_ready(task, state)
                                    task["verified_epoch"] = state["current_epoch"]
                                    task["verified_dependencies"] = {key: state["tasks"][key]["revision"] for key in task["depends_on"]}
                                    task["claim"] = None
                                if args.status in ("harness-blocked", "deferred", "fix-drafted", "reviewed", "integrated"):
                                    require(args.summary and args.next_action, "checkpoint_required", "transition needs --summary and --next-action")
                                if args.status == "integrated":
                                    require(state["phase"] == "idle" and claim["owner"] == state["integrator"],
                                            "integration_refused", "only integrator may record integration at an idle boundary")
                                task["status"] = args.status
                        if task["claim"]:
                            task["claim"]["expires"] = time.time() + args.lease_minutes * 60
                task["revision"] += 1
                result = copy.deepcopy(task)
        state["revision"] += 1
        state["history"].append(dict(event, at=stamp(), revision=state["revision"],
                                     summary=result.get("summary"), next_action=result.get("next_action")))
        store.save(state)
        if result.get("id") in state["tasks"]:
            result = mutation_task_view(state, state["tasks"][result["id"]], event.get("actor"), store.path, args)
        return {"campaign_revision": state["revision"], "result": result}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refused("invalid_arguments", message)


def response_options(command):
    command.add_argument("--evidence-limit", type=int, default=0, help="raw evidence rows in task receipt; default0")
    command.add_argument("--evidence-offset", type=int, default=0, help="skip this many latest evidence rows")
    command.add_argument("--history-limit", type=int, default=0, help="raw history rows in task receipt; default0")
    command.add_argument("--history-offset", type=int, default=0, help="skip this many latest history rows")


def parser():
    result = Parser(description=__doc__)
    result.add_argument("--state", type=Path, default=DEFAULT_STATE)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("schema")
    init = sub.add_parser("init")
    init.add_argument("--seed", type=Path, required=True)
    for name in ("status", "resume", "next"):
        query = sub.add_parser(name)
        query.add_argument("--owner")
        query.add_argument("--limit", type=int, default=5)
        query.add_argument("--owned-offset", type=int, default=0)
        query.add_argument("--ready-offset", type=int, default=0)
        query.add_argument("--blocked-offset", type=int, default=0)
        query.add_argument("--at-revision", type=int, help="refuse a changed campaign while paging")
    show = sub.add_parser("show")
    show.add_argument("id")
    show.add_argument("--owner")
    show.add_argument("--history-limit", type=int, default=5)
    show.add_argument("--evidence-limit", type=int, help="default follows legacy history-limit")
    show.add_argument("--history-offset", type=int, default=0)
    show.add_argument("--evidence-offset", type=int, default=0)
    show.add_argument("--at-task-revision", type=int, help="refuse changed task details while paging")
    for name in ("add", "epoch", "phase"):
        command = sub.add_parser(name)
        command.add_argument("--expect", type=int, required=True)
        command.add_argument("--actor", required=True)
        if name == "add":
            response_options(command)
            command.add_argument("--file", type=Path, required=True)
        elif name == "epoch":
            command.add_argument("id")
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--file", type=Path)
            source.add_argument("--capture", action="store_true")
        else:
            command.add_argument("value", choices=("idle", "frozen"))
            command.add_argument("--reason", required=True)
    reopen = sub.add_parser("reopen")
    reopen.add_argument("id")
    reopen.add_argument("--expect", type=int, required=True)
    reopen.add_argument("--actor", required=True)
    reopen.add_argument("--reason", required=True)
    reopen.add_argument("--next-action", required=True)
    response_options(reopen)
    defer = sub.add_parser("defer", help="coordinator disposition of idle unclaimed work, even with blocked prerequisites")
    defer.add_argument("id")
    defer.add_argument("--expect", type=int, required=True)
    defer.add_argument("--actor", required=True)
    defer.add_argument("--reason", required=True)
    defer.add_argument("--next-action", required=True)
    response_options(defer)
    amend = sub.add_parser("amend", help="coordinator-only strengthening of idle unclaimed task definitions")
    amend.add_argument("id")
    amend.add_argument("--file", type=Path, required=True)
    amend.add_argument("--expect", type=int, required=True)
    amend.add_argument("--actor", required=True)
    amend.add_argument("--reason", required=True)
    amend.add_argument("--next-action", required=True)
    response_options(amend)
    bundle = sub.add_parser("record-pool-bundle", help="atomically import reviewed pool child mappings")
    bundle.add_argument("--bundle", type=Path, required=True)
    bundle.add_argument("--verify-complete", action="store_true", help="verify only imported tasks using existing requirements")
    response_options(bundle)
    plan = sub.add_parser("plan-pool-import", help="read-only proposal from frozen catalog admissions")
    plan.add_argument("--journal", "--receipt", type=Path, required=True)
    plan.add_argument("--epoch", required=True)
    plan.add_argument("--reviewer", required=True, help="reviewer of the ACTUAL native results, not inferred from source review")
    plan.add_argument("--observed", required=True)
    plan.add_argument("--index", type=int, action="append")
    plan.add_argument("--verify-complete", action="store_true")
    for name in ("claim", "update", "release", "record-batch", "record-pool"):
        command = sub.add_parser(name)
        command.add_argument("id")
        response_options(command)
        command.add_argument("--expect", type=int, required=True)
        if name == "claim":
            command.add_argument("--owner", required=True)
            command.add_argument("--reclaim", action="store_true")
            command.add_argument("--reason")
        else:
            command.add_argument("--token", required=True)
        if name != "release":
            command.add_argument("--lease-minutes", type=int, default=120)
        if name in ("update", "release"):
            command.add_argument("--summary", required=name == "release")
            command.add_argument("--next-action", required=name == "release")
        if name == "update":
            command.add_argument("--status", choices=STATUSES)
            command.add_argument("--evidence", type=Path)
        if name in ("record-batch", "record-pool"):
            command.add_argument("--journal", *( ["--receipt"] if name == "record-pool" else []), type=Path, required=True)
            command.add_argument("--index", type=int, required=True)
            command.add_argument("--epoch", required=True)
            command.add_argument("--scope", choices=sorted(NATIVE_SCOPES), required=True)
            for key in ("expected", "observed", "reviewer"):
                command.add_argument("--" + key, required=True)
    return result


def main(argv=None):
    command = None
    try:
        args = parser().parse_args(argv)
        command = args.command
        if hasattr(args, "lease_minutes"):
            require(1 <= args.lease_minutes <= 1440, "invalid_arguments", "lease minutes must be 1..1440")
        if hasattr(args, "limit"):
            require(1 <= args.limit <= 100, "invalid_arguments", "limit must be 1..100")
        for field in ("evidence_limit", "history_limit"):
            value = getattr(args, field, None)
            require(value is None or 0 <= value <= 100, "invalid_arguments", f"{field} must be0..100")
        for field in ("evidence_offset", "history_offset", "owned_offset", "ready_offset", "blocked_offset"):
            require(getattr(args, field, 0) >= 0, "invalid_arguments", f"{field} must be nonnegative")
        store = Store(args.state)
        if command == "schema":
            data = {"schema_version": SCHEMA, "statuses": STATUSES, "operations": OPERATIONS, "scopes": SCOPES,
                    "commands": ("schema", "init", "status", "resume", "next", "show", "add", "epoch", "phase", "claim", "update", "release", "record-batch", "record-pool", "record-pool-bundle", "plan-pool-import", "reopen", "defer", "amend"),
                    "amendment_fields": AMEND_FIELDS,
                    "amendment_replacements": "replace_deferred_dependencies",
                    "task_required": ("id", "title", "lane", "operation", "paths", "depends_on", "required_scopes", "checks", "next_action"),
                    "evidence_required": ("scope", "outcome", "epoch", "expected", "observed", "reviewer", "artifacts"),
                    "native_pass_required": ("command", "exit", "build", "run_id", "scenario", "source_before", "source_after", "verdict", "partial", "build_drift", "error", "teardown_clean", "assertions_ok"),
                    "error_exit": 2, "guide": "docs/qa/SWARM_TRACKER.md",
                    "safety": "Advisory bookkeeping only; leases never grant runtime ownership or source-edit permission."}
        elif command == "record-pool-bundle":
            data = record_pool_bundle(store, args)
        elif command == "plan-pool-import":
            data = plan_pool_import(store, args)
        elif command in ("status", "resume", "next", "show"):
            state = store.load()
            if command == "show":
                require(args.id in state["tasks"], "unknown_task", "unknown task ID")
                require(0 <= args.history_limit <= 100, "invalid_arguments", "history limit must be 0..100")
                data = card(state, state["tasks"][args.id], args.owner, store.path)
                task = state["tasks"][args.id]
                require(args.at_task_revision is None or args.at_task_revision == task["revision"],
                        "revision_conflict", "task changed while paging; reread its first page",
                        expected=args.at_task_revision, actual=task["revision"])
                data.update(detail_pages(state, task, args.owner, store.path,
                    args.history_limit if args.evidence_limit is None else args.evidence_limit,
                    args.evidence_offset, args.history_limit, args.history_offset))
            else:
                require(args.at_revision is None or args.at_revision == state["revision"],
                        "revision_conflict", "campaign changed while paging; reread its first page",
                        expected=args.at_revision, actual=state["revision"])
                data = packet(state, args.owner, args.limit, store.path, command=command,
                              owned_offset=args.owned_offset, ready_offset=args.ready_offset,
                              blocked_offset=args.blocked_offset)
                data["state_path"] = str(store.path)
                data["agent_guide"] = "docs/qa/SWARM_TRACKER.md"
        else:
            data = mutate(store, args)
        print(json.dumps({"schema_version": SCHEMA, "ok": True, "command": command, "data": data}, allow_nan=False))
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as error:
        print(json.dumps({"schema_version": SCHEMA, "ok": False, "command": command,
                          "error": {"code": getattr(error, "code", "invalid_or_unreadable_state"), "message": str(error),
                                    "details": getattr(error, "details", {})}}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
