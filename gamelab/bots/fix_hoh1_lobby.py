"""Issue #123: HoH1 content on by default, checked per lobby (HWP::HoH1 in hwplib). One lab game
stands in for a lobby with `hwp hoh1 fake <none|other|match|silent|clear>`: the host counts a
"Lab peer" that reported no import, a different one, the same one, or never reported (saved in
the town, so it is still there on the next floor).

- on: no fake. `hwp hoh1` says the setting and the lobby are on; the Dark Citadel's chain runs
  dark_halls_1 -> dark_halls_2 -> hwp_battlements_1 -> hwp_battlements_2 -> dark_halls_boss.
- pets: with the lobby on an HoH1 pet is bought and out; `fake none` puts it away (logged) and
  every player is told in red who's pet and why; `fake match` brings it back; `fake clear`.
- none: `fake none`: one red join warning naming the Lab peer (and only one, a few seconds
  later still); the log's verdict is off; `hwp hoh1` lists the peer as "no import"; the chain is
  dark_halls_1 -> dark_halls_boss; the town portal offers the HoH2 tower and warns why.
- citadel: (fake none still on) dark_halls_1 loads, warns that the Battlements are skipped;
  `cht_finish_level` loads the Avatar's level, which warns again. No level from hoh1/.
- other: `fake clear` then `fake other`: the warning says the import differs.
- silent: `fake clear` then `fake silent`: no warning at once, the "sent no HoH1 report" one
  after HWP::HoH1::SILENT_MS (10 s).
- match: `fake match`: the verdict is on again and the chain runs through the Battlements.

Run the sections in that order (the default); each ends with `fake clear` unless noted.
"""
import re
import time

from gamelab.bots.fix_hoh1 import Checks as HoH1Checks

FULL = "chain dark_halls_1 -> dark_halls_2 -> hwp_battlements_1 -> hwp_battlements_2 -> dark_halls_boss"
SHORT = "chain dark_halls_1 -> dark_halls_boss"
WARN = r"\[HWP:hoh1\] warning: "


class Checks(HoH1Checks):
    def fake(self, what):
        rep = self.hwp(f"hoh1 fake {what}", 0.5, until="hoh1 fake")
        time.sleep(1.5)   # a few core ticks: the peer list, the verdict, the warnings
        return rep

    def warnings(self, mark):
        return re.findall(WARN + r"([^\r\n]*)", self.g.read_log()[mark:])

    def chain(self):
        _, text = self.citadel_floors()
        return text

    def report(self):
        return self.hwp("hoh1", 0.6, until="hoh1.content")

    # --- sections
    def sec_on(self):
        rep = self.report()
        self.flag("on_setting_default_on", "hoh1.content: on" in rep, rep.strip()[-300:])
        self.flag("on_lobby_on", "lobby on" in rep, rep.strip()[-300:])
        text = self.chain()
        self.flag("on_chain_through_battlements", FULL in text, text[-200:])

    def sec_pets(self):
        self.set_gold(200000)
        items, hits = self.shop_pets()
        pick = next((i for i in hits if "imp" in items[i].get("title", "").lower().split()), hits[0] if hits else None)
        self.flag("pets_listed_lobby_on", pick is not None, f"{len(hits)} HoH1-looking of {len(items)}")
        if pick is None:
            self.close_window()
            return
        self.gl("shop", "buy", pick)
        time.sleep(1.5)
        self.close_window()
        out = self.pet_units()
        self.flag("pets_bought_out", bool(out), f"{out[:1]}")
        mark = len(self.g.read_log())
        self.fake("none")
        log = self.g.read_log()[mark:]
        away = re.findall(r"\[HWP:pets\] HoH1 content off: put away the HoH1 pet (\S+)", log)
        self.flag("pets_put_away_on_mismatch", bool(away) and not self.pet_units(), f"{away}")
        # the pet's own line (hwp.pets.hoh1_away), not the join warning's "HoH1 pets are put away"
        warns = [w for w in self.warnings(mark) if "'s HoH1 pet " in w]
        self.flag("pets_warned_in_red", len(warns) == 1 and "Lab peer has no HoH1 import" in warns[0], f"{warns}")
        mark = len(self.g.read_log())
        self.fake("match")
        back = re.findall(r"\[HWP:pets\] HoH1 content on: the HoH1 pet (\S+) is back", self.g.read_log()[mark:])
        self.flag("pets_back_on_match", back == away[-1:] and bool(self.pet_units()), f"{away} -> {back}")
        self.fake("clear")

    def sec_none(self):
        mark = len(self.g.read_log())
        self.fake("none")
        warns = [w for w in self.warnings(mark) if w.startswith("HoH1 import mismatch")]
        self.flag("none_join_warned", len(warns) == 1 and "Lab peer has no HoH1 import" in warns[0], f"{warns}")
        log = self.g.read_log()[mark:]
        self.flag("none_verdict_logged", "lobby: HoH1 content off" in log,
                  " | ".join(l for l in log.splitlines() if "[HWP:hoh1]" in l)[-300:])
        rep = self.report()
        self.flag("none_report_lists_peer", "lobby off" in rep and "Lab peer: no import" in rep, rep.strip()[-300:])
        text = self.chain()
        self.flag("none_chain_skips_battlements", SHORT in text, text[-200:])
        time.sleep(3)
        again = [w for w in self.warnings(mark) if w.startswith("HoH1 import mismatch")]
        self.flag("none_join_warned_once", len(again) == 1, f"{again}")
        # the portal: the HoH2 tower, and why
        at = len(self.g.read_log())
        self.sec_portal()
        log = self.g.read_log()[at:]
        offering = re.findall(r"portal: offering ([^\r\n]*)", log)
        self.flag("none_portal_offers_hoh2", bool(offering) and "HoH2 themes" in offering[-1], f"{offering[-1:]}")
        pw = [w for w in self.warnings(at) if "portal offers the HoH2" in w]
        self.flag("none_portal_warned", len(pw) >= 1 and "Lab peer has no HoH1 import" in pw[0], f"{pw}")

    def sec_citadel(self):
        mark = len(self.g.read_log())
        floors, text = self.citadel_floors()
        halls = [i for i, fid in floors if fid == "dark_halls_1"]
        self.flag("citadel_halls_listed", bool(halls), text[-200:])
        if not halls:
            return
        self.gl("setvar", "cht_god", 1)
        at = len(self.g.read_log())
        r = self.gl("mission", "dark_citadel", halls[0])
        lvl = self.load(at)
        self.flag("citadel_halls_loads", r.get("ok", False) and lvl.startswith("levels/"), f"{r} {lvl!r}")
        time.sleep(3)
        skip = [w for w in self.warnings(at) if "Battlements are skipped" in w]
        self.flag("citadel_halls_warned", len(skip) == 1 and "Lab peer has no HoH1 import" in skip[0], f"{skip}")
        at = len(self.g.read_log())
        self.g.console("cht_finish_level")
        lvl2 = self.load(at)
        self.flag("citadel_next_is_avatar", "boss_avatar" in lvl2, f"{lvl!r} -> {lvl2!r}")
        ok, p = self.alive()
        self.flag("citadel_avatar_player_alive", ok, f"{p}")
        time.sleep(3)
        done = [w for w in self.warnings(at) if "skipped the HoH1 Battlements" in w]
        self.flag("citadel_avatar_warned", len(done) == 1, f"{done}")
        self.flag("citadel_no_hoh1_load", not self.hoh1_loads(mark), f"{self.hoh1_loads(mark)}")
        log = self.g.read_log()[mark:]
        self.flag("citadel_no_script_exception", "Script exception" not in log,
                  f"{[l for l in log.splitlines() if 'exception' in l.lower()][:3]}")
        self.fake("clear")

    def sec_other(self):
        self.fake("clear")
        mark = len(self.g.read_log())
        self.fake("other")
        warns = [w for w in self.warnings(mark) if w.startswith("HoH1 import mismatch")]
        self.flag("other_warned_differs", len(warns) == 1 and "Lab peer's HoH1 import differs" in warns[0], f"{warns}")
        self.fake("clear")

    def sec_silent(self):
        self.fake("clear")
        mark = len(self.g.read_log())
        self.fake("silent")
        early = [w for w in self.warnings(mark) if w.startswith("HoH1 import mismatch")]
        self.flag("silent_not_at_once", not early, f"{early}")
        rep = self.report()
        self.flag("silent_waiting", "waiting for reports" in rep, rep.strip()[-300:])
        time.sleep(11)
        late = [w for w in self.warnings(mark) if w.startswith("HoH1 import mismatch")]
        self.flag("silent_warned_after_timeout", len(late) == 1 and "sent no HoH1 report" in late[0], f"{late}")
        self.fake("clear")

    def sec_match(self):
        mark = len(self.g.read_log())
        self.fake("match")
        warns = self.warnings(mark)
        self.flag("match_no_warning", not warns, f"{warns}")
        rep = self.report()
        self.flag("match_lobby_on", "lobby on" in rep and "(match)" in rep, rep.strip()[-300:])
        text = self.chain()
        self.flag("match_chain_through_battlements", FULL in text, text[-200:])
        self.fake("clear")


def run(p, sections="on,pets,none,citadel,other,silent,match"):
    c = Checks(p)
    for s in [s.strip() for s in sections.split(",")]:
        try:
            getattr(c, "sec_" + s)()
        except Exception as exc:  # a crashed section is a failed section, not a crashed run
            c.flag(s + "_crashed", False, repr(exc))
    c.out["ok"] = bool(c.out) and all(v for v in c.out.values() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
