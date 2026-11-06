"""Pure checks for recorded Fury boss observations; no native execution on import."""
from collections import Counter
import math


def unit_id(value):
    return type(value) is int and value > 0


def roster_matches(rows, expected):
    """One observation per explicitly selected boss; empty/duplicate rosters refuse."""
    if (not rows or not expected or any(not isinstance(name, str) or not name for name in expected)
            or len(set(expected)) != len(expected)):
        return False
    observed = [row.get("boss") for row in rows]
    return (all(isinstance(name, str) and name for name in observed)
            and Counter(observed) == Counter(expected))


def target_matches(row):
    """A held sibling cannot establish effects for the requested unit."""
    requested = row.get("requested_id")
    picked = row.get("pick", {}).get("picked")
    held = row.get("held_id")
    cast_ids = row.get("cast_ids", [])
    if not unit_id(requested) or not unit_id(picked) or picked != requested:
        return False
    if held is None:
        return not cast_ids and bool(row.get("refused"))
    samples = row.get("hold_samples", [])
    return (unit_id(held) and held == requested and cast_ids == [requested]
            and all(unit_id(uid) for uid in cast_ids) and bool(samples)
            and all(unit_id(sample.get("holding")) and sample["holding"] == requested for sample in samples))


def motion_distance(row):
    """Maximum L1 movement of the actual held unit; missing reads supply no zero."""
    held = row.get("held_id")
    positions = row.get("positions", [])
    if not unit_id(held) or len(positions) < 2:
        return None
    for position in positions:
        if (not isinstance(position, dict) or position.get("unit") != held
                or any(type(position.get(axis)) not in (int, float)
                       or not math.isfinite(position[axis]) for axis in ("x", "y"))):
            return None
    origin = positions[0]
    return max(abs(position["x"] - origin["x"]) + abs(position["y"] - origin["y"])
               for position in positions[1:])


def nonpassive_casts(actor):
    """Observed IsCasting names, excluding passive and ambiguous channel-stop states.

    `actors` cannot read ChannelingBaseSkill.m_durationC, so a Channeling* name
    does not establish an active pre-cast channel. Its unsupported state is retained
    in the raw actor observation instead of receiving interruption credit.
    """
    names = actor.get("casting")
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        return []
    return [name for name in names if not any(kind in name for kind in ("Triggered", "Aura", "Channeling"))]


def precast_active_observed(row):
    actor = row.get("pre_actor", {})
    return (actor.get("unit") == row.get("requested_id") and actor.get("dead") is False
            and bool(nonpassive_casts(actor)))


def pre_active_then_suppressed(row):
    """Two sampled states, not causal interruption proof.

    The pre-cast skill may end naturally between console RPCs and the castpoint.
    Cancellation events tied to this actor/cast would be needed for stronger credit.
    """
    return target_matches(row) and precast_active_observed(row) and row.get("post_suppressed") is True


def held_fraction_ok(rows):
    """Ceiling of two thirds; one selected boss requires one actual hold."""
    return bool(rows) and sum(bool(row.get("held")) for row in rows) >= (2 * len(rows) + 2) // 3


def stays(row, limit=4):
    distance = motion_distance(row)
    return distance is not None and distance < limit
