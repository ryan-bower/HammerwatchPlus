"""Magazine-local owned fan/HP fixture; native hits remain separately required.

Only existing public verbs are used. Post-shot reads precede trace collection.
Pure guards and injected fake calls do not establish native aim or hit effects.
"""
import math
import time

from gamelab.bots.qa_firearms_input_geometry import cursor_binding

DUMMY = "doodads/generic/target_dummy_breakable.unit"
ANGLES = (-20, -10, 0, 10, 20)
BLOCKERS = {"Breakable", "CompositeActorBehavior", "CompositeActorBehaviorNPC", "StateActorBehavior"}
POST_MS = 200  # Preserve the original fixed post-shot .2s observation window.


class FixtureError(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise FixtureError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def world(row):
    if (type(row) is not dict or row.get("_preload") is True
            or not isinstance(row.get("level"), str) or not row["level"]
            or any(type(row.get(k)) is not int or row[k] <= 0 for k in ("boots", "_lvl"))):
        return None
    return row["level"], row["boots"], row["_lvl"]


def actor(row, origin=None, expected=None):
    need(type(row) is dict and row.get("ok") is True and world(row) is not None,
         "missing current native actor/world")
    need(type(row.get("player")) is int and row["player"] > 0
         and all(type(row.get(k)) is int and row[k] >= 0 for k in ("now", "frame"))
         and all(finite(row.get(k)) for k in ("x", "y", "z", "_t", "timescale"))
         and row.get("gameplay_focus") is True and row.get("window") == ""
         and abs(row["timescale"] - 1) < .0001 and abs(row["z"]) < .1,
         "actor clock/focus/position prerequisite")
    need(all(type(row.get(hand)) is dict for hand in ("main", "off")), "missing actual equipment snapshot")
    gear = tuple(row[hand].get("id") for hand in ("main", "off"))
    need(all(isinstance(v, str) for v in gear) and bool(gear[0]), "missing actual equipment identity")
    need(all(type(row[h].get("item_token")) is int
             and (row[h]["item_token"] > 0 if row[h]["id"] else row[h]["item_token"] == 0)
             for h in ("main", "off")), "missing native item instance identity")
    if expected is not None:
        need(gear == expected, "requested equipment identity changed")
    if origin is not None:
        need(world(row) == world(origin) and row["player"] == origin["player"]
             and origin["now"] <= row["now"] <= origin["now"] + 5000
             and row["frame"] >= origin["frame"] and row["_t"] >= origin["_t"]
             and math.dist((row["x"], row["y"]), (origin["x"], origin["y"])) <= .3,
             "stale/foreign/moved fan actor")
        need(gear == tuple(origin[h]["id"] for h in ("main", "off")), "fan equipment changed")
        need(all(row[h]["item_token"] == origin[h]["item_token"] for h in ("main", "off")),
             "fan item instance changed")
    return row


def fresh(reply, origin):
    need(type(reply) is dict and reply.get("_preload") is not True
         and reply.get("_lvl") == origin["_lvl"] and reply.get("_place") == origin.get("_place")
         and finite(reply.get("_t")) and reply["_t"] >= origin["_t"],
         "foreign/stale delivery context")


def read_batch(game, commands, origin):
    """Bind one current native multi frame; _t is delivery order, not a native clock."""
    mark = len(game.gl)
    rows = game.gl_multi(commands)
    need(type(rows) is list and len(rows) == len(commands) and len(rows) > 0, "missing native batch")
    parent = None
    for index, row in enumerate(rows):
        fresh(row, origin)
        need(row.get("ok") is True and isinstance(row.get("id"), str), "failed native batch reply")
        parts = row["id"].rsplit(".", 1)
        need(len(parts) == 2 and bool(parts[0]) and parts[1] == str(index), "wrong native batch suffix/order")
        if parent is None:
            parent = parts[0]
        need(parts[0] == parent, "foreign native batch parent")
    need(0 <= len(game.gl) - mark <= 4096, "native batch delivery observation cap")
    facts = game.gl[mark:]
    heads = [r for r in facts if r.get("id") == parent and r.get("n") == len(commands) and r.get("ok") is True]
    rx = [r for r in facts if r.get("ev") == "rx" and r.get("cid") == parent and r.get("verb") == "multi"]
    need(len(heads) == len(rx) == 1, "missing current multi receipt/dispatch binding")
    fresh(heads[0], origin)
    fresh(rx[0], origin)
    need(all(a["_t"] <= b["_t"] for a, b in zip(rows, rows[1:]))
         and rx[0]["_t"] <= rows[0]["_t"] <= rows[-1]["_t"] <= heads[0]["_t"],
         "native batch delivery order changed")
    return rows


def reconcile(game, mark, tag, record):
    """One bounded read-only lookup. A locator is never a fabricated acceptance."""
    need(0 <= len(game.gl) - mark <= 4096, "uncertain dispatch reconciliation observation cap")
    facts = game.gl[mark:]
    if not any(r.get("tag") == tag for r in facts):
        game.wait_gl(lambda r: r.get("tag") == tag, timeout=5)
        need(0 <= len(game.gl) - mark <= 4096, "uncertain dispatch reconciliation observation cap")
        facts = game.gl[mark:]
    need(len(facts) <= 4096, "uncertain dispatch reconciliation observation cap")
    rows = [r for r in facts if r.get("tag") == tag and isinstance(r.get("id"), str) and r["id"]]
    record["reconciliation"] = {"tag": tag, "facts": rows, "read_only": True}
    identities = {r["id"] for r in rows if r.get("ev") in (None, "inputtarget", "inputsequence")}
    need(len(identities) == 1, "uncertain dispatch has missing/ambiguous native identity")
    ident = next(iter(identities))
    ack = [r for r in rows if r.get("ev") is None and r.get("ok") is True and r["id"] == ident]
    need(len(ack) <= 1, "duplicate uncertain dispatch acknowledgement")
    if ack:
        return ack[0]
    locator = next((r for r in rows if r["id"] == ident and r.get("ev") == "inputtarget"), rows[0])
    record["reconciliation"]["locator_only_no_ack_credit"] = True
    return locator  # It lacks ok=true; collector must retain invalid acceptance.


def offsets(direction):
    need(type(direction) in (list, tuple) and len(direction) == 2
         and all(finite(v) for v in direction) and abs(math.hypot(*direction) - 1) <= .002,
         "invalid fan direction")
    angle = math.atan2(direction[1], direction[0])
    return [(round(math.cos(angle + math.radians(a)) * 45, 1),
             round(math.sin(angle + math.radians(a)) * 45, 1)) for a in ANGLES]


def complete(reply):
    need(type(reply) is dict and reply.get("ok") is True and reply.get("_preload") is not True
         and type(reply.get("truncated")) in (int, bool) and reply["truncated"] == 0
         and type(reply.get("units")) is list and type(reply.get("count")) is int
         and reply["count"] == len(reply["units"]), "missing/truncated complete near reply")
    return reply["units"]


def geometry(origin, points, rays, nearby):
    need(type(rays) is list and len(rays) == 5
         and all(type(r) is dict and r.get("ok") is True and r.get("wall") is False
                 and r.get("tile") is False for r in rays), "uncertified fan ray")
    for unit in complete(nearby):
        if unit.get("dead") is True:
            continue
        need("target_dummy" not in unit.get("name", ""), "old live dummy remains before new births")
        if unit.get("behavior") not in BLOCKERS:
            continue
        need(all(finite(unit.get(k)) for k in ("x", "y")), "malformed fan blocker")
        delta = (unit["x"] - origin["x"], unit["y"] - origin["y"])
        for point in points:
            size = math.hypot(*point)
            d = (point[0] / size, point[1] / size)
            along = delta[0]*d[0] + delta[1]*d[1]
            across = abs(delta[0]*d[1] - delta[1]*d[0])
            need(not (6 < along < 81 and across < 12), "actor/breakable blocks fan ray")


def owned_hp(origin, current, births, points, reply, initial):
    actor(current, origin)
    need(type(births) is list and len(births) == len(points) == 5, "missing five current fan births")
    need(all(type(b) is dict for b in births), "malformed fan births")
    need(len({b.get("unit") for b in births}) == 5 and len({b.get("id") for b in births}) == 5,
         "duplicate fan birth identity")
    rows = complete(reply)
    need(all(type(r) is dict for r in rows), "malformed HP target rows")
    need(reply.get("_lvl") == origin["_lvl"] and reply.get("_place") == origin.get("_place")
         and finite(reply.get("_t")) and origin["_t"] <= reply["_t"] <= current["_t"] + .001,
         "foreign/stale HP snapshot context")
    need(len(rows) == 5 and {r.get("unit") for r in rows} == {b.get("unit") for b in births},
         "missing/duplicate/foreign current HP targets; absence is not death")
    result = {}
    for birth, point in zip(births, points):
        need(birth.get("ok") is True and birth.get("name") == DUMMY
             and type(birth.get("unit")) is int and birth["unit"] > 0
             and isinstance(birth.get("id"), str) and bool(birth["id"])
             and birth.get("_preload") is not True and birth.get("_lvl") == origin["_lvl"]
             and birth.get("_place") == origin.get("_place")
             and all(finite(birth.get(k)) for k in ("x", "y", "_t"))
             and origin["_t"] <= birth["_t"] <= reply["_t"]
             and math.dist((birth["x"], birth["y"]),
                           (origin["x"] + point[0], origin["y"] + point[1])) <= .3,
             "foreign/stale/moved fan birth")
        matches = [r for r in rows if r.get("unit") == birth["unit"]]
        need(len(matches) == 1, "nonunique current HP identity")
        unit = matches[0]
        need(unit.get("name") == DUMMY and unit.get("behavior") == "CompositeActorBehavior"
             and unit.get("scene") == "pop" and unit.get("hpMax") == 500
             and finite(unit.get("hpExact")) and 0 <= unit["hpExact"] <= 500
             and type(unit.get("dead")) is bool
             and (not unit["dead"] or unit["hpExact"] == 0)
             and all(finite(unit.get(k)) for k in ("x", "y"))
             and math.dist((unit["x"], unit["y"]), (birth["x"], birth["y"])) <= .15,
             "missing actual precise500HP breakable target")
        if initial:
            need(unit["hpExact"] == 500 and unit["dead"] is False, "fan target not initially full/live")
        result[birth["unit"]] = unit["hpExact"]
    return result


def idle(reply):
    return (type(reply) is dict and reply.get("ok") is True
            and type(reply.get("held")) is int and reply["held"] <= 0
            and reply.get("releasing") is False and reply.get("down") == []
            and reply.get("gamepad") is False
            and all(finite(reply.get(k)) and abs(reply[k]) < .0001 for k in ("mx", "my")))


def shot_contract(pre, post, released, accepted, cursor, target, tag, controllers):
    actor(post, pre)
    actor(released, pre)
    need(accepted.get("player") == pre["player"] and accepted.get("tag") == tag,
         "native cursor accepted another actor/request")
    binding = cursor_binding(accepted, cursor, target)
    need(binding["valid"], "strict requested cursor/projection/owned restoration failed: " + repr(binding["errors"]))
    terminal = cursor.get("terminal", {})
    steps = terminal.get("steps", [])
    need(len(steps) == 1 and all(type(terminal.get(k)) is int for k in ("start", "end"))
         and type(steps[0].get("last_write")) is int
         and pre["now"] <= terminal["start"] <= terminal["end"] <= post["now"]
         and 0 <= post["now"] - steps[0]["last_write"] <= POST_MS
         and post["now"] <= released["now"], "post-shot batch outside completed native input/.2s window")
    need(all(type(row) is dict and all(finite(row.get(k)) for k in ("x", "y"))
             and math.dist((row["x"], row["y"]), (pre["x"], pre["y"])) <= .3
             for row in cursor["samples"]), "shooter moved during cursor sequence")
    need(len(controllers) == 2 and all(idle(c) for c in controllers), "native release did not remain idle across RPCs")
    return binding


def measured_cycle(checks, direction, button="main", duration=320, refill=False, *, collect=None, sleep=time.sleep):
    """One fixed sample. Failure retains receipts and stops dependent setup; never retries."""
    record = {"status": "UNRUN", "input_dispatched": False, "measurement": "UNRUN",
              "button": button, "duration_ms": duration}
    checks.out.setdefault("magazine_fixture_receipts", []).append(record)
    try:
        need(button in ("main", "off") and type(duration) is int and 1 <= duration <= 1000,
             "invalid fixed magazine schedule")
        need(not getattr(checks, "_magazine_loadout_failed", False), "loadout prerequisite failed; shot unrun")
        need(not any(r.get("runtime") == "FAIL" and (r.get("case", "").endswith("god_disabled")
                     or r.get("case", "").endswith(("_floor_loadout", "_gear"))) for r in checks.rows),
             "recorded setup prerequisite failed; shot unrun")
        checks.clear_dummies()
        # Certify this requested direction itself; never inherit clear_dir's
        # exhausted-candidate fallback or a certificate from an older position.
        dd = direction
        tag = "fs-mag-" + str(len(checks.out["magazine_fixture_receipts"]))
        origin = actor(checks.gl("qa_poseframe", tag + "-origin"), expected=getattr(checks, "_magazine_expected", None))
        record["origin"] = origin
        points = offsets(dd)
        geometry_reads = read_batch(checks.g, [["near", 95]] + [
            ["rayhit", origin["x"], origin["y"], origin["x"] + p[0]*81/45,
             origin["y"] + p[1]*81/45] for p in points] + [["qa_poseframe", tag+"-geometry"]], origin)
        record["geometry_batch"] = geometry_reads
        actor(geometry_reads[-1], origin)
        nearby, rays = geometry_reads[0], geometry_reads[1:6]
        record.update(rays=rays, blockers=nearby)
        try:
            geometry(origin, points, rays, nearby)
        except FixtureError:
            from gamelab.bots import qa_firearms_magazine_navigation as navigation
            need(navigation.blocked(origin, points, rays, nearby), "invalid initial fan geometry")
            origin, dd, geometry_reads = navigation.prepare(checks, geometry_reads[-1], dd, tag, record,
                                                           sleep=sleep)
            points = offsets(dd)
            record.update(geometry_batch=geometry_reads, rays=geometry_reads[1:6], blockers=geometry_reads[0])
            # Keep the original final gate even after the selector's certificate.
            actor(geometry_reads[-1], origin)
            geometry(origin, points, geometry_reads[1:6], geometry_reads[0])
        origin = geometry_reads[-1]
        record["birth_origin"] = origin
        births = []
        record["births"] = births
        for dx, dy in points:
            births.append(checks.gl("spawn", DUMMY, dx, dy))
            sleep(.3)  # Same native fan spawn settling as plan_firearms.dummy.
        if refill:
            checks.top_up()
        before = read_batch(checks.g, [["near", 600, "target_dummy"], ["qa_poseframe", tag + "-pre"],
                                      ["givestacks", checks.CLIP, 0]], origin)
        need(len(before) == 3, "missing pre-shot batch")
        record["before"] = before
        hp0 = owned_hp(origin, before[1], births, points, before[0], True)
        clip0 = before[2].get("stacks")
        need(before[2].get("ok") is True and type(clip0) is int and clip0 > 0, "missing positive initial clip")
        center = births[2]
        target = (center["x"], center["y"] - 11)  # Source physical-ray height; pop circle contains its unit center.
        step = "/".join([str(duration), "0", "0", format(dd[0], ".6f"), format(dd[1], ".6f"), button])
        if collect is None:
            # qa_input_target imports input_sequence, which imports the rank hierarchy.
            from gamelab.bots.qa_input_target import collect
        tag = "fs-mag-%d-%d-%d-%d" % (origin["boots"], origin["player"], origin["frame"],
                                        len(checks.out["magazine_fixture_receipts"]))
        mark = len(checks.g.gl)
        record.update(input_dispatched=True, measurement="DISPATCH_ATTEMPTED_NO_EFFECT_CREDIT")
        accepted, after, released, primary = {}, None, None, None
        cleanup_errors = []
        try:
            accepted = checks.gl("inputtarget", tag, "-", *target, step)
            record["accepted"] = accepted
            need(accepted.get("ok") is True, "native cursor sequence refused before measurement")
            sleep(duration / 1000 + .2)  # Preserve fixed schedule and original observation delay.
            # Atomic native frame; collect only AFTER these causal effect reads.
            after = read_batch(checks.g, [["givestacks", checks.CLIP, 0], ["critprobe", 1, 400, "target_dummy"],
                                          ["near", 600, "target_dummy"], ["qa_poseframe", tag + "-post"], ["controller"]], before[1])
            record["after"] = after
        except Exception as exc:
            primary = exc
            record["primary_error"] = repr(exc)
        finally:
            try:
                locator = accepted if accepted.get("ok") is True else reconcile(checks.g, mark, tag, record)
                record["cursor"] = collect(checks.g, locator, [(duration, [button])])
            except Exception as exc:
                cleanup_errors.append("cursor observation: " + repr(exc))
            try:
                released = read_batch(checks.g, [["qa_poseframe", tag + "-released"], ["controller"]], before[1])
                record["released"] = released
                need(len(released) == 2 and idle(released[1]), "cleanup release is not idle")
                actor(released[0], before[1])
            except Exception as exc:
                cleanup_errors.append("release observation: " + repr(exc))
            record["cleanup_errors"] = cleanup_errors
        if primary is not None:
            raise FixtureError("primary " + repr(primary) + "; cleanup " + repr(cleanup_errors)) from primary
        need(not cleanup_errors, "cleanup observations failed: " + repr(cleanup_errors))
        need(type(after) is list and len(after) == 5 and len(released) == 2, "missing effect/release batch")
        need(after[2]["_t"] >= before[0]["_t"], "post HP delivery precedes pre HP")
        record["binding"] = shot_contract(before[1], after[3], released[0], accepted,
                                           record["cursor"], target, tag, [after[4], released[1]])
        hp1 = owned_hp(origin, after[3], births, points, after[2], False)
        need(all(hp1[i] <= hp0[i] for i in hp0), "target HP increased/identity changed")
        clip1 = after[0].get("stacks")
        need(after[0].get("ok") is True and type(clip1) is int and 0 <= clip1 <= clip0
             and after[1].get("ok") is True, "missing immediate clip/static effect snapshot")
        record["status"] = "VALID_FIXTURE_EFFECT_SEPARATELY_REQUIRED"
        record["measurement"] = "EFFECT_MEASURED"
        return {"clip": [clip0, clip1], "hp_before": {i: v/500 for i, v in hp0.items()},
                "hp_after": {i: v/500 for i, v in hp1.items()}, "actual_damage": sum(hp0[i]-hp1[i] for i in hp0),
                "stats": after[1], "button": button, "duration_ms": duration, "fixture": record}
    except Exception as exc:
        record.setdefault("primary_error", repr(exc))
        record.update(status="INVALID_UNRUN_OR_FAILED_FIXTURE", error=repr(exc))
        raise
