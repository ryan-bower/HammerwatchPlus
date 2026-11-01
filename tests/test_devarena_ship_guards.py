"""Ship report evidence guards, with fake run directories and no generated data."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.devarena import ship_check  # noqa: E402

MOD = Path(__file__).resolve().parent / "fake-spec"


@pytest.fixture(autouse=True)
def isolated_tooltip_lint(monkeypatch):
    # This suite tests report acceptance, not numeric tooltip binding. Keep that
    # independent contract in the tooltip/clone tests without requiring an SDK.
    monkeypatch.setattr(ship_check.tooltip_lint, "skill_entries", lambda: {})
    monkeypatch.setattr(ship_check.tooltip_lint, "lint_spec", lambda entries, mod: (2, []))


def reply(cid, **kw):
    base = {"id": cid, "ok": True, "class": "ranger_test", "name": "Test Warden", "icon": True, "parent": "ranger",
            "siblings": ["ranger_marksman", "ranger_beasts", "ranger_nature", "ranger_test"], "pickerIndex": 3,
            "skillCount": 1, "stars": 33, "skills": [{"id": "s", "name": "S", "levels": 5, "cost": 33, "params": []}],
            "unresolved": [], "unresolvedCount": 0, "playerClass": "ranger", "picked": False, "picker": False}
    base.update(kw)
    return base


def write_run(tmp_path, replies, ok=True):
    lines = []
    for r in replies:
        lines += [json.dumps({"ev": "rx", "cid": r["id"], "verb": "da-ship"}), json.dumps(r)]
    lines.insert(0, json.dumps({"ev": "rx", "cid": "c0", "verb": "state"}))
    (tmp_path / "gl.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    inner = {"scenario": "hp6-ship", "mode": "lab", "partial": False,
             "assertions": [{"name": "a step", "ok": ok}]}
    record = {"scenario": "hp6-ship", "mode": "lab", "environment": "gamelab", "verdict": "PASS",
              "error": None, "partial": False, "build_drift": False, "teardown": {"clean": True},
              "assertions": inner["assertions"] + [{"name": "isolation guard", "ok": True}]}
    (tmp_path / "inner.json").write_text(json.dumps(inner), encoding="utf-8")
    (tmp_path / "run.json").write_text(json.dumps(record), encoding="utf-8")


def picked_run(tmp_path, ok=True):
    write_run(tmp_path, [reply("c1"),
                         reply("c2", picker=True, shows="ranger_test", **{"picked-class": "Test Warden"}),
                         reply("c3", picked=True, playerClass="ranger_test")], ok)


def rewrite(tmp_path, filename, updates=None, remove=()):
    path = tmp_path / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(updates or {})
    for key in remove:
        data.pop(key, None)
    path.write_text(json.dumps(data), encoding="utf-8")


def report(tmp_path):
    return ship_check.main(["--run", str(tmp_path), "--mod", str(MOD), "--out", str(tmp_path / "r.md")])


def test_outer_failure_cannot_ship(tmp_path):
    picked_run(tmp_path)
    rewrite(tmp_path, "run.json", {"verdict": "INVALID"})
    assert report(tmp_path) == 1
    assert "NOT SHIPPABLE" in (tmp_path / "r.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("updates", [
    {"verdict": "FAIL"}, {"verdict": "TIMEOUT"}, {"verdict": "ABORTED"},
    {"error": "native process crashed"}, {"partial": True}, {"partial": None},
    {"build_drift": True}, {"build_drift": None}, {"teardown": {"clean": False}},
    {"teardown": None}, {"mode": "watch"}, {"environment": "modded-prod"},
    {"scenario": "another-scenario"}, {"assertions": []}, {"assertions": None},
    {"assertions": "malformed"}, {"assertions": ["malformed"]},
    {"assertions": [{"name": "truthy is not true", "ok": 1}]},
])
def test_unsafe_outer_results_do_not_ship(tmp_path, updates):
    picked_run(tmp_path)
    rewrite(tmp_path, "run.json", updates)
    assert report(tmp_path) == 1
    assert "NOT SHIPPABLE" in (tmp_path / "r.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("key", ["verdict", "assertions", "partial", "build_drift", "teardown"])
def test_missing_outer_guards_do_not_ship(tmp_path, key):
    picked_run(tmp_path)
    rewrite(tmp_path, "run.json", remove=[key])
    assert report(tmp_path) == 1


@pytest.mark.parametrize("updates", [
    {"scenario": "another-scenario"}, {"mode": "watch"}, {"partial": True},
    {"error": "inner crashed"}, {"timeout": True}, {"assertions": []},
    {"assertions": [{"name": "a different step", "ok": True}]},
    {"assertions": [{"name": "a step", "ok": False}]},
    {"fixture": "stale-fixture"},
])
def test_unfinished_or_mismatched_inner_does_not_ship(tmp_path, updates):
    picked_run(tmp_path)
    rewrite(tmp_path, "inner.json", updates)
    assert report(tmp_path) == 1


def test_missing_inner_is_bad_input_and_preserves_existing_report(tmp_path):
    picked_run(tmp_path)
    (tmp_path / "inner.json").unlink()
    (tmp_path / "r.md").write_text("old report", encoding="utf-8")
    assert report(tmp_path) == 2
    assert (tmp_path / "r.md").read_text(encoding="utf-8") == "old report"


@pytest.mark.parametrize("filename", ["run.json", "inner.json"])
@pytest.mark.parametrize("text", ["not json", "[]", "null", '"text"'])
def test_malformed_result_is_bad_input(tmp_path, filename, text):
    picked_run(tmp_path)
    (tmp_path / filename).write_text(text, encoding="utf-8")
    assert report(tmp_path) == 2
    assert not (tmp_path / "r.md").exists()


@pytest.mark.parametrize("index", [0, 1, 2])
def test_failed_da_ship_reply_does_not_ship(tmp_path, index):
    replies = [reply("c1"), reply("c2", picker=True, shows="ranger_test"),
               reply("c3", picked=True, playerClass="ranger_test")]
    replies[index]["ok"] = False
    write_run(tmp_path, replies)
    assert report(tmp_path) == 1


def test_da_ship_replies_must_describe_the_same_class(tmp_path):
    write_run(tmp_path, [reply("c1"), reply("c2", picker=True, shows="ranger_test", **{"class": "stale_class"}),
                         reply("c3", picked=True, playerClass="ranger_test")])
    assert report(tmp_path) == 1


def test_zero_linted_skills_cannot_establish_correct_tooltips(tmp_path, monkeypatch):
    picked_run(tmp_path)
    monkeypatch.setattr(ship_check.tooltip_lint, "lint_spec", lambda entries, mod: (0, []))
    assert report(tmp_path) == 1
    assert "| its tooltips show its numbers | FAIL | 0 skills linted, 0 stale |" in (tmp_path / "r.md").read_text(encoding="utf-8")
