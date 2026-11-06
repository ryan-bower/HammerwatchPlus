"""Causal negative controls for the two-cast observer; never gameplay evidence."""
import unittest

from gamelab.bots.qa_specs_static_overlap import PHASES, evaluate


def observation():
    rows = []
    times = (33, 900, 924, 2000, 4400, 4700, 4800)
    positions = ([], [40], [40], [90, 145], [210, 270], [225, 285], [230, 290])
    health = (15000, 15000, 15000, 14980, 14900, 14889, 14880)
    stacks = (0, 1, 1, 3, 4, 4, 4)
    for i, (name, t, orbs, hp, stack) in enumerate(zip(PHASES, times, positions, health, stacks)):
        rows.append({"phase": name, "t": t, "now": 10000 + t, "stacks": stack,
                     "targets": [{"unit": unit, "valid": True, "dead": False, "hpMax": 15000, "hpExact": hp, "x": 180, "y": side}
                                 for unit, side in ((1, -15), (2, 0), (3, 15))],
                     "projectiles": [{"unit": -i - 1, "x": x, "y": 0} for i, x in enumerate(orbs)],
                     "crits": [] if i < 3 else [{"type": 11, "text": "11!", "born": 10000 + t - 50}],
                     "player_x": 0 if i < 2 else 100, "player_y": 0,
                     "tt_crit": 1, "spell_crit": 0, "mana": 250 if i == 0 else 205 if i < 3 else 155})
    samples = []
    for t in range(50, 4801, 50):
        cd = 0 if t < 650 or 900 <= t < 1550 else 12000 - t
        samples.append({"t": t, "tt_cd": cd, "stacks": 1 if t < 1000 else 2 if t < 1400 else 3 if t < 2600 else 4})
    return {"complete": True, "error": "", "retention_error": "", "truncated": False, "ms": 4800, "frames": len(samples),
            "first_input_at": 10033, "second_input_at": 10900, "first_input_frames": 19, "second_input_frames": 19,
            "cooldown_before_setup": 11600, "cooldown_after_setup": 0,
            "aim_x": 1, "aim_y": 0, "origin_x": 0, "origin_y": 0, "samples": samples, "phases": rows}


class OverlapOracleTests(unittest.TestCase):
    def test_both_independent_critical_damage_windows_are_required(self):
        self.assertTrue(all(ok for ok, _ in evaluate(observation()).values()))

    def test_original_three_stacks_does_not_pass(self):
        data = observation()
        for row in data["phases"]:
            if row["t"] >= 2600:
                row["stacks"] = 3
        for row in data["samples"]:
            if row["t"] >= 2600:
                row["stacks"] = 3
        result = evaluate(data)
        self.assertTrue(result["new_orb_crit"][0])
        self.assertTrue(result["old_orb_crit"][0])
        self.assertFalse(result["two_bonuses"][0])

    def test_new_orb_still_in_range_invalidates_old_attribution(self):
        data = observation()
        for row in data["phases"]:
            if row["t"] >= 4400:
                row["projectiles"][-1]["x"] = 235
        self.assertFalse(evaluate(data)["old_orb_crit"][0])

    def test_old_only_window_requires_new_hp_loss(self):
        data = observation()
        for target in data["phases"][-2]["targets"]:
            target["hpExact"] = 14900
        self.assertFalse(evaluate(data)["old_orb_crit"][0])

    def test_cast_acknowledgements_alone_do_not_prove_two_casts(self):
        data = observation()
        for row in data["samples"]:
            row["tt_cd"] = 0
        self.assertFalse(evaluate(data)["two_casts"][0])



class CurrentSpeedGeometryTests(unittest.TestCase):
    """Source-time model controls are not native critical/damage evidence."""

    @staticmethod
    def native_schedule():
        from pathlib import Path
        import re
        source = (Path(__file__).resolve().parents[1] /
                  "mods/gamelab-hands/scripts/GameLab/Verbs_qa_static_overlap.as").read_text()
        return tuple(int(re.search(r"!" + name + r" && m_t >= (\d+)", source).group(1))
                     for name in ("m_newOnly", "m_oldStart", "m_oldOnly"))

    @staticmethod
    def physics(schedule, first_delay=132, second_delay=132, overshoot=0):
        data = observation()
        times = (33, 900, 924, *schedule, 4800)
        for index, (row, when) in enumerate(zip(data["phases"], times)):
            when += overshoot if index in (3, 4, 5) else 0
            row["t"], row["now"] = when, 10000 + when
            if index:
                old = 8 + 2 * (when - 33 - first_delay) / 33
                positions = [old] if index < 3 else [old, 108 + 2 * (when - 900 - second_delay) / 33]
                row["projectiles"] = [{"unit": -k - 1, "x": x, "y": 0} for k, x in enumerate(positions)]
            if index >= 3:
                row["crits"] = [{"type": 11, "text": "11!", "born": row["now"] - 50}]
        return data

    def test_historical_fixed_times_fail_current_speed_geometry(self):
        result = evaluate(self.physics((2000, 4400, 4700)))
        self.assertTrue(result["two_casts"][0])
        self.assertFalse(result["new_orb_crit"][0])
        self.assertFalse(result["old_orb_crit"][0])

    def test_current_native_schedule_retains_both_isolated_windows(self):
        schedule = self.native_schedule()
        self.assertEqual(schedule[2] - schedule[1], 300)
        for first in (99, 132, 165):
            for second in (99, 132, 165):
                for overshoot in (0, 33):
                    with self.subTest(first=first, second=second, overshoot=overshoot):
                        result = evaluate(self.physics(schedule, first, second, overshoot))
                        self.assertTrue(all(ok for ok, _ in result.values()), result)

    def test_measured_positions_still_refuse_old_orb_in_new_window(self):
        data = self.physics(self.native_schedule())
        data["phases"][3]["projectiles"][0]["x"] = 125
        self.assertFalse(evaluate(data)["new_orb_crit"][0])

    def test_measured_positions_still_refuse_new_orb_in_old_window(self):
        data = self.physics(self.native_schedule())
        data["phases"][4]["projectiles"][1]["x"] = 250
        self.assertFalse(evaluate(data)["old_orb_crit"][0])

if __name__ == "__main__":
    unittest.main()
