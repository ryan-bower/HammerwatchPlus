"""Measures where the stray presses of an open window come from, and which Enter the console's
gl lines should be submitted with.

A stray press: the top window's m_usePressed set while no pointer job runs (HandsUi.as
WatchStray), Forward down and pressed. Seen 9-12 frames after a click's reply in pets-bowl
20261018-100131, fishing-coast 20261018-101524 and bufftips-hover 20261018-104456. Every gl
line is typed into the console and submitted with Enter (session.py console()), and the main
Enter is also MenuForward (res/controls_default.cfg:32). The keypad Enter (VK_RETURN with the
extended bit) may not be. Each stray entry carries framesAfterCmd (frames since a gl line was
last dispatched) and cmdsAfterJob, which tell a gl line's own Enter from something later.

  {"do": "bot", "bot": "console_enter", "kwargs": {"widget": "bet-btn-2"},
   "expect": {"terminal": "done", "kp_accepted": true}}

With the mouse on `widget` of the top window, `reps` times each: a click there (it lets go of
any press left over), then either `idle` s with no gl line or `lines` read-only gl lines, then
a pointer move whose reply carries the stray presses since the click. Every line of a trial,
the click's too, is submitted with that trial's Enter. kwargs: widget, lines (4), idle (1.5),
reps (3). Returns terminal ("done", "no_widget", "kp_rejected"), trials ([{case, kp, strays,
strayLog, click}]), totals ({case: {trials, with_strays, strays}}: main_idle, main_lines,
kp_idle, kp_lines), kp_accepted.
"""
import time

from gamelab.session import GameError

CASES = (("main_idle", False, True), ("main_lines", False, False), ("kp_idle", True, True), ("kp_lines", True, False))


def _trial(p, px, py, lines, idle, kp, quiet):
    was = p.game.console_kp_enter
    p.game.console_kp_enter = kp
    try:
        click = p.cmd("pointer", px, py, "click")
        if quiet:
            time.sleep(idle)
        else:
            for _ in range(lines):
                p.cmd("cinema", timeout=6)
        mv = p.cmd("pointer", px, py, "move", timeout=6)
    finally:
        p.game.console_kp_enter = was
    return {"strays": mv.get("strays") or 0, "strayLog": mv.get("strayLog"), "hovered": mv.get("hovered"),
            "click": {k: click.get(k) for k in ("pressedBefore", "letGo", "downSeen", "upSeen", "hovered")}}


def run(p, widget="bet-btn-2", lines=4, idle=1.5, reps=3):
    r = p.cmd("clickables", "top", widget)
    items = r.get("items", [])
    if not items:
        return {"terminal": "no_widget", "reason": f"no clickable {widget!r} in {r.get('top')!r}"}
    px, py = items[0]["px"], items[0]["py"]
    trials, totals = [], {c: {"trials": 0, "with_strays": 0, "strays": 0} for c, _, _ in CASES}
    for _ in range(reps):
        for case, kp, quiet in CASES:
            try:
                t = _trial(p, px, py, lines, idle, kp, quiet)
            except GameError as e:
                if not kp:
                    raise
                return {"terminal": "kp_rejected", "reason": str(e), "trials": trials, "totals": totals,
                        "kp_accepted": False}
            trials.append({"case": case, "kp": kp, **t})
            tot = totals[case]
            tot["trials"] += 1
            tot["with_strays"] += 1 if t["strays"] else 0
            tot["strays"] += t["strays"]
    return {"terminal": "done", "trials": trials, "totals": totals, "kp_accepted": True, "at": [px, py]}
