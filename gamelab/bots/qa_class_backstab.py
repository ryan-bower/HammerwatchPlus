"""Controlled Backstab: actual focused main input, one native swing, all ranks.

The legal common1 shortsword has one hit and no native bleed. This isolates the
passive from the starter daggers' two swings and the dagger's own20% bleed.
Eight fixed modifier0 controls classify actual physical crit text; native global
physical chance is deliberately retained, and at least one actual noncrit is required.
The benchmark resets resources/cooldowns as an explicit controlled fixture;
its noskills path only holds the ordinary main button while gameplay has focus.
"""
import math
import re

from gamelab.bots.qa_class_procs import Checks as ProcChecks
from gamelab.bots.qa_classes import QA_DUMMY_FILTER
from gamelab.hps import hash_string


class Checks(ProcChecks):
    def snapshot(self, uid):
        # Read the short-lived numeric critical text first, in the same batch as
        # the scene clock and exact target HP/stacks; no intervening GL command.
        mark = len(self.g.gl)
        self.gl("multi", "floats", "+", "clock", "+", "actorbuffs", 200, QA_DUMMY_FILTER)
        replies = self.g.gl[mark:]
        floats = next((r for r in replies if "texts" in r), {})
        clock = next((r for r in replies if "sceneMs" in r), {})
        actor = next((a for r in replies for a in r.get("actors", []) if a.get("unit") == uid), None)
        return actor, floats, clock

    def backstab(self):
        if not self.prepare("hwp_thief", "hwp_thief_assassin", "QABackstabInput"):
            return
        equip = self.gl("equip", "mainhand_shortsword_01", "common", 1)
        skills = self.gl("skills")
        mains = [s for s in skills.get("skills", []) if s.get("button") == "main"]
        main = mains[0].get("id") if len(mains) == 1 else None
        equipped = self.gl("inspect", "player", "equipped").get("value")
        item_present = any(isinstance(x, list) and len(x) >= 4
                           and int(x[1]) & 0xFFFFFFFF == hash_string("mainhand_shortsword_01")
                           and x[3] == 1 for x in equipped or [])
        setup = bool(equip.get("ok") and equip.get("quality") == 1 and equip.get("ilvl") == 1
                     and item_present and main == "attack_swing_shortsword")
        self.flag("backstab_clean_one_swing_weapon", setup,
                  str({"equip": equip, "equipped": equipped, "skills": skills}))
        if not setup:
            return
        rows, passed, observed_noncrits = [], True, 0
        primary_error = None
        try:
            for rank, critical, trial in [(r, True, 0) for r in range(6)] + [(5, False, i) for i in range(8)]:
                tag = f"backstab_r{rank}_crit" if critical else f"backstab_r5_unforced_{trial}"
                learned = self.learn("hwp_thief_backstab", rank, tag)
                fixture = self.gl("skillcrit", main, 1 if critical else 0)
                fixture_ok = bool(fixture.get("ok") and fixture.get("override_active")
                                  and fixture.get("crit_chance") == int(critical))
                target = self.fresh_dummy(tag, offset=26)
                if not target:
                    passed = False
                    continue
                px, py = self.me()
                distance = math.hypot(target["x"]-px, target["y"]-py)
                physical_probe = self.gl("critprobe", 0, 200, QA_DUMMY_FILTER, main)
                start = self.gl("clock")
                event = self.bench(tag, 350)
                after, floats, end = self.snapshot(target["unit"])
                aliases = (main, "#" + str(hash_string(main)))
                hits = sum(w.get("hits", 0) for w in event.get("weapons", []) if w.get("weapon") in aliases)
                main_damage = sum(w.get("dmg", 0) for w in event.get("weapons", []) if w.get("weapon") in aliases)
                fresh = []
                for f in floats.get("texts", []):
                    lived = f.get("lived")
                    if not isinstance(lived, (int, float)) or not isinstance(end.get("sceneMs"), (int, float)):
                        continue
                    birth = end["sceneMs"]-lived
                    if (isinstance(start.get("sceneMs"), (int, float)) and start["sceneMs"]-20 <= birth <= end["sceneMs"]
                            and 0 <= lived <= 500 and abs(f.get("x", 1e9)-target["x"]) <= 24
                            and abs(f.get("y", 1e9)-target["y"]) <= 64):
                        fresh.append(f)
                crits = [f for f in fresh if f.get("type") == 11
                         and re.fullmatch(r"[0-9]+!", f.get("text", "")) and int(f.get("text", "0").rstrip("!")) > 0]
                stacks = sum(s.get("count", 0) for s in (after or {}).get("stacks", [])
                             if "bleeding" in s.get("tags", []))
                numeric = [f for f in fresh if f.get("type") in (7, 8, 9, 11)
                           and re.fullmatch(r"[0-9]+!?", f.get("text", "")) and int(f.get("text", "0").rstrip("!")) > 0]
                observed_critical = len(crits) == 1
                expected = rank+1 if rank and observed_critical else 0
                damage = target["hpExact"]-after["hpExact"] if after is not None else None
                actual_path = (8 <= distance <= 30 and event.get("dummyCount") == 1
                               and 350 <= event.get("ms", 0) <= 450 and event.get("frames", 0) >= 5
                               and hits == 1 and main_damage > 0 and event.get("total", 0) > 0
                               and after is not None and damage is not None and damage > 0)
                text_ok = len(numeric) == 1 and (len(crits) == 1 if critical else len(crits) in (0, 1))
                if not critical and text_ok and not observed_critical:
                    observed_noncrits += 1
                ok = bool(learned and fixture_ok and actual_path and floats.get("truncated") == 0
                          and text_ok and stacks == expected)
                row = {"rank": rank, "forced_skill_modifier_crit": critical, "trial": trial,
                       "observed_critical": observed_critical, "physical_probe": physical_probe, "expected_stacks": expected, "actual_stacks": stacks,
                       "fixture": fixture, "before": target, "after": after, "distance": distance,
                       "actual_hp_lost": damage, "event": event, "main_hits": hits, "main_damage": main_damage,
                       "start_clock": start, "end_clock": end, "fresh_texts": fresh,
                       "critical_texts": crits, "floats": floats}
                self.flag(tag+"_actual_effect", ok, str(row))
                rows.append(row)
                passed &= ok
        except Exception as exc:
            primary_error = repr(exc)
            passed = False
            self.flag("backstab_input_exception", False, primary_error)
        finally:
            # A transport failure must retain its original cause even if cleanup
            # also fails. Root teardown isolates the fixture in either case.
            try:
                restored = self.gl("skillcrit", main, "restore")
                restored_ok = bool(restored.get("ok") and not restored.get("override_active"))
                self.flag("backstab_input_fixture_restored", restored_ok, str(restored))
            except Exception as exc:
                restored_ok = False
                self.flag("backstab_input_fixture_restored", False, repr(exc))
        self.out["backstab_input_trials"] = rows
        self.out["backstab_input_error"] = primary_error
        self.flag("backstab_observed_noncrit_control", observed_noncrits >= 1, str(observed_noncrits)+"/8 fixed unforced physical hits")
        self.flag("backstab_all_ranks_actual", passed and len(rows) == 14 and observed_noncrits >= 1 and restored_ok)
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.backstab()
    except Exception as exc:
        c.flag("backstab_input_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
