"""Auto-tuner logic (docs/devarena/SPEC.md HP7, "Decided during build" 28).

The tuner searches one numeric field at a time for the smallest change that meets a dps target
against A, on the Bench tab's own benches (gamelab/bots/devarena_autotune.py drives the game).
This module is the part with no game in it: the field and target syntax, the feel locks, the
candidate ladder, the target check, and the report.

  field   "<skillId>:<path>"            e.g. "ran_mark:binds.proj-dmg"
  target  "+15%" / "-10%"               mean dps delta of B vs A, and the bench's verdict agreeing
  muls    [1.25, 2, 4]                  candidates = round(current * mul), nearest first, deduplicated
  bounds  {field: [lo, hi]}             candidates outside are never tried
  bisect  n                             after the first hit, n halvings toward the last miss

Feel locks: fields that change how a skill feels to play rather than how hard it hits (cast
point, timeline, cooldown, move speed, blocking, animation) are refused unless the call unlocks
them by name. A dps search would happily trade feel for numbers; that trade is the player's.

    python tools/devarena/autotune.py --run gamelab/results/<time>-devarena-autotune-lab
        writes docs/devarena/proposals/<run>.md from the run's autotune-* log lines.
Exit 0 with at least one proposal, 1 without, 2 on a bad input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PROPOSALS = REPO / "docs" / "devarena" / "proposals"

FEEL_LOCKS = ("castpoint", "timeline", "cooldown", "move-speed-mul", "blocking", "anim")
DEFAULT_MULS = (1.25, 1.5, 2.0, 3.0, 4.0)


def parse_field(spec: str) -> tuple[str, str]:
    skill, sep, path = spec.partition(":")
    if not sep or not skill or not path or " " in spec:
        raise ValueError(f"field {spec!r}: want <skillId>:<path>")
    return skill, path


def locked_by(path: str, unlock=()) -> str | None:
    """The feel lock `path` falls under, None when free (or unlocked)."""
    parts = re.split(r"[.\[\]]+", path.lower())
    for lock in FEEL_LOCKS:
        if lock in unlock:
            continue
        if any(p == lock or p.startswith(lock + "-") or p.endswith("-" + lock) for p in parts if p):
            return lock
    return None


def parse_target(t: str) -> float:
    m = re.fullmatch(r"\s*([+-]\d+(?:\.\d+)?)\s*%\s*", str(t))
    if not m:
        raise ValueError(f"target {t!r}: want a signed percent like +15%")
    return float(m.group(1))


def candidates(current: float, muls=DEFAULT_MULS, integer=True, lo=None, hi=None) -> list:
    """round(current * mul) per mul, nearest first, without repeats or current, inside [lo, hi]."""
    out = []
    for m in sorted(muls, key=lambda m: abs(m - 1)):
        v = current * m
        v = int(round(v)) if integer else round(v, 3)
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            continue
        if v != current and v not in out:
            out.append(v)
    return out


def midpoint(miss, hit, integer=True):
    """The bisection step between a value that missed the target and one that met it; None when adjacent."""
    m = (miss + hit) / 2
    if integer:
        m = int(round(m))
        return None if m in (miss, hit) else m
    return None if abs(hit - miss) < 1e-3 else round(m, 3)


def meets(result: dict, target: float) -> bool:
    """A bench-result meets a target when its delta is at least it and its verdict agrees."""
    if not result or result.get("A") is None or result.get("B") is None:
        return False
    delta = float(result.get("delta", 0))
    if target >= 0:
        return delta >= target and result.get("verdict") == "B better"
    return delta <= target and result.get("verdict") == "B worse"


def trial(value, version: int, result: dict, target: float) -> dict:
    a, b = result.get("A") or {}, result.get("B") or {}
    return {"value": value, "version": version, "bench": result.get("bench"), "a": a.get("mean"), "b": b.get("mean"),
            "aVersion": a.get("version"), "bVersion": b.get("version"), "delta": result.get("delta"),
            "verdict": result.get("verdict"), "meets": meets(result, target)}


def note(skill: str, path: str, old, new, t: dict, target: float) -> str:
    """One line, console-safe (it travels as gl words): letters, digits, spaces and . _ - + :"""
    return f"{skill} {path} {old} to {new}: {t['delta']:+.1f}pct dps vs A, {t['verdict']}, target {target:+g}pct"


def log_events(log: Path) -> list[tuple[str, dict]]:
    """("proposal"|"accept"|"discard", payload) per autotune-* line, in order."""
    out = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"\[HWP:devarena\] autotune-(proposal|accept|discard) (\{.*\})\s*$", line)
        if m:
            try:
                out.append((m.group(1), json.loads(m.group(2))))
            except ValueError:
                pass
    return out


def render(run: Path, events: list[tuple[str, dict]]) -> str:
    out = [f"# Auto-tuner proposals: {run.name}", "",
           f"Generated by `tools/devarena/autotune.py` from `{run.as_posix()}`.", "",
           "| # | Version | Note | Evidence | Outcome |", "|---|---|---|---|---|"]
    n = 0
    for i, (kind, d) in enumerate(events):
        if kind != "proposal":
            continue
        n += 1
        ev = d.get("evidence") or {}
        a, b = ev.get("A") or {}, ev.get("B") or {}
        settle = next((k for k, e in events[i + 1:] if k != "proposal" and e.get("version") == d["version"]), "pending")
        out.append(f"| {n} | v{d['version']} over v{d.get('base')} | {d.get('note')} | bench #{d.get('bench')}: "
                   f"A {a.get('mean')} (sd {a.get('sd')}, n {a.get('n')}) vs B {b.get('mean')} (sd {b.get('sd')}, n {b.get('n')}), "
                   f"{ev.get('delta')}%, {ev.get('verdict')}, {ev.get('golem')} NG+{ev.get('ngp')}, {ev.get('driver')} | {settle} |")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True, help="a devarena-autotune run folder")
    ap.add_argument("--log", help="the game log (default <run>/logs/pass1.HWR2.exe.log)")
    ap.add_argument("--out", help="the report (default docs/devarena/proposals/<run>.md)")
    a = ap.parse_args(argv)
    run = Path(a.run)
    log = Path(a.log) if a.log else run / "logs" / "pass1.HWR2.exe.log"
    try:
        events = log_events(log)
    except OSError as e:
        print(f"bad input: {e}")
        return 2
    out = Path(a.out) if a.out else PROPOSALS / f"{run.name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(run, events), encoding="utf-8")
    n = sum(1 for k, _ in events if k == "proposal")
    print(f"{n} proposals, wrote {out}")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
