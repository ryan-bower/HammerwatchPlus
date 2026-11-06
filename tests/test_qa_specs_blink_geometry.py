"""Guard the geometry requirement exposed by clipped Far Step endpoints."""
import unittest

from gamelab.bots.qa_specs_arcane_ranks import blink_lanes


class BlinkGeometryTests(unittest.TestCase):
    def test_wide_open_floor_has_a_centered_full_length_lane(self):
        grid = {"size": 41, "step": 8, "rows": ["." * 41 for _ in range(41)]}
        self.assertIn((0, 0, 1, 0), blink_lanes(grid))

    def test_narrow_center_ray_gap_cannot_certify_wide_teleport(self):
        grid = {"size": 41, "step": 8, "rows": ["." * 41 if 18 <= y <= 22 else "#" * 41 for y in range(41)]}
        self.assertFalse(blink_lanes(grid))

    def test_partial_terrain_cannot_be_treated_as_free_space(self):
        self.assertFalse(blink_lanes({"size": 41, "step": 8, "rows": ["." * 40] * 41}))


if __name__ == "__main__":
    unittest.main()
