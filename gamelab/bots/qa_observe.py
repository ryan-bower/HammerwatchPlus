"""Bounded native observer retention, endpoint-clock and identity contracts.

Semantic transitions and every-frame Actor samples remain distinct. An optional
expected mapping binds known request identity; consumers still prove effects.
"""


def _matches(row, event, tag, part=None):
    return (type(row) is dict and row.get("ev") == event and row.get("tag") == tag
            and (part is None or type(row.get("part")) is int and row["part"] == part))


def validate(chunks, event, tag, expected=None):
    """Validate completed retained chunks; raw chunks remain available on failure."""
    first = chunks[0] if type(chunks) is list and chunks and type(chunks[0]) is dict else {}
    errors, rows = [], []

    def result():
        return {**first, "chunks": chunks, "events": rows, "complete": not errors,
                "usable": not errors, "errors": errors}

    actor = event == "actorbuffobserve"
    if event not in ("buffobserve", "actorbuffobserve") or type(tag) is not str or not 1 <= len(tag) <= 64:
        errors.append("unsupported observer or invalid tag")
        return result()
    cap, maximum_parts, field = (1024, 64, "samples") if actor else (64, 4, "events")
    integers = ("parts", "stored", "seen", "dropped", "start", "end", "ms", "frames")
    identity = ("buff", "unit") if actor else ("buff", "stack", "target_unit")
    if (not first or any(type(first.get(k)) is not int for k in integers)
            or type(first.get("truncated")) is not bool
            or not 1 <= first.get("parts", 0) <= maximum_parts
            or not 2 <= first.get("stored", 0) <= cap
            or not 0 <= first.get("start", -1) < first.get("end", -1)
            or first.get("ms", 0) < 100 or first.get("frames", 0) < 1
            or first.get("dropped", -1) < 0
            or any(type(first.get(k)) is not str or not first[k] for k in identity if k not in ("unit", "target_unit"))
            or type(first.get("unit" if actor else "target_unit")) is not int
            or (first.get("unit", 0) <= 0 if actor else first.get("target_unit", 0) not in (-1,) and first.get("target_unit", 0) <= 0)):
        errors.append("missing or malformed observer header")
        return result()
    stored, seen, dropped, parts = (first[k] for k in ("stored", "seen", "dropped", "parts"))
    if (parts != (stored + 15)//16 or len(chunks) != parts or seen != stored + dropped
            or first["truncated"] != (dropped > 0)
            or (seen != first["frames"] + 1 if actor else seen > first["frames"] + 1)):
        errors.append("observer part/count/frame retention mismatch")
    if first["truncated"] or dropped:
        errors.append("observer dropped native observations")
    headers = (*integers, "truncated", *identity)
    for index, chunk in enumerate(chunks):
        if (not _matches(chunk, event, tag, index)
                or any(type(chunk.get(k)) is not type(first[k]) or chunk.get(k) != first[k] for k in headers)):
            errors.append("foreign, duplicate or inconsistent observer chunk")
            continue
        values = chunk.get(field)
        if type(values) is not list or len(values) != min(16, stored - index*16):
            errors.append("invalid observer chunk size")
            continue
        for row in values:
            clock = type(row) is dict and all(type(row.get(k)) is int for k in ("now", "elapsed"))
            shape = (clock and (type(row.get("dt")) is int and type(row.get("final")) is bool
                                and type(row.get("valid")) is bool if actor else
                                type(row.get("reason")) is str and bool(row["reason"])
                                and all(type(row.get(k)) is bool for k in ("player_valid", "target_valid", "buff_on"))))
            if not shape:
                errors.append("malformed observer row")
                continue
            rows.append(row)
            unit = "unit" if actor else "target_unit"
            if type(row.get(unit)) is not int or row[unit] != first[unit]:
                errors.append("foreign observer sample target")
            if not first["start"] <= row["now"] <= first["end"] or not 0 <= row["elapsed"] <= first["ms"]:
                errors.append("observer sample clock outside header")
    if len(rows) != stored:
        errors.append("missing retained observer rows")
    if (not rows or rows[0]["now"] != first["start"] or rows[0]["elapsed"] != 0
            or rows[-1]["now"] != first["end"] or rows[-1]["elapsed"] != first["ms"]):
        errors.append("observer initial/final clocks differ from header")
    if rows:
        if actor:
            if (rows[0]["dt"] != 0 or rows[-1]["final"] is not True
                    or any(row["final"] is not False for row in rows[:-1])):
                errors.append("actor initial/final frame proof missing")
        elif (rows[0]["reason"] != "initial" or not rows[-1]["reason"].startswith("final")
              or any(row["reason"] == "initial" or row["reason"].startswith("final") for row in rows[1:-1])):
            errors.append("semantic initial/final proof missing")
    for before, after in zip(rows, rows[1:]):
        if after["now"] < before["now"] or after["elapsed"] < before["elapsed"]:
            errors.append("observer timestamps not monotonic")
        if actor and (after["dt"] <= 0 or after["elapsed"] - before["elapsed"] != after["dt"]
                      or not 0 <= after["now"] - before["now"] <= after["dt"] + 1):
            errors.append("actor native-frame continuity mismatch")
    if expected is not None:
        if type(expected) is not dict or not expected or any(k not in identity for k in expected):
            errors.append("invalid expected request identity")
        elif any(type(value) is not type(first[k]) or value != first[k] for k, value in expected.items()):
            errors.append("observer differs from requested identity")
    return result()


def _collect(game, event, tag, timeout, expected):
    first = game.wait_gl(lambda row: _matches(row, event, tag, 0), timeout)
    chunks = [] if first is None else [first]
    count = first.get("parts") if type(first) is dict else None
    maximum_parts = 64 if event == "actorbuffobserve" else 4
    if type(count) is int and 1 <= count <= maximum_parts:
        for index in range(1, count):
            chunk = game.wait_gl(lambda row: _matches(row, event, tag, index),
                                 10 if event == "buffobserve" else 3)
            if chunk is None:
                break
            chunks.append(chunk)
    # wait_gl searches retained history. Inspect every already-retained chunk
    # with this identity so duplicate part0 cannot silently impersonate one run.
    history = getattr(game, "gl", None)
    if type(history) is list:
        retained = [row for row in history if _matches(row, event, tag)]
        if retained:
            chunks = retained
    return validate(chunks, event, tag, expected)


def collect(game, tag, timeout=75, *, expected=None):
    return _collect(game, "buffobserve", tag, timeout, expected)


def collect_trace(game, event, tag, timeout, *, expected=None):
    observed = _collect(game, event, tag, timeout, expected)
    return {"valid": observed["usable"], "parts": observed["chunks"], "samples": observed["events"],
            "errors": observed["errors"], "completeness": {"retention_clock_identity": observed["usable"]}}
