"""make_hwp_traps.py - the HoH1 trap kinds of the campaign module (issue #37).

HoH1's traps are a few families of unit that its level scripts switch on and off: floor
plates (spikes, poison, mana drain, frost, confusion), pressure spikes, glyphs, wall
shooters (arrows, poison arrows, fire balls, blades), turrets, falling stalactites and
bricks, bear traps. On HoH2's generated floors one script behaviour, HWPTrap
(mods/campaign/scripts/HWP/Campaign/TrapBehavior.as), is the level script, and every kind
is a unit file of it on HoH2 art. They differ only in numbers and scene lists, so this
script writes them, one prefab per placement (prefabs/hwp/traps/), and their entries in the
hwp_traps prefab set (the generated block of tweak/hwp/campaign_prefabs.sval). Which kinds a
floor gets, and how often, is the theme table in scripts/HWP/Campaign/Traps.as.

Every trap telegraphs before it hurts (issue #38): a plate shows HoH2's red area warning
for a second, a glyph lights up with it, a dropper's shadow grows while it falls.

    python tools/make_hwp_traps.py          # (re)write the units, prefabs and the set block
    python tools/make_hwp_traps.py --check  # exit 1 when a file is stale or missing
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOD = REPO / "mods" / "campaign"
UNITS = "doodads/hwp/traps"
PREFABS = "prefabs/hwp/traps"
DEFS = MOD / "tweak" / "hwp" / "campaign_prefabs.sval"
BEGIN = "\t<!-- BEGIN make_hwp_traps.py: generated, do not edit by hand -->\n"
END = "\t<!-- END make_hwp_traps.py -->\n"
BUFFS = "tweak/hwp/campaign_buffs.sval"
STATUS = "tweak/buffs/status_effects.sval"

SPIKES = "doodads/traps/floors/floor_spikes.unit"
PRESSURE = "doodads/traps/floors/floor_spikes_pressure.unit"
CURSE = "doodads/traps/floors/floor_curse.unit"
WARN = "effects/generic/other/area_warning_xray_{ms}.effect?radius={r}"
TILE = ('<sprite origin="16 16" texture="doodads/traps/floors/trap_curse.png" material="system/default.mats:floor">'
        '<frame>0 32 32 32</frame></sprite>')
MINIMAP_ON = '<scene src="special/minimap.unit:trap_spikes_on"/>'
MINIMAP_OFF = '<scene src="special/minimap.unit:trap_spikes_off"/>'
SPIKE_SOUNDS = {
    "sound-loop": "event:/sfx/doodads/traps/floor_spikes/floor_spikes_loop",
    "sound-loop-start-snd": "event:/sfx/doodads/traps/floor_spikes/floor_spikes_start",
    "sound-loop-stop-snd": "event:/sfx/doodads/traps/floor_spikes/floor_spikes_stop",
    "sound-on-scene": "on",
}


# --- effects -------------------------------------------------------------------------
def dmg(elem, n, true_strike=False):
    ts = '<bool name="true-strike">true</bool>' if true_strike else ""
    return f'<dict><string name="class">Damage</string><int name="{elem}">{n}</int>{ts}</dict>'


def hp(elem, f, true_strike=False):
    ts = '<bool name="true-strike">true</bool>' if true_strike else ""
    return (f'<dict><string name="class">HPBasedDamage</string><float name="{elem}">{f}</float>'
            f'<bool name="curr-hp">true</bool>{ts}</dict>')


def buff(path):
    return f'<dict><string name="class">ApplyBuff</string><string name="buff">{path}</string></dict>'


def mana(f):
    return (f'<dict><string name="class">GivePercentageMana</string><float name="mana">{f}</float>'
            '<bool name="curr-mana">false</bool></dict>')


def fx(path):
    return f'<effect src="{path}"/>'


def inc(src):
    return f'<scene src="{src}"/>'


# --- the kinds -----------------------------------------------------------------------
# name: (comment, behaviour params, effects, {scene: [xml...]}, layer)
def plate(off, warn, on, freq=500):
    return {"trigger": "timer", "off": off, "warn": warn, "on": on, "freq": freq, "radius": 14, "actor-filter": 6}


def kinds():
    k = {}
    warn14 = fx(WARN.format(ms=1000, r=14))
    k["hwp_plate_spikes"] = (
        "HoH1's spike plate: HoH2's floor spikes on a cycle (2.5 s down, 1 s red warning, 1.5 s up), "
        "25 physical + 10% of current health every 0.5 s while up (HoH2's spike numbers)",
        {**plate(2500, 1000, 1500), **SPIKE_SOUNDS},
        [dmg("physical", 25, True), hp("physical", 0.1, True)],
        {"off": [inc(SPIKES + ":off")], "warn": [inc(SPIKES + ":inactive"), warn14], "on": [inc(SPIKES + ":on")]},
        -20)
    k["hwp_pressure_spikes"] = (
        "HoH1's pressure spikes: stepping on the plate clicks, half a second later the spikes "
        "come up for 1.2 s (20% of current health every 0.5 s); 1.5 s to re-arm",
        {"trigger": "near", "sense": 12, "warn": 500, "on": 1200, "rearm": 1500, "freq": 500, "radius": 14,
         "actor-filter": 6, "warn-snd": "event:/sfx/character/classes/rogue/pressure_trap_trigger", **SPIKE_SOUNDS},
        [dmg("physical", 15, True), hp("physical", 0.2, True)],
        {"off": [inc(PRESSURE + ":off")], "warn": [inc(PRESSURE + ":off"), fx(WARN.format(ms=500, r=14))],
         "on": [inc(PRESSURE + ":on")]},
        -20)
    k["hwp_plate_poison"] = (
        "HoH1's poison plate (poison_strong): while it bubbles, 8 poison every 0.5 s and 4 s of "
        "poison (16 a second, 70% speed: hwp_trap_poison)",
        plate(3000, 1000, 2000),
        [dmg("poison", 8), buff(f"{BUFFS}:hwp_trap_poison")],
        {"off": [TILE, MINIMAP_OFF], "warn": [TILE, MINIMAP_OFF, warn14],
         "on": [TILE, MINIMAP_ON, fx("effects/generic/areas/poison_area_ground_green_1.effect?radius=16")]},
        -20)
    k["hwp_plate_drain"] = (
        "HoH1's drain plate (drain_strong): HoH2's curse floor; while active it takes 5% of "
        "maximum mana every 0.5 s and darkens the view for 2.5 s (hwp_trap_darkness)",
        plate(3000, 1000, 2000),
        [mana(-0.05), buff(f"{BUFFS}:hwp_trap_darkness")],
        {"off": [inc(CURSE + ":off")], "warn": [inc(CURSE + ":inactive"), warn14], "on": [inc(CURSE + ":on")]},
        -20)
    k["hwp_plate_frost"] = (
        "HoH1's frost plate (freezing_short): while it is iced over, 6 ice and HoH2's area slow "
        "(70% speed) every 0.25 s",
        plate(3000, 1000, 2000, freq=250),
        [dmg("ice", 6), buff(f"{STATUS}:slow_area")],
        {"off": [TILE, MINIMAP_OFF], "warn": [TILE, MINIMAP_OFF, warn14],
         "on": [TILE, MINIMAP_ON, fx("effects/generic/areas/ice_area_ground_1.effect?radius=16")]},
        -20)
    k["hwp_plate_confusion"] = (
        "HoH1's confusion plate (trap_confusion): while the rune glows, 1 s of confusion "
        "(hwp_trap_confusion: movement and aim reversed), renewed every 0.5 s",
        {**plate(3500, 1000, 1500), "setting": "campaign.confusion"},
        [buff(f"{BUFFS}:hwp_trap_confusion")],
        {"off": [TILE, MINIMAP_OFF], "warn": [TILE, MINIMAP_OFF, warn14],
         "on": [TILE, MINIMAP_ON, fx("effects/generic/other/arcane/glyph_active.effect")]},
        -20)
    k["hwp_glyph_frost"] = (
        "HoH1's frost glyph: a player within 20 px lights it, a second later it bursts (32 px: "
        "20 ice + 10% of current health, frozen 1 s); back after 6 s",
        {"trigger": "near", "sense": 20, "warn": 1000, "on": 300, "rearm": 6000, "once": True, "radius": 32,
         "freq": 0, "actor-filter": 6, "warn-snd": "event:/sfx/player/classes/ranger/trap/trap_set_pre",
         "on-snd": "event:/sfx/doodads/traps/magic_ball/magic_ball_ice_hit",
         "on-fx": "effects/generic/explosions/ice_explosion_2.effect?radius=32"},
        [dmg("ice", 20), hp("ice", 0.1), buff(f"{STATUS}:freeze_minor")],
        {"off": [fx("effects/generic/other/arcane/glyph_idle.effect")],
         "warn": [fx("effects/generic/other/arcane/glyph_ice.effect"), fx(WARN.format(ms=1000, r=32))],
         "on": [fx("effects/generic/other/arcane/glyph_ice.effect")]},
        0)
    # issue #38: the confusion and dart glyphs were TripMines, hidden until a player was 40 px
    # away and firing 0.15-0.2 s after one came within 20 px, too fast to step off; a TripMine
    # put back under a player who stood on it never fired again (no overlap begins). Now they
    # show all the time, light up with the red warning for a second, then fire, and re-arm in
    # place
    glyph_warn_snd = "event:/sfx/doodads/buttons/button_magic"
    k["hwp_glyph_confusion"] = (
        "HoH1's confusion glyph: a player within 20 px lights it, a second later it bursts and "
        "everyone in 40 px is confused for 1 s (hwp_trap_confusion: movement and aim reversed); "
        "back after 6 s",
        {"trigger": "near", "sense": 20, "warn": 1000, "on": 300, "rearm": 6000, "once": True, "radius": 40,
         "freq": 0, "actor-filter": 6, "warn-snd": glyph_warn_snd, "setting": "campaign.confusion",
         "on-fx": "effects/generic/explosions/arcane_explosion_1.effect"},
        [buff(f"{BUFFS}:hwp_trap_confusion")],
        {"off": [fx("effects/generic/other/arcane/glyph_idle.effect")],
         "warn": [fx("effects/generic/other/arcane/glyph_active.effect"), fx(WARN.format(ms=1000, r=40))],
         "on": [fx("effects/generic/other/arcane/glyph_active.effect")]},
        0)
    # the ring starts 12 px out with one arrow aimed at the nearest player, and a player
    # standing on the glyph gets one stab instead: from the middle, all 8 arrows overlapped a
    # player on it and hit (160 -> 22 health in one go)
    k["hwp_glyph_dart"] = (
        "HoH1's dart trap: a player within 20 px lights the glyph, a second later a ring of 8 "
        "trap arrows (HoH2's arrow.unit) flies out of it, one at the nearest player, and a "
        "player on it is stabbed once (an arrow's 20 physical + 20% of current health); back after 5 s",
        {"trigger": "near", "sense": 20, "warn": 1000, "on": 300, "rearm": 5000, "once": True, "freq": 0,
         "radius": 8, "actor-filter": 6, "warn-snd": glyph_warn_snd,
         "shoot": "doodads/traps/projectiles/arrow.unit", "shots": 8, "arc": 315, "aim": True, "muzzle": 12},
        [dmg("physical", 20), hp("physical", 0.2)],
        {"off": [fx("effects/generic/other/arcane/glyph_idle.effect")],
         "warn": [fx("effects/generic/other/arcane/glyph_active.effect"), fx(WARN.format(ms=1000, r=24))],
         "on": [fx("effects/generic/other/arcane/glyph_active.effect")]},
        0)
    k["hwp_dropper_stalactite"] = (
        "HoH1's stalactites: a player within 20 px shakes one loose; its shadow grows while it "
        "falls (0.9 s) and the impact hits 18 px (20 physical + 20% of current health); another "
        "hangs there 5 s later",
        {"trigger": "near", "sense": 20, "warn": 900, "on": 200, "rearm": 5000, "once": True, "radius": 18,
         "freq": 0, "actor-filter": 6, "warn-snd": "event:/sfx/doodads/traps/boulder/boulder_fall",
         "on-snd": "event:/sfx/doodads/traps/boulder/boulder_impact",
         "on-fx": "effects/generic/impacts/stalactite_impact.effect"},
        [dmg("physical", 20, True), hp("physical", 0.2, True)],
        {"off": [], "warn": [fx("actors/bosses/bone_serpent/effects/trap_falling_stalactite_shadow_small.effect"),
                             fx("effects/generic/other/environment/stalactite.effect")],
         "on": []},
        0)
    k["hwp_crusher_bricks"] = (
        "HoH1's crushing ceiling: a player within 40 px brings dust down and the red warning "
        "for 1 s, then the bricks hit 16 px (30 physical + 20% of current health); 3 s to re-arm",
        {"trigger": "near", "sense": 40, "warn": 1000, "on": 300, "rearm": 3000, "once": True, "radius": 16,
         "freq": 0, "actor-filter": 6, "on-snd": "event:/sfx/doodads/traps/boulder/boulder_impact",
         "on-fx": "effects/generic/impacts/stalactite_impact.effect"},
        [dmg("physical", 30, True), hp("physical", 0.2, True)],
        {"off": [], "warn": [fx("actors/bosses/bone_serpent/effects/environment/falling_bricks_hint.effect"),
                             fx(WARN.format(ms=1000, r=16))],
         "on": []},
        0)
    k["hwp_bear_trap"] = (
        "HoH1's bear traps (the Warden's): the ranger's trap art; it snaps on a player within "
        "10 px (30 physical, immobilized 2 s) and stays sprung",
        {"trigger": "near", "sense": 10, "warn": 0, "on": 500, "uses": 1, "once": True, "radius": 16,
         "freq": 0, "actor-filter": 6, "on-snd": "event:/sfx/player/classes/ranger/trap/trap_trigger"},
        [dmg("physical", 30, True), buff(f"{STATUS}:immobilize_minor")],
        {"off": [fx("players/ranger/units/bear_trap.effect")], "warn": [fx("players/ranger/units/bear_trap.effect")],
         "on": [fx("players/ranger/units/bear_trap_triggered.effect")], "spent": []},
        0)
    # wall shooters: (ammo unit, re-arm ms, shooter art)
    ammo = {
        "arrow": ("doodads/traps/projectiles/arrow.unit", 1500, "shooter_wall"),
        "poison": ("doodads/traps/projectiles/arrow_poison.unit", 2000, "shooter_wall"),
        "fire": ("doodads/traps/projectiles/magic_ball_fire.unit", 2500, "shooter_wall_big"),
        "blade": ("doodads/traps/projectiles/blade.unit", 2000, "shooter_wall_big"),
    }
    for name, (proj, rearm, art) in ammo.items():
        for face, deg, my in (("s", 90, 0), ("e", 0, -8), ("w", 180, -8)):
            k[f"hwp_shooter_{name}_{face}"] = (
                f"HoH1's {name} shooter on a wall, facing {face}: with a player within 200 px it fires "
                f"HoH2's trap projectile ({proj.split('/')[-1]}) every {rearm / 1000:g} s",
                {"trigger": "near", "sense": 200, "warn": 0, "on": 100, "rearm": rearm, "freq": 0, "radius": 1,
                 "shoot": proj, "dir": deg, "muzzle": 4, "muzzle-y": my},
                [],
                {"off": [inc(f"doodads/traps/shooters/{art}.unit:{face}")],
                 "on": [inc(f"doodads/traps/shooters/{art}.unit:{face}")]},
                0)
    turret = "doodads/traps/turrets/turret_arrows.unit"
    scenes = {}
    for face in "nesw":
        scenes[f"off_{face}"] = [inc(f"{turret}:{face}")]
        scenes[f"warn_{face}"] = [inc(f"{turret}:{face}"), fx("effects/generic/other/area_warning_xray_500.effect?radius=12")]
        scenes[f"on_{face}"] = [inc(f"{turret}:shoot_{face}")]
    # the turret's own collision reaches 16 px out (its barrel); an arrow (radius 3) started
    # touching it dies there: 26 px out, less the 6 px lift, clears the south barrel too
    k["hwp_turret_arrows"] = (
        "HoH1's arrow turret: HoH2's turret art; a player it can see within 220 px wakes it, half "
        "a second later it turns and fires a fan of 3 arrows (30 degrees) at them, every 2.5 s",
        {"trigger": "near", "sense": 220, "los": True, "aim": True, "facing": True, "warn": 500, "on": 200,
         "rearm": 2500, "freq": 0, "radius": 1, "shoot": "doodads/traps/projectiles/arrow.unit", "shots": 3,
         "arc": 30, "dir": 90, "muzzle": 26, "muzzle-y": -6},
        [],
        scenes,
        0)
    return k


def param_xml(key, v):
    if isinstance(v, bool):
        return f'<bool name="{key}">{"true" if v else "false"}</bool>'
    if isinstance(v, int):
        return f'<int name="{key}">{v}</int>'
    return f'<string name="{key}">{v}</string>'


def unit_xml(name, spec):
    about, params, effects, scenes, layer = spec
    out = [f"<!-- {about}.", f"     Generated by tools/make_hwp_traps.py (HWPTrap, scripts/HWP/Campaign/TrapBehavior.as). -->",
           f'<unit slot="doodad" layer="{layer}">', '\t<behavior class="HWPTrap">']
    out += [f"\t\t{param_xml(k, v)}" for k, v in params.items()]
    out.append('\t\t<array name="effects">')
    out += [f"\t\t\t{e}" for e in effects]
    out.append("\t\t</array>")
    out.append("\t</behavior>")
    out.append("\t<scenes>")
    for sname, parts in scenes.items():
        if not parts:
            out.append(f'\t\t<scene name="{sname}"/>')
            continue
        out.append(f'\t\t<scene name="{sname}">')
        out += [f"\t\t\t{p}" for p in parts]
        out.append("\t\t</scene>")
    out.append("\t</scenes>")
    out.append("</unit>")
    return "\n".join(out) + "\n"


# --- placements ----------------------------------------------------------------------
# prefab id (family_variant): (units [(unit path, x, y)], max-num, grid-pos, grid-size,
# pattern bytes, command bytes). Pattern 05 Wall, 07 Walkable; command 03 ReserveFloor,
# 00 Ignore. Units sit in cell pixels from the grid's top-left corner.
OPEN3 = ("070707070707070707", "000000000300000000")
FULL3 = ("070707070707070707", "030303030303030303")


def placements():
    p = {}

    def one(pid, unit, max_num, pattern=OPEN3):
        p[pid] = ([(unit, 8, 8)], max_num, (-1, -1), (3, 3), *pattern)

    one("plate_spikes_1", f"{UNITS}/hwp_plate_spikes.unit", 6)
    # three 32 px plates side by side along a 5x1 strip (each starts at its own point of the cycle)
    p["plate_spikes_row"] = ([(f"{UNITS}/hwp_plate_spikes.unit", 8 + 32 * i, 8) for i in range(3)], 2, (0, 0), (5, 1),
                             "07" * 5, "03" * 5)
    one("pressure_spikes_1", f"{UNITS}/hwp_pressure_spikes.unit", 4)
    one("plate_poison_1", f"{UNITS}/hwp_plate_poison.unit", 4)
    one("plate_drain_1", f"{UNITS}/hwp_plate_drain.unit", 3)
    one("plate_frost_1", f"{UNITS}/hwp_plate_frost.unit", 4)
    one("plate_confusion_1", f"{UNITS}/hwp_plate_confusion.unit", 3)
    one("glyph_frost_1", f"{UNITS}/hwp_glyph_frost.unit", 3)
    one("glyph_curse_1", "doodads/traps/mines/glyph_shadow.unit", 3)
    one("dropper_stalactite_1", f"{UNITS}/hwp_dropper_stalactite.unit", 6)
    one("crusher_bricks_1", f"{UNITS}/hwp_crusher_bricks.unit", 3)
    one("bear_trap_1", f"{UNITS}/hwp_bear_trap.unit", 4)
    one("turret_arrows_1", f"{UNITS}/hwp_turret_arrows.unit", 2, FULL3)
    one("gargoyle_flame_1", "doodads/traps/statues/haunted_gargoyle/haunted_gargoyle_s.unit", 2, FULL3)
    for name in ("arrow", "poison", "fire", "blade"):
        u = f"{UNITS}/hwp_shooter_{name}"
        # south: the wall cell above three floor cells; the shooter at the wall's foot
        p[f"shooter_{name}_s"] = ([(f"{u}_s.unit", 8, 16)], 2, (0, 0), (1, 4), "05070707", "00030000")
        # east (on a west wall) and west (on an east wall): the hole 8 px above the foot
        p[f"shooter_{name}_e"] = ([(f"{u}_e.unit", 16, 16)], 2, (0, 0), (4, 1), "05070707", "00030000")
        p[f"shooter_{name}_w"] = ([(f"{u}_w.unit", 48, 16)], 2, (0, 0), (4, 1), "07070705", "00000300")
    return p


def prefab_xml(units):
    by = {}
    for path, x, y in units:
        by.setdefault(path, []).append((x, y))
    out = ["<!-- HWP campaign trap prefab, generated by tools/make_hwp_traps.py (set hwp_traps, "
           "tweak/hwp/campaign_prefabs.sval); no editor origin unit (generation prefabs carry none) -->",
           "<dict>", '\t<int name="version">1</int>', '\t<dict name="units">']
    n = 1
    for path, spots in by.items():
        out.append(f'\t\t<array name="{path}">')
        for x, y in spots:
            out.append(f"\t\t\t<vec2>{x} {y}</vec2>")
            out.append(f"\t\t\t<int>{n}</int>")
            n += 1
        out.append("\t\t</array>")
    out += ["\t</dict>", "</dict>"]
    return "\n".join(out) + "\n"


def defs_block(pl):
    out = [BEGIN]
    for pid, (_, max_num, gpos, gsize, pat, cmd) in pl.items():
        out.append(
            "\t<dict>\n"
            f'\t\t<string name="id">{PREFABS}/{pid}.pfb</string>\n'
            '\t\t<string name="theme">hwp_traps</string>\n'
            f'\t\t<int name="max-num">{max_num}</int>\n'
            f'\t\t<ivec2 name="grid-pos">{gpos[0]} {gpos[1]}</ivec2>\n'
            f'\t\t<ivec2 name="grid-size">{gsize[0]} {gsize[1]}</ivec2>\n'
            '\t\t<array name="junctions"><a></a><a></a><a></a><a></a></array>\n'
            f'\t\t<bytes name="grid-pattern">{pat}</bytes>\n'
            f'\t\t<bytes name="grid-command">{cmd}</bytes>\n'
            "\t</dict>\n")
    out.append(END)
    return "".join(out)


def plan():
    files = {}
    for name, spec in kinds().items():
        files[MOD / UNITS / f"{name}.unit"] = unit_xml(name, spec)
    pl = placements()
    for pid, (units, *_rest) in pl.items():
        files[MOD / PREFABS / f"{pid}.pfb"] = prefab_xml(units)
    text = DEFS.read_text(encoding="utf-8")
    block = defs_block(pl)
    if BEGIN in text:
        a = text.index(BEGIN)
        b = text.index(END) + len(END)
        text = text[:a] + block + text[b:]
    else:
        tail = text.rindex("</array>")
        text = text[:tail] + block + text[tail:]
    files[DEFS] = text
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    stale = []
    for path, text in plan().items():
        have = path.read_text(encoding="utf-8") if path.exists() else None
        if have == text:
            continue
        stale.append(path.relative_to(REPO).as_posix())
        if not a.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if a.check:
        print(f"hwp traps: {len(stale)} stale" + (": " + ", ".join(stale) if stale else ""))
        return 1 if stale else 0
    print(f"hwp traps: wrote {len(stale)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
