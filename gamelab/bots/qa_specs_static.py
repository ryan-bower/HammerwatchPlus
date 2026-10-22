"""Static Charge first-crit/overlapping-spell regression through actual cast damage.

The temporary skillcrit fixture controls native per-skill crit chance; it never sends
critical-hit events or adds the measured stacks. Direct stack removal only establishes
zero before each case. All outcomes from the fixed trial count are retained.
"""
import re
import time

from gamelab.bots.plan_specs import Checks, TARGET

ORB = "hwp_wiz_tempest_torrent"
STATIC = "hwp_wiz_static_charge"
MISSILES = "wiz_magic_missiles"
LINGERING = "hwp_wiz_tt_lingering_storm"
STACK = "players/hwp/specs/stacks_specs.sval:static_charge"


def snap(c):
    raw = c.hwp("specs", 0.05, until="specs:", timeout=1.0)
    found = re.findall(r"static charge (-?\d+)", raw)
    return {"static": int(found[-1]) if found else None,
            "hp": c.dummy_hp("target_dummy"), "clock": c.gl("clock"), "raw": raw}


def damaged(before, after):
    return any(after.get(unit, 0.0) < hp - 0.0001 for unit, hp in before.items())


def probe(c, skill):
    # Zero rolls: independent native field readback without consuming crit RNG.
    return c.gl("critprobe", 0, 400, "target_dummy", skill)


def spawn(c, direction):
    c.gl("kill", 600, "target_dummy")
    dx, dy = direction
    for side in (-15, 0, 15):
        c.gl("spawn", TARGET, round(60 * dx - side * dy, 2), round(60 * dy + side * dx, 2))
    time.sleep(0.2)


def ready(c):
    end = time.monotonic() + 40
    while time.monotonic() < end:
        cd = c.skill_cd(ORB)
        if cd is not None and cd <= 0:
            return True
        time.sleep(0.25)
    return False


def helper_contract(c):
    before = c.gl("skillcrit", ORB)
    applied = c.gl("skillcrit", ORB, 1)
    independent0 = probe(c, ORB)
    # Native orb temp-level changes reload skills and refresh their real modifiers.
    down = c.gl("orb", LINGERING, "down")
    up = c.gl("orb", LINGERING, 1)
    after_rebuild = c.gl("skillcrit", ORB)
    independent1 = probe(c, ORB)
    restored = c.gl("skillcrit", ORB, "restore")
    after_restore = c.gl("skillcrit", ORB)
    baseline = before.get("crit_chance")
    c.flag("staticqa_helper_query", before.get("ok") and baseline is not None and not before.get("override_active"), str(before))
    c.flag("staticqa_helper_set", applied.get("ok") and applied.get("override_active")
           and applied.get("crit_chance") == 1 and independent0.get("skillCrit") == 1
           and applied.get("spell_crit_chance") == 0 and independent0.get("spellCrit") == 0,
           f"set {applied}; independent native readback {independent0}")
    c.flag("staticqa_helper_rebuild", down.get("ok") and up.get("ok")
           and c.bind(ORB, "tt-ttl-add") == "2000" and after_rebuild.get("override_active")
           and after_rebuild.get("crit_chance") == 1 and independent1.get("skillCrit") == 1
           and after_rebuild.get("spell_crit_chance") == 0 and independent1.get("spellCrit") == 0,
           f"native orb rebuild {down}, {up}; readback {after_rebuild}; independent {independent1}")
    c.flag("staticqa_helper_restore", restored.get("ok") and after_restore.get("ok")
           and not after_restore.get("override_active") and baseline is not None
           and abs(after_restore.get("crit_chance", -99) - baseline) < 0.00001
           and after_restore.get("spell_crit_chance") == before.get("spell_crit_chance"),
           f"baseline {before}; restore {restored}; query {after_restore}")
    return {"before": before, "set": applied, "independent_set": independent0,
            "rebuild_down": down, "rebuild_up": up, "after_rebuild": after_rebuild,
            "independent_rebuild": independent1, "restore": restored, "after_restore": after_restore}


def trial(c, direction, button, index):
    tag = f"static_{index}"
    c.gl("timescale", 1)
    is_ready = ready(c)
    c.flag(tag + "_ready", is_ready, "Thunder Orb's real cooldown is readable and over")
    if not is_ready:
        return {"trial": index, "setup_failed": "cooldown never became ready"}
    dx, dy = direction
    spawn(c, direction)
    c.set_stacks(STACK, 0)
    control0 = snap(c)
    control_crit = c.gl("skillcrit", MISSILES)
    control_probe = probe(c, MISSILES)
    c.gl("mana", 250)
    control_cast = c.gl("castat", MISSILES, dx, dy, "nocd")
    time.sleep(1.2)
    control1 = snap(c)
    no_crit = (control_crit.get("crit_chance") == 0 and control_crit.get("spell_crit_chance") == 0
               and control_probe.get("skillCrit") == 0 and control_probe.get("spellCrit") == 0)
    c.flag(tag + "_control", no_crit and control_cast.get("ok") and control0["static"] == 0
           and control1["static"] == 1 and damaged(control0["hp"], control1["hp"]),
           f"noncritical real Magic Missiles: {control_crit}; {control_probe}; stacks {control0['static']}->{control1['static']}; "
           f"target HP {control0['hp']}->{control1['hp']}")
    c.gl("kill", 600, "target_dummy")
    time.sleep(4.0)  # let the control's seeking missiles expire before fresh targets
    spawn(c, direction)
    c.set_stacks(STACK, 0)
    c.gl("mana", 250)
    before = snap(c)
    original = c.gl("skillcrit", ORB)
    applied = c.gl("skillcrit", ORB, 1)
    independent = probe(c, ORB)
    scale = c.gl("timescale", 0.25)
    input_reply = c.gl("input", 600, 0, 0, dx, dy, button)
    snapshots = []
    restore = {}
    try:
        time.sleep(2.0)
        first = snap(c)
        snapshots.append(first)
        time.sleep(1.0)
        later = snap(c)
        snapshots.append(later)
        setup_ok = (len(before["hp"]) == 3 and before["static"] == 0 and applied.get("override_active")
                    and applied.get("crit_chance") == 1 and independent.get("skillCrit") == 1
                    and scale.get("timescale") == 0.25 and input_reply.get("ok"))
        c.flag(tag + "_setup", setup_ok,
               f"before {before}; set {applied}; independent {independent}; timescale {scale}; input {input_reply}")
        c.flag(tag + "_first_crit", setup_ok and first["static"] == 2 and damaged(before["hp"], first["hp"]),
               f"one real Thunder Orb cast plus first guaranteed critical damage: stacks {before['static']}->{first['static']}; "
               f"target HP {before['hp']}->{first['hp']}")
        c.flag(tag + "_later_crits", first["static"] == 2 and later["static"] == 2 and damaged(first["hp"], later["hp"]),
               f"subsequent guaranteed critical zaps of the same orb: stacks {first['static']}->{later['static']}; "
               f"target HP {first['hp']}->{later['hp']}")
        other_crit = c.gl("skillcrit", MISSILES)
        other_probe = probe(c, MISSILES)
        c.gl("mana", 250)
        other_cast = c.gl("castat", MISSILES, dx, dy, "nocd")
        time.sleep(1.5)
        for _ in range(3):
            snapshots.append(snap(c))
            time.sleep(0.10)
        actual_crit = c.gl("skillcrit", ORB)
        valid_other = (no_crit and other_crit.get("crit_chance") == 0 and other_crit.get("spell_crit_chance") == 0
                       and other_probe.get("skillCrit") == 0 and other_probe.get("spellCrit") == 0 and other_cast.get("ok"))
        overlap = snapshots[2:]
        c.flag(tag + "_overlap_control", valid_other and actual_crit.get("crit_chance") == 1
               and actual_crit.get("override_active"),
               f"different spell remains noncritical: {other_crit}; {other_probe}; cast {other_cast}; old orb crit {actual_crit}")
        c.flag(tag + "_overlap_one_bonus", setup_ok and valid_other and later["static"] == 2
               and all(s["static"] == 3 for s in overlap) and damaged(later["hp"], overlap[-1]["hp"]),
               f"a different noncritical cast adds exactly one: 2 -> {[s['static'] for s in overlap]}; "
               f"old orb's ongoing critical damage cannot earn a second first-crit bonus; HP {later['hp']}->{overlap[-1]['hp']}")
    finally:
        restore = c.gl("skillcrit", ORB, "restore")
        restored_query = c.gl("skillcrit", ORB)
        c.gl("timescale", 1)
        baseline = original.get("crit_chance")
        c.flag(tag + "_restored", restore.get("ok") and not restored_query.get("override_active")
               and baseline is not None and abs(restored_query.get("crit_chance", -99) - baseline) < 0.00001,
               f"original {original}; restore {restore}; query {restored_query}")
    return {"trial": index, "aim": direction, "control_before": control0, "control_after": control1,
            "control_crit": control_crit, "control_probe": control_probe, "control_cast": control_cast,
            "before": before, "original": original, "set": applied, "independent": independent,
            "timescale": scale, "input": input_reply, "snapshots": snapshots, "restore": restore}


def run(p, trials=3, contract_only=False, **_):
    c = Checks(p)
    records = []
    helper = {}
    c.setup("staticqa", "wizard", "hwp_wizard_invocation", [ORB, STATIC], orbs=((LINGERING, 2),))
    if not c.enter_floor("staticqa"):
        return {**c.out, "notes": c.notes, "trials": records}
    direction = c.open_dir(260)
    button = c.button_for("staticqa_input", ORB, "skill3")
    spawn(c, direction)
    try:
        c.gl("timescale", 1)
        helper = helper_contract(c)
        if not contract_only:
            for index in range(1, max(1, min(5, int(trials))) + 1):
                records.append(trial(c, direction, button, index))
    finally:
        c.gl("skillcrit", ORB, "restore")
        c.gl("timescale", 1)
        c.g.shot("static qa end", settle=False)
        c.to_town()
    return {**c.out, "notes": c.notes, "helper": helper, "trials": records, "contract_only": bool(contract_only),
            "source_expectation": "Static Charge: every spell cast +1, its first critical hit +1; later crits of that cast +0, including after another spell is cast",
            "measurement_only": "god mode, fresh target fixtures, zero-stack setup, bounded native crit modifier and slow scene time; no ordinary-play claim"}
