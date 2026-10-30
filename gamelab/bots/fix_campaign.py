"""The campaign module's 10.22.26 items (mods/campaign/README.md, scenarios fix-campaign-*):

- portal (town, host, cheats on): once the story intro flag is set, the chapel portal's
  picker lists the HoH1 mission (hwp_forsaken_tower_hoh1) alone when the import is packed,
  and the log says `portal: offering ... (HoH1 levels)`; without the import it lists the
  HoH2-themed tower and says `(HoH2 themes)`.
- citadel: `hwp campaign citadel` replies the Dark Citadel floors from the first Dark Halls
  on, as `index:id`; with the import: dark_halls_1, dark_halls_2, hwp_battlements_1,
  hwp_battlements_2, dark_halls_boss in that order; without: the vanilla list and a
  `(HoH1 import absent)` line.
- battlements: loads the first Battlements floor of the Dark Citadel (its mission index
  from `hwp campaign citadel`) and checks the level file is the HoH1 one.
- traps (in a generated indoor floor): `traps: placed N/M` with N > 0, trap units present
  (`gl unitsof`), and standing on a spike floor (or a bomb glyph's blast) costs health.
- teleporter (same floor): the pad the log placed (or a cheat pad) moves the player to the
  logged destination on `gl use teleport_pad`, and a second use lands on the same spot.
- confusion: `hwp campaign confuse 4000` puts tweak/hwp/campaign_buffs.sval:hwp_confusion
  on the player, holding right moves the player left while it lasts and right again after;
  a confusion glyph spawned under the player applies the 1 s trap buff.

Sections: all (the default), or any of portal, citadel, battlements, traps, teleporter,
confusion. The result carries `battlements_index` for scenarios.
"""
import re
import time

from gamelab.bots.plan_checks import Checks as Base

HOH1 = "hwp_forsaken_tower_hoh1"
BUFF = "tweak/hwp/campaign_buffs.sval:hwp_confusion"
TRAP_BUFF = "tweak/hwp/campaign_buffs.sval:hwp_trap_confusion"
TRAP_UNITS = [
    "doodads/traps/floors/floor_spikes.unit",
    "doodads/traps/floors/floor_fire.unit",
    "doodads/hwp/traps/hwp_glyph_bomb.unit",
    "doodads/hwp/traps/hwp_glyph_dart.unit",
    "doodads/hwp/traps/hwp_glyph_confusion.unit",
]
ORDER = ["dark_halls_1", "dark_halls_2", "hwp_battlements_1", "hwp_battlements_2", "dark_halls_boss"]


class Checks(Base):
    # --- helpers
    def player(self):
        return self.gl("state").get("player") or {}

    def pos(self):
        p = self.player()
        return float(p.get("x", 0)), float(p.get("y", 0))

    def has_buff(self, path):
        r = self.gl("hasbuff", path)
        for b in r.get("buffs") or []:
            if b.get("path") == path:
                return bool(b.get("on")), int(b.get("left") or 0)
        return False, 0

    def close_window(self):
        if self.gl("state").get("window"):
            self.g.key("escape")
            time.sleep(0.5)

    def citadel_floors(self):
        """[(index, id)] from `hwp campaign citadel`."""
        log = self.hwp("campaign citadel", 0.6, until="Dark Citadel")
        line = [l for l in log.splitlines() if "Dark Citadel" in l]
        text = line[-1] if line else ""
        # only the list after "Dark Citadel: " (the log timestamp "[00:00:15]" also matches d+:w+,
        # fix-campaign-portal-version 20261025-235953); the indices are the run's, 19.. for the citadel
        floors = text.split("Dark Citadel: ", 1)[-1].split("; chain")[0] if "Dark Citadel: " in text else text
        return [(int(i), fid) for i, fid in re.findall(r"(\d+):(\w+)", floors)], text

    def hoh1_imported(self):
        """The HoH1 import is packed: the Battlements floors are in the citadel list."""
        floors, _ = self.citadel_floors()
        return any(fid == "hwp_battlements_1" for _, fid in floors)

    # --- sections
    def sec_portal(self):
        p = self.gl("near", 8000, "forsaken_portal").get("units") or []
        self.flag("portal_in_town", bool(p), f"{p[:1]}")
        if not p:
            return
        self.gl("teleport", p[0]["x"], p[0]["y"] + 50)
        time.sleep(1)
        self.g.console("cht_set_flag mission_story_intro_find_npcs 1 0")
        time.sleep(0.5)
        mark = len(self.g.read_log())
        u = self.gl("use", "forsaken_portal")
        time.sleep(0.8)
        log = self.g.read_log()[mark:]
        items = self.gl("shop").get("items") or []
        titles = [(it.get("title", ""), it.get("sub", "")) for it in items]
        imported = self.hoh1_imported()
        offering = re.findall(r"portal: offering ([^\r\n]*)", log)
        self.flag("portal_opens", u.get("ok") and bool(items), f"{u.get('window')}: {titles}")
        self.flag("portal_logs_version", bool(offering), f"{offering[-1:]}")
        if imported:
            self.flag("portal_offers_hoh1_only", len(items) == 1 and any("hoh1" in t.lower() for t, _ in titles)
                      and offering and HOH1 in offering[-1] and "HoH1 levels" in offering[-1],
                      f"{titles}; {offering[-1:]}")
        else:
            self.flag("portal_offers_tower_without_import", len(items) >= 1 and offering and "HoH2 themes" in offering[-1],
                      f"{titles}; {offering[-1:]}")
        self.close_window()

    def sec_citadel(self):
        floors, text = self.citadel_floors()
        ids = [fid for _, fid in floors]
        self.flag("citadel_replies", bool(floors), text[-300:])
        if not floors:
            return
        imported = "hwp_battlements_1" in ids
        if imported:
            want = ORDER
            self.flag("citadel_two_halls_two_battlements", ids[:5] == want, f"{ids}")
            halls = [i for i, fid in floors if fid == "dark_halls_1"]
            bat = [i for i, fid in floors if fid == "hwp_battlements_1"]
            self.flag("citadel_battlements_after_halls", bool(halls and bat) and bat[0] == halls[0] + 2, f"halls {halls} battlements {bat}")
            self.out["battlements_index"] = bat[0] if bat else -1
            self.flag("citadel_chain", "chain dark_halls_1 -> dark_halls_2 -> hwp_battlements_1 -> hwp_battlements_2 -> dark_halls_boss" in text, text[-200:])
        else:
            self.flag("citadel_vanilla_fallback_logged", "HoH1 import absent" in text and ids[:2] == ["dark_halls_1", "dark_halls_boss"], f"{ids}; {text[-200:]}")
            self.out["battlements_index"] = -1

    def sec_battlements(self):
        floors, text = self.citadel_floors()
        bat = [i for i, fid in floors if fid == "hwp_battlements_1"]
        self.out["battlements_index"] = bat[0] if bat else -1
        self.flag("battlements_in_citadel", bool(bat), text[-200:])
        if not bat:
            return
        mark = len(self.g.read_log())
        r = self.gl("mission", "dark_citadel", bat[0])
        self.flag("battlements_mission_started", r.get("ok", False), f"{r}")
        ok = self.wait_phase("mission", 180)
        st = self.gl("state")
        level = st.get("level", "")
        self.flag("battlements_level_loaded", ok and "battlements_1" in level and "hoh1/" in level, f"phase {st.get('phase')} level {level!r}")
        time.sleep(3)
        log = self.g.read_log()[mark:]
        self.flag("battlements_no_script_exception", "Script exception" not in log and "Failed to open" not in log,
                  f"{[l for l in log.splitlines() if 'exception' in l.lower() or 'Failed' in l][:3]}")
        p = self.player()
        self.flag("battlements_player_alive", p.get("spawned") and not p.get("dead"), f"{p}")

    def sec_traps(self):
        log = self.g.read_log()
        placed = re.findall(r"traps: placed (\d+)/(\d+) on a (\d+x\d+) floor", log)
        self.flag("traps_placed_logged", bool(placed) and int(placed[-1][0]) > 0, f"{placed[-1:]}")
        r = self.gl("unitsof", *TRAP_UNITS)
        counts = {u.split("/")[-1]: (r.get(u) or {}).get("count", 0) for u in TRAP_UNITS}
        total = sum(counts.values())
        self.flag("traps_present", total > 0, f"{counts}")
        # a spike floor (always on) or a flame jet (activates when stood on), else a bomb glyph
        spikes = (r.get(TRAP_UNITS[0]) or {}).get("units") or []
        fires = (r.get(TRAP_UNITS[1]) or {}).get("units") or []
        before = self.player()
        hp0 = before.get("hp", 0)
        if spikes or fires:
            t = (spikes or fires)[0]
            self.gl("teleport", t["x"], t["y"])
            how = "spikes" if spikes else "fire"
        else:
            self.gl("spawn", "doodads/hwp/traps/hwp_glyph_bomb.unit", 0, 0)
            how = "bomb glyph"
        # traps kill a level-1 paladin in about a second (spikes tick fast, the jet burns):
        # poll and leave at the first lost hit point, at most 4 s
        after = self.player()
        hp1 = after.get("hp", 0)
        for _ in range(16):
            if hp1 < hp0 or after.get("dead"):
                break
            time.sleep(0.25)
            after = self.player()
            hp1 = after.get("hp", 0)
        self.flag("trap_damages", hp0 > 0 and (hp1 < hp0 or after.get("dead")), f"{how}: hp {hp0} -> {hp1} dead {after.get('dead')}")
        # step off and heal (hurt <fraction> writes PlayerRecord.hp), so the next section has a live player
        x, y = self.pos()
        self.gl("teleport", x + 96, y)
        time.sleep(0.3)
        self.gl("hurt", 1.0)
        time.sleep(0.3)

    def usable(self, text):
        """The `usables` entry whose unit json mentions text, else None."""
        for u in self.gl("usables").get("usables") or []:
            if text in str(u.get("unit")) or text in str(u):
                return u
        return None

    def onto_pad(self, px, py):
        """Stand next to the pad: `gl use <filter>` acts on the nearest matching unit from
        wherever the player stands (`usables` never lists the pad after a teleport: the
        static sensor sees no overlap begin), so a short step towards it is enough."""
        self.gl("teleport", px, py + 28)
        time.sleep(0.5)
        self.gl("input", 120, 0, -1)
        time.sleep(0.4)

    def sec_teleporter(self):
        log = self.g.read_log()
        pads = re.findall(r"teleporter placed at (-?\d+),(-?\d+) \(cell [^)]*\) -> (-?\d+),(-?\d+)", log)
        if pads:
            px, py, dx, dy = (int(v) for v in pads[-1])
            how = "generated"
        else:
            reply = self.hwp("campaign teleporter 240 0", 0.8, until="teleport pad")
            m = re.findall(r"teleport pad \d+ at (-?\d+),(-?\d+) -> (-?\d+),(-?\d+)", reply)
            if not m:
                self.flag("teleporter_available", False, f"no pad placed and no cheat pad: {reply[-200:]!r}")
                return
            px, py, dx, dy = (int(v) for v in m[-1])
            how = "cheat"
        self.flag("teleporter_available", True, f"{how} pad {px},{py} -> {dx},{dy}")
        # the pad sits among the floor's enemies: a level-1 paladin died twice on the way
        # onto it, so god mode (cheats on) for the walk and the two uses
        self.gl("hurt", 1.0)
        self.hwp("god", 0.3)
        self.onto_pad(px, py)
        u = self.gl("use", "teleport_pad")
        time.sleep(1.0)
        x1, y1 = self.pos()
        d1 = ((x1 - dx) ** 2 + (y1 - dy) ** 2) ** 0.5
        self.flag("teleporter_jumps", u.get("ok", False) and d1 < 48, f"use {u.get('unit')}; landed {x1:.0f},{y1:.0f}, {d1:.0f} px from {dx},{dy}")
        self.onto_pad(px, py)
        self.gl("use", "teleport_pad")
        time.sleep(1.0)
        x2, y2 = self.pos()
        d2 = ((x2 - dx) ** 2 + (y2 - dy) ** 2) ** 0.5
        # the pad's fixed spot is the logged "-> x,y" of each use; where the player stands a
        # second later can differ by a few px (enemies at the spot push them; 13 and 16 px
        # in two runs), so the positions are only checked against the 48 px landing radius
        uses = re.findall(r"teleporter: \S+ -?\d+,-?\d+ -> (-?\d+),(-?\d+) \(use", self.g.read_log()[len(log):])
        same = len(uses) >= 2 and uses[-1] == uses[-2] == (str(dx), str(dy))
        self.flag("teleporter_same_spot", d1 < 48 and d2 < 48 and same,
                  f"second landing {x2:.0f},{y2:.0f}, {((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5:.1f} px from the first, {d2:.0f} from {dx},{dy}; logged uses {uses[-2:]}")
        self.flag("teleporter_logged", bool(uses), "")

    def sec_confusion(self):
        self.hwp("campaign confuse 4000", 0.8, until="confused")
        on, left = self.has_buff(BUFF)
        self.flag("confusion_buff_on", on and 0 < left <= 4000, f"on {on} left {left}")
        x0, _ = self.pos()
        self.gl("input", 700, 1, 0)
        time.sleep(1.4)
        x1, _ = self.pos()
        self.flag("confusion_inverts_input", on and x1 < x0 - 8, f"held right: x {x0:.0f} -> {x1:.0f}")
        time.sleep(3.2)
        on2, _ = self.has_buff(BUFF)
        x2, _ = self.pos()
        self.gl("input", 700, 1, 0)
        time.sleep(1.4)
        x3, _ = self.pos()
        self.flag("confusion_expires", not on2 and x3 > x2 + 8, f"buff on {on2}; held right: x {x2:.0f} -> {x3:.0f}")
        # the trap buff from a confusion glyph under the player (TripMine, 20 px trigger)
        mark = len(self.g.read_log())
        self.gl("spawn", "doodads/hwp/traps/hwp_glyph_confusion.unit", 0, 0)
        got = False
        end = time.time() + 4
        while time.time() < end and not got:
            got, _ = self.has_buff(TRAP_BUFF)
            if not got:
                time.sleep(0.3)
        self.flag("confusion_trap_applies", got, f"log: {self.g.read_log()[mark:][-200:]!r}")
        time.sleep(1.5)


def run(p, sections="all"):
    c = Checks(p)
    want = ["portal", "citadel", "battlements", "traps", "teleporter", "confusion"] if sections == "all" else [s.strip() for s in sections.split(",")]
    for s in want:
        fn = getattr(c, "sec_" + s, None)
        if fn is None:
            c.flag("unknown_section_" + s, False, "")
            continue
        try:
            fn()
        except Exception as e:  # a failed read must not hide the other sections
            c.flag(s + "_raised", False, repr(e))
    c.out["ok"] = all(v for k, v in c.out.items() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
