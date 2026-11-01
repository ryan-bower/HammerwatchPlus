"""Bootstrap gates with synthetic trees and fake gamepaths/pin/compiler modules.

No setup command, compiler, archive extractor or game is executed. The sibling
bootstrap.py is loaded only after every machine-specific dependency is replaced.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeBootstrap:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="b-", dir=os.environ.get("HWP_BOOTSTRAP_TEST_ROOT"))
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "w"
        self.repo.mkdir()
        self.install = self.root / "install"
        self.install.mkdir()
        (self.install / "untouched.cfg").write_bytes(b"fake install configuration")
        (self.root / "answers.json").write_text('{"no_hoh1": true}', encoding="utf-8")
        self.payloads = {
            "gamecode/sdk/hoh2": {"scripts/base.as": b"fake source"},
            "gamecode/assets": {"api.txt": b"fake API"},
            "gamecode/datatables": {"table.json": b"{}"},
            "tools/bin": {"PACKAGER.exe": b"fake packager; never execute"},
        }
        for tree, files in self.payloads.items():
            for relative, data in files.items():
                path = self.repo / tree / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        paths = types.ModuleType("gamepaths")
        for key, value in {"REPO": self.repo, "GAMELAB": self.repo / "gamelab", "DOCS": self.repo / "docs",
                           "GAMECODE": self.repo / "gamecode", "TOOLS": self.repo / "tools",
                           "TOOLS_BIN": self.repo / "tools/bin", "BASE_HOH2": self.repo / "gamecode/sdk/hoh2",
                           "BASE_HOH1": self.repo / "gamecode/sdk/hoh1"}.items():
            setattr(paths, key, value)
        paths.find_gcc = lambda: str(self.repo / "compiler/gcc.exe")
        paths.gcc_environment = lambda gcc: {"PATH": str(Path(gcc).parent), "FAKE_COMPILER": "1"}
        paths.hoh2_dir = lambda *args, **kwargs: self._forbidden("install discovery")
        paths.hoh1_dir = lambda *args, **kwargs: self._forbidden("HoH1 discovery")
        pin = types.ModuleType("pin_build")
        self.pin = {"build_id": "fake-build", "exe_sha256": "0" * 64}
        pin.pinned = lambda: dict(self.pin)
        pin.mismatch = lambda: []
        pin.EXIT_BUILD_MISMATCH = 3
        spec = importlib.util.spec_from_file_location("_isolated_bootstrap", Path(__file__).with_name("bootstrap.py"))
        self.tool = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"gamepaths": paths, "pin_build": pin}), patch.object(sys, "path", sys.path.copy()):
            spec.loader.exec_module(self.tool)
        self.tool.SHIM_SRC.parent.mkdir(parents=True)
        self.tool.SHIM_SRC.write_bytes(b"/* fake compiler source */")
        self.tool.SHIM_DLL.write_bytes(b"previous complete fake DLL")
        self.stamp = paths.TOOLS_BIN / "hwr2_capture.build.json"
        self.write_stamp()
        self.tool.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        self.manifest = {"build_id": self.pin["build_id"], "recorded": "fixture",
                         "tiers": {"required": {tree: self.expected(files) for tree, files in self.payloads.items()},
                                   "optional": {}}}
        self.write_manifest()
        self.tool.MANIFEST_LOCAL.write_text('{"checked": "historical", "ok": true}', encoding="utf-8")
        self.compiler_calls = []

    @staticmethod
    def _forbidden(label):
        raise AssertionError(f"Fake bootstrap must never call real {label}")

    @staticmethod
    def expected(files):
        groups = {}
        for relative, data in files.items():
            top = relative.split("/", 1)[0] if "/" in relative else "."
            groups.setdefault(top, []).append((relative, hashlib.sha256(data).hexdigest(), len(data)))
        return {top: {"files": len(items), "bytes": sum(size for _, _, size in items),
                      "sha256": hashlib.sha256("".join(f"{name}\0{digest}\n" for name, digest, _ in sorted(items)).encode()).hexdigest()}
                for top, items in groups.items()}

    def write_stamp(self, value=None):
        value = value if value is not None else {"source_sha256": hashlib.sha256(self.tool.SHIM_SRC.read_bytes()).hexdigest(),
                                                "dll_sha256": hashlib.sha256(self.tool.SHIM_DLL.read_bytes()).hexdigest(),
                                                "gcc": "fake-version"}
        self.stamp.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def write_manifest(self, value=None):
        value = self.manifest if value is None else value
        self.tool.MANIFEST.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def state(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path != self.tool.MANIFEST_LOCAL}

    def compiler(self, *, compile_code=0, version_code=0, version="fake-version", write_output=True, launch_error=None):
        def run(command, *args, **kwargs):
            self.compiler_calls.append(command)
            if launch_error is not None:
                raise launch_error
            if "-shared" in command:
                output = Path(command[command.index("-o") + 1])
                if not output.resolve().is_relative_to(self.repo.resolve()):
                    raise AssertionError("Compiler output escaped the fake repository")
                if write_output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"new complete fake DLL")
                return subprocess.CompletedProcess(command, compile_code, "", "fake compile failure" if compile_code else "")
            if command[-1] == "-dumpfullversion":
                return subprocess.CompletedProcess(command, version_code, version, "fake version failure" if version_code else "")
            raise AssertionError(f"Unexpected external command: {command}")
        return run


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.f = FakeBootstrap()
        self.addCleanup(self.f.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.object(self.f.tool.subprocess, "run", side_effect=AssertionError("No external command is permitted")).start()

    def verify_refuses(self):
        before = self.f.state()
        try:
            code = self.f.tool.verify()
        except Exception as error:
            self.fail(f"Verification must refuse safely, not raise {type(error).__name__}: {error}")
        self.assertNotEqual(code, 0)
        self.assertFalse(json.loads(self.f.tool.MANIFEST_LOCAL.read_text())["ok"], "A failed check left historical green metadata")
        self.assertEqual(self.f.state(), before)

    def build(self, *, force=True):
        try:
            self.f.tool.build_shim(force)
            return "ok"
        except SystemExit:
            return "refused"
        except Exception as error:
            self.fail(f"Shim build must refuse safely, not raise {type(error).__name__}: {error}")

    def test_valid_fixture_verifies_without_external_commands(self):
        before = self.f.state()
        self.assertEqual(self.f.tool.verify(), 0)
        self.assertEqual(self.f.state(), before)

    def test_manifest_build_must_match_the_current_pin(self):
        self.f.manifest["build_id"] = "old-build"
        self.f.write_manifest()
        self.verify_refuses()

    def test_missing_manifest_invalidates_historical_green(self):
        self.f.tool.MANIFEST.unlink()
        self.verify_refuses()

    def test_local_diagnostic_hardlink_does_not_overwrite_fake_answers(self):
        answer = self.f.root / "answers.json"
        before = answer.read_bytes()
        self.f.tool.MANIFEST_LOCAL.unlink()
        os.link(answer, self.f.tool.MANIFEST_LOCAL)
        self.assertEqual(self.f.tool.verify(), 0)
        self.assertEqual(answer.read_bytes(), before)
        self.assertTrue(json.loads(self.f.tool.MANIFEST_LOCAL.read_text())["ok"])

    def test_missing_or_changed_required_data_refuses(self):
        target = self.f.repo / "gamecode/sdk/hoh2/scripts/base.as"
        target.write_bytes(b"changed base data")
        self.verify_refuses()
        target.unlink()
        self.verify_refuses()

    def test_invalid_manifest_schemas_refuse_without_other_mutation(self):
        original = json.loads(json.dumps(self.f.manifest))
        mutations = ("{", "[]", {}, {**original, "tiers": []},
                     {**original, "tiers": {"required": {}, "optional": {}}},
                     {**original, "tiers": {**original["tiers"], "unknown": {}}},
                     {**original, "tiers": {"required": {**original["tiers"]["required"], "../outside": {}}}},
                     {**original, "tiers": {"required": {**original["tiers"]["required"], "tools/bin": []}}})
        for value in mutations:
            with self.subTest(value=value):
                self.f.write_manifest(value)
                self.verify_refuses()

    def test_manifest_cannot_authorize_hashing_outside_the_repo(self):
        outside = self.f.root / "outside"
        outside.mkdir()
        (outside / "protected.txt").write_bytes(b"outside generated tree")
        self.f.manifest["tiers"]["required"]["../outside"] = self.f.expected({"protected.txt": b"outside generated tree"})
        self.f.write_manifest()
        original = self.f.tool.tree_hash

        def guarded(path):
            if not Path(path).resolve().is_relative_to(self.f.repo.resolve()):
                raise AssertionError("Manifest attempted to hash outside the fake repository")
            return original(path)

        with patch.object(self.f.tool, "tree_hash", guarded):
            self.verify_refuses()

    def test_malformed_or_legacy_shim_stamps_refuse(self):
        current = json.loads(self.f.stamp.read_text())
        for value in ("{", "[]", {}, {**current, "source_sha256": []}, {**current, "dll_sha256": []},
                      {"source_sha256": current["source_sha256"], "gcc": "legacy-source-only"}):
            with self.subTest(value=value):
                self.f.write_stamp(value)
                self.verify_refuses()

    def test_changed_dll_cannot_use_an_unchanged_source_stamp(self):
        self.f.tool.SHIM_DLL.write_bytes(b"partial or corrupted DLL")
        self.verify_refuses()

    def test_optional_hoh1_absence_is_explicit_but_changed_present_data_refuses(self):
        relative = "scripts/optional.as"
        self.f.manifest["tiers"]["required"]["gamecode/sdk/hoh1"] = self.f.expected({relative: b"optional"})
        self.f.write_manifest()
        self.assertEqual(self.f.tool.verify(), 0)
        path = self.f.repo / "gamecode/sdk/hoh1" / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(b"optional")
        self.assertEqual(self.f.tool.verify(), 0)
        path.write_bytes(b"changed optional")
        self.verify_refuses()

    def test_reparse_root_or_empty_directory_refuses_from_stat_contract(self):
        empty = self.f.repo / "gamecode/sdk/hoh2/empty"
        empty.mkdir()
        original = Path.lstat
        for target in (self.f.repo / "gamecode/sdk/hoh2", empty):
            with self.subTest(target=target):
                def reparse(path, *args, **kwargs):
                    if path == target:
                        return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                    return original(path, *args, **kwargs)
                with patch.object(Path, "lstat", reparse):
                    self.verify_refuses()

    def test_build_mismatch_refuses_before_any_mutator_even_with_force(self):
        before = self.f.state()
        with patch.object(self.f.tool.pin_build, "mismatch", return_value=["fake changed build"]):
            for name in ("ensure_packager", "build_shim", "extract_hoh2", "extract_hoh1", "api_strings", "datatables", "record", "community"):
                patch.object(self.f.tool, name, side_effect=AssertionError("Build mismatch must not call a mutator")).start()
            self.assertEqual(self.f.tool.main(["--force", "--with-community"]), 3)
        self.assertEqual(self.f.state(), before)

    def test_matching_build_dispatches_only_explicitly_mocked_setup_steps(self):
        before = self.f.state()
        calls = []
        names = ("ensure_packager", "build_shim", "extract_hoh2", "extract_hoh1", "api_strings", "datatables")
        for name in names:
            patch.object(self.f.tool, name, side_effect=lambda force, selected=name: calls.append((selected, force))).start()
        patch.object(self.f.tool, "verify", side_effect=lambda: calls.append(("verify", None)) or 0).start()
        patch.object(self.f.tool, "record", side_effect=AssertionError("Matching build must not re-record or re-pin")).start()
        with patch.dict(sys.modules, {"hidden_desktop": types.ModuleType("hidden_desktop")}):
            self.assertEqual(self.f.tool.main(["--force"]), 0)
        self.assertEqual(calls, [(name, True) for name in names] + [("verify", None)])
        self.assertEqual(self.f.state(), before)

    def test_current_cache_skips_compiler_without_mutating_inputs(self):
        before = self.f.state()
        self.assertEqual(self.build(force=False), "ok")
        self.assertEqual(self.f.state(), before)

    def test_successful_fake_compile_publishes_verified_dll_and_stamp(self):
        with patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler()):
            self.assertEqual(self.build(), "ok")
        self.assertEqual(self.f.tool.SHIM_DLL.read_bytes(), b"new complete fake DLL")
        stamp = json.loads(self.f.stamp.read_text())
        self.assertEqual(stamp.get("dll_sha256"), hashlib.sha256(self.f.tool.SHIM_DLL.read_bytes()).hexdigest())
        self.assertEqual(self.f.tool.verify(), 0)

    def test_failed_force_compile_preserves_prior_complete_pair(self):
        before = self.f.state()
        with patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler(compile_code=1)):
            self.assertEqual(self.build(), "refused")
        self.assertEqual(self.f.state(), before)
        self.assertEqual(self.f.tool.verify(), 0)

    def test_compiler_launch_failure_preserves_prior_complete_pair(self):
        before = self.f.state()
        with patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler(launch_error=PermissionError("fake launch denial"))):
            self.assertEqual(self.build(), "refused")
        self.assertEqual(self.f.state(), before)

    def test_zero_exit_without_output_cannot_restamp_old_dll_as_new_source(self):
        self.f.tool.SHIM_SRC.write_bytes(b"new source requires a new DLL")
        before = self.f.state()
        with patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler(write_output=False)):
            self.assertEqual(self.build(), "refused")
        self.assertEqual(self.f.state(), before)

    def test_failed_or_empty_version_probe_cannot_replace_the_pair(self):
        for code, version in ((1, "fake-version"), (0, "")):
            with self.subTest(code=code, version=version):
                before = self.f.state()
                with patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler(version_code=code, version=version)):
                    self.assertEqual(self.build(), "refused")
                self.assertEqual(self.f.state(), before)

    def test_stamp_write_failure_preserves_prior_pair(self):
        before = self.f.state()
        original = Path.write_text
        reached = []

        def fail(path, data, *args, **kwargs):
            if path.name == self.f.stamp.name:
                reached.append(True)
                original(path, "{", *args, **kwargs)
                raise OSError("fake stamp write failure")
            return original(path, data, *args, **kwargs)

        with patch.object(Path, "write_text", fail), patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler()):
            self.assertEqual(self.build(), "refused")
        self.assertTrue(reached)
        self.assertEqual(self.f.state(), before)

    def test_silent_staged_corruption_refuses_before_publication(self):
        original = Path.write_text
        for corruption in ("invalid-json", "source_sha256", "dll_sha256", "gcc", "dll-bytes"):
            with self.subTest(corruption=corruption):
                before = self.f.state()
                reached = []

                def corrupt(path, data, *args, **kwargs):
                    if path.name == self.f.stamp.name and path != self.f.stamp:
                        reached.append(True)
                        if corruption == "invalid-json":
                            data = "{"
                        elif corruption == "dll-bytes":
                            path.with_name(self.f.tool.SHIM_DLL.name).write_bytes(b"silently changed staged DLL")
                        else:
                            value = json.loads(data)
                            value[corruption] = "wrong compiler" if corruption == "gcc" else "0" * 64
                            data = json.dumps(value)
                    return original(path, data, *args, **kwargs)

                with patch.object(Path, "write_text", corrupt), \
                        patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler()):
                    self.assertEqual(self.build(), "refused")
                self.assertTrue(reached, "The staged corruption fault must be reached")
                self.assertEqual(self.f.state(), before)
                self.assertEqual(self.f.tool.verify(), 0)

    def test_stamp_publication_failure_rolls_back_dll(self):
        before = self.f.state()
        original = os.replace
        reached = []

        def fail(source, destination, *args, **kwargs):
            if Path(destination) == self.f.stamp and not reached:
                reached.append(True)
                raise PermissionError("fake stamp publication denial")
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "replace", fail), patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler()):
            self.assertEqual(self.build(), "refused")
        self.assertTrue(reached, "Publication fault hook must be reached")
        self.assertEqual(self.f.state(), before)

    def test_corrupted_cache_rebuilds_instead_of_skipping_on_source_hash(self):
        self.f.tool.SHIM_DLL.write_bytes(b"corrupted cache")
        with patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler()):
            self.assertEqual(self.build(force=False), "ok")
        self.assertEqual(len(self.f.compiler_calls), 2)
        self.assertEqual(self.f.tool.verify(), 0)

    def test_failed_publication_rollback_keeps_recovery_and_never_verifies_green(self):
        original = os.replace
        publish, rollback = [], []
        previous = self.f.tool.SHIM_DLL.read_bytes()

        def fail(source, destination, *args, **kwargs):
            if Path(destination) == self.f.stamp and not publish:
                publish.append(True)
                raise PermissionError("fake stamp publication denial")
            if publish and Path(destination) == self.f.tool.SHIM_DLL and not rollback:
                rollback.append(True)
                raise PermissionError("fake old-DLL rollback denial")
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "replace", fail), patch.object(self.f.tool.subprocess, "run", side_effect=self.f.compiler()):
            self.assertEqual(self.build(), "refused")
        self.assertTrue(publish and rollback)
        self.assertNotEqual(self.f.tool.verify(), 0)
        self.assertTrue(any(path.read_bytes() == previous for path in (self.f.repo / "tools/bin").rglob("*") if path.is_file()),
                        "Last complete DLL was lost after rollback failure")
        self.assertEqual((self.f.install / "untouched.cfg").read_bytes(), b"fake install configuration")


if __name__ == "__main__":
    unittest.main(verbosity=2)
