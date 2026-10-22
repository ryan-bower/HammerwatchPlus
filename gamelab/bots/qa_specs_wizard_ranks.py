"""Real first-impact fourth-spec rank and Lightning Rod geometry measurements.

Requires actorbuffs hpExact/hpMax readback. Binds document setup; PASS also requires
real HP changes from native casts. No damage, crit events or measured stacks are set.
"""
import math
import re
import time

from gamelab.bots.plan_specs import Checks

TT = "hwp_wiz_tempest_torrent"
SC = "hwp_wiz_static_charge"
MM = "wiz_magic_missiles"
ROD = "hwp_wiz_tt_lightning_rod"
STACK = "players/hwp/specs/stacks_specs.sval:static_charge"
PROJECTILE = "players/hwp/specs/invocation/torrent.unit"
TARGET = "gamelab/qa_class_target_dummy.unit"
FILTER = "qa_class_target_dummy"
MAX_HP = 15000
TT_DAMAGE = (5, 6, 7, 8, 10)
SC_DAMAGE = (50, 70, 90, 120, 150)
ROD_RADIUS = (70, 77, 84, 95)
ROD_ZAPS = (3, 4, 4, 5)


def targets(c):
    reply = c.gl("actorbuffs", 400, FILTER)
    return {r["unit"]: r for r in reply.get("actors", []) if "unit" in r}


def health(rows):
    return {unit: row["hpExact"] for unit, row in rows.items() if "hpExact" in row}


def target_ok(rows, count):
    return len(rows) == count and all(r.get("hpMax") == MAX_HP and r.get("hpExact", 0) > 0 for r in rows.values())


def charges(c):
    line = c.hwp("specs", 0.05, until="specs:", timeout=1.0)
    values = re.findall(r"static charge (-?\d+)", line)
    return int(values[-1]) if values else None


def wait_ready(c):
    c.gl("timescale", 1)
    end = time.monotonic() + 40
    while time.monotonic() < end:
        value = c.skill_cd(TT)
        if value is not None and value <= 0:
            return True
        time.sleep(0.25)
    return False


def spawn(c, direction, offsets):
    c.gl("kill", 600, FILTER)
    dx, dy = direction
    for forward, side in offsets:
        c.gl("spawn", TARGET, round(forward * dx - side * dy, 3), round(forward * dy + side * dx, 3))
    return targets(c)


def first_impact(c, before, timeout=10):
    end = time.monotonic() + timeout
    reads = []
    while time.monotonic() < end:
        rows = targets(c)
        hp = health(rows)
        hit = [unit for unit, value in before.items() if hp.get(unit, value) < value - 0.1]
        if hit:
            return rows, hit, reads
        reads.append({"clock": c.gl("clock"), "hp": hp})
        time.sleep(0.06)
    return targets(c), [], reads


def evaluate_impact(data, before, expected_hits, spell):
    first, start, after = (data.get(key) or {} for key in ("first", "before", "after"))
    initial = {row.get("unit"): row for row in start.get("targets", [])}
    final = {row.get("unit"): row for row in first.get("targets", [])}
    stable = (set(initial) == set(final) == set(before) and len(initial) > 0
              and all(row.get("valid") and not row.get("dead") and row.get("hpMax") == MAX_HP
                      and row.get("hpExact", 0) > 0 for row in list(initial.values()) + list(final.values())))
    controlled = (stable and all(row.get("hpExact") == MAX_HP for row in initial.values())
                  and all(row.get("skill_crit") == 0 and row.get("spell_crit") == 0 for row in (start, first, after)))
    native = (data.get("complete") is True and not data.get("error") and not data.get("truncated")
              and 900 <= data.get("ms", 0) <= 1000 and 20 <= data.get("frames", 0) <= 80
              and data.get("input_frames", 0) >= 2
              and data.get("first_at", -1) >= data.get("input_at", 0)
              and after.get("mana", 1e9) < start.get("mana", 0) - 1
              and (spell != TT or after.get("cooldown", 0) > 0))
    deltas = {unit: initial[unit]["hpExact"] - final[unit]["hpExact"] for unit in initial if unit in final}
    drops = {unit: value for unit, value in deltas.items() if value > 0.1}
    setup = controlled and native
    hit = setup and len(drops) == expected_hits and all(value >= -0.01 for value in deltas.values())
    return setup, hit, drops


def cast_first(c, direction, offsets, tag, expected_hits, expected_damage=None, spell=TT):
    is_ready = wait_ready(c) if spell == TT else True
    rows0 = spawn(c, direction, offsets)
    c.gl("mana", 250)
    crit = c.gl("skillcrit", spell)
    queue = c.gl("qa_spec_impact", tag, spell, direction[0], direction[1])
    data = c.g.wait_gl(lambda row: row.get("ev") == "qa_spec_impact" and row.get("tag") == tag, 8) if queue.get("ok") else None
    data = data or {}
    setup, hit, drops = evaluate_impact(data, rows0, expected_hits, spell)
    first = data.get("first") or {}
    rows1 = {row["unit"]: row for row in first.get("targets", []) if "unit" in row}
    units = {PROJECTILE: {"units": first.get("projectiles", [])}}
    c.flag(tag + "_setup", setup and is_ready and queue.get("ok"),
           f"native1x setup={setup}; ready={is_ready}; crit={crit}; queue={queue}; observation={data}")
    c.flag(tag + "_hits", hit,
           f"first native damage group: {len(drops)} targets (want {expected_hits}); HP deltas {drops}; native={data}")
    return {"tag": tag, "spell": spell, "source_base_damage": expected_damage,
            "before": rows0, "after": rows1, "hit_units": list(drops), "damage": drops,
            "mean_damage": sum(drops.values()) / len(drops) if drops else None,
            "projectiles": units, "cast": queue, "crit": crit, "native": data}


def progression(c, records, expected, tag):
    # Native integer damage can round each strike. A single constant multiplier must
    # explain every independently specified source rank, within two HP per strike.
    low, high = 0.0, float("inf")
    actual = []
    for row, base in zip(records, expected):
        value = row.get("mean_damage")
        if value is None:
            low, high = 1.0, 0.0
            break
        actual.append(value)
        low = max(low, (value - 2.0) / base)
        high = min(high, (value + 2.0) / base)
    ok = len(actual) == len(expected) and low <= high and high > 0
    ok = ok and all(b > a + 0.1 for a, b in zip(actual, actual[1:]))
    c.flag(tag, ok, f"source damage {expected}; actual first-impact HP/strike {actual}; compatible native multiplier [{low}, {high}]")


def release(c, direction, rank):
    c.gl("kill", 600, FILTER)
    c.gl("timescale", 1)
    time.sleep(0.3)  # finish the prior posted input's 600ms animation/hold
    c.set_stacks(STACK, 0)
    casts = []
    # Earn the prerequisites by actual spell casts with no enemy to crit on. Each
    # Thunder Orb expires within three seconds; wait four after the final cast.
    for _ in range(5):
        c.gl("mana", 250)
        casts.append(c.gl("castat", TT, direction[0], direction[1], "nocd"))
        time.sleep(0.65)
    earned = charges(c)
    time.sleep(4.0)
    before_release = charges(c)
    release_crit = c.gl("skillcrit", SC)
    row = cast_first(c, direction, [(60, -20), (60, 0), (60, 20)], f"sc_rank_{rank}", 3, SC_DAMAGE[rank - 1], MM)
    after_release = charges(c)
    drops = list(row["damage"].values())
    c.flag(f"sc_rank_{rank}_released", earned == 5 and before_release == 5 and after_release == 0
           and all(reply.get("activated") for reply in casts) and release_crit.get("crit_chance") == 0
           and release_crit.get("spell_crit_chance") == 0 and len(drops) == 3 and max(drops) - min(drops) < 0.05,
           f"five actual casts {casts}; charges {earned} -> {before_release} -> {after_release}; "
           f"release native crit {release_crit}; equal first strike damage {drops}")
    row["charge_casts"] = casts
    row["charges"] = [earned, before_release, after_release]
    row["release_crit"] = release_crit
    c.gl("kill", 600, FILTER)
    time.sleep(1.8)  # the release cast's seeking missiles have native TTL 1500 ms
    return row


def radius(c, direction, rank):
    c.set_stacks(STACK, 0)
    radius_value = ROD_RADIUS[rank]
    # First orb period occurs 250 ms after spawn: near 20 px along the aim. The
    # actual unitsof position, not this estimate, gates the measured geometry.
    row = cast_first(c, direction, [(20, radius_value - 1), (20, -radius_value - 8)],
                     f"rod_radius_{rank}", 1)
    orb_rows = row["projectiles"].get(PROJECTILE, {}).get("units") or []
    geometry = []
    if len(orb_rows) == 1:
        orb = orb_rows[0]
        for unit, target in row["before"].items():
            distance = math.hypot(target.get("x", 0) - orb["x"], target.get("y", 0) - orb["y"])
            geometry.append({"unit": unit, "distance": distance, "damage": row["damage"].get(unit, 0)})
    inner = [r for r in geometry if r["distance"] < radius_value]
    # EnemiesNear uses QueryCircle: outer center must also clear the dummy's 5px
    # collision radius. This avoids inventing a center-only targeting requirement.
    outer = [r for r in geometry if r["distance"] > radius_value + 5]
    valid = len(inner) == len(outer) == 1
    c.flag(f"rod_radius_{rank}_geometry", valid and inner[0]["damage"] > 0.1 and outer[0]["damage"] == 0,
           f"source radius {radius_value}, native target circle5; measured orb {orb_rows}; targets {geometry}")
    row["geometry"] = geometry
    row["source_radius"] = radius_value
    return row


def run(p, **_):
    c = Checks(p)
    tt_rows, sc_rows, rod_rows = [], [], []
    # Both spec skills start at one; do not silently raise them to two in setup.
    c.setup("wizranks", "wizard", "hwp_wizard_invocation", [])
    if not c.enter_floor("wizranks"):
        return {**c.out, "notes": c.notes}
    direction = c.open_dir(300)
    c.qa_tt_button = c.button_for("wizranks_input", TT, "skill3")
    initial = {skill: c.gl("skill", skill, 0) for skill in (TT, SC)}
    c.flag("wizranks_start", all(reply.get("level") == 1 for reply in initial.values()), str(initial))
    crit_original = c.gl("skillcrit", TT)
    c.gl("skillcrit", TT, 0)
    try:
        rows = spawn(c, direction, [(60, 0)])
        c.flag("wizranks_target_readback", target_ok(rows, 1), f"requires actual hpMax=15000 and hpExact: {rows}")
        if not target_ok(rows, 1):
            return {**c.out, "notes": c.notes, "blocked": "read-only actorbuffs hpMax/hpExact not available or fixture mismatch"}
        for rank in range(1, 6):
            if rank > 1:
                c.gl("skill", TT, 1)
                c.gl("skill", SC, 1)
            levels = {skill: c.gl("skill", skill, 0).get("level") for skill in (TT, SC)}
            c.flag(f"wizranks_{rank}_levels", all(value == rank for value in levels.values()), str(levels))
            c.set_stacks(STACK, 0)
            c.gl("skillcrit", TT, 0)
            tt_rows.append(cast_first(c, direction, [(60, side) for side in (-25, -15, -5, 5, 15, 25)],
                                      f"tt_rank_{rank}", 3, TT_DAMAGE[rank - 1]))
            sc_rows.append(release(c, direction, rank))
        progression(c, tt_rows, TT_DAMAGE, "tt_rank_damage_progression")
        progression(c, sc_rows, SC_DAMAGE, "sc_rank_damage_progression")
        rod_rows.append(radius(c, direction, 0))
        for rank in range(1, 4):
            equipped = c.gl("orb", ROD, 1)
            c.flag(f"rod_rank_{rank}_equipped", equipped.get("level") == rank, str(equipped))
            c.set_stacks(STACK, 0)
            c.gl("skillcrit", TT, 0)
            rod_rows.append(cast_first(c, direction, [(60, side) for side in (-25, -15, -5, 5, 15, 25)],
                                       f"rod_targets_{rank}", ROD_ZAPS[rank]))
            rod_rows.append(radius(c, direction, rank))
    finally:
        restored = c.gl("skillcrit", TT, "restore")
        final = c.gl("skillcrit", TT)
        c.flag("wizranks_crit_restored", restored.get("ok") and not final.get("override_active")
               and final.get("crit_chance") == crit_original.get("crit_chance"), f"{crit_original} -> {restored} -> {final}")
        c.gl("timescale", 1)
        c.g.shot("wizard rank qa end", settle=False)
        c.to_town()
    return {**c.out, "notes": c.notes, "thunder_orb_ranks": tt_rows, "static_charge_ranks": sc_rows,
            "lightning_rod": rod_rows,
            "expected_source": ["mods/specs/players/hwp/specs/invocation/tempest_torrent.sval",
                                "mods/specs/players/hwp/specs/invocation/static_charge.sval",
                                "mods/specs/scripts/HWP/Specs/Invocation.as", "mods/specs/scripts/HWP/Specs/Common.as"],
            "measurement_only": "isolated fixture, god mode, prerequisite native cooldown resets and stack removal, bounded native crit setup; measured impacts use actual mapped input and1x native frame snapshots"}
