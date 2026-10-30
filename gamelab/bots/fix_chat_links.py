"""Issue #62: link an item in chat from the inventory, hover the link to see the item.

Sections:
- hint: a bag item's hint bar has "[L] Link in chat" (hwplib ItemActions, chatlinks LinkAction);
  clicking the hint links it (navbar click: the hint's own handler) and so does the L key.
- right: the equipped main hand hovered (`gl hover mainhand`), then a right-click links it.
  Lab mode can't press the mouse (posted mouse messages never reach the game, docs/RE_NOTES.md),
  so `hwp chatlinks rclick` stands in for the button: one press on the first frame the tab is on
  top again, through the same PollRightClick path as the raw button.
- panel: the chat itself is out of mod reach (the main menu's script context), so the links
  show on a HUD panel just above it. With the menu shut the panel is up with every link, the
  cursor pinned on a line puts that item's tooltip up (`hwp chatlinks`: hovered, tooltip
  ours), and off the line takes it down. The chat line has no slot or item level. The panel
  follows ui_chat_pos (the chat moved to the bottom, the panel goes with it).
"""
import json
import re
import time

from gamelab.bots.plan_gear import BAG, LONGSWORD, Checks as Base

LINK = "Link in chat"


class Checks(Base):
    def status(self):
        """hwp chatlinks as a dict."""
        t = self.hwp("chatlinks", 0.3, until="chatlinks:")
        lines = [ln for ln in t.splitlines() if "chatlinks:" in ln and "armed" not in ln]
        raw = lines[-1] if lines else ""
        d = {"raw": raw}
        m = re.search(r"links (\d+) announced (\d+) tips (\d+) by action (\d+) by right (\d+)", raw)
        if m:
            d.update(zip(("links", "announced", "tips", "action", "right"), map(int, m.groups())))
        m = re.search(r"; tab item (.*?); hovered (.*?); tooltip (\w+)", raw)
        d["tab_item"], d["hovered"], d["tooltip"] = m.groups() if m else ("", "", "")
        m = re.search(r"; panel (shown|hidden) (-?\d+),(-?\d+) (\d+)x(\d+)", raw)
        d["shown"] = bool(m) and m.group(1) == "shown"
        d["panel"] = tuple(map(int, m.groups()[1:])) if m else None
        d["rects"] = [(n, tuple(map(int, r))) for n, *r in
                      re.findall(r"; line \d+ (.+?) (-?\d+),(-?\d+) (\d+)x(\d+)", raw)]
        return d

    def drop_char(self):
        """A fresh character with the starting mace in the bag (a longsword in hand); no
        `hwp bag` here, that is droptrade's."""
        self.new_char("LabDrop")
        r = self.gl("equip", LONGSWORD, "common", 1)
        self.flag("char_ready", bool(r.get("ok")), json.dumps(r)[:200])

    def linked(self, mark, how, name):
        log = self.log_since(mark)
        return bool(name) and f"linked by {how}: {name}" in log, log

    def hint(self):
        self.menu()
        h = self.hover(BAG, 0)
        name = h.get("item", "")
        nav = h.get("nav") or []
        at = next((i for i, t in enumerate(nav) if LINK in t), -1)
        self.flag("hint_shown", at >= 0 and "[L]" in nav[at], f"{name}: {nav}")
        mark = len(self.g.read_log())
        c = self.gl("navbar", "click", at) if at >= 0 else {}
        time.sleep(0.6)
        ok, log = self.linked(mark, "the action", name)
        self.flag("hint_click_links", ok, f"{json.dumps(c)[:160]} | {log[-300:]}")
        self.hover(BAG, 0)
        mark = len(self.g.read_log())
        self.press("l")
        ok, log = self.linked(mark, "the action", name)
        self.flag("key_links", ok, log[-300:])
        # the chat line: the player and the item, no slot or item level any more
        self.flag("chat_line_plain", f"linked {name} (" in log and "ilvl" not in log, log[-300:])
        self.close()
        return name

    def right(self):
        self.menu()
        main = self.hover("mainhand")
        name = main.get("item", "")
        mark = len(self.g.read_log())
        self.hwp("chatlinks rclick", 0.3, until="armed")
        time.sleep(1.0)
        ok, log = self.linked(mark, "right click", name)
        self.flag("right_click_links", ok and "right click stand-in" in log,
                  f"main hand {name}: {json.dumps(main)[:200]} | {log[-400:]}")
        self.close()
        return name

    def panel(self):
        self.close()
        time.sleep(0.5)
        s = self.status()
        self.notes.append("status " + s["raw"][:700])
        self.flag("panel_shown", s["shown"] and len(s["rects"]) >= 3 and s.get("links", 0) == len(s["rects"]),
                  s["raw"][:400])
        if not s["rects"]:
            self.flag("hover_tooltip", False, "no panel lines: " + s["raw"][:300])
            return
        name, (x, y, w, hgt) = s["rects"][-1]
        cx, cy = x + min(w, 60) // 2, y + hgt // 2
        self.gl("mouse", cx, cy)
        time.sleep(0.6)
        on = self.status()
        self.flag("hover_tooltip", on["hovered"] == name and on["tooltip"] == "ours" and on["tips"] > s.get("tips", 0),
                  f"cursor {cx},{cy} on {name}: {on['raw'][:400]}")
        px, py, pw, ph = on["panel"] or (0, 0, 0, 0)
        self.gl("mouse", px + pw + 150, max(py - 150, 10))
        time.sleep(0.5)
        off = self.status()
        self.flag("hover_leaves", off["hovered"] == "none" and off["tooltip"] != "ours", off["raw"][:300])
        # the panel follows the chat: ui_chat_pos lower moves it down with the chat (and clears
        # the new character's tutorial box off the tooltip for the shot)
        self.g.console("ui_chat_pos 0.05 1")
        time.sleep(0.6)
        low = self.status()
        lp = low["panel"] or (0, 0, 0, 0)
        self.flag("panel_follows_chat", low["shown"] and lp[1] > py + 20, f"before {on['panel']} | {low['raw'][:300]}")
        # back on the last line for the scenario's shot (its next step); the pin stays
        if low["rects"]:
            name, (x, y, w, hgt) = low["rects"][-1]
            cx, cy = x + min(w, 60) // 2, y + hgt // 2
        self.gl("mouse", cx, cy)
        time.sleep(0.6)
        shot = self.status()
        self.flag("shot_hover", shot["tooltip"] == "ours", shot["raw"][:300])


def run(p, sections="drop_char,hint,right,panel", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
