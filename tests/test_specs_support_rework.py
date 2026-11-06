"""Source/data contracts only; these do not replace native/co-op gameplay tests."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "mods/specs"


def skill(path):
    text = (SPECS / "players/hwp/specs" / path).read_text()
    return ET.fromstring(re.sub(r'^%include.*$', '', text, flags=re.M))


class SupportReworkContracts(unittest.TestCase):
    def test_standard_rank_values(self):
        root = skill("bannerlord/battlefield_standard.sval")
        ranks = [root.find("dict[@name='skill']"), *root.find("array[@name='upgrades']")]
        values = [float(r.find("dict[@name='binds']/float[@name='std-shield']").text) for r in ranks]
        self.assertEqual(values, [.03, .035, .04, .045, .05])
        self.assertEqual(root.find("dict[@name='skill']/dict[@name='binds']/int[@name='std-radius']").text, "120")
        perks = root.find("array[@name='modifier-skills']")
        self.assertEqual(perks[0].find("string[@name='id']").text, "hwp_war_bs_feared_crest")
        self.assertEqual(perks[0].find("dict[@name='skill']/dict/int[@name='std-rally']").text, "1")
        self.assertNotIn("vulnerability_area", ET.tostring(root).decode())

    def test_warlock_perk_values_and_ids(self):
        root = skill("branding/essence_extraction.sval")
        perks = root.find("array[@name='modifier-skills']")
        self.assertEqual(perks[0].find("string[@name='id']").text, "hwp_wlk_ee_essence_empowerment")
        self.assertEqual(perks[1].find("string[@name='id']").text, "hwp_wlk_ee_released_essence")
        guard = [perks[0].find("dict[@name='skill']"), *perks[0].find("array[@name='upgrades']")]
        self.assertEqual([float(r.find("dict/float[@name='ee-guard']").text) for r in guard], [.01, .015, .02])
        stride = [perks[1].find("dict[@name='skill']"), *perks[1].find("array[@name='upgrades']")]
        self.assertEqual([int(r.find("dict/int[@name='ee-stride']").text) for r in stride], [1, 2, 3])
        self.assertIn("HWPSpecsEssenceSupport", ET.tostring(root).decode())
        self.assertNotIn("ee-emp", ET.tostring(root).decode())

    def test_enfeeblement_uses_native_tiers(self):
        root = skill("branding/pyrebrand.sval")
        perk = root.find("array[@name='modifier-skills']")[1]
        ranks = [perk.find("dict[@name='skill']"), *perk.find("array[@name='upgrades']")]
        self.assertEqual([int(r.find("dict/int[@name='pb-weakness']").text) for r in ranks], [1, 2, 3])

    def test_planner_replacements_are_not_claimed_tested(self):
        replacements = {
            "prolif": "Enfeeblement", "mods-us23z4by": "Soul Guard",
            "released-essence": "Soul Stride", "mods-1ubkp58h": "Rallying Standard",
            "mods-f3gfmk7d": "Martyr's Banner",
        }
        for filename, name in replacements.items():
            data = json.loads((ROOT / f"planner/data/mods/{filename}.json").read_text())
            self.assertEqual(data["name"], name)
            self.assertEqual(data["status"], "built")
            self.assertEqual(len(data["levels"]), 3)

    def test_recipient_authority_and_no_duplicate_damage_channels(self):
        text = (SPECS / "scripts/HWP/Specs/Support.as").read_text()
        self.assertIn("if (!IsLocal(recipient)", text)
        self.assertIn("g_rallyC <= 0", text)
        self.assertIn("HWPSpecsRalliedGain", text)
        self.assertIn("HasDamageMul()", text)
        self.assertNotIn("stats.PhysicalDamageMul +=", text)
        self.assertIn("s.m_timerTickC = max", text)
        self.assertIn("support_shield", text)
        buffs = (SPECS / "players/hwp/specs/buffs_specs.sval").read_text()
        self.assertEqual(buffs.count('>HWPSpecsShield<'), 1)
        self.assertIn('>HWPSpecsCrusadeDuration<', buffs)
        self.assertIn('m_scale / max(1.0f, own)', text)

    def test_throw_and_proliferation_safety_contracts(self):
        banner = (SPECS / "scripts/HWP/Specs/Bannerlord.as").read_text()
        self.assertIn("4000, false, source.GetMaxHp()", banner)
        self.assertNotIn("s.m_left /= 2", banner)
        self.assertIn("players.findByRef(carried[i])", banner)
        self.assertIn("StandardPulse(s, true, false)", banner)
        branding = (SPECS / "scripts/HWP/Specs/Branding.as").read_text()
        self.assertIn("g_clawResolving", branding)
        self.assertIn("b.m_left, b.m_full", branding)
        self.assertIn("b.m_visited.findByRef(enemies[i])", branding)
        self.assertIn("g_brands.length() >= MAX_BRANDS", branding)
        self.assertNotIn("BRAND_TIME / 2", branding)


if __name__ == "__main__":
    unittest.main()
