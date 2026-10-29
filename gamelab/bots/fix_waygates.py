"""Way Gates (mods/waygates: HWP/WayGates), in town as the host:

- The fixture town gets a guild hall and a tavern (`gl build`, then `gl townrefresh`).
- `hwp waygates` lists the gates: the town square first, then one per built building.
- `gl unitsof doodads/hwp/hwp_waygate.unit` finds one unit at each listed spot.
- Using the square's gate (`gl use hwp_waygate` beside it) opens HWPWayGateMenu with one
  button per gate, the square's own greyed.
- Pressing the last gate's button closes the menu and puts the player on that gate.
- A building upgrade reloads the town: the host spawns the gates again (same count).

Shots: waygate-square, waygate-menu, waygate-arrived, waygate-<id> for up to four gates
(placement in front of each building).

Sections: waygates."""
import re
import time

from gamelab.bots.plan_runs import Checks as Base

UNIT = "doodads/hwp/hwp_waygate.unit"
GATE = re.compile(r"(\d+) ([\w-]+) at (-?\d+),(-?\d+)")


class Checks(Base):
    def gates(self):
        log = self.hwp("waygates", 0.6, until="way gates (")
        line = [ln for ln in log.splitlines() if "way gates (" in ln]
        if not line:
            return []
        return [(m[1], int(m[2]), int(m[3])) for m in GATE.findall(line[-1])]

    def units(self):
        r = self.gl("unitsof", UNIT)
        lst = (r.get(UNIT) or {}).get("units") or []
        return [(round(u.get("x", 0)), round(u.get("y", 0))) for u in lst]

    def pos(self):
        p = self.gl("state").get("player") or {}
        return p.get("x", 0.0), p.get("y", 0.0)

    def waygates(self):
        # the fixture town has no buildings: build two and reload it (what an upgrade's cutscene does)
        if not self.gl("buildings").get("buildings"):
            for b in ("guild_hall", "tavern"):
                r = self.gl("build", b)
                self.notes.append(f"build {b}: {r.get('ok')} {r.get('error', '')}")
            self.gl("townrefresh")
        time.sleep(3)  # the gates spawn 800 ms after the town's own units
        gates = self.gates()
        self.flag("wg_listed", len(gates) >= 2 and gates[0][0] == "square", f"{gates}")
        if len(gates) < 2:
            return
        units = self.units()
        missing = [g for g in gates if not any(abs(u[0] - g[1]) <= 2 and abs(u[1] - g[2]) <= 2 for u in units)]
        self.flag("wg_units", len(units) == len(gates) and not missing, f"{len(units)} unit(s) {units}; missing {missing}")

        sq = gates[0]
        self.gl("teleport", sq[1], sq[2] + 14)
        time.sleep(0.8)
        self.g.shot("waygate-square")
        u = self.gl("use", "hwp_waygate")
        time.sleep(0.8)
        win = self.window()
        nodes = self.gl("wchildren", "list", 1).get("nodes", [])
        btns = [n for n in nodes if str(n.get("id", "")).startswith("hwp-waygate-")]
        here = [n for n in btns if n.get("id") == "hwp-waygate-0"]
        self.flag("wg_menu", "HWPWayGateMenu" in win and len(btns) == len(gates) and here and here[0].get("enabled") is False,
                  f"use {u}; window {win}; {len(btns)} button(s); square's {here[:1]}")
        self.g.shot("waygate-menu")

        last = len(gates) - 1
        self.gl("press", f"hwp-waygate-{last}")
        # the first read: in the lab town the player starts walking a moment after any
        # teleport (gl teleport too, about 90 px/s), whatever moved them there
        x, y = self.pos()
        to = gates[last]
        time.sleep(0.3)
        self.flag("wg_travel", not self.window() and abs(x - to[1]) <= 6 and abs(y - (to[2] + 4)) <= 6,
                  f"to {to}; player at {x:.0f},{y:.0f}; window {self.window()!r}")
        self.g.shot("waygate-arrived")

        for g in gates[1:5]:
            self.gl("teleport", g[1], g[2] + 14)
            time.sleep(0.7)
            self.g.shot(f"waygate-{g[0]}")

        # a building upgrade reloads the town; the host places the gates again
        b = gates[1][0]
        r = self.gl("buildup", b, 1)
        time.sleep(4)
        again = self.gates()
        units2 = self.units()
        self.flag("wg_rebuilt", len(units2) == len(again) and len(again) >= len(gates),
                  f"buildup {b}: {str(r)[:160]}; {len(again)} gate(s), {len(units2)} unit(s)")


def run(p, sections="waygates", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
