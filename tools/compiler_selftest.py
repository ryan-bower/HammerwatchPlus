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
        patch.object(bootstrap, "REPO", self.root).start()

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
        def fake_compiler(command, **kwargs):
            if "-shared" in command:
                Path(command[command.index("-o") + 1]).write_bytes(b"fake DLL; never loaded")
                return subprocess.CompletedProcess(command, 0)
            return subprocess.CompletedProcess(command, 0, "15.2.0\n", "")
        with patch.object(gamepaths, "find_gcc", return_value=gcc), \
                patch.object(gamepaths, "TOOLS_BIN", tools_bin), \
                patch.object(bootstrap, "SHIM_SRC", source), \
                patch.object(bootstrap, "SHIM_DLL", tools_bin / "capture.dll"), \
                patch.object(bootstrap.subprocess, "run", side_effect=fake_compiler) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            bootstrap.build_shim(force=True)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][0], gcc)
            self.assertEqual(call.kwargs["env"], gamepaths.gcc_environment(gcc))


    def test_doctor_probe_rejects_nonzero_exit_even_with_target_stdout(self):
        gcc = self.compiler("mingw64")
        for code in (1, 2):
            with self.subTest(returncode=code), patch.object(gamepaths, "find_gcc", return_value=gcc), \
                    patch.object(doctor.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [gcc, "-dumpmachine"], code, "x86_64-w64-mingw32\n", "fake probe failure")):
                self.assertIsNone(doctor.gcc_target(), "Failed commands cannot establish a usable compiler")

    def test_doctor_probe_handles_launch_denial_and_timeout(self):
        gcc = self.compiler("mingw64")
        for error in (PermissionError("fake compiler access denied"),
                      subprocess.TimeoutExpired([gcc, "-dumpmachine"], 10)):
            with self.subTest(error=type(error).__name__), patch.object(gamepaths, "find_gcc", return_value=gcc), \
                    patch.object(doctor.subprocess, "run", side_effect=error) as child:
                try:
                    result = doctor.gcc_target()
                except (OSError, subprocess.SubprocessError) as raised:
                    self.fail(f"Failed compiler probe must return unavailable, not raise {raised!r}")
                self.assertIsNone(result)
                self.assertGreater(child.call_args.kwargs.get("timeout", 0), 0)
                self.assertLessEqual(child.call_args.kwargs["timeout"], 30)

    def test_failed_probe_blocks_bootstrap_in_complete_fake_diagnosis(self):
        import types
        from gamelab import __name__ as package_name

        root = self.root / "diagnosis"
        install = root / "install"
        install.mkdir(parents=True)
        (install / "HWR2.exe").write_bytes(b"fake executable; never run")
        (install / "HWR2.exe.cfg").write_text("g_save_slot_cloud 1\n", encoding="utf-8")
        (root / "paths.local.json").write_text('{"no_hoh1": true, "hoh1_dir": null}', encoding="utf-8")
        (root / "confirmed.json").write_text('{"fixture": "already confirmed"}', encoding="utf-8")
        gcc = self.compiler("mingw64")

        def files():
            return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}

        original = files()
        responses = (subprocess.CompletedProcess([], 1, "x86_64-w64-mingw32\n", "fake failure"),
                     subprocess.CompletedProcess([], 0, "aarch64-w64-mingw32\n", ""),
                     subprocess.TimeoutExpired([gcc, "-dumpmachine"], 10))
        for response in responses:
            with self.subTest(response=repr(response)), contextlib.ExitStack() as stack:
                def replace(obj, name, **kwargs):
                    return stack.enter_context(patch.object(obj, name, **kwargs))

                for name, path in {"REPO": root, "GAMELAB": root / "gamelab", "DOCS": root / "docs",
                                   "TOOLS": root / "tools", "TOOLS_BIN": root / "tools/bin",
                                   "GAMECODE": root / "gamecode", "BASE_HOH2": root / "gamecode/sdk/hoh2",
                                   "BASE_HOH1": root / "gamecode/sdk/hoh1", "SAVES_BACKUP": root / "backups"}.items():
                    replace(gamepaths, name, new=path)
                replace(doctor, "REPO", new=root)
                replace(doctor, "VENV_PY", new=root / ".venv/Scripts/python.exe")
                replace(doctor, "SMOKE_STAMP", new=root / "smoke.local.json")
                replace(doctor, "python", return_value="fake-python; never run")
                replace(doctor, "deps_missing", return_value=[])
                replace(gamepaths, "hoh2_dir", return_value=install)
                replace(gamepaths, "steam_root", return_value=root / "Steam")
                replace(gamepaths, "local_paths_file", return_value=root / "paths.local.json")
                replace(gamepaths, "real_save_dirs", return_value={"cloud": root / "cloud"})
                replace(gamepaths, "real_config", return_value=install / "HWR2.exe.cfg")
                replace(gamepaths, "find_gcc", return_value=gcc)
                replace(doctor, "process_running", return_value=True)
                replace(doctor, "hoh1_check", return_value=("declined", None, "fixture user choice"))
                replace(doctor.pin_build, "mismatch", return_value=[])
                replace(doctor.pin_build, "pinned", return_value={"build_id": "fake-build"})
                replace(doctor.shutil, "which", return_value=None)
                replace(doctor.shutil, "disk_usage", return_value=types.SimpleNamespace(free=8 * 2**30))
                replace(doctor.saves, "confirmation_problems", return_value=[])
                confirm = replace(doctor, "confirm_saves", side_effect=AssertionError("No confirmation is authorized"))
                replace(doctor, "local_content", return_value=None)
                replace(doctor, "smoke", side_effect=AssertionError("No smoke is authorized"))
                verify_calls, denied_commands = [], []

                def verify(arguments):
                    self.assertEqual(arguments, [str(root / "tools/bootstrap.py"), "--verify"])
                    verify_calls.append(arguments)
                    return subprocess.CompletedProcess(arguments, 1, "fake missing generated tree\n", "")

                def compiler(command, **kwargs):
                    if command != [gcc, "-dumpmachine"]:
                        denied_commands.append(command)
                        raise AssertionError("Unresolved compiler attempted a setup command")
                    if isinstance(response, BaseException):
                        raise response
                    return response

                replace(doctor, "run_py", side_effect=verify)
                replace(doctor.subprocess, "run", side_effect=compiler)
                fake_env = types.ModuleType("gamelab.env")
                fake_env.link = lambda fix: []
                stack.enter_context(patch.dict(sys.modules, {"gamelab.env": fake_env}))
                stack.enter_context(patch.object(sys.modules[package_name], "env", fake_env, create=True))
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        report = doctor.diagnose(fix=True, no_smoke=True)
                    except (OSError, subprocess.SubprocessError, AssertionError) as error:
                        self.fail(f"Failed prerequisite must refuse without launching setup: {error!r}")
                compiler_rows = [ok for name, ok, _ in report.rows if name.startswith("gcc mingw-w64")]
                self.assertEqual(compiler_rows, [False])
                self.assertFalse(report.green)
                self.assertEqual(len(verify_calls), 1)
                self.assertEqual(denied_commands, [])
                confirm.assert_not_called()
                self.assertEqual(files(), original)


if __name__ == "__main__":
    unittest.main()
