"""Shrapnel ranks: natural Frag hit, timed debuff and independent armor damage.

An armor-only QA dummy isolates the physical defense. Every rifle burst uses
native input and a bounded crit fixture, with HP read before/after the burst.
"""
import time

from gamelab.bots.plan_firearms_more import RESIST
from gamelab.bots.qa_firearms_passives import Checks as Base


ARMOR = "gamelab/qa_firearms_target_dummy_armor.unit"


class Checks(Base):
    def trial(self, d, unit=ARMOR, grenade=True):
        self.ready("hwp_fs_frag", 8)
        self.top_up()
        # Each fixed trial gets its own bounded60s window. A single override
        # around all fifteen trials could expire before the final rank.
        crit_fixture = self.gl("skillcrit", "hwp_attack_rifle", 1)
        dd, dummy = self.tough(d, 90, unit)
        initial = next((u for u in self.gl("near", 500, "target_dummy").get("units", [])
                        if u.get("unit") == dummy), {})
        if grenade:
            self.skill_press("hwp_fs_frag", "fs_frag.sval", dd)
            time.sleep(1)
        commands = [["actorbuffs", 300, "target_dummy"], ["near", 500, "target_dummy"],
                    ["input", 320, 0, 0, dd[0], dd[1], "main"]]
        reads = self.g.gl_multi(commands)
        before = next((u for u in reads[1].get("units", []) if u.get("unit") == dummy), {})
        tags = sorted({tag for actor in reads[0].get("actors", []) for buff in actor.get("buffs", [])
                       for tag in buff.get("tags", [])})
        buffs = [buff for actor in reads[0].get("actors", []) for buff in actor.get("buffs", [])
                 if "armor_break" in buff.get("tags", [])]
        time.sleep(0.65)
        after = next((u for u in self.gl("near", 500, "target_dummy").get("units", [])
                      if u.get("unit") == dummy), {})
        damage = before.get("hpExact", 0) - after.get("hpExact", 0)
        crit_after = self.gl("skillcrit", "hwp_attack_rifle")
        clip = self.clip()
        time.sleep(2.1)
        expired = self.gl("actorbuffs", 300, "target_dummy")
        remains = any("armor_break" in buff.get("tags", []) for actor in expired.get("actors", [])
                      for buff in actor.get("buffs", []))
        return {"fixture": initial, "fixture_unit": unit, "natural_frag": grenade,
                "after_natural_frag": before, "after_natural_rifle": after,
                "crit_fixture": crit_fixture, "crit_after_rifle": crit_after,
                "tags_before_rifle": tags, "armor_break_buffs": buffs, "armor_break_expired": not remains,
                "rifle_damage": damage, "clip_after_rifle": clip,
                "valid": crit_fixture.get("override_active") and crit_after.get("override_active")
                         and crit_after.get("crit_chance") == 1
                         and initial.get("hpMax") == 600 and 0 < before.get("hpExact", 0) <= initial.get("hpExact", 0)
                         and (not grenade or before.get("hpExact", 0) < initial.get("hpExact", 0))
                         and 0 < after.get("hpExact", 0) < before.get("hpExact", 0) and clip == 27}

    def shrapnel(self):
        if not self.prepare("QAFragShrapnel"):
            return
        # Native ApplyArmor rounds each hit to whole HP. A legal tier3/ilvl40
        # common rifle gives the10% first-rank effect useful integer resolution,
        # without damage/attribute setters or random quality affixes.
        equipped = self.gl("equip", "hwp_rifle_03", "common", 40)
        time.sleep(0.9)
        gear = self.gl("bagitems").get("main", {})
        self.check("shrapnel_legal_high_resolution_rifle", equipped.get("ok")
                   and gear.get("id") == "hwp_rifle_03" and gear.get("quality") == 1
                   and gear.get("ilvl") == 40 and self.clip_max() == 30,
                   {"equip_reply": equipped, "actual_main": gear, "purpose": "Resolve native integer armor rounding."})
        if gear.get("id") != "hwp_rifle_03" or gear.get("ilvl") != 40:
            return
        d = self.open_dirs(140)[0]
        fixture = self.gl("skillcrit", "hwp_attack_rifle", 1)
        try:
            unarmored = [self.trial(d, RESIST, False) for _ in range(3)]
            native_per_hit = sum(x["rifle_damage"] for x in unarmored) / 9
            raw = int(native_per_hit + 0.5)
            self.check("shrapnel_native_unarmored_physical_control", all(x["valid"] for x in unarmored)
                       and raw > 0 and abs(raw - native_per_hit) < 0.01
                       and all(abs(x["rifle_damage"] - 3 * raw) < 0.1 for x in unarmored),
                       {"fixed_controls": unarmored, "measured_native_physical_damage_per_hit": native_per_hit,
                        "note": "The existing resist dummy has armor0; Scavenger is unlearned, so elemental resistance cannot affect these common-rifle physical rounds."})
            control = [self.trial(d) for _ in range(3)]
            baseline = sum(x["rifle_damage"] for x in control)
            expected_control = 9 * int(raw / 4.75 + 0.5)
            self.check("frag_shrapnel_armor_control", fixture.get("override_active") and baseline > 0
                       and abs(baseline - expected_control) < 0.1
                       and all(x["valid"] and "armor_break" not in x["tags_before_rifle"] for x in control),
                       {"fixed_controls": control, "rifle_damage_total": baseline,
                        "expected_integer_armor_damage_total": expected_control, "crit_fixture": fixture})
            for rank, armor_mul in enumerate((0.9, 0.8, 0.7), 1):
                ok, got = self.orb("hwp_fs_frag_shrapnel", 1)
                trials = [self.trial(d) for _ in range(3)]
                damage = sum(x["rifle_damage"] for x in trials)
                ratio = damage / max(0.001, baseline)
                # The common rifle penetrates25% armor: ArmorApplyEfficiency .005.
                expected = 4.75 / (1 + 3.75 * armor_mul)
                expected_integer_damage = 9 * int(raw / (1 + 3.75 * armor_mul) + 0.5)
                self.check(f"frag_shrapnel_rank_{rank}_real_armor_reduction", ok and got == rank
                           and all(x["valid"] and "armor_break" in x["tags_before_rifle"]
                                   and x["armor_break_expired"] for x in trials)
                           and expected_integer_damage > expected_control
                           and abs(damage - expected_integer_damage) < 0.1,
                           {"orb": "hwp_fs_frag_shrapnel", "rank": rank, "expected_armor_multiplier": armor_mul,
                            "expected_damage_ratio_at1000armor": expected, "actual_damage_ratio": ratio,
                            "measured_native_pre_armor_damage_per_hit": native_per_hit,
                            "expected_actual_integer_damage_total": expected_integer_damage,
                            "integer_oracle_source": "gamecode/sdk/hoh2/scripts/Behaviors/Armor.as:11 ApplyArmor/damage_round",
                            "fixed_trials": trials, "control_rifle_damage_total": baseline,
                            "actual_rifle_damage_total": damage})
        finally:
            restored = self.gl("skillcrit", "hwp_attack_rifle", "restore")
            self.check("shrapnel_crit_fixture_restored", not restored.get("override_active"), restored)
        self.clear_dummies()
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.shrapnel()
    except Exception as exc:
        c.check("frag_shrapnel_crashed", False, {"error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
