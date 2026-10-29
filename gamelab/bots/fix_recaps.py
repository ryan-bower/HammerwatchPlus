"""fix-recaps: the boss-fight damage recap (mods/deathrecap, BossRecap.as) and the last-run
board's search + one-page bar graphs (mods/laststats).

Sections (kwargs sections="boss,board"):
- boss: start Bandit Keep floor 0, spawn the Bandit boss next to the ranger, let the pilot
  shoot it for a few seconds (real hits: PlayerDamagedActor is the only path that records
  damage), then `gl kill 600 tag:boss me` ends the fight. Asserts the recap log line
  ("boss recap Boss Bandit: Pilot dealt N (P%) took T: <sources>") with N > 0 and at least
  one named source, the HUD panel ("hwp bossrecap" logs "boss panel shown: N lines"), and
  takes the "boss-recap" shot while the panel is up.
- board: abort the run as failed (DeadMenu's path), back in town note whether the real
  snapshot landed (soft), then `hwp laststats sample 2` (two deterministic snapshots: the
  local player and "Sample 2"), open the board with `gl use laststats_board`, and assert
  through "hwp laststats board" (a log line with the counts) and `gl wtext` (row titles,
  bar names and values): two players in the legend and on every row, bars, the search
  filter through the window's own OnFunc ("search damage" hides the other rows,
  "search-clear" brings them back) and a typed search (press the field, type "damage": soft,
  the console's own key may end the field's focus). Shots "board" (all rows) and
  "board-search" (filtered).
Every section returns its flags; the scenario asserts them. No real input.
"""
import json
import re
import time

from gamelab.bots.plan_checks import Checks as Base

BOSS_UNIT = "actors/bosses/boss_bandit/boss_bandit.unit"
RECAP = re.compile(r"boss recap (?P<boss>[^:]+): (?P<name>\S+) dealt (?P<dealt>\d+) \((?P<pct>\d+)%\) took (?P<taken>\d+): (?P<sources>.*)")
BOARD = re.compile(r"board open: (?P<shown>\d+) of (?P<total>\d+) stats, (?P<players>\d+) players, (?P<bars>\d+) bars, "
                   r"filter \"(?P<filter>[^\"]*)\", typing (?P<typing>\d), input \"(?P<input>[^\"]*)\", rows: (?P<rows>.*)")


class Checks(Base):
    def log_since(self, mark):
        return self.g.read_log()[mark:]

    def wait_log(self, mark, pattern, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            m = pattern.search(self.log_since(mark))
            if m:
                return m
            time.sleep(0.25)
        return None

    def board_status(self):
        txt = self.hwp("laststats board", 0.4, until="board ")
        ms = list(BOARD.finditer(txt))
        if not ms:
            return None
        m = ms[-1]
        d = {k: (int(v) if k in ("shown", "total", "players", "bars", "typing") else v) for k, v in m.groupdict().items()}
        d["rows"] = [r.strip() for r in d["rows"].split(";") if r.strip()]
        return d

    def wtext(self, *ids):
        return self.gl("wtext", *ids)

    # --- boss
    def boss(self):
        self.flag("boss_floor", self.start_floor(0))
        if not self.out["boss_floor"]:
            return
        # god mode first: the boss killed the level-20 ranger within the 10 s attack window
        # (fix-recaps 20261025-231419, "player dead or not spawned"); damage taken is a soft flag
        self.hwp("god", 0.3)
        mark = len(self.g.read_log())
        sp = self.gl("spawn", BOSS_UNIT, 70, 0)
        self.flag("boss_spawned", sp.get("ok") is True and isinstance(sp.get("unit"), int), str(sp))
        if not self.out["boss_spawned"]:
            return
        uid = sp["unit"]
        time.sleep(0.5)
        # real hits for up to 10 s (the boss has 20000 hp: the pilot will not kill it)
        r = self.p.attack(uid, timeout=10)
        self.notes.append(f"attack: {r.result} {r.reason}")
        near = self.gl("near", 600, "boss_bandit")
        boss = next((u for u in near.get("units", []) if u.get("unit") == uid), None)
        started = "boss fight started: Boss Bandit" in self.log_since(mark)
        self.flag("boss_hit", boss is not None and isinstance(boss.get("hp"), (int, float)) and boss["hp"] < 1.0 and started,
                  f"near {boss}, fight started {started}")
        kill = self.gl("kill", 600, "tag:boss", "me")
        self.flag("boss_killed", kill.get("ok") is True and (kill.get("killed") or 0) >= 1, str(kill))
        m = self.wait_log(mark, RECAP, 10)
        if m is None:
            self.flag("boss_recap_logged", False, "no 'boss recap' line within 10 s")
            self.flag("boss_recap_damage", False)
            self.flag("boss_recap_sources", False)
        else:
            d = m.groupdict()
            self.flag("boss_recap_logged", d["name"] == "Pilot" and d["boss"].strip() == "Boss Bandit", m.group(0))
            self.flag("boss_recap_damage", int(d["dealt"]) > 0 and int(d["pct"]) == 100, f"dealt {d['dealt']} ({d['pct']}%)")
            srcs = [s.strip() for s in d["sources"].split(",") if s.strip()]
            self.flag("boss_recap_sources", len(srcs) >= 1 and all(re.search(r" \d+$", s) for s in srcs), str(srcs))
            self.out["boss_taken"] = int(d["taken"])  # the boss may not have landed a hit in 10 s: recorded, not asserted
            self.out["boss_recap_line"] = m.group(0)
        txt = self.hwp("bossrecap", 0.4, until="boss panel")
        pm = re.search(r"boss panel shown: (\d+) lines", txt)
        self.flag("boss_panel", pm is not None and int(pm.group(1)) >= 2, txt.strip()[-200:])
        # the HUD component in the widgets dump (may be cut by the dump's cap in a run)
        root = next((r for r in self.gl("widgets", 3).get("roots", []) if r.get("root") == "HUD:HWPBossRecapHUD"), None)
        self.out["boss_panel_widget"] = bool(root and root.get("visible"))
        self.notes.append(f"panel widget root: {json.dumps(root)[:300] if root else 'cut/absent'}")
        self.g.shot("boss-recap")

    # --- board
    def board(self):
        mark = len(self.g.read_log())
        st = self.gl("state")
        if st.get("phase") == "mission":
            self.gl("abort", "failed")
        ok = self.wait_phase("town", 120)
        time.sleep(2.5)
        if self.gl("state").get("window"):
            self.g.key("escape")  # the MissionEndMenu
            time.sleep(0.5)
        self.flag("board_town", ok)
        if not ok:
            return
        snap = re.search(r"\[HWP:laststats\] snapshot of Pilot, (.*)", self.log_since(mark))
        self.out["board_real_snapshot"] = snap is not None  # soft: the run's own snapshot (RE_NOTES: taken in PlayerRecordLoad)
        self.notes.append(f"real snapshot: {snap.group(1) if snap else 'none'}")

        txt = self.hwp("laststats sample 2", 0.5, until="sample:")
        self.flag("board_sample", "sample: 2 snapshots" in txt, txt.strip()[-120:])
        use = self.gl("use", "laststats_board")
        time.sleep(0.8)
        self.flag("board_opens", use.get("ok") is True and self.gl("state").get("window") == "HWPLastStatsMenu", str(use))
        if not self.out["board_opens"]:
            return
        s0 = self.board_status()
        self.flag("board_status", s0 is not None, str(s0)[:300])
        if s0 is None:
            return
        self.flag("board_one_page", s0["players"] == 2 and s0["total"] >= 10 and s0["shown"] == s0["total"] and s0["filter"] == "",
                  f"{s0['shown']}/{s0['total']} stats, {s0['players']} players")
        # a bar per player per stat where the value is > 0: the second sample skips every 5th stat
        self.flag("board_bars", s0["total"] < s0["bars"] <= 2 * s0["total"], f"bars {s0['bars']} for {s0['total']} stats")
        w = self.wtext("legend-0", "legend-1", "stat-title-0", "bar-name-0-0", "bar-name-0-1", "bar-value-0-0", "bar-value-0-1",
                       "stat-title-1", "bar-name-1-1", "bar-value-1-1")
        t = w.get("texts", {}) if isinstance(w.get("texts"), dict) else w
        self.flag("board_row_players", str(t.get("bar-name-0-0", "")).strip() == "Pilot" and str(t.get("bar-name-0-1", "")).strip() == "Sample 2"
                  and str(t.get("legend-0", "")).startswith("Pilot") and str(t.get("legend-1", "")).startswith("Sample 2")
                  and bool(t.get("stat-title-0")) and bool(t.get("bar-value-0-0")) and bool(t.get("bar-value-0-1"))
                  and not w.get("missing"), json.dumps(w)[:400])
        self.g.shot("board")

        # search through the window's own OnFunc (what the field's func-edit calls)
        mark2 = len(self.g.read_log())
        self.gl("func", "search", "damage")
        time.sleep(0.4)
        s1 = self.board_status()
        self.flag("board_filter", s1 is not None and s1["filter"] == "damage" and 0 < s1["shown"] < s1["total"]
                  and all("damage" in r.lower() for r in s1["rows"]) and s1["input"] == "damage",
                  str(s1)[:300])
        self.g.shot("board-search")
        self.gl("func", "search-clear")
        time.sleep(0.4)
        s2 = self.board_status()
        self.flag("board_filter_clear", s2 is not None and s2["filter"] == "" and s2["shown"] == s2["total"], str(s2)[:200])

        # typed search: press the field, then posted WM_CHARs. Soft: `press` clicks while the
        # console is open and the console's closing can end the field's focus (gamelab skill,
        # "type" step); the func path above is the hard check of the filter itself.
        pr = self.gl("press", "search")
        time.sleep(0.8)
        self.g.type_text("damage", 0.08)
        time.sleep(0.6)
        s3 = self.board_status()
        typed = s3 is not None and s3["input"] == "damage" and s3["filter"] == "damage" and 0 < s3["shown"] < s3["total"]
        self.out["board_typed"] = bool(typed)
        self.notes.append(f"typed search: press {pr.get('ok')} -> {str(s3)[:200]}")
        if typed:
            self.gl("func", "search-clear")
            time.sleep(0.3)
        self.gl("func", "close")
        time.sleep(0.5)
        self.flag("board_closed", not self.gl("state").get("window"))


def run(p, sections="boss,board", **_):
    c = Checks(p)
    for s in [x.strip() for x in sections.split(",") if x.strip()]:
        getattr(c, s)()
    c.out["notes"] = c.notes
    return c.out
