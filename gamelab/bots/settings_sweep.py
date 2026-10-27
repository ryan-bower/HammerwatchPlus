"""Every row of the settings page (the Plus tab, hwplib Options.as + Config.as), clicked through
the way a player would, with every package installed. The rows come from the same sources the
page does: packages.json and each module.json's config block (tools/make_config.py).

- Module switches: a click turns the module off ("[HWP:options] <id> -> off", the row reads
  Off), a second one on again. All modules are turned off together first, so the town runs
  with every module off for a while, then back on.
- Settings with a list of values: one click per value walks the whole list and lands on the
  first value again; every click shows a new value and logs the same one.
- Settings with a range: one click moves to the next step; `hwp set <key> <default>` puts it
  back and the row shows the first value again.
- On/off settings: two clicks, off and on (or on and off).
- Options (presets): clicked until the first value comes back (at most 10), each click a new
  value. Key binds: a click waits for a key (the row reads "press a key..."), K binds it, then
  the old key is bound again.
- `hwp settings` after the first round: every switch reads false and every setting's value
  has moved off its default; after the restore every one reads its default again.
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
KEY_OPTIONS = {"swapkey", "dropkey", "skill4", "skill5", "skill6"}
SETTING_LINE = re.compile(r"\[HWP\] ([\w.]+) = (\S+)")


def load():
    pk = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    pkgs = []
    for p in pk["packages"]:
        mods = []
        for m in p["mods"]:
            cfg = json.loads((REPO / "mods" / m / "module.json").read_text(encoding="utf-8")).get("config")
            if isinstance(cfg, dict):
                mods.append((m, cfg))
        pkgs.append((p["id"], mods))
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

    def sweep(self):
        _, self.pkgs = load()
        mark0 = len(self.g.read_log())
        self.open_page()
        missing, bad = [], {k: [] for k in ("off", "on", "values", "ranges", "bools", "options", "keys")}
        switches, settings, options = [], [], []
        for pid, mods in self.pkgs:
            for mod, cfg in mods:
                if cfg.get("toggle"):
                    switches.append((mod, cfg["toggle"]))
                for s in cfg.get("settings", []):
                    (options if "option" in s else settings).append((mod, s))
        # the rows are on the page
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

        # every module off
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
        unmoved += [s["key"] for _, s in settings if s["key"] not in st or same(st[s["key"]], s["default"])]
        self.flag("sweep_stored_changed", not unmoved, f"{len(st)} stored; not changed: {unmoved}")

        # options
        for mod, s in options:
            oid = s["option"]
            w = f"hwp-opt-{oid}"
            v0, shown = self.value(w)
            if not shown:
                continue
            if oid in KEY_OPTIONS:
                self.menu(w, "hwp-opt", oid)
                time.sleep(0.3)
                cap, _ = self.value(w)
                self.g.key("k", 0.15)
                time.sleep(0.4)
                v1, _ = self.value(w)
                back = v0.lower() if re.fullmatch(r"[A-Z0-9]|F\d{1,2}", v0) else None
                if back:
                    self.menu(w, "hwp-opt", oid)
                    time.sleep(0.3)
                    self.g.key(back, 0.15)
                    time.sleep(0.4)
                v2, _ = self.value(w)
                if "press a key" not in cap or v1 != "K" or (back and v2 != v0):
                    bad["keys"].append(f"{oid}: {v0!r}, capture {cap!r}, after K {v1!r}, back {v2!r}")
                self.notes.append(f"key {oid}: {v0} -> {v1} -> {v2}")
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

        # restore: settings to their defaults, modules on
        for mod, s in settings:
            if s.get("type") == "bool" or s.get("values"):
                # one more lap: a bool's second click, a list's remaining values
                n = 1 if s.get("type") == "bool" else len(s["values"]) - 1
                for _ in range(n):
                    self.click(f"hwp-cfg-{s['key']}", "hwp-cfg", s["key"], 0.08)
            else:
                d = s["default"]
                self.hwp(f"set {s['key']} {str(d).lower() if isinstance(d, bool) else d}", 0.3)
        for mod, key in switches:
            v, said = self.click(f"hwp-mod-{mod}", "hwp-mod", mod)
            if v != "On" or said != "on":
                bad["on"].append(f"{mod}: row {v!r}, log {said!r}")
        time.sleep(1.0)
        st = self.stored()
        off = [k for _, k in switches if st.get(k, "true") != "true"]
        off += [s["key"] for _, s in settings if s["key"] in st and not same(st[s["key"]], s["default"])]
        self.flag("sweep_restored", not off, f"not back to default: {off} "
                  f"({', '.join(f'{k}={st.get(k)}' for k in off[:10])})")
        self.g.shot("sweep_restored")

        self.flag("sweep_switch_off", not bad["off"], "; ".join(bad["off"]))
        self.flag("sweep_switch_on", not bad["on"], "; ".join(bad["on"]))
        self.flag("sweep_values", not bad["values"], "; ".join(bad["values"]))
        self.flag("sweep_ranges", not bad["ranges"], "; ".join(bad["ranges"]))
        self.flag("sweep_bools", not bad["bools"], "; ".join(bad["bools"]))
        self.flag("sweep_options", not bad["options"], "; ".join(bad["options"]))
        self.flag("sweep_keys", not bad["keys"], "; ".join(bad["keys"]))
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
