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



def fake_current_speed_run(module, *, damage_outside=False, reject_geometry=False):
    """Exercise the real bot functions with deterministic transport/physics fakes.

    This supplies synthetic HP/trajectory records, never native execution evidence.
    The baseline85px target loses periodic HP but cannot receive the3s terminal burst.
    """
    import copy
    import math
    from contextlib import ExitStack
    from unittest.mock import patch

    class Game:
        def __init__(self, checks):
            self.checks = checks

        def gl_multi(self, commands):
            self.checks.uid = commands[0][-1]
            self.checks.observer_tag = commands[0][1]
            self.checks.produce()
            return [{"ok": True}, {"ok": True}, {"ok": True}]

        def wait_gl(self, predicate, timeout):
            assert predicate(self.checks.trace)
            return copy.deepcopy(self.checks.trace)

    class Checks:
        def __init__(self, pilot):
            self.out, self.notes, self.levels = {}, [], {}
            self.active_override = False
            self.g = Game(self)
            self.identity_calls = []

        def setup(self, *args):
            pass

        def enter_floor(self, *args):
            return True

        def open_dir(self, *args):
            return (1, 0)

        def button_for(self, *args):
            return "skill3"

        def pos(self):
            return (0, 0)

        def set_stacks(self, *args):
            pass

        def to_town(self):
            pass

        def flag(self, name, value, detail=""):
            self.out[name] = bool(value)

        def gl(self, verb, *args):
            if verb == "orb":
                skill, action = args
                old = self.levels.get(skill, 0)
                self.levels[skill] = max(0, old - 1) if action == "down" else old + action
                return {"level": self.levels[skill]}
            if verb == "skill":
                return {"level": 5}
            if verb == "skillcrit":
                if len(args) > 1:
                    self.active_override = args[1] != "restore"
                return {"ok": True, "crit_chance": 0, "spell_crit_chance": 0,
                        "override_active": self.active_override}
            if verb == "unitsof":
                return {module.PROJECTILE: {"units": [], "count": 0}}
            return {"ok": True}

        def produce(self):
            start, duration = 132, 2970
            last_x = 8 + 2 * duration / 33
            self.trace = {"ev": "track", "tag": self.observer_tag + ".orb", "ms": 4224,
                          "frames": 128, "most": 1, "truncated": 0,
                          "tracks": [{"name": module.PROJECTILE, "unit": -1, "n": 91,
                                      "t0": start, "t1": start + duration,
                                      "x0": 8, "y0": 0, "x1": last_x, "y1": 0}]}
            hp, zapped = 15000, 0
            events = [{"target_valid": True, "target_hpMax": 15000, "target_hpExact": hp,
                       "now": 10000, "elapsed": 0}]
            target = self.before[self.uid]
            per = (0, .04, .07)[self.levels.get(module.FOCAL, 0)]
            for period in range(1, 12):
                at = period * 250
                x = 8 + 2 * at / 33
                if math.dist((x, 0), (target["x"], target["y"])) <= 75:
                    hp -= sum(module.rounded(module.rounded(10 * (1 + per * min(zapped + z, 10))) * .9)
                              for z in range(3))
                    zapped += 3
                    events.append({"target_valid": True, "target_hpMax": 15000, "target_hpExact": hp,
                                   "now": 10000 + start + at, "elapsed": start + at})
            if self.levels.get(module.CLAP, 0) and math.dist((last_x, 0), (target["x"], target["y"])) <= 75:
                hp -= module.rounded(module.rounded(15) * .9)
                events.append({"target_valid": True, "target_hpMax": 15000, "target_hpExact": hp,
                               "now": 10000 + start + 3000, "elapsed": start + 3000})
            events.append({"target_valid": True, "target_hpMax": 15000, "target_hpExact": hp,
                           "now": 14224, "elapsed": 4224})
            self.observation = {"usable": True, "events": events}
            self.after = copy.deepcopy(self.before)
            self.after[self.uid]["hpExact"] = hp
            if damage_outside:
                for uid, row in self.after.items():
                    if uid != self.uid:
                        row["hpExact"] -= 1

    instances = []

    def make_checks(pilot):
        instance = Checks(pilot)
        instances.append(instance)
        return instance

    def spawn(checks, direction, offsets):
        checks.before = {100 + index: {"unit": 100 + index, "x": forward, "y": side,
                                      "hpMax": 15000, "hpExact": 15000}
                         for index, (forward, side) in enumerate(offsets)}
        return copy.deepcopy(checks.before)

    def collect(game, tag, timeout, *, expected=None):
        assert tag == game.checks.observer_tag
        if expected is not None:
            assert expected == {"buff": "-", "stack": module.STACK, "target_unit": game.checks.uid}
            game.checks.identity_calls.append(expected)
        return copy.deepcopy(game.checks.observation)

    replacements = {"Checks": make_checks, "spawn": spawn, "wait_ready": lambda checks: True,
                    "collect": collect, "checkpoint": lambda *args, **kwargs: None}
    if hasattr(module, "targets"):
        replacements["targets"] = lambda checks: copy.deepcopy(checks.after)
    if reject_geometry and hasattr(module, "expiry_geometry"):
        replacements["expiry_geometry"] = lambda *args: {"valid": False}
    with ExitStack() as stack:
        stack.enter_context(patch.dict(module.__dict__, replacements))
        result = module.run(None, section="orb_damage")
    return {"result": result, "identity_calls": len(instances[0].identity_calls)}


class CurrentSpeedClapGeometryTests(unittest.TestCase):
    @staticmethod
    def fixture():
        before = {1: {"unit": 1, "x": 130, "y": 0, "hpMax": 15000, "hpExact": 15000},
                  2: {"unit": 2, "x": 130, "y": 160, "hpMax": 15000, "hpExact": 15000}}
        import copy
        after = copy.deepcopy(before)
        after[1]["hpExact"] = 14770
        trace = {"most": 1, "truncated": 0,
                 "tracks": [{"n": 91, "t0": 132, "t1": 3102,
                             "x0": 8, "y0": 0, "x1": 188, "y1": 0}]}
        return before, after, trace

    def test_real_bot_fake_transport_current_speed_passes_all_fixed_clap_trials(self):
        import gamelab.bots.qa_specs_wizard_orbs as module
        result = fake_current_speed_run(module)
        self.assertTrue(all(result["result"][f"clap_{trial}_natural_expiry_extra_damage"] for trial in (1, 2, 3)))
        self.assertEqual(result["identity_calls"], 12)
        claps = [row for row in result["result"]["cases"] if row.get("orb") == module.CLAP]
        self.assertEqual(len(claps), 3)
        self.assertTrue(all(row["expiry_geometry"]["valid"] for row in claps))

    def test_original_target85_is_outside_measured_expiry_radius(self):
        from gamelab.bots.qa_specs_wizard_orbs import expiry_geometry
        before, after, trace = self.fixture()
        before[1]["x"] = after[1]["x"] = 85
        self.assertFalse(expiry_geometry(before, after, 1, 2, trace, (1, 0))["valid"])

    def test_wall_stop_cannot_hide_free_flight_fixture_drift(self):
        from gamelab.bots.qa_specs_wizard_orbs import expiry_geometry
        before, after, trace = self.fixture()
        trace["tracks"][0]["x1"] = 150
        self.assertFalse(expiry_geometry(before, after, 1, 2, trace, (1, 0))["valid"])

    def test_nearby_outside_or_damaged_control_is_refused(self):
        from gamelab.bots.qa_specs_wizard_orbs import expiry_geometry
        for mutation in ("inside", "damage", "move", "missing", "nonfinite", "truncated"):
            with self.subTest(mutation=mutation):
                before, after, trace = self.fixture()
                if mutation == "inside":
                    before[2]["y"] = after[2]["y"] = 0
                elif mutation == "damage":
                    after[2]["hpExact"] -= 1
                elif mutation == "move":
                    after[2]["x"] += 2
                elif mutation == "missing":
                    after.pop(2)
                elif mutation == "nonfinite":
                    trace["tracks"][0]["x1"] = float("nan")
                else:
                    trace["truncated"] = 1
                self.assertFalse(expiry_geometry(before, after, 1, 2, trace, (1, 0))["valid"])

    def test_positive_expiry_endpoint_is_measured_and_not_an_estimated_85px_target(self):
        from gamelab.bots.qa_specs_wizard_orbs import expiry_geometry
        before, after, trace = self.fixture()
        geometry = expiry_geometry(before, after, 1, 2, trace, (1, 0))
        self.assertTrue(geometry["valid"])
        self.assertEqual(geometry["inside_distance"], 58)
        self.assertGreater(geometry["outside_distance"], 75)

    def test_untouched_control_and_geometry_are_actual_run_gates(self):
        import gamelab.bots.qa_specs_wizard_orbs as module
        for options in ({"damage_outside": True}, {"reject_geometry": True}):
            with self.subTest(options=options):
                result = fake_current_speed_run(module, **options)["result"]
                self.assertTrue(all(not result[f"clap_{trial}_natural_expiry_extra_damage"] for trial in (1, 2, 3)))

if __name__ == "__main__":
    unittest.main()
