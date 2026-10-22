"""Per-gun magazine boundaries plus real damage from the other hand in a mixed burst.

All sample counts are fixed in advance. Setters establish ammo/crit controls; every
measured shot/reload uses natural input and actual target HP, with no retry-to-pass.
"""
import math
import time

from gamelab.bots.qa_firearms_passives import Checks as Base


class Checks(Base):
    def fan(self, d):
        self.clear_dummies()
        dd, _ = self.clear_dir(d, 65)
        angle = math.atan2(dd[1], dd[0])
        targets = [self.dummy(math.cos(angle + math.radians(a)) * 45,
                              math.sin(angle + math.radians(a)) * 45) for a in (-20, -10, 0, 10, 20)]
        return dd, targets

    def cycle(self, d, button="main", duration=320, refill=False):
        dd, targets = self.fan(d)
        if refill:
            self.top_up()
        hp0 = self.hps(targets)
        before = self.clip()
        self.gl("input", duration, 0, 0, dd[0], dd[1], button)
        time.sleep(duration / 1000 + 0.2)
        # One native batch keeps the empty-magazine crit observation ahead of
        # the automatic reload, even when console round trips are relatively slow.
        reads = self.g.gl_multi([["givestacks", self.CLIP, 0], ["critprobe", 1, 400, "target_dummy"],
                                 ["near", 600, "target_dummy"]])
        after = reads[0].get("stacks", -1)
        stats = reads[1]
        live = {u["unit"]: 0.0 if u.get("dead") else
                u["hpExact"] / u["hpMax"] if u.get("hpExact") is not None and u.get("hpMax", 0) > 0
                else u.get("hp", 1.0) for u in reads[2].get("units", [])}
        hp1 = {unit: live.get(unit, 0.0) for unit in targets}
        return {"clip": [before, after], "hp_before": hp0, "hp_after": hp1,
                "actual_damage": sum((hp0[x] - hp1[x]) * 500 for x in targets),
                "stats": stats, "button": button, "duration_ms": duration}

    def bonuses(self, row):
        s = row["stats"]
        return [s.get("mainCritDmg", -99) - self.baseline.get("mainCritDmg", 0),
                s.get("offCritDmg", -99) - self.baseline.get("offCritDmg", 0)]

    def edges(self):
        if not self.prepare("QAMagEdges"):
            return
        d = self.open_dirs(130)[0]
        self.tough(d, 60)
        self.baseline = self.probe(rolls=1)
        self.learn_rank("hwp_fs_steady", 5)
        for name, main, off, capacities, spend in (
            ("pistol_cannon", "hwp_glock_mh_01", "hwp_hcannon_oh_01", [15, 9], [2, 1]),
            ("cannon_pistol", "hwp_hcannon_mh_01", "hwp_glock_oh_01", [9, 15], [1, 2]),
        ):
            ok, gear = self.fixture_loadout(main, off)
            self.check(name + "_gear", ok and gear["clip_max"] == 24, gear)
            self.top_up()
            remaining = list(capacities)
            for trial in range(3):
                row = self.cycle(d)
                remaining = [n - used for n, used in zip(remaining, spend)]
                added = self.bonuses(row)
                self.check(f"{name}_unequal_cycle_{trial + 1}", row["actual_damage"] > 0
                           and row["clip"][1] == sum(remaining)
                           and all(abs(a - n * 0.02) < 0.003 for a, n in zip(added, remaining)),
                           {"configuration": name, "trial": trial + 1, "own_remaining": remaining,
                            "crit_bonuses": added, "natural_cycle": row})
            # Right click consumes one round of each gun atomically.
            row = self.cycle(d, "off", 180)
            remaining = [n - 1 for n in remaining]
            added = self.bonuses(row)
            self.check(name + "_paired_atomic", row["actual_damage"] > 0 and row["clip"][1] == sum(remaining)
                       and all(abs(a - n * 0.02) < 0.003 for a, n in zip(added, remaining)),
                       {"configuration": name, "own_remaining": remaining, "crit_bonuses": added, "natural_cycle": row})
            # A real manual reload must reset both bonus magazines, without changing
            # the tuned shared capacity. No ammo setter supplies this refill.
            before = self.clip()
            self.gl("input", 60, 0, 0, d[0], d[1], "skill1")
            end = time.monotonic() + 3
            while time.monotonic() < end and self.clip() != 24:
                time.sleep(0.08)
            live = {"stats": self.probe(rolls=1)}
            added = self.bonuses(live)
            self.check(name + "_natural_reload", before < 24 and self.clip() == 24
                       and all(abs(a - n * 0.02) < 0.003 for a, n in zip(added, capacities)),
                       {"configuration": name, "clip_before": before, "clip_after": self.clip(),
                        "expected_magazines": capacities, "crit_bonuses": added})
            for total in (7, 24, 1, 24):
                self.set_clip(total)
                live = {"stats": self.probe(rolls=1)}
                added = self.bonuses(live)
                self.check(f"{name}_external_total_{total}", self.clip() == total
                           and all(0 <= a <= cap * 0.02 + 0.003 for a, cap in zip(added, capacities))
                           and abs(sum(added) - total * 0.02) < 0.004,
                           {"configuration": name, "setup_shared_total": total, "crit_bonuses": added})
        # Eight natural P,C,P cycles exhaust15+9 while retaining the shared native
        # last-round borrowing: in cycle8 the empty pistol borrows the last cannon round.
        ok, gear = self.fixture_loadout("hwp_glock_mh_01", "hwp_hcannon_oh_01")
        self.top_up()
        trials = []
        for trial in range(8):
            row = self.cycle(d)
            trials.append(row)
        last = trials[-1]
        added = self.bonuses(last)
        self.check("mixed_empty_hand_preserves_shared_borrowing", ok and all(r["actual_damage"] > 0 for r in trials)
                   and last["clip"] == [3, 0]
                   and all(abs(a) < 0.003 for a in added),
                   {"gear": gear, "fixed_natural_cycles": trials, "final_bonuses": added})
        self.clear_dummies()
        self.to_town()

    def real_damage(self):
        if not self.prepare("QAMagDamage"):
            return
        d = self.open_dirs(130)[0]
        self.tough(d, 60)
        baseline = self.probe(rolls=1)
        ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        pistol = [self.cycle(d, duration=180, refill=True) for _ in range(5)]
        pistol_normal = min(r["actual_damage"] for r in pistol)
        self.check("mixed_damage_pistol_control", ok and all(r["clip"][0] - r["clip"][1] == 1 for r in pistol)
                   and pistol_normal > 0, {"gear": gear, "five_fixed_controls": pistol, "normal_damage": pistol_normal})
        ok, gear = self.fixture_loadout("mainhand_longsword_01", "hwp_hcannon_oh_01")
        fixture = self.gl("skillcrit", "hwp_attack_hcannon_off", 1)
        try:
            cannon = [self.cycle(d, "off", 180, refill=True) for _ in range(3)]
        finally:
            restored = self.gl("skillcrit", "hwp_attack_hcannon_off", "restore")
        cannon_crit = min(r["actual_damage"] for r in cannon)
        self.check("mixed_damage_cannon_control", ok and fixture.get("override_active") and not restored.get("override_active")
                   and cannon_crit > 0 and all(r["clip"][0] - r["clip"][1] == 1 for r in cannon),
                   {"gear": gear, "three_fixed_critical_controls": cannon, "critical_damage": cannon_crit,
                    "fixture": fixture, "fixture_restore": restored})
        self.learn_rank("hwp_fs_steady", 5)
        ok, gear = self.fixture_loadout("hwp_glock_mh_01", "hwp_hcannon_oh_01")
        fixture = self.gl("skillcrit", "hwp_attack_hcannon_off", 1)
        try:
            mixed = [self.cycle(d, refill=True) for _ in range(5)]
        finally:
            restored = self.gl("skillcrit", "hwp_attack_hcannon_off", "restore")
        observed = min(r["actual_damage"] for r in mixed)
        crit0 = baseline.get("offCritDmg", 0)
        expected = 2 * pistol_normal + cannon_crit * (crit0 + 8 * 0.02) / max(0.001, crit0)
        self.check("mixed_other_hand_real_crit_damage", ok and fixture.get("override_active") and not restored.get("override_active")
                   and all(r["clip"] == [24, 21] for r in mixed) and abs(observed - expected) <= 3,
                   {"gear": gear, "five_fixed_mixed_bursts": mixed,
                    "normal_pistol_component": pistol_normal, "baseline_cannon_critical_component": cannon_crit,
                    "baseline_off_crit_multiplier": crit0, "expected_off_magazine_after_its_shot": 8,
                    "expected_total_damage": expected, "observed_minimum_total_damage": observed,
                    "fixture": fixture, "fixture_restore": restored,
                    "note": "Five fixed trials retain chance main-hand crits; the minimum estimates two normal pistol rounds plus the forced off-hand cannon critical."})
        self.clear_dummies()
        self.to_town()

    def continuity(self):
        if not self.prepare("QAMagFloor"):
            return
        # Legal ilvl1 handguns keep contributing their magazines when the floor
        # reloads and the debug equipment-override script global resets.
        assigned = [self.gl("assign", "str", 10), self.gl("assign", "dex", 10)]
        d = self.open_dirs(130)[0]
        self.tough(d, 60)
        self.baseline = self.probe(rolls=1)
        self.learn_rank("hwp_fs_steady", 5)
        equipped, gear = self.fixture_loadout("hwp_glock_mh_01", "hwp_hcannon_oh_01")
        rows = [self.cycle(d, refill=trial == 0) for trial in range(4)]
        row = rows[-1]
        initial = self.bonuses(row)
        self.check("floor_unequal_setup", equipped and all(x.get("ok") for x in assigned)
                   and row["clip"] == [15, 12] and all(x["actual_damage"] > 0 for x in rows)
                   and abs(initial[0] - 0.14) < 0.003 and abs(initial[1] - 0.10) < 0.003,
                   {"gear": gear, "attribute_setup": assigned, "four_natural_cycles": rows, "crit_bonuses": initial})
        self.next_floor()
        time.sleep(2)
        self.god_on()
        self.gl("kill", 6000, "tag:enemy")
        self.check("floor_god_disabled", self.ordinary_damage(), {"fixture": "next cleared isolated floor"})
        state = self.gl("state")
        clip = self.clip()
        maximum = self.clip_max()
        ids = [s.get("id") for s in self.bar().get("skills", [])]
        d = self.open_dirs(130)[0]
        self.tough(d, 60)
        after = {"stats": self.probe(rolls=1)}
        added = self.bonuses(after)
        self.check("floor_preserves_unequal_magazines", state.get("phase") == "mission" and clip == 12 and maximum == 24
                   and "hwp_attack_glock" in ids and "hwp_attack_hcannon_off" in ids
                   and abs(added[0] - 0.14) < 0.003 and abs(added[1] - 0.10) < 0.003,
                   {"clip": clip, "capacity": maximum, "crit_bonuses": added, "state": state, "skills": ids,
                    "note": "No ammo setter or equipment change is used after the floor transition."})
        row = self.cycle(d)
        added = self.bonuses(row)
        self.check("floor_next_natural_burst", row["clip"] == [12, 9] and row["actual_damage"] > 0
                   and abs(added[0] - 0.10) < 0.003 and abs(added[1] - 0.08) < 0.003,
                   {"natural_cycle": row, "own_remaining": [5, 4], "crit_bonuses": added})
        self.clear_dummies()
        self.to_town()


def run(p, section="edges", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("magazine_edges_crashed", False, {"section": section, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
