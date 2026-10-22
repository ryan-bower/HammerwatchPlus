"""All five Pyre ranks with real bound input, ownership, damage and expiry.

Controlled cleared floor, native skill learning and setup-only mana refill.
The inputsequence controller waits for gameplay focus before it writes input.
No exact burn coefficient/cadence/radius or ordinary/save/co-op claim is made.
"""
import math
import time

from gamelab.bots.qa_class_base import Checks as Base, collect
from gamelab.bots.qa_firearms_input_sequence import sequence_protocol

SKILL = "hwp_witch_hunter_pyre"
FILTER = "witchhunter/units/pyre"


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class Checks(Base):
    def cast_observed(self, direction, button, target, tag):
        observer_tag, input_tag = tag + "-hp", tag + "-input"
        sent = self.g.gl_multi([
            ["buffobserve", observer_tag, 14000, "-", "-", target],
            ["inputsequence", input_tag,
             "/".join(["500", "0", "0", format(direction[0], ".6f"),
                       format(direction[1], ".6f"), button]),
             "/".join(["200", "0", "0", format(direction[0], ".6f"),
                       format(direction[1], ".6f"), "-"]),
             "/".join(["500", "0", "0", format(direction[0], ".6f"),
                       format(direction[1], ".6f"), button])],
        ])
        accepted = sent[1]
        terminal = (self.g.wait_gl(lambda e: e.get("ev") == "inputsequence"
                                  and e.get("tag") == input_tag, timeout=15) or {}) if accepted.get("ok") else {}
        done = [e for e in self.g.gl if e.get("ev") == "input_done" and e.get("sequence") == input_tag]
        protocol = sequence_protocol(accepted, terminal, done, [(500, [button]), (200, []), (500, [button])])
        units = self.gl("near", 250, FILTER)
        owned = [self.gl("summonmove", u["unit"]) for u in units.get("units", [])]
        skills = self.gl("skills")
        selected = [row for row in skills.get("skills", []) if row.get("id") == SKILL]
        return {"cooldown_reply": skills, "selected_skill": selected[0] if len(selected) == 1 else {},
                "observer_tag": observer_tag, "observer_start": sent[0], "accepted": accepted,
                "terminal": terminal, "input_done": done, "protocol": protocol,
                "near": units, "owned": owned}

    def all_ranks(self):
        if not self.prepare("hwp_witch_hunter", None, "QAPyreAllInput"):
            return
        lane, note = self.to_trident_lane(front=50, back_neighbor=True, ray_distance=80,
                                          clearance_points=((0, 0, 32),), tag="pyre_all")
        self.flag("pyre_all_geometry", bool(lane), note)
        if not lane:
            return
        direction, rows, damages = lane[0], [], []
        for rank, expected_hp in enumerate((200, 300, 400, 500, 600), 1):
            tag = f"pyre_all_r{rank}"
            learned = self.learn(SKILL, rank, tag)
            old = self.gl("near", 500, FILTER)
            absent = old.get("ok") is True and not old.get("truncated") and old.get("units") == []
            self.flag(tag + "_old_units_absent", absent, str(old))
            before = self.targets([(direction[0] * 50, direction[1] * 50)])
            self.flag(tag + "_target", bool(before), str(before))
            button = self.normal_button(SKILL)
            self.flag(tag + "_bound_button", bool(button), str(button))
            if not learned or not absent or not before or not button:
                continue
            fixture = self.gl("skillcrit", SKILL, 0)
            fixture_ok = (fixture.get("ok") is True and fixture.get("skill") == SKILL
                          and fixture.get("override_active") is True
                          and fixture.get("crit_chance") == 0 and fixture.get("spell_crit_chance") == 0)
            self.flag(tag + "_noncrit_fixture", fixture_ok, str(fixture))
            try:
                self.gl("mana", 999)
                if not fixture_ok or not self.raw_ready(SKILL, tag):
                    continue
                origin = self.me()
                native_tag = f"pyre{rank}-{time.time_ns()}"
                track, cast = self.track(14500, 500, FILTER,
                    lambda: self.cast_observed(direction, button, before[0]["unit"], native_tag))
                observed = collect(self.g, cast["observer_tag"], 22)
                after, loss = self.snapshots(before)
                time.sleep(2)
                tail, later_loss = self.snapshots(before)
                gone = self.gl("near", 500, FILTER)
                owned = cast["owned"]
                owner = owned[0] if len(owned) == 1 else {}
                ownership = bool(cast["near"].get("ok") is True and not cast["near"].get("truncated")
                    and len(owned) == 1 and owner.get("ok") is True
                    and owner.get("hpMax") == expected_hp and owner.get("hpExact") == expected_hp
                    and owner.get("movement", "").endswith("PassiveMovement")
                    and type(owner.get("owner")) is int and owner["owner"] > 0
                    and all(number(owner.get(k)) for k in ("ownerX", "ownerY", "x", "y"))
                    and math.dist(origin, (owner["ownerX"], owner["ownerY"])) <= 1)
                placement = bool(ownership and math.dist((owner["x"], owner["y"]),
                    (origin[0] + 24 * direction[0], origin[1] + 24 * direction[1])) <= 2)
                samples = observed.get("events", [])
                native_hp = [e.get("target_hpExact") for e in samples]
                burning = bool(cast["observer_start"].get("ok") is True and observed.get("usable")
                    and observed.get("target_unit") == before[0]["unit"] and samples
                    and all(e.get("target_valid") is True and e.get("target_hpMax") == 15000
                            and number(e.get("target_hpExact")) for e in samples)
                    and native_hp[0] == 15000 and len(set(native_hp)) >= 3
                    and number(loss) and loss > 0 and len(after) == 1
                    and abs(native_hp[-1] - after[0]["hpExact"]) <= .01)
                tracks = (track or {}).get("tracks", [])
                life = tracks[0].get("t1", 0) - tracks[0].get("t0", 0) if len(tracks) == 1 else 0
                expiry = bool(track and not track.get("truncated") and len(tracks) == 1
                    and 7400 <= life <= 8800 and number(loss) and later_loss == loss
                    and gone.get("ok") is True and not gone.get("truncated") and gone.get("units") == [])
                steps = cast["terminal"].get("steps", [])
                cooldown = cast["selected_skill"].get("cd")
                second_refused = bool(cast["protocol"]["valid"] and len(steps) == 3
                    and 700 <= steps[2]["first_write"] - steps[0]["first_write"] < 12000
                    and cast["cooldown_reply"].get("ok") is True and number(cooldown) and 0 < cooldown <= 12000
                    and ownership and len(tracks) == 1)
                self.flag(tag + "_cooldown_started_and_second_refused", second_refused,
                          str({"native_input": cast, "tracks": tracks}))
                self.flag(tag + "_native_input", cast["protocol"]["valid"], str(cast["protocol"]))
                self.flag(tag + "_native_hp_owner", ownership, str(owner))
                self.flag(tag + "_forward_placement", placement, str({"origin": origin, "unit": owner, "aim": direction}))
                self.flag(tag + "_actual_burn", burning, str({"damage": loss, "observer": observed}))
                self.flag(tag + "_natural_expiry", expiry, str({"life": life, "damage": loss, "tail": later_loss, "gone": gone}))
                passed = bool(cast["protocol"]["valid"] and second_refused and ownership and placement and burning and expiry)
                rows.append({"rank": rank, "expected_hp": expected_hp, "origin": origin, "direction": direction,
                    "fixture": fixture, "input": cast, "owned": owned, "track": track, "native_hp": observed,
                    "before": before, "after": after, "after_expiry": tail, "damage": loss, "passed": passed})
                damages.append(loss)
            finally:
                restored = self.gl("skillcrit", SKILL, "restore")
                self.flag(tag + "_crit_restored", restored.get("ok") is True
                          and restored.get("override_active") is False, str(restored))
        scaled = bool(len(damages) == 5 and all(number(d) for d in damages) and damages[-1] > damages[0])
        self.flag("pyre_all_endpoint_damage", scaled, str(damages))
        self.flag("pyre_all_ranks", len(rows) == 5 and all(row["passed"] for row in rows) and scaled)
        self.out["pyre_all_trials"] = rows
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.all_ranks()
    except Exception as exc:
        c.flag("pyre_all_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
