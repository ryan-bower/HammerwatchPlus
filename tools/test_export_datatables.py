"""Export retry regressions, without importing the live GameLab launcher."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import export_datatables as export


class ExportRetryTests(unittest.TestCase):
    def test_complete_export_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            (dest / "_index.json").write_text(json.dumps({"test.sval": "ok"}))
            (dest / "test.sval.json").write_text("{}")
            sdk = dest / "sdk"
            sdk.mkdir()
            (sdk / "test.sval").write_text("<sval />")
            with mock.patch.object(export, "DEST", dest), \
                    mock.patch.object(export, "SDK", sdk):
                self.assertEqual(export.main([]), 0)

    def test_partial_export_does_not_skip_full_export(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            sdk = dest / "sdk"
            sdk.mkdir()
            for name in ("first.sval", "second.sval"):
                (sdk / name).write_text("<sval />")
            # A successful --only export contains just the selected table.
            (dest / "_index.json").write_text(json.dumps({"first.sval": "ok"}))
            (dest / "first.sval.json").write_text("{}")
            with mock.patch.object(export, "DEST", dest), \
                    mock.patch.object(export, "SDK", sdk), \
                    mock.patch.object(export, "step", side_effect=RuntimeError("export requested")) as step, \
                    self.assertRaisesRegex(RuntimeError, "export requested"):
                export.main([])
            step.assert_called_once_with("first.sval")
            self.assertTrue((dest / "first.sval.json").is_file())

    def test_failed_or_missing_exports_do_not_count_as_complete(self):
        for status in ("not reached", "ok"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                dest = Path(temp)
                (dest / "_index.json").write_text(json.dumps({"test.sval": status}))
                marker = dest / "existing.json"
                marker.write_text("keep")
                sdk = dest / "sdk"
                sdk.mkdir()
                (sdk / "test.sval").write_text("<sval />")
                with mock.patch.object(export, "DEST", dest), \
                        mock.patch.object(export, "SDK", sdk), \
                        mock.patch.object(export, "step", side_effect=RuntimeError("export requested")), \
                        self.assertRaisesRegex(RuntimeError, "export requested"):
                    export.main([])
                self.assertEqual(marker.read_text(), "keep")

    def test_cached_export_still_requires_sdk(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            (dest / "_index.json").write_text(json.dumps({"test.sval": "ok"}))
            (dest / "test.sval.json").write_text("{}")
            with mock.patch.object(export, "DEST", dest), \
                    mock.patch.object(export, "SDK", dest / "missing-sdk"), \
                    self.assertRaisesRegex(SystemExit, "no .sval files"):
                export.main([])


if __name__ == "__main__":
    unittest.main()
