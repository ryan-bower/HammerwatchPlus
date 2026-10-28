"""HoH1's two OpenInterface windows in the Forsaken Tower (mods/campaign/scripts/HWP/Campaign/
HoH1/Interfaces.as), on HoH1's own .gui files. HoH2 has neither class: its OpenInterface hit a
null pointer on them.

- The gambler: HoH1's gambler room (prefabs/special/special_item_gambler.pfb) fabricated beside
  the player on floor 1, the player given trinkets (itc-host fill: 2 common, 2 uncommon, 1 rare,
  1 cursed), the room's UseTrigger used. The window opens (HoH1ItemDealer) listing every trinket
  but the cursed one (HoH1 had no cursed items), the dice off until something is ticked. Three
  ticked: the chances read HoH1's tweak/itemdealer.sval row for the points bet, the dice on;
  rolled: the three are gone, one new trinket is in, shown as the final item, the list and dice
  off. Closed and opened again: the same final item, still off (one gamble per gambler). Closed:
  no window left.
- The end: the dragon's floor started the level's way (tower_bosses RECIPES), Thundersnow
  killed; HoH1's UnitDestroyedTrigger opens the end window (HoH1EndOfGame) with HoH1's story,
  and its CONTINUE ends the mission as won: the game goes back to town.
"""
import time

from gamelab.bots.plan_checks import Checks as Base
from gamelab.bots.tower_bosses import RECIPES, TowerBoss, level_name
from gamelab.bots.tower_floors import MISSION

GAMBLER = "hoh1/prefabs/special/special_item_gambler.pfb"
GAMBLER_AT = (0, 128)            # from the player
GAMBLER_USE = (-64, -32)         # the room's UseTrigger, from the prefab's origin (its area is on the origin)
FILL = (2, 2, 1, 0, 1)           # common, uncommon, rare, epic, cursed
BET = 3
BETS = ("common", "uncommon", "rare", "epic", "legendary")
POINTS = {"common": 1, "uncommon": 3, "rare": 7, "epic": 12, "legendary": 24}
END_TEXT = "You managed to climb to the top of the Forsaken Tower"


def quality(t):
    return t.rsplit(":", 1)[-1]


class Checks(TowerBoss, Base):
    def host(self, *a):
        return self.gl("itc-host", *a)

    def wait_host(self, cls, timeout=15):
        end = time.time() + timeout
        r = {}
        while time.time() < end:
            r = self.host()
            if r.get("top") == cls:
                return r
            time.sleep(0.5)
        return r

    def gambler(self):
        rep = {}
        mark = len(self.g.read_log())
        r = self.gl("mission", MISSION, 0, timeout=30)
        ok = bool(r.get("ok")) and self.wait_phase("mission", 240)
        self.flag("dealer_floor", ok, str(r))
        if not ok:
            return
        time.sleep(4)
        self.god_on()
        fill = self.host("fill", *FILL)
        before = fill.get("trinkets") or []
        rep["before"] = before
        betable = [t for t in before if quality(t) in BETS]
        p = self.gl("state").get("player") or {}
        px, py = float(p.get("x", 0)), float(p.get("y", 0))
        ox, oy = px + GAMBLER_AT[0], py + GAMBLER_AT[1]
        rep["prefab"] = self.gl("prefab", GAMBLER, *GAMBLER_AT)
        time.sleep(1)
        ux, uy = ox + GAMBLER_USE[0], oy + GAMBLER_USE[1]
        use = [s for s in self.gl("ws", "UseTrigger").get("scripts") or []
               if abs(float(s.get("x", 0)) - ux) < 2 and abs(float(s.get("y", 0)) - uy) < 2]
        self.flag("dealer_spawned", bool(use), f"prefab {rep['prefab']}, UseTrigger at {(ux, uy)}: {use}")
        if not use:
            return
        sid = use[0]["id"]
        self.gl("teleport", ox, oy)
        time.sleep(0.5)
        rep["use"] = self.gl("itc-use", f"#{sid}", 3000)
        w = self.wait_host("HoH1ItemDealer")
        rep["open"] = w
        self.g.shot("dealer-open")
        self.flag("dealer_opens", w.get("top") == "HoH1ItemDealer" and "UNSCRUPULOUS GAMBLER" in (w.get("texts") or []),
                  f"use {rep['use']}, window {w}")
        self.flag("dealer_lists_trinkets", w.get("items") == len(betable) and w.get("itemsEnabled") == len(betable)
                  and not w.get("gambleEnabled"),
                  f"{w.get('items')} listed ({w.get('itemsEnabled')} enabled) of {before}, want {len(betable)} (no cursed); "
                  f"dice on {w.get('gambleEnabled')}")
        # HoH1 lists the record's items in order; ours lists the trinkets in inventory order
        bet = betable[:BET]
        points = sum(POINTS[quality(t)] for t in bet)
        c = self.host("check", BET)
        rep["checked"] = c
        self.g.shot("dealer-checked")
        chances = c.get("chances") or []
        self.flag("dealer_chances", c.get("itemsChecked") == BET and c.get("gambleEnabled") and len(chances) == 5
                  and any(x != "0%" for x in chances),
                  f"{c.get('itemsChecked')} ticked, {points} points, chances {chances}, dice on {c.get('gambleEnabled')}, "
                  f"tip {c.get('gambleTip')!r}")
        g = self.host("func", "gamble")
        rep["gambled"] = g
        self.g.shot("dealer-gambled")
        after = g.get("trinkets") or []
        new = [t for t in after if t not in before]
        gone = [t for t in before if t not in after]
        self.flag("dealer_gamble", len(after) == len(before) - BET + 1 and g.get("final")
                  and g.get("itemsEnabled") == 0 and not g.get("gambleEnabled"),
                  f"before {before}, after {after} (new {new}, gone {gone}), final {g.get('final')!r}, "
                  f"list on {g.get('itemsEnabled')}, dice on {g.get('gambleEnabled')}")
        self.host("func", "close")
        time.sleep(0.5)
        shut = self.host()
        self.gl("teleport", ox, oy + 48)
        time.sleep(0.5)
        self.gl("teleport", ox, oy)
        time.sleep(0.5)
        rep["reuse"] = self.gl("itc-use", f"#{sid}", 3000)
        again = self.wait_host("HoH1ItemDealer", 6)
        rep["again"] = again
        # (GameLab's own PointerHost is always there)
        self.flag("dealer_once", "HoH1ItemDealer" not in (shut.get("hosts") or []) and again.get("final") == g.get("final")
                  and not again.get("gambleEnabled") and again.get("itemsEnabled") == 0,
                  f"after close {shut.get('hosts')}; reopened ({rep['reuse']}): final {again.get('final')!r}, "
                  f"list on {again.get('itemsEnabled')}, dice on {again.get('gambleEnabled')}")
        self.host("func", "close")
        time.sleep(0.5)
        bad = self.bad_lines(mark)
        rep["bad"] = bad[:10]
        self.flag("dealer_clean_log", not bad, f"{len(bad)}: {bad[:5]}")
        self.out["dealer"] = rep

    def end(self):
        rep = {}
        mark = len(self.g.read_log())
        levels = self.levels()
        dragon = [(i, lvl) for i, _, lvl in levels if level_name(lvl) == "boss_dragon"]
        self.flag("end_floor_found", bool(dragon), str(levels))
        if not dragon:
            return
        i, lvl = dragon[0]
        number, files, _ = RECIPES["boss_dragon"]
        found, r, started = self.start_boss(i, lvl)
        rep["start"] = started
        self.flag("end_dragon", bool(found), f"load {r}, {started}, found {found}")
        line = f"HoH1 boss {number} killed"
        for _ in range(3):
            if line in self.g.read_log()[mark:]:
                break
            self.gl("kill", 4000, "/" + files[0].rsplit("/", 1)[-1], "me")
            time.sleep(3)
        w = self.wait_host("HoH1EndOfGame", 20)
        rep["window"] = w
        self.g.shot("end-window")
        texts = w.get("texts") or []
        self.flag("end_opens", w.get("top") == "HoH1EndOfGame" and "THE END" in texts
                  and any(t.startswith(END_TEXT) for t in texts), f"{line in self.g.read_log()[mark:]}, window {w}")
        self.host("func", "town")
        town = self.wait_phase("town", 120)
        st = self.gl("state")
        rep["after"] = {k: st.get(k) for k in ("phase", "level")}
        self.flag("end_continue", town, f"{rep['after']}")
        bad = self.bad_lines(mark)
        rep["bad"] = bad[:10]
        self.flag("end_clean_log", not bad, f"{len(bad)}: {bad[:5]}")
        self.out["end"] = rep


def run(p, sections="dealer,end", **_):
    c = Checks(p)
    want = str(sections).split(",")
    if "dealer" in want:
        c.gambler()
    if "end" in want:
        c.end()
    return c.out
