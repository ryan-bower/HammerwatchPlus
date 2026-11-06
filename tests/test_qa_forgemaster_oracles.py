"""Fake RPC observations for Forgemaster boss rows and actual runner scoring.

No game, fixture setup, source writes, generation or input APIs are used.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from gamelab.bots import plan_forgemaster as bot
from gamelab.runner import check

SCENARIO_ROOT = Path(__file__).resolve().parents[1]
BOSS = "bosses/boss_bandit/boss_bandit_encounter.unit"


class ForgemasterOracles(unittest.TestCase):
    def collector(self, bodies, *, spawned=(True, True, True), killed=(1, 1, 1),
                  kill_ok=(True, True, True), counters=(10, 13), fail_trial=None):
        c = bot.Checks.__new__(bot.Checks)
        c.out, c.notes = {}, []
        c.setup_forge, c.to_arena = Mock(), Mock(return_value=True)
        c.bind = Mock(side_effect=[0, 1])
        c.forge_status = Mock(side_effect=[
            "forge: status missing" if n is None else f"forge: rolls {n}" for n in counters
        ])
        c.cull, c.origin = Mock(), Mock()
        body_values = iter(bodies)
        spawn_values, kill_values, kill_flags = iter(spawned), iter(killed), iter(kill_ok)
        current = {"trial": 0}

        def rpc(verb, *args):
            if verb == "spawn":
                current["trial"] += 1
                ok = next(spawn_values)
                return {"ok": ok, "unit": 100 + current["trial"],
                        "name": BOSS, "detail": f"spawn-{current['trial']}"}
            if verb == "kill":
                if current["trial"] == fail_trial:
                    raise RuntimeError("controlled RPC failure")
                return {"ok": next(kill_flags), "killed": next(kill_values),
                        "detail": f"death-{current['trial']}"}
            if verb == "orb":
                return {"ok": True}
            raise AssertionError(f"Unexpected live RPC path: {verb} {args}")

        def body_reply(*args, **kwargs):
            if args[0] != "forge bodies":
                raise AssertionError(f"Unexpected console path: {args}")
            n = next(body_values)
            return f"forge bodies {n}: " + " | ".join(
                f"{200 + i} {BOSS} at 120 0 ttl 59000 boss glow 1" for i in range(n)
            )

        c.gl, c.hwp = rpc, body_reply
        # No real Game/Pilot exists: any unmocked live path fails immediately.
        c.g = Mock(spec=[])
        return c

    def run_bosses(self, bodies, **kwargs):
        c = self.collector(bodies, **kwargs)
        with patch.object(bot.time, "sleep"):
            c.orb_boss()
        return c.out

    def test_final_success_cannot_hide_two_missing_bodies(self):
        result = self.run_bosses((0, 0, 1))
        self.assertFalse(result["orb_boss_always"])
        self.assertEqual([r["bodies"] for r in result["orb_boss_rows"]], [0, 0, 1])

    def test_middle_missing_body_is_retained_and_failed(self):
        result = self.run_bosses((1, 0, 1))
        self.assertFalse(result["orb_boss_always"])
        self.assertEqual(result["orb_boss_rows"][1]["bodies"], 0)

    def test_three_independent_deaths_preserve_all_raw_results(self):
        result = self.run_bosses((1, 1, 1))
        self.assertTrue(result["orb_boss_always"])
        rows = result.get("orb_boss_rows", [])
        self.assertEqual(len(rows), 3)
        for trial, row in enumerate(rows, 1):
            self.assertEqual(row["trial"], trial)
            self.assertEqual(row["spawn"]["detail"], f"spawn-{trial}")
            self.assertEqual(row["kill"]["detail"], f"death-{trial}")
            self.assertIn("ttl 59000 boss glow 1", row["body_status"])

    def test_body_text_does_not_mask_failed_spawn_or_death(self):
        for override in ({"spawned": (False, True, True)}, {"killed": (0, 1, 1)},
                         {"kill_ok": (False, True, True)}, {"killed": (True, 1, 1)}):
            with self.subTest(override=override):
                self.assertFalse(self.run_bosses((1, 1, 1), **override)["orb_boss_always"])

    def test_duplicate_drop_is_not_one_body_per_death(self):
        self.assertFalse(self.run_bosses((1, 2, 1))["orb_boss_always"])

    def test_missing_roll_endpoint_cannot_be_zero_default(self):
        for counters in ((None, 13), (10, None)):
            with self.subTest(counters=counters):
                self.assertFalse(self.run_bosses((1, 1, 1), counters=counters)["orb_boss_always"])

    def test_completed_rows_survive_a_later_rpc_exception(self):
        c = self.collector((1, 1, 1), fail_trial=3)
        with patch.object(bot.time, "sleep"), self.assertRaisesRegex(RuntimeError, "controlled RPC"):
            c.orb_boss()
        rows = c.out.get("orb_boss_rows", [])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["bodies"], 1)
        self.assertEqual(rows[1]["kill"]["detail"], "death-2")
        self.assertEqual(rows[2]["spawn"]["detail"], "spawn-3")
        self.assertNotIn("orb_boss_always", c.out)

    def lunge_steps(self):
        for name in ("plan-forgemaster", "plan-forgemaster-bosses", "plan-forgemaster-eat"):
            doc = json.loads((SCENARIO_ROOT / "gamelab/scenarios" / f"{name}.json").read_text())
            steps = [s for s in doc["steps"] if s.get("bot") == "plan_forgemaster"
                     and "lunge" in s.get("kwargs", {}).get("sections", "").split(",")]
            self.assertTrue(steps, name)
            for step in steps:
                yield name, step["expect"]

    def test_actual_runner_rejects_false_healing_observation(self):
        for name, expected in self.lunge_steps():
            with self.subTest(scenario=name):
                reply = {key: True for key in expected}
                reply["lunge_heal"] = False
                self.assertTrue(any("lunge_heal" in issue for issue in check(reply, expected)))

    def test_actual_runner_rejects_missing_healing_observation(self):
        for name, expected in self.lunge_steps():
            with self.subTest(scenario=name):
                reply = {key: True for key in expected if key != "lunge_heal"}
                self.assertTrue(any("lunge_heal" in issue for issue in check(reply, expected)))

    def test_actual_runner_accepts_complete_healing_positive_control(self):
        for name, expected in self.lunge_steps():
            with self.subTest(scenario=name):
                reply = {key: True for key in expected}
                reply["lunge_heal"] = True
                self.assertEqual(check(reply, expected), [])


if __name__ == "__main__":
    unittest.main()
