"""tools/devarena/clone_spec.py and make_compose.py, offline (no game)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.devarena import clone_spec, make_compose  # noqa: E402

BUILT = {"class": "Skills::PlayerSkillDirectional", "anim": "cast", "skill-cost": 5, "cooldown": 3000,
         "move-speed-mul": {"f": 0.5}, "blocking": {"ivec2": [0, 250]},
         "binds": {"proj-unit": "players/ranger/projectiles/marked_shot_arrow.unit", "proj-dmg": 40},
         "actions": {"cast": [{"class": "ShootProjectile", "projectile-bind": "proj-unit", "dist": 8}]},
         "timeline": [150, "cast"]}


def state(*edits):
    return {"schema": 1, "live": 1, "a": 0, "b": 1, "slot": "B", "pins": [],
            "versions": [{"note": "", "edits": [list(e) for e in edits]}]}


def log_with(st, dicts=()):
    # as Flush logs them: the version's compose-dicts, then "live vN"
    lines = [f"12:00:00 [HWP:devarena] compose-dict {s} {json.dumps(d)}" for s, d in dicts]
    lines.append(f"12:00:00 [HWP:devarena] live v{st['live']} (1 edits)")
    lines.append("12:00:01 [HWP:devarena] override " + json.dumps(st))
    return "\n".join(lines) + "\n"


def run(tmp_path, *extra):
    return clone_spec.main(["--from", "ranger_nature", "--id", "ranger_test", "--name", "Test Warden",
                            "--out", str(tmp_path), "--force", *extra])


def skill(tmp_path, name="hwp_ranger_test_nature_entangle"):
    return (tmp_path / "spec-ranger-test/players/hwp/spec_ranger_test/skills" / f"{name}.sval").read_text(encoding="utf-8")


def test_plain_clone_keeps_shared_skills_and_renames_own(tmp_path):
    assert run(tmp_path) == 0
    mod = tmp_path / "spec-ranger-test"
    cls = (mod / "players/hwp/spec_ranger_test/class_ranger_test.sval").read_text(encoding="utf-8")
    assert '<string name="id">ranger_test</string>' in cls and "%defblock SharedStats" in cls
    assert "players/ranger/skills/ran_trap.sval" in cls
    assert "players/hwp/spec_ranger_test/skills/hwp_ranger_test_nature_entangle.sval" in cls
    t = skill(tmp_path)
    assert ">nature_entangle_heal<" not in t and ">hwp_ranger_test_nature_entangle_heal<" in t
    assert json.loads((mod / "module.json").read_text())["requires"] == ["core"]
    assert "Test Warden" in (mod / "res/language/english/hwp_spec_ranger_test.lang").read_text(encoding="utf-8")


def test_plain_edits_patch_the_level_dict(tmp_path):
    log = tmp_path / "game.log"
    log.write_text(log_with(state(["nature_entangle", 0, "binds.area-dmg", "33"],
                                  ["nature_entangle", 0, "timeline.2", "120"])), encoding="utf-8")
    assert run(tmp_path / "out", "--log", str(log)) == 0
    t = skill(tmp_path / "out")
    base = re.search(r'^\t<dict name="skill">.*?^\t</dict>', t, flags=re.M | re.S).group(0)
    assert '<int name="area-dmg">33</int>' in base
    assert "<i>120</i><s>cast</s>" in base


def test_an_edit_the_file_does_not_spell_out_is_refused(tmp_path, capsys):
    log = tmp_path / "game.log"
    log.write_text(log_with(state(["nature_entangle", 0, "binds.no-such", "1"],
                                  ["ran_trap", 0, "cooldown", "1"])), encoding="utf-8")
    assert run(tmp_path / "out", "--log", str(log)) == 1
    out = capsys.readouterr().out
    assert "binds.no-such" in out and "does not own: ran_trap" in out


def test_compose_bakes_the_dict_and_keeps_the_star_budget(tmp_path, capsys):
    log = tmp_path / "game.log"
    draft = "t=projectile;p=marked_arrow;c=;s=;dt=;st=;n=Thorn Volley;src=;cp=;cd=;mc=;dmg="
    log.write_text(log_with(state(["nature_entangle", 0, "@compose", draft]), [("nature_entangle", BUILT)]),
                   encoding="utf-8")
    assert run(tmp_path / "out", "--log", str(log)) == 0, capsys.readouterr().out
    t = skill(tmp_path / "out")
    assert '<float name="move-speed-mul">0.5</float>' in t and '<ivec2 name="blocking">0 250</ivec2>' in t
    assert "entangle_area.unit" not in re.search(r'^\t<dict name="skill">.*?^\t</dict>', t, flags=re.M | re.S).group(0)
    up = re.search(r'^\t<array name="upgrades">.*?^\t</array>', t, flags=re.M | re.S).group(0)
    assert set(re.findall(r'<(\w+) name="', up.split("\n", 1)[1])) == {"int"}  # skill-cost only
    lang = (tmp_path / "out/spec-ranger-test/res/language/english/hwp_spec_ranger_test.lang").read_text(encoding="utf-8")
    assert "Thorn Volley" in lang


def test_compose_without_its_dict_line_is_refused(tmp_path):
    log = tmp_path / "game.log"
    log.write_text(log_with(state(["nature_entangle", 0, "@compose", "t=nova;n=X"])), encoding="utf-8")
    assert run(tmp_path / "out", "--log", str(log)) == 1


def test_a_base_class_is_not_a_subclass(tmp_path):
    try:
        clone_spec.main(["--from", "ranger", "--id", "x", "--name", "X", "--out", str(tmp_path)])
    except SystemExit as e:
        assert "subclass" in str(e)
    else:
        raise AssertionError("cloned a base class")


def test_compose_catalog_is_current():
    cat, _ = make_compose.catalog()
    assert make_compose.render(cat) == make_compose.OUT.read_text(encoding="utf-8")
    assert {p["id"] for p in cat["projectiles"]} >= {"marked_arrow", "magic_missile"}
    for p in cat["projectiles"]:
        assert p["unit"] and (make_compose.GAME / p["unit"]).is_file()


def test_a_changed_field_rewrites_its_tooltip_and_the_spec_lint_passes(tmp_path):
    from tools.devarena import tooltip_lint
    log = tmp_path / "game.log"
    log.write_text(log_with(state(["nature_entangle", 0, "cooldown", "5000"])), encoding="utf-8")
    assert run(tmp_path / "out", "--log", str(log)) == 0
    mod = tmp_path / "out/spec-ranger-test"
    t = skill(tmp_path / "out")
    assert "<s>.skills.desc.params.cooldown</s><s>5s</s>" in t and "<s>20s</s>" not in t
    entries = tooltip_lint.skill_entries()
    assert tooltip_lint.lint_spec(entries, mod) == (2, [])
    f = mod / "players/hwp/spec_ranger_test/skills/hwp_ranger_test_nature_entangle.sval"
    f.write_text(t.replace("<s>5s</s>", "<s>20s</s>"), encoding="utf-8")
    n, stale = tooltip_lint.lint_spec(entries, mod)
    assert n == 2 and {s["param"] for s in stale} == {"cooldown"}


def test_compose_drops_the_tooltip_rows_whose_fields_are_gone(tmp_path):
    log = tmp_path / "game.log"
    draft = "t=projectile;p=marked_arrow;c=;s=;dt=;st=;n=Thorn Volley;src=;cp=;cd=;mc=;dmg="
    log.write_text(log_with(state(["nature_entangle", 0, "@compose", draft]), [("nature_entangle", BUILT)]),
                   encoding="utf-8")
    assert run(tmp_path / "out", "--log", str(log)) == 0
    t = skill(tmp_path / "out")
    rows = re.search(r'<array name="description-params">.*?^\t</array>', t, flags=re.M | re.S).group(0)
    assert ".params.damage<" not in rows and ".params.duration<" not in rows
    assert "<s>.skills.desc.params.cooldown</s><s>3s</s>" in rows


def test_version_dicts_takes_the_compose_dict_logged_for_that_version():
    # review 6: the last compose-dict of a slot belonged to v3, and --version a (v1) shipped it
    log = "\n".join([
        '[NFO] [HWP:devarena] compose-dict nature_entangle {"cooldown":3000}',
        "[NFO] [HWP:devarena] live v1 (1 edits)",
        '[NFO] [HWP:devarena] compose-dict nature_entangle {"cooldown":9000}',
        "[NFO] [HWP:devarena] live v3 (2 edits)",
    ])
    assert clone_spec.version_dicts(log, 1) == {"nature_entangle": {"cooldown": 3000}}
    assert clone_spec.version_dicts(log, 3) == {"nature_entangle": {"cooldown": 9000}}
    assert clone_spec.version_dicts(log, 2) is None
