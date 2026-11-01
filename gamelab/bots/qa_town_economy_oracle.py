"""Independent bounded town-economy expectations; no runtime imports or mutations."""
import math
import struct
import json
import re


def assess(flags, required):
    required = tuple(required)
    missing = sorted(set(required) - set(flags))
    failed = sorted(k for k, value in flags.items() if isinstance(value, bool) and not value)
    return dict(ok=bool(required) and not missing and not failed
                and all(flags[k] is True for k in required),
                missing_required=missing, failed_flags=failed)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bonus_from_inputs(inputs):
    """Read raw modifier inputs, not production Bonus/Payout or rounded status text."""
    if inputs.get("ok") is not True:
        raise ValueError("economyinputs observer refused")
    names = ("luck", "goldMul", "goldMulMul")
    if any(type(inputs.get(name)) not in (int, float) for name in names):
        raise ValueError("missing or nonnumeric raw economy input")
    values = [float(inputs[name]) for name in names]
    if not all(math.isfinite(x) for x in values):
        raise ValueError("nonfinite economy modifier")
    luck, gold_a, gold_b = values
    # The engine stores these inputs and intermediate stat arithmetic as float32.
    luck_factor = max(0.0, f32(1.0 + f32(luck / 100.0)))
    luck_bonus = max(0.0, f32(luck_factor - 1.0))
    gold_bonus = max(0.0, f32(f32(gold_a * gold_b) - 1.0))
    return f32(luck_bonus + gold_bonus)


def same_inputs(a, b):
    return (a.get("ok") is True and b.get("ok") is True
            and all(a.get(key) == b.get(key) for key in ("luck", "goldMul", "goldMulMul")))


def credit(stakes, result, inputs):
    """Fixed independent 0/17 controls, with source-authored odds and integer truncation."""
    bets = {"s:17": ({17}, 35), "c:13": ({13, 14, 16, 17}, 8),
            "odd": (set(range(1, 37, 2)), 1),
            "red": ({1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}, 1),
            "s:0": ({0}, 35), "f4": ({0, 1, 2, 3}, 8),
            "even": (set(range(2, 37, 2)), 1)}
    bonus = bonus_from_inputs(inputs)
    if result not in (0, 17):
        raise ValueError("this bounded oracle supports only results0 and17")
    total = 0
    for key, stake in stakes.items():
        if type(stake) is not int or stake <= 0 or key not in bets:
            raise ValueError("invalid oracle stake")
        numbers, odds = bets[key]
        if result in numbers:
            total += min(2_000_000_000, int(stake + stake * odds * (1.0 + bonus)))
    if total > 2_000_000_000:
        raise ValueError("aggregate overflow policy is outside this ordinary ledger oracle")
    return total


def ledger(before, after_debit, after_result, stakes, expected_credit):
    return (before - after_debit == sum(stakes.values())
            and after_result - after_debit == expected_credit)


def equipment_identity(reply, expected_base_id="mainhand_mace_01"):
    """Accept only the complete module-owned typed transport, never rounded inspect."""
    if (reply.get("ok") is not True or reply.get("schema") != "gamelab.itemidentity.v1"
            or reply.get("complete") is not True or reply.get("truncated") is not False
            or reply.get("slot") != "mainhand" or reply.get("base_id") != expected_base_id):
        raise ValueError("exact typed equipment transport refused or incomplete")
    counted, deepest = 0, 0

    def hex_bytes(value):
        if (type(value) is not str or len(value) > 2048 or len(value) % 2
                or re.fullmatch(r"[0-9a-f]*", value) is None):
            raise ValueError("invalid exact string byte encoding")
        return value

    def integer(value, bits):
        if type(value) is not str or re.fullmatch(r"-?(0|[1-9][0-9]*)", value) is None:
            raise ValueError("invalid typed integer")
        number = int(value)
        if not -(1 << (bits - 1)) <= number < (1 << (bits - 1)) or str(number) != value:
            raise ValueError("typed integer out of range or noncanonical")
        return value

    def floating(value, single):
        decimals = 8 if single else 16
        if type(value) is not str or re.fullmatch(r"-?[0-9]\.\d{" + str(decimals) + r"}e[+-]\d{2,3}", value) is None:
            raise ValueError("float lacks roundtrip scientific precision")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite typed float")
        try:
            binary = struct.pack("<f" if single else "<d", number)
            restored = struct.unpack("<f" if single else "<d", binary)[0]
        except (OverflowError, struct.error) as exc:
            raise ValueError("typed float outside its native range") from exc
        if format(restored, "." + str(decimals) + "e") != value:
            raise ValueError("typed float is not canonical native roundtrip text")
        return binary.hex()  # Preserves adjacent values and signed zero.

    def visit(node, depth):
        nonlocal counted, deepest
        counted += 1
        deepest = max(deepest, depth)
        if counted > 512 or depth > 16 or not isinstance(node, dict) or set(node) != {"t", "v"}:
            raise ValueError("typed item node/depth contract refused")
        tag, value = node["t"], node["v"]
        if tag == "Null" and value is None:
            return [tag, None]
        if tag == "Boolean" and type(value) is bool:
            return [tag, value]
        if tag in ("Integer", "Long"):
            return [tag, integer(value, 32 if tag == "Integer" else 64)]
        if tag in ("Float", "Double"):
            return [tag, floating(value, tag == "Float")]
        if tag == "String":
            return [tag, hex_bytes(value)]
        if tag in ("Vector2", "Vector3", "Vector4", "IVector2", "IVector3", "IVector4"):
            if not isinstance(value, list) or len(value) != int(tag[-1]):
                raise ValueError("invalid typed vector dimension")
            return [tag, [integer(x, 32) if tag.startswith("I") else floating(x, True) for x in value]]
        if tag in ("Array", "Dictionary") and isinstance(value, list) and len(value) <= 128:
            if tag == "Array":
                return [tag, [visit(child, depth + 1) for child in value]]
            pairs, keys = [], set()
            for pair in value:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("invalid typed dictionary entry")
                key = hex_bytes(pair[0])
                if key in keys:
                    raise ValueError("duplicate typed dictionary key")
                keys.add(key)
                pairs.append([key, visit(pair[1], depth + 1)])
            return [tag, sorted(pairs, key=lambda pair: pair[0])]
        raise ValueError("unsupported/malformed typed item node")

    typed = reply.get("typed")
    if not isinstance(typed, dict) or typed.get("t") not in ("Array", "Dictionary") or not typed.get("v"):
        raise ValueError("missing serialized item container")
    canonical = visit(typed, 0)
    if len(json.dumps(typed, separators=(",", ":"), allow_nan=False)) > 11000:
        raise ValueError("typed item text exceeds transport cap")
    if (type(reply.get("nodes")) is not int or reply["nodes"] != counted
            or type(reply.get("depth")) is not int or reply["depth"] != deepest):
        raise ValueError("recursive item completeness metadata disagrees")
    return json.dumps(canonical, separators=(",", ":"), allow_nan=False)
