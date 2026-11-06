"""Exercise the shell launcher's forwarding and source isolation without Nix."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == "linux", "Linux shell launcher")
class LauncherTests(unittest.TestCase):
    def test_only_flake_files_are_staged_and_exit_status_is_preserved(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = root / "nix"
            fake.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
source = Path(sys.argv[sys.argv.index("develop") + 1].removeprefix("path:"))
Path(os.environ["NIX_SPY"]).write_text(json.dumps({"args": sys.argv[1:],
    "source": str(source), "files": sorted(p.name for p in source.iterdir()), "cwd": os.getcwd()}))
sys.exit(6)
''')
            fake.chmod(0o755)
            spy = root / "spy.json"
            for args, command in ((["run", "null-payload", "--mode", "lab"],
                                   ["python", "-m", "gamelab", "run", "null-payload", "--mode", "lab"]),
                                  (["setup"], ["python", "tools/setup_gamelab_linux.py"])):
                done = subprocess.run([str(repo / "gamelab.sh"), *args], cwd=root,
                                      env=dict(os.environ, PATH=str(root) + ":" + os.environ["PATH"],
                                               TMPDIR=str(root), NIX_SPY=str(spy)),
                                      capture_output=True, text=True, timeout=15)
                self.assertEqual(done.returncode, 6, done.stderr)
                observed = json.loads(spy.read_text())
                self.assertEqual(observed["files"], ["flake.lock", "flake.nix"])
                self.assertEqual(observed["cwd"], str(repo))
                command_index = observed["args"].index("--command") + 1
                self.assertEqual(observed["args"][command_index:], command)
                self.assertFalse(Path(observed["source"]).exists())


if __name__ == "__main__":
    unittest.main()
