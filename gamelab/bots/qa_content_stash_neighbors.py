"""Real stash family sorting with ordinary Firearms neighbors.

The built weapons share the hwp_mh prefix but are different weapon families.
Native item/level readbacks guard the fixture before the Sort button is used.
Ordinary hwp_rifle/hwp_autorifle families must retain their existing token1 rule.
"""
from collections import Counter

from gamelab.bots.plan_newa import Checks as Base


BEFORE = ["hwp_rifle_01@16", "hwp_mh_warhammer@36", "hwp_autorifle_01@18",
          "hwp_mh_frostbrand@38", "hwp_rifle_01@20", "hwp_mh_warhammer@40",
          "hwp_autorifle_01@15", "hwp_mh_frostbrand@35"]
EXPECTED = ["hwp_mh_frostbrand@38", "hwp_mh_frostbrand@35",
            "hwp_mh_warhammer@40", "hwp_mh_warhammer@36",
            "hwp_autorifle_01@18", "hwp_autorifle_01@15",
            "hwp_rifle_01@20", "hwp_rifle_01@16"]


class Checks(Base):
    def __init__(self, p):
        super().__init__(p)
        self.rows = []

    def check(self, tag, ok, row):
        self.flag(tag, ok, str(row))
        self.rows.append({"case": tag, "runtime": "PASS" if ok else "FAIL", **row})

    def families(self):
        self.close_windows()
        cleared = self.gl("stashclear", 0)
        replies = self.g.gl_multi([["stashput", 0, item.split("@")[0], "common", item.split("@")[1]]
                                   for item in BEFORE])
        before, name = self.stash_items(0)
        valid = all(r.get("ok") for r in replies) and before == BEFORE
        self.check("custom_family_stash_fixture", valid,
                   {"clear": cleared, "put_replies": replies, "actual_before": before, "expected_before": BEFORE})
        if not valid:
            return
        opened = self.open_stash()
        self.check("custom_family_stash_ui", opened,
                   {"window": self.gl("state").get("window"), "tab": name})
        if not opened:
            return
        press, said = self.press_sort("custom weapon family sort")
        after, _ = self.stash_items(0)
        self.check("custom_weapons_group_by_actual_family", press.get("ok") and after == EXPECTED,
                   {"actual_order": after, "expected_family_then_ilvl_order": EXPECTED,
                    "independent_weapon_types": {"hwp_mh_frostbrand": "attack_swing_longsword",
                                                 "hwp_mh_warhammer": "attack_swing_mace"},
                    "source": ["mods/weapons/tweak/hwp/equipment_weapons_hwp.sval",
                               "mods/firearms/tweak/hwp/equipment_firearms.sval"],
                    "rule": "STR/mainhand custom families precede DEX/twohand guns; Frostbrand/Warhammer and ordinary Autorifle/Rifle remain separate, each with descending ilvl. A generic hwp namespace strip would collapse both guns to01 and fail.",
                    "sort_log": said})
        self.check("custom_family_sort_preserves_all_items", Counter(after or []) == Counter(before),
                   {"before": before, "after": after})
        _, second = self.press_sort("custom weapon family second press")
        after_again, _ = self.stash_items(0)
        self.check("custom_family_second_press_idempotent", after_again == after
                   and any("already in order" in line for line in second),
                   {"after_second_press": after_again, "sort_log": second})
        self.close_windows()


def run(p, **_):
    c = Checks(p)
    try:
        c.families()
    except Exception as exc:
        c.check("custom_family_sort_crashed", False, {"error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
