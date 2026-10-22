"""Controlled natural-input cases for Firearms qualities absent from the rank suites.

Resource setters are confined to setup. Measured reloads spend real pistol rounds;
all short timing guards use the native scene clock and matching input_done IDs.
These cleared-floor measurements are separate from ordinary-run evidence.
"""
import math
import time

from gamelab.bots.qa_firearms_passives import Checks as Base
from gamelab.bots.plan_firearms import SKILLS, BLOCKERS


def rider_counter_oracle(samples, kind, expect):
    """Forward counter/factor model, with one native-frame phase uncertainty.

    The observer reads after native actor updates; projectile application may be
    on either side of that actor's update within the sampled frame. Never infer
    an application from observed damage or fit a duration to the output.
    """
    if len(samples) < 2:
        return {"valid": False, "reason": "incomplete trace"}
    valid = all(x.get("valid") and x.get("list_valid") and x.get("matches") in (0, 1)
                and x.get("hpMax") == 10000000 and x.get("actor_tick_rate") == 0 for x in samples)
    active = [x for x in samples if x.get("buff_on")]
    frames = max((x.get("dt", 0) for x in samples), default=0)
    # The known native fixture has tick-rate0. A coarse observer frame cannot
    # establish a strict1000ms addition; fail that measurement guard explicitly.
    valid = valid and 0 < frames <= 66 and samples[0].get("buff_on") is False
    factors, counters, additions, expiries = [], [], [], []
    anchor = None
    for index, row in enumerate(samples):
        on = row.get("buff_on", False)
        pool, hp_max = row.get("icePool", -1), row.get("hpMax", -1)
        ice_move = (1 - min(row["iceSlowMax"], (pool / hp_max) ** row["iceSlowPow"])) if pool >= 0 and hp_max > 0 else None
        expected_move = ice_move * (.6 if on and kind == "slow" else 1) if ice_move is not None else None
        expected_miss = .4 if on and kind == "blind" else 0
        factor_ok = (expected_move is not None and abs(row.get("moveMul", -1) - expected_move) < .00001
                     and abs(row.get("missAttack", -1) - expected_miss) < .00001
                     and abs(row.get("missSpell", -1)) < .00001)
        factors.append(factor_ok)
        if on:
            counters.append(row.get("duration") == 1000 and row.get("matches") == 1
                            and 0 < row.get("left", -1) <= 3000
                            and abs(row.get("intensity", -1) - 1) < .00001)
        if index == 0:
            continue
        previous = samples[index - 1]
        elapsed = row["now"] - previous["now"]
        phase = frames
        if on and not previous.get("buff_on"):
            additions.append({"kind": "onset", "valid": 1000 - phase <= row["left"] <= 1000,
                              "left": row["left"], "now": row["now"]})
            anchor = row
        elif on and previous.get("buff_on"):
            # Anchor to the last application rather than the previous frame.
            # A wrong decay rate must accumulate error and fail this model.
            without_hit = max(0, anchor["left"] - (row["now"] - anchor["now"])) if anchor else -1
            if row["left"] > without_hit + phase:
                expected = min(3000, without_hit + 1000)
                additions.append({"kind": "stack", "valid": abs(row["left"] - expected) <= phase,
                                  "expected": expected, "actual": row["left"], "phase": phase, "now": row["now"]})
                anchor = row
            else:
                counters.append(abs(row["left"] - without_hit) <= phase)
        elif previous.get("buff_on"):
            remaining = anchor["left"] - (row["now"] - anchor["now"]) if anchor else 1e9
            expiries.append({"valid": abs(remaining) <= phase,
                             "last_positive": previous, "first_absent": row})
            anchor = None
    stack_adds = [x for x in additions if x["kind"] == "stack"]
    max_left = max((x["left"] for x in active), default=0)
    if expect:
        behavior = (bool(active) and len(stack_adds) >= 2 and all(x["valid"] for x in additions)
                    and all(counters) and 3000 - frames <= max_left <= 3000
                    and bool(expiries) and all(x["valid"] for x in expiries)
                    and samples[-1].get("buff_on") is False)
    else:
        behavior = not active
    return {"valid": valid and all(factors) and behavior, "native_target_valid": valid,
            "all_native_factors": all(factors), "factor_checks": factors,
            "counter_checks": counters, "applications": additions, "expiries": expiries,
            "maximum_left": max_left, "native_max_frame_ms": frames,
            "scope": "Controlled deterministic actual elemental gun hits;1000ms additions,3000ms cap, native factors and counter expiry."}


class Checks(Base):
    def collect_trace(self, event, tag, timeout):
        first = self.g.wait_gl(lambda e: e.get("ev") == event and e.get("tag") == tag,
                               timeout=timeout) or {}
        count = first.get("parts", 0)
        if not isinstance(count, int) or not 1 <= count <= 64:
            return {"valid": False, "parts": [first], "samples": []}
        parts = []
        for index in range(count):
            part = (first if first.get("part") == index else
                    self.g.wait_gl(lambda e: e.get("ev") == event and e.get("tag") == tag
                                   and e.get("part") == index, timeout=3) or {})
            parts.append(part)
        samples = [row for part in parts for row in part.get("samples", part.get("events", []))]
        valid = (all(p.get("parts") == count and p.get("part") == i
                     and p.get("dropped") == 0 and p.get("truncated") is False
                     and p.get("start") == first.get("start") and p.get("end") == first.get("end")
                     for i, p in enumerate(parts))
                 and len(samples) == first.get("stored") and bool(samples))
        complete = {}
        if event == "actorbuffobserve":
            # This observer stores every native frame plus its initial sample.
            # buffobserve above stores only semantic transitions and therefore
            # intentionally does not share this per-frame contract.
            complete = {
                "all_headers_consistent": all(all(p.get(k) == first.get(k) for k in
                    ("stored", "seen", "frames", "ms", "unit", "buff")) for p in parts),
                "every_native_frame_retained": first.get("stored") == first.get("seen")
                    == first.get("frames", -2) + 1,
                "initial_and_final": bool(samples) and samples[0].get("elapsed") == 0
                    and samples[0].get("dt") == 0 and samples[0].get("now") == first.get("start")
                    and samples[-1].get("elapsed") == first.get("ms")
                    and samples[-1].get("now") == first.get("end")
                    and samples[-1].get("final") is True
                    and all(x.get("final") is False for x in samples[:-1]),
                "sample_identity": all(x.get("unit") == first.get("unit") for x in samples),
                "native_frame_continuity": all(
                    isinstance(b.get("dt"), int) and b["dt"] > 0
                    and b.get("elapsed", -1) - a.get("elapsed", -1) == b["dt"]
                    and 0 <= b.get("now", -1) - a.get("now", -1) <= b["dt"] + 1
                    for a, b in zip(samples, samples[1:])),
            }
            valid = valid and all(complete.values())
        return {"valid": valid, "parts": parts, "samples": samples, "completeness": complete}

    def native_snapshot(self, final_input=None):
        commands = [("skills",), ("state",), ("givestacks", self.CLIP, 0),
                    ("givestacks", self.STACKS + "reloading", 0),
                    ("givestacks", self.STACKS + "reload_cast", 0), ("skillbar",)]
        if final_input is not None:
            commands.append(("input", 1, 0, 0, final_input[0], final_input[1], final_input[2]))
        raw = self.g.gl_multi(commands)
        parents = {x.get("id", "").rsplit(".", 1)[0] for x in raw}
        return {"valid": len(raw) == len(commands) and all(x.get("ok") for x in raw)
                and len(parents) == 1 and "" not in parents and not raw[0].get("truncated"),
                "now": raw[0].get("now", -1), "skills": raw[0], "state": raw[1],
                "clip": raw[2].get("stacks", -1), "reloading": raw[3].get("stacks", -1),
                "reload_cast": raw[4].get("stacks", -1), "bar": raw[5], "raw": raw,
                "input": raw[-1] if final_input is not None else None}

    def input_done(self, reply):
        return self.g.wait_gl(lambda e: e.get("ev") == "input_done"
                              and e.get("id") == reply.get("id"), timeout=3) or {}

    def press(self, d, button, ms=1):
        reply = self.gl("input", ms, 0, 0, d[0], d[1], button)
        done = self.input_done(reply)
        return {"reply": reply, "done": done,
                "valid": reply.get("ok") and done.get("id") == reply.get("id")
                and done.get("frames", 0) >= 1}

    @staticmethod
    def dash_lanes(terrain, ox=0, oy=0):
        """Fine raster guides only; native body paths and rays decide acceptance."""
        rows, n, step = terrain["rows"], terrain["size"], terrain["step"]
        mid, lanes = n // 2, []
        for angle in range(0, 360, 45):
            d = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
            # Conservative full body envelope along BOTH110px travel segments.
            good = True
            for forward in range(-112, 113, 4):
                for lateral in range(-12, 13, 4):
                    ix = mid + round((ox + d[0]*forward - d[1]*lateral)/step)
                    iy = mid + round((oy + d[1]*forward + d[0]*lateral)/step)
                    if not (0 <= ix < n and 0 <= iy < n and rows[iy][ix] != "#"):
                        good = False
                        break
                if not good:
                    break
            if good:
                lanes.append((d, (-d[1], d[0])))
        return lanes

    @staticmethod
    def dash_probe(c, terrain, origin, d):
        commands, goals = [], []
        for sign in (-1, 1):
            x, y = origin[0] + sign*110*d[0], origin[1] + sign*110*d[1]
            goals.append((x, y))
            commands.append(["pathfind", x, y, 12])
            for side in (-6, 0, 6):
                sx, sy = origin[0] - side*d[1], origin[1] + side*d[0]
                commands.append(["rayhit", sx, sy, x-side*d[1], y+side*d[0]])
        replies = c.g.gl_multi(commands)
        routes, rays = replies[::4], [r for i, r in enumerate(replies) if i % 4]
        # Match tough()/clear_dir's independent near-target line requirement.
        nearby = c.gl("near", 66)
        blockers = [u for u in nearby.get("units", [])
                    if u.get("behavior") in BLOCKERS and "target_dummy" not in u.get("name", "")
                    and 6 < (u["x"]-origin[0])*d[0] + (u["y"]-origin[1])*d[1] < 52
                    and abs((u["x"]-origin[0])*d[1] - (u["y"]-origin[1])*d[0]) < 12]
        actual = c.pos()
        clear = (nearby.get("ok") is True and not nearby.get("truncated") and not blockers
                 and len(replies) == 8 and len(routes) == 2 and len(rays) == 6
                 and all(r.get("ok") is True and r.get("wall") is False
                         and r.get("tile") is False for r in rays)
                 and all(r.get("ok") is True and not r.get("truncated") and r.get("nodes", 0) > 0
                         and r.get("length", 1e9) <= 137.5
                         and math.dist(origin, (r.get("fx", 1e9), r.get("fy", 1e9))) <= 1
                         and math.dist(goal, (r.get("lastX", 1e9), r.get("lastY", 1e9))) <= 12
                         for r, goal in zip(routes, goals))
                 and math.dist(origin, actual) <= 1)
        return {"clear": bool(clear), "direction": d, "rays": rays, "routes": routes,
                "actual_start": origin, "player_after": actual, "nearby": nearby, "near_target_blockers": blockers}

    def local_dash_line(self):
        """Normally walk to, then certify, the unchanged bidirectional110px corridor."""
        from gamelab.bots.qa_specs_navigation import _walk
        self._dash_navigation_count = getattr(self, "_dash_navigation_count", 0) + 1
        tag = "missing_orbs_dash_" + str(self._dash_navigation_count)
        origin, direction, _, geometry = _walk(
            self, self.dash_lanes, tag, 110, 6,
            {"bidirectional_length": 110, "native_body_diameter": 12,
             "native_parallel_ray_offsets": [-6, 0, 6], "max_path_length": 137.5,
             "endpoint_tolerance": 12, "fine_step": 8, "coarse_step": 16},
            extra_probe=self.dash_probe)
        self.check("missing_orbs_local_dash_corridor", direction is not None,
                   {"actual_start": origin, "direction": direction, "geometry": geometry,
                    "scope": "ordinary native Pathfind/Pilot.path_to; fresh fine body envelope plus unchanged both110px native paths and six rays; no teleport"})
        return direction

    def real_rounds(self, d, count):
        """Fixed number of actual solo-pistol presses; never retry a failed shot."""
        rows = []
        for _ in range(count):
            before = self.clip()
            fired = self.press(d, "main", 60)
            time.sleep(.4)
            after = self.clip()
            rows.append({"before": before, "after": after, "input": fired})
        return {"valid": len(rows) == count and all(r["input"]["valid"]
                 and r["after"] == r["before"] - 1 for r in rows), "rows": rows}

    def dash_refusal_window(self, d, started_before=None):
        before = self.native_snapshot((d[0], d[1], "dash"))
        done = self.input_done(before["input"])
        after = self.native_snapshot()
        dash0 = self.entry(before["skills"], "dash_skill")
        elapsed = after["now"] - before["now"]
        p0, p1 = before["state"].get("player", {}), after["state"].get("player", {})
        moved = math.dist((p0.get("x", 1e9), p0.get("y", 1e9)),
                          (p1.get("x", -1e9), p1.get("y", -1e9)))
        origin = started_before if started_before is not None else before["now"]
        return {"before": before, "after": after, "done": done, "elapsed": elapsed,
                "since_origin": after["now"] - origin, "actual_displacement": moved,
                "valid": before["valid"] and after["valid"] and dash0.get("button") == "dash"
                # Native ActiveSkill subtracts dt while positive without a
                # clamp, so a ready Charge can have a negative residual CD.
                and isinstance(dash0.get("cd"), (int, float)) and dash0["cd"] <= 0
                and moved >= 8 and done.get("frames") == 1
                and done.get("id") == before["input"].get("id") and 0 <= elapsed}

    def manual_dodge(self, d, skip):
        self.ready("dash_skill")
        self.ready("hwp_fs_reload")
        self.top_up()
        spent = self.real_rounds(d, 3)
        partial = self.clip()
        marker = self.log_pos()
        reload_input = self.press(d, self.entry(self.bar(), "hwp_fs_reload").get("button"))
        result = self.dash_refusal_window(d)
        before, after = result["before"], result["after"]
        cd = self.entry(before["skills"], "hwp_fs_reload").get("cd", -1)
        log = self.log_from(marker)
        guards = (spent["valid"] and partial == 7 and reload_input["valid"] and result["valid"]
                  and before["clip"] == partial and before["reload_cast"] == 1 and before["reloading"] == 0
                  and 0 < result["elapsed"] < cd and "reload: dodge at " in log)
        expected = 10 if skip else partial
        self.check("dodge_skip_manual_" + ("with_orb" if skip else "control"),
                   guards and after["clip"] == expected and after["reload_cast"] == 0
                   and self.entry(after["skills"], "hwp_fs_reload").get("cd") == 0
                   and ("finishes it" if skip else "cancels it") in log,
                   {"orb": "hwp_fs_reload_dodge", "quality": "rare", "rank": int(skip),
                    "spent": spent, "partial": partial, "reload_input": reload_input,
                    "guarded_dash": result, "initial_remaining_ms": cd, "expected_clip": expected, "log": log})

    def automatic_dodge(self, d, skip):
        self.ready("dash_skill")
        self.top_up()
        spent = self.real_rounds(d, 9)
        origin = self.native_snapshot((d[0], d[1], "main"))
        last_done = self.input_done(origin["input"])
        result = self.dash_refusal_window(d, origin["now"])
        before, after = result["before"], result["after"]
        # Rank1's authored reload timer is2000ms. Requiring a result before even
        # the unmodified1600ms default additionally excludes natural completion.
        guards = (spent["valid"] and origin["valid"] and origin["clip"] == 1
                  and last_done.get("frames") == 1 and result["valid"]
                  and before["clip"] == 0 and before["reloading"] == 1
                  and 0 < result["since_origin"] < 1600)
        self.check("dodge_skip_automatic_" + ("with_orb" if skip else "control"),
                   guards and after["clip"] == (10 if skip else 0)
                   and after["reloading"] == (0 if skip else 1),
                   {"orb": "hwp_fs_reload_dodge", "quality": "rare", "rank": int(skip),
                    "first_nine_real_rounds": spent, "before_final_round": origin,
                    "final_round_done": last_done, "guarded_dash": result})
        time.sleep(2.2)
        final = self.native_snapshot()
        self.check("dodge_skip_automatic_eventual_full_" + str(int(skip)),
                   final["valid"] and final["clip"] == 10 and final["reloading"] == 0,
                   {"snapshot": final})

    def dodge(self):
        if not self.prepare("QADodgeSkip"):
            return
        ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        self.check("dodge_skip_solo_fixture", ok and self.clip_max() == 10,
                   {"gear": gear, "reload_rank": self.current_rank("hwp_fs_reload")})
        if not ok:
            return
        d = self.local_dash_line()
        if d is None:
            return
        # Normal walking returns between trials; each start re-certifies its own
        # live corridor because an actual dodge changed the player's position.
        for skip in (False, True):
            if skip:
                learned, rank = self.orb("hwp_fs_reload_dodge", 1)
                self.check("dodge_skip_rare_acquired", learned and rank == 1,
                           {"orb": "hwp_fs_reload_dodge", "quality": "rare", "rank": rank})
            for kind in ("manual", "automatic"):
                start = self.pos()
                d = self.local_dash_line()
                if d is None:
                    return
                getattr(self, kind + "_dodge")(d, skip)
                self.p.path_to(*start, tol=4, timeout=15)
        self.ready("dash_skill")
        self.top_up()
        d = self.local_dash_line()
        if d is None:
            return
        spent = self.real_rounds(d, 3)
        result = self.dash_refusal_window(d)
        self.check("dodge_skip_no_refill_when_not_reloading", spent["valid"] and result["valid"]
                   and result["before"]["clip"] == 7 and result["before"]["reloading"] == 0
                   and result["before"]["reload_cast"] == 0 and result["after"]["clip"] == 7,
                   {"spent": spent, "guarded_dash": result})
        self.to_town()

    def rocket_bank_ready(self, tag, target):
        """Wait for this built class's natural rank1 Hoarder bank; never give a charge."""
        tip = self.gl("skilltip", "hwp_fs_hoarder")
        samples, deadline = [], time.monotonic() + 12
        valid = False
        for attempt in range(24):
            if time.monotonic() >= deadline:
                break
            key = tag + "-bank-ready-" + str(attempt)
            started = self.gl("buffobserve", key, 100, "-", self.STACKS + "rocket_charges", target)
            trace = self.collect_trace("buffobserve", key, timeout=3)
            raw = self.gl("skills")
            shown = self.stacks("rocket_charges_shown")  # existing zero-delta native counter read
            rows = trace["samples"]
            bank = rows[-1].get("stacks") if rows else None
            cooldown = self.entry(raw, "hwp_fs_rpg").get("cd")
            valid = (tip.get("ok") and tip.get("level") == 1 and started.get("ok") and trace["valid"]
                     and raw.get("ok") and not raw.get("truncated") and bank == 1 and shown == 2
                     and isinstance(cooldown, (int, float)) and cooldown <= 0
                     and all(x.get("player_valid") and x.get("target_valid") for x in rows))
            samples.append({"trace": trace, "skills": raw, "bank": bank, "shown": shown})
            if valid:
                break
        return {"valid": bool(valid), "rank_readback": tip, "expected_rank": 1, "expected_cap": 1,
                "cap_source": "demo_hoarder.sval rank1 hoard-max1/1 + stacks_firearms.sval base max0",
                "samples": samples, "policy": "Natural banking only; no positive or negative bank setter. General cap/rate coverage remains the separate Hoarder rank suite."}

    def rocket_trial(self, d, tag, near, expect_jump):
        self.ready("hwp_fs_rpg")
        self.ready("dash_skill")
        dd, dummy = self.tough(d, 36 if near else 132)
        if near and math.dist(dd, d) > .01:
            self.check(tag + "_certified_direction", False,
                       {"certified_direction": d, "actual_target_direction": dd})
            return
        self.top_up()
        bank_fixture = self.rocket_bank_ready(tag, dummy)
        self.check(tag + "_natural_hoarder_bank_fixture", bank_fixture["valid"], bank_fixture)
        if not bank_fixture["valid"]:
            self.clear_dummies()
            return
        before = self.native_snapshot()
        clip0, hp0 = before["clip"], self.hps([dummy]).get(dummy)
        marker = self.log_pos()
        sent = []
        def fire():
            sent.extend(self.g.gl_multi([
                ("buffobserve", tag, 2500, "players/hwp/firearms/buffs_firearms.sval:rocket_jump", self.STACKS + "rocket_charges", dummy),
                ("input", 700, 0, 0, dd[0], dd[1], self.entry(self.bar(), "hwp_fs_rpg").get("button")),
            ]))
        watch = self.cast_watch("hwp_fs_rpg", fire, secs=1.6)
        done = self.input_done(sent[-1])
        trace = self.collect_trace("buffobserve", tag, timeout=5)
        after = self.native_snapshot()
        hp1, log = self.hps([dummy]).get(dummy), self.log_from(marker)
        p0, p1 = before["state"].get("player", {}), after["state"].get("player", {})
        delta = (p1.get("x", 1e9) - p0.get("x", -1e9), p1.get("y", 1e9) - p0.get("y", -1e9))
        backwards = -(delta[0] * dd[0] + delta[1] * dd[1])
        side = abs(delta[0] * dd[1] - delta[1] * dd[0])
        active = [x for x in trace["samples"] if x.get("buff_on")]
        inactive = [x for x in trace["samples"] if not x.get("buff_on")]
        onset = next((x for x in active), None)
        expiry = next((x for x in trace["samples"] if onset is not None
                       and x.get("now", -1) > onset["now"] and not x.get("buff_on")), None)
        buff_ok = (bool(active) and all(x.get("buff_dur") == 500 and 0 < x.get("buff_left", -1) <= 500
                                     for x in active)
                   and any(abs(x.get("evade", -1) - 1) < .0001 for x in active)
                   and expiry is not None and onset is not None
                   and abs((expiry["now"] - onset["now"]) - onset["buff_left"]) <= 66
                   and inactive[-1].get("buff_on") is False)
        self.cost_flag(tag, "hwp_fs_rpg", SKILLS / "demo_rpg.sval", watch)
        bank_rows = trace["samples"]
        bank_changes = [(a.get("stacks"), b.get("stacks")) for a, b in zip(bank_rows, bank_rows[1:])
                        if a.get("stacks") != b.get("stacks")]
        native_cd = self.entry(after["skills"], "hwp_fs_rpg").get("cd")
        bank_reset = (bank_fixture["valid"] and bool(bank_rows) and bank_rows[0].get("stacks") == 1
                      and bank_rows[-1].get("stacks") == 0 and bank_changes == [(1, 0)]
                      and all(x.get("stacks") in (0, 1) for x in bank_rows) and native_cd == 0)
        basic = (before["valid"] and after["valid"] and len(sent) == 2 and all(x.get("ok") for x in sent)
                 and trace["valid"] and all(x.get("target_valid") and x.get("player_valid") for x in trace["samples"])
                 and isinstance(hp0, (int, float)) and isinstance(hp1, (int, float)) and hp1 < hp0
                 and after["clip"] == clip0 and p1.get("hp", -1) >= p0.get("hp", 1) - .001
                 and self.out.get(tag + "_cost") and bank_reset
                 and done.get("id") == sent[-1].get("id") and done.get("frames", 0) > 0)
        observed = (buff_ok and backwards >= 70 and side <= 12 and "rocket jump:" in log) if expect_jump else (
            not active and math.hypot(*delta) <= 2 and "rocket jump:" not in log)
        self.check(tag, basic and observed,
                   {"orb": "hwp_fs_rpg_jump", "quality": "rare", "near_blast": near,
                    "expect_jump": expect_jump, "target": dummy, "hp": [hp0, hp1], "before": before,
                    "after": after, "delta": delta, "backwards": backwards, "lateral": side,
                    "watch": watch, "observer": trace, "log": log, "input_done": done,
                    "natural_bank_fixture": bank_fixture, "native_bank_changes": bank_changes,
                    "native_cooldown_after": native_cd, "bank_consumed_and_reset": bool(bank_reset),
                    "scope": "Real rocket impact, owner displacement/HP, native500ms100%evade buff, cost/CLIP and exact natural Hoarder1-to0 consumption/native cooldown reset0. Dash-charge economy is separately unverified."})
        self.clear_dummies()
        returned = self.p.path_to(p0.get("x"), p0.get("y"), tol=4, timeout=20)
        self.check(tag + "_normal_walk_return", returned.ok and math.dist(self.pos(), (p0["x"], p0["y"])) <= 6,
                   {"intent": str(returned), "actual": self.pos(), "goal": [p0["x"], p0["y"]]})

    def jump(self):
        if not self.prepare("QARocketJump", "hwp_firearms_demolitions"):
            return
        self.learn_rank("hwp_fs_rpg", 1)
        d = self.local_dash_line()
        if d is None:
            return
        self.rocket_trial(d, "rocket_jump_without_orb_near", True, False)
        ok, rank = self.orb("hwp_fs_rpg_jump", 1)
        self.check("rocket_jump_rare_acquired", ok and rank == 1,
                   {"orb": "hwp_fs_rpg_jump", "quality": "rare", "rank": rank})
        d = self.local_dash_line()
        if d is None:
            return
        self.rocket_trial(d, "rocket_jump_with_orb_near", True, True)
        self.rocket_trial(d, "rocket_jump_with_orb_far", False, False)
        self.orb_off("hwp_fs_rpg_jump")
        d = self.local_dash_line()
        if d is not None:
            self.rocket_trial(d, "rocket_jump_removed_orb_near", True, False)
        self.to_town()

    def rider_trial(self, kind, expect, tag):
        element = "poison" if kind == "blind" else "ice"
        desired_index = 3 if kind == "blind" else 1
        fixture = "gamelab/qa_firearms_rider_fixture.sval:only_" + element
        # critprobe needs a real live Actor even for its caster-stat fields.
        # Spawn the actual trial target first; never interpret a failed reply's defaults.
        d = self.open_dirs(110)[0]
        dd, target = self.tough(d, 80)
        targets = self.gl("near", 400, "target_dummy")
        live = [u for u in targets.get("units", []) if not u.get("dead")]
        applied = self.gl("givebuff", fixture, 30000)
        time.sleep(.7)
        probe = self.probe(rolls=1)
        chance = self.custom(probe, "hwp-ele-chance")
        weights = [1 + self.custom(probe, "hwp-ele-" + name)
                   for name in ("fire", "ice", "lightning", "poison")]
        desired_weights = [float(i == desired_index) for i in range(4)]
        required_custom = ["hwp-ele-chance"] + ["hwp-ele-" + name for name in ("fire", "ice", "lightning", "poison")]
        custom_rows = probe.get("custom", [])
        # Native custom stats are sparse: an absent desired-element bonus is
        # the source-defined zero. Chance and the three injected -1 weights
        # must actually be present; never default fields from a failed probe.
        mandatory = [key for key in required_custom if key != "hwp-ele-" + element]
        valid_custom = (all(sum(r.get("id") == key for r in custom_rows) == 1 for key in mandatory)
                        and all(sum(r.get("id") == key for r in custom_rows) <= 1 for key in required_custom)
                        and all(isinstance(r.get("value"), (int, float)) and not isinstance(r.get("value"), bool)
                                and math.isfinite(r["value"]) for r in custom_rows if r.get("id") in required_custom))
        valid_target = (targets.get("ok") is True and not targets.get("truncated") and len(live) == 1
                        and live[0].get("unit") == target and live[0].get("hpMax") == 10000000
                        and live[0].get("hpExact") == 10000000)
        fixture_ok = (probe.get("ok") is True and valid_custom and valid_target
                      and applied.get("ok") and applied.get("applied")
                      and abs(chance - 1) < .00001 and all(abs(a-b) < .00001 for a,b in zip(weights, desired_weights)))
        self.check(tag + "_controlled_caster", fixture_ok,
                   {"fixture": fixture, "application": applied, "native_chance": chance,
                    "native_weights": weights, "expected_weights": desired_weights, "native_probe": probe,
                    "native_custom_complete": valid_custom, "native_target_valid": valid_target, "targets": targets})
        if not fixture_ok:
            self.clear_dummies()
            return
        self.top_up()
        self.hwp("firearms elements reset", .2, until="elements: reset")
        buff = "players/hwp/firearms/buffs_firearms.sval:ele_" + kind
        sent = self.g.gl_multi([
            ("actorbuffobserve", tag, 8000, target, buff),
            ("input", 4000, 0, 0, dd[0], dd[1], "main"),
        ])
        # The real hold lasts4000ms, beyond input_done's3s immediate wait.
        # Collect the complete8s native trace first; the exact matching native
        # completion is then already retained. No input, trace, or guard changes.
        trace = self.collect_trace("actorbuffobserve", tag, timeout=12)
        done = self.input_done(sent[-1])
        fired = self.fired()
        counts = {name: value for name, value in fired.items() if value > 0}
        samples = trace["samples"]
        predicted = rider_counter_oracle(samples, kind, expect)
        self.check(tag, all(x.get("ok") for x in sent) and done.get("id") == sent[-1].get("id")
                   and done.get("frames", 0) > 1 and trace["valid"] and predicted["valid"]
                   and counts.get(element, 0) >= 8 and len(counts) == 1
                   and samples[-1].get("hpExact", -1) < samples[0].get("hpExact", -1),
                   {"orb": "hwp_fs_scavenger_" + kind, "quality": "uncommon", "expect_rider": expect,
                    "target": target, "real_element_shots": fired, "input_done": done,
                    "observer": trace, "forward_model": predicted,
                    "scope": "Caster-only fixture isolates native projectile/rider mechanics. Natural unmodified proc-frequency and orb acquisition in ordinary runs remain separate."})
        self.clear_dummies()

    def rider(self, kind):
        if not self.prepare("QARider" + kind.title()):
            return
        gear_ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        level = self.learn_rank("hwp_fs_scavenger", 5)
        self.check(kind + "_solo_fixture", gear_ok and level == 5 and self.clip_max() == 10,
                   {"gear": gear, "scavenger_rank": level})
        if not gear_ok or level != 5:
            return
        self.rider_trial(kind, False, kind + "_without_orb")
        ok, rank = self.orb("hwp_fs_scavenger_" + kind, 1)
        self.check(kind + "_uncommon_acquired", ok and rank == 1,
                   {"orb": "hwp_fs_scavenger_" + kind, "quality": "uncommon", "rank": rank})
        self.rider_trial(kind, True, kind + "_with_orb")
        self.orb_off("hwp_fs_scavenger_" + kind)
        self.rider_trial(kind, False, kind + "_removed_orb")
        self.to_town()

    def blind(self):
        self.rider("blind")

    def slow(self):
        self.rider("slow")


def run(p, family="dodge", **_):
    c = Checks(p)
    try:
        getattr(c, family)()
    except Exception as exc:
        c.check("missing_orbs_" + family + "_crashed", False, {"error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows),
                 rows=c.rows, notes=c.notes, terminal=" | ".join(c.notes)[-4000:])
    return c.out
