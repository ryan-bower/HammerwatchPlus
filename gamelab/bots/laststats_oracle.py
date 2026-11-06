"""UNEXECUTED QA-only LastStats consumer oracle draft.

Pure data only: no bot, game, file, process, input or platform imports.
The native adapter remains an explicit separate integration design. This does
not independently validate the producer's numeric raw counters: native end UI
validates formatted text; numeric snapshot values are inputs to the bar oracle.
English / ASCII search and at most four distinct display names are bounded here.
"""

from struct import pack, unpack
from collections import Counter


def f32(value):
    return unpack("<f", pack("<f", value))[0]


def bar_width(value, largest):
    # AS casts both ints to float, then each arithmetic operation is float32.
    if value <= 0 or largest <= 0:
        return 1
    scaled = f32(f32(150.0) * f32(value))
    ratio = f32(scaled / f32(largest))
    return max(2, int(f32(ratio + f32(.5))))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def lines_of(snap, legacy=False):
    require(isinstance(snap, dict), "missing snapshot")
    require(isinstance(snap.get("player"), str) and snap["player"], "blank player")
    require(type(snap.get("peer")) is int, "invalid peer")
    require(type(snap.get("state")) is int, "invalid state")
    require(isinstance(snap.get("mission"), str) and snap["mission"], "blank mission")
    lines = snap.get("lines")
    require(isinstance(lines, list) and type(snap.get("count")) is int
            and snap["count"] == len(lines), "line count mismatch")
    seen = set()
    for line in lines:
        require(isinstance(line, dict), "invalid line")
        fields = set(line)
        require(fields == {"cat", "title", "text", "value"}
                or (legacy and fields == {"cat", "title", "text"}), "line schema")
        require(all(isinstance(line.get(k), str) and line[k]
                    for k in ("cat", "title", "text")), "blank line text")
        require("|" not in line["cat"] and "|" not in line["title"], "ambiguous key")
        require(line["title"].isascii(), "search locale outside bounded oracle")
        require("value" not in line or type(line["value"]) is int
                and -(2**31) <= line["value"] < 2**31, "invalid raw value")
        key = (line["cat"], line["title"])
        require(key not in seen, "duplicate snapshot stat key")
        seen.add(key)
    return lines


def snapshot_assertions(snap, native, state, name):
    """Retain independent native MissionEnd formatted values; raw value is typed only."""
    lines = lines_of(snap)
    require(snap["state"] == state and snap["player"] == name and len(lines) >= 2,
            "snapshot identity/state or insufficient measured rows")
    require(isinstance(native, dict) and isinstance(native.get("headers"), list)
            and isinstance(native.get("rows"), list), "missing independent native UI")
    headers = dict(native["headers"])
    require(len(headers) == len(native["headers"]), "duplicate native category")
    require(all(line["cat"] in headers for line in lines), "unknown snapshot category")
    for r in native["rows"]:
        require(isinstance(r, dict) and r.get("cat") in headers
                and r.get("category_text") == headers[r["cat"]]
                and all(isinstance(r.get(k), str) and r[k] for k in ("cat", "title", "text")),
                "malformed independent native row")
    expected = Counter((r["cat"], r["title"], r["text"]) for r in native["rows"]
                       if r["cat"] != "skill_dmg")
    actual = Counter((r["cat"], r["title"], r["text"]) for r in lines)
    require(actual == expected, "native formatted values differ")
    return {"formatted_rows": len(lines), "raw_value_scope": "typed snapshot input only"}


def union_of(party, local_name, legacy=False):
    """Expected UI from input snapshots; preserve source's local-first/category order."""
    require(isinstance(party, list) and len(party) <= 4, "unbounded party")
    names = []
    for snap in party:
        lines_of(snap, legacy)
        names.append(snap["player"])
    require(len(set(names)) == len(names), "same-name identity outside oracle scope")
    ordered = [s for s in party if s["player"] == local_name]
    ordered += [s for s in party if s["player"] != local_name]
    # Dict insertion order gives first category appearance, then first stat in it.
    # Expectations are derived from snapshots, never from observed row ids/text.
    categories = {}
    for p, snap in enumerate(ordered):
        for line in snap["lines"]:
            stats = categories.setdefault(line["cat"], {})
            row = stats.setdefault(line["title"], {"cat": line["cat"],
                "title": line["title"], "cells": [None] * len(ordered)})
            row["cells"][p] = line
    return ordered, [r for stats in categories.values() for r in stats.values()]


def children(reply, depth):
    require(isinstance(reply, dict) and reply.get("ok") is True, "children RPC failed")
    require(type(reply.get("visible")) is bool, "missing parent visibility")
    nodes = reply.get("nodes")
    require(isinstance(nodes, list) and len(nodes) < 60, "missing or possibly capped60 tree")
    for n in nodes:
        require(isinstance(n, dict) and type(n.get("depth")) is int
                and 1 <= n["depth"] <= depth and isinstance(n.get("id"), str)
                and isinstance(n.get("type"), str) and type(n.get("visible")) is bool
                and isinstance(n.get("caption"), str), "malformed node")
        require(all(type(n.get(k)) is int for k in ("x", "y", "w", "h")), "bad geometry")
    return nodes


def unique(nodes):
    require(len({n["id"] for n in nodes}) == len(nodes), "duplicate sibling id")
    return {n["id"]: n for n in nodes}


def split_row(reply):
    nodes = children(reply, 2)
    direct, nested, parent = [], {}, None
    for n in nodes:
        if n["depth"] == 1:
            direct.append(n)
            parent = n["id"]
            nested[parent] = []
        else:
            require(parent is not None, "orphan nested row child")
            nested[parent].append(n)
    return unique(direct), {k: unique(v) for k, v in nested.items()}


def board_assertions(party, local_name, category_text, labels, observed, query="", legacy=False, tab=None):
    """Raise on any missing/mismatched consumer; return a concise data-only receipt.

    Tabs (issue #98): one per category in row order; `tab` is the open one (default:
    the first). An empty query shows the open tab's rows and no category header or
    separator; a query shows every tab's matching rows under their headers.

    observed: header=wtext(subtitle), legend=wchildren(legend,1),
    list=wchildren(stat-group,1), siblings=wchildren(^empty,1),
    rows={stat-N:wchildren(stat-N,2)}. Adapter must bracket exact window, stable
    snapshot and unchanged input query around reads and retain all raw replies.
    Search visibility is local m_visible, not a claim of viewport/pixel exposure.
    """
    require(isinstance(query, str) and query.isascii(), "unsupported query")
    ordered, rows = union_of(party, local_name, legacy)
    normalized = query.lower().strip(" ")
    tabs = list(dict.fromkeys(r["cat"] for r in rows))
    if tab is None:
        tab = tabs[0] if tabs else ""
    require(tab in tabs or (not tabs and tab == ""), "unknown open tab")
    if normalized:
        shown = [normalized in r["title"].lower() for r in rows]
    else:
        shown = [r["cat"] == tab for r in rows]
    header = observed["header"]
    expected_subtitle = (ordered[0]["mission"] + " - " + str(len(ordered)) + " player(s)") if ordered else ""
    require(header.get("ok") is True and header.get("window") == "HWPLastStatsMenu"
            and header.get("missing") == "" and header.get("truncated") is False
            and header.get("texts") == {"subtitle": expected_subtitle}, "board header")
    legend = children(observed["legend"], 1)
    require(observed["legend"]["visible"] is True and len(legend) == len(ordered), "legend count")
    unique(legend)
    for p, snap in enumerate(ordered):
        n = legend[p]
        require(n["id"] == "legend-" + str(p) and n["type"] == "TextWidget"
                and n["visible"] is True and snap["state"] in labels
                and n["caption"] == snap["player"] + " (" + labels[snap["state"]] + ")", "legend identity/result")
    siblings = unique(children(observed["siblings"], 1))
    require(observed["siblings"]["visible"] is True, "list container hidden")
    require("empty" in siblings and "nomatch" in siblings
            and siblings["empty"]["visible"] is (not ordered)
            and siblings["nomatch"]["visible"] is (bool(rows) and not any(shown)), "empty/nomatch visibility")
    require(siblings["empty"]["caption"] == "No run recorded yet. Finish (or abandon) an expedition and come back."
            and siblings["nomatch"]["caption"] == "No stat matches the search.", "empty/nomatch text")
    roots = children(observed["list"], 1)
    require(observed["list"]["visible"] is True, "stat group hidden")
    unique(roots)
    expected_roots = []
    previous = None
    cats_shown = {r["cat"] for r, show in zip(rows, shown) if show} if normalized else set()
    for i, row in enumerate(rows):
        if row["cat"] != previous:
            if previous is not None:
                expected_roots.append(("sep-" + row["cat"], row["cat"] in cats_shown))
            expected_roots.append(("cat-" + row["cat"], row["cat"] in cats_shown))
            previous = row["cat"]
        expected_roots.append(("stat-" + str(i), shown[i]))
    require([(n["id"], n["visible"]) for n in roots] == expected_roots, "union/order/filter/category visibility")
    require(set(observed["rows"]) == {"stat-" + str(i) for i in range(len(rows))}, "missing/extra row reads")
    for n in roots:
        if n["id"].startswith("cat-"):
            cat = n["id"][4:]
            require(cat in category_text and n["type"] == "TextWidget"
                    and n["caption"] == category_text[cat], "category caption")
    positive = 0
    for i, row in enumerate(rows):
        wid = "stat-" + str(i)
        reply = observed["rows"][wid]
        require(reply.get("visible") is shown[i], "row parent visibility")
        direct, nested = split_row(reply)
        barids = ["bar-" + str(i) + "-" + str(p) for p in range(len(ordered))]
        require(set(direct) == {"stat-bg", "stat-title-" + str(i), "bar-template", *barids}, "row structure")
        title = direct["stat-title-" + str(i)]
        require(title["type"] == "TextWidget" and title["visible"] is True
                and title["caption"] == row["title"], "stat title")
        require(direct["stat-bg"]["visible"] is (i % 2 == 1)
                and direct["bar-template"]["visible"] is False, "template/background visibility")
        require(not nested["stat-bg"] and not nested["stat-title-" + str(i)]
                and set(nested["bar-template"]) == {"bar-name", "bar", "bar-value"}, "template structure")
        values = [c.get("value", 0) if c is not None else 0 for c in row["cells"]]
        largest = max([0] + values)
        for p, snap in enumerate(ordered):
            line = direct[barids[p]]
            cells = nested[barids[p]]
            nameid, valueid = "bar-name-" + str(i) + "-" + str(p), "bar-value-" + str(i) + "-" + str(p)
            require(line["visible"] is True and set(cells) == {nameid, "bar", valueid}, "bar line structure")
            cell = row["cells"][p]
            text = cell["text"] if cell is not None else "-"
            require(cells[nameid]["type"] == "TextWidget" and cells[nameid]["visible"] is True
                    and cells[nameid]["caption"] == snap["player"]
                    and cells[valueid]["type"] == "TextWidget" and cells[valueid]["visible"] is True
                    and cells[valueid]["caption"] == text, "per-player formatted value")
            value = values[p]
            width = bar_width(value, largest)
            bar = cells["bar"]
            require(bar["type"] == "RectWidget" and bar["w"] == width
                    and bar["h"] == 8 and bar["visible"] is (value > 0), "bar width/visibility")
            positive += int(shown[i] and value > 0)
    return {"rows": len(rows), "shown": sum(shown), "players": len(ordered), "tab": tab, "tabs": len(tabs),
            "visible_bar_lines": sum(shown) * len(ordered), "positive_rectangles": positive,
            "query": normalized, "scope": "local-widget-state/geometry, not rendered pixels or raw producer correctness"}
