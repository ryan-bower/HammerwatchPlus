"""Pinned native float32 direct spell model; no observed target HP is fitted.

This first model deliberately requires a clean zero-defense target and a
noncritical ordinary Spell. Element pools/penetration and native PlayerDamage
hand-component truncation are separate future models, never silently inferred.
"""
import math
import struct


def f32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def damage_round(value):
    value = f32(value)
    if value == 0:
        return 0
    answer = int(f32(value + (.5 if value > 0 else -.5)))
    return (1 if value > 0 else -1) if abs(value) < 1 else answer


def native_single(value):
    """Recover only a UNIQUE native float32 from a nine-decimal serialization."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("missing/nonfinite native float")
    center = f32(value)
    if not 0 < center < 1e7:
        raise ValueError("positive bounded model factor required")
    bits = struct.unpack("<I", struct.pack("<f", center))[0]
    candidates = [struct.unpack("<f", struct.pack("<I", key))[0]
                  for key in (bits - 1, bits, bits + 1)]
    retained = [candidate for candidate in candidates if abs(candidate - value) <= .500001e-9]
    if len(retained) != 1:
        raise ValueError("nine-decimal native factor does not identify one float32")
    return retained[0]


def physical_spell(base_damage, native, skill_id, *, intensity=1, summon=False):
    """Forward Damage.FillDamage -> PlayerBase -> clean enemy armor0 receive.

    PlayerClass.as enum Spell=4. Every multiplication/division/addition follows
    the native float32 expression order; Armor.as26 rounds away from zero with
    its signed one-HP floor. No outcome HP or fitted multiplier is an input.
    """
    errors, chain = [], []
    if (type(base_damage) is not int or not 0 < base_damage <= 100000
            or native.get("ok") is not True or native.get("precision") != 9
            or native.get("ngp") != 0 or native.get("sampledCritRng") is not False):
        return {"valid": False, "errors": ["source damage or native query contract invalid"]}
    owner, skill, target = (native.get(key, {}) for key in ("owner", "skill", "target"))
    if (skill.get("id") != skill_id or skill.get("matches") != 1 or skill.get("type") != 4
            or skill.get("critChance") != 0 or owner.get("spellCritChance") != 0
            or target.get("receiveCritChance") != 0):
        errors.append("not the exact unique controlled noncritical native Spell")
    if (any(target.get(key) != 0 for key in ("armor", "firePool", "icePool", "poisonPool", "lightningPool", "physicalPool"))
            or target.get("armorMul") != 1 or target.get("damageTakenMul") != 1
            or target.get("afflictionDamageTakenMul") != 1):
        errors.append("clean zero-armor/pool/buff target required")
    if errors:
        return {"valid": False, "errors": errors}
    try:
        buff, global_mul = (native_single(owner[k]) for k in ("buffDamageMul", "damageMul"))
        multiplier = f32(buff * global_mul)
        chain.append(["buff*global", multiplier])
        if summon:
            multiplier = f32(multiplier * native_single(owner["summonDamageMul"]))
            chain.append(["summon", multiplier])
        divisor = native_single(owner["damagePowerDivisor"])
        power = owner["spellPower"]
        if type(power) not in (int, float) or not math.isfinite(power) or power < 0 or power != int(power):
            raise ValueError("current tested fixtures require actual nonnegative integer SpellPower")
        power_scale = f32(f32(divisor + f32(power)) / divisor)
        multiplier = f32(multiplier * power_scale)
        chain.append(["spellPower", multiplier])
        multiplier = f32(multiplier * native_single(skill["damageMul"]))
        chain.append(["skill", multiplier])
        multiplier = f32(multiplier * native_single(owner["modifierSpell"]))
        chain.append(["modifierSpell", multiplier])
        raw = damage_round(f32(f32(base_damage) * native_single(intensity)))
        scaled = f32(f32(raw * multiplier) * native_single(owner["physicalMul"]))
        outgoing = damage_round(scaled)
        # At armor0 ApplyArmor returns the same rounded integer; clean target
        # DamageTakenMul1 leaves the outer receive round unchanged.
        return {"valid": True, "errors": [], "source_base": base_damage,
                "raw_after_intensity": raw, "native_factor_chain": chain,
                "outgoing_before_round": scaled, "expected_hp_loss": outgoing,
                "scope": "Exact direct physical Spell on clean armor0 target; native crit/pool/proc controls remain independent."}
    except (KeyError, ValueError, OverflowError) as exc:
        return {"valid": False, "errors": [str(exc)]}
