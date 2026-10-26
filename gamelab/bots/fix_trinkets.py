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

HoH1 trinkets (HWP/Trinkets/HoH1.as), section hoh1:
- `hwp trinkets hoh1`: all 37 loaded; the vanilla changes applied (Apothecary's Supplies 7
  pieces and 5 tiers, Emblems of Hermes 5 pieces and 4 tiers, Trader's Coin +1 modifier).
- `hwp trinkets set <id>`: Spheres of Power has 6 pieces and tiers 2-6; Apothecary's 4-piece
  tier holds 3 modifiers (the vanilla merge would give it 4: its 2-piece twice); Pyromancer
  holds the vanilla Fire Salts.
- Lucky Hat and Lucky Horseshoe given: Luck 35 (20 + 10 + the Charms of Fortune 2-piece 5).
- Trader's Coin, Fancy Plume and Key Ring given: shop price x0.75, stock +2, key ring 50%.
- Judgement reads "Adds 12 Physical"; at `hwp trinkets ng 2`, 14 (NGScaling SPEC).

Sections: trinkets, hoh1."""
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
        self.flag("tr_status", "trinket NG+ scaling (on): 58/58 trinket(s) found" in log and "no trinket" not in self.g.read_log(),
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


    def give(self, tid):
        self.gl("cheat", "cht_give_specific_trinket", tid)
        time.sleep(0.6)

    def setinfo(self, sid):
        log = self.hwp("trinkets set " + sid, 0.5, until="set " + sid + " (")
        line = [ln for ln in log.splitlines() if "set " + sid + " (" in ln]
        return line[-1] if line else ""

    def hoh1(self):
        self.g.console("e_cheats 1")
        log = self.hwp("trinkets hoh1", 0.6, until="hoh1 trinkets:")
        self.flag("h1_loaded", "hoh1 trinkets: 37 loaded" in log, log[-400:])
        self.flag("h1_vanilla", "apothecarys +3 piece(s) (7), 5 tier(s)" in log and "emblems_of_hermes +2 piece(s) (5), 4 tier(s)" in log
                  and "traders_coin +1/1 modifier(s)" in log, log[-400:])
        sp = self.setinfo("hwp_spheres_of_power")
        self.flag("h1_spheres", "6 piece(s)" in sp and all(f" {n}:" in " " + sp.split("tiers ", 1)[-1].replace("| ", " ") for n in range(2, 7)), sp)
        ap = self.setinfo("apothecarys")
        self.flag("h1_apothecary_merge", "7 piece(s)" in ap and "4:3 " in ap and "7:" in ap, ap)
        py = self.setinfo("hwp_pyromancer")
        self.flag("h1_pyromancer", "fire_salts" in py and "4 piece(s)" in py, py)

        for t in ("hwp_lucky_hat", "hwp_lucky_horseshoe"):
            self.give(t)
        luck = self.hwp("luck", 0.6, until="Luck:")
        m = re.findall(r"Luck: (-?[\d.]+)", luck)
        self.flag("h1_luck", bool(m) and abs(float(m[-1]) - 35) < 0.01, luck[-200:])

        for t in ("traders_coin", "hwp_fancy_plume", "hwp_key_ring"):
            self.give(t)
        log = self.hwp("trinkets hoh1", 0.6, until="hoh1 trinkets:")
        self.flag("h1_shop_stats", "shop price x0.75" in log and "stock +2" in log and "key ring 50%" in log, log[-300:])

        j = self.show("hwp_judgement")
        self.ng(2)
        j2 = self.show("hwp_judgement")
        self.ng(0)
        self.flag("h1_judgement_ng", j is not None and j2 is not None and "Adds 12 Physical" in j[0] and "Adds 14 Physical" in j2[0]
                  and "Adds 28 Physical" in j2[1], f"{j} -> {j2}")
        errs = [ln for ln in self.g.read_log().splitlines()
                if "Couldn't find trinket" in ln or ("HWP:trinkets" in ln and ("not a set" in ln or "no trinket" in ln))]
        self.flag("h1_no_errors", not errs, "; ".join(errs[:5]))


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
