"""UNRUN bounded input-only reference and adversarial queued-world controls.

These tests do not import, compile, or execute AngelScript. The independent world
queues already written commands for 0..3 observations; it does not divide a world
step by a just-written stick or assign physical units to native body velocity.
Only math/unittest and in-memory values are used. No source/log/native IO.
"""
import math
import unittest


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def route_bound(origin, goal, tol, points):
    """New stricter local proposal, not qa_routeleg's native complete12 flag."""
    if (not points or len(points) > 256 or not all(finite(p) for p in points)
            or abs(points[0] - origin) > tol):
        return False
    previous, arc = origin, 0
    for point in points:
        arc += abs(point - previous)
        previous = point
    return finite(arc) and arc <= 128 and abs(previous - goal) <= tol


def admit(kind, tol, idle=True, neutral=True, active_tight=False):
    if active_tight:
        return "refuse_before_replace"
    if kind != "path_to" or not finite(tol) or not 0 < tol <= 2:
        return "original_policy"
    return "tight" if idle and neutral else "refuse_before_replace"


class Controller:
    """Scalar reference to the proposed tight-only policy, not an AS interpreter."""

    def __init__(self, goal=0.0, position=-107.404, tol=2.0, deadline=15000):
        self.goal, self.tol = goal, tol
        self.previous, self.now = position, 0
        self.expected, self.writes = 0.0, 0
        self.peak, self.cap = 0.0, 1.0
        self.holding = False
        self.holds = self.quiet = self.inside_quiet = self.neutrals = self.corrections = 0
        self.observations = self.no_motion = self.elapsed = 0
        self.stuck_from, self.stuck_ms = position, 0
        self.deadline, self.result, self.release = deadline, None, False

    def end(self, result, owned):
        self.result, self.release = result, owned
        return None

    def owner(self, sample):
        return (sample["world"] == "original" and sample["actor"] == "original"
                and sample["sole"] and sample["held_ms"] <= 0 and not sample["qa_busy"]
                and sample["reflex_fire"] <= 0 and sample["reflex_potion"] <= 0
                and sample["skillkeys"] == "" and not sample["releasing"]
                and sample["writes"] == self.writes and self.writes < 2000000000
                and sample["tracked"] and sample["current_is_callback"]
                and sample["same_buffers"] and sample["same_gamepad"]
                and sample["buttons"] == [] and sample["moves"] == [self.expected])

    def write(self, value):
        self.expected = value
        self.writes += 1
        return value

    def repath(self, sample):
        if self.corrections >= 4:
            self.end("correction_budget", True)
            return False
        self.corrections += 1
        if not sample["routed"] or sample["route_goal"] != self.goal:
            self.end("no_route", True)
            return False
        self.holding = False
        self.quiet = self.inside_quiet = self.neutrals = 0
        self.stuck_from, self.stuck_ms = sample["position"], 0
        return True

    def step(self, sample):
        if self.result is not None:
            return None  # cancellation/new intent cannot retain old controller writes
        if not self.owner(sample):
            return self.end("foreign_or_unknown", False)
        if sample["paused"] or sample["cancel"] or not sample["alive"]:
            return self.end("interrupted", True)
        self.elapsed += sample["dt"]
        if self.elapsed > self.deadline:
            return self.end("timeout", True)
        position, now, velocity = sample["position"], sample["now"], sample["velocity"]
        self.observations += 1
        if (not all(finite(v) for v in (position, velocity, now, sample["dt"]))
                or not 0 < sample["dt"] <= 250 or now < 0 or now <= self.now
                or sample["goal"] != self.goal
                or sample["tol"] != self.tol):
            return self.end("observation", True)
        step = abs(position - self.previous)
        self.peak = max(self.peak, step)
        self.previous, self.now = position, now
        remaining = abs(position - self.goal)
        if remaining <= self.tol:
            self.holding = True
        if self.holding:
            self.holds += 1
            if self.holds > 12:
                return self.end("hold_budget", True)
            quiet = self.expected == 0 and step <= .05 and velocity == 0
            self.quiet = self.quiet + 1 if quiet else 0
            self.inside_quiet = self.inside_quiet + 1 if quiet and remaining <= self.tol else 0
            if self.neutrals >= 4 and self.quiet >= 2 and (remaining > self.tol or self.inside_quiet >= 2):
                if remaining <= self.tol:
                    # The AS uses its existing final diagnostic/release/done sequence.
                    self.write(0)
                    return self.end("done", True)
                if not self.repath(sample):
                    return None
            else:
                self.neutrals += 1
                return self.write(0)
        self.stuck_ms += sample["dt"]
        if self.stuck_ms >= 1000:
            if abs(position - self.stuck_from) < 3 and not self.repath(sample):
                return None
            self.stuck_from, self.stuck_ms = position, 0
        direction = sample["direction"]
        if not finite(direction) or abs(direction) != 1:
            return self.end("route_direction", True)
        if remaining <= max(16, 4 * self.peak):
            cap = remaining / (4 * max(self.tol, self.peak)) if self.peak > 0 else .125
            self.cap = min(self.cap, 1, cap)
        self.no_motion = self.no_motion + 1 if step <= .0001 and self.expected != 0 else 0
        if self.no_motion > 8:
            return self.end("no_motion", True)
        return self.write(direction * self.cap)

    def callback(self, sample):
        try:
            return self.step(sample)
        except Exception:
            # Unknown on the first ownership read stays unknown even if a later
            # read would recover; no new release or clearing of foreign state.
            if self.result is None:
                return self.end("callback_unknown", False)
            return None


def observation(controller, at, clock, **changes):
    sample = dict(position=at, now=clock, velocity=0, dt=33,
                  world="original", actor="original", sole=True, held_ms=-12,
                  qa_busy=False, reflex_fire=0, reflex_potion=-1, skillkeys="",
                  releasing=False, writes=controller.writes, tracked=True,
                  current_is_callback=True, same_buffers=True, same_gamepad=True,
                  buttons=[], moves=[controller.expected], paused=False, cancel=False,
                  alive=True, routed=True, route_goal=controller.goal,
                  goal=controller.goal, tol=controller.tol,
                  direction=1 if controller.goal > at else -1)
    sample.update(changes)
    return sample


def queued_world(lag, gain=3.915, direction=1, speed_change=None, min_speed=0, distance=107.404):
    """Independent causal queue: lag0 integrates this write before next observation.

    lag1..3 insert that many additional update slots. Velocity is an intentionally
    synthetic nonzero/zero motion signal, not a native unit conversion.
    """
    controller = Controller(goal=distance * direction, position=0)
    position, queue, records, velocity = 0.0, [0.0] * lag, [], 0.0
    for tick in range(1, 513):
        sample = observation(controller, position, tick * 33, velocity=velocity)
        before = controller.writes
        command = controller.callback(sample)
        if controller.result == "callback_unknown":
            raise AssertionError("unexpected reference-model exception in synthetic world")
        records.append((sample, command, controller.writes - before))
        if controller.result is not None:
            return controller, position, records
        queue.append(command)
        old = queue.pop(0)
        scale = speed_change(tick) if speed_change else gain
        delta = math.copysign(max(abs(old) * scale, min_speed), old) if old else 0.0
        position += delta
        velocity = old
    raise AssertionError("reference escaped observation bound")


class TightArrivalControllerTests(unittest.TestCase):
    def test_first_ownership_read_throws_then_recovers_without_new_tail(self):
        c = Controller()
        normal_owner, reads = c.owner, []

        def transient_owner(sample):
            reads.append(1)
            if len(reads) == 1:
                raise RuntimeError("synthetic ownership read unavailable")
            return normal_owner(sample)

        c.owner = transient_owner
        row = observation(c, -107.404, 33)
        c.callback(row)
        self.assertEqual(c.result, "callback_unknown")
        self.assertEqual(len(reads), 1)
        self.assertEqual(c.writes, 0)
        self.assertFalse(c.release)
        self.assertTrue(c.owner(row))  # a second read could recover, but cannot re-authorize
        self.assertFalse(c.release)
        c.callback(observation(c, -107.404, 66))
        self.assertEqual(c.writes, 0)

    def test_quiet_outside_to_first_inside_sample_cannot_complete(self):
        c = Controller(position=-2.01)
        c.holding, c.neutrals, c.quiet = True, 4, 1
        c.step(observation(c, -1.99, 33))  # zero velocity,0.02step, first quiet inside
        self.assertEqual(c.inside_quiet, 1)
        self.assertIsNone(c.result)
        c.step(observation(c, -1.99, 66))
        self.assertEqual(c.inside_quiet, 2)
        self.assertEqual(c.result, "done")

    def test_only_literal_finite_tight_path_scope_uses_new_policy(self):
        self.assertEqual(admit("path_to", 2), "tight")
        for kind, tol in (("move", 2), ("path_to", 4), ("exit", 2),
                          ("path_to", 0), ("path_to", math.nan)):
            self.assertEqual(admit(kind, tol), "original_policy")

    def test_busy_or_nonneutral_admission_refuses_before_replacing_any_old_intent(self):
        self.assertEqual(admit("path_to", 2, idle=False), "refuse_before_replace")
        self.assertEqual(admit("path_to", 2, neutral=False), "refuse_before_replace")
        c = Controller()
        before = (c.writes, c.result, c.release, c.expected)
        result = admit("move", 4, active_tight=c.result is None)
        self.assertEqual(result, "refuse_before_replace")
        self.assertEqual((c.writes, c.result, c.release, c.expected), before)

    def test_new_short_route_guard_rejects_partial_escape_start_and_excess_arc(self):
        self.assertTrue(route_bound(0, 107.404, 2, [0, 107.404]))
        self.assertFalse(route_bound(0, 10, 2, [0, 0]))  # native complete12 could say true
        self.assertFalse(route_bound(0, 30, 2, [24, 30]))
        self.assertFalse(route_bound(0, 10, 2, [0, 80, -80, 10]))
        self.assertFalse(route_bound(0, 10, 2, [0, math.nan, 10]))

    def test_long_original_approach_is_not_rejected_by_new_correction_arc_cap(self):
        self.assertFalse(route_bound(0, 600, 2, [0, 600]))
        c, position, _ = queued_world(0, distance=600)
        self.assertEqual(c.result, "done")
        self.assertLessEqual(abs(position - c.goal), 2)

    def test_queued_world_zero_through_three_updates_requires_actual_settling(self):
        for lag in range(4):
            for direction in (-1, 1):
                with self.subTest(lag=lag, direction=direction):
                    c, position, records = queued_world(lag, direction=direction)
                    self.assertEqual(c.result, "done")
                    self.assertLessEqual(abs(position - c.goal), 2)
                    self.assertGreaterEqual(c.holds, 5)
                    self.assertLessEqual(c.holds, 12)
                    self.assertLessEqual(c.corrections, 4)
                    self.assertTrue(all(writes <= 1 for _, _, writes in records))
                    self.assertEqual(records[-1][0]["velocity"], 0)

    def test_different_and_changing_speeds_never_grant_false_done(self):
        for gain in (.5, 2, 3.915, 7):
            for lag in range(4):
                with self.subTest(gain=gain, lag=lag):
                    c, position, _ = queued_world(lag, gain=gain,
                        speed_change=lambda tick: gain if tick < 18 else gain * 1.4)
                    self.assertIsNotNone(c.result)
                    if c.result == "done":
                        self.assertLessEqual(abs(position - c.goal), 2)
                    self.assertLessEqual(c.corrections, 4)
                    self.assertLessEqual(c.holds, 13)

    def test_observed_extra_motion_cannot_complete_at_first_inside_point(self):
        c = Controller(goal=-48, position=-46.319)
        self.assertEqual(c.step(observation(c, -46.319, 33, velocity=-3.708)), 0)
        self.assertIsNone(c.result)
        self.assertEqual(c.step(observation(c, -50.234, 66, velocity=0)), 0)
        self.assertIsNone(c.result)
        for now in (99, 132, 165):
            c.step(observation(c, -50.234, now))
        self.assertEqual(c.corrections, 1)
        self.assertNotEqual(c.result, "done")

    def test_raw_zero_velocity_and_neutral_samples_required_inside_band(self):
        c = Controller(position=-1)
        for tick in range(1, 14):
            c.step(observation(c, -1, tick * 33, velocity=.00001))
        self.assertEqual(c.result, "hold_budget")

    def test_already_inside_can_finish_only_after_consecutive_fresh_quiet_reads(self):
        c = Controller(position=-1)
        for tick in range(1, 5):
            c.step(observation(c, -1, tick * 33))
            self.assertIsNone(c.result)
        c.step(observation(c, -1, 165))
        self.assertEqual(c.result, "done")

    def test_foreign_takeover_checked_before_paused_stop_or_failure_cleanup(self):
        for field, value in (("held_ms", 1), ("qa_busy", True), ("reflex_fire", 1),
                             ("reflex_potion", 1), ("skillkeys", "4"), ("releasing", True)):
            for control in ("paused", "cancel", "alive"):
                with self.subTest(field=field, control=control):
                    c = Controller()
                    row = observation(c, -107.404, 33, **{field: value, control: control != "alive"})
                    c.step(row)
                    self.assertEqual(c.result, "foreign_or_unknown")
                    self.assertFalse(c.release)
                    self.assertEqual(c.writes, 0)

    def test_counter_buffer_current_and_button_takeovers_schedule_no_old_release(self):
        for changes in (dict(writes=1), dict(tracked=False), dict(current_is_callback=False),
                        dict(same_buffers=False), dict(same_gamepad=False), dict(buttons=["dash"]),
                        dict(moves=[.1]), dict(sole=False)):
            with self.subTest(changes=changes):
                c = Controller()
                c.step(observation(c, -107.404, 33, **changes))
                self.assertEqual(c.result, "foreign_or_unknown")
                self.assertFalse(c.release)

    def test_actor_world_missing_or_replaced_during_hold_has_no_old_neutral_tail(self):
        for changes in (dict(world="other"), dict(actor=None), dict(actor="replacement")):
            c = Controller(position=-1)
            c.step(observation(c, -1, 33))
            before = c.writes
            c.step(observation(c, -1, 66, **changes))
            self.assertFalse(c.release)
            self.assertEqual(c.writes, before)

    def test_owned_cancel_death_and_pause_end_old_state_without_later_writes(self):
        for changes in (dict(cancel=True), dict(alive=False), dict(paused=True)):
            c = Controller(position=-1)
            c.step(observation(c, -1, 33))
            c.step(observation(c, -1, 66, **changes))
            before = c.writes
            self.assertTrue(c.release)
            c.step(observation(c, -1, 99))
            self.assertEqual(c.writes, before)

    def test_equal_regressing_negative_clock_and_invalid_dt_refuse_credit(self):
        for changes in (dict(now=0), dict(now=-1), dict(dt=0), dict(dt=-1), dict(dt=251)):
            c = Controller(position=-1)
            c.step(observation(c, -1, 33, **changes))
            self.assertEqual(c.result, "observation")
            self.assertEqual(c.writes, 0)

    def test_nonfinite_position_velocity_and_changed_original_goal_refuse_credit(self):
        for changes in (dict(position=math.nan), dict(velocity=math.inf),
                        dict(goal=.01), dict(tol=2.01)):
            c = Controller(position=-1)
            c.step(observation(c, -1, 33, **changes))
            self.assertEqual(c.result, "observation")

    def test_deadline_persists_across_hold_and_correction(self):
        c = Controller(position=-1, deadline=150)
        for tick, position in enumerate((-1, -3, -3, -3, -3), 1):
            c.step(observation(c, position, tick * 33))
        self.assertEqual(c.result, "timeout")
        self.assertEqual(c.elapsed, 165)

    def test_blocked_or_substituted_correction_is_not_arrival(self):
        for changes in (dict(routed=False), dict(route_goal=.1)):
            c = Controller(position=-1)
            for tick in range(1, 6):
                c.step(observation(c, -1 if tick == 1 else -3, tick * 33, **changes))
            self.assertEqual(c.result, "no_route")
            self.assertEqual(c.corrections, 1)

    def test_cumulative_hold_and_correction_budgets_never_reset_on_reentry(self):
        c = Controller(position=-1)
        c.holds, c.corrections, c.neutrals, c.quiet, c.holding = 12, 3, 4, 2, True
        c.step(observation(c, -3, 33))
        self.assertEqual(c.result, "hold_budget")
        d = Controller(position=-3)
        d.corrections, d.holding, d.neutrals, d.quiet = 4, True, 4, 2
        d.step(observation(d, -3, 33))
        self.assertEqual(d.result, "correction_budget")

    def test_zero_motion_unknown_gain_fails_instead_of_inventing_progress(self):
        c = Controller(position=-10)
        for tick in range(1, 11):
            c.step(observation(c, -10, tick * 33))
        self.assertEqual(c.result, "no_motion")
        self.assertEqual(c.peak, 0)
        self.assertLessEqual(c.cap, .125)

    def test_stale_or_missing_collision_selected_direction_refuses_movement(self):
        for direction in (0, .5, math.nan):
            c = Controller()
            c.step(observation(c, -107.404, 33, direction=direction))
            self.assertEqual(c.result, "route_direction")
            self.assertEqual(c.writes, 0)

    def test_minimum_speed_and_oscillation_must_finish_bounded_without_false_pass(self):
        for lag in range(4):
            c, position, _ = queued_world(lag, min_speed=8)
            self.assertIsNotNone(c.result)
            if c.result == "done":
                self.assertLessEqual(abs(position - c.goal), 2)
            self.assertLessEqual(c.holds, 13)
            self.assertLessEqual(c.corrections, 4)

    def test_command_cap_never_increases_and_each_observation_writes_at_most_once(self):
        c, _, records = queued_world(3)
        self.assertTrue(all(count in (0, 1) for _, _, count in records))
        nonzero = [abs(command) for _, command, _ in records if command]
        self.assertTrue(all(a >= b for a, b in zip(nonzero, nonzero[1:])))
        self.assertIsNotNone(c.result)


if __name__ == "__main__":
    unittest.main()
