"""Save-rotation selection regressions: sandbox files only."""
from pathlib import Path
import struct
import tempfile
import unittest

from gamelab import hps


class RotationTests(unittest.TestCase):
    def test_unsigned_timestamps_do_not_reverse_when_high_bit_is_set(self):
        for older, newer in ((0x10000000, 0x10000100),
                             (0x7fffffff, 0x80000000),
                             (1793473658120, 1793473673479),
                             (0xffffffff, 0x100000000)):
            with self.subTest(older=older, newer=newer), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name, timestamp in (("0.hps", older), ("0_1.hps", newer), ("10.hps", 0xffffffffffffffff)):
                    (root / name).write_bytes(b"H2SV\x03\0\0\0" + struct.pack("<Q", timestamp))
                self.assertEqual(hps.current_save(0, root), root / "0_1.hps")

    def test_header_round_trips_the_full_timestamp(self):
        timestamp = 1793473673479
        data = b"H2SV\x03\0\0\0" + struct.pack("<Q", timestamp) + bytes(12)
        header = hps.Header(data)
        self.assertEqual(header.saved_ms, timestamp)
        self.assertEqual(header.encode(), data[:16])


class HashAndWriteTests(unittest.TestCase):
    def test_hash_string_known_answers(self):
        self.assertEqual(hps.hash_string("test", 0), 0xBA6BD213)
        self.assertEqual(hps.hash_string("The quick brown fox jumps over the lazy dog", 0), 0x2E4FF723)
        self.assertEqual(hps.hash_string("gamelab-probe"), 0x6F7F1318)

    def test_script_issues_keeps_last_char_without_trailing_newline(self):
        from gamelab import logparse
        text = "[x] [12:00:00] ERR : a.as (ln 3, col 4) : Error\nFunction foo not found"
        issues = logparse.script_issues(text)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["msg"], "Function foo not found")


if __name__ == "__main__":
    unittest.main()
