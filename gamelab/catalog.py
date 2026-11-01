"""Reviewed, data-driven admission for independent GameLab pool cases.

This checks explicit review bindings and their selected source leaves.  Import
discovery is only an omission check, never a claim that a closure was reviewed.
The coordinator owns snapshot publication, source freeze, leases and execution.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON = 16 * 1024 * 1024
MAX_CASES = 256
MAX_FILES = 20000
SAFE_STEPS = frozenset({"gl", "console", "sleep", "shot", "log_has", "log_lacks", "log_clean", "bot"})
PRIVATE_WRITES = frozenset({"slot-game", "slot-results", "slot-cache", "slot-modules", "pool-acceptance"})
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TOP = {"schema_version", "catalog_id", "cases"}
_CASE = {"id", "status", "scenario", "task", "check", "scope", "expected", "predicates",
         "lifecycle", "private_writes", "review", "closure"}


class CatalogError(ValueError):
    """A stable machine-readable refusal, with no implied dispatch or verdict."""
    def __init__(self, code, message, *, case=None, path=None):
        super().__init__(message)
        self.code, self.case, self.path = code, case, str(path) if path is not None else None

    def as_dict(self):
        return {"code": self.code, "message": str(self), "case": self.case, "path": self.path}


def _refuse(code, message, **context):
    raise CatalogError(code, message, **context)


def _keys(value, keys, label, optional=frozenset()):
    if type(value) is not dict or not keys <= set(value) or set(value) - keys - optional:
        _refuse("schema", f"{label} requires exactly {sorted(keys)}")


def _text(value, label):
    if type(value) is not str or not value.strip() or len(value) > 8192 or "\x00" in value:
        _refuse("schema", f"invalid {label}")


def _name(value, label):
    if type(value) is not str or not _NAME.fullmatch(value):
        _refuse("schema", f"invalid {label}")


def _digest(value):
    if type(value) is not str or not _SHA.fullmatch(value):
        _refuse("schema", "SHA256 must be 64 lowercase hex characters")


def _relative(value):
    _text(value, "repo-relative path")
    parts = value.split("/")
    if (any(char in value for char in '\\:<>"|?*') or any(ord(char) < 32 for char in value)
            or any(part in ("", ".", "..") for part in parts)
            or any(part.endswith((".", " ")) for part in parts)):
        _refuse("path", "a normalized repo-relative slash path is required", path=value)
    # Windows device aliases can name something other than the reviewed leaf.
    for part in parts:
        stem = part.split(".", 1)[0].rstrip(" ").upper()
        if (stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                or re.fullmatch(r"(?:COM|LPT)[1-9\u00b9\u00b2\u00b3]", stem)):
            _refuse("path", "device path is refused", path=value)
    return value


def _ordinary(path):
    """lstat every ancestor without resolve() following an untrusted redirect."""
    root = ROOT.absolute()
    path = Path(path).absolute()
    try:
        relative = path.relative_to(root)
    except ValueError:
        _refuse("path", "artifact escapes repository", path=path)
    if any(part in (".", "..") for part in relative.parts):
        _refuse("path", "unnormalized artifact path", path=path)
    current = root
    try:
        for part in (None, *relative.parts):
            if part is not None:
                current /= part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                _refuse("path", "reparse or symlink artifact refused", path=current)
            if current != path:
                if not stat.S_ISDIR(info.st_mode):
                    _refuse("path", "artifact ancestor is not a directory", path=current)
            elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                _refuse("path", "artifact must be an ordinary single-link file", path=current)
    except OSError as exc:
        raise CatalogError("unreadable", f"cannot inspect artifact: {exc}", path=current) from exc
    return path


def _read(path, limit=None):
    path = _ordinary(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read() if limit is None else stream.read(limit + 1)
    except OSError as exc:
        raise CatalogError("unreadable", f"cannot read artifact: {exc}", path=path) from exc
    if limit is not None and len(raw) > limit:
        _refuse("bounds", "JSON artifact exceeds size limit", path=path)
    return raw


def _hash_file(path):
    path = _ordinary(path)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise CatalogError("unreadable", f"cannot hash artifact: {exc}", path=path) from exc
    return digest.hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _refuse("json", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(raw):
    def constant(value):
        _refuse("json", f"nonfinite JSON constant: {value}")
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=constant)
        # Reject exponent overflow (e.g. 1e999), which parse_constant does not see.
        json.dumps(value, allow_nan=False)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, CatalogError):
            raise
        raise CatalogError("json", f"invalid strict JSON: {exc}") from exc


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _names(values, label):
    if type(values) is not list or len(values) > MAX_FILES:
        _refuse("schema", f"invalid {label} list")
    for value in values:
        _name(value, label)
    if len(values) != len(set(values)):
        _refuse("schema", f"duplicate {label}")


def _structure(data):
    _keys(data, _TOP, "catalog")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        _refuse("schema", "unsupported catalog schema_version")
    _name(data["catalog_id"], "catalog_id")
    cases = data["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        _refuse("bounds", "catalog requires 1..256 entries")
    ids = set()
    for entry in cases:
        _keys(entry, _CASE, "case", {"consumers"})
        for field in ("id", "task", "check", "scope"):
            _name(entry[field], field)
        name = entry["id"]
        if name.casefold() in ids:
            _refuse("schema", "duplicate case ID", case=name)
        ids.add(name.casefold())
        if entry["scenario"] != f"gamelab/scenarios/{name}.json":
            _refuse("schema", "case must select its exact stock scenario path", case=name)
        if entry["check"] != name:
            _refuse("schema", "check must equal the actual scenario ID", case=name)
        if entry["status"] not in ("reviewed", "blocked", "retired"):
            _refuse("schema", "invalid review status", case=name)
        if entry["lifecycle"] not in ("independent", "paired-probe", "exclusive"):
            _refuse("schema", "invalid lifecycle", case=name)
        writes = entry["private_writes"]
        if (type(writes) is not list or any(type(w) is not str for w in writes)
                or len(writes) != len(set(writes)) or any(w not in PRIVATE_WRITES for w in writes)):
            _refuse("schema", "unknown or repeated private-write class", case=name)
        _text(entry["expected"], "expected scope")
        predicates = entry["predicates"]
        if type(predicates) is not list or not predicates or len(predicates) > 10000:
            _refuse("schema", "explicit expected predicates are required", case=name)
        steps = []
        for predicate in predicates:
            _keys(predicate, {"step", "expect"}, "predicate")
            if type(predicate["step"]) is not int or predicate["step"] < 0 or type(predicate["expect"]) is not dict or not predicate["expect"]:
                _refuse("schema", "invalid step predicate", case=name)
            steps.append(predicate["step"])
        if steps != sorted(set(steps)):
            _refuse("schema", "predicates must have unique increasing step indexes", case=name)
        consumers = entry.get("consumers", [])
        if type(consumers) is not list or len(consumers) > 10000:
            _refuse("schema", "invalid consumer list", case=name)
        consumer_steps = set()
        for consumer in consumers:
            _keys(consumer, {"step", "bot", "rows"}, "consumer")
            step = consumer["step"]
            if type(step) is not int or step < 0 or step in consumer_steps:
                _refuse("schema", "consumer steps must be unique nonnegative indexes", case=name)
            consumer_steps.add(step)
            _name(consumer["bot"], "consumer bot")
            rows = consumer["rows"]
            _names(rows, "consumer rows")
            if not rows:
                _refuse("schema", "consumer rows must be nonempty", case=name)
        review = entry["review"]
        _keys(review, {"reviewer", "verdict", "artifact", "sha256", "closure_complete"}, "review")
        _text(review["reviewer"], "reviewer")
        _relative(review["artifact"])
        _digest(review["sha256"])
        if review["verdict"] != "accepted" or review["closure_complete"] is not True:
            _refuse("schema", "an explicit accepted complete-closure review is required", case=name)
        closure = entry["closure"]
        _keys(closure, {"files", "bots", "fixture", "modules"}, "closure")
        _name(closure["fixture"], "fixture")
        _names(closure["bots"], "bots")
        _names(closure["modules"], "modules")
        files = closure["files"]
        if type(files) is not dict or not 1 <= len(files) <= MAX_FILES:
            _refuse("bounds", "closure requires explicit reviewed files", case=name)
        folded = set()
        for path, digest in files.items():
            _relative(path)
            if path.casefold() in folded:
                _refuse("path", "case-insensitive closure path collision", path=path)
            folded.add(path.casefold())
            if (path.startswith(("gamelab/results/", "gamelab/env/userdata/", "gamelab/fixtures/cache/"))
                    or path.split("/", 1)[0] not in {"gamelab", "mods", "tools", "gamecode", "docs", "planner"}):
                _refuse("path", "closure must pin source/input leaves, not live state", path=path)
            _digest(digest)
        required = {entry["scenario"], f"gamelab/fixtures/{closure['fixture']}.json"}
        required.update(f"gamelab/bots/{bot}.py" for bot in closure["bots"])
        required.update(f"mods/{mod}/module.json" for mod in closure["modules"])
        if not required <= files.keys():
            _refuse("closure", f"missing mandatory reviewed leaves: {sorted(required - files.keys())}", case=name)


def load_catalog(path, expected_sha256=None):
    """Validate all descriptors, without touching their case closure files.

    The caller chooses the trusted catalog digest.  Review labels in a file are
    explicit attestations, not cryptographic proof of a human's authority.
    """
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    raw = _read(path, MAX_JSON)
    digest = _sha(raw)
    if expected_sha256 is not None:
        _digest(expected_sha256)
        if digest != expected_sha256:
            _refuse("catalog-hash", "catalog differs from the admitted digest", path=path)
    data = _json(raw)
    _structure(data)
    data["metadata"] = {"path": str(path.absolute()), "sha256": digest}
    return data


def _descriptor(catalog):
    if type(catalog) is not dict or set(catalog) != _TOP | {"metadata"}:
        _refuse("schema", "load_catalog descriptor required")
    _keys(catalog["metadata"], {"path", "sha256"}, "descriptor metadata")
    current = load_catalog(catalog["metadata"]["path"], catalog["metadata"]["sha256"])
    if current != catalog:
        _refuse("catalog-tampered", "catalog descriptor was modified after loading")
    return current


def list_cases(catalog):
    """Structural review statuses only; this does not award live eligibility."""
    catalog = _descriptor(catalog)
    return [{key: entry[key] for key in ("id", "status", "task", "check", "scope", "lifecycle")}
            for entry in catalog["cases"]]


def describe_case(catalog, name):
    """Read a frozen descriptor for historical review, without current leaf reads.

    A descriptor is not a result, live eligibility check, or evidence acceptance.
    """
    catalog = _descriptor(catalog)
    for entry in catalog["cases"]:
        if entry["id"] == name:
            return copy.deepcopy(entry)
    _refuse("unknown-case", "case is absent from reviewed catalog", case=name)


def hash_reviewed_files(paths):
    """Seal only the caller's explicitly enumerated reviewed leaves.

    No tree discovery, review assertion, catalog write or status promotion occurs.
    """
    if type(paths) not in (list, tuple) or not 1 <= len(paths) <= MAX_FILES:
        _refuse("bounds", "explicit reviewed paths required")
    result = {}
    folded = set()
    for relative in paths:
        _relative(relative)
        if relative.casefold() in folded:
            _refuse("path", "duplicate reviewed path", path=relative)
        folded.add(relative.casefold())
        result[relative] = _hash_file(ROOT / relative)
    return result


def _bot_imports(raw, bot):
    try:
        tree = ast.parse(raw, filename=f"gamelab/bots/{bot}.py")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise CatalogError("closure", f"cannot inspect reviewed bot imports: {exc}") from exc
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = ["gamelab", "bots"]
                if node.level > len(base):
                    _refuse("closure", "bot relative import escapes its package")
                base = base[:len(base) - node.level + 1]
                module = ".".join(base) + ("." + module if module else "")
            modules = [module]
            if module == "gamelab.bots":
                if any(alias.name == "*" for alias in node.names):
                    _refuse("closure", "wildcard bot imports have no explicit static binding")
                modules += [module + "." + alias.name for alias in node.names]
        else:
            continue
        for module in modules:
            if module.startswith("gamelab.bots."):
                found.add(module.split(".")[2])
    return found


def _check_module_inventory(modules, files, case):
    """Refuse omitted consumed leaves; discovery never adds reviewed hashes."""
    prefixes = tuple(f"mods/{module}/" for module in modules)
    expected = {path for path in files if path.startswith(prefixes)}
    actual, folded = set(), set()
    pending = [ROOT / "mods" / module for module in sorted(modules)]
    inspected = 0
    while pending:
        path = pending.pop()
        inspected += 1
        if inspected > MAX_FILES * 2:
            _refuse("bounds", "selected module inventory exceeds traversal limit", case=case)
        try:
            relative = _relative(path.relative_to(ROOT).as_posix())
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                _refuse("path", "redirected module inventory entry refused", case=case, path=relative)
            if stat.S_ISDIR(info.st_mode):
                for child in path.iterdir():
                    if inspected + len(pending) >= MAX_FILES * 2:
                        _refuse("bounds", "selected module inventory exceeds traversal limit", case=case)
                    pending.append(child)
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                _refuse("path", "module inventory leaf must be an ordinary single-link file", case=case, path=relative)
        except OSError as exc:
            raise CatalogError("unreadable", f"cannot inventory selected module: {exc}", case=case, path=path) from exc
        if relative.casefold() in folded:
            _refuse("path", "case-insensitive module inventory collision", case=case, path=relative)
        folded.add(relative.casefold())
        actual.add(relative)
        if relative not in expected:
            _refuse("closure-inventory", "module leaf is absent from reviewed closure", case=case, path=relative)
    if actual != expected:
        _refuse("closure-inventory", "reviewed module leaves are missing from selected inventory", case=case,
                path=sorted(expected - actual)[0])


def validate_case(catalog, name):
    """Hash-check one reviewed case and preserve mechanical pool refusals."""
    catalog = _descriptor(catalog)
    entry = next((item for item in catalog["cases"] if item["id"] == name), None)
    if entry is None:
        _refuse("unknown-case", "case is absent from reviewed catalog", case=name)
    if entry["status"] != "reviewed" or entry["lifecycle"] == "exclusive":
        _refuse("ineligible", "case is not admitted to an independent pool", case=name)
    closure = entry["closure"]
    files = closure["files"]
    raw_files = {}
    for path, digest in files.items():
        # Retain only the small leaves needed for mechanical checks.
        if path == entry["scenario"] or path.endswith("/module.json") or path == f"gamelab/fixtures/{closure['fixture']}.json" or path.startswith("gamelab/bots/"):
            raw = _read(ROOT / path, MAX_JSON)
            actual = _sha(raw)
            raw_files[path] = raw
        else:
            actual = _hash_file(ROOT / path)
        if actual != digest:
            _refuse("stale-hash", "reviewed source/input leaf changed", case=name, path=path)
    review = entry["review"]
    if _sha(_read(ROOT / review["artifact"], MAX_JSON)) != review["sha256"]:
        _refuse("review-hash", "review artifact changed", case=name, path=review["artifact"])
    scenario = _json(raw_files[entry["scenario"]])
    if type(scenario) is not dict or scenario.get("name") != name or scenario.get("fixture") != closure["fixture"]:
        _refuse("scenario", "scenario name/fixture differs from reviewed case", case=name)
    if any(key in scenario for key in ("plan", "explore", "packages", "profile_export", "export_profile", "exports")):
        _refuse("unsafe-scenario", "plans, exploration, packages and exports are not pool eligible", case=name)
    for key in ("timeout", "outer_timeout"):
        value = scenario.get(key, 300)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 3600:
            _refuse("budget", f"invalid bounded pool {key}", case=name)
    steps = scenario.get("steps")
    if type(steps) is not list or not steps or len(steps) > 10000:
        _refuse("scenario", "nonempty bounded steps required", case=name)
    actual_predicates = []
    for index, step in enumerate(steps):
        if type(step) is not dict or type(step.get("do")) is not str or step["do"] not in SAFE_STEPS:
            _refuse("unsafe-step", "source-writing, relaunch and unknown steps refused", case=name)
        if "expect" in step:
            actual_predicates.append({"step": index, "expect": step["expect"]})
        if step["do"] == "bot" and step.get("bot") not in closure["bots"]:
            _refuse("closure", "direct bot is absent from reviewed closure", case=name)
    if _canonical(actual_predicates) != _canonical(entry["predicates"]):
        _refuse("predicates", "scenario expected predicates differ from reviewed predicates", case=name)
    for consumer in entry.get("consumers", []):
        index = consumer["step"]
        if index >= len(steps) or steps[index]["do"] != "bot" or steps[index].get("bot") != consumer["bot"]:
            _refuse("consumers", "consumer must bind its exact scenario bot step", case=name)
    for bot in closure["bots"]:
        missing = _bot_imports(raw_files[f"gamelab/bots/{bot}.py"], bot) - set(closure["bots"])
        if missing:
            _refuse("closure", f"static bot imports missing from explicit review: {sorted(missing)}", case=name)
    fixture = _json(raw_files[f"gamelab/fixtures/{closure['fixture']}.json"])
    if type(fixture) is not dict or fixture.get("name") != closure["fixture"]:
        _refuse("fixture", "fixture identity differs from review", case=name)
    edits = fixture.get("binary_edits", {})
    if type(edits) is not dict:
        _refuse("fixture", "invalid fixture edits", case=name)
    enabled = edits.get("enable_mods", [])
    extra = scenario.get("mods", [])
    _names(enabled, "fixture modules")
    _names(extra, "scenario modules")
    pending, reached = list(enabled) + extra, set()
    while pending:
        module = pending.pop()
        if module in reached:
            continue
        if module not in closure["modules"]:
            _refuse("closure", f"enabled/transitive module missing: {module}", case=name)
        reached.add(module)
        metadata = _json(raw_files[f"mods/{module}/module.json"])
        if type(metadata) is not dict or metadata.get("id") != module:
            _refuse("closure", "module identity differs from reviewed module", case=name)
        requires = metadata.get("requires", [])
        _names(requires, "module requirements")
        pending.extend(requires)
    _check_module_inventory(reached, files, name)
    admission = {key: copy.deepcopy(entry[key]) for key in ("id", "task", "check", "scope", "expected", "predicates", "lifecycle", "private_writes", "review")}
    admission.update(schema_version=catalog["schema_version"], catalog_id=catalog["catalog_id"],
                     catalog_sha256=catalog["metadata"]["sha256"],
                     closure_sha256=_sha(_canonical(closure)), files=copy.deepcopy(files),
                     consumers=copy.deepcopy(entry.get("consumers", [])))
    return {"scenario": scenario, "admission": admission}
