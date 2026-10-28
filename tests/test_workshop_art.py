"""tools/workshop_art.py: every module has a symbol, every package's card lays out (no text
past the frame), and each card saves under Steam's 1 MB. The cards are drawn from the game's
own art (gamecode/), so they are skipped on a machine without it."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import workshop  # noqa: E402
import workshop_art  # noqa: E402

pytestmark = pytest.mark.skipif(not (workshop_art.BASE / "gui" / "gui.png").is_file(),
                                reason="needs gamecode/ (python -m gamelab doctor --fix)")


def test_every_module_has_a_symbol():
    packages, _ = workshop.load_packages()
    missing = [m for p in packages for m in p["mods"] if m not in workshop_art.SYMBOLS]
    assert not missing, missing


def test_every_card_lays_out_and_fits_steam(tmp_path):
    packages, _ = workshop.load_packages()
    cards = workshop_art.cards(packages, workshop_art.held_ids())
    assert set(cards) == {p["id"] for p in packages} | {"all"}
    for pid, im in cards.items():
        assert im.size == workshop_art.NATIVE, pid
        f = workshop_art.save(im, tmp_path / f"{pid}.png")
        assert f.stat().st_size < 1024 * 1024, pid


def test_the_dlc_footer_names_only_what_needs_it():
    assert workshop_art.prereq(["specs"]) == "Devil Forgemaster: Celestial Ruins DLC"
    assert workshop_art.prereq(["town", "pets"]) == ""
