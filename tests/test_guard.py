"""HWP::Guard coverage (tools/guard_modules.py, mods/hwplib/scripts/HWP/Core/Guard.as)."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import guard_modules  # noqa: E402

SAMPLE = (
    "namespace Modules\n"
    "{\n"
    "\tclass HWPSampleModule : Module, HWP::ModuleStart\n"
    "\t{\n"
    "\t\tHWPSampleModule() { super(\"hwp-sample\"); }\n"
    "\n"
    "\t\tvoid UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override\n"
    "\t\t{\n"
    "\t\t\tTick(ms);\n"
    "\t\t}\n"
    "\n"
    "\t\tvoid RenderFrame(int idt, SpriteBatch& sb)\n"
    "\t\t{\n"
    "\t\t\tDraw(sb);\n"
    "\t\t}\n"
    "\t}\n"
    "\n"
    "\tclass NotAModule : Widget\n"
    "\t{\n"
    "\t\tvoid UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) {}\n"
    "\t}\n"
    "}\n"
)


def test_every_module_entry_point_is_guarded():
    assert guard_modules.missing() == [], "run python tools/guard_modules.py"


def test_wrapping_renames_the_body_and_adds_the_guard():
    out, done = guard_modules.guard_text("sample", SAMPLE)
    assert done == ["HWPSampleModule.RenderFrame", "HWPSampleModule.UpdateFrame"]
    assert "void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)\n\t\t{\n\t\t\tTick(ms);" in out
    assert "try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }" in out
    assert 'm_guardRenderFrame.Skip("sample", "HWPSampleModule.RenderFrame")' in out
    assert "void RenderFrame(int idt, SpriteBatch& sb) override" in out
    # a class that is not a module is left alone, and a second pass changes nothing
    assert out.count("void UpdateFrame(") == 2
    assert guard_modules.guard_text("sample", out) == (out, [])


def test_wrapping_keeps_crlf():
    out, done = guard_modules.guard_text("sample", SAMPLE.replace("\n", "\r\n"))
    assert len(done) == 2
    assert "\n" not in out.replace("\r\n", "")


def test_tested_build_matches_the_gamelab_pin():
    pin = json.loads((REPO / "gamelab" / "build_id.json").read_text(encoding="utf-8"))
    log_as = (REPO / "mods/hwplib/scripts/HWP/Core/Log.as").read_text(encoding="utf-8")
    tested = re.search(r"const int TESTED_BUILD = (\d+);", log_as)
    assert tested and pin["game_version"] == f"Build {tested.group(1)}"
