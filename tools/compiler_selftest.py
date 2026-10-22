#!/usr/bin/env python3
"""Check compiler discovery and child environments without invoking GCC or the game."""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
import bootstrap  # noqa: E402
import gamepaths  # noqa: E402
from gamelab import doctor  # noqa: E402


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="hwp-compiler-selftest-")
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.addCleanup(patch.stopall)
        patch.object(gamepaths, "REPO", self.root).start()

    def compiler(self, name):
        gcc = self.root / "gamelab" / "fixtures" / "cache" / "toolchain" / name / "bin" / "gcc.exe"
        gcc.parent.mkdir(parents=True, exist_ok=True)
        gcc.touch()
        return str(gcc)

    def test_path_compiler_takes_precedence(self):
        self.compiler("mingw64")
        with patch.object(gamepaths.shutil, "which", return_value="existing-gcc"):
            self.assertEqual(gamepaths.find_gcc(), "existing-gcc")

    def test_local_mingw64_precedes_w64devkit(self):
        expected = self.compiler("mingw64")
        self.compiler("w64devkit")
        with patch.object(gamepaths.shutil, "which", return_value=None):
            self.assertEqual(gamepaths.find_gcc(), expected)

    def test_local_w64devkit_fallback(self):
        expected = self.compiler("w64devkit")
        with patch.object(gamepaths.shutil, "which", return_value=None):
            self.assertEqual(gamepaths.find_gcc(), expected)

    def test_missing_compiler(self):
        with patch.object(gamepaths.shutil, "which", return_value=None):
            self.assertIsNone(gamepaths.find_gcc())

    def test_compiler_environment_preserves_parent(self):
        gcc = self.compiler("mingw64")
        before = os.environ.copy()
        env = gamepaths.gcc_environment(gcc)
        self.assertEqual(env["PATH"], str(Path(gcc).parent) + os.pathsep + before.get("PATH", ""))
        self.assertEqual(os.environ.copy(), before)
        self.assertEqual({k: v for k, v in env.items() if k != "PATH"},
                         {k: v for k, v in before.items() if k != "PATH"})

    def test_doctor_probe_uses_compiler_environment(self):
        gcc = self.compiler("mingw64")
        reply = subprocess.CompletedProcess([], 0, "x86_64-w64-mingw32\n", "")
        with patch.object(gamepaths, "find_gcc", return_value=gcc), \
                patch.object(doctor.subprocess, "run", return_value=reply) as run:
            self.assertEqual(doctor.gcc_target(), "x86_64-w64-mingw32")
        self.assertEqual(run.call_args.args[0], [gcc, "-dumpmachine"])
        self.assertEqual(run.call_args.kwargs["env"], gamepaths.gcc_environment(gcc))

    def test_bootstrap_children_use_compiler_environment(self):
        gcc = self.compiler("w64devkit")
        source = self.root / "capture.c"
        source.write_text("/* test source */", encoding="utf-8")
        tools_bin = self.root / "tools" / "bin"
        replies = [subprocess.CompletedProcess([], 0),
                   subprocess.CompletedProcess([], 0, "15.2.0\n", "")]
        with patch.object(gamepaths, "find_gcc", return_value=gcc), \
                patch.object(gamepaths, "TOOLS_BIN", tools_bin), \
                patch.object(bootstrap, "SHIM_SRC", source), \
                patch.object(bootstrap, "SHIM_DLL", tools_bin / "capture.dll"), \
                patch.object(bootstrap.subprocess, "run", side_effect=replies) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            bootstrap.build_shim(force=True)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][0], gcc)
            self.assertEqual(call.kwargs["env"], gamepaths.gcc_environment(gcc))


if __name__ == "__main__":
    unittest.main()
