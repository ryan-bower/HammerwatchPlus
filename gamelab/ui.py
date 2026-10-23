"""Scenario steps that use the game's UI as a human does: aim at a widget, then hover or
click it with the emulated mouse (gamelab-hands `pointer`: GameInput.MousePos and the left
button as MenuInput.Forward, written into the engine's own input objects; the real cursor
never moves and nothing is focused), and console lines whose reply is read from the log
written after them.

  {"do": "click", "widget": "<id>", "n": 0}              aimed with `gl clickables top <id>`
  {"do": "click", "widget": "<id>", "root": "HUD:HUDBuffs"}   aimed with `gl widgets`
  {"do": "click", "x": 320, "y": 180}                     game window pixels
  {"do": "click", "dock": "<id>"}                          a Dev Arena dock button (`gl da-dock <id>`)
  {"do": "hover", ...the same targets...}
  {"do": "console", "line": "hwp help", "expect": "<regex>", "lacks": "<regex>"}

A click: the pointer to the widget's centre (a window hit-tests only on a frame the mouse
moved, WindowInput::UpdateMouseInputs), the game's view read back (`verify`, default on:
the engine kept the position and the top window hovers that widget), then the button down
and up (`gl pointer ... click`: the window must take both), and `after` s for the handler
to run. The left button is
MenuForward in the kbm map (res/controls_default.cfg:31), which the top window turns into
ClickDown/ClickUp on the hovered widget (GUI/WindowObject.as:96-139).

Posted WM_MOUSEMOVE / WM_LBUTTONDOWN do not reach the game (ui-click 20261018-055552: its
mouse stayed at 0,0 while the messages were posted at 302,225).

`gl press <id>` (gamelab-hands) is the other way in: the widget's own handlers called
directly, no mouse. A scenario that needs "a human clicks it" uses `click`.
"""
from __future__ import annotations

import json
import re
import time

STEPS = ("click", "hover")
NO_ID = "__gamelab_no_widget__"     # a clickables filter nothing matches: the reply is just its screen block
ECHO = re.compile(r"^\[\w+\] \[[\d:]+\] > ")     # the console's echo of a typed line


def _fail(why: str) -> dict:
    return {"found": False, "why": why}


def locate(game, s: dict) -> dict:
    """Where to point: {"found", "px", "py" (game pixels), "target", "screen", "why"}."""
    if "x" in s and "y" in s:
        r = game.gl_cmd("clickables", "top", NO_ID)     # only for its screen block
        return {"found": True, "px": int(s["x"]), "py": int(s["y"]), "target": None, "screen": r.get("screen")}
    if "dock" in s:
        # mods/devarena draws its dock itself, so it is not a widget; it lists its own buttons
        r = game.gl_cmd("da-dock", s["dock"])
        at = (r.get("buttons") or {}).get(s["dock"])
        if not at:
            return _fail(f"no dock button {s['dock']!r} (open={r.get('open')}, tab={r.get('tab')!r})")
        return {"found": True, "px": int(at[0]), "py": int(at[1]), "target": {"id": s["dock"]}, "screen": None,
                "via": "dock"}
    wid, n = s["widget"], int(s.get("n", 0))
    if "root" not in s:
        r = game.gl_cmd("clickables", "all" if s.get("any_window") else "top", wid)
        items = r.get("items", [])
        if len(items) > n:
            it = items[n]
            return {"found": True, "px": it["px"], "py": it["py"], "target": it, "screen": r.get("screen"),
                    "via": "clickables", "top": r.get("top")}
        if s.get("clickables_only"):
            return {**_fail(f"no clickable {wid!r} #{n} in the top window {r.get('top')!r} ({len(items)} with that id)"),
                    "screen": r.get("screen")}
    # only the named root: every tree at depth 14 can outgrow a log line (Probe.as WIDGET_BYTES)
    r = game.gl_cmd("widgets", s.get("depth", 14), *([s["root"]] if s.get("root") else []),
                    timeout=s.get("timeout", 20))
    hits = []
    for root in r.get("roots", []):
        if s.get("root") and root.get("root") != s["root"]:
            continue
        hits += [{**node, "root": root.get("root")} for node in root.get("nodes", []) if node.get("id") == wid]
    if len(hits) > n:
        it = hits[n]
        return {"found": True, "px": it["px"], "py": it["py"], "target": it, "screen": r.get("screen"), "via": "widgets"}
    return {**_fail(f"no widget {wid!r} #{n}" + (f" under {s['root']!r}" if s.get("root") else "")
                    + f" ({len(hits)} found, widgets truncated={r.get('truncated')})"), "screen": r.get("screen")}


def step(run, game, s: dict, saved: dict) -> None:
    kind = s["do"]
    label = s.get("name") or f"{kind} {s.get('widget') or s.get('dock') or (s.get('x'), s.get('y'))}"
    at = locate(game, s)
    if not at["found"]:
        run.assert_(label, False, at["why"])
        return
    verify = s.get("verify", True)
    want = (at.get("target") or {}).get("id") if at.get("via") == "clickables" else None
    mv = game.gl_cmd("pointer", at["px"], at["py"], "move", timeout=s.get("timeout", 10))
    # the engine kept the position we wrote, and the top window hovers the aimed clickable
    hovered = mv.get("hovered")
    ok = bool(mv.get("ok")) and (not verify or (mv.get("posKept") and (want is None or hovered == want)))
    ck = {}
    if kind == "click" and (ok or s.get("click_anyway")):
        ck = game.gl_cmd("pointer", at["px"], at["py"], "click", timeout=s.get("timeout", 10))
        # a press left over from before the click (source open: docs/RE_NOTES.md, stray presses)
        # is fine once the click let go of it first (letGo, HandsUi.as PointerPost)
        ok = ok and bool(ck.get("ok")) and (not verify or (ck.get("downSeen") and ck.get("upSeen")
                                                           and not (ck.get("pressedBefore") and not ck.get("letGo"))))
        time.sleep(s.get("after", 0.3))
    detail = {"at": [at["px"], at["py"]], "target": at.get("target"), "via": at.get("via"),
              "move": {k: mv.get(k) for k in ("posKept", "mouseX", "mouseY", "hovered", "top", "error")},
              "click": {k: ck.get(k) for k in ("pressedBefore", "letGo", "downSeen", "upSeen", "strays", "topAfter", "error")}
              if ck else None}
    if "save_as" in s:
        saved[s["save_as"]] = {"ok": ok, **detail}
    if not ok:
        if not mv.get("ok"):
            why = f"pointer failed: {mv.get('error')}"
        elif not mv.get("posKept"):
            why = "the engine did not keep the pointer position"
        elif want is not None and hovered != want:
            why = f"the top window hovers {hovered!r}, not {want!r}"
        else:
            why = "the top window did not take the press and release (ClickDown / ClickUp)"
        run.assert_(label, False, why + " | " + json.dumps(detail))
        return
    run.assert_(label, True, json.dumps(detail))


def console(run, game, s: dict, saved: dict) -> None:
    """A console line; with `expect` / `lacks`, its reply is matched against only the log
    written after it was typed (the echo of typed lines left out), waited up to `timeout`."""
    start = len(game.read_log())
    game.console(s["line"])
    if "expect" not in s and "lacks" not in s:
        return
    # per log line: "$" ends a line, not the whole text read so far
    rx = re.compile(s["expect"], re.M) if "expect" in s else None
    t0 = time.time()
    end = t0 + s.get("timeout", 10)
    hit, text = None, ""
    while True:
        text = "\n".join(l for l in game.read_log()[start:].splitlines() if not ECHO.match(l))
        if rx is not None and (hit := rx.search(text)):
            break
        # lacks only: give the reply `settle` s to arrive before checking it is absent
        if time.time() >= (end if rx is not None else t0 + s.get("settle", 1.5)):
            break
        time.sleep(0.2)
    label = s.get("name") or f"console {s['line']!r}"
    bad = []
    if rx is not None and hit is None:
        bad.append(f"no /{s['expect']}/")
    if "lacks" in s:
        found = [m.group(0) for m in re.finditer(s["lacks"], text)]
        if found:
            bad.append(f"has /{s['lacks']}/: {found[:3]}")
    if "save_as" in s:
        saved[s["save_as"]] = {"ok": not bad, "text": text[-4000:], "match": hit.group(0) if hit else None,
                               "groups": list(hit.groups()) if hit else []}
    tail = " | " + text[-600:].replace("\n", " / ") if text else " | (nothing new in the log)"
    run.assert_(label, not bad, ("; ".join(bad) if bad else hit.group(0) if hit else "nothing it lacks") + (tail if bad else ""))

