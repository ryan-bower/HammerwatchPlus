"""Draft target: planner/test_server.py. Pure standard-library temporary fixtures.

Run after review/integration: python -m unittest planner.test_server -q
The fixture imports definitions only, never calls planner.main or opens a browser.
"""
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from planner import __main__ as planner


class PlannerPersistenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="planner-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        data, web = root / "data", root / "web"
        data.mkdir()
        web.mkdir()
        for collection in planner.COLLECTIONS:
            (data / collection).mkdir()
        self.record = data / "skills" / "fixture.json"
        self.other = data / "skills" / "untouched.json"
        self.original = b'{"name":"original","unknown":{"preserve":true}}\n'
        self.record.write_bytes(self.original)
        self.other.write_bytes(b'{"name":"untouched"}\n')
        self.data = data
        patcher = mock.patch.multiple(planner, DATA=data, WEB=web)
        patcher.start()
        self.addCleanup(patcher.stop)

        class Handler(planner.Handler):
            timeout = 1

            def log_message(self, *args):
                pass

        self.server = planner.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = False
        self.server.block_on_close = True
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(lambda: self.thread.join(timeout=5))
        self.addCleanup(self.server.shutdown)

    def request(self, method, body=None, path=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=2)
        path = path if path is not None else ("/api/data" if method == "GET" else "/api/skills/fixture")
        try:
            connection.request(method, path, body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            raw = response.read()

            def reject_constant(value):
                raise ValueError("nonfinite JSON: " + value)

            return response.status, json.loads(raw, parse_constant=reject_constant)
        except http.client.HTTPException as error:
            return None, {"transport_error": type(error).__name__}
        finally:
            connection.close()

    def snapshot(self):
        return {str(p.relative_to(self.data)): p.read_bytes()
                for p in self.data.rglob("*") if p.is_file()}

    def assert_failed_save_preserved(self, reply, before):
        self.assertEqual(reply, (500, {"error": "write_failed"}))
        self.assertEqual(self.snapshot(), before)
        status, body = self.request("GET")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["skills"]["fixture"], json.loads(self.original))

    def test_successful_save_round_trips_utf8_and_metadata(self):
        before_other = self.other.read_bytes()
        record = {"name": "café 🛠", "unknown": {"preserve": [0, False, None]}, "_id": "remove"}
        status, _ = self.request("PUT", json.dumps(record, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(status, 200)
        expected = {key: value for key, value in record.items() if key != "_id"}
        self.assertEqual(json.loads(self.record.read_text(encoding="utf-8")), expected)
        self.assertEqual(self.request("GET")[1]["data"]["skills"]["fixture"], expected)
        self.assertEqual(self.other.read_bytes(), before_other)
        self.assertEqual(sorted(p.name for p in self.record.parent.iterdir()), ["fixture.json", "untouched.json"])

    def assert_bad_unicode_preserved(self, raw):
        before = self.snapshot()
        status, stamp_before = self.request("GET", path="/api/stamp")
        self.assertEqual(status, 200)
        reply = self.request("PUT", raw)  # exactly one fixed PUT; disconnect is not a structured refusal
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.request("GET", path="/api/stamp"), (200, stamp_before))
        status, body = self.request("GET")
        self.assertEqual(status, 200)  # the same server must still handle strict JSON after refusal
        self.assertEqual(body["stamp"], stamp_before["stamp"])
        self.assertEqual(body["data"]["skills"]["fixture"], json.loads(self.original))
        self.assertEqual(list(self.data.rglob(".planner-*.tmp")), [])
        self.assertEqual(reply, (400, {"error": "bad_json"}))  # checked last so baseline postconditions are reached

    def assert_unicode_round_trip(self, raw, expected):
        before = self.snapshot()
        status, stamp_before = self.request("GET", path="/api/stamp")
        self.assertEqual(status, 200)
        status, saved = self.request("PUT", raw)  # exactly one fixed PUT, with the normal200 response shape
        self.assertEqual(status, 200)
        self.assertEqual(set(saved), {"stamp"})
        self.assertNotEqual(saved["stamp"], stamp_before["stamp"])
        self.assertEqual(self.request("GET", path="/api/stamp"), (200, saved))
        status, body = self.request("GET")
        self.assertEqual(status, 200)
        self.assertEqual(body["stamp"], saved["stamp"])
        self.assertEqual(body["data"]["skills"]["fixture"], expected)
        stored = self.record.read_bytes()
        self.assertEqual(json.loads(stored.decode("utf-8")), expected)
        self.assertIn(expected["name"].encode("utf-8"), stored)
        after = self.snapshot()
        self.assertEqual(set(after), set(before))
        record_key = str(self.record.relative_to(self.data))
        for name in before:
            if name != record_key:
                self.assertEqual(after[name], before[name], name)
        self.assertEqual(list(self.data.rglob(".planner-*.tmp")), [])

    def test_unpaired_high_surrogate_refuses_without_changing_data(self):
        self.assert_bad_unicode_preserved(br'{"name":"\ud800"}')

    def test_unpaired_low_surrogate_refuses_without_changing_data(self):
        self.assert_bad_unicode_preserved(br'{"name":"\udc00"}')

    def test_valid_utf8_accent_and_emoji_preserve_unknown_fields(self):
        record = {"name": "caf\u00e9 \U0001f6e0", "unknown": {"preserve": True}}
        self.assert_unicode_round_trip(json.dumps(record, ensure_ascii=False).encode("utf-8"), record)

    def test_valid_escaped_surrogate_pair_preserves_emoji_and_unknown_fields(self):
        self.assert_unicode_round_trip(br'{"name":"\ud83d\udee0","unknown":{"preserve":true}}',
            {"name": "\U0001f6e0", "unknown": {"preserve": True}})

    def test_nonfinite_values_refuse_without_changing_existing_data(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e999", '[0,{"nested":NaN}]'):
            with self.subTest(value=value):
                before = self.snapshot()
                try:
                    reply = self.request("PUT", ('{"value":' + value + '}').encode("ascii"))
                    self.assertEqual(reply, (400, {"error": "bad_json"}))
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(self.request("GET")[0], 200)
                finally:
                    self.record.write_bytes(self.original)

    def test_failed_write_or_close_preserves_existing_document(self):
        real_open = io.open
        record, parent = self.record.resolve(), self.record.parent.resolve()
        for stage in ("write", "close"):
            with self.subTest(stage=stage):
                self.record.write_bytes(self.original)
                before = self.snapshot()
                fault = {"triggered": False}

                class Writer:
                    def __init__(self, stream):
                        self.stream = stream

                    def __getattr__(self, name):
                        return getattr(self.stream, name)

                    def __enter__(self):
                        return self

                    def __exit__(self, *exc):
                        self.close()
                        return False

                    def write(self, value):
                        if stage == "write" and not fault["triggered"]:
                            fault["triggered"] = True
                            self.stream.write(value[:13])
                            self.stream.flush()
                            raise OSError("injected temporary-fixture write failure")
                        return self.stream.write(value)

                    def close(self):
                        self.stream.close()
                        if stage == "close" and not fault["triggered"]:
                            fault["triggered"] = True
                            raise OSError("injected temporary-fixture close failure")

                def fault_open(file, mode="r", *args, **kwargs):
                    stream = real_open(file, mode, *args, **kwargs)
                    if isinstance(file, (str, os.PathLike)) and "w" in mode:
                        path = Path(file).resolve()
                        if path == record or path == parent:
                            return Writer(stream)
                    return stream

                try:
                    with mock.patch.object(io, "open", side_effect=fault_open):
                        reply = self.request("PUT", b'{"name":"replacement document"}')
                    self.assertTrue(fault["triggered"])
                    self.assert_failed_save_preserved(reply, before)
                finally:
                    self.record.write_bytes(self.original)

    def test_failed_replace_preserves_existing_document(self):
        before = self.snapshot()

        def fail_replace(source, destination):
            self.assertEqual(Path(source).resolve().parent, self.record.parent.resolve())
            self.assertEqual(Path(destination).resolve(), self.record.resolve())
            raise OSError("injected temporary-fixture replace failure")

        with mock.patch.object(os, "replace", side_effect=fail_replace):
            reply = self.request("PUT", b'{"name":"replacement document"}')
        self.assert_failed_save_preserved(reply, before)


if __name__ == "__main__":
    unittest.main()
