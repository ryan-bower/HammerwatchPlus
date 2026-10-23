"""Ctrl+C during a run is ABORTED (exit 130) with a clean teardown, so the next run is not
refused (arena watch 20261021-192533 needed `python -m gamelab reset`)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamelab import launcher, lock  # noqa: E402


class _NoSampler:
    t0 = 0.0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def report(self):
        return {"switches": [], "unexplained": [], "window_scans": 1, "game_windows_on_input_desktop": []}


def test_ctrl_c_is_aborted_and_releases_the_lock_clean(tmp_path, monkeypatch):
    cfg = tmp_path / "HWR2.exe.cfg"
    cfg.write_text("x", encoding="utf-8")
    monkeypatch.setattr(launcher, "REPO", tmp_path)
    monkeypatch.setattr(launcher, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(lock, "LOCK", tmp_path / "lock.json")
    monkeypatch.setattr(lock, "TEARDOWN", tmp_path / "teardown.json")
    monkeypatch.setattr(lock, "lab_processes", lambda: [])
    monkeypatch.setattr(launcher.winproc, "ForegroundSampler", lambda **k: _NoSampler())
    monkeypatch.setattr(launcher.gamepaths, "real_config", lambda: cfg)
    monkeypatch.setattr(launcher.env, "install_res_snapshot", lambda: {})
    monkeypatch.setattr(launcher.saves, "snapshot", lambda: {})
    monkeypatch.setattr(launcher.saves, "diff", lambda a, b: [])
    monkeypatch.setattr(launcher.pin_build, "pinned", lambda: {})
    monkeypatch.setattr(launcher.pin_build, "live", lambda: {})

    def ctrl_c(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(launcher.hidden_desktop, "run", ctrl_c)
    (tmp_path / "lock.json").write_text("{}", encoding="utf-8")

    code = launcher._run(tmp_path / "s.json", "s", {"timeout": 1}, "watch", [])

    assert code == 130
    teardown = json.loads((tmp_path / "teardown.json").read_text(encoding="utf-8"))
    assert teardown["clean"] and teardown["reasons"] == []
    assert not (tmp_path / "lock.json").exists()
    run = json.loads(next((tmp_path / "results").glob("*/run.json")).read_text(encoding="utf-8"))
    assert run["verdict"] == "ABORTED"
