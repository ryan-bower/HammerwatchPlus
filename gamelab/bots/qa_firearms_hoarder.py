"""Hoarder's displayed GL charges follow whether a grenade launcher is equipped.

The charge banks naturally; no stack setter supplies it. Swapping weapons should
hide the unavailable skill's HUD count and preserve its bank for re-equipping.
"""
import time

from gamelab.bots.qa_firearms_ranks import Checks as Base


class Checks(Base):
    def snapshot(self):
        ids = [x.get("id") for x in self.bar().get("skills", [])]
        return {"gl_held": any(x in ids for x in ("hwp_attack_rifle_gl", "hwp_attack_rifle_gl_epic")),
                "banked": self.stacks("gl_charges"), "shown": self.stacks("gl_charges_shown"),
                "skills": ids}

    def hoarder(self):
        self.new_char("QAHoarder", "hwp_firearms_demolitions")
        if not self.enter_floor("qa_hoarder"):
            return
        self.ordinary_damage()
        end = time.monotonic() + 5
        seen = []
        while time.monotonic() < end:
            initial = self.snapshot()
            seen.append(initial)
            if initial["banked"] >= 1 and initial["shown"] == initial["banked"] + 1:
                break
            time.sleep(0.15)
        self.check("gl_naturally_banked", initial["gl_held"] and initial["banked"] >= 1
                   and initial["shown"] == initial["banked"] + 1, {"initial": initial, "samples": seen})
        equipped, gear = self.fixture_loadout("hwp_flamerifle_01", reset=False)
        self.check("gl_removal_gear", equipped and "hwp_attack_flamer" in gear["live_skills"], gear)
        removed = self.snapshot()
        self.g.shot("hoarder-gl-unequipped")
        self.check("gl_unequipped_hides_count", not removed["gl_held"] and removed["shown"] == 0,
                   {"before": initial, "after": removed})
        self.check("gl_unequipped_keeps_bank", removed["banked"] == initial["banked"],
                   {"before": initial, "after": removed})
        equipped, gear = self.fixture_loadout("hwp_rifle_01", reset=False)
        self.check("gl_restoration_gear", equipped and "hwp_attack_rifle_gl" in gear["live_skills"], gear)
        restored = self.snapshot()
        self.g.shot("hoarder-gl-reequipped")
        self.check("gl_reequipped_restores_count", restored["gl_held"] and restored["banked"] == initial["banked"]
                   and restored["shown"] == restored["banked"] + 1,
                   {"before": initial, "restored": restored})
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.hoarder()
    except Exception as exc:
        c.check("hoarder_crashed", False, {"error": repr(exc)})
    c.out["ok"] = bool(c.rows) and all(row["runtime"] == "PASS" for row in c.rows)
    c.out["rows"] = c.rows
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
