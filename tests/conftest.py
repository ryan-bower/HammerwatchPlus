import os
from pathlib import Path

import pytest

GAMECODE = Path(__file__).resolve().parents[1] / "gamecode" / "sdk" / "hoh2"


def _checked_fsync(fd):
    """Stands in for os.fsync in tests: same refusal for a bad descriptor, no disk flush.

    The tools fsync every journal and manifest write; on Windows each flush costs ~0.1 s and
    was most of the suite's wall time. Tests check the write logic, not power-loss durability,
    and a test that needs fsync to fail still patches it on top of this.
    """
    os.fstat(fd)


@pytest.fixture(autouse=True, scope="session")
def _no_disk_flush():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(os, "fsync", _checked_fsync)
        yield


def pytest_collection_modifyitems(config, items):
    """`needs_gamecode` tests read the local game dump, which CI and a fresh clone don't have."""
    if GAMECODE.is_dir():
        return
    skip = pytest.mark.skip(reason="needs gamecode/ (python -m gamelab doctor --fix)")
    for item in items:
        if "needs_gamecode" in item.keywords:
            item.add_marker(skip)
