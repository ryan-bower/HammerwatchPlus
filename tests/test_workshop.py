"""tools/workshop.py: every Workshop item has its texts and a ledger entry, the pages say what
a player needs first and how to install last, and the HoH1 stand-in notes come from the game's
own strings."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import workshop  # noqa: E402


def pages():
    packages, allp = workshop.load_packages()
    led = workshop.ledger(packages)
    stand = workshop.standins()
    return {file: workshop.describe(p, led, inside, stand)
            for file, p, inside in workshop.items(packages, allp)}, packages


def test_texts_and_ledger_are_complete():
    assert workshop.main(["--check"]) == 0


def test_standins_are_the_report_strings():
    s = workshop.standins()
    assert set(s) >= {"campaign", "classes", "pets", "trinkets"}, s
    assert all(not v.startswith(".") and "hoh1art" not in v for v in s.values()), s


def test_every_package_describes_every_module():
    texts, packages = pages()
    for p in packages:
        for mod in p["mods"]:
            assert f"[b]{workshop.module_title(mod)}[/b]" in texts[f"HWP-{p['id']}"], (p["id"], mod)
    assert all(workshop.short(p) in texts[workshop.ALL_FILE] for p in packages)


def test_pages_open_with_prereqs_and_end_with_install_and_the_all_pack():
    texts, _ = pages()
    for file, text in texts.items():
        lines = text.splitlines()
        assert lines[0] == "[b]Multiplayer supported.[/b]", file
        assert lines[1].startswith("[b]Requires:[/b] Heroes of Hammerwatch II"), file
        assert "Heroes of Hammerwatch 1:" in lines[2], file
        assert "[h2]Install[/h2]" in text and "[b]Plus[/b] tab" in text, file
        if file != workshop.ALL_FILE:
            assert "HammerwatchPlus: All[/url]" in lines[-1], file
    assert "Celestial Ruins DLC" in texts["HWP-specs"].splitlines()[1]
    assert "Celestial Ruins" not in texts["HWP-town"]
    assert "Turning modules off" in texts[workshop.ALL_FILE]


def test_descriptions_name_no_repo_paths():
    """A Workshop page is for players: no repo paths or developer steps."""
    texts, _ = pages()
    for file, text in texts.items():
        assert not workshop.DEV_TEXT.search(text), (file, workshop.DEV_TEXT.search(text))
