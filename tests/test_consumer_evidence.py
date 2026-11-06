"""Vacuity, binding and incomplete-result controls for retained native evidence."""
import copy
import unittest

from gamelab.consumer_evidence import validate_consumers


class ConsumerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.scenario = {"steps": [{"do": "sleep", "seconds": 1},
                                   {"do": "bot", "bot": "stash", "kwargs": {"tab": 0}}]}
        self.admission = {"consumers": [{"step": 1, "bot": "stash", "rows": ["fixture", "preservation"]}]}
        self.record = {"bot": "stash", "kwargs": {"tab": 0}, "pass": 1, "assertion_index": 8,
                       "result": {"ok": True, "rows": [{"case": "fixture", "runtime": "PASS"},
                                                       {"case": "preservation", "runtime": "PASS"}]}}

    def check(self, record=None, admission=None, scenario=None):
        return validate_consumers(admission or self.admission, scenario or self.scenario,
                                  [self.record if record is None else record])

    def test_full_return_reconciles_declared_rows(self):
        result = self.check()
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["checks"]), 2)

    def test_true_aggregate_cannot_hide_missing_duplicate_failed_or_extra_rows(self):
        variants = [[], [{"case": "fixture", "runtime": "PASS"}] * 2,
                    [{"case": "fixture", "runtime": "PASS"}, {"case": "preservation", "runtime": "FAIL"}],
                    self.record["result"]["rows"] + [{"case": "unexpected", "runtime": "PASS"}]]
        for rows in variants:
            with self.subTest(rows=rows):
                record = copy.deepcopy(self.record)
                record["result"]["rows"] = rows
                self.assertFalse(self.check(record)["valid"])

    def test_foreign_bot_kwargs_and_untyped_or_reused_identity_refuse(self):
        for key, value in [("bot", "foreign"), ("kwargs", {"tab": False}),
                           ("pass", True), ("assertion_index", True)]:
            with self.subTest(key=key):
                self.assertFalse(self.check({**self.record, key: value})["valid"])

    def test_missing_or_extra_invocation_refuses_even_with_good_first_result(self):
        for rows in [[], [self.record, self.record]]:
            with self.subTest(count=len(rows)):
                self.assertFalse(validate_consumers(self.admission, self.scenario, rows)["valid"])

    def test_same_bot_invocations_are_bound_by_order_and_kwargs(self):
        scenario = {"steps": [{"do": "bot", "bot": "stash", "kwargs": {"tab": 0}},
                              {"do": "bot", "bot": "stash", "kwargs": {"tab": 1}}]}
        admission = {"consumers": [{"step": 0, "bot": "stash", "rows": ["fixture", "preservation"]},
                                    {"step": 1, "bot": "stash", "rows": ["fixture", "preservation"]}]}
        two = {**self.record, "kwargs": {"tab": 1}, "assertion_index": 9}
        self.assertTrue(validate_consumers(admission, scenario, [self.record, two])["valid"])
        self.assertFalse(validate_consumers(admission, scenario, [two, self.record])["valid"])
        self.assertFalse(validate_consumers(admission, scenario, [self.record, {**two, "assertion_index": 8}])["valid"])

    def test_no_bot_case_requires_no_fabricated_returns(self):
        self.assertTrue(validate_consumers({}, {"steps": [{"do": "gl", "verb": "ping"}]}, [])["valid"])
        self.assertFalse(validate_consumers({}, {"steps": []}, [self.record])["valid"])

    def test_invalid_declarations_or_claimed_success_values_refuse(self):
        for declaration in [{"step": True, "bot": "stash", "rows": ["fixture"]},
                            {"step": 1, "bot": "stash", "rows": ["fixture", "fixture"]},
                            {"step": 0, "bot": "stash", "rows": ["fixture"]}]:
            self.assertFalse(self.check(admission={"consumers": [declaration]})["valid"])
        record = copy.deepcopy(self.record)
        record["result"]["ok"] = 1
        self.assertFalse(self.check(record)["valid"])


if __name__ == "__main__":
    unittest.main()
