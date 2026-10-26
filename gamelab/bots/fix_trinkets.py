"""Trinket NG+ scaling (mods/trinkets: HWP/Trinkets/NGScaling.as), in town as the host:

- `hwp trinkets` lists the scaled trinkets at NG+ 0, every one of them found (no
  "[HWP:trinkets] no trinket" in the log).
- Amulet of Health given (cht_give_specific_trinket): its tooltip reads "+30 Health".
- `hwp trinkets ng 3` (cheat, sets g_ngp): "+45 Health", the attuned tooltip "+90 Health",
  and the character's max health 15 higher.
- At NG+ 3 the proc and float trinkets rebuild with the same modifier counts and their
  tooltips read the scaled numbers: Searing Torch 80 dmg (cd 2 kept), Chicken Feet 3.5 mana,
  Arctic Step 60 dmg, Apothecary's Tincture 8 s.
- `hwp trinkets ng 4`: Apothecary's Flask holds 2 charges, 4 attuned.
- `hwp trinkets ng 0`: "+30 Health" and the max health back.

Sections: trinkets."""
import re
import time

from gamelab.bots.plan_runs import Checks as Base

SHOW = re.compile(r"(\w+) at NG\+ (\d+): (.*?) \| attuned: (.*?) \| (\d+)\+(\d+) modifier\(s\)(?: \| max health (\d+), max mana (\d+))?")


class Checks(Base):
    def show(self, tid):
        """(desc, attuned desc, mods, attuned mods, max health) from `hwp trinkets show`."""
        log = self.hwp("trinkets show " + tid, 0.5, until=tid + " at NG+")
        m = [x for x in SHOW.findall(log) if x[0] == tid]
        if not m:
            return None
        _, _, d1, d2, n1, n2, hp, _ = m[-1]
        return d1, d2, int(n1), int(n2), int(hp) if hp else -1

    def ng(self, n):
        return self.hwp(f"trinkets ng {n}", 0.8, until=f"NG+ {n}:")

    def trinkets(self):
        self.g.console("e_cheats 1")
        log = self.hwp("trinkets", 0.6, until="trinket NG+ scaling")
        self.flag("tr_status", "trinket NG+ scaling (on): 56/56 trinket(s) found" in log and "no trinket" not in self.g.read_log(),
                  log[-300:])

        self.gl("cheat", "cht_give_specific_trinket", "amulet_health")
        time.sleep(0.8)
        base = self.show("amulet_health")
        self.flag("tr_given", base is not None and "+30 Health" in base[0] and "+60 Health" in base[1], f"{base}")

        r = self.ng(3)
        ng3 = self.show("amulet_health")
        self.flag("tr_ng3_desc", ng3 is not None and "+45 Health" in ng3[0] and "+90 Health" in ng3[1],
                  f"{ng3}; {r[-200:]!r}")
        self.flag("tr_ng3_health", base is not None and ng3 is not None and base[4] > 0 and ng3[4] == base[4] + 15,
                  f"max health {base and base[4]} -> {ng3 and ng3[4]}")

        want = {
            "searing_torch": ("80 Fire damage", "2s cooldown"),
            "chicken_feet": ("3.5 Mana", None),
            "arctic_step": ("60 Ice damage", None),
            "apothecarys_tincture": ("for 8 seconds", None),
        }
        got = {}
        for tid, (frag, keep) in want.items():
            s = self.show(tid)
            got[tid] = s
            ok = s is not None and frag in s[0] and (keep is None or keep in s[0]) and s[2] > 0
            self.flag(f"tr_ng3_{tid}", ok, f"{s}")

        self.ng(4)
        flask = self.show("apothecarys_flask")
        self.notes.append(f"flask at 4: {flask}")
        self.flag("tr_ng4_flask", flask is not None and re.search(r"\b2\b", flask[0]) and re.search(r"\b4\b", flask[1]),
                  f"{flask}")

        self.ng(0)
        back = self.show("amulet_health")
        self.flag("tr_ng0_back", back is not None and base is not None and "+30 Health" in back[0] and back[4] == base[4],
                  f"{back}")
        errs = [ln for ln in self.g.read_log().splitlines() if "HWP:trinkets" in ln and ("rror" in ln or "no trinket" in ln)]
        self.flag("tr_no_errors", not errs, "; ".join(errs[:5]))


def run(p, sections="trinkets", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
