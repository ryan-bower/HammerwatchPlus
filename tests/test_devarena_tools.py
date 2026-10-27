import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.devarena import curve, overrides  # noqa: E402

STATE = {
    "schema": 1, "live": 3, "a": 0, "b": 3, "slot": "B", "pins": ["entangle|binds.area-dmg|3"],
    "versions": [
        {"note": "area-dmg L5 = 99", "edits": [["entangle", 4, "binds.area-dmg", "99"]]},
        {"note": "growth", "edits": [["entangle", 1, "binds.area-dmg", "35"], ["entangle", 4, "binds.area-dmg", "81"]]},
        {"note": "castpoint 100", "edits": [["entangle", 0, "castpoint", "100"], ["entangle", 0, "timeline.1", "100"]]},
    ],
}


def test_override_line_round_trips_through_the_sval():
    line = "12:00:01 [HWP:devarena] override " + __import__("json").dumps(STATE)
    log = "noise\n" + line.replace('"live": 3', '"live": 1').replace('"b": 3', '"b": 1') + "\n" + line + "\nmore\n"
    st = overrides.last_in(log)
    assert st == STATE
    text = overrides.to_sval(st)
    assert text.startswith("<!--")
    assert overrides.from_sval(text) == STATE


def test_empty_sval_in_the_mod_reads_as_vanilla():
    st = overrides.from_sval(overrides.SVAL.read_text(encoding="utf-8"))
    assert st == overrides.empty()
    assert overrides.to_sval(st) == overrides.SVAL.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", [
    {"live": 9}, {"slot": "B", "b": -1}, {"schema": 2},
    {"versions": [{"note": "x", "edits": [["entangle", "4", "p", "1"]]}]},
])
def test_bad_states_are_refused(bad):
    with pytest.raises(ValueError):
        overrides.check({**overrides.empty(), **bad})


def test_sync_writes_from_a_log(tmp_path):
    log = tmp_path / "HWR2.exe.log"
    log.write_text("[HWP:devarena] override " + __import__("json").dumps(STATE) + "\n", encoding="utf-8")
    out = tmp_path / "o.sval"
    assert overrides.main(["sync", "--log", str(log), "--out", str(out)]) == 0
    assert overrides.from_sval(out.read_text(encoding="utf-8")) == STATE
    assert overrides.main(["sync", "--log", str(tmp_path / "missing.log"), "--out", str(out)]) == 1


def test_growth_matches_the_tuner_run():
    # gamelab/results/20261020-225735-tuner-dock-lab: Entangle area-dmg, vanilla 20,25,35,45,60
    v = [20, 25, 35, 45, 60]
    assert curve.fit_growth(v) == pytest.approx(9.0)
    assert curve.growth_step(20, True) == 1
    edits = curve.growth_edits([20, 25, 35, 45, 99], 15.2, True, pinned=frozenset())
    assert edits == [(1, "35"), (2, "50"), (3, "66"), (4, "81")]
    assert curve.growth_edits([20, 35, 50, 66, 81], 15.2, True, pinned={3}) == []


def test_rounding_and_steps():
    assert curve.round_int(2.5) == 3 and curve.round_int(-2.5) == -3 and curve.round_int(-2.4) == -2
    assert curve.num_text(1.23456, False) == "1.235"
    assert curve.growth_step(0, False) == 0.05
    assert curve.growth_step(3.0, False) == pytest.approx(0.15)
    assert curve.growth_step(-100, True) == 5


def test_level_values_fall_back_to_the_base():
    base = {"castpoint": 300, "binds": {"area-dmg": 20}}
    ups = [{"binds": {"area-dmg": 25}}, {}]
    assert curve.level_values(base, ups, "binds.area-dmg") == [20, 25, 20]


SKILL = """<dict>
	<string name="id">hwp_test_bolt</string>
	<dict name="skill">
		<int name="castpoint">300</int>
		<dict name="binds">
			<int name="dmg">20</int>
		</dict>
	</dict>
	<array name="upgrades">
		<dict>
			<dict name="binds">
				<int name="dmg">25</int>
			</dict>
		</dict>
	</array>
	<array name="modifier-skills">
		<dict>
			<string name="id">hwp_test_bolt_orb</string>
		</dict>
	</array>
</dict>
"""


def test_export_picks_a_version():
    from tools.devarena import export
    assert export.pick(STATE, "live") == 3 and export.pick(STATE, "a") == 0 and export.pick(STATE, "v2") == 2
    with pytest.raises(ValueError):
        export.pick(STATE, "4")
    assert export.version_edits(STATE, 2) == STATE["versions"][1]["edits"]
    assert export.version_edits(STATE, 0) == []


def test_export_bakes_into_the_mod_skill_file(tmp_path):
    from tools.devarena import export
    f = tmp_path / "mods" / "specs" / "players" / "skills" / "bolt.sval"
    f.parent.mkdir(parents=True)
    f.write_text(SKILL, encoding="utf-8")
    (tmp_path / "mods" / "devarena" / "x.sval").parent.mkdir(parents=True)
    (tmp_path / "mods" / "devarena" / "x.sval").write_text(SKILL.replace("hwp_test_bolt", "da_bolt"), encoding="utf-8")
    texts, refused, _ = export.bake([["hwp_test_bolt", 0, "castpoint", "150"], ["hwp_test_bolt", 1, "binds.dmg", "30"]],
                                    tmp_path / "mods")
    assert refused == [] and list(texts) == [f]
    assert '<int name="castpoint">150</int>' in texts[f] and '<int name="dmg">30</int>' in texts[f]
    assert '<int name="dmg">20</int>' in texts[f]
    assert f.read_text(encoding="utf-8") == SKILL, "bake writes nothing itself"


@pytest.mark.parametrize("edit, why", [
    (["ran_mark", 0, "cooldown", "1"], "vanilla"),
    (["hwp_test_bolt_orb", 0, "castpoint", "1"], "sub-skill"),
    (["hwp_test_bolt", 0, "cooldown", "1"], "not spelled out"),
    (["hwp_test_bolt", 0, "@compose", "{}"], "composed"),
    (["da_bolt", 0, "castpoint", "1"], "vanilla"),
])
def test_export_refuses(tmp_path, edit, why):
    from tools.devarena import export
    f = tmp_path / "mods" / "classes" / "bolt.sval"
    f.parent.mkdir(parents=True)
    f.write_text(SKILL, encoding="utf-8")
    (tmp_path / "mods" / "devarena").mkdir()
    (tmp_path / "mods" / "devarena" / "x.sval").write_text(SKILL.replace("hwp_test_bolt", "da_bolt"), encoding="utf-8")
    _, refused, _ = export.bake([edit], tmp_path / "mods")
    assert len(refused) == 1 and why in refused[0]
