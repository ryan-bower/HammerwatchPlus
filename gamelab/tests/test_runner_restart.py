"""Restart selection must preserve fixture, mod, probe and muted-profile gates."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gamelab.runner import GameError, Run


class FakeGame:
    def __init__(self, phase="mission"):
        self.phase = phase
        self.commands = []
        self.state = {"phase": phase, "player": {"class": "hwp_firearms", "level": 20, "dead": False}}
        self.probe = {"clip": 12}
        self.mods = [{"id": "core", "enabled": True}]
        self.cvars = {"snd_volume": 0, "e_cheats": 1}
        self.saved_run = "qa-run"

    def wait_gl(self, predicate, timeout):
        for phase in ("no_character", self.phase):
            hb = {"ev": "hb", "phase": phase}
            if predicate(hb):
                return hb

    def gl_cmd(self, verb, *args):
        self.commands.append((verb, *args))
        if verb == "pick":
            return {"ok": True, "choice": args[1] if len(args) > 1 else "town", "run": self.saved_run}
        if verb == "cvars":
            return {"cvars": self.cvars}
        raise AssertionError(verb)

    def gl_multi(self, commands):
        return [self.state, self.probe, {"mods": self.mods}]


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "lab").mkdir()
        (root / "lab" / "HWR2.exe.cfg").write_text("fixture profile", encoding="utf-8")
        self.addCleanup(patch.stopall)
        patch("gamelab.runner.env.SETTINGS", root).start()
        patch("gamelab.runner.env.cvars", return_value={"snd_volume": "0", "e_cheats": "1"}).start()
        self.runner = Run({}, root, "lab")
        self.game = FakeGame()
        self.runner.boot = Mock(return_value=self.game)
        self.runner.finish = Mock()
        self.runner.recipe = {
            "readback": {"phase": "town", "player.class": "hwp_firearms", "player.level": 20, "player.dead": False},
            "readback_probes": [{"verb": "magazine", "expect": {"clip": 12}}],
            "binary_edits": {"enable_mods": ["core"]},
        }

    def resume(self):
        return self.runner.step(self.game, {"do": "restart", "choice": "resume", "readback": {"phase": "mission"}}, {})

    def test_default_restart_keeps_town_selection(self):
        self.game.phase = self.game.state["phase"] = "town"
        self.assertIs(self.runner.step(self.game, {"do": "restart"}, {}), self.game)
        self.runner.finish.assert_called_once_with(self.game)
        self.assertIn(("pick", 0), self.game.commands)
        self.assertTrue(all(a["ok"] for a in self.runner.assertions))

    def test_resume_uses_native_choice_and_records_readback(self):
        self.assertIs(self.resume(), self.game)
        self.assertIn(("pick", 0, "resume"), self.game.commands)
        entry = self.runner.out["fixture_entries"][-1]
        self.assertEqual(entry["selection"]["run"], "qa-run")
        self.assertEqual(entry["readback"]["player.level"], 20)
        self.assertTrue(all(a["ok"] for a in self.runner.assertions))

    def test_resume_preserves_identity_check(self):
        self.game.state["player"]["class"] = "wrong"
        with self.assertRaisesRegex(GameError, "fixture readback failed"):
            self.resume()

    def test_resume_preserves_recipe_probe(self):
        self.game.probe["clip"] = 11
        with self.assertRaisesRegex(GameError, "fixture readback failed"):
            self.resume()

    def test_resume_preserves_exact_mod_and_mute_assertions(self):
        self.game.mods.append({"id": "unexpected", "enabled": True})
        self.game.cvars["snd_volume"] = 1
        self.resume()
        failures = [a["name"] for a in self.runner.assertions if not a["ok"]]
        self.assertTrue(any("enabled mods" in name for name in failures))
        self.assertTrue(any("profile loaded" in name for name in failures))

    def test_resume_requires_actual_saved_run(self):
        self.game.saved_run = ""
        with self.assertRaisesRegex(GameError, "no saved run to resume"):
            self.resume()

    def no_selection_window(self):
        # the game went straight to town: no character selection window to pick from
        self.game.wait_gl = lambda predicate, timeout: {"ev": "hb", "phase": "town"}
        self.game.state["phase"] = "town"

    def test_explicit_town_without_selection_window_is_the_default(self):
        self.no_selection_window()
        self.assertIs(self.runner.step(self.game, {"do": "restart", "choice": "town"}, {}), self.game)
        self.assertNotIn(("pick", 0, "town"), self.game.commands)
        self.assertTrue(all(a["ok"] for a in self.runner.assertions))

    def test_resume_without_selection_window_is_refused(self):
        self.no_selection_window()
        with self.assertRaisesRegex(GameError, "requires the character selection window"):
            self.resume()

    def test_unknown_choice_is_rejected_before_boot(self):
        with self.assertRaisesRegex(GameError, "unsupported restart choice"):
            self.runner.enter_fixture(self.runner.recipe, [], choice="unknown")
        self.runner.boot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
