"""Every module's switch (module.json config.toggle, the settings page's module rows), turned off
and on again with every package installed, each checked by something the module itself does
in game, not by the stored value. The switch goes through `hwp set <key> false|true`, the same
HWP::Settings write and OnSettingChanged event as the page's row (settings_sweep clicks the
rows themselves).

What each one shows, off then on:
- town units (campaign portal, farm, fishing coast, gambler, notice board, roulette wheel, wave
  statue, way gates, a dye bucket's map icon): the count drops to 0 and comes back to what it was.
  The campaign portal stays until the town is rebuilt (gl townrefresh), as its README says.
- status lines (hwp abyss, architect, autoaim, chatlinks, groupcombo, keys, maps, mercenary,
  mmhmm, pets, specs, strongbox, summons, valuables, weapons, weaponswap): the off text, then
  the on text or its absence.
- effects: colors (a trap arrow's tint), bufftips (a hovered buff's tip, its log line), droptrade
  (the item on top of a Skill Trainer at the feet), firearms (create-character hides the class),
  legacy (the Title Bonuses buff), stash (the sort button), trinkets (the HoH1 trinkets out of the
  drops), tavern (a level 4 tavern's 4th drink slot).
- run: two Bandit Keep floors, every run module off then on, with the chances at 100: abyss
  crack, strongbox, key chest art, objectives, the keep puzzle room; each run ends in a death
  (deathrecap's line, only when on).
- orbwarn: a Firearms character's endless orb picker (mod-orbwarn's setup), the warning lines.
- classes: parked (ClassesModule PARKED), so its switch has nothing to show: only the stored value
  and "parked" are checked.

Flags: off_<module> for each of the 38 (both halves held), off_<module>_run for the run
modules, off_restored (every switch back on, the chances back at their defaults), off_no_errors."""
import json
import re
import time

from gamelab.bots.plan_runs import Checks as Base
from gamelab.bots.plan_ui import PRESETS, TRAP_RAY, near_color
from gamelab.bots.settings_sweep import load

SHRINE = "tweak/buffs/shrine_buffs.sval:damage"
LEGACY = "tweak/hwp/buffs_legacy.sval:hwp_legacy"
DRINKS = re.compile(r"(\d+)/(\d+)")
# a floor's chances, at 100 so the off run's absence means something
CHANCES = {"abyss.chance": 100, "strongbox.chance": 100, "puzzles.room_chance": 100}


class Checks(Base):
    # --- plumbing
    def mark(self):
        return len(self.g.read_log())

    def since(self, mark):
        return self.g.read_log()[mark:]

    def god(self, on):
        if bool(self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")) != on:
            self.hwp("god", 0.4)

    def set(self, key, value):
        out = self.hwp(f"set {key} {value}", 0.3, until=f"] {key} = ")
        return f"] {key} = {value}" in out

    def says(self, cmd, pattern, until="[HWP]"):
        out = self.hwp(cmd, 0.5, until=until)
        lines = [ln.strip() for ln in out.splitlines() if "[HWP]" in ln]
        return re.search(pattern, out) is not None, (lines[-1][-140:] if lines else "(no reply)")

    def logged(self, mark, pattern, timeout=5.0):
        end = time.time() + timeout
        while True:
            m = re.search(pattern, self.since(mark))
            if m or time.time() >= end:
                return m is not None
            time.sleep(0.25)

    def count(self, filt, radius=6000):
        r = self.gl("near", radius, filt)
        return r.get("count", len(r.get("units") or []))

    def errors_since(self, mark):
        return [ln.strip()[:160] for ln in self.since(mark).splitlines()
                if "Script exception" in ln or ("[ERR]" in ln and "HWP" in ln)]

    def toggle(self, mod, key, test, settle=0.6):
        """Off, test("off"), on, test("on"): off_<mod> holds when both halves do."""
        mark = self.mark()
        s_off = self.set(key, "false")
        time.sleep(settle)
        off, n_off = test("off", mark)
        mark = self.mark()
        s_on = self.set(key, "true")
        time.sleep(settle)
        on, n_on = test("on", mark)
        self.flag(f"off_{mod}", s_off and s_on and off and on,
                  f"set {s_off}/{s_on}; off {off}: {n_off} | on {on}: {n_on}")
        return off and on

    # --- the kinds of test
    def status(self, cmd, off_pat, on_pat=None, until="[HWP]"):
        """The off text when off; when on, on_pat, or no off text when on_pat is None."""
        def t(phase, mark):
            if phase == "off":
                return self.says(cmd, off_pat, until)
            if on_pat:
                return self.says(cmd, on_pat, until)
            ok, said = self.says(cmd, off_pat, until)
            return not ok, said
        return t

    def units(self, filt, off_log=None, on_log=None, refresh=False):
        """The module's town units: none when off, as many as before when on."""
        base = self.count(filt)

        def t(phase, mark):
            if phase == "off" and refresh:
                self.gl("townrefresh")
                time.sleep(3)
            pat = off_log if phase == "off" else on_log
            said = self.logged(mark, pat, 6) if pat else True
            want = 0 if phase == "off" else base
            n = self.count(filt)
            end = time.time() + 4
            while n != want and time.time() < end:
                time.sleep(0.5)
                n = self.count(filt)
            return base > 0 and n == want and said, f"{filt} {n} (before {base}), log {said}"
        return t

    # --- town: units and status lines
    def town(self):
        self.mark0 = self.mark()
        self.god(True)
        self.hwp("material gold 300000", 0.3)
        # campaign first: its off half rebuilds the town, which the other unit modules then
        # re-place before they are counted
        self.toggle("campaign", "campaign.enabled",
                    self.units("forsaken_portal", None,
                               r"\[HWP:campaign\] the town was rebuilt, placing doodads/hwp/forsaken_portal\.unit again",
                               refresh=True))
        time.sleep(3)
        self.toggle("farming", "farm.enabled", self.units("farm_plot", r"\[HWP:farming\] turned off: the farm is put away",
                                                          r"\[HWP:farming\] spawned the farm well at"))
        self.toggle("fishing", "fishing.enabled", self.units("fishing_spot", None,
                                                             r"\[HWP:fishing\] coast: \d+ spots; pirate at"))
        self.toggle("gambler", "gambler.enabled", self.units("hwp_gambler", r"\[HWP:gambler\] turned off: took the gambler away",
                                                             r"\[HWP:gambler\] spawned the gambler in the tavern"))
        self.toggle("laststats", "laststats.enabled", self.units("laststats_board", r"\[HWP:laststats\] off: removed the notice board",
                                                                 r"\[HWP:laststats\] spawned the notice board at"))
        self.toggle("roulette", "roulette.enabled", self.units("hwp_roulette_wheel", r"\[HWP:roulette\] turned off: took the wheel away",
                                                               r"\[HWP:roulette\] the wheel is on "))
        self.toggle("wavemode", "wave.enabled", self.units("wave_statue", r"\[HWP:wave\] wave\.enabled off: statue removed",
                                                           r"\[HWP:wave\] the town was rebuilt, placing doodads/hwp/wave_statue\.unit again"))
        self.toggle("waygates", "waygates.enabled", self.units("hwp_waygate", r"\[HWP:waygates\] off: removed the gates",
                                                               r"\[HWP:waygates\] the town was rebuilt, placing the gates again"))
        self.gl("spawn", "items/dyes/dye_bucket_cloth_common.unit", 70, 0)
        time.sleep(2)
        self.toggle("mapicons", "mapicons.enabled", self.units("map_icon_dye"), settle=1.5)

        self.toggle("abyss", "abyss.enabled", self.status("abyss", r"Abyss cracks off:", r"Abyss cracks on:"))
        self.toggle("architect", "architect.enabled", self.status("architect", r"split host cost off", r"split host cost on"))
        self.toggle("autoaim", "autoaim.enabled", self.status("autoaim", r"autoaim: off \(autoaim\.enabled\)",
                                                              r"autoaim: on, mode", until="] autoaim: "))
        self.toggle("chatlinks", "chatlinks.enabled", self.status("link", r"Chat links are off \(HammerwatchPlus tab, Chat links\)\."))
        self.toggle("groupcombo", "groupcombo.enabled", self.status("groupcombo", r"enabled no", r"enabled yes", until="Group combo"))
        self.toggle("keys", "keys.enabled", self.keys_test())
        self.toggle("maps", "maps.enabled", self.status("maps", r"Maps are off: new map drops roll only the vanilla maps\."))
        self.toggle("mercenary", "mercenary.enabled", self.status("merc enlist", r"Mercenary mode is off \(HammerwatchPlus settings"))
        self.toggle("mmhmm", "mmhmm.enabled", self.status("mmhmm", r"\(off: mmhmm\.enabled\)"))
        self.toggle("pets", "pets.enabled", self.status("pet skill x", r"Pet progression is off \(pets\.enabled"))
        self.toggle("specs", "specs.enabled", self.status("specs", r"specs\.enabled off \(not offered at the Subclass Picker\)"))
        self.toggle("strongbox", "strongbox.enabled", self.status("strongbox", r"Strongboxes off:", r"Strongboxes on:"))
        self.toggle("summons", "summons.enabled", self.status("summons", r"Persistent summons off \(", r"Persistent summons on \("))
        self.toggle("valuables", "valuables.enabled", self.status("valuables", r"Valuables are off: they pay their vanilla gold",
                                                                  r"Valuables pay \S+x their vanilla gold"))
        self.toggle("weapons", "weapons.enabled", self.status("weapons", r"Weapons are off: no new one drops",
                                                              r"They drop at \S+x the weight"))
        self.toggle("weaponswap", "weaponswap.enabled", self.swap_test())
        self.toggle("trinkets", "trinkets.enabled", self.trinkets_test())
        self.toggle("classes", "classes.enabled", self.classes_test())

        # effects
        self.toggle("colors", "colors.enabled", self.colors_test())
        self.hwp("colors off", 0.4)
        self.toggle("bufftips", "bufftips.enabled", self.bufftips_test())
        self.toggle("legacy", "legacy.enabled", self.legacy_test(), settle=1.0)
        self.toggle("stash", "stash.enabled", self.stash_test())
        self.close_all()
        self.toggle("firearms", "firearms.enabled", self.firearms_test())
        self.close_all()
        self.toggle("droptrade", "droptrade.enabled", self.droptrade_test())
        self.gl("kill", 300, "npc_skill_trainer")

    def keys_test(self):
        def t(phase, mark):
            ok, said = self.says("keys", r"\[HWP\] keys\.enabled off; ")
            if phase == "off":
                ok2, said2 = self.says("bag buy", r"keys\.enabled is off: no bag slots for sale")
                return ok and ok2, f"{said} / {said2}"
            return not ok, said
        return t

    def swap_test(self):
        def t(phase, mark):
            ok, said = self.says("swap", r"weapon swap is off \(weaponswap\.enabled\)")
            if phase == "off":
                return ok, said
            # on: the command starts the 2 s swap channel; a second one cancels it
            self.hwp("swap", 0.3)
            return not ok, said
        return t

    def trinkets_test(self):
        def t(phase, mark):
            if phase == "off":
                said = self.logged(mark, r"\[HWP:trinkets\] trinkets\.enabled off: \d+ HoH1 trinket\(s\) out of the drops")
                ok, line = self.says("trinkets", r"trinket NG\+ scaling \(off, trinkets\.enabled is off\)")
                return said and ok, f"log {said}, {line}"
            said = self.logged(mark, r"\[HWP:trinkets\] trinkets\.enabled on: \d+ HoH1 trinket\(s\) back in the drops")
            return said, f"log {said}"
        return t

    def classes_test(self):
        def t(phase, mark):
            v = "false" if phase == "off" else "true"
            ok, said = self.says("get classes.enabled", rf"classes\.enabled = {v}")
            parked, line = self.says("classes", r"parked")
            return ok and parked, f"{said}; {line} (parked: the switch has nothing to show)"
        return t

    def colors_test(self):
        self.hwp("colors contrast", 0.4)
        enemy = PRESETS["contrast"][0]

        def t(phase, mark):
            c = (self.gl("shootproj", TRAP_RAY, "none", 0, 1).get("projectile") or {}).get("color") or {}
            time.sleep(0.3)
            tinted = near_color(c, enemy)
            return (not tinted) if phase == "off" else tinted, f"arrow {c}"
        return t

    def bufftips_test(self):
        self.gl("givebuff", SHRINE, -1)
        time.sleep(0.5)

        def t(phase, mark):
            self.gl("mouse", "buff", "buff")
            time.sleep(1.0)
            tip = self.logged(mark, r"\[HWP:bufftips\] tip: ", 1.5)
            self.gl("mouse", "off")
            time.sleep(0.3)
            return tip == (phase == "on"), f"tip logged {tip}"
        return t

    def legacy_test(self):
        # a hero above level 1 gives a title (plan_ui ensure_run, legacy README Testing 2)
        self.hwp("levelup 4", 1.0, until="level")
        time.sleep(1)

        def t(phase, mark):
            r = self.gl("hasbuff", LEGACY)
            has = json.dumps(r)
            got = any(b.get("on") for b in r.get("buffs") or [])
            return got == (phase == "on"), has[:160]
        return t

    def stash_test(self):
        self.g.console("dbg_show_stash")
        time.sleep(1)

        def t(phase, mark):
            time.sleep(0.4)
            r = self.gl("widget", "hwp-stash-sort", 0, "all")
            w = dict(r.get("widget") or {}, count=r.get("count", 0))
            vis = bool(w.get("shown"))
            seen = {k: w.get(k) for k in ("count", "root", "visible", "shown", "x", "y")}
            return vis == (phase == "on") and w.get("count", 0) > 0, f"window {self.window()}, {json.dumps(seen)}"
        return t

    def firearms_test(self):
        def t(phase, mark):
            ok, said = self.says("firearms", r"firearms\.enabled is off: new characters can't pick the class")
            m = self.mark()
            self.gl("charcreate")
            time.sleep(1.5)
            hid = "create-character: hid hwp_firearms" in self.since(m)
            self.close_all()
            if phase == "off":
                return ok and hid, f"{said}; hid {hid}"
            return not ok and not hid, f"{said}; hid {hid}"
        return t

    def droptrade_test(self):
        self.gl("spawn", "actors/npcs/town/npc_skill_trainer.unit", 0, -40)
        self.gl("dropitem", "hwp_rifle_02", "common", 0, -40)
        time.sleep(1)

        def t(phase, mark):
            # walk onto them (a unit spawned on a standing player is no usable until a collision
            # starts: mod-droptrade-pickup), read the top usable, walk back off
            self.gl("input", 300, 0, -1, 0, 1)
            time.sleep(1.5)
            u = self.gl("usables").get("usables") or []
            top = ((u[0].get("unit") or {}).get("name") if u else None)
            first = "[HWP:droptrade] pickup first" in self.since(mark)
            self.gl("input", 300, 0, 1, 0, 1)
            time.sleep(1.0)
            item = top == "items/base.unit"
            ok = (item and first) if phase == "on" else (not item and not first)
            return ok, f"top {top}, pickup-first log {first}, {len(u)} usable(s)"
        return t

    # --- tavern: the 4th drink slot of a level 4 tavern (tavern.enabled read live)
    def wtext(self, wid):
        return (self.gl("wtext", wid).get("texts") or {}).get(wid, "")

    def close_all(self):
        for _ in range(3):
            if not self.window():
                return
            self.g.key("escape")
            time.sleep(0.6)

    def tavern(self):
        self.close_all()
        self.g.console("e_cheats 1")
        self.gl("build", "guild_hall")
        self.g.console("cht_add_all_blueprints")
        self.set_gold(200000)
        lvl = (self.gl("buildings").get("buildings") or {}).get("tavern", -1) + 1
        if lvl < 4:
            self.gl("buildup", "tavern", 4 - lvl)
            time.sleep(4)  # the town reloads
        lvl = (self.gl("buildings").get("buildings") or {}).get("tavern", -1) + 1

        def t(phase, mark):
            self.g.console("mission_start dark_citadel")
            time.sleep(2.5)
            w1 = self.window()
            self.gl("func", "tavern", "open")
            time.sleep(0.8)
            w2 = self.window()
            m = DRINKS.search(self.wtext("drinks"))
            n = int(m.group(2)) if m else None
            self.close_all()
            return n == (3 if phase == "off" else 4), f"tavern level {lvl}, windows {w1}/{w2}, drink slots {n}"
        self.toggle("tavern", "tavern.enabled", t)

    # --- run: two floors, the run modules off then on
    RUN = (("abyss", "abyss.enabled", r"\[HWP:abyss\] placed a crack at", None),
           ("strongbox", "strongbox.enabled", r"\[HWP:strongbox\] placed a strongbox at", None),
           ("keys", "keys.enabled", r"\[HWP:keys\] chest art ", None),
           ("objectives", "objectives.enabled", r"\[HWP:objectives\] placed \d+ vault\(s\), exit switch",
            r"\[HWP:objectives\] objectives\.enabled is off: nothing placed on "),
           ("puzzles", "puzzles.enabled", r"\[HWP:puzzles\] keep_puzzle rolled \(100%\)",
            r"\[HWP:puzzles\] \S+ skipped: puzzles\.enabled is off"),
           ("deathrecap", "deathrecap.enabled", r"\[HWP:deathrecap\] GameLab died: ", None))

    def floor(self, phase):
        self.close_all()
        for _, key, _, _ in self.RUN:
            self.set(key, "false" if phase == "off" else "true")
        mark = self.mark()
        ok = self.start_floor(0)
        time.sleep(8)  # the abyss and strongbox placers decide 3 s into the floor
        # deathrecap: die (god off), the recap line only when on; the death ends the run
        self.god(False)
        self.gl("damageme", 999999)
        end = time.time() + 10
        while not (self.gl("state").get("player") or {}).get("dead") and time.time() < end:
            time.sleep(0.5)
        time.sleep(2)
        log = self.since(mark)
        self.g.key("enter")
        town = self.wait_phase("town", 120)
        time.sleep(2)
        self.close_all()
        self.god(True)
        got = {}
        for mod, _, on_pat, off_pat in self.RUN:
            if phase == "on":
                got[mod] = bool(re.search(on_pat, log))
            else:
                got[mod] = not re.search(on_pat, log) and (not off_pat or bool(re.search(off_pat, log)))
        self.notes.append(f"run {phase}: floor {ok}, back in town {town}, {got}")
        return got

    def run_floors(self):
        for k, v in CHANCES.items():
            self.set(k, v)
        off = self.floor("off")
        on = self.floor("on")
        for mod, *_ in self.RUN:
            self.flag(f"off_{mod}_run", off.get(mod) and on.get(mod), f"off run {off.get(mod)}, on run {on.get(mod)}")

    # --- orbwarn: a Firearms character's endless orb (mod-orbwarn's setup)
    def orbwarn(self):
        self.close_all()
        self.new_char("hwp_firearms", "Orbs")
        time.sleep(2)
        self.g.console("e_cheats 1")
        self.hwp("levelup 20", 1.0, until="level")
        self.hwp("skillpoints 40", 0.5)
        self.gl("skill", "hwp_fs_frag", 1)
        self.gl("spawn", "gamelab/skill_sphere_endless.unit", 0, 0)
        time.sleep(1)

        def t(phase, mark):
            self.gl("spherepicks", "hwp_fs_frag_stun", "hwp_fs_frag_shrapnel", "hwp_fs_frag_gas")
            m = self.mark()
            w = self.gl("use", "GameLabEndless").get("window")
            time.sleep(1.5)
            said = bool(re.search(r"\[HWP:orbwarn\] pick 1 \(", self.since(m)))
            self.close_all()
            return said == (phase == "on"), f"window {w}, pick lines {said}"
        self.toggle("orbwarn", "orbwarn.enabled", t)

    # --- after: every switch on, the chances at their defaults
    def restore(self):
        _, pkgs = load()
        defaults = {s["key"]: s["default"] for _, mods in pkgs for _, cfg in mods for s in cfg.get("settings", [])
                    if "key" in s}
        for k in CHANCES:
            self.set(k, defaults[k])
        st = dict(re.findall(r"\[HWP\] ([\w.]+) = (\S+)", self.hwp("settings", 1.0, until="] ")))
        toggles = [cfg["toggle"] for _, mods in pkgs for _, cfg in mods if cfg.get("toggle")]
        off = [k for k in toggles if st.get(k, "true") != "true"]
        moved = [k for k in CHANCES if k in st and float(st[k]) != float(defaults[k])]
        self.flag("off_restored", not off and not moved, f"still off {off}, chances moved {moved}")
        errs = self.errors_since(getattr(self, "mark0", 0))
        self.flag("off_no_errors", not errs, "; ".join(errs[:8]))


def run(p, sections="town,tavern,run_floors,orbwarn,restore", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
