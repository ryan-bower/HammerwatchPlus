"""Class-specific ordinary Pilot policy, without changing the shared/native Pilot.

Native Pilot attack approaches22px and fires within28.6px. Kite fires from
180px even when range24 is requested, strafes, and dashes away at close range;
that ranged policy is unsuitable for dagger/trident compatibility fixtures.

Source: keep/level_exit_part_open.pfb and closed.pfb: LevelExitNext at
(64,-112), connected UseTrigger at(64,-40), sensor at(0,-24). The node is
an editor execution node, not the place to stand. Require its rigid transform
to match an actual native sensor before walking; never execute its script.
"""
import math
import time
from dataclasses import asdict
from gamelab.pilot import Result


def keep_exit_geometry(scan, nearby, areas):
    exits = sorted((e for e in scan.get("exits", []) if e.get("enabled")
                    and e.get("type") == "LevelExitNext"), key=lambda e: e.get("dist", 1e30))
    if not exits:
        return None, "no plain native Keep exit"
    node = exits[0]
    if (not nearby.get("ok") or nearby.get("truncated")
            or not areas.get("ok") or areas.get("truncated") or areas.get("unit") != node.get("unit")):
        return None, "native trigger/sensor readback incomplete or identifies another exit"
    matches = []
    for usable in nearby.get("units", []):
        if "UseTrigger" not in usable.get("name", ""):
            continue
        dx, dy = usable["x"] - node["x"], usable["y"] - node["y"]
        if abs(math.hypot(dx, dy) - 72) > .5:
            continue
        # Rotation derived from observed node->UseTrigger, whose local vector is(0,72).
        cosine, sine = dy / 72, -dx / 72
        sx = node["x"] - 64 * cosine - 88 * sine
        sy = node["y"] - 64 * sine + 88 * cosine
        sensors = [s for s in areas.get("sensors", []) if s.get("name", "").startswith(":Physics")
                   and math.hypot(s.get("x", 1e30) - sx, s.get("y", 1e30) - sy) <= .5]
        if len(sensors) == 1:
            matches.append({"node": node, "usable": usable, "sensor": sensors[0],
                            "rotation": {"cos": cosine, "sin": sine},
                            "predicted_sensor": {"x": sx, "y": sy}})
    return (matches[0], "validated native prefab transform") if len(matches) == 1 else (
        None, f"native Keep exit transform/sensor is missing or ambiguous ({len(matches)} matches)")


class ClassPilot:
    def __init__(self, pilot, cls):
        self.pilot = pilot
        self.melee = cls.startswith("hwp_thief") or cls.startswith("hwp_gladiator")
        self.keep_objectives = {}

    def __getattr__(self, name):
        return getattr(self.pilot, name)

    def reflex(self, potion=None, fire=None):
        if self.melee and fire not in (None, 0, "off"):
            fire = min(float(fire), 28)
        return self.pilot.reflex(potion=potion, fire=fire)

    def kite(self, unit="nearest", rng=70, **kwargs):
        if self.melee:
            return self.pilot.attack(unit, **kwargs)
        return self.pilot.kite(unit, rng, **kwargs)

    def keep_objective(self, place, deadline, **kwargs):
        """Walk into the real chair's native area, fight its actual encounter.

        Keep3/4/5 set should_spawn_bandit_boss. Native level_exit.pfb raises
        spawn_bandit_boss and chooses the closed exit. The chair prefab then
        enables a radius100 circle at the armchair's exact world origin; an
        ordinary player enter changes the spawn scene and spawns the2500HP
        encounter2340ms later. Only its real OnDeath raises unlock_exit.
        """
        if place not in {"bandit_keep/keep_3", "bandit_keep/keep_4", "bandit_keep/keep_5"}:
            return None
        memo = self.keep_objectives.setdefault(place, {"place": place, "samples": [], "attempts": 0})
        if memo.get("combat_ended"):
            return None  # exit still independently requires actual top usable/CanUse
        memo["attempts"] += 1
        if memo["attempts"] > 6:
            return Result("failed", "native Keep objective exhausted six ordinary attempts", "exit", event=memo)
        left = lambda: deadline - time.monotonic()
        interrupts = list(kwargs.get("until") or [])
        if "dead" not in interrupts:
            interrupts.append("dead")
        def observe():
            near = self.pilot.cmd("near", 12000, "actors/bosses/boss_bandit/boss_bandit_encounter.unit")
            state = self.pilot.state()
            row = {"stage": "native_encounter", "near": near, "state": state}
            memo["samples"].append(row)
            self.pilot.game.note("class_keep_objective", **row)
            if not near.get("ok") or near.get("truncated"):
                return None, state, "incomplete native encounter readback"
            actors = near.get("units", [])
            if len(actors) > 1 or any(a.get("hpMax") != 2500 for a in actors):
                return None, state, "ambiguous or unexpected native encounter actor"
            live = [a for a in actors if a.get("dead") is False and a.get("hpExact", 0) > 0]
            return (live[0] if live else None), state, None
        boss, state, error = observe()
        if error:
            return Result("failed", error, "exit", event=memo)
        if state.get("player", {}).get("dead"):
            return Result("interrupted", "dead", "exit", event=memo)
        if boss is None and not memo.get("seen_unit"):
            chair = self.pilot.cmd("near", 12000, "actors/bosses/boss_bandit/bandit_armchair.unit")
            circles = self.pilot.cmd("near", 12000, ":Physics_Circle")
            chairs = chair.get("units", [])
            sensors = [s for s in circles.get("units", []) if len(chairs) == 1
                       and math.dist((s.get("x", 1e9), s.get("y", 1e9)),
                                     (chairs[0].get("x", -1e9), chairs[0].get("y", -1e9))) <= .5]
            geometry = {"chair_readback": chair, "circle_readback": circles,
                        "same_origin_sensors": sensors, "native_trigger_radius": 100}
            memo["geometry"] = geometry
            self.pilot.game.note("class_keep_objective", stage="chair_geometry", **geometry)
            if (not chair.get("ok") or chair.get("truncated") or len(chairs) != 1
                    or not circles.get("ok") or circles.get("truncated") or len(sensors) != 1):
                return Result("failed", "native chair/same-origin trigger circle missing or ambiguous", "exit", event=memo)
            if left() <= 4:
                return Result("timeout", "native Keep objective has no approach budget", "exit", event=memo)
            armchair = chairs[0]
            # Real stand points are75px from the chair origin, inside the
            # source100px enter area and outside its small solid collider.
            # A path to the chair's solid origin can be correctly refused.
            # Native Pathfind must certify a real stand point strictly inside
            # its100px trigger; the approach tolerance never replaces a route.
            walk_interrupts = interrupts + (["under_attack"] if "under_attack" not in interrupts else [])
            within = False
            for leg in range(12):
                if left() <= 2:
                    return Result("timeout","native Keep chair travel/combat budget exhausted","exit",event=memo)
                at = self.pilot.state()
                player = at.get("player", {})
                if player.get("dead"):
                    return Result("interrupted","dead","exit",event=memo)
                px, py = player.get("x"), player.get("y")
                inside_before = (isinstance(px,(int,float)) and isinstance(py,(int,float))
                                 and math.dist((px,py),(armchair["x"],armchair["y"])) <= 80)
                points = [(armchair["x"]+75*math.cos(a*math.pi/4),
                           armchair["y"]+75*math.sin(a*math.pi/4)) for a in range(8)]
                routes = self.pilot.game.gl_multi([["pathfind", x, y, 12] for x,y in points]) if not inside_before else []
                reachable = [(point, route) for point,route in zip(points,routes)
                             if route.get("ok") is True and route.get("nodes",0)>0
                             and math.dist(point,(route.get("lastX",1e9),route.get("lastY",1e9))) <= 12]
                memo.setdefault("approach_route_queries",[]).append({"leg":leg,"at":at,
                    "routes":[{"goal":point,"native_path":route} for point,route in zip(points,routes)]})
                if inside_before:
                    walk = Result("done", "already inside source native circle", "path_to")
                elif len(routes) != len(points) or not reachable:
                    return Result("failed", "no complete native route to a stand point inside chair enter circle", "exit", event=memo)
                else:
                    goal, route = min(reachable, key=lambda pair: pair[1].get("length",1e30))
                    # Native Pilot under_attack compares currentHP to previous
                    # native-frame HP (Pilot.as713), so combat starts on the
                    # first actual hit instead of after the former30% threshold.
                    if left()<=1:
                        return Result("timeout","native route query exhausted chair travel budget","exit",event=memo)
                    walk = self.pilot.path_to(*goal, tol=4, timeout=min(35, left()), until=walk_interrupts)
                at = self.pilot.state()
                player = at.get("player", {})
                within = (isinstance(player.get("x"),(int,float)) and isinstance(player.get("y"),(int,float))
                          and math.dist((player["x"],player["y"]),(armchair["x"],armchair["y"])) <= 100)
                row = {"stage":"ordinary_chair_approach","leg":leg,"intent":asdict(walk),"state":at,
                       "actual_inside_native_radius":within}
                memo["samples"].append(row); self.pilot.game.note("class_keep_objective",**row)
                if player.get("dead"):
                    return Result("interrupted","dead","exit",event=memo)
                if within:
                    break
                if walk.reason == "under_attack":
                    foes = self.pilot.scan(700)
                    live = sorted((a for a in foes.get("enemies",[]) if not a.get("dead") and a.get("hp",1)>0),
                                  key=lambda a:a.get("dist",1e30))
                    foe = live[0] if live else None
                    if left()<=1:
                        return Result("timeout","native enemy readback exhausted travel combat budget","exit",event=memo)
                    native = self.kite(foe["unit"] if foe else "nearest",90,
                                       until=["dead","target_dead"],timeout=min(14,left()))
                    after = self.pilot.state()
                    remaining = self.pilot.scan(400) if not after.get("player",{}).get("dead") else {}
                    combat = {"stage":"ordinary_travel_combat","leg":leg,"before":at,"target":foe,
                              "native_scan_before":foes,"intent":asdict(native),"after":after,
                              "native_scan_after":remaining}
                    memo["samples"].append(combat); self.pilot.game.note("class_keep_objective",**combat)
                    if after.get("player",{}).get("dead"):
                        return Result("interrupted","dead","exit",event=memo)
                    if left()<=1:
                        return Result("timeout","ordinary native travel combat exhausted budget","exit",event=memo)
                    continue
                if walk.reason.startswith("hp_below"):
                    return walk
                return Result("failed","ordinary chair approach did not enter native area: "+walk.reason,
                              "exit",event={**walk.event,"objective":memo})
            if not within:
                return Result("failed","twelve bounded ordinary chair travel/combat legs did not reach native area","exit",event=memo)
            spawn_deadline = min(deadline, time.monotonic() + 7)
            while time.monotonic() < spawn_deadline and boss is None:
                boss, state, error = observe()
                if error or state.get("player", {}).get("dead"):
                    break
                if boss is None:
                    time.sleep(.15)
            if error:
                return Result("failed", error, "exit", event=memo)
            if state.get("player", {}).get("dead"):
                return Result("interrupted", "dead", "exit", event=memo)
            if boss is None:
                return Result("failed", "ordinary chair enter produced no live native encounter within7s", "exit", event=memo)
        while left() > 1:
            if boss is None:
                if memo.get("seen_unit"):
                    memo["combat_ended"] = True
                    memo["scope"] = "real native live encounter disappeared after ordinary attacks; exit CanUse remains independently required"
                    self.pilot.game.note("class_keep_objective", stage="native_combat_ended", objective=memo)
                    return None
                return Result("failed", "no observed native encounter", "exit", event=memo)
            if memo.get("seen_unit") not in (None, boss["unit"]):
                return Result("failed", "native encounter identity changed during ordinary combat", "exit", event=memo)
            memo.setdefault("seen_unit", boss["unit"])
            memo.setdefault("initial_hp", boss["hpExact"])
            memo["observed_hp_loss"] = memo.get("observed_hp_loss", False) or boss["hpExact"] < memo["initial_hp"]
            native = self.kite(boss["unit"], 90, until=interrupts + (["target_dead"] if "target_dead" not in interrupts else []),
                               timeout=min(20, left()))
            memo["samples"].append({"stage": "ordinary_encounter_combat", "before": boss, "intent": asdict(native)})
            boss, state, error = observe()
            if error:
                return Result("failed", error, "exit", event=memo)
            if state.get("player", {}).get("dead"):
                return Result("interrupted", "dead", "exit", event=memo)
            if native.reason.startswith("hp_below") and boss is not None:
                return native
        return Result("timeout", "ordinary native Keep encounter combat budget exhausted", "exit", event=memo)

    def exit(self, timeout=60, **kwargs):
        deadline = time.monotonic() + timeout
        scan = self.pilot.scan(2000)
        before = scan.get("place", "?")
        enabled = sorted((e for e in scan.get("exits", []) if e.get("enabled")), key=lambda e: e.get("dist", 1e30))
        plain = bool(enabled) and enabled[0].get("type") == "LevelExitNext"
        if not before.startswith("bandit_keep/keep_") or not plain:
            return self.pilot.exit(timeout=timeout, **kwargs)
        objective = self.keep_objective(before, deadline, **kwargs)
        if objective is not None:
            return objective
        if deadline - time.monotonic() <= 1:
            return Result("timeout", "ordinary objective left no native exit budget", "exit")
        scan = self.pilot.scan(2000)
        nodes = [e for e in scan.get("exits", []) if e.get("enabled") and e.get("type") == "LevelExitNext"]
        if not scan.get("ok") or not nodes:
            self.pilot.game.note("class_exit_adapter", stage="post_objective_exit_missing", scan=scan)
            return Result("no_route", "native exit readback missing after ordinary objective", "exit",
                          event={"x":scan.get("x"),"y":scan.get("y"),"scan":scan})
        search_radius = math.ceil(min(12000, max(math.hypot(e["x"] - scan["x"], e["y"] - scan["y"]) for e in nodes) + 80))
        nearby = self.pilot.cmd("near", search_radius, "UseTrigger")
        areas = self.pilot.cmd("exitareas", 128)
        geometry, reason = keep_exit_geometry(scan, nearby, areas)
        self.pilot.game.note("class_exit_adapter", stage="geometry", geometry=geometry, reason=reason,
                             native_near=nearby, native_areas=areas)
        if geometry is None:
            return Result("no_route", reason, "exit", event={"x": scan.get("x"), "y": scan.get("y")})
        sensor, usable, node = geometry["sensor"], geometry["usable"], geometry["node"]
        self.pilot.last_exit_accept = {"ax": sensor["x"], "ay": sensor["y"], "ux": node["x"], "uy": node["y"],
                                       "native_use_unit": usable["unit"]}
        left = lambda: max(1.0, deadline - time.monotonic())
        walking = self.pilot.path_to(sensor["x"], sensor["y"], tol=4, timeout=min(90, left()), **kwargs)
        self.pilot.game.note("class_exit_adapter", stage="walk", geometry=geometry, intent=asdict(walking))
        if not walking.ok:
            return walking
        current_usables = self.pilot.cmd("usables")
        native_top = [u for u in current_usables.get("usables", []) if u.get("top") is True
                      and u.get("canUse") is True and u.get("unit", {}).get("unit") == usable["unit"]]
        self.pilot.game.note("class_exit_adapter", stage="actual_area_usable", readback=current_usables)
        if len(native_top) != 1:
            return Result("failed", "walked to validated sensor but native matching exit is not the top usable", "exit")
        used = self.pilot.use(usable["unit"], timeout=min(20, left()), **kwargs)
        self.pilot.game.note("class_exit_adapter", stage="native_use", intent=asdict(used))
        if not used.ok and used.reason != "level_changed":
            return used
        after = self.pilot.arrived(min(90, left() + 10))
        state = self.pilot.state()
        valid = (after.startswith("bandit_keep/") and after != before
                 and state.get("phase") == "mission" and state.get("player", {}).get("dead") is False)
        self.pilot.game.note("class_exit_adapter", stage="arrival", place_from=before, place_to=after,
                             state=state, actual_transition=valid)
        return Result("done" if valid else "failed", "level_changed" if valid else "native use did not reach a new live Keep floor",
                      "exit", used.id, used.tick, {**used.event, "place_from": before, "place_to": after,
                                                "learned": False, "new_edge": False, "native_keep_geometry": geometry})

    def description(self):
        return {"melee": self.melee, "combat": "native attack" if self.melee else "native kite",
                "native_melee_approach": 22 if self.melee else None,
                "travel_fire_radius_cap": 28 if self.melee else 160,
                "source": "mods/gamelab-pilot/scripts/GameLab/Pilot.as:27,761-774,972-1049",
                "keep_exit": "validated native UseTrigger sensor; ordinary path/use only",
                "keep_objectives": "native chair area enter and actual2500HP encounter combat on keep3/4/5; no direct events/flags"}
