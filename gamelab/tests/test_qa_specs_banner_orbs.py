"""Independent negative controls for Bannerlord effect/cooldown oracles."""
import unittest

from gamelab.bots.qa_specs_banner_orbs import (
    cooldown_matches, cooldown_total, crest_matches, provisions_expected,
)


class BannerOrbOracles(unittest.TestCase):
    def test_vulnerability_rounding_and_wrong_quality_rejected(self):
        self.assertTrue(crest_matches(25, 28, 1))  # native25*1.1=27.5 rounds up
        self.assertTrue(crest_matches(25, 30, 2))
        self.assertTrue(crest_matches(25, 33, 3))
        self.assertTrue(crest_matches(24.9996, 27.9996, 1))  # float HP readback of integer strikes
        self.assertFalse(crest_matches(25.25, 28, 1))  # mixed/variable strikes cannot calibrate one packet
        self.assertFalse(crest_matches(25, 25, 1))
        self.assertFalse(crest_matches(25, 30, 3))
        self.assertFalse(crest_matches(None, 28, 1))

    def test_actual_hud_count_scaling_and_cap(self):
        self.assertEqual([provisions_expected(2, q) for q in (0, 1, 2, 3)], [0, 2, 4, 6])
        self.assertEqual(provisions_expected(10, 3), 30)
        self.assertEqual(provisions_expected(11, 3), 30)
        self.assertEqual(provisions_expected(31, 1), 30)
        self.assertIsNone(provisions_expected(-1, 2))
        self.assertIsNone(provisions_expected(2, 4))

    def test_clock_corrected_native_cooldown(self):
        state = {"ok": True, "now": 1833, "skills": [{"id": "warcry", "cd": 10927}]}
        self.assertEqual(cooldown_total(1000, state, "warcry"), 11760)
        self.assertTrue(cooldown_matches(12000, 11760, 2))
        self.assertFalse(cooldown_matches(12000, 12000, 2))
        self.assertFalse(cooldown_matches(12000, 11760, 4))
        self.assertTrue(cooldown_matches(12000, 8400, 30))
        self.assertFalse(cooldown_matches(12000, 8040, 30))

    def test_missing_or_truncated_native_evidence_cannot_pass(self):
        self.assertIsNone(cooldown_total(100, {"ok": True, "now": 200, "skills": []}, "warcry"))
        self.assertIsNone(cooldown_total(100, {"ok": True, "now": 200, "truncated": True,
                                               "skills": [{"id": "warcry", "cd": 100}]}, "warcry"))
        self.assertIsNone(cooldown_total(100, {"ok": True, "now": 99,
                                               "skills": [{"id": "warcry", "cd": 100}]}, "warcry"))
        self.assertFalse(cooldown_matches(None, 1000, 2))


if __name__ == "__main__":
    unittest.main()
