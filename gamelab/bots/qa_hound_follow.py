"""Ordinary hound-follow measurement beyond its live return threshold.

Used by the original classA bot. No summon orders, teleports, freezes or state
writes: the only actions are bounded player walking and native-frame tracking.
"""
import math
import time

from gamelab.bots.plan_classesa import DIRS, dist


def observe(c, uid, filt):
    config = c.gl("summonmove", uid)
    threshold = config.get("runBackDistance", 0)
    roaming = config.get("roamingDistance", 0)
    detail = {"initial_movement": config, "navigation": []}
    c.out["hound_follow_details"] = detail
    if not config.get("follower") or not 0 < threshold <= 500 or roaming <= 0:
        return False, "setup: no bounded native follower configuration: " + str(config)
    need = threshold + 180
    selected = None
    for attempt in range(6):
        px, py = c.me()
        choices = []
        for direction in DIRS:
            ray = c.gl("rayhit", px, py, px + direction[0] * need, py + direction[1] * need)
            clear = need
            if ray.get("wall"):
                clear = min(clear, ray.get("wd", 0))
            if ray.get("tile"):
                clear = min(clear, ray.get("td", 0))
            choices.append({"direction": direction, "clear": clear, "ray": ray})
        choices.sort(key=lambda row: -row["clear"])
        detail["navigation"].append({"player": (px, py), "choices": choices})
        if choices and choices[0]["clear"] >= need:
            selected = choices[0]
            break
        if not choices or choices[0]["clear"] < 96:
            break
        # A finite setup search follows the clearest connected lane; every move
        # is retained even if no sufficient final lane can be reached.
        direction = choices[0]["direction"]
        ms = int(min(64, choices[0]["clear"] - 32) / 115 * 1000)
        before = c.me()
        c.gl("input", ms, direction[0], direction[1])
        time.sleep(ms / 1000 + 0.3)
        detail["navigation"][-1]["walk"] = {"before": before, "after": c.me(), "ms": ms}
    if selected is None:
        return False, "setup: no long unobstructed ordinary-walking lane; " + str(detail)
    detail["before_walk"] = c.gl("summonmove", uid)
    direction = selected["direction"]
    hold = int((threshold + 150) / 115 * 1000)
    event, action = c.track(10000, 1000, filt,
                            lambda: c.gl("input", hold, direction[0], direction[1]))
    final = c.gl("summonmove", uid)
    records = [row for row in (event or {}).get("tracks", []) if row.get("unit") == uid]
    track = records[0] if len(records) == 1 else {}
    player_walked = dist(((event or {}).get("px0", 0), (event or {}).get("py0", 0)),
                         ((event or {}).get("px1", 0), (event or {}).get("py1", 0)))
    moved = dist((track.get("x0", 0), track.get("y0", 0)), (track.get("x1", 0), track.get("y1", 0)))
    crossed = track.get("dmax", 0) > threshold
    closed = track.get("dmax", 0) - track.get("dminafter", 0) > 40 and track.get("dlast", 9999) < 100
    # The native producer's teleport leash is350. Reject a measurement near it
    # rather than credit an automatic teleport as actual return movement.
    no_teleport_risk = track.get("dmax", 9999) < 335
    ok = (bool(event) and (event or {}).get("truncated") == 0 and player_walked > threshold + 30
          and moved > 20 and crossed and closed and no_teleport_risk and final.get("follower"))
    detail.update(selected_lane=selected, hold_ms=hold, action=action, native_track=event,
                  final_movement=final, player_walked=player_walked, summon_moved=moved,
                  crossed_live_return_threshold=crossed, gap_closed=closed, no_teleport_risk=no_teleport_risk)
    return bool(ok), (f"native run-back {threshold:.0f}px, idle tolerance {roaming:.0f}px; "
                      f"player walked {player_walked:.1f}, summon moved {moved:.1f}, "
                      f"max gap {track.get('dmax')}, closest after {track.get('dminafter')}, "
                      f"final gap {track.get('dlast')}; full native position evidence in hound_follow_details")
