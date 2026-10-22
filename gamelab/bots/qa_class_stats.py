"""Live effective-stat checks of every rank of HoH1 stat passives.

The expected tables are the shipped skill descriptions, interpreted with the
pinned engine's stat combination rules. These measure applied player stats,
not just the raw data binds. Proc, combat and lifecycle checks are separate.
"""
import time

from gamelab.bots.plan_classesa import Checks as ClassChecks


CRIT = [0.05, 0.08, 0.11, 0.14, 0.18]
PHYSICAL = [(4, 6), (8, 12), (12, 18), (16, 24), (20, 30)]
CASES = {
    "sidestep": ("hwp_thief", None, "hwp_thief_sidestep", [("evade", "combine", CRIT)]),
    "vicious_cuts": ("hwp_thief", "hwp_thief_assassin", "hwp_thief_vicious_cuts",
                     [("mhCrit", "combine", CRIT), ("mhCritDmg", "add", [0.2, 0.3, 0.4, 0.5, 0.6])]),
    "quick_hands": ("hwp_thief", "hwp_thief_trickster", "hwp_thief_quick_hands",
                    [("mhSpeed", "multiply", [1.05, 1.1, 1.15, 1.2, 1.25])]),
    "arena_mastery": ("hwp_gladiator", "hwp_gladiator_champion", "hwp_gladiator_arena_mastery",
                      [("armor", "add", [5, 10, 15, 20, 25]), ("health", "add", [20, 40, 60, 80, 100])]),
    "riposte": ("hwp_gladiator", "hwp_gladiator_champion", "hwp_gladiator_riposte",
                [("thorns", "add", [10, 20, 30, 40, 50])]),
    "trident_mastery": ("hwp_gladiator", "hwp_gladiator_retiarius", "hwp_gladiator_trident_mastery",
                        [("mhPhys", "range_add", PHYSICAL)]),
    "zeal": ("hwp_witch_hunter", "hwp_witch_hunter_inquisitor", "hwp_witch_hunter_zeal",
             [("mhCrit", "combine", CRIT), ("spellCrit", "combine", CRIT)]),
    "brand": ("hwp_witch_hunter", "hwp_witch_hunter_pyromancer", "hwp_witch_hunter_brand",
              [("mhFire", "range_add", [(4, 6), (7, 10), (10, 14), (13, 18), (16, 24)])]),
    "silver_bolts": ("hwp_witch_hunter", "hwp_witch_hunter_hunter", "hwp_witch_hunter_silver_bolts",
                     [("mhPhys", "range_add", PHYSICAL)]),
    "tracker": ("hwp_witch_hunter", "hwp_witch_hunter_hunter", "hwp_witch_hunter_tracker",
                [("moveSpeed", "multiply", [1.05, 1.08, 1.11, 1.15, 1.2])]),
}


def expected(baseline, mode, value):
    if mode == "combine":
        return 1 - (1 - baseline) * (1 - value)
    if mode == "multiply":
        return baseline * value
    return baseline + value


class Checks(ClassChecks):
    def case(self, key, index):
        cls, mastery, skill, fields = CASES[key]
        if not self.new_char(cls, f"QAStat{index}"):
            return
        self.hwp("levelup 20", 0.3)
        self.hwp("skillpoints 1000", 0.3)
        if mastery:
            changed = self.gl("subclass", mastery)
            self.flag(key + "_mastery", changed.get("class") == mastery, str(changed))
        baseline = self.gl("benchstats")
        self.notes.append(key + " baseline: " + str(baseline))
        ok_all = True
        rows = []
        for rank in range(1, 6):
            learned = self.gl("skill", skill, 1)
            time.sleep(0.08)
            stats = self.gl("benchstats")
            rank_ok = learned.get("level") == rank
            self.flag(f"{key}_r{rank}_learned", rank_ok, str(learned))
            row = {"rank": rank, "stats": stats, "expected": {}}
            effects_ok = rank_ok
            for field, mode, values in fields:
                actual = stats.get(field)
                base = baseline.get(field)
                value = values[rank - 1]
                if actual is None or base is None:
                    effects_ok = False
                    row["expected"][field] = "BLOCKED: required read-only stat is missing"
                    continue
                if mode == "range_add":
                    low, high = base + value[0], base + value[1]
                    field_ok = low <= actual <= high
                    row["expected"][field] = [low, high]
                else:
                    want = expected(base, mode, value)
                    tolerance = 0.002 if mode == "combine" else 0.02
                    field_ok = abs(actual - want) <= tolerance
                    row["expected"][field] = want
                effects_ok &= field_ok
            self.flag(f"{key}_r{rank}_effect", effects_ok, str(row))
            ok_all &= effects_ok
            rows.append(row)
        self.flag(key + "_all_ranks", ok_all)
        self.out[key + "_observations"] = rows


def run(p, cases="sidestep,vicious_cuts,quick_hands,arena_mastery,riposte,trident_mastery,zeal,brand,silver_bolts,tracker", **_):
    c = Checks(p)
    for index, key in enumerate(cases.split(",")):
        try:
            c.case(key, index)
        except Exception as exc:
            c.flag(key + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
