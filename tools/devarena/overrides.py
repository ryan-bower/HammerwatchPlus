"""The Dev Arena override file (docs/devarena/SPEC.md, "Decided during build" 2).

The game reads mods/devarena/tweak/hwp/devarena_overrides.sval once at boot
(mods/devarena/scripts/HWP/DevArena/Overrides.as) and cannot write files, so it logs its whole
tuner state on every change as one line:

    [HWP:devarena] override {"schema":1,"live":2,"a":0,"b":2,"slot":"B","pins":[...],
                             "versions":[{"note":"...","edits":[[skill,level,path,value],...]},...]}

This tool writes the .sval from the last such line, so the next boot starts where the last
session stopped. v0 (vanilla) is implied and not stored.

    python tools/devarena/overrides.py sync [--log PATH] [--follow] [--out PATH]
    python tools/devarena/overrides.py show [--sval PATH]

--log defaults to the GameLab game's live log (gamelab/env: userdata/game/HWR2.exe.log); a
run's copy is gamelab/results/<run>/logs/pass1.HWR2.exe.log.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import hwr_archive  # noqa: E402

SCHEMA = 1
SVAL = REPO / "mods" / "devarena" / "tweak" / "hwp" / "devarena_overrides.sval"
LINE = re.compile(r"\[HWP:devarena\] override (\{.*\})\s*$")
HEADER = ("<!-- Dev Arena override file (mods/devarena/scripts/HWP/DevArena/Overrides.as). Written by\n"
          "     tools/devarena/overrides.py from the game log; read once at boot. Empty = vanilla. -->\n")


def empty() -> dict:
    return {"schema": SCHEMA, "live": 0, "a": 0, "b": -1, "slot": "A", "pins": [], "versions": []}


def check(state: dict) -> dict:
    """The state, validated: ints in range, every edit [str, int, str, str]. Raises ValueError."""
    if state.get("schema") != SCHEMA:
        raise ValueError(f"schema {state.get('schema')!r} is not {SCHEMA}")
    versions = state.get("versions")
    if not isinstance(versions, list):
        raise ValueError("versions is not a list")
    n = len(versions)
    for key, lo in (("live", 0), ("a", 0), ("b", -1)):
        v = state.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= n:
            raise ValueError(f"{key}={v!r} is outside {lo}..{n}")
    if state.get("slot") not in ("A", "B") or (state["slot"] == "B" and state["b"] < 0):
        raise ValueError(f"slot {state.get('slot')!r} with b={state['b']}")
    if not all(isinstance(p, str) for p in state.get("pins", [])):
        raise ValueError("pins must be strings")
    for i, v in enumerate(versions, 1):
        if not isinstance(v.get("note", ""), str):
            raise ValueError(f"v{i}: note is not a string")
        for e in v.get("edits", []):
            ok = (isinstance(e, list) and len(e) == 4 and isinstance(e[0], str) and isinstance(e[1], int)
                  and not isinstance(e[1], bool) and isinstance(e[2], str) and isinstance(e[3], str))
            if not ok:
                raise ValueError(f"v{i}: bad edit {e!r}")
    return state


def parse_line(line: str) -> dict | None:
    """The state on one log line, or None when the line is not an override line."""
    m = LINE.search(line)
    return check(json.loads(m.group(1))) if m else None


def last_in(text: str) -> dict | None:
    """The state on the last override line of a log."""
    for line in reversed(text.splitlines()):
        st = parse_line(line)
        if st is not None:
            return st
    return None


def to_sval(state: dict) -> str:
    """The .sval text Overrides.as LoadOverrides reads. Edit values stay strings: the game
    parses them against the field's type when it applies them (Patch.as)."""
    check(state)
    doc = {
        "schema": state["schema"], "live": state["live"], "a": state["a"], "b": state["b"],
        "slot": state["slot"], "pins": list(state.get("pins", [])),
        "versions": [{"note": v.get("note", ""), "edits": [list(e) for e in v.get("edits", [])]}
                     for v in state["versions"]],
    }
    return HEADER + hwr_archive.svalue_to_xml(doc) + "\n"


def from_sval(text: str) -> dict:
    d = hwr_archive.parse_svalue_xml(text)
    state = {**empty(), **d}
    for v in state["versions"]:
        v.setdefault("note", "")
        v.setdefault("edits", [])
    return check(state)


def default_log() -> Path:
    sys.path.insert(0, str(REPO))
    from gamelab import env
    return env.GAME / "HWR2.exe.log"


def write(state: dict, out: Path) -> bool:
    """Write when it changed; True when written."""
    text = to_sval(state)
    if out.exists() and out.read_text(encoding="utf-8") == text:
        return False
    out.write_text(text, encoding="utf-8")
    return True


def summary(state: dict) -> str:
    return (f"{len(state['versions'])} versions, live v{state['live']}, A v{state['a']}, "
            f"B {'-' if state['b'] < 0 else 'v' + str(state['b'])}, slot {state['slot']}, {len(state['pins'])} pins")


def cmd_sync(a) -> int:
    log = Path(a.log) if a.log else default_log()
    out = Path(a.out) if a.out else SVAL
    pos = 0
    last = None
    deadline = time.monotonic() + a.timeout if a.follow else 0
    while True:
        if log.exists():
            size = log.stat().st_size
            if size < pos:
                pos = 0
            if size > pos:
                with open(log, "rb") as f:
                    f.seek(pos)
                    chunk = f.read(size - pos)
                cut = chunk.rfind(b"\n") + 1 if a.follow else len(chunk)
                st = last_in(chunk[:cut].decode("utf-8", "replace"))
                pos += cut
                if st is not None:
                    last = st
                    if write(st, out):
                        print(f"wrote {out}: {summary(st)}", flush=True)
        if not a.follow:
            break
        if time.monotonic() > deadline:
            break
        time.sleep(0.5)
    if last is None:
        print(f"no override line in {log}; {out} left as it was")
        return 1 if not a.follow else 0
    if not a.follow:
        print(f"{out} is current: {summary(last)}")
    return 0


def cmd_show(a) -> int:
    p = Path(a.sval) if a.sval else SVAL
    st = from_sval(p.read_text(encoding="utf-8"))
    print(summary(st))
    for i, v in enumerate(st["versions"], 1):
        print(f"  v{i}: {v['note']} ({len(v['edits'])} edits)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync", help="write the .sval from the last override line of a log")
    s.add_argument("--log")
    s.add_argument("--out")
    s.add_argument("--follow", action="store_true", help="keep watching the log")
    s.add_argument("--timeout", type=float, default=3600, help="with --follow: stop after this many s")
    s.set_defaults(fn=cmd_sync)
    s = sub.add_parser("show", help="print the override file's versions")
    s.add_argument("--sval")
    s.set_defaults(fn=cmd_show)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
