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


class TransactionFailures(unittest.TestCase):
    """Faults affect temporary fake install paths only."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="h1-profile-transaction-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "game"
        self.saves = self.install / "saves"
        self.saves.mkdir(parents=True)
        self.previous = self.saves / "0.hps"
        self.previous.write_bytes(b"existing profile must survive")
        self.config = self.install / "HWR2.exe.cfg"
        self.config.write_bytes(b"g_save_slot 0\nsnd_volume 0.2\ng_save_slot_cloud 1\n")
        self.before_config = self.config.read_bytes()
        self.new_profile = self.saves / "1.hps"

    def assert_preserved(self, new_exists=False):
        self.assertEqual(self.previous.read_bytes(), b"existing profile must survive")
        self.assertEqual(self.config.read_bytes(), self.before_config)
        self.assertEqual(self.new_profile.exists(), new_exists)
        self.assertEqual(list(self.install.glob("HWR2.cfg-*")), [])

    def create(self):
        return play_profile.create(self.install, ["HammerwatchPlus-All"],
                                   self.root / "backups", "FaultProbe")

    def save_failure(self, stage):
        original = Path.open
        target = self.new_profile

        class FaultedFile:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                self.file.__enter__()
                return self

            def __exit__(self, *error):
                result = self.file.__exit__(*error)
                if stage == "close":
                    raise OSError("injected save close failure")
                return result

            def write(self, data):
                if stage == "write":
                    self.file.write(data[:8])
                    self.file.flush()
                    raise OSError("injected save prefix write failure")
                return self.file.write(data)

        def opened(path, *args, **kwargs):
            file = original(path, *args, **kwargs)
            return FaultedFile(file) if path == target and args and args[0] == "xb" else file

        with mock.patch.object(Path, "open", new=opened):
            with self.assertRaises(OSError):
                self.create()
        self.assert_preserved()

    def test_save_write_failure_removes_only_new_profile(self):
        self.save_failure("write")

    def test_save_close_failure_removes_only_new_profile(self):
        self.save_failure("close")

    def test_config_temp_creation_failure_rolls_back_new_profile(self):
        with mock.patch.object(play_profile.tempfile, "NamedTemporaryFile",
                               side_effect=OSError("injected config temp creation failure")):
            with self.assertRaises(OSError):
                self.create()
        self.assert_preserved()

    def test_config_temp_write_failure_rolls_back_new_profile(self):
        original = play_profile.tempfile.NamedTemporaryFile

        class FaultedTemp:
            def __init__(self, file):
                self.file = file
                self.name = file.name

            def __enter__(self):
                self.file.__enter__()
                return self

            def __exit__(self, *error):
                return self.file.__exit__(*error)

            def write(self, data):
                self.file.write(data[:4])
                raise OSError("injected config temp write failure")

        with mock.patch.object(play_profile.tempfile, "NamedTemporaryFile",
                               side_effect=lambda *a, **kw: FaultedTemp(original(*a, **kw))):
            with self.assertRaises(OSError):
                self.create()
        self.assert_preserved()

    def test_config_replace_failure_rolls_back_new_profile(self):
        original = Path.replace
        install = self.install

        def replaced(path, target):
            if path.parent == install and path.name.startswith("HWR2.cfg-"):
                raise OSError("injected config replacement failure")
            return original(path, target)

        with mock.patch.object(Path, "replace", new=replaced):
            with self.assertRaises(OSError):
                self.create()
        self.assert_preserved()

    def test_exclusive_collision_preserves_the_competing_profile(self):
        original = Path.open
        target = self.new_profile

        def opened(path, *args, **kwargs):
            if path == target and args and args[0] == "xb":
                with original(target, "wb") as file:
                    file.write(b"competing profile")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "open", new=opened):
            with self.assertRaises(FileExistsError):
                self.create()
        self.assert_preserved(new_exists=True)
        self.assertEqual(self.new_profile.read_bytes(), b"competing profile")

    def test_config_backup_failure_never_creates_profile(self):
        original = Path.write_bytes

        def write(path, data):
            if path.name == "HWR2.exe.cfg.before":
                raise OSError("injected config backup failure")
            return original(path, data)

        with mock.patch.object(Path, "write_bytes", new=write):
            with self.assertRaises(OSError):
                self.create()
        self.assert_preserved()

    def test_receipt_failure_never_creates_profile(self):
        original = Path.write_text

        def write(path, *args, **kwargs):
            if path.name == "profile.json":
                raise OSError("injected receipt failure")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "write_text", new=write):
            with self.assertRaises(OSError):
                self.create()
        self.assert_preserved()


if __name__ == "__main__":
    unittest.main()
