"""tools/devarena/ship_check.py, offline: a synthetic hp6-ship run over the committed spec mod."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.devarena import ship_check  # noqa: E402

MOD = Path(__file__).resolve().parents[1] / "mods" / "spec-ranger-test"


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
    (tmp_path / "run.json").write_text(json.dumps({"assertions": [{"name": "a step", "ok": ok}]}), encoding="utf-8")


def picked_run(tmp_path, ok=True):
    write_run(tmp_path, [reply("c1"),
                         reply("c2", picker=True, shows="ranger_test", **{"picked-class": "Test Warden"}),
                         reply("c3", picked=True, playerClass="ranger_test")], ok)


def test_a_picked_resolved_spec_ships(tmp_path):
    picked_run(tmp_path)
    out = tmp_path / "r.md"
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(MOD), "--out", str(out)]) == 0
    assert "SHIPPABLE" in out.read_text(encoding="utf-8") and "NOT SHIPPABLE" not in out.read_text(encoding="utf-8")


def test_unresolved_keys_or_a_failed_step_do_not_ship(tmp_path):
    write_run(tmp_path, [reply("c1", unresolved=["x.name"], unresolvedCount=1), reply("c2", picked=True, playerClass="ranger_test")])
    out = tmp_path / "r.md"
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(MOD), "--out", str(out)]) == 1
    text = out.read_text(encoding="utf-8")
    assert "| every lang key resolves | FAIL | x.name |" in text
    assert "| the Subclass Picker shows it | FAIL |" in text
    picked_run(tmp_path, ok=False)
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(MOD), "--out", str(out)]) == 1


def test_a_run_without_da_ship_is_a_bad_input(tmp_path):
    write_run(tmp_path, [])
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(MOD), "--out", str(tmp_path / "r.md")]) == 2
