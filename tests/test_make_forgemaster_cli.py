"""CLI safety with synthetic outputs; no SDK build, image generation or game calls."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ForgeCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="forge-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.actors = self.root / "actors"
        self.actors.mkdir()
        self.out = self.root / "output"
        self.out.mkdir()
        self.text = self.out / "expected.txt"
        self.binary = self.out / "expected.bin"
        self.expected = {self.text: "synthetic output\n", self.binary: b"\x00\x01synthetic"}
        self.text.write_text(self.expected[self.text], encoding="utf-8")
        self.binary.write_bytes(self.expected[self.binary])
        self.sentinel = self.root / "user-answers.json"
        self.sentinel.write_text('{"preserve": true}', encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "tools" / "generate" / "make_forgemaster_risen.py"
        spec = importlib.util.spec_from_file_location("_forge_cli_test", script)
        self.gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gen)
        self.addCleanup(patch.stopall)
        for name, value in {"REPO": self.root, "ACTORS": self.actors, "OUT_DIRS": (self.out,),
                            "UNITS_AS": self.root / "units.as"}.items():
            patch.object(self.gen, name, value).start()
        self.build = patch.object(self.gen, "build", return_value=(self.expected, ["synthetic/unit.unit"])).start()

    def state(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    @contextlib.contextmanager
    def no_writes(self):
        with contextlib.ExitStack() as stack:
            spies = [stack.enter_context(patch.object(Path, name, side_effect=AssertionError("CLI must not write")))
                     for name in ("mkdir", "unlink", "write_text", "write_bytes")]
            yield spies
            for spy in spies:
                spy.assert_not_called()

    def invoke(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                result = self.gen.main(arguments)
                self.assertIsNone(result)
            except SystemExit as error:
                code = error.code
            except Exception as error:
                self.fail(f"Unexpected CLI failure: {error!r}")
        return code, stdout.getvalue(), stderr.getvalue()

    def test_unknown_arguments_refuse_before_sdk_probe_build_or_writes(self):
        before = self.state()
        original = Path.is_dir

        def no_sdk_probe(path):
            if path == self.actors:
                raise AssertionError("Argument validation must precede SDK probing")
            return original(path)

        for arguments in (["--verify"], ["--typo"], ["--che"], ["--check", "--verify"], ["unexpected"]):
            with self.subTest(arguments=arguments), patch.object(Path, "is_dir", no_sdk_probe), self.no_writes():
                code, _, error = self.invoke(arguments)
                self.assertEqual(code, 2)
                self.assertIn("unrecognized arguments", error)
                self.build.assert_not_called()
        self.assertEqual(self.state(), before)

    def test_help_succeeds_before_sdk_probe_build_or_writes(self):
        before = self.state()
        original = Path.is_dir

        def no_sdk_probe(path):
            if path == self.actors:
                raise AssertionError("Help must not need SDK discovery")
            return original(path)

        for arguments in (["--help"], ["-h"]):
            with self.subTest(arguments=arguments), patch.object(Path, "is_dir", no_sdk_probe), self.no_writes():
                code, output, _ = self.invoke(arguments)
                self.assertEqual(code, 0)
                self.assertIn("--check", output)
                self.assertIn("--list", output)
                self.build.assert_not_called()
        self.assertEqual(self.state(), before)

    def test_check_current_outputs_is_read_only(self):
        before = self.state()
        with self.no_writes():
            self.assertEqual(self.invoke(["--check"])[0], 0)
        self.build.assert_called_once_with()
        self.assertEqual(self.state(), before)

    def test_check_stale_or_extra_outputs_refuses_without_writing(self):
        extra = self.out / "orphan.txt"
        for fault in ("stale", "extra"):
            with self.subTest(fault=fault):
                self.text.write_text(self.expected[self.text], encoding="utf-8")
                extra.unlink(missing_ok=True)
                if fault == "stale":
                    self.text.write_text("stale synthetic output", encoding="utf-8")
                else:
                    extra.write_text("retain during check", encoding="utf-8")
                before = self.state()
                self.build.reset_mock()
                with self.no_writes():
                    code, output, _ = self.invoke(["--check"])
                    self.assertEqual(code, 1)
                    self.assertIn("stale:", output)
                self.build.assert_called_once_with()
                self.assertEqual(self.state(), before)

    def test_default_generation_keeps_writer_bytes_and_scope(self):
        self.text.write_text("old", encoding="utf-8")
        self.binary.write_bytes(b"old")
        extra = self.out / "orphan.txt"
        extra.write_text("remove only this synthetic extra", encoding="utf-8")
        sentinel = self.sentinel.read_bytes()
        calls = []

        def bounded(name, original):
            def call(path, *args, **kwargs):
                resolved = path.resolve()
                if resolved != self.out.resolve() and not resolved.is_relative_to(self.out.resolve()):
                    raise AssertionError(f"Writer escaped synthetic output: {path}")
                calls.append(name)
                return original(path, *args, **kwargs)
            return call

        with contextlib.ExitStack() as stack:
            for name in ("mkdir", "unlink", "write_text", "write_bytes"):
                original = getattr(Path, name)
                stack.enter_context(patch.object(Path, name, bounded(name, original)))
            self.assertEqual(self.invoke([])[0], 0)
        self.build.assert_called_once_with()
        self.assertEqual(self.text.read_bytes(), self.expected[self.text].encode("utf-8"))
        self.assertEqual(self.binary.read_bytes(), self.expected[self.binary])
        self.assertFalse(extra.exists())
        self.assertTrue({"unlink", "write_text", "write_bytes"}.issubset(calls))
        self.assertEqual(self.sentinel.read_bytes(), sentinel)

    def test_list_and_legacy_check_list_combination_are_read_only(self):
        before = self.state()
        for arguments in (["--list"], ["--check", "--list"]):
            with self.subTest(arguments=arguments), self.no_writes():
                self.build.reset_mock()
                code, output, _ = self.invoke(arguments)
                self.assertEqual(code, 0)
                self.assertIn("synthetic/unit.unit", output)
                self.assertIn("1 raisable", output)
                self.build.assert_called_once_with()
        self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()
