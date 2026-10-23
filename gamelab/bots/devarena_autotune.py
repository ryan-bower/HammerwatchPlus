"""The Dev Arena auto-tuner (docs/devarena/SPEC.md HP7, "Decided during build" 28).

  {"do": "bot", "bot": "devarena_autotune",
   "kwargs": {"fields": ["ran_mark:binds.proj-dmg"], "target": "+15%", "muls": [1.25, 4]},
   "expect": {"terminal": "proposed"}}

Needs the arena as a player would leave it for a bench: in the golem room, the dock open on the
Bench tab, driver/pulls/secs set, "vs" on versions, B empty or a scratch B. Then per field
(tools/devarena/autotune.py: syntax, feel locks, ladder, target check):

1. da-skill reads the player's level of the skill and the field's current value there
   (levelIndex = level - 1: PlayerBase.as:187 stacks m_levelParams[lvl - 1] on the base dict).
2. Per candidate, nearest first: da-set writes it into B (Tuner.as Commit: the first edit makes B,
   later ones re-pin it; A stays), the dock's Start bench button is clicked with the emulated
   mouse (da-dock's button centre, gamelab-hands `pointer ... click`), the mouse is parked off
   the dock, and da-bench is polled until that bench finishes. Its bench-result is the evidence.
3. The first candidate whose bench meets the target is filed with da-propose: pending on the
   Bench tab until the player accepts or discards it there. Nothing is kept by the tuner.

Returns terminal ("proposed", "no_candidate", "locked", "rejected", "bench_failed"), proposal
(the da-propose reply), trials (one per bench: value, version, A/B mean, delta, verdict, meets),
field, from, to, note.
"""
import time

from tools.devarena import autotune


def click_dock(p, bid):
    at = (p.cmd("da-dock", bid).get("buttons") or {}).get(bid)
    if not at:
        return False
    p.cmd("pointer", int(at[0]), int(at[1]), "move")
    r = p.cmd("pointer", int(at[0]), int(at[1]), "click")
    time.sleep(0.3)
    return bool(r.get("ok"))


def bench_once(p, park, timeout):
    """Start one bench from the dock and wait for it; the bench-result dict or an error string."""
    before = p.cmd("da-bench")
    if before.get("running"):
        return "a bench is already running"
    if not click_dock(p, "bstart"):
        return "no Start bench button (dock closed or not on the Bench tab?)"
    p.cmd("pointer", park[0], park[1], "move")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        b = p.cmd("da-bench")
        if b.get("bench", 0) > before.get("bench", 0) and not b.get("running"):
            last = b.get("last") or {}
            if last.get("bench") != b.get("bench"):
                return f"bench {b.get('bench')} stopped: {b.get('aborted') or 'no result'}"
            return last
    return f"bench did not finish in {timeout}s"


def num(v):
    """da-skill's binds are the param's text ("50"); a number or None."""
    if isinstance(v, (int, float)):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() and "." not in str(v) else f


def run(p, fields, target="+15%", muls=None, unlock=(), bounds=None, bisect=1, park=(320, 130), bench_timeout=240,
        max_benches=8):
    goal = autotune.parse_target(target)
    if not 1 <= len(fields) <= 3:
        return {"terminal": "rejected", "why": "1-3 fields", "trials": []}
    trials, benches = [], 0

    def try_value(skill, li, path, value):
        nonlocal benches
        s = p.cmd("da-set", skill, li, path, value)
        if not s.get("ok"):
            return {"terminal": "rejected", "value": value, "why": s.get("error")}
        time.sleep(0.5)
        res = bench_once(p, park, bench_timeout)
        benches += 1
        if isinstance(res, str):
            return {"terminal": "bench_failed", "value": value, "why": res}
        t = autotune.trial(value, s.get("version"), res, goal)
        trials.append(t)
        return t

    for spec in fields:
        skill, path = autotune.parse_field(spec)
        lock = autotune.locked_by(path, unlock)
        if lock:
            return {"terminal": "locked", "field": spec, "lock": lock, "trials": trials}
        bind = path.split(".", 1)[1] if path.startswith("binds.") else None
        info = p.cmd("da-skill", skill, *([bind] if bind else []))
        level = int(info.get("level") or 0)
        cur = num((info.get("binds") or {}).get(bind)) if bind else None
        if not info.get("ok") or level < 1 or not isinstance(cur, (int, float)):
            return {"terminal": "rejected", "field": spec, "why": f"no numeric current value: {info}", "trials": trials}
        li, integer = level - 1, isinstance(cur, int)
        lo_b, hi_b = (bounds or {}).get(spec, (None, None))
        ladder = autotune.candidates(cur, muls or autotune.DEFAULT_MULS, integer, lo_b, hi_b)
        last_miss = cur
        for value in ladder:
            if benches >= max_benches:
                break
            t = try_value(skill, li, path, value)
            if "terminal" in t:
                return {**t, "field": spec, "trials": trials}
            if not t["meets"]:
                last_miss = value
                continue
            best = t
            # bisection between the last miss and the hit: the smallest change that still meets
            for _ in range(bisect):
                mid = autotune.midpoint(last_miss, best["value"], integer)
                if mid is None or benches >= max_benches:
                    break
                m = try_value(skill, li, path, mid)
                if "terminal" in m:
                    return {**m, "field": spec, "trials": trials}
                if m["meets"]:
                    best = m
                else:
                    last_miss = mid
            if best is not trials[-1]:
                # B holds the last value tried; put the proposed one back and bench it as the evidence
                again = try_value(skill, li, path, best["value"])
                if "terminal" in again:
                    return {**again, "field": spec, "trials": trials}
                if not again["meets"]:
                    return {"terminal": "no_candidate", "why": f"{best['value']} did not meet on a re-bench",
                            "field": spec, "trials": trials}
                best = again
            note = autotune.note(skill, path, cur, best["value"], best, goal)
            prop = p.cmd("da-propose", note)
            return {"terminal": "proposed" if prop.get("ok") else "rejected", "proposal": prop, "trials": trials,
                    "field": spec, "level": level, "from": cur, "to": best["value"], "note": note}
    return {"terminal": "no_candidate", "trials": trials}
