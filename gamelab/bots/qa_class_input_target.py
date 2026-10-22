"""Normal Net mouse-targeting protocol, before ordinary or cancellation credit.

Cleared controlled floor; native buttons and projected current-input cursor only.
No Skill.Activate, castat, targeting-helper state, measured-resource or cooldown writes.
"""
import math
import time

from gamelab.bots.qa_class_base import Checks as Base
from gamelab.bots.qa_classes import QA_DUMMY_FILTER
from gamelab.bots.qa_firearms_missing_orbs import Checks as TraceChecks
from gamelab.bots.qa_input_target import collect, finite

SKILL = "hwp_gladiator_net"
BUFF = "tweak/buffs/status_effects.sval:immobilize"


def step(ms, direction, button="-"):
    return "/".join([str(ms), "0", "0", *(format(v, ".6f") for v in direction), button])


class Checks(Base):
    def idle(self):
        first = self.g.gl_multi([["controller"], ["state"]])
        time.sleep(.2)
        second = self.g.gl_multi([["controller"], ["state"]])
        def released(row):
            return (row.get("ok") is True and type(row.get("held")) is int and row["held"] <= 0
                    and row.get("releasing") is False
                    and row.get("down") == [] and finite(row.get("mx")) and finite(row.get("my"))
                    and abs(row["mx"]) < .0001 and abs(row["my"]) < .0001)
        positions = [r[1].get("player", {}) for r in (first, second)]
        stationary = (all(finite(p.get(k)) for p in positions for k in ("x", "y"))
                      and math.dist(tuple(positions[0][k] for k in ("x", "y")),
                                    tuple(positions[1][k] for k in ("x", "y"))) <= 1)
        return {"valid": all(r.get("ok") is True for r in first+second)
                and released(first[0]) and released(second[0]) and stationary,
                "first": first, "second": second, "stationary": stationary}

    def protocol(self):
        if not self.prepare("hwp_gladiator", None, "QANormalNet"):
            return
        lane, note = self.to_trident_lane(front=136, back_neighbor=True, ray_distance=144,
                                          tag="input_target", clearance_points=((0, 0, 48),))
        self.flag("target_geometry", bool(lane), note)
        if not lane:
            return
        direction, side = lane
        actors = self.targets([(128*direction[0], 128*direction[1]), (32*side[0], 32*side[1])])
        self.flag("target_fixture", bool(actors and len(actors) == 2), str(actors))
        if not actors:
            return
        origin = self.pos()
        center = max(actors, key=lambda a: math.dist(origin, (a["x"], a["y"])))
        outside = next(a for a in actors if a["unit"] != center["unit"])
        target = center["x"], center["y"]
        actual_geometry = (120 <= math.dist(origin, target) <= 136
            and math.dist(target, (outside["x"], outside["y"])) >= 100)
        self.flag("target_actual_centers", actual_geometry, str({"origin": origin, "center": center, "outside": outside}))
        button = self.normal_button(SKILL)
        learned = self.learn(SKILL, 1, "target_net")
        self.flag("target_bound_button", bool(button and button != "main"), str(button))
        if not actual_geometry or not learned or not button or button == "main" or not self.raw_ready(SKILL, "target_net"):
            return
        #100ms skill hold, separate release, ordinary main-confirm and neutral.
        #Quickcast casts on release; its300ms animation still blocks the later
        #confirm. The128px target is beyond the primary melee hit, independently.
        steps = [step(100, direction, button), step(100, direction),
                 step(1, direction, "main"), step(500, direction)]
        expected = [(100, [button]), (100, []), (1, ["main"]), (500, [])]
        before = self.gl("state")
        tag = "normal-net-" + str(time.time_ns())
        accepted = self.g.gl_multi([["actorbuffobserve", tag, 8000, center["unit"], BUFF],
                                    ["inputtarget", tag, SKILL, *target, *steps]])
        sequence = collect(self.g, accepted[1] if len(accepted) == 2 else {}, expected, timeout=15)
        #Read both actors BEFORE waiting the8s observer, while center's native
        #buff is demonstrably live. Expired outside buffs cannot pass.
        early = self.g.gl_multi([["actorbuffs", 300, QA_DUMMY_FILTER], ["skills"], ["state"], ["clock"]])
        trace = TraceChecks.collect_trace(self, "actorbuffobserve", tag, timeout=12)
        release = self.idle()
        rows = sequence.get("samples", [])
        early_actors = {a.get("unit"): a for a in early[0].get("actors", [])}
        hit, away = early_actors.get(center["unit"]), early_actors.get(outside["unit"])
        current = next((s for s in early[1].get("skills", []) if s.get("id") == SKILL), {})
        valid_actor = lambda a: bool(a and a.get("hpMax") == 15000
            and finite(a.get("hpExact")) and abs(a["hpExact"]-15000) <= .003)
        effect = (valid_actor(hit) and "immobilize" in self.tags(hit)
                  and valid_actor(away) and "immobilize" not in self.tags(away))
        cast_rows = [r for r in rows if type(r.get("cd")) is int and r["cd"] > 0
                     and type(r.get("timeline")) is int and r["timeline"] >= 0]
        target_readback = bool(cast_rows and any(math.dist((r["cast_x"], r["cast_y"]), target) <= 1 for r in cast_rows))
        samples = trace.get("samples", [])
        active = [r for r in samples if r.get("buff_on") is True]
        lifecycle = bool(trace.get("valid") and samples and samples[0].get("buff_on") is False
            and samples[-1].get("buff_on") is False and active
            and all(r.get("valid") is True and r.get("unit") == center["unit"]
                    and r.get("hpMax") == 15000 and finite(r.get("hpExact"))
                    and abs(r["hpExact"]-15000) <= .003 for r in samples)
            and all(r.get("matches") == 1 and r.get("duration") == 3500 and r.get("left", 0) > 0 for r in active))
        mana0, mana1 = before.get("player", {}).get("manaExact"), early[2].get("player", {}).get("manaExact")
        paid = (finite(mana0) and finite(mana1) and mana0 > mana1
                and type(current.get("cd")) is int and 0 < current["cd"] <= 8000)
        detail = {"accepted": accepted, "sequence": sequence, "before": before, "early": early,
                  "center": center, "outside": outside, "native_target": target, "actual_cast_rows": cast_rows,
                  "actor_trace": trace, "release": release}
        self.flag("target_native_sequence_and_cursor", len(accepted) == 2 and all(a.get("ok") is True for a in accepted)
                  and sequence.get("valid") is True, str(sequence))
        self.flag("target_native_position_timeline", sequence.get("valid") is True and target_readback, str(cast_rows))
        self.flag("target_actual_effect_and_outside", sequence.get("valid") is True and effect, str(early))
        self.flag("target_normal_paid_cast", sequence.get("valid") is True and paid, str({"before": before, "early": early}))
        self.flag("target_natural_buff_lifecycle", lifecycle, str(trace))
        self.flag("target_release_across_console", release["valid"], str(release))
        self.out["normal_target_trial"] = detail
        self.out["duration_scope"] = ("Controller protocol expects actual native immobilize definition3500ms; "
            "Net tooltip says2000ms. This discrepancy is retained for separate gameplay verification, "
            "not treated as duration-correctness PASS by this protocol.")
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.protocol()
    except Exception as exc:
        c.flag("target_protocol_crashed", False, repr(exc))
    c.out.update(notes=c.notes, terminal=" | ".join(c.notes)[-5000:])
    return c.out
