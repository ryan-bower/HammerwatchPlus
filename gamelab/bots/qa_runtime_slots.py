"""Bounded two-slot state/posted-menu/capture acceptance; never launches a Game.

IPC is restricted to the authenticated pool's acceptance directory. The timeout
role deliberately outlives its outer budget; its missing return is not a PASS.
No movement, controller repair, account isolation or gameplay claim is made.
"""
import json
import math
import os
from pathlib import Path
import secrets
import time


MARKER_CVAR = "v_fps_limit"
ROLES = {"a": ("routing", "b", 57), "b": ("routing", "a", 59),
         "timeout": ("fault", "survivor", 57),
         "survivor": ("fault", "timeout", 59)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def remaining(deadline, now):
    left = deadline - now
    require(math.isfinite(left) and left > 0, "runtime probe deadline exhausted")
    return left


def validate_peer(value, own, peer_slot, peer_role, phase):
    """Reject stale/cross-pool/cross-role/cross-slot records before process queries."""
    require(isinstance(value, dict) and type(value.get("version")) is int
            and value["version"] == 1, "bad barrier record")
    require(value.get("pool_id") == own["pool_id"] and value.get("phase") == phase
            and value.get("role") == peer_role, "foreign barrier pool/phase/role")
    require(value.get("slot_id") == peer_slot["slot_id"] != own["slot_id"], "wrong sibling slot")
    require(type(value.get("game_pid")) is int and value["game_pid"] > 0
            and value["game_pid"] != own["game_pid"]
            and type(value.get("game_created")) is int and value["game_created"] > 0,
            "invalid or shared game identity")
    expected = Path(peer_slot["game_dir"]) / "HWR2.exe"
    require(os.path.normcase(value.get("game_image", "")) == os.path.normcase(str(expected)),
            "sibling executable mismatch")
    require(".." not in Path(value.get("results", "")).parts, "sibling results traversal")
    result = Path(value.get("results", "")).absolute()
    root = Path(peer_slot["results"]).absolute()
    require(result != root and result.is_relative_to(root), "sibling result path escapes slot")
    require(isinstance(value.get("run_id"), str) and value["run_id"] == result.name,
            "sibling result/run mismatch")
    return value


def assess_observation(value, marker_value, menu_open, tag):
    """Independent routing predicate: nonce, state, scalar and UI must all agree."""
    return (isinstance(value, dict) and value.get("marker_value") == marker_value
            and value.get("tag") == tag and value.get("tag_ok") is True
            and value.get("phase") == "town" and value.get("spawned") is True
            and value.get("menu_open") is menu_open)


def assess_marker_write(ack, readback, requested):
    """A successful command is insufficient: its immediate value and fresh read must match."""
    return (isinstance(ack, dict) and ack.get("ok") is True
            and ack.get("name") == MARKER_CVAR
            and type(ack.get("value")) in (int, float) and math.isfinite(ack["value"])
            and ack["value"] == requested
            and isinstance(readback, dict) and readback.get("ok") is True
            and readback.get("cvars", {}).get(MARKER_CVAR) == requested)


def old_process_gone(info, created):
    # PID reuse proves the OLD identity gone, never authorizes touching its successor.
    return info is None or info[0] != created


def wait_until(predicate, deadline, pump, clock=time.monotonic, sleep=time.sleep):
    while True:
        remaining(deadline, clock())
        value = predicate()  # visibility/identity errors propagate, never become absence
        if value is not None:
            return value
        pump()
        sleep(min(.1, remaining(deadline, clock())))


def publish(path, value, runtime):
    """Atomic no-replace publication on the supported Windows runtime."""
    runtime._dirs(path.parent)
    require(not path.exists(), "barrier record already exists; use a new pool")
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(8) + ".tmp")
    runtime._new(temporary, value)
    try:
        # Windows rename refuses an existing destination. A slot has one writer.
        require(not path.exists(), "barrier publication collision")
        os.rename(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    require(runtime._read(path) == value, "barrier publication readback mismatch")


def run(p, role="a", deadline_s=120, **_):
    from gamelab import runtime

    g = p.game
    require(role in ROLES and type(deadline_s) in (int, float)
            and math.isfinite(deadline_s) and 10 <= deadline_s <= 300, "invalid probe role/budget")
    deadline = time.monotonic() + deadline_s
    ctx = runtime.current()
    require(ctx is not None, "runtime slot probe requires authenticated pool context")
    family, peer_role, marker_value = ROLES[role]
    peer_slot = next(s for s in ctx.manifest["slots"] if s["slot_id"] != ctx.slot_id)
    ipc = Path(ctx.manifest["manifest_path"]).parent / "acceptance" / family
    # Both authenticated slots may create the two new IPC ancestors together.
    for attempt in range(4):
        try:
            runtime._dirs(ipc, create=True)
            break
        except FileExistsError:
            if attempt == 3:
                raise
    info = runtime.process_info(g.proc.pid)
    require(info is not None and runtime.is_registered_process(g.proc.pid, info[1]),
            "own game lacks live registered identity")
    live = g.verify_live()
    require(all(live.get(k) is True for k in ("image_in_gamelab", "known_folder_hooked",
            "swap_hooked", "in_job", "child_of_runner", "owned_job", "registered_slot")),
            "live slot isolation incomplete")
    identity = {"version": 1, "pool_id": ctx.pool_id, "slot_id": ctx.slot_id,
                "role": role, "run_id": g.results.name, "results": str(g.results),
                "game_pid": g.proc.pid, "game_created": info[0], "game_image": info[1]}
    rows, captures, errors = [], [], []
    original = None
    restored = False

    def cmd(verb, *args):
        return g.gl_cmd(verb, *args, timeout=min(10, remaining(deadline, time.monotonic())))

    def state():
        value = cmd("state")
        require(value.get("ok") is True and value.get("phase") == "town"
                and (value.get("player") or {}).get("spawned") is True, "not a live Town fixture")
        return value

    def menu(opened):
        current = state()
        if opened:
            require(cmd("menu", "character").get("ok") is True, "menu open refused")
        if not opened:
            for _ in range(3):
                if not state().get("window"):
                    break
                g.key("escape")
                time.sleep(.15)
        require(bool(state().get("window")) == opened, "menu state did not settle")

    def observe(phase, opened=False, capture=False):
        tag = f"{ctx.pool_id}:{ctx.slot_id}:{role}:{phase}"
        cv = cmd("cvars", MARKER_CVAR)
        s = state()
        frame = cmd("qa_poseframe", tag)
        row = {"phase_name": phase, "at_monotonic": time.monotonic(),
               "marker_value": cv.get("cvars", {}).get(MARKER_CVAR), "tag": frame.get("tag"),
               "tag_ok": frame.get("ok") is True, "native_frame": frame.get("frame"),
               "native_player": frame.get("player"), "phase": s.get("phase"),
               "spawned": (s.get("player") or {}).get("spawned"),
               "window": s.get("window"), "menu_open": bool(s.get("window"))}
        require(assess_observation(row, marker_value, opened, tag), "state/cvar/tag/UI cross-routing predicate failed")
        if capture:
            # Deliberately identical names across workers, distinct owned result roots.
            shot = g.shot("slot-shared-" + phase)
            require(shot is not None and shot.is_file(), "owned capture missing")
            captures.append(str(shot))
            row["capture"] = str(shot)
        rows.append(row)
        g.note("runtime_slot_probe", **identity, observation=row)
        return row

    def announce(phase, observation):
        payload = dict(identity, phase=phase, observation=observation)
        publish(ipc / (role + "." + phase + ".json"), payload, runtime)

    def peer(phase):
        path = ipc / (peer_role + "." + phase + ".json")
        def read():
            if not path.exists():
                return None
            value = validate_peer(runtime._read(path), identity, peer_slot, peer_role, phase)
            want_menu = ((phase == "one" and peer_role == "a")
                         or (phase == "three" and peer_role == "b"))
            peer_tag = f"{ctx.pool_id}:{peer_slot['slot_id']}:{peer_role}:{phase}"
            require(assess_observation(value.get("observation"), ROLES[peer_role][2],
                                       want_menu, peer_tag), "sibling observation cross-routed")
            seen = runtime.process_info(value["game_pid"])
            require(seen is not None and seen[0] == value["game_created"]
                    and os.path.normcase(seen[1]) == os.path.normcase(value["game_image"])
                    and runtime.is_registered_process(value["game_pid"], seen[1]),
                    "sibling identity absent/reused/unregistered at barrier")
            return value
        return wait_until(read, deadline, g.pump)

    try:
        original = cmd("cvars", MARKER_CVAR).get("cvars", {}).get(MARKER_CVAR)
        require(type(original) in (int, float) and math.isfinite(original), "original FPS marker unavailable")
        ack = cmd("setvar", MARKER_CVAR, marker_value)
        readback = cmd("cvars", MARKER_CVAR)
        require(assess_marker_write(ack, readback, marker_value), "marker write acknowledgement/readback mismatch")
        menu(False)
        announce("ready", observe("ready"))
        sibling = peer("ready")
        if family == "routing":
            for phase, opened in [("one", role == "a"), ("two", False),
                                  ("three", role == "b"), ("four", False)]:
                if phase in ("two", "four"):
                    # Only the worker whose menu was open receives a posted escape.
                    if (phase == "two" and role == "a") or (phase == "four" and role == "b"):
                        g.key("escape")
                        time.sleep(.15)
                else:
                    menu(opened)
                announce(phase, observe(phase, opened, capture=True))
                peer(phase)
        elif role == "timeout":
            announce("armed", observe("armed"))
            # Expected outer TIMEOUT terminates this owned worker; never a successful bot return.
            while True:
                observe("timeout-wait")
                time.sleep(min(2, remaining(deadline, time.monotonic())))
        else:
            sibling = peer("armed")
            polls = 0
            while True:
                remaining(deadline, time.monotonic())
                seen = runtime.process_info(sibling["game_pid"])
                observe("survivor-wait-" + str(polls), capture=(polls % 10 == 0))
                polls += 1
                if old_process_gone(seen, sibling["game_created"]):
                    break
                require(os.path.normcase(seen[1]) == os.path.normcase(sibling["game_image"]),
                        "same birth changed executable")
                time.sleep(min(2, remaining(deadline, time.monotonic())))
            # Continue own actual input/readback/capture after the sibling's OLD identity disappeared.
            menu(True)
            observe("after-peer-menu", True, True)
            g.key("escape")
            time.sleep(.15)
            observe("after-peer-escape", False, True)
            observe("after-peer-final", False, True)
    except Exception as exc:
        errors.append(type(exc).__name__ + ": " + str(exc))
    finally:
        if original is not None and g.alive():
            try:
                # A separate bounded cleanup allowance never turns a failed probe into PASS.
                deadline = max(deadline, time.monotonic() + 10)
                menu(False)
                ack = cmd("setvar", MARKER_CVAR, original)
                readback = cmd("cvars", MARKER_CVAR)
                restored = assess_marker_write(ack, readback, original)
                require(restored, "FPS marker restore acknowledgement/readback mismatch")
            except Exception as exc:
                errors.append("cleanup: " + type(exc).__name__ + ": " + str(exc))
    return {"ok": not errors and restored and role != "timeout", "role": role,
            "identity": identity, "live_isolation": live, "rows": rows, "captures": captures,
            "errors": errors, "marker_cvar": MARKER_CVAR, "marker_value": marker_value,
            "original_marker": original, "restored_marker": restored, "movement_proven": False,
            "visual_content_reviewed": False, "account_isolation_proven": False}
