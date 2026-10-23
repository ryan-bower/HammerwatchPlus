"""gamelab/bots/devarena_clone.py, offline: clone_spec is faked, the comparison is real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamelab.bots import devarena_clone as bot  # noqa: E402


class FakeGame:
    def read_log(self):
        return "x [HWP:devarena] nothing\n"


class P:
    run_id = "fake"
    game = FakeGame()


def fake_clone(files):
    def main(argv):
        out = Path(argv[argv.index("--out") + 1]) / "spec-ranger-test"
        for rel, text in files.items():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_text(text, encoding="utf-8")
        print("cloned")
        return 0
    return main


def test_identical_and_differ(tmp_path, monkeypatch):
    mod = tmp_path / "repo" / "mods" / "spec-ranger-test"
    (mod / "a").mkdir(parents=True)
    (mod / "a" / "x.sval").write_text("1", encoding="utf-8")
    (mod / "y.txt").write_text("2", encoding="utf-8")
    monkeypatch.setattr(bot, "REPO", tmp_path / "repo")
    res = tmp_path / "run"
    res.mkdir()

    monkeypatch.setattr(bot.clone_spec, "main", fake_clone({"a/x.sval": "1", "y.txt": "2"}))
    r = bot.run(P, "ranger_nature", "ranger_test", "Test Warden", version=1, results=res)
    assert r["terminal"] == "done" and r["identical"] and r["files"] == 2
    assert (res / "clone.HWR2.exe.log").read_text(encoding="utf-8").startswith("x [HWP")
    assert "cloned" in (res / "clone.out.txt").read_text(encoding="utf-8")

    monkeypatch.setattr(bot.clone_spec, "main", fake_clone({"a/x.sval": "9", "z.txt": "3"}))
    r = bot.run(P, "ranger_nature", "ranger_test", "Test Warden", results=res)
    assert not r["identical"] and r["differ"] == ["a/x.sval", "z.txt"]


def test_clone_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "REPO", tmp_path)
    monkeypatch.setattr(bot.clone_spec, "main", lambda argv: 1)
    r = bot.run(P, "ranger_nature", "ranger_test", "Test Warden", results=tmp_path)
    assert r["terminal"] == "clone_failed" and r["code"] == 1
