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


if __name__ == "__main__":
    unittest.main()
