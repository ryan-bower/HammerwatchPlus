"""The Luck stat (mods/core/scripts/HWP/Core/Luck.as, docs/design/luck.md, scenario
fix-core-luck), in town as the host:

- `hwp luck 50` (cheat): the status line reads `Luck: 50 (factor 1.5`.
- the character sheet's Mods tab has the row (widget `hwp-luck`, read with
  `gl menu mods - hwp-luck`): "50 Luck".
- `hwp luck item 2` equips a chest piece carrying the rare affix (+10): `Luck: 60`.
- `hwp luck buff 25 4000`: `gl hasbuff` sees tweak/hwp/buffs_luck.sval:hwp_luck_charm,
  the status reads 85; 5 s later the buff is gone and the status is back to 60.
- `hwp luck roll hwp_strongbox 3000 0` vs `... 500`: the trinket pool's epic count is
  higher at 500 Luck; `roll chance 40 3000` hits more; `roll tier 3000` ups 0 -> many;
  `roll quality` picks more rares, `roll secret` adds rooms, `roll count` leans counts up.
- a strongbox spawned next to the player and used (no enemies in town to sample a pack
  from, so it pays at once) logs `[HWP:strongbox] luck x1.6 payout` and
  `[HWP:luck] loot strongbox factor 1.6`; a spawned bronze resource cache (a Chest unit,
  HWPChest through the keys module) logs `[HWP:keys] luck x1.6 chest open loot`.

Sections: all (the default), or any of status, sheet, item, buff, rolls, sites.
"""
import re
import time

from gamelab.bots.plan_checks import Checks as Base

BUFF = "tweak/hwp/buffs_luck.sval:hwp_luck_charm"


class Checks(Base):
    def status(self):
        """The status line hwp luck prints: (luck, factor) or None."""
        log = self.hwp("luck", 0.6, until="Luck: ")
        m = re.findall(r"Luck: (-?\d+) \(factor ([\d.]+)", log)
        if not m:
            return None
        return int(m[-1][0]), float(m[-1][1])

    def has_buff(self):
        r = self.gl("hasbuff", BUFF)
        for b in r.get("buffs") or []:
            if b.get("path") == BUFF:
                return bool(b.get("on")), int(b.get("left") or 0)
        return False, 0

    def close_menu(self):
        if self.gl("state").get("window"):
            self.g.key("escape")
            time.sleep(0.5)

    # --- sections
    def sec_status(self):
        log = self.hwp("luck 50", 0.8, until="Luck: ")
        st = self.status()
        self.flag("status_50", st is not None and st[0] == 50 and abs(st[1] - 1.5) < 0.01, f"status {st}; {log[-200:]!r}")

    def sec_sheet(self):
        self.gl("menu", "mods")
        time.sleep(0.6)
        r = self.gl("menu", "mods", "-", "hwp-luck")
        texts = r.get("texts") or ""
        # the row's own `shown` reads False while its texts render ("   | 50 Luck", lab run
        # 20261025-221657), so the texts decide
        self.flag("sheet_row", "Luck" in texts and re.search(r"\b50\b", texts) is not None,
                  f"tab {r.get('tab')} shown {r.get('shown')} texts {texts!r}")
        self.close_menu()

    def sec_item(self):
        log = self.hwp("luck item 2", 1.0, until="Luck affix tier 2")
        st = self.status()
        self.flag("item_adds_10", st is not None and st[0] == 60 and abs(st[1] - 1.6) < 0.01, f"status {st}; {log[-200:]!r}")

    def sec_buff(self):
        self.hwp("luck buff 25 4000", 0.8, until="Lucky Charm")
        on, left = self.has_buff()
        st = self.status()
        self.flag("buff_on", on and 0 < left <= 4000, f"on {on} left {left}")
        self.flag("buff_adds_25", st is not None and st[0] == 85, f"status {st}")
        time.sleep(5)
        on2, left2 = self.has_buff()
        st2 = self.status()
        self.flag("buff_expired", not on2 and st2 is not None and st2[0] == 60, f"on {on2} left {left2} status {st2}")

    def pool_counts(self, log):
        """{pool: [e0, e1, ..., none]} from the roll reply lines."""
        out = {}
        for pool, body in re.findall(r"pool (\d+):((?: e\d+ \d+)+ none \d+)", log):
            nums = [int(x) for x in re.findall(r"\d+(?= )|\d+$", body.replace(" e", " e"))]
            vals = [int(v) for v in re.findall(r"(?:e\d+|none) (\d+)", body)]
            out[int(pool)] = vals
        return out

    def epics(self, counts):
        """The strongbox trinket pool (index 2: 700 rare / 300 epic): its epic count, or -1."""
        pool = counts.get(2)
        if not pool or len(pool) < 3:
            return -1
        return pool[1]

    def sec_rolls(self):
        a = self.pool_counts(self.hwp("luck roll hwp_strongbox 3000 0", 1.2, until="pool 3:"))
        b = self.pool_counts(self.hwp("luck roll hwp_strongbox 3000 500", 1.2, until="pool 3:"))
        ea, eb = self.epics(a), self.epics(b)
        # 30 % vs 72 % of 3000: 900 vs 2160; a 300 margin is 20 standard deviations
        self.flag("roll_epics_up", ea >= 0 and eb > ea + 300, f"epics at luck 0: {ea}, at 500: {eb}; pools {a} / {b}")
        ha = re.findall(r"chance 40 luck 0 factor 1 n 3000: hits (\d+)", self.hwp("luck roll chance 40 3000 0", 1.0, until="hits"))
        hb = re.findall(r"chance 40 luck 500 factor 6 n 3000: hits (\d+)", self.hwp("luck roll chance 40 3000 500", 1.0, until="hits"))
        self.flag("roll_chance_up", ha and hb and 1000 < int(ha[-1]) < 1400 and int(hb[-1]) == 3000, f"hits {ha} {hb}")
        ua = re.findall(r"tier luck 0 factor 1 n 3000: ups (\d+)", self.hwp("luck roll tier 3000 0", 1.0, until="ups"))
        ub = re.findall(r"tier luck 500 factor 6 n 3000: ups (\d+)", self.hwp("luck roll tier 3000 500", 1.0, until="ups"))
        self.flag("roll_tier_up", ua and ub and int(ua[-1]) == 0 and 2000 < int(ub[-1]) < 2500, f"ups {ua} {ub}")
        # floors (LuckFloors.as): blueprint quality picks among {common, common, uncommon, rare}
        # weigh the rarer ones x6 at 500 Luck (rare ~750 -> ~1286 of 3000); the extra secret
        # room 0 -> 75 %; a reward count's lean, mean 1/2 -> 6/7
        qa = re.findall(r"quality luck 0 factor 1 n 3000: common (\d+) uncommon (\d+) rare (\d+)", self.hwp("luck roll quality 3000 0", 1.0, until="rare"))
        qb = re.findall(r"quality luck 500 factor 6 n 3000: common (\d+) uncommon (\d+) rare (\d+)", self.hwp("luck roll quality 3000 500", 1.0, until="rare"))
        self.flag("roll_quality_up", qa and qb and int(qb[-1][2]) > int(qa[-1][2]) + 300 and int(qb[-1][0]) < int(qa[-1][0]) - 600,
                  f"common/uncommon/rare {qa} {qb}")
        sa = re.findall(r"secret luck 0 factor 1 n 3000: extra rooms (\d+)", self.hwp("luck roll secret 3000 0", 1.0, until="extra rooms"))
        sb = re.findall(r"secret luck 500 factor 6 n 3000: extra rooms (\d+)", self.hwp("luck roll secret 3000 500", 1.0, until="extra rooms"))
        self.flag("roll_secret_up", sa and sb and int(sa[-1]) == 0 and 2100 < int(sb[-1]) < 2400, f"extra rooms {sa} {sb}")
        ca = re.findall(r"count luck 0 factor 1 n 3000: mean (\d+)/1000", self.hwp("luck roll count 3000 0", 1.0, until="mean"))
        cb = re.findall(r"count luck 500 factor 6 n 3000: mean (\d+)/1000", self.hwp("luck roll count 3000 500", 1.0, until="mean"))
        self.flag("roll_count_up", ca and cb and 460 < int(ca[-1]) < 540 and 830 < int(cb[-1]) < 885, f"means {ca} {cb}")

    def sec_sites(self):
        # luck 60 (cheat 50 + the tier 2 piece) when the sections ran in order
        mark = len(self.g.read_log())
        sp = self.gl("spawn", "doodads/hwp/strongbox.unit", 0, 40)
        time.sleep(0.6)
        u = self.gl("use", "strongbox")
        time.sleep(1.5)
        log = self.g.read_log()[mark:]
        self.flag("site_strongbox", "[HWP:strongbox] luck x" in log and "[HWP:luck] loot strongbox factor" in log,
                  f"spawn {sp.get('ok')} {sp.get('name')}; use {u.get('ok')} {u.get('unit')}; "
                  + repr(re.findall(r"\[HWP:(?:strongbox|luck)\][^\n]*", log)[-4:]))
        mark = len(self.g.read_log())
        sp = self.gl("spawn", "items/chests/cache_bronze.unit", 40, 0)
        time.sleep(0.6)
        u = self.gl("use", "cache_bronze")
        time.sleep(1.5)
        log = self.g.read_log()[mark:]
        self.flag("site_chest", "[HWP:keys] luck x" in log and "chest open loot" in log and "[HWP:luck] loot chest factor" in log,
                  f"spawn {sp.get('ok')} {sp.get('name')}; use {u.get('ok')} {u.get('unit')}; "
                  + repr(re.findall(r"\[HWP:(?:keys|luck)\][^\n]*", log)[-4:]))
        self.hwp("luck 0", 0.5)


SECTIONS = ["status", "sheet", "item", "buff", "rolls", "sites"]


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
