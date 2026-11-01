"""floor_runner: the first Pilot bot. MECHANICS.md section 1, the gameplay loop's
"Next floor" step: from wherever it stands on a mission floor, reach the floor's exit and
take it, fighting what attacks it on the way.

Combat verb: kite (the intake's default). Reflexes (engine-side, no round trip): a potion
below 50% hp, and fire at the nearest enemy within 160 while travelling. One gl round trip
took 1.7 s in which a swarm took 140 hp off an unsteered player (pilot-crosslevel
20261017-161022), so reacting from Python alone is too slow.
Terminal telemetry event: "bot_terminal" in gl.jsonl, with terminal = "next_floor" when
the next floor's place differs from this one; "died", "no_route", "stuck" or "budget" otherwise.
"""
import math
import time

BREAK_RADIUS = 250     # breakables this close to where the route was lost are tried


def run(p, budget_s=300, kite_range=90, potion_below=50, fire_radius=160, to_place=None,
        combat_before_travel=False):
    """to_place: travel there through the travel graph (path_to(level), no_route when the
    graph does not know the transition); None takes the nearest exit, as an exploration run does."""
    if combat_before_travel:
        return _run_combat_before_travel(p, budget_s, kite_range, potion_below, fire_radius, to_place)
    t0 = time.time()
    p.reflex(potion=potion_below, fire=fire_radius)
    start = p.scan(400)
    spawn = p.status()
    out = {"start_place": start.get("place"), "exits_seen": start.get("exitCount"),
           "fights": 0, "exit_attempts": 0}

    def finish(terminal, **kw):
        if terminal != "next_floor":      # the level load reset the engine's counter
            out["reflex_potions"] = p.status().get("reflexPotions")
        out.update(kw, terminal=terminal, seconds=round(time.time() - t0, 1))
        p.game.note("bot_terminal", bot="floor_runner", **{k: v for k, v in out.items() if k != "intents"})
        return out

    failed_breaks = set()

    def break_near():
        """A Breakable (debris pile) is static collision with no nav-block opt-out: it closes
        the passage until smashed (floor-soak 20261017-192513: a debris pile 160 units from
        where every route ended, four 20 s kites later still cut). Attack the nearest few."""
        broke = []
        found = [b for b in p.cmd("breakables", BREAK_RADIUS, timeout=15).get("breakables", [])
                 if b.get("unit") not in failed_breaks]
        # debris first: crates and chairs sit in rooms and rarely close a passage, and the ones
        # tried in floor-soak 20261017-193859 were mostly unreachable (12 s each)
        found.sort(key=lambda b: ("debris" not in b.get("name", ""), b.get("d", 0)))
        for b in found[:3]:
            a = p.attack(b["unit"], until=["dead"], timeout=8)
            if a.result != "done":
                failed_breaks.add(b.get("unit"))
            broke.append([b.get("name", "").rsplit("/", 1)[-1], round(b.get("d", 0)), a.result, a.reason])
        return broke

    def same_spot(spots):
        last = spots[-3:]
        return len(last) == 3 and all(abs(a[0] - last[0][0]) + abs(a[1] - last[0][1]) < 64 for a in last)

    while time.time() - t0 < budget_s:
        out["exit_attempts"] += 1
        if to_place:
            r = p.travel(to_place, until=["hp_below:30", "dead"], timeout=120)
        else:
            r = p.exit(until=["hp_below:30", "dead"], timeout=120)
        if r.ok:
            to = r.event.get("place_to")
            if to and to != "?" and to != out["start_place"]:
                return finish("next_floor", place_to=to, learned=r.event.get("learned"), new_edge=r.event.get("new_edge"))
            return finish("arrived_unknown", place_to=to)
        if r.result == "no_route" and r.intent == "travel":
            return finish("no_route", reason=r.reason)      # the graph has no such transition
        if r.result == "no_route":
            # no route from the spawn itself is final; mid-floor (the planner's graph changed
            # under it: floor-soak 20261017-183722 sample 2 routed from the spawn, then lost
            # the exit 1200 units on) the bot clears what is close and tries again from where
            # it stands
            moved = ((r.event.get("x", spawn.get("x", 0)) - spawn.get("x", 0)) ** 2
                     + (r.event.get("y", spawn.get("y", 0)) - spawn.get("y", 0)) ** 2) ** 0.5
            if out["exit_attempts"] == 1 and not out["fights"] and moved < 48 and "wedge" not in r.reason:
                return finish("no_route", reason=r.reason)
            if "x" in spawn and len(out.setdefault("probes", [])) < 2:
                # measurement: is the exit still reachable from the spawn (the graph changed)
                # and is the spawn reachable from here (this spot is cut off)?
                out["probes"].append(p.cmd("exitprobe", int(spawn["x"]), int(spawn["y"]), timeout=60))
            at = [round(r.event.get("x", 0)), round(r.event.get("y", 0))]
            broke = break_near()
            if any(x[2] == "done" for x in broke):
                out.setdefault("retries", []).append({"at": at, "broke": broke, "t": round(time.time() - t0, 1)})
                if out["exit_attempts"] >= 6:
                    return finish("no_route", reason=r.reason)
                continue
            out["fights"] += 1
            k = p.kite("nearest", kite_range, until=["dead"], timeout=20)
            retry = {"at": at, "kite": k.result, "kite_reason": k.reason, "t": round(time.time() - t0, 1)}
            if broke:
                retry["broke"] = broke
            if len(out.setdefault("retries", [])) == 0:
                # measurement: what stands between here and the exit's stand point (static
                # collision blocks nav by default); walkable/raycastFree per 16 units
                acc = getattr(p, "last_exit_accept", {}) or {}
                if "ax" in acc:
                    b = p.cmd("bodies", int(acc["ax"]), int(acc["ay"]), timeout=15)
                    retry["bodies"] = {k: b.get(k) for k in ("walkable", "raycastFree", "bodyCount", "truncated")}
                    retry["bodies"]["list"] = [[u.get("name"), round(u.get("x", 0)), round(u.get("y", 0)), u.get("actor")]
                                               for u in b.get("bodies", [])]
                # and the engine's own nav overlay over the cut, for the eye
                for line in ("e_cheats 1", "r_draw_nav_data 1"):
                    p.game.console(line)
                time.sleep(0.3)
                p.game.shot(f"cut-nav-{at[0]}_{at[1]}")     # one per cut: soak samples share a run
                for line in ("r_draw_nav_data 0", "e_cheats 0"):
                    p.game.console(line)
            out["retries"].append(retry)
            if "within" in (k.reason or "") or "no live target" in (k.reason or ""):
                # nothing within reach: an idle pack standing in a passage cuts the engine's
                # graph (floor-soak 20261017-191104: beetles in the only passage east, the
                # nav overlay orange around them, the route lost 700 units short of them).
                # Go and fight the nearest enemy further out, by unit id
                far = sorted(p.scan(700).get("enemies", []), key=lambda e: e.get("dist", 1e9))
                retry["far_enemies"] = len(far)
                if far:
                    k2 = p.kite(far[0]["unit"], kite_range, until=["dead"], timeout=40)
                    retry["far_kite"] = [far[0].get("name"), round(far[0].get("dist", 0)), k2.result, k2.reason]
                else:
                    time.sleep(5)   # nothing to fight anywhere near: give the graph time, re-plan
            if out["exit_attempts"] >= 6:
                return finish("no_route", reason=r.reason)
            if same_spot([x["at"] for x in out["retries"]]):
                # three retries from one spot changed nothing (floor-soak 20261017-192513
                # sample 0: four 20 s kites at -125,971, then no_route anyway)
                return finish("no_route", reason=r.reason + " (no progress in 3 retries)")
            continue
        if r.reason == "dead" or p.state().get("player", {}).get("dead"):
            return finish("died")
        if r.reason.startswith("hp_below"):
            # low and the reflex potion did not hold it: back off and fight what follows
            out["fights"] += 1
            p.kite("nearest", kite_range, until=["dead"], timeout=30)
            continue
        # stuck or out of time on the way: smash breakables, clear what is close, try again
        stuck = out.setdefault("stuck", [])
        entry = {"at": [round(r.event.get("x", 0)), round(r.event.get("y", 0))], "reason": r.reason,
                 "t": round(time.time() - t0, 1)}
        stuck.append(entry)
        entry["broke"] = break_near()
        if any(x[2] == "done" for x in entry["broke"]):
            continue
        out["fights"] += 1
        k = p.kite("nearest", kite_range, until=["dead"], timeout=45)
        entry["kite"] = [k.result, k.reason]
        if k.reason == "level_changed":
            return finish("level_changed_in_fight")
        if same_spot([x["at"] for x in stuck]):
            # three stops in one spot with nothing to break or fight (pilot-floor
            # 20261017-193337: 33 exit/kite cycles stuck at 909,-2170 until the budget ran out)
            return finish("stuck", reason=r.reason + " (no progress in 3 retries)")
    return finish("budget")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _player_observation(reply):
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        return "UNRUN", "native state refused or malformed"
    player = reply.get("player")
    if not isinstance(player, dict) or type(player.get("dead")) is not bool:
        return "UNRUN", "native player/dead readback missing"
    if player["dead"]:
        return "dead", "native player dead"
    if (reply.get("phase") != "mission" or player.get("spawned") is not True
            or not all(_finite(player.get(k)) for k in ("hp", "hpMax", "x", "y"))
            or player["hpMax"] <= 0 or player["hp"] <= 0):
        return "UNRUN", "live mission player readback incomplete"
    return "live", ""


def _nearby_enemies(reply):
    """Validate scan180; its native enemy list caps at32 without a truncation flag."""
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        return None, "native enemy scan refused or malformed"
    rows = reply.get("enemies")
    count = reply.get("enemyCount")
    if (reply.get("truncated", False) not in (False, 0) or not isinstance(rows, list)
            or type(count) is not int or count != len(rows) or count >= 32
            or not isinstance(reply.get("place"), str) or not reply["place"]):
        return None, "enemy scan incomplete, capped or truncated"
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or type(row.get("unit")) is not int or not row["unit"]
                or row["unit"] in seen or not all(_finite(row.get(k)) for k in ("x", "y", "dist", "hp"))
                or row["dist"] < 0 or not 0 < row["hp"] <= 1):
            return None, "enemy row malformed, duplicate or nonfinite"
        seen.add(row["unit"])
    return sorted((row for row in rows if row["dist"] <= 180), key=lambda row: row["dist"]), ""


def _intent_observation(result):
    return {key: getattr(result, key, None) for key in ("intent", "id", "result", "reason", "tick", "event")}


def _run_combat_before_travel(p, budget_s, kite_range, potion_below, fire_radius, to_place):
    """Opt-in ordinary strategy. No new abilities, resources or native steering."""
    if not _finite(budget_s) or budget_s <= 0:
        raise ValueError("floor budget must be finite and positive")
    t0 = time.monotonic()
    deadline = t0 + budget_s
    out = {"strategy": "combat_before_travel", "start_place": None, "exits_seen": None,
           "fights": 0, "exit_attempts": 0, "observations": [], "combat": [], "routes": []}

    def finish(terminal, **extra):
        out.update(extra, terminal=terminal, seconds=round(time.monotonic() - t0, 1))
        p.game.note("bot_terminal", bot="floor_runner", **out)
        return out

    while time.monotonic() < deadline:
        state = p.state()
        status, reason = _player_observation(state)
        out["observations"].append({"kind": "state", "status": status, "reason": reason, "raw": state})
        if status == "dead":
            return finish("died")
        if status == "UNRUN":
            return finish("observation_failed", reason=reason)
        if "reflex_configuration" not in out:
            reply = p.reflex(potion=potion_below, fire=fire_radius)
            out["reflex_configuration"] = reply
            if not isinstance(reply, dict) or reply.get("ok") is not True:
                return finish("observation_failed", reason="native reflex configuration refused")
        scan = p.scan(180)
        enemies, reason = _nearby_enemies(scan)
        out["observations"].append({"kind": "enemy_scan", "status": "UNRUN" if enemies is None else "OBSERVED",
                                    "reason": reason, "raw": scan})
        if enemies is None:
            return finish("observation_failed", reason=reason)
        if out["start_place"] is None:
            out.update(start_place=scan["place"], exits_seen=scan.get("exitCount"))
        elif scan["place"] != out["start_place"]:
            return finish("level_changed_in_fight", place_to=scan["place"])
        remaining = deadline - time.monotonic()
        if remaining < 1:
            return finish("budget")
        if enemies:
            if out["fights"] >= 6:
                return finish("combat_limit", reason="six bounded combat episodes completed")
            target = enemies[0]
            out["fights"] += 1
            result = p.kite(target["unit"], kite_range, until=["dead", "target_dead"], timeout=min(20, remaining))
            out["combat"].append({"target": target, "state_before": state, "result": _intent_observation(result)})
            if result.reason == "dead":
                return finish("died")  # Do not issue another scan/exit after a native death result.
            if not ((result.result == "interrupted" and result.reason == "target_dead")
                    or (result.result == "done" and result.reason == "target dead")):
                return finish("combat_failed", reason=result.reason)
            continue  # Fresh native state/scan precedes another episode or route.
        if out["exit_attempts"] >= 6:
            return finish("route_limit", reason="six bounded route attempts exhausted")
        out["exit_attempts"] += 1
        until = ["dead", "under_attack", "hp_below:30"]
        action = p.travel if to_place else p.exit
        args = (to_place,) if to_place else ()
        result = action(*args, until=until, timeout=min(120, remaining))
        out["routes"].append(_intent_observation(result))
        if result.reason == "dead":
            return finish("died")
        if result.ok:
            event = result.event if isinstance(result.event, dict) else {}
            to = event.get("place_to")
            if isinstance(to, str) and to and to != "?" and to != out["start_place"]:
                return finish("next_floor", place_to=to, learned=result.event.get("learned"), new_edge=result.event.get("new_edge"))
            return finish("arrived_unknown", place_to=to)
        if result.reason == "under_attack" or result.reason.startswith("hp_below"):
            continue  # Observe actual nearby targets; never invent an aggro/LOS state.
        return finish("route_failed", reason=result.reason)
    return finish("budget")
