"""Pure/fake fixture controls. No native cursor, projectile, HP or cleanup proof."""
import ast
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamelab.bots import qa_firearms_magazine_fixture as fixture

# Portable source invariant for the authored legacy rows/schedules. Frozen from
# original8615a8e8 using source lines (original indentation, trailing whitespace
# stripped per line, LF join, UTF8 SHA256). No outside-repo baseline file is read.
LEGACY_FUNCTION_HASHES = {
    "fan": "6fbd70dbb05dfa3ff39c11229ac8c75a7d83c7e5fc49f91cb22fe02d6c33d09a",
    "bonuses": "0ba2118cdaf719cfebd4696c21c0b42bb7452683c5a52bebfd0e134fda1caac5",
    "edges": "987ac5cda6aef36e10ab988298b28c0d516dda7f341dfed545ae9fb10c2256c0",
    "real_damage": "9a7d2f308925ed4e2a30b3ef28ca9ef9756c32931a4e5433a87684191ef34a8c",
    "continuity": "479c157c9f9facb769c15a3555338d3724e26281498514aeb6d1343f7a503607",
    "run": "0c6a912a7b103d60f28549b612265015e63b2f58bc016a576eb2439f4c88f6a2",
}


class FakeGame:
    def __init__(self, owner):
        self.gl = []
        self.gl_multi = owner.gl_multi
        self.wait_gl = owner.wait_gl


class FakeChecks:
    CLIP = "players/hwp/firearms/stacks_firearms.sval:clip"

    def __init__(self, button="main", duration=320, damage=10):
        self.g = FakeGame(self)
        self.out, self.rows, self.events, self.births = {}, [], [], []
        self._magazine_expected = ("hwp_glock_mh_01", "hwp_hcannon_oh_01")
        self.button, self.duration, self.damage = button, duration, damage
        self.modify, self.fail_post = None, False
        self.number, self.request = 0, 0
        self.accepted = None
        self.uncertain, self.collect_error = False, False
        self.batch_number = 0

    def frame(self, when):
        last = 2000 + 33*math.ceil(self.duration/33)
        now = {"origin": 1000, "pre": 2000, "post": last+170, "released": last+203}[when]
        return {"ok": True, "level": "levels/keep.lvl", "boots": 1, "_lvl": 2,
                "_place": "keep", "_t": now/1000, "now": now, "frame": now//33,
                "player": 77, "x": -240., "y": -48., "z": 0., "timescale": 1.,
                "gameplay_focus": True, "window": "", "main": {"id": self._magazine_expected[0], "item_token": 1},
                "off": {"id": self._magazine_expected[1], "item_token": 2}}

    @staticmethod
    def controller():
        return {"ok": True, "held": -33, "releasing": False, "down": [],
                "gamepad": False, "mx": 0., "my": 0.}

    def hp(self, after=False):
        result = {"ok": True, "count": 5, "truncated": 0, "_lvl": 2,
                  "_place": "keep", "_t": self.frame("post" if after else "pre")["_t"], "units": []}
        for n, birth in enumerate(self.births):
            result["units"].append({"unit": birth["unit"], "name": fixture.DUMMY,
                                    "behavior": "CompositeActorBehavior", "scene": "pop",
                                    "hpMax": 500, "hpExact": 500 - (self.damage if after and n == 2 else 0),
                                    "dead": False, "x": birth["x"], "y": birth["y"]})
        return result

    def clear_dummies(self):
        self.events.append("clear")
        self.births = []

    def top_up(self):
        self.events.append("setup_refill")

    def gl(self, verb, *args):
        self.events.append(verb)
        if verb == "qa_poseframe":
            row = self.frame("origin")
        elif verb == "near":
            row = {"ok": True, "count": 0, "truncated": 0, "units": []}
        elif verb == "rayhit":
            row = {"ok": True, "wall": False, "tile": False}
        elif verb == "spawn":
            self.request += 1
            row = {"ok": True, "id": "birth"+str(self.request), "unit": 100+len(self.births),
                   "name": args[0], "x": -240+args[1], "y": -48+args[2],
                   "_lvl": 2, "_place": "keep", "_t": 1.1+len(self.births)*.1}
            self.births.append(row)
        elif verb == "inputtarget":
            self.accepted = row = {"ok": True, "id": "input"+str(self.request), "tag": args[0],
                                    "skill": args[1], "player": 77, "target_x": args[2], "target_y": args[3]}
            self.step = args[4]
            self.g.gl.append(deepcopy(row))
            if self.uncertain:
                raise RuntimeError("fake uncertain acknowledgement after send")
        else:
            raise AssertionError("Unexpected real verb: " + verb)
        return self.change(verb, row)

    def change(self, phase, value):
        return self.modify(phase, deepcopy(value)) if self.modify else deepcopy(value)

    def gl_multi(self, commands):
        if len(commands) == 7:
            self.events.append("geometry_reads")
            rows = [self.gl("near", 95)] + [self.gl("rayhit") for _ in range(5)] + [self.frame("origin")]
            return self.batch("geometry", rows)
        if len(commands) == 3:
            self.events.append("pre_reads")
            return self.batch("pre", [self.hp(), self.frame("pre"), {"ok": True, "stacks": 24}])
        if len(commands) == 5:
            self.events.append("post_reads")
            self.post_commands = commands
            if self.fail_post:
                raise RuntimeError("fake missing post batch")
            return self.batch("post", [{"ok": True, "stacks": 21 if self.button == "main" else 22},
                                         {"ok": True, "mainCritDmg": 1.26, "offCritDmg": 1.16},
                                         self.hp(True), self.frame("post"), self.controller()])
        if len(commands) == 2:
            self.events.append("release_reads")
            return self.batch("released", [self.frame("released"), self.controller()])
        raise AssertionError("Unexpected fake batch")

    def batch(self, phase, rows):
        self.batch_number += 1
        parent = "multi" + str(self.batch_number)
        clock = self.frame("origin" if phase == "geometry" else phase)["_t"]
        meta = {"_lvl": 2, "_place": "keep", "_t": clock}
        for index, row in enumerate(rows):
            row.update(meta, id=parent+"."+str(index))
        self.g.gl.extend([{"ev": "rx", "cid": parent, "verb": "multi", **meta},
                          {"id": parent, "n": len(rows), "ok": True, **meta}])
        return self.change(phase, rows)

    def wait_gl(self, predicate, timeout):
        self.events.append(("reconcile_wait", timeout))
        return next((r for r in self.g.gl if predicate(r)), None)

    def collect(self, game, accepted, expected):
        self.events.append("collect")
        if self.collect_error:
            raise RuntimeError("fake collector cleanup failure")
        if expected != [(self.duration, [self.button])]:
            raise AssertionError("Changed native schedule")
        last = 2000+33*math.ceil(self.duration/33)
        terminal = {**accepted, "steps": [{"last_write": last}], "start": 2033, "end": last+66}
        samples = [{"world_x": accepted["target_x"], "world_y": accepted["target_y"],
                    "x": -240., "y": -48., "gamepad": False} for _ in range(2)]
        return self.change("cursor", {"valid": True, "sequence": {"valid": True}, "accepted": accepted,
                                       "terminal": terminal, "samples": samples,
                                       "chunks": [{"restore": [{"restored": True, "owned_last_value": True,
                                                                  "already_neutral": False}]}]})

    def run(self):
        return fixture.measured_cycle(self, (math.sqrt(.5), math.sqrt(.5)), self.button, self.duration,
                                      collect=self.collect, sleep=lambda seconds: self.events.append(("sleep", seconds)))


class MagazineFixtureTests(unittest.TestCase):
    def rejected(self, modify, before_input=False):
        fake = FakeChecks()
        fake.modify = modify
        with self.assertRaises((fixture.FixtureError, RuntimeError)):
            fake.run()
        self.assertEqual(fake.out["magazine_fixture_receipts"][-1]["status"], "INVALID_UNRUN_OR_FAILED_FIXTURE")
        if before_input:
            self.assertNotIn("inputtarget", fake.events)
        return fake

    def test_valid_fake_uses_body_point_fixed_schedule_and_immediate_reads(self):
        fake = FakeChecks()
        row = fake.run()
        self.assertEqual(row["clip"], [24, 21])
        self.assertEqual(row["actual_damage"], 10)
        self.assertEqual(fake.accepted["target_y"], fake.births[2]["y"]-11)
        self.assertEqual(fake.step, "320/0/0/0.707107/0.707107/main")
        self.assertLess(fake.events.index("post_reads"), fake.events.index("collect"))
        self.assertEqual([c[0] for c in fake.post_commands], ["givestacks", "critprobe", "near", "qa_poseframe", "controller"])

    def test_off_duration_and_button_unchanged(self):
        fake = FakeChecks("off", 180)
        row = fake.run()
        self.assertEqual(row["clip"], [24, 22])
        self.assertEqual(fake.step, "180/0/0/0.707107/0.707107/off")

    def test_zero_hp_loss_stays_zero_despite_valid_ammo_and_cursor(self):
        row = FakeChecks(damage=0).run()
        self.assertEqual(row["actual_damage"], 0)
        self.assertFalse(row["actual_damage"] > 0)

    def test_failed_loadout_and_recorded_setup_leave_shot_unrun(self):
        for mode in ("loadout", "gear", "god", "floor", "floor_god", "resume_god"):
            fake = FakeChecks()
            fake._magazine_loadout_failed = mode == "loadout"
            if mode != "loadout":
                fake.rows = [{"case": {"gear": "pistol_cannon_gear", "god": "god_disabled", "floor": "QAMagEdges_floor_loadout", "floor_god": "floor_god_disabled", "resume_god": "resume_x_god_disabled"}[mode], "runtime": "FAIL"}]
            with self.assertRaises(fixture.FixtureError):
                fake.run()
            self.assertEqual(fake.events, [])
            self.assertFalse(fake.out["magazine_fixture_receipts"][0]["input_dispatched"])
            self.assertEqual(fake.out["magazine_fixture_receipts"][0]["measurement"], "UNRUN")

    def test_failed_ray_or_blocker_refuses_before_births_and_input(self):
        for mode in ("wall", "missing", "blocker", "old_dummy"):
            def modify(phase, value):
                if phase == "rayhit" and mode in ("wall", "missing"):
                    value["wall" if mode == "wall" else "ok"] = mode == "wall"
                if phase == "near" and mode in ("blocker", "old_dummy"):
                    value.update(count=1, units=[{"name": fixture.DUMMY if mode == "old_dummy" else "wall_crate", "behavior": "Breakable", "x": -220., "y": -28.}])
                return value
            fake = self.rejected(modify, True)
            self.assertNotIn("spawn", fake.events)

    def test_wrong_resource_hp_scene_or_birth_geometry_refuses_before_input(self):
        for key, bad in (("name", "foreign"), ("hpMax", 10000000), ("hpExact", 499), ("scene", "outlook"), ("x", 1e4)):
            def modify(phase, value):
                if phase == "pre":
                    value[0]["units"][2][key] = bad
                return value
            self.rejected(modify, True)

    def test_stale_duplicate_or_foreign_birth_refuses(self):
        for key, bad in (("unit", 100), ("_t", .9), ("_lvl", 1), ("name", "foreign")):
            def modify(phase, value):
                if phase == "spawn" and value["unit"] == 102:
                    value[key] = bad
                return value
            # Modify the actual retained spawn object too: the fake return is its owned receipt.
            fake = FakeChecks()
            original = fake.gl
            def spawn_receipt(verb, *args):
                row = original(verb, *args)
                if verb == "spawn":
                    fake.births[-1] = row
                return row
            fake.gl = spawn_receipt
            fake.modify = modify
            with self.assertRaises(fixture.FixtureError):
                fake.run()
            self.assertNotIn("inputtarget", fake.events)

    def test_missing_truncated_duplicate_or_nonfinite_post_hp_never_becomes_damage(self):
        for mode in ("missing", "truncated", "duplicate", "nan"):
            def modify(phase, value):
                if phase == "post":
                    hp = value[2]
                    if mode == "missing": hp["units"].pop(); hp["count"] -= 1
                    if mode == "truncated": hp["truncated"] = 1
                    if mode == "duplicate": hp["units"][1] = deepcopy(hp["units"][0])
                    if mode == "nan": hp["units"][2]["hpExact"] = float("nan")
                return value
            fake = self.rejected(modify)
            self.assertIn("collect", fake.events)

    def test_foreign_consistent_native_request_or_actor_is_rejected(self):
        for mode in ("world", "player", "tag"):
            def modify(phase, value):
                if phase == "inputtarget":
                    if mode == "world": value["target_x"] += 50
                    if mode == "player": value["player"] = 88
                    if mode == "tag": value["tag"] = "foreign"
                return value
            self.rejected(modify)

    def test_invalid_projection_protocol_or_owned_restore_is_rejected(self):
        for mode in ("projection", "protocol", "restore", "missing"):
            def modify(phase, value):
                if phase == "cursor":
                    if mode == "projection": value["samples"][0]["world_y"] += 2
                    if mode == "protocol": value["sequence"]["valid"] = False
                    if mode == "restore": value["chunks"][0]["restore"][0]["restored"] = False
                    if mode == "missing": value["valid"] = False; value["samples"] = []
                return value
            self.rejected(modify)

    def test_changed_actor_world_equipment_and_position_are_rejected(self):
        for key, bad in (("player", 88), ("boots", 2), ("_lvl", 3), ("level", "foreign"), ("x", -230.)):
            def modify(phase, value):
                if phase == "post": value[3][key] = bad
                return value
            self.rejected(modify)
        self.rejected(lambda p, v: ([*v[:3], {**v[3], "main": {"id": "foreign"}}, v[4]] if p == "post" else v))

    def test_pre_focus_timescale_or_identity_failure_is_unrun(self):
        for key, bad in (("gameplay_focus", False), ("timescale", .1), ("player", 0), ("x", float("nan")), ("_preload", True)):
            def modify(phase, value):
                if phase == "qa_poseframe": value[key] = bad
                return value
            self.rejected(modify, True)

    def test_post_batch_before_completion_or_after_window_is_rejected(self):
        for now in (2200, 2900):
            def modify(phase, value):
                if phase == "post": value[3]["now"] = now
                return value
            self.rejected(modify)

    def test_release_still_down_or_motion_is_rejected(self):
        for mode in ("down", "motion"):
            def modify(phase, value):
                if phase == "released": value[1]["down" if mode == "down" else "mx"] = ["main"] if mode == "down" else .5
                return value
            self.rejected(modify)

    def test_post_read_error_still_collects_required_cleanup_receipt(self):
        fake = FakeChecks()
        fake.fail_post = True
        with self.assertRaisesRegex(RuntimeError, "missing post batch"):
            fake.run()
        self.assertLess(fake.events.index("collect"), fake.events.index("release_reads"))
        self.assertIn("cursor", fake.out["magazine_fixture_receipts"][0])

    def test_uncertain_ack_reconciles_read_only_without_redispatch_and_stays_failed(self):
        fake = FakeChecks()
        fake.uncertain = True
        with self.assertRaisesRegex(fixture.FixtureError, "uncertain acknowledgement"):
            fake.run()
        record = fake.out["magazine_fixture_receipts"][0]
        self.assertEqual(fake.events.count("inputtarget"), 1)
        self.assertIn("collect", fake.events)
        self.assertIn("release_reads", fake.events)
        self.assertIn("reconciliation", record)
        self.assertEqual(record["measurement"], "DISPATCH_ATTEMPTED_NO_EFFECT_CREDIT")
        self.assertIn("uncertain acknowledgement", record["primary_error"])

    def test_primary_and_cleanup_failures_are_both_retained(self):
        fake = FakeChecks()
        fake.fail_post = fake.collect_error = True
        with self.assertRaisesRegex(fixture.FixtureError, "missing post batch"):
            fake.run()
        record = fake.out["magazine_fixture_receipts"][0]
        self.assertIn("missing post batch", record["primary_error"])
        self.assertIn("collector cleanup failure", record["cleanup_errors"][0])
        self.assertIn("release_reads", fake.events)

    def test_chunk_locator_without_ack_is_never_fabricated_acceptance(self):
        fake = FakeChecks()
        fake.uncertain = True
        original = fake.gl
        def chunk_only(verb, *args):
            try:
                return original(verb, *args)
            except RuntimeError:
                row = fake.g.gl[-1]
                row.pop("ok")
                row["ev"] = "inputtarget"
                raise
        fake.gl = chunk_only
        with self.assertRaises(fixture.FixtureError): fake.run()
        record = fake.out["magazine_fixture_receipts"][0]
        self.assertTrue(record["reconciliation"]["locator_only_no_ack_credit"])
        self.assertIsNot(record["cursor"]["accepted"].get("ok"), True)
        self.assertEqual(record["measurement"], "DISPATCH_ATTEMPTED_NO_EFFECT_CREDIT")
        self.assertEqual(fake.events.count("inputtarget"), 1)

    def test_missing_or_ambiguous_reconciliation_never_redispatches(self):
        for mode in ("missing", "ambiguous"):
            fake = FakeChecks()
            fake.uncertain = True
            original = fake.gl
            def uncertain(verb, *args):
                try:
                    return original(verb, *args)
                except RuntimeError:
                    if mode == "missing": fake.g.gl.clear()
                    else: fake.g.gl.append({**fake.g.gl[-1], "id": "another-input"})
                    raise
            fake.gl = uncertain
            with self.assertRaises(fixture.FixtureError): fake.run()
            self.assertEqual(fake.events.count("inputtarget"), 1)
            self.assertNotIn("collect", fake.events)
            self.assertTrue(fake.out["magazine_fixture_receipts"][0]["cleanup_errors"])

    def test_same_id_item_replacement_is_rejected_at_every_bracket(self):
        for phase, index in (("pre", 1), ("post", 3), ("released", 0)):
            def modify(p, value):
                if p == phase: value[index]["main"]["item_token"] = 99
                return value
            self.rejected(modify, phase == "pre")

    def test_current_multi_parent_suffix_and_delivery_context_are_required(self):
        for phase, index, mode in (("geometry", 0, "parent"), ("geometry", 1, "world"),
                                   ("post", 2, "parent"), ("post", 4, "suffix"), ("post", 1, "world"),
                                   ("post", 0, "consistent_parent")):
            def modify(p, value):
                if p == phase:
                    if mode == "parent": value[index]["id"] = "oldmulti."+str(index)
                    if mode == "suffix": value[index]["id"] = value[index]["id"].rsplit(".", 1)[0]+".0"
                    if mode == "world": value[index]["_lvl"] = 1
                    if mode == "consistent_parent":
                        for i, row in enumerate(value): row["id"] = "foreignmulti."+str(i)
                return value
            self.rejected(modify, phase == "geometry")

    def test_stale_consistent_old_hp_batch_cannot_use_current_native_clock(self):
        def modify(phase, value):
            if phase == "post":
                for row in value: row["_t"] = 1.9  # New IDs with old delivered effect data.
            return value
        self.rejected(modify)

    def test_reused_ids_require_new_current_births_and_tags(self):
        fake = FakeChecks()
        first = fake.run()
        old = deepcopy(first["fixture"])
        second = fake.run()
        self.assertEqual(set(first["hp_before"]), set(second["hp_before"]))
        self.assertNotEqual(old["births"][0]["id"], second["fixture"]["births"][0]["id"])
        self.assertNotEqual(old["accepted"]["tag"], second["fixture"]["accepted"]["tag"])

    def test_all_original_scenario_assertion_bodies_and_fixed_counts_preserved(self):
        source = (ROOT/"gamelab/bots/qa_firearms_magazine_edges.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Checks")
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(methods), {"fan", "cycle", "bonuses", "edges", "real_damage", "continuity", "fixture_loadout"})
        functions = {name: methods[name] for name in LEGACY_FUNCTION_HASHES if name != "run"}
        functions["run"] = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
        lines = source.splitlines()
        for name, expected in LEGACY_FUNCTION_HASHES.items():
            node = functions[name]
            normalized = "\n".join(line.rstrip() for line in lines[node.lineno-1:node.end_lineno])
            self.assertEqual(hashlib.sha256(normalized.encode("utf-8")).hexdigest(), expected, name)


if __name__ == "__main__":
    unittest.main()
