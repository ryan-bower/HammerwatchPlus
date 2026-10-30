"""hoh1.content off (the default; game night 10.28.26: the host's HoH1 Battlements floor hung
every client on wait_loaded_level): with the HoH1 import packed, no floor loads an HoH1 file.

- town: `hwp hoh1` says `hoh1.content: off` and no feature reports HoH1 content installed;
  the portal offers the HoH2-themed tower (fix_campaign's portal section).
- pets: the Pet Shop lists no HoH1 pet; `hwp set hoh1.content true` puts the HoH1 floors
  back (logged) and lists the pets again, one is bought and out; `hwp set hoh1.content false` puts it away at once (logged), the campaign
  swaps its floors again in town (logged), the shop drops them; on again, the pet is back;
  off once more for the sections after this one.
- citadel: the Dark Citadel's hwp_battlements_1 (its index from `hwp campaign citadel`) loads
  a generated levels/ file; `cht_finish_level` goes on to hwp_battlements_2 (generated too),
  then to dark_halls_boss: the run reaches the Avatar the way the save stuck at floor 21 would.
- tower: floor 0 and the last floor of hwp_forsaken_tower_hoh1 (a save already in it) load
  HoH2 tower files.

Every section also checks no level loaded from hoh1/ (StartLoadServer in the log), and each
floor it loads has no hoh1/ unit near the player (gl near).
"""
import re
import time

from gamelab.bots.fix_campaign import Checks as Campaign

HOH1_PETS = ["imp", "scarab", "beetle", "ladybug", "raven", "magpie", "parrot", "toucan", "cat", "dog",
             "collie", "corgi", "hound", "wyrm", "squire", "flame"]


class Checks(Campaign):
    def hoh1_loads(self, mark):
        return re.findall(r"StartLoadServer (hoh1/[^\s]+)", self.g.read_log()[mark:])

    def load(self, mark, timeout=180):
        """The level file the host loaded after mark (StartLoadServer), once in play: phase
        mission and the player spawned; "" when nothing loaded in time."""
        end = time.time() + timeout
        while time.time() < end:
            hit = re.findall(r"StartLoadServer (\S+)", self.g.read_log()[mark:])
            try:
                st = self.gl("state") if hit else {}
                if st.get("phase") == "mission" and (st.get("player") or {}).get("spawned"):
                    time.sleep(2)
                    return hit[-1]
            except Exception:
                pass
            time.sleep(1)
        return ""

    def hoh1_units(self):
        """HoH1 unit files spawned around the player (an HoH1 theme pulls hoh1/actors and
        hoh1/doodads into a levels/generated.lvl floor; a client without the import lacks them)."""
        r = self.gl("near", 4000, "hoh1/")
        return [u.get("name") for u in r.get("units") or []][:5], r.get("count", 0)

    def no_hoh1_units(self, name):
        names, n = self.hoh1_units()
        self.flag(name, n == 0, f"{n} hoh1/ unit(s): {names}")

    def alive(self):
        p = self.player()
        return bool(p.get("spawned")) and not p.get("dead"), p

    def hidden(self):
        """How many HoH1 pets the pets self-check counted (its off line, else its on line)."""
        m = re.findall(r"\[HWP:pets\] (?:hoh1\.content off: )?(\d+) HoH1 pet\(s\)", self.g.read_log())
        return int(m[-1]) if m else 0

    def pet_units(self):
        """Pet units beside the player (gl near: names under pets/)."""
        time.sleep(0.8)
        return [u for u in self.gl("near", 300, "pets/").get("units") or [] if "pets/" in u.get("name", "")]

    def shop_pets(self):
        """(items, indices of HoH1-looking titles) of the Pet Shop keeper's window; the titles
        only pick one to buy (vanilla has a cat, a raven and a scarab too): counts decide."""
        self.npc("npc_pets", "actors/npcs/town/npc_pets.unit")
        self.gl("use", "npc_pets")
        time.sleep(0.6)
        if not self.gl("wtext", "pet-state").get("missing"):
            self.gl("press", "buy-btn")  # already has a pet: the Buy / Train choice first
            time.sleep(0.6)
        items = self.gl("shop").get("items") or []
        hits = [i for i, it in enumerate(items) if any(w in it.get("title", "").lower().split() for w in HOH1_PETS)]
        return items, hits

    def set_hoh1(self, on):
        return self.hwp(f"set hoh1.content {'true' if on else 'false'}", 0.8, until="hoh1.content =")

    # --- sections
    def sec_town(self):
        rep = self.hwp("hoh1", 0.6, until="hoh1.content")
        self.flag("town_reports_off", "hoh1.content: off" in rep, rep.strip()[-300:])
        self.flag("town_no_feature_installed", "Heroes of Hammerwatch 1 content installed" not in rep, rep.strip()[-300:])
        self.sec_portal()

    def sec_pets(self):
        mark = len(self.g.read_log())
        self.set_gold(200000)
        n = self.hidden()
        off, _ = self.shop_pets()
        self.close_window()
        live = len(self.g.read_log())
        self.set_hoh1(True)
        time.sleep(1.0)
        back = re.findall(r"\[HWP:campaign\] hoh1\.content on: (\d+) HoH1 floor\(s\) back", self.g.read_log()[live:])
        self.flag("campaign_on_restores_live", bool(back) and int(back[-1]) >= 25, f"{back}")  # 23 tower + 2 Battlements
        items, hits = self.shop_pets()
        self.flag("pets_off_shop_lacks_them", n > 0 and bool(off) and len(items) - len(off) == n,
                  f"off {len(off)} entries, on {len(items)}, {n} HoH1 pets imported")
        self.flag("pets_on_listed", len(hits) >= 15, f"{len(hits)} HoH1-looking of {len(items)}")
        pick = next((i for i in hits if "imp" in items[i].get("title", "").lower().split()), hits[0] if hits else None)
        if pick is None:
            self.close_window()
            return
        name = items[pick].get("title", "")
        self.gl("shop", "buy", pick)
        time.sleep(1.5)
        self.close_window()
        st = self.hwp("pet", 0.5, until="level")
        out = self.pet_units()
        self.flag("pets_on_bought", name.split()[0].lower() in st.lower() and bool(out), f"{name}: {out[:1]}")
        live = len(self.g.read_log())
        self.set_hoh1(False)
        time.sleep(1.0)
        log = self.g.read_log()[live:]
        away = re.findall(r"\[HWP:pets\] hoh1\.content off: put away the HoH1 pet (\S+)", log)
        self.flag("pets_off_put_away_live", bool(away), f"{away}")
        gone = self.pet_units()
        self.flag("pets_off_no_pet_unit", bool(out) and not gone, f"{out[:1]} -> {gone[:1]}")
        self.flag("campaign_off_swaps_live", "hoh1.content off: hwp_forsaken_tower_hoh1: " in log
                  and "hoh1.content off: Dark Citadel" in log,
                  " | ".join(l for l in log.splitlines() if "[HWP:campaign]" in l)[-300:])
        again, _ = self.shop_pets()
        self.flag("pets_off_shop_drops_them_live", len(again) == len(off), f"{len(again)} entries, {len(off)} at boot")
        self.close_window()
        live = len(self.g.read_log())
        self.set_hoh1(True)
        time.sleep(1.0)
        back = re.findall(r"\[HWP:pets\] hoh1\.content on: the HoH1 pet (\S+) is back", self.g.read_log()[live:])
        self.flag("pets_on_back", bool(away) and back == away[-1:] and bool(self.pet_units()), f"{away} -> {back}")
        self.set_hoh1(False)
        time.sleep(1.0)
        self.flag("pets_no_hoh1_load", not self.hoh1_loads(mark), f"{self.hoh1_loads(mark)}")

    def sec_citadel(self):
        mark = len(self.g.read_log())
        floors, text = self.citadel_floors()
        ids = [fid for _, fid in floors]
        bat = [i for i, fid in floors if fid == "hwp_battlements_1"]
        self.flag("citadel_order_kept", ids[:5] == ["dark_halls_1", "dark_halls_2", "hwp_battlements_1",
                                                    "hwp_battlements_2", "dark_halls_boss"], f"{ids}")
        if not bat:
            return
        self.gl("setvar", "cht_god", 1)
        at = len(self.g.read_log())
        r = self.gl("mission", "dark_citadel", bat[0])
        self.flag("citadel_mission_started", r.get("ok", False), f"{r}")
        lvl = self.load(at)
        self.flag("citadel_bat1_generated", lvl.startswith("levels/") and "hoh1/" not in lvl, f"index {bat[0]}: {lvl!r}")
        ok, p = self.alive()
        self.flag("citadel_bat1_player_alive", ok, f"{p}")
        self.no_hoh1_units("citadel_bat1_no_hoh1_units")
        time.sleep(1)
        at = len(self.g.read_log())
        self.g.console("cht_finish_level")
        lvl2 = self.load(at)
        self.flag("citadel_bat2_generated", lvl2.startswith("levels/") and "hoh1/" not in lvl2, f"{lvl!r} -> {lvl2!r}")
        self.no_hoh1_units("citadel_bat2_no_hoh1_units")
        time.sleep(1)
        at = len(self.g.read_log())
        self.g.console("cht_finish_level")
        lvl3 = self.load(at)
        self.flag("citadel_reaches_boss", "boss" in lvl3 and "hoh1/" not in lvl3, f"{lvl2!r} -> {lvl3!r}")
        ok, p = self.alive()
        self.flag("citadel_boss_player_alive", ok, f"{p}")
        log = self.g.read_log()[mark:]
        self.flag("citadel_no_hoh1_load", not self.hoh1_loads(mark), f"{self.hoh1_loads(mark)}")
        self.flag("citadel_no_script_exception", "Script exception" not in log,
                  f"{[l for l in log.splitlines() if 'exception' in l.lower()][:3]}")

    def sec_tower(self):
        mark = len(self.g.read_log())
        for floor in (0, 22):
            at = len(self.g.read_log())
            r = self.gl("mission", "hwp_forsaken_tower_hoh1", floor)
            lvl = self.load(at)
            self.flag(f"tower_{floor}_hoh2_file", r.get("ok", False) and bool(lvl) and "hoh1/" not in lvl, f"{r} {lvl!r}")
            self.no_hoh1_units(f"tower_{floor}_no_hoh1_units")
        self.flag("tower_no_hoh1_load", not self.hoh1_loads(mark), f"{self.hoh1_loads(mark)}")


def run(p, sections="town,pets,citadel,tower"):
    c = Checks(p)
    for s in [s.strip() for s in sections.split(",")]:
        try:
            getattr(c, "sec_" + s)()
        except Exception as exc:  # a crashed section is a failed section, not a crashed run
            c.flag(s + "_crashed", False, repr(exc))
    c.out["ok"] = bool(c.out) and all(v for v in c.out.values() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
