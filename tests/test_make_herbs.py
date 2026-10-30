"""tools/make_herbs.py: the Holy Herb strains come from one table, and every file and sprite
sheet it writes is current (issue #15: a strain was copied by hand into seven files and three
sheets indexed by seed order)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import make_herbs  # noqa: E402

FARMING = make_herbs.FARM / "scripts" / "HWP" / "Farming" / "FarmingModule.as"


def test_generated_files_current():
    assert make_herbs.stale() == []


def test_define_seeds_is_food_then_herbs():
    """The sheets are indexed by DefineSeeds order: the food crops (FOOD), then DefineHerbs."""
    body = re.search(r"void DefineSeeds\(\)\s*\{(.*?)\n\t\t\}", FARMING.read_text(encoding="utf-8"), re.S).group(1)
    food = re.findall(r'AddSeed\("(\w+)", \d+, false', body)
    assert food == make_herbs.FOOD
    assert body.rstrip().endswith("DefineHerbs();")


def test_sheets_have_a_cell_per_seed():
    from PIL import Image
    n = len(make_herbs.seed_ids())
    for sheet, cell in (("hwp_seeds.png", 13), ("hwp_harvest.png", 16)):
        w, _ = Image.open(make_herbs.FARM / "gui" / sheet).size
        assert w >= n * cell, sheet
        assert w & (w - 1) == 0, f"{sheet} is {w} wide: GUI textures stay power-of-two sized"


def test_materials_grid_fits_every_seed_and_harvest():
    """farming registers a seed and a harvest cell per seed in hwplib's materials section b."""
    gui = (make_herbs.ROOT / "mods" / "hwplib" / "gui" / "playermenu" / "character.gui").read_text(encoding="utf-8")
    cells = re.findall(r'<hwp-material id="hwp-mat-b\d+"', gui)
    assert len(cells) >= 2 * len(make_herbs.seed_ids())
