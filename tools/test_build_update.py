"""Build identity must follow shipped inputs, including staged/deleted/new files."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import build


class UpdateIdentity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.environment = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.git("init", "-q")
        self.mod = {"id": "hwplib", "dev": False, "local_only": False, "exclude": ["notes.txt"]}
        for name in ("packages.json", "mods/hwplib/module.json", "mods/hwplib/info.xml",
                     "mods/hwplib/scripts/Core.as", "mods/hwplib/README.md", "mods/hwplib/notes.txt",
                     "mods/gamelab-hands/scripts/Build.as", "tools/run.py", "README.md"):
            self.write(name, "original")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline")
        self.patcher = mock.patch.object(build.paths, "REPO", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.clean = self.identity()
        self.assertFalse(self.clean.endswith("+"))

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, env=self.environment,
                       capture_output=True, check=True)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def identity(self):
        return build.update_id([self.mod])

    def test_tooling_docs_and_lab_changes_keep_the_clean_gameplay_identity(self):
        for name in ("tools/run.py", "README.md", "mods/gamelab-hands/scripts/Build.as",
                     "mods/hwplib/README.md", "mods/hwplib/notes.txt"):
            self.write(name, "changed")
        self.write("tools/new_builder.py", "new")
        self.write("mods/hwplib/.cache/scratch.as", "not shipped")
        self.write("mods/hwplib/scripts/Core.as.orig", "pristine comparison")
        self.git("add", "tools/run.py")
        self.assertEqual(self.identity(), self.clean)

    def test_runtime_script_changes_keep_a_real_mismatch(self):
        self.write("mods/hwplib/scripts/Core.as", "changed gameplay")
        self.assertEqual(self.identity(), self.clean + "+")

    def test_named_lab_and_local_only_modules_are_not_release_inputs(self):
        for cfg in ({"id": "devarena", "gamelab": True}, {"id": "spec-ranger-test", "local_only": True},
                    {"id": "custom-dev", "dev": True}):
            self.assertFalse(build.affects_release_update(f"mods/{cfg['id']}/scripts/Test.as", [cfg]))

    def test_staged_runtime_changes_count(self):
        self.write("mods/hwplib/scripts/Core.as", "changed gameplay")
        self.git("add", "mods/hwplib/scripts/Core.as")
        self.assertEqual(self.identity(), self.clean + "+")

    def test_untracked_runtime_files_count_because_the_builder_packs_them(self):
        self.write("mods/hwplib/scripts/New.as", "new gameplay")
        self.assertEqual(self.identity(), self.clean + "+")

    def test_deleted_runtime_file_counts(self):
        (self.root / "mods/hwplib/scripts/Core.as").unlink()
        self.assertEqual(self.identity(), self.clean + "+")

    def test_package_and_module_metadata_count(self):
        self.write("mods/hwplib/info.xml", "new metadata")
        self.assertEqual(self.identity(), self.clean + "+")
        self.write("mods/hwplib/info.xml", "original")
        self.write("mods/hwplib/module.json", "new dependencies")
        self.assertEqual(self.identity(), self.clean + "+")
        self.write("mods/hwplib/module.json", "original")
        self.write("packages.json", "new composition")
        self.assertEqual(self.identity(), self.clean + "+")


if __name__ == "__main__":
    unittest.main()
