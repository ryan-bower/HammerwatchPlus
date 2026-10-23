"""The Dev Arena bench, outside the game (docs/devarena/SPEC.md, Bench Q28 and Q14).

The game runs a bench in-engine (mods/devarena/scripts/HWP/DevArena/Bench.as) and cannot write
files, so it logs one line per pull and one per bench:

    [HWP:devarena] bench-pull {"bench":3,"variant":"B","version":2,"pull":4,"dps":512,...}
    [HWP:devarena] bench-result {"bench":3,"A":{"n":5,"mean":..,"sd":..},"B":{..},"verdict":..}
    [HWP:devarena] bench-promote {..the bench-result..}

This module holds the statistics (the same formulas as Bench.as, so a CSV row can be checked
against the game's own verdict) and the tools around the lines:

    python tools/devarena/bench.py csv [--log PATH] [--run NAME]      rows -> gamelab/results/bench/
    python tools/devarena/bench.py baseline [--log PATH]               vanilla baseline -> tweak sval
    python tools/devarena/bench.py promote [--log PATH]                bench-promote -> docs/bench/

RNG mode is "stats" (SPEC "Decided during build" 7: a fixed seed does not repeat draws), so
every result is a mean with its spread and the n it would take to pin the mean to +-3%.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
OUT = REPO / "gamelab" / "results" / "bench"
BASELINE = REPO / "mods" / "devarena" / "tweak" / "hwp" / "devarena_baseline.sval"
PROMOTED = REPO / "docs" / "bench"
GAME_LOG = REPO / "gamelab" / "env" / "userdata" / "game" / "HWR2.exe.log"

# two-sided 95% Student t, df 1..30; 1.96 above
T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
       2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
       2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]
TARGET = 0.03  # +-3%

LINE = re.compile(r"\[HWP:devarena\] (bench-pull|bench-result|bench-promote|bench-aborted) (\{.*\})\s*$")

COLUMNS = ["run", "bench", "preset", "variant", "version", "rotation", "mode", "golem", "ngp", "pool",
           "debuffs", "pull", "dps", "dealt", "ms", "ttk", "hits", "mana_in", "mana_out", "oom_ms",
           "procs", "blocked", "n", "mean", "spread", "rel", "n_for_3pct", "verdict", "delta_pct"]


def tcrit(df: int) -> float:
    if df < 1:
        return float("inf")
    return T95[df - 1] if df <= len(T95) else 1.96


def stats(values: list[float]) -> dict:
    """n, mean, sd (sample), rel = 95% CI half-width / mean, nFor3 = pulls for +-3%."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "sd": 0.0, "rel": 0.0, "nFor3": 0}
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    if n < 2 or mean <= 0:
        return {"n": n, "mean": mean, "sd": sd, "rel": 0.0 if n < 2 else float("inf"), "nFor3": 0}
    t = tcrit(n - 1)
    rel = t * sd / math.sqrt(n) / mean
    need = math.ceil((t * sd / (TARGET * mean)) ** 2) if sd > 0 else n
    return {"n": n, "mean": mean, "sd": sd, "rel": rel, "nFor3": max(need, 2)}


def compare(a: list[float], b: list[float]) -> dict:
    """B against A: delta %, Welch t and df, and a verdict at 95%."""
    sa, sb = stats(a), stats(b)
    if sa["n"] < 2 or sb["n"] < 2:
        return {"delta": 0.0, "t": 0.0, "df": 0, "verdict": "too few pulls"}
    delta = 100.0 * (sb["mean"] - sa["mean"]) / sa["mean"] if sa["mean"] > 0 else 0.0
    va, vb = sa["sd"] ** 2 / sa["n"], sb["sd"] ** 2 / sb["n"]
    se = math.sqrt(va + vb)
    if se == 0:
        if sb["mean"] == sa["mean"]:
            return {"delta": delta, "t": 0.0, "df": sa["n"] + sb["n"] - 2, "verdict": "no difference"}
        return {"delta": delta, "t": math.copysign(float("inf"), delta), "df": sa["n"] + sb["n"] - 2,
                "verdict": "B better" if delta > 0 else "B worse"}
    t = (sb["mean"] - sa["mean"]) / se
    num = (va + vb) ** 2
    den = (va ** 2 / (sa["n"] - 1) if va else 0) + (vb ** 2 / (sb["n"] - 1) if vb else 0)
    df = int(num / den) if den > 0 else sa["n"] + sb["n"] - 2
    df = max(1, df)
    if abs(t) < tcrit(df):
        verdict = "no difference"
    else:
        verdict = "B better" if t > 0 else "B worse"
    return {"delta": delta, "t": t, "df": df, "verdict": verdict}


def siblings(cls: str, tier: str, base: list[dict]) -> dict:
    """The baseline rows for the other subclasses of cls's class at a tier, and all of that tier.

    cls is a subclass id ("ranger_nature"); its class is the part before the first "_"."""
    klass = cls.split("_")[0]
    tier_rows = [r for r in base if r["preset"].endswith("/" + tier)]
    sib = [r for r in tier_rows if r["preset"].split("/")[0].split("_")[0] == klass
           and r["preset"].split("/")[0] != cls]
    return {"siblings": sib, "all": tier_rows}


def rank(mean: float, rows: list[dict]) -> int:
    """1-based place of mean among rows' means (1 = highest)."""
    return 1 + sum(1 for r in rows if r["mean"] > mean)


# ---- log lines -------------------------------------------------------------------------

def parse(text: str) -> list[tuple[str, dict]]:
    out = []
    for line in text.splitlines():
        m = LINE.search(line)
        if m:
            try:
                out.append((m.group(1), json.loads(m.group(2))))
            except json.JSONDecodeError:
                continue
    return out


def rows(text: str, run: str = "") -> list[dict]:
    """One CSV row per bench-pull, with its variant's aggregate from the matching bench-result."""
    events = parse(text)
    results = {e["bench"]: e for k, e in events if k == "bench-result"}
    out = []
    for kind, p in events:
        if kind != "bench-pull":
            continue
        res = results.get(p["bench"], {})
        agg = res.get(p["variant"]) or {}
        out.append({
            "run": run, "bench": p["bench"], "preset": p.get("preset", ""), "variant": p["variant"],
            "version": p.get("version", ""), "rotation": p.get("rotation", ""), "mode": p.get("mode", ""),
            "golem": p.get("golem", ""), "ngp": p.get("ngp", ""), "pool": p.get("pool", ""),
            "debuffs": p.get("debuffs", ""), "pull": p.get("pull", ""), "dps": p.get("dps", ""),
            "dealt": p.get("dealt", ""), "ms": p.get("ms", ""), "ttk": p.get("ttk", ""),
            "hits": p.get("hits", ""), "mana_in": p.get("manaIn", ""), "mana_out": p.get("manaOut", ""),
            "oom_ms": p.get("oomMs", ""), "procs": p.get("procs", ""), "blocked": p.get("blocked", ""),
            "n": agg.get("n", ""), "mean": agg.get("mean", ""), "spread": agg.get("sd", ""),
            "rel": agg.get("rel", ""), "n_for_3pct": agg.get("nFor3", ""),
            "verdict": res.get("verdict", ""), "delta_pct": res.get("delta", ""),
        })
    return out


def check_results(text: str) -> list[str]:
    """Recompute each bench-result from its bench-pull rows; the differences (none = agreed)."""
    events = parse(text)
    pulls: dict[tuple[int, str], list[float]] = {}
    for k, p in events:
        if k == "bench-pull":
            pulls.setdefault((p["bench"], p["variant"]), []).append(float(p["dps"]))
    bad = []
    for k, r in events:
        if k != "bench-result":
            continue
        for v in ("A", "B"):
            if not r.get(v):
                continue
            mine = stats(pulls.get((r["bench"], v), []))
            got = r[v]
            if mine["n"] != got.get("n") or abs(mine["mean"] - got.get("mean", 0)) > 1.0 \
                    or abs(mine["sd"] - got.get("sd", 0)) > 1.0:
                bad.append(f"bench {r['bench']} {v}: game n={got.get('n')} mean={got.get('mean')} "
                           f"sd={got.get('sd')}, recomputed n={mine['n']} mean={mine['mean']:.1f} sd={mine['sd']:.1f}")
        if r.get("A") and r.get("B"):
            mine = compare(pulls.get((r["bench"], "A"), []), pulls.get((r["bench"], "B"), []))
            if mine["verdict"] != r.get("verdict"):
                bad.append(f"bench {r['bench']}: game verdict {r.get('verdict')!r}, recomputed {mine['verdict']!r}")
    return bad


def write_csv(text: str, run: str, out: Path = OUT) -> tuple[Path, list[dict]]:
    rs = rows(text, run)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run or 'bench'}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rs)
    allp = out / "all.csv"
    new = not allp.is_file()
    with allp.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rs)
    return path, rs


# ---- baseline ---------------------------------------------------------------------------

def baseline_rows(text: str) -> list[dict]:
    """The last bench-result per (preset, golem, ngp, pool, rotation) from a baseline bench (A only)."""
    keep: dict[tuple, dict] = {}
    for k, r in parse(text):
        if k != "bench-result" or not r.get("A") or not r.get("preset"):
            continue
        key = (r["preset"], r.get("golem"), r.get("ngp"), r.get("pool"), r.get("rotation"))
        keep[key] = {"preset": r["preset"], "golem": r.get("golem", ""), "ngp": int(r.get("ngp", 0)),
                     "pool": int(r.get("pool", 0)), "rotation": r.get("rotation", ""),
                     "n": int(r["A"]["n"]), "mean": float(r["A"]["mean"]), "sd": float(r["A"]["sd"])}
    return sorted(keep.values(), key=lambda r: (r["golem"], r["ngp"], r["pool"], r["rotation"], r["preset"]))


def baseline_sval(base: list[dict]) -> str:
    out = ["<!-- Dev Arena vanilla bench baseline. GENERATED by tools/devarena/bench.py baseline",
           "     from a devarena/bench-baseline run. -->", "<dict>", '\t<int name="schema">1</int>',
           '\t<array name="rows">']
    for r in base:
        out.append("\t\t<dict>")
        out.append(f'\t\t\t<string name="preset">{r["preset"]}</string>')
        out.append(f'\t\t\t<string name="golem">{r["golem"]}</string>')
        out.append(f'\t\t\t<int name="ngp">{r["ngp"]}</int>')
        out.append(f'\t\t\t<int name="pool">{r["pool"]}</int>')
        out.append(f'\t\t\t<string name="rotation">{r["rotation"]}</string>')
        out.append(f'\t\t\t<int name="n">{r["n"]}</int>')
        out.append(f'\t\t\t<float name="mean">{r["mean"]:.1f}</float>')
        out.append(f'\t\t\t<float name="sd">{r["sd"]:.1f}</float>')
        out.append("\t\t</dict>")
    out += ["\t</array>", "</dict>", ""]
    return "\n".join(out)


def merge_baseline(old: list[dict], new: list[dict]) -> list[dict]:
    key = lambda r: (r["preset"], r["golem"], r["ngp"], r["pool"], r["rotation"])  # noqa: E731
    have = {key(r): r for r in old}
    have.update({key(r): r for r in new})
    return sorted(have.values(), key=lambda r: (r["golem"], r["ngp"], r["pool"], r["rotation"], r["preset"]))


def read_baseline(path: Path = BASELINE) -> list[dict]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    out = []
    for block in re.findall(r"<dict>(.*?)</dict>", text, re.S):
        f = dict(re.findall(r'name="(\w+)">([^<]*)<', block))
        if "preset" not in f:
            continue
        out.append({"preset": f["preset"], "golem": f.get("golem", ""), "ngp": int(f.get("ngp", 0)),
                    "pool": int(f.get("pool", 0)), "rotation": f.get("rotation", ""), "n": int(f.get("n", 0)),
                    "mean": float(f.get("mean", 0)), "sd": float(f.get("sd", 0))})
    return out


# ---- promote ----------------------------------------------------------------------------

def promote_md(r: dict) -> str:
    def side(v):
        s = r.get(v)
        if not s:
            return f"| {v} | - | - | - | - | - |"
        return (f"| {v} (v{s.get('version', '?')}) | {s['n']} | {s['mean']:.0f} | {s['sd']:.0f} | "
                f"{100 * s.get('rel', 0):.1f}% | {s.get('ttk', -1)} |")
    lines = [f"## {r.get('preset') or '(no preset)'}: bench {r['bench']} ({r.get('when', '')})", "",
             f"Golem {r.get('golem')} NG+{r.get('ngp')} pool {r.get('pool')}, debuffs "
             f"{r.get('debuffs') or 'none'}; rotation {r.get('rotation')}; RNG mode {r.get('mode')}.", "",
             "| variant | n | mean dps | spread | +-95% | ttk ms |", "|---|---|---|---|---|---|",
             side("A"), side("B"), "",
             f"Verdict: **{r.get('verdict')}** (B vs A {r.get('delta', 0):+.1f}%)."]
    if r.get("siblings"):
        lines.append(f"Siblings: {r['siblings']}.")
    lines.append("")
    return "\n".join(lines)


def promote(text: str, out: Path = PROMOTED) -> list[Path]:
    written = []
    for k, r in parse(text):
        if k != "bench-promote":
            continue
        name = (r.get("preset") or "unnamed").split("/")[0]
        out.mkdir(parents=True, exist_ok=True)
        p = out / f"{name}.md"
        head = "" if p.is_file() else f"# Bench: {name}\n\nPromoted from the Dev Arena Bench tab.\n\n"
        body = promote_md(r)
        old = p.read_text(encoding="utf-8") if p.is_file() else ""
        if body in old:
            continue
        p.write_text(old + head + body, encoding="utf-8")
        written.append(p)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("csv", "baseline", "promote", "check"):
        s = sub.add_parser(name)
        s.add_argument("--log", type=Path, default=GAME_LOG)
        if name == "csv":
            s.add_argument("--run", default="")
    a = ap.parse_args(argv)
    text = a.log.read_text(encoding="utf-8", errors="replace")
    if a.cmd == "csv":
        path, rs = write_csv(text, a.run or a.log.stem)
        print(f"wrote {path}: {len(rs)} rows")
    elif a.cmd == "baseline":
        new = baseline_rows(text)
        if not new:
            print("no bench-result lines with a preset", file=sys.stderr)
            return 1
        base = merge_baseline(read_baseline(), new)
        BASELINE.write_text(baseline_sval(base), encoding="utf-8")
        print(f"wrote {BASELINE}: {len(base)} rows ({len(new)} new)")
    elif a.cmd == "promote":
        for p in promote(text):
            print(f"wrote {p}")
    elif a.cmd == "check":
        bad = check_results(text)
        for b in bad:
            print(b)
        print("agreed" if not bad else f"{len(bad)} disagreements")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
