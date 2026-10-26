"""The run-start screen (mods/architect overrides of GUI/MissionLoadoutMenu.as and
Missions/MissionArchitect.as, scenario fix-architect-runstart): the New Game+ row sits under
the loadout options and reads "Starting on New Game+ N", the Start hint reads "Start NG+ N",
the window keeps its key hints on screen, Escape closes it (the host's Back path; a client's
own Back now closes its window too, which solo cannot show), the architect picks and the NG+
level come back when it reopens, the picker's preset row saves (through the name dialog and
through `hwp architect preset save`) and loads a preset, and Start at NG+ asks for a
confirmation that names the level.

Lab facts this leans on: `gl widgets` truncates before the picker's preset row, so its captions
are read with `gl wtext`; a focused text input locks the window manager's input, so the name
dialog is accepted with Enter (its Submit releases the lock) and the mod clears the lock too.

Sections: runstart."""
import re
import time

from gamelab.bots.plan_runs import Checks as Base

NAV_BAR = 20  # KeyNavigationBar: 20 px of gui.png drawn right under the window


class Checks(Base):
    def open_loadout(self):
        self.g.console("mission_start dark_citadel")
        time.sleep(2.5)
        return self.window()

    def layout_line(self, log):
        m = re.findall(r"run-start layout: window (\d+) of (\d+) px([^\n]*)", log)
        return m[-1] if m else None

    def window_rect(self):
        """The loadout's "window" group as laid out: {x, y, w, h}, from its parent's children."""
        for n in self.gl("wchildren", "^window", 1).get("nodes", []):
            if n.get("id") == "window":
                return n
        return {}

    def nav(self):
        return self.gl("navbar").get("nav") or []

    def close_top(self):
        """Escape on the top window (the host's Back path), then the top window after."""
        self.g.key("escape")
        time.sleep(0.8)
        return self.window()

    def wtext(self, wid):
        """A TextWidget's text by id from the top window's own tree (gl wtext). The widgets
        dump truncates before it reaches the picker's preset row, so the row is read here."""
        return (self.gl("wtext", wid).get("texts") or {}).get(wid, "")

    # --- the section
    def runstart(self):
        town = self.new_char("paladin", "LabRunStart")
        self.flag("rs_town", town, "fresh character in town" if town else "no fresh character in town")
        if not town:
            return
        b = self.gl("build", "architect")
        for extra in ("chapel", "magic_shop", "guild_hall"):  # more loadout rows, where the lab town has a plot
            self.gl("build", extra)
        self.set_gold(100000)
        self.gl("material", "wood", 200)
        self.gl("material", "stone", 200)
        ng = self.gl("ngp", 2)
        self.flag("rs_setup", b.get("ok") and ng.get("ok"), f"build {b.get('ok')} {b.get('error', '')}, ngp {ng}")
        time.sleep(0.5)
        screen = self.gl("mouse").get("wndH")

        # 1. open: NG+ row at the bottom of the options, Start hint names the level, hints fit
        mark = len(self.g.read_log())
        w = self.open_loadout()
        self.flag("rs_open", "MissionLoadout" in w, f"window {w}")
        if "MissionLoadout" not in w:
            return
        log = self.g.read_log()[mark:]
        lay = self.layout_line(log)
        self.flag("rs_layout_logged", lay is not None and "NG+ row" in (lay[2] if lay else ""), f"layout {lay}")
        kids = self.gl("wchildren", "content", 1).get("nodes", [])
        ys = [(n.get("id"), n.get("y")) for n in kids if n.get("visible")]
        ngp_y = [y for i, y in ys if i == "ngp"]
        other_y = [y for i, y in ys if i != "ngp" and y is not None]
        self.flag("rs_ngp_bottom", bool(ngp_y) and bool(other_y) and ngp_y[0] > max(other_y),
                  f"content rows (id, y): {ys}")
        rect = self.window_rect()
        bottom = (rect.get("y") or 0) + (rect.get("h") or 0)
        self.flag("rs_hints_on_screen", bool(rect) and screen and bottom + NAV_BAR <= screen,
                  f"window {rect}, bottom {bottom} + bar {NAV_BAR} vs screen {screen}")
        self.gl("func", "ngplus")
        self.gl("func", "ngplus")
        time.sleep(0.4)
        row = self.widget("ngp-text").get("text", "")
        nav = self.nav()
        self.flag("rs_ngp_text", "New Game+ 2" in row, f"row {row!r}")
        self.flag("rs_start_hint", any("Start NG+ 2" in t for t in nav), f"hints {nav}")
        self.g.shot("runstart-window")

        # 2. picks + presets in the picker
        r = self.gl("pressfunc", "architect", "open")
        time.sleep(1)
        w2 = self.window()
        self.flag("rs_picker", r.get("ok") and "SelectArchitectSelector" in w2, f"pressfunc {r.get('ok')} {r.get('error', '')}, window {w2}")
        if "SelectArchitectSelector" not in w2:
            return
        slot1 = self.wtext("hwp-preset-name-1")
        self.flag("rs_preset_row", slot1 == "empty", f"slot 1 reads {slot1!r}")
        mark = len(self.g.read_log())
        picks = ["architect_far_sight", "architect_toppled_towers"]
        pressed = [self.gl("press", pk).get("ok") for pk in picks]
        time.sleep(0.8)
        log = self.g.read_log()[mark:]
        self.flag("rs_picks_remembered", all(pressed) and "[HWP:architect] remembered 2 pick(s)" in log,
                  f"pressed {pressed}; {log.strip()[-160:]}")
        # save slot 1 through the row: the name dialog, typed text, Enter (the text input's
        # Submit, which also releases the input lock the focused field holds; `gl func yes`
        # would skip that and the next Escape would only clear the lock)
        mark = len(self.g.read_log())
        self.gl("press", "hwp-preset-save-1")
        time.sleep(0.8)
        w3 = self.window()
        self.flag("rs_name_dialog", "DialogWindow" in w3, f"window {w3}")
        if "DialogWindow" in w3:
            self.g.type_text("Tanky")
            time.sleep(0.4)
            self.g.key("enter")
            time.sleep(0.8)
            if "DialogWindow" in self.window():  # Enter did not reach the field: the func path
                self.notes.append("name dialog: Enter did not submit, func yes used")
                self.gl("func", "yes")
                time.sleep(0.8)
        log = self.g.read_log()[mark:]
        name1 = self.wtext("hwp-preset-name-1")
        self.flag("rs_preset_saved", "preset 1 'Tanky' saved: 2 pick(s), NG+ 2" in log and name1 == "Tanky",
                  f"slot 1 reads {name1!r}; {log.strip()[-200:]}")
        self.g.shot("runstart-picker")
        # the command path for slot 2, then change the picks and load slot 1 back
        st = self.hwp("architect preset save 2 Second one", 0.6, until="saved")
        self.flag("rs_preset_cmd", "preset 2 'Second one' saved" in st, st.strip()[-120:])
        self.gl("press", "architect_far_sight")  # unpick: 1 left
        time.sleep(0.6)
        mark = len(self.g.read_log())
        self.gl("press", "hwp-preset-1")
        time.sleep(1)
        log = self.g.read_log()[mark:]
        st = self.hwp("architect", 0.5, until="remembered:")
        n_now = len(re.findall(r"\] - .*\(", st))  # the status' "- name (payer)" lines
        self.flag("rs_preset_loaded", "preset 1 'Tanky' loaded: 2 pick(s), NG+ 2" in log and n_now == 2,
                  f"{n_now} pick lines; {log.strip()[-160:]}")
        self.gl("func", "exit", "yes")
        time.sleep(0.8)
        if "SelectArchitectSelector" in self.window():
            self.close_top()

        # 3. Escape closes the setup (the host's Back); it reopens with the picks and level
        self.gl("func", "ngminus")  # NG+ 1 is what should come back
        time.sleep(0.4)
        mark = len(self.g.read_log())
        w4 = self.close_top()
        log = self.g.read_log()[mark:]
        self.flag("rs_back_closes", "MissionLoadout" not in w4 and "run-start setup closed by the host" in log,
                  f"window after Escape {w4!r}; {log.strip()[-120:]}")
        mark = len(self.g.read_log())
        w5 = self.open_loadout()
        log = self.g.read_log()[mark:]
        st = self.hwp("architect", 0.5, until="remembered:")
        n_again = len(re.findall(r"\] - .*\(", st))
        row = self.widget("ngp-text").get("text", "")
        self.flag("rs_restore_picks", "MissionLoadout" in w5 and "restored 2 remembered pick(s)" in log and n_again == 2,
                  f"window {w5}, {n_again} pick lines; {log.strip()[-160:]}")
        self.flag("rs_restore_ngp", "New Game+ 1" in row, f"row {row!r}")

        # 4. Start at NG+ asks, naming the level; yes starts the run on it
        self.gl("func", "play")
        time.sleep(0.8)
        w6 = self.window()
        texts = [n.get("text") for r in self.gl("widgets", 6).get("roots", []) if r.get("root") == "DialogWindow"
                 for n in r.get("nodes", []) if n.get("text")]
        self.flag("rs_confirm_dialog", "DialogWindow" in w6, f"window {w6}, dialog texts {texts}")
        self.g.shot("runstart-confirm")
        mark = len(self.g.read_log())
        if "DialogWindow" in w6:
            self.gl("func", "yes")
        ok = self.wait_phase("mission", 120)
        time.sleep(2)
        log = self.g.read_log()[mark:]
        st = self.gl("state")
        self.flag("rs_started_ngp", ok and "host starts the run at NG+ 1" in log and st.get("ngp") == 1,
                  f"phase {st.get('phase')}, ngp {st.get('ngp')}; {log.strip()[-120:]}")


def run(p, sections="runstart", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
