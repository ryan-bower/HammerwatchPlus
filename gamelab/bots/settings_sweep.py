"""Every row of the settings page (the Plus tab, hwplib Options.as + Config.as), checked through
posted GameLab input/UI dispatch, with every current feature and required library loaded.
This checks row/store/capture behavior, not every feature's functional toggle effect. The rows come from the same sources the
page does: packages.json and each module.json's config block (tools/make_config.py).

- Module switches: a click turns the module off ("[HWP:options] <id> -> off", the row reads
  Off), a second one on again. All modules are turned off together first, so the town runs
  with every module off for a while, then back on.
- Settings with a list of values: one click per value walks the whole list and lands on the
  first value again; every click shows a new value and logs the same one.
- Settings with a range: one click moves to the next step; `hwp set <key> <default>` puts it
  back and the row shows its initial effective value again.
- On/off settings: two clicks, off and on (or on and off).
- Options (presets): clicked until the first value comes back (at most 10), each click a new
  value. Key binds: a click waits for a key (the row reads "press a key..."), K binds it, then
  the old key is bound again.
- `hwp settings` after the first round: every switch reads false and every setting's value
  has moved from its initial effective value; after the restore every one reads its initial effective value again.
- A sweep-level finally independently cancels captures, releases emulated holds and
  reconciles/restores owned settings after exceptions; original and cleanup errors remain separate.
- No script errors from HWP files during the sweep (errors_since).

Flags: sweep_rows (every row is on the page), sweep_switch_off, sweep_switch_on, sweep_values,
sweep_ranges, sweep_bools, sweep_options, sweep_keys, sweep_stored_changed, sweep_restored,
sweep_no_errors. Shots: sweep_all_off, sweep_restored."""
import json
import re
import time
from pathlib import Path

from gamelab.bots.plan_checks import Checks as Base

REPO = Path(__file__).resolve().parents[2]
# Explicit source-defined Option subclasses. Unknown options fail accounting rather than
# being guessed to be presets. ItemActions KeyedAction reads the setting directly;
# the other setters notify their owning module through hwp set.
KEY_CAPTURES = {
    "swapkey": ("weaponswap.key", 27, "weaponswap.keyname"),
    "dropkey": ("droptrade.key", 20, "droptrade.keyname"),
    "eatkey": ("fishing.eat_key", 9, None),
    "courierkey": ("pets.courier_key", 11, None),
    "skill4": ("skillkeys.skill4", 33, None),
    "skill5": ("skillkeys.skill5", 34, None),
    "skill6": ("skillkeys.skill6", 35, None),
}
PAD_CAPTURES = {"swappad": ("weaponswap.pad", "gp_dl")}
PRESET_OPTIONS = {"colors", "playercolors", "autoaim", "aimcone", "autofire", "autoskill"}
# Each preset's actual setting writes, from the source Option.Next methods. Snapshot
# these before cycling so an exception does not rely on reaching the last UI click.
OPTION_SETTINGS = {
    "colors": {"colors.preset": "default", "colors.enemy": "", "colors.friendly": ""},
    "playercolors": {"playercolors.palette": "default"},
    "autoaim": {"autoaim.mode": 1},
    "aimcone": {"autoaim.cone": 180},
    "autofire": {"autoaim.fire": True},
    "autoskill": {"autoaim.skill": True, "autoaim.skill_mana": 60},
}
SETTING_LINE = re.compile(r"\[HWP\] ([\w.]+) = (\S+)")


def load():
    """Match make_config.load's carried shared modules and Config.Load's first owner.

    Read metadata only; importing a generator here would add write side effects to a bot.
    All packages are enabled by these scenarios. Each shared row is tested once.
    """
    pk = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    direct = list(dict.fromkeys(m for p in pk["packages"] for m in p["mods"]))
    metadata = {m: json.loads((REPO / "mods" / m / "module.json").read_text(encoding="utf-8")) for m in direct}
    shared = {m for m, meta in metadata.items() if meta.get("shared")}
    pkgs, seen = [], set()
    for p in pk["packages"]:
        carried, todo = list(p["mods"]), list(p["mods"])
        while todo:
            for dep in metadata[todo.pop()].get("requires", []):
                if dep in shared and dep not in carried:
                    carried.append(dep)
                    todo.append(dep)
        mods = []
        for mod in carried:
            cfg = metadata[mod].get("config")
            if mod not in seen and isinstance(cfg, dict):
                seen.add(mod)
                mods.append((mod, cfg))
        pkgs.append((p["id"], mods))
    # Dependency closure also accounts explicitly for the three libraries' lack of
    # feature toggles. It supplies no gameplay or library compile/load credit.
    libraries, todo, walked = {}, list(direct), set()
    while todo:
        mod = todo.pop()
        if mod in walked:
            continue
        walked.add(mod)
        meta = metadata.get(mod)
        if meta is None:
            meta = json.loads((REPO / "mods" / mod / "module.json").read_text(encoding="utf-8"))
        if meta.get("library"):
            libraries[mod] = "Library plumbing: no feature config/toggle; load checked separately."
        todo.extend(meta.get("requires", []))
    pk["libraries"] = libraries
    return pk, pkgs

def same(a, b):
    """A stored value (text) against a default (json)."""
    if isinstance(b, bool):
        return a == ("true" if b else "false")
    try:
        return abs(float(a) - float(b)) < 1e-4
    except ValueError:
        return a == str(b)


class Checks(Base):
    def menu(self, widget, *func):
        return self.gl("menu", "hwp_options", "-", widget, *func)

    def value(self, widget):
        r = self.menu(widget)
        return r.get("texts", "").partition(" | ")[2], r.get("shown")

    def click(self, widget, func, id_, wait=0.12):
        mark = len(self.g.read_log())
        self.menu(widget, func, id_)
        time.sleep(wait)
        v, _ = self.value(widget)
        said = re.findall(r"\[HWP:options\] " + re.escape(id_) + r" -> (.*)", self.g.read_log()[mark:])
        return v, (said[-1].strip() if said else None)

    def errors_since(self, mark):
        new = self.g.read_log()[mark:]
        return [ln.strip()[:160] for ln in new.splitlines()
                if "Script exception" in ln or ("[ERR]" in ln and "HWP" in ln)
                or ("SValue param error" in ln and "hwp/" in ln.lower())]

    def stored(self):
        out = self.hwp("settings", 1.0, until="] ")
        return dict(SETTING_LINE.findall(out))

    def open_page(self):
        self.gl("menu", "character")
        time.sleep(0.5)
        for pid, _ in self.pkgs:
            self.menu(f"hwp-pkg-{pid}", "hwp-open", pid)
        time.sleep(0.4)

    def stored_value(self, key, default):
        log = self.hwp(f"get {key}", 0.15, until=f"] {key} = ")
        values = re.findall(r"\[HWP\] " + re.escape(key) + r" = ([^\r\n]*)", log)
        if not values:
            raise RuntimeError(f"missing setting readback: {key}")
        return default if values[-1].strip() == "(unset)" else values[-1].strip()

    def restore_setting(self, key, value):
        text = str(value).lower() if isinstance(value, bool) else str(value)
        self.hwp(f"set {key} {text}", 0.15, until=f"] {key} = ")

    def remember_setting(self, key, initial, default):
        if key not in self._owned_settings:
            self._owned_settings[key] = {"initial": initial, "default": default}
        if isinstance(initial, str) and any(c.isspace() for c in initial):
            raise RuntimeError(f"unrestorable one-token setting fixture: {key}={initial!r}")

    def cleanup_step(self, label, action):
        """Every cleanup action is independent; never replace the original exception."""
        try:
            action()
            return True
        except Exception as exc:
            row = {"operation": label, "error": repr(exc)}
            self._cleanup_errors.append(row)
            self.notes.append(f"cleanup failed: {row}")
            return False

    def close_capture(self):
        if self.gl("state").get("window") == "HWPKeyCaptureWindow":
            self.g.key("escape", 0.1)
            time.sleep(0.2)
            if self.gl("state").get("window") == "HWPKeyCaptureWindow":
                raise RuntimeError("capture remained open after one cancellation")

    def release_owned_pad(self):
        reply = self.gl("pad", "release")
        if not reply.get("ok") or reply.get("held") or reply.get("ms", 0) != 0:
            raise RuntimeError(f"emulated pad release refused: {reply}")

    def restore_owned_setting(self, key):
        snapshot = self._owned_settings[key]
        initial, default = snapshot["initial"], snapshot["default"]
        current = self.stored_value(key, default)  # independent read before any restore write
        text = str(current).lower() if isinstance(current, bool) else str(current)
        if same(text, initial):
            return
        if initial == "":
            raise RuntimeError(f"cannot restore empty {key!r} through CmdSet; no guessed reset")
        self.restore_setting(key, initial)  # one dispatch; no blind retry on missing ack
        after = self.stored_value(key, default)
        text = str(after).lower() if isinstance(after, bool) else str(after)
        if not same(text, initial):
            raise RuntimeError(f"restore readback differs for {key}: {after!r}, initial {initial!r}")

    def cleanup_owned_settings(self):
        self.cleanup_step("cancel owned capture", self.close_capture)
        if self._pad_capture_used:
            self.cleanup_step("release owned emulated pad hold", self.release_owned_pad)
        # Options were snapshotted last; restore them and scalar rows before toggles.
        for key in reversed(self._owned_settings):
            self.cleanup_step(f"restore {key}", lambda key=key: self.restore_owned_setting(key))
        self.out["owned_initial_settings"] = self._owned_settings
        self.out["cleanup_failures"] = self._cleanup_errors

    def capture_key(self, oid, bad):
        key, default, alias = KEY_CAPTURES[oid]
        w = f"hwp-opt-{oid}"
        before, shown = self.value(w)
        original = int(float(self.stored_value(key, default)))
        self.remember_setting(key, original, default)
        # Those two older options clear a custom display name on rebind. Do not erase
        # an arbitrary nickname that CmdSet's one-token parser cannot restore exactly.
        if alias and self.stored_value(alias, ""):
            bad.append(f"{oid}: custom key label needs a separate restorable fixture")
            return
        test_key, test_sc = ("l", 15) if original == 14 else ("k", 14)
        try:
            mark = len(self.g.read_log())
            self.menu(w, "hwp-opt", oid)
            time.sleep(0.3)
            opened = self.gl("state").get("window") == "HWPKeyCaptureWindow"
            self.g.key("escape", 0.1)
            time.sleep(0.3)
            cancelled = (f"{oid} key capture cancelled" in self.g.read_log()[mark:]
                         and int(float(self.stored_value(key, default))) == original)
            self.menu(w, "hwp-opt", oid)
            time.sleep(0.3)
            self.g.key(test_key, 0.15)  # posted GameLab press AND release; capture binds on release
            time.sleep(0.4)
            after, _ = self.value(w)
            bound = int(float(self.stored_value(key, default)))
            ended = self.gl("state").get("window") != "HWPKeyCaptureWindow"
            if not (shown and opened and cancelled and ended and bound == test_sc and after == test_key.upper()):
                bad.append(f"{oid}: opened {opened}, cancelled {cancelled}, ended {ended}, value {after!r}, sc {bound}")
        finally:
            self.cleanup_step(f"{oid} close capture", self.close_capture)
            self.cleanup_step(f"{oid} restore key", lambda: self.restore_owned_setting(key))
            def check_row():
                restored, _ = self.value(w)
                if restored != before:
                    raise RuntimeError(f"{oid}: row restore {before!r} -> {restored!r}")
            self.cleanup_step(f"{oid} restore row readback", check_row)
        self.notes.append(f"key {oid}: capture/cancel, {test_key.upper()}, restored {before}")

    def capture_pad(self, oid, bad):
        key, default = PAD_CAPTURES[oid]
        w = f"hwp-opt-{oid}"
        original = str(self.stored_value(key, default))
        self.remember_setting(key, original or "none", default)
        self._pad_capture_used = True
        before, shown = self.value(w)
        test_button = "gp_rth" if original == "gp_lth" else "gp_lth"
        try:
            mark = len(self.g.read_log())
            self.menu(w, "hwp-opt", oid)
            time.sleep(0.3)
            opened = self.gl("state").get("window") == "HWPKeyCaptureWindow"
            # Held-only emulation does not send MenuBack; B and Start must not bind.
            for reserved in ("gp_b", "gp_start"):
                self.gl("pad", "hold", reserved, 150)
                time.sleep(0.3)
            ignored = (self.gl("state").get("window") == "HWPKeyCaptureWindow"
                       and self.stored_value(key, default) == original)
            self.g.key("escape", 0.1)
            time.sleep(0.3)
            cancelled = f"{oid} key capture cancelled" in self.g.read_log()[mark:]
            self.menu(w, "hwp-opt", oid)
            time.sleep(0.3)
            self.gl("pad", "hold", test_button, 150)
            time.sleep(0.4)
            ended = self.gl("state").get("window") != "HWPKeyCaptureWindow"
            bound = self.stored_value(key, default)
            if not (shown and opened and ignored and cancelled and ended and bound == test_button):
                bad.append(f"{oid}: opened {opened}, reserved {ignored}, cancel {cancelled}, ended {ended}, bound {bound}")
        finally:
            self.cleanup_step(f"{oid} release hold", self.release_owned_pad)
            self.cleanup_step(f"{oid} close capture", self.close_capture)
            self.cleanup_step(f"{oid} restore button", lambda: self.restore_owned_setting(key))
            def check_row():
                restored, _ = self.value(w)
                if restored != before:
                    raise RuntimeError(f"{oid}: row restore {before!r} -> {restored!r}")
            self.cleanup_step(f"{oid} restore row readback", check_row)
        self.notes.append(f"pad {oid}: emulated capture/reserved/cancel/release; restored {original}")

    def gamekey_rows(self):
        # Read the declared rows, without writing global controls in this broad sweep.
        # Binding effects/restoration belong to mod-keys-layout/play/persist, whose
        # scenarios declare writes_controls. This flag is row presence only.
        code = (REPO / "mods/hwplib/scripts/HWP/Core/GameKeys.as").read_text(encoding="utf-8")
        ids = re.findall(r'Add\("([^"\n]+)",', code)
        self.menu("hwp-pkg-gamekeys", "hwp-open", "gamekeys")
        missing = [name for name in ids if not self.value(f"hwp-opt-game-{name}")[1]]
        self.flag("sweep_gamekey_rows", bool(ids) and len(ids) == len(set(ids)) and not missing,
                  f"{len(ids)} source-declared game-key rows; missing {missing}; no control binds changed")
        self.out["gamekeys_scope"] = "row presence only; binding consumers are mod-keys-layout/play/persist"

    def sweep(self):
        self._owned_settings = {}
        self._cleanup_errors = []
        self._pad_capture_used = False
        try:
            self.sweep_body()
        except Exception as exc:
            self.out["original_failure"] = {"stage": "sweep", "error": repr(exc)}
            self.flag("sweep_original_error", False, repr(exc))
            raise  # finally below records cleanup errors without masking this failure
        finally:
            normal_restored = bool(self.out.get("sweep_restored", False))
            self.cleanup_owned_settings()
            clean = not self._cleanup_errors
            self.flag("sweep_cleanup", clean, str(self._cleanup_errors))
            self.flag("sweep_restored", normal_restored and clean,
                      "normal completion plus unconditional owned-setting restoration")

    def sweep_body(self):
        pk, self.pkgs = load()
        mark0 = len(self.g.read_log())
        self.open_page()
        missing, bad = [], {k: [] for k in ("off", "on", "values", "ranges", "bools", "options", "keys", "pads")}
        switches, settings, options = [], [], []
        for pid, mods in self.pkgs:
            for mod, cfg in mods:
                if cfg.get("toggle"):
                    switches.append((mod, cfg["toggle"]))
                for s in cfg.get("settings", []):
                    (options if "option" in s else settings).append((mod, s))
        # Account for every feature row, including data-only modules with no switch.
        self.out["applicability"] = [{"module": mod, "toggle": cfg.get("toggle"),
            "applies": cfg.get("applies", "now"), "scope": cfg.get("scope", "host"),
            "off_on": "toggle UI/store only" if cfg.get("toggle") else "not applicable",
            "reason": cfg.get("always_on", "")} for _, mods in self.pkgs for mod, cfg in mods]
        self.out["libraries_not_applicable"] = pk["libraries"]
        always = [(mod, cfg) for _, mods in self.pkgs for mod, cfg in mods if not cfg.get("toggle")]
        no_toggle_bad = [mod for mod, cfg in always if not cfg.get("always_on")
                         or self.value(f"hwp-mod-{mod}") != ("Always on", True)]
        self.flag("sweep_not_applicable", bool(pk["libraries"]) and not no_toggle_bad,
                  f"data-only {[m for m, _ in always]}; libraries {sorted(pk['libraries'])}; bad {no_toggle_bad}")
        for _, mods in self.pkgs:
            for mod, _ in mods:
                if not self.value(f"hwp-mod-{mod}")[1]:
                    missing.append(f"hwp-mod-{mod}")
        # The scenario's fresh fixture must start with switches on; refuse mutation if
        # it does not, instead of silently turning an authored off choice into on.
        initial_off = [mod for mod, _ in switches if self.value(f"hwp-mod-{mod}")[0] != "On"]
        self.flag("sweep_initial_enabled", not initial_off, f"initial switches not On: {initial_off}")
        if initial_off:
            return
        baseline = {s["key"]: self.stored_value(s["key"], s["default"]) for _, s in settings}
        for _, key in switches:
            self.remember_setting(key, True, True)
        for _, setting in settings:
            self.remember_setting(setting["key"], baseline[setting["key"]], setting["default"])
        for mod, _ in switches:
            if not self.value(f"hwp-mod-{mod}")[1]:
                missing.append(f"hwp-mod-{mod}")
        for mod, s in settings:
            if not self.value(f"hwp-cfg-{s['key']}")[1]:
                missing.append(f"hwp-cfg-{s['key']}")
        for mod, s in options:
            if not self.value(f"hwp-opt-{s['option']}")[1]:
                missing.append(f"hwp-opt-{s['option']}")
        self.flag("sweep_rows", not missing, f"{len(switches)} switches, {len(settings)} settings, "
                  f"{len(options)} options; missing {missing}")

        self.gamekey_rows()

        # every toggle off; always-on modules and libraries are explicit N/A
        for mod, key in switches:
            v, said = self.click(f"hwp-mod-{mod}", "hwp-mod", mod)
            if v != "Off" or said != "off":
                bad["off"].append(f"{mod}: row {v!r}, log {said!r}")
        time.sleep(1.0)
        self.g.shot("sweep_all_off")

        # every setting through its values
        moved = {}
        for mod, s in settings:
            key, w = s["key"], f"hwp-cfg-{s['key']}"
            v0, _ = self.value(w)
            if s.get("type") == "bool":
                v1, said1 = self.click(w, "hwp-cfg", key)
                moved[key] = v1
                v2, said2 = self.click(w, "hwp-cfg", key)
                if v1 == v0 or said1 != v1 or v2 != v0 or said2 != v2:
                    bad["bools"].append(f"{key}: {v0!r} -> {v1!r} ({said1!r}) -> {v2!r} ({said2!r})")
                # leave it moved for the stored check, back after
                self.click(w, "hwp-cfg", key)
            elif s.get("values"):
                seen = [v0]
                for _ in range(len(s["values"])):
                    v, said = self.click(w, "hwp-cfg", key)
                    if said != v:
                        bad["values"].append(f"{key}: row {v!r}, log {said!r}")
                    seen.append(v)
                distinct = len(set(seen[:-1]))
                if seen[-1] != v0 or distinct != len(s["values"]):
                    bad["values"].append(f"{key}: {seen}")
                v1, _ = self.click(w, "hwp-cfg", key)
                moved[key] = v1
            else:
                v1, said = self.click(w, "hwp-cfg", key)
                moved[key] = v1
                if v1 == v0 or said != v1:
                    bad["ranges"].append(f"{key}: {v0!r} -> {v1!r} (log {said!r})")
        st = self.stored()
        unmoved = [k for _, k in switches if st.get(k) != "false"]
        unmoved += [s["key"] for _, s in settings if s["key"] not in st or same(st[s["key"]], baseline[s["key"]])]
        self.flag("sweep_stored_changed", not unmoved, f"{len(st)} stored; not changed: {unmoved}")

        # options
        for mod, s in options:
            oid = s["option"]
            w = f"hwp-opt-{oid}"
            v0, shown = self.value(w)
            if not shown:
                continue
            for key, default in OPTION_SETTINGS.get(oid, {}).items():
                self.remember_setting(key, self.stored_value(key, default), default)
            if oid in KEY_CAPTURES:
                self.capture_key(oid, bad["keys"])
            elif oid in PAD_CAPTURES:
                self.capture_pad(oid, bad["pads"])
            elif oid not in PRESET_OPTIONS:
                bad["options"].append(f"{oid}: unknown Option subclass; add a source-defined capture/cycle disposition")
            else:
                seen = [v0]
                for _ in range(10):
                    v, said = self.click(w, "hwp-opt", oid)
                    seen.append(v)
                    if v == v0:
                        break
                if seen[-1] != v0 or len(seen) < 3 or len(set(seen[:-1])) != len(seen) - 1:
                    bad["options"].append(f"{oid}: {seen}")
                self.notes.append(f"option {oid}: {' -> '.join(seen)}")

        # Restore effective values from the initial fixture; switches started On.
        for mod, s in settings:
            if s.get("type") == "bool" or s.get("values"):
                # one more lap: a bool's second click, a list's remaining values
                n = 1 if s.get("type") == "bool" else len(s["values"]) - 1
                for _ in range(n):
                    self.click(f"hwp-cfg-{s['key']}", "hwp-cfg", s["key"], 0.08)
            else:
                d = baseline[s["key"]]
                self.hwp(f"set {s['key']} {str(d).lower() if isinstance(d, bool) else d}", 0.3)
        for mod, key in switches:
            v, said = self.click(f"hwp-mod-{mod}", "hwp-mod", mod)
            if v != "On" or said != "on":
                bad["on"].append(f"{mod}: row {v!r}, log {said!r}")
        time.sleep(1.0)
        st = self.stored()
        off = [k for _, k in switches if st.get(k, "true") != "true"]
        off += [s["key"] for _, s in settings if s["key"] in st and not same(st[s["key"]], baseline[s["key"]])]
        self.flag("sweep_restored", not off, f"not back to initial effective value: {off} "
                  f"({', '.join(f'{k}={st.get(k)}' for k in off[:10])})")
        self.g.shot("sweep_restored")

        self.flag("sweep_switch_off", not bad["off"], "; ".join(bad["off"]))
        self.flag("sweep_switch_on", not bad["on"], "; ".join(bad["on"]))
        self.flag("sweep_values", not bad["values"], "; ".join(bad["values"]))
        self.flag("sweep_ranges", not bad["ranges"], "; ".join(bad["ranges"]))
        self.flag("sweep_bools", not bad["bools"], "; ".join(bad["bools"]))
        self.flag("sweep_options", not bad["options"], "; ".join(bad["options"]))
        self.flag("sweep_keys", not bad["keys"], "; ".join(bad["keys"]))
        self.flag("sweep_pads", not bad["pads"], "; ".join(bad["pads"]))
        errs = self.errors_since(mark0)
        self.flag("sweep_no_errors", not errs, "; ".join(errs[:8]))


def run(p, sections="sweep", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
