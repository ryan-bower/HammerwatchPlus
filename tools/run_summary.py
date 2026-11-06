"""One run dir -> summary.json + summary.md: where the time went, per level.

    python tools/run_summary.py gamelab/results/<run>      # writes <run>/summary.{json,md}
    python tools/run_summary.py <run> --print               # also print the markdown

Per place (mission/level, in the order visited): wall seconds, stalled seconds (the game log
silent for STALL_S or more: a frame the scripts held, or a load), engine loot ms against wall,
hits and damage by kind/source/visit, loot visits by type and result, the units visited most,
loot_pick outcomes and rejection totals, intent results, gains. Then deaths (the last events
before each), and harness anomalies (retypes, backstops, timeouts, stalls).

Runs from before the harness tagged events (_place/_lvl, harness.stall; 2026-10-18) are
rebuilt: place from the last "place" any reply carried, stalls from the pass logs' own
[HH:MM:SS] clock, matched to gl.jsonl by the order of their [GL] lines. Measured against
cube-run 20261018-222736: 16 stalls, 392 s, 15 of them on barracks_1 inside the loot loop.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

GL_LINE = re.compile(r"\[GL\] (\{.*\})\s*$")
LOG_TS = re.compile(r"^\[\w{3}\] \[(\d\d):(\d\d):(\d\d)\]")
STALL_S = 6                 # gamelab/session.py STALL_S
DEATH_TAIL = 15             # events listed before each death
TOP = 8


def load(run: Path) -> list[dict]:
    out = []
    for line in (run / "gl.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"ev": "bad_json_line", "raw": line[:200]})
    return out


def tag(evs: list[dict]) -> None:
    """_place/_lvl on every event, as gamelab/session.py does live (kept when present)."""
    place, lvl = "", 0
    boot_level = {0: "pre-boot"}
    for o in evs:
        if o.get("ev") == "boot" and not o.get("_preload"):
            boot_level[o.get("_lvl", lvl + 1)] = o.get("level", "?")
        if "_place" in o:
            place, lvl = o["_place"], o.get("_lvl", lvl)
            continue
        if not str(o.get("ev", "")).startswith("harness.") and not o.get("_preload"):
            if o.get("ev") == "boot":
                lvl += 1
                place = ""
            if isinstance(o.get("place"), str) and o["place"]:
                place = o["place"]
        o["_place"], o["_lvl"] = place, lvl
    # a level's events before its first place-bearing line: back-fill from the first one
    first: dict[int, str] = {}
    for o in evs:
        if o["_place"] and o["_lvl"] not in first:
            first[o["_lvl"]] = o["_place"]
    for o in evs:
        if not o["_place"]:
            o["_place"] = first.get(o["_lvl"], boot_level.get(o["_lvl"], "?"))


def log_stalls(run: Path, evs: list[dict]) -> list[dict]:
    """harness.stall equivalents from the pass logs (for runs that predate them)."""
    engine = [o for o in evs if not str(o.get("ev", "")).startswith("harness.") and o.get("ev") != "bad_json_line"]
    out, k = [], 0
    for log in sorted((run / "logs").glob("pass*.HWR2.exe.log")):
        prev, hb, last = None, False, ""
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LOG_TS.match(line)
            g = GL_LINE.search(line)
            if m:
                sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                if prev is not None and hb and (sec - prev) % 86400 >= STALL_S:
                    o = engine[k] if g and k < len(engine) else (engine[k - 1] if 0 < k <= len(engine) else {})
                    out.append({"ev": "harness.stall", "s": (sec - prev) % 86400, "before": last,
                                "after": (line[g.start():] if g else line[m.end():].strip())[:160],
                                "_t": o.get("_t"), "_place": o.get("_place", "?"), "_lvl": o.get("_lvl", 0),
                                "rebuilt": True})
                prev = sec
            if g:
                if '"ev":"hb"' in g.group(1):
                    hb = True
                if k < len(engine):
                    last = str(engine[k].get("ev") or engine[k].get("id") or "")
                k += 1
    return out


def stall_kind(s: dict) -> str:
    a = s.get("after", "")
    if '"ev":"boot"' in a or "Making Module" in a or "Loading" in a or "[preload]" in a:
        return "load"
    return "frame"


def summarize(run: Path) -> dict:
    evs = load(run)
    tag(evs)
    stalls = [o for o in evs if o.get("ev") == "harness.stall"]
    if not stalls:
        stalls = log_stalls(run, evs)
    places: dict[tuple, dict] = {}
    order: list[tuple] = []

    def P(o) -> dict:
        key = (o["_lvl"], o["_place"])
        if key not in places:
            order.append(key)
            places[key] = {"lvl": key[0], "place": key[1], "t0": o.get("_t"), "t1": o.get("_t"),
                           "stall_s": 0, "stalls": 0, "load_stall_s": 0,
                           "hits": 0, "landed": 0, "dmg": 0, "by_kind": Counter(), "by_src": Counter(),
                           "by_visit": Counter(), "visits": Counter(), "units": Counter(), "unit_names": {},
                           "picks": Counter(), "rej": Counter(), "carpet_checks": [], "intents": Counter(),
                           "loot_ms": {}, "gains": [], "census": None, "external": 0}
        return places[key]

    deaths, anomalies = [], Counter()
    anomaly_list: list[dict] = []
    tail: list[dict] = []
    phase = ""
    for o in evs:
        if o.get("_preload"):
            continue
        ev = o.get("ev", "reply" if "id" in o else "?")
        p = P(o)
        if o.get("_t") is not None:
            p["t1"] = o["_t"]
            if p["t0"] is None:
                p["t0"] = o["_t"]
        if ev not in ("ptick", "hb"):
            tail.append(o)
            del tail[:-DEATH_TAIL]
        if ev == "hb":
            if o.get("phase") == "dead" and phase != "dead":
                deaths.append({"_t": o.get("_t"), "place": o["_place"],
                               "last": [_brief(x) for x in tail]})
            phase = o.get("phase", phase)
        elif ev == "hit":
            p["hits"] += 1
            p["landed"] += bool(o.get("landed"))
            p["dmg"] += o.get("dmg", 0) or 0
            p["by_kind"][o.get("kind", "?")] += o.get("dmg", 0) or 0
            p["by_src"][o.get("src", "?")] += o.get("dmg", 0) or 0
            p["by_visit"][o.get("visit") or o.get("intent", "-")] += o.get("dmg", 0) or 0
        elif ev == "loot_visit":
            p["visits"][f"{o.get('type')} {o.get('result')}"] += 1
            u = o.get("unit")
            if u:
                p["units"][u] += 1
                p["unit_names"][u] = f"{o.get('type')} {o.get('name', '')}"
            p["loot_ms"][o.get("id")] = max(p["loot_ms"].get(o.get("id"), 0), o.get("ms", 0) or 0)
        elif ev == "loot_pick":
            p["picks"][o.get("outcome", "?") + (" " + o["type"] if o.get("type") else "")] += 1
            for k, v in (o.get("rej") or {}).items():
                p["rej"][k] += v
            p["carpet_checks"].append(o.get("carpetChecks", 0))
        elif ev == "loot_external":
            p["external"] += 1
            anomalies["loot_external"] += 1
            anomaly_list.append(_brief(o))
        elif ev in ("loot_leaving",) or (ev == "pilot" and o.get("intent") == "loot"):
            p["loot_ms"][o.get("id")] = max(p["loot_ms"].get(o.get("id"), 0), o.get("ms", 0) or 0)
            p["census"] = {k: o[k] for k in o if k.startswith("left") or k.startswith("census")}
            p["gains"] = o.get("gains", p["gains"])
        if ev == "pilot":
            p["intents"][f"{o.get('intent')} {o.get('result')}"] += 1
        if ev.startswith("harness."):
            name = ev[8:]
            if name in ("console_retype", "pilot_backstop", "shot_failed", "stall") or \
                    (name == "pilot_result" and o.get("result") == "timeout"):
                anomalies[name] += 1
                if name != "stall":
                    anomaly_list.append(_brief(o))
        if ev in ("bad_json", "bad_json_line"):
            anomalies[ev] += 1
    for s in stalls:
        key = (s.get("_lvl", 0), s.get("_place", "?"))
        p = places.get(key) or P({"_lvl": key[0], "_place": key[1], "_t": s.get("_t")})
        kind = stall_kind(s)
        if kind == "load":
            p["load_stall_s"] += s.get("s", 0)
        else:
            p["stall_s"] += s.get("s", 0)
            p["stalls"] += 1
    if not any(o.get("ev") == "harness.stall" for o in evs):
        anomalies["stall"] = len(stalls)
    run_json = {}
    if (run / "run.json").exists():
        run_json = json.loads((run / "run.json").read_text(encoding="utf-8"))
    out_places = []
    for key in order:
        p = places[key]
        wall = round((p["t1"] or 0) - (p["t0"] or 0), 1)
        cc = p.pop("carpet_checks")
        names = p.pop("unit_names")
        out_places.append(dict(
            p, wall_s=wall, by_kind=dict(p["by_kind"].most_common(TOP)), by_src=dict(p["by_src"].most_common(TOP)),
            by_visit=dict(p["by_visit"].most_common(TOP)), visits=dict(p["visits"].most_common()),
            units=[[u, n, names.get(u, "")] for u, n in p["units"].most_common(TOP) if n > 1],
            picks=dict(p["picks"].most_common()), rej=dict(p["rej"].most_common()),
            carpet_checks_max=max(cc) if cc else None, intents=dict(p["intents"].most_common()),
            loot_ms_max=max(p["loot_ms"].values()) if p["loot_ms"] else None, loot_ms=p["loot_ms"]))
    return {"run": run.name, "verdict": run_json.get("verdict"), "seconds": run_json.get("seconds"),
            "error": run_json.get("error"), "stall_s": sum(s.get("s", 0) for s in stalls if stall_kind(s) == "frame"),
            "load_stall_s": sum(s.get("s", 0) for s in stalls if stall_kind(s) == "load"),
            "stalls_rebuilt": bool(stalls and stalls[0].get("rebuilt")),
            "places": out_places, "deaths": deaths, "anomalies": dict(anomalies),
            "anomaly_events": anomaly_list[:60]}


def _brief(o: dict) -> dict:
    keep = ("_t", "ev", "id", "intent", "result", "reason", "type", "unit", "name", "kind", "src", "dmg", "hp",
            "visit", "cid", "outcome", "s", "attempt", "silent_s", "stop", "wall_s", "last_ms", "by", "replaced", "accepted")
    return {k: o[k] for k in keep if k in o}


def markdown(s: dict) -> str:
    L = [f"# {s['run']}", "", f"verdict **{s['verdict']}**, {s['seconds']} s"
         + (f", error: {s['error']}" if s.get("error") else ""),
         f"stalled frames: **{s['stall_s']} s**, loads: {s['load_stall_s']} s"
         + (" (rebuilt from the pass logs)" if s["stalls_rebuilt"] else ""), ""]
    if any(s["anomalies"].values()):
        L += ["anomalies: " + ", ".join(f"{k} {v}" for k, v in s["anomalies"].items() if v), ""]
    L += ["| lvl | place | wall s | stall s | loot ms max | hits | dmg | visits | picks |", "|---|---|---|---|---|---|---|---|---|"]
    for p in s["places"]:
        L.append(f"| {p['lvl']} | {p['place']} | {p['wall_s']} | {p['stall_s']} | {p['loot_ms_max'] or ''} | "
                 f"{p['hits']} | {p['dmg']} | {sum(p['visits'].values())} | {sum(p['picks'].values())} |")
    for p in s["places"]:
        if not (p["hits"] or p["visits"] or p["picks"] or p["stall_s"]):
            continue
        L += ["", f"## {p['lvl']} {p['place']}", ""]
        if p["stall_s"]:
            L.append(f"- stalls: {p['stalls']}, {p['stall_s']} s of {p['wall_s']} s wall")
        if p["loot_ms_max"]:
            L.append(f"- loot engine ms (game time) per loop: {p['loot_ms']}")
        if p["intents"]:
            L.append("- intents: " + ", ".join(f"{k} {v}" for k, v in p["intents"].items()))
        if p["visits"]:
            L.append("- visits: " + ", ".join(f"{k} {v}" for k, v in p["visits"].items()))
        if p["units"]:
            L.append("- visited more than once: " + ", ".join(f"{u} x{n} ({nm})" for u, n, nm in p["units"]))
        if p["picks"]:
            L.append("- picks: " + ", ".join(f"{k} {v}" for k, v in p["picks"].items())
                     + f"; max carpetChecks {p['carpet_checks_max']}")
            L.append("- rejected: " + ", ".join(f"{k} {v}" for k, v in p["rej"].items() if v))
        if p["hits"]:
            L.append(f"- hits {p['hits']} ({p['landed']} landed), dmg {p['dmg']}")
            L.append("  - by kind: " + ", ".join(f"{k} {v}" for k, v in p["by_kind"].items()))
            L.append("  - by source: " + ", ".join(f"{k} {v}" for k, v in p["by_src"].items()))
            L.append("  - by visit: " + ", ".join(f"{k} {v}" for k, v in p["by_visit"].items()))
        if p["external"]:
            L.append(f"- loot_external: {p['external']} (an outside intent replaced the loop's child)")
    if s["deaths"]:
        L += ["", "## deaths", ""]
        for d in s["deaths"]:
            L.append(f"- {d['_t']} s on {d['place']}; before it:")
            L += [f"  - {json.dumps(x)}" for x in d["last"]]
    if s["anomaly_events"]:
        L += ["", "## anomaly events", ""] + [f"- {json.dumps(x)}" for x in s["anomaly_events"]]
    return "\n".join(L) + "\n"


def _write_report(path: Path, text: str) -> None:
    """Replace a derived directory entry without opening/truncating its inode."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write(run: Path) -> dict:
    s = summarize(run)
    # Compute both payloads first; replacement is atomic per leaf, not as a pair.
    reports = ((run / "summary.json", json.dumps(s, indent=1, default=str)),
               (run / "summary.md", markdown(s)))
    for path, text in reports:
        _write_report(path, text)
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path)
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args(argv)
    s = write(a.run)
    if a.print:
        sys.stdout.write(markdown(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
