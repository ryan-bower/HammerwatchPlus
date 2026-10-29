"""tools/make_forgemaster_risen.py: the generated units' invariants, without a game.

    python -m unittest tools.test_make_forgemaster_risen -q

Needs the game dumps (gamecode/sdk/hoh2/actors, `python -m gamelab doctor --fix`); skipped without.
"""
from __future__ import annotations

import re
import sys
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_forgemaster_risen as gen  # noqa: E402


@unittest.skipUnless(gen.ACTORS.is_dir(), "gamecode/sdk/hoh2/actors missing")
class GeneratedUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.rels = gen.build()
        cls.risen = {rel: cls.out[gen.RISEN / rel] for rel in cls.rels}
        cls.bodies = {rel: cls.out[gen.BODIES / rel] for rel in cls.rels}

    def test_every_unit_parses(self):
        bad = [(p, why) for p, t in self.out.items() if p.suffix == ".unit" and (why := gen.well_formed(t))]
        self.assertEqual(bad, [])

    def test_risen_look_like_summons(self):
        for rel, t in self.risen.items():
            with self.subTest(rel=rel):
                self.assertNotIn('mats:enemy"', t)
                self.assertNotIn("mats:enemy_maggot", t)
                self.assertNotIn("minimap.unit:enemy_", t)
                self.assertNotIn("actors/shared/elite_marker.unit", t)
                self.assertIn(f'<float name="target-find-cooldown-mul">{gen.SEARCH_MUL}</float>', t)
                self.assertRegex(t, r'<behavior class="HWPSpecsRisen(State)?Unit">')
        # a unit drawn with the enemy material has the NPC one now (a totem's default-noxray, a
        # shade's effects stay: they were never the enemies' red)
        src = gen.enemy_units()
        for rel, text in src:
            if rel in self.risen and gen.ENEMY_MATERIAL_RE.search(gen.common(rel, text)):
                self.assertIn(gen.RISEN_MATERIAL, self.risen[rel], rel)
                self.assertIn(gen.BODY_MATERIAL, self.bodies[rel], rel)
        elite = self.risen["undead/horde/horde_soldier_elite.unit"]
        self.assertIn(gen.MARKER_REL + "elite_marker.unit:16", elite)
        self.assertIn(gen.RISEN_MINIMAP, elite)

    def test_bodies_are_dead_dark_and_shot_through(self):
        for rel, t in self.bodies.items():
            with self.subTest(rel=rel):
                self.assertIn(f'<behavior class="{gen.BODY_CLASS}">', t)
                self.assertNotIn("mats:enemy", t)
                self.assertNotIn("minimap.unit:", t)
                self.assertNotIn("elite_marker", t)
                live = re.sub(r"^[ 	]*%//.*$", "", t, flags=re.M)  # Arista keeps a %// commented effect
                self.assertNotIn("<effect", live)
                self.assertNotIn("<light", live)
                self.assertNotIn("<particle", live)
                self.assertNotIn("looping=", live)
                self.assertNotIn("random-start=", live)
                for shape in gen.SHAPE_RE.findall(t):
                    for attr in gen.THROUGH:
                        self.assertIn(f'{attr}="true"', shape, shape)
                    self.assertNotIn('shoot-through="false"', shape)
                # a sprite without % lines keeps one frame
                for sprite in gen.SPRITE_RE.findall(t):
                    if not re.search(r"^[ \t]*%", sprite, re.M):
                        self.assertEqual(len(gen.FRAME_RE.findall(sprite)), 1, sprite[:200])

    def test_wisp_body_is_a_still_core(self):
        for rel in ("aberrations/wisp/wisp_lightning.unit", "aberrations/wisp/wisp_fire_giant.unit"):
            if rel not in self.bodies:
                continue
            t = self.bodies[rel]
            self.assertIn(gen.MARKER_REL + "dead_core.png", t)
            self.assertIn(gen.BODY_MATERIAL, t)
            self.assertIn('<scene name="idle" editor-bounds="-16 -16 32 32">' + gen.DEAD_CORE, t)
        bat = self.bodies["beasts/bats/bat_black.unit"]
        self.assertNotIn("dead_core", bat)   # a bat keeps its own (frozen) sprite
        self.assertEqual(bat.count('<frame time="90">'), 1)

    def test_marker_ring_is_orange(self):
        from PIL import Image
        png = self.out[gen.MARKER / "elite_marker.png"]
        im = Image.open(BytesIO(png)).convert("RGBA")
        bright = [im.getpixel((x, y)) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3] > 200]
        self.assertTrue(bright)
        best = max(bright, key=lambda p: p[0])
        self.assertEqual(best[:3], gen.RING_COLOR)
        for p in bright:  # every opaque pixel keeps the ring's hue: no red (g 0) or green pixel left
            self.assertLessEqual(abs(p[1] * gen.RING_COLOR[0] - p[0] * gen.RING_COLOR[1]), 255 * 2)
            self.assertEqual(p[2], 0)
        core = Image.open(BytesIO(self.out[gen.MARKER / "dead_core.png"])).convert("RGBA")
        self.assertEqual(core.size, (gen.CORE_TEX, gen.CORE_TEX))
        self.assertEqual(gen.CORE_TEX & (gen.CORE_TEX - 1), 0, "texture side must be a power of two")
        self.assertTrue(all(p[0] == p[1] == p[2] for p in core.get_flattened_data()))
        unit = self.out[gen.MARKER / "elite_marker.unit"]
        for n in (14, 16, 20):
            self.assertIn(f'src="{gen.MARKER_REL}elite_marker_{n}.effect"', unit)
            eff = self.out[gen.MARKER / f"elite_marker_{n}.effect"]
            self.assertIn(f'texture="{gen.MARKER_REL}elite_marker.png"', eff)
            self.assertIn('material="actors/shared/shared.mats:elite"', eff)
            self.assertNotIn('"./', eff)

    def test_gitignore_block_names_every_dir(self):
        block = gen.ignore_text("")
        for d in ("risen", "bodies", "marker"):
            self.assertIn("/" + gen.FORGE + d + "/", block)


if __name__ == "__main__":
    unittest.main()
