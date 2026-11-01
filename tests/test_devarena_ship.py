"""tools/devarena/ship_check.py, offline: a synthetic hp6-ship run over the committed spec mod."""
import json
import shutil
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


def test_ship_main_checks_real_numeric_tooltip_values(tmp_path_factory):
    # The cloned skill paths are long; keep this temporary root short on Windows.
    tmp_path = tmp_path_factory.mktemp("n")
    picked_run(tmp_path)
    valid = tmp_path / "valid.md"
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(MOD), "--out", str(valid)]) == 0
    assert "| its tooltips show its numbers | pass | 2 skills linted, 0 stale |" in valid.read_text(encoding="utf-8")

    bad_mod = tmp_path / "m"
    shutil.copytree(MOD, bad_mod)
    skill = bad_mod / "players/hwp/spec_ranger_test/skills/hwp_ranger_test_nature_wind_weaver.sval"
    text = skill.read_text(encoding="utf-8")
    shown = "<s>.skills.desc.params.damage</s><s>20%</s>"
    assert shown in text
    skill.write_text(text.replace(shown, "<s>.skills.desc.params.damage</s><s>99%</s>", 1), encoding="utf-8")
    stale = tmp_path / "stale.md"
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(bad_mod), "--out", str(stale)]) == 1
    report = stale.read_text(encoding="utf-8")
    assert "| its tooltips show its numbers | FAIL | 2 skills linted," in report
    assert "damage shows '99%'" in report and "binds.mainhand-dmg-mul" in report


def test_ship_main_rejects_stale_composed_tooltip(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("c")
    picked_run(tmp_path)
    bad_mod = tmp_path / "m"
    shutil.copytree(MOD, bad_mod)
    skill = bad_mod / "players/hwp/spec_ranger_test/skills/hwp_ranger_test_nature_entangle.sval"
    text = skill.read_text(encoding="utf-8")
    shown = "<s>.skills.desc.params.cooldown</s><s>3s</s>"
    assert shown in text
    skill.write_text(text.replace(shown, "<s>.skills.desc.params.cooldown</s><s>20s</s>", 1), encoding="utf-8")
    out = tmp_path / "r.md"
    assert ship_check.main(["--run", str(tmp_path), "--mod", str(bad_mod), "--out", str(out)]) == 1
    report = out.read_text(encoding="utf-8")
    assert "NOT SHIPPABLE" in report
    assert "cooldown shows '20s'" in report and "3000" in report
