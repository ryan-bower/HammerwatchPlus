#!/usr/bin/env python3
"""Wrap every HWP module entry point in an HWP::Guard (mods/hwplib/scripts/HWP/Core/Guard.as).

A script exception in a module's UpdateFrame aborts the game mode's whole frame
update after the module loop (docs/RE_NOTES.md, "Script errors"), so each entry
point a module overrides runs its body as Guarded<Name> behind a try/catch:

    python tools/guard_modules.py           wrap the entry points that are not wrapped yet
    python tools/guard_modules.py --check   exit 1 and list them instead

A module is a direct subclass of Modules::Module (the only kind MakeModules
makes). Save is left alone: the game mode already catches it.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODS = REPO / "mods"

# entry point -> argument names in the base's order (Modules/Module.as)
ENTRIES = {
    "UpdateFrame": 4,
    "PreRenderFrame": 1,
    "RenderFrame": 2,
    "RenderWidgets": 3,
    "Load": 2,
}
CLASS = re.compile(r"^[ \t]*class\s+(\w+)\s*:\s*(?:Modules::)?Module\b[^{;]*\{", re.M)


def class_body(text: str, open_brace: int) -> int:
    """The index of the brace that closes the one at open_brace."""
    depth = 0
    for j in range(open_brace, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError("unbalanced braces")


def arg_names(params: str) -> list[str]:
    return [re.findall(r"\w+", p)[-1] for p in params.split(",") if p.strip()]


def wrapper(indent: str, mod: str, cls: str, name: str, params: str) -> str:
    g = f"m_guard{name}"
    call = f"Guarded{name}({', '.join(arg_names(params))});"
    once = "true" if name == "Load" else ""
    i1, i2 = indent + "\t", indent + "\t\t"
    return (
        f"{indent}// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game\n"
        f"{indent}HWP::Guard {g};\n"
        f"{indent}void {name}({params}) override\n"
        f"{indent}{{\n"
        f"{i1}if ({g}.Skip(\"{mod}\", \"{cls}.{name}\"))\n"
        f"{i2}return;\n"
        f"{i1}if ({g}.Raw())\n"
        f"{i1}{{\n"
        f"{i2}{call}\n"
        f"{i2}{g}.Ok();\n"
        f"{i2}return;\n"
        f"{i1}}}\n"
        f"{i1}try {{ {call} {g}.Ok(); }}\n"
        f"{i1}catch {{ {g}.Failed({once}); }}\n"
        f"{indent}}}\n"
    )


def unguarded(text: str):
    """(class, entry, match) for every module entry point not yet wrapped, last first."""
    found = []
    for m in CLASS.finditer(text):
        start = m.end() - 1
        end = class_body(text, start)
        body = text[start:end]
        for name, nargs in ENTRIES.items():
            if f"void Guarded{name}(" in body:
                continue
            sig = re.compile(rf"^([ \t]*)void\s+{name}\s*\(([^)]*)\)[ \t]*(?:override)?[ \t]*(?=\r?$)", re.M)
            for sm in sig.finditer(text, start, end):
                if len(arg_names(sm.group(2))) == nargs:
                    found.append((m.group(1), name, sm))
    return sorted(found, key=lambda f: f[2].start(), reverse=True)


def guard_text(mod: str, text: str) -> tuple[str, list[str]]:
    done = []
    for cls, name, sm in unguarded(text):
        indent, params = sm.group(1), sm.group(2)
        nl = "\r\n" if "\r\n" in text else "\n"
        new = wrapper(indent, mod, cls, name, params).replace("\n", nl)
        renamed = f"{indent}void Guarded{name}({params})"
        text = text[: sm.start()] + new + nl + renamed + text[sm.end():]
        done.append(f"{cls}.{name}")
    return text, done


def files():
    for f in sorted(MODS.glob("*/scripts/**/*.as")):
        mod = f.relative_to(MODS).parts[0]
        if mod.startswith("gamelab"):
            continue  # GameLab probes measure the engine's own behaviour
        yield mod, f


def missing() -> list[str]:
    out = []
    for mod, f in files():
        text = f.read_bytes().decode("utf-8")
        for cls, name, _ in unguarded(text):
            out.append(f"{f.relative_to(REPO).as_posix()}: {cls}.{name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="list unwrapped entry points, exit 1 if any")
    args = ap.parse_args()
    if args.check:
        left = missing()
        for line in left:
            print("unguarded:", line)
        return 1 if left else 0
    total = 0
    for mod, f in files():
        raw = f.read_bytes().decode("utf-8")
        new, done = guard_text(mod, raw)
        if done:
            f.write_bytes(new.encode("utf-8"))
            total += len(done)
            print(f"{f.relative_to(REPO).as_posix()}: {', '.join(done)}")
    print(f"wrapped {total} entry point(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
