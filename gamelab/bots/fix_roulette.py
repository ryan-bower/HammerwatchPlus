"""Roulette (mods/roulette: HWP/Roulette), in town as the host, solo:

- The fixture town gets a guild hall and a tavern (`gl build`, then `gl townrefresh`).
- The wheel: the log names the tavern table it went on; `gl unitsof` finds one
  hwp_roulette_wheel; the table under it shows its bare "default" scene (no food).
- The table: `hwp roulette` reports a betting round and all 157 bets.
- The window: using the wheel opens HWPRouletteMenu (no pause).
- A round: Luck 20 (`hwp luck 20`), 1000 each on s:17, c:13 (13-14-16-17), odd and red,
  then `hwp roulette spin 17`. While the ball runs the wheel shows its "spin" scene. The
  result pays 1000 + 35000 x 1.2, 1000 + 8000 x 1.2 and 1000 + 1000 x 1.2 (red loses):
  55800 back on 4000 staked at +20%. A fixture gold-find bonus adds to that; its status
  line is rounded to whole percent, so the check allows 0.6% of the winnings.
- Clear: chips placed and cleared in the next round come back in full.
- The limit: ten 100K chips fill roulette.max_stake (1,000,000); an eleventh is refused.

- Tiers (section tiers): the tavern upgraded to tiers 2 and 3, the wheel comes back each
  time, one of it, on a table in the main hall.
- Leaving (section leave, last): 7000 on black, then a run starts (`gl mission
  bandit_keep`) before the result. The level change resets the script's stakes; the
  module's Start pays the 7000 back to the town's gold from the town's save ("7000 back
  (left on the table at a level change)"), not to the run's gold (still 0). Back in town
  (`gl abort`) the town's gold equals the gold before the bet.

Shots: roulette-wheel, roulette-menu, roulette-spin, roulette-result, roulette-tier2/3.

Sections: roulette, tiers, leave."""
import re
import time

from gamelab.bots.plan_runs import Checks as Base

WHEEL = "doodads/hwp/hwp_roulette_wheel.unit"
STATUS = re.compile(r"roulette: round (\d+), phase (\d+), .*?bonus (\d+)% \(luck (\d+)%, gold (\d+)%\).*?; (\d+) bets")
ON_TABLE = re.compile(r"the wheel is on (\S+) at (-?\d+),(-?\d+)")
LANDED = re.compile(r"round (\d+) landed (\d+): staked (\d+), paid (\d+)")


class Checks(Base):
    def gold(self):
        return self.gl("inv").get("materials", {}).get("gold", 0)

    def status(self):
        log = self.hwp("roulette", 0.5, until="roulette: round")
        m = STATUS.findall(log)
        return m[-1] if m else None

    def go_wheel(self):
        """Teleport to just below the wheel: the lab town walks the player off a moment
        after a teleport, so read or shoot what is near at once."""
        units = (self.gl("unitsof", WHEEL).get(WHEEL) or {}).get("units") or []
        if units:
            self.gl("teleport", round(units[0].get("x", 0)), round(units[0].get("y", 0)) + 26)
        return units

    def wheel_scene(self):
        self.go_wheel()
        units = self.gl("near", 80, "hwp_roulette_wheel").get("units") or []
        return units[0].get("scene") if units else None

    def wait_phase(self, phase, timeout=30):
        end = time.time() + timeout
        st = None
        while time.time() < end:
            st = self.status()
            if st and int(st[1]) == phase:
                return st
            time.sleep(0.5)
        return st

    def roulette(self):
        if not self.gl("buildings").get("buildings"):
            for b in ("guild_hall", "tavern"):
                r = self.gl("build", b)
                self.notes.append(f"build {b}: {r.get('ok')} {r.get('error', '')}")
            self.gl("townrefresh")
        time.sleep(3)

        # the wheel on a table
        on = ON_TABLE.findall(self.g.read_log())
        units = self.go_wheel()
        table_scene = None
        if units:
            tables = self.gl("near", 80, "table_wood").get("units") or []
            time.sleep(0.2)
            self.g.shot("roulette-wheel")
            # the table the log names, not just the nearest: tier 1 has two in reach
            if on:
                tx, ty = float(on[-1][1]), float(on[-1][2])
                tables.sort(key=lambda t: abs(t.get("x", 0) - tx) + abs(t.get("y", 0) - ty))
            table_scene = tables[0].get("scene") if tables else None
        self.flag("rl_wheel", bool(on) and on[-1][0].startswith("doodads/furniture/table_") and len(units) == 1
                  and table_scene == "default", f"{on[-1:]}; {len(units)} wheel(s); table scene {table_scene}")

        st = self.status()
        self.flag("rl_table", st is not None and int(st[0]) >= 1 and int(st[5]) == 157, f"{st}")
        if st is None:
            return

        u = self.gl("use", "hwp_roulette_wheel")
        time.sleep(0.8)
        win = self.window()
        self.flag("rl_menu", "HWPRouletteMenu" in win, f"use {u}; window {win!r}")

        # a round with a known number and a known bonus
        self.hwp("luck 20", 0.4)
        self.gl("material", "gold", 200000)
        st = self.wait_phase(0)
        self.hwp("roulette clear", 0.3)
        g0 = self.gold()
        bets = ["s:17", "c:13", "odd", "red"]
        for k in bets:
            self.hwp(f"roulette bet {k} 1000", 0.3, until=f"on {k}")
        g1 = self.gold()
        self.g.shot("roulette-menu")
        st = self.status()
        bonus = (int(st[3]) + int(st[4])) / 100 if st else 0
        mark = len(self.g.read_log())
        self.hwp("roulette spin 17", 0.3, until="the ball lands on 17")
        time.sleep(1.2)
        spin_scene = self.wheel_scene()
        self.g.shot("roulette-spin")
        end = time.time() + 12
        landed = []
        while time.time() < end and not landed:
            time.sleep(0.5)
            landed = LANDED.findall(self.g.read_log()[mark:])
        g2 = self.gold()
        want = 1000 + int(35000 * (1 + bonus)) + 1000 + int(8000 * (1 + bonus)) + 1000 + int(1000 * (1 + bonus))
        paid = int(landed[-1][3]) if landed else -1
        self.flag("rl_scene", spin_scene == "spin", f"wheel scene while the ball runs: {spin_scene}")
        self.flag("rl_payout", g0 - g1 == 4000 and landed and landed[-1][1] == "17" and abs(paid - want) <= 3 + 0.006 * 44000
                  and g2 - g1 == paid, f"gold {g0} -> {g1} (bets) -> {g2}; landed {landed[-1:]}; want {want} "
                  f"(bonus {bonus:.2f}: luck {st[3] if st else '?'}%, gold {st[4] if st else '?'}%)")
        self.g.shot("roulette-result")

        # Clear in the next round
        self.wait_phase(0)
        idle = self.wheel_scene()
        h0 = self.gold()
        self.hwp("roulette bet black 5000", 0.3, until="on black")
        h1 = self.gold()
        self.hwp("roulette clear", 0.3, until="cleared")
        h2 = self.gold()
        self.flag("rl_clear", h0 - h1 == 5000 and h2 == h0 and idle == "idle",
                  f"gold {h0} -> {h1} -> {h2}; wheel scene between spins {idle}")

        # the per-round limit
        self.gl("material", "gold", 1100000)
        replies = []
        for i in range(11):
            log = self.hwp("roulette bet low 100000", 0.25, until="bet 100000 on low" if i < 10 else "no bet")
            replies.append("no bet" not in log)
        refused = self.hwp("roulette bet low 100", 0.3, until="no bet")
        self.flag("rl_limit", all(replies[:10]) and not replies[10] and "table limit" in refused,
                  f"{replies}; {refused.strip()[-120:]}")
        self.hwp("roulette clear", 0.3)

    def tiers(self):
        """Each tavern upgrade reloads the town: the wheel comes back, one of it, on a main
        hall table (y between -280 and -150, RouletteModule.as HALL_TOP/HALL_BOTTOM)."""
        seen = []
        for tier in (2, 3):
            mark = len(self.g.read_log())
            r = self.gl("buildup", "tavern", 1)
            end = time.time() + 15
            on = []
            while time.time() < end and not on:
                time.sleep(0.5)
                on = ON_TABLE.findall(self.g.read_log()[mark:])
            time.sleep(1)
            units = self.go_wheel()
            time.sleep(0.2)
            self.g.shot(f"roulette-tier{tier}")
            ok = bool(on) and len(units) == 1 and -280 <= int(on[-1][2]) <= -150
            seen.append(ok)
            self.notes.append(f"tier {tier} (buildup ok {r.get('ok')}): {on[-1:]}; {len(units)} wheel(s)")
        self.flag("rl_tiers", all(seen), f"{seen}")


    def leave(self):
        self.gl("material", "gold", 50000)
        self.wait_phase(0)
        self.hwp("roulette clear", 0.3)
        g0 = self.gold()
        self.hwp("roulette bet black 7000", 0.3, until="on black")
        g1 = self.gold()
        mark = len(self.g.read_log())
        r = self.gl("mission", "bandit_keep", 0)
        end = time.time() + 120
        phase = None
        while time.time() < end:
            phase = self.gl("state", timeout=4).get("phase")
            if phase == "mission":
                break
            time.sleep(1)
        time.sleep(2)
        run_gold = self.gold()
        log = self.g.read_log()[mark:]
        back = "7000 back (left on the table at a level change)" in log
        self.gl("abort")
        end = time.time() + 90
        town = None
        while time.time() < end:
            town = self.gl("state", timeout=4).get("phase")
            if town == "town":
                break
            time.sleep(1)
        time.sleep(2)
        g2 = self.gold()
        self.flag("rl_leave", g0 - g1 == 7000 and phase == "mission" and back and run_gold == 0 and town == "town" and g2 == g0,
                  f"town gold {g0} -> {g1} (bet); run gold {run_gold}; phase {phase}; refund logged {back}; "
                  f"back in {town}: town gold {g2}; mission {r}")

def run(p, sections="roulette", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
