"""Pins for mods/partyframes and HWP::AllyStatus: source facts the game can't check in CI."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLY = (ROOT / "mods/hwplib/scripts/HWP/Core/AllyStatus.as").read_text(encoding="utf-8")
FRAMES = (ROOT / "mods/partyframes/scripts/HWP/PartyFrames/PartyFrames.as").read_text(encoding="utf-8")
SUPPORT = (ROOT / "mods/specs/scripts/HWP/Specs/Support.as").read_text(encoding="utf-8")
ARCANE = (ROOT / "mods/specs/scripts/HWP/Specs/Arcane.as").read_text(encoding="utf-8")


def test_ally_status_api_stays_put():
    for signature in ("void ReportShield(float fraction)", "bool HasReport(PlayerRecord@ record)",
                      "float Shield(PlayerRecord@ record)", "int PotionsMax(PlayerRecord@ record)",
                      "int PotionsLeft(PlayerRecord@ record)"):
        assert signature in ALLY


def test_ally_status_registers_itself_not_through_core():
    assert "class HWPAllyStatusModule : Module" in ALLY
    core = (ROOT / "mods/hwplib/scripts/HWP/Core/CoreModule.as").read_text(encoding="utf-8")
    assert "AllyStatus" not in core


def test_support_reports_before_the_shared_spree_return():
    body = SUPPORT[SUPPORT.index("void UpdateSupport(int ms)"):]
    assert body.index("ReportShield(p);") < body.index("if (!g_sharedSpree) return;")


def test_clearing_support_reports_zero():
    body = SUPPORT[SUPPORT.index("void ClearSupport()"):SUPPORT.index("void UpdateSupport(int ms)")]
    assert "HWP::AllyStatus::ReportShield(0);" in body


def test_shield_fraction_uses_the_pool_living_mana_keeps_hp_on():
    assert "Learned(p, LIVING_MANA) ? p.m_record.MaxMana() : p.GetMaxHp()" in SUPPORT


def test_living_mana_literal_matches_the_skill():
    literal = re.search(r'LIVING_MANA = HashString\("([^"]+)"\)', ARCANE).group(1)
    assert f'HashString("{literal}")' in FRAMES


def test_frames_keep_vanilla_update_and_stay_a_subclass():
    assert "class HWPPartyFramesHUD : HUDCoop" in FRAMES
    assert "HUDCoop::Draw(sb, idt);" in FRAMES
    hud = FRAMES[FRAMES.index("class HWPPartyFramesHUD"):FRAMES.index("namespace HWPPartyFrames")]
    assert "void Update(" not in hud and "void Refresh(" not in hud


def test_defaults_are_thick_leading_edge_in_a_local_scope_package():
    config = json.loads((ROOT / "mods/partyframes/module.json").read_text(encoding="utf-8"))["config"]
    assert config["scope"] == "local" and config["applies"] == "now"
    settings = {s["key"]: s for s in config["settings"]}
    assert {k: s["labels"][s["default"]] for k, s in settings.items() if "labels" in s} == {
        "partyframes.size": "Thick", "partyframes.shield": "Leading edge"}
    assert {k: s["default"] for k, s in settings.items() if s["type"] == "bool"} == {
        "partyframes.level": False, "partyframes.class": False}
    packages = json.loads((ROOT / "packages.json").read_text(encoding="utf-8"))["packages"]
    assert [p["mods"] for p in packages if p["id"] == "interface"] == [["partyframes"]]


def test_stripe_art_matches_the_bar_heights():
    png = (ROOT / "mods/partyframes/gui/hwp_partyframes_stripes.png").read_bytes()
    assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == (128, 64)


def test_a_living_mana_ally_is_one_solid_blue_pool():
    frames = (ROOT / "mods/partyframes/scripts/HWP/PartyFrames/PartyFrames.as").read_text(encoding="utf-8")
    assert "return f.pool ? HWP::PartyFrames::Rgb(40, 130, 235) : f.color;" in frames
    assert frames.count("f.pool ? h - 2 :") == 2  # the bar takes the whole block on both sizes
    assert frames.count("if (!f.pool)") == 2      # and neither size draws the strip


def test_the_frames_start_below_the_tutorial_panel():
    draw = FRAMES[FRAMES.index("int top = max(HWP::PartyFrames::Y"):]
    assert "TutorialBottom() + HWP::PartyFrames::GAP" in draw
    assert "top + int(count) * rowH >" in draw      # the auto-thin counts the slide
    assert "int y = top + int(i) * rowH;" in draw


def test_the_options_list_has_no_spacing_so_its_scroll_reaches_the_last_row():
    # ScrollbarWidget::DoLayout leaves spacing out of the height it scrolls over
    gui = (ROOT / "mods/hwplib/gui/hwp/options.gui").read_text(encoding="utf-8")
    rows = next(line for line in gui.splitlines() if 'id="rows"' in line)
    assert "spacing" not in rows

