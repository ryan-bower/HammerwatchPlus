"""The six-level tavern (mods/tavern: tweak/town/buildings/tavern.sval with levels 4-6 on the
third's building, Missions/MissionFoods.as with a list of foods): the picker's slot counts per
level (food 1, 1, 1, 1, 2, 3; drinks 1, 2, 3, 4, 4, 5), a full level 6 pick (3 foods, 5
drinks; a 4th food drops the oldest), the picks back after the loadout reopens (the save's
"foods" array), and a started run holding 3 foods and 5 drinks as mission buffs.

Sections: tavern."""
import re
import time

from gamelab.bots.plan_runs import Checks as Base

FOODS = ("tavern_simple_broth", "tavern_meal_hearty", "tavern_meal_elemental_breakfast", "tavern_meal_beasts",
         "tavern_meal_foragers_feast", "tavern_meal_undead", "tavern_pancakes")
DRINKS = ("tavern_drink_hair_of_the_goblin", "tavern_drink_the_impetuous_apprentice", "tavern_drink_slow_and_steady",
          "tavern_drink_saw_dust", "tavern_drink_crooked_back", "tavern_drink_prospectors_pride")
# tavern level -> (food slots, drink slots)
SLOTS = {1: (1, 1), 4: (1, 4), 5: (2, 4), 6: (3, 5)}
SLOT_TEXT = re.compile(r"(\d+)/(\d+)")


class Checks(Base):
    def wtext(self, wid):
        return (self.gl("wtext", wid).get("texts") or {}).get(wid, "")

    def slots(self, wid):
        m = SLOT_TEXT.search(self.wtext(wid))
        return (int(m.group(1)), int(m.group(2))) if m else None

    def open_picker(self):
        """The run-start loadout, then its tavern row's picker (SelectFoodLoadout "tavern open")."""
        self.g.console("mission_start dark_citadel")
        time.sleep(2.5)
        if "MissionLoadout" not in self.window():
            return False
        self.gl("func", "tavern", "open")
        time.sleep(0.8)
        return "SelectFoodSelector" in self.window()

    def close_all(self):
        for _ in range(3):
            if not self.window():
                return
            self.g.key("escape")
            time.sleep(0.6)

    def level(self):
        return (self.gl("buildings").get("buildings") or {}).get("tavern", -1) + 1

    def tavern(self):
        town = self.new_char("paladin", "LabTavern")
        self.flag("tv_town", town, "fresh character in town" if town else "no fresh character in town")
        if not town:
            return
        # the loadout's tavern row needs a guild hall (tweak/town/loadouts.sval conditionals): without
        # it MissionLoadoutMenu never builds the row and the picker's Apply has no icons to update
        self.gl("build", "guild_hall")
        b = self.gl("build", "tavern")
        self.g.console("cht_add_all_blueprints")
        self.set_gold(100000)
        time.sleep(0.5)
        self.flag("tv_built", self.level() == 1, f"build {b.get('ok')} {b.get('error', '')}; level {self.level()}")

        # 1. the slot counts per level: the picker's "Food n/N" and "Drinks n/N"
        seen = {}
        for lvl in (1, 4, 5, 6):
            have = self.level()
            if lvl > have:
                r = self.gl("buildup", "tavern", lvl - have)
                time.sleep(3)  # the town reloads
                self.notes.append(f"buildup to {lvl}: {str(r)[:160]}")
            opened = self.open_picker()
            food, drink = self.slots("foods"), self.slots("drinks")
            seen[lvl] = (food[1] if food else None, drink[1] if drink else None)
            self.notes.append(f"level {self.level()}: picker {opened}, food {food}, drinks {drink}")
            if lvl == 6:
                break  # the picker stays open for the picks
            self.close_all()
        self.flag("tv_levels", self.level() == 6, f"tavern level {self.level()}")
        self.flag("tv_slots", seen == SLOTS, f"seen {seen}, want {SLOTS}")
        upg = self.gl("sval", "tweak/town/buildings/tavern.sval")
        self.flag("tv_sval_six", upg.get("ok") and upg.get("chunk", "").count("tavern_tier_3.pfb") == 4,
                  f"{str(upg)[:200]}")

        # 2. a full level 6 pick: 4 foods (the 4th drops the oldest), 6 drinks (the 6th too);
        # the first four the picker offers (a fresh town has no broth: run 20261026-141417)
        foods = []
        for f in FOODS:
            if len(foods) < 4 and self.gl("press", f).get("ok"):
                foods.append(f)
                time.sleep(0.2)
        self.notes.append(f"foods picked {foods}")
        for d in DRINKS:
            self.gl("press", d)
            time.sleep(0.2)
        food, drink = self.slots("foods"), self.slots("drinks")
        cur = self.gl("wchildren", "current", 1).get("nodes", [])
        self.flag("tv_full_pick", food == (3, 3) and drink == (5, 5) and len(cur) == 8,
                  f"food {food}, drinks {drink}, {len(cur)} icon(s) under current")
        self.g.shot("tavern-picker")
        self.gl("func", "exit", "yes")
        time.sleep(0.6)
        self.g.shot("tavern-loadout")

        # 3. the picks come back when the loadout reopens (Save: "food" + "foods")
        self.close_all()
        reopened = self.open_picker()
        food, drink = self.slots("foods"), self.slots("drinks")
        self.flag("tv_picks_kept", reopened and food == (3, 3) and drink == (5, 5),
                  f"picker {reopened}, food {food}, drinks {drink}")
        self.gl("func", "exit", "yes")
        time.sleep(0.6)

        # 4. Start: the run holds the three foods and five drinks
        self.gl("func", "play")
        ok = self.wait_phase("mission", 120)
        time.sleep(2)
        run = self.gl("run")
        buffs = [b.get("id", "") for b in (run.get("missionBuffs") or run.get("buffs") or [])]
        got_foods = [b for b in buffs if b.startswith("tavern_") and b not in DRINKS]
        got_drinks = [b for b in buffs if b in DRINKS]
        self.flag("tv_run_buffs", ok and len(foods) == 4 and sorted(got_foods) == sorted(foods[1:])
                  and len(got_drinks) == 5 and DRINKS[0] not in got_drinks,
                  f"phase ok {ok}; picked {foods}; foods {got_foods}; drinks {got_drinks}")


def run(p, sections="tavern", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
