"""Strict bounded native world-cursor input collector; no input or skill calls."""
import math

from gamelab.bots.qa_firearms_input_sequence import sequence_protocol

PHASE = "post_input_write_before_player_update; final neutral release restores cursor"
NUM_FIELDS = ("x", "y", "screen_x", "screen_y", "world_x", "world_y", "round_error",
              "actor_dir_x", "actor_dir_y", "cast_x", "cast_y", "cast_dir_x", "cast_dir_y",
              "manaExact", "hpExact")


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value):
    return type(value) is int


def validate(accepted, terminal, chunks, done, expected):
    try:
        base = sequence_protocol(accepted, terminal, done, expected)
    except (TypeError, ValueError, KeyError) as exc:
        return {"valid": False, "errors": ["malformed input sequence: " + repr(exc)], "samples": []}
    errors, samples = list(base["errors"]), []
    if not chunks or any(type(c) is not dict for c in chunks):
        return {"valid": False, "errors": errors + ["missing cursor trace"], "samples": [], "sequence": base}
    first = chunks[0]
    headers = ("id", "tag", "complete", "parts", "stored", "seen", "dropped", "truncated", "start", "end",
               "frames", "skill", "player", "target_x", "target_y", "cursor_restored", "error", "phase", "restore")
    parts, count = first.get("parts"), first.get("stored")
    if (not integer(parts) or not 1 <= parts <= 32 or len(chunks) != parts
            or not integer(count) or not 1 <= count <= 256 or parts != (count + 7)//8):
        errors.append("cursor chunk/count bounds mismatch")
    for index, chunk in enumerate(chunks):
        if (chunk.get("ev") != "inputtarget" or not integer(chunk.get("part")) or chunk.get("part") != index
                or any(chunk.get(k) != first.get(k) for k in headers)):
            errors.append("foreign/inconsistent/duplicate cursor chunk")
        rows = chunk.get("samples")
        if type(rows) is not list or not 1 <= len(rows) <= 8 or any(type(r) is not dict for r in rows):
            errors.append("invalid cursor sample chunk")
            continue
        samples.extend(rows)
    if (first.get("complete") is not True or first.get("error") != ""
            or first.get("truncated") is not False or not integer(first.get("dropped")) or first.get("dropped") != 0
            or not integer(first.get("seen")) or first.get("seen") != count or count != len(samples)
            or not integer(first.get("frames")) or count != first["frames"] + 1
            or first.get("frames") != terminal.get("frames")
            or first.get("id") != accepted.get("id") or first.get("tag") != accepted.get("tag")
            or type(accepted.get("id")) is not str or not accepted["id"]
            or type(accepted.get("tag")) is not str or not accepted["tag"]
            or type(accepted.get("skill")) is not str or not accepted["skill"]
            or not integer(accepted.get("player")) or accepted["player"] <= 0
            or first.get("skill") != accepted.get("skill") or first.get("player") != accepted.get("player")
            or first.get("start") != terminal.get("start") or first.get("end") != terminal.get("end")
            or first.get("phase") != PHASE or first.get("cursor_restored") is not True
            or any(not finite(first.get(k)) or not finite(accepted.get(k))
                   or abs(first[k]-accepted[k]) > .001 for k in ("target_x", "target_y"))):
        errors.append("incomplete/foreign cursor terminal/count/release")
    if not all(finite(first.get(k)) for k in ("target_x", "target_y")):
        return {"valid": False, "errors": errors + ["missing native world target"], "samples": samples, "sequence": base}
    times = []
    for row in samples:
        numeric = all(finite(row.get(k)) for k in NUM_FIELDS)
        ints = all(integer(row.get(k)) for k in ("now", "dt", "step", "buffer", "ct", "cd", "timeline"))
        if (not numeric or not ints or row.get("gamepad") is not False
                or type(row.get("release")) is not bool or not 0 < row.get("dt", 0) <= 100
                or not 0 <= row.get("buffer", -1) < 8 or row.get("manaExact", -1) < 0
                or row.get("hpExact", -1) <= 0):
            errors.append("invalid native cursor/actor/frame readback")
            continue
        actual = math.dist((row["world_x"], row["world_y"]), (first["target_x"], first["target_y"]))
        if (row["screen_x"] < 0 or row["screen_y"] < 0 or actual > .102
                or not 0 <= row["round_error"] <= .101 or abs(actual-row["round_error"]) > .002):
            errors.append("native world-cursor roundtrip mismatch")
        times.append(row["now"])
    if len(times) != len(samples) or any(b <= a or b-a > 100 for a, b in zip(times, times[1:])):
        errors.append("native cursor frame clocks not strictly consecutive")
    action = [r for r in samples if r.get("release") is False]
    release = [r for r in samples if r.get("release") is True]
    if (len(action) != terminal.get("frames") or len(release) != 1 or not samples
            or samples[-1] is not release[0] or release[0].get("step") != len(expected)
            or not integer(first.get("end")) or release[0].get("now", first.get("end", 0)) >= first.get("end", 0)):
        errors.append("cursor neutral-release frame missing or misplaced")
    for index, step in enumerate(base["steps"]):
        rows = [r for r in action if r.get("step") == index]
        if (len(rows) != step.get("frames") or not rows or rows[0].get("now") != step.get("first_write")
                or rows[-1].get("now") != step.get("last_write")
                or not all(integer(r.get("dt")) for r in rows)
                or sum(r.get("dt", 0) for r in rows) != step.get("actual_ms")):
            errors.append("cursor frame group differs from exact native input step")
    receipts = first.get("restore")
    if type(receipts) is not list or not 1 <= len(receipts) <= 8:
        errors.append("missing bounded cursor restoration receipts")
    else:
        for index, receipt in enumerate(receipts):
            if (type(receipt) is not dict or not integer(receipt.get("buffer"))
                    or receipt.get("buffer") != index or receipt.get("restored") is not True
                    or type(receipt.get("owned_last_value")) is not bool
                    or type(receipt.get("already_neutral")) is not bool
                    or not (receipt["owned_last_value"] or receipt["already_neutral"])
                    or not all(finite(receipt.get(k)) for k in ("before_x", "before_y", "original_x", "original_y"))):
                errors.append("invalid native cursor restoration receipt")
                continue
            matching = [r for r in samples if r.get("buffer") == index]
            if not matching:
                errors.append("restored input handle has no owned frame")
                continue
            before = (receipt["before_x"], receipt["before_y"])
            original = (receipt["original_x"], receipt["original_y"])
            last = (matching[-1].get("screen_x"), matching[-1].get("screen_y"))
            if not all(finite(v) for v in last):
                errors.append("invalid last owned screen point")
                continue
            if (receipt["owned_last_value"] and math.dist(before, last) > .012
                    or receipt["already_neutral"] and math.dist(before, original) > .012):
                errors.append("cursor restoration differs from last owned/original point")
        if any(not integer(r.get("buffer")) or not 0 <= r["buffer"] < len(receipts) for r in samples):
            errors.append("native cursor sample has no restoration receipt")
    return {"valid": not errors, "errors": errors, "samples": samples, "chunks": chunks,
            "sequence": base, "terminal": terminal, "accepted": accepted, "input_done": done,
            "scope": "One native writer, exact button frames, world cursor projection and restore; ability effect is separately required."}


def collect(game, accepted, expected, timeout=20):
    tag, ident = accepted.get("tag"), accepted.get("id")
    first = game.wait_gl(lambda e: e.get("ev") == "inputtarget" and e.get("tag") == tag
                         and e.get("id") == ident and e.get("part") == 0, timeout) or {}
    parts = first.get("parts")
    if integer(parts) and 1 <= parts <= 32:
        for index in range(1, parts):
            game.wait_gl(lambda e: e.get("ev") == "inputtarget" and e.get("tag") == tag
                         and e.get("id") == ident and e.get("part") == index, 5)
    chunks = [e for e in game.gl if e.get("ev") == "inputtarget" and e.get("tag") == tag]
    terminal = game.wait_gl(lambda e: e.get("ev") == "inputsequence" and e.get("tag") == tag
                            and e.get("id") == ident, 5) or {}
    done = [e for e in game.gl if e.get("ev") == "input_done" and e.get("sequence") == tag]
    return validate(accepted, terminal, chunks, done, expected)
