"""Actual Backstab critical-hit stacks and Cinders spell-hit procs.

Backstab's expiring skillcrit fixture only sets up the chance: numeric ! text,
target HP loss and native bleeding stacks are independently required. Cinders
triggers on spellhit, so its fixed ordinary-damage trials do not force crits.
"""
import re
import math
import time

from gamelab.bots.qa_class_procs import Checks as ProcChecks
from gamelab.bots.qa_classes import QA_DUMMY_FILTER


class Checks(ProcChecks):
    def target_snapshot(self, uid):
        mark = len(self.g.gl)
        self.gl("multi", "actorbuffs", 200, QA_DUMMY_FILTER, "+", "floats")
        replies = self.g.gl[mark:]
        target = next((a for r in replies for a in r.get("actors", []) if a.get("unit") == uid), None)
        floats = next((r for r in replies if "texts" in r), {})
        return target, floats

    def cast_once(self, skill, direction):
        mark = len(self.g.gl)
        self.gl("multi", "mana", 999, "+", "input", 1000, 0, 0, direction[0], direction[1], "+",
                "castat", skill, round(direction[0] * 64), round(direction[1] * 64), "nocd")
        return next((r for r in self.g.gl[mark:] if r.get("skill") == skill and "activated" in r), {})

    def direction_to(self, target):
        px, py = self.me()
        dx, dy = target["x"] - px, target["y"] - py
        length = math.hypot(dx, dy)
        if length <= 0:
            raise RuntimeError("target overlaps player; no valid cast direction")
        return dx / length, dy / length

    def backstab(self):
        if not self.prepare("hwp_thief", "hwp_thief_assassin", "QABackstab"):
            return
        skills = self.gl("skills")
        main = next((s.get("id") for s in skills.get("skills", []) if s.get("button") == "main"), None)
        self.flag("backstab_main_skill", bool(main), str(skills))
        if not main:
            return
        rows, passed = [], True
        try:
            forced = self.gl("skillcrit", main, 1)
            self.flag("backstab_crit_fixture", forced.get("override_active") and forced.get("crit_chance") == 1, str(forced))
            passed &= bool(forced.get("override_active")) and forced.get("crit_chance") == 1
            for rank, expected in ((0, 0), (1, 2), (5, 6)):
                tag = f"backstab_r{rank}"
                learned = self.learn("hwp_thief_backstab", rank, tag)
                # Rank changes rebuild native skill modifiers; explicitly verify
                # the fixture survived, and refresh its bounded60s expiry.
                fixture = self.gl("skillcrit", main, 1)
                target = self.fresh_dummy(tag, offset=18)
                if not target:
                    passed = False
                    continue
                direction = self.direction_to(target)
                cast = self.cast_once(main, direction)
                time.sleep(0.15)
                after, floats = self.target_snapshot(target["unit"])
                crits = [f for f in floats.get("texts", []) if f.get("type") == 11
                         and re.fullmatch(r"[0-9]+!", f.get("text", ""))]
                stacks = sum(s.get("count", 0) for s in (after or {}).get("stacks", [])
                             if "bleeding" in s.get("tags", []))
                damage = target["hpExact"] - after["hpExact"] if after else None
                ok = (learned and fixture.get("override_active") and cast.get("activated") and after is not None
                      and damage is not None and damage > 0 and bool(crits) and floats.get("truncated") == 0
                      and stacks == expected)
                row = {"rank": rank, "expected_stacks": expected, "actual_stacks": stacks, "fixture": fixture,
                       "before": target, "after": after, "actual_hp_lost": damage, "cast": cast,
                       "critical_texts": crits, "floats": floats}
                self.flag(tag + "_actual_crit_bleed", bool(ok), str(row))
                passed &= bool(ok)
                rows.append(row)
        finally:
            restored = self.gl("skillcrit", main, "restore")
            self.flag("backstab_fixture_restored", restored.get("ok") and not restored.get("override_active"), str(restored))
        self.flag("backstab_observed", passed and len(rows) == 3 and self.out.get("backstab_fixture_restored"))
        self.out["backstab_trials"] = rows
        self.to_town()

    def cinders(self):
        if not self.prepare("hwp_witch_hunter", "hwp_witch_hunter_pyromancer", "QACinders"):
            return
        ward = "hwp_witch_hunter_ward"
        if not self.learn(ward, 1, "cinders_ward"):
            return
        rows, passed = [], True
        for rank, trials in ((0, 8), (1, 40), (5, 40)):
            learned = self.learn("hwp_witch_hunter_cinders", rank, f"cinders_r{rank}")
            count, valid = 0, 0
            for index in range(trials):
                tag = f"cinders_r{rank}_{index}"
                target = self.fresh_dummy(tag, offset=64)
                if not target:
                    continue
                direction = self.direction_to(target)
                cast = self.cast_once(ward, direction)
                time.sleep(0.2)
                after, floats = self.target_snapshot(target["unit"])
                damage = target["hpExact"] - after["hpExact"] if after else None
                hit = cast.get("activated") and damage is not None and damage > 0
                proc = "armor_break" in self.tags(after)
                valid += bool(hit)
                count += bool(hit and proc)
                rows.append({"rank": rank, "trial": index, "cast": cast, "before": target, "after": after,
                             "actual_hp_lost": damage, "armor_break": proc, "actual_spell_hit": bool(hit), "floats": floats})
            # Fixed samples never rerun until a random success. A zero outcome at
            # either built rank remains a failed observation for investigation.
            ok = learned and valid == trials and (count == 0 if rank == 0 else 0 < count < trials)
            self.flag(f"cinders_r{rank}_spell_proc", bool(ok), f"{count}/{valid} actual Ward hits proc armor break, fixed trials {trials}")
            passed &= bool(ok)
        self.flag("cinders_observed", passed and len(rows) == 88)
        self.out["cinders_trials"] = rows
        self.to_town()


def run(p, sections="backstab,cinders", **_):
    c = Checks(p)
    for section in sections.split(","):
        try:
            getattr(c, section)()
        except Exception as exc:
            c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
