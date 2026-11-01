"""Durable fake controls for town harness oracles; never constructs a Game or Pilot.

Optional HWP_TOWN_TEST_SOURCE redirects only source imports/JSON reads to an
explicit isolated snapshot. No launch, native calls, profile access or writes.
"""
import copy
import importlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

SOURCE = Path(os.environ.get("HWP_TOWN_TEST_SOURCE", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(SOURCE))


class Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += .001
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


def load(name):
    return importlib.import_module("gamelab.bots." + name)


def use_clock(test, module):
    previous = module.time
    module.time = Clock()
    test.addCleanup(setattr, module, "time", previous)


def optional_oracle(test):
    try:
        return load("qa_town_economy_oracle")
    except ModuleNotFoundError:
        test.fail("candidate's independent town oracle is absent")


def fake_farm(test, price=200):
    module = load("plan_farming")
    use_clock(test, module)

    class Farm(module.Checks):
        def __init__(self):
            self.out, self.notes = {}, []
            self.balance, self.can = 5000, False
            self.g = SimpleNamespace(read_log=lambda: "")

        def grooves(self):
            return {"v": ["vertical"], "h": ["horizontal"]}

        def farmer(self):
            return {"x": 0, "y": 5}

        def bbox(self, grooves):
            return (-10, 0, -5, 10) if grooves == ["vertical"] else (5, 0, 10, 10)

        def set_gold(self, amount):
            self.balance = amount

        def gold(self):
            return self.balance

        def shop(self):
            return {"ok": True, "window": "HWPFarmMenu"}

        def top_widget(self, name):
            return {"text": "Water: 4/4" if self.can else "No watering can"}

        def gl(self, verb, *args, **kwargs):
            if (verb, args) == ("press", ("row-0",)):
                self.balance -= price
                self.can = True
            elif (verb, args) == ("press", ("row-1",)):
                self.balance -= 20
            else:
                raise AssertionError((verb, args))
            return {"ok": True}

        def farm_say(self, mark):
            return ["Cabbage seed bought"]

        def close_windows(self):
            return True

    return Farm()


def fake_traps(test, caught=0, stored=None, missing_units=False):
    module = load("plan_fishing")
    use_clock(test, module)
    stored = list(stored if stored is not None else (caught, 0, 0))

    class Traps(module.Checks):
        def __init__(self):
            self.out, self.notes, self.commands = {}, [], []
            self.phase, self.contents, self.log = "town", [0, 0, 0], ""
            self.g = SimpleNamespace(read_log=lambda: self.log, shot=lambda *a: None)

        def fresh(self, name):
            return True

        def start_floor(self, floor):
            self.phase = "mission"
            return True

        def to_town(self):
            self.phase, self.contents = "town", list(stored)
            self.log += f"\n[HWP:fishing] traps: 21 min run, 2 rolls, {caught} fish\n"

        def hwp(self, command, *args, **kwargs):
            self.commands.append(command)
            if command == "fishing traps 60":
                self.contents = [1, 1, 1]  # model debug injection on the original path
            if command == "fishing traps":
                if self.phase == "mission":
                    return "This run so far: 21 min"
                parts = "; ".join(f"{i+1}: " + (",".join(["perch"]*n) if n else "-")
                                  for i, n in enumerate(self.contents))
                return "[HWP] Fish traps 3/3: " + parts + ". This run so far: 0 min"
            return ""

        def gl(self, verb, *args, **kwargs):
            if verb == "near":
                return {"units": [] if missing_units else
                        [{"unit": i+1, "x": 0, "y": i*100}
                         for i, n in enumerate(self.contents) if n]}
            if verb == "mapicons":
                return {"minimap": True, "uiMinimap": True, "units": [{"icon": True, "hidden": False}]}
            if verb in ("kill", "timescale", "menu"):
                return {"ok": True}
            raise AssertionError((verb, args))

        def trap_approach(self, unit, **kwargs):
            return (0, 0), "fake legal geometry"

    return Traps()


def fake_roulette(test, credit_error=0):
    module = load("fix_roulette")
    use_clock(test, module)

    class Roulette(module.Checks):
        def __init__(self):
            self.out, self.notes = {}, []
            self.balance, self.stakes, self.spinning = 50000, {}, False
            self.log = "the wheel is on doodads/furniture/table_wood_poor_h.unit at 0,-200\n"
            self.g = SimpleNamespace(read_log=lambda: self.log, shot=lambda *a: None)

        def gold(self):
            return self.balance

        def set_gold(self, amount):
            self.balance = amount

        def status(self):
            return ("1", "0", "20", "20", "0", "157")

        def wait_phase(self, *args, **kwargs):
            self.spinning = False
            return self.status()

        def go_wheel(self):
            return [{"unit": 5, "x": 0, "y": -205}]

        def wheel_scene(self):
            return "spin" if self.spinning else "idle"

        def window(self):
            return "HWPRouletteMenu"

        def gl(self, verb, *args, **kwargs):
            if verb == "buildings":
                return {"buildings": {"tavern": 0}}
            if verb == "near":
                return {"units": [{"unit": 1, "x": 0, "y": -200, "scene": "default"}]}
            if verb == "use":
                return {"ok": True}
            if verb == "material":
                self.balance += args[1]
                return {"ok": True}
            if verb == "economyinputs":
                return {"ok": True, "luck": 20.0, "goldMul": 1.0, "goldMulMul": 1.0, "gold": self.balance}
            raise AssertionError((verb, args))

        def hwp(self, command, *args, **kwargs):
            words = command.split()
            if words[:2] == ["roulette", "bet"]:
                key, amount = words[2], int(words[3])
                if sum(self.stakes.values()) + amount > 1000000:
                    return "no bet: table limit"
                if amount > self.balance:
                    return "no bet: no gold"
                self.balance -= amount
                self.stakes[key] = self.stakes.get(key, 0) + amount
                return f"bet {amount} on {key}"
            if words[:2] == ["roulette", "clear"]:
                self.balance += sum(self.stakes.values())
                self.stakes.clear()
                return "cleared"
            if words[:2] == ["roulette", "spin"]:
                # Fixed independent fixture outcome: 1000 s17,c13,odd win, red loses.
                amount = 55800 + credit_error
                self.log += f"round 1 landed 17: staked 4000, paid {amount}\n"
                self.balance += amount
                self.stakes.clear()
                self.spinning = True
                return "the ball lands on 17"
            return ""

    return Roulette()


class ExistingConsumerControls(unittest.TestCase):
    def test_authored_200g_purchase_is_required_and_passes(self):
        c = fake_farm(self, 200)
        c.farmer_buy()
        self.assertIs(c.out.get("s2_can_price_200"), True, c.out)
        scenario = json.loads((SOURCE/"gamelab/scenarios/plan-farming-a.json").read_text())
        step = next(s for s in scenario["steps"] if s.get("kwargs", {}).get("sections") == "farmer_buy")
        self.assertIn("s2_can_price_200", step["kwargs"]["required_flags"])
        self.assertIs(step["expect"].get("ok"), True)

    def test_wrong_150g_debit_is_rejected(self):
        c = fake_farm(self, 150)
        c.farmer_buy()
        self.assertIs(c.out.get("s2_can_price_200"), False, c.out)

    def test_lost_ack_after_debit_is_dispatched_once(self):
        module = load("plan_checks")
        use_clock(self, module)
        game = SimpleNamespace(calls=[], gold=1000)
        game.read_log = lambda: ""
        def applied_without_ack(line):
            game.calls.append(line)
            game.gold -= 200
        game.console = applied_without_ack
        c = module.Checks(SimpleNamespace(game=game))
        try:
            c.hwp("farm buy can", wait=0, until="Bought", timeout=0)
        except RuntimeError:
            pass
        self.assertEqual(game.calls, ["hwp farm buy can"])
        self.assertEqual(game.gold, 800)
        self.assertIs(c.out.get("hwp_unconfirmed_dispatch"), False)

    def test_missing_ack_stops_the_section(self):
        module = load("plan_checks")
        use_clock(self, module)
        c = module.Checks(SimpleNamespace(game=SimpleNamespace(read_log=lambda: "", console=lambda *a: None)))
        with self.assertRaisesRegex(RuntimeError, "sent once"):
            c.hwp("fishing buy trap", wait=0, until="trap bought", timeout=0)

    def test_natural_zero_retains_zero_without_debug_replacement(self):
        c = fake_traps(self, 0)
        c.traps_run()
        self.assertNotIn("fishing traps 60", c.commands)
        self.assertEqual(c.contents, [0, 0, 0])
        self.assertIs(c.out["coverage"]["natural_traps"]["positive_observed"], False)
        self.assertIs(c.out.get("traps_natural_conserved"), True)
        self.assertIs(c.out["coverage"]["trap_visual"]["observed"], False)

    def test_positive_natural_sample_checks_exact_stored_count(self):
        c = fake_traps(self, 1, stored=[1, 0, 0])
        c.traps_run()
        self.assertIs(c.out.get("traps_natural_conserved"), True, c.out)
        self.assertIs(c.out.get("traps_full_shown"), True)

    def test_wrong_natural_count_is_rejected(self):
        c = fake_traps(self, 1, stored=[2, 0, 0])
        c.traps_run()
        self.assertIs(c.out.get("traps_natural_conserved"), False, c.out)

    def test_positive_contents_with_missing_units_is_rejected(self):
        c = fake_traps(self, 1, missing_units=True)
        c.traps_run()
        self.assertIs(c.out.get("traps_full_shown"), False, c.out)

    def test_clean_roulette_credit_is_accepted(self):
        c = fake_roulette(self, 0)
        c.roulette()
        self.assertIs(c.out.get("rl_payout"), True, c.out)

    def test_one_gold_credit_error_is_rejected(self):
        c = fake_roulette(self, 1)
        c.roulette()
        self.assertIs(c.out.get("rl_payout"), False, c.out)

    def test_old_tolerance_edge_267_gold_is_rejected(self):
        c = fake_roulette(self, 267)
        c.roulette()
        self.assertIs(c.out.get("rl_payout"), False, c.out)

    def test_268_gold_error_negative_control(self):
        c = fake_roulette(self, 268)
        c.roulette()
        self.assertIs(c.out.get("rl_payout"), False, c.out)


class NewOracleControls(unittest.TestCase):
    def test_exact_f32_luck_one_boundary(self):
        oracle = optional_oracle(self)
        stakes = {"s:17":1000, "c:13":1000, "odd":1000, "red":1000}
        inputs = {"ok":True, "luck":1.0, "goldMul":1.0, "goldMulMul":1.0}
        # Exact binary32 factor1.0099999904632568 truncates each winning credit.
        self.assertEqual(oracle.credit(stakes, 17, inputs), 47437)

    def test_zero_bonus_and_zero_number_have_independent_fixed_answers(self):
        oracle = optional_oracle(self)
        inputs = {"ok":True, "luck":0.0, "goldMul":1.0, "goldMulMul":1.0}
        self.assertEqual(oracle.credit({"s:17":1000,"c:13":1000,"odd":1000,"red":1000}, 17, inputs), 47000)
        self.assertEqual(oracle.credit({"s:0":1000,"f4":1000,"even":1000}, 0, inputs), 45000)

    def test_raw_modifier_failures_are_not_defaulted(self):
        oracle = optional_oracle(self)
        good = {"ok":True, "luck":20.0, "goldMul":1.0, "goldMulMul":1.0}
        for field in ("luck","goldMul","goldMulMul"):
            for bad in (None, True, "20", float("nan"), float("inf")):
                with self.subTest(field=field, bad=bad):
                    changed = dict(good, **{field:bad})
                    with self.assertRaises((ValueError, KeyError)):
                        oracle.credit({"s:17":1000}, 17, changed)

    def test_one_gold_debit_or_credit_cannot_hide(self):
        oracle = optional_oracle(self)
        stakes = {"s:17":1000,"red":1000}
        self.assertTrue(oracle.ledger(50000,48000,84000,stakes,36000))
        self.assertFalse(oracle.ledger(50000,47999,83999,stakes,36000))
        self.assertFalse(oracle.ledger(50000,48000,84001,stakes,36000))

    def test_missing_required_and_hidden_failure_are_rejected(self):
        oracle = optional_oracle(self)
        self.assertFalse(oracle.assess({"good":True},["good","missing"])["ok"])
        self.assertFalse(oracle.assess({"good":True,"unclaimed_crash":False},["good"])["ok"])
        self.assertFalse(oracle.assess({},[])["ok"])
        self.assertTrue(oracle.assess({"good":True},["good"])["ok"])

    def test_legacy_decoded_json_is_not_complete_native_identity(self):
        oracle = optional_oracle(self)
        reply = {"ok":True,"truncated":False,"value":[
            {"id":"mace","quality":4,"level":1,"upgrades":0,"color":[.2,.3,.4],
             "mods":[{"id":"damage","intensity":.123456789}]}]}
        # Historical v1 only preserved supplied JSON and bypassed six-digit transport.
        with self.assertRaises(ValueError):
            oracle.equipment_identity(reply)

    def test_failed_or_empty_equipment_read_cannot_prove_preservation(self):
        oracle = optional_oracle(self)
        for reply in ({}, {"ok":False,"truncated":False,"value":[{}]},
                      {"ok":True,"truncated":True,"value":[{"id":"mace"}]},
                      {"ok":True,"truncated":False,"value":[]},
                      {"ok":True,"truncated":False,"value":[None]},
                      {"ok":True,"truncated":False,"value":[{}]}):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                oracle.equipment_identity(reply)

    def test_restart_requires_real_original_gold_and_cleared_owed(self):
        try:
            module = load("qa_town_roulette_restart")
        except ModuleNotFoundError:
            self.fail("candidate's restart verifier is absent")
        use_clock(self, module)
        for golds, owed, identity, want in (
            ([50000,50000],[0,0],[True,True],True),
            ([57000,57000],[0,0],[True,True],False),
            ([43000,43000],[7000,7000],[True,True],False),
            ([50000,50001],[0,0],[True,True],False),
            ([50000,50000],[0,0],[False,False],False)):
            with self.subTest(golds=golds,owed=owed,identity=identity):
                c = module.Checks.__new__(module.Checks)
                c.out, c.notes, events = {}, [], []
                g, o, who = iter(golds), iter(owed), iter(identity)
                c.identity=lambda: (events.append("identity"),next(who))[1]
                c.gold=lambda: (events.append("gold"),next(g))[1]
                c.owed=lambda: (events.append("owed"),next(o))[1]
                c.verify()
                self.assertIs(c.out["restart_refund_once"],want)
                self.assertEqual(events,["identity","gold","owed","identity","gold","owed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

