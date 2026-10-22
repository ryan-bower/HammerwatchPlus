"""Native 1x Static Charge observation: actual inputs, HP, crit text and stack reads.

The queued native observer must be installed at a clean runtime boundary. It only
posts existing GameLab inputs and reads native state; no damage/event hooks are used.
"""
import json
import re

from gamelab.bots.qa_specs_wizard_ranks import Checks, TT, SC, STACK, spawn, wait_ready

LINGERING = "hwp_wiz_tt_lingering_storm"
MM = "wiz_magic_missiles"
PHASES = ("before_tt", "first_crit", "later_crits", "before_mm", "after_mm", "old_orb_late", "finished")


def crit_text(row):
    return row.get("type") == 11 and bool(re.fullmatch(r"[1-9]\d*!", row.get("text", "")))


def hp_map(phase):
    return {row.get("unit"): row.get("hpExact") for row in phase.get("targets", [])}


def hp_falls(before, after, every=False):
    a, b = hp_map(before), hp_map(after)
    if not a or set(a) != set(b) or any(not isinstance(value, (int, float)) for value in [*a.values(), *b.values()]):
        return False
    changes = [0 < b[unit] < value - 0.1 for unit, value in a.items()]
    return all(changes) if every else any(changes)


def assemble_observation(events, final, phase_names=PHASES, event_prefix="qa_static"):
    """Rebuild bounded native payloads; missing/conflicting evidence cannot pass."""
    result = dict(final)
    samples, phases, errors = {}, {}, []
    count = final.get("sample_count", -1)
    if not isinstance(count, int) or not 0 <= count <= 200:
        errors.append("invalid native sample_count")
        count = 0
    for event in events:
        if event.get("tag") != final.get("tag"):
            continue
        if event.get("ev") == event_prefix + "_phase":
            phase = event.get("data") or {}
            key = phase.get("phase")
            if key in phases and phases[key] != phase:
                errors.append(f"conflicting phase {key}")
            phases[key] = phase
        elif event.get("ev") == event_prefix + "_samples":
            offset, rows = event.get("offset"), event.get("samples")
            if not isinstance(offset, int) or offset < 0 or not isinstance(rows, list) or not 1 <= len(rows) <= 16:
                errors.append("invalid sample chunk")
                continue
            for index, row in enumerate(rows, offset):
                if index >= count or (index in samples and samples[index] != row):
                    errors.append(f"conflicting/out-of-range sample {index}")
                samples[index] = row
    if set(samples) != set(range(count)):
        errors.append("missing native frame samples")
    if set(phases) != set(phase_names) or final.get("phase_count") != len(phase_names):
        errors.append("missing/unexpected native phases")
    result["samples"] = [samples[index] for index in sorted(samples)]
    result["phases"] = [phases[name] for name in phase_names if name in phases]
    result["retention_error"] = "; ".join(errors)
    return result


def evaluate_observation(data):
    phases = {row.get("phase"): row for row in data.get("phases", [])}
    samples = data.get("samples") or []
    complete = (data.get("complete") is True and not data.get("error") and not data.get("truncated") and not data.get("retention_error")
                and 2500 <= data.get("ms", 0) <= 2700 and data.get("frames", 0) >= 40
                and len(samples) == data.get("frames") and all(name in phases for name in PHASES))
    result = {"complete": (complete, f"complete={data.get('complete')}, frames={data.get('frames')}, ms={data.get('ms')}, truncated={data.get('truncated')}")}
    if not complete:
        return {**result, **{name: (False, "missing complete bounded native observation")
                             for name in ("setup", "first_crit", "later_crits", "other_cast", "old_orb_critical", "overlap_one_bonus")}}
    before, first, later, pre_mm, post_mm, late, end = (phases[name] for name in PHASES)
    ids = set(hp_map(before))
    target_ok = len(ids) == 3 and all(
        len(phase.get("targets", [])) == 3 and set(hp_map(phase)) == ids
        and all(row.get("valid") and not row.get("dead") and row.get("hpMax") == 15000
                and 0 < row.get("hpExact", -1) <= 15000.05 for row in phase["targets"])
        for phase in phases.values())
    crit_setup = all(phase.get("tt_crit") == 1 and phase.get("mm_crit") == 0 and phase.get("spell_crit") == 0
                     for phase in phases.values())
    setup = (target_ok and crit_setup and before.get("stacks") == 0 and not before.get("crits")
             and not before.get("projectiles") and data.get("tt_input_frames", 0) >= 2
             and data.get("mm_input_at", 0) > data.get("tt_input_at", 0))
    result["setup"] = (setup, f"stable3 native15000HP targets={target_ok}, actual crit controls={crit_setup}, zero stacks={before.get('stacks')}")
    # PlayerSkill starts cooldown after its casting animation. Its first actual
    # critical damage can precede the positive cooldown; later readback proves it.
    first_ok = (setup and first.get("stacks") == 2 and later.get("tt_cd", 0) > 0
                and hp_falls(before, first, every=True) and any(crit_text(row) for row in first.get("crits", []))
                and first.get("mana", 1e9) < before.get("mana", 0) - 1)
    result["first_crit"] = (first_ok, f"one actual TT cast plus first real critical HP loss: stacks={first.get('stacks')}, crit texts={first.get('crits')}")
    initial = [row for row in samples if 600 <= row.get("t", 0) <= 850]
    later_ok = (first_ok and initial and all(row.get("stacks") == 2 for row in initial)
                and later.get("stacks") == pre_mm.get("stacks") == 2
                and hp_falls(first, later, every=True) and any(crit_text(row) for row in later.get("crits", [])))
    result["later_crits"] = (bool(later_ok), f"repeated old-orb critical damage before MM: stacks={[row.get('stacks') for row in initial]}; HP {hp_map(first)} -> {hp_map(later)}")
    mm_jumps = 0
    previous = 0
    for row in samples:
        current = row.get("mm_cd", -1)
        if current > previous + 100:
            mm_jumps += 1
        previous = current
    actual_mm = (setup and data.get("mm_input_frames", 0) >= 2 and mm_jumps == 1
                 and any(row.get("t", 0) >= 900 and row.get("mm_cd", 0) > 0 for row in samples))
    result["other_cast"] = (actual_mm, f"posted MM frames={data.get('mm_input_frames')}; actual cooldown activation jumps={mm_jumps}; noncritical native fields={crit_setup}")
    tt_jumps = 0
    previous = 0
    for row in samples:
        current = row.get("tt_cd", -1)
        tt_jumps += current > previous + 100
        previous = current
    # Local unsynchronized projectile IDs are negative and can be recycled. They
    # are retained as raw observations, but do not establish cast identity. Only
    # TT has a forced crit contribution, MM/global crit are zero, one TT input
    # and one cooldown activation occurred, and the producer stays present.
    one_tt = tt_jumps == 1 and all(len(phase.get("projectiles") or []) == 1 for phase in (first, later, pre_mm, post_mm, late, end))
    new_crits = [row for phase in (post_mm, late, end) for row in phase.get("crits", [])
                 if crit_text(row) and row.get("born", -1) > data.get("mm_input_at", 0) + 250]
    old_critical = (actual_mm and one_tt and crit_setup and bool(new_crits) and hp_falls(pre_mm, late)
                    and any(row.get("t", 0) >= 1400 and row.get("new_crits", 0) > 0 for row in samples))
    result["old_orb_critical"] = (old_critical, f"one TT input/cooldown activation and live producer={one_tt}; only TT can crit; newly born critical texts after MM={new_crits}; HP {hp_map(pre_mm)} -> {hp_map(late)}")
    after = [row for row in samples if row.get("t", 0) >= 1450]
    correct = (later_ok and old_critical and after and all(row.get("stacks") == 3 for row in after)
               and post_mm.get("stacks") == late.get("stacks") == end.get("stacks") == 3)
    result["overlap_one_bonus"] = (bool(correct), f"different noncritical cast adds1, old orb adds0: {[row.get('stacks') for row in after]}")
    return result


def checkpoint(c, records, complete=False):
    path = c.g.results / "qa-specs-static-native.partial.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps({"complete": complete, "checks": c.out, "notes": c.notes, "trials": records}, indent=2), encoding="utf-8")
    temp.replace(path)


def run(p, trials=3, **_):
    c = Checks(p)
    records = []
    c.setup("staticnative", "wizard", "hwp_wizard_invocation", [TT, SC], orbs=((LINGERING, 2),))
    if not c.enter_floor("staticnative"):
        return {**c.out, "notes": c.notes, "trials": records}
    direction = c.open_dir(260)
    c.button_for("staticnative_tt", TT, "skill2")
    c.button_for("staticnative_mm", MM, "skill1")
    c.flag("staticnative_lifetime_setup", c.bind(TT, "tt-ttl-add") == "2000", "Lingering Storm2 keeps the same old orb alive throughout observation")
    try:
        for index in range(1, max(1, min(5, int(trials))) + 1):
            tag = f"static_native_{index}"
            is_ready = wait_ready(c)
            rows = spawn(c, direction, [(60, -15), (60, 0), (60, 15)])
            c.set_stacks(STACK, 0)
            c.gl("mana", 250)
            original = c.gl("skillcrit", TT)
            applied = c.gl("skillcrit", TT, 1)
            scale = c.gl("timescale", 1)
            c.flag(f"native_{index}_ready", is_ready and applied.get("override_active")
                   and applied.get("crit_chance") == 1 and applied.get("spell_crit_chance") == 0
                   and scale.get("timescale") == 1,
                   f"cooldown ready={is_ready}; native crit={applied}; time={scale}; target setup={rows}")
            queued = c.gl("qa_static_observe", tag, direction[0], direction[1])
            c.notes.append(f"{tag} native observer queue: {queued}")
            observed = c.g.wait_gl(lambda event: event.get("ev") == "qa_static_observe" and event.get("tag") == tag, 15) if queued.get("ok") else {}
            observed = observed or {}
            if observed:
                observed = assemble_observation(c.g.gl, observed)
            for name, (ok, detail) in evaluate_observation(observed).items():
                c.flag(f"native_{index}_{name}", bool(ok), detail)
            restored = c.gl("skillcrit", TT, "restore")
            final = c.gl("skillcrit", TT)
            c.flag(f"native_{index}_restored", restored.get("ok") and not final.get("override_active")
                   and final.get("crit_chance") == original.get("crit_chance"), f"{original} -> {restored} -> {final}")
            records.append({"trial": index, "setup": rows, "crit": applied, "queue": queued,
                            "observation": observed, "restore": restored})
            checkpoint(c, records)
    finally:
        checkpoint(c, records)
        c.gl("skillcrit", TT, "restore")
        c.gl("timescale", 1)
        c.g.shot("native Static observation end", settle=False)
        c.to_town()
    checkpoint(c, records, complete=True)
    return {**c.out, "notes": c.notes, "trials": records,
            "expected_source": "mods/specs/players/hwp/specs/invocation/static_charge.sval: each actual spell cast +1, its first crit +1; later crits of the old cast +0",
            "measurement_only": "isolated15k fixtures, god mode, zero-stack prerequisite and bounded native crit setup; actual posted inputs/natural effects at1x, no direct damage/event hooks"}
