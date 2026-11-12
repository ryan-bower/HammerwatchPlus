"""Source-derived item comparisons, not a combat simulator or a BiS search.

python -m tools.devarena.item_power --game-root /path/to/gamecode/sdk/hoh2
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from tools.devarena.tooltip_lint import parse_sval_text


def crit_factor(attribute, extra_chance=0.0, extra_damage=0.0, spell=False):
    chance = 0.3 * attribute / (attribute + 100)
    chance = 1 - (1 - chance) * (1 - extra_chance)
    blend = min(1, attribute / 500)
    damage = (1 - blend) * 0.007 * attribute
    damage += blend * (0.17 if spell else 0.15) * math.sqrt(attribute)
    return 1 + chance * (1.5 + damage + extra_damage - 1)


def power_ratio(before, added):
    return (200 + before + added) / (200 + before)


def effective_health(hp, armor):
    taken = 1 / (1 + armor * 0.005) if armor >= 0 else 1 - armor * 0.005
    return hp / taken


def item_share(ratio):
    """Removal-based attribution, not an additive allocation of all power sources."""
    return 1 - 1 / ratio


class Sources:
    def __init__(self, root):
        self.root = root
        self.hashes = {}

    def text(self, path):
        raw = (self.root / path).read_bytes()
        self.hashes[path] = hashlib.sha256(raw).hexdigest()
        return raw.decode("utf-8-sig")

    def records(self, path):
        text = re.sub(r"<loader[^>]*>.*?</loader>", "", self.text(path))
        text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", text)
        return {record["id"]: record for record in parse_sval_text(text)}


def modifiers(record):
    return record.get("modifiers", [record["modifier"]] if "modifier" in record else [])


def field(record, kind, name):
    return next(mod[name] for mod in modifiers(record) if mod["class"] == f"Modifiers::{kind}")


def investigate(root):
    src = Sources(root)
    trinkets = {}
    for quality in ("common", "uncommon", "rare", "epic"):
        trinkets.update(src.records(f"tweak/trinkets/{quality}.sval"))
    rare = src.records("tweak/items/modifiers_equipment_rare.sval")
    epic = src.records("tweak/items/modifiers_equipment_epic.sval")

    # These equations need review if the source implementation changes.
    checks = {
        "scripts/Data/Player.as": ["DamagePowerDivisor = 200.0f", "0.007f", "0.15f", "0.17f", "500.0f", "100.0f", "0.30f"],
        "scripts/Data/Misc.as": ["ArmorApplyEfficiency = 0.005f", "BaseWeaponCritDamage = 1.5f", "BaseSpellCritDamage = 1.5f", "ArmorNegativeMul = 1.0f"],
        "scripts/Behaviors/Armor.as": ["1.0f - a / (1.0f + a)", "1.0f - a * Tweak::ArmorNegativeMul"],
        "scripts/Behaviors/Actors/Modifiers/Modifiers.mas": ['AddModifier("DamageMul", { "PlayerBase@", "Actor@" }, ModifierType::Vec2SumMul)'],
        "scripts/Behaviors/Actors/Modifiers/SkillModifier.as": ["skill.m_modCooldownMul *= lerp(m_cooldownMul, intensity)"],
        "scripts/Behaviors/Actors/Modifiers/StatModifier.as": ["stats.MainHand.AttackSpeed +=", "1.0f - (1.0f - stats.SpellCritChance)"],
        "scripts/Items/Equipment.as": ["/ 9.0f", "case Item::Quality::Rare: return 2", "case Item::Quality::Epic: return 3"],
    }
    for path, fragments in checks.items():
        text = src.text(path)
        for fragment in fragments:
            if fragment not in text:
                raise ValueError(f"Review formula: {fragment!r} missing in {path}")
    for path in (
        "scripts/Behaviors/Actors/Player/PlayerBase.as",
        "scripts/Behaviors/Actors/Player/Player.as",
        "scripts/Behaviors/Actors/Modifiers/Modifiers.as",
        "scripts/Items/EquipmentGenerator.as",
        "scripts/Items/Trinkets.as",
        "players/warrior/class_warrior.sval",
        "players/wizard/class_wizard.sval",
    ):
        src.text(path)

    weapon_packet = ["book_attacks", "girdle_might", "torc_alactiy", "codex_power", "parry_medal"]
    spell_packet = ["book_spells", "pendant_prowess", "focus_crystal", "codex_power", "hourglass"]
    for packet in (weapon_packet, spell_packet):
        assert sorted(trinkets[key]["quality"] for key in packet) == ["common", "epic", "rare", "uncommon", "uncommon"]

    ap_add = field(trinkets["book_attacks"], "DamagePowerAdd", "attack-power") + field(trinkets["codex_power"], "DamagePowerAdd", "attack-power")
    sp_add = field(trinkets["book_spells"], "DamagePowerAdd", "spell-power") + field(trinkets["codex_power"], "DamagePowerAdd", "spell-power")
    attack_bonus = field(trinkets["girdle_might"], "Damage", "attack-mul") - 1
    spell_bonus = field(trinkets["pendant_prowess"], "Damage", "spell-mul") - 1
    attack_speed = field(trinkets["torc_alactiy"], "SpeedAdd", "attack-speed")
    cooldown = field(trinkets["hourglass"], "BaseSkillModifier", "cooldown-mul")
    focus_chance = field(trinkets["focus_crystal"], "CriticalHit", "spell-chance")
    focus_damage = field(trinkets["focus_crystal"], "CritDamage", "spell-crit-dmg")
    attack_affix = field(rare["mod_attack_damage"], "Damage", "attack-mul") - 1
    spell_affix = field(rare["mod_spell_damage"], "Damage", "spell-mul") - 1
    speed_affix = field(rare["mod_attack_speed"], "SpeedAdd", "attack-speed")
    fire_cd = field(epic["mod_epic_speed_fire"], "BaseSkillModifier", "cooldown-mul")
    assert set(rare["mod_spell_damage"]["tags"]) >= {"mods_chest", "mods_hands"}
    assert set(epic["mod_epic_speed_fire"]["tags"]) >= {"mods_hands", "mods_back"}
    assert set(rare["mod_attack_speed"]["tags"]) >= {"mods_head", "mods_back"}

    rows = []
    for ap in (0, 100, 300):
        matched = power_ratio(ap, ap_add) * (1 + attack_bonus) * (1 + attack_speed)
        geared = power_ratio(ap, ap_add) * (1 + attack_bonus + 2 * attack_affix) * (1 + attack_speed + 2 * speed_affix)
        wrong = power_ratio(ap, field(trinkets["codex_power"], "DamagePowerAdd", "attack-power"))
        rows.append(dict(channel="weapon", existing_power=ap, matched=matched, mismatched=wrong, selected_gear_and_trinkets=geared, removal_share=item_share(matched)))
    crit_ratio = crit_factor(60, focus_chance, focus_damage, spell=True) / crit_factor(60, spell=True)
    for sp in (120, 300, 600):
        hit = power_ratio(sp, sp_add) * (1 + spell_bonus) * crit_ratio
        geared = power_ratio(sp, sp_add) * (1 + spell_bonus + 2 * spell_affix) * crit_ratio / (cooldown * fire_cd**2)
        wrong = power_ratio(sp, field(trinkets["codex_power"], "DamagePowerAdd", "spell-power"))
        rows.append(dict(channel="spell", existing_power=sp, matched=hit / cooldown, per_hit=hit, mismatched=wrong, selected_gear_and_trinkets=geared, removal_share=item_share(hit / cooldown)))

    armor = 0
    armor_items = []
    for slot, item_id in (("chest", "chest_str_t3a"), ("head", "head_str_t3a"), ("feet", "feet_str_t3a"), ("hands", "hands_str_3a")):
        item = src.records(f"tweak/items/equipment/equipment_shared_{slot}.sval")[item_id]
        low, high = map(int, field(item, "ArmorAdd", "armor").split())
        added = math.floor(low + (high - low) * 19 / 9 + 0.5)
        req_low, req_high = map(int, item["req-str"].split())
        req = math.floor(req_low + (req_high - req_low) * 19 / 9 + 0.5)
        assert req <= 60
        armor += added
        armor_items.append(dict(id=item_id, item_level=20, quality="common", armor=added, required_strength=req))

    return {
        "evidence": "source review and analytical model; no native game run",
        "assumptions": {"spell_intelligence": 60, "attack_speed_before": 1, "no_other_additive_damage_bonus": True, "spell_cadence": "cooldown-limited, sufficient mana and animation headroom", "attunement": False, "procs": "excluded", "equipment_base_stats": "held fixed for damage comparisons"},
        "packets": {"weapon": weapon_packet, "spell": spell_packet},
        "comparisons": rows,
        "armor": {"items": armor_items, "added_armor": armor, "baseline_hp": 350, "baseline_armor": 132, "ehp_before": effective_health(350, 132), "ehp_after": effective_health(350, 132 + armor), "ratio": effective_health(350, 132 + armor) / effective_health(350, 132)},
        "source_sha256": dict(sorted(src.hashes.items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.game_root), indent=2))


if __name__ == "__main__":
    main()
