"""tools/workshop.py: every Workshop item has its texts and a ledger entry, and the HoH1
stand-in notes come from the game's own strings."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import workshop  # noqa: E402


def test_texts_and_ledger_are_complete():
    assert workshop.main(["--check"]) == 0


def test_standins_are_the_report_strings():
    s = workshop.standins()
    assert set(s) >= {"campaign", "classes", "pets", "trinkets"}, s
    assert all(not v.startswith(".") and "hoh1art" not in v for v in s.values()), s


def test_every_package_describes_every_module():
    packages, allp = workshop.load_packages()
    lines = workshop.module_lines()
    for p in packages:
        text = workshop.describe(p, lines, None, workshop.standins())
        for mod in p["mods"]:
            assert f"[b]{workshop.module_title(mod)}[/b]" in text, (p["id"], mod)
    text = workshop.describe(dict(allp, mods=[m for p in packages for m in p["mods"]]), lines, packages)
    assert all(p["name"].split(": ", 1)[-1] in text for p in packages)


def test_descriptions_name_no_repo_paths():
    """A Workshop page is for players: no repo paths or developer steps from the README rows."""
    packages, _ = workshop.load_packages()
    lines = workshop.module_lines()
    for p in packages:
        text = workshop.describe(p, lines, None, workshop.standins())
        assert not workshop.DEV_TEXT.search(text), (p["id"], workshop.DEV_TEXT.search(text))
