"""All positive direct-damage passive ranks through fixed actual main-input benches.

Original low/max files remain unchanged. Proc occurrence/attribution and actualHP
are measured; fixed samples are not rerun until success. Instantiated nominal chance/raw payload are read independently; actual hit damage
coefficients/proc distributions are not inferred from pool-damage averages.
"""
import math

from gamelab.bots.qa_class_procs import Checks as ProcChecks, PROCS as BASE_PROCS
from gamelab.bots.qa_classes import QA_DUMMY_FILTER
from gamelab.hps import hash_string
PROCS={k:(*v[:3],tuple(range(0 if k=="poisoned_blades" else 1,6))) for k,v in BASE_PROCS.items()}

NOMINAL_CHANCES = {"poisoned_blades": (.25, .30, .35, .40, .50),
                   "torch": (.30, .35, .40, .45, .50)}
NATIVE_PAYLOADS = {"poisoned_blades": ("poison", (15, 25, 35, 45, 55)),
                   "torch": ("fire", (10, 18, 26, 34, 42))}
ELEMENTS = ("physical", "fire", "ice", "lightning", "poison", "pure")


def uint32(value):
    return value & 0xffffffff if isinstance(value, int) and not isinstance(value, bool) else None


def native_payload_valid(reply, skill, key, rank):
    # Nominal actual instantiated data; stochastic and partly censored native
    # Fire/Poison pool means cannot establish exact per-proc HP coefficients.
    records = reply.get("records")
    integers = ("state_count", "scanned", "matches", "count", "scan_truncated", "truncated")
    common = (reply.get("ok") is True and reply.get("filter") == skill
              and uint32(reply.get("filter_hash")) == uint32(hash_string(skill))
              and all(isinstance(reply.get(k), int) and not isinstance(reply[k], bool)
                      and reply[k] >= 0 for k in integers)
              and reply.get("scan_truncated") == 0 and reply.get("truncated") == 0
              and reply.get("scanned") == reply.get("state_count")
              and isinstance(records, list) and all(isinstance(r, dict) for r in records)
              and reply.get("count") == len(records))
    if not common:
        return False
    if rank == 0:
        return reply["matches"] == 0 and records == []
    if reply["matches"] != 1 or len(records) != 1:
        return False
    row = records[0]
    chance = NOMINAL_CHANCES[key][rank-1]
    element, payloads = NATIVE_PAYLOADS[key]
    payload = row.get("payload", {})
    effects = payload.get("effects", [])
    if not (type(row.get("verb")) is int and row["verb"] == 1
            and uint32(row.get("source_id")) == uint32(hash_string(skill))
            and type(row.get("trigger")) is int and row["trigger"] == 1
            and row.get("effect_trigger") is True and row.get("timed") is False
            and row.get("target_self") is False
            and all(isinstance(row.get(k), (int, float)) and not isinstance(row[k], bool)
                    and math.isfinite(row[k]) for k in ("intensity", "chance0", "chance1", "nominal_chance"))
            and row["intensity"] == 1 and abs(row["nominal_chance"]-chance) <= .000001
            and payload.get("present") is True and type(payload.get("truncated")) is int
            and payload["truncated"] == 0 and type(payload.get("count")) is int
            and payload["count"] == 1 and isinstance(effects, list) and len(effects) == 1
            and isinstance(effects[0], dict)):
        return False
    effect = effects[0]
    return bool(effect.get("entry") is True and effect.get("present") is True
                and effect.get("damage") is True and type(effect.get("merged")) is int
                and effect["merged"] == 0
                and uint32(effect.get("weapon_info")) == uint32(hash_string(skill))
                and all(type(effect.get(k)) is int
                        and effect[k] == (payloads[rank-1] if k == element else 0)
                        for k in ELEMENTS))


class Checks(ProcChecks):
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
            payload = self.gl("qa_trigger_payload", skill)
            payload_ok = native_payload_valid(payload, skill, key, rank)
            self.flag(tag + "_native_payload", payload_ok, str(payload))
            passed &= payload_ok
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
                   "native_payload": payload, "native_payload_ok": payload_ok,
                   "proc_damage": damage, "proc_hits": hits, "ordinary_hits": ordinary_hits}
            self.flag(tag + "_actual_hits", live_path, str(row))
            self.flag(tag + "_proc", live_path and proc_ok, str(row))
            passed &= live_path and proc_ok
            if hits:
                per_hit[rank] = damage / hits
            rows.append(row)
        tables_ok = (len(rows) == len(ranks) and
                     all(row["native_payload_ok"] for row in rows))
        self.flag(key + "_instantiated_rank_tables", tables_ok)
        self.out[key + "_mean_proc_diagnostics"] = per_hit
        self.flag(key + "_observed", passed and tables_ok)
        self.out[key + "_limits"] = (
            "Actual instantiated nominal chance/raw elemental payload and native real-proc/HP evidence. "
            "Mean damage is diagnostic only: native Fire/Poison pool ticks share attribution and are censored by fixed bench end. "
            "No exact proc probability distribution, fully settled per-proc HP coefficient, ordinary-run or co-op credit.")
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
            if rank in range(1, 6):
                target = self.fresh_dummy(f"planned_r{rank}")
                event = self.bench(f"planned_r{rank}", 10000) if target else {}
                after = self.actor(target["unit"], QA_DUMMY_FILTER) if target else None
                actual_hits = (event.get("dummyCount") == 1 and event.get("total", 0) > 0
                               and event.get("hooked", 0) > 0 and after is not None
                               and after.get("hpExact",15000) < target["hpExact"])
                self.flag(f"planned_r{rank}_actual_damage", actual_hits, str(event))
                row["event"] = event
                row["before"], row["after"] = target, after
                passed &= actual_hits
            rows.append(row)
            passed &= ok
        self.flag("planned_attack_all_ranks", passed)
        self.out["planned_attack_trials"] = rows
        self.to_town()

def run(p,sections="poisoned_blades,torch,planned_attack",**_):
    c=Checks(p)
    for section in sections.split(","):
        try:
            c.proc(section) if section in PROCS else getattr(c,section)()
        except Exception as exc:
            c.flag(section+"_crashed",False,repr(exc))
    c.out["notes"]=c.notes
    c.out["terminal"]=" | ".join(c.notes)[-5000:]
    return c.out
