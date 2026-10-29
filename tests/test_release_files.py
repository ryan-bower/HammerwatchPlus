"""A release package (tools/build.py without --with-local) packs only files the repo ships.

A file git ignores is machine-local: HoH1 content tools/import_hoh1.py cut from the player's
own install, or something a tool made. It may reach a package only when

- module.json lists it as `local` (packed with --with-local, never released), or
- a tool remakes it from the HoH2 base on every machine: the .gitignore pattern that ignores
  it sits in a `# >>> tools/<tool>.py (generated from the HoH2 base ...)` block
  (tools/class_units.py, tools/make_forgemaster_risen.py, ...).

HWP-pets.bin carried 216 imported HoH1 pet files before the pets module listed them
(2026-10-27).
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import build  # noqa: E402

BASE_BLOCK = "(generated from the HoH2 base"


def released_modules() -> list[str]:
    doc = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    mods = {m for p in doc["packages"] for m in p["mods"]}
    for d in (REPO / "mods").iterdir():
        cfg = d / "module.json"
        if cfg.is_file() and json.loads(cfg.read_text(encoding="utf-8")).get("library"):
            mods.add(d.name)
    return sorted(mods)


def base_block_lines(gitignore: Path) -> set[int]:
    """1-based line numbers inside the generated-from-the-HoH2-base blocks of a .gitignore."""
    inside, lines = False, set()
    for n, line in enumerate(gitignore.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("# >>> "):
            inside = BASE_BLOCK in line
        elif line.startswith("# <<< "):
            inside = False
        elif inside:
            lines.add(n)
    return lines


def ignored(paths: list[str]) -> dict[str, tuple[str, int]]:
    """path -> (the .gitignore, line) that ignores it, for the ignored ones."""
    if not paths:
        return {}
    out = subprocess.run(["git", "check-ignore", "-v", "-z", "--stdin"], cwd=REPO,
                         input="\0".join(paths).encode(), capture_output=True)
    f = out.stdout.decode().split("\0")
    return {f[i + 3]: (f[i], int(f[i + 1])) for i in range(0, len(f) - 3, 4)}


def leaks() -> list[str]:
    bad = []
    blocks: dict[str, set[int]] = {}
    for mod in released_modules():
        cfg = build.load_module(REPO / "mods" / mod)
        rels = [rel for rel, _ in build.module_files(cfg, with_local=False) if rel not in cfg["generated"]]
        for path, (source, line) in sorted(ignored([f"mods/{mod}/{rel}" for rel in rels]).items()):
            if source not in blocks:
                blocks[source] = base_block_lines(REPO / source)
            if line not in blocks[source]:
                bad.append(path)
    return bad


def test_no_ignored_file_in_a_release_package():
    bad = leaks()
    assert not bad, f"{len(bad)} git-ignored file(s) would ship; list them under `local` in module.json: {bad[:10]}"
