"""`"needs_hoh1": true` scenarios are skipped (exit 7) on a machine without the HoH1 import
their mods read (gamelab/launcher.py hoh1_missing)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamelab import launcher  # noqa: E402
from tools import import_hoh1  # noqa: E402


def test_only_marked_scenarios_check(monkeypatch):
    monkeypatch.setattr(import_hoh1, "IMPORT_OUTPUTS", {"campaign": Path("/nope")})
    assert launcher.hoh1_missing({"mods": ["campaign"]}) == []


def test_the_mods_imports(monkeypatch, tmp_path):
    there = tmp_path / "there"
    there.mkdir()
    monkeypatch.setattr(import_hoh1, "IMPORT_OUTPUTS", {"campaign": tmp_path / "gone", "trinkets": there})
    assert launcher.hoh1_missing({"needs_hoh1": True, "mods": ["campaign", "trinkets"]}) == ["campaign"]
    assert launcher.hoh1_missing({"needs_hoh1": True, "mods": ["trinkets"]}) == []


def test_no_import_mod_means_every_import(monkeypatch, tmp_path):
    monkeypatch.setattr(import_hoh1, "IMPORT_OUTPUTS", {"pets": tmp_path / "gone"})
    assert launcher.hoh1_missing({"needs_hoh1": True, "mods": ["hwplib"]}) == ["pets"]


def test_run_skips_before_the_lock(monkeypatch, tmp_path, capsys):
    f = tmp_path / "s.json"
    f.write_text('{"name": "s", "needs_hoh1": true, "mods": ["hwplib"], "steps": []}', encoding="utf-8")
    monkeypatch.setattr(import_hoh1, "IMPORT_OUTPUTS", {"pets": tmp_path / "gone"})
    monkeypatch.setattr(launcher, "acquire", lambda *a: (_ for _ in ()).throw(AssertionError("locked")))
    assert launcher.run(str(f), "lab") == launcher.EXIT_SKIPPED
    assert "SKIPPED" in capsys.readouterr().out
