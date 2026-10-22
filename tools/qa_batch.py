#!/usr/bin/env python3
"""Serial lab-only QA; no retries, reset, re-pinning, or implicit continuation.

Run GameLab doctor first. Journals/output stay in ignored gamelab/results/.
A .stop file is checked only between cases; incomplete batches exit 2.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def fingerprint():
    paths = sorted(set(subprocess.check_output([
        "git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
        "--", "mods", "gamelab", "tools"], cwd=ROOT).split(b"\0")) - {b""})
    digest = hashlib.sha256()
    for raw in paths:
        path = ROOT / raw.decode("utf-8")
        content = hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b"MISSING"
        digest.update(raw + b"\0" + content)
    return {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                           text=True).strip(),
            "source_sha256": digest.hexdigest(), "files": len(paths),
            "fingerprint_scope": "mods+gamelab+tools-v2"}


def command(name):
    return [sys.executable, "-m", "gamelab", "run", name, "--mode", "lab"]


def validate(names):
    directory = (ROOT / "gamelab" / "scenarios").resolve()
    for name in names:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
            raise ValueError(f"invalid scenario name: {name!r}; use a scenario stem")
        path = directory / (name + ".json")
        if path.resolve().parent != directory:
            raise ValueError(f"scenario escapes scenarios directory: {name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
            raise ValueError(f"invalid scenario object/steps: {name}")
        for key in ("timeout", "outer_timeout"):
            value = data.get(key, 300)
            if type(value) not in (int, float) or not 0 < value < float("inf"):
                raise ValueError(f"invalid {key}: {name}")


def successful(record, name):
    assertions = record.get("assertions")
    return (record.get("scenario") == name and record.get("mode") == "lab"
            and record.get("environment") == "gamelab" and record.get("verdict") == "PASS"
            and not record.get("error") and record.get("partial") is False
            and record.get("build_drift") is False
            and isinstance(record.get("teardown"), dict)
            and record["teardown"].get("clean") is True
            and isinstance(assertions, list) and bool(assertions)
            and all(isinstance(a, dict) and a.get("ok") is True for a in assertions))


def run_case(name, index, prefix, results, source):
    output = results / f"{prefix}-{index:03d}-{name}.out.txt"
    row = {"scenario": name, "index": index, "started": dt.datetime.now(dt.timezone.utc).isoformat(),
           "exit": None, "verdict": "NO_RESULT", "run_id": None, "result": None,
           "source_before": None, "source_after": None, "output": str(output.relative_to(ROOT)),
           "problems": []}
    started = time.monotonic()
    try:
        row["source_before"] = fingerprint()
        if row["source_before"] != source:
            raise ValueError("source drift before launch; batch source was not re-pinned")
        previous = set(results.glob(f"*-{name}-lab"))
        print(f"START {index}: {name}", flush=True)
        with output.open("x", encoding="utf-8") as stream:
            process = subprocess.run(command(name), cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT, text=True)
        row["exit"] = process.returncode
        fresh = set(results.glob(f"*-{name}-lab")) - previous
        if len(fresh) != 1:
            raise ValueError(f"expected one new result directory, found {len(fresh)}")
        directory = fresh.pop()
        row["run_id"] = directory.name
        record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        row["result"] = record
        if not isinstance(record, dict):
            raise ValueError("run.json must be an object")
        row["verdict"] = record.get("verdict", "NO_RESULT")
        inner = json.loads((directory / "inner.json").read_text(encoding="utf-8"))
        if (not isinstance(inner, dict) or inner.get("scenario") != name
                or inner.get("mode") != "lab" or inner.get("partial") is not False or inner.get("error")):
            raise ValueError("missing, mismatched, partial or errored runner result")
        if process.returncode != 0 or not successful(record, name):
            raise ValueError("nonzero exit or unsafe/non-PASS result; inspect native records")
    except (Exception, KeyboardInterrupt) as error:
        row["problems"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            row["source_after"] = fingerprint()
            if row["source_after"] != source:
                row["problems"].append("source drift after case; continuation refused")
        except Exception as error:
            row["problems"].append(f"fingerprint failed: {error}")
    row["seconds"] = round(time.monotonic() - started, 3)
    row["ok"] = not row["problems"]
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Stop between cases: create gamelab/results/qa-batch-<sanitized-label>.stop. "
        "Labels use letters/digits/_/-; other characters become '-'. Existing journals refuse reuse. "
        "A stale qa-batch.lock requires inspection; this tool never resets it."))
    parser.add_argument("--label", help="unique local journal label (required except --fingerprint)")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="validate/print only; no writes or launches")
    modes.add_argument("--fingerprint", action="store_true", help="print source fingerprint only")
    parser.add_argument("scenarios", nargs="*")
    args = parser.parse_args(argv)
    if args.fingerprint:
        if args.label or args.scenarios:
            parser.error("--fingerprint takes no label or scenarios")
        print(json.dumps(fingerprint(), sort_keys=True))
        return 0
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", args.label or "").strip("-_")
    if not label or len(label) > 80 or not args.scenarios:
        parser.error("provide --label (1-80 filename characters after sanitizing) and scenario stems")
    results = ROOT / "gamelab" / "results"
    prefix = "qa-batch-" + label
    journal, stop = results / (prefix + ".jsonl"), results / (prefix + ".stop")
    try:
        validate(args.scenarios)  # Entire queue before any file write or launch.
        if journal.exists():
            raise ValueError("journal already exists; use a new label to preserve outcomes")
        source = fingerprint()
        print(json.dumps({"source": source, "journal": str(journal), "stop_file": str(stop)}), flush=True)
        if args.dry_run:
            for name in args.scenarios:
                print(json.dumps({"command": command(name)}))
            return 0
        results.mkdir(parents=True, exist_ok=True)
        lock = results / "qa-batch.lock"
        with lock.open("x", encoding="utf-8") as owner:
            owner.write(json.dumps({"label": label, "source": source}) + "\n")
        try:
            with journal.open("x", encoding="utf-8") as stream:
                for index, name in enumerate(args.scenarios, 1):
                    if stop.exists():
                        stream.write(json.dumps({"event": "STOP_REQUESTED", "next": name,
                                                 "completed": index - 1, "ok": False}) + "\n")
                        print("STOP_REQUESTED: incomplete batch", flush=True)
                        return 2
                    row = run_case(name, index, prefix, results, source)
                    stream.write(json.dumps(row) + "\n")
                    stream.flush()
                    print(json.dumps(row), flush=True)
                    if not row["ok"]:
                        return 1
        finally:
            lock.unlink()
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
