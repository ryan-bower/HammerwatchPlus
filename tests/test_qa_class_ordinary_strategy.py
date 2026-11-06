"""Unexecuted draft: actual Python branches with fake native boundaries.

No game/process/file writes. Tests do not prove live combat, geometry or survival.
Import from an applied/sandbox package only; do not execute ignored drafts in place.
"""
from collections import deque
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gamelab.bots import floor_runner as floor
from gamelab.bots import qa_class_integration as integration


class Clock:
    now = 0.0

    def read(self):
        return self.now


def result(kind, reason, intent="kite", event=None):
    return SimpleNamespace(result=kind, reason=reason, intent=intent, id="fake-native", tick=1,
                           event=event or {}, ok=kind == "done")


def enemy(uid=41, dist=160):
    return {"unit": uid, "name": "actors/humans/bandits/bandit_rogue.unit",
            "x": dist, "y": 0., "dist": dist, "hp": 1.0}


def scan(rows=(), place="bandit_keep/keep_1"):
    return {"ok": True, "place": place, "enemyCount": len(rows), "enemies": list(rows), "exitCount": 1}


def wolf_reply():
    return {"ok": True, "truncated": 0, "count": 1, "units": [
        {"unit": 99, "name": "players/ranger/units/wolf.unit", "dead": False,
         "hpMax": 500, "hpExact": 264., "x": 0., "y": 1., "dist": 1.}]}


class FakePilot:
    """Only boundary replies are scripted; production strategy/validation executes."""
    def __init__(self, scans=(), kites=(), exits=()):
        self.clock = Clock()
        self.calls, self.notes = [], []
        self.scans, self.kites, self.exits = map(deque, (scans, kites, exits))
        self.dead, self.phase, self.place, self.hp, self.xp = False, "mission", "bandit_keep/keep_1", 145, 42224
        self.state_cost, self.kite_cost = 0., 0.1
        self.game = SimpleNamespace(note=lambda *a, **kw: self.notes.append((a, deepcopy(kw))))

    def description(self):
        """Use real ranged-driver metadata; native ClassPilot remains mocked."""
        from gamelab.bots.qa_class_drive import ClassPilot
        return ClassPilot.description(SimpleNamespace(melee=False))

    def state(self):
        self.calls.append(("state",))
        self.clock.now += self.state_cost
        return {"ok": True, "phase": "dead" if self.dead else self.phase, "player": {
            "class": "hwp_witch_hunter", "name": "QAHunterRun", "level": 5, "xp": self.xp,
            "dead": self.dead, "spawned": not self.dead, "hp": self.hp, "hpMax": 145, "x": 0., "y": 0.}}

    def reflex(self, **kw):
        self.calls.append(("reflex", kw))
        return {"ok": True, "reflexPotion": kw["potion"], "reflexFire": kw["fire"]}

    def scan(self, radius):
        self.calls.append(("scan", radius))
        return deepcopy(self.scans.popleft()) if self.scans else scan(place=self.place)

    def status(self):
        self.calls.append(("status",))
        return {"ok": True, "x": 0., "y": 0., "reflexPotions": 0}

    def kite(self, target, rng, **kw):
        self.calls.append(("kite", target, rng, deepcopy(kw)))
        self.clock.now += min(self.kite_cost, kw["timeout"])
        end = self.kites.popleft() if self.kites else result("done", "target dead")
        if end.reason == "dead":
            self.dead, self.hp = True, -2
        return end

    def exit(self, **kw):
        self.calls.append(("exit", deepcopy(kw)))
        self.clock.now += .1
        next_place = "bandit_keep/keep_" + str(int(self.place.rsplit("_", 1)[-1]) + 1)
        end = self.exits.popleft() if self.exits else result("done", "level_changed", "exit", {"place_to": next_place})
        if end.ok:
            self.place, self.xp = end.event["place_to"], self.xp + 1
        elif end.reason == "under_attack":
            self.hp = 128
        return end


class StrategyTests(unittest.TestCase):
    def run_floor(self, pilot, **kw):
        with patch.object(floor.time, "monotonic", pilot.clock.read):
            return floor.run(pilot, budget_s=kw.pop("budget_s", 180), combat_before_travel=True, **kw)

    def test_nearby_native_target_is_fought_before_exit(self):
        p = FakePilot(scans=[scan([enemy()]), scan()])
        out = self.run_floor(p)
        actions = [x[0] for x in p.calls]
        self.assertLess(actions.index("kite"), actions.index("exit"))
        fight = next(x for x in p.calls if x[0] == "kite")
        self.assertEqual(fight[1:3], (41, 90))
        self.assertEqual(fight[3]["until"], ["dead", "target_dead"])
        self.assertEqual(out["terminal"], "next_floor")
        self.assertEqual(out["fights"], 1)

    def test_actual_under_attack_result_enters_combat_then_requires_exit(self):
        p = FakePilot(scans=[scan(), scan([enemy()]), scan()], exits=[result("interrupted", "under_attack", "path_to")])
        out = self.run_floor(p)
        exits = [x for x in p.calls if x[0] == "exit"]
        self.assertEqual(len(exits), 2)
        self.assertEqual(exits[0][1]["until"], ["dead", "under_attack", "hp_below:30"])
        self.assertEqual(out["routes"][0]["reason"], "under_attack")
        self.assertEqual(out["terminal"], "next_floor")

    def test_dead_kite_cannot_issue_postdeath_scan_or_second_exit(self):
        p = FakePilot(scans=[scan([enemy()])], kites=[result("interrupted", "dead")])
        out = self.run_floor(p)
        self.assertEqual(out["terminal"], "died")
        self.assertEqual([x[0] for x in p.calls].count("scan"), 1)
        self.assertFalse(any(x[0] == "exit" for x in p.calls))
        self.assertEqual(p.calls[-1][0], "kite")
        self.assertEqual(out["combat"][0]["result"]["reason"], "dead")

    def test_refused_malformed_nonfinite_or_truncated_scan_cannot_be_empty(self):
        bad = [None, {"ok": False, "error": "no spawned local player"},
               {**scan(), "enemies": None}, {**scan(), "enemyCount": 1},
               {**scan(), "truncated": True}, scan([enemy(1), enemy(1)]),
               scan([{**enemy(), "dist": float("nan")}]), scan([{**enemy(), "unit": True}]),
               scan([enemy(i + 1) for i in range(32)])]
        for reply in bad:
            with self.subTest(reply=reply):
                p = FakePilot(scans=[reply])
                out = self.run_floor(p)
                self.assertEqual(out["terminal"], "observation_failed")
                self.assertEqual(out["observations"][-1]["status"], "UNRUN")
                self.assertFalse(any(x[0] in ("kite", "exit") for x in p.calls))

    def test_timeout_is_retained_as_combat_failure_not_retried(self):
        p = FakePilot(scans=[scan([enemy()])], kites=[result("timeout", "after 20000 ms")])
        out = self.run_floor(p)
        self.assertEqual(out["terminal"], "combat_failed")
        self.assertEqual(out["combat"][0]["result"]["result"], "timeout")
        self.assertEqual(len([x for x in p.calls if x[0] == "kite"]), 1)
        self.assertFalse(any(x[0] == "exit" for x in p.calls))

    def test_failed_result_with_target_dead_label_is_not_a_success(self):
        p = FakePilot(scans=[scan([enemy()])], kites=[result("failed", "target_dead")])
        out = self.run_floor(p)
        self.assertEqual(out["terminal"], "combat_failed")
        self.assertFalse(any(x[0] == "exit" for x in p.calls))

    def test_six_episodes_is_a_failure_bound_not_success_or_reset(self):
        p = FakePilot(scans=[scan([enemy(i + 1)]) for i in range(7)])
        out = self.run_floor(p)
        self.assertEqual(out["terminal"], "combat_limit")
        self.assertEqual(len([x for x in p.calls if x[0] == "kite"]), 6)
        self.assertFalse(any(x[0] == "exit" for x in p.calls))

    def test_intent_timeout_uses_remaining_floor_budget(self):
        p = FakePilot(scans=[scan([enemy()])], kites=[result("timeout", "budget")])
        p.state_cost = 6
        out = self.run_floor(p, budget_s=7)
        fight = next(x for x in p.calls if x[0] == "kite")
        self.assertLessEqual(fight[3]["timeout"], 1)
        self.assertEqual(out["terminal"], "combat_failed")

    def test_budget_expiry_cannot_dispatch_intent(self):
        p = FakePilot(scans=[scan([enemy()])])
        p.state_cost = 180
        out = self.run_floor(p)
        self.assertEqual(out["terminal"], "budget")
        self.assertFalse(any(x[0] in ("kite", "exit") for x in p.calls))

    def test_optout_still_executes_original_strategy_and_interrupts(self):
        p = FakePilot()
        out = floor.run(p, budget_s=180)
        self.assertEqual(out["terminal"], "next_floor")
        self.assertEqual([x[1] for x in p.calls if x[0] == "scan"], [400])
        self.assertEqual(next(x for x in p.calls if x[0] == "exit")[1]["until"], ["hp_below:30", "dead"])


class FakeChecks(integration.Checks):
    def __init__(self, pilot, censuses=()):
        super().__init__(pilot)
        self.censuses = deque(censuses)
        self.near_calls, self.returned = 0, False
        pilot.phase = "town"

    def gl(self, verb, *args, **kw):
        if verb == "state":
            return self.p.state()
        if verb == "cvars":
            return {"ok": True, "cvars": {"cht_god": 0}}
        if verb == "mission":
            self.p.phase = "mission"
            return {"ok": True}
        if verb == "inspect":
            return {"ok": True, "value": ["same-native-equipment-record"]}
        if verb == "benchstats":
            return {"ok": True, "mhPhys": 46}
        if verb == "inv":
            return {"ok": True, "materials": {"gold": 0}}
        if verb == "near":
            self.near_calls += 1
            return deepcopy(self.censuses.popleft()) if self.censuses else wolf_reply()
        raise AssertionError("unexpected fake-native command: " + verb)

    def to_town(self):
        # The known separate abandonment boundary is outside these fake controls.
        self.returned = True
        return True


class OrdinaryIntegrationTests(unittest.TestCase):
    def run_ordinary(self, checks):
        with patch.object(integration.time, "sleep", lambda _: None), \
                patch.object(floor.time, "monotonic", checks.p.clock.read), \
                patch.object(integration, "ClassPilot", lambda p, cls: p):
            # The unchanged ClassPilot geometry/native boundary is separately reviewed.
            # Checks.ordinary and the actual new floor_runner branch both execute.
            checks.ordinary("hwp_witch_hunter", floors=2, budget_s=180, combat_before_travel=True)
        return checks.out

    def test_actual_ordinary_optin_requires_two_native_place_changes(self):
        p = FakePilot()
        c = FakeChecks(p)
        out = self.run_ordinary(c)
        self.assertTrue(out["ordinary_floors"])
        self.assertTrue(out["ordinary_class_survives"])
        self.assertTrue(out["ordinary_rewards"])
        self.assertTrue(out["ordinary_summon_after_floor"])
        self.assertEqual(len(out["ordinary_samples"]), 2)
        self.assertTrue(all(x["strategy"] == "combat_before_travel" for x in out["ordinary_samples"]))
        self.assertEqual(len([x for x in p.calls if x[0] == "exit"]), 2)

    def test_death_keeps_original_flags_false_and_after_census_unrun(self):
        p = FakePilot(scans=[scan([enemy()])], kites=[result("interrupted", "dead")])
        c = FakeChecks(p)
        out = self.run_ordinary(c)
        for key in ("ordinary_floors", "ordinary_class_survives", "ordinary_summon_after_floor"):
            self.assertIs(out[key], False)
        self.assertEqual(out["ordinary_summon_after"]["status"], "UNRUN")
        self.assertIsNone(out["ordinary_summon_after"]["units"])
        self.assertEqual(c.near_calls, 1)  # Before only; no refused query disguised as[].
        self.assertFalse(any(x[0] == "exit" for x in p.calls))

    def test_refused_before_census_cannot_start_floor_driver(self):
        p = FakePilot()
        c = FakeChecks(p, censuses=[{"ok": False, "error": "refused"}])
        out = self.run_ordinary(c)
        self.assertEqual(out["ordinary_summon_before"]["status"], "UNRUN")
        self.assertIs(out["ordinary_floors"], False)
        self.assertIs(out["ordinary_summon_after_floor"], False)
        self.assertFalse(any(x[0] in ("scan", "kite", "exit") for x in p.calls))

    def test_successful_floors_do_not_hide_truncated_after_census(self):
        c = FakeChecks(FakePilot(), censuses=[wolf_reply(), {**wolf_reply(), "truncated": 1}])
        out = self.run_ordinary(c)
        self.assertTrue(out["ordinary_floors"])
        self.assertIs(out["ordinary_summon_after_floor"], False)
        self.assertEqual(out["ordinary_summon_after"]["status"], "UNRUN")
        self.assertIsNone(out["ordinary_summon_after"]["units"])

    def test_actual_census_distinguishes_valid_empty_from_unusable(self):
        bad = [None, {"ok": False}, {"ok": True, "count": 0, "truncated": 0},
               {**wolf_reply(), "count": 2}, {**wolf_reply(), "truncated": True},
               {**wolf_reply(), "units": [{**wolf_reply()["units"][0], "hpMax": float("nan")}]}]
        for reply in bad:
            with self.subTest(reply=reply):
                c = FakeChecks(FakePilot(), censuses=[reply])
                c.p.phase = "mission"
                observed = c.summon_census("players/ranger/units/wolf", c.p.state())
                self.assertEqual(observed["status"], "UNRUN")
                self.assertIsNone(observed["units"])
        c = FakeChecks(FakePilot(), censuses=[{"ok": True, "count": 0, "truncated": 0, "units": []}])
        c.p.phase = "mission"
        observed = c.summon_census("players/ranger/units/wolf", c.p.state())
        self.assertEqual(observed["status"], "OBSERVED")
        self.assertEqual(observed["units"], [])


if __name__ == "__main__":
    unittest.main()
