"""UNRUN pure/fake controls; no native route, cursor, hit or cleanup proof."""
from copy import deepcopy
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gamelab.bots import qa_firearms_magazine_fixture as f
from gamelab.bots import qa_firearms_magazine_navigation as m


class FakeGame:
    def __init__(self, owner):
        self.owner, self.gl = owner, []

    def gl_multi(self, commands, timeout=5):
        o = self.owner
        o.now += 100
        o.commands.append(deepcopy(commands))
        if commands[0][0] == "qa_poseframe" and len(commands) == 3:
            phase = "idle"
            rows = [o.frame(), o.controller(), o.status()]
        elif commands[0][0] == "near" and len(commands) == 7:
            phase = "fan"
            rows = [{"ok": True, "count": 0, "truncated": 0, "units": []}]
            rows += [o.ray(c) for c in commands[1:6]]
            rows += [o.frame()]
        elif all(c[0] == "rayhit" for c in commands):
            phase, rows = "guide_rays", [o.ray(c) for c in commands]
        elif all(c[0] == "qa_routeleg" for c in commands):
            phase, rows = "routes", []
            for c in commands:
                distance = math.dist(o.xy, c[1:3])
                rows.append({"ok": True, "planner": "Pilot.Repath", "routed": True,
                             "nodes": 2, "fx": o.xy[0], "fy": o.xy[1],
                             "lastX": c[1], "lastY": c[2], "legX": c[1], "legY": c[2],
                             "legLength": distance, "length": distance,
                             "diameter": 12, "limit": 128, "complete": True, "legClipped": False})
        else:
            raise AssertionError("Unreviewed fake command: " + repr(commands))
        o.batch += 1
        parent = "native"+str(o.batch)
        meta = {"_lvl": 2, "_place": "keep", "_t": o.now/1000}
        rows = [{**r, **meta, "id": parent+"."+str(i)} for i, r in enumerate(rows)]
        self.gl.extend([{"ev": "rx", "cid": parent, "verb": "multi", **meta},
                        {"id": parent, "n": len(rows), "ok": True, **meta}])
        return o.change(phase, rows)


class FakePilot:
    def __init__(self, owner):
        self.owner, self.last_accept = owner, {}

    def path_to(self, x, y, tol, timeout):
        o = self.owner
        if tol != 4 or timeout != 6:
            raise AssertionError("Weakened path bounds")
        o.paths.append((o.xy, (x, y)))
        o.xy = (x, y)
        self.last_accept = {"id": "walk"+str(len(o.paths)), "ok": True}
        return SimpleNamespace(result="done", reason="", tick=len(o.paths))


class FakeChecks:
    def __init__(self):
        self.xy, self.now, self.batch = (0., 0.), 1000, 0
        self.out, self.paths, self.commands, self.verbs = {}, [], [], []
        self.g, self.p = FakeGame(self), FakePilot(self)
        self.modify = None
        self.block_until_moves = 0
        self.only_heading = None
        self.force_block = False

    def change(self, phase, row):
        return self.modify(phase, deepcopy(row)) if self.modify else deepcopy(row)

    def frame(self):
        return {"ok": True, "boots": 1, "_lvl": 2, "level": "levels/keep.lvl",
                "_place": "keep", "_t": self.now/1000, "now": self.now, "frame": self.now//33,
                "player": 77, "x": self.xy[0], "y": self.xy[1], "z": 0., "timescale": 1.,
                "gameplay_focus": True, "window": "", "main": {"id": "pistol", "item_token": 1},
                "off": {"id": "cannon", "item_token": 2}}

    def controller(self):
        return {"ok": True, "held": -33, "releasing": False, "down": [], "gamepad": False,
                "mx": 0., "my": 0., "frames": 7+len(self.paths)}

    @staticmethod
    def status():
        return {"ok": True, "paused": False, "intent": "", "reflexFire": 0, "reflexPotion": -1}

    def ray(self, command):
        dx, dy = command[3]-command[1], command[4]-command[2]
        angle = math.atan2(dy, dx)
        blocked = self.force_block or len(self.paths) < self.block_until_moves
        if self.only_heading is not None:
            wanted = math.atan2(self.only_heading[1], self.only_heading[0])
            blocked = blocked or abs(math.atan2(math.sin(angle-wanted), math.cos(angle-wanted))) > math.radians(22)
        if not blocked:
            return {"ok": True, "wall": False, "tile": False}
        size = math.hypot(dx, dy)
        return {"ok": True, "wall": True, "tile": False, "wd": 47.437,
                "wx": command[1]+dx/size*47.437, "wy": command[2]+dy/size*47.437,
                "wname": "doodads/walls/barracks/crn_sw.unit", "wsensor": False}

    def gl(self, verb, *args, timeout=5):
        self.verbs.append(verb)
        if timeout != 5:
            raise AssertionError("Unbounded local RPC")
        if verb == "qa_poseframe":
            self.now += 33
            row = self.frame()
        elif verb == "terrain":
            radius, step = args
            n = int(radius*2/step)+1
            rows = ["."*n for _ in range(n)]
            rows[n//2] = "."*(n//2)+"@"+"."*(n//2)
            row = {"ok": True, "size": n, "step": step, "truncated": False,
                   "rows": rows, "x": self.xy[0], "y": self.xy[1],
                   "_lvl": 2, "_place": "keep", "_t": self.now/1000}
        else:
            raise AssertionError("Mutation/unknown command during seek: " + verb)
        return self.change(verb, row)

    def run(self, walk=None):
        record = {"status": "UNRUN", "input_dispatched": False, "measurement": "UNRUN"}
        self.out["magazine_fixture_receipts"] = [record]
        result = m.prepare(self, self.frame(), (1, 0), "fixture", record,
                           walk=walk, sleep=lambda seconds: None)
        return result, record


def no_move_walk(adapter, predicate, tag, length, half_width, requirements,
                 extra_probe, max_moves, max_seconds):
    xy = adapter.pos()
    terrain = adapter.gl("terrain", 160, 8)
    for direction, side in predicate(terrain, 0, 0):
        if extra_probe(adapter, terrain, xy, direction)["clear"]:
            return xy, direction, side, {"attempts": [], "model": True}
    return None, None, None, {"attempts": [], "model": True}


class MagazineNavigationTests(unittest.TestCase):
    def test_eight_hashable_oriented_guides_include_body_margin(self):
        fake = FakeChecks()
        grid = fake.gl("terrain", 160, 8)
        lanes = m.lanes(grid)
        self.assertEqual(len(set(lanes)), 8)
        self.assertEqual(lanes[0][0], (1., 0.))
        self.assertFalse(m.lanes({**grid, "truncated": True}))
        rows = grid["rows"][:]
        rows[20] = rows[20][:19]+"#"+rows[20][20:]
        self.assertFalse(m.lanes({**grid, "rows": rows}))

    def test_recorded_first_ray_wall_remains_blocked(self):
        origin = FakeChecks().frame()
        rays = [{"ok": True, "wall": False, "tile": False} for _ in range(5)]
        rays[0].update(wall=True, wd=47.437, wx=-483.106, wy=-63.323,
                       wname="doodads/walls/barracks/crn_sw.unit", wsensor=False)
        near = {"ok": True, "count": 0, "truncated": 0, "units": []}
        self.assertTrue(m.blocked(origin, f.offsets((1, 0)), rays, near))
        with self.assertRaises(f.FixtureError): f.geometry(origin, f.offsets((1, 0)), rays, near)

    def test_malformed_wall_tile_and_near_never_become_seekable(self):
        fake = FakeChecks()
        near = {"ok": True, "count": 0, "truncated": 0, "units": []}
        for bad in ({"ok": True, "wall": True, "tile": False},
                    {"ok": True, "wall": False, "tile": True},
                    {"ok": True, "wall": 0, "tile": False},
                    {"ok": False, "wall": False, "tile": False}):
            with self.assertRaises(f.FixtureError): m.blocked(fake.frame(), f.offsets((1, 0)), [bad]*5, near)
        with self.assertRaises(f.FixtureError):
            m.blocked(fake.frame(), f.offsets((1, 0)), [{"ok": True, "wall": False, "tile": False}]*5,
                      {**near, "count": 1, "units": [{"name": "crate", "behavior": "Breakable", "x": float("nan"), "y": 0}]})

    def test_changed_heading_can_be_certified_without_movement(self):
        fake = FakeChecks()
        fake.only_heading = (0, 1)
        (origin, direction, rows), record = fake.run(no_move_walk)
        self.assertEqual(direction, (0., 1.))
        self.assertFalse(fake.paths)
        self.assertFalse(record["input_dispatched"])
        self.assertEqual(record["navigation"]["status"], "CERTIFIED_SETUP_ONLY")
        self.assertEqual((origin["x"], origin["y"]), (0., 0.))
        self.assertEqual(len(rows), 7)

    def test_actual_shared_walk_uses_multiple_fake_origins_and_fresh_final_fan(self):
        fake = FakeChecks()
        fake.block_until_moves = 2
        (origin, direction, rows), record = fake.run()
        self.assertGreaterEqual(len(fake.paths), 2)
        self.assertLessEqual(len(fake.paths), 4)
        self.assertEqual((origin["x"], origin["y"]), fake.xy)
        self.assertNotEqual(fake.xy, (0., 0.))
        proof = record["navigation"]["final"]
        self.assertTrue(proof["clear"])
        self.assertEqual(proof["batch"], rows)
        self.assertEqual(len(proof["batch"][1:6]), 5)
        self.assertTrue(all(math.dist(a, b) <= 128.01 for a, b in fake.paths))
        self.assertTrue(all([c[0] for c in commands] not in (["inputtarget"], ["spawn"]) for commands in fake.commands))
        self.assertFalse(record["input_dispatched"])

    def test_raster_alone_and_done_arrival_never_grant_fan_credit(self):
        fake = FakeChecks()
        fake.force_block = True
        def false_done(adapter, *args, **kwargs):
            return adapter.pos(), (1., 0.), (0., 1.), {"result": "done"}
        with self.assertRaisesRegex(f.FixtureError, "final fresh"):
            fake.run(false_done)
        self.assertFalse(fake.paths)

    def test_fresh_final_obstruction_invalidates_prior_clear_probe(self):
        fake = FakeChecks()
        def changes_after_certificate(*args, **kwargs):
            result = no_move_walk(*args, **kwargs)
            fake.force_block = True
            return result
        with self.assertRaisesRegex(f.FixtureError, "final fresh"):
            fake.run(changes_after_certificate)
        self.assertTrue(fake.out["magazine_fixture_receipts"][0]["navigation"]["fan_probes"][0]["clear"])

    def test_missing_truncated_foreign_or_wrong_parent_probe_stops_without_walking(self):
        for mode in ("truncated", "world", "parent", "missing"):
            fake = FakeChecks()
            def change(phase, rows):
                if phase == "fan":
                    if mode == "truncated": rows[0]["truncated"] = 1
                    if mode == "world": rows[1]["_lvl"] = 9
                    if mode == "parent": rows[1]["id"] = "foreign.1"
                    if mode == "missing": rows.pop()
                return rows
            fake.modify = change
            with self.assertRaises(f.FixtureError): fake.run(no_move_walk)
            self.assertFalse(fake.paths)

    def test_same_id_item_replacement_and_consistent_foreign_world_are_rejected(self):
        for mode in ("item", "player", "world", "clock"):
            fake = FakeChecks()
            def change(phase, rows):
                if phase == "idle":
                    if mode == "item": rows[0]["main"]["item_token"] = 99
                    if mode == "player": rows[0]["player"] = 99
                    if mode == "world": rows[0]["level"] = "levels/foreign.lvl"
                    if mode == "clock": rows[0]["now"] = 1
                return rows
            fake.modify = change
            with self.assertRaises(f.FixtureError): fake.run(no_move_walk)
            self.assertFalse(fake.paths)

    def test_held_input_live_intent_and_reflexes_refuse_navigation(self):
        for mode in ("held", "motion", "intent", "fire", "potion", "paused"):
            fake = FakeChecks()
            def change(phase, rows):
                if phase == "idle":
                    if mode == "held": rows[1]["held"] = 30
                    if mode == "motion": rows[1]["mx"] = .2
                    if mode == "intent": rows[2]["intent"] = "path_to"
                    if mode == "fire": rows[2]["reflexFire"] = 100
                    if mode == "potion": rows[2]["reflexPotion"] = 20
                    if mode == "paused": rows[2]["paused"] = True
                return rows
            fake.modify = change
            with self.assertRaises(f.FixtureError): fake.run(no_move_walk)
            self.assertFalse(fake.paths)

    def test_input_counter_change_across_two_native_frames_refuses(self):
        fake = FakeChecks()
        count = 0
        def change(phase, rows):
            nonlocal count
            if phase == "idle":
                count += 1
                rows[1]["frames"] = count
            return rows
        fake.modify = change
        with self.assertRaisesRegex(f.FixtureError, "stable idle"):
            fake.run(no_move_walk)
        self.assertFalse(fake.paths)

    def test_postwalk_drift_stops_before_final_birth_origin(self):
        fake = FakeChecks()
        fake.block_until_moves = 1
        def change(phase, rows):
            if phase == "idle" and fake.paths:
                rows[0]["x"] += .31
            return rows
        fake.modify = change
        with self.assertRaisesRegex(f.FixtureError, "moved fan actor"):
            fake.run()
        self.assertEqual(len(fake.paths), 1)

    def test_prior_owned_cursor_missing_restoration_refuses_all_navigation(self):
        fake = FakeChecks()
        record = {"input_dispatched": False}
        fake.out["magazine_fixture_receipts"] = [{"input_dispatched": True, "status": "INVALID"}, record]
        with self.assertRaisesRegex(f.FixtureError, "prior magazine input"):
            m.prepare(fake, fake.frame(), (1, 0), "fixture", record, walk=no_move_walk, sleep=lambda _: None)
        self.assertFalse(fake.commands)
        self.assertFalse(fake.paths)

    def test_unchanged_bounded_walk_arguments_and_final_readonly_commands(self):
        fake = FakeChecks()
        def checked(adapter, predicate, tag, length, half_width, requirements, **kwargs):
            self.assertEqual((length, half_width, kwargs["max_moves"], kwargs["max_seconds"]), (81, 12, 4, 30))
            self.assertEqual(requirements["native_leg_limit"], 128)
            return no_move_walk(adapter, predicate, tag, length, half_width, requirements, **kwargs)
        fake.run(checked)
        allowed = {"qa_poseframe", "controller", "pilot", "near", "rayhit", "qa_routeleg"}
        self.assertTrue(all(c[0] in allowed for commands in fake.commands for c in commands))
        self.assertEqual(set(fake.verbs), {"qa_poseframe", "terrain"})


if __name__ == "__main__":
    unittest.main()
