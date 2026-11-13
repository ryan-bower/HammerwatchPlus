"""mods/objectives: the per-floor vault and exit-seal chances (issue #67).

Offline source and data checks; the game was not run:

- module.json has `objectives.vault_chance` (25 %) and `objectives.exit_chance` (15 %), host-scoped
  like the other objectives settings, with the agreed values.
- ObjectivesModule.as RefreshSettings reads both keys with those defaults, and Generation.as Run
  rolls each vault slot before PlaceVault and the exit once before PlaceExitSwitch.
- Every GameLab scenario that expects a vault or the exit switch on a floor forces both chances to
  100 before the floor is generated, so it does not depend on the roll.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mods" / "objectives"
SCRIPTS = MOD / "scripts" / "HWP" / "Objectives"
SCENARIOS = REPO / "gamelab" / "scenarios"
VALUES = [0, 10, 15, 25, 50, 75, 100]


def settings():
    cfg = json.loads((MOD / "module.json").read_text(encoding="utf-8"))["config"]
    assert cfg["scope"] == "host"
    return {s["key"]: s for s in cfg["settings"]}


@pytest.mark.parametrize("key,default", [("objectives.vault_chance", 25), ("objectives.exit_chance", 15)])
def test_chance_settings(key, default):
    s = settings()[key]
    assert s["type"] == "int"
    assert s["default"] == default
    assert s["values"] == VALUES
    assert s.get("suffix") == "%"


def test_refresh_settings_reads_the_chances():
    src = (SCRIPTS / "ObjectivesModule.as").read_text(encoding="utf-8")
    body = re.search(r"void RefreshSettings\(\)\s*\{(.*?)\n\t\t\}", src, re.S).group(1)
    assert re.search(r'g_vaultChance = clamp\(HWP::Settings::GetInt\("objectives\.vault_chance", VAULT_CHANCE\), 0, 100\)', body)
    assert re.search(r'g_exitChance = clamp\(HWP::Settings::GetInt\("objectives\.exit_chance", EXIT_CHANCE\), 0, 100\)', body)
    assert "const int VAULT_CHANCE = 25;" in src
    assert "const int EXIT_CHANCE = 15;" in src


def test_run_rolls_before_placing():
    src = (SCRIPTS / "Generation.as").read_text(encoding="utf-8")
    run = re.search(r"void Run\(DungeonBrush@ brush, PrefabPlacement@ placer\)\s*\{(.*?)\n\t\t\t\}", src, re.S).group(1)
    loop = re.search(r"for \(int i = 0; i < g_vaultCount; i\+\+\)\s*\{(.*?)\n\t\t\t\t\}", run, re.S).group(1)
    roll = loop.index('Rolled("vault " + i, g_vaultChance)')
    assert roll < loop.index("PlaceVault(")
    # a skipped slot moves on; the placed vault takes the next index (g_vaults[k] is "vault k")
    assert re.search(r"if \(!Rolled\([^;]*\)\)\s*continue;", loop)
    assert "PlaceVault(brush, placer, placed," in loop
    assert re.search(r'if \(g_exitOn && Rolled\("exit", g_exitChance\)\)\s*exit = PlaceExitSwitch\(', run)
    assert '"placed " + placed + " vault(s), exit switch " + (exit ? "yes" : "no")' in run
    rolled = re.search(r"bool Rolled\(const string &in what, int chance\)\s*\{(.*?)\n\t\t\t\}", src, re.S).group(1)
    assert "randi(100)" in rolled and "roll < chance" in rolled
    assert '" roll "' in rolled and '": skipped"' in rolled


def model_run(vaults, vault_rolls, chance):
    """Generation.as Run's vault loop with the rolls given: the indices PlaceVault gets."""
    placed, out = 0, []
    for i in range(vaults):
        if not vault_rolls[i] < chance:
            continue
        out.append(placed)
        placed += 1
    return out


def test_model_indices_stay_contiguous():
    assert model_run(2, [90, 3], 25) == [0]
    assert model_run(2, [3, 4], 25) == [0, 1]
    assert model_run(2, [99, 99], 100) == [0, 1]
    assert model_run(2, [0, 0], 0) == []


# a scenario step that only passes when generation placed a vault or the exit switch
NEEDS = re.compile(r"vault 0 at cell|placed [1-9] vault|exit switch (yes|sealed)|exit switch at cell")


def scenario_files():
    out = []
    for p in sorted(SCENARIOS.rglob("*.json")):
        text = p.read_text(encoding="utf-8")
        if "objectives" in text and NEEDS.search(text):
            out.append(p)
    return out


def test_scenarios_found():
    names = {p.stem for p in scenario_files()}
    assert {"fix-objectives", "fix-objectives-preloaded", "fix-objectives-vault-art"} <= names


@pytest.mark.parametrize("path", scenario_files(), ids=lambda p: p.stem)
def test_scenario_forces_the_chances(path):
    text = path.read_text(encoding="utf-8")
    steps = text.index('"steps"')  # past the scenario's "about"
    first_need = NEEDS.search(text, steps).start()
    for key in ("vault_chance", "exit_chance"):
        at = text.find(f'"line": "hwp set objectives.{key} 100"')
        assert at >= 0, f"{path.name} does not set objectives.{key} 100"
        assert at < first_need, f"{path.name} sets objectives.{key} after it expects a placement"
