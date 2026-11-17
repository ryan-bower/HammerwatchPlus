"""suite --since only skips scenarios whose earlier run passed cleanly on the pinned build."""
import json
from unittest.mock import patch

from gamelab import __main__ as cli

PIN = "build-1"


def _run(results, stamp, name, **over):
    d = results / f"{stamp}-{name}-lab"
    d.mkdir(parents=True)
    rec = {"scenario": name, "verdict": "PASS", "partial": False, "build_drift": False,
           "teardown": {"clean": True, "reasons": []}, "build": {"build_id": PIN}}
    rec.update(over)
    (d / "run.json").write_text(json.dumps(rec), encoding="utf-8")


def test_only_clean_pass_counts_as_done(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (tmp_path / "build_id.json").write_text(json.dumps({"build_id": PIN}), encoding="utf-8")
    _run(results, "20261101-100000", "ok")
    _run(results, "20261101-100001", "failed", verdict="FAIL")
    _run(results, "20261101-100002", "invalid", verdict="INVALID")
    _run(results, "20261101-100003", "timeout", verdict="TIMEOUT")
    _run(results, "20261101-100004", "partial", partial=True)
    _run(results, "20261101-100005", "dirty", teardown={"clean": False, "reasons": ["x"]})
    _run(results, "20261101-100006", "drift", build_drift=True)
    _run(results, "20261101-100007", "oldbuild", build={"build_id": "other"})
    _run(results, "20261031-100000", "early")
    with patch("gamelab.launcher.RESULTS", results):
        assert cli.ran_since("20261101-000000", "lab") == {"ok"}
