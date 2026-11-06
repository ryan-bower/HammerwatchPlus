"""A Workshop subscription with the id of a package under test (gamelab/env.py SHADOW_SUFFIX)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gamelab import env, logparse

LOG = r"""[NFO] [23:28:07] Workshop: Subscribed items: 2
[NFO] [23:28:07] Workshop: Item: e432bb1e - C:\Steam\steamapps\workshop\content\619820\3828529950
[NFO] [23:28:07] Workshop: Item: d7cb75da - C:\Steam\steamapps\workshop\content\619820\3620435418
[NFO] [23:28:07] Resource mod: gamelab-probe: GameLab Probe
[NFO] [23:28:07] Resource mod: HammerwatchPlus-All.bin: HammerwatchPlus: All (HammerwatchPlus-All)
[NFO] [23:28:07] logos size: 0
[NFO] [23:28:07] Resource mod: HammerwatchPlus-All.bin: HammerwatchPlus: All (HammerwatchPlus-All)
[NFO] [23:28:07] Resource mod: drop_me.bin: Drop Me (drop_me)
"""


class WorkshopShadowTests(unittest.TestCase):
    def test_log_names_the_mod_found_twice(self):
        self.assertEqual(logparse.duplicate_mods(LOG), {"HammerwatchPlus-All": 2})
        self.assertEqual(len(logparse.workshop_items(LOG)), 2)

    def test_shadowed_package_gets_a_lab_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = Path(tmp) / "3828529950"
            item.mkdir()
            (item / "HammerwatchPlus-All.bin").write_bytes(b"")
            with patch.object(env, "workshop_dir", return_value=Path(tmp)):
                self.assertEqual(env.package_ids(["all", "pets"]), ["HammerwatchPlus-All" + env.SHADOW_SUFFIX, "HWP-pets"])
                self.assertEqual(list(env.shadowed_packages(["all", "pets"])), ["all"])
                self.assertEqual(env.lab_package_name("pets"), "HWP-pets.bin")
                # the lab copy is still a package copy: the next scenario's link removes it
                with tempfile.TemporaryDirectory() as lab:
                    copy = Path(lab) / env.lab_package_name("all")
                    copy.write_bytes(b"")
                    self.assertTrue(env.is_package_copy(copy))

    def test_no_workshop_folder(self):
        with patch.object(env, "workshop_dir", return_value=Path(tempfile.gettempdir()) / "no-such-workshop-dir"):
            self.assertEqual(env.workshop_ids(), {})
            self.assertEqual(env.package_ids(["all"]), ["HammerwatchPlus-All"])


if __name__ == "__main__":
    unittest.main()
