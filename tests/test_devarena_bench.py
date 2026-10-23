"""Bench statistics and log tooling (tools/devarena/bench.py)."""
import json
import math
import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo))

from tools.devarena import bench  # noqa: E402


def test_stats_known_values():
    s = bench.stats([100, 110, 90, 100, 100])
    assert s["n"] == 5
    assert s["mean"] == 100
    assert math.isclose(s["sd"], math.sqrt(50))
    assert math.isclose(s["rel"], 2.776 * math.sqrt(50) / math.sqrt(5) / 100)
    assert s["nFor3"] == 43


def test_stats_edges():
    assert bench.stats([])["n"] == 0
    one = bench.stats([250])
    assert one["mean"] == 250 and one["sd"] == 0 and one["rel"] == 0
    flat = bench.stats([300, 300, 300])
    assert flat["sd"] == 0 and flat["rel"] == 0 and flat["nFor3"] == 3


def test_tcrit_falls_back_to_normal():
    assert bench.tcrit(1) == 12.706
    assert bench.tcrit(30) == 2.042
    assert bench.tcrit(200) == 1.96
    assert bench.tcrit(0) == float("inf")


def test_compare_verdicts():
    a = [500, 510, 495, 505, 490]
    assert bench.compare(a, [600, 610, 595, 605, 590])["verdict"] == "B better"
    assert bench.compare(a, [400, 410, 395, 405, 390])["verdict"] == "B worse"
    assert bench.compare(a, [502, 508, 497, 503, 492])["verdict"] == "no difference"
    assert bench.compare([500], [600])["verdict"] == "too few pulls"
    c = bench.compare(a, [600, 610, 595, 605, 590])
    assert math.isclose(c["delta"], 100 * (600 - 500) / 500)


def test_compare_zero_spread():
    assert bench.compare([5, 5], [5, 5])["verdict"] == "no difference"
    assert bench.compare([5, 5], [6, 6])["verdict"] == "B better"


def _log(pulls, results, promote=None):
    lines = ["noise line", "[HWP:devarena] golem-pull {\"dps\":1}"]
    for p in pulls:
        lines.append("[12:00:00] [HWP:devarena] bench-pull " + json.dumps(p))
    for r in results:
        lines.append("[HWP:devarena] bench-result " + json.dumps(r))
    if promote:
        lines.append("[HWP:devarena] bench-promote " + json.dumps(promote))
    lines.append("[HWP:devarena] bench-pull {broken")
    return "\n".join(lines)


def _bench(a, b):
    pulls = []
    for i, (x, y) in enumerate(zip(a, b)):
        pulls.append({"bench": 1, "variant": "A", "pull": 2 * i + 1, "dps": x, "preset": "ranger_nature/early",
                      "version": 1, "mode": "stats", "golem": "guard_footman_elite", "ngp": 3, "pool": 4000000})
        pulls.append({"bench": 1, "variant": "B", "pull": 2 * i + 2, "dps": y, "preset": "ranger_nature/early",
                      "version": 2, "mode": "stats", "golem": "guard_footman_elite", "ngp": 3, "pool": 4000000})
    sa, sb, c = bench.stats(a), bench.stats(b), bench.compare(a, b)
    res = {"bench": 1, "preset": "ranger_nature/early", "golem": "guard_footman_elite", "ngp": 3,
           "pool": 4000000, "rotation": "default", "mode": "stats",
           "A": dict(sa, version=1), "B": dict(sb, version=2), "verdict": c["verdict"], "delta": c["delta"]}
    return pulls, res


def test_rows_join_pulls_with_their_result():
    pulls, res = _bench([500, 510, 495], [600, 610, 595])
    rs = bench.rows(_log(pulls, [res]), run="r1")
    assert len(rs) == 6
    assert {r["variant"] for r in rs} == {"A", "B"}
    b = [r for r in rs if r["variant"] == "B"][0]
    assert b["run"] == "r1" and b["version"] == 2 and b["mode"] == "stats"
    assert b["n"] == 3 and b["verdict"] == "B better"
    assert set(rs[0]) == set(bench.COLUMNS)


def test_check_results_agrees_and_catches_a_wrong_verdict():
    pulls, res = _bench([500, 510, 495, 505, 490], [600, 610, 595, 605, 590])
    assert bench.check_results(_log(pulls, [res])) == []
    bad = dict(res, verdict="no difference")
    assert len(bench.check_results(_log(pulls, [bad]))) == 1
    off = dict(res, A=dict(res["A"], mean=1))
    assert len(bench.check_results(_log(pulls, [off]))) == 1


def test_write_csv(tmp_path):
    pulls, res = _bench([500, 510], [600, 610])
    path, rs = bench.write_csv(_log(pulls, [res]), "runX", out=tmp_path)
    assert path.name == "runX.csv" and len(rs) == 4
    text = path.read_text(encoding="utf-8").splitlines()
    assert text[0].split(",") == bench.COLUMNS
    assert len(text) == 5
    bench.write_csv(_log(pulls, [res]), "runY", out=tmp_path)
    assert len((tmp_path / "all.csv").read_text(encoding="utf-8").splitlines()) == 9


def test_baseline_round_trip(tmp_path):
    _, r1 = _bench([500, 510, 495], [600, 610, 595])
    r1.pop("B")
    r2 = dict(r1, preset="ranger_hunter/early", A=dict(r1["A"], mean=444.0))
    rows = bench.baseline_rows(_log([], [r1, r2]))
    assert [r["preset"] for r in rows] == ["ranger_hunter/early", "ranger_nature/early"]
    p = tmp_path / "base.sval"
    p.write_text(bench.baseline_sval(rows), encoding="utf-8")
    back = bench.read_baseline(p)
    assert back == [dict(r, mean=round(r["mean"], 1), sd=round(r["sd"], 1)) for r in rows]
    newer = [dict(rows[0], mean=999.0)]
    merged = bench.merge_baseline(back, newer)
    assert len(merged) == 2 and merged[0]["mean"] == 999.0


def test_siblings_and_rank():
    base = [{"preset": p, "mean": m} for p, m in [
        ("ranger_nature/early", 500), ("ranger_hunter/early", 600), ("ranger_marksman/early", 400),
        ("paladin_divine/early", 700), ("ranger_hunter/late", 9000)]]
    s = bench.siblings("ranger_nature", "early", base)
    assert sorted(r["preset"] for r in s["siblings"]) == ["ranger_hunter/early", "ranger_marksman/early"]
    assert len(s["all"]) == 4
    assert bench.rank(550, s["all"]) == 3
    assert bench.rank(800, s["all"]) == 1


def test_promote_writes_once(tmp_path):
    _, res = _bench([500, 510, 495], [600, 610, 595])
    res["when"] = "2026-10-21"
    text = _log([], [], promote=res)
    out = bench.promote(text, out=tmp_path)
    assert [p.name for p in out] == ["ranger_nature.md"]
    md = out[0].read_text(encoding="utf-8")
    assert "Verdict: **B better**" in md and "| B (v2) | 3 |" in md
    assert bench.promote(text, out=tmp_path) == []
