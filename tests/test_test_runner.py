"""scripts/test.py's worker choice, and conftest's fsync stand-in matching the real fsync."""
import importlib.util
import os
from pathlib import Path
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("hwp_test_runner", REPO / "scripts" / "test.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

REAL_FSYNC = getattr(__import__(os.name), "fsync")  # conftest replaces os.fsync, not nt/posix.fsync


@pytest.fixture
def local_with_xdist():
    env = {k: v for k, v in os.environ.items()
           if k not in ("CI", "PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD")}
    with mock.patch.dict(os.environ, env, clear=True), \
            mock.patch.object(runner.importlib.util, "find_spec", return_value=object()), \
            mock.patch.object(runner.os, "cpu_count", return_value=16):
        yield


@pytest.mark.parametrize("args", [[], ["-q"], ["-x", "-p", "no:cacheprovider"], ["-m", "needs_gamecode"],
                                  ["--dist", "loadfile"], ["--pdb"]])
def test_full_run_is_parallel_on_all_but_two_cores(local_with_xdist, args):
    assert runner.pytest_args(args) == ["-n", "14", *args]


def test_ci_uses_every_core(local_with_xdist):
    with mock.patch.dict(os.environ, {"CI": "true"}):
        assert runner.pytest_args([]) == ["-n", "auto"]


@pytest.mark.parametrize("args", [["tests/test_build_update.py"], ["tests/test_pool.py::PoolTests"],
                                  ["-k", "pool"], ["-kpool"], ["-s"], ["--capture=no"], ["--lf"], ["--sw"]])
def test_narrowed_run_stays_serial(local_with_xdist, args):
    assert runner.pytest_args(args) == args


@pytest.mark.parametrize("args", [["-n", "4"], ["-n0"], ["--numprocesses=2"], ["-p", "no:xdist"]])
def test_explicit_choice_is_left_alone(local_with_xdist, args):
    assert runner.pytest_args(args) == args


def test_serial_when_xdist_is_missing_or_not_loaded(local_with_xdist):
    with mock.patch.object(runner.importlib.util, "find_spec", return_value=None):
        assert runner.pytest_args([]) == []
    with mock.patch.dict(os.environ, {"PYTEST_ADDOPTS": "-p no:xdist"}):
        assert runner.pytest_args([]) == []
    with mock.patch.dict(os.environ, {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}):
        assert runner.pytest_args([]) == []
        assert runner.pytest_args(["-p", "xdist"]) == ["-n", "14", "-p", "xdist"]


def _outcome(fsync, target):
    try:
        fsync(target)
        return "ok"
    except OSError as error:
        return f"OSError {error.errno}"
    except TypeError:
        return "TypeError"


@pytest.mark.parametrize("mode", ["rb", "wb", "ab", "r+b"])
def test_fsync_stand_in_refuses_what_the_real_fsync_refuses(tmp_path, mode):
    assert os.fsync is not REAL_FSYNC, "conftest should have replaced os.fsync"
    path = tmp_path / "file.bin"
    path.write_bytes(b"x")
    with open(path, mode) as stream:
        for target in (stream.fileno(), stream):
            assert _outcome(os.fsync, target) == _outcome(REAL_FSYNC, target), (mode, target)


def test_fsync_stand_in_refuses_a_closed_descriptor(tmp_path):
    fd = os.open(tmp_path / "file.bin", os.O_WRONLY | os.O_CREAT)
    os.close(fd)
    assert _outcome(os.fsync, fd) == _outcome(REAL_FSYNC, fd) == "OSError 9"
