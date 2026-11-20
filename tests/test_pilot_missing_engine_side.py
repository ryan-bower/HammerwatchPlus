"""Pilot client calls that have no in-engine side fail fast, before anything is sent."""
import unittest
from unittest.mock import Mock

from gamelab.pilot import Pilot


class MissingEngineSide(unittest.TestCase):
    def setUp(self):
        self.game = Mock()
        self.pilot = Pilot(self.game)

    def test_unsupported_calls_raise_without_sending(self):
        for call in (lambda: self.pilot.loot(), lambda: self.pilot.lootmap(),
                     lambda: self.pilot.reflex(dodge=200), lambda: self.pilot.reflex(traps="weave")):
            with self.assertRaises(NotImplementedError):
                call()
        self.game.gl_cmd.assert_not_called()

    def test_supported_reflex_still_sends(self):
        self.pilot.reflex(potion=40, fire=300)
        self.game.gl_cmd.assert_called_once()


if __name__ == "__main__":
    unittest.main()
