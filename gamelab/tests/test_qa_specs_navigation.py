"""Pure selection and fake-native controls for bounded QA navigation.

Synthetic terrain reproduces a nearby spawn pocket with distant raster-clear
room guides. Fake routes prove helper policy, not live Pathfind or gameplay.
Only the pure navigation module is imported; no game, files or input are used.
"""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gamelab.bots import qa_specs_navigation as nav


def grid(step, size, x=0, y=0):
    rows = ["." * size for _ in range(size)]
    mid = size // 2
    rows[mid] = rows[mid][:mid] + "@" + rows[mid][mid+1:]
    return {"ok": True, "truncated": False, "size": size, "step": step, "x": x, "y": y, "rows": rows}


def scene(step, size, origin=(0, 0), connected_room=False):
    """Sample a narrow legal approach and a room needing a later origin."""
    result = grid(step, size, *origin)
    mid = size // 2
    rows = []
    for iy in range(size):
        y = origin[1] + (iy - mid) * step
        row = []
        for ix in range(size):
            x = origin[0] + (ix - mid) * step
            if connected_room:
                free = (-32 <= x <= 640 and -16 <= y <= 16
                        or 192 <= x <= 640 and -96 <= y <= 96)
            else:
                free = (-48 <= x <= 48 and -16 <= y <= 96
                        or -240 <= x <= -32 and -240 <= y <= -96)
            row.append("." if free else "#")
        rows.append("".join(row))
    rows[mid] = rows[mid][:mid] + "@" + rows[mid][mid + 1:]
    result["rows"] = rows
    return result


class SelectionTests(unittest.TestCase):
    def test_spawn_pocket_queries_local_departures_before_remote_room(self):
        origin = (0, 0)
        fine, coarse = scene(8, 41), scene(16, 31)
        self.assertFalse(nav.corridor_lanes(fine))
        targets = nav._route_targets(fine, coarse, origin, nav.corridor_lanes, [], set())
        self.assertTrue(targets)
        # Synthetic regression for trial1's distant-guide starvation. It says
        # nothing about whether a returned local goal routes in the live game.
        self.assertLessEqual(max(math.dist(origin, t["goal"]) for t in targets[:8]), 128)
        self.assertLessEqual(min(math.dist(origin, t["goal"]) for t in targets[:8]), 48)
        self.assertTrue(all(not t["provisional_lanes"] for t in targets[:8]))

    def test_exploration_includes_short_departures_and_excludes_long_goals(self):
        targets = nav._route_targets(grid(8, 41), grid(16, 31), (0, 0), lambda *_: [], [], set())
        goals = {tuple(t["goal"]) for t in targets}
        self.assertTrue({(32, 0), (-32, 0), (0, 32), (0, -32)} <= goals)
        self.assertTrue({(128, 0), (-128, 0), (0, 128), (0, -128)} <= goals)
        self.assertNotIn((144, 0), goals)
        self.assertNotIn((96, 96), goals)  # Euclidean135.76, not an axis-only bound.
        self.assertTrue(all(32 <= math.hypot(*goal) <= 128 for goal in goals))

    def test_empty_room_queries_nearest_native_frontiers_first(self):
        targets = nav._route_targets(grid(8, 41), grid(16, 31), (0, 0), lambda *_: [], [], set())
        self.assertEqual({tuple(t["goal"]) for t in targets[:4]}, {(32, 0), (-32, 0), (0, 32), (0, -32)})

    def test_footprint_guides_also_stay_inside_local_neighborhood(self):
        lane = [((1, 0), (0, 1))]
        targets = nav._route_targets(grid(8, 41), grid(16, 31), (0, 0), lambda *_: lane, [], set())
        self.assertTrue(targets)
        self.assertTrue(all(math.hypot(*t["goal"]) <= 128 for t in targets))
        self.assertTrue(any(tuple(t["goal"]) == (128, 0) for t in targets))

    def test_excluded_goals_stay_excluded_and_visited_goals_lose_priority(self):
        excluded = {(4, 0)}
        targets = nav._route_targets(grid(8, 41), grid(16, 31), (0, 0), lambda *_: [], [(0, 32)], excluded)
        self.assertNotIn((32, 0), {tuple(t["goal"]) for t in targets})
        self.assertNotEqual(tuple(targets[0]["goal"]), (0, 32))


class FakeController:
    def __init__(self, route_ok=True, ray_ok=True, drift=False, malformed=False):
        self.at = (0, 0)
        self.out = {}
        self.calls = []
        self.moves = []
        self.route_ok, self.ray_ok, self.drift, self.malformed = route_ok, ray_ok, drift, malformed
        self.g = SimpleNamespace(gl_multi=self.multi)
        self.p = SimpleNamespace(path_to=self.walk, last_accept={"ok": True})

    def pos(self):
        return self.at

    def gl(self, verb, radius, step):
        self.calls.append((verb, step, self.at))
        return grid(step, 41 if step == 8 else 31, *self.at)

    def multi(self, commands):
        self.calls.append(("multi", commands))
        if commands[0][0] == "rayhit":
            if self.drift:
                self.at = (self.at[0] + 2, self.at[1])
            return [{"ok": True, "wall": not self.ray_ok, "tile": False} for _ in commands]
        replies = []
        for command in commands:
            self.assert_route_command(command)
            x, y = command[1:3]
            distance = math.dist(self.at, (x, y))
            r = {"ok": True, "planner": "Pilot.Repath", "routed": self.route_ok,
                 "nodes": 1, "diameter": 12, "limit": 128, "fx": self.at[0], "fy": self.at[1],
                 "lastX": x, "lastY": y, "length": distance, "legX": x, "legY": y,
                 "legLength": distance, "complete": True, "legClipped": False}
            if self.malformed:
                r["legLength"] = float("nan")
            replies.append(r)
        return replies

    @staticmethod
    def assert_route_command(command):
        assert command[0] == "qa_routeleg" and command[3] == 128

    def walk(self, x, y, **kwargs):
        self.moves.append({"from": self.at, "to": (x, y), "kwargs": kwargs})
        self.at = (x, y)
        return SimpleNamespace(result="arrived", reason="", tick=100)


class FakeBoundaryTests(unittest.TestCase):
    def walk(self, c, certified=True, extra=None):
        # First loop may move; next loop is the mandatory terminal recertification.
        predicate = lambda t, *_: [((1, 0), (0, 1))] if certified and t["x"] >= 32 else []
        with patch.object(nav.time, "monotonic", side_effect=[0, 1, 151]):
            return nav._walk(c, predicate, "fake", 110, 6,
                             {"bidirectional_length": 110, "native_body_diameter": 12}, extra_probe=extra)

    def test_native_walk_must_get_fresh_full_terminal_certificate(self):
        c = FakeController()
        origin, direction, _, geometry = self.walk(c)
        self.assertEqual(len(c.moves), 1)
        self.assertEqual(origin, c.at)
        self.assertEqual(direction, (1, 0))
        self.assertEqual([x[2] for x in c.calls if x[:2] == ("terrain", 8)], [(0, 0), c.at])
        self.assertEqual(len(geometry["attempts"]), 2)

    def test_arrival_alone_cannot_pass_geometry(self):
        c = FakeController()
        origin, direction, _, geometry = self.walk(c, certified=False)
        self.assertEqual(len(c.moves), 1)
        self.assertIsNone(origin)
        self.assertIsNone(direction)
        self.assertTrue(geometry["attempts"][-1]["final_recertification_only"])

    def test_failed_native_route_cannot_issue_walk(self):
        c = FakeController(route_ok=False)
        result = self.walk(c)
        self.assertEqual(c.moves, [])
        self.assertIsNone(result[1])

    def test_nonfinite_native_leg_cannot_issue_walk(self):
        c = FakeController(malformed=True)
        result = self.walk(c)
        self.assertEqual(c.moves, [])
        self.assertIsNone(result[1])

    def test_failed_native_rays_cannot_pass_after_arrival(self):
        c = FakeController(ray_ok=False)
        result = self.walk(c)
        self.assertIsNone(result[1])
        self.assertFalse(result[3]["attempts"][-1]["candidates"][0]["clear"])

    def test_failed_bidirectional_body_probe_cannot_pass(self):
        c = FakeController()
        result = self.walk(c, extra=lambda *_: {"clear": False})
        self.assertIsNone(result[1])
        self.assertFalse(result[3]["attempts"][-1]["candidates"][0]["extra"]["clear"])

    def test_player_drift_during_probe_cannot_pass(self):
        c = FakeController(drift=True)
        result = self.walk(c)
        self.assertIsNone(result[1])
        self.assertFalse(result[3]["attempts"][-1]["candidates"][0]["stable"])


class ProgressiveController(FakeController):
    def __init__(self):
        super().__init__()
        self.extra_origins = []

    def gl(self, verb, radius, step):
        self.calls.append((verb, step, self.at))
        return scene(step, 41 if step == 8 else 31, self.at, connected_room=True)

    def multi(self, commands):
        replies = super().multi(commands)
        if commands[0][0] == "qa_routeleg":
            for command, reply in zip(commands, replies):
                # A fake native route exists only for forward travel in the
                # narrow hall. Other raster candidates still must be refused.
                reply["routed"] = command[1] > self.at[0] and command[2] == 0
        return replies

    def extra(self, _controller, _terrain, origin, direction):
        self.extra_origins.append((origin, direction))
        return {"clear": True, "scope": "fake additional native body/target consumer"}


class ProgressiveWalkingTests(unittest.TestCase):
    def test_distant_full_corridor_requires_multiple_recentered_native_walks(self):
        c = ProgressiveController()
        initial = scene(8, 41, connected_room=True)
        self.assertFalse(nav.corridor_lanes(initial))
        # A full source-defined144px-by96px corridor exists in the room, over
        #128px from the start. Short fake-native hops must reach a new origin.
        self.assertTrue(nav.corridor_lanes(scene(8, 41, (224, 0), connected_room=True)))
        with patch.object(nav.time, "monotonic", return_value=0):
            origin, direction, _, geometry = nav._walk(
                c, nav.corridor_lanes, "progressive", 144, 12,
                {"length": 144, "half_width": 48, "native_body_diameter": 12},
                extra_probe=c.extra)
        self.assertGreaterEqual(len(c.moves), 2)
        self.assertEqual(origin, c.at)
        self.assertIsNotNone(direction)
        self.assertGreater(origin[0], 128)
        self.assertTrue(all(0 < math.dist(m["from"], m["to"]) <= 128 for m in c.moves))
        self.assertEqual([m["from"] for m in c.moves], [(0, 0)] + [m["to"] for m in c.moves[:-1]])
        fine_origins = [row[2] for row in c.calls if row[:2] == ("terrain", 8)]
        self.assertEqual(fine_origins, [(0, 0)] + [m["to"] for m in c.moves])
        self.assertEqual(c.extra_origins[-1], (origin, direction))
        final = geometry["attempts"][-1]
        self.assertEqual(final["origin"], origin)
        self.assertTrue(final["candidates"][-1]["clear"])
        self.assertTrue(final["candidates"][-1]["extra"]["clear"])
        self.assertTrue(final["candidates"][-1]["stable"])
        self.assertNotIn("walk", final)


if __name__ == "__main__":
    unittest.main()
