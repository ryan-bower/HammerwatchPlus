from pathlib import Path

import pytest

GAMECODE = Path(__file__).resolve().parents[1] / "gamecode" / "sdk" / "hoh2"


def pytest_collection_modifyitems(config, items):
    """`needs_gamecode` tests read the local game dump, which CI and a fresh clone don't have."""
    if GAMECODE.is_dir():
        return
    skip = pytest.mark.skip(reason="needs gamecode/ (python -m gamelab doctor --fix)")
    for item in items:
        if "needs_gamecode" in item.keywords:
            item.add_marker(skip)
