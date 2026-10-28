"""gamelab/hps.py: the save rotation file the game loads is the one written last."""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamelab import hps  # noqa: E402


def save(path: Path, saved_ms: int, mtime: float) -> None:
    path.write_bytes(hps.MAGIC + bytes([3, 0, 0, 0]) + struct.pack("<Q", saved_ms) + bytes(8))
    os.utime(path, (mtime, mtime))


def test_latest_saved_ms_wins_across_bit_31(tmp_path):
    # 2026-10-28: the low word crossed 0x80000000 between these two writes; read as an
    # f32 the later one was negative and lost
    save(tmp_path / "0.hps", 0x01A1_7FFF_FF00, 100)
    save(tmp_path / "0_1.hps", 0x01A1_8433_0B66, 50)
    assert hps.current_save(0, tmp_path).name == "0_1.hps"


def test_header_round_trips_saved_ms():
    data = hps.MAGIC + bytes([3, 0, 0, 0]) + struct.pack("<Q", 1793219300198) + bytes(8)
    hdr = hps.Header(data)
    assert hdr.saved_ms == 1793219300198
