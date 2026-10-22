"""DRAFT: Arcane orb effects from native damage, casts and exact resource/HP reads.

Controlled lab fixture: prerequisite mana setup, certified-lane relocation,
stationary15k hostile actor, bounded noncrit override and real Player.Damage.
No positive measured stack/bank setter. Not ordinary-play or teammate evidence.
Install only after root review; this ignored draft has never run.
"""
import math
import re
import time

from gamelab.bots.plan_specs import Checks
from gamelab.bots.qa_specs_navigation import certified_corridor as certified_lane
from gamelab.bots.qa_specs_wizard_ranks import spawn, targets, health, target_ok

BLINK = "hwp_sor_blink"
LM = "hwp_sor_living_mana"
SD = "static_discharge"
BARRIER = "hwp_sor_bl_void_barrier"
FAR = "hwp_sor_bl_far_step"
FEEDBACK = "hwp_sor_lm_arcane_feedback"
CONDUIT = "hwp_sor_lm_mana_conduit"
ORBS = (BARRIER, FAR, FEEDBACK, CONDUIT)
SOURCES = ["mods/specs/scripts/HWP/Specs/Arcane.as",
           "mods/specs/players/hwp/specs/arcane/blink.sval",
           "mods/specs/players/hwp/specs/arcane/living_mana.sval",
           "gamecode/sdk/hoh2/players/sorcerer/skills/static_discharge.sval"]


def nums(c):
    raw = c.specs()
    values = {}
    for key in ("feedback", "used", "mul", "barrier saves", "blinks", "recasts", "drained"):
        found = re.findall(re.escape(key) + r" (-?\d+)", raw)
        values[key] = int(found[-1]) if found else None
    return {"raw": raw, **values}


def scene_wait(c, until, cap=8):
    """Require native scene time to pass a deadline; never reset cooldown/time."""
    end = time.monotonic() + cap
    while time.monotonic() < end:
        row = c.gl("clock")
        if isinstance(row.get("sceneMs"), (int, float)) and row["sceneMs"] >= until:
            return row
        time.sleep(0.1)
    return c.gl("clock")


def ready(c, skill, cap=10):
    end = time.monotonic() + cap
    while time.monotonic() < end:
        cd = c.skill_cd(skill)
        if cd is not None and cd <= 0:
            return True
        time.sleep(0.15)
    return False


def state(c):
    return c.gl("state").get("player", {})


def crit_zero(c):
    reply = c.gl("skillcrit", SD, 0)
    return reply, bool(reply.get("ok") and reply.get("override_active")
                       and reply.get("crit_chance") == 0 and reply.get("spell_crit_chance") == 0)


def setup(c, section):
    created, _, _ = c.new_char("sorcerer", "LabArcane" + section.capitalize())
    before = state(c)
    selected = c.gl("subclass", "hwp_sorcerer_arcane")
    c.hwp("skillpoints 100")
    levels = {sid: c.gl("skill", sid, 0).get("level") for sid in (BLINK, LM, SD)}
    if levels.get(SD) == 0:
        levels[SD] = c.gl("skill", SD, 1).get("level")
    orbs = {orb: c.gl("orb", orb, 0).get("level") for orb in ORBS}
    c.flag("arc_orb_fresh", bool(created.get("ok") and before.get("class") == "sorcerer"
           and before.get("level", 0) >= 20 and selected.get("class") == "hwp_sorcerer_arcane"
           and levels == {BLINK: 1, LM: 1, SD: 1} and all(v == 0 for v in orbs.values())),
           f"fresh native character={before}; subclass={selected}; skills={levels}; orbs={orbs}")
    if not c.out["arc_orb_fresh"] or not c.enter_floor("arc_orb_" + section):
        return None
    c.gl("timescale", 1)
    c.god(True)
    origin, direction, geometry = certified_lane(c)
    c.god(False)
    cvars = c.gl("cvars", "cht_god", "g_timescale").get("cvars", {})
    off = "cht_god" in cvars and cvars["cht_god"] in (0, False)
    one = cvars.get("g_timescale") == 1
    c.flag("arc_orb_lane", origin is not None and direction is not None, str(geometry))
    c.flag("arc_orb_controls", off and one, str(cvars))
    c.out["fixture_geometry"] = geometry
    if origin is None or not off or not one:
        return None
    return origin, direction


def barrier(c, origin, direction):
    equipped = c.gl("orb", BARRIER, 1)
    time.sleep(0.4)
    orbs = {orb: c.gl("orb", orb, 0).get("level") for orb in ORBS}
    rows = spawn(c, direction, [(0, 40)])
    uid = next(iter(rows), 0)
    button = c.button_for("arc_barrier_blink", BLINK, "skill2")
    c.gl("mana", 10000)  # prerequisite pool; not a measured bank/stack
    time.sleep(0.4)
    base = state(c)
    counters0 = nums(c)
    eligible = (equipped.get("level") == 1 and orbs == {BARRIER: 1, FAR: 0, FEEDBACK: 0, CONDUIT: 0}
                and target_ok(rows, 1) and 160 <= base.get("manaExact", 0) < 900
                and ready(c, BLINK) and c.out.get("arc_barrier_blink_own_button") is True)
    c.flag("barrier_setup", bool(eligible), f"orbs={orbs}; target={rows}; native pool={base}; counters={counters0}")
    if not eligible:
        return []
    pre = c.g.gl_multi([["clock"], ["state"]])
    fired = c.gl("input", 400, 0, 0, direction[0], direction[1], button)
    time.sleep(0.2)  # native Blink castpoint100; exact window is checked below
    sample = c.g.gl_multi([["clock"], ["state"], ["damagefrom", uid, 5, "ranged"], ["state"],
                          ["damagefrom", uid, 1000, "ranged"], ["state"], ["clock"]])
    p0 = pre[1].get("player", {})
    p1, p2, p3 = (sample[n].get("player", {}) for n in (1, 3, 5))
    elapsed = (sample[6].get("sceneMs", -10000) - pre[0].get("sceneMs", 0))
    moved = math.hypot(p1.get("x", 1e6) - p0.get("x", 0), p1.get("y", 1e6) - p0.get("y", 0))
    window = bool(fired.get("ok") and 100 <= elapsed <= 950 and abs(moved - 85.5) <= 1)
    nonlethal = bool(window and sample[2].get("ok") and sample[2].get("took") == 5
                     and abs(p1.get("manaExact", -1000) - p2.get("manaExact", 1000) - 5) <= 0.05
                     and p2.get("dead") is False)
    saved = bool(window and sample[4].get("ok") and sample[4].get("took") == 1000
                 and abs(p3.get("manaExact", -1000) - 1) <= 0.05 and p3.get("dead") is False)
    time.sleep(0.1)
    after = state(c)
    counters1 = nums(c)
    mirror = bool(after.get("dead") is False and abs(after.get("hp", 0) / max(1, after.get("hpMax", 1))
                  - after.get("manaExact", 0) / max(1, after.get("manaMax", 1))) < 0.02)
    c.flag("barrier_native_window", window, f"pre={pre}; input={fired}; sample={sample}; moved={moved}; elapsed={elapsed}")
    c.flag("barrier_nonlethal_drain", nonlethal, f"real pure5, same-frame mana {p1.get('manaExact')}->{p2.get('manaExact')}")
    c.flag("barrier_lethal_saved", saved and mirror and counters1.get("barrier saves") == counters0.get("barrier saves", -10) + 1,
           f"real pure1000; same-frame={p3}; next-frame={after}; counters={counters0}->{counters1}")
    # Blink is already observed by this latest native clock. Waiting from the
    # earlier input clock could underwait when transport itself was delayed.
    deadline = sample[6].get("sceneMs", 0) + 1100
    expired = scene_wait(c, deadline)
    fatal = c.g.gl_multi([["clock"], ["damagefrom", uid, 1000, "ranged"], ["state"]])
    dead = fatal[2].get("player", {})
    c.flag("barrier_expiry_lethal", bool(expired.get("sceneMs", -1) >= deadline
           and fatal[0].get("sceneMs", -1) >= deadline and fatal[1].get("ok")
           and fatal[1].get("took", 0) > 0 and dead.get("dead") is True
           and dead.get("hp", 1) <= 0 and dead.get("manaExact", 1) <= 0.05), str(fatal))
    c.flag("barrier_all_effects", all(c.out.get(key) is True for key in
           ("barrier_setup", "barrier_native_window", "barrier_nonlethal_drain", "barrier_lethal_saved", "barrier_expiry_lethal")),
           "native Blink + controlled real damage; inside and post-expiry controls, no exact1ms boundary claim")
    return [{"pre": pre, "input": fired, "inside": sample, "after": after, "counters0": counters0,
             "counters1": counters1, "expiry_clock": expired, "fatal": fatal}]


def actual_spell(c, direction, uid, label):
    """Deferred ordinary button, one fresh actor, native exact HP and mana timeline."""
    ready_before = ready(c, SD)
    crit, controlled = crit_zero(c)
    # The observer requires >99% HP. A new actor per cast also keeps all three
    # independent measurements at exactly15000HP and identical geometry.
    old_uid = uid
    rows0 = spawn(c, direction, [(64, 0)])
    uid = next(iter(rows0), None)
    queued = c.gl("qa_spec_impact", label, SD, *direction)
    data = (c.g.wait_gl(lambda row: row.get("ev") == "qa_spec_impact"
                      and row.get("tag") == label, 8) if queued.get("ok") else {}) or {}
    before, first, after = (data.get(key) or {} for key in ("before", "first", "after"))
    phases = (before, first, after)
    phase_ids = [{row.get("unit") for row in phase.get("targets", [])} for phase in phases]
    same_actor = bool(uid is not None and all(ids == {uid} for ids in phase_ids))
    readbacks = [row for phase in phases for row in phase.get("targets", [])]
    controls = bool(same_actor and all(phase.get("skill_crit") == phase.get("spell_crit") == 0
                    for phase in phases) and all(row.get("valid") is True and row.get("dead") is False
                    and row.get("hpMax") == 15000 and row.get("hpExact", 0) > 0 for row in readbacks))
    first_rows = {row.get("unit"): row for row in first.get("targets", [])}
    final_rows = {row.get("unit"): row for row in after.get("targets", [])}
    hp0 = next((row.get("hpExact") for row in before.get("targets", []) if row.get("unit") == uid), None)
    hp_first = first_rows.get(uid, {}).get("hpExact")
    hp1 = final_rows.get(uid, {}).get("hpExact")
    mana0, mana1 = before.get("mana"), after.get("mana")
    valid = bool(ready_before and controlled and target_ok(rows0, 1) and controls
                 and queued.get("ok") is True and bool(queued.get("button"))
                 and data.get("skill") == SD and data.get("complete") is True
                 and not data.get("error") and data.get("truncated") is False
                 and data.get("cast_trace_truncated") is False
                 and 900 <= data.get("ms", 0) <= 1000 and 20 <= data.get("frames", 0) <= 80
                 and data.get("input_frames", 0) >= 2
                 and data.get("first_at", -1) >= data.get("input_at", 0) >= 0
                 and hp0 == 15000 and hp_first is not None and hp1 is not None
                 and hp_first < hp0 - .1 and hp1 <= hp_first + .01
                 and mana0 is not None and mana1 is not None and mana1 < mana0 - 1
                 and after.get("cooldown", 0) > 0)
    # first is actual SD damage; after proves normal completion, payment and CD.
    # No TT producer or Wizard Static Charge gate applies to Sorcerer SD.
    damage = hp0 - hp_first if hp0 is not None and hp_first is not None else None
    return {"label": label, "uid": uid, "replaced_uid": old_uid, "ready": ready_before,
            "crit": crit, "queued": queued, "native": data, "before": rows0,
            "mana0": mana0, "mana1": mana1, "damage": damage, "valid": valid,
            "clock": {"sceneMs": data.get("input_at", 0)}}


def feedback(c, origin, direction):
    cases = []
    for quality, cap in enumerate((50, 80, 120), 1):
        equipped = c.gl("orb", FEEDBACK, 1)
        time.sleep(0.4)
        orbs = {orb: c.gl("orb", orb, 0).get("level") for orb in ORBS}
        rows = spawn(c, direction, [(64, 0)])
        uid = next(iter(rows), 0)
        c.gl("mana", 10000)
        time.sleep(0.4)
        pool = state(c)
        clean = nums(c)
        setup_ok = bool(equipped.get("level") == quality and orbs == {BARRIER: 0, FAR: 0, FEEDBACK: quality, CONDUIT: 0}
                        and target_ok(rows, 1) and pool.get("manaExact", 0) >= 240
                        and clean.get("feedback") == 0 and clean.get("mul") == 1000)
        c.flag(f"feedback_{quality}_setup", setup_ok, f"orbs={orbs}; native target={rows}; pool={pool}; status={clean}")
        if not setup_ok:
            cases.append({"quality": quality, "setup": False, "pool": pool, "status": clean, "targets": rows})
            continue
        baseline = actual_spell(c, direction, uid, f"feedback{quality}_baseline")
        uid = baseline["uid"]  # the earlier fixture actor was replaced before the native cast
        # Full pool is prerequisite setup BEFORE measured enemy damage; never refill the bank.
        c.gl("mana", 10000)
        time.sleep(0.4)
        before_bank = nums(c)
        damaged = c.g.gl_multi([["state"], ["damagefrom", uid, 150, "ranged"], ["state"]])
        a, b = (damaged[n].get("player", {}) for n in (0, 2))
        bank = nums(c)
        bank_ok = bool(damaged[1].get("ok") and damaged[1].get("took") == 150 and b.get("dead") is False
                       and abs(a.get("manaExact", -1000) - b.get("manaExact", 1000) - 150) <= 0.05
                       and bank.get("feedback") == cap and bank.get("used") == before_bank.get("used"))
        boosted = actual_spell(c, direction, uid, f"feedback{quality}_boosted")
        consumed = nums(c)
        want_mul = 1000 + cap * 5
        expected = baseline["damage"] * (1 + cap * 0.005) if baseline["damage"] is not None else None
        damage_ok = bool(baseline["valid"] and boosted["valid"] and expected is not None
                         and abs(boosted["damage"] - expected) <= 2.1)
        consume_ok = bool(bank_ok and consumed.get("feedback") == 0
                          and consumed.get("used") == bank.get("used", -10) + 1
                          and consumed.get("mul") == want_mul)
        start = boosted["clock"].get("sceneMs", 0)
        deadline = start + 3500
        expiry = scene_wait(c, deadline)
        expired = nums(c)
        reverted = actual_spell(c, direction, uid, f"feedback{quality}_expired")
        revert_ok = bool(expiry.get("sceneMs", -1) >= deadline and expired.get("feedback") == 0
                         and expired.get("mul") == 1000 and reverted["valid"] and baseline["valid"]
                         and abs(reverted["damage"] - baseline["damage"]) <= 2.1)
        c.flag(f"feedback_{quality}_bank", bank_ok, f"actual pure150={damaged}; source cap={cap}; status={before_bank}->{bank}")
        c.flag(f"feedback_{quality}_consume_damage", consume_ok and damage_ok,
               f"baseline={baseline}; boosted={boosted}; expectedHP={expected}; consumed={consumed}")
        c.flag(f"feedback_{quality}_expiry", revert_ok,
               f"native deadline={deadline}; observed={expiry}; status={expired}; actual reversion={reverted}")
        cases.append({"quality": quality, "source_cap": cap, "baseline": baseline, "damagefrom": damaged,
                      "bank_before": before_bank, "bank_after": bank, "boosted": boosted, "consumed": consumed,
                      "expiry_clock": expiry, "expired": expired, "reverted": reverted})
    c.flag("feedback_all_qualities", all(c.out.get(f"feedback_{q}_{suffix}") is True
           for q in (1, 2, 3) for suffix in ("setup", "bank", "consume_damage", "expiry")),
           "source caps50/80/120, real damage bank, native elemental cast, actual targetHP boost and natural3s reversion")
    return cases


def run(p, section="feedback", **_):
    c = Checks(p)
    if section not in ("barrier", "feedback"):
        return {"invalid_section": section}
    geometry = setup(c, section)
    if geometry is None:
        return {**c.out, "notes": c.notes, "cases": [], "expected_source": SOURCES}
    if section == "barrier":
        # No damage dealt by the player is measured here, so no crit fixture is
        # needed. Intentional expiry death may remove the local actor entirely.
        cases = barrier(c, *geometry)
    else:
        original = c.gl("skillcrit", SD)
        try:
            cases = feedback(c, *geometry)
        except Exception as exc:
            # Preserve the first transport/runtime exception. The expiring
            # fixture and isolated runner teardown own exceptional cleanup.
            c.notes.append("First error preserved; runner owns teardown: " + repr(exc))
            raise
        restored = c.gl("skillcrit", SD, "restore")
        final = c.gl("skillcrit", SD)
        c.flag("arc_orb_crit_restored", bool(restored.get("ok") and final.get("override_active") is False
               and final.get("crit_chance") == original.get("crit_chance")
               and final.get("spell_crit_chance") == original.get("spell_crit_chance")),
               f"native override restored {original}->{restored}->{final}")
        if state(c).get("dead") is False:
            c.to_town()
    return {**c.out, "notes": c.notes, "cases": cases, "expected_source": SOURCES,
            "scope": "controlled1x/godoff native damage/casts; prerequisite mana and lane relocation; no ordinary-play, exact1ms boundary, true teammate, or Blink-skip claim"}
