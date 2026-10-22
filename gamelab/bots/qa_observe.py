"""Collect bounded native buffobserve chunks without treating partial data as proof."""


def collect(game, tag, timeout=75):
    first = game.wait_gl(lambda row: row.get("ev") == "buffobserve" and row.get("tag") == tag
                         and row.get("part") == 0, timeout)
    if first is None:
        return {"tag": tag, "complete": False, "usable": False,
                "errors": ["missing native observer part0"], "events": []}
    errors, chunks = [], [first]
    parts = first.get("parts", 0)
    if not isinstance(parts, int) or not 1 <= parts <= 4:
        return {**first, "complete": False, "usable": False,
                "errors": ["invalid observer part count"], "events": first.get("events", [])}
    for index in range(1, parts):
        chunk = game.wait_gl(lambda row: row.get("ev") == "buffobserve" and row.get("tag") == tag
                            and row.get("part") == index, 10)
        if chunk is None:
            errors.append(f"missing native observer part{index}")
            break
        chunks.append(chunk)
    fields = ("parts", "stored", "seen", "dropped", "truncated", "start", "end", "ms", "frames",
              "buff", "stack", "target_unit")
    events = []
    for index, chunk in enumerate(chunks):
        if chunk.get("part") != index or any(chunk.get(key) != first.get(key) for key in fields):
            errors.append(f"inconsistent observer header at part{index}")
        rows = chunk.get("events", [])
        if not isinstance(rows, list) or len(rows) > 16:
            errors.append(f"invalid observer chunk size at part{index}")
            continue
        events.extend(rows)
    stored, seen, dropped = (first.get(key) for key in ("stored", "seen", "dropped"))
    if not all(isinstance(n, int) and n >= 0 for n in (stored, seen, dropped)):
        errors.append("invalid observer event counts")
    elif not (len(events) == stored <= 64 and seen == stored + dropped
              and bool(first.get("truncated")) == (dropped > 0)):
        errors.append("observer count/truncation proof mismatch")
    if (not events or events[0].get("reason") != "initial"
            or not events[-1].get("reason", "").startswith("final")):
        errors.append("observer initial/final snapshots missing")
    for before, after in zip(events, events[1:]):
        if (not isinstance(before.get("now"), int) or not isinstance(after.get("now"), int)
                or after["now"] < before["now"] or after.get("elapsed", -1) < before.get("elapsed", 0)):
            errors.append("observer timestamps not monotonic")
            break
    return {**first, "events": events, "complete": not errors,
            "usable": not errors and not first.get("truncated"), "errors": errors}
