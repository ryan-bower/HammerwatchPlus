"""One GameLab run at a time, and none after a dirty one (playbook P6, per-test isolation).

All runs share one game dir (gamelab/env/userdata/game), so two at once would share
saves, logs and the capture request file. `acquire` takes an exclusive lock file and
refuses when another live run holds it, when a dead run left it behind, or when the last
run reported a dirty teardown (a lab HWR2.exe had to be killed, a pass did not exit 0, or
the runner wrote no inner.json). `python -m gamelab reset` is the one way past a refusal:
it kills lab game processes (only those whose image is inside the lab game dir), wipes the
scratch areas and records a clean teardown.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
import io
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from gamelab import env, runtime
from gamelab.session import process_image

LOCK = env.GAME.parent / "gamelab.lock"
TEARDOWN = env.GAME.parent / "teardown.json"
SCRATCH = ("saves", "appdata")          # wiped before every run; materialize refills saves
EXIT_REFUSED = 4


class Refused(RuntimeError):
    pass


class Busy(Refused):
    """A stable fence whose recorded owner is positively observable as live."""
    waitable = True


class _ClaimCollision(Refused):
    """An atomic claim lost a race; inspect ownership after leaving the sidecar."""


def owner_contention(path: Path, kind: str) -> Refused:
    """Classify a foreign fence without modifying it or trusting refusal text."""
    try:
        before = path.read_bytes()
        held = json.loads(before)
        if (not isinstance(held, dict) or type(held.get("pid")) is not int
                or held["pid"] <= 0 or not isinstance(held.get("token"), str)
                or len(held["token"]) != 32
                or any(c not in "0123456789abcdef" for c in held["token"])):
            return Refused(f"unrecognized {kind} lock owner: {path}; inspect before retrying")
        image = process_image(held["pid"])
        after = path.read_bytes()
    except (OSError, ValueError, TypeError) as error:
        return Refused(f"cannot establish {kind} lock owner: {path}: {error}")
    if before != after:
        return Refused(f"{kind} ownership changed while inspected: {path}; retry after inspection")
    if not isinstance(image, str) or not image:
        return Refused(f"stale or uninspectable {kind} lock owner: {path}; inspect before retrying")
    return Busy(f"another live runtime owner holds the {kind} lock: {path}; pid={held['pid']}")


def pid_alive(pid: int) -> bool:
    return bool(process_image(pid))


def game_processes() -> list[tuple[int, Path]]:
    """Resolved HWR2 identities; incomplete visibility is never an empty scan."""
    result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq HWR2.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True)
    if result.returncode:
        raise Refused("cannot check running game processes: " + (result.stderr or result.stdout).strip())
    processes = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) > 1 and row[0].lower() == "hwr2.exe" and row[1].isdigit():
            pid = int(row[1])
            image = process_image(pid)
            if not image:
                # A registered sibling can finish between tasklist and this
                # query. Only proved exit is absence; access failures still
                # refuse, and serial behavior remains unchanged.
                if runtime.current():
                    try:
                        if runtime.process_info(pid) is None:
                            continue
                    except (OSError, ValueError) as error:
                        raise Refused(f"cannot establish exited game PID {pid}: {error}") from error
                raise Refused(f"cannot inspect HWR2.exe PID {pid}; resolve process visibility before running")
            processes.append((pid, Path(image).resolve()))
    return processes


def lab_processes() -> list[int]:
    """Only the exact lab executable is eligible for lab cleanup."""
    lab_image = (env.GAME / "HWR2.exe").resolve()
    found = [pid for pid, image in game_processes() if image == lab_image]
    if runtime.current():
        for pid in found:
            if not runtime.owned_game(pid, lab_image):
                raise Refused(f"unregistered process at this slot executable: {pid}")
    return found


def player_processes() -> list[int]:
    """A real play session also owns the runtime, after the Steam launcher exits."""
    lab_image = (env.GAME / "HWR2.exe").resolve()
    return [pid for pid, image in game_processes() if image != lab_image
            and not (runtime.current() and runtime.is_registered_process(pid, image))]



@contextmanager
def lifecycle_guard():
    """Serialize lock-file transitions and cleanup; never reset an active guard."""
    guard = LOCK.with_name(LOCK.name + ".lifecycle")
    token = uuid.uuid4().hex
    try:
        fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise owner_contention(guard, "lifecycle") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "token": token}, stream)
        yield
    finally:
        held = json.loads(guard.read_text(encoding="utf-8"))
        if held.get("token") != token:
            raise Refused("runtime lifecycle ownership changed; refusing to remove another guard")
        guard.unlink()


_OWNERS: dict[str, str] = {}


def owned() -> bool:
    """Does this process still own this exact runtime acquisition?"""
    token = _OWNERS.get(str(LOCK.resolve()))
    if not token:
        return False
    try:
        held = json.loads(LOCK.read_text(encoding="utf-8"))
        return held.get("pid") == os.getpid() and held.get("token") == token
    except (OSError, ValueError, AttributeError):
        return False


def require_owned() -> None:
    if not owned():
        raise Refused("runtime ownership changed; refusing scans, cleanup or writes for another owner")


def _claim_file(scenario: str, mode: str) -> None:
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if mode == "play":
            held = json.loads(LOCK.read_text(encoding="utf-8") or "{}")
            raise Refused(f"runtime lock held: {held}; diagnose the owner before retrying") from None
        raise _ClaimCollision("runtime fence appeared during atomic claim") from None
    token = uuid.uuid4().hex
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "token": token, "scenario": scenario, "mode": mode,
                   "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, stream)
    _OWNERS[str(LOCK.resolve())] = token


def _drop_owned() -> None:
    require_owned()
    LOCK.unlink()
    _OWNERS.pop(str(LOCK.resolve()), None)


def abandon() -> None:
    """Release an unused acquisition without rewriting the previous teardown."""
    with lifecycle_guard():
        _drop_owned()


def _wipe_scratch() -> None:
    base = env.GAME.resolve()
    for name in SCRATCH:
        require_owned()
        target = env.GAME / name
        if base not in target.resolve().parents:
            raise Refused(f"scratch target escapes the lab game directory: {target}")
        if target.exists():
            shutil.rmtree(target)


def kill(pids: list[int]) -> None:
    for pid in pids:
        require_owned()
        image = process_image(pid)
        if not image or Path(image).resolve() != (env.GAME / "HWR2.exe").resolve():
            raise Refused(f"cleanup PID {pid} no longer identifies the exact lab executable")
        if runtime.current() and not runtime.owned_game(pid, Path(image)):
            raise Refused(f"cleanup PID {pid} does not belong to this slot acquisition")
        if runtime.current():
            runtime.terminate_owned_game(pid, Path(image))
            continue
        result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        if result.returncode:
            raise Refused(f"could not stop lab PID {pid}; runtime remains refused")


def acquire(scenario: str, mode: str) -> None:
    slot = runtime.current()
    if slot:
        if mode != "lab":
            raise Refused("runtime slots support lab mode only")
        LOCK.parent.mkdir(parents=True, exist_ok=True)
    # Waiting on an existing owner must not hold the fence that owner needs
    # for finishing. The exclusive claim below remains authoritative.
    if LOCK.exists():
        raise owner_contention(LOCK, "runtime")
    try:
        with lifecycle_guard():
            _claim_file(scenario, mode)
            try:
                require_owned()
                players = player_processes()
                if players:
                    raise Refused(f"a player game owns the runtime: HWR2.exe {players}; close the game before running GameLab")
                require_owned()
                last = json.loads(TEARDOWN.read_text(encoding="utf-8")) if TEARDOWN.is_file() else {"clean": True}
                leftover = lab_processes()
                if not last.get("clean") or leftover:
                    raise Refused(f"previous run did not tear down cleanly: {last}"
                                  + (f"; lab HWR2.exe still running: {leftover}" if leftover else "")
                                  + " (python -m gamelab reset)")
                _wipe_scratch()
                require_owned()
                (env.GAME / "appdata").mkdir(parents=True, exist_ok=True)
            except BaseException:
                if owned():
                    _drop_owned()
                raise
    except _ClaimCollision:
        # Another owner won after the read-only precheck. Release our sidecar
        # before the potentially slow process identity probe in this path too.
        raise owner_contention(LOCK, "runtime") from None


@contextmanager
def play_lease():
    """The real-play caller shares lifecycle fencing without wiping lab scratch."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with lifecycle_guard():
        _claim_file("player-run", "play")
        try:
            last = json.loads(TEARDOWN.read_text()) if TEARDOWN.exists() else {"clean": True}
            if not last.get("clean"):
                raise Refused(f"previous GameLab teardown is dirty: {last}; diagnose before retrying")
        except BaseException:
            if owned():
                _drop_owned()
            raise
    try:
        yield
    finally:
        abandon()


@contextmanager
def finishing(run: str, reasons: list[str]):
    """Keep ownership through cleanup and result output, then release exactly once."""
    with lifecycle_guard():
        require_owned()
        leftover = lab_processes()
        require_owned()
        if leftover:
            kill(leftover)
            reasons = reasons + [f"killed leftover lab HWR2.exe {leftover}"]
        record = {"clean": not reasons, "reasons": reasons, "run": run,
                  "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        require_owned()
        TEARDOWN.write_text(json.dumps(record, indent=1), encoding="utf-8")
        try:
            yield record
        except BaseException as error:
            require_owned()
            record["clean"] = False
            record["reasons"] = record["reasons"] + [f"result finalization failed: {type(error).__name__}: {error}"]
            TEARDOWN.write_text(json.dumps(record, indent=1), encoding="utf-8")
            _drop_owned()
            raise
        else:
            _drop_owned()


def release(run: str, reasons: list[str]) -> dict:
    with finishing(run, reasons) as record:
        return record


def _prove_owner_absent(held: dict) -> bool:
    pid = held.get("pid")
    if type(pid) is not int or pid <= 0:
        raise Refused("cannot prove the recorded runtime owner is absent")
    if pid_alive(pid):
        return False
    result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True)
    if result.returncode:
        raise Refused("cannot check the previous runtime owner; reset refused")
    if any(len(row) > 1 and row[1] == str(pid) for row in csv.reader(io.StringIO(result.stdout))):
        raise Refused("runtime owner exists but its image is inaccessible; reset refused")
    return True


def reset() -> int:
    try:
        with lifecycle_guard():
            held = json.loads(LOCK.read_text(encoding="utf-8") or "{}") if LOCK.is_file() else None
            if held is not None:
                if not _prove_owner_absent(held):
                    print(f"refusing: run {held} is still alive")
                    return EXIT_REFUSED
                LOCK.unlink()  # Absence proved while all lifecycle mutations are fenced.
            _claim_file("reset", "lab")
            leftover = lab_processes()
            require_owned()
            kill(leftover)
            _wipe_scratch()
            require_owned()
            TEARDOWN.write_text(json.dumps({"clean": True, "reasons": [], "run": "reset", "killed": leftover,
                                          "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "previous_owner": held},
                                         indent=1), encoding="utf-8")
            _drop_owned()
        print(f"reset: killed {leftover or 'nothing'}, wiped {', '.join(SCRATCH)}")
        return 0
    except (Refused, OSError, ValueError) as error:
        print(f"refusing reset: {error}")
        return EXIT_REFUSED
