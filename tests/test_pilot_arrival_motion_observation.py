"""UNRUN observation-contract and queued-update models, not AS/native proof.

The possible input-only settling controller exists ONLY in this model proposal.
The staged AS adds observations and preserves its original steering/done behavior.
"""
from copy import deepcopy
import math
import unittest

PHASES = ("pre_neutral", "post_neutral", "future1", "future2", "future3")
HELD_BUTTONS = {"use", "potion", "dash", "main", "off", "skill1", "skill2", "skill3",
                "hwp_skill4", "hwp_skill5", "hwp_skill6"}


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def neutral(row):
    return (type(row) is dict and all(finite(row.get(k)) and abs(row[k]) < .0001 for k in ("mx", "my"))
            and row.get("down") == [])


def assess(terminal, settled, samples, tolerance=2):
    """A complete callback observation cannot prove engine actor/physics order."""
    result = {"complete": False, "cause_proven": False, "queued_motion_consistent": False,
              "model_settled_condition": False, "errors": []}
    if (type(samples) is not list or len(samples) != 5 or any(type(r) is not dict for r in samples)
            or [r.get("phase") for r in samples] != list(PHASES)
            or [r.get("sample") for r in samples] != list(range(5))
            or any(type(r.get("sample")) is not int or type(r.get("planned")) is not int
                   or r["planned"] != 5 for r in samples)
            or any(r.get("id") != terminal["id"] for r in samples)):
        result["errors"].append("missing/foreign/duplicate planned observations")
        return result
    identity = tuple(samples[0].get(k) for k in ("player", "boots", "level"))
    if identity != terminal.get("binding"):
        result["errors"].append("probe is not the expected pre-route actor/world")
        return result
    numbers = ("x", "y", "vx", "vy", "now", "callback", "dt", "input_writes")
    for row in samples:
        buffers = row.get("buffers")
        if type(buffers) is not list:
            result["errors"].append("unavailable remembered-buffer observation")
            continue
        inputs = [row.get("callback_input"), row.get("current_input"), *buffers]
        if (tuple(row.get(k) for k in ("player", "boots", "level")) != identity
                or any(not finite(row.get(k)) for k in numbers)
                or any(type(row.get(k)) is not int for k in ("now", "callback", "dt", "input_writes"))
                or any(row[k] < 0 for k in ("now", "callback", "input_writes"))
                or not 0 < row["dt"] <= 100 or row.get("paused") is not False
                or not isinstance(identity[2], str) or not identity[2]
                or type(identity[0]) is not int or identity[0] <= 0 or type(identity[1]) is not int or identity[1] <= 0
                or not 0 <= len(row.get("buffers", [])) <= 8
                or type(row.get("callback_is_current")) is not bool
                or any(type(i) is not dict or any(not finite(i.get(k)) for k in ("mx", "my"))
                       or type(i.get("slot")) is not int or not -1 <= i["slot"] < 8
                       or type(i.get("gamepad")) is not bool
                       or type(i.get("down")) is not list or any(type(v) is not str for v in i["down"])
                       for i in inputs)):
            result["errors"].append("unavailable/malformed/foreign callback observation")
        if (type(row.get("held_ms")) is not int or type(row.get("held_owner")) is not str
                or type(row.get("held_buttons")) is not list
                or any(type(v) is not str or v not in HELD_BUTTONS for v in row["held_buttons"])
                or type(row.get("sequence_busy")) is not bool or type(row.get("active_intent")) is not str
                or type(row.get("skillkeys_held")) is not str
                or any(not finite(row.get(k)) for k in ("reflex_fire", "reflex_potion"))
                or type(row.get("release_pending")) is not bool
                or type(row.get("release_calls_left")) is not int or not 0 <= row["release_calls_left"] <= 2):
            result["errors"].append("missing/malformed required ownership observation")
    if result["errors"]:
        return result
    pre, post = samples[:2]
    if (pre["callback"] != post["callback"] or pre["now"] != post["now"]
            or post["input_writes"] != pre["input_writes"]+1
            or any(b["callback"] != a["callback"]+1 or b["now"] <= a["now"]
                   for a, b in zip(samples[1:], samples[2:]))
            or any(b["input_writes"] < a["input_writes"] for a, b in zip(samples, samples[1:]))
            or [r.get("complete") for r in samples] != [False, False, False, False, True]):
        result["errors"].append("callback/native-clock/write-count/completeness gap")
        return result
    result["complete"] = True
    result["foreign_writer_observed"] = any(r["sequence_busy"] or r["held_ms"] > 0
        or r["active_intent"] not in ("", terminal["id"]) or r["reflex_fire"] > 0
        or r["reflex_potion"] > 0 or bool(r["skillkeys_held"]) for r in samples)
    # ApplyHeld returns without writing when msLeft<=0; its old buttons/owner
    # may remain. Retain those observed values, never call them an active Hold.
    result["inactive_held_buttons_observed"] = any(r["held_ms"] <= 0 and r["held_buttons"] for r in samples)
    result["buffer_counts"] = [len(r["buffers"]) for r in samples]
    all_neutral = all(neutral(i) for r in samples[1:]
                      for i in [r["callback_input"], r["current_input"], *r["buffers"]])
    result["nonneutral_after_neutral_observed"] = not all_neutral
    displacement = (samples[-1]["x"]-post["x"], samples[-1]["y"]-post["y"])
    result["queued_motion_consistent"] = bool(all_neutral and not result["foreign_writer_observed"]
        and math.hypot(post["vx"], post["vy"]) > .1 and math.hypot(*displacement) > .001
        and displacement[0]*post["vx"]+displacement[1]*post["vy"] > 0)
    last, previous = samples[-1], samples[-2]
    result["model_settled_condition"] = bool(all_neutral and not result["foreign_writer_observed"]
        and math.dist(settled, terminal["goal"]) <= tolerance
        and math.dist((last["x"], last["y"]), terminal["goal"]) <= tolerance
        and math.dist((last["x"], last["y"]), (previous["x"], previous["y"])) <= .05
        and all(math.hypot(r["vx"], r["vy"]) <= .1
                and all(neutral(i) for i in [r["callback_input"], r["current_input"], *r["buffers"]])
                for r in (previous, last)))
    return result


def observations():
    terminal = {"id": "c48", "goal": (-305.783, 1.337), "binding": (29816, 1, "levels/generated.lvl")}
    rows = []
    for n, phase in enumerate(PHASES):
        x = -304.102 if n < 2 else -308.017
        move = {"mx": -1. if n == 0 else 0., "my": 0., "down": [], "slot": 0, "gamepad": False}
        rows.append({"id": "c48", "phase": phase, "sample": n, "planned": 5, "complete": n == 4,
                     "player": 29816, "boots": 1, "level": "levels/generated.lvl",
                     "x": x, "y": 1.337, "vx": -118.636 if n < 2 else 0., "vy": 0.,
                     "callback": 100+max(0, n-1), "now": 1000+max(0, n-1)*33,
                     "dt": 33, "paused": False, "input_writes": 120 if n == 0 else 120+n,
                     "callback_input": deepcopy(move), "current_input": deepcopy(move), "buffers": [deepcopy(move)],
                     "callback_is_current": True,
                     "held_ms": -12, "held_owner": "c43", "held_buttons": [], "sequence_busy": False,
                     "skillkeys_held": "", "reflex_fire": 0., "reflex_potion": -1.,
                     "release_pending": n == 1, "release_calls_left": 1 if n == 2 else 0,
                     "active_intent": "c48" if n < 2 else ""})
    return terminal, rows


def queued_model(distance, step, lag, revised, max_ticks=512, tolerance=2):
    """Explicit hypothetical update queues; no assumption about actual native lag."""
    x, pending, history, stable = 0., [0.]*lag, [], 0
    for tick in range(max_ticks):
        error = distance-x
        if revised:
            command = 0. if abs(error) <= tolerance else max(-1., min(1., error/(4*max(step, tolerance))))
            # A future design would require observed motion to have stopped.
            stable = stable+1 if abs(error) <= tolerance and all(abs(v) < 1e-12 for v in pending) else 0
            done = stable >= 2
        else:
            command, done = (0., True) if abs(error) <= tolerance else (math.copysign(1., error), False)
        applied = pending.pop(0) if lag else command
        if lag:
            pending.append(command)
        history.append({"x": x, "command": command, "applied": applied, "done": done})
        x += applied*step
        if done:
            return {"done": True, "terminal": history[-1]["x"], "settled": x+sum(pending)*step,
                    "ticks": tick+1, "history": history}
    return {"done": False, "terminal": None, "settled": x, "ticks": max_ticks, "history": history}


class ArrivalMotionObservationTests(unittest.TestCase):
    def test_actual_e013_positions_without_motion_samples_keep_cause_unknown(self):
        terminal = {"id": "c48", "goal": (-305.783, 1.337)}
        report = assess(terminal, (-308.017, 1.337), [])
        self.assertFalse(report["complete"])
        self.assertFalse(report["cause_proven"])
        self.assertAlmostEqual(math.dist((-304.102, 1.337), terminal["goal"]), 1.681)
        self.assertGreater(math.dist((-308.017, 1.337), terminal["goal"]), 2)

    def test_synthetic_neutral_input_and_remaining_body_motion_only_gives_consistency(self):
        terminal, rows = observations()
        report = assess(terminal, (-308.017, 1.337), rows)
        self.assertTrue(report["complete"])
        self.assertTrue(report["queued_motion_consistent"])
        self.assertFalse(report["cause_proven"])
        self.assertFalse(report["model_settled_condition"])

    def test_nonzero_current_or_remembered_input_prevents_neutral_motion_inference(self):
        for sample in (1, 2, 3, 4):
            for target in ("callback_input", "current_input", "buffers"):
                terminal, rows = observations()
                item = rows[sample][target][0] if target == "buffers" else rows[sample][target]
                item["mx"] = -1.
                report = assess(terminal, (-308.017, 1.337), rows)
                self.assertFalse(report["queued_motion_consistent"])
                self.assertTrue(report["nonneutral_after_neutral_observed"])

    def test_no_velocity_evidence_does_not_become_proof_of_failed_neutral(self):
        terminal, rows = observations()
        rows[1]["vx"] = 0.
        report = assess(terminal, (-308.017, 1.337), rows)
        self.assertTrue(report["complete"])
        self.assertFalse(report["queued_motion_consistent"])
        self.assertFalse(report["cause_proven"])

    def test_observed_other_writer_retains_uncertainty(self):
        for changes in ({"held_ms": 33}, {"held_ms": 33, "held_owner": "foreign", "held_buttons": ["dash"]},
                        {"sequence_busy": True}, {"active_intent": "foreign"},
                        {"reflex_fire": 200.}, {"reflex_potion": 50.}, {"skillkeys_held": "4"}):
            terminal, rows = observations()
            rows[-1].update(changes)
            report = assess(terminal, (-308.017, 1.337), rows)
            self.assertTrue(report["foreign_writer_observed"])
            self.assertFalse(report["queued_motion_consistent"])
        terminal, rows = observations()
        rows[-1]["held_buttons"] = ["dash"]  # Inactive historical Hold configuration.
        report = assess(terminal, (-308.017, 1.337), rows)
        self.assertTrue(report["inactive_held_buttons_observed"])
        self.assertFalse(report["foreign_writer_observed"])

    def test_missing_duplicate_and_abort_observations_are_incomplete(self):
        terminal, rows = observations()
        for bad in (rows[:-1], rows+[rows[-1]], [rows[0], rows[1], rows[2], rows[2], rows[4]],
                    [*rows[:4], {**rows[4], "phase": "abort", "complete": False}]):
            self.assertFalse(assess(terminal, (-308.017, 1.337), bad)["complete"])
        for value in (None, 4, 5.0):
            bad = deepcopy(rows)
            bad[3]["planned"] = value
            self.assertFalse(assess(terminal, (-308.017, 1.337), bad)["complete"])

    def test_foreign_identity_nonfinite_and_unavailable_body_are_incomplete(self):
        for key, value in (("id", "foreign"), ("player", 999), ("boots", 2),
                           ("level", "foreign"), ("vx", float("nan")), ("current_input", None)):
            terminal, rows = observations()
            rows[3][key] = value
            self.assertFalse(assess(terminal, (-308.017, 1.337), rows)["complete"])
        malformed = {"held_ms": False, "held_owner": None, "held_buttons": "dash", "sequence_busy": None,
                     "active_intent": None, "skillkeys_held": None, "reflex_fire": float("nan"),
                     "reflex_potion": None, "release_pending": 0, "release_calls_left": -1}
        for key, value in malformed.items():
            for missing in (False, True):
                terminal, rows = observations()
                if missing: rows[3].pop(key)
                else: rows[3][key] = value
                self.assertFalse(assess(terminal, (-308.017, 1.337), rows)["complete"], (key, missing))

    def test_internally_consistent_foreign_actor_cannot_replace_expected_binding(self):
        terminal, rows = observations()
        for row in rows: row["player"] = 999
        self.assertFalse(assess(terminal, (-308.017, 1.337), rows)["complete"])

    def test_callback_clock_pause_and_write_gaps_are_incomplete(self):
        for key, value in (("callback", 100), ("now", 1000), ("paused", True), ("dt", 0), ("input_writes", 1),
                           ("callback", -1), ("now", -1), ("input_writes", -1)):
            terminal, rows = observations()
            rows[2][key] = value
            self.assertFalse(assess(terminal, (-308.017, 1.337), rows)["complete"])

    def test_write_counter_units_are_not_required_to_be_distinct_engine_frames(self):
        terminal, rows = observations()
        for n, row in enumerate(rows[2:]): row["input_writes"] = 125+n*2
        report = assess(terminal, (-308.017, 1.337), rows)
        self.assertTrue(report["complete"])
        self.assertFalse(report["cause_proven"])
        # Observation must not assume the remembered handle set is invariant:
        # the EXISTING ReleaseInput can register the callback between PRE/POST.
        terminal, rows = observations()
        rows[0]["buffers"] = []
        rows[0]["callback_input"]["slot"] = rows[0]["current_input"]["slot"] = -1
        report = assess(terminal, (-308.017, 1.337), rows)
        self.assertTrue(report["complete"])
        self.assertEqual(report["buffer_counts"], [0, 1, 1, 1, 1])

    def test_stationary_model_still_requires_original_tolerance(self):
        terminal, rows = observations()
        for row in rows[2:]: row.update(x=-308.017, vx=0.)
        self.assertFalse(assess(terminal, (-308.017, 1.337), rows)["model_settled_condition"])
        for row in rows[2:]: row.update(x=-305.783, vx=0.)
        self.assertTrue(assess(terminal, (-305.783, 1.337), rows)["model_settled_condition"])

    def test_full_stick_instant_arrival_can_fail_with_one_hypothetical_queued_update(self):
        model = queued_model(107.404, 3.915, 1, revised=False)
        self.assertTrue(model["done"])
        self.assertLessEqual(abs(model["terminal"]-107.404), 2)
        self.assertGreater(abs(model["settled"]-107.404), 2)

    def test_input_only_settling_proposal_handles_multiple_queue_lengths_and_speeds(self):
        for lag in range(4):
            for step in (.5, 1.25, 3.915, 7.):
                for distance in (-107.404, 23.25, 107.404):
                    model = queued_model(distance, step, lag, revised=True)
                    self.assertTrue(model["done"], (lag, step, distance))
                    self.assertLessEqual(abs(model["terminal"]-distance), 2)
                    self.assertLessEqual(abs(model["settled"]-distance), 2)
                    self.assertTrue(all(abs(row["command"]) <= 1 for row in model["history"]))

    def test_model_uses_only_queued_input_motion_and_bounded_deadline(self):
        model = queued_model(1e6, 3.915, 3, revised=True, max_ticks=40)
        self.assertFalse(model["done"])
        self.assertEqual(model["ticks"], 40)
        for a, b in zip(model["history"], model["history"][1:]):
            self.assertAlmostEqual(b["x"]-a["x"], a["applied"]*3.915)


if __name__ == "__main__":
    unittest.main()
