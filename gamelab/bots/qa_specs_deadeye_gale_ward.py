"""Real earned-Tailwind Gale Force/Wind Ward orb qualities; ignored draft.

Native1HP targets earn all positive measured stacks through Lightning Arrow.
Native15k targets and native attack/projectile/HP observations prove Gale Force.
Wind Ward uses same-frame native Player.Damage from a hostile actor, pure200
TrueStrike, with actual HP loss, zero-orb controls and natural expiry/reversion.
"""
import json
import math
import time

from gamelab.bots.plan_specs import Checks, BUFFS
from gamelab.bots.qa_specs_deadeye import ARROW, WINDS, STACK, FRAGILE, FRAGILE_FILTER, ready, status
from gamelab.bots.qa_specs_navigation import certified_corridor as certified_lane
from gamelab.bots.qa_observe import collect as collect_observation
from gamelab.bots.qa_specs_wizard_ranks import spawn, targets, health, target_ok

GALE = "hwp_ran_gw_gale_force"
WARD = "hwp_ran_gw_wind_ward"
MAIN = "attack_2h_shortbow"
BOW_ARROW = "players/projectiles/arrow.unit"
CIRCUIT = "players/hwp/specs/stormbringer/circuit.unit"


def checkpoint(c, cases, complete=False):
    path = c.g.results / "qa-specs-deadeye-gale-ward.partial.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"complete": complete, "checks": c.out, "notes": c.notes, "cases": cases}, indent=2))
    tmp.replace(path)


def actual_earn(c, direction, tag, clustered=False):
    # Only clear prerequisites; never add a positive Tailwind stack.
    c.gl("kill", 600, FRAGILE_FILTER)
    zero = c.gl("givestacks", STACK, -999)
    time.sleep(.7)
    is_ready = ready(c)
    dx, dy = direction
    origin = c.pos() if clustered else None
    # The cap-isolation fixture uses coincident native actors. NewProjectile's
    # collision loop processes one piercing contact synchronously; native frame
    # observations must independently show0->5 with no intermediate stack sample.
    distances = [32] * 25 if clustered else [20+i*5 for i in range(25)]
    commands = [["spawn", FRAGILE, round(dx * distance, 3), round(dy * distance, 3)] for distance in distances]
    spawned = c.g.gl_multi(commands)
    before = c.gl("actorbuffs", 250, FRAGILE_FILTER)
    c.gl("mana", 999)
    crit = c.gl("skillcrit", ARROW, 0)
    s0 = status(c)
    observation, clock0, clock1 = None, None, None
    if clustered:
        # Fixed duration, never polling for a favorable intensity. The observer
        # covers actual acquisition and several source250ms native reapplications.
        clock0, queued, fired = c.g.gl_multi([["clock"],
            ["buffobserve", tag+"_cap", 1400, BUFFS+"wind_ward", STACK],
            ["input", 400, 0, 0, dx, dy, c.qa_arrow_button]])
        observation = collect_observation(c.g, tag+"_cap", timeout=8) if queued.get("ok") else {}
    else:
        fired = c.gl("input", 400, 0, 0, dx, dy, c.qa_arrow_button)
        time.sleep(.7)
    s1 = status(c)
    if clustered:
        after, stack, clock1 = c.g.gl_multi([["near", 250, FRAGILE_FILTER], ["givestacks", STACK, 0], ["clock"]])
    else:
        after, stack = c.g.gl_multi([["near", 250, FRAGILE_FILTER], ["givestacks", STACK, 0]])
    live = [a for a in after.get("units", []) if not a.get("dead") and a.get("hp", 1) > 0]
    initial = before.get("actors", [])
    valid = (is_ready and len(spawned) == 25 and all(r.get("ok") for r in spawned)
             and not before.get("truncated") and len(initial) == 25
             and all(a.get("hpMax") == 1 and a.get("hpExact") == 1 for a in initial)
             and not after.get("truncated") and not live and fired.get("ok")
             and crit.get("crit_chance") == 0 and crit.get("spell_crit_chance") == 0
             and s0.get("tailwind") == 0 and s1.get("tailwind") == stack.get("stacks") == 5
             and s1.get("tailwind kills", -100) - s0.get("tailwind kills", 100) == 25)
    if clustered:
        events = observation.get("events", [])
        positive = [row for row in events if row.get("stacks", 0) > 0]
        first = positive[0] if positive else {}
        refreshes = [row for row in positive if "refresh" in row.get("reason", "")]
        coincident = (origin is not None and len(initial) == 25 and all(
            isinstance(row.get("x"), (int,float)) and isinstance(row.get("y"), (int,float))
            and math.dist((row["x"],row["y"]), (origin[0]+dx*32,origin[1]+dy*32)) <= .1
            for row in initial))
        observing = (coincident and observation.get("usable") is True and events and events[0].get("stacks") == 0
                     and positive and all(row.get("stacks") == 5 for row in positive)
                     and 0 <= first.get("elapsed", -1) <= 600
                     and 1400 <= observation.get("ms", 0) <= 1466
                     and observation.get("frames", 0) >= 30
                     and clock0.get("sceneMs") == observation.get("start")
                     and events[-1].get("stacks") == 5
                     and (not events[-1].get("buff_on") or len(refreshes) >= 3))
        valid = valid and observing
        c.flag(tag+"_cap_observer", bool(observing), str(observation))
    row = {"tag": tag, "valid": bool(valid), "clustered_cap_fixture": clustered, "coincident_origin":origin,
           "cap_observer": observation, "input_clock": clock0, "post_observer_clock": clock1,
           "negative_only_stack_setup": zero,
           "spawns": spawned, "before": before, "input": fired, "crit": crit,
           "status_before": s0, "status_after": s1, "after": after, "stack_read": stack}
    c.flag(tag + "_earned", bool(valid), str(row))
    return row


def projectile_angles(observation, direction):
    values = []
    dx, dy = direction
    for row in observation.get("tracks", []):
        x, y = row.get("x1", 0) - row.get("x0", 0), row.get("y1", 0) - row.get("y0", 0)
        if row.get("n", 0) < 2 or math.hypot(x, y) <= 1:
            values.append(999.0)  # insufficient actual flight; cannot prove angle
            continue
        forward, side = x * dx + y * dy, -x * dy + y * dx
        values.append(math.degrees(math.atan2(side, forward)))
    return sorted(values)


def gale_trial(c, direction, quality, trial):
    tag = f"gale_q{quality}_t{trial}"
    # At100px the0/+10/-10 degree arrows are separated17.63px. Native
    # projectile radius6 plus target circle5 cannot hit the neighboring lane.
    side = math.tan(math.radians(10)) * 100
    c.gl("kill", 600, "qa_class_target_dummy")
    earned = actual_earn(c, direction, tag)
    # Fresh measured actors AFTER earning avoid lingering physical/lightning
    # affliction pools from the real kill cast contaminating Gale HP evidence.
    dx, dy = direction
    points = [(100, 0), (100, side), (100, -side)]
    spawned = c.g.gl_multi([["spawn", "gamelab/qa_class_target_dummy.unit",
                            round(forward*dx-lateral*dy, 3), round(forward*dy+lateral*dx, 3)]
                           for forward,lateral in points])
    initial = targets(c)
    # Gale reads the native actor aim. Settle real aim for several frames; the
    # following native stack read still requires all5 earned stacks at cast time.
    aim = c.gl("input", 1000, 0, 0, *direction)
    time.sleep(.15)
    before, old, stack0, clock, queue, cast, stack1 = c.g.gl_multi([
        ["actorbuffs", 400, "qa_class_target_dummy"], ["unitsof", CIRCUIT, BOW_ARROW],
        ["givestacks", STACK, 0], ["clock"], ["track", tag, 1000, 400, BOW_ARROW],
        ["castat", MAIN, *direction], ["givestacks", STACK, 0]])
    native = c.g.wait_gl(lambda r: r.get("ev") == "track" and r.get("tag") == tag, 6) if queue.get("ok") else None
    native = native or {}
    after = targets(c)
    base = {a["unit"]: a for a in before.get("actors", []) if "unit" in a}
    hp0, hp1 = health(base), health(after)
    drops = {uid: hp0[uid] - hp1.get(uid, hp0[uid]) for uid in hp0}
    x, y = c.pos()
    dx, dy = direction
    lanes = [{"unit": uid, "side": -(a["x"]-x)*dy+(a["y"]-y)*dx,
              "forward": (a["x"]-x)*dx+(a["y"]-y)*dy, "damage": drops.get(uid, 0)} for uid,a in base.items()]
    lanes.sort(key=lambda a: a["side"])
    expected_angles = sorted([0] + ([10] if quality >= 1 else []) + ([-10] if quality >= 2 else []))
    angles = projectile_angles(native, direction)
    setup = (earned["valid"] and aim.get("ok") and len(spawned)==3 and all(a.get("ok") for a in spawned)
             and target_ok(initial, 3) and all(a.get("hpExact")==15000 for a in initial.values()) and target_ok(base, 3) and target_ok(after, 3)
             and set(base) == set(after) and all(a.get("hpExact")==15000 for a in base.values()) and not before.get("truncated")
             and old.get("ok") and all(old.get(path, {}).get("found") and old[path].get("count") == 0 for path in (CIRCUIT, BOW_ARROW))
             and stack0.get("stacks") == stack1.get("stacks") == 5
             and queue.get("ok") and cast.get("activated")
             and not native.get("truncated") and 1000 <= native.get("ms", 0) <= 1100 and native.get("frames", 0) >= 20)
    count = (setup and len(angles) == quality+1 and len(native.get("tracks", [])) == quality+1
             and all(a.get("name") == BOW_ARROW and a.get("n", 0) >= 2 for a in native.get("tracks", []))
             and all(abs(a-b) <= 1.5 for a,b in zip(angles, expected_angles)))
    # Negative side is quality2 only; positive side is qualities1 and2.
    hp = (setup and len(lanes) == 3 and abs(lanes[0]["side"] + side) < .1
          and abs(lanes[1]["side"]) < .1 and abs(lanes[2]["side"] - side) < .1
          and all(abs(a["forward"]-100) < .1 for a in lanes)
          and lanes[1]["damage"] > .1
          and ((lanes[2]["damage"] > .1) if quality >= 1 else abs(lanes[2]["damage"]) < .01)
          and ((lanes[0]["damage"] > .1) if quality >= 2 else abs(lanes[0]["damage"]) < .01))
    row = {"tag": tag, "earned": earned, "initial": initial, "before": before, "after": after,
           "old_projectiles": old, "stack_before": stack0, "stack_after": stack1, "clock": clock,
           "queue": queue, "fresh_measurement_spawns": spawned, "aim_setup": aim, "native_cast": cast, "native_track": native, "angles": angles,
           "expected_angles": expected_angles, "target_lanes": lanes, "valid_setup": bool(setup)}
    c.flag(tag + "_setup", bool(setup), str(row))
    c.flag(tag + "_projectiles", bool(count), f"angles {angles}, expected {expected_angles}; {native}")
    c.flag(tag + "_actual_hp", bool(hp), str(lanes))
    return row


def ward_trial(c, direction, quality, trial, settled=False):
    tag = f"ward_q{quality}_t{trial}"
    initial = spawn(c, direction, [(100, 0)])
    earned = actual_earn(c, direction, tag, clustered=settled)
    uid = next(iter(initial)) if initial else -1
    replies = c.g.gl_multi([
        ["givestacks", STACK, 0], ["hasbuff", BUFFS+"wind_ward"], ["hurt", .95], ["state"],
        ["damagefrom", uid, 200, "ranged"], ["givestacks", STACK, 0], ["hasbuff", BUFFS+"wind_ward"], ["clock"]])
    a, buff0, hurt, pool, hit, b, buff1, measured_clock = replies
    if settled:
        started = (earned.get("input_clock") or {}).get("sceneMs")
        now = measured_clock.get("sceneMs")
        native_window = (isinstance(started, int) and isinstance(now, int)
                         and 1400 <= now-started <= 3500
                         and a.get("stacks") == b.get("stacks") == 5)
        c.flag(tag+"_settle_clock", bool(native_window), str({"input":started,"measured":now,
               "earliest_expiry_lower_bound":started+4000 if isinstance(started,int) else None}))
        earned["valid"] = earned["valid"] and native_window
    wb0, wb1 = (r.get("buffs", [{}])[0] for r in (buff0, buff1))
    intensity = 5 * (0, .015, .03)[quality]
    expected = (200, 185, 170)[quality]
    ward = (all(w.get("on") and abs(w.get("intensity", -1)-intensity)<.0001 for w in (wb0,wb1)) if quality else all(w.get("on") is False for w in (wb0,wb1)))
    loss = hit.get("hp0", 0)-hit.get("hp", 0)
    setup = (earned["valid"] and target_ok(initial, 1) and a.get("stacks") == b.get("stacks") == 5
             and pool.get("player", {}).get("hp", 0) > 200 and hit.get("hp0", 0) > 200
             and hit.get("ok") and hit.get("attacker_hpMax") == 15000)
    c.flag(tag+"_setup", bool(setup), str({"earned":earned,"actual_starting_pool":pool,"hit":hit}))
    valid = (setup and ward and hit.get("took") == loss == expected and hit.get("hp", 0) > 0)
    c.flag(tag+"_native_dr", bool(valid), str({"earned": earned, "buff_before": buff0,"buff_after":buff1,
           "stack_before":a,"stack_after":b,"hurt_setup":hurt,"actual_hit":hit,"expected_loss":expected}))
    time.sleep(4.7)
    expired, off, hurt2, plain = c.g.gl_multi([["givestacks",STACK,0],["hasbuff",BUFFS+"wind_ward"],
                                             ["hurt",.95],["damagefrom",uid,200,"ranged"]])
    offbuff=off.get("buffs",[{}])[0]
    reverted=(expired.get("stacks")==0 and offbuff.get("on") is False and plain.get("ok")
              and plain.get("took")==plain.get("hp0",0)-plain.get("hp",0)==200 and plain.get("hp",0)>0)
    c.flag(tag+"_expires_reverts", bool(reverted), str({"stack":expired,"buff":off,"actual_hit":plain}))
    return {"tag":tag,"initial":initial,"earned":earned,"actual_hit":hit,"buff_before":buff0,"buff_after":buff1,
            "expected_intensity":intensity,"expected_hp_loss":expected,"measurement_clock":measured_clock,
            "expiry":{"stack":expired,"buff":off,"hit":plain}}


def run(p, section, ward_fixture="staggered", **_):
    c=Checks(p);cases=[]
    c.setup("galeqa","ranger","hwp_ranger_stormbringer",[])
    if not c.out.get("galeqa_char") or not c.out.get("galeqa_learned"):return {**c.out,"notes":c.notes}
    if not c.enter_floor("galeqa"):return {**c.out,"notes":c.notes}
    c.gl("timescale",1)
    origin,direction,geometry=certified_lane(c,gale=True)
    c.flag("galeqa_lane",direction is not None,str(geometry))
    if direction is None:return {**c.out,"notes":c.notes}
    c.qa_arrow_button=c.button_for("galeqa_arrow_input",ARROW,"skill2")
    native_skills=c.gl("skills").get("skills",[])
    c.flag("galeqa_native_bow",any(s.get("id")==MAIN and s.get("button")=="main" for s in native_skills),str(native_skills))
    if not c.out.get("galeqa_native_bow"):return {**c.out,"notes":c.notes}
    original=c.gl("skillcrit",ARROW)
    try:
        if section=="ward":
            c.god(False)
            god=c.gl("cvars","cht_god").get("cvars",{}).get("cht_god")
            c.flag("ward_god_off",isinstance(god,(int,float)) and god==0,str(god))
            pool=c.gl("state").get("player",{})
            c.flag("ward_health_pool",pool.get("hpMax",0)>=213,str(pool))
            if not c.out["ward_god_off"] or not c.out["ward_health_pool"]:
                return {**c.out,"notes":c.notes,"cases":cases}
        orb=GALE if section=="gale" else WARD
        for quality in range(3):
            reply=c.gl("orb",orb,1 if quality else 0)
            c.flag(f"{section}_q{quality}_equipped",reply.get("level")==quality,str(reply))
            for trial in (1,2):
                row=(gale_trial(c,direction,quality,trial) if section=="gale"
                     else ward_trial(c,direction,quality,trial,settled=ward_fixture=="coincident-cap"))
                cases.append(row);checkpoint(c,cases)
        restored=c.gl("skillcrit",ARROW,"restore");final=c.gl("skillcrit",ARROW)
        c.flag("galeqa_restored",restored.get("ok") and not final.get("override_active")
               and final.get("crit_chance")==original.get("crit_chance")
               and final.get("spell_crit_chance")==original.get("spell_crit_chance"),str(final))
    except Exception as exc:
        c.notes.append("First error preserved; isolated runner owns teardown: "+repr(exc));checkpoint(c,cases);raise
    c.to_town();checkpoint(c,cases,True)
    return {**c.out,"notes":c.notes,"cases":cases,"measurement_only":True,
            "source":["mods/specs/scripts/HWP/Specs/Stormbringer.as:298","mods/specs/players/hwp/specs/stormbringer/gathering_winds.sval",
                      "mods/specs/players/hwp/specs/buffs_specs.sval:wind_ward","gamecode/sdk/hoh2/scripts/Behaviors/Actors/Player/Player.as:524"],
            "not_covered":["GaleForce crossbow/secondary/epic weapon variants","WindWard intermediate1..4stack scaling",
                           "ordinary acquisition/UI, co-op/network, all-orb combinations and transitions"]}
