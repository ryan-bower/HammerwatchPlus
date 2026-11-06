"""Tracker persistence, fencing and evidence checks; temporary trees only, no game."""
import concurrent.futures
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import qa_swarm as tracker


def task(key="H1-A", **changes):
    return dict(id=key, title="Inventory the assigned contracts", lane="H1", operation="review",
                paths=["tools/save_builder.py"], depends_on=[], required_scopes=["source"], checks=[],
                next_action="Read source and add bounded follow-up tasks.", **changes)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hwp-swarm-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state.json"
        self.seed = self.root / "seed.json"
        self.source = {"head": "a" * 40, "source_sha256": "b" * 64, "files": 3,
                       "fingerprint_scope": "mods+gamelab+tools-v2"}
        self.build = {"build_id": "test", "exe_sha256": "c" * 64}
        self.epoch = self.write("epoch.json", {"native": self.source, "supplementary": {}, "build": self.build})

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def call(self, *argv, ok=True):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = tracker.main(["--state", str(self.state), *map(str, argv)])
        record = json.loads(output.getvalue())
        self.assertEqual(code, 0 if ok else 2, record)
        self.assertEqual(record["ok"], ok)
        return record["data"] if ok else record["error"]

    def init(self, tasks=None):
        self.write("seed.json", {"campaign": "test-swarm", "tasks": tasks or [task()]})
        return self.call("init", "--seed", self.seed)

    def pin(self, key="E001"):
        return self.call("epoch", key, "--file", self.epoch, "--expect", self.load()["revision"], "--actor", "coordinator")

    def load(self):
        return tracker.Store(self.state).load()

    def claim(self, key="H1-A", owner="H1"):
        revision = self.load()["tasks"][key]["revision"]
        return self.call("claim", key, "--owner", owner, "--expect", revision)["result"]

    def update(self, claimed, *args, ok=True):
        return self.call("update", claimed["id"], "--expect", claimed["revision"],
                         "--token", claimed["claim"]["token"], *args, ok=ok)

    def release(self, claimed):
        return self.call("release", claimed["id"], "--expect", claimed["revision"], "--token", claimed["claim"]["token"],
                         "--summary", "Durable handoff", "--next-action", "Resume the saved next step")["result"]

    def evidence(self, **changes):
        record = {"scope": "source", "outcome": "pass", "epoch": "E001", "reviewer": "independent",
                  "expected": "Document every contract", "observed": "Inventory includes all owned paths",
                  "artifacts": ["docs/qa/review.md"]}
        record.update(changes)
        return self.write("evidence.json", record)

    def verify(self, key="H1-A", owner="H1"):
        claimed = self.claim(key, owner)
        return self.update(claimed, "--evidence", self.evidence(), "--status", "verified")["result"]

    def freeze(self, value="frozen", ok=True):
        return self.call("phase", value, "--expect", self.load()["revision"], "--actor", "runtime",
                         "--reason", "Owner has reviewed runtime state and source boundary.", ok=ok)

    def test_coordinator_can_defer_obsolete_native_after_prerequisite_reopens(self):
        self.init([task(), dict(task("OBSOLETE"), operation="native", required_scopes=["load"], depends_on=["H1-A"])])
        self.pin()
        prerequisite = self.verify()
        self.freeze()
        native = self.claim("OBSOLETE", "runtime")
        historical = self.update(native, "--evidence", self.evidence(outcome="fail", observed="Historical setup refused"))["result"]
        released = self.release(historical)
        self.freeze("idle")
        self.call("reopen", "H1-A", "--expect", prerequisite["revision"], "--actor", "coordinator",
                  "--reason", "Obsolete prerequisite changed", "--next-action", "Use replacement contract")
        before = self.load()
        self.assertIn("dependency:H1-A", tracker.blockers(before, before["tasks"]["OBSOLETE"]))
        original = self.state.read_bytes()
        refusal = self.call("claim", "OBSOLETE", "--owner", "runtime", "--expect", released["revision"], ok=False)
        self.assertEqual(refusal["code"], "dependencies_blocked")
        self.assertEqual(self.state.read_bytes(), original)
        refusal = self.call("update", "OBSOLETE", "--expect", released["revision"], "--token", "no-current-claim",
                            "--status", "deferred", "--summary", "Obsolete", "--next-action", "Keep replacement", ok=False)
        self.assertEqual(refusal["code"], "claim_conflict")
        self.assertEqual(self.state.read_bytes(), original)
        result = self.call("defer", "OBSOLETE", "--expect", released["revision"], "--actor", "coordinator",
                           "--reason", "Superseded by replacement task", "--next-action", "Retain historical evidence")["result"]
        after = self.load()
        self.assertEqual(result["status"], "deferred")
        self.assertIsNone(result["claim"])
        self.assertEqual(result["revision"], released["revision"] + 1)
        self.assertEqual(result["depends_on"], before["tasks"]["OBSOLETE"]["depends_on"])
        self.assertEqual(after["tasks"]["OBSOLETE"]["evidence"], before["tasks"]["OBSOLETE"]["evidence"])
        self.assertEqual(after["history"][:-1], before["history"])
        self.assertEqual(after["history"][-1]["action"], "defer")
        self.assertEqual(after["history"][-1]["actor"], "coordinator")
        self.assertEqual(after["history"][-1]["reason"], "Superseded by replacement task")
        self.assertEqual(result["next_action"], "Retain historical evidence")
        self.assertIn("dependency:H1-A", tracker.blockers(after, result))
        packet = self.call("resume", "--owner", "coordinator")
        self.assertNotIn("OBSOLETE", [row["id"] for row in packet["next_tasks"]])
        self.assertIn("OBSOLETE", [row["id"] for row in packet["blocked_tasks"]])
        self.assertFalse(packet["all_tasks_verified_current"])

    def test_coordinator_defer_fences_wrong_actor_and_stale_revision(self):
        self.init()
        original = self.state.read_bytes()
        args = ["defer", "H1-A", "--reason", "Superseded", "--next-action", "Retain replacement"]
        self.assertEqual(self.call(*args, "--actor", "H3", "--expect", 0, ok=False)["code"], "wrong_role")
        self.assertEqual(self.state.read_bytes(), original)
        self.assertEqual(self.call(*args, "--actor", "coordinator", "--expect", 1, ok=False)["code"], "revision_conflict")
        self.assertEqual(self.state.read_bytes(), original)

    def test_coordinator_defer_requires_nonempty_reason_and_next_action(self):
        self.init()
        original = self.state.read_bytes()
        for reason, action in (("", "Continue"), ("   ", "Continue"), ("Superseded", ""), ("Superseded", "   ")):
            with self.subTest(reason=reason, action=action):
                self.assertEqual(self.call("defer", "H1-A", "--expect", 0, "--actor", "coordinator",
                                          "--reason", reason, "--next-action", action, ok=False)["code"], "invalid_record")
                self.assertEqual(self.state.read_bytes(), original)

    def test_coordinator_defer_refuses_frozen_campaign(self):
        self.init()
        self.pin()
        self.freeze()
        original = self.state.read_bytes()
        self.assertEqual(self.call("defer", "H1-A", "--expect", 0, "--actor", "coordinator",
                                  "--reason", "Superseded", "--next-action", "Retain", ok=False)["code"], "source_frozen")
        self.assertEqual(self.state.read_bytes(), original)
        self.assertEqual(self.load()["phase"], "frozen")

    def test_coordinator_defer_never_overwrites_live_or_expired_claim(self):
        self.init()
        self.pin()
        claimed = self.claim()
        original = self.state.read_bytes()
        args = ["defer", "H1-A", "--expect", claimed["revision"], "--actor", "coordinator",
                "--reason", "Superseded", "--next-action", "Owner must release"]
        self.assertEqual(self.call(*args, ok=False)["code"], "already_claimed")
        self.assertEqual(self.state.read_bytes(), original)
        with patch.object(tracker.time, "time", return_value=claimed["claim"]["expires"] + 1):
            self.assertEqual(self.call(*args, ok=False)["code"], "already_claimed")
        self.assertEqual(self.state.read_bytes(), original)

    def test_coordinator_defer_requires_explicit_reopen_of_verified_task(self):
        self.init()
        self.pin()
        done = self.verify()
        original = self.state.read_bytes()
        self.assertEqual(self.call("defer", "H1-A", "--expect", done["revision"], "--actor", "coordinator",
                                  "--reason", "Superseded", "--next-action", "Reopen first", ok=False)["code"], "terminal_task")
        self.assertEqual(self.state.read_bytes(), original)
        self.assertTrue(self.call("show", "H1-A")["fresh_verified"])

    def test_coordinator_defer_is_discoverable_and_never_rewrites_dependency_graph(self):
        self.init([task(), dict(task("H1-B"), depends_on=["H1-A"])])
        self.assertIn("defer", self.call("schema")["commands"])
        before = self.load()
        result = self.call("defer", "H1-B", "--expect", 0, "--actor", "coordinator",
                           "--reason", "Superseded", "--next-action", "Use replacement")["result"]
        after = self.load()
        self.assertEqual(result["depends_on"], ["H1-A"])
        self.assertEqual(after["tasks"]["H1-A"], before["tasks"]["H1-A"])
        self.assertEqual(after["epochs"], before["epochs"])
        self.assertEqual(after["freeze"], before["freeze"])
        self.assertEqual(after["current_epoch"], before["current_epoch"])

    def replay_page(self, argv, ok=True):
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(Path(argv[1]).resolve(), Path(tracker.__file__).resolve())
        self.assertEqual(argv[2:4], ["--state", str(self.state.resolve())])
        return self.call(*argv[2:], ok=ok)

    def fill_evidence(self, count=23):
        self.init()
        self.pin()
        claimed = self.claim()
        for index in range(count):
            claimed = self.update(claimed, "--evidence", self.evidence(
                scope="load", command=["python", "-m", "gamelab", "run", "mod-all", "--mode", "lab"],
                exit=0, build=self.build, run_id="fake-mod-all-lab", scenario="mod-all",
                source_before=self.source, source_after=self.source, verdict="PASS", partial=False,
                build_drift=False, error=None, teardown_clean=True, assertions_ok=True,
                check="check-" + str(index), outcome="fail" if index == 2 else "pass",
                observed="NATIVE-SHAPED-PAYLOAD-" + str(index) + "x" * 12000))["result"]
        return claimed

    def test_owner_ready_and_blocked_packets_are_bounded_and_fully_retrievable(self):
        active = [task("ACTIVE-" + str(index)) for index in range(13)]
        ready = [task("READY-" + str(index)) for index in range(7)]
        blocked = [dict(task("BLOCKED-" + str(index)), depends_on=["PREREQUISITE"]) for index in range(9)]
        self.init([*active, *ready, *blocked, task("PREREQUISITE")])
        for item in active:
            self.claim(item["id"], "H3")
        original = self.state.read_bytes()
        canonical = self.load()
        for command in ("resume", "status", "next"):
            packet = self.call(command, "--owner", "H3", "--limit", 4)
            self.assertLessEqual(len(packet["owned_tasks"]), 4)
            self.assertEqual(packet["pagination"]["owned_tasks"]["total"], 13)
            for key, expected in (("owned_tasks", 13), ("next_tasks", 8), ("blocked_tasks", 9)):
                page, recovered = packet, []
                while True:
                    self.assertLessEqual(len(page[key]), 4)
                    self.assertEqual(page["pagination"][key]["returned"], len(page[key]))
                    recovered.extend(row["id"] for row in page[key])
                    for row in page[key] if key == "owned_tasks" else []:
                        claim = canonical["tasks"][row["id"]]["claim"]
                        self.assertEqual(row["claim"]["token"], claim["token"])
                        self.assertEqual(row["claim"]["attempt"], claim["attempt"])
                        self.assertEqual(row["paths"], canonical["tasks"][row["id"]]["paths"])
                        self.assertEqual(row["depends_on"], canonical["tasks"][row["id"]]["depends_on"])
                    continuation = page["pagination"][key]["next_argv"]
                    if continuation is None:
                        break
                    page = self.replay_page(continuation)
                self.assertEqual(len(recovered), expected)
                self.assertEqual(len(set(recovered)), expected)
        self.assertEqual(self.state.read_bytes(), original)

    def test_mutation_default_omits_large_payloads_but_preserves_claim_and_counts(self):
        result = self.fill_evidence(12)
        canonical = self.load()["tasks"][result["id"]]
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["history"], [])
        self.assertEqual(result["evidence_count"], 12)
        self.assertEqual(result["pagination"]["evidence"]["returned"], 0)
        self.assertEqual(result["latest_evidence"]["check"], "check-11")
        self.assertNotIn("NATIVE-SHAPED-PAYLOAD-", json.dumps(result))
        for key in ("id", "revision", "status", "paths", "depends_on", "required_scopes", "checks", "next_action", "claim"):
            self.assertEqual(result[key], canonical[key])
        self.assertEqual(len(canonical["evidence"]), 12)
        self.assertTrue(all(len(row["observed"]) > 12000 for row in canonical["evidence"]))
        self.assertIsNotNone(result["pagination"]["evidence"]["next_argv"])
        self.assertIsNotNone(result["pagination"]["history"]["next_argv"])

    def test_detail_pages_reconstruct_every_large_evidence_and_history_row(self):
        claimed = self.fill_evidence(23)
        canonical = self.load()
        original = self.state.read_bytes()
        legacy = self.call("show", claimed["id"], "--owner", "H1", "--history-limit", 5)
        self.assertEqual(legacy["evidence"], canonical["tasks"][claimed["id"]]["evidence"][-5:])
        first = self.call("show", claimed["id"], "--owner", "H1", "--evidence-limit", 4, "--history-limit", 3)
        for key, limit, expected in (("evidence", 4, canonical["tasks"][claimed["id"]]["evidence"]),
                                     ("history", 3, [row for row in canonical["history"] if row.get("task") == claimed["id"]])):
            page, pages = first, []
            while True:
                self.assertLessEqual(len(page[key]), limit)
                pages.append(page[key])
                self.assertEqual(page["pagination"][key]["total"], len(expected))
                continuation = page["pagination"][key]["next_argv"]
                if continuation is None:
                    break
                page = self.replay_page(continuation)
            recovered = [row for chunk in reversed(pages) for row in chunk]
            self.assertEqual(recovered, expected)
        compact = self.call("show", claimed["id"], "--evidence-limit", 0, "--history-limit", 0)
        self.assertEqual(compact["evidence"], [])
        self.assertEqual(compact["history"], [])
        self.assertEqual(compact["evidence_count"], 23)
        self.assertEqual(self.state.read_bytes(), original)

    def test_response_limits_offsets_and_snapshot_guards_fail_without_writes(self):
        claimed = self.fill_evidence(7)
        original = self.state.read_bytes()
        for arguments in (("resume", "--owned-offset", -1), ("status", "--ready-offset", -1),
                          ("next", "--blocked-offset", -1), ("show", claimed["id"], "--evidence-limit", 101),
                          ("show", claimed["id"], "--history-offset", -1),
                          ("update", claimed["id"], "--expect", claimed["revision"], "--token", claimed["claim"]["token"], "--evidence-limit", -1)):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.call(*arguments, ok=False)["code"], "invalid_arguments")
                self.assertEqual(self.state.read_bytes(), original)
        packet = self.call("resume", "--owner", "H1", "--limit", 1)
        detail = self.call("show", claimed["id"], "--evidence-limit", 1, "--history-limit", 0)
        updated = self.update(claimed, "--summary", "Another checkpoint")["result"]
        after = self.state.read_bytes()
        self.assertEqual(self.replay_page(detail["pagination"]["evidence"]["next_argv"], ok=False)["code"], "revision_conflict")
        self.assertEqual(self.call("resume", "--at-revision", packet["revision"], ok=False)["code"], "revision_conflict")
        self.assertEqual(self.state.read_bytes(), after)
        self.assertEqual(updated["revision"], claimed["revision"] + 1)

    def test_explicit_mutation_pages_and_release_keep_small_compatible_result_fields(self):
        claimed = self.fill_evidence(7)
        updated = self.update(claimed, "--evidence-limit", 2, "--evidence-offset", 1, "--history-limit", 1)["result"]
        canonical = self.load()["tasks"][claimed["id"]]
        self.assertEqual(updated["evidence"], canonical["evidence"][-3:-1])
        self.assertEqual(len(updated["history"]), 1)
        self.assertEqual(updated["evidence_count"], 7)
        released = self.release(updated)
        self.assertEqual(released["id"], claimed["id"])
        self.assertEqual(released["status"], "queued")
        self.assertIsNone(released["claim"])
        self.assertEqual(released["evidence"], [])
        self.assertEqual(released["evidence_count"], 7)
        page = self.replay_page(released["pagination"]["evidence"]["next_argv"])
        self.assertEqual(page["evidence_count"], 7)
        self.assertEqual(len(page["evidence"]), 5)
        definition = self.write("added-task.json", dict(task("ADDED"), depends_on=[claimed["id"]]))
        added = self.call("add", "--file", definition, "--expect", self.load()["revision"], "--actor", "H3")["result"]
        self.assertEqual(added["depends_on"], [claimed["id"]])
        self.assertIsNone(added["claim"])
        self.assertEqual(added["evidence"], [])
        self.assertEqual(added["evidence_count"], 0)

    def test_hidden_failure_still_blocks_verification_in_complete_canonical_state(self):
        self.init()
        self.pin()
        claimed = self.claim()
        claimed = self.update(claimed, "--evidence", self.evidence(check="critical", outcome="fail"))["result"]
        for index in range(7):
            claimed = self.update(claimed, "--evidence", self.evidence(check="other-" + str(index)))["result"]
        self.assertEqual(claimed["evidence"], [])
        self.assertEqual(claimed["evidence_count"], 8)
        self.assertEqual(self.update(claimed, "--status", "verified", ok=False)["code"], "unresolved_evidence")
        done = self.update(claimed, "--status", "verified", "--evidence", self.evidence(check="critical"))["result"]
        self.assertIsNone(done["claim"])
        self.assertEqual(done["evidence_count"], 9)
        self.assertEqual(self.load()["tasks"][done["id"]]["evidence"][0]["outcome"], "fail")

    def test_resume_is_read_only_and_bounded_and_restores_owner_checkpoint(self):
        self.init([task(), task("H1-B")])
        claimed = self.claim()
        updated = self.update(claimed, "--summary", "Found malformed-input gap", "--next-action", "Draft the corruption case")["result"]
        before = self.state.read_bytes()
        packet = self.call("resume", "--owner", "H1", "--limit", 1)
        self.assertEqual(packet["owned_tasks"][0]["claim"]["token"], updated["claim"]["token"])
        self.assertEqual(packet["owned_tasks"][0]["next_action"], "Draft the corruption case")
        self.assertEqual(len(packet["next_tasks"]), 1)
        self.assertFalse(packet["automatic_campaign_signoff"])
        self.assertEqual(self.state.read_bytes(), before)
        self.assertNotIn("token", self.call("show", "H1-A")["claim"])

    def test_init_rejects_duplicate_missing_self_and_cyclic_dependencies_without_state(self):
        cases = [[task(), task()], [dict(task(), depends_on=["MISSING"])],
                 [dict(task(), depends_on=["H1-A"])],
                 [dict(task(), depends_on=["H1-B"]), dict(task("H1-B"), depends_on=["H1-A"])]]
        for tasks in cases:
            self.write("seed.json", {"campaign": "test", "tasks": tasks})
            self.call("init", "--seed", self.seed, ok=False)
            self.assertFalse(self.state.exists())
        self.init()
        before = self.state.read_bytes()
        self.call("init", "--seed", self.seed, ok=False)
        self.assertEqual(before, self.state.read_bytes())

    def test_revision_and_token_conflicts_never_overwrite_newer_work(self):
        self.init()
        claimed = self.claim()
        updated = self.update(claimed, "--summary", "New observation")["result"]
        before = self.state.read_bytes()
        self.assertEqual(self.update(claimed, "--summary", "Stale", ok=False)["code"], "revision_conflict")
        altered = copy.deepcopy(updated)
        altered["claim"]["token"] = "old-token"
        self.assertEqual(self.update(altered, "--summary", "Wrong owner", ok=False)["code"], "claim_conflict")
        self.assertEqual(self.state.read_bytes(), before)

    def test_explicit_reclaim_fences_old_owner_and_retains_attempt(self):
        self.init()
        claimed = self.claim()
        with patch.object(tracker.time, "time", return_value=claimed["claim"]["expires"]):
            self.assertEqual(self.update(claimed, "--summary", "Expired", ok=False)["code"], "lease_expired")
            self.call("claim", "H1-A", "--owner", "H1-new", "--expect", claimed["revision"], ok=False)
            replacement = self.call("claim", "H1-A", "--owner", "H1-new", "--expect", claimed["revision"],
                                    "--reclaim", "--reason", "Previous offline agent stopped.")["result"]
        self.assertNotEqual(replacement["claim"]["token"], claimed["claim"]["token"])
        self.assertNotEqual(replacement["claim"]["artifacts"], claimed["claim"]["artifacts"])
        self.assertIn("previous_claim", self.load()["history"][-1])
        self.update(dict(claimed, revision=replacement["revision"]), "--summary", "Stale owner", ok=False)

    def test_replace_failure_preserves_state_and_releases_only_own_writer_lock(self):
        self.init()
        before = self.state.read_bytes()
        with patch.object(tracker.os, "replace", side_effect=PermissionError("injected replace failure")):
            self.call("claim", "H1-A", "--owner", "H1", "--expect", 0, ok=False)
        self.assertEqual(before, self.state.read_bytes())
        self.assertFalse(list(self.root.glob("state.json.*")))
        lock = self.state.with_suffix(".json.lock")
        lock.write_text("another writer", encoding="utf-8")
        with patch.object(tracker.time, "monotonic", side_effect=[0, 4]):
            self.assertEqual(self.call("claim", "H1-A", "--owner", "H1", "--expect", 0, ok=False)["code"], "writer_locked")
        self.assertEqual(lock.read_text(), "another writer")
        self.assertEqual(before, self.state.read_bytes())

    def test_real_concurrent_claims_and_distinct_task_updates(self):
        self.init([task(), task("H1-B")])
        script = Path(tracker.__file__).resolve()

        def claim(key, owner):
            process = subprocess.run([sys.executable, str(script), "--state", str(self.state), "claim", key,
                                      "--owner", owner, "--expect", "0"], capture_output=True, text=True)
            return process.returncode, json.loads(process.stdout)

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda owner: claim("H1-A", owner), ("one", "two")))
        self.assertEqual(sorted(code for code, _ in results), [0, 2])
        self.assertEqual(self.load()["tasks"]["H1-A"]["revision"], 1)
        winner = next(row["data"]["result"] for code, row in results if code == 0)
        self.call("release", "H1-A", "--expect", 1, "--token", winner["claim"]["token"],
                  "--summary", "Completed concurrency probe", "--next-action", "Resume later")
        # Both tasks now update concurrently using their own revisions, without losing either write.
        def current_claim(key):
            revision = self.load()["tasks"][key]["revision"]
            process = subprocess.run([sys.executable, str(script), "--state", str(self.state), "claim", key,
                                      "--owner", key, "--expect", str(revision)], capture_output=True, text=True)
            return process.returncode
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(list(pool.map(current_claim, ("H1-A", "H1-B"))), [0, 0])
        self.assertTrue(all(row["claim"] for row in self.load()["tasks"].values()))

    def test_verification_requires_scope_checks_independent_review_and_epoch(self):
        self.init([dict(task(), required_scopes=["offline"], checks=["corruption"])])
        claimed = self.claim()
        self.assertEqual(self.update(claimed, "--status", "verified", ok=False)["code"], "epoch_required")
        self.pin()
        self.release(claimed)
        claimed = self.claim()
        self.update(claimed, "--status", "verified", "--evidence", self.evidence(), ok=False)
        for changes in ({"reviewer": "H1", "check": "corruption"}, {"reviewer": "independent"}):
            evidence = self.evidence(scope="offline", command=["python", "test.py"], exit=0, **changes)
            self.update(claimed, "--status", "verified", "--evidence", evidence, ok=False)
        evidence = self.evidence(scope="offline", command=["python", "test.py"], exit=0, check="corruption")
        done = self.update(claimed, "--status", "verified", "--evidence", evidence)["result"]
        self.assertIsNone(done["claim"])
        self.assertTrue(self.call("show", "H1-A")["fresh_verified"])

    def test_dependency_freshness_and_explicit_reopen_preserve_old_evidence(self):
        self.init([task(), dict(task("H1-B"), depends_on=["H1-A"])])
        self.pin()
        self.call("claim", "H1-B", "--owner", "H1", "--expect", 0, ok=False)
        self.verify()
        self.verify("H1-B")
        self.pin("E002")
        self.assertEqual(set(self.call("resume")["stale_verification"]), {"H1-A", "H1-B"})
        previous = self.load()["tasks"]["H1-A"]
        self.call("reopen", "H1-A", "--actor", "coordinator", "--expect", previous["revision"],
                  "--reason", "New source epoch", "--next-action", "Recheck affected contracts")
        self.assertEqual(self.load()["tasks"]["H1-A"]["evidence"], previous["evidence"])
        self.assertFalse(self.call("show", "H1-B")["fresh_verified"])

    def test_reopen_cannot_reuse_old_evidence_in_the_same_epoch(self):
        self.init()
        self.pin()
        done = self.verify()
        self.call("reopen", "H1-A", "--expect", done["revision"], "--actor", "coordinator",
                  "--reason", "Recheck the oracle", "--next-action", "Collect new evidence")
        claimed = self.claim()
        self.assertEqual(self.update(claimed, "--status", "verified", ok=False)["code"], "evidence_required")

    def test_later_failure_cannot_hide_behind_an_earlier_pass(self):
        self.init()
        self.pin()
        claimed = self.claim()
        passed = self.update(claimed, "--evidence", self.evidence())["result"]
        failed = self.update(passed, "--evidence", self.evidence(outcome="fail", observed="Later review found missing contracts"))["result"]
        self.assertEqual(self.update(failed, "--status", "verified", ok=False)["code"], "unresolved_evidence")
        fixed = self.update(failed, "--evidence", self.evidence(), "--status", "verified")["result"]
        self.assertEqual([row["outcome"] for row in self.load()["tasks"][fixed["id"]]["evidence"]], ["pass", "fail", "pass"])

    def test_native_pass_needs_actual_matching_pin_and_final_guards(self):
        self.init()
        self.pin()
        claimed = self.claim()
        fields = dict(scope="load", command=["python", "-m", "gamelab", "run", "mod-all", "--mode", "lab"],
                      exit=0, build=self.build, run_id="test-mod-all-lab", scenario="mod-all", source_before=self.source,
                      source_after=self.source, verdict="PASS", partial=False, build_drift=False,
                      error=None, teardown_clean=True, assertions_ok=True)
        for changes in ({"build": None}, {"build": "unrecorded"}, {"build": dict(self.build, build_id="other")},
                        {"source_after": dict(self.source, head="d" * 40)}, {"partial": True},
                        {"teardown_clean": False}, {"exit": 2}):
            invalid = dict(fields, **changes)
            self.update(claimed, "--evidence", self.evidence(**invalid), ok=False)
        self.assertEqual(self.load()["tasks"]["H1-A"]["evidence"], [])

    def test_prerequisite_change_cannot_relabel_old_observations(self):
        self.init([task(), dict(task("H1-B"), depends_on=["H1-A"])])
        self.pin()
        done = self.verify()
        claimed = self.claim("H1-B")
        observed = self.update(claimed, "--evidence", self.evidence())["result"]
        self.call("reopen", "H1-A", "--expect", done["revision"], "--actor", "coordinator",
                  "--reason", "Prerequisite changed", "--next-action", "Revalidate prerequisite")
        self.verify()
        self.assertEqual(self.update(observed, "--status", "verified", ok=False)["code"], "dependencies_changed")

    def test_released_fix_is_discoverable_and_integration_is_role_gated(self):
        self.init()
        self.pin()
        claimed = self.claim()
        drafted = self.update(claimed, "--status", "fix-drafted", "--summary", "Minimal patch drafted",
                              "--next-action", "Review draft artifact")["result"]
        self.release(drafted)
        packet = self.call("resume", "--owner", "independent")
        self.assertEqual(packet["next_tasks"][0]["status"], "fix-drafted")
        self.assertEqual(packet["next_tasks"][0]["claim_argv"][3], str(self.state))
        reviewer = self.claim(owner="independent")
        reviewed = self.update(reviewer, "--status", "reviewed", "--summary", "Reviewed reproduction and patch",
                               "--next-action", "Integrator to apply patch")["result"]
        self.update(reviewed, "--status", "integrated", "--summary", "Attempted",
                    "--next-action", "Validate", ok=False)
        self.release(reviewed)
        integrator = self.claim(owner="integrator")
        self.freeze()
        self.assertEqual(self.update(integrator, "--status", "integrated", "--summary", "Frozen attempt",
                                    "--next-action", "Validate", ok=False)["code"], "integration_refused")

    def test_malformed_journal_and_nested_state_are_json_refusals(self):
        self.init()
        self.pin()
        claimed = self.claim()
        journal = self.root / "bad.jsonl"
        for row in (None, [], {"index": 1, "result": ["wrong"]}):
            journal.write_text(json.dumps(row) + "\n")
            self.call("record-batch", "H1-A", "--journal", journal, "--index", 1, "--epoch", "E001", "--scope", "load",
                      "--expected", "Expected", "--observed", "Observed", "--reviewer", "independent",
                      "--expect", claimed["revision"], "--token", claimed["claim"]["token"], ok=False)
        state = self.load()
        state["history"].append("malformed")
        self.state.write_text(json.dumps(state))
        self.call("show", "H1-A", ok=False)

    def test_runtime_freeze_survives_expiry_and_blocks_integration_and_repin(self):
        self.init([dict(task("NATIVE"), operation="native", required_scopes=["load"]),
                   dict(task("INTEGRATE"), operation="integration")])
        self.pin()
        integration = self.claim("INTEGRATE", "integrator")
        self.freeze(ok=False)
        self.call("release", "INTEGRATE", "--expect", integration["revision"], "--token", integration["claim"]["token"],
                  "--summary", "Idle boundary", "--next-action", "Wait for runtime queue")
        self.freeze()
        native = self.claim("NATIVE", "runtime")
        with patch.object(tracker.time, "time", return_value=native["claim"]["expires"] + 1):
            self.call("claim", "NATIVE", "--owner", "runtime", "--expect", native["revision"],
                      "--reclaim", "--reason", "Expired", ok=False)
            self.assertEqual(self.call("resume")["phase"], "frozen")
            self.freeze("idle", ok=False)
        self.call("epoch", "E002", "--file", self.epoch, "--expect", self.load()["revision"], "--actor", "coordinator", ok=False)
        self.call("claim", "INTEGRATE", "--owner", "integrator", "--expect", 2, ok=False)

    def test_record_batch_rechecks_raw_results_and_preserves_failed_attempts(self):
        self.init([dict(task("NATIVE"), operation="native", required_scopes=["load"], checks=["mod-all"])])
        self.pin()
        self.freeze()
        claimed = self.claim("NATIVE", "runtime")
        run_id = "20000101-000000-mod-all-lab"
        record = {"scenario": "mod-all", "mode": "lab", "environment": "gamelab", "verdict": "PASS",
                  "partial": False, "build_drift": False, "error": None, "build": self.build,
                  "assertions": [{"name": "load", "ok": True}], "teardown": {"clean": True}}
        self.write(f"gamelab/results/{run_id}/run.json", record)
        inner_path = self.write(f"gamelab/results/{run_id}/inner.json", {"scenario": "mod-all", "mode": "lab", "partial": True})
        journal = self.root / "batch.jsonl"
        journal.write_text(json.dumps({"index": 1, "scenario": "mod-all", "ok": True, "exit": 0, "problems": [],
                                       "run_id": run_id, "result": record, "source_before": self.source, "source_after": self.source}) + "\n")
        args = ["record-batch", "NATIVE", "--journal", journal, "--index", 1, "--epoch", "E001", "--scope", "load",
                "--expected", "All modules load", "--observed", "Inspected log and load assertions", "--reviewer", "auditor"]
        with patch.object(tracker, "ROOT", self.root):
            failed = self.call(*args, "--expect", claimed["revision"], "--token", claimed["claim"]["token"])["result"]
            self.assertEqual(self.load()["tasks"][failed["id"]]["evidence"][-1]["outcome"], "fail")
            self.update(failed, "--status", "verified", ok=False)
            inner_path.write_text(json.dumps({"scenario": "mod-all", "mode": "lab", "partial": False, "assertions": record["assertions"]}))
            passed = self.call(*args, "--expect", failed["revision"], "--token", failed["claim"]["token"])["result"]
        done = self.update(passed, "--status", "verified")["result"]
        self.assertEqual([row["outcome"] for row in self.load()["tasks"][done["id"]]["evidence"]], ["fail", "pass"])

    def test_record_batch_rejects_inner_assertion_or_metadata_disagreement(self):
        self.init([dict(task("NATIVE"), operation="native", required_scopes=["load"], checks=["mod-all"])])
        self.pin()
        self.freeze()
        claimed = self.claim("NATIVE", "runtime")
        run_id = "20000101-000000-mod-all-lab"
        native_assertions = [{"name": "load", "ok": True, "detail": "current"}]
        record = {"scenario": "mod-all", "mode": "lab", "environment": "gamelab", "verdict": "PASS",
                  "partial": False, "build_drift": False, "error": None, "build": self.build,
                  "assertions": native_assertions + [{"name": "isolation guard", "ok": True}],
                  "teardown": {"clean": True}, "fixture": "town-paladin", "passes": 1}
        self.write(f"gamelab/results/{run_id}/run.json", record)
        inner = {"scenario": "mod-all", "mode": "lab", "partial": False,
                 "assertions": native_assertions, "fixture": "town-paladin", "passes": 1}
        path = self.root / f"gamelab/results/{run_id}/inner.json"
        journal = self.root / "batch.jsonl"
        journal.write_text(json.dumps({"index": 1, "scenario": "mod-all", "ok": True, "exit": 0, "problems": [],
                                       "run_id": run_id, "result": record,
                                       "source_before": self.source, "source_after": self.source}) + "\n")
        args = ["record-batch", "NATIVE", "--journal", journal, "--index", 1, "--epoch", "E001", "--scope", "load",
                "--expected", "Exact raw assertion agreement", "--observed", "Fake artifact regression",
                "--reviewer", "auditor"]
        mutations = ({}, {"assertions": None}, {"assertions": []}, {"assertions": [True]},
                     {"assertions": [{"name": "load", "ok": False}]},
                     {"assertions": [{"name": "load", "ok": True, "detail": "stale"}]},
                     {"assertions": record["assertions"] + [{"name": "extra", "ok": True}]},
                     {"error": None}, {"error": ""}, {"timeout": True},
                     {"fixture": "different-fixture"}, {"passes": 2})
        with patch.object(tracker, "ROOT", self.root):
            for change in mutations:
                with self.subTest(change=change):
                    corrupted = dict(inner)
                    if not change or "assertions" in change:
                        corrupted.pop("assertions")
                    corrupted.update(change)
                    path.write_text(json.dumps(corrupted), encoding="utf-8")
                    claimed = self.call(*args, "--expect", claimed["revision"],
                                        "--token", claimed["claim"]["token"])["result"]
                    self.assertEqual(self.load()["tasks"][claimed["id"]]["evidence"][-1]["outcome"], "fail")
                    self.assertFalse(self.load()["tasks"][claimed["id"]]["evidence"][-1]["raw_result_checked"])
            path.write_text(json.dumps(inner), encoding="utf-8")
            accepted = self.call(*args, "--expect", claimed["revision"],
                                 "--token", claimed["claim"]["token"])["result"]
        self.assertEqual(self.load()["tasks"][accepted["id"]]["evidence"][-1]["outcome"], "pass")
        self.assertTrue(self.load()["tasks"][accepted["id"]]["evidence"][-1]["raw_result_checked"])
        self.assertTrue(all(row["outcome"] == "fail" for row in self.load()["tasks"][accepted["id"]]["evidence"][:-1]))

    def test_corruption_unknown_schema_and_bad_arguments_are_json_refusals(self):
        self.init()
        for raw in ("{", '{"schema_version":99}', '{"schema_version":NaN}'):
            self.state.write_text(raw)
            self.call("resume", ok=False)
            self.call("claim", "H1-A", "--owner", "H1", "--expect", 0, ok=False)
            self.assertEqual(self.state.read_text(), raw)
        self.call("claim", "H1-A", "--owner", "H1", "--expect", "bad", ok=False)
        self.call("resume", "--limit", 0, ok=False)


class PoolEvidenceTests(unittest.TestCase):
    setUp = TrackerTests.setUp
    write = TrackerTests.write
    call = TrackerTests.call
    init = TrackerTests.init
    pin = TrackerTests.pin
    load = TrackerTests.load
    claim = TrackerTests.claim
    freeze = TrackerTests.freeze

    def fixture(self, tasks=None):
        self.init(tasks or [dict(task("NATIVE"), operation="native", required_scopes=["load"], checks=["mod-all"])])
        self.pin(); self.freeze()
        claimed = self.claim("NATIVE", "runtime")
        root = self.root / "gamelab/env/userdata/workers/ptest"
        token = "a" * 32
        slots = [dict(slot_id=f"worker-{i}", game_dir=str(root / f"worker-{i}/game"),
                      results=str(self.root / f"gamelab/results/workers/ptest/worker-{i}"),
                      desktop_name=f"gamelab_ptest_{i}_{token[:8]}", job_name=f"gamelab_job_ptest_{i}_{token[:8]}") for i in (1, 2)]
        manifest = dict(version=1, pool_id="ptest", token=token, manifest_path=str(root / "pool.json"),
                        closed=False, source=self.source, slots=slots)
        final = self.write("gamelab/env/userdata/workers/ptest/pool.json", dict(manifest, closed=True))
        rid = "case-0001-mod-all-lab"
        folder = self.root / "gamelab/results/workers/ptest/worker-1" / rid
        identity = {key: slots[0][key] for key in ("slot_id", "game_dir", "desktop_name", "job_name")}
        identity["pool_id"] = "ptest"
        teardown = dict(clean=True, run=rid, reasons=[])
        live = [dict(owned_job=True, registered_slot=True)]
        assertions = [dict(name="load", ok=True)]
        record = dict(scenario="mod-all", mode="lab", environment="gamelab", verdict="PASS", partial=False,
                      build_drift=False, error=None, build=self.build, teardown=teardown, live=live,
                      assertions=assertions, runtime_slot=identity)
        inner = dict(scenario="mod-all", mode="lab", partial=False, assertions=assertions, live=live)
        def put_at(path, value):
            return self.write(str(path.relative_to(self.root)), value)
        run = put_at(folder / "run.json", record)
        inside = put_at(folder / "inner.json", inner)
        td = self.write("gamelab/results/pool-test/child-0001.teardown.json", teardown)
        logs = [self.write(f"gamelab/results/pool-test/child-0001.{suffix}", {}) for suffix in ("stdout", "stderr")]
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        child = dict(index=1, scenario="mod-all", slot_index=0, run_id=rid, results=str(folder), result=record,
                     exit=0, terminal=True, timed_out=False, ok=True, problems=[], source_before=self.source,
                     source_after=self.source, run_sha256=digest(run), inner_sha256=digest(inside), teardown=teardown,
                     teardown_copy=str(td), teardown_sha256=digest(td), stdout_sha256=digest(logs[0]), stderr_sha256=digest(logs[1]))
        parent = dict(label="test", pool=manifest, children=[child], source_before=self.source, source_after=self.source,
                      source_stable=True, games_after=[], global_games_absent=True, registered_games_absent=True,
                      all_cli_handles_terminal=True, slot_leases_absent=True, pool_closed=True, lease_retained=False,
                      requires_owned_descendant_audit=False, teardown=dict(clean=True), ok=True, exit_code=0, problems=[],
                      named_jobs_empty={slot["job_name"]: True for slot in slots}, pool_manifest_after_sha256=digest(final))
        receipt = self.write("gamelab/results/pool-test/pool.json", parent)
        argv = ["record-pool", "NATIVE", "--receipt", receipt, "--index", 1, "--epoch", "E001", "--scope", "load",
                "--expected", "Raw slot identity and finality", "--observed", "Temporary fixtures only", "--reviewer", "auditor",
                "--expect", claimed["revision"], "--token", claimed["claim"]["token"]]
        return parent, receipt, argv, run, inside, final

    def record(self, fixture, ok=True):
        parent, receipt, argv, *_ = fixture
        receipt.write_text(json.dumps(parent), encoding="utf-8")
        with patch.object(tracker, "ROOT", self.root):
            return self.call(*argv, ok=ok)

    def test_public_command_reads_explicit_nested_slot_result(self):
        self.record(self.fixture())
        value = self.load()["tasks"]["NATIVE"]["evidence"][-1]
        self.assertEqual(value["outcome"], "pass")
        self.assertTrue(value["raw_result_checked"])
        self.assertEqual(value["runtime_slot"]["slot_id"], "worker-1")

    def test_clean_product_failed_parent_preserves_scoped_survivor_context(self):
        data = self.fixture()
        data[0].update(ok=False, exit_code=1, problems=["other child product failure"])
        self.record(data)
        value = self.load()["tasks"]["NATIVE"]["evidence"][-1]
        self.assertEqual(value["outcome"], "pass")
        self.assertFalse(value["parent_pool_ok"])
        self.assertEqual(value["parent_pool_exit"], 1)

    def test_rejects_duplicate_index_and_escaped_result_without_ledger_mutation(self):
        for mutation in (lambda p: p["children"].append(copy.deepcopy(p["children"][0])),
                         lambda p: p["children"][0].update(results=str(self.root.parent / "outside"))):
            data = self.fixture() if not self.state.exists() else None
            if data is None:
                self.state.unlink(); data = self.fixture()
            mutation(data[0]); before = self.state.read_bytes()
            self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")
            self.assertEqual(self.state.read_bytes(), before)

    def test_rejects_tampered_raw_hash_and_missing_hash(self):
        data = self.fixture()
        data[3].write_text("{}", encoding="utf-8")
        self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")
        data[0]["children"][0].pop("run_sha256")
        self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")

    def test_rejects_source_slot_manifest_and_parent_finality_mismatch(self):
        data = self.fixture(); original = copy.deepcopy(data[0])
        for mutate in (lambda p: p.update(source_after=dict(self.source, files=4)),
                       lambda p: p["children"][0].update(slot_index=1),
                       lambda p: p.update(lease_retained=True),
                       lambda p: p.update(named_jobs_empty={}),
                       lambda p: p.update(games_after=[[123, "foreign"]]),
                       lambda p: p.update(pool_manifest_after_sha256="f" * 64)):
            data[0].clear(); data[0].update(copy.deepcopy(original)); mutate(data[0])
            self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")

    def test_inner_disagreement_is_failure_even_with_matching_new_hash(self):
        data = self.fixture()
        raw = json.loads(data[4].read_text()); raw["assertions"][0]["ok"] = False
        data[4].write_text(json.dumps(raw), encoding="utf-8")
        data[0]["children"][0]["inner_sha256"] = hashlib.sha256(data[4].read_bytes()).hexdigest()
        self.record(data)
        self.assertEqual(self.load()["tasks"]["NATIVE"]["evidence"][-1]["outcome"], "fail")

    def test_reparse_artifact_is_refused_before_read(self):
        from types import SimpleNamespace
        data = self.fixture()
        actual = Path.lstat
        target = data[3]

        def attributes(path, *args, **kwargs):
            info = actual(path, *args, **kwargs)
            if path == target:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info

        with patch.object(Path, "lstat", attributes):
            self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")


class PoolBundleTests(unittest.TestCase):
    setUp = TrackerTests.setUp
    write = TrackerTests.write
    call = TrackerTests.call
    init = TrackerTests.init
    pin = TrackerTests.pin
    load = TrackerTests.load
    claim = TrackerTests.claim
    freeze = TrackerTests.freeze

    def fixture(self):
        tasks = [dict(task(name), operation="native", required_scopes=["load"], checks=[scenario])
                 for name, scenario in (("NATIVE", "mod-all"), ("SECOND", "null-payload"))]
        data = PoolEvidenceTests.fixture(self, tasks)
        self.claim("SECOND", "runtime")
        parent, receipt, _, _, _, _ = data
        child = copy.deepcopy(parent["children"][0])
        slot = parent["pool"]["slots"][1]
        rid = "case-0002-null-payload-lab"
        folder = Path(slot["results"]) / rid
        child.update(index=2, scenario="null-payload", slot_index=1, run_id=rid, results=str(folder))
        identity = {key: slot[key] for key in ("slot_id", "game_dir", "desktop_name", "job_name")}
        identity["pool_id"] = "ptest"
        child["result"].update(scenario="null-payload", runtime_slot=identity)
        child["teardown"]["run"] = rid
        child["result"]["teardown"] = child["teardown"]
        child["teardown_copy"] = str(receipt.parent / "child-0002.teardown.json")
        inner = dict(scenario="null-payload", mode="lab", partial=False,
                     assertions=child["result"]["assertions"], live=child["result"]["live"])
        for path, value, key in ((folder / "run.json", child["result"], "run_sha256"),
                                 (folder / "inner.json", inner, "inner_sha256"),
                                 (Path(child["teardown_copy"]), child["teardown"], "teardown_sha256"),
                                 (receipt.parent / "child-0002.stdout", {}, "stdout_sha256"),
                                 (receipt.parent / "child-0002.stderr", {}, "stderr_sha256")):
            self.write(str(path.relative_to(self.root)), value)
            child[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        parent["children"].append(child)
        receipt.write_text(json.dumps(parent), encoding="utf-8")
        state = self.load()
        imports = [dict(task=name, journal=str(receipt), index=index, epoch="E001", scope="load", check=scenario,
                        expected="Exact scoped result", observed="Temporary fixture raw result", reviewer="auditor",
                        expect=state["tasks"][name]["revision"], token=state["tasks"][name]["claim"]["token"])
                   for name, index, scenario in (("NATIVE", 1, "mod-all"), ("SECOND", 2, "null-payload"))]
        return parent, receipt, {"schema_version": 1, "imports": imports, "verify_complete": ["NATIVE", "SECOND"]}

    def run_bundle(self, data, ok=True):
        parent, receipt, spec = data
        receipt.write_text(json.dumps(parent), encoding="utf-8")
        bundle = self.write("bundle.json", spec)
        with patch.object(tracker, "ROOT", self.root):
            return self.call("record-pool-bundle", "--bundle", bundle, ok=ok)

    def test_two_tasks_commit_once_and_preserve_failed_trial(self):
        data = self.fixture()
        state = self.load()
        retained = dict(scope="load", outcome="fail", epoch="E001", reviewer="auditor", expected="Load",
                        observed="Original failed trial", artifacts=["retained/run.json"], command=["python"],
                        exit=1, run_id="original-fail", scenario="mod-all", check="mod-all")
        state["tasks"]["NATIVE"]["evidence"].append(retained)
        self.write("state.json", state)
        original_save = tracker.Store.save
        with patch.object(tracker.Store, "save", autospec=True, side_effect=original_save) as save:
            result = self.run_bundle(data)
        after = self.load()
        self.assertEqual(save.call_count, 1)
        self.assertEqual(result["result"]["verified"], ["NATIVE", "SECOND"])
        self.assertEqual(after["revision"], state["revision"] + 1)
        self.assertEqual(after["tasks"]["NATIVE"]["evidence"][0], retained)
        for name in ("NATIVE", "SECOND"):
            self.assertEqual(after["tasks"][name]["revision"], state["tasks"][name]["revision"] + 1)
            self.assertEqual(after["tasks"][name]["status"], "verified")
            self.assertEqual(after["tasks"][name]["evidence"][-1]["epoch"], "E001")

    def test_stale_second_cas_rolls_back_all_tasks(self):
        data = self.fixture(); data[2]["imports"][1]["expect"] -= 1
        before = self.state.read_bytes()
        self.assertEqual(self.run_bundle(data, ok=False)["code"], "revision_conflict")
        self.assertEqual(self.state.read_bytes(), before)

    def test_missing_second_raw_file_rolls_back_first(self):
        data = self.fixture()
        (Path(data[0]["children"][1]["results"]) / "inner.json").unlink()
        before = self.state.read_bytes()
        self.run_bundle(data, ok=False)
        self.assertEqual(self.state.read_bytes(), before)

    def test_missing_declared_check_rolls_back_staged_evidence_and_verification(self):
        data = self.fixture(); state = self.load()
        state["tasks"]["SECOND"]["checks"].append("unexecuted-contract")
        self.write("state.json", state); before = self.state.read_bytes()
        self.assertEqual(self.run_bundle(data, ok=False)["code"], "checks_required")
        self.assertEqual(self.state.read_bytes(), before)

    def test_tamper_between_staging_and_writer_does_not_commit(self):
        data = self.fixture(); before = self.state.read_bytes()
        writer = tracker.Store.writer
        @contextlib.contextmanager
        def changed(store):
            (Path(data[0]["children"][1]["results"]) / "run.json").write_text("{}", encoding="utf-8")
            with writer(store):
                yield
        with patch.object(tracker.Store, "writer", changed):
            self.assertEqual(self.run_bundle(data, ok=False)["code"], "invalid_pool")
        self.assertEqual(self.state.read_bytes(), before)

    def test_dependency_revision_change_under_writer_does_not_import(self):
        data = self.fixture(); state = self.load()
        prerequisite = tracker.new_task(task("READY"))
        prerequisite.update(status="verified", revision=1, verified_epoch="E001", verified_dependencies={})
        state["tasks"]["READY"] = prerequisite
        for name in ("NATIVE", "SECOND"):
            state["tasks"][name]["depends_on"] = ["READY"]
            state["tasks"][name]["claim"]["dependencies"] = {"READY": 1}
        self.write("state.json", state)
        writer = tracker.Store.writer
        changed_bytes = []
        @contextlib.contextmanager
        def changed(store):
            current = self.load(); current["tasks"]["READY"]["revision"] += 1
            self.write("state.json", current); changed_bytes.append(self.state.read_bytes())
            with writer(store):
                yield
        with patch.object(tracker.Store, "writer", changed):
            self.assertEqual(self.run_bundle(data, ok=False)["code"], "dependencies_changed")
        self.assertEqual(self.state.read_bytes(), changed_bytes[0])
        self.assertEqual(self.load()["tasks"]["NATIVE"]["evidence"], [])

    def test_failed_child_is_recorded_but_cannot_atomically_verify(self):
        data = self.fixture(); child = data[0]["children"][1]
        child.update(ok=False, exit=1, problems=["product failure"])
        before = self.state.read_bytes()
        self.assertEqual(self.run_bundle(data, ok=False)["code"], "unresolved_evidence")
        self.assertEqual(self.state.read_bytes(), before)
        data[2]["verify_complete"] = []
        self.run_bundle(data)
        self.assertEqual(self.load()["tasks"]["SECOND"]["evidence"][-1]["outcome"], "fail")

    def test_duplicate_import_and_undeclared_labels_refuse_without_mutation(self):
        data = self.fixture(); original = copy.deepcopy(data[2]); before = self.state.read_bytes()
        for mutation in (lambda spec: spec["imports"].append(copy.deepcopy(spec["imports"][0])),
                         lambda spec: spec["imports"][1].update(check="not-declared"),
                         lambda spec: spec["imports"][1].update(token="stale-token")):
            data[2].clear(); data[2].update(copy.deepcopy(original)); mutation(data[2])
            self.run_bundle(data, ok=False)
            self.assertEqual(self.state.read_bytes(), before)


class CatalogPoolEvidenceTests(unittest.TestCase):
    setUp = TrackerTests.setUp
    write = TrackerTests.write
    call = TrackerTests.call
    init = TrackerTests.init
    pin = TrackerTests.pin
    load = TrackerTests.load
    claim = TrackerTests.claim
    freeze = TrackerTests.freeze
    fixture = PoolEvidenceTests.fixture
    record = PoolEvidenceTests.record

    def direct_cli(self, *arguments):
        # Execute byte-identical public sources, in a disposable repository tree.
        # cwd remains the real repository; PYTHONPATH must not mask script imports.
        repository = Path(tracker.__file__).resolve().parents[1]
        for relative in ("tools/qa_swarm.py", "tools/qa_batch.py", "gamelab/__init__.py",
                         "gamelab/catalog.py", "gamelab/consumer_evidence.py"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repository / relative).read_bytes())
        environment = {key: value for key, value in os.environ.items() if key.upper() != "PYTHONPATH"}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([sys.executable, "-B", str(self.root / "tools/qa_swarm.py"),
                               "--state", str(self.state), *map(str, arguments)],
                              cwd=repository, env=environment, capture_output=True, text=True, timeout=15)

    def catalog_fixture(self, result=None):
        from gamelab.consumer_evidence import validate_consumers
        data = self.fixture()
        parent, receipt, _, _, _, final = data
        row = parent["children"][0]
        scenario = dict(name="mod-all", fixture="town", steps=[dict(do="bot", bot="sample", expect={"ok": True})])
        scenario_path = self.write("gamelab/results/pool-test/child-0001.scenario.json", scenario)
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        files = {"gamelab/scenarios/mod-all.json": sha(scenario_path),
                 "gamelab/fixtures/town.json": "d" * 64, "gamelab/bots/sample.py": "e" * 64}
        entry = dict(id="mod-all", status="reviewed", scenario="gamelab/scenarios/mod-all.json",
                     task="NATIVE", check="mod-all", scope="load", expected="Only exact consumer rows",
                     predicates=[{"step": 0, "expect": {"ok": True}}], lifecycle="independent",
                     private_writes=["slot-game", "slot-results"],
                     review=dict(reviewer="source-reviewer", verdict="accepted", artifact="docs/source-review.json",
                                 sha256="f" * 64, closure_complete=True),
                     closure=dict(files=files, bots=["sample"], fixture="town", modules=[]),
                     consumers=[dict(step=0, bot="sample", rows=["stash-a", "stash-b"])])
        snapshot = self.write("gamelab/results/pool-test/catalog.snapshot.json",
                              dict(schema_version=1, catalog_id="fixture", cases=[entry]))
        admission = {key: entry[key] for key in ("id", "task", "check", "scope", "expected", "predicates", "lifecycle", "private_writes", "review")}
        closure_sha = hashlib.sha256(json.dumps(entry["closure"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        admission.update(schema_version=1, catalog_id="fixture", catalog_sha256=sha(snapshot), closure_sha256=closure_sha,
                         files=files, consumers=entry["consumers"])
        reference = dict(path=str(snapshot), sha256=sha(snapshot))
        parent["catalog"] = dict(input=dict(path="historical-catalog.json", sha256=sha(snapshot)),
                                 snapshot=reference, admissions=[admission], stable=True)
        parent["closure_stable"] = True
        parent["mechanical_admission"] = dict(valid=True, catalog_sha256=sha(snapshot), checks=[
            dict(scenario="mod-all", closure_sha256=closure_sha, review_and_closure_current=True)])
        parent["pool"]["catalog"] = reference
        final.write_text(json.dumps(dict(parent["pool"], closed=True)), encoding="utf-8")
        parent["pool_manifest_after_sha256"] = sha(final)
        records = [dict(bot="sample", kwargs={}, assertion_index=0, **{"pass": 1},
                        result=result or {"ok": True, "rows": [{"case": tag, "runtime": "PASS"} for tag in ("stash-a", "stash-b")]})]
        bot_path = Path(row["results"]) / "bot-results.jsonl"
        bot_path.write_text(json.dumps(records[0]) + "\n", encoding="utf-8")
        row.update(admission=admission, scenario_copy=str(scenario_path), scenario_sha256=sha(scenario_path),
                   bot_results=str(bot_path), bot_results_sha256=sha(bot_path),
                   consumer_validation=validate_consumers(admission, scenario, records))
        return data, bot_path

    def test_frozen_catalog_consumers_read_without_live_closure_or_source_review_reuse(self):
        from gamelab import catalog
        data, _ = self.catalog_fixture()
        before = self.state.read_bytes()
        data[1].write_text(json.dumps(data[0]), encoding="utf-8")
        with patch.object(catalog, "ROOT", self.root), patch.object(tracker, "ROOT", self.root), \
                patch.object(catalog, "validate_case", side_effect=AssertionError("historical evidence must not revalidate current source")):
            proposal = self.call("plan-pool-import", "--journal", data[1], "--epoch", "E001",
                                 "--reviewer", "actual-reviewer", "--observed", "Reviewed exact consumer rows")
            self.assertEqual(self.state.read_bytes(), before)
            bundle = self.write("catalog-bundle.json", proposal["bundle"])
            self.call("record-pool-bundle", "--bundle", bundle, "--verify-complete")
        evidence = self.load()["tasks"]["NATIVE"]["evidence"][-1]
        self.assertEqual(evidence["outcome"], "pass")
        self.assertEqual(evidence["reviewer"], "actual-reviewer")
        self.assertEqual(len(evidence["consumer_validation"]["checks"]), 2)
        self.assertFalse((self.root / "gamelab/bots/sample.py").exists())

    def test_direct_script_plans_and_atomically_imports_catalog_without_pythonpath(self):
        data, _ = self.catalog_fixture()
        data[1].write_text(json.dumps(data[0]), encoding="utf-8")
        before = self.state.read_bytes()
        planned = self.direct_cli("plan-pool-import", "--journal", data[1], "--epoch", "E001",
                                  "--reviewer", "actual-reviewer", "--observed", "Reviewed exact consumer rows")
        self.assertEqual(planned.returncode, 0, planned.stderr or planned.stdout)
        self.assertEqual(planned.stderr, "")
        proposal = json.loads(planned.stdout)["data"]
        self.assertTrue(proposal["read_only"])
        self.assertEqual(self.state.read_bytes(), before)
        bundle = self.write("direct-bundle.json", proposal["bundle"])
        imported = self.direct_cli("record-pool-bundle", "--bundle", bundle, "--verify-complete")
        self.assertEqual(imported.returncode, 0, imported.stderr or imported.stdout)
        self.assertEqual(imported.stderr, "")
        self.assertEqual(json.loads(imported.stdout)["data"]["result"]["verified"], ["NATIVE"])
        self.assertEqual(self.load()["tasks"]["NATIVE"]["evidence"][-1]["outcome"], "pass")

    def test_direct_script_catalog_refusal_is_json_and_preserves_ledger_without_pythonpath(self):
        data, _ = self.catalog_fixture()
        data[0]["closure_stable"] = False
        data[1].write_text(json.dumps(data[0]), encoding="utf-8")
        before = self.state.read_bytes()
        refused = self.direct_cli("plan-pool-import", "--journal", data[1], "--epoch", "E001",
                                  "--reviewer", "actual-reviewer", "--observed", "Changed closure")
        self.assertEqual(refused.returncode, 2, refused.stderr or refused.stdout)
        self.assertEqual(refused.stderr, "")
        self.assertEqual(json.loads(refused.stdout)["error"]["code"], "invalid_pool")
        self.assertEqual(self.state.read_bytes(), before)

    def test_aggregate_only_return_is_failed_evidence_even_with_outer_pass(self):
        from gamelab import catalog
        data, _ = self.catalog_fixture({"ok": True})
        with patch.object(catalog, "ROOT", self.root):
            self.record(data)
        evidence = self.load()["tasks"]["NATIVE"]["evidence"][-1]
        self.assertEqual(evidence["outcome"], "fail")
        self.assertTrue(evidence["raw_result_checked"])
        self.assertFalse(evidence["consumer_validation"]["valid"])

    def test_missing_bot_log_or_hash_tamper_cannot_record(self):
        from gamelab import catalog
        data, bot_path = self.catalog_fixture(); before = self.state.read_bytes()
        with patch.object(catalog, "ROOT", self.root):
            original = copy.deepcopy(data[0]["children"][0])
            data[0]["children"][0].update(bot_results=None, bot_results_sha256=None)
            self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")
            data[0]["children"][0] = original
            bot_path.write_text("{}\n", encoding="utf-8")
            self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")
        self.assertEqual(self.state.read_bytes(), before)

    def test_changed_or_unmeasured_catalog_closure_cannot_record(self):
        from gamelab import catalog
        data, _ = self.catalog_fixture(); before = self.state.read_bytes()
        with patch.object(catalog, "ROOT", self.root):
            for value in (False, None):
                if value is None:
                    data[0].pop("closure_stable", None)
                else:
                    data[0]["closure_stable"] = value
                self.assertEqual(self.record(data, ok=False)["code"], "invalid_pool")
                self.assertEqual(self.state.read_bytes(), before)

    def test_pinned_duplicate_nonfinite_or_blank_bot_records_are_refused(self):
        from gamelab import catalog
        data, bot_path = self.catalog_fixture(); before = self.state.read_bytes()
        with patch.object(catalog, "ROOT", self.root):
            for raw in ('{"bot":"sample","bot":"other"}\n', '{"value":1e999}\n', '\n'):
                bot_path.write_text(raw, encoding="utf-8")
                data[0]["children"][0]["bot_results_sha256"] = hashlib.sha256(bot_path.read_bytes()).hexdigest()
                self.record(data, ok=False)
                self.assertEqual(self.state.read_bytes(), before)


class TaskAmendmentTests(unittest.TestCase):
    cli_receipts = []

    write = TrackerTests.write
    init = TrackerTests.init
    pin = TrackerTests.pin
    load = TrackerTests.load
    claim = TrackerTests.claim
    update = TrackerTests.update
    release = TrackerTests.release
    evidence = TrackerTests.evidence
    freeze = TrackerTests.freeze

    def setUp(self):
        TrackerTests.setUp(self)

    def call(self, *argv, ok=True):
        before = self.state.read_bytes() if self.state.exists() else None
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = tracker.main(["--state", str(self.state), *map(str, argv)])
        record = json.loads(output.getvalue())
        self.cli_receipts.append({"argv": list(map(str, argv)), "exit": code, "record": record,
                                  "state_unchanged": before == (self.state.read_bytes() if self.state.exists() else None)})
        self.assertEqual(record["schema_version"], tracker.SCHEMA)
        self.assertEqual(code, 0 if ok else 2, record)
        self.assertEqual(record["ok"], ok)
        return record["data"] if ok else record["error"]

    def amend(self, payload, key="TARGET", actor="coordinator", expect=None, reason="Discovered transport contract",
              action="Collect the strengthened contract evidence", ok=True, **view):
        path = self.write("amend.json", payload)
        args = ["amend", key, "--file", path, "--expect",
                self.load()["tasks"][key]["revision"] if expect is None else expect,
                "--actor", actor, "--reason", reason, "--next-action", action]
        for name, value in view.items():
            args.extend(["--" + name.replace("_", "-"), value])
        return self.call(*args, ok=ok)

    def refuse(self, payload, code, **kwargs):
        before = self.state.read_bytes()
        self.assertEqual(self.amend(payload, ok=False, **kwargs)["code"], code)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertFalse(self.state.with_suffix(".json.lock").exists())
        self.assertFalse(list(self.root.glob("state.json.*.tmp")))

    def finish(self, key, claimed=None):
        current = claimed or self.claim(key)
        definition = self.load()["tasks"][key]
        for scope in definition["required_scopes"]:
            for check in definition["checks"] or [None]:
                fields = dict(scope=scope, check=check)
                if scope != "source":
                    fields.update(command=["fake-fixture-check"], exit=0)
                current = self.update(current, "--evidence", self.evidence(**fields))["result"]
        return self.update(current, "--status", "verified")["result"]

    def replacement_seed(self, **new_changes):
        old = dict(task("OLD"), operation="native", required_scopes=["controlled-native"], checks=["ownership", "effect"])
        new = dict(old, id="NEW", paths=["new/owner.py"], checks=["ownership", "effect", "transport"],
                   required_scopes=["controlled-native", "ordinary"])
        new.update(new_changes)
        self.init([old, new, task("EXTRA"), dict(task("TARGET"), depends_on=["OLD"])])
        self.call("defer", "OLD", "--expect", 0, "--actor", "coordinator",
                  "--reason", "Superseded contract", "--next-action", "Keep historical evidence")

    def test_public_cli_adds_transport_gate_and_blocks_claim(self):
        gate = "M3-ITEM-TRANSPORT-CONTRACT"
        target = "M3-GAMBLER-LIFECYCLE"
        self.init([dict(task(target), operation="native"), task(gate)])
        self.pin()
        before = self.load()
        result = self.amend({"depends_on": [gate]}, key=target)["result"]
        after = self.load()
        self.assertEqual(result["depends_on"], [gate])
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["revision"], before["tasks"][target]["revision"] + 1)
        self.assertEqual(after["tasks"][gate], before["tasks"][gate])
        self.freeze()
        refused = self.call("claim", target, "--owner", "runtime", "--expect", result["revision"], ok=False)
        self.assertEqual(refused["code"], "dependencies_blocked")
        self.assertIn("dependency:" + gate, refused["details"]["blockers"])

    def test_all_additive_fields_preserve_evidence_history_and_reset_work(self):
        self.init([dict(task("TARGET"), checks=["old"], owner_decision="Keep authored contract"), task("GATE")])
        self.pin()
        current = self.claim("TARGET")
        current = self.update(current, "--evidence", self.evidence(check="old"))["result"]
        current = self.update(current, "--evidence", self.evidence(check="old", outcome="fail"),
                              "--status", "fix-drafted", "--summary", "Old failure", "--next-action", "Repair it")["result"]
        self.release(current)
        before = self.load()
        result = self.amend({"paths": ["tools/save_builder.py", "new/test.py"], "checks": ["old", "new"],
                             "required_scopes": ["source", "offline"], "depends_on": ["GATE"]})["result"]
        after = self.load()
        self.assertEqual(result["status"], "queued")
        self.assertIsNone(result["claim"])
        self.assertEqual(after["tasks"]["TARGET"]["evidence"], before["tasks"]["TARGET"]["evidence"])
        self.assertEqual(after["history"][:-1], before["history"])
        self.assertEqual(after["epochs"], before["epochs"])
        self.assertEqual(after["freeze"], before["freeze"])
        self.assertEqual(after["tasks"]["GATE"], before["tasks"]["GATE"])
        self.assertEqual(result["owner_decision"], "Keep authored contract")
        event = after["history"][-1]
        self.assertEqual(event["before_definition"], tracker.task_definition(before["tasks"]["TARGET"]))
        self.assertEqual(event["after_definition"], tracker.task_definition(after["tasks"]["TARGET"]))
        self.assertEqual(event["actor"], "coordinator")
        self.assertEqual(event["reason"], "Discovered transport contract")
        self.assertEqual(event["replaced_dependencies"], [])
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["history"], [])
        self.assertEqual(result["evidence_count"], 2)
        self.assertEqual(result["latest_evidence"]["outcome"], "fail")

    def test_role_cas_and_required_text_refuse_atomically(self):
        self.init([task("TARGET")])
        payload = {"paths": ["tools/save_builder.py", "new.py"]}
        self.refuse(payload, "wrong_role", actor="P1")
        self.refuse(payload, "revision_conflict", expect=1)
        for reason, action in (("", "Continue"), ("  ", "Continue"), ("Strengthen", ""), ("Strengthen", "  ")):
            with self.subTest(reason=reason, action=action):
                self.refuse(payload, "invalid_record", reason=reason, action=action)

    def test_frozen_campaign_refuses_without_thawing(self):
        self.init([task("TARGET")])
        self.pin()
        self.freeze()
        frozen = copy.deepcopy(self.load()["freeze"])
        self.refuse({"checks": ["new"]}, "source_frozen")
        self.assertEqual(self.load()["freeze"], frozen)
        self.assertEqual(self.load()["phase"], "frozen")

    def test_live_and_expired_target_claims_require_owner_release(self):
        self.init([task("TARGET")])
        self.pin()
        claimed = self.claim("TARGET")
        self.refuse({"checks": ["new"]}, "already_claimed")
        with patch.object(tracker.time, "time", return_value=claimed["claim"]["expires"] + 1):
            self.refuse({"checks": ["new"]}, "already_claimed")

    def test_verified_target_requires_explicit_reopen_and_new_observations(self):
        self.init([task("TARGET"), dict(task("CHILD"), depends_on=["TARGET"])])
        self.pin()
        done = self.finish("TARGET")
        self.finish("CHILD")
        child = copy.deepcopy(self.load()["tasks"]["CHILD"])
        self.assertTrue(self.call("show", "CHILD")["fresh_verified"])
        self.refuse({"checks": ["new"]}, "terminal_task")
        self.call("reopen", "TARGET", "--expect", done["revision"], "--actor", "coordinator",
                  "--reason", "New obligations", "--next-action", "Review strengthened task")
        self.amend({"checks": ["new"]})
        claimed = self.claim("TARGET")
        self.assertEqual(self.update(claimed, "--status", "verified", ok=False)["code"], "evidence_required")
        refreshed = self.finish("TARGET", claimed)
        self.assertTrue(self.call("show", "TARGET")["fresh_verified"])
        self.assertFalse(self.call("show", "CHILD")["fresh_verified"])
        self.assertEqual(self.load()["tasks"]["CHILD"], child)
        self.assertNotEqual(child["verified_dependencies"]["TARGET"], refreshed["revision"])

    def test_deferred_target_keeps_disposition_and_full_history(self):
        self.init([task("TARGET")])
        self.call("defer", "TARGET", "--expect", 0, "--actor", "coordinator",
                  "--reason", "Parked", "--next-action", "Keep parked")
        before = self.load()
        result = self.amend({"checks": ["new"]})["result"]
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.load()["history"][:-1], before["history"])
        self.assertEqual(self.load()["history"][-1]["before_definition"]["summary"], "Parked")

    def test_unknown_keys_malformed_lists_and_noops_refuse(self):
        self.init([dict(task("TARGET"), paths=["a", "b"], checks=["old"], required_scopes=["source", "offline"])])
        for key in ("id", "title", "lane", "operation", "priority", "status", "claim", "revision", "evidence", "summary", "next_action", "unknown"):
            with self.subTest(key=key):
                self.refuse({"paths": ["a", "b", "c"], key: "forbidden"}, "invalid_amendment")
        for payload in (None, [], "text", True, {"paths": "not-list"}, {"checks": [""]}, {"checks": [" "]},
                        {"checks": ["old", 1]}, {"checks": ["old", "old"]}, {"required_scopes": ["source", "offline", "unknown"]}):
            with self.subTest(payload=payload):
                self.refuse(payload, "invalid_amendment")
        for payload in ({}, {"paths": ["b", "a"]}, {"checks": ["old"]}, {"replace_deferred_dependencies": {}}):
            with self.subTest(noop=payload):
                self.refuse(payload, "no_op")

    def test_each_existing_obligation_cannot_be_removed(self):
        self.init([task("GATE"), dict(task("TARGET"), paths=["a", "b"], checks=["old"],
                                      required_scopes=["source", "offline"], depends_on=["GATE"])])
        for payload in ({"paths": ["a"]}, {"checks": []}, {"required_scopes": ["source"]}, {"depends_on": []}):
            with self.subTest(payload=payload):
                self.refuse(payload, "definition_weakening")

    def test_malformed_files_and_unknown_target_are_single_json_refusals(self):
        self.init([task("TARGET")])
        path = self.root / "malformed.json"
        args = ["--file", path, "--expect", 0, "--actor", "coordinator",
                "--reason", "Discovered gate", "--next-action", "Collect evidence"]
        for raw in ("{", '{"checks":NaN}'):
            path.write_text(raw, encoding="utf-8")
            before = self.state.read_bytes()
            self.assertEqual(self.call("amend", "TARGET", *args, ok=False)["code"], "invalid_or_unreadable_state")
            self.assertEqual(self.state.read_bytes(), before)
        path.unlink()
        before = self.state.read_bytes()
        self.assertEqual(self.call("amend", "TARGET", *args, ok=False)["code"], "invalid_or_unreadable_state")
        self.assertEqual(self.call("amend", "MISSING", *args, ok=False)["code"], "unknown_task")
        self.assertEqual(self.state.read_bytes(), before)

    def test_missing_self_and_transitive_cycles_refuse_before_replace(self):
        self.init([task("TARGET"), dict(task("BACK"), depends_on=["TARGET"])])
        for dependency, code in (("MISSING", "dependency_missing"), ("TARGET", "dependency_cycle"), ("BACK", "dependency_cycle")):
            with self.subTest(dependency=dependency), patch.object(tracker.os, "replace") as replace:
                self.refuse({"depends_on": [dependency]}, code)
                replace.assert_not_called()

    def test_successful_deferred_replacement_preserves_old_gate_obligations(self):
        self.replacement_seed()
        before = self.load()
        result = self.amend({"replace_deferred_dependencies": {"OLD": "NEW"}, "depends_on": ["NEW", "EXTRA"]})["result"]
        after = self.load()
        self.assertEqual(result["depends_on"], ["NEW", "EXTRA"])
        self.assertEqual(result["operation"], before["tasks"]["TARGET"]["operation"])
        self.assertEqual(after["tasks"]["OLD"], before["tasks"]["OLD"])
        self.assertEqual(after["tasks"]["NEW"], before["tasks"]["NEW"])
        audit = after["history"][-1]["replaced_dependencies"][0]
        self.assertEqual((audit["old_id"], audit["new_id"]), ("OLD", "NEW"))
        self.assertEqual(audit["old_revision"], before["tasks"]["OLD"]["revision"])
        self.assertEqual(audit["new_revision"], before["tasks"]["NEW"]["revision"])
        self.assertEqual(audit["old_definition"], tracker.task_definition(before["tasks"]["OLD"]))
        self.assertEqual(audit["new_definition"], tracker.task_definition(before["tasks"]["NEW"]))
        self.assertFalse(after["tasks"]["TARGET"].get("verified_epoch"))
        self.assertIn("dependency:NEW", tracker.blockers(after, after["tasks"]["TARGET"]))

    def test_replacement_may_use_an_already_required_stronger_gate(self):
        self.replacement_seed()
        self.amend({"depends_on": ["OLD", "NEW"]})
        result = self.amend({"replace_deferred_dependencies": {"OLD": "NEW"}})["result"]
        self.assertEqual(result["depends_on"], ["NEW"])

    def test_replacement_refuses_weaker_operation_checks_or_scopes(self):
        for changes in ({"operation": "review"}, {"checks": ["ownership"]}, {"required_scopes": ["ordinary"]}):
            with self.subTest(changes=changes):
                self.replacement_seed(**changes)
                self.refuse({"replace_deferred_dependencies": {"OLD": "NEW"}}, "definition_weakening")
                self.state.unlink()

    def test_replacement_requires_unclaimed_deferred_old_dependency(self):
        self.init([task("OLD"), task("NEW"), dict(task("TARGET"), depends_on=["OLD"])])
        payload = {"replace_deferred_dependencies": {"OLD": "NEW"}}
        self.refuse(payload, "replacement_refused")
        self.pin()
        claimed = self.claim("OLD")
        claimed = self.update(claimed, "--status", "deferred", "--summary", "Parked with owner",
                              "--next-action", "Owner must release")["result"]
        self.refuse(payload, "replacement_refused")
        with patch.object(tracker.time, "time", return_value=claimed["claim"]["expires"] + 1):
            self.refuse(payload, "replacement_refused")

    def test_invalid_replacement_maps_and_cycles_refuse_atomically(self):
        self.replacement_seed()
        cases = [(None, "invalid_amendment"), ([], "invalid_amendment"), ({"NOT-A-DEPENDENCY": "NEW"}, "invalid_amendment"),
                 ({"OLD": "OLD"}, "invalid_amendment"), ({"OLD": "MISSING"}, "dependency_missing"),
                 ({"OLD": "TARGET"}, "dependency_cycle"), ({"OLD": 1}, "invalid_amendment")]
        for mapping, code in cases:
            with self.subTest(mapping=mapping):
                self.refuse({"replace_deferred_dependencies": mapping}, code)
        self.refuse({"replace_deferred_dependencies": {"OLD": "NEW", "NEW": "EXTRA"}}, "invalid_amendment")
        self.refuse({"replace_deferred_dependencies": {"OLD": "NEW"}, "depends_on": ["OLD", "NEW"]}, "invalid_amendment")
        self.refuse({"replace_deferred_dependencies": {"OLD": "NEW"}, "depends_on": []}, "definition_weakening")
        back = dict(task("BACK"), operation="native", checks=["ownership", "effect"], required_scopes=["controlled-native"], depends_on=["TARGET"])
        self.call("add", "--file", self.write("back.json", back), "--expect", self.load()["revision"], "--actor", "P1")
        self.refuse({"replace_deferred_dependencies": {"OLD": "BACK"}}, "dependency_cycle")

    def test_save_failure_is_atomic_and_only_owned_lock_is_removed(self):
        self.init([task("TARGET")])
        with patch.object(tracker.os, "replace", side_effect=PermissionError("injected fake-ledger replace failure")):
            self.refuse({"checks": ["new"]}, "invalid_or_unreadable_state")

    def test_amend_schema_and_bounded_default_receipt_preserve_full_history(self):
        self.init([task("TARGET")])
        self.pin()
        current = self.claim("TARGET")
        current = self.update(current, "--evidence", self.evidence(observed="LARGE-RETAINED-" + "x" * 20000))["result"]
        self.release(current)
        result = self.amend({"checks": ["new"]})["result"]
        self.assertIn("amend", self.call("schema")["commands"])
        self.assertEqual(set(self.call("schema")["amendment_fields"]), {"paths", "checks", "required_scopes", "depends_on"})
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["history"], [])
        self.assertEqual(result["evidence_count"], 1)
        self.assertNotIn("LARGE-RETAINED-", json.dumps(result))
        page = self.call("show", "TARGET", "--history-limit", 1, "--evidence-limit", 0, "--at-task-revision", result["revision"])
        self.assertEqual(page["history"][-1]["action"], "amend")
        self.assertIn("before_definition", page["history"][-1])
        self.assertIn("after_definition", page["history"][-1])
        self.assertIn("LARGE-RETAINED-", self.load()["tasks"]["TARGET"]["evidence"][0]["observed"])


if __name__ == "__main__":
    unittest.main()
