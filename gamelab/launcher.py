"""Outer GameLab launcher: preflight, then the inner runner on a hidden desktop, then the
checks that only the outside can make (the user's config and saves untouched, focus never
left the user's window).

    python -m gamelab run <scenario> --mode lab     # programmatic runs: always --mode lab
    python -m gamelab run <scenario>                # a human at the keyboard: watch mode

Preflight, in order, any failure aborts before the game starts (docs/PLAYBOOK.md P6 item 1):
  0. save backups confirmed on this machine (`python -m gamelab doctor --confirm-saves`)
  1. tools/saves.py backup         2. build-id gate (exit 3)
  3. tools/env_link.py --verify    4. environment resolution (here) + live verification
                                      of the running process (gamelab/runner.py)

One run at a time, and never after a dirty teardown (gamelab/lock.py; exit 4,
`python -m gamelab reset` clears it). `--accept-build-drift` lets one run past the build
gate and stamps "build_drift": true into its run.json.

Verdicts (exit code): PASS (0), FAIL (1: an assertion failed), INVALID (5: the run itself
cannot be trusted: the user's config or saves changed, focus moved, or probes and the
renderer disagreed), TIMEOUT (6: the scenario's deadline passed; whatever was collected
is still in run.json, flagged "partial"), SKIPPED (7: a `"needs_hoh1": true` scenario on a
machine without the HoH1 import its mods read; nothing ran).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
from gamelab import env, lock, winproc, runtime  # noqa: E402
from gamelab.runner import restore_written  # noqa: E402
import gamepaths  # noqa: E402
import hidden_desktop  # noqa: E402
import pin_build  # noqa: E402
import saves  # noqa: E402

SCENARIOS = REPO / "gamelab" / "scenarios"
RESULTS = REPO / "gamelab" / "results"
INVALIDATING = ("user config unchanged", "user saves unchanged", "install res/ unchanged",
                "focus never left the user's window", "no game-tree window on the input desktop",
                "foreground never the game tree from launch to first frame")


def sha(p: Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def mods_version() -> dict:
    """Mod sources as deployed into the GameLab game dir: git tree id + dirty flag per mod."""
    out = {}
    for m in env.environments()["gamelab"]["mods"]:
        tree = subprocess.run(["git", "rev-parse", f"HEAD:mods/{m}"], cwd=REPO, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", f"mods/{m}"], cwd=REPO, capture_output=True, text=True).stdout.strip())
        out[m] = {"tree": tree or None, "dirty": dirty}
    return out


def preflight(mode: str, accept_drift: bool = False, mods: list[str] | None = None,
              packages: list[str] | None = None) -> tuple[list[str], list[str]]:
    slot = runtime.current()
    if slot and env.GAME.resolve() != slot.game_dir.resolve():
        return ["runtime slot game directory does not match its admission"], []
    errors = [f"saves: {p}" for p in saves.confirmation_problems()]
    if errors:
        return errors, []
    code = saves.backup(quiet=True)
    if code:
        errors.append(f"saves.py backup failed (exit {code})")
    mism = pin_build.mismatch()
    if mism and not accept_drift:
        print("build gate:", "; ".join(mism))
        sys.exit(pin_build.EXIT_BUILD_MISMATCH)
    if mism:
        print("BUILD DRIFT accepted for this run:", "; ".join(mism))
    if packages:
        # the packages as players get them: built from this tree now, without local content
        r = subprocess.run([sys.executable, str(REPO / "tools" / "build.py"), *packages], cwd=REPO,
                           capture_output=True, text=True)
        if r.returncode:
            errors.append("tools/build.py " + " ".join(packages) + ": " + (r.stderr or r.stdout).strip()[-400:])
            return errors, mism
    problems = env.link(fix=True, mods=mods, packages=packages)
    errors += [f"env_link: {p}" for p in problems]
    gl = env.environments()["gamelab"]
    user_data = Path(gl["user_data"].replace("<repo>", str(REPO))).resolve()
    if not slot and env.GAME.resolve() != user_data and user_data not in env.GAME.resolve().parents:
        errors.append(f"gamelab game dir {env.GAME} is not the declared user_data {user_data}")
    profile = env.cvars((env.SETTINGS / mode / "HWR2.exe.cfg").read_text())
    if mode == "lab" and any(float(v) != 0 for k, v in profile.items() if k.startswith("snd_volume")):
        errors.append("lab profile is not muted on disk")
    if profile.get("g_save_slot_cloud") not in ("0", "false"):
        errors.append("profile enables cloud saves (g_save_slot_cloud must be 0)")
    return errors, mism


def scenario_file(name: str) -> Path:
    """A scenario by name (`mod-x`, or a path under gamelab/scenarios/ such as
    `it/gambler/gambler-bet`) or by .json path."""
    return Path(name) if name.endswith(".json") else SCENARIOS / f"{name}.json"


def acquire(scenario_name: str, mode: str, wait: float = 0) -> None:
    """lock.acquire; with `wait` seconds, wait while another LIVE run holds the lock (another
    agent's run). A stale lock or a dirty teardown is still refused at once: those need a
    look, then `python -m gamelab reset`."""
    if not math.isfinite(wait) or wait < 0:
        raise lock.Refused("--wait must be a finite nonnegative number of seconds")
    deadline, said, pending = time.monotonic() + wait, False, None
    while True:
        if pending is not None and time.monotonic() >= deadline:
            raise pending
        try:
            lock.acquire(scenario_name, mode)
            return
        except lock.Refused as error:
            remaining = deadline - time.monotonic()
            if not (wait and isinstance(error, lock.Busy) and remaining > 0):
                raise
            if not said:
                print("WAITING", error, flush=True)
                said = True
            pending = error
            time.sleep(min(3.0, remaining))



EXIT_SKIPPED = 7


def hoh1_missing(scenario: dict) -> list[str]:
    """`"needs_hoh1": true`: the HoH1 imports (tools/import_hoh1.py, named like the mods that read
    them; every import when none of its mods has one) this machine lacks."""
    if not scenario.get("needs_hoh1"):
        return []
    from tools import import_hoh1
    outputs = import_hoh1.IMPORT_OUTPUTS
    want = [m for m in env.expand_mods(scenario.get("mods")) if m in outputs] or list(outputs)
    return [m for m in want if not outputs[m].exists()]


def run(scenario_name: str, mode: str, accept_drift: bool = False, wait: float = 0) -> int:
    scenario_path = scenario_file(scenario_name)
    scenario_name = scenario_path.stem
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    slot = runtime.current()
    if slot and (mode != "lab" or accept_drift):
        print("REFUSED runtime slots require lab mode and the pinned build")
        return lock.EXIT_REFUSED
    if slot:
        from gamelab.pool import validate_scenario
        try:
            admitted = validate_scenario(scenario_name)
            if scenario_path.resolve() != (SCENARIOS / (scenario_name + ".json")).resolve() or admitted != scenario:
                raise ValueError("slot scenario is not the canonical admitted file")
        except (OSError, ValueError) as error:
            print("REFUSED", error)
            return lock.EXIT_REFUSED
    missing = hoh1_missing(scenario)
    if missing:
        print("SKIPPED", f"needs_hoh1: no HoH1 import of {', '.join(missing)} on this machine "
              "(python -m gamelab doctor --hoh1 <folder> --fix)")
        return EXIT_SKIPPED
    # the lock before preflight: preflight re-links the lab mods dir (env.link), and doing that
    # under another live run drops that run's mods under test from the game dir
    try:
        with runtime.preparation_guard():
            acquire(scenario_name, mode, wait)
    except lock.Refused as e:
        print("REFUSED", e)
        return lock.EXIT_REFUSED
    try:
        with runtime.preparation_guard():
            errors, drift = preflight(mode, accept_drift, env.expand_mods(scenario.get("mods")), scenario.get("packages"))
    except BaseException:
        lock.release(scenario_name, [])     # nothing ran (e.g. the build gate's exit 3)
        raise
    if errors:
        lock.release(scenario_name, [])
        for e in errors:
            print("PREFLIGHT", e)
        return 2
    try:
        return _run(scenario_path, scenario_name, scenario, mode, drift)
    except BaseException as e:
        if lock.owned():
            lock.release(scenario_name, [f"launcher raised {type(e).__name__}: {e}"])
        raise


def _run(scenario_path: Path, scenario_name: str, scenario: dict, mode: str, drift: list[str]) -> int:
    slot = runtime.current()
    results = slot.results if slot else RESULTS / f"{time.strftime('%Y%m%d-%H%M%S')}-{scenario_name}-{mode}"
    baseline_step = "result directory"
    try:
        results.mkdir(parents=True)
        baseline_step = "user config discovery"
        config = gamepaths.real_config()
        baseline_step = "user config snapshot"
        config_before = sha(config)
        baseline_step = "install res snapshot"
        res_before = env.install_res_snapshot()
        baseline_step = "user save snapshot"
        saves_before = saves.snapshot()
        baseline_step = "baseline evidence"
        # Preserve completed observations locally even if a later preflight
        # operation fails. These files never establish a native run or PASS.
        res_evidence = {"before": res_before}
        (results / "isolation-res.json").write_text(json.dumps(res_evidence, indent=1), encoding="utf-8")
    except (OSError, saves.MetadataError) as error:
        # No runner/game has started. Keep any partial evidence and refuse;
        # never reinterpret a denied baseline read as gameplay or retry ACLs.
        print("PREFLIGHT", f"{baseline_step}: {type(error).__name__}: {error}")
        try:
            lock.abandon()
        except (lock.Refused, OSError) as refusal:
            print("REFUSED", f"cannot release unused runtime ownership: {refusal}")
            return lock.EXIT_REFUSED
        return 2
    cmd = [sys.executable, "-m", "gamelab.runner", str(scenario_path), str(results), "--mode", mode]
    timeout = scenario.get("timeout", 300) * 3          # fixture passes + the run itself
    timeout = scenario.get("outer_timeout", timeout)   # test hook: kill before the runner's own deadline
    t0 = time.time()
    timed_out = aborted = False
    runner_box = None
    with winproc.ForegroundSampler(game_dir=str(env.GAME.resolve()) if mode == "lab" else None) as fg:
        try:
            options = {}
            if slot:
                options = dict(desktop_name=slot.desktop_name, job_name=slot.job_name,
                               affinity_mask=slot.affinity_mask, memory_mb=slot.memory_mb,
                               allow_breakaway=False)
            done = hidden_desktop.run(cmd, cwd=REPO, timeout=timeout, visible=(mode == "watch"), **options)
            inner_code, stdout, stderr = done.returncode, done.stdout, done.stderr
            runner_box = getattr(done, "isolation", None)
        except subprocess.TimeoutExpired as e:
            inner_code, stdout, stderr = None, str(e.stdout or ""), f"timeout after {timeout}s"
            timed_out = True
            runner_box = getattr(e, "isolation", None)
        except KeyboardInterrupt:
            # Ctrl+C (the user ending a watch session): hidden_desktop's job object has killed
            # the game tree, and the checks below still run, so this is a normal end, not a
            # dirty teardown that refuses the next run (arena watch 20261021-192533 needed a reset)
            inner_code, stdout, stderr = None, "", "aborted by Ctrl+C"
            aborted = True
            print("ABORTED by Ctrl+C: checking the install and tearing down", flush=True)
    (results / "runner.out.txt").write_text(f"{stdout}\n--- stderr ---\n{stderr}", encoding="utf-8")
    # a killed runner never reached its finally: put back what its write_* steps edited
    restored = restore_written(results)
    if restored:
        print("restored after the runner died:", ", ".join(restored))
    inner_path = results / "inner.json"
    inner = json.loads(inner_path.read_text(encoding="utf-8")) if inner_path.exists() else {"error": "runner wrote no inner.json"}
    assertions = list(inner.get("assertions", []))

    def outer(name, ok, detail=""):
        assertions.append({"name": name, "ok": bool(ok), "detail": detail})

    if slot:
        outer("owned worker job fully exited", isinstance(runner_box, dict)
              and runner_box.get("job_name") == slot.job_name and runner_box.get("tree_clean") is True
              and runner_box.get("active_processes") == 0, json.dumps(runner_box))
    outer("user config unchanged", sha(config) == config_before, str(config))
    try:
        res_after = env.install_res_snapshot()
    except OSError as e:
        res_after = {"<snapshot failed>": {"error": str(e)}}   # differs from before: INVALID below
    res_evidence["after"] = res_after
    res_evidence["changed"] = {k: {"before": res_before.get(k), "after": res_after.get(k)}
                               for k in sorted(set(res_before) | set(res_after))
                               if res_before.get(k) != res_after.get(k)}
    (results / "isolation-res.json").write_text(json.dumps(res_evidence, indent=1), encoding="utf-8")
    outer("install res/ unchanged", res_after == res_before,
          ", ".join(sorted(k for k in set(res_before) | set(res_after) if res_before.get(k) != res_after.get(k))))
    want_ver = (pin_build.pinned() or {}).get("game_version", "unknown")
    seen_ver = sorted({m.group(1) for log in (results / "logs").glob("pass*.HWR2.exe.log")
                       for m in [re.search(r"\] (Build \d+):", log.read_text(encoding="utf-8", errors="replace")[:600])] if m})
    outer("game log names the pinned version", want_ver == "unknown" or seen_ver in ([], [want_ver]),
          f"pin {want_ver}, logs {seen_ver or 'none'}" + (" (pin_build.py --game-version to pin it)" if want_ver == "unknown" else ""))
    changed = saves.diff(saves_before, saves.snapshot())
    outer("user saves unchanged", not changed, ", ".join(changed))
    report = fg.report()
    if mode == "lab":
        # every switch is listed; only one the user's own input does not explain invalidates
        outer("focus never left the user's window", not report["unexplained"], json.dumps(report))
        outer("no game-tree window on the input desktop", report["window_scans"] > 0 and not report["game_windows_on_input_desktop"],
              f"{report['window_scans']} scans, leaks {report['game_windows_on_input_desktop']}")
    else:
        # watch: the window is visible and the human may click it, but from launch to the
        # first frame the foreground must never belong to the GameLab tree (no focus steal).
        # No first frame (the game exited while booting) checks the whole run instead: a boot
        # that dies is the run's own error, not an INVALID (watch 20261019-005852: the game
        # exited code 0 at 5 s, nothing stole focus, and the verdict hid the GameError)
        first = inner.get("first_frame_at")
        stolen = [sw for sw in report["switches"] if sw.get("ours") and (first is None or fg.t0 + sw["t"] < first)]
        outer("foreground never the game tree from launch to first frame", not stolen,
              json.dumps({"first_frame_s": round(first - fg.t0, 2) if first else None, "stolen": stolen}))
    failed = [a for a in assertions if not a["ok"]]
    shot_fail = [a for a in failed if a["name"].startswith("shot ")]
    probes_ok = not [a for a in failed if not a["name"].startswith("shot ")]
    if any(a["name"] in INVALIDATING for a in failed) or (shot_fail and probes_ok):
        verdict = "INVALID"
    elif aborted:
        verdict = "ABORTED"
    elif timed_out or inner.get("timeout"):
        verdict = "TIMEOUT"
    elif failed or "error" in inner or inner_code != 0:
        verdict = "FAIL"
    else:
        verdict = "PASS"
    dirty = [f"{a['name']}: {a['detail']}" for a in assertions if a["name"].endswith("exited cleanly") and not a["ok"]]
    if aborted:
        pass                                   # a runner cut short by Ctrl+C has no full inner.json by design
    elif not (results / "inner.json").exists():
        dirty.append("runner wrote no inner.json")
    elif inner.get("partial"):
        dirty.append("runner was killed before it finished (inner.json is partial)")
    with lock.finishing(results.name, dirty) as teardown:
        record = {"verdict": verdict, "build_drift": bool(drift), "teardown": teardown, "scenario": scenario_name, "mode": mode, "environment": "gamelab",
                  "build": pin_build.live(), "fixture": inner.get("fixture"), "mods": mods_version(),
                  "seconds": round(time.time() - t0, 1), "foreground": report, "error": inner.get("error"),
                  "assertions": assertions, "live": inner.get("live"), "passes": inner.get("passes"),
                  "partial": bool(inner.get("partial")), "menu": inner.get("menu"),
                  "boundaries": inner.get("boundaries"), "travel_revision": inner.get("travel_revision"),
                  "explore": inner.get("explore")}
        if slot:
            record["runtime_slot"] = {"pool_id": slot.pool_id, "slot_id": slot.slot_id,
                                      "game_dir": str(slot.game_dir), "desktop_name": slot.desktop_name,
                                      "job_name": slot.job_name}
            record["runner_box"] = runner_box
        (results / "run.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        if inner.get("boundaries"):
            (results / "boundaries.md").write_text(boundary_table(inner["boundaries"]), encoding="utf-8")
        # summary.{json,md}: per place wall/stall/loot/hits (tools/run_summary.py); never fails the run
        try:
            sys.path.insert(0, str(REPO / "tools"))
            import run_summary
            summ = run_summary.write(results)
            if summ.get("stall_s"):
                print(f"  stalled frames: {summ['stall_s']} s (summary.md)")
        except Exception as e:                     # noqa: BLE001 - a report, not a gate
            print(f"  summary failed: {type(e).__name__}: {e}")
        for a in assertions:
            print(f"  [{'PASS' if a['ok'] else 'FAIL'}] {a['name']}" + (f"  -- {a['detail']}" if a["detail"] and not a["ok"] else ""))
        if inner.get("error"):
            print("  error:", inner["error"])
        if drift:
            print("  BUILD DRIFT: this run is not comparable to clean runs")
        if not teardown["clean"]:
            print("  dirty teardown:", "; ".join(teardown["reasons"]))
        print(f"{verdict}  {scenario_name} ({mode}) in {record['seconds']}s -> {results.relative_to(REPO)}")
        return {"PASS": 0, "FAIL": 1, "INVALID": 5, "TIMEOUT": 6, "ABORTED": 130}[verdict]


def boundary_table(rows: list[dict]) -> str:
    """The run's boundary rows (repro playbook 3.1) as a markdown table."""
    out = ["| boundary | kind | copies | re-initialises | probed | before | after | ok |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        for c in r["cells"] or [{"path": "-", "rule": "", "before": "", "after": ""}]:
            out.append(f"| {r['name']} | {r['kind']} | {r['copies']} | {r['reinit']} | {c['rule']} `{c['path']}` "
                       f"| `{json.dumps(c['before'])}` | `{json.dumps(c['after'])}` | {'yes' if r['ok'] else 'NO'} |")
    return "\n".join(out) + "\n"
