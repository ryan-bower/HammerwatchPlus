"""Issue #66: Destroy becomes Salvage; gear leaves Crystals or Dust, more the higher its level.

Sections:
- setup: a fresh paladin (in town), its bag filled by equipping over the hand: the starting
  mace, a Common Long Sword ilvl 1, a Rare one ilvl 20 and an Epic one ilvl 30 go to the bag
  (an Uncommon ilvl 10 stays in hand). `hwp salvage` lists each bag item's yield.
- bag: in the character screen a bag item's third hint reads Salvage. E opens the confirm,
  which names the yield, and No keeps the item. The clicked hint and Yes salvage it: the Rare
  ilvl 20 into 3 Dust and the Common ilvl 1 into 1 Crystal, given to the town (in town).
- settings: salvage.yield 200 doubles the yields; salvage.enabled off brings back the vanilla
  Destroy (its hint, its confirm, nothing given).
- stash: in the town stash (dbg_show_stash, its Deposit tab) a bag item's hint also reads Salvage, and Yes
  salvages the Epic ilvl 30 into 12 Dust.
"""
import json
import re
import time

from gamelab.bots.plan_gear import BAG, LONGSWORD, Checks as Base


class Checks(Base):
    def status(self):
        """hwp salvage: {on, yield, salvaged, crystals, dust, bag: [(i, name, quality, ilvl, yield)]}."""
        t = self.hwp("salvage", 0.3, until="salvage:")
        lines = [ln for ln in t.splitlines() if "salvage:" in ln]
        raw = lines[-1] if lines else ""
        d = {"raw": raw}
        m = re.search(r"salvage: (on|off) yield (\d+)% salvaged (\d+); crystals (\d+) dust (\d+)", raw)
        if m:
            d.update(on=m.group(1) == "on", pct=int(m.group(2)), salvaged=int(m.group(3)),
                     crystals=int(m.group(4)), dust=int(m.group(5)))
        d["bag"] = [(int(i), n, q, int(lv), y) for i, n, q, lv, y in
                    re.findall(r"; (\d+) (.+?) (\w+) ilvl (-?\d+) -> ([^;]+)", raw)]
        return d

    def confirm(self, mark):
        """The confirm the dialog opened with since mark: salvage logs its yield ("" = vanilla)."""
        m = re.findall(r"\[HWP:salvage\] confirm: (.+)", self.log_since(mark))
        return m[-1].strip() if m else ""

    def window(self):
        return self.gl("state").get("window")

    def setup(self):
        self.new_char("LabSalv")
        self.req_cheat(True)
        for quality, ilvl in (("common", 1), ("rare", 20), ("epic", 30), ("uncommon", 10)):
            r = self.gl("equip", LONGSWORD, quality, ilvl)
            if not r.get("ok"):
                self.notes.append(f"equip {quality} {ilvl}: {json.dumps(r)[:160]}")
        s = self.status()
        self.notes.append("bag " + s["raw"][:600])
        want = {("rare", 20): "3 Dust", ("common", 1): "1 Crystal", ("epic", 30): "12 Dust"}
        got = {(q, lv): y.strip() for _, n, q, lv, y in s["bag"] if "Long Sword" in n}
        self.flag("salv_yields", all(got.get(k) == v for k, v in want.items()), f"{got}")

    def find(self, quality, ilvl, root=BAG):
        """The bag widget child holding the Long Sword of this quality and level."""
        for i in range(8):
            h = self.hover(root, i)
            if not h.get("ok"):
                break
            if "Long Sword" in h.get("item", "") and h.get("quality") == quality and h.get("ilvl", ilvl) == ilvl:
                return i, h
        return -1, {}

    def salvage(self, label, quality, ilvl, gives, material, how="click", root=BAG, shot=None):
        """Salvage the item through its hint (click) and Yes; flags the hint, the confirm and the gain."""
        i, h = self.find(quality, ilvl, root)
        nav = h.get("nav") or []
        at = next((k for k, t in enumerate(nav) if "Salvage" in t), -1)
        self.flag(f"{label}_hint", at >= 0, f"#{i} {json.dumps(h)[:300]}")
        if at < 0:
            return
        before = self.status()
        mark = len(self.g.read_log())
        if how == "key":
            self.press("e")
        else:
            self.gl("navbar", "click", at)
            time.sleep(0.5)
        text = self.confirm(mark)
        self.flag(f"{label}_confirm", self.window() == "DialogWindow" and text.endswith(f"into {gives}"), text)
        if shot:
            self.g.shot(shot)
        mark = len(self.g.read_log())
        self.gl("func", "yes")
        time.sleep(0.6)
        log = self.log_since(mark)
        after = self.status()
        n = int(gives.split()[0])
        self.flag(f"{label}_given", f"into {gives} (town), given {n}" in log
                  and after[material] - before[material] == n and len(after["bag"]) == len(before["bag"]) - 1,
                  f"{material} {before.get(material)} -> {after.get(material)}, bag {len(before['bag'])} -> "
                  f"{len(after['bag'])} | {log[-300:]}")

    def bag(self):
        self.menu()
        # E opens the confirm, No keeps the item
        i, h = self.find("rare", 20)
        n0 = len(self.status()["bag"])
        mark = len(self.g.read_log())
        self.press("e")
        text = self.confirm(mark)
        self.flag("salv_key_confirm", self.window() == "DialogWindow" and text.endswith("into 3 Dust"), f"#{i} {text}")
        self.gl("func", "no")
        time.sleep(0.5)
        self.flag("salv_no_keeps", self.window() == "PlayerMenu" and len(self.status()["bag"]) == n0, self.window())
        self.salvage("salv_rare", "rare", 20, "3 Dust", "dust", shot="salvage-confirm")
        self.salvage("salv_common", "common", 1, "1 Crystal", "crystals")
        self.close()

    def settings(self):
        base = {n: y for _, n, *_, y in self.status()["bag"]}
        self.hwp("set salvage.yield 200", 0.5)
        dbl = self.status()
        self.flag("salv_yield_setting", dbl.get("pct") == 200 and any("24 Dust" in y for *_, y in dbl["bag"]),
                  f"{base} -> {dbl['raw'][:300]}")
        self.hwp("set salvage.yield 100", 0.5)
        self.hwp("set salvage.enabled 0", 0.5)
        self.menu()
        h = self.hover(BAG, 0)
        nav = h.get("nav") or []
        self.flag("salv_off_destroy", len(nav) > 3 and "Destroy" in nav[3] and not any("Salvage" in t for t in nav), str(nav))
        before = self.status()
        mark = len(self.g.read_log())
        self.gl("navbar", "click", 3)
        time.sleep(0.5)
        w = self.window()
        text = self.confirm(mark)
        self.gl("func", "yes")
        time.sleep(0.6)
        after = self.status()
        self.flag("salv_off_vanilla", w == "DialogWindow" and text == "" and after["salvaged"] == before["salvaged"]
                  and (after["crystals"], after["dust"]) == (before["crystals"], before["dust"])
                  and len(after["bag"]) == len(before["bag"]) - 1, f"{w} {text!r} | {after['raw'][:200]}")
        self.close()
        self.hwp("set salvage.enabled 1", 0.5)

    def stash(self):
        self.g.console("dbg_show_stash")
        time.sleep(1.0)
        w = self.window()
        self.flag("salv_stash_open", w == "PlayerStashWindow", str(w))
        if w != "PlayerStashWindow":
            return
        # it opens on Withdraw; the Deposit tab (its own func) shows the bag
        self.gl("func", "set-mode", "deposit-content")
        time.sleep(0.5)
        # the stash's hints are not buttons (only hwplib's character tab makes them clickable): E
        self.salvage("salv_stash", "epic", 30, "12 Dust", "dust", how="key", root="player-inventory",
                     shot="salvage-stash-confirm")
        self.close()


def run(p, sections="setup,bag,settings,stash", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
