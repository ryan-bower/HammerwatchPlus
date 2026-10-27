#!/usr/bin/env python3
"""make_package_scenarios.py - write the GameLab scenarios that load the built Workshop packages
(packages.json, tools/build.py): gamelab/scenarios/pkg-<id>.json for each package alone,
pkg-all.json for the all-in-one pack, and pkg-pair-*.json for packages side by side.

It also writes gamelab/scenarios/pkgfeat/pf-<scenario>.json: every feature scenario (mod-, qa-,
fix-, plan- ...) whose mods ship in at most MAX_FEATURE_PACKAGES packages, run against those
packages instead of the mods' source folders, so each package's features are tested the way
players get them (`python -m gamelab suite pkgfeat`). Its GameLab probe mods stay as mods.

    make_package_scenarios.py          # (re)write them
    make_package_scenarios.py --check  # exit 1 when one is missing or stale

A package scenario lists `packages`, not `mods`: the launcher builds them from this tree and
copies the .bin files into the GameLab mods dir, so the run loads them packed, the way
players get them. Each checks that the library booted, that every package's stamp check
passed (no "was built with library"), whether the Luck part is there (the character tab's
Luck cell shows only with it), the package's own commands, and a clean log.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from gamelab import env  # noqa: E402
SCENARIOS = REPO / "gamelab" / "scenarios"
# packages side by side: one without Luck beside one with it, two that both carry Luck, and the
# all-in-one pack beside a package it already holds
PAIRS = [("qol", "keys"), ("town", "dungeon"), ("all", "qol"), ("firearms", "classes")]
# the engine's line for a path a second package also ships
SHARED_PATH = r"Resource name hash conflict in package 'mods/(HWP-[a-z0-9]+|HammerwatchPlus-All)\.bin' for file "
# what `hwp help` lists for a package's own commands, and a command whose reply shows it works
PROBES = {
    "keys": [("hwp bag", r"\[HWP\] Bag: \d+/\d+ items")],
    "town": [("hwp help", r"\[HWP\] hwp fishing ")],
    "firearms": [("hwp help", r"\[HWP\] hwp firearms")],
    "classes": [("hwp help", r"\[HWP\] hwp skillkeys ")],
}


# feature scenarios that are not about a package's features: looks, benchmarks, probes
FEATURE_SKIP = ("look-", "bench-", "diag-", "probe-", "demo-", "export-", "spike-", "pkg-", "dup-",
                "compile-err", "throw", "guard", "reload-")
MAX_FEATURE_PACKAGES = 3
FEATURES = SCENARIOS / "pkgfeat"


def requires_closure(mods: list[str]) -> set[str]:
    return set(env.expand_mods(mods))


def scenario(name: str, about: str, packages: list[str], ids: list[str], luck: bool, probes: list[tuple],
             bags: bool) -> dict:
    steps = [
        {"do": "log_has", "pattern": r"\[HWP:core\] module created, version \S+", "timeout": 30,
         "name": "library: module created"},
        *({"do": "log_has", "pattern": rf"\[HWP:core\] package {i}, library [0-9a-f]{{12}}",
           "name": f"{i}: stamp check passed"} for i in ids),
        {"do": "log_has", "pattern": r"\[HWP:core\] gameplay started; server=yes town=yes", "timeout": 60,
         "name": "gameplay started in town"},
        {"do": "gl", "verb": "state", "expect": {"phase": "town"}, "name": "in town"},
        {"do": "log_lacks", "pattern": "was built with library", "name": "no package of another library build"},
        ({"do": "log_has", "pattern": r"\[HWP:luck\] self-check done", "name": "the Luck part loaded"} if luck else
         {"do": "log_lacks", "pattern": r"\[HWP:luck\]", "name": "no Luck part"}),
        {"do": "gl", "verb": "menu", "args": ["character", "-", "hwp-luck-stat"],
         "expect": {"tab": "PlayerMenuCharacterTab"}, "name": "character tab open"},
        {"do": "sleep", "seconds": 0.5},
        {"do": "gl", "verb": "menu", "args": ["character", "-", "hwp-luck-stat"],
         "expect": {"tab": "PlayerMenuCharacterTab", "shown": luck},
         "name": "the Luck cell " + ("shows" if luck else "is hidden")},
        {"do": "shot", "name": "character-tab"},
        {"do": "key", "key": "escape"},
    ]
    steps += [{"do": "console", "line": "hwp help"},
              {"do": "log_has", "pattern": r"\[HWP\] commands \(\d+\):", "timeout": 5, "name": "hwp help answers"}]
    if not bags:
        # the bag slots are sold by keys (HWP::BagShop); the bag itself is the library's
        steps.append({"do": "log_lacks", "pattern": r"\[HWP\] hwp bag ", "name": "no bag shop without keys"})
    for line, pattern in probes:
        steps += [{"do": "console", "line": line},
                  {"do": "log_has", "pattern": pattern, "timeout": 5, "name": f"{line}: {pattern}"}]
    if len(packages) > 1:
        # the engine logs one ERR per path two enabled mods share and keeps the first copy
        # (RE_NOTES "one path, two mods"); packages of one build share only identical files,
        # which the stamp check above vouches for
        steps.append({"do": "log_clean", "allow": [SHARED_PATH]})
    else:
        steps.append({"do": "log_clean"})
    return {"name": name, "about": about, "fixture": "town-paladin", "packages": packages, "timeout": 240,
            "steps": steps}


def build_all() -> dict[str, dict]:
    doc = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    pkgs = {p["id"]: p for p in doc["packages"]}
    all_file = doc["all"].get("file", "HammerwatchPlus-All")
    mods_of = {pid: requires_closure(p["mods"]) for pid, p in pkgs.items()}
    mods_of["all"] = set().union(*mods_of.values())
    ids_of = {pid: [f"HWP-{pid}"] for pid in pkgs}
    ids_of["all"] = [f"HWP-{pid}" for pid in pkgs]      # the all pack carries every package's check
    probes_of = {pid: list(PROBES.get(pid, [])) for pid in pkgs}
    probes_of["all"] = [x for v in PROBES.values() for x in v]
    out = {}
    for pid in [*pkgs, "all"]:
        title = doc["all"]["name"] if pid == "all" else pkgs[pid]["name"]
        what = f"{all_file}.bin" if pid == "all" else f"HWP-{pid}.bin"
        out[f"pkg-{pid}"] = scenario(
            f"pkg-{pid}", f"{title} ({what}, built by tools/build.py) alone, packed as players get it: the library "
            "boots from the package's own copy, the stamp check passes, the Luck cell "
            + ("shows (the package carries hwplib-luck)" if "hwplib-luck" in mods_of[pid] else
               "is hidden (no hwplib-luck in it)") + ", and the log is clean. tools/make_package_scenarios.py.",
            [pid], ids_of[pid], "hwplib-luck" in mods_of[pid], probes_of[pid], "keys" in mods_of[pid])
    for a, b in PAIRS:
        ids = list(dict.fromkeys(ids_of[a] + ids_of[b]))
        out[f"pkg-pair-{a}-{b}"] = scenario(
            f"pkg-pair-{a}-{b}", f"Two packages side by side ({a} and {b}): both carry the library at the same "
            "paths, the game keeps one copy of each and nothing conflicts; every stamp check passes. "
            "tools/make_package_scenarios.py.",
            [a, b], ids, "hwplib-luck" in (mods_of[a] | mods_of[b]),
            probes_of[a] + [p for p in probes_of[b] if p not in probes_of[a]], "keys" in (mods_of[a] | mods_of[b]))
    # the all-in-one pack with every package it already holds enabled as well
    every = ["all", *pkgs]
    out["pkg-all-every"] = scenario(
        "pkg-all-every", "The all-in-one pack with every single package enabled beside it, as a player who "
        "subscribed to both would have them: every path is shipped up to twice, the game keeps one copy, "
        "nothing conflicts, every stamp check passes and every package's commands answer. "
        "tools/make_package_scenarios.py.",
        every, ids_of["all"], True, probes_of["all"], True)
    return out


def feature_variants() -> dict[str, dict]:
    """pf-<scenario>: a feature scenario run against the packages that ship its mods."""
    doc = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    owner = {m: p["id"] for p in doc["packages"] for m in p["mods"]}
    library = {f.parent.name for f in (REPO / "mods").glob("*/module.json")
               if json.loads(f.read_text(encoding="utf-8")).get("library")}
    out = {}
    for f in sorted(SCENARIOS.glob("*.json")):
        if f.stem.startswith(FEATURE_SKIP):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        # needs_hoh1: it reads the local content tools/import_hoh1.py wrote into the source
        # folders, which a built package carries only with --with-local (pf-fix-campaign-traps
        # 20261027-033114); hoh1-standins checks the packages without it
        if "packages" in d or d.get("compile_error") or d.get("needs_hoh1"):
            continue
        feat = [m for m in d.get("mods", []) if not m.startswith("gamelab") and m not in library]
        if not feat or any(m not in owner for m in feat):
            continue   # library-only, or a mod no package ships (the bench, local HoH1 content)
        pkgs = sorted({owner[m] for m in feat})
        if len(pkgs) > MAX_FEATURE_PACKAGES:
            continue
        v = dict(d)
        v["name"] = f"pf-{d['name']}"
        v["about"] = (f"{f.stem} against the built package{'s' if len(pkgs) > 1 else ''} "
                      f"{', '.join(pkgs)} instead of the mods' source folders "
                      "(tools/make_package_scenarios.py). " + d.get("about", ""))
        probes = [m for m in d.get("mods", []) if m.startswith("gamelab")]
        if probes:
            v["mods"] = probes
        else:
            v.pop("mods", None)
        v["packages"] = pkgs
        if len(pkgs) > 1:
            v["steps"] = [dict(s, allow=list(s.get("allow", [])) + [SHARED_PATH]) if s.get("do") == "log_clean"
                          else s for s in d["steps"]]
        out[f"pf-{f.stem}"] = v
    return out


def text(d: dict) -> str:
    return json.dumps(d, indent=1) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    stale = []
    FEATURES.mkdir(exist_ok=True)
    want_files = {SCENARIOS / f"{n}.json": d for n, d in build_all().items()}
    want_files.update({FEATURES / f"{n}.json": d for n, d in feature_variants().items()})
    for p in sorted(FEATURES.glob("*.json")):
        if p not in want_files:
            if a.check:
                stale.append(p.stem)
            else:
                p.unlink()
                print("removed", p.relative_to(REPO))
    for p, d in want_files.items():
        name = p.stem
        want = text(d)
        if p.is_file() and p.read_text(encoding="utf-8") == want:
            continue
        if a.check:
            stale.append(name)
        else:
            p.write_bytes(want.encode("utf-8"))
            print("wrote", p.relative_to(REPO))
    if stale:
        print("stale package scenarios (run tools/make_package_scenarios.py):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
