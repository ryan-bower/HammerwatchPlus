"""Independent integer damage controls for natural single-target zap groups."""
import unittest

from gamelab.bots.qa_specs_wizard_orbs import hp_pulses, matching_coefficients, pulse_damage, rounded


def curve(per, actual=None):
    values = actual if actual is not None else [pulse_damage(.9, per, index) for index in range(10)]
    return {"per": per, "pulses": [{"damage": value} for value in values]}


class WizardOrbOracleTests(unittest.TestCase):
    def test_pinned_positive_damage_round_avoids_bankers_rounding(self):
        self.assertEqual(rounded(2.5), 3)
        self.assertEqual(rounded(.1), 1)
        self.assertEqual(rounded(0), 0)

    def test_source_curves_share_native_coefficient_and_reach_cap(self):
        cases = [curve(per) for per in (0, .04, .07)]
        self.assertTrue(matching_coefficients(cases, [.9]))
        self.assertEqual([pulse_damage(.9, per, 5) for per in (0, .04, .07)], [27, 39, 45])

    def test_constant_damage_cannot_claim_overcharge(self):
        self.assertFalse(matching_coefficients([curve(.04, [27] * 10)], [.85, .9, .95]))

    def test_wrong_quality_curve_cannot_pass_common_model(self):
        self.assertFalse(matching_coefficients([curve(0), curve(.07, [pulse_damage(.9, .04, i) for i in range(10)])], [.9]))

    def test_stack_only_observer_events_do_not_invent_hp_hits(self):
        rows = [{"target_valid": True, "target_hpExact": hp, "now": now, "elapsed": now}
                for now, hp in ((0, 15000), (33, 15000), (300, 14973), (330, 14973), (550, 14946))]
        self.assertEqual([row["damage"] for row in hp_pulses({"events": rows})], [27, 27])


if __name__ == "__main__":
    unittest.main()
