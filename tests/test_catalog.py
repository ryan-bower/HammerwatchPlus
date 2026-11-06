"""Catalog admission tests use only disposable files, never a GameLab backend."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gamelab import catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="catalog-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(catalog, "ROOT", self.root).start()
        # Even the valid path must be entirely filesystem/AST based.
        patch("subprocess.Popen", side_effect=AssertionError("no processes in catalog tests")).start()
        patch("socket.socket", side_effect=AssertionError("no sockets in catalog tests")).start()
        self.scenario = {"name": "sample", "fixture": "town", "mods": ["feature"],
                         "timeout": 20, "outer_timeout": 30,
                         "steps": [{"do": "bot", "bot": "sample", "expect": {"ok": True}},
                                   {"do": "log_clean"}]}
        self.put("gamelab/scenarios/sample.json", self.scenario)
        self.put("gamelab/fixtures/town.json", {"name": "town", "binary_edits": {"enable_mods": ["probe"]}})
        self.put("mods/feature/module.json", {"id": "feature", "requires": ["probe"]})
        self.put("mods/probe/module.json", {"id": "probe", "requires": []})
        self.put("gamelab/bots/sample.py", "from gamelab.bots.helper import run\nraise AssertionError('never import')\n")
        self.put("gamelab/bots/helper.py", "def run(*args):\n    raise AssertionError('never execute')\n")
        self.put("mods/feature/scripts/Consumer.as", "// explicit reviewed resource\n")
        self.put("docs/review.json", {"review": "finite fixture audit"})
        files = ["gamelab/scenarios/sample.json", "gamelab/fixtures/town.json",
                 "gamelab/bots/sample.py", "gamelab/bots/helper.py",
                 "mods/feature/module.json", "mods/probe/module.json",
                 "mods/feature/scripts/Consumer.as"]
        self.entry = {"id": "sample", "status": "reviewed", "scenario": files[0],
                      "task": "TEST-SAMPLE", "check": "sample", "scope": "controlled-native",
                      "expected": "Fixture consumer only; no ordinary gameplay claim.",
                      "predicates": [{"step": 0, "expect": {"ok": True}}],
                      "lifecycle": "independent", "private_writes": ["slot-game", "slot-results"],
                      "review": {"reviewer": "fixture-reviewer", "verdict": "accepted",
                                 "artifact": "docs/review.json", "sha256": self.sha("docs/review.json"),
                                 "closure_complete": True},
                      "closure": {"files": catalog.hash_reviewed_files(files),
                                  "bots": ["sample", "helper"], "fixture": "town",
                                  "modules": ["feature", "probe"]}}
        self.document = {"schema_version": 1, "catalog_id": "fixture-v1", "cases": [self.entry]}
        self.path = self.root / "docs/qa/swarm/catalogs/test.json"

    def put(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = value if isinstance(value, str) else json.dumps(value, indent=2)
        path.write_text(raw, encoding="utf-8")
        return path

    def sha(self, relative):
        return hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def load(self):
        self.put(self.path.relative_to(self.root).as_posix(), self.document)
        return catalog.load_catalog(self.path)

    def refresh_scenario(self):
        self.put("gamelab/scenarios/sample.json", self.scenario)
        self.entry["closure"]["files"]["gamelab/scenarios/sample.json"] = self.sha("gamelab/scenarios/sample.json")

    def refuse(self, action, code):
        with self.assertRaises(catalog.CatalogError) as raised:
            action()
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(raised.exception.as_dict()["code"], code)

    def test_valid_case_preserves_labels_predicates_and_exact_file_pins_without_import(self):
        loaded = self.load()
        result = catalog.validate_case(loaded, "sample")
        self.assertEqual(result["scenario"], self.scenario)
        admission = result["admission"]
        self.assertEqual(admission["task"], "TEST-SAMPLE")
        self.assertEqual(admission["predicates"], self.entry["predicates"])
        self.assertEqual(admission["files"], self.entry["closure"]["files"])
        self.assertEqual(admission["catalog_sha256"], self.sha(self.path.relative_to(self.root)))
        self.assertEqual(admission["consumers"], [])

    def test_exact_snapshot_preserves_admission_after_original_catalog_changes(self):
        loaded = self.load()
        snapshot = self.root / "gamelab/results/pool/catalog.snapshot.json"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_bytes(self.path.read_bytes())
        frozen = catalog.load_catalog(snapshot, loaded["metadata"]["sha256"])
        first = catalog.validate_case(loaded, "sample")
        self.assertEqual(catalog.validate_case(frozen, "sample"), first)
        self.path.write_text("{}", encoding="utf-8")
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "catalog-hash")
        self.assertEqual(catalog.validate_case(frozen, "sample"), first)

    def test_catalog_digest_required_when_supplied(self):
        self.load()
        self.refuse(lambda: catalog.load_catalog(self.path, "0" * 64), "catalog-hash")

    def test_descriptor_mutation_is_not_an_alternate_admission_path(self):
        loaded = self.load()
        loaded["cases"][0]["task"] = "MUTATED"
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "catalog-tampered")

    def test_missing_explicit_closure_is_refused_before_any_dispatch(self):
        del self.entry["closure"]
        self.refuse(self.load, "schema")

    def test_missing_mandatory_fixture_leaf_is_refused(self):
        del self.entry["closure"]["files"]["gamelab/fixtures/town.json"]
        self.refuse(self.load, "closure")

    def test_stale_direct_bot_and_resource_are_both_refused(self):
        loaded = self.load()
        for relative in ("gamelab/bots/sample.py", "mods/feature/scripts/Consumer.as"):
            with self.subTest(path=relative):
                path = self.root / relative
                raw = path.read_bytes()
                path.write_bytes(raw + b"\n// changed")
                self.refuse(lambda: catalog.validate_case(loaded, "sample"), "stale-hash")
                path.write_bytes(raw)

    def test_selected_case_ignores_unrelated_stale_closure(self):
        other = copy.deepcopy(self.entry)
        other.update(id="other", scenario="gamelab/scenarios/other.json", check="other")
        other["closure"]["files"][other["scenario"]] = "0" * 64
        self.document["cases"].append(other)
        loaded = self.load()
        self.assertEqual(catalog.validate_case(loaded, "sample")["admission"]["id"], "sample")
        self.refuse(lambda: catalog.validate_case(loaded, "other"), "unreadable")

    def test_list_statuses_does_not_award_eligibility_or_read_sources(self):
        self.entry["status"] = "blocked"
        loaded = self.load()
        (self.root / "gamelab/bots/sample.py").unlink()
        self.assertEqual(catalog.list_cases(loaded)[0]["status"], "blocked")
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "ineligible")

    def test_historical_descriptor_does_not_revalidate_changed_live_closure(self):
        loaded = self.load()
        (self.root / "gamelab/bots/sample.py").unlink()
        (self.root / "docs/review.json").unlink()
        historical = catalog.describe_case(loaded, "sample")
        self.assertEqual(historical, self.entry)
        historical["task"] = "LOCAL-EDIT"
        self.assertEqual(catalog.describe_case(loaded, "sample")["task"], "TEST-SAMPLE")
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "unreadable")

    def test_unknown_case_and_exclusive_lifecycle_refuse(self):
        loaded = self.load()
        self.refuse(lambda: catalog.validate_case(loaded, "absent"), "unknown-case")
        self.entry["lifecycle"] = "exclusive"
        loaded = self.load()
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "ineligible")

    def test_review_artifact_is_pinned(self):
        loaded = self.load()
        self.put("docs/review.json", {"changed": True})
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "review-hash")

    def test_review_requires_literal_complete_and_accepted_assertions(self):
        for field, value in (("closure_complete", 1), ("closure_complete", False), ("verdict", "pending")):
            with self.subTest(field=field, value=value):
                original = self.entry["review"][field]
                self.entry["review"][field] = value
                self.refuse(self.load, "schema")
                self.entry["review"][field] = original

    def test_unknown_fields_at_each_descriptor_layer_refuse(self):
        for target in (self.document, self.entry, self.entry["review"], self.entry["closure"], self.entry["predicates"][0]):
            with self.subTest(keys=list(target)):
                target["typo"] = True
                self.refuse(self.load, "schema")
                del target["typo"]

    def test_duplicate_json_keys_and_nonfinite_numbers_refuse(self):
        self.load()
        for raw in ('{"schema_version":1,"schema_version":1}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'):
            with self.subTest(raw=raw):
                self.path.write_text(raw, encoding="utf-8")
                self.refuse(lambda: catalog.load_catalog(self.path), "json")

    def test_casefold_case_collision_is_refused(self):
        other = copy.deepcopy(self.entry)
        other.update(id="Sample", check="Sample", scenario="gamelab/scenarios/Sample.json")
        self.document["cases"].append(other)
        self.refuse(self.load, "schema")

    def test_invalid_paths_refuse_without_reading_external_leaves(self):
        for relative in ("../outside", "/absolute", "C:/outside", "mods\\x", "mods//x", "mods/NUL.txt", "mods/COM\u00b9.x", "mods/x. ", "mods/*"):
            with self.subTest(path=relative):
                self.entry["closure"]["files"][relative] = "0" * 64
                self.refuse(self.load, "path")
                del self.entry["closure"]["files"][relative]

    def test_live_state_is_not_a_source_closure(self):
        for relative in ("gamelab/env/userdata/x", "gamelab/results/x", "gamelab/fixtures/cache/x", ".git/config"):
            with self.subTest(path=relative):
                self.entry["closure"]["files"][relative] = "0" * 64
                self.refuse(self.load, "path")
                del self.entry["closure"]["files"][relative]

    def test_external_catalog_path_refuses(self):
        self.refuse(lambda: catalog.load_catalog(self.root.parent / "unowned.json"), "path")

    def test_masked_reparse_ancestor_refuses_using_lstat(self):
        loaded = self.load()
        real_lstat = Path.lstat
        ancestor = self.root / "mods/feature"
        def redirected(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if path == ancestor:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_nlink=1, st_file_attributes=0x400)
            return info
        with patch.object(Path, "lstat", redirected):
            self.refuse(lambda: catalog.validate_case(loaded, "sample"), "path")

    def test_unreadable_ancestor_is_not_treated_as_absent(self):
        loaded = self.load()
        real_lstat = Path.lstat
        def denied(path, *args, **kwargs):
            if path == self.root / "mods/feature":
                raise PermissionError("fixture denied")
            return real_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", denied):
            self.refuse(lambda: catalog.validate_case(loaded, "sample"), "unreadable")

    def test_hardlinked_leaf_is_refused(self):
        loaded = self.load()
        path = self.root / "mods/feature/scripts/Consumer.as"
        alias = path.with_name("alias.as")
        os.link(path, alias)
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "path")

    def test_transitive_bot_import_omission_is_refused(self):
        self.entry["closure"]["bots"].remove("helper")
        del self.entry["closure"]["files"]["gamelab/bots/helper.py"]
        loaded = self.load()
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "closure")

    def test_relative_bot_import_omission_is_refused(self):
        self.put("gamelab/bots/sample.py", "from .missing import run\n")
        self.entry["closure"]["files"]["gamelab/bots/sample.py"] = self.sha("gamelab/bots/sample.py")
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "closure")

    def test_direct_bot_cannot_be_substituted_by_review_text(self):
        self.scenario["steps"][0]["bot"] = "unreviewed"
        self.refresh_scenario()
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "closure")

    def test_predicate_mismatch_refuses_even_with_fresh_source_hash(self):
        self.scenario["steps"][0]["expect"] = {"ok": False}
        self.refresh_scenario()
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "predicates")

    def test_predicates_distinguish_json_boolean_from_numeric_one(self):
        self.entry["predicates"][0]["expect"] = {"ok": 1}
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "predicates")

    def test_all_actual_predicates_must_be_bound(self):
        self.scenario["steps"].append({"do": "gl", "verb": "state", "expect": {"ok": True}})
        self.refresh_scenario()
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "predicates")

    def test_unsafe_top_level_keys_refuse_even_false_values(self):
        for key in ("plan", "explore", "packages", "profile_export", "export_profile", "exports"):
            with self.subTest(key=key):
                self.scenario[key] = False
                self.refresh_scenario()
                self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "unsafe-scenario")
                del self.scenario[key]

    def test_relaunch_and_write_steps_cannot_be_admitted_by_data(self):
        for operation in ("restart", "write_file", "write_mod_file", "unknown"):
            with self.subTest(operation=operation):
                self.scenario["steps"][1]["do"] = operation
                self.refresh_scenario()
                self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "unsafe-step")

    def test_invalid_budgets_refuse(self):
        for number in (True, 0, -1, 3601, "10"):
            with self.subTest(value=number):
                self.scenario["outer_timeout"] = number
                self.refresh_scenario()
                self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "budget")

    def test_module_transitive_dependency_cannot_be_omitted(self):
        self.put("mods/feature/module.json", {"id": "feature", "requires": ["unreviewed"]})
        self.entry["closure"]["files"]["mods/feature/module.json"] = self.sha("mods/feature/module.json")
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "closure")

    def test_new_enabled_or_transitive_module_leaves_are_not_implicitly_reviewed(self):
        loaded = self.load()
        for relative in ("mods/feature/scripts/Extra.as", "mods/probe/scripts/Extra.as", "mods/feature/res/extra.png"):
            with self.subTest(path=relative):
                path = self.put(relative, "unreviewed leaf")
                self.refuse(lambda: catalog.validate_case(loaded, "sample"), "closure-inventory")
                path.unlink()

    def test_deleted_reviewed_module_leaf_refuses_admission(self):
        loaded = self.load()
        (self.root / "mods/feature/scripts/Consumer.as").unlink()
        self.refuse(lambda: catalog.validate_case(loaded, "sample"), "unreadable")

    def test_unlisted_symlink_or_reparse_subtree_is_refused_without_traversal(self):
        loaded = self.load()
        redirected = self.root / "mods/feature/redirected"
        redirected.mkdir()
        original_lstat, original_iterdir = Path.lstat, Path.iterdir
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400)):
            with self.subTest(mode=mode, attributes=attributes):
                def lstat(path, *args, **kwargs):
                    if path == redirected:
                        return SimpleNamespace(st_mode=mode, st_nlink=1, st_file_attributes=attributes)
                    return original_lstat(path, *args, **kwargs)
                def iterdir(path):
                    if path == redirected:
                        raise AssertionError("redirected module subtree must not be traversed")
                    return original_iterdir(path)
                with patch.object(Path, "lstat", lstat), patch.object(Path, "iterdir", iterdir):
                    self.refuse(lambda: catalog.validate_case(loaded, "sample"), "path")

    def test_inventory_visits_only_selected_enabled_and_transitive_modules(self):
        loaded = self.load()
        self.put("mods/unrelated/module.json", {"id": "unrelated"})
        self.put("mods/unrelated/scripts/Unreviewed.as", "unreviewed unrelated source")
        original_iterdir = Path.iterdir
        visited = []
        def iterdir(path):
            visited.append(path)
            if path == self.root / "mods" or path.is_relative_to(self.root / "mods/unrelated"):
                raise AssertionError("unselected module inventory must not be read")
            return original_iterdir(path)
        with patch.object(Path, "iterdir", iterdir):
            self.assertEqual(catalog.validate_case(loaded, "sample")["admission"]["id"], "sample")
        self.assertIn(self.root / "mods/feature", visited)
        self.assertIn(self.root / "mods/probe", visited)

    def test_explicit_reviewed_inventory_accepts_additional_leaf_and_slot_module_deployment(self):
        relative = "mods/probe/scripts/Reviewed.as"
        self.put(relative, "// explicitly reviewed dependency source")
        self.entry["closure"]["files"][relative] = self.sha(relative)
        self.entry["private_writes"].append("slot-modules")
        result = catalog.validate_case(self.load(), "sample")
        self.assertEqual(result["admission"]["files"][relative], self.sha(relative))
        self.assertIn("slot-modules", result["admission"]["private_writes"])

    def test_fixture_module_is_required_even_when_scenario_does_not_name_it(self):
        self.entry["closure"]["modules"].remove("probe")
        del self.entry["closure"]["files"]["mods/probe/module.json"]
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "closure")

    def test_source_identity_and_fixture_identity_are_bound(self):
        self.scenario["fixture"] = "other"
        self.refresh_scenario()
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "scenario")

    def test_consumer_tags_are_explicit_and_bind_exact_bot_step(self):
        consumers = [{"step": 0, "bot": "sample", "rows": ["fixture", "consumer", "preservation"]}]
        self.entry["consumers"] = consumers
        result = catalog.validate_case(self.load(), "sample")
        self.assertEqual(result["admission"]["consumers"], consumers)
        self.entry["consumers"][0]["step"] = 1
        self.refuse(lambda: catalog.validate_case(self.load(), "sample"), "consumers")

    def test_consumer_duplicate_or_unknown_fields_refuse(self):
        self.entry["consumers"] = [{"step": 0, "bot": "sample", "rows": ["same", "same"]}]
        self.refuse(self.load, "schema")
        self.entry["consumers"][0]["rows"] = ["only"]
        self.entry["consumers"][0]["typo"] = True
        self.refuse(self.load, "schema")

    def test_hash_sealing_is_explicit_and_does_not_mutate_review_or_catalog(self):
        loaded = self.load()
        raw = self.path.read_bytes()
        review = copy.deepcopy(self.entry["review"])
        hashes = catalog.hash_reviewed_files(["gamelab/bots/helper.py"])
        self.assertEqual(hashes, {"gamelab/bots/helper.py": self.sha("gamelab/bots/helper.py")})
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(self.entry["review"], review)
        self.assertEqual(catalog.list_cases(loaded)[0]["id"], "sample")
        self.refuse(lambda: catalog.hash_reviewed_files(["mods/feature/*.as"]), "path")


if __name__ == "__main__":
    unittest.main()
