#!/usr/bin/env python3
"""
build.py - package HammerwatchPlus into HoH2 mod .bin files: the Steam Workshop packages.

    build.py                 # every package (packages.json) -> dist/HWP-<id>.bin + dist/HammerwatchPlus-All.bin
    build.py qol keys        # only these packages (no all-in-one)
    build.py all             # only the all-in-one pack
    build.py --check         # compare our wholesale overrides against gamecode/sdk/hoh2/ (docs/modules.md, rule 1)
                             # and check packages.json against the modules
    build.py --no-all        # skip the all-in-one package
    build.py --with-local    # also pack `local` content (your own install only)
    build.py --workshop      # the all-in-one pack as published: without `"workshop": false` packages
    build.py --beta          # every `beta_into` module rides in the packages that carry its host (a beta
                             # build, never published)

A package (packages.json) is its mods plus every library part they require, transitively:
the shared code is copied into each package at the same paths, so a package works alone and
beside any other one (the game keeps one copy of a path, the first mod's; RE_NOTES
"2026-10-26: one path, two mods"). Each package also carries the library stamp
(scripts/HWP/Core/LibStamp.as, a hash of every library part) and its own check module, which
logs an error when the stamp the game loaded is another build's. The all-in-one pack is every
package together.

Each module is `mods/<id>/` with an `info.xml` (author/name/description read
from it) and an optional `module.json`:

    {
      "id": "gambler",                 # defaults to the folder name
      "library": false,                # true: a library part (hwplib, hwplib-luck, ...): never a package of
                                       # its own, copied into every package whose mods require it
      "shared": false,                 # true: a feature module listed in one package that mods of other
                                       # packages may require too, and so carry (petrooms: QoL, and Pets)
      "requires": ["hwplib"],          # modules this one builds on: libraries, shared modules, or mods of
                                       # the same package
      "overrides": ["scripts/GUI/PlayerMenu/Character.as"],  # wholesale base-file overrides
      "class_swaps": {"Chest": "HWPChest"},  # base units using Chest are copied with HWPChest (tools/class_units.py)
      "scene_art": "tweak/hwp/chest_art.sval",  # extra art scenes in those copies (tools/class_units.py)
      "exclude": ["notes.md"],         # files not to package
      "local": ["hoh1/"],              # generated from the player's own HoH1 install:
                                       # packed only with --with-local, never released
      "local_overlay": "hoh1art/",     # local too, but packed in place of the committed file
                                       # at the same path without the prefix (hoh1art/x.png -> x.png)
      "dev": false,                    # true: development harness, never packaged
      "local_only": false,             # true: in no package (a machine-local testing aid)
      "beta_into": "hwplib"            # with --beta, this (local_only) module's files are packed into
                                       # every package carrying hwplib, so beta testers enable nothing
                                       # extra; a build without --beta never carries them
    }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import class_units  # noqa: E402
import hwr_archive as hwr  # noqa: E402
import gamepaths as paths  # noqa: E402

ALL_NAME = "HammerwatchPlus-All"
PACKAGE_PREFIX = "HWP-"
AUTHOR = "Ryan Bower"
PACKAGES = paths.REPO / "packages.json"
NEVER_PACK = {"module.json", "README.md", "_hwr_manifest.json", "info.xml"}  # info.xml becomes the archive meta
# overrides compare these as text (line endings and a BOM do not matter to the engine); anything else byte-exact
TEXT_EXTS = {".as", ".xml", ".sval", ".lang", ".gui", ".inc", ".net", ".unit", ".effect", ".txt", ".md", ".json", ".fnt"}


def load_module(mod_dir: Path) -> dict:
    cfg = {}
    cfg_path = mod_dir / "module.json"
    if cfg_path.is_file():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("id", mod_dir.name)
    if cfg["id"] != mod_dir.name:
        # deploy.py names the deployed mod after the folder; keep one identity everywhere
        sys.exit(f"{cfg_path}: id {cfg['id']!r} must match the folder name {mod_dir.name!r}")
    cfg.setdefault("requires", [])
    cfg.setdefault("overrides", [])
    cfg.setdefault("class_swaps", {})
    cfg.setdefault("exclude", [])
    cfg.setdefault("local", [])
    cfg.setdefault("local_overlay", "")
    if cfg["local_overlay"]:
        cfg["local_overlay"] = cfg["local_overlay"].rstrip("/") + "/"
        cfg["local"].append(cfg["local_overlay"])
    cfg.setdefault("library", False)
    cfg.setdefault("shared", False)
    cfg.setdefault("dev", False)
    cfg.setdefault("local_only", False)
    cfg.setdefault("beta_into", "")
    if cfg["beta_into"] and not cfg["local_only"]:
        sys.exit(f"{cfg_path}: beta_into needs local_only true (a beta-only module is never released on its own)")
    cfg["dir"] = mod_dir
    # overrides tools/class_units.py remakes from gamecode/sdk/hoh2/ on every build (no .orig needed)
    cfg["generated"] = class_units.units_for(cfg["class_swaps"]) if paths.BASE_HOH2.is_dir() else []
    try:
        cfg["meta"] = hwr.read_info_xml(mod_dir)
    except ValueError as e:
        sys.exit(str(e))
    if not cfg["meta"].get("name"):
        sys.exit(f"{mod_dir}/info.xml has no <name>")
    return cfg


def is_pristine_copy(rel: str) -> bool:
    """`<override>.orig` files are the untouched base copies that --check compares against."""
    return rel.endswith(".orig")


def is_local(cfg: dict, rel: str) -> bool:
    """Content the player generated from their own copy of another game (module.json
    `local`: path prefixes, e.g. the converted HoH1 levels). Never part of a release."""
    return any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in cfg["local"])


def _skipper(cfg: dict, with_local: bool):
    return lambda rel: is_pristine_copy(rel) or (not with_local and is_local(cfg, rel))


def module_files(cfg: dict, with_local: bool = False):
    """(rel, path) of every file the module packs; the one rule build and --check share."""
    return hwr.packable_files(cfg["dir"], NEVER_PACK | set(cfg["exclude"]), _skipper(cfg, with_local))


def personal_content(mods: list[dict]) -> list[str]:
    """The module.json `local` files on disk (<module>/<path>) that --with-local packs: what the
    player made from their own HoH1 install (tools/import_hoh1.py). Not the local_only modules'
    (a beta rider rides only with --beta). deploy.py modded-prod packs these by default."""
    return [f"{m['id']}/{rel}" for m in mods if not m["local_only"]
            for rel, _fp in module_files(m, True) if is_local(m, rel)]


def local_entries(mods: list[dict]) -> dict[str, bytes]:
    """Packed path -> content of every file only a --with-local or --beta build carries: `local`
    content, `local_overlay` stand-ins (same path, other content) and beta riders. A .bin holding
    one of them is a personal build and is never published (tools/workshop.py checks)."""
    out: dict[str, bytes] = {}
    for m in mods:
        if not m["local"]:
            continue
        plain = {e.path: e.data() for e in module_entries(m, True, False)}
        for e in module_entries(m, True, True):
            data = e.data()
            if plain.get(e.path) != data:
                out[e.path] = data
    return out


def personal_files(package: Path, local: dict[str, bytes]) -> list[str]:
    """The paths in a built .bin that are personal content (local_entries)."""
    return sorted(e.path for e in hwr.Archive.read(package).entries
                  if e.path in local and e.data() == local[e.path])


def module_entries(cfg: dict, store: bool, with_local: bool = False) -> list[hwr.Entry]:
    manifest = None
    mpath = cfg["dir"] / hwr.MANIFEST
    if mpath.is_file():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    entries = hwr.collect_dir(cfg["dir"], manifest, store, NEVER_PACK | set(cfg["exclude"]), _skipper(cfg, with_local))
    overlay = cfg["local_overlay"]
    if not (with_local and overlay):
        return entries
    # local_overlay: hoh1art/<path> stands in for the committed <path> (e.g. a placeholder)
    over = {e.path[len(overlay):]: e for e in entries if e.path.startswith(overlay)}
    for path, e in over.items():
        e.path = path
    return [e for e in entries if e.path not in over or over[e.path] is e]


def write_package(name: str, meta: dict, entries: list[hwr.Entry], store: bool) -> Path:
    paths.DIST.mkdir(exist_ok=True)
    out = paths.DIST / f"{name}.bin"
    # author/name/description first (what the Resource Mods menu shows), then everything else
    ordered = {k: meta[k] for k in ("author", "name", "description") if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    hwr.Archive("hoh2", hwr.GAMES["hoh2"][1], 0, ordered, entries).write(out)
    size = sum(len(e.blob) for e in entries)
    print(f"  {out.name:40s} {len(entries):5d} files  {size:>10,} B")
    return out


def _comparable(rel: str, data: bytes) -> bytes:
    """Text files compare without BOM and line-ending differences (git may rewrite them);
    binary files compare byte-exact."""
    if Path(rel).suffix.lower() not in TEXT_EXTS:
        return data
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def check_overrides(mods: list[dict]) -> int:
    """Report wholesale overrides whose base copy no longer matches gamecode/sdk/hoh2/."""
    if not paths.BASE_HOH2.is_dir():
        sys.exit("run tools/bootstrap.py first (gamecode/sdk/hoh2 missing)")
    problems = 0
    owners: dict[str, str] = {}
    for cfg in mods:
        for rel in cfg["overrides"] + cfg["generated"]:
            if rel in owners:
                print(f"CONFLICT {rel}: owned by {owners[rel]} and {cfg['id']}")
                problems += 1
            owners[rel] = cfg["id"]
            base = paths.BASE_HOH2 / rel
            if rel in cfg["generated"]:
                if not base.is_file():
                    print(f"MISSING  {rel}: not in base game any more ({cfg['id']}, generated)")
                    problems += 1
                continue
            orig = cfg["dir"] / (rel + ".orig")
            if not base.is_file():
                print(f"MISSING  {rel}: not in base game any more ({cfg['id']})")
                problems += 1
                continue
            if not orig.is_file():
                print(f"NO-ORIG  {rel}: add {orig.relative_to(paths.REPO)} (copy of the base file you patched)")
                problems += 1
                continue
            if _comparable(rel, base.read_bytes()) != _comparable(rel, orig.read_bytes()):
                print(f"CHANGED  {rel}: base game updated since {cfg['id']} copied it; re-apply the patch"
                      f"{' (compared ignoring line endings)' if Path(rel).suffix.lower() in TEXT_EXTS else ''}")
                problems += 1
    # Any packed file that also exists in base but isn't declared is an undeclared override.
    for cfg in mods:
        for rel, _fp in module_files(cfg):
            if rel in cfg["overrides"] or rel in cfg["generated"]:
                continue
            if (paths.BASE_HOH2 / rel).is_file():
                print(f"UNDECLARED {rel}: {cfg['id']} shadows a base file; list it in module.json overrides")
                problems += 1
    print("override check:", "OK" if not problems else f"{problems} problem(s)")
    return problems


def load_packages(mods: list[dict]) -> tuple[list[dict], dict]:
    """packages.json, checked against the modules: every content module in exactly one package
    or on the bench, libraries in none, and each package's closure (its mods plus everything they
    require, transitively) holding only its own mods, libraries and shared modules, so it works
    alone."""
    doc = json.loads(PACKAGES.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in mods}
    owner: dict[str, str] = {}
    bench = set(doc.get("bench", []))
    pkgs = doc["packages"]
    for p in pkgs:
        if not p["id"].isalnum() or p["id"] != p["id"].lower():
            sys.exit(f"packages.json: package id {p['id']!r} must be lowercase letters and digits")
        for mid in p["mods"]:
            if mid not in by_id:
                sys.exit(f"packages.json: {p['id']} lists unknown module {mid!r}")
            if mid in owner:
                sys.exit(f"packages.json: {mid} is in both {owner[mid]} and {p['id']}")
            m = by_id[mid]
            if m["library"] or m["dev"] or m["local_only"] or mid in bench:
                sys.exit(f"packages.json: {p['id']} lists {mid}, a library, dev, local-only or bench module")
            owner[mid] = p["id"]
    if len({p["id"] for p in pkgs}) != len(pkgs):
        sys.exit("packages.json: two packages share an id")
    for m in mods:
        if m["id"] not in owner and not (m["library"] or m["dev"] or m["local_only"] or m["id"] in bench):
            sys.exit(f"packages.json: module {m['id']} is in no package; add it to one, or to the bench")
    for p in pkgs:
        closure: list[str] = []
        seen: set[str] = set()

        # each module after what it requires, so a library part follows its base
        def add(mid: str, via: str) -> None:
            if mid in seen:
                return
            if mid not in by_id:
                sys.exit(f"{via} requires unknown module {mid!r}")
            m = by_id[mid]
            if not (m["library"] or m["shared"]) and owner.get(mid) != p["id"]:
                sys.exit(f"package {p['id']}: {via} requires {mid}, which is not in it; a package must work alone "
                         f"(move the shared code into a library part, module.json `library: true`)")
            seen.add(mid)
            for r in m["requires"]:
                add(r, mid)
            closure.append(mid)
        for mid in p["mods"]:
            add(mid, mid)
        # libraries first, each after the parts it builds on: the base before its parts
        p["closure"] = [x for x in closure if by_id[x]["library"]] + [x for x in closure if not by_id[x]["library"]]
    return pkgs, doc["all"]


def library_stamp(mods: list[dict]) -> str:
    """One hash over every library part's packed files, whichever parts a package carries: two
    packages carry the same library build exactly when they carry the same stamp."""
    h = hashlib.sha256()
    for m in sorted((m for m in mods if m["library"]), key=lambda m: m["id"]):
        for rel, fp in module_files(m):
            h.update(f"{m['id']}/{rel}\0".encode())
            h.update(_comparable(rel, fp.read_bytes()))
            h.update(b"\0")
    return h.hexdigest()[:12]


STAMP_FILE = "scripts/HWP/Core/LibStamp.as"


def stamp_entries(pkg_id: str, stamp: str, store: bool) -> list[hwr.Entry]:
    """The library stamp (one path every package ships, byte-identical within a build) and the
    package's own check: its module compares the stamp it was built with to the one the game
    loaded (the first package's copy of a path wins), so an older or newer package beside it
    shows in the log instead of as a puzzling failure."""
    lib = ("// Generated by tools/build.py: the library build every HammerwatchPlus package of this\n"
           "// build carries (a hash of all library parts). Never edit; never commit.\n"
           "namespace HWP\n{\n"
           f"\tconst string LIB_STAMP = \"{stamp}\";\n"
           "}\n")
    cls = f"HWPPackage_{pkg_id}"
    check = (f"// Generated by tools/build.py for {PACKAGE_PREFIX}{pkg_id}.bin: the library build it was made with.\n"
             "namespace Modules\n{\n"
             f"\tclass {cls} : Module\n\t{{\n"
             f"\t\t{cls}()\n\t\t{{\n"
             f"\t\t\tsuper(\"hwp-package-{pkg_id}\");\n"
             f"\t\t\tif (HWP::LIB_STAMP == \"{stamp}\")\n"
             f"\t\t\t\tHWP::Log(\"core\", \"package {PACKAGE_PREFIX}{pkg_id}, library {stamp}\");\n"
             "\t\t\telse\n\t\t\t{\n"
             f"\t\t\t\tHWP::LogError(\"core\", \"package {PACKAGE_PREFIX}{pkg_id} was built with library {stamp} but library \"\n"
             "\t\t\t\t\t+ HWP::LIB_STAMP + \" loaded: another HammerwatchPlus package is older or newer; update them all\");\n"
             f"\t\t\t\tHWP::Packages::Mismatch(\"{PACKAGE_PREFIX}{pkg_id}\");\n"
             "\t\t\t}\n"
             "\t\t}\n\t}\n}\n")
    return [hwr.make_entry(STAMP_FILE, lib.encode(), None, store),
            hwr.make_entry(f"scripts/HWP/Packages/{pkg_id}.as", check.encode(), None, store)]


def add_entries(into: dict[str, hwr.Entry], entries: list[hwr.Entry], where: str, source: str) -> None:
    """Merge into a package by path: one path, one content (a library file every mod's closure
    reaches is the same file), or the build stops."""
    for e in entries:
        have = into.get(e.path)
        if have is not None and have.blob != e.blob:
            sys.exit(f"{where}: {e.path} differs between {source} and another module")
        into[e.path] = e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packages", nargs="*", help="package ids to build (packages.json), or `all` for the all-in-one "
                                                "pack (default: every package and the all-in-one pack)")
    ap.add_argument("--check", action="store_true", help="only run the override check")
    ap.add_argument("--no-all", action="store_true", help="skip the all-in-one package")
    ap.add_argument("--store", action="store_true", help="skip LZ4 compression")
    ap.add_argument("--workshop", action="store_true",
                    help="the all-in-one pack as the Workshop has it: packages.json `\"workshop\": false` "
                         "packages are left out of it (tools/workshop.py)")
    ap.add_argument("--with-local", action="store_true",
                    help="also pack module.json `local` content (converted HoH1 levels); for your own "
                         "install only, never publish such a package")
    ap.add_argument("--beta", action="store_true",
                    help="a beta build: every module.json `beta_into` module rides in each package that "
                         "carries its host (holylocal: every package, through hwplib); never publish such a package")
    args = ap.parse_args(argv)

    mods = [load_module(d) for d in paths.module_dirs()]
    if args.check:
        problems = check_overrides(mods)
        load_packages(mods)
        sys.exit(1 if problems else 0)
    by_id = {m["id"]: m for m in mods}
    pkgs, all_doc = load_packages(mods)
    beta = [m for m in mods if m["beta_into"]] if args.beta else []
    for m in beta:
        if m["beta_into"] not in by_id:
            sys.exit(f"{m['id']}: beta_into names an unknown module {m['beta_into']!r}")
    known = {p["id"] for p in pkgs}
    unknown = set(args.packages) - known - {"all"}
    if unknown:
        sys.exit(f"unknown package(s): {', '.join(sorted(unknown))}; known: {', '.join(sorted(known))}, all")
    named = set(args.packages) - {"all"}
    if args.no_all and args.packages and not named:
        sys.exit("--no-all with only `all` named: nothing to build")
    build_all = not args.no_all and (not args.packages or "all" in args.packages)
    # the all-in-one pack is every package, so naming it builds them all; only the packages
    # named (every one when none is) and the pack itself are written
    wanted = pkgs if (build_all or not named) else [p for p in pkgs if p["id"] in named]

    def written(p: dict) -> bool:
        return not args.packages or p["id"] in named
    used = {mid for p in wanted for mid in p["closure"]}

    if paths.BASE_HOH2.is_dir():
        for mid in sorted(used):
            if by_id[mid]["class_swaps"]:
                print(f"class units: {mid} {len(class_units.generate(by_id[mid]))}")
    if "pets" in used and paths.BASE_HOH2.exists():
        import make_pet_dyes  # the two-section pet dye copies (gitignored, made from your installs)
        make_pet_dyes.main([])

    import import_hoh1
    for what in import_hoh1.stale_imports():
        print(f"warning: the HoH1 {what} import predates converter version {hwr.CONVERTER_VERSION}; "
              f"rerun tools/import_hoh1.py {what}")

    stamp = library_stamp(mods)
    print(f"building (library {stamp}):")
    cache: dict[str, list[hwr.Entry]] = {}

    def entries_of(m: dict, with_local: bool) -> list[hwr.Entry]:
        key = f"{m['id']}:{with_local}"
        if key not in cache:
            cache[key] = module_entries(m, args.store, with_local)
        return cache[key]

    all_entries: dict[str, hwr.Entry] = {}
    all_meta: dict = {}
    for p in wanted:
        entries: dict[str, hwr.Entry] = {}
        meta: dict = {}
        local = False
        for mid in p["closure"]:
            m = by_id[mid]
            add_entries(entries, entries_of(m, args.with_local), f"{PACKAGE_PREFIX}{p['id']}.bin", mid)
            merge_meta(meta, m["meta"], mid)
            local = local or (args.with_local and any(is_local(m, rel) for rel, _fp in module_files(m, True)))
        for rider in beta:
            if rider["beta_into"] not in p["closure"]:
                continue
            # the rider's `local` content is the point of it, so it packs as if --with-local
            riding = entries_of(rider, True)
            add_entries(entries, riding, f"{PACKAGE_PREFIX}{p['id']}.bin", rider["id"])
            print(f"  beta: {PACKAGE_PREFIX}{p['id']}.bin carries {rider['id']} ({len(riding)} files); do not publish it")
        add_entries(entries, stamp_entries(p["id"], stamp, args.store), f"{PACKAGE_PREFIX}{p['id']}.bin", "build.py")
        if local:
            print(f"  note: {PACKAGE_PREFIX}{p['id']}.bin contains locally generated content; do not publish it")
        meta.update({"author": AUTHOR, "name": p["name"], "description": p["description"]})
        if written(p):
            write_package(PACKAGE_PREFIX + p["id"], meta, list(entries.values()), args.store)
        if args.workshop and p.get("workshop") is False:
            print(f"  workshop: {p['id']} is not in the all-in-one pack")
            continue
        add_entries(all_entries, list(entries.values()), ALL_NAME + ".bin", p["id"])
        merge_meta(all_meta, meta, p["id"])
    if build_all:
        all_meta.update({"author": AUTHOR, "name": all_doc["name"], "description": all_doc["description"]})
        write_package(all_doc.get("file", ALL_NAME), all_meta, list(all_entries.values()), args.store)


def merge_meta(into: dict, meta: dict, mod_id: str) -> None:
    """Combine the non-descriptive info.xml keys (classmaps, scripts, ...) of every module
    in a package. Lists concatenate; anything else must agree."""
    for k, v in meta.items():
        if k in ("author", "name", "description"):
            continue
        if k not in into:
            into[k] = list(v) if isinstance(v, list) else v
        elif isinstance(v, list) and isinstance(into[k], list):
            into[k] += [x for x in v if x not in into[k]]
        elif into[k] != v:
            sys.exit(f"package conflict: info.xml key {k!r} differs in {mod_id}")


if __name__ == "__main__":
    main()
