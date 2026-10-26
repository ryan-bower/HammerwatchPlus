"""Clone a spec from the running game's log (docs/devarena/SPEC.md DoD 2, build step 7).

  {"do": "bot", "bot": "devarena_clone",
   "kwargs": {"src": "ranger_nature", "id": "ranger_test", "name": "Test Warden", "version": 1},
   "expect": {"terminal": "done", "identical": true}}

What a player does after composing a skill they like: tools/devarena/clone_spec.py over this
session's log, at the composed version. The log so far is written into the run folder, the clone
goes to <run>/clone/ (never over the mod the game booted with), and every file is compared with
mods/spec-<id>/. identical=true means the committed mod is exactly what this session's edit
clones to, so the cold relaunch that follows boots this session's spec.

Returns terminal ("done", "clone_failed"), code (clone_spec's exit), identical, files, differ
(relative paths that differ or exist on one side only), out.
"""
import filecmp
import io
from contextlib import redirect_stdout
from pathlib import Path

from tools.devarena import clone_spec

REPO = Path(__file__).resolve().parents[2]


def tree(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def run(p, src, id, name, version="live", results=None):
    results = Path(results or REPO / "gamelab" / "results" / p.run_id)
    log = results / "clone.HWR2.exe.log"
    log.write_text(p.game.read_log(), encoding="utf-8")
    out = results / "clone"
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = clone_spec.main(["--from", src, "--id", id, "--name", name, "--log", str(log),
                                "--version", str(version), "--out", str(out), "--force"])
    (results / "clone.out.txt").write_text(buf.getvalue(), encoding="utf-8")
    folder = "spec-" + id.replace("_", "-")
    made, mod = out / folder, REPO / "mods" / folder
    if code != 0 or not made.is_dir():
        return {"terminal": "clone_failed", "code": code, "out": buf.getvalue()[-600:]}
    a, b = tree(made), tree(mod) if mod.is_dir() else set()
    differ = sorted((a ^ b) | {f for f in a & b if not filecmp.cmp(made / f, mod / f, shallow=False)})
    return {"terminal": "done", "code": code, "identical": not differ, "files": len(a), "differ": differ[:20],
            "out": str(made)}
