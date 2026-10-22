"""All Burst ranks: real first-shell/dash cancellation with full cost and no refund.

Cleared-floor fixture only. Uses validated c657 inputsequence; every measured
write holds Directional aim. No activation/cancellation/resource setter inside
measurement, and all fixed full/cancel pairs are retained without retries.
"""
import math
import re
import time

from gamelab.bots.qa_firearms_missing_orbs import Checks as Base
from gamelab.bots.qa_firearms_input_sequence import Checks as SequenceChecks, sequence_protocol
from gamelab.bots.qa_specs_living_mana import collect as collect_resources
from gamelab.bots.qa_firearms_resource_oracle import cast_payment

SKILL="hwp_fs_burst"
CLASS="hwp_firearms_assault"
COSTS=(5,5,6,6,7)


def source_cost(raw, cost):
    expected={"health_flat":0,"mana_flat":cost,"health_max_percent":0,"mana_max_percent":0,
              "health_current_percent":0,"mana_current_percent":0,"health_multiplier":1,"mana_multiplier":1,"dash":0}
    modified={**expected,"mana_flat":0}
    valid=(raw.get("ok") is True and raw.get("class")==CLASS and raw.get("skill")==SKILL
           and raw.get("matches")==1 and raw.get("type")==4 and raw.get("truncated") is False
           and raw.get("free_health") is False and raw.get("free_mana") is False
           and raw.get("global_health_multiplier")==raw.get("global_mana_multiplier")==1
           and raw.get("expense_health")==raw.get("scaled_health")==raw.get("use_points_health")==0
           and raw.get("expense_mana")==raw.get("scaled_mana")==cost and raw.get("use_points_mana")==0
           and all(raw.get("base",{}).get(k)==v and raw.get("combined",{}).get(k)==v for k,v in expected.items())
           and all(raw.get("modified",{}).get(k)==v for k,v in modified.items())
           and type(raw.get("max_mana")) is int and raw["max_mana"]>cost
           and isinstance(raw.get("mana_fraction"),(int,float)) and .1<raw["mana_fraction"]<.9)
    return {"valid":bool(valid),"expense":cost,"max_mana":raw.get("max_mana"),"raw":raw}


def cancellation_oracle(full, cancelled):
    """The unconditional shell log excludes a geometric miss masquerading as cancel."""
    errors=[]
    if not full.get("valid") or not cancelled.get("valid"):errors.append("fixture/input/resource/damage guard failed")
    if len(full.get("hits",[]))!=2 or full.get("shells")!=2:errors.append("normal control must execute two real damaging shells")
    if len(cancelled.get("hits",[]))!=1 or cancelled.get("shells")!=1:errors.append("cancel must execute exactly the first shell")
    if full.get("cost")!=cancelled.get("cost") or not full.get("paid") or not cancelled.get("paid"):
        errors.append("full source cost without refund required in both paths")
    if cancelled.get("dash_displacement",0)<20:errors.append("no actual native dash displacement")
    rows=cancelled.get("sequence",{}).get("steps",[])
    control=full.get("sequence",{}).get("steps",[])
    timing={}
    if len(rows)==4 and control and len(full.get("hits",[]))==2 and len(cancelled.get("hits",[]))==1:
        dash=rows[2]["first_write"]
        relative_dash=dash-rows[0]["first_write"]
        second=full["hits"][1]["now"]-control[0]["first_write"]
        maximum=max(x["dt_max"] for x in rows+control)
        timing={"first_hp_before_dash":cancelled["hits"][0]["now"]<dash,
                "relative_dash_ms":relative_dash,"normal_second_hp_ms":second,"native_endpoint_frame_ms":maximum,
                "dash_precedes_control_second_by_two_frames":0<relative_dash<second-2*maximum}
        if not timing["first_hp_before_dash"] or not timing["dash_precedes_control_second_by_two_frames"]:
            errors.append("first-shell-before-dash/second-shell timing not causally isolated")
    else:errors.append("missing native step/hit timing")
    return {"valid":not errors,"errors":errors,"timing":timing,
            "scope":"First real shell then native dash suppresses later shell execution; same full mana cost/no refund within complete six-second native cast/cooldown trace."}


class Checks(Base):
    step=staticmethod(SequenceChecks.step)
    released=SequenceChecks.released

    def raw_ready(self, ids):
        deadline=time.monotonic()+16
        samples=[]
        while time.monotonic()<deadline:
            raw=self.gl("skills");samples.append(raw)
            rows=[[x for x in raw.get("skills",[]) if x.get("id")==sid] for sid in ids]
            if (raw.get("ok") is True and raw.get("truncated") is False
                    and all(len(x)==1 and type(x[0].get("cd")) is int and x[0]["cd"]<=0 for x in rows)):
                return True,samples
            time.sleep(.2)
        return False,samples

    def trial(self, rank, direction, cancel):
        self.clear_dummies()
        self.top_up()
        dd,target=self.tough(direction,60)
        bar=self.bar();dash=[x for x in bar.get("skills",[]) if x.get("button")=="dash"]
        entry=self.entry(bar,SKILL)
        if len(dash)!=1 or not entry.get("button"):raise RuntimeError("unique live Burst/dash mapping missing")
        ready,readiness=self.raw_ready([SKILL,dash[0]["id"]])
        if not ready:raise RuntimeError("natural cooldowns did not become ready")
        self.gl("mana",bar["manaMax"]*.5)
        fixture=self.gl("skillcrit",SKILL,0)
        origin=self.pos();clip=self.clip();tag="burst-r%d-%s-%d"%(rank,"cancel" if cancel else "full",time.time_ns())
        neutral=lambda ms:self.step(ms,(0,0),dd)
        if cancel:
            steps=[self.step(1,(0,0),dd,entry["button"]),neutral(33),self.step(1,(0,0),dd,"dash"),neutral(700)]
            expected=[(1,[entry["button"]]),(33,[]),(1,["dash"]),(700,[])]
        else:
            steps=[self.step(1,(0,0),dd,entry["button"]),neutral(900)]
            expected=[(1,[entry["button"]]),(900,[])]
        mark=self.log_pos()
        try:
            replies=self.g.gl_multi([["skills"],["skillcost",SKILL,CLASS],["resourceobserve",tag+"r",6000],
                ["buffobserve",tag+"h",1500,"-","-",target],["inputsequence",tag,*steps]])
            accepted=replies[-1]
            terminal=(self.g.wait_gl(lambda e:e.get("ev")=="inputsequence" and e.get("tag")==tag,timeout=15) or {}) if accepted.get("ok") else {}
            done=[e for e in self.g.gl if e.get("ev")=="input_done" and e.get("sequence")==tag]
            sequence=sequence_protocol(accepted,terminal,done,expected)
            resources=collect_resources(self.g,tag+"r",10)
            hp=self.collect_trace("buffobserve",tag+"h",8)
            cost=source_cost(replies[1],COSTS[rank-1])
            payment=cast_payment(resources,cost,refund=False,baseline_max=cost.get("max_mana"),duration_ms=6000)
            end=self.pos();release=self.released();crit_end=self.gl("skillcrit",SKILL)
        finally:
            restored=self.gl("skillcrit",SKILL,"restore")
        samples=hp.get("samples",[])
        hits=[{"now":b["now"],"loss":a["target_hpExact"]-b["target_hpExact"]} for a,b in zip(samples,samples[1:])
              if a.get("target_hpExact",0)-b.get("target_hpExact",0)>.01]
        shell_logs=re.findall(r"shotgun: (\d+) hit, (\d+) within",self.log_from(mark))
        crit=all(x.get("ok") is True and x.get("skill")==SKILL and x.get("override_active") is True
                 and x.get("left",0)>0 and x.get("crit_chance")==x.get("spell_crit_chance")==0 for x in (fixture,crit_end))
        parents={x.get("id","").rsplit(".",1)[0] for x in replies}
        atomic=len(replies)==5 and all(x.get("ok") is True for x in replies) and len(parents)==1 and "" not in parents
        expenses=payment.get("decreases",[])
        max_frame=max((x.get("dt",0) for x in resources.get("samples",[])),default=0)
        observed_after_payment=(resources.get("end",-1)-expenses[0].get("now",-1)) if len(expenses)==1 else -1
        no_refund_window={"valid":bool(payment.get("valid") and 0<max_frame<=100
            and observed_after_payment>=5000+2*max_frame),"observed_after_payment_ms":observed_after_payment,
            "required_after_payment_ms":5000+2*max_frame,"native_frame_ms":max_frame,
            "scope":"Complete authored5000ms post-payment no-refund window, including two native endpoint frames; no exact cooldown-duration claim."}
        target_valid=(hp.get("valid") is True and bool(samples) and all(x.get("target_valid") is True
            and x.get("player_valid") is True and x.get("target_hpMax")==10000000 for x in samples)
            and samples[0].get("target_hpExact",0)>samples[-1].get("target_hpExact",0)>0)
        idle_clip=self.clip()==clip==30
        result={"rank":rank,"cancel":cancel,"cost":COSTS[rank-1],"paid":payment.get("valid") is True,
            "valid":bool(atomic and ready and sequence["valid"] and target_valid and payment.get("valid")
                and crit and restored.get("ok") is True and restored.get("override_active") is False
                and idle_clip and release.get("valid") and no_refund_window["valid"]),"origin":origin,"end":end,
            "dash_displacement":math.dist(origin,end) if cancel else 0,"sequence":sequence,
            "sequence_accepted":accepted,"sequence_terminal":terminal,"input_done":done,
            "resources":resources,"source_cost":cost,"payment":payment,"no_refund_window":no_refund_window,"hp_trace":hp,"hits":hits,
            "shells":len(shell_logs),"shell_logs":shell_logs,"clip_unchanged":idle_clip,"release":release,
            "readiness":readiness,"crit_begin":fixture,"crit_end":crit_end,"crit_restore":restored}
        # Return naturally only after all measured traces/input releases completed.
        if cancel:
            # Controlled dummy cleanup is after every retained measurement; its
            # collider must not obstruct the separate ordinary walking return.
            self.clear_dummies()
            self.p.reflex(potion=0,fire=0)
            returned=self.p.path_to(*origin,tol=2,timeout=15)
            result["ordinary_return"]={"ok":returned.ok,"end":self.pos()}
            result["valid"]=result["valid"] and returned.ok and math.dist(origin,self.pos())<=2
        return result

    def all_ranks(self):
        if not self.prepare("QABurstCancel",CLASS):return
        direction=self.local_dash_line()
        if direction is None:return
        for rank in range(1,6):
            learned=self.learn_rank(SKILL,rank)
            full=self.trial(rank,direction,False)
            cancel=self.trial(rank,direction,True)
            oracle=cancellation_oracle(full,cancel)
            self.check("burst_rank_%d_first_shell_cancel_full_cost"%rank,learned==rank and oracle["valid"],
                {"skill":SKILL,"rank":rank,"source_cost":COSTS[rank-1],"full_control":full,"cancelled":cancel,"oracle":oracle})
        self.clear_dummies();self.to_town()


def run(p,**_):
    c=Checks(p)
    try:c.all_ranks()
    except Exception as exc:c.check("burst_cancellation_crashed",False,{"error":repr(exc)})
    c.out.update(ok=bool(c.rows) and all(x["runtime"]=="PASS" for x in c.rows),rows=c.rows,notes=c.notes)
    return c.out
