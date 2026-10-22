"""Exact source-derived Burst amplitudes, separate from cancellation/ordinary play.

Every fixed rank uses two real normal-button shells on a fresh 60k zero-defense
target. Native Raw9 outgoing factors drive the forward float32 model; target HP
is never a model input. No timed setter/direct activation occurs in measurement.
"""
import math
import re
import time

from gamelab.bots.qa_firearms_burst_cancel import Checks as Base, SKILL, CLASS, COSTS, source_cost
from gamelab.bots.qa_firearms_damage_model import physical_spell
from gamelab.bots.qa_firearms_input_sequence import sequence_protocol
from gamelab.bots.qa_firearms_resource_oracle import cast_payment
from gamelab.bots.qa_specs_living_mana import collect as collect_resources

UNIT = "gamelab/qa_firearms_target_dummy_damage.unit"
CLOSE = (1.5, 2.0, 2.5, 3.0, 3.5)
RANGES = (80, 80, 112, 112, 160)
# Two fractional-health float32 endpoints (ULP <=2^-24), plus two
# absolute-HP float32 endpoint products (ULP <=2^-8), and Raw9 serialization.
# This is a source/representation bound, independent of observed damage.
HP_BOUND = 60000 * 2**-24 + 2**-8 + 1e-9


def amplitude_oracle(model, hits, shell_logs, rank):
    expected = model.get("expected_hp_loss")
    valid = (model.get("valid") is True and type(expected) is int and expected > 0
             and len(hits) == 2 and len(shell_logs) == 2
             and all(h["loss"] > 0 and abs(h["loss"] - expected) <= HP_BOUND for h in hits)
             and all(int(a) >= int(b) >= 1 and int(c) == RANGES[rank-1]
                     and abs(float(d) - CLOSE[rank-1]) < .00001
                     for a, b, c, d in shell_logs))
    return {"valid": bool(valid), "expected_each_shell": expected,
            "actual_losses": [h["loss"] for h in hits], "hp_representation_bound": HP_BOUND,
            "source_close_intensity": CLOSE[rank-1], "source_close_range": RANGES[rank-1],
            "scope": "Exact two physical noncritical near-shell amplitudes at this rank; range boundaries, cadence/DPS, orbs and ordinary acquisition remain separate."}


class Checks(Base):
    def amplitude(self, rank, direction):
        self.clear_dummies()
        self.top_up()
        dd, target = self.tough(direction, 60, unit=UNIT)
        bar = self.bar()
        entry = self.entry(bar, SKILL)
        ready, readiness = self.raw_ready([SKILL])
        if not ready or not entry.get("button"):
            raise RuntimeError("unique mapped native Burst or naturally ready cooldown absent")
        self.gl("mana", bar["manaMax"] * .5)
        fixture = self.gl("skillcrit", SKILL, 0)
        origin, clip = self.pos(), self.clip()
        tag = "burst-amplitude-r%d-%d" % (rank, time.time_ns())
        steps = [self.step(1, (0, 0), dd, entry["button"]), self.step(900, (0, 0), dd)]
        mark = self.log_pos()
        try:
            replies = self.g.gl_multi([
                ["skills"], ["damagefields", SKILL, target], ["skillcost", SKILL, CLASS],
                ["resourceobserve", tag+"r", 1500], ["buffobserve", tag+"h", 1500, "-", "-", target],
                ["inputsequence", tag, *steps]])
            accepted = replies[-1]
            terminal = (self.g.wait_gl(lambda e: e.get("ev") == "inputsequence" and e.get("tag") == tag
                                       and e.get("id") == accepted.get("id"), timeout=15) or {}) if accepted.get("ok") else {}
            done = [e for e in self.g.gl if e.get("ev") == "input_done" and e.get("sequence") == tag]
            sequence = sequence_protocol(accepted, terminal, done, [(1, [entry["button"]]), (900, [])])
            resources = collect_resources(self.g, tag+"r", 10)
            hp = self.collect_trace("buffobserve", tag+"h", 8)
            cost = source_cost(replies[2], COSTS[rank-1])
            payment = cast_payment(resources, cost, refund=False, baseline_max=cost.get("max_mana"), duration_ms=1500)
            after = self.gl("damagefields", SKILL, target)
            end, idle_clip, release = self.pos(), self.clip(), self.released()
            crit_end = self.gl("skillcrit", SKILL)
        finally:
            restored = self.gl("skillcrit", SKILL, "restore")
        native = replies[1]
        model = physical_spell(150, native, SKILL, intensity=CLOSE[rank-1])
        model_end = physical_spell(150, after, SKILL, intensity=CLOSE[rank-1])
        samples = hp.get("samples", [])
        hits = [{"now": b["now"], "loss": a["target_hpExact"] - b["target_hpExact"]}
                for a, b in zip(samples, samples[1:])
                if a.get("target_hpExact", 0) - b.get("target_hpExact", 0) > .01]
        logs = re.findall(r"shotgun: (\d+) hit, (\d+) within (\d+) at x([0-9.]+)", self.log_from(mark))
        oracle = amplitude_oracle(model, hits, logs, rank)
        owner, enemy = native.get("owner", {}), native.get("target", {})
        target_position = (enemy.get("x", 1e9), enemy.get("y", 1e9))
        actual_vector = (target_position[0]-origin[0], target_position[1]-origin[1])
        distance = math.hypot(*actual_vector)
        placement = (enemy.get("unit") == target == after.get("target", {}).get("unit")
                     and enemy.get("name", "").endswith(UNIT) and enemy.get("hpMax") == 60000
                     and abs(enemy.get("hpFraction", 0)-1) < 1e-9 and 59 <= distance <= 61
                     and distance < RANGES[rank-1] - 10
                     and sum(actual_vector[i]*dd[i] for i in (0, 1)) > distance-.01
                     and math.dist(target_position, (after.get("target", {}).get("x", -1e9),
                                                     after.get("target", {}).get("y", -1e9))) < .001
                     and owner.get("class") == CLASS and owner.get("level") == 20)
        target_trace = (hp.get("valid") is True and bool(samples)
                        and all(x.get("target_valid") is True and x.get("player_valid") is True
                                and x.get("target_hpMax") == 60000 for x in samples)
                        and samples[0].get("target_hpExact") == 60000
                        and samples[-1].get("target_hpExact", 0) > 0
                        and all(b["target_hpExact"] <= a["target_hpExact"] for a, b in zip(samples, samples[1:])))
        crit = all(x.get("ok") is True and x.get("skill") == SKILL and x.get("override_active") is True
                   and x.get("left", 0) > 0 and x.get("crit_chance") == x.get("spell_crit_chance") == 0
                   for x in (fixture, crit_end))
        parents = {x.get("id", "").rsplit(".", 1)[0] for x in replies}
        atomic = len(replies) == 6 and all(x.get("ok") is True for x in replies) and len(parents) == 1 and "" not in parents
        in_input_window = (sequence.get("valid") and len(hits) == 2
                           and all(terminal.get("start", 1e9) <= h["now"] <= terminal.get("end", -1) for h in hits))
        unchanged_model = (model_end.get("valid") and model_end.get("expected_hp_loss") == model.get("expected_hp_loss")
                           and model_end.get("native_factor_chain") == model.get("native_factor_chain"))
        return {"valid": bool(atomic and ready and placement and target_trace and crit and in_input_window
                     and model.get("valid") and unchanged_model and oracle["valid"] and payment.get("valid")
                     and clip == idle_clip == 30 and math.dist(origin, end) <= 1 and release.get("valid")
                     and restored.get("ok") is True and restored.get("override_active") is False),
                "rank": rank, "model": model, "model_end": model_end, "oracle": oracle,
                "native_before": native, "native_after": after, "placement_valid": placement,
                "actual_target_distance": distance, "origin": origin, "end": end,
                "source_cost": cost, "payment": payment, "resources": resources,
                "hp_trace": hp, "hits": hits, "shell_logs": logs, "sequence": sequence,
                "sequence_accepted": accepted, "sequence_terminal": terminal, "input_done": done,
                "readiness": readiness, "clip": [clip, idle_clip], "release": release,
                "crit_begin": fixture, "crit_end": crit_end, "crit_restore": restored}

    def all_amplitudes(self):
        if not self.prepare("QABurstAmplitude", CLASS):
            return
        direction = self.local_dash_line()
        if direction is None:
            return
        for rank in range(1, 6):
            learned = self.learn_rank(SKILL, rank)
            result = self.amplitude(rank, direction)
            self.check("burst_rank_%d_exact_near_amplitude" % rank, learned == rank and result["valid"], result)
        self.clear_dummies()
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.all_amplitudes()
    except Exception as exc:
        c.check("burst_exact_amplitude_crashed", False, {"error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(x["runtime"] == "PASS" for x in c.rows), rows=c.rows, notes=c.notes)
    return c.out
