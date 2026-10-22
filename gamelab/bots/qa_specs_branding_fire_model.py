"""Pinned native float32 Pyrebrand Fire model; no target HP is fitted."""
from gamelab.bots.qa_firearms_damage_model import f32, native_single, damage_round


def expected_fire(combust_per, essence, native):
    """Damage100*intensity -> outgoing Spell factors -> zero-res Fire + enemy pool."""
    owner, skill, target = (native.get(k, {}) for k in ("owner", "skill", "target"))
    if (native.get("ok") is not True or native.get("precision") != 9 or native.get("sampledCritRng") is not False
            or native.get("ngp") != 0 or owner.get("class") != "hwp_warlock_branding"
            or skill.get("id") != "hwp_wlk_pyrebrand" or skill.get("type") != 4 or skill.get("matches") != 1
            or skill.get("critChance") != 0 or owner.get("spellCritChance") != 0 or target.get("receiveCritChance") != 0
            or target.get("fireRes") != 0 or target.get("resistanceMul") != 1 or target.get("damageTakenMul") != 1
            or target.get("afflictionDamageTakenMul") != 1 or target.get("hpMax") != 500 or target.get("hpFraction") != 1
            or any(target.get(k) != 0 for k in ("firePool", "icePool", "poisonPool", "lightningPool", "physicalPool"))
            or type(essence) is not int or not 0 <= essence <= 10 or combust_per not in (.02, .03, .04)):
        return {"valid": False, "errors": ["source/identity/crit/fresh zero-res target contract"]}
    try:
        amount = f32(f32(40) * f32(f32(1) + f32(f32(combust_per) * f32(essence))))
        intensity = f32(amount / f32(100))
        raw = damage_round(f32(f32(100) * intensity))
        mul = f32(native_single(owner["buffDamageMul"]) * native_single(owner["damageMul"]))
        divisor = native_single(owner["damagePowerDivisor"])
        power = owner["spellPower"]
        if type(power) not in (int, float) or power < 0 or power != int(power):
            raise ValueError("actual integer spell power required")
        mul = f32(mul * f32(f32(divisor + f32(power)) / divisor))
        mul = f32(mul * native_single(skill["damageMul"]))
        mul = f32(mul * native_single(owner["modifierSpell"]))
        fire = native_single(owner["fireMul"])
        direct = damage_round(f32(f32(f32(raw) * mul) * fire))
        # Composite754-759 first truncates its target affliction multiplier;
        # ActorBuffList543 then truncates enemy FireDmgScale0.33. Native ticks
        # only consume that fixed pool, with the required target factor1.
        affliction = int(f32(native_single(target["afflictionFireMul"]) * f32(direct)))
        pool = int(f32(f32(affliction) * f32(.33)))
        left, ticks = pool, 0
        while left > 0:
            left -= max(1, int(f32(f32(left) * f32(.5))))
            ticks += 1
        return {"valid": True, "errors": [], "amount": amount, "radius": amount,
                "raw": raw, "fire": fire, "multiplier": mul, "direct": direct,
                "pool": pool, "ticks": ticks, "hp_loss": direct + pool}
    except (KeyError, ValueError, OverflowError) as exc:
        return {"valid": False, "errors": [str(exc)]}


def empowerment_fields(zero, high, coefficient, essence):
    try:
        a, b = zero["owner"], high["owner"]
        expected = f32(native_single(a["fireMul"]) + f32(f32(native_single(b["physicalMul"]) * f32(coefficient)) * f32(essence)))
        return (zero.get("ok") is True and high.get("ok") is True
                and a["unit"] == b["unit"] and a["class"] == b["class"] == "hwp_warlock_branding"
                and zero["target"]["unit"] == high["target"]["unit"]
                and native_single(b["fireMul"]) == expected)
    except (KeyError, ValueError, OverflowError):
        return False
