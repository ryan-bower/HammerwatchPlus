"""Run gamelab/scenarios/devarena/export-boot.json: write its two input files, run it, restore
the committed defaults (both vanilla) whatever the run did. Exits with the run's exit code.

    python tools/devarena/run_export_boot.py [--log LOG]

--log is a log holding a tuner override line; default the newest tuner-dock run's.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.devarena import export, overrides  # noqa: E402

REPO = overrides.REPO
EDITS = [["ran_mark", 0, "cooldown", "1234"], ["ran_mark", 0, "castpoint", "77"]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log")
    a = ap.parse_args(argv)
    if a.log:
        log = Path(a.log)
    else:
        runs = sorted((REPO / "gamelab" / "results").glob("*-tuner-dock-lab"))
        if not runs:
            print("no tuner-dock run to take the override line from; pass --log")
            return 2
        log = runs[-1] / "logs" / "pass1.HWR2.exe.log"
    state = overrides.last_in(log.read_text(encoding="utf-8", errors="replace"))
    if state is None or len(state["versions"]) != 3:
        print(f"{log}: want a 3-version override line, got {state and len(state['versions'])}")
        return 2
    sval_before = overrides.SVAL.read_text(encoding="utf-8")
    export_before = export.OUT.read_text(encoding="utf-8")
    try:
        overrides.write(state, overrides.SVAL)
        export.OUT.write_text(export.to_sval({"schema": 1, "version": 1, "note": "export-boot test", "edits": EDITS}),
                              encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "gamelab", "run", "devarena/export-boot", "--mode", "lab",
                            "--wait", "600"], cwd=REPO)
        return r.returncode
    finally:
        overrides.SVAL.write_text(sval_before, encoding="utf-8")
        export.OUT.write_text(export_before, encoding="utf-8")
        print("restored the override file and the export")


if __name__ == "__main__":
    sys.exit(main())
