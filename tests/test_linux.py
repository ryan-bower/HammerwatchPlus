"""Host-side regressions; no game, Steam, or real saves are touched.

    python3 -m unittest gamelab.test_linux -v
"""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

if sys.platform == "linux":
    from gamelab import linux


@unittest.skipUnless(sys.platform == "linux", "Linux host backend")
class LinuxHostTests(unittest.TestCase):
    def test_windows_bridge_preserves_exit_code_and_output(self):
        from gamelab import wine_entry
        def exit_with_output(argv):
            print("diagnostic")
            raise SystemExit(6)
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.dict(os.environ, {"HWP_LINUX_RESULT": temp + "/result.json",
                                              "HWP_LINUX_OUTPUT": temp + "/output.log"}), \
                mock.patch("gamelab.__main__.main", side_effect=exit_with_output):
            self.assertEqual(wine_entry.run(), 6)
            self.assertEqual((Path(temp) / "result.json").read_text(), '{"exit_code": 6}\n')
            self.assertEqual((Path(temp) / "output.log").read_text(), "diagnostic\n")

    def test_host_returns_windows_status_not_proton_wrapper_status(self):
        runtime = {"wine": "wine", "wineserver": "server", "Xvfb": "Xvfb", "python": "/python.exe"}
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            def start(*args, **kwargs):
                (state / "host-result.json").write_text('{"exit_code": 5}')
                return mock.Mock(wait=mock.Mock(return_value=0))
            with mock.patch.object(linux, "STATE", state), \
                    mock.patch.object(linux, "prerequisites", return_value=(runtime, [])), \
                    mock.patch.object(linux, "isolated_display", return_value=contextlib.nullcontext(":123")), \
                    mock.patch.object(linux, "child_environment", return_value={}), \
                    mock.patch.object(linux, "mod_versions", return_value={}), \
                    mock.patch.object(linux.shutil, "which", return_value=None), \
                    mock.patch.object(linux.subprocess, "Popen", side_effect=start), \
                    mock.patch.object(linux.subprocess, "run"), \
                    mock.patch.object(linux, "stop_process_group"), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(linux.main(["doctor"]), 5)

    def test_host_git_provenance_includes_tracked_and_untracked_edits(self):
        replies = [subprocess.CompletedProcess([], 0, "040000 tree abc\tcore\n040000 tree def\tpets\n", ""),
                   subprocess.CompletedProcess([], 0, "mods/core/script.as\0", ""),
                   subprocess.CompletedProcess([], 0, "mods/newmod/info.xml\0", "")]
        with mock.patch.object(linux.subprocess, "run", side_effect=replies):
            self.assertEqual(linux.mod_versions(), {
                "core": {"tree": "abc", "dirty": True},
                "pets": {"tree": "def", "dirty": False},
                "newmod": {"tree": None, "dirty": True}})

    def test_native_steam_detection_ignores_other_users_and_dead_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "self").mkdir()
            (root / "123").mkdir()
            self.assertFalse(linux.steam_running(root))
            (root / "123/comm").write_text("steamwebhelper\n")
            self.assertFalse(linux.steam_running(root))
            (root / "123/comm").write_text("steam\n")
            self.assertTrue(linux.steam_running(root))
            with mock.patch.object(linux.os, "getuid", return_value=-1):
                self.assertFalse(linux.steam_running(root))

    def test_wine_doctor_uses_measured_host_facts(self):
        from gamelab import doctor
        for running in ("0", "1"):
            with mock.patch.dict(os.environ, {"HWP_HOST_STEAM_RUNNING": running,
                                              "HWP_HOST_GCC_TARGET": "x86_64-w64-mingw32"}), \
                    mock.patch.object(doctor.subprocess, "run") as run:
                self.assertEqual(doctor.process_running("steam.exe"), running == "1")
                self.assertEqual(doctor.gcc_target(), "x86_64-w64-mingw32")
                run.assert_not_called()

    def test_prefers_64_bit_wine_and_matching_server(self):
        def which(name):
            return {"wine64": "/opt/wine/bin/wine64",
                    "/opt/wine/bin/wineserver": "/opt/wine/bin/wineserver",
                    "Xvfb": "/usr/bin/Xvfb"}.get(name)
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(linux.shutil, "which", side_effect=which), \
                mock.patch.object(Path, "is_file", return_value=True):
            runtime, errors = linux.prerequisites()
        self.assertEqual(errors, [])
        self.assertEqual(runtime["wine"], "/opt/wine/bin/wine64")
        self.assertEqual(runtime["wineserver"], "/opt/wine/bin/wineserver")

    def test_cleanup_kills_descendants_after_leader_exits(self):
        proc = mock.Mock(pid=123)
        with mock.patch.object(linux.os, "killpg") as kill:
            linux.stop_process_group(proc)
        self.assertEqual(kill.call_args_list,
                         [mock.call(123, linux.signal.SIGTERM),
                          mock.call(123, linux.signal.SIGKILL)])

    def test_native_hoh1_is_usable_for_asset_imports(self):
        sys.path.insert(0, str(linux.REPO / "tools"))
        import gamepaths
        with tempfile.TemporaryDirectory() as temp:
            install = Path(temp)
            (install / "HWR").write_bytes(b"\x7fELF")
            self.assertFalse(gamepaths.valid_hoh1(install))
            (install / "res").mkdir()
            (install / "res/assets.bin").write_bytes(b"HWRR")
            self.assertTrue(gamepaths.valid_hoh1(install))
            # Windows Python in the Wine bridge must recognize it too.
            with mock.patch.object(gamepaths.sys, "platform", "win32"):
                self.assertTrue(gamepaths.valid_hoh1(install))

    def test_windows_doctor_keeps_native_dispatch(self):
        from gamelab.__main__ import main
        doctor = types.ModuleType("gamelab.doctor")
        doctor.main = mock.Mock(return_value=17)
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.dict(sys.modules, {"gamelab.doctor": doctor}):
            self.assertEqual(main(["doctor", "--fix"]), 17)
        doctor.main.assert_called_once_with(["--fix"])

    def test_native_cli_does_not_import_win32(self):
        for args in (["list"], ["list", "it"], ["--help"]):
            done = subprocess.run([sys.executable, "-m", "gamelab", *args],
                                  cwd=linux.REPO, capture_output=True, text=True, timeout=15)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn("WinDLL", done.stderr)

    def test_missing_runtime_is_preflight_failure(self):
        with mock.patch.object(linux, "prerequisites", return_value=({}, ["missing runtime"])), \
                mock.patch.object(linux, "isolated_display") as display, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(linux.main(["doctor"]), 2)
            display.assert_not_called()

    def test_watch_and_implicit_watch_are_refused_before_wine(self):
        for argv in (["run", "null-payload"], ["run", "null-payload", "--mode=watch"],
                     ["run", "null-payload", "--mode", "lab", "--mode", "watch"]):
            with mock.patch.object(linux, "prerequisites") as prerequisites, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(linux.main(argv), 2)
                prerequisites.assert_not_called()

    def test_equals_lab_is_accepted(self):
        with mock.patch.object(linux, "prerequisites", return_value=({}, ["missing runtime"])) as check, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(linux.main(["run", "null-payload", "--mode=lab"]), 2)
            check.assert_called_once()

    def test_run_without_native_steam_is_refused_before_wine(self):
        with mock.patch.object(linux, "prerequisites", return_value=({}, [])), \
                mock.patch.object(linux, "steam_running", return_value=False), \
                mock.patch.object(linux, "isolated_display") as display, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(linux.main(["run", "null-payload", "--mode", "lab"]), 2)
            display.assert_not_called()

    def test_path_translation(self):
        self.assertEqual(linux.windows_path("/tmp/opencode/with spaces/é"),
                         "Z:\\tmp\\opencode\\with spaces\\é")
        args = linux.translate_arguments(["run", "test.json", "--mode", "lab"])
        self.assertEqual(args[1], linux.windows_path("test.json"))
        for args in (["doctor", "--hoh1", "/games/HoH 1"],
                     ["doctor", "--hoh1=/games/HoH 1"]):
            translated = linux.translate_arguments(args)
            self.assertIn(linux.windows_path("/games/HoH 1"), translated[-1])

    def test_host_game_detection_includes_other_wine_prefixes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "123").mkdir()
            (root / "123/comm").write_text("HWR2.exe\n")
            self.assertEqual(linux.game_processes(root), [123])
            with mock.patch.object(linux.os, "getuid", return_value=-1):
                self.assertEqual(linux.game_processes(root), [])

    def test_player_game_or_unknown_visibility_refuses_before_wine(self):
        for error, pids in ((None, [123]), (RuntimeError("permission denied"), [])):
            for args in (["run", "null-payload", "--mode", "lab"],
                         ["suite", "it", "--mode", "lab"], ["doctor", "--smoke"]):
                with mock.patch.object(linux, "prerequisites", return_value=({}, [])), \
                        mock.patch.object(linux, "steam_running", return_value=True), \
                        mock.patch.object(linux, "game_processes", return_value=pids, side_effect=error), \
                        mock.patch.object(linux, "isolated_display") as display, \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(linux.main(args), 4)
                    display.assert_not_called()

    def test_current_run_and_suite_options_are_forwarded(self):
        for args in (["run", "null-payload", "--mode", "lab", "--wait", "30"],
                     ["suite", "it", "--stop-on-fail", "--since", "20261105-190000", "--wait", "30"]):
            with mock.patch.object(linux, "prerequisites", return_value=({}, ["missing runtime"])) as check, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(linux.main(args), 2)
                check.assert_called_once()
        with mock.patch.object(linux, "prerequisites") as check, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(linux.main(["suite", "it", "--mode", "watch"]), 2)
            check.assert_not_called()

    def test_private_environment_and_real_proton_backup_discovery(self):
        sys.path.insert(0, str(linux.REPO / "tools"))
        import gamepaths
        with mock.patch.dict(os.environ, {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0",
                                         "WINEPREFIX": "/real/player/prefix",
                                         "WINELOADER": "/real/player/wine",
                                         "WINESERVER": "/real/player/wineserver",
                                         "HWP_HOST_GCC_TARGET": "stale-compiler",
                                         "XAUTHORITY": "/real/player/auth"}, clear=True), \
                mock.patch.object(gamepaths, "steam_root", return_value=Path("/steam")), \
                mock.patch.object(gamepaths, "hoh2_dir", return_value=Path("/games/HoH2")), \
                mock.patch.object(gamepaths, "hoh1_dir", return_value=None), \
                mock.patch.object(gamepaths, "proton_localappdata", return_value=Path("/real/proton/appdata")):
            env = linux.child_environment(":123")
        self.assertEqual(env["DISPLAY"], ":123")
        self.assertEqual(env["WINEPREFIX"], str(linux.PREFIX))
        self.assertEqual(env["WINEARCH"], "win64")
        self.assertNotIn("WAYLAND_DISPLAY", env)
        self.assertNotIn("XAUTHORITY", env)
        self.assertNotIn("WINELOADER", env)
        self.assertNotIn("WINESERVER", env)
        self.assertNotIn("HWP_HOST_GCC_TARGET", env)
        self.assertEqual(env["HWP_STEAM_DIR"], "Z:\\steam")
        self.assertEqual(env["HWP_LOCALAPPDATA"], "Z:\\real\\proton\\appdata")

    def test_concurrent_host_is_refused(self):
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(linux, "STATE", Path(temp)), \
                mock.patch.object(linux, "prerequisites", return_value=({"wine": "wine"}, [])), \
                mock.patch.object(linux.fcntl, "flock", side_effect=BlockingIOError), \
                mock.patch.object(linux, "isolated_display") as display, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(linux.main(["doctor"]), 4)
            display.assert_not_called()

    def test_timeout_kills_only_private_wineserver(self):
        runtime = {"wine": "wine", "wineserver": "matching-wineserver",
                   "Xvfb": "Xvfb", "python": "/windows/python.exe"}
        private_env = {"DISPLAY": ":123", "WINEPREFIX": str(linux.PREFIX)}
        proc = mock.Mock()
        proc.wait.side_effect = subprocess.TimeoutExpired("wine", 180)
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(linux, "STATE", Path(temp)), \
                mock.patch.object(linux, "prerequisites", return_value=(runtime, [])), \
                mock.patch.object(linux, "isolated_display", return_value=contextlib.nullcontext(":123")), \
                mock.patch.object(linux, "child_environment", return_value=private_env), \
                mock.patch.object(linux, "mod_versions", return_value={}), \
                mock.patch.object(linux.subprocess, "Popen", return_value=proc), \
                mock.patch.object(linux, "stop_process_group") as stop, \
                mock.patch.object(linux.subprocess, "run") as cleanup, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(linux.main(["doctor"]), 2)
            stop.assert_called_once_with(proc)
            cleanup.assert_called_once_with(["matching-wineserver", "-k"], env=private_env,
                                            timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_proton_save_path_uses_the_games_library(self):
        sys.path.insert(0, str(linux.REPO / "tools"))
        import gamepaths
        with tempfile.TemporaryDirectory() as temp:
            steamapps = Path(temp) / "external-library" / "steamapps"
            appdata = (steamapps / "compatdata" / gamepaths.HOH2_APPID / "pfx" /
                       "drive_c/users/steamuser/AppData/Local")
            appdata.mkdir(parents=True)
            with mock.patch.object(gamepaths, "app_manifest", return_value=steamapps / "appmanifest_619820.acf"):
                self.assertEqual(gamepaths.proton_localappdata(), appdata)
                with mock.patch.object(gamepaths.sys, "platform", "win32"):
                    self.assertIsNone(gamepaths.proton_localappdata())

    def test_proton_runtime_uses_only_private_compatibility_data(self):
        sys.path.insert(0, str(linux.REPO / "tools"))
        import gamepaths
        private = linux.STATE / "proton/pfx"
        with mock.patch.dict(os.environ, {"HWP_PROTON": "1",
                                          "STEAM_COMPAT_DATA_PATH": "/player/compatdata",
                                          "STEAM_COMPAT_SHADER_PATH": "/player/shaders"}, clear=True), \
                mock.patch.object(linux, "PREFIX", private), \
                mock.patch.object(gamepaths, "steam_root", return_value=Path("/steam")), \
                mock.patch.object(gamepaths, "hoh2_dir", return_value=Path("/game")), \
                mock.patch.object(gamepaths, "hoh1_dir", return_value=None), \
                mock.patch.object(gamepaths, "proton_localappdata", return_value=None):
            env = linux.child_environment(":123")
        self.assertEqual(env["WINEPREFIX"], str(private))
        self.assertEqual(env["STEAM_COMPAT_DATA_PATH"], str(private.parent))
        self.assertEqual(env["STEAM_COMPAT_CLIENT_INSTALL_PATH"], "/steam")
        self.assertEqual(env["SteamAppId"], gamepaths.HOH2_APPID)
        self.assertEqual(env["STEAM_COMPAT_SHADER_PATH"], str(linux.STATE / "shaders"))

    @unittest.skipUnless(shutil.which("Xvfb"), "Xvfb not installed")
    def test_real_xvfb_uses_a_separate_display_and_cleans_up(self):
        with linux.isolated_display(shutil.which("Xvfb")) as display:
            self.assertNotEqual(display, os.environ.get("DISPLAY"))
            socket = Path("/tmp/.X11-unix") / ("X" + display[1:])
            self.assertTrue(socket.exists())
        self.assertFalse(socket.exists())


if __name__ == "__main__":
    unittest.main()
