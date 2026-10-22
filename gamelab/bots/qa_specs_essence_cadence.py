"""Discriminate all five Essence cooldowns with actual faster native wand hits.

The temporary native ActorBuff scales attack timing only. No hit/gain events or
positive Essence stacks are injected; original normal-cadence evidence remains.
"""
import json

from gamelab.bots.qa_specs_branding_effects import Checks as Parent, audit_rate, EE, PB

FIXTURE = "gamelab/qa_specs_rate_buffs.sval:ee_fast_hits"
COOLDOWNS = (2000, 1750, 1500, 1250, 1000)


class Checks(Parent):
    def rate_trial(self, tag, uid, duration_ms, branded):
        applied = self.gl("givebuff", FIXTURE)
        before = self.gl("hasbuff", FIXTURE)
        row = super().rate_trial(tag, uid, duration_ms, branded)
        after = self.gl("hasbuff", FIXTURE)
        events = row["observer"].get("events", [])
        candidates = [{"cooldown_ms": cd, **audit_rate(events, cd, 2 if branded else 1)} for cd in COOLDOWNS]
        matches = [a["cooldown_ms"] for a in candidates if a["ok"]]
        pre = before.get("buffs", [{}])[0]
        post = after.get("buffs", [{}])[0]
        fixture = (applied.get("ok") is True and before.get("ok") is True and after.get("ok") is True
                   and pre.get("path") == post.get("path") == FIXTURE and pre.get("on") is True and post.get("on") is True
                   and pre.get("left", 0) >= duration_ms + 2500 and post.get("left", 0) > 0
                   and bool(events) and all(e.get("attackMul") == 2.5 for e in events))
        unique = fixture and matches == [self.rate_cd]
        row.update(fixture_before=before, fixture_applied=applied, fixture_after=after,
                   native_speed_fixture_valid=fixture, all_source_candidate_models=candidates,
                   matching_source_cooldowns=matches, uniquely_discriminated=unique)
        row["ok"] = bool(row["ok"] and unique)
        self.flag(tag + "_unique_source_cooldown", bool(unique), str({"matches": matches, "expected": self.rate_cd,
                  "fixture": fixture, "observer_errors": row["observer"].get("errors")}))
        return row

    def all_ranks(self):
        if not self.prepare("essence_fast"):
            return
        equipped = self.gl("equip", "mainhand_wand_ice_01", 1, 1)
        self.flag("essence_fast_legal_wand", equipped.get("ok") is True, str(equipped))
        records, passed = [], equipped.get("ok") is True
        for rank, cooldown in enumerate(COOLDOWNS, 1):
            learned = self.rank(EE, rank, f"essence_fast_r{rank}")
            self.rate_cd = cooldown
            for trial in range(1, 4):
                label = f"ee-fast-r{rank}-t{trial}"
                noncrit = self.noncrit(label)
                targets = self.fresh()
                ready = self.scene_gap(2100)
                if not learned or not noncrit or not targets or not ready:
                    self.flag(label + "_fixed_trial", False, str({"learned": learned, "noncrit": noncrit,
                              "targets": targets, "ready": ready}))
                    records.append({"rank": rank, "trial": trial, "setup_valid": False})
                    passed = False
                    continue
                #3200ms gives at least one whole2000ms interval plus actual
                #in-cooldown hits. Semantic64-event retention stays bounded;
                #every observer still rejects truncation/missing evidence.
                plain = self.rate_trial(label + "-plain", targets[0], 3200, False)
                ready = self.scene_gap(2100)
                branded = self.rate_trial(label + "-branded", targets[0], 3200, True)
                ok = bool(ready and plain["ok"] and branded["ok"])
                self.flag(label + "_fixed_trial", ok)
                records.append({"rank": rank, "trial": trial, "expected_cooldown_ms": cooldown,
                                "plain": plain, "branded": branded, "ok": ok})
                passed = passed and ok
                (self.g.results / "essence-fast.partial.json").write_text(json.dumps(
                    {"flags": self.out, "trials": records}, indent=2) + "\n", encoding="utf-8")
        self.out["essence_fast_trials"] = records
        self.flag("essence_fast_all_15_trials", passed and len(records) == 15)
        self.gl("skillcrit", PB, "restore")
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.all_ranks()
    except Exception as exc:
        c.flag("essence_fast_exception", False, repr(exc))
    return {**c.out, "notes": c.notes,
            "scope": "Three fixed plain/branded native wand-hit trials for every rank; exact unique fit among all5source cooldowns with original67ms native phase bound. Controlled2.5 attack-speed fixture, godmode and explicit zero-stack/cooldown prerequisites. No ordinary acquisition/cadence/weapon-variant/lifecycle claim."}
