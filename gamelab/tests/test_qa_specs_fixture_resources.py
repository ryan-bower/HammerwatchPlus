"""Moved QA units must resolve native resources from the game resource root."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / "mods/gamelab-hands/gamelab/qa_specs_fragile_target_dummy.unit"
SDK = ROOT / "gamecode/sdk/hoh2"


class SpecFixtureResourceTests(unittest.TestCase):
    def test_moved_fragile_unit_has_no_relative_texture_dependencies(self):
        source = UNIT.read_text(encoding="utf-8")
        textures = re.findall(r'texture="([^"]+)"', source)
        self.assertEqual(len(textures), 6)
        self.assertTrue(all(not path.startswith(".") for path in textures))
        if SDK.exists():
            for path in textures:
                self.assertTrue((SDK / path).is_file(), path)

    def test_other_native_dependencies_keep_existing_absolute_paths(self):
        source = UNIT.read_text(encoding="utf-8")
        paths = set(re.findall(r'material="([^"]+)"', source))
        paths.update(re.findall(r'<string name="gore">([^<]+)</string>', source))
        self.assertTrue(paths)
        self.assertTrue(all(not path.startswith(".") for path in paths))
        if SDK.exists():
            for path in paths:
                self.assertTrue((SDK / path.split(":", 1)[0]).is_file(), path)


if __name__ == "__main__":
    unittest.main()
