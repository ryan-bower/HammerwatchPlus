"""UNRUN diagnostic data/control designs. No project/AS/native/file imports or IO.

These controls test bounded cache/trace interpretation, not native getter
semantics, the AS implementation, ownership arbitration, physics or a fix.
"""
import json
import math
import unittest

U = "unobserved"
MAX_RECORDS, MAX_CHARS, MAX_UTF8 = 16, 3000, 12000
BUTTONS = tuple(f"{name}.{edge}" for name in
                ("use", "potion", "dash", "main", "off", "skill1", "skill2", "skill3")
                for edge in ("down", "pressed"))
PREDICATES = {
    "record_null", "actor_null", "record_handle", "actor_handle", "record_local", "record_actor",
    "unit_invalid", "unit_id", "scene_handle", "boots", "level", "player_bound", "other_player",
    "held_positive", "sequence_busy", "reflex_fire", "reflex_potion", "skillkeys", "releasing",
    "write_counter", "write_bound", "current_null", "callback_null", "callback_handle", "inputs_empty",
    "inputs_bound", "inputs_count", "input_null", "saved_input_handle", "gamepad", "move_x", "move_y",
    "current_untracked", *BUTTONS,
}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def observe_first(getters):
    """Only ordered evaluated operands are cached; serialization never re-reads."""
    cache = {name: U for name, _ in getters}
    first = ""
    for name, getter in getters:
        cache[name] = getter()
        if cache[name] is True:
            first = name
            break
    return first, cache


def input_row(mx=0.0, my=0.0):
    return dict(null=False, handle_same=True, pad=False, saved_pad=False, mx=mx, my=my,
                down_seen=255, down_true=0, pressed_seen=255, pressed_true=0)


def record(seq, callback, entry, phase, location, code="", writes=92, expected=92):
    value = dict(intent_id="c48", ev="tight_input_probe", seq=seq, callback=callback, entry=entry,
                 frame=546 + callback, now=18018 + 33 * callback, boots=1, expected_boots=1,
                 player=30314, expected_player=30314, phase=phase, location=location,
                 first_failed=code, valid=True, owner_binding_ok=True, writer_guard_ok=True,
                 callback_same=True, writes_at_start=writes, expected_writes=expected,
                 guard_writes=writes, guard_expected_writes=expected, held_ms=-12,
                 expected_x=0.0 if expected == 92 else -1.0, expected_y=0.0,
                 planned_x=-1.0, planned_y=0.0, guard_actual=U, guard_expected=U,
                 failed_slot=-1, current=input_row(), callback_input=input_row(),
                 current_slot=0, callback_slot=0, slot0=input_row(), failed_input=U,
                 window_entries=3, record_cap=16, char_cap=3000)
    value.update(binding_source="preceding guard cache; NEW input readback" if phase == "post_write" else
                 "original guard operands; marker inputs unobserved", later_predicates="unobserved after first failure")
    if phase == "guard_fail" and code == "move_x":
        value.update(guard_actual=-.999999940, guard_expected=-1.0, failed_slot=0,
                     failed_input=input_row(-.999999940, U), slot0=input_row(-.999999940, U),
                     current=input_row(-.999999940, U), callback_input=input_row(-.999999940, U))
    return value


def assess(rows, terminal):
    result = dict(valid=False, location=U, first=U, interpretation="incomplete", foreign_writer_proven=False,
                  physics_phase_proven=False, controller_fixed=False)
    required = ("intent_id", "ev", "seq", "callback", "entry", "frame", "now", "boots", "expected_boots",
                "player", "expected_player", "phase", "location", "first_failed", "valid",
                "current", "callback_input", "slot0", "failed_input", "guard_actual", "guard_expected",
                "owner_binding_ok", "writer_guard_ok", "callback_same", "writes_at_start", "expected_writes",
                "guard_writes", "guard_expected_writes", "held_ms", "expected_x", "expected_y", "planned_x",
                "planned_y", "binding_source", "later_predicates", "window_entries", "record_cap", "char_cap",
                "current_slot", "callback_slot", "failed_slot")
    if (type(rows) is not list or not 0 < len(rows) <= MAX_RECORDS or type(terminal) is not dict
            or type(terminal.get("diag_records")) is not int or terminal["diag_records"] != len(rows)
            or type(terminal.get("diag_dropped")) is not int or terminal["diag_dropped"] != 0
            or terminal.get("diag_truncated") is not False or terminal.get("diag_invalid") is not False):
        return result
    previous_callback, previous_now, previous_entry = -1, -1, -1
    failures, posts = [], []
    for index, row in enumerate(rows, 1):
        if (type(row) is not dict or any(name not in row for name in required)
                or "id" in row or row["intent_id"] != "c48" or row["ev"] != "tight_input_probe" or row["valid"] is not True
                or type(row["seq"]) is not int or row["seq"] != index
                or any(type(row[key]) is not int or row[key] < 0 for key in ("callback", "entry", "frame", "now"))
                or any(type(row[key]) is not int or row[key] < 0 for key in
                       ("boots", "expected_boots", "expected_player", "writes_at_start", "expected_writes"))
                or row["callback"] < previous_callback or row["now"] < previous_now
                or row["entry"] < previous_entry
                or (row["entry"] > previous_entry >= 0 and row["callback"] <= previous_callback)
                or row["boots"] != 1 or row["expected_boots"] != 1 or row["expected_player"] != 30314
                or row["phase"] not in ("before_guard", "guard_pass", "guard_fail", "post_write")
                or row["location"] not in ("admit", "admit_after_route", "frame_entry", "pre_write",
                                           "final_release", "end_owner", "paused", "tight_write")
                or row["window_entries"] != 3 or row["record_cap"] != 16 or row["char_cap"] != 3000
                or any(not finite(row[key]) for key in ("expected_x", "expected_y"))
                or any(row[key] != U and not finite(row[key]) for key in ("planned_x", "planned_y"))
                or any(type(row[key]) is not int or not -1 <= row[key] < 8
                       for key in ("current_slot", "callback_slot", "failed_slot"))
                or type(row["first_failed"]) is not str):
            return result
        for key in ("current", "callback_input", "slot0", "failed_input"):
            data = row[key]
            if data == U:
                continue
            if type(data) is not dict:
                return result
            for mask in ("down_seen", "down_true", "pressed_seen", "pressed_true"):
                if type(data.get(mask)) is not int or not 0 <= data[mask] <= 255:
                    return result
            if data["down_true"] & ~data["down_seen"] or data["pressed_true"] & ~data["pressed_seen"]:
                return result
            if any(value != U and type(value) is not bool for value in
                   (data.get("null"), data.get("handle_same"), data.get("pad"), data.get("saved_pad"))):
                return result
            if any(data.get(key) != U and not finite(data.get(key)) for key in ("mx", "my")):
                return result
        if row.get("current_slot") == 0 and row["current"] != row["slot0"]:
            return result
        if row.get("callback_slot") == 0 and row["callback_input"] != row["slot0"]:
            return result
        if row.get("failed_slot") == 0 and row["failed_input"] != row["slot0"]:
            return result
        raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        if len(raw) > MAX_CHARS or len(raw.encode("utf-8")) > MAX_UTF8:
            return result
        previous_callback, previous_now, previous_entry = row["callback"], row["now"], row["entry"]
        if row["phase"] in ("guard_pass", "post_write") and row["player"] != 30314:
            return result
        if row["phase"] in ("guard_pass", "post_write") and row["first_failed"] != "":
            return result
        if row["phase"] == "post_write":
            posts.append(row)
        if row["phase"] == "guard_fail":
            if row["first_failed"] not in PREDICATES:
                return result
            if row["first_failed"] == "move_x":
                failed = row["failed_input"]
                if (type(failed) is not dict or failed.get("my") != U
                        or row["owner_binding_ok"] is not True or row["writer_guard_ok"] is not True
                        or row["callback_same"] is not True or row["player"] != 30314
                        or failed.get("null") is not False or failed.get("handle_same") is not True
                        or failed.get("pad") != failed.get("saved_pad")
                        or any(failed.get(key) != 255 for key in ("down_seen", "pressed_seen"))
                        or any(failed.get(key) != 0 for key in ("down_true", "pressed_true"))
                        or not finite(row["guard_actual"]) or not finite(row["guard_expected"])):
                    return result
            failures.append(row)
    if len(failures) != 1:
        return result
    failure = failures[0]
    result.update(valid=True, location=failure["location"], first=failure["first_failed"],
                  interpretation="predicate-only; write origin unproved")
    if failure["location"] == "pre_write" and failure["entry"] == 1 and not posts:
        result["interpretation"] = "first observed pre-write call refused before its write"
    elif failure["location"] == "frame_entry" and any(
            post["callback"] < failure["callback"] and post["entry"] < failure["entry"] for post in posts):
        result["interpretation"] = "later entry refusal after an observed own write/readback"
    return result


def terminal(count, **changes):
    value = dict(diag_records=count, diag_dropped=0, diag_truncated=False, diag_invalid=False,
                 intent_frames=1, observations=1)
    value.update(changes)
    return value


class TightInputDiagnosticTests(unittest.TestCase):
    def test_admit_diagnostics_cannot_steal_the_normal_accept_reply(self):
        diagnostic = record(1, 100, 0, "guard_pass", "admit")
        accepted = dict(id="c48", ok=True, accepted="path_to", tight=True)
        reply = next(row for row in (diagnostic, accepted) if row.get("id") == "c48")
        self.assertIs(reply, accepted)
        diagnostic["id"] = "c48"
        self.assertFalse(assess([diagnostic], terminal(1))["valid"])

    def test_identical_old_counters_disambiguate_same_callback_and_next_entry(self):
        pre = [record(1, 100, 1, "guard_pass", "frame_entry"),
               record(2, 100, 1, "guard_fail", "pre_write", "move_x")]
        later = [record(1, 100, 1, "guard_pass", "pre_write"),
                 record(2, 100, 1, "post_write", "tight_write", writes=93, expected=93),
                 record(3, 101, 2, "guard_fail", "frame_entry", "move_x", writes=93, expected=93)]
        a, b = assess(pre, terminal(2)), assess(later, terminal(3))
        self.assertTrue(a["valid"] and b["valid"])
        self.assertNotEqual(a["interpretation"], b["interpretation"])
        self.assertFalse(a["foreign_writer_proven"] or b["physics_phase_proven"])

    def test_first_failing_predicate_preserves_order_and_later_unobserved(self):
        calls = []
        def getter(name, value):
            def read():
                calls.append(name)
                return value
            return read
        first, cache = observe_first([(name, getter(name, name == "dash.pressed")) for name in BUTTONS])
        self.assertEqual(first, "dash.pressed")
        self.assertEqual(calls, list(BUTTONS[:6]))
        self.assertTrue(all(cache[name] == U for name in BUTTONS[6:]))

    def test_unknown_getter_is_not_retried_or_defaulted_by_failure_serialization(self):
        calls, cache = [], {"move_x": U, "move_y": U}
        def unavailable():
            calls.append(1)
            raise RuntimeError("synthetic unavailable native read")
        try:
            cache["move_x"] = unavailable()
        except RuntimeError:
            encoded = json.dumps(dict(valid=False, cached=cache))
        self.assertIn(U, encoded)
        self.assertEqual(len(calls), 1)
        # Both existing exception paths retain their original ownership/release
        # disposition and only latch diagnostic invalidity. No local guard cache
        # survives a throwing getter, so do not fabricate a rejection record.
        for location in ("paused", "end_owner"):
            before = dict(tightForeign=location == "paused", release=False, diag_invalid=False)
            after = dict(before)
            after["diag_invalid"] = True
            self.assertEqual(after["tightForeign"], before["tightForeign"])
            self.assertIs(after["release"], False)
            self.assertFalse(assess([record(1, 100, 1, "guard_fail", "pre_write", "move_x")],
                                    terminal(1, diag_invalid=after["diag_invalid"]))["valid"])
        self.assertEqual(len(calls), 1)  # neither exception path re-reads the getter
        self.assertFalse(assess([record(1, 100, 1, "guard_fail", "pre_write", "move_x")],
                                terminal(1, diag_invalid=True))["valid"])

    def test_nine_decimal_mismatch_is_evidence_not_an_ownership_tolerance(self):
        row = record(1, 100, 1, "guard_fail", "pre_write", "move_x")
        result = assess([row], terminal(1))
        self.assertTrue(result["valid"])
        self.assertNotEqual(row["guard_actual"], row["guard_expected"])
        self.assertFalse(result["controller_fixed"] or result["foreign_writer_proven"])

    def test_later_unobserved_fields_cannot_be_fabricated_as_neutral(self):
        row = record(1, 100, 1, "guard_fail", "pre_write", "move_x")
        row["failed_input"]["my"] = 0
        self.assertFalse(assess([row], terminal(1))["valid"])

    def test_missing_foreign_duplicate_regressing_or_unknown_records_fail_closed(self):
        for change in (dict(intent_id="other"), dict(seq=2), dict(valid=False), dict(expected_player=123),
                       dict(first_failed="invented"), dict(guard_actual=math.nan), dict(owner_binding_ok=U),
                       dict(writer_guard_ok=False), dict(callback_same=False), dict(player=U)):
            row = record(1, 100, 1, "guard_fail", "pre_write", "move_x")
            row.update(change)
            self.assertFalse(assess([row], terminal(1))["valid"])
        rows = [record(1, 100, 1, "post_write", "tight_write"),
                record(2, 99, 2, "guard_fail", "frame_entry", "move_x")]
        self.assertFalse(assess(rows, terminal(2))["valid"])

    def test_truncated_dropped_over_budget_or_incomplete_counts_are_not_proof(self):
        row = record(1, 100, 1, "guard_fail", "pre_write", "move_x")
        for changes in (dict(diag_records=2), dict(diag_dropped=1), dict(diag_truncated=True), dict(diag_invalid=True)):
            self.assertFalse(assess([row], terminal(1, **changes))["valid"])
        row["padding"] = "x" * 3001
        self.assertFalse(assess([row], terminal(1))["valid"])
        self.assertFalse(assess([record(i, 100, 1, "guard_fail", "pre_write", "move_x")
                                 for i in range(1, 18)], terminal(17))["valid"])

    def test_postwrite_readback_does_not_rescue_or_mutate_expected_owned_command(self):
        post = record(1, 100, 1, "post_write", "tight_write", writes=93, expected=93)
        for key in ("current", "callback_input", "slot0"):
            post[key]["mx"] = -.999999940
        fail = record(2, 101, 2, "guard_fail", "frame_entry", "move_x", writes=93, expected=93)
        result = assess([post, fail], terminal(2))
        self.assertTrue(result["valid"])
        self.assertEqual(post["expected_x"], -1)
        self.assertFalse(result["controller_fixed"] or result["physics_phase_proven"])

    def test_individual_emit_and_separate_final_probe_transport_budgets(self):
        self.assertLess(MAX_UTF8, 15000)
        self.assertEqual(MAX_RECORDS * MAX_CHARS, 48000)
        self.assertEqual(5 * 12000, 60000)  # unchanged five separate final-probe rows
        self.assertEqual(MAX_RECORDS + 5, 21)  # not concatenated into one reply/terminal


if __name__ == "__main__":
    unittest.main()
