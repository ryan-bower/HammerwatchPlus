"""tools/make_config.py: a module's config block is checked against how its code reads each
setting, and the generated files are current."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import make_config  # noqa: E402


def fake_mod(tmp_path, monkeypatch, code: str, name="demo"):
    scripts = tmp_path / name / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "Demo.as").write_text(code, encoding="utf-8")
    monkeypatch.setattr(make_config, "MODS", tmp_path)
    return name


def errors(mod, cfg):
    out: list[str] = []
    make_config.check_block(mod, cfg, out)
    return out


CODE = """
	bool on = HWP::Settings::GetBool("demo.enabled", true);
	float mult = HWP::Settings::GetFloat("demo.mult", 2.0f);
	int n = HWP::Settings::GetInt("demo.n", 3);
	HWP::Options::Register("demokey", DemoKey());
"""


def good():
    return {"about": "A demo.", "toggle": "demo.enabled", "settings": [
        {"key": "demo.mult", "type": "float", "default": 2, "values": [1, 2, 3], "suffix": "x", "title": "Mult"},
        {"key": "demo.n", "type": "int", "default": 3, "min": 1, "max": 5, "step": 1, "title": "Count"},
        {"option": "demokey"}]}


def test_a_matching_block_passes(tmp_path, monkeypatch):
    mod = fake_mod(tmp_path, monkeypatch, CODE)
    assert errors(mod, good()) == []


def test_the_code_decides_type_and_default(tmp_path, monkeypatch):
    mod = fake_mod(tmp_path, monkeypatch, CODE)
    cfg = good()
    cfg["settings"][0]["default"] = 3
    cfg["settings"][1]["type"] = "float"
    got = errors(mod, cfg)
    assert any("declared default 3, the code reads it with 2.0" in e for e in got), got
    assert any("declared float, read as GetInt" in e for e in got), got


def test_the_toggle_must_default_on(tmp_path, monkeypatch):
    mod = fake_mod(tmp_path, monkeypatch, CODE.replace('"demo.enabled", true', '"demo.enabled", false'))
    assert any("want GetBool(..., true)" in e for e in errors(mod, good()))


def test_no_toggle_needs_a_reason(tmp_path, monkeypatch):
    mod = fake_mod(tmp_path, monkeypatch, CODE)
    cfg = good()
    cfg["toggle"] = None
    assert any("always_on" in e for e in errors(mod, cfg))
    cfg["always_on"] = "Data only."
    assert errors(mod, cfg) == []


def test_choices_hold_the_default_and_a_label_each(tmp_path, monkeypatch):
    mod = fake_mod(tmp_path, monkeypatch, CODE)
    cfg = good()
    cfg["settings"][0]["values"] = [1, 3]
    cfg["settings"][0]["labels"] = ["One"]
    got = errors(mod, cfg)
    assert any("not one of the values" in e for e in got), got
    assert any("one label per value" in e for e in got), got


def test_an_option_must_be_registered(tmp_path, monkeypatch):
    mod = fake_mod(tmp_path, monkeypatch, CODE)
    cfg = good()
    cfg["settings"][2]["option"] = "nokey"
    assert any('Register("nokey"' in e for e in errors(mod, cfg))


def test_the_generated_files_are_current():
    assert make_config.main(["--check"]) == 0
