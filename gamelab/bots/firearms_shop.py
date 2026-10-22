"""The equipment seller's stock by class (mods/firearms, HWP/Firearms/Shops.as and the
Town/EquipmentSeller.as override): a Paladin is never offered a gun, a Firearms Specialist's
weapon offers are all guns, her stock always holds at least one, and buying the guns out of a
saved stock puts one back on the next open.

The seller is spawned beside the player (`gl spawn`, as a town building's placement would
produce her) and opened with `gl use`; `gl shop` reads each entry's base item slot and its
supported tags as HashString values, so a gun is an entry tagged hwp_firearm (gamelab/hps.py
hashes the name the same way). The Specialist is a fresh level-1 character made with `gl char`,
which reloads the town, so her seller is spawned again.

Sections: paladin_shop (the fixture's Paladin), specialist_shop (char + stock + restock)."""
import time

from gamelab.bots.plan_checks import Checks as Base
from gamelab.hps import hash_string

SELLER = "actors/npcs/town/npc_equipment_seller.unit"
WEAPON_SLOTS = {1, 2, 4}  # Equipment::Slot MainHand, OffHand, TwoHanded
FIREARM = hash_string("hwp_firearm")


def is_gun(entry):
    return FIREARM in set(entry.get("tags") or [])


def is_weapon(entry):
    return entry.get("slot") in WEAPON_SLOTS


class Checks(Base):
    def open_seller(self):
        """A fresh seller 40 px right of the player, every tier open, her shop window up; the
        entries (empty when the window did not open)."""
        r = self.gl("spawn", SELLER, "40", "0")
        if not r.get("ok"):
            self.notes.append(f"seller spawn: {r}")
            return []
        time.sleep(0.5)
        self.gl("shoplevel", "equipment_seller", "3")
        u = self.gl("use", "equipment_seller")
        time.sleep(0.6)
        s = self.gl("shop")
        if not u.get("ok") or not s.get("ok"):
            self.notes.append(f"seller open: use {u.get('ok')} shop {s.get('error', s.get('ok'))}")
            return []
        return s.get("items", [])

    def describe(self, items):
        return ", ".join(f"{e.get('base', '?').split('.')[-2:][0]}/{e.get('slot')}{'*' if is_gun(e) else ''}" for e in items)

    def paladin_shop(self):
        items = self.open_seller()
        guns = [e for e in items if is_gun(e)]
        self.flag("paladin_stock_full", len(items) == 8, f"{len(items)} offers: {self.describe(items)}")
        self.flag("paladin_no_guns", bool(items) and not guns, f"{len(guns)} gun(s)")
        self.g.key("escape")
        time.sleep(0.5)

    def specialist_shop(self):
        r = self.gl("char", "hwp_firearms", "Shopper")
        made = r.get("ok") and self.wait_phase("town", 90)
        self.flag("specialist_made", made, str(r)[:200])
        if not made:
            return
        time.sleep(3)
        items = self.open_seller()
        guns = [e for e in items if is_gun(e)]
        weapons = [e for e in items if is_weapon(e)]
        self.flag("specialist_stock_full", len(items) == 8, f"{len(items)} offers: {self.describe(items)}")
        self.flag("specialist_has_gun", len(guns) >= 1, f"{len(guns)} gun(s) of {len(weapons)} weapon(s)")
        self.flag("specialist_weapons_are_guns", bool(weapons) and all(is_gun(e) for e in weapons),
                  "non-gun weapons: " + self.describe([e for e in weapons if not is_gun(e)]))

        # the saved-stock path: buy every gun, reopen, a gun is back in place of a non-weapon offer
        self.hwp("material gold 300000")
        bought = 0
        for _ in range(len(guns)):
            s = self.gl("shop")
            at = next((i for i, e in enumerate(s.get("items", [])) if is_gun(e)), None)
            if at is None:
                break
            b = self.gl("shop", "buy", str(at))
            bought += 1 if b.get("changed") else 0
            time.sleep(0.4)
        self.g.key("escape")
        time.sleep(0.6)
        self.gl("use", "equipment_seller")
        time.sleep(0.6)
        s = self.gl("shop")
        again = s.get("items", [])
        guns2 = [e for e in again if is_gun(e)]
        self.flag("specialist_restock_keeps_gun", bought >= 1 and len(guns2) >= 1 and len(again) == len(items) - bought,
                  f"bought {bought}, then {len(again)} offers with {len(guns2)} gun(s): {self.describe(again)}")
        self.g.key("escape")
        time.sleep(0.5)


def run(p, sections="paladin_shop,specialist_shop", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
