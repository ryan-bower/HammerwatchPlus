"""Roster validation, native profile conversion and export acceptance gates."""
import hashlib
import json
import struct
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from gamelab import hps
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
            good = {"verdict": "PASS", "teardown": {"clean": True}, "assertions": [], "partial": False}
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


if __name__ == "__main__":
    unittest.main()
