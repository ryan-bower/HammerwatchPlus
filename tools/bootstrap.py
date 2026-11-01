#!/usr/bin/env python3
"""bootstrap.py - regenerate every gitignored, regenerable path from the local game install.

    bootstrap.py                     # required tier (refuses if the install's build != gamelab/build_id.json)
    bootstrap.py --force             # re-extract even where outputs exist
    bootstrap.py --with-community    # + optional tier from the shared folder (docs/SOURCES.md)
    bootstrap.py --verify            # compare the tree to gamelab/manifest.json, write manifest.local.json
    bootstrap.py --record            # (after a deliberate re-pin) rewrite gamelab/manifest.json from the tree

Required tier, in order:
  1. build-id gate (tools/pin_build.py)
  2. tools/bin/PACKAGER.exe: Steam-free patched copy + the game's DLLs (tools/patch_packager.py)
  3. gamecode/sdk/hoh2/: PACKAGER --unpack of res/assets.bin, plus res/language/
  4. gamecode/sdk/hoh1/: hwr_archive extract of HoH1's assets.bin, when HoH1 is installed
  5. gamecode/assets/hwr2_api_strings.txt: printable strings of HWR2.exe (the registered script API)
  6. gamecode/datatables/: JSON exports (tools/export_datatables.py)
  7. tools/bin/hwr2_capture.dll: GameLab's in-process shim (tools/capture_shim/, gcc)
  8. tools/hidden_desktop.py importable (vendored, committed)

The manifest records, per output tree and top-level subdirectory, a file count, byte
count and a sha256 over the sorted (path, sha256) list. PACKAGER output is deterministic
(measured: two unpacks hash identical), so these are output hashes. The shim DLL is not
(the linker stamps it), so its machine-local hwr2_capture.build.json records the source
and DLL sha256 plus the successful gcc version. Both local artifacts are excluded from
the portable tree hash; --verify checks both hashes. Legacy source-only stamps need a
rebuild at an authorized setup boundary; verification never upgrades them by assertion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gamepaths  # noqa: E402
import pin_build  # noqa: E402

REPO = gamepaths.REPO
MANIFEST = gamepaths.GAMELAB / "manifest.json"
MANIFEST_LOCAL = gamepaths.GAMELAB / "manifest.local.json"
SOURCES = gamepaths.DOCS / "SOURCES.md"
PACKAGER_TIMEOUT = 900
REQUIRED_TREES = ["gamecode/sdk/hoh2", "gamecode/assets", "gamecode/datatables", "tools/bin"]
OPTIONAL_REQUIRED = ["gamecode/sdk/hoh1"]          # required tier, but only where HoH1 is installed
COMMUNITY_TREES = ["docs/community/discord"]


NOT_HASHED = {"_hwr_manifest.json", "hwr2_capture.dll", "hwr2_capture.build.json"}   # recorded by input instead (see above)
SHIM_SRC = gamepaths.TOOLS / "capture_shim" / "hwr2_capture.c"
SHIM_DLL = gamepaths.TOOLS_BIN / "hwr2_capture.dll"


def step(msg: str) -> None:
    print(f"[bootstrap] {msg}", flush=True)


def _checked(path: Path) -> Path:
    """Generated inputs/outputs remain ordinary paths beneath the repository."""
    root, path = Path(REPO).absolute(), Path(path).absolute()
    if not path.is_relative_to(root):
        raise ValueError(f"path is outside the repository: {path}")
    current = root
    checks = [root]
    for part in path.relative_to(root).parts:
        current = current / part
        checks.append(current)
    for entry in checks:
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"linked generated path is not accepted: {entry}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"generated path escapes the repository: {path}")
    return path


def _files(root: Path):
    root = _checked(root)
    for entry in sorted(root.iterdir()):
        safe = _checked(entry)
        if safe.is_dir():
            yield from _files(safe)
        elif safe.is_file():
            yield safe
        else:
            raise ValueError(f"unsupported generated entry: {safe}")


def _shim_problems() -> list[str]:
    try:
        source = _checked(SHIM_SRC)
        dll = _checked(SHIM_DLL)
        stamp = _checked(gamepaths.TOOLS_BIN / "hwr2_capture.build.json")
        if not (dll.is_file() and stamp.is_file()):
            return ["tools/bin/hwr2_capture.dll: not built"]
        value = json.loads(stamp.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("shim build stamp must be an object")
        for key in ("source_sha256", "dll_sha256"):
            if not isinstance(value.get(key), str) or re.fullmatch(r"[0-9a-f]{64}", value[key]) is None:
                raise ValueError(f"shim stamp needs {key}; rebuild with bootstrap.py")
        if not isinstance(value.get("gcc"), str) or not value["gcc"].strip():
            raise ValueError("shim stamp needs the successful compiler version")
        if value["source_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError("capture shim source changed; rebuild with bootstrap.py")
        data = dll.read_bytes()
        if not data or value["dll_sha256"] != hashlib.sha256(data).hexdigest():
            raise ValueError("capture shim bytes differ from their successful build stamp")
        return []
    except (OSError, ValueError) as error:
        return [f"tools/bin/hwr2_capture.dll: {error}"]


def _manifest_shape(value: dict) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("tiers"), dict):
        raise ValueError("manifest must contain a tiers object")
    tiers = value["tiers"]
    if "required" not in tiers or set(tiers) - {"required", "optional"}:
        raise ValueError("manifest tiers must be required and optional")
    required = tiers["required"]
    if not isinstance(required, dict) or not set(REQUIRED_TREES).issubset(required):
        raise ValueError("manifest omits required generated trees")
    allowed = {"required": set(REQUIRED_TREES + OPTIONAL_REQUIRED), "optional": set(COMMUNITY_TREES)}
    for tier, trees in tiers.items():
        if not isinstance(trees, dict) or set(trees) - allowed[tier]:
            raise ValueError(f"unexpected generated tree in {tier} manifest")
        for tree, groups in trees.items():
            if not isinstance(groups, dict) or (tree in REQUIRED_TREES and not groups):
                raise ValueError(f"missing hash groups for {tree}")
            for group, metadata in groups.items():
                if not isinstance(group, str) or not group or "/" in group or "\\" in group or group == "..":
                    raise ValueError("manifest groups must be top-level names")
                if not isinstance(metadata, dict) or set(metadata) != {"files", "bytes", "sha256"}:
                    raise ValueError("manifest hash group has an invalid shape")
                if type(metadata["files"]) is not int or metadata["files"] <= 0 \
                        or type(metadata["bytes"]) is not int or metadata["bytes"] < 0 \
                        or not isinstance(metadata["sha256"], str) \
                        or re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) is None:
                    raise ValueError("manifest hash group has invalid counts or digest")
    pinned = pin_build.pinned()
    if not isinstance(pinned, dict) or not isinstance(pinned.get("build_id"), str) or not pinned["build_id"] \
            or value.get("build_id") != pinned["build_id"]:
        raise ValueError("generated manifest build does not match the current pin; do not re-pin automatically")
    return tiers


def tree_hash(root: Path) -> dict:
    """{subdir: {files, bytes, sha256}} for the top-level entries of root ('.' = loose files)."""
    groups: dict[str, list[tuple[str, str, int]]] = {}
    for f in _files(root):
        if not f.is_file() or f.name in NOT_HASHED:
            continue
        rel = f.relative_to(root).as_posix()
        top = rel.split("/", 1)[0] if "/" in rel else "."
        data = f.read_bytes()
        groups.setdefault(top, []).append((rel, hashlib.sha256(data).hexdigest(), len(data)))
    out = {}
    for top, items in sorted(groups.items()):
        h = hashlib.sha256("".join(f"{p}\0{s}\n" for p, s, _ in items).encode()).hexdigest()
        out[top] = {"files": len(items), "bytes": sum(n for *_, n in items), "sha256": h}
    return out


def packager_unpack(archive: Path, dest: Path) -> None:
    """Unpack with the patched PACKAGER on the hidden desktop. It ends on a modal error box
    (five sound-bank entries without data, docs/packager.md), so the run is expected to hit
    the timeout or exit -1; completeness is checked against the archive's own entry list."""
    import hidden_desktop
    import hwr_archive
    want = [e.path for e in hwr_archive.Archive.read(archive).entries if not e.is_bank]
    dest.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    # The driver runs on the hidden desktop with PACKAGER as its child and returns once
    # every entry is on disk and the tree has stopped growing; the job then kills the box.
    try:
        done = hidden_desktop.run([sys.executable, __file__, "--unpack-driver", str(archive), str(dest), str(len(want))],
                                  cwd=gamepaths.TOOLS_BIN, timeout=PACKAGER_TIMEOUT)
        print(done.stdout.strip())
    except subprocess.TimeoutExpired:
        pass
    missing = [p for p in want if not (dest / p).is_file()]
    if missing:
        sys.exit(f"PACKAGER unpack of {archive} incomplete: {len(missing)} of {len(want)} files missing "
                 f"(first: {missing[:3]})")
    step(f"unpacked {len(want)} files from {archive.name} in {time.time() - t0:.0f}s")


def unpack_driver(archive: str, dest: str, count: int) -> int:
    """Runs on the hidden desktop: start PACKAGER, wait for `count` files to settle."""
    proc = subprocess.Popen([str(gamepaths.TOOLS_BIN / "PACKAGER.exe"), f"--unpack={archive}",
                             f"--destination={dest}"], cwd=str(gamepaths.TOOLS_BIN))
    last, stable_since = -1, time.time()
    while True:
        time.sleep(2)
        n = sum(1 for f in Path(dest).rglob("*") if f.is_file()) if Path(dest).is_dir() else 0
        if n != last:
            last, stable_since = n, time.time()
        exited = proc.poll() is not None
        if (n >= count and time.time() - stable_since > 4) or (exited and time.time() - stable_since > 4):
            print(f"driver: {n}/{count} files, PACKAGER {'exited ' + str(proc.returncode) if exited else 'blocked on its dialog'}")
            return 0


def ensure_packager(force: bool) -> None:
    exe = gamepaths.TOOLS_BIN / "PACKAGER.exe"
    if exe.is_file() and not force:
        return
    game = gamepaths.hoh2_dir()
    gamepaths.TOOLS_BIN.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(gamepaths.TOOLS / "patch_packager.py"), str(game / "PACKAGER.exe"), str(exe)])
    if r.returncode:
        sys.exit("patch_packager.py failed")
    for dll in game.glob("*.dll"):
        shutil.copy2(dll, gamepaths.TOOLS_BIN / dll.name)
    step("built tools/bin/PACKAGER.exe")


def build_shim(force: bool) -> None:
    """Publish a complete compiler-checked DLL/stamp pair or retain the prior pair."""
    stage = None
    retained = False
    try:
        source = _checked(SHIM_SRC)
        dll = _checked(SHIM_DLL)
        stamp = _checked(gamepaths.TOOLS_BIN / "hwr2_capture.build.json")
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        if not force and not _shim_problems():
            return
        gcc = gamepaths.find_gcc()
        if not gcc:
            raise ValueError("gcc (mingw-w64, x86_64) is required to build tools/bin/hwr2_capture.dll")
        compiler_env = gamepaths.gcc_environment(gcc)
        directory = _checked(gamepaths.TOOLS_BIN)
        directory.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".shim-", dir=directory))
        built = stage / dll.name
        built_stamp = stage / stamp.name
        previous = stage / "previous.dll"
        had_dll = dll.is_file()
        if had_dll:
            shutil.copy2(dll, previous)
        result = subprocess.run([gcc, "-shared", "-O2", "-Wall", "-o", str(built), str(source),
                                 "-lgdi32", "-lopengl32", "-lole32"], env=compiler_env, timeout=120)
        built = _checked(built)
        if result.returncode or not built.is_file() or not built.stat().st_size:
            raise ValueError("compiler did not produce a complete capture shim")
        version_result = subprocess.run([gcc, "-dumpfullversion"], env=compiler_env,
                                        capture_output=True, text=True, timeout=30)
        if version_result.returncode or not isinstance(version_result.stdout, str) or not version_result.stdout.strip():
            raise ValueError("compiler version probe failed")
        version = version_result.stdout.strip()
        expected_stamp = {"source_sha256": source_sha,
                          "dll_sha256": hashlib.sha256(built.read_bytes()).hexdigest(),
                          "gcc": version}
        built_stamp.write_text(json.dumps(expected_stamp, indent=1) + "\n", encoding="utf-8")
        if json.loads(_checked(built_stamp).read_text(encoding="utf-8")) != expected_stamp \
                or hashlib.sha256(_checked(built).read_bytes()).hexdigest() != expected_stamp["dll_sha256"]:
            raise ValueError("staged capture shim/stamp did not read back as the complete build pair")
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_sha:
            raise ValueError("capture shim source changed during the build")
        installed = False
        try:
            os.replace(built, dll)
            installed = True
            os.replace(built_stamp, stamp)
        except OSError as error:
            if installed:
                try:
                    if had_dll:
                        os.replace(previous, dll)
                    else:
                        dll.unlink()
                except OSError as rollback_error:
                    retained = True
                    raise ValueError(f"shim publication/rollback failed; recovery retained at {stage}: {rollback_error}") from error
            raise
        step(f"built tools/bin/hwr2_capture.dll (gcc {version})")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(f"capture shim build refused: {error}")
    finally:
        if stage is not None and not retained:
            try:
                safe = _checked(stage)
                if safe.parent != Path(gamepaths.TOOLS_BIN).absolute() or not safe.name.startswith(".shim-"):
                    raise ValueError("refusing cleanup outside this shim build's private staging")
                shutil.rmtree(safe)
            except (OSError, ValueError) as error:
                sys.exit(f"capture shim staging retained at {stage}; inspect before setup retry: {error}")


def extract_hoh2(force: bool) -> None:
    out = gamepaths.BASE_HOH2
    if out.is_dir() and any(out.iterdir()) and not force:
        step(f"{out.relative_to(REPO)} exists (use --force to redo)")
        return
    if out.is_dir():
        shutil.rmtree(out)
    game = gamepaths.hoh2_dir()
    packager_unpack(game / "res" / "assets.bin", out)
    shutil.copytree(game / "res" / "language", out / "language", dirs_exist_ok=True)


def extract_hoh1(force: bool) -> None:
    game = gamepaths.hoh1_dir(required=False)
    if game is None:
        step("HoH1 not installed: skipping gamecode/sdk/hoh1 (import_hoh1.py needs it)")
        return
    out = gamepaths.BASE_HOH1
    if out.is_dir() and any(out.iterdir()) and not force:
        return
    import hwr_archive
    hwr_archive.main(["extract", str(game / "res" / "assets.bin"), str(out)])
    if (game / "res" / "language").is_dir():
        shutil.copytree(game / "res" / "language", out / "language", dirs_exist_ok=True)


def api_strings(force: bool) -> None:
    out = gamepaths.GAMECODE / "assets" / "hwr2_api_strings.txt"
    if out.is_file() and not force:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    data = (gamepaths.hoh2_dir() / "HWR2.exe").read_bytes()
    strings = sorted({m.group().decode() for m in re.finditer(rb"[\x20-\x7e]{6,}", data)})
    out.write_text("\n".join(strings) + "\n", encoding="utf-8", newline="\n")
    step(f"wrote {len(strings)} strings to {out.relative_to(REPO)}")


def datatables(force: bool) -> None:
    exporter = gamepaths.TOOLS / "export_datatables.py"
    r = subprocess.run([sys.executable, str(exporter)] + (["--force"] if force else []))
    if r.returncode:
        sys.exit("export_datatables.py failed")


def current_manifest(trees: list[str]) -> dict:
    return {t: tree_hash(REPO / t) for t in trees if (REPO / t).is_dir()}


def verify() -> int:
    bad, have_optional = [], {}
    try:
        manifest = _checked(MANIFEST)
        if not manifest.is_file():
            raise ValueError("no gamelab/manifest.json; record only on the originating pinned machine")
        tiers = _manifest_shape(json.loads(manifest.read_text(encoding="utf-8")))
        for tier, trees in tiers.items():
            for tree, groups in trees.items():
                root = _checked(REPO / tree)
                present = root.is_dir() and any(root.iterdir())
                if tier != "required" or tree in OPTIONAL_REQUIRED:
                    have_optional[tree] = present
                    if not present:
                        continue
                elif not present:
                    bad.append(f"{tree}: missing")
                    continue
                got = tree_hash(root)
                for group in sorted(set(groups) | set(got)):
                    if groups.get(group) != got.get(group):
                        bad.append(f"{tree}/{group}: recorded hash/count differs from current generated data")
    except (OSError, ValueError) as error:
        bad.append(f"generated manifest: {error}")
    bad.extend(_shim_problems())
    temporary = None
    try:
        local = _checked(MANIFEST_LOCAL)
        # Replace the diagnostic leaf so an existing hardlink cannot redirect writes.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".verify-",
                                         dir=local.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(json.dumps({"checked": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                     "optional_present": have_optional, "ok": not bad}, indent=1) + "\n")
        os.replace(temporary, local)
    except (OSError, ValueError) as error:
        bad.append(f"cannot record current verification: {error}")
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError as error:
                bad.append(f"verification temporary retained at {temporary}: {error}")
    for problem in bad:
        print("DIFF", problem)
    print(f"verify: {'green' if not bad else f'{len(bad)} difference(s)'}; optional present: "
          f"{[tree for tree, present in have_optional.items() if present] or 'none'}")
    return 1 if bad else 0


def record() -> int:
    tiers = {"required": current_manifest(REQUIRED_TREES + OPTIONAL_REQUIRED),
             "optional": current_manifest(COMMUNITY_TREES)}
    pin = pin_build.pinned()
    MANIFEST.write_text(json.dumps({"build_id": pin and pin["build_id"], "recorded": time.strftime("%Y-%m-%d"),
                                    "tiers": tiers}, indent=1) + "\n", encoding="utf-8")
    print(f"recorded {sum(len(v) for t in tiers.values() for v in t.values())} groups -> {MANIFEST.relative_to(REPO)}")
    return 0


def community() -> None:
    """Optional tier: copy the non-regenerable mirrors from the shared folder named in SOURCES.md."""
    text = SOURCES.read_text(encoding="utf-8") if SOURCES.is_file() else ""
    m = re.search(r"Shared folder:\s*`([^`]+)`", text)
    if not m or not Path(m.group(1)).is_dir():
        sys.exit("--with-community: the shared folder in docs/SOURCES.md is not reachable from this machine")
    src = Path(m.group(1))
    for tree in COMMUNITY_TREES:
        name = Path(tree).name
        if (src / name).is_dir():
            shutil.copytree(src / name, REPO / tree, dirs_exist_ok=True)
            step(f"copied {name} from the shared folder")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--unpack-driver"]:
        return unpack_driver(argv[1], argv[2], int(argv[3]))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--with-community", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args(argv)
    if a.verify:
        return verify()
    if a.record:
        return record()
    bad = pin_build.mismatch()
    if bad:
        print("REFUSED: the install is not the pinned build: " + "; ".join(bad))
        print("If the update is deliberate: python tools/pin_build.py --reason '...' then bootstrap.py --force")
        return pin_build.EXIT_BUILD_MISMATCH
    ensure_packager(a.force)
    build_shim(a.force)
    extract_hoh2(a.force)
    extract_hoh1(a.force)
    api_strings(a.force)
    datatables(a.force)
    import hidden_desktop  # noqa: F401  (step 8: vendored copy importable)
    step("tools/hidden_desktop.py importable")
    if a.with_community:
        community()
    return verify() if MANIFEST.is_file() else 0


if __name__ == "__main__":
    sys.exit(main())
