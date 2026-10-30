"""Packs bufftips' buff-bar icons for vanilla's class skill buffs and writes the table the module reads.

python tools/make_bufftips_icons.py [--check]

Vanilla gives most class skill buffs no "hud" sprite (War Cry, issue #28), so they never reach the
HUD's buff bar. bufftips gives each of the buffs below a 14x14 icon at runtime. Each icon is the
middle 14x14 of the skill's own 24x24 icon (players/icons_skills.png, players/icons_combo.png),
cut rather than scaled, so the pixel art stays sharp. Two buffs from one skill get a tint to tell
them apart.

Writes:
  mods/bufftips/gui/hwp/bufftips/icons.png    256x16, icon i at x = 16 * i, y = 0
  mods/bufftips/scripts/HWP/BuffTips/SkillBuffs.as    the buff paths, icon x, name and
      description keys (the name and description are only used when the def has none)

The description keys are in mods/bufftips/res/language/english/hwp_bufftips.lang.
--check exits 1 when either file on disk is stale."""
import io
import sys
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "gamecode/sdk/hoh2/players/icons_skills.png"
COMBO = REPO / "gamecode/sdk/hoh2/players/icons_combo.png"
OUT_PNG = REPO / "mods/bufftips/gui/hwp/bufftips/icons.png"
OUT_AS = REPO / "mods/bufftips/scripts/HWP/BuffTips/SkillBuffs.as"
SHEET = "gui/hwp/bufftips/icons.png"

# id, icon sheet, the skill icon's cell (x, y), tint or None, buff paths, name key, description key
BUFFS = [
    ("warcry", SKILLS, (72, 336), None,
     ["players/warrior/buffs_warrior.sval:warcry_%d" % i for i in range(1, 6)],
     ".skills.warrior.spell_2.name", ".hwp.bufftips.skill.warcry.desc"),
    ("fuel_the_flames", SKILLS, (24, 24), None,
     ["players/paladin/buffs_paladin.sval:fuel_the_flames_%d" % i for i in range(1, 3)],
     ".skills.paladin.mastery_3.spell_1.up1.name", ".hwp.bufftips.skill.fuel_the_flames.desc"),
    ("invigorating", SKILLS, (0, 24), None,
     ["players/paladin/buffs_paladin.sval:invigorating_%d" % i for i in range(1, 4)],
     ".skills.paladin.spell_2.up1.name", ".hwp.bufftips.skill.invigorating.desc"),
    ("cleansing_touch", SKILLS, (0, 24), (200, 230, 255),
     ["players/paladin/buffs_paladin.sval:cleansing_touch"],
     ".skills.paladin.spell_2.up2.name", ".hwp.bufftips.skill.cleansing_touch.desc"),
    ("holy_flames", SKILLS, (72, 384), None,
     ["players/priest/buffs_priest.sval:holy_flames_%d" % i for i in range(1, 3)],
     ".skills.priest.passive_2.up1.name", ".hwp.bufftips.skill.holy_flames.desc"),
    ("entangle_heal", SKILLS, (120, 72), None,
     ["players/ranger/buffs_ranger.sval:entangle_heal_%d" % i for i in range(1, 4)],
     ".skills.ranger.mastery_3.spell_1.up1.name", ".hwp.bufftips.skill.entangle_heal.desc"),
    ("marked_pursuit", SKILLS, (144, 48), None,
     ["players/ranger/buffs_ranger.sval:marked_pursuit_%d" % i for i in range(1, 4)],
     ".skills.ranger.spell_1.up1.name", ".hwp.bufftips.skill.marked_pursuit.desc"),
    ("sidestep_opening", SKILLS, (72, 120), None,
     ["players/rogue/buffs_rogue.sval:sidestep_opening_%d" % i for i in range(1, 4)],
     ".skills.rogue.passive_2.up2.name", ".hwp.bufftips.skill.sidestep_opening.desc"),
    ("flamewalker", SKILLS, (120, 240), None,
     ["players/sorcerer/buffs_sorcerer.sval:flamewalker_%d" % i for i in range(1, 4)],
     ".skills.sorcerer.mastery_1.spell_1.up1.name", ".hwp.bufftips.skill.flamewalker.desc"),
    ("powersurge", SKILLS, (24, 216), None,
     ["players/sorcerer/buffs_sorcerer.sval:powersurge_%d" % i for i in range(1, 4)],
     ".skills.sorcerer.passive_2.up2.name", ".hwp.bufftips.skill.powersurge.desc"),
    ("combo_speed", COMBO, (0, 48), None, ["tweak/buffs/buffs_combo.sval:speed"],
     ".skills.combo.combo_bursting_speed.name", ".hwp.bufftips.skill.combo_speed.desc"),
    ("combo_damage", COMBO, (96, 120), None, ["tweak/buffs/buffs_combo.sval:damage"],
     ".skills.combo.combo_bursting_dmg.name", ".hwp.bufftips.skill.combo_damage.desc"),
    ("combo_protection", COMBO, (72, 48), None, ["tweak/buffs/buffs_combo.sval:protection"],
     ".skills.combo.combo_bursting_prot.name", ".hwp.bufftips.skill.combo_protection.desc"),
]


def icon(sheet, cell, tint):
    x, y = cell
    im = sheet.crop((x + 5, y + 5, x + 19, y + 19))
    if tint is None:
        return im
    r, g, b, a = im.split()
    lit = Image.merge("RGBA", (r.point(lambda v: (v + tint[0]) // 2), g.point(lambda v: (v + tint[1]) // 2),
                               b.point(lambda v: (v + tint[2]) // 2), a))
    return Image.blend(im, lit, 0.6)


def build_png():
    sheets = {}
    out = Image.new("RGBA", (256, 16), (0, 0, 0, 0))
    for i, (_, path, cell, tint, _, _, _) in enumerate(BUFFS):
        if path not in sheets:
            sheets[path] = Image.open(path).convert("RGBA")
        out.paste(icon(sheets[path], cell, tint), (16 * i, 0))
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def build_as():
    paths, xs, names, descs = [], [], [], []
    for i, (_, _, _, _, buffs, name, desc) in enumerate(BUFFS):
        for p in buffs:
            paths.append('"%s"' % p)
            xs.append(str(16 * i))
            names.append('"%s"' % name)
            descs.append('"%s"' % desc)
    def arr(items, per):
        rows = [", ".join(items[j:j + per]) for j in range(0, len(items), per)]
        return "\n\t\t\t" + ",\n\t\t\t".join(rows) + "\n\t\t"
    lines = [
        "// Generated by tools/make_bufftips_icons.py; do not edit.",
        "// Vanilla class skill buffs that have no \"hud\" icon (issue #28): each one's icon cell on",
        "// " + SHEET + " (x; y 0, 14x14) and the name and description keys it gets",
        "// when its def has none.",
        "namespace HWP",
        "{",
        "\tnamespace BuffTips",
        "\t{",
        "\t\tconst string SKILL_ICONS = \"%s\";" % SHEET,
        "\t\tconst array<string> SKILL_BUFFS = {%s};" % arr(paths, 1),
        "\t\tconst array<int> SKILL_BUFF_ICON_X = {%s};" % arr(xs, 16),
        "\t\tconst array<string> SKILL_BUFF_NAMES = {%s};" % arr(names, 1),
        "\t\tconst array<string> SKILL_BUFF_DESCS = {%s};" % arr(descs, 1),
        "\t}",
        "}",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def main():
    png, src = build_png(), build_as()
    if "--check" in sys.argv:
        bad = []
        if not OUT_PNG.exists() or Image.open(OUT_PNG).tobytes() != Image.open(io.BytesIO(png)).tobytes():
            bad.append("stale: " + OUT_PNG.relative_to(REPO).as_posix())
        if not OUT_AS.exists() or OUT_AS.read_bytes() != src:
            bad.append("stale: " + OUT_AS.relative_to(REPO).as_posix())
        for line in bad:
            print(line)
        if bad:
            sys.exit(1)
        print("bufftips icons: OK")
        return
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    OUT_PNG.write_bytes(png)
    OUT_AS.write_bytes(src)
    print("wrote %s (%d icons) and %s (%d buffs)" % (OUT_PNG.relative_to(REPO).as_posix(), len(BUFFS),
                                                     OUT_AS.relative_to(REPO).as_posix(),
                                                     sum(len(b[4]) for b in BUFFS)))


if __name__ == "__main__":
    main()
