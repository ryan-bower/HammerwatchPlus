"""Roster validation, native profile conversion and export acceptance gates."""
import hashlib
import json
import struct
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from gamelab import hps
from gamelab.bots import play_profile as profile_bot
from tools import hwr_archive as hwr, play_profile, profile_seed
from tools.save_builder import Character, Plan, parse_character, parse_gold, DEFAULT_GOLD, MAX_GOLD


def native_profile(records, gold=DEFAULT_GOLD):
    def section(value):
        value = dict(value, padding="native records contain substantially more data" * 40)
        raw = hwr.encode_svalue(value)
        compressed = hwr.lz4_compress(raw)
        return struct.pack("<II", len(raw), len(compressed)) + compressed

    seed = play_profile.empty_profile(["gamelab-probe", "gamelab-hands"], "Native")
    header = hps.Header(seed)
    body = section({"materials": [gold, 0, 0, 0, 0, 0, 0]}) + struct.pack("<I", len(records))
    for index, record in enumerate(records, 1):
        body += struct.pack("<I", index) + section(record) + struct.pack("<I", 0)
    data = header.encode() + body
    return data + hashlib.md5(data).digest()[:4]


class SaveBuilderTests(unittest.TestCase):
    def test_starting_gold_defaults_to_one_million_and_accepts_zero_and_commas(self):
        self.assertEqual(Plan().starting_gold, 1_000_000)
        self.assertEqual(parse_gold("1,000,000"), 1_000_000)
        self.assertEqual(parse_gold("0"), 0)
        self.assertEqual(parse_gold(str(MAX_GOLD)), MAX_GOLD)
        for value in ("-1", "1.5", "money", str(MAX_GOLD + 1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_gold(value)
        for value in (-1, 1.5, True, MAX_GOLD + 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Plan(starting_gold=value).validate()

    def test_sorc_alias_and_default_name(self):
        self.assertEqual(parse_character("sorc:15"), Character("sorcerer", 15, "Sorcerer15"))

    def test_invalid_levels_names_and_duplicates_are_rejected(self):
        for character in (Character("sorcerer", 0, "Test"), Character("sorcerer", 21, "Test"),
                          Character("missing", 15, "Test"), Character("sorcerer", 15, "A + B")):
            with self.subTest(character=character), self.assertRaises(ValueError):
                Plan(characters=[character]).validate()
        with self.assertRaisesRegex(ValueError, "different name"):
            Plan(characters=[Character("sorcerer", 15, "Test"), Character("ranger", 1, "test")]).validate()

    def test_class_choices_follow_selected_packages(self):
        self.assertIn("hwp_firearms", profile_seed.available_classes(["firearms"]))
        self.assertNotIn("hwp_thief", profile_seed.available_classes(["firearms"]))
        self.assertNotIn("hwp_firearms", profile_seed.available_classes(["town"]))

    def test_native_body_and_character_data_are_preserved_when_removing_lab_mods(self):
        original = native_profile([{"class": "sorcerer", "name": "TestSorc", "level": 15, "experience": 664496}])
        converted = play_profile.from_native(original, ["HammerwatchPlus-All"], "Play")
        header = hps.Header(converted)
        self.assertEqual(header.mods, [hps.hash_string("HammerwatchPlus-All")])
        self.assertEqual(header.mod_name, b"Play")
        self.assertEqual(converted[header.body_offset:-4], original[hps.Header(original).body_offset:-4])
        self.assertEqual(play_profile.characters_in(converted), [{"class": "sorcerer", "name": "TestSorc", "level": 15}])
        self.assertTrue(hps.trailer_ok(converted))
        self.assertEqual(play_profile.gold_in(converted), DEFAULT_GOLD)

    def test_corrupt_native_profile_is_rejected(self):
        original = native_profile([{"class": "sorcerer", "name": "TestSorc", "level": 15}])
        with self.assertRaisesRegex(ValueError, "checksum"):
            play_profile.from_native(original[:-1] + bytes([original[-1] ^ 1]), ["HammerwatchPlus-All"], "Play")

    def test_export_requires_outer_pass_clean_teardown_and_exact_persisted_roster(self):
        plan = Plan(characters=[Character("sorcerer", 15, "TestSorc")])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = native_profile([{"class": "sorcerer", "name": "TestSorc", "level": 15}])
            (root / "profile.hps").write_bytes(data)
            good = {"verdict": "PASS", "teardown": {"clean": True},
                    "assertions": [{"ok": True}], "partial": False, "build_drift": False}
            for change in ({"verdict": "INVALID"}, {"partial": True}, {"build_drift": True},
                           {"teardown": {"clean": False}}, {"assertions": [{"ok": False}]}):
                (root / "run.json").write_text(json.dumps(good | change))
                with self.subTest(change=change), self.assertRaises(RuntimeError):
                    profile_seed.verified_export(root, plan)
            (root / "run.json").write_text(json.dumps(good))
            self.assertEqual(profile_seed.verified_export(root, plan), data)
            with self.assertRaisesRegex(RuntimeError, "roster differs"):
                profile_seed.verified_export(root, Plan(characters=[Character("ranger", 10, "Other")]))
            with self.assertRaisesRegex(RuntimeError, "gold differs"):
                profile_seed.verified_export(root, Plan(characters=plan.characters, starting_gold=2_500_000))

    def test_inline_fixture_uses_native_levelups_and_exact_first_character_readback(self):
        plan = Plan(characters=[Character("sorcerer", 15, "TestSorc"), Character("ranger", 1, "TestRanger")])
        with mock.patch.object(profile_seed, "required_unlocks", return_value=["unlocked_class_sorcerer"]):
            scenario = profile_seed.scenario(plan, ["all"], "test-builder")
        self.assertEqual(scenario["fixture"]["setup"][0]["args"], [14])
        self.assertEqual(scenario["fixture"]["readback"]["player.level"], 15)
        self.assertEqual(len(scenario["steps"][0]["kwargs"]["characters"]), 2)
        self.assertTrue(scenario["export_profile"])
        unlocks = [step["args"] for step in scenario["fixture"]["setup"] if step["verb"] == "townflag"]
        self.assertEqual(unlocks, [["unlocked_class_sorcerer", "on"]])
        money = [step for step in scenario["fixture"]["setup"] if step["verb"] == "townmoney"]
        self.assertEqual(money, [{"verb": "townmoney", "args": [DEFAULT_GOLD],
                                 "expect": {"ok": True, "gold": DEFAULT_GOLD}}])

    def test_gold_only_profile_has_no_hidden_seed_character(self):
        plan = Plan(starting_gold=2_500_000)
        scenario = profile_seed.scenario(plan, ["all"], "gold-only")
        self.assertIsNone(scenario["fixture"]["character"])
        self.assertEqual(scenario["fixture"]["readback"], {"phase": "no_character"})
        self.assertEqual(scenario["steps"][0]["kwargs"]["characters"], [])
        self.assertEqual(scenario["steps"][0]["kwargs"]["starting_gold"], 2_500_000)
        self.assertEqual(scenario["fixture"]["readback_probes"][-1]["expect"]["gold"], 2_500_000)

    def test_exported_zero_character_profile_keeps_configured_gold(self):
        data = native_profile([], gold=2_500_000)
        converted = play_profile.from_native(data, ["HammerwatchPlus-All"], "Funded")
        self.assertEqual(play_profile.characters_in(converted), [])
        self.assertEqual(play_profile.gold_in(converted), 2_500_000)
        self.assertEqual(play_profile.gold_in(play_profile.empty_profile(["HammerwatchPlus-All"], "Empty")), 0)

    def test_only_requested_class_unlock_flags_are_copied_from_game_definitions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "datatables/players/sorcerer/class_sorcerer.sval.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([{"id": "sorcerer", "conditionals": [
                ["local flag", "is", "unlocked_class_sorcerer"], ["local flag", "is", "unrelated_progress"]]},
                {"id": "sorcerer_fire", "conditionals": [["local flag", "is", "unlocked_other_class"]]}]))
            with mock.patch.object(profile_seed.gamepaths, "GAMECODE", root):
                self.assertEqual(profile_seed.required_unlocks(Plan(characters=[Character("sorcerer", 15, "Test")])),
                                 ["unlocked_class_sorcerer"])


class ExportFinality(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="h1-export-finality-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = Plan(characters=[Character("sorcerer", 15, "TestSorc")])
        self.data = native_profile([{"class": "sorcerer", "name": "TestSorc", "level": 15}])
        (self.root / "profile.hps").write_bytes(self.data)
        self.good = {"verdict": "PASS", "teardown": {"clean": True},
                     "assertions": [{"ok": True}], "partial": False,
                     "build_drift": False, "error": None}

    def reject(self, record):
        (self.root / "run.json").write_text(json.dumps(record))
        with self.assertRaises(RuntimeError):
            profile_seed.verified_export(self.root, self.plan)
        self.assertEqual((self.root / "profile.hps").read_bytes(), self.data)

    def test_complete_result_accepts_exact_persisted_roster_and_gold(self):
        (self.root / "run.json").write_text(json.dumps(self.good))
        self.assertEqual(profile_seed.verified_export(self.root, self.plan), self.data)

    def test_missing_finality_fields_are_refused(self):
        for key in ("partial", "build_drift", "assertions"):
            with self.subTest(missing=key):
                record = dict(self.good)
                del record[key]
                self.reject(record)

    def test_empty_or_malformed_assertions_are_refused(self):
        for value in ([], None, "not-a-list", [None]):
            with self.subTest(assertions=value):
                self.reject(self.good | {"assertions": value})

    def test_nonboolean_success_flags_are_refused(self):
        for change in ({"partial": 0}, {"build_drift": 0},
                       {"teardown": {"clean": 1}}, {"assertions": [{"ok": 1}]}):
            with self.subTest(change=change):
                self.reject(self.good | change)

    def test_nonobject_outer_result_is_refused(self):
        for value in ([], None, "PASS"):
            with self.subTest(outer=value):
                self.reject(value)


class ProfileCorruption(unittest.TestCase):
    @staticmethod
    def checksummed(raw):
        return raw + hashlib.md5(raw).digest()[:4]

    def header(self):
        return hps.Header(play_profile.empty_profile(["gamelab-probe"], "Native")).encode()

    def test_checksummed_truncated_header_has_public_validation_error(self):
        data = self.checksummed(hps.MAGIC + b"\x03\x00\x00\x00")
        with self.assertRaises(ValueError):
            play_profile.characters_in(data)

    def test_invalid_compressed_section_is_refused(self):
        data = self.checksummed(self.header() + struct.pack("<II", 2048, 8)
                                + b"\x00" * 8 + struct.pack("<I", 0))
        # LZ4's codec error is an existing documented refusal at this boundary.
        codec_error = hwr._lz4.LZ4BlockError if hwr._lz4 is not None else ValueError
        with self.assertRaises((ValueError, codec_error)):
            play_profile.characters_in(data)

    def test_truncated_svalue_is_refused_without_accepting_partial_identity(self):
        raw = hwr.encode_svalue({"padding": "x" * 2048, "truncated": True})[:-1]
        compressed = hwr.lz4_compress(raw)
        data = self.checksummed(self.header() + struct.pack("<II", len(raw), len(compressed))
                                + compressed + struct.pack("<I", 0))
        with self.assertRaises((ValueError, IndexError, struct.error)):
            play_profile.characters_in(data)

    def test_character_identity_field_types_are_validated(self):
        base = {"class": "sorcerer", "name": "TestSorc", "level": 1}
        for change in ({"class": 42}, {"name": []}, {"level": True}, {"level": "1"}, {"level": 0}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    play_profile.characters_in(native_profile([base | change]))

    def test_active_run_excessive_count_and_tail_are_refused(self):
        data = native_profile([{"class": "sorcerer", "name": "TestSorc", "level": 15}])
        malformed = [
            self.checksummed(data[:-8] + struct.pack("<I", 1)),
            self.checksummed(self.header() + struct.pack("<II", 0, 101)),
            self.checksummed(data[:-4] + b"tail"),
        ]
        for value in malformed:
            with self.subTest(shape=len(value)), self.assertRaises(ValueError):
                play_profile.characters_in(value)

    def test_town_gold_requires_nonboolean_signed32_integer(self):
        for gold in (True, -1, 2147483648, "100"):
            with self.subTest(gold=gold), self.assertRaises(ValueError):
                play_profile.gold_in(native_profile([], gold=gold))


class RequestBoundaries(unittest.TestCase):
    def test_roster_count_empty_and_maximum_neighbors(self):
        for count in (0, 1, 16):
            Plan(characters=[Character("warrior", 1, f"Hero{i}") for i in range(count)]).validate()
        with self.assertRaises(ValueError):
            Plan(characters=[Character("warrior", 1, f"Hero{i}") for i in range(17)]).validate()

    def test_character_name_utf8_bytes_and_casefold_duplicates(self):
        Character("warrior", 1, chr(233) * 24).validate()
        for name in ("", chr(233) * 25, "two names", "bad|pipe", "line" + chr(10)):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                Character("warrior", 1, name).validate()
        with self.assertRaises(ValueError):
            Plan(characters=[Character("warrior", 1, "Stra" + chr(223) + "e"),
                             Character("ranger", 1, "STRASSE")]).validate()

    def test_profile_name_utf8_bytes_and_nul(self):
        Plan(profile_name=chr(233) * 120).validate()
        for name in ("", chr(233) * 121, "bad" + chr(0)):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                Plan(profile_name=name).validate()

    def test_level_and_gold_boundary_types(self):
        for level in (1, 20):
            Character("warrior", level, "Hero").validate()
        for level in (0, 21, True, 1.0):
            with self.subTest(level=level), self.assertRaises(ValueError):
                Character("warrior", level, "Hero").validate()
        for gold in (0, MAX_GOLD):
            Plan(starting_gold=gold).validate()
            self.assertEqual(parse_gold(str(gold)), gold)
        for gold in (-1, MAX_GOLD + 1, True, 1.0):
            with self.subTest(gold=gold), self.assertRaises(ValueError):
                Plan(starting_gold=gold).validate()

    def test_package_availability_follows_required_module(self):
        for modules, firearms, thief in (([], False, False), (["firearms"], True, False),
                                        (["classes"], False, True)):
            with self.subTest(modules=modules), mock.patch.object(profile_seed, "modules_for", return_value=modules):
                available = profile_seed.available_classes(["audited-fixture"])
                self.assertEqual("hwp_firearms" in available, firearms)
                self.assertEqual("hwp_thief" in available, thief)
                self.assertIn("warrior", available)

    def test_unlocks_are_requested_only_sorted_and_deduplicated(self):
        with tempfile.TemporaryDirectory(prefix="h1-unlocks-") as temp:
            root = Path(temp)
            for class_id in ("sorcerer", "ranger"):
                path = root / "datatables/players" / class_id / f"class_{class_id}.sval.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps([{"id": class_id, "conditionals": [
                    ["local flag", "is", "unlocked_class_" + class_id],
                    ["local flag", "is", "unlocked_class_" + class_id],
                    ["local flag", "is", "unrelated_progress"]]},
                    {"id": class_id + "_other", "conditionals": [
                        ["local flag", "is", "unlocked_class_unrequested"]]}]))
            plan = Plan(characters=[Character("sorcerer", 1, "A"), Character("ranger", 1, "B")])
            with mock.patch.object(profile_seed.gamepaths, "GAMECODE", root):
                self.assertEqual(profile_seed.required_unlocks(plan),
                                 ["unlocked_class_ranger", "unlocked_class_sorcerer"])

    class FakeGame:
        def __init__(self, mode="ready", gold=100):
            self.mode, self.gold, self.calls = mode, gold, []
            self.player = {"class": "sorcerer", "name": "First", "level": 1, "dead": False}
            if mode == "wrong-first":
                self.player["class"] = "ranger"

        def gl_cmd(self, verb, *args):
            self.calls.append((verb, *args))
            if verb == "state":
                return {"phase": "town", "player": dict(self.player)}
            if verb == "char":
                if self.mode == "char-refused":
                    return {"ok": False, "error": "fixture refusal"}
                if self.mode != "timeout":
                    self.player = {"class": args[0], "name": args[1], "level": 1, "dead": False}
                    if self.mode == "wrong-class":
                        self.player["class"] = "sorcerer"
                return {"ok": True}
            if verb == "levelup":
                self.player["level"] += args[0]
                return {"ok": True, "level": self.player["level"] - (1 if self.mode == "wrong-level" else 0)}
            if verb == "save":
                return {"ok": self.mode != "save-refused"}
            if verb == "townmoney":
                return {"ok": True, "gold": self.gold}
            raise AssertionError(verb)

    def run_bot(self, mode="ready", characters=None, gold=100):
        from types import SimpleNamespace
        game = self.FakeGame(mode, gold)
        characters = characters if characters is not None else [
            {"class_id": "sorcerer", "name": "First", "level": 1},
            {"class_id": "ranger", "name": "Second", "level": 10}]
        tick = iter(range(0, 10000, 31))
        with mock.patch.object(profile_bot.time, "monotonic", side_effect=lambda: next(tick)),                 mock.patch.object(profile_bot.time, "sleep", return_value=None):
            result = profile_bot.run(SimpleNamespace(game=game), characters, starting_gold=100)
        return result, game.calls

    def test_bot_empty_roster_only_checks_gold_and_saves(self):
        result, calls = self.run_bot(characters=[])
        self.assertTrue(result["ok"])
        self.assertEqual(calls, [("townmoney",), ("save",)])

    def test_bot_happy_path_orders_creation_leveling_and_persistence(self):
        result, calls = self.run_bot()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(calls, [("state",), ("save",), ("char", "ranger", "Second"),
                                 ("state",), ("levelup", 9), ("state",), ("save",),
                                 ("townmoney",), ("save",)])

    def test_bot_timeout_does_not_level_or_save_the_prior_character(self):
        result, calls = self.run_bot("timeout")
        self.assertFalse(result["ok"])
        index = next(i for i, call in enumerate(calls) if call[0] == "char")
        self.assertFalse(any(call[0] in ("levelup", "save") for call in calls[index + 1:]), calls)

    def test_bot_wrong_class_readiness_does_not_level_or_save(self):
        result, calls = self.run_bot("wrong-class")
        self.assertFalse(result["ok"])
        index = next(i for i, call in enumerate(calls) if call[0] == "char")
        self.assertFalse(any(call[0] in ("levelup", "save") for call in calls[index + 1:]), calls)

    def test_bot_mismatched_first_identity_is_not_saved(self):
        result, calls = self.run_bot("wrong-first")
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [("state",)])

    def test_bot_native_refusal_and_gold_mismatch_never_claim_success(self):
        for mode, gold in (("char-refused", 100), ("wrong-level", 100),
                           ("save-refused", 100), ("ready", 99)):
            with self.subTest(mode=mode, gold=gold):
                result, _ = self.run_bot(mode, gold=gold)
                self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
