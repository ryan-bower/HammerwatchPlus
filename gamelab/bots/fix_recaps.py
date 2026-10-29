"""fix-recaps: the boss-fight damage recap (mods/deathrecap, BossRecap.as) and the last-run
board's search + one-page bar graphs (mods/laststats).

Sections (kwargs sections="boss,board"):
- boss: start Bandit Keep floor 0, spawn the Bandit boss next to the ranger, let the pilot
  shoot it for a few seconds (real hits: PlayerDamagedActor is the only path that records
  damage), then `gl kill 600 tag:boss me` ends the fight. Asserts the recap log line
  ("boss recap Bandit Lord: Pilot dealt N (P%) took T: <sources>", the boss bar's name) with N > 0 and at least
  one named source, the HUD panel ("hwp bossrecap" logs "boss panel shown: N lines"), and
  takes the "boss-recap" shot while the panel is up.
- multi (issue #33): the Bandit Lord and its boss-tagged mirror image, both hit, are one fight;
  the mirror killed first (`gl kill 600 id:<unit> me`) logs "down" and no recap while the
  Lord's bar is up; the Lord's death gives one recap of 2 units.
- serpents (issue #33): dark_citadel floor 18 (levels/boss_bone_serpent.lvl), `gl wsexec
  ScriptLink BossStart`, hit a serpent ("Serpents of Demise"), kill it: "down", no recap;
  kill the rest and the health unit: one recap. Shot "serpent-recap".
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
MIRROR_UNIT = "actors/bosses/boss_bandit/boss_bandit_mirror.unit"  # the Bandit Lord's boss-tagged mirror image, no bar
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
        started = "boss fight started: Bandit Lord" in self.log_since(mark)
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
            # named after the HUD's boss bar (issue #33)
            self.flag("boss_recap_logged", d["name"] == "Pilot" and d["boss"].strip() == "Bandit Lord", m.group(0))
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

    def god_on(self):
        """hwp god toggles (the cht_god cvar, which outlives the floor): on, never back off."""
        if not self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"):
            self.hwp("god", 0.4)

    # --- several boss units, one fight (issue #33)
    def recaps_since(self, mark):
        return list(RECAP.finditer(self.log_since(mark)))

    def multi(self):
        """The Bandit Lord and its boss-tagged mirror image (no bar of its own): both hit, the
        mirror killed first must not end the fight (the Lord's bar is up); the Lord's death
        does, with one recap holding the hits on both."""
        self.flag("multi_floor", self.start_floor(0))
        if not self.out["multi_floor"]:
            return
        self.god_on()
        mark = len(self.g.read_log())
        lord = self.gl("spawn", BOSS_UNIT, 70, 0)
        mirror = self.gl("spawn", MIRROR_UNIT, -70, 0)
        ok = all(s.get("ok") is True and isinstance(s.get("unit"), int) for s in (lord, mirror))
        self.flag("multi_spawned", ok, f"{lord} {mirror}")
        if not ok:
            return
        time.sleep(0.5)
        for uid in (mirror["unit"], lord["unit"]):
            r = self.p.attack(uid, timeout=6)
            self.notes.append(f"attack {uid}: {r.result} {r.reason}")
        log = self.log_since(mark)
        starts = re.findall(r"boss fight started: ([^\n(]+)\(", log)
        joins = re.findall(r"boss fight [^:\n]+: (\S+[^\n(]*)\(unit (\d+)\) joins", log)
        self.flag("multi_one_fight", len(starts) == 1 and len(joins) == 1, f"started {starts}, joins {joins}")
        mk2 = len(self.g.read_log())
        k = self.gl("kill", 600, f"id:{mirror['unit']}", "me")
        time.sleep(4)
        after = self.log_since(mk2)
        down = re.search(r"boss fight Bandit Lord: .*\(unit " + str(mirror["unit"]) + r"\) down, (\d+) hit units alive, (\d+) boss bars up", log + after)
        self.flag("multi_mirror_down_goes_on", (k.get("killed") == 1 or down is not None) and down is not None
                  and not self.recaps_since(mark) and "boss fight over" not in self.log_since(mark),
                  f"kill {k}; down {down.group(0) if down else None}; recaps {[m.group(0) for m in self.recaps_since(mark)]}")
        self.gl("kill", 600, f"id:{lord['unit']}", "me")
        m = self.wait_log(mark, RECAP, 10)
        time.sleep(2)
        recaps = self.recaps_since(mark)
        over = re.search(r"boss fight over: Bandit Lord, (\d+) units, Pilot dealt (\d+)", self.log_since(mark))
        self.flag("multi_one_recap", m is not None and len(recaps) == 1 and recaps[0]["boss"].strip() == "Bandit Lord"
                  and over is not None and int(over.group(1)) == 2 and int(recaps[0]["dealt"]) > 0,
                  f"recaps {[r.group(0) for r in recaps]}; over {over.group(0) if over else None}")

    def serpents(self):
        """The issue's own boss: the Serpents of Demise (dark_citadel courts_boss, levels/boss_bone_serpent.lvl).
        Four boss-tagged serpents (TransferDamageActor) pass their damage to one health unit with
        the bar. The fight starts through the level's own BossStart script; a serpent killed must
        not end the fight, the whole set (serpents and the health unit) does, with one recap."""
        r = self.gl("mission", "dark_citadel", 18)
        ok = bool(r.get("ok")) and str(r.get("level", "")).endswith("boss_bone_serpent.lvl") and self.wait_phase("mission")
        self.flag("serpent_floor", ok, str(r))
        if not ok:
            return
        time.sleep(3)
        self.god_on()
        mark = len(self.g.read_log())
        ws = self.gl("wsexec", "ScriptLink", "BossStart")
        self.flag("serpent_start", ws.get("ok") is True, str(ws))
        live = []
        end = time.time() + 30
        while time.time() < end and not live:
            acts = self.gl("actors", 5000, "TransferDamageActor").get("actors", [])
            live = [a for a in acts if not a.get("dead") and a.get("targetable")]
            if not live:
                time.sleep(1)
        self.notes.append(f"serpents: {json.dumps(live)[:600]}")
        self.flag("serpent_up", bool(live), f"{len(live)} targetable serpents")
        if not live:
            return
        # the heads surface, spew and dive: stand 90 px from a surfaced one and shoot, again
        # with a fresh list until a hit lands (fix-boss-recap-encounter 044715: three 8 s
        # attacks from the arena's edge landed nothing)
        hit = None
        end = time.time() + 45
        while time.time() < end and hit is None:
            acts = self.gl("actors", 5000, "TransferDamageActor").get("actors", [])
            live = [a for a in acts if not a.get("dead") and a.get("targetable")]
            if not live:
                time.sleep(1)
                continue
            a = live[0]
            pl = self.gl("state").get("player", {})
            px, py = pl.get("x", 0.0), pl.get("y", 0.0)
            d = max(1.0, ((a["x"] - px) ** 2 + (a["y"] - py) ** 2) ** 0.5)
            if d > 120:
                self.gl("teleport", round(a["x"] - (a["x"] - px) / d * 90, 1), round(a["y"] - (a["y"] - py) / d * 90, 1))
                time.sleep(0.3)
            res = self.p.attack(a["unit"], timeout=4)
            self.notes.append(f"attack serpent {a['unit']} from {round(d)} px: {res.result} {res.reason}")
            if "boss fight started" in self.log_since(mark):
                hit = a
        # the serpent the shots hit first (not always the one aimed at)
        st = re.search(r"boss fight started: ([^\n(]+)\([^,\n]*, unit (\d+)\)", self.log_since(mark))
        self.flag("serpent_fight_started", hit is not None and st is not None and st.group(1).strip() == "Serpents of Demise",
                  st.group(0) if st else "no fight started")
        if st is None:
            return
        hit = {"unit": int(st.group(2))}
        k = self.gl("kill", 5000, f"id:{hit['unit']}", "me")
        time.sleep(4)
        log = self.log_since(mark)
        down = re.search(r"boss fight Serpents of Demise: .*\(unit " + str(hit["unit"]) + r"\) down, (\d+) hit units alive, (\d+) boss bars up", log)
        self.flag("serpent_one_down_goes_on", k.get("killed") == 1 and down is not None and int(down.group(2)) >= 1
                  and not self.recaps_since(mark) and "boss fight over" not in log,
                  f"kill {k}; down {down.group(0) if down else None}; recaps {[m.group(0) for m in self.recaps_since(mark)]}")
        k2 = self.gl("kill", 5000, "tag:boss", "me")
        k3 = self.gl("kill", 5000, "boss_serpent_health", "me")
        self.notes.append(f"end: {k2} {k3}")
        m = self.wait_log(mark, RECAP, 12)
        time.sleep(2)
        recaps = self.recaps_since(mark)
        self.flag("serpent_one_recap", m is not None and len(recaps) == 1 and recaps[0]["boss"].strip() == "Serpents of Demise"
                  and int(recaps[0]["dealt"]) > 0, f"recaps {[r.group(0) for r in recaps]}")
        self.g.shot("serpent-recap")

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
