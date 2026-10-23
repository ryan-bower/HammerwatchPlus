"""Level-curve math of the Tune tab, the same as mods/devarena/scripts/HWP/DevArena/Curve.as.

values[i] is the field at level i+1: the upgrade's own leaf when it sets one, else the base
(PlayerBase.AddPlayerSkill). Growth is the slope of the line through level 1 that fits the
other levels best (least squares with the intercept fixed at v1):
    g = sum((L-1)(v_L - v_1)) / sum((L-1)^2)
Setting a growth puts every unpinned level from 2 up on v1 + g(L-1), rounded half away from
zero for int fields.
"""
from __future__ import annotations


def level_values(base: dict, upgrades: list[dict], path: str):
    """The field at every level, from a skill's "skill" dict and its "upgrades" list."""
    def lookup(d, parts):
        for p in parts:
            if isinstance(d, dict) and p in d:
                d = d[p]
            elif isinstance(d, list) and p.isdigit() and int(p) < len(d):
                d = d[int(p)]
            else:
                return None
        return d
    parts = path.split(".")
    v1 = lookup(base, parts)
    out = [v1]
    for up in upgrades:
        own = lookup(up, parts)
        out.append(v1 if own is None else own)
    return out


def fit_growth(values: list[float]) -> float:
    num = sum(i * (v - values[0]) for i, v in enumerate(values) if i)
    den = sum(i * i for i in range(1, len(values)))
    return 0.0 if den == 0 else num / den


def round_int(f: float) -> int:
    """Curve.as NumText: int(f + 0.5), or int(f - 0.5) below 0 (truncation toward zero)."""
    return int(f - 0.5) if f < 0 else int(f + 0.5)


def num_text(f: float, is_int: bool) -> str:
    """Curve.as NumText: an int, or formatFloat(f, "", 0, 3)."""
    return str(round_int(f)) if is_int else f"{f:.3f}"


def growth_edits(values: list[float], g: float, is_int: bool, pinned=frozenset()):
    """[(level index, text)] for every level 2.. not pinned and not already on the line;
    level index k = upgrades[k-1] = level k+1 (pins are by level, 1-based)."""
    out = []
    for L in range(2, len(values) + 1):
        if L in pinned:
            continue
        want = num_text(values[0] + g * (L - 1), is_int)
        have = str(values[L - 1]) if is_int else f"{float(values[L - 1]):.3f}"
        if have != want:
            out.append((L - 1, want))
    return out


def growth_step(base: float, is_int: bool) -> float:
    """5% of the base, at least 1 for an int field, 0.05 when that is 0."""
    s = abs(base) * 0.05
    if is_int:
        s = max(1.0, float(int(s + 0.5)))
    return 0.05 if s <= 0 else s
