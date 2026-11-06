"""Negative controls for native first-impact attribution, not gameplay evidence."""
import copy
import unittest

from gamelab.bots.qa_specs_wizard_ranks import MAX_HP, TT, evaluate_impact


def observation():
    targets = [{"unit": unit, "valid": True, "dead": False, "hpMax": MAX_HP, "hpExact": MAX_HP}
               for unit in range(1, 7)]
    before = {row["unit"]: dict(row) for row in targets}
    first = copy.deepcopy(targets)
    for row in first[:3]:
        row["hpExact"] -= 5
    def snapshot(rows, mana, cooldown):
        return {"targets": rows, "skill_crit": 0, "spell_crit": 0, "mana": mana, "cooldown": cooldown}
    return before, {"complete": True, "error": "", "truncated": False, "ms": 924, "frames": 28,
                    "input_frames": 19, "input_at": 1000, "first_at": 1500,
                    "before": snapshot(targets, 250, 0), "first": snapshot(first, 210, -30),
                    "after": snapshot(first, 211, 11700)}


class ImpactOracleTests(unittest.TestCase):
    def test_complete_real_first_group_accepts_three_of_six(self):
        before, data = observation()
        setup, hit, drops = evaluate_impact(data, before, 3, TT)
        self.assertTrue(setup and hit)
        self.assertEqual(drops, {1: 5, 2: 5, 3: 5})

    def test_later_zap_sweeping_extra_target_cannot_pass_first_group(self):
        before, data = observation()
        data["first"]["targets"][3]["hpExact"] -= 5
        self.assertFalse(evaluate_impact(data, before, 3, TT)[1])

    def test_disappeared_target_cannot_count_as_damage(self):
        before, data = observation()
        data["first"]["targets"].pop()
        self.assertFalse(evaluate_impact(data, before, 3, TT)[0])

    def test_ack_without_actual_input_cannot_pass(self):
        before, data = observation()
        data["input_frames"] = 0
        self.assertFalse(evaluate_impact(data, before, 3, TT)[0])

    def test_uncontrolled_critical_damage_cannot_pass_rank_oracle(self):
        before, data = observation()
        data["first"]["spell_crit"] = 0.03
        self.assertFalse(evaluate_impact(data, before, 3, TT)[0])


if __name__ == "__main__":
    unittest.main()
