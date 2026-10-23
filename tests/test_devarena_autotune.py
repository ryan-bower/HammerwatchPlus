"""tools/devarena/autotune.py and gamelab/bots/devarena_autotune.py, offline (a fake game)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.devarena import autotune  # noqa: E402
from gamelab.bots import devarena_autotune as bot  # noqa: E402


def test_field_and_target_syntax():
    assert autotune.parse_field("ran_mark:binds.proj-dmg") == ("ran_mark", "binds.proj-dmg")
    assert autotune.parse_target("+15%") == 15.0 and autotune.parse_target("-7.5 %") == -7.5
    for bad in ("ran_mark", ":x", "a b:c"):
        with pytest.raises(ValueError):
            autotune.parse_field(bad)
    with pytest.raises(ValueError):
        autotune.parse_target("15")


def test_feel_locks_refuse_unless_unlocked():
    assert autotune.locked_by("castpoint") == "castpoint"
    assert autotune.locked_by("actions[0].cooldown") == "cooldown"
    assert autotune.locked_by("binds.move-speed-mul") == "move-speed-mul"
    assert autotune.locked_by("timeline[2]") == "timeline"
    assert autotune.locked_by("binds.proj-dmg") is None
    assert autotune.locked_by("castpoint", unlock=["castpoint"]) is None


def test_ladder_is_nearest_first_without_repeats():
    assert autotune.candidates(80, [4, 1.25, 2]) == [100, 160, 320]
    assert autotune.candidates(1, [1.25, 1.4]) == []          # both round back to 1
    assert autotune.candidates(0.5, [2], integer=False) == [1.0]
    assert autotune.candidates(80, [1.25, 2, 4], lo=90, hi=200) == [100, 160]
    assert autotune.midpoint(160, 320) == 240 and autotune.midpoint(3, 4) is None


def result(delta, verdict, a=300.0, b=None):
    return {"bench": 1, "A": {"mean": a, "version": 0}, "B": {"mean": b or a * (1 + delta / 100), "version": 1},
            "delta": delta, "verdict": verdict}


def test_target_needs_the_delta_and_the_verdict():
    assert autotune.meets(result(20, "B better"), 15)
    assert not autotune.meets(result(20, "no difference"), 15)   # noise, not a win
    assert not autotune.meets(result(10, "B better"), 15)
    assert autotune.meets(result(-12, "B worse"), -10)
    assert not autotune.meets({"A": None, "B": {}}, 15)


class FakeGame:
    """da-skill / da-set / da-dock / pointer / da-bench / da-propose, with a canned dps per value."""

    def __init__(self, dps_of, current=80, level=5):
        self.dps_of, self.current, self.level = dps_of, current, level
        self.version, self.bench, self.b_value, self.calls, self.last = 0, 0, None, [], None

    def cmd(self, verb, *args, **kw):
        self.calls.append((verb, *args))
        if verb == "da-skill":
            return {"ok": True, "level": self.level, "binds": {"proj-dmg": str(self.current)}}
        if verb == "da-set":
            assert args[1] == self.level - 1
            self.version += 1
            self.b_value = args[3]
            return {"ok": True, "version": self.version}
        if verb == "da-dock":
            return {"buttons": {args[0]: [900, 300]}}
        if verb == "pointer":
            if args[2] == "click":
                self.bench += 1
                a, b = 300.0, self.dps_of(self.b_value)
                d = 100 * (b - a) / a
                self.last = {"bench": self.bench, "A": {"mean": a, "version": 0}, "B": {"mean": b, "version": self.version},
                             "delta": d, "verdict": "B better" if d > 5 else "no difference"}
            return {"ok": True}
        if verb == "da-bench":
            return {"ok": True, "bench": self.bench, "running": False, "last": self.last}
        if verb == "da-propose":
            return {"ok": True, "version": self.version, "note": " ".join(args)}
        raise AssertionError(verb)


def test_bot_proposes_the_first_candidate_that_meets(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda s: None)
    g = FakeGame(lambda v: 300 + (v - 80) * 0.5)      # 100 -> +3.3%, 160 -> +13.3%, 320 -> +40%
    r = bot.run(g, ["ran_mark:binds.proj-dmg"], "+15%", [1.25, 2, 4], bisect=0)
    assert r["terminal"] == "proposed" and r["to"] == 320 and r["from"] == 80
    assert [t["value"] for t in r["trials"]] == [100, 160, 320] and [t["meets"] for t in r["trials"]] == [False, False, True]
    # one halving between the last miss (100) and the hit (320): 210 is +21.7%, so it is proposed
    g = FakeGame(lambda v: 300 + (v - 80) * 0.5)
    r = bot.run(g, ["ran_mark:binds.proj-dmg"], "+15%", [1.25, 4], bisect=1)
    assert [t["value"] for t in r["trials"]] == [100, 320, 210] and r["to"] == 210 and g.b_value == 210
    # the halving misses at +30%: B is put back to the hit and re-benched, so the evidence is B's
    g = FakeGame(lambda v: 300 + (v - 80) * 0.5)
    r = bot.run(g, ["ran_mark:binds.proj-dmg"], "+30%", [1.25, 4], bisect=1)
    assert [t["value"] for t in r["trials"]] == [100, 320, 210, 320] and r["to"] == 320 and g.b_value == 320
    propose = [c for c in g.calls if c[0] == "da-propose"][0]
    assert all(ch.isalnum() or ch in " ._-+:," for ch in " ".join(map(str, propose[1:])))


def test_bot_refuses_a_feel_locked_field_and_reports_no_candidate(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda s: None)
    g = FakeGame(lambda v: 300)
    assert bot.run(g, ["ran_mark:castpoint"], "+15%")["terminal"] == "locked"
    assert not [c for c in g.calls if c[0] == "da-set"]
    r = bot.run(g, ["ran_mark:binds.proj-dmg"], "+15%", [1.25, 2])
    assert r["terminal"] == "no_candidate" and len(r["trials"]) == 2
    assert not [c for c in g.calls if c[0] == "da-propose"]


def test_report_pairs_each_proposal_with_its_outcome(tmp_path):
    ev = {"bench": 3, "A": {"mean": 300, "sd": 20, "n": 3}, "B": {"mean": 400, "sd": 25, "n": 3}, "delta": 33.3,
          "verdict": "B better", "golem": "footman elite", "ngp": 3, "driver": "bot"}
    log = tmp_path / "logs" / "pass1.HWR2.exe.log"
    log.parent.mkdir()
    log.write_text("\n".join([
        "x [HWP:devarena] autotune-proposal " + json.dumps({"version": 2, "base": 0, "bench": 3, "note": "n1", "evidence": ev}),
        "x [HWP:devarena] autotune-discard " + json.dumps({"version": 2, "bench": 3, "note": "n1"}),
        "x [HWP:devarena] autotune-proposal " + json.dumps({"version": 5, "base": 0, "bench": 6, "note": "n2", "evidence": ev}),
        "x [HWP:devarena] autotune-accept " + json.dumps({"version": 5, "bench": 6, "note": "n2"}),
    ]) + "\n", encoding="utf-8")
    out = tmp_path / "r.md"
    assert autotune.main(["--run", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "| 1 | v2 over v0 | n1 |" in text and "| discard |" in text
    assert "| 2 | v5 over v0 | n2 |" in text and "| accept |" in text
    (tmp_path / "logs" / "pass1.HWR2.exe.log").write_text("nothing\n", encoding="utf-8")
    assert autotune.main(["--run", str(tmp_path), "--out", str(out)]) == 1
