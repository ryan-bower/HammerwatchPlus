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
    led = workshop.ledger(packages)
    shipped = workshop.on_workshop(packages)
    for p in shipped:
        for mod in p["mods"]:
            assert f"[b]{workshop.module_title(mod)}[/b]" in texts[f"HWP-{p['id']}"], (p["id"], mod)
    assert all(workshop.short(p) in texts[workshop.ALL_FILE] for p in workshop.listed(shipped, led))


def test_off_workshop_and_held_packages_stay_off_the_all_page():
    """A `"workshop": false` package has no item; the All page names neither it nor a held one."""
    texts, packages = pages()
    led = workshop.ledger(packages)
    off = [p for p in packages if p not in workshop.on_workshop(packages)]
    assert off and all(f"HWP-{p['id']}" not in texts for p in off)
    held = [p for p in workshop.on_workshop(packages) if p not in workshop.listed(packages, led)]
    for p in off + held:
        assert workshop.short(p) not in texts[workshop.ALL_FILE], p["id"]
    assert "coming back later" not in texts[workshop.ALL_FILE]


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
    assert "Priest's 4th specialization" in texts["HWP-specs"].splitlines()[1]
    assert "Celestial Ruins" not in texts["HWP-town"]
    assert "Turning modules off" in texts[workshop.ALL_FILE]


def test_descriptions_name_no_repo_paths():
    """A Workshop page is for players: no repo paths or developer steps."""
    texts, _ = pages()
    for file, text in texts.items():
        assert not workshop.DEV_TEXT.search(text), (file, workshop.DEV_TEXT.search(text))
