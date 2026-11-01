"""Content made from the HoH2 base (issue #76): a build without gamecode/sdk/hoh2/ used to pack
the packages without it and say nothing, so v0.3 shipped no Forgemaster bodies (Necrotic
Resurrection had nothing to raise), Keys chests, projectile colours or pet dyes. build.py now
stops instead, and makes the Forgemaster units itself as it does the class units and pet dyes."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import build  # noqa: E402


def modules() -> dict:
    return {m["id"]: m for m in (build.load_module(d) for d in build.paths.module_dirs())}


def test_the_forgemaster_units_are_generated_from_the_base():
    assert "tools/make_forgemaster_risen.py" in build.base_generators(modules()["specs"])


def test_build_runs_every_base_generator_a_module_names():
    named = {t for m in modules().values() for t in build.base_generators(m)}
    assert named <= set(build.BASE_TOOLS), named - set(build.BASE_TOOLS)


def test_a_package_needing_the_base_does_not_build_without_it(monkeypatch, tmp_path):
    by_id = modules()
    monkeypatch.setattr(build.paths, "BASE_HOH2", tmp_path / "no-base")
    with pytest.raises(SystemExit) as e:
        build.require_base(["hwplib", "specs"], by_id)
    assert "specs (" in str(e.value) and "make_forgemaster_risen.py" in str(e.value)


def test_a_package_with_nothing_from_the_base_still_builds_without_it(monkeypatch, tmp_path):
    by_id = modules()
    monkeypatch.setattr(build.paths, "BASE_HOH2", tmp_path / "no-base")
    build.require_base(["hwplib", "architect"], by_id)
