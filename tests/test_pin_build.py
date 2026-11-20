import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import pin_build  # noqa: E402


def test_repin_does_not_write_a_stale_game_version(tmp_path):
    pin = tmp_path / "build_id.json"
    fake = {"app_id": "1", "build_id": "9", "exe_sha256": "ab" * 32, "exe_pe_timestamp": 1}
    with patch.object(pin_build, "PIN", pin), patch.object(pin_build, "live", return_value=fake), \
            patch.object(pin_build.gamepaths, "REPO", tmp_path):
        assert pin_build.main(["--reason", "test"]) == 0
    assert json.loads(pin.read_text(encoding="utf-8"))["game_version"] == "unknown"
