"""Reject legal-looking lanes that cannot fit current Blink/Far Step consumers."""
import math
import unittest
from unittest.mock import patch

from gamelab.bots.qa_specs_arcane_ranks import blink, blink_lanes, blink_target_clearance, certified_lane


def grid(rect=None, blocked=(), **changes):
    """Native-shaped untruncated184/8 grid; rect coordinates are world offsets."""
    size, step, center = 47, 8, 23
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            px, py = (x-center)*step, (y-center)*step
            clear = rect is None or rect[0] <= px <= rect[1] and rect[2] <= py <= rect[3]
            row.append("." if clear and (px, py) not in blocked else "#")
        rows.append("".join(row))
    return {"ok": True, "truncated": False, "size": size, "step": step,
            "x": 0, "y": 0, "rows": rows, **changes}


class NativeFixture:
    """Readback-only fake. No game, native module or launcher is imported/run."""
    def __init__(self, fresh=None, wall_at=None, body=None, short_reply=False, blocked_target=None):
        self.at = (0, 0)
        self.initial = grid()
        self.fresh = fresh
        self.wall_at = wall_at
        self.body = body
        self.blocked_target = blocked_target
        self.out = {}
        self.short_reply = short_reply
        self.terrain_reads = 0
        self.commands = []
        self.g = self

    def pos(self):
        return self.at

    def skill_cd(self, skill):
        return 0

    def flag(self, key, value, detail=""):
        self.out[key] = value

    def gl(self, verb, *args):
        self.commands.append((verb, *args))
        if verb == "kill":
            return {"ok": True}
        if verb == "teleport":
            self.at = tuple(args)
            return {"ok": True}
        if verb == "terrain":
            self.terrain_reads += 1
            source = self.initial if self.terrain_reads == 1 or self.fresh is None else self.fresh
            return {**source, "x": self.at[0], "y": self.at[1]}
        raise AssertionError("unexpected native command: " + str((verb, args)))

    def gl_multi(self, commands):
        self.commands.extend(tuple(row) for row in commands)
        replies = []
        for row in commands:
            if row[0] == "rayhit":
                replies.append({"ok": True, "wall": self.wall_at is not None
                                and math.dist(row[1:3], row[3:5]) >= self.wall_at, "tile": False})
            elif row[0] == "bodies":
                if self.short_reply:
                    continue
                reply = {"ok": True, "truncated": False, "bodyCount": 1,
                         "fx": self.at[0], "fy": self.at[1], "tx": row[1], "ty": row[2], "step": row[3],
                         "bodies": [{"actor": True, "name": "local player"}]}
                if self.blocked_target is not None and math.dist(row[1:3], self.blocked_target) <= .001:
                    reply["bodies"] = [{"actor": False, "name": "thin obstruction at exact target"}]
                if self.body is not None:
                    reply.update(self.body)
                replies.append(reply)
            else:
                raise AssertionError("unexpected native probe: " + str(row))
        return replies


class BlinkGeometryTests(unittest.TestCase):
    def test_wide_open_floor_has_a_centered_full_length_lane(self):
        self.assertIn((0, 0, 1, 0), blink_lanes(grid(), centered=True))

    def test_old144px_corridor_cannot_certify_rare_far_step(self):
        # The old predicate accepted this exact centered footprint. Rare Far
        # Step's151.2px center would already be beyond its clear floor.
        self.assertFalse(blink_lanes(grid(rect=(-16, 144, -48, 48)), centered=True))

    def test_obstacle_beyond144_in_landing_target_envelope_rejects_lane(self):
        # At rare Far Step151.2, the outer radius30 target is38px lateral,
        # with a5px body. Its sampled152,-40 footprint must remain clear.
        lanes = blink_lanes(grid(blocked={(152, -40)}), centered=True)
        self.assertNotIn((0, 0, 1, 0), lanes)

    def test_narrow_center_ray_gap_cannot_certify_wide_teleport(self):
        self.assertFalse(blink_lanes(grid(rect=(-184, 184, -16, 16))))

    def test_partial_terrain_cannot_be_treated_as_free_space(self):
        malformed = grid()
        malformed["rows"][0] = malformed["rows"][0][:-1]
        self.assertFalse(blink_lanes(malformed))

    def test_truncated_or_failed_grid_cannot_certify_any_lane(self):
        for changes in ({"truncated": True}, {"ok": False}, {"step": 16}, {"size": 48}):
            with self.subTest(changes=changes):
                self.assertFalse(blink_lanes(grid(**changes)))

    def test_native_probes_cover_beyond_largest_landing_and_report_actual_center(self):
        fake = NativeFixture()
        origin, direction, detail = certified_lane(fake)
        self.assertEqual(origin, (0, 0))
        self.assertEqual(direction, (1, 0))
        rays = [row for row in fake.commands if row[0] == "rayhit"]
        bodies = [row for row in fake.commands if row[0] == "bodies"]
        self.assertEqual(len(rays), 3)
        self.assertEqual(len(bodies), 3)
        # Independent consumer envelope:151.2 rare endpoint plus9px landing
        # query plus8px sample margin. A144px native probe cannot cover it.
        self.assertTrue(all(math.dist(row[1:3], row[3:5]) >= 151.2 + 9 + 8 for row in rays))
        self.assertEqual(detail["verified_length"], 176)
        self.assertEqual(fake.terrain_reads, 2)
        self.assertTrue(all(row[1:] == (184, 8) for row in fake.commands if row[0] == "terrain"))

    def test_native_wall_after_old144px_range_still_refuses_fixture(self):
        fake = NativeFixture(wall_at=160)
        self.assertEqual(certified_lane(fake)[:2], (None, None))
        self.assertTrue(any(row[0] == "rayhit" for row in fake.commands))

    def test_fresh_grid_must_recertify_suggested_relocation(self):
        fake = NativeFixture(fresh=grid(rect=(-16, 144, -48, 48)))
        self.assertEqual(certified_lane(fake)[:2], (None, None))
        self.assertFalse(any(row[0] == "rayhit" for row in fake.commands))

    def test_any_query_rail_refuses_clear_shot_rays(self):
        fake = NativeFixture(body={"ok": True, "truncated": False, "bodyCount": 1,
                                   "bodies": [{"actor": False, "name": "ledge rail"}]})
        self.assertEqual(certified_lane(fake)[:2], (None, None))

    def test_exact_offaxis_target_clearance_rejects_obstacle_missed_by_raster_and_center_fans(self):
        fake = NativeFixture(blocked_target=(151.2, -38))
        origin, direction, _ = certified_lane(fake)
        self.assertEqual((origin, direction), ((0, 0), (1, 0)))
        self.assertIn((0, 0, 1, 0), blink_lanes(fake.initial, centered=True))
        clearance = blink_target_clearance(fake, origin, direction, 151.2, 30)
        self.assertFalse(clearance["clear"])
        self.assertEqual(clearance["endpoints"], [(151.2, 0), (151.2, 29), (151.2, -38)])
        self.assertEqual(clearance["native"][2]["bodies"][0]["actor"], False)
        self.assertEqual(clearance["native_body_radius"], 8)
        self.assertEqual(clearance["target_body_radius"], 5)

    def test_blocked_offaxis_target_refuses_spawn_and_measured_blink_input(self):
        fake = NativeFixture(blocked_target=(151.2, -38))
        with patch("gamelab.bots.qa_specs_arcane_ranks.time.sleep"), \
                patch("gamelab.bots.qa_specs_arcane_ranks.spawn") as spawned:
            row = blink(fake, (0, 0), (1, 0), "rare", 30, 151.2)
        spawned.assert_not_called()
        self.assertFalse(fake.out["rare_setup"])
        self.assertFalse(fake.out["rare_distance"])
        self.assertFalse(fake.out["rare_damage_radius"])
        self.assertIsNone(row["mean_damage"])
        self.assertFalse(any(command[0] == "input" for command in fake.commands))

    def test_exact_target_clearance_accepts_complete_clear_native_paths(self):
        clearance = blink_target_clearance(NativeFixture(), (0, 0), (1, 0), 151.2, 30)
        self.assertTrue(clearance["clear"])
        self.assertEqual(len(clearance["native"]), 3)

    def test_unbound_or_nonfinite_any_path_provenance_refuses_clearance(self):
        for fields in ({"fx": 2}, {"ty": 999}, {"step": 16}, {"tx": float("nan")}):
            with self.subTest(fields=fields):
                clearance = blink_target_clearance(NativeFixture(body=fields), (0, 0), (1, 0), 151.2, 30)
                self.assertFalse(clearance["clear"])

    def test_incomplete_or_truncated_any_scan_cannot_certify_fixture(self):
        for fake in (NativeFixture(short_reply=True),
                     NativeFixture(body={"ok": True, "truncated": True, "bodyCount": 0, "bodies": []}),
                     NativeFixture(body={"ok": True, "truncated": False, "bodyCount": 1, "bodies": []})):
            with self.subTest(fake=fake):
                self.assertEqual(certified_lane(fake)[:2], (None, None))


if __name__ == "__main__":
    unittest.main()
