"""HWR2.exe.log parsing, salvaged from the retired tools/dev_check.py (git show 9d99f0b:tools/dev_check.py).

Formats, as the engine writes them (build 25509441):
  script compile issue   "... ] ERR : scripts/HWP/Foo.as (ln 12, col 3)" with the message on the next line
  runtime error          a line with "Script exception" or "[ERR]"
  mod enabled            "Adding unpacked mod '<id>'" (logged twice: boot + menu level)
The game's own baseline ERR lines are the same with and without mods (docs/RE_NOTES.md),
so a check is scoped to files of the mods under test, never "no ERR at all".
"""
from __future__ import annotations

import re

SCRIPT_ISSUE = re.compile(r"\] (ERR|WARN|WRN|ERROR)\s+: (?P<file>[^ ]+) \(ln (?P<line>\d+), col (?P<col>\d+)\)")
MOD_ADDED = re.compile(r"Adding (packed|unpacked) mod '([^']+)'")
# "sval does not exist": a gui naming a sprite set nobody defines; vanilla never logs it
OURS = (r"scripts/HWP/", r"scripts/GameLab/", r"hwp_", r"\[HWP:", r"HammerwatchPlus", r"sval does not exist")
LINE_PREFIX = re.compile(r"^\[\w+\] \[[\d:]+\] (?:SE|INFO|ERR|WARN)?\s*:?\s*")
# the engine's last word when any script fails to compile: every mod script stops, the probe too
COMPILE_FAILED = "Please correct the errors in the script"


def script_issues(text: str) -> list[dict]:
    out = []
    for m in SCRIPT_ISSUE.finditer(text):
        end = text.find("\n", m.end())
        msg = text[end + 1:text.find("\n", end + 1)].strip() if end >= 0 else ""
        msg = LINE_PREFIX.sub("", msg)          # "[WRN] [15:33:16] SE : Function 'opNeg()' not found"
        out.append({"kind": m.group(1), "file": m.group("file"), "line": int(m.group("line")),
                    "col": int(m.group("col")), "msg": msg})
    return out


def errors_in(text: str, patterns=OURS, allow=()) -> list[str]:
    """Compile errors in files matching `patterns`, plus runtime errors mentioning them.
    `allow`: regexes for expected error lines; one is dropped with the engine's `From "<file>"
    line N` line right after it (an HWP::LogError is two lines, the second naming Log.as:
    architect-errors 20261020-160604)."""
    ours = re.compile("|".join(patterns))
    ok = re.compile("|".join(allow)) if allow else None
    bad = [f"{i['kind']} {i['file']}:{i['line']}:{i['col']} {i['msg']}" for i in script_issues(text)
           if i["kind"].startswith("ERR") and ours.search(i["file"])]
    skip_from = False
    for ln in text.splitlines():
        if ok is not None and ok.search(ln):
            skip_from = True
            continue
        if skip_from and re.search(r'\[ERR\].* From "', ln):
            skip_from = False
            continue
        skip_from = False
        if ("Script exception" in ln or "[ERR]" in ln) and ours.search(ln):
            bad.append(ln.strip())
    return list(dict.fromkeys(bad))         # the engine compiles twice (boot, menu level): once each


def compile_failed(text: str) -> bool:
    return COMPILE_FAILED in text


RESOURCE_MOD = re.compile(r"\] Resource mod: (?P<file>[^:]+): .* \((?P<id>[^()]+)\)\s*$", re.M)
WORKSHOP_ITEM = re.compile(r"\] Workshop: Item: (?P<item>[0-9a-f]+) - (?P<path>.+?)\s*$", re.M)


def duplicate_mods(text: str) -> dict[str, int]:
    """Mod ids the game found more than once ("Resource mod: <file>: <name> (<id>)", one line
    per mod it found, the Workshop's subscriptions included): when such an id is enabled, both
    copies load and the first copy of each path wins (gamelab/env.py SHADOW_SUFFIX)."""
    seen: dict[str, int] = {}
    for m in RESOURCE_MOD.finditer(text):
        seen[m.group("id")] = seen.get(m.group("id"), 0) + 1
    return {k: n for k, n in seen.items() if n > 1}


def workshop_items(text: str) -> list[str]:
    """The Workshop item folders the game loaded ("Workshop: Item: <hex> - <path>")."""
    return [m.group("path") for m in WORKSHOP_ITEM.finditer(text)]


def mods_added(text: str) -> list[str]:
    return list(dict.fromkeys(mid for _kind, mid in MOD_ADDED.findall(text)))
