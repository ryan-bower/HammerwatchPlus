"""Pure observer retention/clock/identity controls; never native-effect proof."""
import ast
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("qa_observe_under_test", ROOT / "gamelab/bots/qa_observe.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def wrapper(game, event="buffobserve", expected=None):
    # Execute only the actual collector method AST. No import of the bot's
    # gameplay hierarchy, native bindings, constructors or runtime objects.
    tree = ast.parse((ROOT / "gamelab/bots/qa_firearms_missing_orbs.py").read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Checks")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "collect_trace")
    namespace = {"collect_observer_trace": getattr(observer, "collect_trace", None)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "actual_collect_trace", "exec"), namespace)
    kwargs = {} if expected is None else {"expected": expected}
    return namespace["collect_trace"](SimpleNamespace(g=game), event, "trial", 0, **kwargs)


class FakeGame:
    def __init__(self, chunks):
        self.gl = chunks

    def wait_gl(self, predicate, timeout=0):
        return next((row for row in self.gl if predicate(row)), None)


def semantic(count=2):
    # Semantic transitions do not store every native frame.
    elapsed = [0, 600] if count == 2 else [0, *range(20, 20 * (count - 1), 20), 600]
    rows = [{"now": 1000 + ms, "elapsed": ms,
             "reason": "initial" if index == 0 else "final hp" if index == len(elapsed)-1 else " hp",
             "target_unit": 42, "player_valid": True, "target_valid": True, "buff_on": False}
            for index, ms in enumerate(elapsed)]
    headers = dict(ev="buffobserve", tag="trial", parts=(len(rows)+15)//16,
                   stored=len(rows), seen=len(rows), dropped=0, truncated=False,
                   start=1000, end=1600, ms=600, frames=30, buff="buff/path", stack="-", target_unit=42)
    return [{**headers, "part": offset//16, "events": rows[offset:offset+16]}
            for offset in range(0, len(rows), 16)]


def actor():
    rows = [{"now": 1000 + index*20, "elapsed": index*20, "dt": 0 if index == 0 else 20,
             "final": index == 5, "valid": True, "unit": 42} for index in range(6)]
    return [dict(ev="actorbuffobserve", tag="trial", part=0, parts=1,
                 stored=6, seen=6, dropped=0, truncated=False,
                 start=1000, end=1100, ms=100, frames=5, unit=42, buff="buff/path", samples=rows)]


def set_headers(chunks, key, value):
    for chunk in chunks:
        chunk[key] = value


class ObserverContractTests(unittest.TestCase):
    def semantic_result(self, chunks):
        return observer.collect(FakeGame(chunks), "trial", timeout=0)

    def test_valid_semantic_transitions_and_chunk_boundary_are_preserved(self):
        for count in (2, 17):
            with self.subTest(count=count):
                chunks = semantic(count)
                result = self.semantic_result(chunks)
                self.assertTrue(result["usable"], result)
                self.assertEqual(len(result["events"]), count)
                self.assertEqual(result["events"][0]["elapsed"], 0)
                self.assertEqual(result["events"][-1]["elapsed"], 600)
                traced = wrapper(FakeGame(chunks))
                self.assertTrue(traced["valid"], traced)
                self.assertEqual(traced["samples"], result["events"])

    def test_semantic_header_fields_are_required_and_strict(self):
        changes = (("start", None), ("end", None), ("ms", None), ("frames", None),
                   ("frames", True), ("parts", True), ("part", False), ("dropped", False),
                   ("truncated", 0), ("buff", None), ("stack", None), ("target_unit", True))
        for key, value in changes:
            with self.subTest(key=key, value=value):
                chunks = semantic()
                if value is None:
                    for chunk in chunks:
                        chunk.pop(key)
                else:
                    set_headers(chunks, key, value)
                self.assertFalse(self.semantic_result(chunks)["usable"])
                self.assertFalse(wrapper(FakeGame(chunks))["valid"])

    def test_semantic_endpoints_bind_to_the_retained_header(self):
        for change in ("initial_now", "final_now", "initial_elapsed", "final_elapsed", "foreign_target"):
            with self.subTest(change=change):
                chunks = semantic()
                first, last = chunks[0]["events"]
                if change == "initial_now": first["now"] = 0
                elif change == "final_now": last["now"] = 1550
                elif change == "initial_elapsed": first["elapsed"] = 1
                elif change == "final_elapsed": last["elapsed"] = 599
                else: last["target_unit"] = 99
                self.assertFalse(self.semantic_result(chunks)["usable"])
                self.assertFalse(wrapper(FakeGame(chunks))["valid"])

    def test_malformed_rows_return_invalid_without_crashing(self):
        for bad in (None, True, 7, "not-a-row", [], {"reason": []}):
            with self.subTest(bad=bad):
                chunks = semantic()
                chunks[0]["events"][1] = bad
                self.assertFalse(self.semantic_result(chunks)["usable"])
                self.assertFalse(wrapper(FakeGame(chunks))["valid"])

    def test_nonobject_telemetry_is_ignored_and_missing_results_fail(self):
        self.assertFalse(self.semantic_result([])["usable"])
        self.assertFalse(wrapper(FakeGame([]))["valid"])
        chunks = [None, [], True, *semantic()]
        self.assertTrue(self.semantic_result(chunks)["usable"])
        self.assertTrue(wrapper(FakeGame(chunks))["valid"])

    def test_duplicate_foreign_missing_and_empty_parts_cannot_pass(self):
        cases = []
        chunks = semantic(); cases.append(chunks + copy.deepcopy(chunks))
        chunks = semantic(17); chunks[-1]["tag"] = "other"; cases.append(chunks)
        chunks = semantic(17); chunks[-1]["ev"] = "other"; cases.append(chunks)
        cases.append(semantic(17)[:-1])
        chunks = semantic(); set_headers(chunks, "parts", 2)
        chunks.append({**chunks[0], "part": 1, "events": []}); cases.append(chunks)
        for index, chunks in enumerate(cases):
            with self.subTest(index=index):
                self.assertFalse(self.semantic_result(chunks)["usable"])
                self.assertFalse(wrapper(FakeGame(chunks))["valid"])

    def test_all_headers_counts_reasons_and_monotonic_clocks_agree(self):
        cases = []
        chunks = semantic(17); chunks[-1]["buff"] = "foreign"; cases.append(chunks)
        chunks = semantic(); set_headers(chunks, "seen", 1); cases.append(chunks)
        chunks = semantic(); set_headers(chunks, "frames", 0); cases.append(chunks)
        chunks = semantic(); chunks[0]["events"][-1]["reason"] = " hp"; cases.append(chunks)
        chunks = semantic(17); chunks[0]["events"][2]["elapsed"] = 0; cases.append(chunks)
        chunks = semantic(17); chunks[0]["events"][2]["now"] = 1000; cases.append(chunks)
        for index, chunks in enumerate(cases):
            with self.subTest(index=index):
                self.assertFalse(self.semantic_result(chunks)["usable"])
                self.assertFalse(wrapper(FakeGame(chunks))["valid"])

    def test_explicit_truncation_supplies_no_usable_trace(self):
        chunks = semantic(); set_headers(chunks, "seen", 3)
        set_headers(chunks, "dropped", 1); set_headers(chunks, "truncated", True)
        self.assertFalse(self.semantic_result(chunks)["usable"])
        self.assertFalse(wrapper(FakeGame(chunks))["valid"])

    def test_optional_request_identity_is_independently_matched(self):
        expected = dict(buff="buff/path", stack="-", target_unit=42)
        result = observer.collect(FakeGame(semantic()), "trial", timeout=0, expected=expected)
        self.assertTrue(result["usable"], result)
        for change in ({"target_unit": 99}, {"buff": "foreign"}, {"target_unit": True}, {"unknown": 1}):
            with self.subTest(change=change):
                self.assertFalse(observer.collect(FakeGame(semantic()), "trial", timeout=0,
                                                 expected={**expected, **change})["usable"])

    def test_local_request_collect_pairs_bind_known_identities(self):
        tree = ast.parse((ROOT / "gamelab/bots/qa_firearms_missing_orbs.py").read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Checks")
        namespace = dict(self=SimpleNamespace(STACKS="stacks/"), target=42, dummy=43, buff="rider/buff")
        for name, event in (("rocket_bank_ready", "buffobserve"), ("rocket_trial", "buffobserve"),
                            ("rider_trial", "actorbuffobserve")):
            with self.subTest(name=name):
                method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
                requests = [node.elts for node in ast.walk(method) if isinstance(node, (ast.List, ast.Tuple))
                            and node.elts and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == event]
                requests += [node.args for node in ast.walk(method) if isinstance(node, ast.Call)
                             and isinstance(node.func, ast.Attribute) and node.func.attr == "gl" and node.args
                             and isinstance(node.args[0], ast.Constant) and node.args[0].value == event]
                self.assertEqual(len(requests), 1)
                collected = next(node for node in ast.walk(method) if isinstance(node, ast.Call)
                                 and isinstance(node.func, ast.Attribute) and node.func.attr == "collect_trace")
                keyword = next((item for item in collected.keywords if item.arg == "expected"), None)
                self.assertIsNotNone(keyword, "actual local collector omits request identity")
                value = lambda expression: eval(compile(ast.Expression(body=expression), "identity_expression", "eval"), {}, namespace)
                expected = value(keyword.value)
                request = requests[0]
                actual = ({"buff": value(request[4]), "unit": value(request[3])} if event == "actorbuffobserve" else
                          {"buff": value(request[3]), "stack": value(request[4]), "target_unit": value(request[5])})
                self.assertEqual(expected, actual)
                chunks = actor() if event == "actorbuffobserve" else semantic()
                unit = "unit" if event == "actorbuffobserve" else "target_unit"
                field = "samples" if event == "actorbuffobserve" else "events"
                for key, item in actual.items():
                    set_headers(chunks, key, item)
                for chunk in chunks:
                    for row in chunk[field]:
                        row[unit] = actual[unit]
                self.assertTrue(wrapper(FakeGame(chunks), event, expected=expected)["valid"])
                # A self-consistent foreign trace still fails the actual request.
                for chunk in chunks:
                    chunk[unit] += 100
                    for row in chunk[field]:
                        row[unit] += 100
                self.assertFalse(wrapper(FakeGame(chunks), event, expected=expected)["valid"])

    def test_valid_actor_trace_retains_every_native_frame(self):
        result = wrapper(FakeGame(actor()), "actorbuffobserve")
        self.assertTrue(result["valid"], result)
        self.assertEqual(len(result["samples"]), 6)
        self.assertEqual(result["samples"][0]["dt"], 0)
        self.assertTrue(result["samples"][-1]["final"])

    def test_actor_strict_header_and_sample_types_identity_and_retention(self):
        cases = []
        for key, value in (("part", False), ("parts", True), ("dropped", False), ("truncated", 0)):
            chunks = actor(); set_headers(chunks, key, value); cases.append(chunks)
        chunks = actor(); chunks[0]["samples"][1]["dt"] = True; cases.append(chunks)
        chunks = actor(); chunks[0]["samples"][1]["unit"] = 99; cases.append(chunks)
        chunks = actor(); chunks[0]["samples"][1] = None; cases.append(chunks)
        chunks = actor(); chunks[0]["samples"].pop(2); set_headers(chunks, "stored", 5); cases.append(chunks)
        chunks = actor(); chunks[0]["samples"][-1]["final"] = 1; cases.append(chunks)
        chunks = actor(); chunks[0]["samples"][1]["now"] = 9000; cases.append(chunks)
        for index, chunks in enumerate(cases):
            with self.subTest(index=index):
                self.assertFalse(wrapper(FakeGame(chunks), "actorbuffobserve")["valid"])

    def test_actor_truncation_and_missing_parts_never_pass(self):
        chunks = actor(); set_headers(chunks, "seen", 7); set_headers(chunks, "frames", 6)
        set_headers(chunks, "dropped", 1); set_headers(chunks, "truncated", True)
        self.assertFalse(wrapper(FakeGame(chunks), "actorbuffobserve")["valid"])
        self.assertFalse(wrapper(FakeGame([]), "actorbuffobserve")["valid"])


if __name__ == "__main__":
    unittest.main()
