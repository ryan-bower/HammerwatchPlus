"""Weapon swap on a controller (issue #14; mods/weaponswap, hwplib HWP::Input), in town:

- `hwp swappad`: the button is D-pad left (gp_dl) by default; with no controller in use
  the hints name the key (X).
- `gl pad on` stands for a controller in use: the hints name the button (its glyph,
  `inp-gp-dl`), and the HUD tip / alt-set label follow (g_version).
- `gl pad hold gp_dl` with no window open starts the 2 s swap channel and the sets change.
- The same press with the character menu open does nothing (D-pad left is the menu's
  MenuLeft there); the X key still swaps there.
- The Plus tab's "Swap weapons (controller)" row captures the next button: B is ignored
  (the menu's back), the left stick click binds; the old button then does nothing and the
  new one swaps. Esc cancels a capture.
- `hwp swappad gp_a` names the clash (vanilla's Use); `default` restores D-pad left.

GameLab can't press a real pad button: gamelab-hands' pad verb writes the held button to
GlobalCache hwp_pad_held, which HWP::Input::Held reads (mods/gamelab-hands/scripts/GameLab/Pad.as).

Sections: pad."""
import re
import time

from gamelab.bots.plan_checks import Checks as Base


class Checks(Base):
    def close_windows(self, n=3):
        """Escape while a window is up (never with none: that opens the pause menu)."""
        for _ in range(n):
            if not self.gl("state").get("window"):
                return True
            self.g.key("escape")
            time.sleep(0.5)
        return not self.gl("state").get("window")

    def status(self):
        """hwp swappad's line, parsed: button, in use, button swaps, hint."""
        log = self.hwp("swappad", 0.3, until="[HWP] swap button")
        m = re.findall(r"\[HWP\] swap button (\S+)( \(also the controller's (\w+)\))?, controller in use (\w+), "
                       r"button swaps (\d+), hint ([^\n]*)", log)
        if not m:
            return {"line": log.strip()[-200:]}
        b, _, clash, using, swaps, hint = m[-1]
        return {"button": b, "clash": clash, "using": using == "yes", "swaps": int(swaps), "hint": hint.strip(), "line": m[-1]}

    def press(self, gp, ms=250):
        self.gl("pad", "hold", gp, ms)
        time.sleep(ms / 1000 + 0.3)

    def started(self, mark):
        return "swap channel started" in self.g.read_log()[mark:]

    def opt(self, widget):
        return self.gl("menu", "hwp_options", "-", widget)

    def capture(self, gp_presses):
        """Click the swappad row (the capture window opens), press each button in turn;
        the log since."""
        mark = len(self.g.read_log())
        self.gl("menu", "hwp_options", "-", "hwp-pkg-qol", "hwp-open", "qol")
        time.sleep(0.4)
        self.gl("menu", "hwp_options", "-", "hwp-opt-swappad", "hwp-opt", "swappad")
        time.sleep(0.6)
        top = self.gl("state").get("window")
        for gp in gp_presses:
            self.press(gp, 250)
            time.sleep(0.3)
        return self.g.read_log()[mark:], top

    def pad(self):
        self.close_windows()
        self.hwp("swappad default", 0.3, until="[HWP] swap button set")
        st = self.status()
        self.flag("default_dpad_left", st.get("button") == "gp_dl", str(st.get("line")))
        self.flag("hint_key_without_pad", not st.get("using") and "X" in st.get("hint", "") and "inp-gp" not in st.get("hint", ""),
                  str(st.get("line")))

        # a controller in use: the hints show the button's glyph
        self.gl("pad", "on")
        time.sleep(0.5)
        st = self.status()
        self.flag("hint_button_with_pad", st.get("using") and "inp-gp-dl" in st.get("hint", ""), str(st.get("line")))

        # the button swaps in gameplay
        e0 = self.main_hand()
        mark = len(self.g.read_log())
        self.press("gp_dl")
        started = self.started(mark)
        landed = self.swapped(mark)
        e1 = self.main_hand()
        st = self.status()
        self.flag("button_swaps", started and landed and e0 != e1 and st.get("swaps") == 1,
                  f"{e0} -> {e1}; started {started} landed {landed}; {st.get('line')}")

        # not with the character menu open (D-pad left is MenuLeft there)
        time.sleep(1.2)  # past the swap's cooldown
        self.gl("menu", "character")
        time.sleep(0.6)
        window = self.gl("state").get("window")
        mark = len(self.g.read_log())
        self.press("gp_dl")
        time.sleep(0.5)
        blocked = not self.started(mark)
        self.g.key("x")  # the key still swaps there
        key_ok = self.swapped(mark)
        self.flag("button_not_in_menu", window and blocked, f"window {window}; {self.swap_lines(self.g.read_log()[mark:])}")
        self.flag("key_still_in_menu", key_ok, self.swap_lines(self.g.read_log()[mark:]))

        # the Plus tab captures a button: B is ignored, the left stick click binds
        time.sleep(1.2)
        row0 = self.opt("hwp-opt-swappad")
        log, top = self.capture(["gp_b", "gp_lth"])
        st = self.status()
        row1 = self.opt("hwp-opt-swappad")
        self.g.shot("swappad-row")
        self.flag("capture_opens", top == "HWPKeyCaptureWindow" or "HWPKeyCaptureWindow" in str(top), f"top {top}")
        self.flag("capture_skips_b", "swappad button set to gp_b" not in log, re.findall(r"\[HWP:options\][^\n]*", log)[-3:])
        self.flag("capture_binds_stick", "swappad button set to gp_lth" in log and st.get("button") == "gp_lth",
                  f"{re.findall(r'[[]HWP:options[]][^\n]*', log)[-3:]}; {st.get('line')}")
        self.flag("row_shows_button", bool(row1.get("shown")) and row1.get("texts") != row0.get("texts"),
                  f"{row0.get('texts')!r} -> {row1.get('texts')!r}")
        self.notes.append(f"swappad row: {row0.get('texts')!r} -> {row1.get('texts')!r}")

        # Esc cancels a capture and keeps the button
        mark = len(self.g.read_log())
        self.gl("menu", "hwp_options", "-", "hwp-opt-swappad", "hwp-opt", "swappad")
        time.sleep(0.6)
        self.g.key("escape")
        time.sleep(0.6)
        st = self.status()
        self.flag("capture_esc_cancels", "swappad key capture cancelled" in self.g.read_log()[mark:] and st.get("button") == "gp_lth",
                  str(st.get("line")))
        self.close_windows()

        # in gameplay the old button does nothing, the new one swaps
        time.sleep(1.0)
        mark = len(self.g.read_log())
        self.press("gp_dl")
        time.sleep(0.5)
        old_quiet = not self.started(mark)
        self.press("gp_lth")
        new_ok = self.swapped(mark)
        self.flag("new_button_swaps", old_quiet and new_ok, self.swap_lines(self.g.read_log()[mark:]))

        # a clash with a gameplay action is named; default restores D-pad left
        # the empty-hands tip names the button (set 2 is empty: the hands are)
        time.sleep(0.5)
        self.g.shot("swappad-tip")
        self.hwp("swappad gp_a", 0.3, until="[HWP] swap button set")
        st = self.status()
        self.flag("clash_named", st.get("clash") == "Use", str(st.get("line")))
        self.hwp("swappad default", 0.3, until="[HWP] swap button set")
        st = self.status()
        self.gl("pad", "off")
        time.sleep(0.4)
        st2 = self.status()
        self.flag("default_restored", st.get("button") == "gp_dl" and not st2.get("using") and "X" in st2.get("hint", ""),
                  f"{st.get('line')}; {st2.get('line')}")


def run(p, sections="pad", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["ok"] = all(v for v in c.out.values() if isinstance(v, bool))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
