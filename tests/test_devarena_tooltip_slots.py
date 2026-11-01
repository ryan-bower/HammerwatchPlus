"""Surviving tooltip slots use authored row identity, with real lint/rewrite consumers."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.devarena import clone_spec, tooltip_lint as lint  # noqa: E402


def entry(fields, rows, sid="s"):
    return {"id": sid, "skill": fields, "description-params": rows}


def pair(shown="20s"):
    vanilla = entry({"damage": 20, "duration": 7000, "cooldown": 20000}, [
        ["damage", ".p.damage", "20"],
        ["duration", True, ".p.duration", "7s"],
        ["cooldown", True, ".p.cooldown", "20s"],
    ])
    spec = entry({"cooldown": 3000}, [["cooldown", True, ".p.cooldown", shown]], "hwp_t_s")
    return vanilla, spec


@pytest.fixture
def mod_root(tmp_path_factory):
    # Keep deep Windows clone paths beneath a short private pytest node.
    return tmp_path_factory.mktemp("s") / "m"


def lint_pair(mod_root, vanilla, spec):
    folder = mod_root / "players/hwp/spec_t"
    (folder / "skills").mkdir(parents=True, exist_ok=True)
    (folder / "class_t.sval").write_text("<dict></dict>\n", encoding="utf-8")
    text = lint.overrides.hwr_archive.svalue_to_xml(spec)
    (folder / "skills/s.sval").write_text(text, encoding="utf-8")
    return lint.lint_spec({"s": vanilla}, mod_root)


def test_lint_checks_retained_row_after_prior_rows_were_dropped(mod_root):
    vanilla, spec = pair()
    n, stale = lint_pair(mod_root, vanilla, spec)
    assert n == 1 and len(stale) == 1
    assert stale[0] == {"skill": "hwp_t_s", "param": "cooldown", "level": 1,
                        "shown": "20s", "fields": {"cooldown": 3000.0}}


def test_rewrite_uses_retained_spec_slot_and_leaves_removed_rows_absent():
    vanilla, spec = pair()
    original = copy.deepcopy(spec)
    changes, notes = lint.rewrite_params(vanilla, spec)
    assert changes == [(0, ["3s"])]
    assert len(notes) == 1 and "20s -> 3s" in notes[0]
    assert spec == original


def test_correct_retained_row_stays_clean(mod_root):
    vanilla, spec = pair("3s")
    assert lint_pair(mod_root, vanilla, spec) == (1, [])
    assert lint.rewrite_params(vanilla, spec) == ([], [])


def test_clone_tooltip_rewrite_updates_the_shifted_row():
    vanilla, _ = pair()
    text = ('<dict>\n\t<string name="id">hwp_t_s</string>\n'
            '\t<dict name="skill">\n\t\t<int name="cooldown">3000</int>\n\t</dict>\n'
            '\t<array name="description-params">\n'
            '\t\t<array><s>cooldown</s><b>true</b><s>.p.cooldown</s><s>20s</s></array>\n'
            '\t</array>\n</dict>\n')
    fixed, notes = clone_spec.fix_tooltips(text, vanilla)
    assert lint.params(lint.parse_sval_text(fixed)) == [("cooldown", ["3s"])]
    assert len(notes) == 1


def test_same_key_different_labels_bind_to_the_right_fields(mod_root):
    vanilla = entry({"physical": 20, "magical": 40}, [
        ["damage", ".p.physical", "20"], ["damage", ".p.magical", "40"],
    ])
    spec = entry({"magical": 80}, [["damage", ".p.magical", "40"]], "hwp_t_s")
    n, stale = lint_pair(mod_root, vanilla, spec)
    assert n == 1 and stale[0]["fields"] == {"magical": 80.0}
    assert lint.rewrite_params(vanilla, spec)[0] == [(0, ["80"])]


def test_exact_duplicate_rows_keep_occurrence_order_when_all_remain(mod_root):
    rows = [["damage", ".p.damage", "20"], ["damage", ".p.damage", "40"]]
    vanilla = entry({"physical": 20, "magical": 40}, rows)
    spec = entry({"physical": 30, "magical": 40}, copy.deepcopy(rows), "hwp_t_s")
    n, stale = lint_pair(mod_root, vanilla, spec)
    assert n == 1 and len(stale) == 1 and stale[0]["fields"] == {"physical": 30.0}
    assert lint.rewrite_params(vanilla, spec)[0] == [(0, ["30"])]


def test_partial_exact_duplicate_rows_are_ambiguous(mod_root):
    vanilla = entry({"physical": 20, "magical": 40}, [
        ["damage", ".p.damage", "20"], ["damage", ".p.damage", "40"],
    ])
    spec = entry({"magical": 80}, [["damage", ".p.damage", "40"]], "hwp_t_s")
    with pytest.raises(ValueError, match="ambiguous"):
        lint_pair(mod_root, vanilla, spec)
    with pytest.raises(ValueError, match="ambiguous"):
        lint.rewrite_params(vanilla, spec)


def test_optional_flag_is_part_of_row_identity(mod_root):
    vanilla = entry({"fast": 1000, "slow": 2000}, [
        ["time", ".p.time", "1s"], ["time", True, ".p.time", "2s"],
    ])
    spec = entry({"slow": 3000}, [["time", True, ".p.time", "2s"]], "hwp_t_s")
    _, stale = lint_pair(mod_root, vanilla, spec)
    assert stale[0]["fields"] == {"slow": 3000.0}
    assert lint.rewrite_params(vanilla, spec)[0] == [(0, ["3s"])]


def test_unrelated_row_label_is_not_substituted(mod_root):
    vanilla = entry({"physical": 20}, [["damage", ".p.physical", "20"]])
    spec = entry({"unrelated": 40}, [["damage", ".p.unrelated", "40"]], "hwp_t_s")
    assert lint_pair(mod_root, vanilla, spec) == (1, [])
    assert lint.rewrite_params(vanilla, spec) == ([], [])
