"""Gold pickups by amount (mods/hwplib items/materials/gold.unit, scenario fix-gold-sprites):

- 15 drops (gl drop: Material::DropMaterial, the call loot makes) at each tier's first amount,
  in a 5 x 3 grid below the player: bronze, silver and gold rows, coin then piles 1-4 from the
  left; each shows its scene (`near` reports the unit's current scene and amount). Screenshot.
- the amount just under each threshold takes the tier below (4 bronze_1, 24 bronze_5, 199
  silver_5), and amounts past the last threshold stay on gold_5.
- picking one up still pays: walking onto the 300 pile raises the character's gold by at least
  300 (gain modifiers only add).
"""
import time

from gamelab.bots.plan_checks import Checks as Base

TIERS = [(1, "bronze_1"), (5, "bronze_2"), (10, "bronze_3"), (15, "bronze_4"), (20, "bronze_5"),
         (25, "silver_1"), (50, "silver_2"), (75, "silver_3"), (100, "silver_4"), (150, "silver_5"),
         (200, "gold_1"), (250, "gold_2"), (300, "gold_3"), (350, "gold_4"), (400, "gold_5")]
EDGES = [(4, "bronze_1"), (9, "bronze_2"), (24, "bronze_5"), (49, "silver_1"), (149, "silver_4"),
         (199, "silver_5"), (399, "gold_4"), (1000, "gold_5"), (5000, "gold_5")]


class Checks(Base):
    def golds(self):
        return {u["unit"]: u for u in self.gl("near", 600, "materials/gold").get("units") or []}

    def drop_all(self, amounts, x0, y0, cols):
        ids = []
        for i, n in enumerate(amounts):
            r = self.gl("drop", "gold", n, x0 + 24 * (i % cols), y0 + 21 * (i // cols))
            ids.append(r.get("unit"))
        time.sleep(0.8)
        seen = self.golds()
        return [(n, seen.get(u, {}).get("scene"), seen.get(u, {}).get("amount")) for n, u in zip(amounts, ids)]

    def sec_grid(self):
        r = self.gl("mission", "bandit_keep", 0)
        if not (r.get("ok") and self.wait_phase("mission")):
            self.flag("mission", False)
            return
        time.sleep(3)
        self.gl("cull")
        got = self.drop_all([n for n, _ in TIERS], -48, 34, 5)
        bad = [(n, s, want) for (n, s, a), (_, want) in zip(got, TIERS) if s != want or a != n]
        self.flag("tier_scenes", not bad, f"wrong: {bad}; got {got}")
        for i in range(3):  # the glints pulse over 2.5 s; one of these catches them low
            time.sleep(0.8)
            self.g.shot(f"gold by amount {i + 1} - rows bronze silver gold - coin then piles")
        self.grid = got

    def sec_edges(self):
        got = self.drop_all([n for n, _ in EDGES], -96, -70, 9)
        bad = [(n, s, want) for (n, s, a), (_, want) in zip(got, EDGES) if s != want]
        self.flag("edge_scenes", not bad, f"wrong: {bad}; got {got}")

    def sec_pickup(self):
        before = self.gl("inv").get("materials", {}).get("gold", 0)
        pl = self.gl("state").get("player", {})
        x, y = pl.get("x", 0.0), pl.get("y", 0.0)
        # the 300 pile: third column (-48 + 48), bottom row (34 + 42)
        self.gl("teleport", x, y + 76)
        time.sleep(1.5)
        after = self.gl("inv").get("materials", {}).get("gold", 0)
        self.flag("pickup_pays", after - before >= 300, f"gold {before} -> {after}")


SECTIONS = ["grid", "edges", "pickup"]


def run(p, sections="all"):
    c = Checks(p)
    names = SECTIONS if sections == "all" else [s for s in sections.split(",") if s]
    for name in names:
        try:
            getattr(c, "sec_" + name)()
        except Exception as exc:  # a crashed section is a failed section, not a crashed run
            c.flag(name + "_crashed", False, repr(exc))
    c.out["ok"] = bool(c.out) and all(v for v in c.out.values() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
