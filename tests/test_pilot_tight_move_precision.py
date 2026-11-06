"""UNRUN binary32 precision policy models; no AS/project/file/native IO.

The retained row proves only X's first mismatch. Y was short-circuited and is
not supplied here as an actual observation. These tests cannot prove an AS
getter, native normalization, sole-writer arbitration, phase or arrival.
"""
import math
import struct
import unittest


# Exact retained seq6/seq8 scalar projection, not a future runtime default.
CAPTURE = {
    "run": "20261031-110413-fix-firearms-poses-lab", "intent_id": "c48",
    "player": 29716, "boots": 1, "lvl": 2,
    "post": {"seq": 6, "callback": 551, "entry": 1, "writes": 93, "expected_writes": 93,
             "mx": -0.999999940, "my": -0.000001082},
    "failure": {"seq": 8, "callback": 552, "entry": 2, "writes": 93, "expected_writes": 93,
                "first": "move_x", "actual": -1.0, "expected": -0.999999940,
                "my": "unobserved", "slot": 0, "current_slot": 0, "callback_slot": 0,
                "handle_same": True, "pad": False, "saved_pad": False,
                "down_seen": 255, "down_true": 0, "pressed_seen": 255, "pressed_true": 0},
}


def binary32(value):
    return struct.unpack("!f", struct.pack("!f", value))[0]


def from_bits(bits):
    return struct.unpack("!f", struct.pack("!I", bits))[0]


def same_component(actual, expected):
    """Scalar reference model of the proposed bounded AS comparison."""
    if not (-1 <= actual <= 1 and -1 <= expected <= 1):
        return False
    if actual == expected:
        return True
    if actual == 0 or expected == 0 or (actual < 0) != (expected < 0):
        return False
    magnitude = max(abs(actual), abs(expected))
    gap, edge = 2.0 ** -24, 0.5
    for _ in range(125):
        if magnitude > edge:
            break
        gap *= 0.5
        edge *= 0.5
    return abs(actual - expected) <= gap


def first_guard_failure(state, get_x, get_y):
    """Selected cached-owner schema, then original ordered X/Y reads."""
    for key in ("actor_world", "sole_player", "writer_idle", "write_counter", "current_callback",
                "input_count", "input_handle", "buttons_clear", "pad_same"):
        if state.get(key) is not True:
            return key
    if not same_component(get_x(), state["expected_x"]):
        return "move_x"
    if not same_component(get_y(), state["expected_y"]):
        return "move_y"
    return ""


def clean_state():
    return dict.fromkeys(("actor_world", "sole_player", "writer_idle", "write_counter", "current_callback",
                          "input_count", "input_handle", "buttons_clear", "pad_same"), True) | {
                              "expected_x": -1.0, "expected_y": 0.0}


class TightMovePrecisionTests(unittest.TestCase):
    def test_retained_x_roundtrips_to_one_adjacent_binary32_value(self):
        failed = CAPTURE["failure"]
        expected = binary32(failed["expected"])
        actual = binary32(failed["actual"])
        self.assertEqual(expected, -from_bits(0x3F7FFFFF))
        self.assertEqual(actual, -from_bits(0x3F800000))
        self.assertEqual(abs(actual - expected), 2.0 ** -24)
        self.assertNotEqual(actual, expected)  # old exact comparison rejects
        self.assertTrue(same_component(actual, expected))

    def test_decimal_telemetry_is_not_the_live_guard_operand(self):
        text_value = CAPTURE["failure"]["expected"]
        self.assertNotEqual(text_value, binary32(text_value))
        # Nine-decimal serialization changes the displayed difference slightly.
        # The proposed AS helper compares cached native operands, never JSON.
        self.assertGreater(abs(-1 - text_value), 2.0 ** -24)

    def test_captured_y_is_unobserved_and_cannot_grant_whole_guard_pass(self):
        self.assertEqual(CAPTURE["failure"]["my"], "unobserved")
        state = clean_state() | {"expected_x": binary32(CAPTURE["failure"]["expected"])}
        calls = []
        def unavailable_y():
            calls.append("y")
            raise RuntimeError("retained Y was not evaluated")
        with self.assertRaisesRegex(RuntimeError, "not evaluated"):
            first_guard_failure(state, lambda: -1.0, unavailable_y)
        self.assertEqual(calls, ["y"])

    def test_one_step_accepted_two_steps_rejected_at_independent_bit_patterns(self):
        for bits in (0x3F800000, 0x3F400000, 0x3F000000, 0x3E800000, 0x35800000, 0x00800000):
            for sign in (-1, 1):
                edge, one, two = (sign * from_bits(bits - n) for n in (0, 1, 2))
                with self.subTest(bits=hex(bits), sign=sign):
                    self.assertTrue(same_component(edge, one))
                    self.assertTrue(same_component(one, edge))
                    self.assertFalse(same_component(edge, two))

    def test_binade_boundary_does_not_admit_two_smaller_inward_steps(self):
        for edge_bits in (0x3F000000, 0x3E800000, 0x3E000000):
            edge, two_inward = from_bits(edge_bits), from_bits(edge_bits - 2)
            self.assertFalse(same_component(edge, two_inward))
            self.assertEqual(edge - two_inward, math.ulp(edge) * (2.0 ** 29))

    def test_nonfinite_and_out_of_unit_range_rejected_even_when_equal(self):
        for value in (math.nan, math.inf, -math.inf, 1.0000001192092896, -1.0000001192092896, 2.0):
            with self.subTest(value=value):
                self.assertFalse(same_component(value, value))
                self.assertFalse(same_component(value, 1.0))

    def test_zero_remains_exact_and_direction_reversal_is_rejected(self):
        self.assertTrue(same_component(0.0, -0.0))
        self.assertTrue(same_component(-0.0, 0.0))
        for value in (from_bits(1), -from_bits(1), 2.0 ** -30, -2.0 ** -30):
            self.assertFalse(same_component(value, 0.0))
            self.assertFalse(same_component(0.0, value))
            self.assertFalse(same_component(value, -value))

    def test_subnormal_floor_is_one_step_and_not_a_zero_tolerance_floor(self):
        self.assertTrue(same_component(from_bits(2), from_bits(1)))
        self.assertFalse(same_component(from_bits(3), from_bits(1)))
        self.assertFalse(same_component(from_bits(1), 0.0))

    def test_material_change_is_rejected_across_several_component_scales(self):
        for expected in (1.0, -1.0, .5, -.5, .01, -.01, 1e-6, -1e-6):
            actual = expected * .9999
            self.assertFalse(same_component(actual, expected))

    def test_every_other_owner_guard_still_preempts_any_movement_read(self):
        for key in ("actor_world", "sole_player", "writer_idle", "write_counter", "current_callback",
                    "input_count", "input_handle", "buttons_clear", "pad_same"):
            for invalid in (False, None, "unobserved"):
                state = clean_state() | {key: invalid}
                def forbidden():
                    self.fail("movement read after an earlier failed guard")
                self.assertEqual(first_guard_failure(state, forbidden, forbidden), key)

    def test_first_material_x_failure_preserves_short_circuit_and_expected_state(self):
        state = clean_state()
        before = dict(state)
        def forbidden_y():
            self.fail("Y must remain unobserved after material X failure")
        self.assertEqual(first_guard_failure(state, lambda: -.9999, forbidden_y), "move_x")
        self.assertEqual(state, before)

    def test_y_is_independently_guarded_after_numerically_matching_x(self):
        state = clean_state() | {"expected_x": -from_bits(0x3F7FFFFF), "expected_y": binary32(1e-6)}
        self.assertEqual(first_guard_failure(state, lambda: -1.0, lambda: binary32(1.001e-6)), "move_y")
        self.assertEqual(state["expected_x"], -from_bits(0x3F7FFFFF))


if __name__ == "__main__":
    unittest.main()
