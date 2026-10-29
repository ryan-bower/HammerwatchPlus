"""python -m gamelab run <scenario> [--mode lab|watch] [--wait S]   (see gamelab/launcher.py)
python -m gamelab suite <dir> [--wait S] [--stop-on-fail] [--since T]   # every scenario under gamelab/scenarios/<dir> ("" = all), one by one
python -m gamelab list [dir]
python -m gamelab reset     # after a refused run: kill lab game processes, wipe scratch
python -m gamelab doctor [--fix] [--confirm-saves] [--smoke]   # fresh clone: is this machine ready (gamelab/doctor.py)"""
import argparse
import json
import sys
import time

from gamelab import launcher, lock


def ran_since(since: str, mode: str) -> set[str]:
    """scenario names with a run in mode on the pinned build, started at or after since (a
    YYYYmmdd-HHMMSS run-dir stamp): what a resumed suite skips"""
    pin = json.loads((launcher.RESULTS.parent / "build_id.json").read_text(encoding="utf-8"))["build_id"]
    done = set()
    for rj in launcher.RESULTS.glob(f"*-{mode}/run.json"):
        if rj.parent.name[:15] < since:
            continue
        try:
            r = json.loads(rj.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if (r.get("build") or {}).get("build_id") == pin and not r.get("build_drift"):
            done.add(r.get("scenario"))
    return done


def expected_kill(f, code: int, rec: dict) -> bool:
    """A scenario with a test-hook outer_timeout ended the way it means to: TIMEOUT, and the only
    dirty-teardown reason is the runner kill."""
    try:
        sc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return False
    reasons = (rec.get("teardown") or {}).get("reasons") or []
    return (bool(sc.get("outer_timeout")) and code == 6 and rec.get("verdict") == "TIMEOUT"
            and bool(reasons) and all(r.startswith("runner was killed") for r in reasons))


def suite(folder: str, mode: str, wait: float, stop_on_fail: bool, accept_drift: bool, since: str = "") -> int:
    """Run every scenario under gamelab/scenarios/<folder> (recursively, sorted), each waiting
    for the lock, then print a table and write gamelab/results/suite-<time>-<folder>.json.
    since: skip scenarios already run on the pinned build from that stamp on (resume).
    Exit 0 when every run passed, else the worst run's code (refusals first)."""
    root = launcher.SCENARIOS / folder
    files = sorted(root.rglob("*.json")) if root.is_dir() else []
    if not files:
        print(f"no scenarios under {root}")
        return 2
    done = ran_since(since, mode) if since else set()
    rows, t0 = [], time.strftime("%Y%m%d-%H%M%S")
    for f in files:
        try:
            name = json.loads(f.read_text(encoding="utf-8")).get("name")
        except (ValueError, AttributeError):
            name = None
        if name in done:
            print(f"SUITE skip {name} (run since {since})", flush=True)
            continue
        start = time.time()
        code = launcher.run(str(f), mode, accept_drift, wait)
        if code == launcher.EXIT_SKIPPED:
            print(f"SUITE skip {name} (needs_hoh1, no HoH1 import here)", flush=True)
            continue
        runs = sorted((d for d in launcher.RESULTS.glob(f"*-{f.stem}-{mode}") if d.stat().st_mtime >= start - 1),
                      key=lambda d: d.name)
        rj = runs[-1] / "run.json" if runs else None
        rec = json.loads(rj.read_text(encoding="utf-8")) if rj and rj.is_file() else {}
        failed = [a["name"] for a in rec.get("assertions", []) if not a.get("ok")]
        rows.append({"scenario": str(f.relative_to(launcher.SCENARIOS).with_suffix("")).replace("\\", "/"),
                     "exit": code, "verdict": rec.get("verdict"), "run": runs[-1].name if runs else None,
                     "failed": failed, "secs": round(time.time() - start)})
        print(f"SUITE {code} {rows[-1]['verdict']} {rows[-1]['scenario']} {rows[-1]['run']}"
              + (f"  failed: {'; '.join(failed[:4])}" if failed else ""), flush=True)
        if expected_kill(f, code, rec):
            # timeout-outer-selftest kills its own runner on purpose: that dirty teardown is the
            # result, not a refusal, so the rest of the suite can run (suite 20261020-112717 stopped here)
            print(f"SUITE reset after {rows[-1]['scenario']} (its outer_timeout kill is the test)", flush=True)
            lock.reset()
        elif code in (2, 3, 4) or (stop_on_fail and code):
            break
    out = launcher.RESULTS / f"suite-{t0}-{folder.replace('/', '_') or 'all'}.json"
    out.write_text(json.dumps({"folder": folder, "mode": mode, "rows": rows}, indent=1), encoding="utf-8")
    passed = sum(1 for r in rows if r["exit"] == 0)
    print(f"suite {folder}: {passed}/{len(rows)} passed of {len(files)} -> {out}")
    codes = [r["exit"] for r in rows if r["exit"]]
    return next((c for c in (4, 3, 2, 5, 6, 1) if c in codes), 0)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["doctor"]:
        from gamelab import doctor
        return doctor.main(argv[1:])
    if argv[:1] == ["tail"]:
        from gamelab import logtail
        return logtail.main(argv[1:])
    ap = argparse.ArgumentParser(prog="python -m gamelab", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one scenario")
    r.add_argument("scenario")
    r.add_argument("--mode", choices=("lab", "watch"), default="watch",
                   help="watch (default, for a human at the keyboard) or lab; programmatic runs always pass --mode lab")
    r.add_argument("--accept-build-drift", action="store_true",
                   help="run despite a build-id mismatch; the run is stamped build_drift")
    r.add_argument("--wait", type=float, default=0, metavar="S",
                   help="wait up to S seconds while another live run holds the lock (default: refuse at once)")
    su = sub.add_parser("suite", help="run every scenario under gamelab/scenarios/<dir>, one after another")
    su.add_argument("folder")
    su.add_argument("--mode", choices=("lab", "watch"), default="lab")
    su.add_argument("--wait", type=float, default=3600, metavar="S", help="per run, as run --wait (default 3600)")
    su.add_argument("--stop-on-fail", action="store_true")
    su.add_argument("--accept-build-drift", action="store_true")
    su.add_argument("--since", default="", metavar="YYYYmmdd-HHMMSS",
                    help="skip scenarios already run on the pinned build from this run stamp on")
    li = sub.add_parser("list", help="list scenarios")
    li.add_argument("folder", nargs="?", default="", help="a folder under gamelab/scenarios/ (recursive)")
    sub.add_parser("doctor", help="fresh clone: check (--fix) every prerequisite, --confirm-saves")
    sub.add_parser("reset", help="clear a refused state: kill lab game processes, wipe scratch, mark clean")
    sub.add_parser("tail", help="the live game log, filtered to our mods' errors and boot milestones (-f follows)")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        if a.folder:
            for p in sorted((launcher.SCENARIOS / a.folder).rglob("*.json")):
                print(str(p.relative_to(launcher.SCENARIOS).with_suffix("")).replace("\\", "/"))
        else:
            for p in sorted(launcher.SCENARIOS.glob("*.json")):
                print(p.stem)
        return 0
    if a.cmd == "reset":
        from gamelab import lock
        return lock.reset()
    if a.cmd == "suite":
        return suite(a.folder, a.mode, a.wait, a.stop_on_fail, a.accept_build_drift, a.since)
    return launcher.run(a.scenario, a.mode, a.accept_build_drift, a.wait)


if __name__ == "__main__":
    sys.exit(main())
