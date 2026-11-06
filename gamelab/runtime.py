"""Authenticated two-slot lab paths and process records; no game launching.

The coordinator retains the legacy machine lease. This is an ownership protocol
between cooperating processes, not a security boundary against the same user.
Absent context preserves the existing serial runtime.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import time

REPO = Path(__file__).resolve().parent.parent
WORKERS = REPO / "gamelab/env/userdata/workers"
RESULTS = REPO / "gamelab/results/workers"
MACHINE_LOCK = REPO / "gamelab/env/userdata/gamelab.lock"
ENV_KEYS = ("GAMELAB_RUNTIME_MANIFEST", "GAMELAB_RUNTIME_SLOT",
            "GAMELAB_RUNTIME_TOKEN", "GAMELAB_RUNTIME_RESULTS")
_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
_HEX = re.compile(r"[0-9a-f]{32}\Z")


class RuntimeError(ValueError):
    """Runtime context cannot be established safely."""


def _require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _name(value):
    _require(isinstance(value, str) and _NAME.fullmatch(value)
             and value.upper() not in {"CON", "PRN", "AUX", "NUL"}
             and not re.fullmatch(r"(?:COM|LPT)[1-9]", value.upper()), "invalid runtime name")
    return value


def _absolute(path):
    path = Path(path)
    _require(".." not in path.parts, "runtime path contains traversal")
    return path.absolute()


def _ordinary(info, directory):
    return (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) \
        and not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400


def _dirs(path, create=False):
    """Inspect every ancestor without resolving/following a reparse point."""
    path = _absolute(path)
    chain = list(reversed(path.parents)) + [path]
    for part in chain:
        try:
            info = part.lstat()
        except FileNotFoundError:
            if create:
                part.mkdir()  # no exist_ok: a racing creator requires inspection
                info = part.lstat()
            else:
                continue
        _require(_ordinary(info, True), f"runtime ancestor is not an ordinary directory: {part}")
    return path


def _read(path):
    path = _absolute(path)
    _dirs(path.parent)
    before = path.lstat()
    _require(_ordinary(before, False) and before.st_nlink == 1 and before.st_size <= 65536,
             f"runtime record is not a bounded independent file: {path}")
    data = path.read_bytes()
    after = path.lstat()
    _dirs(path.parent)
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    _require(_ordinary(after, False) and after.st_nlink == 1 and identity(before) == identity(after), "runtime record changed while reading")
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError) as error:
        raise RuntimeError(f"malformed runtime record: {path}") from error
    _require(isinstance(value, dict), "runtime record must be an object")
    return value


def _new(path, value):
    path = _absolute(path)
    _dirs(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    _require(_read(path) == value, "runtime record did not read back")


def _replace(path, value, old):
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    _new(temporary, value)
    _require(_read(path) == old, "runtime ownership changed before publication")
    os.replace(temporary, path)


def _kernel():
    _require(os.name == "nt", "runtime process authentication requires Windows")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, *(ctypes.POINTER(wintypes.FILETIME),) * 4)
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _handle_info(kernel, handle, pid):
    """Read identity from the held object, never by reopening its numeric PID."""
    from ctypes import wintypes
    code = wintypes.DWORD()
    if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
        raise RuntimeError(f"cannot query process {pid} exit")
    if code.value != 259:
        return None
    c, e, k, u = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(handle, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
        raise RuntimeError(f"cannot query process {pid} creation")
    if e.dwHighDateTime or e.dwLowDateTime:  # an exited process may itself return code259
        return None
    image = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(image))
    if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
        raise RuntimeError(f"cannot query process {pid} image")
    return ((c.dwHighDateTime << 32) | c.dwLowDateTime, image.value)


def process_info(pid):
    """Exact creation FILETIME/image; None only absent/exited, unknown raises."""
    _require(type(pid) is int and pid > 0, "invalid process PID")
    kernel = _kernel()
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: the PID does not exist
            return None
        raise RuntimeError(f"cannot inspect process {pid}: WinError {error}")
    try:
        return _handle_info(kernel, handle, pid)
    finally:
        kernel.CloseHandle(handle)


def process_creation(pid):
    info = process_info(pid)
    return info[0] if info else None


def _identity(pid):
    value = process_info(pid)
    _require(value is not None, f"runtime owner PID {pid} is absent")
    return {"pid": pid, "created": value[0]}


def _alive(owner):
    _require(isinstance(owner, dict) and type(owner.get("pid")) is int
             and owner["pid"] > 0 and type(owner.get("created")) is int and owner["created"] > 0,
             "malformed runtime process identity")
    info = process_info(owner["pid"])
    return info is not None and info[0] == owner["created"]


def _same(a, b):
    return os.path.normcase(str(_absolute(str(a).removeprefix("\\\\?\\")))) == os.path.normcase(str(_absolute(b)))


def _root(root):
    root = _absolute(root)
    _require(root.parent == _absolute(WORKERS), "pool must be directly under the worker root")
    _name(root.name)
    _dirs(root)
    return root


def _source(value):
    _require(isinstance(value, dict) and value.get("fingerprint_scope") == "mods+gamelab+tools-v2"
             and isinstance(value.get("head"), str) and bool(value["head"])
             and isinstance(value.get("source_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", value["source_sha256"])
             and type(value.get("files")) is int and value["files"] > 0, "invalid frozen source fingerprint")


def _catalog_pin(value):
    """Authenticate the immutable per-pool data snapshot, independently of code."""
    _require(isinstance(value, dict) and set(value) == {"path", "sha256"}, "invalid catalog descriptor")
    path = _absolute(value["path"])
    _require(path.parent.parent == _absolute(RESULTS).parent
             and re.fullmatch(r"pool-[A-Za-z0-9][A-Za-z0-9_-]{0,79}", path.parent.name)
             and path.name == "catalog.snapshot.json", "catalog snapshot is outside managed pool results")
    _require(isinstance(value["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
             "invalid catalog snapshot hash")
    _dirs(path.parent)
    before = path.lstat()
    _require(_ordinary(before, False) and before.st_nlink == 1 and 0 < before.st_size <= 16 * 1024 * 1024,
             "catalog snapshot is not a bounded independent file")
    raw = path.read_bytes()
    after = path.lstat()
    _require(_ordinary(after, False) and after.st_nlink == 1
             and (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size)
             == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)
             and hashlib.sha256(raw).hexdigest() == value["sha256"], "catalog snapshot changed")
    return {"path": str(path), "sha256": value["sha256"]}


def _manifest(value):
    path = value["manifest_path"] if isinstance(value, dict) else value
    path = _absolute(path)
    root = _root(path.parent)
    _require(path.name == "pool.json", "invalid pool manifest path")
    m = _read(path)
    _require(type(m.get("version")) is int and m["version"] == 1 and m.get("pool_id") == root.name
             and m.get("manifest_path") == str(path) and m.get("closed") is False
             and isinstance(m.get("token"), str) and _HEX.fullmatch(m["token"]), "invalid/closed pool manifest")
    _require(_alive(m.get("coordinator")), "pool coordinator is absent or PID was reused")
    _source(m.get("source"))
    if "catalog" in m:
        _require(_catalog_pin(m["catalog"]) == m["catalog"], "catalog descriptor is not canonical")
    _require(isinstance(m.get("machine_lease"), dict), "malformed machine lease binding")
    lease = _read(MACHINE_LOCK)
    _require(lease.get("pid") == m["coordinator"]["pid"] == m["machine_lease"].get("pid")
             and lease.get("token") == m["machine_lease"].get("token")
             and isinstance(lease.get("token"), str) and _HEX.fullmatch(lease["token"]), "pool lost the legacy machine lease")
    _require(isinstance(m.get("slots"), list) and len(m["slots"]) == 2, "pool must contain exactly two slots")
    usable = max(1, (os.cpu_count() or 4) - 2)
    _require(usable >= 2, "two slots require two available worker cores")
    per = usable // 2
    for index, slot in enumerate(m["slots"], 1):
        sid = f"worker-{index}"
        _require(isinstance(slot, dict) and slot.get("slot_id") == sid and slot.get("game_dir") == str(root / sid / "game")
                 and slot.get("module_root") == str(root / sid / "mods")
                 and slot.get("cache_dir") == str(root / sid / "cache")
                 and slot.get("results") == str(_absolute(RESULTS) / root.name / sid)
                 and isinstance(slot.get("token"), str) and _HEX.fullmatch(slot["token"]), "invalid slot roots or token")
        _require(slot.get("desktop_name") == f"gamelab_{root.name}_{index}_{m['token'][:8]}"
                 and slot.get("job_name") == f"gamelab_job_{root.name}_{index}_{m['token'][:8]}"
                 and type(slot.get("affinity_mask")) is int and slot["affinity_mask"] == ((1 << per) - 1) << ((index - 1) * per)
                 and type(slot.get("memory_mb")) is int and slot["memory_mb"] == 4096, "slot resource identity changed")
        for key in ("game_dir", "module_root", "cache_dir", "results"):
            _dirs(slot[key])
            _require(_ordinary(Path(slot[key]).lstat(), True), "slot root is absent or not an ordinary directory")
    _require(len({s["token"] for s in m["slots"]}) == 2 and all(s["token"] != m["token"] for s in m["slots"]), "slot secrets are not distinct")
    return m


def create_pool(root, machine_lease, source, slot_count=2, *, catalog=None):
    """Create one fresh pool while this coordinator holds the legacy machine lock."""
    _require(type(slot_count) is int and slot_count == 2, "only two-worker pools are supported")
    root = _root(root)
    _require(len(str(root / "worker-1/game/appdata").encode("utf-16-le")) // 2 < 260,
             "worker AppData path exceeds the isolation shim buffer")
    lease = _read(MACHINE_LOCK)
    _require(isinstance(machine_lease, dict) and lease == machine_lease and lease.get("pid") == os.getpid()
             and isinstance(lease.get("token"), str) and _HEX.fullmatch(lease["token"]), "coordinator does not own the machine lease")
    _source(source)
    catalog_pin = _catalog_pin(catalog) if catalog is not None else None
    _dirs(WORKERS, create=True)
    root.mkdir()  # one lifetime per pool name; never reuse an existing tree
    _dirs(root)
    token = secrets.token_hex(16)
    usable = max(1, (os.cpu_count() or 4) - 2)
    _require(usable >= 2, "two slots require two available worker cores")
    slots = []
    for index in (1, 2):
        sid = f"worker-{index}"
        per = usable // 2
        mask = ((1 << per) - 1) << ((index - 1) * per)
        slot = {"slot_id": sid, "token": secrets.token_hex(16),
                "game_dir": str(root / sid / "game"), "module_root": str(root / sid / "mods"),
                "cache_dir": str(root / sid / "cache"), "results": str(_absolute(RESULTS) / root.name / sid),
                "desktop_name": f"gamelab_{root.name}_{index}_{token[:8]}",
                "job_name": f"gamelab_job_{root.name}_{index}_{token[:8]}",
                "affinity_mask": mask, "memory_mb": 4096}
        for key in ("game_dir", "module_root", "cache_dir", "results"):
            _dirs(slot[key], create=True)
        slots.append(slot)
    m = {"version": 1, "pool_id": root.name, "manifest_path": str(root / "pool.json"), "token": token,
         "coordinator": _identity(os.getpid()), "machine_lease": {"pid": lease["pid"], "token": lease["token"]},
         "source": json.loads(json.dumps(source)), "slots": slots, "closed": False}
    if catalog_pin is not None:
        m["catalog"] = catalog_pin
    _new(root / "pool.json", m)
    return _manifest(m)


@dataclass(frozen=True)
class RuntimeSlot:
    manifest: dict
    slot: dict
    results: Path

    @property
    def pool_id(self): return self.manifest["pool_id"]
    @property
    def slot_id(self): return self.slot["slot_id"]
    @property
    def game_dir(self): return Path(self.slot["game_dir"])
    @property
    def module_root(self): return Path(self.slot["module_root"])
    @property
    def cache_dir(self): return Path(self.slot["cache_dir"])
    @property
    def desktop_name(self): return self.slot["desktop_name"]
    @property
    def job_name(self): return self.slot["job_name"]
    @property
    def affinity_mask(self): return self.slot["affinity_mask"]
    @property
    def memory_mb(self): return self.slot["memory_mb"]


def _slot(m, name):
    if type(name) is int:
        _require(name in (0, 1), "invalid slot index")
        name = f"worker-{name + 1}"
    match = [s for s in m["slots"] if s["slot_id"] == name]
    _require(len(match) == 1, "unknown runtime slot")
    return match[0]


def _results(slot, results):
    root = _absolute(slot["results"])
    result = _absolute(results) if results is not None else root / "run"
    _require(result != root and result.is_relative_to(root), "results must be inside the selected slot result root")
    _dirs(result)
    return result


def child_env(manifest, slot, results=None):
    m = _manifest(manifest)
    s = _slot(m, slot)
    return dict(zip(ENV_KEYS, (m["manifest_path"], s["slot_id"], s["token"], str(_results(s, results)))))


def current(environ=None):
    values = os.environ if environ is None else environ
    present = [key in values for key in ENV_KEYS]
    if not any(present):
        return None
    _require(all(present) and all(isinstance(values[k], str) and values[k] for k in ENV_KEYS), "partial runtime environment")
    m = _manifest(values[ENV_KEYS[0]])
    slot = _slot(m, values[ENV_KEYS[1]])
    _require(secrets.compare_digest(slot["token"], values[ENV_KEYS[2]]), "runtime slot secret mismatch")
    return RuntimeSlot(m, slot, _results(slot, values[ENV_KEYS[3]]))


@contextmanager
def _guard(path, token, timeout):
    _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 3600, "invalid preparation timeout")
    owner = dict(_identity(os.getpid()), token=secrets.token_hex(16), pool_token=token)
    deadline = time.monotonic() + timeout
    while True:
        try:
            _new(path, owner)
            break
        except FileExistsError:
            held = _read(path)
            _require(held.get("pool_token") == token and _alive(held), "stale/foreign preparation guard; inspect before retry")
            _require(time.monotonic() < deadline, "preparation guard is busy")
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    try:
        yield
    finally:
        _require(_read(path) == owner, "preparation ownership changed; foreign guard retained")
        path.unlink()


@contextmanager
def preparation_guard(timeout=300):
    ctx = current()
    if ctx is None:
        yield
        return
    with _guard(Path(ctx.manifest["manifest_path"]).with_name("preparation.lock"), ctx.manifest["token"], timeout):
        _manifest(ctx.manifest)
        yield


def _lease(ctx):
    value = _read(ctx.game_dir.parent / "gamelab.lock")
    _require(isinstance(value.get("token"), str) and _HEX.fullmatch(value["token"]), "invalid slot lease")
    return dict(_identity(value.get("pid")), token=value["token"])


def _game_record(ctx):
    path = ctx.game_dir.parent / "game.json"
    try:
        record = _read(path)
    except FileNotFoundError:
        return None
    _require(record.get("pool_token") == ctx.manifest["token"] and record.get("slot_token") == ctx.slot["token"]
             and _same(record.get("image", ""), ctx.game_dir / "HWR2.exe"), "foreign/malformed game registration")
    _require(type(record.get("pid")) is int and record["pid"] > 0 and type(record.get("created")) is int and record["created"] > 0
             and isinstance(record.get("lease"), dict), "malformed registered game identity")
    return record


def register_game(pid, creation=None):
    ctx = current()
    if ctx is None:
        return
    info = process_info(pid)
    _require(info is not None and _same(info[1], ctx.game_dir / "HWR2.exe")
             and (creation is None or type(creation) is int and creation == info[0]), "game PID/image/creation does not identify this slot")
    lease = _lease(ctx)
    path = ctx.game_dir.parent / "game.json"
    with _guard(path.with_suffix(".guard"), ctx.manifest["token"], 0):
        old = _game_record(ctx)
        if old:
            previous = process_info(old["pid"])
            _require(previous is None or previous[0] != old["created"], "slot already owns a live game")
        record = {"pid": pid, "created": info[0], "image": str(ctx.game_dir / "HWR2.exe"),
                  "pool_token": ctx.manifest["token"], "slot_token": ctx.slot["token"], "lease": lease}
        if old is None:
            _new(path, record)
        else:
            _replace(path, record, old)


def _registered(ctx, pid, image):
    if not _same(image, ctx.game_dir / "HWR2.exe"):
        return False
    record = _game_record(ctx)
    if record is None or record["pid"] != pid:
        return False
    info = process_info(pid)
    return info is not None and info[0] == record["created"] and _same(info[1], image) and record["lease"] == _lease(ctx)


def owned_game(pid, image):
    ctx = current()
    return _registered(ctx, pid, image) if ctx else _same(image, MACHINE_LOCK.parent / "game/HWR2.exe")


def terminate_owned_game(pid, image, timeout=10):
    """Terminate only the authenticated slot game through one held HANDLE.

    PID reuse cannot redirect termination after opening: creation, image,
    exact named-job membership, termination and wait all use that same object.
    Failure preserves the registration/lease and never falls back to taskkill.
    """
    from ctypes import wintypes
    _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 60,
             "invalid owned-process termination timeout")
    ctx = current()
    _require(ctx is not None, "held-handle cleanup is for runtime slots only")
    record = _game_record(ctx)
    _require(record is not None and record["pid"] == pid and _same(image, ctx.game_dir / "HWR2.exe")
             and record["lease"] == _lease(ctx), "process is not owned by this slot acquisition")
    kernel = _kernel()
    kernel.OpenJobObjectW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    handle = job = None
    try:
        handle = kernel.OpenProcess(0x1000 | 0x0001 | 0x100000, False, pid)
        _require(bool(handle), "cannot open owned game for authenticated termination")
        info = _handle_info(kernel, handle, pid)
        _require(info is not None and info[0] == record["created"] and _same(info[1], image),
                 "held game creation/image changed or is unavailable")
        job = kernel.OpenJobObjectW(0x0004, False, ctx.job_name)  # JOB_OBJECT_QUERY
        _require(bool(job), "cannot establish the slot's exact named job")
        belongs = wintypes.BOOL()
        _require(bool(kernel.IsProcessInJob(handle, job, ctypes.byref(belongs))) and bool(belongs.value),
                 "held game is not demonstrably in this slot's named job")
        _manifest(ctx.manifest)
        _require(_game_record(ctx) == record and record["lease"] == _lease(ctx),
                 "slot registration or ownership changed before termination")
        _require(bool(kernel.TerminateProcess(handle, 1)), "owned game termination failed")
        _require(kernel.WaitForSingleObject(handle, math.ceil(timeout * 1000)) == 0,
                 "owned game termination did not finish; retain dirty slot")
        return True
    finally:
        try:
            if job:
                kernel.CloseHandle(job)
        finally:
            if handle:
                kernel.CloseHandle(handle)


def is_registered_process(pid, image):
    ctx = current()
    if ctx is None:
        return False
    return any(_registered(RuntimeSlot(ctx.manifest, slot, Path(slot["results"]) / "run"), pid, image)
               for slot in ctx.manifest["slots"])


def registered_games_absent(manifest):
    """Only registered identities; caller still scans for unknown HWR2 processes."""
    m = _manifest(manifest)
    for slot in m["slots"]:
        record = _game_record(RuntimeSlot(m, slot, Path(slot["results"]) / "run"))
        if record:
            info = process_info(record["pid"])
            if info is not None and info[0] == record["created"]:
                return False
    return True


def close_pool(manifest):
    m = _manifest(manifest)
    _require(m["coordinator"] == _identity(os.getpid()), "only the coordinator closes the pool")
    _require(registered_games_absent(m), "registered games remain; pool retained")
    for slot in m["slots"]:
        path = Path(slot["game_dir"]).parent / "gamelab.lock"
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        raise RuntimeError("slot lease remains; preserve and account it before closing")
    closed = dict(m, closed=True)
    _replace(Path(m["manifest_path"]), closed, m)
