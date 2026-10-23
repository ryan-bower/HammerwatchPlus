import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from tools import make_presets as mp  # noqa: E402
from tools.devarena import gamedata as gd  # noqa: E402
from tools.devarena import tooltip_lint as tl  # noqa: E402

# Lines the Loadout tab logged in gamelab/results/20261020-232844-loadout-dock-lab: level [+],
# str [+] on paladin_divine/early, Save variant, and a star.
LOG = """\
[NFO] [23:29:04] [HWP:devarena] loadout-favorites ["paladin_divine/early"]
[NFO] [23:29:08] [HWP:devarena] loadout-variant {"id":"paladin_divine/early+e1","from":"paladin_divine/early","level":6,"rows":[["stat","str","9"],["stat","vit","4"],["skill","divine_pillars","1"],["skill","divine_protection","1"],["equip","mainhand_mace_01"],["equip","offhand_shield_01"],["equip","head_str_t1a"],["equip","chest_str_t1a"],["equip","feet_str_t1a"],["equip","hands_str_1a"],["trinket","book_attacks"],["trinket","amulet_health"]]}
"""


@pytest.fixture(scope="module")
def presets():
    return mp.all_presets()


def test_gamedata_budgets_and_classes():
    assert gd.stars_at(1) == 0 and gd.stat_points_at(5) == 12 and gd.stat_points_at(20) == 57
    subs = gd.subclasses()
    assert len(subs) == 24 and all(c.parent for c in subs)


def test_every_preset_is_valid_and_the_file_is_current(presets):
    assert len(presets) >= 72
    assert len({p["id"] for p in presets}) == len(presets)
    bad = {p["id"]: mp.validate(p) for p in presets if mp.validate(p)}
    assert bad == {}
    assert mp.OUT.read_text(encoding="utf-8") == mp.to_sval(presets)


def test_tiers_spend_the_whole_budget(presets):
    early = next(p for p in presets if p["id"] == "paladin_divine/early")
    stats = sum(int(r[2]) for r in early["rows"] if r[0] == "stat")
    assert early["level"] == 5 and stats == gd.stat_points_at(5)


def test_import_log_round_trips_a_saved_variant(tmp_path, monkeypatch, presets):
    hand = tmp_path / "presets_hand.json"
    hand.write_text(mp.HAND.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(mp, "HAND", hand)
    assert mp.import_log(LOG) == (1, True)
    doc = json.loads(hand.read_text(encoding="utf-8"))
    v = doc["variants"][-1]
    assert v["from"] == "paladin_divine/early" and v["level"] == 6
    # the base places str 9 vit 3 (chest_str_t1a's str 12 first); the logged build had vit 4
    assert v["set"] == [["stat", "vit", "4"]] and "drop" not in v and "add" not in v
    assert doc["favorites"] == ["paladin_divine/early"]

    p = next(x for x in mp.all_presets() if x["id"] == v["id"])
    assert mp.validate(p) == []
    logged = json.loads(LOG.splitlines()[1].split("loadout-variant ", 1)[1])
    assert [r[:2] + r[2:3] for r in p["rows"] if r[0] in mp.KEYED] == [r for r in logged["rows"] if r[0] in mp.KEYED]
    assert mp.favorites(mp.all_presets()) == ["paladin_divine/early"]

    # the same line again is a new id, not a clobber
    assert mp.import_log(LOG) == (1, False)
    ids = [x["id"] for x in json.loads(hand.read_text(encoding="utf-8"))["variants"]]
    assert ids[-2:] == ["paladin_divine/early+e1", "paladin_divine/early+e2"]


def test_validate_reports_gear_the_stats_cannot_wear(presets):
    p = next(x for x in presets if x["id"] == "priest_crusader/mid")
    bad = {**p, "rows": [r for r in p["rows"] if r[0] != "stat"]}
    errs = mp.validate(bad)
    assert any("mainhand_scepter_02: unusable" in e and "skills stay blocked" in e for e in errs)


def test_diff_variant_drops_and_adds(presets):
    base = next(p for p in presets if p["id"] == "ranger_nature/mid")
    rows = [r for r in base["rows"] if r[0] != "trinket"] + [["trinket", "x_new"]]
    v = mp.diff_variant(base, {"id": "t", "rows": rows})
    assert v["add"] == [["trinket", "x_new"]]
    assert {tuple(d) for d in v["drop"]} == {tuple(r[:2]) for r in base["rows"] if r[0] == "trinket"}
    assert "set" not in v and "level" not in v


@pytest.fixture(scope="module")
def skills():
    return tl.skill_entries()


def test_lint_vanilla_has_nothing_stale(skills):
    assert len(skills) > 300
    assert sum(len(tl.bind(e)[0]) for e in skills.values()) > 300
    assert [s for sid in skills for s in tl.stale(skills, [[sid, 0, "\0none", ""]])] == []


def test_lint_binds_with_units(skills):
    bound, unbound = tl.bind(skills["charge"])
    assert unbound == 0
    assert bound == {0: (["binds.charge-dmg"], 1.0), 1: (["mana-cost"], 1.0), 2: (["cooldown"], 0.001)}
    # "tick-rate 0.5s" must not bind to move-speed-mul 0.5
    assert all("move-speed-mul" not in b[0] for b in tl.bind(skills["nature_entangle"])[0].values())


def test_lint_reports_edits_that_the_tooltip_misses(skills):
    found = tl.stale(skills, [["charge", 1, "binds.charge-dmg", "55"], ["nature_entangle", 4, "binds.area-dmg", "99"]])
    assert [(s["skill"], s["level"], s["param"], s["shown"]) for s in found] == [
        ("charge", 2, "damage", "50"), ("nature_entangle", 5, "damage", "60")]
    # a base edit an upgrade overrides is stale at level 1 only (upgrades overlay the base, PlayerBase.as:179-187)
    found = tl.stale(skills, [["charge", 0, "binds.charge-dmg", "41"]])
    assert [s["level"] for s in found] == [1]
    # an edit that keeps the shown value is not stale
    assert tl.stale(skills, [["charge", 0, "cooldown", "3000"]]) == []


def test_lint_cli(tmp_path, capsys):
    from tools.devarena import overrides
    state = overrides.empty()
    state["versions"] = [{"note": "cd", "edits": [["charge", 0, "cooldown", "4000"]]}]
    state["live"] = 1
    sval = tmp_path / "o.sval"
    sval.write_text(overrides.to_sval(state), encoding="utf-8")
    assert tl.main(["--from", str(sval)]) == 1
    out = capsys.readouterr().out
    assert "vanilla stale 0" in out and "1 edits, 5 stale" in out
    assert tl.main(["--stats"]) == 0
