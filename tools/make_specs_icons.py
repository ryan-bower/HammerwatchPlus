"""Packs the 4th specializations' icon sheet, mods/specs/players/hwp/specs/icons.png (256x256, a power of two: the texture loader rejects 256x144).

python tools/make_specs_icons.py [--check]

One 24 px row per spec (SPECS order in tools/make_specs_classes.py): col 0 the class icon,
col 1 the active, col 2 the passive, cols 3-5 the active's orbs, cols 6-7 the passive's orbs,
and the 14x14 HUD icons at x 192, 208, 224 (y = the row's top). A fourth orb on the active
goes in col 9 (x 216, clear of the HUD icons): the Wizard's Lightning Rod. The cells are what the svals
reference (mods/specs/players/hwp/specs/<spec>/*.sval, buffs_specs.sval, stacks_specs.sval).

Each icon is art/specs/override/<name>.png when it exists (the art requests in
art/specs/REQUESTS.md, painted by tools/icon_art/sp.py --pick), else a placeholder: a vanilla
skill icon (players/icons_skills.png) tinted in the spec's colour, so the game never shows an
empty cell. --check exits 1 when the sheet on disk is stale."""
import io
import sys
from pathlib import Path
from PIL import Image, ImageEnhance

REPO = Path(__file__).resolve().parents[1]
VANILLA = REPO / "gamecode/sdk/hoh2/players/icons_skills.png"
OVERRIDE = REPO / "art/specs/override"
OUT = REPO / "mods/specs/players/hwp/specs/icons.png"

# spec row: tint, then (name, column or hud x, vanilla cell (x, y) for the placeholder)
ROWS = [
    ((90, 170, 255), [("ran_class", 0, (168, 48)), ("ran_electric_circuit", 1, (144, 48)),
                      ("ran_gathering_winds", 2, (168, 48)), ("ran_ec_boomerang", 3, (144, 48)),
                      ("ran_ec_lightning_rod", 4, (144, 48)), ("ran_ec_tailwind_catch", 5, (144, 48)),
                      ("ran_gw_gale_force", 6, (168, 48)), ("ran_gw_wind_ward", 7, (168, 48)),
                      ("hud_tailwind", 192, (168, 48))]),
    ((110, 150, 255), [("wiz_class", 0, (144, 168)), ("wiz_tempest_torrent", 1, (144, 168)),
                       ("wiz_static_charge", 2, (0, 216)), ("wiz_tt_overcharge", 3, (144, 168)),
                       ("wiz_tt_lingering_storm", 4, (144, 168)), ("wiz_tt_thunderclap", 5, (144, 168)),
                       ("wiz_sc_static_channel", 6, (0, 216)), ("wiz_sc_conduit", 7, (0, 216)),
                       ("hud_static_charge", 192, (0, 216)), ("wiz_tt_lightning_rod", 9, (144, 168))]),
    ((190, 110, 255), [("sor_class", 0, (24, 216)), ("sor_blink", 1, (0, 192)),
                       ("sor_living_mana", 2, (24, 216)), ("sor_bl_void_barrier", 3, (0, 192)),
                       ("sor_bl_far_step", 4, (0, 192)), ("sor_lm_arcane_feedback", 6, (24, 216)),
                       ("sor_lm_mana_conduit", 7, (24, 216)), ("hud_void_barrier", 192, (72, 192)),
                       ("hud_arcane_feedback", 208, (24, 216))]),
    ((140, 240, 190), [("rog_class", 0, (72, 120)), ("rog_protective_gale", 1, (72, 120)),
                       ("rog_second_wind", 2, (72, 120)), ("rog_pg_lasting_gale", 3, (72, 120)),
                       ("rog_pg_tailwind", 4, (72, 120)), ("rog_sw_lingering_breeze", 6, (72, 120)),
                       ("rog_sw_shared_breath", 7, (72, 120)), ("hud_protective_gale", 192, (72, 120)),
                       ("hud_lingering_breeze", 208, (72, 120))]),
    ((255, 120, 90), [("war_class", 0, (72, 336)), ("war_battlefield_standard", 1, (144, 384)),
                      ("war_righteous_crusade", 2, (144, 384)), ("war_bs_feared_crest", 3, (144, 384)),
                      ("war_bs_martyrs_banner", 4, (144, 384)), ("war_rc_war_drum", 6, (72, 336)),
                      ("war_rc_shared_provisions", 7, (192, 24)), ("hud_standard_raised", 192, (144, 384)),
                      ("hud_standard_planted", 208, (144, 384)), ("hud_shared_provisions", 224, (192, 24))]),
    ((255, 110, 60), [("wlk_class", 0, (24, 168)), ("wlk_pyrebrand", 1, (0, 144)),
                      ("wlk_essence_extraction", 2, (24, 168)), ("wlk_pb_combustion", 3, (0, 144)),
                      ("wlk_pb_proliferation", 4, (0, 144)), ("wlk_ee_essence_empowerment", 6, (24, 168)),
                      ("wlk_ee_released_essence", 7, (24, 168)), ("hud_pyrebrand", 192, (0, 144))]),
    ((120, 220, 110), [("pri_class", 0, (48, 240)), ("pri_necrotic_resurrection", 1, (48, 240)),
                       ("pri_call_of_heresy", 2, (48, 240)), ("pri_deeper_depravity", 3, (48, 240)),
                       ("pri_pyre_sacrifice", 4, (48, 240)), ("pri_sacrificial_penance", 5, (48, 240)),
                       ("pri_ravenous_lunge", 6, (48, 240)), ("pri_rot_bloom", 7, (48, 240)),
                       ("hud_heresy", 192, (48, 240)), ("hud_heresy_5", 208, (48, 240)),
                       ("hud_devouring", 224, (48, 240))]),
]


def placeholder(src, cell, tint, size):
    im = src.crop((cell[0], cell[1], cell[0] + 24, cell[1] + 24)).convert("RGBA")
    grey = ImageEnhance.Color(im).enhance(0.0)
    r, g, b, a = grey.split()
    tinted = Image.merge("RGBA", (r.point(lambda v: v * tint[0] // 255), g.point(lambda v: v * tint[1] // 255),
                                  b.point(lambda v: v * tint[2] // 255), a))
    out = Image.blend(im, tinted, 0.7)
    return out if size == 24 else out.resize((size, size), Image.LANCZOS)


def build():
    src = Image.open(VANILLA).convert("RGBA")
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    used = []
    for row, (tint, icons) in enumerate(ROWS):
        y = row * 24
        for name, col, cell in icons:
            hud = name.startswith("hud_")
            size = 14 if hud else 24
            x = col if hud else col * 24
            ov = OVERRIDE / f"{name}.png"
            if ov.exists():
                im = Image.open(ov).convert("RGBA")
                if im.size != (size, size):
                    sys.exit(f"{ov}: {im.size}, want {size}x{size}")
                used.append(name)
            else:
                im = placeholder(src, cell, tint, size)
            sheet.paste(im, (x, y))
    buf = io.BytesIO()
    sheet.save(buf, "PNG", optimize=True)
    return buf.getvalue(), used


def main():
    data, used = build()
    if "--check" in sys.argv:
        if not OUT.exists() or Image.open(OUT).tobytes() != Image.open(io.BytesIO(data)).tobytes():
            print("stale:", OUT.relative_to(REPO)); sys.exit(1)
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    print("wrote", OUT.relative_to(REPO), f"({len(used)} painted, the rest placeholders)")


if __name__ == "__main__":
    main()
