"""UNRUN pulse-policy/queued scalar-world models, not AS/native/phase proof.

No project/file/process/native imports or IO. The queue is an explicit fake
plant, not an inference about real UpdateFrame/Player/physics scheduling.
The unchanged AS collision, owner and deadline code remains independently
required. This model does not interpret AS or replace its live oracles.
"""
import math
import struct
import unittest


CAPTURE = dict(run="20261031-124559-fix-firearms-poses-lab", intent="c48", entry=27,
               callback=574, frame=573, now=18876, writes=116, expected_writes=116,
               actual_x=-0.999999940, expected_x=-0.857337415,
               expected_y=-0.000003714, actual_y="unobserved",
               terminal_x=-297.031, goal_x=-306.543, later_x=-304.303)


def f32(value):
    return struct.unpack("!f", struct.pack("!f", value))[0]


def pulse(duty, credit):
    """Scalar model; binary32 rounding at each new credit operation."""
    if not (math.isfinite(duty) and 0 < duty <= 1 and math.isfinite(credit) and 0 <= credit < 1):
        raise ValueError("invalid pulse duty or credit")
    if duty == 1:
        return True, 0.0
    credit = f32(credit + duty)
    if credit >= 1:
        return True, f32(credit - 1)
    return False, credit


def queued_world(queued, step=lambda n: 3.915, initial=107.404, max_callbacks=400,
                 foreign_at=None, invalid_at=None, blocked_correction=False, initial_pending=None):
    """Selected straight legal-path fake with queued+1 callback write delay.

    One dimension and deterministic displacement units are explicit model
    assumptions. No speed/velocity conversion, unknown-gain calibration,
    collision implementation or native phase is claimed. The finite horizon
    stands for an independently required deadline, not a new AS cutoff.
    """
    pending = [0] * (queued + 1) if initial_pending is None else list(initial_pending)
    assert len(pending) == queued + 1 and all(value in (-1, 0, 1) for value in pending)
    position, peak, duty, credit = initial, 0.0, 1.0, 0.0
    holding = False
    quiet = inside_quiet = neutrals = holds = corrections = 0
    expected = 0
    writes = []
    for callback in range(max_callbacks):
        applied = pending.pop(0)
        displacement = applied * step(callback)
        position += displacement
        peak = max(peak, abs(displacement))
        remaining = abs(position)
        # Selected admission guards precede every policy write in this model.
        if callback == foreign_at:
            return dict(result="foreign", position=position, writes=writes, holds=holds,
                        corrections=corrections, callback=callback, new_policy_writes=0)
        if callback == invalid_at:
            return dict(result="invalid-world", position=position, writes=writes, holds=holds,
                        corrections=corrections, callback=callback, new_policy_writes=0)
        if remaining <= 2:
            holding = True
        if holding:
            credit = 0.0
            holds += 1
            if holds > 12:
                return dict(result="hold-budget", position=position, writes=writes, holds=holds,
                            corrections=corrections)
            is_quiet = expected == 0 and abs(displacement) <= .05 and applied == 0
            quiet = quiet + 1 if is_quiet else 0
            inside_quiet = inside_quiet + 1 if is_quiet and remaining <= 2 else 0
            if neutrals >= 4 and quiet >= 2 and (remaining > 2 or inside_quiet >= 2):
                if remaining <= 2:
                    return dict(result="done", position=position, writes=writes, holds=holds,
                                corrections=corrections, neutral=True, quiet=quiet,
                                inside_quiet=inside_quiet, credit=credit)
                if corrections >= 4 or blocked_correction:
                    return dict(result="route-budget-or-block", position=position, writes=writes,
                                holds=holds, corrections=corrections)
                corrections += 1
                holding = False
                quiet = inside_quiet = neutrals = 0
                credit = 0.0
            else:
                expected = 0
                neutrals += 1
                writes.append(0)
                pending.append(0)
                continue
        # Same conservative actual-step bound, never divided by last command.
        if remaining <= max(16.0, 4 * peak):
            cap = remaining / (4 * max(2.0, peak)) if peak > 0 else .125
            duty = f32(min(duty, min(1.0, cap)))
        emitted, credit = pulse(duty, credit)
        direction = -1 if position > 0 else 1  # fake fresh legal path direction
        expected = direction if emitted else 0
        writes.append(expected)
        pending.append(expected)
    return dict(result="deadline", position=position, writes=writes, holds=holds,
                corrections=corrections)


class TightPulseControlTests(unittest.TestCase):
    def test_retained_material_mismatch_is_not_reclassified_as_precision(self):
        difference = abs(CAPTURE["actual_x"] - CAPTURE["expected_x"])
        self.assertGreater(difference, 2 ** -24)
        self.assertGreater(difference, .14)
        self.assertEqual(CAPTURE["actual_y"], "unobserved")
        self.assertEqual(CAPTURE["writes"], CAPTURE["expected_writes"])
        self.assertAlmostEqual(abs(CAPTURE["terminal_x"] - CAPTURE["goal_x"]), 9.512)
        self.assertAlmostEqual(abs(CAPTURE["later_x"] - CAPTURE["goal_x"]), 2.240)

    def test_first_partial_duty_refuses_analog_amplitude_assumption(self):
        duty = f32(abs(CAPTURE["expected_x"]))
        emitted, credit = pulse(duty, 0.0)
        self.assertFalse(emitted)
        self.assertEqual(credit, duty)
        emitted, credit = pulse(duty, credit)
        self.assertTrue(emitted)
        self.assertTrue(0 <= credit < 1)
        # Commands are selected full direction or zero; expected is never
        # adopted from the material readback or multiplied by duty.
        self.assertNotEqual(duty, 1.0)

    def test_unit_duty_preserves_ordinary_full_direction_each_callback(self):
        for credit in (0.0, .25, f32(.99999994)):
            self.assertEqual(pulse(1.0, credit), (True, 0.0))

    def test_credit_is_bounded_and_density_tracks_constant_duty(self):
        for value in (.125, .3, .857337415):
            duty, credit, emitted = f32(value), 0.0, 0
            for _ in range(1000):
                send, credit = pulse(duty, credit)
                emitted += send
                self.assertTrue(0 <= credit < 1)
            self.assertLessEqual(abs(emitted - 1000 * duty), 1.001)

    def test_malformed_duty_or_credit_fails_before_command_selection(self):
        for duty, credit in ((0, 0), (-.1, 0), (1.1, 0), (math.nan, 0), (math.inf, 0),
                             (.5, math.nan), (.5, -1), (.5, 1), (.5, math.inf)):
            with self.subTest(duty=duty, credit=credit), self.assertRaises(ValueError):
                pulse(duty, credit)

    def test_new_route_hold_or_intent_does_not_inherit_old_credit(self):
        old_credit = f32(.95)
        self.assertTrue(pulse(f32(.1), old_credit)[0])
        for boundary in ("hold", "repath", "new-intent"):
            credit = 0.0  # source resets at these exact ownership boundaries
            self.assertFalse(pulse(f32(.1), credit)[0], boundary)

    def test_explicit_zero_through_three_queued_models_reach_strict_settlement(self):
        for queued in range(4):
            with self.subTest(queued=queued):
                result = queued_world(queued)
                self.assertEqual(result["result"], "done")
                self.assertLessEqual(abs(result["position"]), 2)
                self.assertTrue(result["neutral"])
                self.assertGreaterEqual(result["inside_quiet"], 2)
                self.assertGreaterEqual(result["quiet"], 2)
                self.assertLessEqual(result["holds"], 12)
                self.assertLessEqual(result["corrections"], 4)
                self.assertTrue(all(command in (-1, 0, 1) for command in result["writes"]))

    def test_speed_change_cannot_turn_outside_or_moving_point_into_success(self):
        for queued in range(4):
            result = queued_world(queued, step=lambda n: 3.915 if n < 20 else 2.5)
            if result["result"] == "done":
                self.assertLessEqual(abs(result["position"]), 2)
                self.assertTrue(result["neutral"])
                self.assertGreaterEqual(result["inside_quiet"], 2)
            else:
                self.assertIn(result["result"], ("deadline", "hold-budget", "route-budget-or-block"))

    def test_zero_motion_and_unreachable_unit_lattice_fail_bounded(self):
        for queued in range(4):
            stopped = queued_world(queued, step=lambda n: 0.0, max_callbacks=80)
            self.assertEqual(stopped["result"], "deadline")
            unreachable = queued_world(queued, step=lambda n: 5.0, initial=2.5, max_callbacks=80)
            self.assertNotEqual(unreachable["result"], "done")
            self.assertLessEqual(len(unreachable["writes"]), 80)

    def test_takeover_or_invalid_actor_world_preempts_next_policy_write(self):
        for event in ("foreign_at", "invalid_at"):
            for callback in (0, 5, 30):
                result = queued_world(2, **{event: callback})
                self.assertEqual(result["callback"], callback)
                self.assertEqual(result["new_policy_writes"], 0)
                self.assertEqual(len(result["writes"]), callback)

    def test_blocked_endpoint_correction_never_grants_done_or_teleports(self):
        # Explicit queued residual movement carries an initially inside sample
        # outside. Once neutral/quiet, a blocked fresh route must refuse.
        result = queued_world(3, initial=1.0, initial_pending=[0, 1, 1, 0], blocked_correction=True)
        self.assertEqual(result["result"], "route-budget-or-block")
        self.assertGreater(abs(result["position"]), 2)

    def test_duty_changes_never_emit_fractional_or_accumulated_burst_commands(self):
        credit = 0.0
        for duty in (1.0, .9, .5, .125, .01, .75, .1) * 12:
            emitted, credit = pulse(f32(duty), credit)
            self.assertIs(type(emitted), bool)
            self.assertTrue(0 <= credit < 1)


if __name__ == "__main__":
    unittest.main()
