"""A visible player session must block native labs without touching either save tree."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gamelab import lock


class PlayerRuntime(unittest.TestCase):
    def test_process_scan_separates_lab_and_real_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lab = root / "lab"
            output = '"HWR2.exe","10","Console","1","100 K"\n"HWR2.exe","20","Console","1","100 K"'
            images = {10: str(lab / "HWR2.exe"), 20: str(root / "real" / "HWR2.exe")}
            with mock.patch.object(lock.env, "GAME", lab), \
                    mock.patch.object(lock.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=output)), \
                    mock.patch.object(lock, "process_image", side_effect=images.get):
                self.assertEqual(lock.player_processes(), [20])

    def test_inaccessible_process_visibility_is_a_refusal(self):
        with mock.patch.object(lock.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="", stderr="Access denied")):
            with self.assertRaisesRegex(lock.Refused, "cannot check"):
                lock.player_processes()
        with mock.patch.object(lock.subprocess, "run", return_value=mock.Mock(returncode=0, stdout='"HWR2.exe","10"')), \
                mock.patch.object(lock, "process_image", return_value=""):
            with self.assertRaisesRegex(lock.Refused, "cannot inspect"):
                lock.player_processes()

    def test_player_session_refuses_before_wiping_lab_saves_and_releases_own_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            saves = game / "saves"
            saves.mkdir(parents=True)
            save = saves / "0.hps"
            save.write_bytes(b"existing lab fixture")
            held = root / "runtime.lock"
            with mock.patch.object(lock, "LOCK", held), mock.patch.object(lock.env, "GAME", game), \
                    mock.patch.object(lock, "player_processes", return_value=[20]), \
                    mock.patch.object(lock, "lab_processes") as lab_scan, \
                    mock.patch.object(lock, "kill") as kill:
                with self.assertRaisesRegex(lock.Refused, "player game owns"):
                    lock.acquire("test", "lab")
            self.assertFalse(held.exists())
            self.assertEqual(save.read_bytes(), b"existing lab fixture")
            lab_scan.assert_not_called()
            kill.assert_not_called()
