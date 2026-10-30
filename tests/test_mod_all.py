"""mod-all (gamelab/scenarios/mod-all.json) is the pre-merge gate that loads every content mod
loose, side by side. Its mod list is kept by hand, so a new module could be left out of it:
petrooms and affixes were. Every mod a package lists must be in it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def packaged_mods():
    pk = json.loads((ROOT / "packages.json").read_text(encoding="utf-8"))
    mods = set()
    for pkg in pk["packages"]:
        mods |= set(pkg.get("mods", []))
    return mods


def test_mod_all_loads_every_packaged_mod():
    scenario = json.loads((ROOT / "gamelab/scenarios/mod-all.json").read_text(encoding="utf-8"))
    missing = sorted(packaged_mods() - set(scenario["mods"]))
    assert missing == [], "add to gamelab/scenarios/mod-all.json: " + ", ".join(missing)
