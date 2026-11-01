"""Pure guards for the solo-pistol input protocol's actual target and cursor.

Combat.as AimAtCursor aims from feet-(0,11); glock_round.unit draws its
collision path11px high. Pin the visible target body11px above its collision
center so the physical ray crosses the dummy's circle, rather than below it.
These checks grant no hit credit: actual native HP/ammo events remain required.
"""
import math

AIM_HEIGHT = 11
TARGET = "doodads/generic/target_dummy_normal.unit"


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def target_body_cursor(state, nearby, target_id, direction):
    errors = []
    state = state if type(state) is dict else {}
    nearby = nearby if type(nearby) is dict else {}
    player = state.get("player") if type(state.get("player")) is dict else {}
    units = nearby.get("units", [])
    rows = [r for r in units if type(r) is dict and r.get("unit") == target_id] if type(units) is list else []
    target = rows[0] if len(rows) == 1 else {}
    if (state.get("ok") is not True or state.get("phase") != "mission"
            or player.get("spawned") is not True or player.get("dead") is not False
            or not all(finite(player.get(k)) for k in ("x", "y"))):
        errors.append("missing actual live shooter position")
    if (nearby.get("ok") is not True or type(nearby.get("truncated")) not in (int, bool)
            or nearby.get("truncated") != 0 or type(target_id) is not int or target_id <= 0
            or len(rows) != 1 or target.get("name") != TARGET
            or target.get("dead") is not False or target.get("hpMax") != 10000000
            or target.get("hpExact") != 10000000
            or not all(finite(target.get(k)) for k in ("x", "y"))):
        errors.append("missing unique full-health actual normal dummy")
    if (type(direction) not in (list, tuple) or len(direction) != 2
            or not all(finite(v) for v in direction) or abs(math.hypot(*direction) - 1) > .002):
        errors.append("invalid requested shot direction")
    if errors:
        return {"valid": False, "errors": errors, "target": target}
    expected = (player["x"] + 80 * direction[0], player["y"] + 80 * direction[1])
    if math.dist(expected, (target["x"], target["y"])) > .3:
        errors.append("dummy differs from requested80px clear line")
    return {"valid": not errors, "errors": errors, "target": target,
            "world": (target["x"], target["y"] - AIM_HEIGHT),
            "shooter": (player["x"], player["y"]), "source_height": AIM_HEIGHT}


def cursor_binding(accepted, cursor, requested_world):
    """Bind the strict native collector to this consumer's external request."""
    errors = []
    accepted = accepted if type(accepted) is dict else {}
    cursor = cursor if type(cursor) is dict else {}
    if (type(requested_world) not in (tuple, list) or len(requested_world) != 2
            or not all(finite(v) for v in requested_world)):
        return {"valid": False, "errors": ["missing requested body point"]}
    if (accepted.get("ok") is not True or accepted.get("skill") != "-"
            or type(accepted.get("id")) is not str or not accepted["id"]
            or type(accepted.get("tag")) is not str or not accepted["tag"]
            or type(accepted.get("player")) is not int or accepted["player"] <= 0
            or not all(finite(accepted.get(k)) for k in ("target_x", "target_y"))
            or math.dist((accepted.get("target_x", 1e9), accepted.get("target_y", 1e9)), requested_world) > .001):
        errors.append("native pin differs from requested body point or actor")
    sequence = cursor.get("sequence") if type(cursor.get("sequence")) is dict else {}
    if cursor.get("valid") is not True or sequence.get("valid") is not True:
        errors.append("strict native cursor/input/restore contract failed")
    for row in (cursor.get("accepted", {}), cursor.get("terminal", {})):
        if type(row) is not dict or any(row.get(k) != accepted.get(k) for k in ("id", "tag", "player")):
            errors.append("foreign native cursor sequence identity")
    samples = cursor.get("samples")
    if (type(samples) is not list or not 2 <= len(samples) <= 256
            or any(type(r) is not dict or r.get("gamepad") is not False
                   or not all(finite(r.get(k)) for k in ("world_x", "world_y"))
                   or math.dist((r["world_x"], r["world_y"]), requested_world) > .102 for r in samples)):
        errors.append("native cursor readback differs from requested body point")
    chunks = cursor.get("chunks", [])
    receipts = chunks[0].get("restore") if type(chunks) is list and chunks and type(chunks[0]) is dict else None
    if (type(receipts) is not list or not receipts
            or any(type(r) is not dict or r.get("restored") is not True
                   or not (r.get("owned_last_value") is True or r.get("already_neutral") is True) for r in receipts)):
        errors.append("missing owned native cursor restoration")
    return {"valid": not errors, "errors": errors, "requested_world": requested_world}
