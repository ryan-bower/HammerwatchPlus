"""Shared modules (module.json `shared: true`): listed in one package, carried by every package
whose mods require them (tools/build.py), and listed by the settings page under each of those
packages (tools/make_config.py). petrooms is Quality of Life's, and Pets carries it too."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from tools import build, make_config  # noqa: E402


def closures():
    mods = [build.load_module(d) for d in build.paths.module_dirs()]
    pkgs, _ = build.load_packages(mods)
    return {p["id"]: p["closure"] for p in pkgs}


def test_petrooms_rides_in_qol_and_pets_only():
    have = sorted(pid for pid, closure in closures().items() if "petrooms" in closure)
    assert have == ["pets", "qol"]


def test_the_settings_page_lists_petrooms_under_both_as_shared():
    pk, _ = make_config.load()
    carried = {p["id"]: p["carried"] for p in pk["packages"]}
    assert "petrooms" in carried["qol"] and "petrooms" in carried["pets"]
    assert pk["shared"] == ["petrooms"]
    sval = make_config.sval(*make_config.load())
    assert sval.count('<string name="id">petrooms</string>') == 2
    assert sval.count('<bool name="shared">true</bool>') == 2
