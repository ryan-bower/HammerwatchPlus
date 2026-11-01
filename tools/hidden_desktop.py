#!/usr/bin/env python
"""Run a child process on its own Windows desktop, boxed so it cannot hog the machine.

Two independent guarantees, because focus and load are two different problems
and fixing only one still leaves the desktop unusable:

1. **It cannot appear.** A Windows desktop object (below).
2. **It cannot starve you.** A job object that pins the whole process tree to
   all-but-two cores, runs it at idle priority, caps total memory, and kills
   every survivor when the handle closes.

The second half is the one that matters for Playwright. Chrome is a process
*tree* — browser, GPU, network, one renderer per site — and a browser booting a
WebGL app will happily take every core it can see. Priority alone is not enough:
idle-priority threads still get scheduled on all cores, and a GPU process at any
priority can wedge the compositor. The affinity mask is what makes the freeze
structurally impossible rather than merely unlikely.

Lifted from `C:\\FastProjects\\godot-forge\\hidden.py`, which is where this was
worked out and measured. The mechanism is a Windows *desktop object*
(`CreateDesktopW` — the kernel object, not the shell's "virtual desktops"): a
separate window-manager namespace with its own window list, its own z-order and
its own foreground window. `lpDesktop` is read by the kernel at `CreateProcess`,
before the child runs a single instruction, so nothing the child does afterwards
can put a window on the desktop you are looking at. There is no window-flag race
because there is no window on your desktop to race.

Descendants inherit it. A child spawned with `lpDesktop = NULL` — which is what
every ordinary launcher passes — lands on its parent's desktop. That is what
makes this work for **Playwright**: launch the *driver script* here and the
Chrome it starts is born on the hidden desktop too, so `headless=False` stays
available (real compositor, real GPU, real presented frames) without a window
ever appearing.

Two things godot-forge measured that carry over:

- Only the window manager is per-desktop; the GPU is not. Frames rendered here
  came out byte-identical to the same frames rendered on screen.
- Across a full run the foreground window on the real desktop never changed
  once, sampled every 50ms, while a fullscreen game held it.

Usage:

    import sys, hidden_desktop
    done = hidden_desktop.run([sys.executable, "my_playwright_driver.py"])
    print(done.stdout)

or from a shell:

    python C:/Users/udaha/.claude/tools/hidden_desktop.py python driver.py
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

WINDOWS = sys.platform == "win32"

if WINDOWS:
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _u32 = ctypes.WinDLL("user32", use_last_error=True)

    _u32.CreateDesktopW.restype = wintypes.HANDLE
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _k32.OpenJobObjectW.restype = wintypes.HANDLE
    _k32.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.GetCurrentProcess.restype = wintypes.HANDLE
    _k32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                   ctypes.POINTER(wintypes.BOOL)]
    _k32.GetProcessAffinityMask.argtypes = [wintypes.HANDLE,
                                          ctypes.POINTER(ctypes.c_size_t),
                                          ctypes.POINTER(ctypes.c_size_t)]
    _k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                            wintypes.LPVOID, wintypes.DWORD]
    _k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                              wintypes.LPVOID, wintypes.DWORD,
                                              wintypes.LPVOID]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _u32.CloseDesktop.argtypes = [wintypes.HANDLE]

    GENERIC_ALL = 0x10000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_RW = 0x00000003
    CREATE_ALWAYS = 2
    FILE_ATTRIBUTE_NORMAL = 0x80
    STARTF_USESTDHANDLES = 0x00000100
    WAIT_TIMEOUT = 0x00000102
    INVALID_HANDLE = wintypes.HANDLE(-1).value

    CREATE_SUSPENDED = 0x00000004
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    IDLE_PRIORITY_CLASS = 0x00000040
    BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

    JOB_OBJECT_LIMIT_AFFINITY = 0x00000010
    JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x00000020
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectBasicAccountingInformation = 1
    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_QUERY = 0x0004
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_ALREADY_EXISTS = 183

    ULONG_PTR = ctypes.c_size_t

    class _JobBasicAccounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_int64),
            ("TotalKernelTime", ctypes.c_int64),
            ("ThisPeriodTotalUserTime", ctypes.c_int64),
            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    class _JobBasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ULONG_PTR),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _JobExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JobBasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _StartupInfoW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class _ProcessInformation(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]

    class _SecurityAttributes(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]

    _u32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    _k32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID,
                                    wintypes.LPVOID, wintypes.BOOL, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.LPCWSTR,
                                    ctypes.POINTER(_StartupInfoW), ctypes.POINTER(_ProcessInformation)]
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k32.ResumeThread.argtypes = [wintypes.HANDLE]
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]


DESKTOP = "claude_hidden"

# Exit code given to every process in the tree when `run()` kills it at the
# timeout (GNU `timeout` uses the same number). `run()` itself raises
# `subprocess.TimeoutExpired`, like `subprocess.run`; this is only what the
# killed processes report.
TIMEOUT_EXIT_CODE = 124


def _win_error(call: str) -> OSError:
    return ctypes.WinError(ctypes.get_last_error(), f"{call} failed")


def _object_name(name: str, kind: str) -> str:
    # A single session-local object name, never a window-station path or a
    # Global namespace. Slot callers supply a fresh pool/slot/run UUID.
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", name):
        raise ValueError(f"{kind} must be 1-120 ASCII letters, digits, dots, dashes or underscores")
    return name


def process_in_job(pid: int, job_name: str) -> bool:
    """Query membership of this exact named job; unknown visibility raises.

    An absent/inaccessible job or process is not proof of membership. No
    machine-wide process enumeration and no fallback to 'in any job' occurs.
    The owning run must still hold its job handle when this is called.
    """
    _object_name(job_name, "job_name")
    if type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
        raise ValueError("pid must be a positive DWORD integer")
    if not WINDOWS:
        raise OSError("exact Windows job membership is unavailable on this platform")
    job = _k32.OpenJobObjectW(JOB_OBJECT_QUERY, False, job_name)
    if not job:
        raise _win_error("OpenJobObjectW")
    process = None
    try:
        process = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process:
            raise _win_error("OpenProcess")
        belongs = wintypes.BOOL()
        if not _k32.IsProcessInJob(process, job, ctypes.byref(belongs)):
            raise _win_error("IsProcessInJob")
        return bool(belongs.value)
    finally:
        if process:
            _k32.CloseHandle(process)
        _k32.CloseHandle(job)


def _environment(env, job_name: str | None):
    """Private UTF-16 environment block; never modify the supervisor's env."""
    if env is None and job_name is None:
        return None
    values = dict(os.environ if env is None else env)
    seen = set()
    for key, value in values.items():
        if (not isinstance(key, str) or not key or "=" in key or "\0" in key
                or not isinstance(value, str) or "\0" in value):
            raise ValueError("child environment requires nonempty string keys and NUL-free string values")
        if key.upper() in seen:
            raise ValueError("duplicate case-insensitive child environment key")
        seen.add(key.upper())
    if job_name is not None:
        values = {k: v for k, v in values.items() if k.upper() != "GAMELAB_JOB_NAME"}
        values["GAMELAB_JOB_NAME"] = job_name
    text = "\0".join(f"{k}={values[k]}" for k in sorted(values, key=str.upper)) + "\0\0"
    payload = text.encode("utf-16le")
    return ctypes.create_string_buffer(payload, len(payload))


def _inheritable_file(path: Path) -> int:
    sa = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), None, True)
    h = _k32.CreateFileW(str(path), GENERIC_WRITE, FILE_SHARE_RW, ctypes.byref(sa),
                         CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None)
    if h == INVALID_HANDLE:
        raise _win_error("CreateFileW")
    return h


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _active_processes(job) -> int:
    acct = _JobBasicAccounting()
    if not _k32.QueryInformationJobObject(job, JobObjectBasicAccountingInformation,
                                          ctypes.byref(acct), ctypes.sizeof(acct), None):
        return -1
    return acct.ActiveProcesses


def job_empty(job_name: str) -> bool:
    """Prove a named worker job absent or empty; visibility errors never pass."""
    _object_name(job_name, "job_name")
    if not WINDOWS:
        raise OSError("named job accounting requires Windows")
    job = _k32.OpenJobObjectW(JOB_OBJECT_QUERY, False, job_name)
    if not job:
        if ctypes.get_last_error() == 2:  # ERROR_FILE_NOT_FOUND
            return True
        raise _win_error("OpenJobObjectW")
    try:
        count = _active_processes(job)
        if count < 0:
            raise _win_error("QueryInformationJobObject")
        return count == 0
    finally:
        _k32.CloseHandle(job)


def _kill_tree(job, exit_code: int, wait: float = 10.0) -> bool:
    """Terminate every process in the job and wait until they are really gone.

    `TerminateJobObject` (and `KILL_ON_JOB_CLOSE`) only *start* termination; it
    completes asynchronously. Until each process has exited, the file handles
    it inherited — our stdout.txt / stderr.txt — are still open, and deleting
    those files fails with a sharing violation. So wait, bounded, for the job's
    active-process count to reach zero. Returns whether it did.
    """
    _k32.TerminateJobObject(job, exit_code)
    deadline = time.monotonic() + wait
    while True:
        n = _active_processes(job)
        if n == 0:
            return True
        if n < 0 or time.monotonic() > deadline:
            return False
        time.sleep(0.02)


def _unlink_quietly(path: Path, wait: float = 2.0) -> None:
    """Delete a temp file, retrying briefly while something still holds it open.

    Never raises: a file still locked after `wait` is left behind rather than
    turning a finished run into a crash that loses its output.
    """
    deadline = time.monotonic() + wait
    while True:
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            if time.monotonic() > deadline:
                return
            time.sleep(0.05)


def _affinity(cores: int | None, affinity_mask: int | None) -> int:
    total = os.cpu_count() or 4
    if cores is not None and (type(cores) is not int or cores < 1):
        raise ValueError("cores must be a positive integer")
    if affinity_mask is None:
        return (1 << max(1, min(cores if cores else total - 2, total))) - 1
    if cores is not None:
        raise ValueError("supply cores or affinity_mask, not both")
    if (type(affinity_mask) is not int or affinity_mask <= 0
            or affinity_mask.bit_length() > min(total, ctypes.sizeof(ctypes.c_size_t) * 8)):
        raise ValueError("affinity_mask must select available processors in one native affinity mask")
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not _k32.GetProcessAffinityMask(_k32.GetCurrentProcess(),
                                      ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise _win_error("GetProcessAffinityMask")
    if affinity_mask & ~process_mask.value:
        raise ValueError("affinity_mask selects processors unavailable to this supervisor")
    return affinity_mask


def _make_job(cores: int | None, memory_mb: int, *, job_name: str | None = None,
              affinity_mask: int | None = None, allow_breakaway: bool = True) -> wintypes.HANDLE:
    """Create the job before the suspended child can spawn descendants.

    `KILL_ON_JOB_CLOSE` is the one that stops runs from accumulating: whatever
    happens to this script — clean exit, exception, being killed — every process
    in the tree dies when the handle closes. A Playwright driver that throws
    used to leave a browser behind, and three of those is a wedged machine.

    `BREAKAWAY_OK` is set because Chrome nests jobs of its own for sandboxing;
    without it the browser fails to start its renderers on older Windows. The
    legacy browser behavior is retained by default. Slot runs disable breakaway
    so a descendant cannot request escape from this owned job.
    """
    if type(memory_mb) is not int or not 0 < memory_mb <= (2 ** (ctypes.sizeof(ctypes.c_size_t) * 8) - 1) // (1024 * 1024):
        raise ValueError("memory_mb must be a positive integer fitting a native byte count")
    if type(allow_breakaway) is not bool:
        raise ValueError("allow_breakaway must be a boolean")
    if job_name is not None:
        _object_name(job_name, "job_name")
    affinity = _affinity(cores, affinity_mask)
    ctypes.set_last_error(0)
    job = _k32.CreateJobObjectW(None, job_name)
    error = ctypes.get_last_error()
    if not job:
        raise _win_error("CreateJobObjectW")
    if job_name is not None and error == ERROR_ALREADY_EXISTS:
        # CreateJobObject opens an existing job. Never change its limits or
        # terminate its members: this run does not own that kernel object.
        _k32.CloseHandle(job)
        raise OSError(f"named job already exists: {job_name}")

    info = _JobExtendedLimits()
    b = info.BasicLimitInformation
    b.LimitFlags = (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    | JOB_OBJECT_LIMIT_PRIORITY_CLASS
                    | JOB_OBJECT_LIMIT_AFFINITY
                    | JOB_OBJECT_LIMIT_JOB_MEMORY)
    if allow_breakaway:
        b.LimitFlags |= JOB_OBJECT_LIMIT_BREAKAWAY_OK
    b.PriorityClass = IDLE_PRIORITY_CLASS
    b.Affinity = affinity
    info.BasicLimitInformation = b
    info.JobMemoryLimit = memory_mb * 1024 * 1024

    if not _k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                        ctypes.byref(info), ctypes.sizeof(info)):
        _k32.CloseHandle(job)
        raise _win_error("SetInformationJobObject")
    return job


def _job_telemetry(job) -> dict:
    """Best-effort scalar accounting, not an independent process-exit proof."""
    info, acct = _JobExtendedLimits(), _JobBasicAccounting()
    limits_ok = bool(_k32.QueryInformationJobObject(job, JobObjectExtendedLimitInformation,
                                                  ctypes.byref(info), ctypes.sizeof(info), None))
    accounting_ok = bool(_k32.QueryInformationJobObject(job, JobObjectBasicAccountingInformation,
                                                      ctypes.byref(acct), ctypes.sizeof(acct), None))
    return {
        "affinity_mask": int(info.BasicLimitInformation.Affinity) if limits_ok else None,
        "memory_limit_bytes": int(info.JobMemoryLimit) if limits_ok else None,
        "peak_job_memory_bytes": int(info.PeakJobMemoryUsed) if limits_ok else None,
        "peak_process_memory_bytes": int(info.PeakProcessMemoryUsed) if limits_ok else None,
        "total_processes": int(acct.TotalProcesses) if accounting_ok else None,
        "active_processes": int(acct.ActiveProcesses) if accounting_ok else None,
        "accounting_ok": accounting_ok, "limits_query_ok": limits_ok,
    }


def run(cmd: list[str], cwd: Path | str | None = None, timeout: float = 1800.0,
        visible: bool = False, cores: int | None = None,
        memory_mb: int = 4096, *, desktop_name: str | None = None,
        job_name: str | None = None, affinity_mask: int | None = None,
        env: dict[str, str] | None = None,
        allow_breakaway: bool = True) -> subprocess.CompletedProcess:
    """Like subprocess.run(capture_output=True, text=True), boxed and out of sight.

    `visible=True` spawns on the caller's desktop instead — the only route by
    which a window ever reaches the screen, and never the fallback for one that
    failed. If the desktop cannot be created this raises rather than downgrading
    silently: the promise that it stays out of the way is the whole point, and a
    caller that disagrees can say so with `visible`.

    `cores` defaults to every core but two, `memory_mb` to 4 GB for the whole
    tree. Both are ceilings on the tree, not on one process.

    Slot callers opt in with fresh ASCII `desktop_name` and `job_name` values,
    `allow_breakaway=False`, and an explicit memory/affinity budget. `affinity_mask`
    and `cores` are mutually exclusive. A named job is exclusive; a collision
    refuses before any child starts. Its exact name is passed to the child as
    GAMELAB_JOB_NAME, for `process_in_job` verification while the owner is alive.
    `env` follows subprocess's replacement-environment convention. The returned
    CompletedProcess has scalar `.isolation` accounting (also on timeout errors).
    Unspecified names retain the shared legacy desktop and unnamed job.

    At `timeout` the whole tree is killed (each process exits with
    `TIMEOUT_EXIT_CODE`) and waited for, then `subprocess.TimeoutExpired` is
    raised with the output captured so far on `.stdout` / `.stderr` — the same
    contract as `subprocess.run`. Any descendant still running after the child
    exits normally is killed the same way before `run()` returns.
    """
    slot_controls = desktop_name is not None or job_name is not None or affinity_mask is not None or not allow_breakaway
    if slot_controls and (visible or not WINDOWS):
        raise ValueError("desktop/job/affinity isolation requires a hidden Windows run")
    if desktop_name is not None:
        _object_name(desktop_name, "desktop_name")
    if job_name is not None:
        _object_name(job_name, "job_name")
    if visible or not WINDOWS:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, **({"env": env} if env is not None else {}))

    selected_desktop = DESKTOP if desktop_name is None else desktop_name
    environment = _environment(env, job_name)
    hdesk = _u32.CreateDesktopW(selected_desktop, None, None, 0, GENERIC_ALL, None)
    if not hdesk:
        raise OSError(
            f"cannot create the hidden desktop {selected_desktop!r} "
            f"(error {ctypes.get_last_error()}), so the child's window would "
            "have to open on your desktop. Refusing — pass visible=True to "
            "allow that deliberately.")

    job = tmp = None
    out_path = err_path = None
    h_out = h_err = None
    killed = False
    pi = _ProcessInformation()
    try:
        job = _make_job(cores, memory_mb, job_name=job_name,
                        affinity_mask=affinity_mask, allow_breakaway=allow_breakaway)
        tmp = Path(tempfile.mkdtemp(prefix="claude-hidden-"))
        out_path, err_path = tmp / "stdout.txt", tmp / "stderr.txt"
        h_out, h_err = _inheritable_file(out_path), _inheritable_file(err_path)

        si = _StartupInfoW()
        si.cb = ctypes.sizeof(si)
        si.lpDesktop = "WinSta0\\" + selected_desktop
        si.dwFlags = STARTF_USESTDHANDLES
        si.hStdInput = None
        si.hStdOutput = h_out
        si.hStdError = h_err

        # Suspended, so the limits are on before the first instruction runs —
        # the same reasoning as `lpDesktop`. A process that is allowed to run
        # first can spawn children that were never in the job.
        line = subprocess.list2cmdline(cmd)
        if not _k32.CreateProcessW(None, ctypes.create_unicode_buffer(line), None,
                                   None, True,
                                   CREATE_SUSPENDED | IDLE_PRIORITY_CLASS
                                   | (CREATE_UNICODE_ENVIRONMENT if environment is not None else 0), environment,
                                   str(cwd) if cwd else None,
                                   ctypes.byref(si), ctypes.byref(pi)):
            raise _win_error("CreateProcessW")
        if not _k32.AssignProcessToJobObject(job, pi.hProcess):
            _k32.TerminateProcess(pi.hProcess, 1)
            _k32.WaitForSingleObject(pi.hProcess, 10000)
            raise _win_error("AssignProcessToJobObject")
        if job_name is not None:
            belongs = wintypes.BOOL()
            if not _k32.IsProcessInJob(pi.hProcess, job, ctypes.byref(belongs)) or not belongs.value:
                raise OSError("suspended child is not verifiably in its exact owned job")
        if _k32.ResumeThread(pi.hThread) == wintypes.DWORD(-1).value:
            raise _win_error("ResumeThread")

        deadline = time.monotonic() + timeout
        timed_out = False
        while True:
            status = _k32.WaitForSingleObject(pi.hProcess, 200)
            if status == 0:
                break
            if status != WAIT_TIMEOUT:
                raise _win_error("WaitForSingleObject")
            if time.monotonic() > deadline:
                timed_out = True
                break
        # Kill the whole tree — not just the direct child — and wait for it to
        # be gone. On timeout that is bun/python *and* the browser it started;
        # after a normal exit it is any orphan still running, which the job's
        # kill-on-close would have killed anyway, only asynchronously and
        # while we were deleting files it still had open.
        tree_clean = _kill_tree(job, TIMEOUT_EXIT_CODE if timed_out else 1)
        killed = True
        isolation = {"desktop_name": selected_desktop, "job_name": job_name,
                     "allow_breakaway": allow_breakaway, "tree_clean": tree_clean,
                     **_job_telemetry(job)}
        code = wintypes.DWORD()
        if not _k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code)):
            raise _win_error("GetExitCodeProcess")
        # Close the write ends before reading, or the tail can still be buffered.
        for h in (h_out, h_err):
            _k32.CloseHandle(h)
        h_out = h_err = None
        stdout, stderr = _read(out_path), _read(err_path)
        if timed_out:
            # Same shape as subprocess.run: partial output on the exception.
            error = subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)
            error.isolation = isolation
            raise error
        if job_name is not None and not tree_clean:
            raise OSError("owned job did not become observably empty before return")
        done = subprocess.CompletedProcess(cmd, code.value, stdout, stderr)
        done.isolation = isolation
        return done
    finally:
        # Nothing here may raise: an exception from cleanup would replace the
        # result (or the TimeoutExpired carrying the partial output).
        for h in (h_out, h_err, pi.hProcess, pi.hThread):
            if h:
                _k32.CloseHandle(h)
        # Tree dead before the job handle goes (kill-on-close would do it, but
        # without waiting) and before the files are deleted.
        if job and not killed:
            _kill_tree(job, 1)
        if job:
            _k32.CloseHandle(job)
        _u32.CloseDesktop(hdesk)
        for p in (out_path, err_path):
            if p is not None:
                _unlink_quietly(p)
        try:
            if tmp is not None:
                tmp.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    try:
        done = run(sys.argv[1:], cwd=Path.cwd())
    except subprocess.TimeoutExpired as e:
        sys.stdout.write(e.stdout or "")
        sys.stderr.write(e.stderr or "")
        sys.exit(TIMEOUT_EXIT_CODE)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    sys.exit(done.returncode)
