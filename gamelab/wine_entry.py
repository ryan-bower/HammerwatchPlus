"""Windows-side bridge entry: preserve logs and exit codes through Proton's steam.exe."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import sys
import traceback


def run() -> int:
    from gamelab.__main__ import main

    result = Path(os.environ["HWP_LINUX_RESULT"])
    output = Path(os.environ["HWP_LINUX_OUTPUT"])
    code = 2
    with output.open("w", encoding="utf-8", buffering=1) as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        if sys.platform == "win32":
            # Python redirection alone does not cover inherited subprocess or
            # native stdout handles (Proton's steam.exe can discard those).
            import ctypes
            from ctypes import wintypes
            import msvcrt
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.SetStdHandle.argtypes = (wintypes.DWORD, wintypes.HANDLE)
            handle = msvcrt.get_osfhandle(stream.fileno())
            for standard in (-11, -12):
                if not kernel.SetStdHandle(standard & 0xffffffff, handle):
                    raise ctypes.WinError(ctypes.get_last_error())
        try:
            code = main(sys.argv[1:])
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            if isinstance(exc.code, str):
                print(exc.code)
        except BaseException:
            traceback.print_exc()
        finally:
            result.write_text(json.dumps({"exit_code": code}) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(run())
