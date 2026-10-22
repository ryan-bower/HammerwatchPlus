"""Lingering Storm's natural projectile lifetime, measured every native frame at 1x."""
from gamelab.bots.qa_specs_wizard_ranks import (
    Checks, TT, SC, STACK, PROJECTILE, FILTER, spawn, targets, health, target_ok, wait_ready,
)

LINGERING = "hwp_wiz_tt_lingering_storm"


def run(p, **_):
    c = Checks(p)
    records = []
    c.setup("lingeringqa", "wizard", "hwp_wizard_invocation", [TT, SC])
    raised = c.gl("skill", TT, 3)
    c.flag("lingeringqa_rank", raised.get("level") == 5, f"actual Thunder Orb rank5: {raised}")
    if not c.enter_floor("lingeringqa"):
        return {**c.out, "notes": c.notes, "cases": records}
    direction = c.open_dir(300)
    button = c.button_for("lingeringqa_input", TT, "skill2")
    baseline = c.gl("skillcrit", TT)
    try:
        for rank, expected in enumerate((3000, 4000, 5000)):
            if rank:
                equipped = c.gl("orb", LINGERING, 1)
            else:
                equipped = c.gl("orb", LINGERING, 0)
            is_ready = wait_ready(c)
            before = spawn(c, direction, [(60, -15), (60, 0), (60, 15)])
            hp0 = health(before)
            c.set_stacks(STACK, 0)
            c.gl("mana", 250)
            crit = c.gl("skillcrit", TT, 0)
            binds = {name: c.bind(TT, name) for name in ("tt-ttl", "tt-ttl-add")}
            tag = f"lingering_natural_{rank}"
            queued = c.gl("track", tag, 7000, 600, "invocation/torrent.unit")
            fired = c.gl("input", 600, 0, 0, direction[0], direction[1], button)
            observed = c.g.wait_gl(lambda event: event.get("ev") == "track" and event.get("tag") == tag, 14) or {}
            after = targets(c)
            hp1 = health(after)
            tracks = observed.get("tracks") or []
            lifetime = tracks[0].get("t1", 0) - tracks[0].get("t0", 0) if len(tracks) == 1 else None
            setup = (is_ready and target_ok(before, 3) and equipped.get("level") == rank
                     and crit.get("crit_chance") == 0 and crit.get("spell_crit_chance") == 0
                     and binds == {"tt-ttl": "3000", "tt-ttl-add": str(rank * 1000)}
                     and queued.get("ok") and fired.get("ok"))
            c.flag(f"lingering_{rank}_setup", setup,
                   f"orb {equipped}; ready {is_ready}; native maxHP/HP {before}; crit {crit}; binds {binds}; queue {queued}; input {fired}")
            c.flag(f"lingering_{rank}_damage", setup and any(hp1.get(unit, value) < value - 0.1 for unit, value in hp0.items()),
                   f"actual cast damage HP {hp0} -> {hp1}")
            c.flag(f"lingering_{rank}_lifetime", setup and lifetime is not None and abs(lifetime - expected) <= 100
                   and observed.get("truncated") == 0 and c.gl("unitsof", PROJECTILE).get(PROJECTILE, {}).get("count") == 0,
                   f"native per-frame observer {observed}; actual lifespan {lifetime}ms, source {expected}ms (100ms frame allowance); naturally gone")
            records.append({"rank": rank, "expected_ms": expected, "actual_ms": lifetime, "before": before,
                            "after": after, "binds": binds, "crit": crit, "observer": observed, "input": fired})
    finally:
        restored = c.gl("skillcrit", TT, "restore")
        final = c.gl("skillcrit", TT)
        c.flag("lingeringqa_restored", restored.get("ok") and not final.get("override_active")
               and final.get("crit_chance") == baseline.get("crit_chance"), f"{baseline} -> {restored} -> {final}")
        c.gl("timescale", 1)
        c.g.shot("lingering natural lifetime end", settle=False)
        c.to_town()
    return {**c.out, "notes": c.notes, "cases": records,
            "expected_source": ["mods/specs/players/hwp/specs/invocation/tempest_torrent.sval",
                                "mods/specs/players/hwp/specs/invocation/torrent.unit"],
            "measurement_only": "fresh15k target fixtures, god mode, native zero-crit override and prerequisite zero stacks; natural expiry at1x, actual posted input"}
