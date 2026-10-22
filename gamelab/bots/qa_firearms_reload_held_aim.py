"""Explosive Reload: normal native input holds Directional aim through its windup.

Original133709 remains retained. This controlled case uses already validated
inputsequence, not the pending normal-AOE mouse helper. No measurement setters.
"""
import math
import re
import time

from gamelab.bots.qa_firearms_reload_orbs import Checks as ReloadChecks
from gamelab.bots.qa_firearms_input_sequence import Checks as SequenceChecks, sequence_protocol


def trajectory_oracle(path, target, direction, anchor, sequence):
    required = ("x0", "y0", "x1", "y1", "px0", "py0", "t0", "t1", "n")
    if (not all(isinstance(path.get(k), (int, float)) and math.isfinite(path[k]) for k in required)
            or not all(isinstance(target.get(k), (int, float)) and math.isfinite(target[k]) for k in ("x", "y"))
            or not isinstance(anchor, int) or not sequence.get("valid") or not sequence.get("steps")):
        return {"valid": False, "reason": "missing actual target/path/native timing"}
    dx, dy = direction
    vx, vy = path["x1"]-path["x0"], path["y1"]-path["y0"]
    along = vx*dx+vy*dy
    cross = abs(vx*dy-vy*dx)
    distance = math.hypot(path["x1"]-target["x"], path["y1"]-target["y"])
    maximum_frame = max(row["dt_max"] for row in sequence["steps"])
    first_write, final_write = sequence["steps"][0]["first_write"], sequence["steps"][-1]["last_write"]
    born_scene_upper = anchor+path["t0"]+maximum_frame
    # TrackTask increments native dt before sampling; one full native endpoint
    # frame safely brackets its first sight relative to the same-batch clock.
    within_held_aim = first_write <= anchor+path["t0"]-maximum_frame and born_scene_upper <= final_write
    valid = (path["n"] >= 2 and path["t1"] > path["t0"] and along >= 70 and cross <= 1
             and distance <= 12 and within_held_aim)
    return {"valid": bool(valid), "forward_progress_px": along, "lateral_drift_px": cross,
            "last_sample_distance_to_actual_target_px": distance, "native_spawn_within_held_aim": within_held_aim,
            "native_born_scene_upper": born_scene_upper, "held_write_window": [first_write, final_write],
            "source": "ReloadThrowMag direction; reload_mag.inc GroundBouncing hit-target100px, blast min-radius12px; actual target/trace rather than assumed aim."}


class Checks(ReloadChecks):
    released = SequenceChecks.released
    step = staticmethod(SequenceChecks.step)

    def explosive_trial(self, d):
        spent = self.spend_burst(d)
        dd, dummy = self.tough(d, 100)
        near = self.gl("near", 400, "target_dummy")
        target = next((x for x in near.get("units", []) if x.get("unit") == dummy), {})
        hp0 = self.hps([dummy])[dummy]
        fixture = self.gl("skillcrit", "hwp_fs_reload", 1)
        mark = self.log_pos()
        tag = "reload-aim-%d" % int(time.time()*1000)
        track_tag = tag+"-mag"
        bar = self.bar()
        entry = self.entry(bar, "hwp_fs_reload")
        button = entry.get("button")
        if not button:
            raise RuntimeError("live Reload mapping missing")
        steps = [self.step(60, (0, 0), dd, button), self.step(1000, (0, 0), dd),
                 self.step(1000, (0, 0), dd), self.step(600, (0, 0), dd)]
        expected = [(60, [button]), (1000, []), (1000, []), (600, [])]
        event, protocol, accepted = {}, {}, {}
        try:
            # All three commands run in one native console frame. Track time is
            # anchored independently of Python/RPC scheduling and focus waits.
            anchor, tracking, accepted = self.g.gl_multi([
                ["skills"], ["track", track_tag, 4200, 500, "reload_mag_rifle.unit"],
                ["inputsequence", tag, *steps]])
            terminal = (self.g.wait_gl(lambda e: e.get("ev") == "inputsequence" and e.get("tag") == tag,
                                       timeout=15) or {}) if accepted.get("ok") else {}
            done = [e for e in self.g.gl if e.get("ev") == "input_done" and e.get("sequence") == tag]
            protocol = sequence_protocol(accepted, terminal, done, expected)
            event = self.track_finish(track_tag, 10)
            hp1 = self.hps([dummy])[dummy]
            crit_after = self.gl("skillcrit", "hwp_fs_reload")
            release = self.released()
            after_target = next((x for x in self.gl("near", 400, "target_dummy").get("units", [])
                                 if x.get("unit") == dummy), {})
        finally:
            restored = self.gl("skillcrit", "hwp_fs_reload", "restore")
        log = self.log_from(mark)
        thrown = re.findall(r"explosive reload: (\d+) rounds at (\d+)", log)
        paths = event.get("tracks", [])
        trajectory = trajectory_oracle(paths[0], target, dd, anchor.get("now"), protocol) if len(paths)==1 else {"valid":False}
        ready = [x for x in anchor.get("skills", []) if x.get("id") == "hwp_fs_reload"]
        parent_ids = {x.get("id", "").rsplit(".", 1)[0] for x in (anchor, tracking, accepted)}
        atomic = (all(x.get("ok") is True for x in (anchor, tracking, accepted)) and len(parent_ids)==1
                  and "" not in parent_ids and anchor.get("truncated") is False)
        track_complete = len(paths)==1 and event.get("ms",0)-paths[0].get("t1",0)>=150
        cooldown_ready = (len(ready)==1 and isinstance(ready[0].get("cd"), int) and ready[0]["cd"]<=0)
        crit_valid = all(x.get("ok") is True and x.get("skill")=="hwp_fs_reload"
                         and x.get("override_active") is True and x.get("left",0)>0
                         and x.get("crit_chance")==1 and x.get("spell_crit_chance")==0
                         for x in (fixture, crit_after))
        damage = (hp0-hp1)*10000000
        mana = [bar.get("mana", -1), self.bar().get("mana", -1)]
        target_valid = (near.get("ok") is True and near.get("truncated")==0
                        and target.get("hpMax")==after_target.get("hpMax")==10000000
                        and target.get("unit")==after_target.get("unit")==dummy
                        and all(abs(target.get(k,1e9)-after_target.get(k,-1e9))<=.01 for k in ("x","y")))
        return {"natural_ammo_spend":spent,"hp":[hp0,hp1],"damage":damage,"track":event,
                "native_throw_log":thrown,"fixture":fixture,"crit_after":crit_after,"restore":restored,
                "clip_after":self.clip(),"mana":mana,"source_flat_mana_cost":entry.get("mana"),
                "atomic_setup":atomic,"track_complete":track_complete,"anchor":anchor,"sequence_accepted":accepted,
                "sequence_terminal":terminal,"input_done":done,"sequence_protocol":protocol,
                "trajectory":trajectory,"release":release,"target":target,"after_target":after_target,
                "valid":(spent["valid"] and atomic and cooldown_ready and target_valid and crit_valid
                         and restored.get("ok") is True and restored.get("override_active") is False
                         and protocol.get("valid") and trajectory.get("valid") and release.get("valid")
                         and track_complete and event.get("truncated")==0 and len(paths)==1 and len(thrown)==1
                         and int(thrown[0][0])==spent["clip"][1] and self.clip()==30
                         and hp0>hp1>0 and damage>0 and entry.get("mana")==0
                         and mana[0]>=0 and abs(mana[1]-mana[0])<.01)}


def run(p, **_):
    c=Checks(p)
    try:
        c.explosive()
    except Exception as exc:
        c.check("reload_held_aim_crashed",False,{"error":repr(exc)})
    c.out.update(ok=bool(c.rows) and all(x["runtime"]=="PASS" for x in c.rows),rows=c.rows,notes=c.notes)
    return c.out
