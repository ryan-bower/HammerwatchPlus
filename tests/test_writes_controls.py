"""A scenario's "writes_controls" (gamelab/runner.py): the run's rebinds land in GameLab's own
res/controls.cfg, which later runs would inherit. The journal puts it back: removed when the
run created it, restored when it was there before."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamelab.runner import remember_written, restore_written  # noqa: E402


def test_created_by_the_run_is_removed(tmp_path):
    results, cfg = tmp_path / "results", tmp_path / "res" / "controls.cfg"
    results.mkdir()
    cfg.parent.mkdir()
    remember_written(results, cfg)
    cfg.write_text("<controls/>")
    assert restore_written(results) == [str(cfg)]
    assert not cfg.exists()


def test_existing_file_is_put_back(tmp_path):
    results, cfg = tmp_path / "results", tmp_path / "controls.cfg"
    results.mkdir()
    cfg.write_bytes(b"before")
    remember_written(results, cfg)
    remember_written(results, cfg)  # once per file
    cfg.write_bytes(b"rebound")
    restore_written(results)
    assert cfg.read_bytes() == b"before"
    assert restore_written(results) == []  # safe twice


def test_the_users_controls_are_never_copied_in(tmp_path):
    # the user's game saved its own binds to the install's res/controls.cfg: GameLab's res/
    # must not pick them up (a run would start from the user's keys, not the defaults)
    from gamelab.env import ensure_res
    src, dst = tmp_path / "install-res", tmp_path / "lab-res"
    src.mkdir()
    (src / "controls_default.cfg").write_bytes(b"defaults")
    (src / "controls.cfg").write_bytes(b"the user's binds")
    problems = []
    ensure_res(src, dst, problems, fix=True)
    assert (dst / "controls_default.cfg").read_bytes() == b"defaults"
    assert not (dst / "controls.cfg").exists()
    (dst / "controls.cfg").write_bytes(b"GameLab's own")
    ensure_res(src, dst, problems, fix=True)
    assert (dst / "controls.cfg").read_bytes() == b"GameLab's own"
    assert problems == []
