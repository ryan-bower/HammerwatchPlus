"""Actual bench radius: one nearby target, one live distant target, native HP."""
import math
from gamelab.bots.qa_class_procs import Checks as ProcChecks
from gamelab.bots.qa_classes import QA_DUMMY, QA_DUMMY_FILTER

class Checks(ProcChecks):
    def check_radius(self):
        if not self.prepare("hwp_thief", None, "QABenchRadius"):
            return
        # Explicit controlled setup: remove every old dummy, including native
        # level-authored ones, before creating the two identified real actors.
        cleanup = self.gl("kill", 12000, "target_dummy")
        self.gl("input", 1, 0, 0)
        _, direction = self.open_dirs()[0]
        px, py = self.me()
        near = self.gl("spawn", QA_DUMMY, round(direction[0]*26), round(direction[1]*26))
        far = self.gl("spawn", QA_DUMMY, round(direction[0]*600), round(direction[1]*600))
        actors = self.gl("actorbuffs", 2000, QA_DUMMY_FILTER).get("actors", [])
        first = next((a for a in actors if a.get("unit")==near.get("unit")), None)
        foreign = next((a for a in actors if a.get("unit")==far.get("unit")), None)
        valid = (first is not None and foreign is not None and first["unit"] != foreign["unit"]
                 and first.get("hpMax")==15000 and foreign.get("hpMax")==15000
                 and first.get("hpExact")==15000 and foreign.get("hpExact")==15000
                 and 8 <= math.dist((px,py),(first["x"],first["y"])) <= 30
                 and math.dist((px,py),(foreign["x"],foreign["y"])) >= 400)
        self.flag("bench_radius_two_real_fixtures", bool(valid), str({"cleanup":cleanup,"near":first,"far":foreign}))
        if not valid:
            return
        event = self.bench("explicitradius",1000)
        afters = self.gl("actorbuffs",2000,QA_DUMMY_FILTER).get("actors",[])
        after = next((a for a in afters if a.get("unit")==first["unit"]),None)
        far_after = next((a for a in afters if a.get("unit")==foreign["unit"]),None)
        target_count = (event.get("dummyCount")==1 and len(event.get("dummies",[]))==1
                        and all(0 <= d.get("dist",-1) <= 200 for d in event.get("dummies",[])))
        local_damage = first["hpExact"]-after["hpExact"] if after else None
        actual_damage = (after is not None and local_damage is not None and local_damage>0
                         and event.get("hooked",0)>0 and event.get("total",0)>0
                         and abs(event["total"]-local_damage)<.1)
        unchanged = (far_after is not None and far_after.get("hpMax")==15000
                     and far_after.get("hpExact")==foreign["hpExact"]==15000)
        self.flag("bench_radius_native_target_count",bool(target_count),str(event))
        self.flag("bench_radius_actual_local_damage",bool(actual_damage),str({"damage":local_damage,"before":first,"after":after}))
        self.flag("bench_radius_foreign_untouched",bool(unchanged),str({"before":foreign,"after":far_after}))
        self.flag("bench_radius_observed",bool(valid and target_count and actual_damage and unchanged))
        self.out["bench_radius_trial"]={"cleanup":cleanup,"near":first,"far":foreign,"event":event,"after":after,"far_after":far_after,
            "scope":"Controlled native held-main bench radius200, actual real actors and HP. Harness proof only; no class rank or ordinary-play credit."}
        self.to_town()

def run(p,**_):
    c=Checks(p)
    try:
        c.check_radius()
    except Exception as exc:
        c.flag("bench_radius_crashed",False,repr(exc))
    c.out["notes"]=c.notes
    c.out["terminal"]=" | ".join(c.notes)[-5000:]
    return c.out
