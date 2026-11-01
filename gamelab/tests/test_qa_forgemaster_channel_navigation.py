"""Unexecuted draft controls for actual endpoint certification, not game proof."""
import copy
import inspect
import unittest
from unittest.mock import patch

from gamelab.bots import qa_forgemaster_channel_navigation as forge
from gamelab.bots import qa_specs_navigation as nav


def terrain(size=45, step=10, truncated=False):
    rows = ["."*size for _ in range(size)]
    mid = size//2
    rows[mid] = rows[mid][:mid]+"@"+rows[mid][mid+1:]
    return {"ok": True, "size": size, "step": step, "truncated": truncated, "x": 40., "y": 80., "rows": rows}


class Controller:
    def __init__(self, grid=None, owner_change=False):
        self.grid = grid or terrain(); self.owner_change = owner_change
        self.at = (40., 80.); self.start = (999., 999.); self.calls = []; self.out = {}; self.owner_reads = 0

    def gl(self, verb, *args):
        self.calls.append((verb, *args))
        if verb == "skillcost":
            self.owner_reads += 1
            return {"ok": True, "skill": "hwp_pri_necrotic_resurrection", "class": "hwp_priest_forgemaster",
                "unit": 8 if self.owner_change and self.owner_reads > 1 else 7, "matches": 1, "truncated": False}
        if verb == "terrain":
            assert args == (220, 10)
            return copy.deepcopy(self.grid)
        raise AssertionError("unexpected setup dispatch: "+verb)

    def pos(self):
        return self.at


def arrived(c, predicate, tag, ray, width, requirements, *, extra_probe, max_moves, max_seconds):
    assert (ray, width, max_moves, max_seconds) == (200, 10, 3, 12)
    proof = extra_probe(c, {}, c.at, (1, 0))
    trace = {"attempts": [{"candidates": [{"direction": (1, 0), "clear": True, "stable": True, "extra": proof}]}]}
    return c.at, (1, 0), (0, 1), trace


class ForgeNavigationControls(unittest.TestCase):
    def test_complete_supported_map_preserves_strict200_strip(self):
        grid = terrain()
        east = next(r for r in forge.lengths(grid, 10) if r["direction"] == (1, 0))
        self.assertEqual(east["free"], 220)
        rows = list(grid["rows"])
        rows[22] = rows[22][:42]+"#"+rows[22][43:]  #200px endpoint blocked
        grid["rows"] = rows
        east = next(r for r in forge.lengths(grid, 10) if r["direction"] == (1, 0))
        self.assertEqual(east["free"], 190)

    def test_observed_truncated48_shape_and_incomplete_flags_are_refused(self):
        for grid in (terrain(48, 10, True), terrain(45, 10, True), terrain(48, 10, False)):
            self.assertEqual(forge.lengths(grid, 10), [])
        grid = terrain(); del grid["truncated"]
        self.assertEqual(forge.lengths(grid, 10), [])

    def test_final_certificate_is_at_arrived_origin_and_replaces_cached_start(self):
        c = Controller()
        with patch.object(nav, "_walk", side_effect=arrived):
            direction, result = forge.prepare_forge_lane(c, "P0")
        self.assertEqual(direction, (1, 0)); self.assertTrue(result["valid"])
        self.assertEqual(c.start, c.at); self.assertEqual(result["teleports"], 0)
        self.assertEqual(result["free"], 220)
        self.assertFalse(any(call[0] == "teleport" for call in c.calls))

    def test_unreachable_candidate_or_arrival_without_certificate_never_passes(self):
        for reply in ((None, None, None, {"attempts": [], "error": "native route unreachable"}),
                      ((40., 80.), (1, 0), (0, 1), {"attempts": [{"walk": {"result": "arrived"}, "candidates": []}]})):
            c = Controller()
            with patch.object(nav, "_walk", return_value=reply):
                direction, result = forge.prepare_forge_lane(c, "C0")
            self.assertIsNone(direction); self.assertFalse(result["valid"])
            self.assertEqual(c.start, (999., 999.))

    def test_failed_or_stale_endpoint_geometry_and_owner_change_are_refused(self):
        bad = terrain(); rows = list(bad["rows"])
        rows[22] = rows[22][:42]+"#"+rows[22][43:]; bad["rows"] = rows
        for c in (Controller(bad), Controller(owner_change=True)):
            with patch.object(nav, "_walk", side_effect=arrived):
                direction, result = forge.prepare_forge_lane(c, "C1")
            self.assertIsNone(direction); self.assertFalse(result["valid"])
            self.assertEqual(c.start, (999., 999.))
        def stale(*args, **kwargs):
            point, direction, side, trace = arrived(*args, **kwargs)
            return (point[0]+2, point[1]), direction, side, trace
        c = Controller()
        with patch.object(nav, "_walk", side_effect=stale):
            direction, result = forge.prepare_forge_lane(c, "P1")
        self.assertIsNone(direction); self.assertFalse(result["valid"])

    def test_truncated_final_map_aborts_before_any_followup_navigation(self):
        c = Controller(terrain(45, 10, True))
        with patch.object(nav, "_walk", side_effect=arrived) as walk:
            direction, result = forge.prepare_forge_lane(c, "P0")
        self.assertIsNone(direction); self.assertFalse(result["valid"])
        self.assertEqual(walk.call_count, 1); self.assertEqual(c.owner_reads, 1)
        self.assertTrue(result["refusal"]["terrain"]["truncated"])
        self.assertEqual(c.start, (999., 999.))

    def test_movement_after_route_certificate_cannot_reuse_old_origin(self):
        class Moved(Controller):
            def gl(self, verb, *args):
                result = super().gl(verb, *args)
                if verb == "skillcost" and self.owner_reads > 1:
                    self.at = (self.at[0]+2, self.at[1])
                return result
        c = Moved()
        with patch.object(nav, "_walk", side_effect=arrived):
            direction, result = forge.prepare_forge_lane(c, "P0")
        self.assertIsNone(direction); self.assertFalse(result["valid"])
        self.assertEqual(c.start, (999., 999.))

    def test_existing_navigation_defaults_stay_and_invalid_budget_cannot_dispatch(self):
        signature = inspect.signature(nav._walk)
        self.assertEqual(signature.parameters["max_moves"].default, 20)
        self.assertEqual(signature.parameters["max_seconds"].default, 150)
        for moves, seconds in ((-1, 12), (21, 12), (3, 0), (3, float("nan"))):
            c = Controller()
            result = nav._walk(c, lambda *_: [], "invalid", 200, 10, {}, max_moves=moves, max_seconds=seconds)
            self.assertIsNone(result[0]); self.assertEqual(c.calls, [])

    def test_opt_in_budget_keeps_terminal_recertification_after_three_moves(self):
        from gamelab.tests.test_qa_specs_navigation import FakeController
        c = FakeController()
        def targets(fine, coarse, origin, predicate, visited, excluded):
            goal = (origin[0]+32, origin[1])
            return [{"goal": goal, "key": (round(goal[0]/8), round(goal[1]/8)), "score": 0, "guide": "fake native-route goal"}]
        with patch.object(nav, "_route_targets", side_effect=targets), patch.object(nav.time, "monotonic", side_effect=[0, 1, 2, 3, 4]):
            point, direction, _, receipt = nav._walk(c, lambda *_: [], "budget", 200, 10, {}, max_moves=3, max_seconds=12)
        self.assertEqual(len(c.moves), 3)
        self.assertEqual(len(receipt["attempts"]), 4)
        self.assertTrue(receipt["attempts"][-1]["final_recertification_only"])
        self.assertIsNone(point); self.assertIsNone(direction)  #arrival never substitutes for geometry


if __name__ == "__main__":
    unittest.main()
