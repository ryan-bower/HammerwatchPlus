"""Offline regressions for the pinned Windows runtime installer."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from tools import setup_gamelab_linux as setup


class RuntimeSetupTests(unittest.TestCase):
    def archive(self, entries):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name, value in entries.items():
                archive.writestr(name, value)
        return data.getvalue()

    def test_install_is_cached_idempotent_and_relocatable(self):
        data = self.archive({"python.exe": b"test", "python311._pth": b"original"})
        artifacts = [("python", "https://example.invalid/python.zip",
                      hashlib.sha256(data).hexdigest())]
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(setup, "ARTIFACTS", artifacts), \
                mock.patch.object(setup.urllib.request, "urlopen",
                                  return_value=io.BytesIO(data)) as download:
            state = Path(temp)
            setup.install(state)
            setup.install(state)
            download.assert_called_once()
            self.assertEqual((state / "python/python.exe").read_bytes(), b"test")
            self.assertIn("../../../../..", (state / "python/python311._pth").read_text())
            (state / "python/python.exe").write_bytes(b"user change")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                setup.install(state)

    def test_bad_hash_is_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(setup, "ARTIFACTS", [("python", "https://example.invalid/bad.zip", "bad")]), \
                mock.patch.object(setup.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                setup.install(Path(temp))
            self.assertFalse((Path(temp) / "python").exists())

    def test_archive_cannot_escape_destination(self):
        data = self.archive({"../escape": b"bad"})
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(setup, "ARTIFACTS", [("python", "https://example.invalid/bad.zip",
                                                       hashlib.sha256(data).hexdigest())]), \
                mock.patch.object(setup.urllib.request, "urlopen", return_value=io.BytesIO(data)):
            with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                setup.install(Path(temp))


if __name__ == "__main__":
    unittest.main()
