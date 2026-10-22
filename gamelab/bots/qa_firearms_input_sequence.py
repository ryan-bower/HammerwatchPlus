"""Native input-sequence protocol control, before any cancellation credit.

Controlled cleared floor, normal emulated movement and two actual pistol presses.
The controller must remain released across subsequent console RPCs. This does
not establish any ability cancellation, precise movement speed or ordinary run.
"""
import math
import time

from gamelab.bots.qa_firearms_missing_orbs import Checks as Base


def sequence_protocol(accepted, terminal, done, expected):
    errors, rows = [], terminal.get("steps", [])
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return {"valid": False, "errors": ["malformed native step list"], "steps": []}
    if (accepted.get("ok") is not True or terminal.get("ok") is not True
            or terminal.get("released") is not True or terminal.get("error") != ""
            or terminal.get("id") != accepted.get("id")
            or terminal.get("tag") != accepted.get("tag")
            or terminal.get("player") != accepted.get("player")
            or terminal.get("completed_steps") != len(expected)
            or terminal.get("requested_steps") != len(expected) or len(rows) != len(expected)):
        errors.append("incomplete/aborted/foreign native sequence or release")
    if len(done) != len(expected):
        errors.append("missing or duplicate per-step input_done")
    numeric_rows = True
    for index, (row, want) in enumerate(zip(rows, expected)):
        ms, buttons = want
        fields = ("actual_ms", "frames", "first_write", "last_write", "dt_min", "dt_max")
        numeric = all(isinstance(row.get(k), int) and not isinstance(row.get(k), bool) for k in fields)
        numeric_rows = numeric_rows and numeric
        match = [e for e in done if e.get("step") == index]
        event = match[0] if len(match) == 1 else {}
        if (not numeric or row.get("step") != index
                or row.get("id") != str(accepted.get("id")) + ":" + str(index)
                or row.get("requested_ms") != ms or row.get("buttons") != buttons
                or row.get("frames", 0) < 1 or not 0 < row.get("dt_min", 0) <= row.get("dt_max", 0) <= 100
                or not ms <= row.get("actual_ms", -1) < ms + row.get("dt_max", 0)
                or not row.get("frames", 0)*row.get("dt_min", 0) <= row.get("actual_ms", -1)
                       <= row.get("frames", 0)*row.get("dt_max", 0)
                or not (row.get("frames", 0)-1)*row.get("dt_min", 0)
                       <= row.get("last_write", -1)-row.get("first_write", 0)
                       <= (row.get("frames", 0)-1)*row.get("dt_max", 0)
                or event.get("sequence") != terminal.get("tag")
                or any(event.get(k) != row.get(k) for k in ("id", "frames", "first_write", "last_write", "actual_ms"))):
            errors.append("step%d native duration/identity/button/input_done mismatch" % index)
        if index and not 0 < row.get("first_write", 0) - rows[index-1].get("last_write", 0) <= 100:
            errors.append("step%d does not begin on the subsequent native frame" % index)
        if not all(isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool)
                   and math.isfinite(row[k]) for k in ("x_first", "y_first", "x_last", "y_last")):
            errors.append("step%d native position missing" % index)
    if rows and numeric_rows and (terminal.get("start") != rows[0].get("first_write")
                 or terminal.get("frames") != sum(x.get("frames", 0) for x in rows)
                 or terminal.get("total_ms") != sum(x.get("actual_ms", 0) for x in rows)
                 or not 2 <= terminal.get("end", 0) - rows[-1].get("last_write", 0) <= 200):
        errors.append("native aggregate/start/release-frame clock mismatch")
    return {"valid": not errors, "errors": errors, "steps": rows,
            "scope": "Exact native writes/input_done; per-step positions have one player-update phase uncertainty."}


def controller_idle(reply):
    # Input.as ApplyHeld165 subtracts dt without clamping msLeft; once<=0,
    # subsequent frames release and return. A negative expired TTL is idle
    # only with the independently observed empty/released stationary input.
    return (reply.get("ok") is True and type(reply.get("held")) is int and reply["held"] <= 0
            and reply.get("releasing") is False and reply.get("down") == []
            and all(type(reply.get(k)) in (int, float) and math.isfinite(reply[k])
                    and abs(reply[k]) < .0001 for k in ("mx", "my")))


class Checks(Base):
    @staticmethod
    def step(ms, move, aim, buttons="-"):
        return "/".join([str(ms), *(format(v, ".6f") for v in (*move, *aim)), buttons])

    def sequence(self, tag, steps, expected):
        accepted = self.gl("inputsequence", tag, *steps)
        terminal = (self.g.wait_gl(lambda e: e.get("ev") == "inputsequence"
                                  and e.get("tag") == tag, timeout=20) or {}) if accepted.get("ok") else {}
        done = [e for e in self.g.gl if e.get("ev") == "input_done" and e.get("sequence") == tag]
        protocol = sequence_protocol(accepted, terminal, done, expected)
        return {"accepted": accepted, "terminal": terminal, "input_done": done, "protocol": protocol}

    def released(self):
        first = self.g.gl_multi([["controller"], ["state"]])
        time.sleep(.2)
        second = self.g.gl_multi([["controller"], ["state"]])
        p0, p1 = first[1].get("player", {}), second[1].get("player", {})
        positions = all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k])
                        for p in (p0, p1) for k in ("x", "y"))
        stationary = positions and math.dist((p0["x"], p0["y"]), (p1["x"], p1["y"])) <= 1
        return {"valid": all(r.get("ok") for r in first+second) and controller_idle(first[0]) and controller_idle(second[0])
                and stationary, "first": first, "second": second, "stationary_after_release": bool(stationary)}

    def protocol_control(self):
        if not self.prepare("QAInputSeq"):
            return
        gear_ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        self.check("sequence_solo_fixture", gear_ok and self.clip_max() == 10, gear)
        if not gear_ok:
            return
        d = self.local_dash_line()
        if d is None:
            return
        start = self.pos()
        movement = self.sequence("fs-sequence-movement", [
            self.step(400, (.5*d[0], .5*d[1]), d), self.step(200, (0, 0), d),
            self.step(400, (-.5*d[0], -.5*d[1]), d)], [(400, []), (200, []), (400, [])])
        release = self.released()
        rows = movement["protocol"]["steps"]
        forward = backward = 0
        if len(rows) == 3:
            forward = ((rows[0].get("x_last", 0)-rows[0].get("x_first", 0))*d[0]
                       + (rows[0].get("y_last", 0)-rows[0].get("y_first", 0))*d[1])
            backward = -((rows[2].get("x_last", 0)-rows[2].get("x_first", 0))*d[0]
                         + (rows[2].get("y_last", 0)-rows[2].get("y_first", 0))*d[1])
        self.check("sequence_native_movement_and_return", movement["protocol"]["valid"]
                   and forward >= 8 and backward >= 8 and math.dist(start, self.pos()) <= 10,
                   {"start": start, "end": self.pos(), "direction": d, "forward": forward,
                    "backward": backward, "sequence": movement})
        self.check("sequence_movement_release_across_console", release["valid"], release)
        if not movement["protocol"]["valid"] or not release["valid"]:
            return
        dd, target = self.tough(d, 80)
        self.top_up()
        before = self.native_snapshot()
        observed = self.gl("buffobserve", "fs-sequence-shots", 1800, "-", self.CLIP, target)
        shots = self.sequence("fs-sequence-shots", [
            self.step(1, (0, 0), dd, "main"), self.step(600, (0, 0), dd),
            self.step(1, (0, 0), dd, "main"), self.step(300, (0, 0), dd)],
            [(1, ["main"]), (600, []), (1, ["main"]), (300, [])])
        trace = self.collect_trace("buffobserve", "fs-sequence-shots", timeout=8)
        after, release = self.native_snapshot(), self.released()
        samples = trace["samples"]
        changes = [(a.get("stacks"), b.get("stacks")) for a, b in zip(samples, samples[1:])
                   if a.get("stacks") != b.get("stacks")]
        hp_hits = [(a.get("now"), b.get("now")) for a, b in zip(samples, samples[1:])
                   if a.get("target_hpExact", 0)-b.get("target_hpExact", 0) > .01]
        self.check("sequence_two_real_button_presses", observed.get("ok") and shots["protocol"]["valid"]
                   and before["valid"] and after["valid"] and before["clip"] == 10 and after["clip"] == 8
                   and trace["valid"] and changes == [(10, 9), (9, 8)] and len(hp_hits) == 2
                   and all(x.get("target_valid") and x.get("target_hpMax") == 10000000
                           and x.get("player_valid") for x in samples),
                   {"sequence": shots, "observer": trace, "clip_changes": changes,
                    "actual_hp_hits": hp_hits, "before": before, "after": after})
        self.check("sequence_button_release_across_console", release["valid"], release)
        self.clear_dummies()
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.protocol_control()
    except Exception as exc:
        c.check("sequence_protocol_crashed", False, {"error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows, notes=c.notes)
    return c.out
