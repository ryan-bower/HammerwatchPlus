"""Tooltip lint: skill tooltips that a tuner edit made stale (docs/devarena/SPEC.md, build order 3).

A skill's tooltip numbers are text in "description-params" ([key, (flag,) label, v1..vN], one
value per level or one for all, PlayerClass.as:212-238), not reads of the fields the skill
runs on. So an edit to binds.charge-dmg leaves "damage 40" in the tooltip.

The lint binds each numeric param to the level fields whose vanilla values show as it at
every level: equal, ms as "Ns", a fraction or a percent as "N%" (most likely scale first). Then it applies a
version's edits and reports every bound param that no bound field shows any more. Vanilla
reports 0 stale by construction; params that bind to nothing are counted, not reported.

Level L reads upgrades[L-2] first and the base "skill" dict second (PlayerBase.as:179-187):
upgrades do not stack, each one overlays the base alone. Edit rows are the tuner's
[skill id, level index (0 = base, k = upgrades[k-1]), path, value] (Patch.as paths).

    python tools/devarena/tooltip_lint.py                 # the override file's versions
    python tools/devarena/tooltip_lint.py --from SVAL     # an override .sval (every version)
    python tools/devarena/tooltip_lint.py --stats         # how many params bind, vanilla only
    python tools/devarena/tooltip_lint.py --spec mods/spec-ranger-test   # a spec mod's own tooltips

Exit 0 when nothing is stale, 1 when something is, 2 on a bad input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from tools.devarena import overrides  # noqa: E402

DATA = overrides.REPO / "gamecode" / "datatables" / "players"
NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def skill_entries(root: Path = DATA) -> dict[str, dict]:
    """id -> the skill entry (has "skill" and maybe "upgrades"), top-level and modifier skills."""
    out: dict[str, dict] = {}

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("id"), str) and isinstance(x.get("skill"), dict):
                out.setdefault(x["id"], x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for f in sorted(root.rglob("*.sval.json")):
        walk(json.loads(f.read_text(encoding="utf-8")))
    return out


def leaves(x, prefix: str = "") -> dict[str, float]:
    """Dot path -> number for every numeric leaf (numeric strings too, bools not)."""
    out: dict[str, float] = {}
    if isinstance(x, dict):
        items = x.items()
    elif isinstance(x, list):
        items = ((str(i), v) for i, v in enumerate(x))
    else:
        return out
    for k, v in items:
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[p] = float(v)
        elif isinstance(v, str) and NUM.fullmatch(v.strip()):
            out[p] = float(v)
        else:
            out.update(leaves(v, p))
    return out


def level_dicts(entry: dict) -> list[dict]:
    """m_levelParams: [0] the base skill dict, [k] upgrades[k-1]."""
    return [entry["skill"]] + [u for u in entry.get("upgrades", []) if isinstance(u, dict)]


def effective(levels: list[dict]) -> list[dict[str, float]]:
    """Per player level L = 1..N, the numbers it reads: upgrades[L-2] over the base."""
    base = leaves(levels[0])
    return [base] + [{**base, **leaves(u)} for u in levels[1:]]


def parse_shown(s) -> tuple[float, str, int] | None:
    """'3s' -> (3, 's', 0), '12.5%' -> (12.5, '%', 1); None unless exactly one number."""
    if not isinstance(s, str):
        return None
    nums = NUM.findall(s)
    if len(nums) != 1:
        return None
    n = nums[0]
    unit = "s" if re.search(r"\d\s*s\b", s) else "%" if "%" in s else ""
    return float(n), unit, len(n.split(".")[1]) if "." in n else 0


# field -> shown scales, most likely first. "3s" is ms only: a seconds field shown as is would
# bind "tick-rate 0.5s" to move-speed-mul 0.5. "25%" is a fraction before a percent.
SCALES = {"s": (0.001,), "%": (100.0, 1.0), "": (1.0, 100.0, 0.001)}


def shows(field: float, shown: tuple[float, str, int], scale: float) -> bool:
    n, _, dec = shown
    return abs(abs(field * scale) - abs(n)) <= 0.5 * 10 ** -dec + 1e-9


def params(entry: dict) -> list[tuple[str, list]]:
    """(key, per-level shown values) for each description param."""
    out = []
    for p in entry.get("description-params", []):
        if not isinstance(p, list) or len(p) < 3 or not isinstance(p[0], str):
            continue
        vals = p[3:] if isinstance(p[1], bool) else p[2:]
        out.append((p[0], vals))
    return out


def per_level(vals: list, n: int) -> list | None:
    if len(vals) == 1:
        return vals * n
    if len(vals) == n:
        return vals
    return None


def bind(entry: dict) -> tuple[dict[int, tuple[list[str], float]], int]:
    """param index (keys repeat) -> (the field paths that show it at every vanilla level, at the
    first scale any does); and how many params did not bind."""
    eff = effective(level_dicts(entry))
    bound: dict[int, tuple[list[str], float]] = {}
    unbound = 0
    for i, (key, vals) in enumerate(params(entry)):
        lv = per_level(vals, len(eff))
        shown = [parse_shown(v) for v in lv] if lv else None
        if not shown or any(s is None for s in shown):
            unbound += 1
            continue
        for scale in SCALES[shown[0][1]]:
            paths = [p for p in eff[0] if all(p in e and shows(e[p], s, scale) for e, s in zip(eff, shown))]
            # a constant 0/1 field matches too much to mean anything
            paths = [p for p in paths if any(e[p] not in (0.0, 1.0) for e in eff)]
            if paths:
                bound[i] = (paths, scale)
                break
        else:
            unbound += 1
    return bound, unbound


def set_path(d, path: str, value: str):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d[int(k)] if isinstance(d, list) else d.setdefault(k, {})
    last = keys[-1]
    if isinstance(d, list):
        d[int(last)] = value
    else:
        d[last] = value


def apply(entry: dict, edits: list) -> dict:
    """A copy of the entry with the edit rows for it applied."""
    e = json.loads(json.dumps(entry))
    levels = level_dicts(e)
    for sid, lvl, path, value in edits:
        if sid == e["id"] and 0 <= lvl < len(levels):
            set_path(levels[lvl], path, value)
    return e


def stale(entries: dict[str, dict], edits: list) -> list[dict]:
    """Bound params whose bound fields no longer show the tooltip's value at some level."""
    out = []
    for sid in sorted({e[0] for e in edits}):
        entry = entries.get(sid)
        if entry is None:
            continue
        bound, _ = bind(entry)
        eff = effective(level_dicts(apply(entry, edits)))
        for i, (key, vals) in enumerate(params(entry)):
            if i not in bound:
                continue
            paths, scale = bound[i]
            lv = per_level(vals, len(eff))
            for L, (e, v) in enumerate(zip(eff, lv), 1):
                s = parse_shown(v)
                if not any(p in e and shows(e[p], s, scale) for p in paths):
                    now = {p: e.get(p) for p in paths}
                    out.append({"skill": sid, "param": key, "level": L, "shown": v, "fields": now})
    return out


# ---- spec mods (HP6 ship check) ---------------------------------------------------------------
# A spec mod's skill files are raw .sval text (tools/devarena/clone_spec.py), %include lines and
# ivec2 and all, so they are read here leniently: scalars by tag, vectors as strings.
SCALAR = {"string": str, "s": str, "int": int, "i": int, "float": float, "f": float}


def parse_sval_text(text: str):
    import xml.etree.ElementTree as ET
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%"))

    def conv(el):
        if el.tag in ("dict", "d"):
            return {c.get("name"): conv(c) for c in el if c.get("name") is not None}
        if el.tag in ("array", "a"):
            return [conv(c) for c in el]
        t = (el.text or "").strip()
        if el.tag in SCALAR:
            try:
                return SCALAR[el.tag](t)
            except ValueError:
                return t
        if el.tag in ("bool", "b"):
            return t.lower() in ("t", "true", "1")
        return t

    return conv(ET.fromstring(body))


def fmt_shown(v: float, unit: str, dec: int) -> str:
    n = f"{v:.{dec}f}" if dec else str(int(round(v)))
    return n + unit


def rewrite_params(vanilla: dict, spec: dict) -> tuple[list[tuple[int, list | None]], list[str]]:
    """For a spec copy of a vanilla skill: (param index, new shown values or None to drop) for
    each bound param whose fields the spec changed, and a note per change. Bound by the vanilla
    entry (the copy's numbers are what the lint must find); a param whose bound fields are all
    gone at some level (a composed skill) is dropped rather than left showing vanilla."""
    bound, _ = bind(vanilla)
    eff = effective(level_dicts(spec))
    out, notes = [], []
    sp = params(spec)
    for i, (key, vals) in enumerate(params(vanilla)):
        if i not in bound or i >= len(sp) or sp[i][0] != key:
            continue
        paths, scale = bound[i]
        lv = per_level(sp[i][1], len(eff))
        if lv is None:
            continue
        shown = [parse_shown(v) for v in lv]
        if all(any(p in e and shows(e[p], s, scale) for p in paths) for e, s in zip(eff, shown)):
            continue
        new = []
        for e, s in zip(eff, shown):
            p = next((p for p in paths if p in e), None)
            if p is None:
                new = None
                break
            new.append(fmt_shown(abs(e[p] * scale), s[1], s[2]))
        if new is not None and len(sp[i][1]) == 1 and len(set(new)) == 1:
            new = new[:1]
        out.append((i, new))
        notes.append(f"{spec.get('id')} {key}: {'dropped (its fields are gone)' if new is None else '/'.join(lv) + ' -> ' + '/'.join(new)}")
    return out, notes


def spec_skills(mod: Path) -> tuple[str, list[Path]]:
    cls = next(mod.glob("players/hwp/spec_*/class_*.sval"), None)
    if cls is None:
        raise ValueError(f"{mod}: no players/hwp/spec_*/class_*.sval")
    return cls.stem[len("class_"):], sorted(cls.parent.glob("skills/*.sval"))


def lint_spec(entries: dict[str, dict], mod: Path) -> tuple[int, list[dict]]:
    """(skills checked, stale params) for a spec mod: each copy's own tooltip against its own
    fields, bound through the vanilla skill it was cloned from (hwp_<spec>_<vanilla id>)."""
    sid, files = spec_skills(mod)
    prefix = f"hwp_{sid}_"
    found, n = [], 0
    for f in files:
        spec = parse_sval_text(f.read_text(encoding="utf-8"))
        vid = str(spec.get("id", "")).removeprefix(prefix)
        vanilla = entries.get(vid)
        if vanilla is None:
            continue
        n += 1
        bound, _ = bind(vanilla)
        eff = effective(level_dicts(spec))
        sp = params(spec)
        for i, (key, _vals) in enumerate(params(vanilla)):
            if i not in bound or i >= len(sp) or sp[i][0] != key:
                continue
            paths, scale = bound[i]
            lv = per_level(sp[i][1], len(eff))
            for L, (e, v) in enumerate(zip(eff, lv or []), 1):
                s = parse_shown(v)
                if s is None or not any(p in e and shows(e[p], s, scale) for p in paths):
                    found.append({"skill": spec.get("id"), "param": key, "level": L, "shown": v,
                                  "fields": {p: e.get(p) for p in paths}})
    return n, found


def sources(a) -> list[tuple[str, list]]:
    """(label, edits) per version to lint."""
    out = []
    sval = Path(a.sval) if a.sval else overrides.SVAL
    if sval.exists():
        state = overrides.from_sval(sval.read_text(encoding="utf-8"))
        for i, v in enumerate(state["versions"], 1):
            out.append((f"{sval.name} v{i} ({v.get('note', '')})", v["edits"]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="sval", help="an override .sval (default the devarena mod's)")
    ap.add_argument("--stats", action="store_true", help="vanilla binding counts only")
    ap.add_argument("--spec", action="append", default=[], help="a spec mod folder (mods/spec-<id>): its own tooltips")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    entries = skill_entries()
    nb = nu = 0
    for entry in entries.values():
        b, u = bind(entry)
        nb += len(b)
        nu += u
    vanilla = [s for sid in entries for s in stale(entries, [[sid, 0, "\0none", ""]])]
    print(f"{len(entries)} skills: {nb} tooltip params bound to fields, {nu} not; vanilla stale {len(vanilla)}")
    if vanilla:
        return 1
    if a.stats:
        return 0
    if a.spec:
        total = 0
        for m in a.spec:
            try:
                n, found = lint_spec(entries, Path(m))
            except (ValueError, OSError) as e:
                print(f"bad input: {e}", file=sys.stderr)
                return 2
            total += len(found)
            print(f"{Path(m).name}: {n} skills, {len(found)} stale")
            for s in found:
                print("  " + (json.dumps(s) if a.json else
                              f"{s['skill']} L{s['level']} {s['param']} shows {s['shown']!r}, fields now {s['fields']}"))
        return 1 if total else 0
    try:
        srcs = sources(a)
    except (ValueError, OSError) as e:
        print(f"bad input: {e}", file=sys.stderr)
        return 2
    total = 0
    for label, edits in srcs:
        found = stale(entries, edits)
        total += len(found)
        print(f"{label}: {len(edits)} edits, {len(found)} stale")
        for s in found:
            print("  " + (json.dumps(s) if a.json else
                          f"{s['skill']} L{s['level']} {s['param']} shows {s['shown']!r}, fields now {s['fields']}"))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
