"""Bounded HoH1 passive observations through real hits and native kill hooks.

These are controlled fixtures. Bench drives normal held attacks and native
damage; kill cases explicitly use lab lethals with a real player killer. Every
fixed trial is retained, including zero-proc outcomes. No retry-until-pass.
"""
import time

from gamelab.bots.qa_classes import Checks as AbilityChecks, QA_DUMMY, QA_DUMMY_FILTER
from gamelab.bots.plan_classesa import BRUTE
from gamelab.hps import hash_string


PROCS = {
    "poisoned_blades": ("hwp_thief", "hwp_thief_shadow", "hwp_thief_poisoned_blades", (0, 1, 5)),
    "torch": ("hwp_witch_hunter", None, "hwp_witch_hunter_torch", (1, 5)),
}


class Checks(AbilityChecks):
    def prepare(self, cls, mastery, name):
        if not self.new_char(cls, name):
            return False
        self.hwp("levelup 20", 0.3)
        self.hwp("skillpoints 1000", 0.3)
        if mastery:
            sub = self.gl("subclass", mastery)
            self.flag(name + "_mastery", sub.get("class") == mastery, str(sub))
            if sub.get("class") != mastery:
                return False
        if not self.arena(name):
            return False
        return True

    def learn(self, skill, rank, tag):
        current = self.gl("skilltip", skill).get("level", -1)
        result = self.gl("skill", skill, rank - current) if 0 <= current < rank else {"level": current}
        ok = result.get("level") == rank
        self.flag(tag + "_rank", ok, str(result))
        return ok

    def fresh_dummy(self, tag, offset=26):
        self.clear()
        # The fixture has target_dummy tags; cleanup must not assume enemy tags.
        self.gl("kill", 800, QA_DUMMY_FILTER)
        _, direction = self.open_dirs()[0]
        spawned = self.gl("spawn", QA_DUMMY, round(direction[0] * offset), round(direction[1] * offset))
        target = self.actor(spawned.get("unit"), QA_DUMMY_FILTER) if spawned.get("unit") is not None else None
        valid = bool(target) and target.get("hpMax") == 15000 and abs(target.get("hpExact", -1) - 15000) < 0.01
        self.flag(tag + "_fixture", valid, str(target or spawned))
        return target if valid else None

    def bench(self, tag, ms=30000):
        unique = f"clproc{int(time.time() * 1000)}{tag}"
        started = self.gl("bench", unique, ms, 200, "noskills")
        if not started.get("ok"):
            return {"setup_error": started}
        return self.g.wait_gl(lambda o: o.get("ev") == "bench" and o.get("tag") == unique,
                              ms / 1000 + 15) or {"setup_error": "missing terminal bench event"}

    def proc(self, key):
        cls, mastery, skill, ranks = PROCS[key]
        if not self.prepare(cls, mastery, "QAProc" + key):
            return
        rows, passed, per_hit = [], True, {}
        for rank in ranks:
            tag = f"{key}_r{rank}"
            if not self.learn(skill, rank, tag):
                passed = False
                continue
            target = self.fresh_dummy(tag)
            if not target:
                passed = False
                continue
            event = self.bench(tag)
            after = self.actor(target["unit"], QA_DUMMY_FILTER)
            aliases = (skill, "#" + str(hash_string(skill)))
            proc_rows = [w for w in event.get("weapons", []) if w.get("weapon") in aliases]
            damage = sum(w.get("dmg", 0) for w in proc_rows)
            hits = sum(w.get("hits", 0) for w in proc_rows)
            ordinary_hits = sum(w.get("hits", 0) for w in event.get("weapons", []) if w.get("weapon") not in aliases)
            live_path = (event.get("dummyCount") == 1 and event.get("total", 0) > 0 and ordinary_hits >= 20
                         and after is not None and 0 < after.get("hpExact", 0) < 15000)
            proc_ok = damage > 0 and hits > 0 if rank else damage == 0 and hits == 0
            row = {"rank": rank, "event": event, "before": target, "after": after,
                   "proc_damage": damage, "proc_hits": hits, "ordinary_hits": ordinary_hits}
            self.flag(tag + "_actual_hits", live_path, str(row))
            self.flag(tag + "_proc", live_path and proc_ok, str(row))
            passed &= live_path and proc_ok
            if hits:
                per_hit[rank] = damage / hits
            rows.append(row)
        scaled = 1 in per_hit and 5 in per_hit and per_hit[5] > per_hit[1]
        self.flag(key + "_damage_scales", scaled, str(per_hit))
        self.flag(key + "_observed", passed and len(rows) == len(ranks) and scaled)
        self.out[key + "_trials"] = rows
        self.to_town()

    def planned_attack(self):
        skill = "hwp_gladiator_planned_attack"
        if not self.prepare("hwp_gladiator", None, "QAPlanned"):
            return
        target = self.fresh_dummy("planned")
        if not target:
            return
        baseline = self.gl("critprobe", 0, 200, QA_DUMMY_FILTER).get("damageMul", [])
        rows, passed = [], len(baseline) == 2
        for rank, multiplier in enumerate((1.06, 1.12, 1.18, 1.24, 1.30), 1):
            learned = self.learn(skill, rank, f"planned_r{rank}")
            probe = self.gl("critprobe", 0, 200, QA_DUMMY_FILTER)
            actual = probe.get("damageMul", [])
            ok = (learned and len(actual) == 2 and len(baseline) == 2
                  and abs(actual[0] - baseline[0] * multiplier) < 0.001
                  and abs(actual[1] - baseline[1]) < 0.001)
            self.flag(f"planned_r{rank}_multiplier", ok, f"baseline {baseline}, probe {probe}")
            row = {"rank": rank, "multiplier": multiplier, "probe": probe}
            if rank in (1, 5):
                target = self.fresh_dummy(f"planned_r{rank}")
                event = self.bench(f"planned_r{rank}", 10000) if target else {}
                actual_hits = event.get("total", 0) > 0 and event.get("hooked", 0) > 0
                self.flag(f"planned_r{rank}_actual_damage", actual_hits, str(event))
                row["event"] = event
                passed &= actual_hits
            rows.append(row)
            passed &= ok
        self.flag("planned_attack_all_ranks", passed)
        self.out["planned_attack_trials"] = rows
        self.to_town()

    def kill_proc(self, key):
        is_heal = key == "bloodlust"
        cls, mastery = (("hwp_gladiator", "hwp_gladiator_beastmaster") if is_heal
                        else ("hwp_witch_hunter", "hwp_witch_hunter_inquisitor"))
        skill = "hwp_gladiator_bloodlust" if is_heal else "hwp_witch_hunter_judgement"
        if not self.prepare(cls, mastery, "QAKill" + key):
            return
        rows, passed = [], True
        for rank in range(1, 6):
            tag = f"{key}_r{rank}"
            learned = self.learn(skill, rank, tag)
            self.clear()
            _, direction = self.open_dirs()[0]
            mark = len(self.g.gl)
            self.gl("multi", "spawn", BRUTE, round(direction[0] * 32), round(direction[1] * 32), "+",
                    "hurt" if is_heal else "mana", 0.5 if is_heal else 0, "+", "state", "+",
                    "kill", 100, "bandit_brute", "me", "+", "state")
            replies = self.g.gl[mark:]
            players = [o["player"] for o in replies if isinstance(o.get("player"), dict)]
            kills = sum(o.get("killed", 0) for o in replies)
            field = "hp" if is_heal else "manaExact"
            delta = players[-1].get(field, 0) - players[0].get(field, 0) if len(players) == 2 else None
            expected = rank * 10 if is_heal else rank + 2
            tolerance = 1.0 if is_heal else 0.02
            ok = learned and kills == 1 and delta is not None and abs(delta - expected) <= tolerance
            row = {"rank": rank, "expected": expected, "delta": delta, "replies": replies,
                   "path": "controlled actor.Kill(localPlayer), real KilledActor hooks; no ordinary-combat claim"}
            self.flag(tag + "_effect", ok, str(row))
            passed &= ok
            rows.append(row)
        self.flag(key + "_all_ranks", passed)
        self.out[key + "_trials"] = rows
        self.to_town()


def run(p, sections="poisoned_blades,torch,planned_attack", **_):
    c = Checks(p)
    for section in sections.split(","):
        try:
            if section in PROCS:
                c.proc(section)
            elif section in ("bloodlust", "judgement"):
                c.kill_proc(section)
            else:
                getattr(c, section)()
        except Exception as exc:
            c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
