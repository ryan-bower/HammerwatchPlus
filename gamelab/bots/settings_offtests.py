"""Every module's switch (module.json config.toggle, the settings page's module rows), turned off
and on again with every current feature and required library loaded. Results explicitly
separate native effects/UI/unit counts from status-only and authored parked-policy checks.
Goldworth and libraries have no toggle and receive N/A, never an invented off-effect pass. The switch goes through `hwp set <key> false|true`, the same
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

Flags: scoped off_<module> or off_<module>_run rows, plus source applicability accounting.
The returned applicability table records each row's exact evidence kind and remaining limits.
No aggregate complete-functionality claim is supplied."""
import json
import math
import re
import time

from gamelab.bots.plan_runs import Checks as Base
from gamelab.bots.plan_ui import PRESETS, TRAP_RAY, near_color
from gamelab.bots.settings_sweep import load, same, OPTION_SETTINGS
from gamelab.bots.plan_pets import Checks as PetChecks, TRAP_UNIT, FLOOR_TRAPS

SHRINE = "tweak/buffs/shrine_buffs.sval:damage"
LEGACY = "tweak/hwp/buffs_legacy.sval:hwp_legacy"
DRINKS = re.compile(r"(\d+)/(\d+)")
# a floor's chances, at 100 so the off run's absence means something
CHANCES = {"abyss.chance": 100, "strongbox.chance": 100, "puzzles.room_chance": 100}

# Pin one base-game producer, not the MiniPet default: the generated Dog unit
# explicitly sets range-idle=90 and leash-range=100. A frozen-source producer/type
# readback is required before this contract applies; other pets refuse setup.
PETROOMS_PET = {"title": "Dungeoneer's Mutt", "resource": "players/pets/pet_dog.unit",
                "behavior": "HWPMiniPetWalking", "idle_range": 90,
                "leash_range": 100, "on_margin": 30}
# The pet parks a radius short of the spikes and the player stops this far short of them, so
# the gap between them is the difference, which the 130 px on-window needs to clear.
PETROOMS_RADIUS = 180  # one of the setting's values
PETROOMS_SHORT = 32
PETROOMS_STEP_BACK = 15  # a small step, or the player closes on the parked pet
PETROOMS_SEED = 2463240320  # a floor with a straight corridor from the start

# This is evidence applicability, not a declaration that every module is functionally tested.
FEATURE_CONTRACTS = {'abyss': {'kind': 'status-and-floor-log',
           'limit': 'Existing status plus off/on generated-floor log; not clear/reward or exact payload proof.'},
 'affixes': {'kind': 'controlled-generator',
             'limit': '24 generated Epic items at forced 100% chance off/on; saved-item extras and acquisition '
                      'remain separate.'},
 'architect': {'kind': 'status-only',
               'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified '
                        'here.'},
 'attrclick': {'kind': 'controlled-assignment',
               'limit': 'Forced Shift plus native trainer Buy; actual pickedStr/free-point delta 1 off versus 20 '
                        'on, not physical modifier input proof.'},
 'autoaim': {'kind': 'status-only',
             'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'bufftips': {'kind': 'ui-or-native-effect',
              'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'campaign': {'kind': 'town-unit-count',
              'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                       'separate.'},
 'chatlinks': {'kind': 'status-only',
               'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified '
                        'here.'},
 'classes': {'kind': 'parked-policy',
             'limit': 'Authored Classes::PARKED=true keeps new class offers hidden on both switch values; this is '
                      'stored value/parked-policy evidence, not an on-effect pass.'},
 'colors': {'kind': 'ui-or-native-effect',
            'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'deathrecap': {'kind': 'floor-log',
                'limit': 'Existing generated-floor/death log; not every lifecycle/reward/UI consumer.'},
 'droptrade': {'kind': 'ui-or-native-effect',
               'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'farming': {'kind': 'town-unit-count',
             'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                      'separate.'},
 'firearms': {'kind': 'ui-or-native-effect',
              'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'fishing': {'kind': 'town-unit-count',
             'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                      'separate.'},
 'gambler': {'kind': 'town-unit-count',
             'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                      'separate.'},
 'goldworth': {'kind': 'not-applicable',
               'limit': 'Data only; config.toggle is null and always_on supplies the authored reason.'},
 'groupcombo': {'kind': 'status-only',
                'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified '
                         'here.'},
 'keys': {'kind': 'status-and-floor-log',
          'limit': 'Existing status plus off/on generated-floor log; not clear/reward or exact payload proof.'},
 'laststats': {'kind': 'town-unit-count',
               'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                        'separate.'},
 'legacy': {'kind': 'ui-or-native-effect',
            'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'mapicons': {'kind': 'town-unit-count',
              'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                       'separate.'},
 'maps': {'kind': 'status-only',
          'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'mercenary': {'kind': 'status-only',
               'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified '
                        'here.'},
 'mmhmm': {'kind': 'status-only',
           'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'objectives': {'kind': 'floor-log',
                'limit': 'Existing generated-floor/death log; not every lifecycle/reward/UI consumer.'},
 'orbwarn': {'kind': 'ui-or-native-effect',
             'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'salvage': {'kind': 'status-only',
  'limit': 'Status line only here; the item action is not exercised by this toggle.'},
 'freeskills': {'kind': 'status-only',
  'limit': 'Status line only here; the respec refund is not exercised by this toggle.'},
 'partyexit': {'kind': 'status-only',
  'limit': 'Status line only here; the floor exit vote is not exercised by this toggle.'},
 'partyframes': {'kind': 'status-only',
                 'limit': 'Status line only here; the drawing is checked by the mod-partyframes screenshots.'},
 'petrooms': {'kind': 'controlled-pet-movement',
              'limit': 'Checked trap-room route, actual pet follows off and parks on; controlled setup, not '
                       'standalone vanilla-pet/coop/ordinary proof.'},
 'pets': {'kind': 'status-only',
          'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'puzzles': {'kind': 'floor-log',
             'limit': 'Existing generated-floor/death log; not every lifecycle/reward/UI consumer.'},
 'roulette': {'kind': 'town-unit-count',
              'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                       'separate.'},
 'specs': {'kind': 'status-only',
           'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'stash': {'kind': 'ui-or-native-effect',
           'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'strongbox': {'kind': 'status-and-floor-log',
               'limit': 'Existing status plus off/on generated-floor log; not clear/reward or exact payload '
                        'proof.'},
 'summons': {'kind': 'status-only',
             'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'tavern': {'kind': 'ui-or-native-effect',
            'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'trinkets': {'kind': 'ui-or-native-effect',
              'limit': 'Checks the existing named UI/effect consumer only; not complete feature functionality.'},
 'valuables': {'kind': 'status-only',
               'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified '
                        'here.'},
 'wavemode': {'kind': 'town-unit-count',
              'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                       'separate.'},
 'waygates': {'kind': 'town-unit-count',
              'limit': 'Counts the named spawned units only; provider UI, payment and ordinary lifecycle remain '
                       'separate.'},
 'weapons': {'kind': 'status-only',
             'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified here.'},
 'weaponswap': {'kind': 'status-only',
                'limit': 'Command refusal/status changes only; functional off/on consumers remain unverified '
                         'here.'}}


class Checks(Base):
    def __init__(self, p):
        super().__init__(p)
        self._owned_settings = {}
        self._owned_defaults = {}
        self._cleanup_errors = []
        self._original_errors = []

    # --- plumbing
    def mark(self):
        return len(self.g.read_log())

    def since(self, mark):
        return self.g.read_log()[mark:]

    def god(self, on):
        if bool(self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")) != on:
            self.hwp("god", 0.4)

    def prepare_owned_settings(self):
        _, pkgs = load()
        toggles = []
        for _, mods in pkgs:
            for mod, cfg in mods:
                if cfg.get("toggle"):
                    toggles.append(cfg["toggle"])
                    self._owned_defaults[cfg["toggle"]] = True
                for setting in cfg.get("settings", []):
                    if "key" in setting:
                        self._owned_defaults[setting["key"]] = setting["default"]
        # Existing colors_test changes the source preset; own its effective values.
        self._owned_defaults.update(OPTION_SETTINGS["colors"])
        for key, default in self._owned_defaults.items():
            initial = self.setting_value(key, default)
            self._owned_settings[key] = {"initial": initial, "default": default}
            if isinstance(initial, str) and any(c.isspace() for c in initial):
                raise RuntimeError(f"unrestorable one-token setting fixture: {key}={initial!r}")
        initial_off = [key for key in toggles if not self.same_setting(self._owned_settings[key]["initial"], True)]
        self.flag("off_initial_enabled", not initial_off, f"fresh-On precondition: {initial_off}")
        if initial_off:
            raise RuntimeError("fixture has authored off choices; refuse mutation")

    @staticmethod
    def same_setting(actual, expected):
        text = str(actual).lower() if isinstance(actual, bool) else str(actual)
        return same(text, expected)

    def cleanup_step(self, label, action):
        try:
            action()
            return True
        except Exception as exc:
            row = {"operation": label, "error": repr(exc)}
            self._cleanup_errors.append(row)
            self.notes.append(f"cleanup failed: {row}")
            return False

    def restore_owned_setting(self, key):
        snapshot = self._owned_settings[key]
        initial, default = snapshot["initial"], snapshot["default"]
        current = self.setting_value(key, default)  # reconcile any uncertain earlier dispatch
        if self.same_setting(current, initial):
            return
        if initial == "":
            raise RuntimeError(f"cannot restore empty {key!r} through CmdSet; no guessed reset")
        text = str(initial).lower() if isinstance(initial, bool) else str(initial)
        self.hwp(f"set {key} {text}", 0.2, until=f"] {key} = ")  # one dispatch only
        after = self.setting_value(key, default)
        if not self.same_setting(after, initial):
            raise RuntimeError(f"restore differs for {key}: {after!r}, initial {initial!r}")

    def cleanup_owned_settings(self):
        self.cleanup_step("close owned lab windows", self.close_all)
        for key in reversed(self._owned_settings):
            self.cleanup_step(f"restore {key}", lambda key=key: self.restore_owned_setting(key))
        self.out["owned_initial_settings"] = self._owned_settings
        self.out["cleanup_failures"] = self._cleanup_errors
        self.out["original_failures"] = self._original_errors

    def set(self, key, value):
        if key not in self._owned_settings:
            raise RuntimeError(f"setting was not snapshotted before mutation: {key}")
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
        """Both halves plus unconditional restoration; original exceptions stay primary."""
        current = self.setting_value(key, self._owned_settings[key]["default"])
        if not self.same_setting(current, True):
            self.flag(f"off_{mod}", False, f"toggle did not start On: {current!r}; no mutation")
            return False
        s_off = s_on = off = on = False
        n_off = n_on = "not attempted"
        clean = False
        try:
            mark = self.mark()
            s_off = self.set(key, "false")
            time.sleep(settle)
            off, n_off = test("off", mark)
            mark = self.mark()
            s_on = self.set(key, "true")
            time.sleep(settle)
            on, n_on = test("on", mark)
        except Exception as exc:
            self._original_errors.append({"stage": f"toggle:{mod}", "error": repr(exc)})
            self.flag(f"off_{mod}", False, f"original failure: {exc!r}")
            raise
        finally:
            clean = self.cleanup_step(f"{mod} restore enabled", lambda: self.restore_owned_setting(key))
            self.flag(f"off_{mod}_cleanup", clean, "independent read before any restore write")
        passed = s_off and s_on and off and on and clean
        self.flag(f"off_{mod}", passed,
                  f"set {s_off}/{s_on}; off {off}: {n_off} | on {on}: {n_on}; cleanup {clean}")
        return passed

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
        self.toggle("partyframes", "partyframes.enabled", self.status("partyframes", r"partyframes\] off, ",
                                                                      r"partyframes\] on, ", until="partyframes] o"))
        self.toggle("salvage", "salvage.enabled", self.status("salvage", r"salvage: off", r"salvage: on", until="salvage: o"))
        self.toggle("freeskills", "freeskills.enabled", self.status("freeskills", r"free skills off;", r"free skills on;", until="free skills o"))
        self.toggle("partyexit", "partyexit.enabled", self.status("partyexit", r"party exit off,", r"party exit on,", until="party exit o"))
        self.toggle("autoaim", "autoaim.enabled", self.status("autoaim", r"autoaim: off \(autoaim\.enabled\)",
                                                              r"autoaim: on, mode", until="] autoaim: "))
        self.toggle("chatlinks", "chatlinks.enabled", self.status("link", r"Chat links are off \(HammerwatchPlus tab, Chat links\)\.", until="[HWP"))
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
        self.droptrade()
        self.affixes()
        self.attrclick()
        self.gl("kill", 300, "npc_skill_trainer")

    def setting_value(self, key, default):
        log = self.hwp(f"get {key}", 0.15, until=f"] {key} = ")
        rows = re.findall(r"\[HWP\] " + re.escape(key) + r" = ([^\r\n]*)", log)
        if not rows:
            raise RuntimeError(f"missing setting readback: {key}")
        return default if rows[-1].strip() == "(unset)" else rows[-1].strip()

    def affixes(self):
        # Actual generator results, fixed bounded trial count, no probabilistic rates. Level 10
        # because the Back slot has no base item below it, so level 1 can only make 21 of 24.
        _, pkgs = load()
        default = next(s["default"] for _, mods in pkgs for mod, cfg in mods if mod == "affixes"
                       for s in cfg["settings"] if s.get("key") == "affixes.chance")
        original = self.setting_value("affixes.chance", default)
        pattern = re.compile(r"roll: (\d+) epic at ilvl 10 \(chance ([^)]*)\): second suffix (\d+), "
                             r"second prefix (\d+), max mods (\d+), over two (\d+), duplicates (\d+), two skills (\d+)")
        def check(phase, mark):
            out = self.hwp("affixes roll 24 epic 10", 0.3, until="[HWP] roll:")
            rows = pattern.findall(out)
            if not rows:
                return False, "no generator result; no consumer credit"
            made, chance, suffixes, prefixes, max_mods, over, duplicates, skills = rows[-1]
            made, suffixes, prefixes, max_mods, over, duplicates, skills = map(int,
                (made, suffixes, prefixes, max_mods, over, duplicates, skills))
            if phase == "off":
                effect = chance == "off" and suffixes == prefixes == 0 and max_mods == 3
            else:
                effect = chance == "100%" and suffixes == prefixes == made and max_mods == 5
            return made == 24 and effect and over == duplicates == skills == 0, str(rows[-1])
        try:
            self.set("affixes.chance", 100)
            self.toggle("affixes", "affixes.enabled", check)
        finally:
            self.cleanup_step("affixes restore chance", lambda: self.restore_owned_setting("affixes.chance"))

    def attr_state(self):
        out = self.hwp("attrclick", 0.2, until="[HWP] attribute clicks")
        rows = re.findall(r"a click places (\d+) \((keys|shift|ctrl|none)\); (\d+) point\(s\) to place, "
                          r"picked str (\d+), dex (\d+), int (\d+), foc (\d+), vit (\d+)", out)
        if not rows:
            raise RuntimeError("attribute record readback missing")
        n, force, free, *picked = rows[-1]
        return {"per_click": int(n), "force": force, "free": int(free), "picked": list(map(int, picked))}

    def attrclick(self):
        self.close_all()
        original_force = self.attr_state()["force"]
        self.hwp("statpoints 40", 0.2, until="attribute points")
        spawn = self.gl("spawn", "actors/npcs/town/npc_attrib_trainer.unit", 0, -40)
        opened = self.gl("use", "npc_attrib_trainer") if spawn.get("ok") else {}
        setup = opened.get("window") == "HWPAttributeAssignerWindow"
        self.flag("off_attrclick_setup", setup, f"spawn {spawn}; opened {opened}")
        if not setup:
            self.flag("off_attrclick", False, "no swapped trainer window; no assignment consumer credit")
            return
        def check(phase, mark):
            before = self.attr_state()
            press = self.gl("press", "strength")
            time.sleep(0.3)
            after = self.attr_state()
            want = 1 if phase == "off" else 20
            other_same = before["picked"][1:] == after["picked"][1:]
            effect = (press.get("window") == "HWPAttributeAssignerWindow" and before["free"] >= want
                      and before["free"] - after["free"] == want
                      and after["picked"][0] - before["picked"][0] == want and other_same)
            return effect, f"forced Shift/native Buy: {before} -> {after}"
        try:
            self.hwp("attrclick force shift", 0.2, until="[HWP] attribute clicks")
            self.toggle("attrclick", "attrclick.enabled", check)
        finally:
            self.cleanup_step("attrclick restore force", lambda: self.hwp(
                f"attrclick force {original_force}", 0.2, until="[HWP] attribute clicks"))
            self.cleanup_step("attrclick close owned window", self.close_all)

    def petrooms(self):
        """One bound pet, explicit native routes and a disposable owned fixture floor."""
        self.close_all()
        c = PetChecks(self.p)
        trace = {"candidate_paths": [], "routes": [], "pet_samples": [], "spawns": [],
                 "owned_trap_ids": [], "preexisting_pressure_ids": [], "cleanup": {}}
        self.out["petrooms_trace"] = trace
        setup = off_effect = on_effect = off_set = on_set = False
        dog_ready = on_geometry = False
        minimum_on_gap = max(PETROOMS_PET["idle_range"], PETROOMS_PET["leash_range"]) + PETROOMS_PET["on_margin"]
        trace["pet_source_contract"] = dict(PETROOMS_PET, minimum_on_gap=minimum_on_gap)
        pet_id = pet_name = None
        preexisting_ids = set()
        fixture_started = False

        def pressure_snapshot():
            raw = self.gl("unitsof", TRAP_UNIT)
            row = raw.get(TRAP_UNIT) or {}
            units = row.get("units") or []
            if not raw.get("ok") or not row.get("found") or row.get("count") != len(units):
                raise RuntimeError(f"pressure-unit readback missing or capped: {raw}")
            return raw, units

        def bound_pet(stage):
            raw = self.gl("near", 1200, "pets/")
            matches = [u for u in raw.get("units") or [] if u.get("unit") == pet_id]
            if (not raw.get("ok") or raw.get("truncated") or len(matches) != 1
                    or matches[0].get("name") != pet_name
                    or matches[0].get("behavior") != PETROOMS_PET["behavior"]):
                raise RuntimeError(f"bound pet missing/changed/capped at {stage}: unit {pet_id}, reply {raw}")
            sample = dict(matches[0], stage=stage, observed_at=time.time(), player=c.player())
            trace["pet_samples"].append(sample)
            return sample

        def samples(stage, count=5):
            rows = []
            for i in range(count):
                rows.append(bound_pet(f"{stage}:{i}"))
                time.sleep(0.4)
            movement = max(math.hypot(u["x"] - rows[0]["x"], u["y"] - rows[0]["y"]) for u in rows)
            return rows[-1], movement, rows

        def route(label, x, y, tol=8):
            # These are native Pilot intents only. No plan_pets.walk_in/puzzle_spot/
            # pet_beside fallback is used: each of those can teleport the player.
            attempts = []
            before = c.player()
            for method, timeout in (("path_to", 12), ("move", 10)):
                result = getattr(self.p, method)(x, y, tol=tol, timeout=timeout)
                state_after = self.gl("state")
                after = state_after.get("player") or {}
                attempts.append({"method": method, "result": result.result, "reason": result.reason,
                                 "intent": result.intent, "id": result.id, "tick": result.tick,
                                 "event": dict(result.event), "player_after": after})
                settled = math.hypot(after.get("x", 1e9) - x, after.get("y", 1e9) - y) <= tol
                if result.ok and settled and state_after.get("phase") == "mission":
                    trace["routes"].append({"label": label, "target": [x, y], "player_before": before,
                                            "attempts": attempts, "ok": True})
                    return True
                if result.result == "interrupted" or state_after.get("phase") != "mission":
                    break  # do not issue a fallback movement after context interruption
            trace["routes"].append({"label": label, "target": [x, y], "player_before": before,
                                    "attempts": attempts, "ok": False})
            return False

        def choose_local_route():
            # Eight fixed near-straight candidates from the ACTUAL current origin.
            # This selector only reads path/scene data; it never repositions a player.
            pl = c.player()
            sx, sy = pl.get("x"), pl.get("y")
            if sx is None or sy is None:
                return None
            trap_reply = self.gl("unitsof", *FLOOR_TRAPS)
            if not trap_reply.get("ok"):
                raise RuntimeError(f"authored trap readback refused: {trap_reply}")
            c.traps = []
            for path in FLOOR_TRAPS:
                row = trap_reply.get(path) or {}
                units = row.get("units") or []
                if row.get("count") != len(units):
                    raise RuntimeError(f"authored trap readback missing/capped: {path}: {row}")
                c.traps.extend((u["x"], u["y"]) for u in units
                               if math.hypot(u["x"] - sx, u["y"] - sy) < 1500)
            trace["authored_trap_snapshot"] = trap_reply
            for dx, dy in ((240, 0), (0, 240), (-240, 0), (0, -240),
                           (170, 170), (-170, 170), (-170, -170), (170, -170)):
                distance = math.hypot(dx, dy)
                if c.by_traps(sx, sy, sx + dx, sy + dy):
                    trace["candidate_paths"].append({"offset": [dx, dy], "refused": "authored trap corridor"})
                    continue
                raw = self.gl("pathfind", round(sx + dx), round(sy + dy), 12, -1, -1, round(sx), round(sy))
                trace["candidate_paths"].append({"offset": [dx, dy], "reply": raw})
                if raw.get("ok") and raw.get("nodes", 0) > 0 and raw.get("length", 1e9) <= distance * 1.25:
                    return sx, sy, dx, dy, distance
            return None

        def setup_dog():
            created = self.gl("char", "paladin", "LabSettingsPetRooms")
            trace["dog_setup"] = {"character_reply": created}
            if not created.get("ok") or not self.wait_phase("town", 60):
                return False
            time.sleep(2)
            c.set_gold(60000)  # isolated controlled purchase fixture; no economy credit
            c.npc("npc_pets", "actors/npcs/town/npc_pets.unit")
            opened = self.gl("use", "npc_pets")
            time.sleep(0.6)
            shop = self.gl("shop")
            entries = shop.get("items") or []
            matches = [i for i, item in enumerate(entries) if item.get("title", "").strip() == PETROOMS_PET["title"]
                       and item.get("available", True)]
            trace["dog_setup"].update(open_reply=opened, shop_reply=shop, matching_rows=matches)
            if opened.get("window") != "PetsShopWindow" or len(matches) != 1:
                return False  # English lab title must be unambiguous; never pick an unknown pet
            bought = self.gl("shop", "buy", matches[0])
            trace["dog_setup"]["buy_reply"] = bought
            if not bought.get("ok"):
                return False
            time.sleep(1.5)
            self.close_all()
            started = self.gl("mission", "bandit_keep", 0, f"seed={PETROOMS_SEED}", "ngp=0")
            trace["dog_setup"]["mission_reply"] = started
            if not started.get("ok") or not self.wait_phase("mission", 120):
                return False
            self.god(True)
            trace["dog_setup"]["controlled_cull"] = self.gl("cull")
            time.sleep(2)
            return True

        def actual_gaps(rows):
            gaps = []
            for sample in rows:
                player = sample.get("player") or {}
                if any(key not in player for key in ("x", "y")):
                    raise RuntimeError(f"missing player pose in same-pet sample: {sample}")
                gaps.append(math.hypot(sample["x"] - player["x"], sample["y"] - player["y"]))
            return gaps

        def preserve_unrelated_before_exit():
            if not fixture_started or self.gl("state").get("phase") != "mission":
                return
            raw, units = pressure_snapshot()
            trace["cleanup"]["pressure_before_abort"] = raw
            now = {u["unit"] for u in units}
            trace["cleanup"]["unrelated_preserved_before_abort"] = preexisting_ids <= now
            if not preexisting_ids <= now:
                raise RuntimeError(f"unrelated pressure IDs disappeared before cleanup: {sorted(preexisting_ids - now)}")

        def dispose_owned_floor():
            # No exact-ID destroy verb exists. Do not use radius/name unitdestroy.
            # End this controlled disposable floor through the game's abort boundary;
            # ordinary scene disposal removes the owned fixtures, not a broad trap edit.
            state = self.gl("state")
            if fixture_started and state.get("phase") == "mission":
                raw = self.gl("abort")
                trace["cleanup"]["abort_reply"] = raw
                if not raw.get("ok") or not self.wait_phase("town", 120):
                    raise RuntimeError("owned fixture floor did not return to town after one abort")
            if self.gl("state").get("phase") != "town":
                raise RuntimeError("owned fixture cleanup did not end in town")
            raw, units = pressure_snapshot()
            trace["cleanup"]["town_pressure_snapshot"] = raw
            # The precondition below requires this disposable fixture's town to start
            # without pressure units; producer absence also handles numeric ID reuse.
            if units:
                raise RuntimeError("pressure fixture producer still present after abort-to-town")

        try:
            town_raw, town_units = pressure_snapshot()
            trace["town_before"] = town_raw
            if town_units:
                return  # do not disturb an authored town pressure fixture
            fixture_started = True  # setup_dog may fail after it has started its owned run
            dog_ready = setup_dog()
            if not dog_ready:
                return
            self.set("petwait.radius", PETROOMS_RADIUS)
            initial_pets = self.gl("near", 1200, "pets/")
            candidates = initial_pets.get("units") or []
            if (self.gl("state").get("phase") != "mission" or not initial_pets.get("ok")
                    or initial_pets.get("truncated") or len(candidates) != 1):
                return
            # a pet is a local, unsynced unit, so its id is negative
            pet_id, pet_name = candidates[0].get("unit"), candidates[0].get("name")
            if (not isinstance(pet_id, int) or pet_id == 0 or pet_name != PETROOMS_PET["resource"]
                    or candidates[0].get("behavior") != PETROOMS_PET["behavior"]):
                trace["setup_refusal"] = "selected runtime pet does not match the pinned Dog producer/type"
                return
            trace["bound_pet"] = {"unit": pet_id, "name": pet_name, "initial_reply": initial_pets}
            selected = choose_local_route()
            if selected is None:
                return
            sx, sy, dx, dy, distance = selected
            if not route("certified origin", sx, sy, tol=3):
                return
            end = time.time() + 8
            first = bound_pet("before-room")
            while time.time() < end and first.get("dist", 1e9) >= 60:
                time.sleep(0.4)
                first = bound_pet("wait-at-origin")
            target = (sx + dx, sy + dy)
            # Spikes block the pathfinder, so the walks stop short of them, still in the room
            stop = (sx + dx * (1 - PETROOMS_SHORT / distance), sy + dy * (1 - PETROOMS_SHORT / distance))
            # A stationary pet cannot be admitted as a valid off control merely
            # because the player endpoint happens to be within the idle radius.
            if (first.get("dist", 1e9) >= 60
                    or math.hypot(first["x"] - target[0], first["y"] - target[1]) < 160):
                return
            raw, units = pressure_snapshot()
            preexisting_ids = {u["unit"] for u in units}
            trace["preexisting_pressure_ids"] = sorted(preexisting_ids)
            trace["pressure_before_spawn"] = raw
            for ox, oy in ((0, 0), (14, 10), (-14, 10)):
                pl = c.player()
                raw = self.gl("spawn", TRAP_UNIT, round(target[0] + ox - pl["x"]), round(target[1] + oy - pl["y"]))
                trace["spawns"].append(raw)
                if not raw.get("ok") or not isinstance(raw.get("unit"), int) or raw["unit"] in preexisting_ids:
                    return
                trace["owned_trap_ids"].append(raw["unit"])
            raw, units = pressure_snapshot()
            trace["pressure_after_spawn"] = raw
            owned = [u for u in units if u["unit"] in trace["owned_trap_ids"]]
            if len(set(trace["owned_trap_ids"])) != 3 or len(owned) != 3:
                return
            if any(math.hypot(u["x"] - target[0], u["y"] - target[1]) > 25 for u in owned):
                return
            if any(math.hypot(owned[i]["x"] - owned[j]["x"], owned[i]["y"] - owned[j]["y"]) < 12
                   for i in range(3) for j in range(i)):
                return
            off_set = self.set("petwait.enabled", "false")
            off_start = bound_pet("off-before-walk")
            if not route("off entry", *stop):
                return
            time.sleep(3)
            off_end, _, _ = samples("off-after-walk")
            off_displacement = math.hypot(off_end["x"] - off_start["x"], off_end["y"] - off_start["y"])
            off_effect = off_end.get("dist", 1e9) < 110 and off_displacement >= 30
            trace["off_motion"] = {"start": off_start, "end": off_end, "displacement": off_displacement}
            if not route("off return to origin", sx, sy, tol=6):
                return
            time.sleep(3)
            on_set = self.set("petwait.enabled", "true")
            if not route("on entry", *stop):
                return
            time.sleep(2.5)
            p1, moved1, on_rows1 = samples("on-before-step-back")
            gaps1 = actual_gaps(on_rows1)
            trace["on_geometry"] = {"required_gap": minimum_on_gap, "first_window_gaps": gaps1}
            if not all(gap >= minimum_on_gap for gap in gaps1):
                trace["setup_refusal"] = "first on window overlaps the selected pet's idle/follow bound plus margin"
                return
            # back along the walk, the one direction a corridor is sure to allow
            if not route("on same-room step back", stop[0] - dx / distance * PETROOMS_STEP_BACK,
                         stop[1] - dy / distance * PETROOMS_STEP_BACK, tol=6):
                return
            time.sleep(1)
            p2, moved2, on_rows2 = samples("on-after-step-back")
            gaps2 = actual_gaps(on_rows2)
            trace["on_geometry"]["second_window_gaps"] = gaps2
            on_geometry = all(gap >= minimum_on_gap for gap in gaps1 + gaps2)
            if not on_geometry:
                trace["setup_refusal"] = "second on window overlaps the selected pet's idle/follow bound plus margin"
                return
            shift = math.hypot(p2["x"] - p1["x"], p2["y"] - p1["y"])
            on_effect = moved1 < 10 and moved2 < 10 and shift < 10
            trace["on_motion"] = {"first": p1, "last": p2, "movement": [moved1, moved2], "shift": shift}
            setup = True  # every certified non-teleport route and bound observation completed
        except Exception as exc:
            self._original_errors.append({"stage": "petrooms", "error": repr(exc)})
            raise
        finally:
            self.flag("off_petrooms_pet_setup", dog_ready and bool(trace.get("bound_pet")),
                      "native base Dog purchase plus exact resource/type readback; no imported pet requirement")
            self.flag("off_petrooms_on_geometry", on_geometry,
                      f"every same-Dog/player pose sample must be >= {minimum_on_gap}px apart")
            self.flag("off_petrooms_setup", setup and on_geometry,
                      "pinned same pet + non-teleport routes + owned traps + both on-window idle/follow separation")
            clean_before = len(self._cleanup_errors)
            self.cleanup_step("petrooms unrelated pressure preservation", preserve_unrelated_before_exit)
            self.cleanup_step("petrooms owned floor abort/fixture absence", dispose_owned_floor)
            self.cleanup_step("petrooms restore radius", lambda: self.restore_owned_setting("petwait.radius"))
            self.cleanup_step("petrooms restore toggle", lambda: self.restore_owned_setting("petwait.enabled"))
            self.cleanup_step("petrooms close owned UI", self.close_all)
            clean = len(self._cleanup_errors) == clean_before
            self.flag("off_petrooms_returned_town", bool(trace["cleanup"].get("town_pressure_snapshot")),
                      "explicit disposable-floor abort, no radius/name destroy")
            self.flag("off_petrooms_cleanup", clean, str(trace["cleanup"]))
            self.flag("off_petrooms", setup and on_geometry and off_set and on_set and off_effect and on_effect and clean,
                      f"set {off_set}/{on_set}; same-pet off motion {off_effect}; same-pet on stationarity {on_effect}; cleanup {clean}")

    def applicability(self):
        pk, pkgs = load()
        configs = {mod: cfg for _, mods in pkgs for mod, cfg in mods}
        missing = sorted(set(configs) - set(FEATURE_CONTRACTS))
        stale = sorted(set(FEATURE_CONTRACTS) - set(configs))
        rows = []
        for mod, cfg in configs.items():
            disposition = FEATURE_CONTRACTS.get(mod, {"kind": "unassigned", "limit": "No consumer disposition"})
            kind = disposition["kind"]
            flag = None if not cfg.get("toggle") else f"off_{mod}"
            if mod in ("objectives", "puzzles", "deathrecap"):
                flag += "_run"
            rows.append({"module": mod, "toggle": cfg.get("toggle"), "scope": cfg.get("scope", "host"),
                         "applies": cfg.get("applies", "now"), "kind": kind, "flag": flag,
                         "observed": self.out.get(flag) if flag else None,
                         "limit": disposition["limit"], "always_on": cfg.get("always_on")})
        invalid_na = [r["module"] for r in rows if not r["toggle"]
                      and (r["kind"] != "not-applicable" or not r["always_on"])]
        unattempted = [r["module"] for r in rows if r["flag"] and r["flag"] not in self.out]
        self.out["applicability"] = rows
        self.out["libraries_not_applicable"] = pk["libraries"]
        self.out["coverage_scope"] = "Scoped effect/UI/status/parked-policy checks; not exhaustive feature off/on, persistence or co-op proof."
        self.out["functional_gaps"] = [r["module"] for r in rows if r["kind"] in ("status-only", "parked-policy")]
        self.flag("off_contract_inventory", not missing and not stale and not invalid_na and not unattempted,
                  f"{len(rows)} features, {len(pk['libraries'])} libraries; missing {missing}, stale {stale}, invalid N/A {invalid_na}, no result {unattempted}")
        self.flag("off_not_applicable", not invalid_na and bool(pk["libraries"]),
                  "goldworth data-only and library toggles N/A; no off-effect pass awarded")

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

    def droptrade(self):
        self.toggle("droptrade", "droptrade.enabled", self.droptrade_test())

    def droptrade_test(self):
        # A drop lands a random few pixels from where it was asked for, and a fixed walk can
        # miss it. So read where it landed, and put the NPC there.
        ids = lambda: {u.get("unit"): u for u in self.gl("near", 200, "items/").get("units") or []}
        before = ids()
        self.gl("dropitem", "hwp_rifle_02", "common", 0, -40)
        time.sleep(1)
        new = [u for unit, u in ids().items() if unit not in before]
        pl = self.gl("state").get("player") or {}
        if len(new) != 1 or "x" not in pl:
            return lambda phase, mark: (False, f"no single new drop: {new}; player {pl}")
        dx, dy = new[0]["x"] - pl["x"], new[0]["y"] - pl["y"]
        distance = math.hypot(dx, dy)
        self.gl("spawn", "actors/npcs/town/npc_skill_trainer.unit", round(dx), round(dy))
        ms = max(50, round(300 * (distance - 9) / 31))  # 300 ms covers 31 px; stop inside both
        # a drop right on the player has no direction: step up, where it was asked for
        mx, my = (round(dx / distance, 3), round(dy / distance, 3)) if distance >= 1 else (0.0, -1.0)

        def t(phase, mark):
            # walk onto them (a unit spawned on a standing player is no usable until a collision
            # starts: mod-droptrade-pickup), read the top usable, walk back off
            self.gl("input", ms, mx, my, 0, 1)
            time.sleep(1.5)
            u = self.gl("usables").get("usables") or []
            top = ((u[0].get("unit") or {}).get("name") if u else None)
            first = "[HWP:droptrade] pickup first" in self.since(mark)
            self.gl("input", ms, -mx, -my, 0, 1)
            time.sleep(1.0)
            item = top == "items/base.unit"
            names = {(row.get("unit") or {}).get("name") for row in u}
            both = {"items/base.unit", "actors/npcs/town/npc_skill_trainer.unit"} <= names
            ok = both and ((item and first) if phase == "on" else (not item and not first))
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
        # Audit the initial effective snapshots after cleanup, not assumed defaults.
        changed = []
        for key, snapshot in self._owned_settings.items():
            try:
                value = self.setting_value(key, snapshot["default"])
                if not self.same_setting(value, snapshot["initial"]):
                    changed.append({"key": key, "initial": snapshot["initial"], "observed": value})
            except Exception as exc:
                self._cleanup_errors.append({"operation": f"audit {key}", "error": repr(exc)})
        self.flag("off_restored", not changed and not self._cleanup_errors,
                  f"initial effective settings; changed {changed}, cleanup errors {self._cleanup_errors}")
        errs = self.errors_since(getattr(self, "mark0", 0))
        self.flag("off_no_errors", not errs, "; ".join(errs[:8]))


def run(p, sections="town,tavern,run_floors,petrooms,orbwarn,restore", **_):
    c = Checks(p)
    try:
        c.prepare_owned_settings()
        for section in sections.split(","):
            if section == "restore":
                continue  # unconditional finally performs cleanup and audit
            try:
                getattr(c, section)()
            except Exception as exc:
                c._original_errors.append({"stage": section, "error": repr(exc)})
                c.flag(f"{section}_crashed", False, repr(exc))
                break  # no dependent mutations after an uncertain/failed section
    except Exception as exc:
        c._original_errors.append({"stage": "initial snapshot", "error": repr(exc)})
        c.flag("off_initial_snapshot", False, repr(exc))
    finally:
        c.cleanup_owned_settings()
        c.cleanup_step("final owned-setting audit", c.restore)
        c.flag("off_cleanup", not c._cleanup_errors, str(c._cleanup_errors))
        c.applicability()
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
