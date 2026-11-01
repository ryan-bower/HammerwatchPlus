"""Pure external-request/cleanup controls; these models do not prove live hits."""
from copy import deepcopy
import math
import unittest

from gamelab.bots.qa_firearms_input_geometry import target_body_cursor, cursor_binding


def fixture():
    state = {"ok": True, "phase": "mission", "player": {
        "spawned": True, "dead": False, "x": -447.417, "y": .35}}
    nearby = {"ok": True, "truncated": 0, "units": [{"unit": 27386,
        "name": "doodads/generic/target_dummy_normal.unit", "dead": False,
        "hpMax": 10000000, "hpExact": 10000000, "x": -367.417, "y": .35}]}
    return state, nearby


def native_cursor(world=(-367.417, -10.65)):
    accepted = {"ok": True, "id": "c67", "tag": "fs-sequence-shots", "player": 30031,
                "skill": "-", "target_x": world[0], "target_y": world[1]}
    cursor = {"valid": True, "sequence": {"valid": True}, "accepted": deepcopy(accepted),
              "terminal": {k: accepted[k] for k in ("id", "tag", "player")},
              "samples": [{"world_x": world[0], "world_y": world[1], "gamepad": False},
                          {"world_x": world[0], "world_y": world[1], "gamepad": False}],
              "chunks": [{"restore": [{"restored": True, "owned_last_value": True,
                                          "already_neutral": False}]}]}
    return accepted, cursor


class BodyFixtureTests(unittest.TestCase):
    def test_actual_east_target_pins_its_visible_body_not_its_feet(self):
        state, nearby = fixture()
        result = target_body_cursor(state, nearby, 27386, (1, 0))
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["world"][0], -367.417)
        self.assertAlmostEqual(result["world"][1], -10.65)
        self.assertEqual(result["target"]["unit"], 27386)

    def test_height_compensation_is_world_vertical_at_all_compass_angles(self):
        for degrees in range(0, 360, 45):
            with self.subTest(degrees=degrees):
                state, nearby = fixture()
                p, t = state["player"], nearby["units"][0]
                d = (math.cos(math.radians(degrees)), math.sin(math.radians(degrees)))
                t.update(x=p["x"] + 80*d[0], y=p["y"] + 80*d[1])
                result = target_body_cursor(state, nearby, 27386, d)
                self.assertTrue(result["valid"])
                ray = (result["world"][0] - p["x"], result["world"][1] - (p["y"]-11))
                self.assertAlmostEqual(ray[0], 80*d[0])
                self.assertAlmostEqual(ray[1], 80*d[1])

    def test_missing_foreign_or_duplicate_target_is_refused(self):
        for alteration in ("missing", "foreign", "duplicate"):
            with self.subTest(alteration=alteration):
                state, nearby = fixture()
                if alteration == "missing": nearby["units"] = []
                elif alteration == "foreign": nearby["units"][0]["unit"] = 27387
                else: nearby["units"].append(deepcopy(nearby["units"][0]))
                self.assertFalse(target_body_cursor(state, nearby, 27386, (1, 0))["valid"])

    def test_truncated_or_absent_target_query_is_refused(self):
        for key, value in (("ok", False), ("truncated", 1), ("truncated", None)):
            with self.subTest(key=key, value=value):
                state, nearby = fixture(); nearby[key] = value
                self.assertFalse(target_body_cursor(state, nearby, 27386, (1, 0))["valid"])

    def test_wrong_target_health_identity_or_position_is_refused(self):
        for key, value in (("name", "target_dummy_other.unit"), ("dead", True),
                           ("hpMax", 500), ("hpExact", 9999999), ("x", -300), ("y", float("nan"))):
            with self.subTest(key=key, value=value):
                state, nearby = fixture(); nearby["units"][0][key] = value
                self.assertFalse(target_body_cursor(state, nearby, 27386, (1, 0))["valid"])

    def test_missing_or_dead_shooter_is_refused(self):
        for key, value in (("spawned", False), ("dead", True), ("x", None)):
            with self.subTest(key=key, value=value):
                state, nearby = fixture(); state["player"][key] = value
                self.assertFalse(target_body_cursor(state, nearby, 27386, (1, 0))["valid"])

    def test_invalid_direction_or_unit_identity_is_refused(self):
        state, nearby = fixture()
        for d in ((0, 0), (2, 0), (float("inf"), 0), (), None):
            with self.subTest(direction=d):
                self.assertFalse(target_body_cursor(state, nearby, 27386, d)["valid"])
        self.assertFalse(target_body_cursor(state, nearby, True, (1, 0))["valid"])
        self.assertFalse(target_body_cursor(None, nearby, 27386, (1, 0))["valid"])
        self.assertFalse(target_body_cursor(state, None, 27386, (1, 0))["valid"])


class CursorBindingTests(unittest.TestCase):
    def test_matching_strict_pin_readback_and_owned_restore_are_required(self):
        accepted, cursor = native_cursor()
        self.assertTrue(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_internally_consistent_foreign_world_pin_is_refused(self):
        accepted, cursor = native_cursor((-800, -200))
        self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_feet_pin_is_refused_even_with_consistent_native_readback(self):
        accepted, cursor = native_cursor((-367.417, .35))
        self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_missing_or_wrong_pin_acknowledgement_is_refused(self):
        for key, value in (("ok", False), ("skill", "hwp_fs_frag"), ("target_x", None),
                           ("player", True), ("id", "")):
            with self.subTest(key=key, value=value):
                accepted, cursor = native_cursor(); accepted[key] = value
                self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_missing_or_incorrect_per_frame_readback_is_refused(self):
        for value in ([], [{"world_x": -800, "world_y": -200, "gamepad": False}],
                      [{"world_x": float("nan"), "world_y": -10.65, "gamepad": False}]):
            with self.subTest(samples=value):
                accepted, cursor = native_cursor(); cursor["samples"] = value
                self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_foreign_native_actor_or_sequence_identity_is_refused(self):
        for section in ("accepted", "terminal"):
            for key, value in (("id", "other"), ("tag", "other"), ("player", 30032)):
                with self.subTest(section=section, key=key):
                    accepted, cursor = native_cursor(); cursor[section][key] = value
                    self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_strict_collector_or_button_contract_failure_is_refused(self):
        for section in ("cursor", "sequence"):
            with self.subTest(section=section):
                accepted, cursor = native_cursor()
                (cursor if section == "cursor" else cursor["sequence"])["valid"] = False
                self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_missing_unrestored_or_unowned_cleanup_is_refused(self):
        for receipt in (None, [], [{"restored": False, "owned_last_value": True}],
                        [{"restored": True, "owned_last_value": False, "already_neutral": False}]):
            with self.subTest(receipt=receipt):
                accepted, cursor = native_cursor(); cursor["chunks"][0]["restore"] = receipt
                self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_already_neutral_owned_cleanup_is_accepted(self):
        accepted, cursor = native_cursor()
        cursor["chunks"][0]["restore"] = [{"restored": True, "owned_last_value": False, "already_neutral": True}]
        self.assertTrue(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])

    def test_gamepad_or_nonfinite_external_point_is_refused(self):
        accepted, cursor = native_cursor(); cursor["samples"][0]["gamepad"] = True
        self.assertFalse(cursor_binding(accepted, cursor, (-367.417, -10.65))["valid"])
        self.assertFalse(cursor_binding(accepted, cursor, (float("inf"), 0))["valid"])
        self.assertFalse(cursor_binding(None, None, (-367.417, -10.65))["valid"])


if __name__ == "__main__":
    unittest.main()
