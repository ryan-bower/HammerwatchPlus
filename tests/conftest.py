import errno
import os
import sys
from pathlib import Path

import pytest

GAMECODE = Path(__file__).resolve().parents[1] / "gamecode" / "sdk" / "hoh2"

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _kernel32.WriteFile.restype = wintypes.BOOL

    def _require_write_access(fd):
        # A zero-byte WriteFile writes nothing but still checks the handle's access, so it
        # refuses a read-only handle exactly where the real fsync (FlushFileBuffers) does.
        written = wintypes.DWORD()
        if not _kernel32.WriteFile(msvcrt.get_osfhandle(fd), None, 0, ctypes.byref(written), None):
            raise OSError(errno.EBADF, os.strerror(errno.EBADF))
else:
    def _require_write_access(fd):
        pass  # POSIX fsync accepts a read-only descriptor


def _checked_fsync(fd):
    """Stands in for os.fsync in tests: the same refusals, without the disk flush.

    The tools fsync every journal and manifest write; on Windows each flush costs ~0.1 s and
    was most of the suite's wall time. Like the real call it takes a descriptor or an object
    with fileno(), raises for a closed or invalid descriptor, and on Windows raises EBADF for
    one opened read-only. Only the flush itself (power-loss durability) is skipped, which no
    test could observe. A test that needs fsync to fail still patches it on top of this.
    """
    if not isinstance(fd, int):
        fd = fd.fileno()
    os.fstat(fd)
    _require_write_access(fd)


@pytest.fixture(autouse=True, scope="session")
def _no_disk_flush():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(os, "fsync", _checked_fsync)
        yield


def pytest_collection_modifyitems(config, items):
    """`needs_gamecode` tests read the local game dump, which CI and a fresh clone don't have."""
    if GAMECODE.is_dir():
        return
    skip = pytest.mark.skip(reason="needs gamecode/ (python -m gamelab doctor --fix)")
    for item in items:
        if "needs_gamecode" in item.keywords:
            item.add_marker(skip)
