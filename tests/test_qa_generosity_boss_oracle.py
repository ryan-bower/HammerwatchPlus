"""Fake-observation negative controls; these cannot establish gameplay evidence."""
import copy
import unittest

from gamelab.bots.qa_generosity_boss_oracle import (
    held_fraction_ok, precast_active_observed, pre_active_then_suppressed,
    motion_distance, roster_matches, stays, target_matches,
)
from gamelab.bots.plan_generosity import Checks


def held_observation():
    return {
        "boss": "boss_armory:wraith_scythe", "spawned": True, "held": True,
        "refused": "", "kept": True, "post_suppressed": True, "boss_cd": True, "spent": True,
        "armor0": True, "beams": 4, "errors": [],
        "requested_id": 101, "pick": {"picked": 101}, "held_id": 101, "cast_ids": [101],
        "pre_actor": {"unit": 101, "dead": False, "casting": ["MeleeAttack"]},
        "hold_samples": [{"holding": 101, "casting": 0}, {"holding": 101, "casting": 0}],
        "positions": [{"unit": 101, "x": 20, "y": 30}, {"unit": 101, "x": 21, "y": 31}],
    }


class GenerosityBossOracleTests(unittest.TestCase):
    def aggregate(self, rows, expected):
        class Flags:
            boss_flags = Checks.boss_flags

            def __init__(self):
                self.out, self.flags = {}, {}

            def flag(self, name, ok, detail):
                self.flags[name] = bool(ok)

        collector = Flags()
        collector.boss_flags("test", rows, expected)
        return collector.flags

    def test_aggregate_rejects_empty_observations_instead_of_all_empty_pass(self):
        flags = self.aggregate([], [])
        self.assertTrue(flags)
        self.assertFalse(any(flags.values()))

    def test_aggregate_distinguishes_target_mismatch_from_actual_motion_failure(self):
        row = held_observation()
        self.assertTrue(all(self.aggregate([row], [row["boss"]]).values()))
        row.update(held_id=202, cast_ids=[202], pick={"picked": 202})
        row["hold_samples"] = [{"holding": 202, "casting": 0}]
        row["positions"] = [{"unit": 202, "x": 0, "y": 0}, {"unit": 202, "x": 0, "y": 0}]
        flags = self.aggregate([row], [row["boss"]])
        self.assertFalse(flags["test_target_identity"])
        self.assertFalse(flags["test_pre_active_then_suppressed"])
        self.assertFalse(flags["test_armor_0"])
        self.assertTrue(flags["test_stays"])
        self.assertTrue(flags["test_motion_observed"])

    def test_complete_matching_hold_and_motion_are_accepted(self):
        row = held_observation()
        self.assertTrue(target_matches(row))
        self.assertTrue(precast_active_observed(row))
        self.assertEqual(motion_distance(row), 2)
        self.assertTrue(stays(row))

    def test_sibling_held_while_requested_wraith_moves_is_identity_failure(self):
        row = held_observation()
        row.update(pick={"picked": 202}, held_id=202, cast_ids=[202])
        row["hold_samples"] = [{"holding": 202, "casting": 0}]
        # The sibling was actually held still. Its motion can be measured, but
        # cannot establish that the requested scythe was held or failed to stay.
        row["positions"] = [{"unit": 202, "x": 20, "y": 30}, {"unit": 202, "x": 20, "y": 30}]
        self.assertFalse(target_matches(row))
        self.assertTrue(stays(row))

    def test_held_actor_really_moving_still_fails_original_four_pixel_limit(self):
        row = held_observation()
        row["positions"][1]["x"] = 243  # historical failure magnitude, 223px
        self.assertTrue(target_matches(row))
        self.assertFalse(stays(row))
        row["positions"][1].update(x=24, y=30)
        self.assertFalse(stays(row))
        row["positions"][1].update(x=23.9, y=30)
        self.assertTrue(stays(row))

    def test_missing_duplicate_stale_or_changed_cast_identity_fails(self):
        for change in ({"cast_ids": []}, {"cast_ids": [101, 101]}, {"cast_ids": [202]},
                       {"pick": {}}, {"requested_id": None}, {"requested_id": True},
                       {"hold_samples": []}, {"hold_samples": [{"holding": 202}]}):
            with self.subTest(change=change):
                row = held_observation()
                row.update(change)
                self.assertFalse(target_matches(row))

    def test_missing_or_wrong_actor_positions_cannot_be_zero_movement(self):
        for positions in ([], [{"unit": 101, "x": 0, "y": 0}],
                          [{"unit": 101, "x": 0, "y": 0}, None],
                          [{"unit": 101, "x": 0, "y": 0}, {"unit": 202, "x": 0, "y": 0}],
                          [{"unit": 101, "x": 0, "y": 0}, {"unit": 101, "x": float("nan"), "y": 0}]):
            with self.subTest(positions=positions):
                row = held_observation()
                row["positions"] = positions
                self.assertIsNone(motion_distance(row))
                self.assertFalse(stays(row))

    def test_empty_missing_duplicate_or_extra_rosters_refuse(self):
        a = held_observation()
        b = copy.deepcopy(a)
        b["boss"] = "boss_armory:wraith_staff"
        expected = [a["boss"], b["boss"]]
        self.assertTrue(roster_matches([a, b], expected))
        for rows, wanted in (([], []), ([], expected), ([a], expected), ([a, a], expected),
                             ([a, b, b], expected), ([a, b], expected + [b["boss"]])):
            with self.subTest(rows=rows, expected=wanted):
                self.assertFalse(roster_matches(rows, wanted))

    def test_one_selected_refused_boss_cannot_pass_held_most(self):
        self.assertFalse(held_fraction_ok([]))
        self.assertFalse(held_fraction_ok([{"held": False}]))
        self.assertTrue(held_fraction_ok([{"held": True}]))
        self.assertFalse(held_fraction_ok([{"held": True}, {"held": False}]))
        self.assertTrue(held_fraction_ok([{"held": True}, {"held": True}, {"held": False}]))

    def test_idle_passive_wrong_actor_or_channel_stop_is_not_interruption_proof(self):
        for actor in ({"unit": 101, "dead": False, "casting": []},
                      {"unit": 101, "dead": False, "casting": ["TriggeredSkill", "AuraSkill"]},
                      {"unit": 101, "dead": False, "casting": ["ChannelingSpewSkill"]},
                      {"unit": 202, "dead": False, "casting": ["MeleeAttack"]},
                      {"unit": 101, "dead": True, "casting": ["MeleeAttack"]}):
            with self.subTest(actor=actor):
                row = held_observation()
                row["pre_actor"] = actor
                self.assertFalse(precast_active_observed(row))

    def test_natural_end_before_castpoint_gets_only_sampled_state_credit(self):
        row = held_observation()
        row["timeline"] = [
            {"at": 1000, "unit": 101, "casting": "MeleeAttack"},
            {"at": 1010, "unit": 101, "natural_end": True},
            {"at": 1200, "fury_castpoint": True},
        ]
        self.assertTrue(pre_active_then_suppressed(row))
        flags = self.aggregate([row], [row["boss"]])
        self.assertTrue(flags["test_pre_active_then_suppressed"])
        self.assertNotIn("test_attack_cut", flags)
        self.assertNotIn("test_interruption_proven", flags)


if __name__ == "__main__":
    unittest.main()
