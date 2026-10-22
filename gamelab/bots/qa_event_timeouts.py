"""Controlled no-reward timeout checks; not ordinary-play evidence.

The event uses its real spawn/use/update path. Live enemies are held by native stun;
the scene clock is accelerated only to measure the documented two/three-minute
timeout. Actual unit disappearance, living pack members and absence of new loot
are asserted together. There are no repeated attempts after a failed setup.
"""
import time

from gamelab.bots.plan_classesa import BRUTE
from gamelab.bots.qa_classes import Checks


STUN = "tweak/buffs/status_effects.sval:stun_greater"
KINDS = {
    "strongbox": {"filter": "doodads/hwp/strongbox.unit", "ms": 180000,
                  "placed": "placed a strongbox", "started": "armed:",
                  "expired": "pack still alive after 3 min", "reward": "pack cleared; the box opens",
                  "settings": {"enabled": 0, "chance": 0, "pack": 1,
                               "pack_per_player": 0, "elite_chance": 0}},
    "abyss": {"filter": "doodads/hwp/abyss_crack.unit", "ms": 120000,
              "placed": "placed a crack", "started": "wave 1/",
              "expired": "still alive after 2 min", "reward": "[HWP:abyss] payout",
              "settings": {"enabled": 0, "chance": 0, "waves": 3,
                           "wave_base": 1, "wave_per_player": 0, "trigger": 130}},
}


def run(pilot, kind, **_):
    if kind not in KINDS:
        raise ValueError("unknown event kind")
    c, cfg = Checks(pilot), KINDS[kind]
    records = {}

    def units(filt, radius=600):
        result = c.gl("near", radius, filt)
        if result.get("truncated"):
            raise RuntimeError("capped event readback cannot prove the expectation")
        return result.get("units") or []

    def command_once(line, expected, seconds=5):
        mark = len(c.g.read_log())
        c.g.console("hwp " + line)
        end = time.monotonic() + seconds
        while expected not in c.g.read_log()[mark:] and time.monotonic() < end:
            time.sleep(0.1)
        return c.g.read_log()[mark:]

    for name, value in cfg["settings"].items():
        c.hwp(f"set {kind}.{name} {value}", 0.1)
    start = c.gl("mission", "bandit_keep", 0)
    ready = start.get("ok") and c.wait_phase("mission", 120)
    c.flag("mission_ready", ready, str(start))
    if not ready:
        return {**c.out, "notes": c.notes, "records": records}
    time.sleep(3)
    c.god_on()
    c.gl("timescale", 1)
    c.gl("cull")
    # The actual debug anchors are fixed world offsets: strongbox +48x,
    # abyss +60y. Verify that anchor's 32px square, the sample brute at96px,
    # and their connected player lane; an all-around128px empty square is
    # unnecessary. Navigation is bounded ordinary walking, never teleport.
    anchor = (48, 0, 16) if kind == "strongbox" else (0, 60, 16)
    lane, note = c.to_trident_lane(front=96, back_neighbor=True, ray_distance=96,
                                   tag=kind + "_timeout", clearance_points=(anchor,))
    opened = bool(lane)
    c.flag("open_floor", opened, note)
    c.flag("disabled_no_natural_event", not units(cfg["filter"]),
           "disabled event must not place itself before its explicit test spawn")
    if not opened or not c.out["disabled_no_natural_event"]:
        return {**c.out, "notes": c.notes, "records": records}
    direction, _ = lane
    spawn = c.gl("multi", "spawn", BRUTE, round(direction[0] * 96), round(direction[1] * 96),
                 "+", "buffnear", 400, "bandit_brute", STUN, 1000000)
    time.sleep(0.25)
    sample = [u for u in units("bandit_brute") if not u.get("dead") and u.get("hp", 0) > 0]
    c.flag("live_sample", bool(sample), str(sample))
    records.update(spawn_reply=spawn, sample=sample, player=c.gl("state").get("player"))
    if not sample:
        return {**c.out, "notes": c.notes, "records": records}
    clock0 = c.gl("clock")
    log0 = len(c.g.read_log())
    placed = command_once(kind + " here", cfg["placed"])
    time.sleep(0.5)
    event = units(cfg["filter"])
    c.flag("one_event", cfg["placed"] in placed and len(event) == 1, str(event))
    if len(event) != 1:
        return {**c.out, "notes": c.notes, "records": records}
    if kind == "strongbox":
        records["use_reply"] = c.gl("use", "strongbox")
    deadline = time.monotonic() + 5
    while cfg["started"] not in c.g.read_log()[log0:] and time.monotonic() < deadline:
        time.sleep(0.1)
    c.gl("buffnear", 600, "bandit_brute", STUN, 1000000)
    pack = [u for u in units("bandit_brute") if not u.get("dead") and u.get("hp", 0) > 0]
    sample_ids = {u["unit"] for u in sample}
    pack_ids = {u["unit"] for u in pack}
    started = cfg["started"] in c.g.read_log()[log0:] and bool(pack_ids - sample_ids)
    c.flag("event_started_with_live_pack", started, str(pack))
    records.update(event_before=event, pack_before=pack, clock_before=clock0,
                   status=c.hwp(kind, 0.1))
    if not started:
        return {**c.out, "notes": c.notes, "records": records}
    loot0 = units("items/", 800)
    scale = c.gl("timescale", 16)
    c.flag("timescale_readback", scale.get("timescale") == 16, str(scale))
    samples = []
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            remaining, clock = units(cfg["filter"]), c.gl("clock")
            samples.append({"event": remaining, "clock": clock})
            if not remaining:
                break
            time.sleep(0.25)
    finally:
        c.gl("timescale", 1)
    clock1 = c.gl("clock")
    after = units(cfg["filter"])
    live_after = [u for u in units("bandit_brute") if not u.get("dead") and u.get("hp", 0) > 0]
    loot1 = units("items/", 800)
    new_loot = [u for u in loot1 if u["unit"] not in {v["unit"] for v in loot0}]
    elapsed = clock1.get("sceneMs", -1) - clock0.get("sceneMs", -1)
    log = c.g.read_log()[log0:]
    c.flag("event_expired", not after and cfg["expired"] in log, log[-2500:])
    c.flag("real_timeout_elapsed", elapsed >= cfg["ms"], f"actual scene elapsed {elapsed} ms")
    c.flag("pack_still_alive", pack_ids <= {u["unit"] for u in live_after}, str(live_after))
    c.flag("no_reward", not new_loot and cfg["reward"] not in log,
           f"new loot {new_loot}; payout log present {cfg['reward'] in log}")
    c.g.shot(kind + "-expired")
    records.update(clock_after=clock1, event_after=after, pack_after=live_after,
                   loot_before=loot0, loot_after=loot1, new_loot=new_loot,
                   clock_event_samples=samples, expected_timeout_ms=cfg["ms"])
    return {**c.out, "notes": c.notes, "records": records}
