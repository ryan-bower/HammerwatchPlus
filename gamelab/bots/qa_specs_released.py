"""Controlled Released Essence kill/payout/cap and Combustion ordering.

Tagged QA actors isolate the native elite/boss tag predicate. This does not
claim ordinary elite/boss combat, real boss AI, or multiplayer attribution.
"""
from gamelab.bots.qa_specs_branding_effects import Checks as Base, PB, EE, ESSENCE, RELEASE, COMBUST, SPREAD, EMPOWER
from gamelab.bots.qa_observe import collect

PREFIX = "gamelab/qa_released_"


class Checks(Base):
    def trial(self, tag, kind, initial, expected, released, combustion=False):
        self.g.note("qa_released_trial_start", tag=tag, kind=kind, initial=initial, expected=expected)
        self.gl("kill", 350, "qa_released_")
        self.gl("kill", 350, "target_dummy")
        if not self.scene_gap(1200):
            self.flag(tag + "_scene_ready", False)
            return {"ok": False, "error": "native scene time did not progress"}
        path = PREFIX + kind + ".unit"
        spawned = self.gl("spawn", path, round(self.direction[0] * 40), round(self.direction[1] * 40))
        uid = spawned.get("unit")
        before = next((u for u in self.gl("near", 100, "qa_released_").get("units", [])
                       if u.get("unit") == uid), {})
        setup = spawned.get("ok") and before.get("hpMax") == 1 and before.get("hpExact") == 1
        self.set_stacks(ESSENCE, initial)
        initial_read = self.gl("givestacks", ESSENCE, 0)
        status_before = self.specs()
        branded, brand_log = self.brand_cast(PB, *self.direction)
        classified = ("branded an elite" in brand_log) if kind != "ordinary" else ("branded an enemy" in brand_log)
        request = self.gl("buffobserve", tag, 6000, "-", ESSENCE, uid) if setup and classified else {}
        cast, claw_log = self.detonate() if request.get("ok") else (False, "observer/setup rejected")
        observed = collect(self.g, tag, timeout=30) if request.get("ok") else {}
        after = next((u for u in self.gl("near", 100, "qa_released_").get("units", [])
                      if u.get("unit") == uid), {})
        # Zero-delta native stack read; it does not manufacture or consume Essence.
        final_read = self.gl("givestacks", ESSENCE, 0)
        status_after = self.specs()
        events = observed.get("events", [])
        dead = bool(before) and (not after or after.get("dead") is True or after.get("hpExact", 1) <= 0)
        ok = (setup and branded and classified and cast and "claw (recast)" in claw_log and dead
              and initial_read.get("stacks") == initial and final_read.get("stacks") == expected
              and observed.get("usable") is True and events
              and events[0].get("stacks") == initial and events[-1].get("stacks") == expected
              and events[0].get("target_valid") is True and events[0].get("target_hpExact") == 1
              and any(e.get("target_valid") is False or e.get("target_hpExact", 1) <= 0 for e in events[1:])
              and (expected == initial or any(e.get("stacks") == expected for e in events[1:])))
        if combustion:
            ok = ok and f"{initial} essence spent" in claw_log
        self.flag(tag, bool(ok), str({"kind": kind, "initial": initial, "expected": expected,
                  "setup": before, "after": after, "initial_read": initial_read, "final_read": final_read,
                  "brand": brand_log, "claw": claw_log, "observer_errors": observed.get("errors")}))
        row = {"tag": tag, "kind": kind, "initial": initial, "expected": expected, "orb_payout": released,
                "combustion": combustion, "before": before, "after": after,
                "initial_read": initial_read, "final_read": final_read,
                "brand_log": brand_log, "claw_log": claw_log, "observation": observed, "ok": bool(ok),
                "native_counters_before": status_before, "native_counters_after": status_after}
        self.g.note("qa_released_trial", row=row)
        return row

    def released(self):
        if not self.prepare("released"):
            return
        parents = self.rank(PB, 5, "released_pyre") and self.rank(EE, 5, "released_essence")
        native_orbs = {orb: self.gl("orb", orb, 0) for orb in (RELEASE, COMBUST, SPREAD, EMPOWER)}
        clean_orbs = all(reply.get("level") == 0 for reply in native_orbs.values())
        self.flag("released_parents_and_control", bool(parents and clean_orbs), str(native_orbs))
        if not parents or not clean_orbs:
            return
        rows = []
        self.out["released_trials"] = rows
        rows.append(self.trial("released_control_boss", "boss", 0, 0, 0))
        for rank, payout in ((1, 3), (2, 6)):
            orb = self.gl("orb", RELEASE, 1)
            self.flag(f"released_rank{rank}_equipped", orb.get("level") == rank, str(orb))
            if orb.get("level") != rank:
                continue
            for kind in ("ordinary", "elite", "boss"):
                rows.append(self.trial(f"released_r{rank}_{kind}", kind, 0,
                                       0 if kind == "ordinary" else payout, payout))
            rows.append(self.trial(f"released_r{rank}_cap", "boss", 8, 10, payout))
        combust = self.gl("orb", COMBUST, 3)
        self.flag("released_combustion_legal_ranks", combust.get("level") == 3,
                  str({"combustion": combust, "released": self.gl("orb", RELEASE, 0),
                       "scope": "Combustion3 + Released Essence2, all other orbs0"}))
        if combust.get("level") == 3:
            rows.append(self.trial("released_combustion_spend_then_payout", "boss", 8, 6, 6, True))
        self.out["released_trials"] = rows
        self.flag("released_all_trials", len(rows) == 10 and all(row.get("ok") for row in rows))
        self.gl("skillcrit", PB, "restore")
        self.to_town()


def run(pilot, **_):
    c = Checks(pilot)
    c.released()
    return {**c.out, "notes": c.notes, "measurement_only": True,
            "expected_source": ["mods/specs/scripts/HWP/Specs/Branding.as",
                                "mods/specs/scripts/HWP/Specs/Common.as"],
            "limits": ["Controlled HP1 actors with native ordinary/elite/boss tags",
                       "Ordinary real boss fights and co-op attribution remain unverified"]}
