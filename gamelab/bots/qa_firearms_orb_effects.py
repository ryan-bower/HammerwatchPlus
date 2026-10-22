"""Every rank of cartridge/adrenaline crit orbs and both EpiPen ranks.

Native live modifier rolls accompany natural shots or naturally gained dodge
stacks. Fixed samples are not retried; controlled native hurt only clears stacks.
"""
import math
import time

from gamelab.bots.qa_firearms_magazine_edges import Checks as Base


class Checks(Base):
    def cartridge(self):
        if not self.prepare("QAOrbClip"):
            return
        self.learn_rank("hwp_fs_steady", 5)
        ok, gear = self.fixture_loadout("hwp_glock_mh_01", "hwp_hcannon_oh_01")
        self.check("cartridge_orb_gear", ok and gear["clip_max"] == 24, gear)
        d = self.open_dirs(130)[0]
        for rank, chance in enumerate((0.0025, 0.005, 0.0075), 1):
            ok, got = self.orb("hwp_fs_steady_crit", 1)
            row = self.cycle(d, refill=True)
            main = self.probe("hwp_attack_glock")
            off = self.probe("hwp_attack_hcannon_off")
            self.check(f"extended_crit_chance_rank_{rank}", ok and got == rank and row["clip"] == [24, 21]
                       and row["actual_damage"] > 0 and abs(main["rate"] - 13 * chance) < 0.012
                       and abs(off["rate"] - 8 * chance) < 0.012,
                       {"orb": "hwp_fs_steady_crit", "rank": rank, "chance_per_own_round": chance,
                        "naturally_depleted_own_rounds": [13, 8], "natural_cycle": row,
                        "main_live_modifier_rolls": main, "off_live_modifier_rolls": off,
                        "expected_main_rate": 13 * chance, "expected_off_rate": 8 * chance})
        self.clear_dummies()
        self.to_town()

    def clear_adrenaline(self):
        self.g.console("cht_give_health 999")
        time.sleep(0.15)
        mark = self.log_pos()
        before = self.stacks("adrenaline")
        self.g.console("cht_damage 1")
        time.sleep(0.35)
        return {"before": before, "after": self.stacks("adrenaline"), "log": self.log_from(mark),
                "fixture": "Native controlled1HP hurt after health refill; no stack setter."}

    def dodge(self, d):
        time.sleep(2.1)
        self.clear_dummies()
        d = self.open_dirs(130)[0]
        before = self.stacks("adrenaline")
        position = self.pos()
        mark = self.log_pos()
        self.gl("input", 120, d[0], d[1], d[0], d[1], "dash")
        time.sleep(0.35)
        after = self.stacks("adrenaline")
        end = self.pos()
        return {"before": before, "after": after, "log_mark": mark,
                "distance": math.hypot(end[0] - position[0], end[1] - position[1]), "direction": d}

    def assault(self):
        if not self.prepare("QAOrbAdrenal", "hwp_firearms_assault"):
            return
        d = self.open_dirs(130)[0]
        dd, _ = self.tough(d, 60)
        crit_ok, crit_rank = self.orb("hwp_fs_adrenaline_crit", 1)
        zero = self.probe("hwp_attack_rifle")
        epi_ok, epi_rank = self.orb("hwp_fs_adrenaline_epipen", 1)
        cleared = self.clear_adrenaline()
        first = self.dodge(dd)
        hiss = self.wait_log(r"adrenaline: epipen hiss faded out at (\d+) ms", first["log_mark"], 3)
        self.check("epipen_rank_1_zero_boundary", epi_ok and epi_rank == 1 and cleared["after"] == 0
                   and first["before"] == 0 and first["after"] == 8 and first["distance"] > 0,
                   {"orb": "hwp_fs_adrenaline_epipen", "rank": 1, "controlled_hurt": cleared,
                    "natural_dodge": first})
        self.check("epipen_rank_1_hiss_timer", hiss is not None and 2000 <= int(hiss[1]) < 2200,
                   {"orb": "hwp_fs_adrenaline_epipen", "rank": 1,
                    "native_hiss_stop_log": hiss.group(0) if hiss else None,
                    "audible_listening": "BLOCKED: GameLab desktop is muted."})
        second = self.dodge(dd)
        log = self.log_from(second["log_mark"])
        self.check("epipen_rank_1_nonzero_boundary", second["before"] == second["after"] == 8
                   and "adrenaline: epipen," not in log,
                   {"orb": "hwp_fs_adrenaline_epipen", "rank": 1, "natural_second_dodge": second, "log": log})
        for rank, chance in enumerate((0.005, 0.01, 0.015), 1):
            if rank == 1:
                ok, got = crit_ok, crit_rank
            else:
                ok, got = self.orb("hwp_fs_adrenaline_crit", 1)
            d = self.open_dirs(130)[0]
            row = self.cycle(d, refill=True)
            earned = self.stacks("adrenaline")
            live = self.probe("hwp_attack_rifle")
            self.check(f"critical_focus_rank_{rank}", ok and got == rank and zero["rate"] < 0.002
                       and earned == 8 and row["clip"][0] - row["clip"][1] == 3 and row["actual_damage"] > 0
                       and abs(live["rate"] - earned * chance) < 0.012,
                       {"orb": "hwp_fs_adrenaline_crit", "rank": rank, "naturally_earned_epipen_stacks": earned,
                        "chance_per_stack": chance, "expected_rate": earned * chance,
                        "zero_stack_control": zero, "live_modifier_rolls": live, "natural_gunfire": row})
        self.orb_off("hwp_fs_adrenaline_crit")
        epi_ok, epi_rank = self.orb("hwp_fs_adrenaline_epipen", 1)
        cleared = self.clear_adrenaline()
        third = self.dodge(d)
        hiss = self.wait_log(r"adrenaline: epipen hiss faded out at (\d+) ms", third["log_mark"], 3)
        fourth = self.dodge(d)
        log = self.log_from(fourth["log_mark"])
        self.check("epipen_rank_2_zero_and_nonzero_boundaries", epi_ok and epi_rank == 2 and cleared["before"] == 8
                   and cleared["after"] == 0 and third["before"] == 0 and third["after"] == 15
                   and third["distance"] > 0 and fourth["before"] == fourth["after"] == 15
                   and "adrenaline: epipen," not in log,
                   {"orb": "hwp_fs_adrenaline_epipen", "rank": 2, "native_hurt_consumption": cleared,
                    "natural_zero_stack_dodge": third, "natural_nonzero_stack_dodge": fourth, "nonzero_log": log})
        self.check("epipen_rank_2_hiss_timer", hiss is not None and 2000 <= int(hiss[1]) < 2200,
                   {"orb": "hwp_fs_adrenaline_epipen", "rank": 2,
                    "native_hiss_stop_log": hiss.group(0) if hiss else None,
                    "audible_listening": "BLOCKED: GameLab desktop is muted."})
        self.clear_dummies()
        self.to_town()


def run(p, section="cartridge", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("orb_effects_crashed", False, {"section": section, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
