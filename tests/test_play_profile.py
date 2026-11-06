"""New profile integrity and preservation tests; no real save/config writes."""
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gamelab import env, hps
from tools import play_profile


class PlayProfile(unittest.TestCase):
    def test_empty_profile_is_named_modded_checksummed_and_has_no_characters(self):
        data = play_profile.empty_profile(["HammerwatchPlus-All", "HWP-town"], "New run", saved_ms=123)
        header = hps.Header(data)
        self.assertTrue(hps.trailer_ok(data))
        self.assertEqual(header.version, 4)
        self.assertEqual(header.saved_ms, 123)
        self.assertEqual(header.mod_name, b"New run")
        self.assertEqual(header.mods, [hps.hash_string(s) for s in ["HammerwatchPlus-All", "HWP-town"]])
        self.assertEqual(data[header.body_offset:-4], struct.pack("<II", 0, 0))

    def test_successive_profiles_preserve_all_existing_files_and_config_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = root / "game"
            saves = install / "saves"
            saves.mkdir(parents=True)
            (saves / "0_7.hps").write_bytes(b"existing rotation only")
            (saves / "1.hps").write_bytes(b"existing player characters")
            config = b"\xef\xbb\xbfg_save_slot 1\r\nsnd_volume 0.2\r\ng_save_slot_cloud 1\r\n"
            (install / "HWR2.exe.cfg").write_bytes(config)
            before = {p.name: p.read_bytes() for p in saves.iterdir()}
            first = play_profile.create(install, ["HammerwatchPlus-All"], root / "backups", "First")
            self.assertEqual(first["slot"], 2)
            first_bytes = Path(first["save"]).read_bytes()
            second = play_profile.create(install, ["HWP-town"], root / "backups", "Second")
            self.assertEqual(second["slot"], 3)
            self.assertEqual(Path(first["save"]).read_bytes(), first_bytes)
            for name, data in before.items():
                self.assertEqual((saves / name).read_bytes(), data)
            self.assertEqual((install / "HWR2.exe.cfg").read_bytes(),
                             b"\xef\xbb\xbfg_save_slot 3\r\nsnd_volume 0.2\r\ng_save_slot_cloud 0\r\n")
            self.assertEqual((Path(first["backup"]) / "HWR2.exe.cfg.before").read_bytes(), config)
            self.assertEqual(json.loads((Path(second["backup"]) / "profile.json").read_text())["mods"], ["HWP-town"])

    def test_config_selection_appends_missing_settings_without_joining_lines(self):
        self.assertEqual(play_profile.select_local_profile(b"snd_volume 0.2", 4),
                         b"snd_volume 0.2\ng_save_slot 4\ng_save_slot_cloud 0\n")

    def test_workshop_collision_uses_an_independent_personal_id(self):
        with mock.patch.object(env, "workshop_ids", return_value={"HammerwatchPlus-All": Path("workshop.bin")}):
            self.assertEqual(env.personal_package_name("all"), "HammerwatchPlus-All-local.bin")
            self.assertEqual(env.personal_package_name("town"), "HWP-town.bin")

    def test_invalid_name_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                play_profile.create(root, ["HammerwatchPlus-All"], root / "backups", "bad\0name")
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
