"""Actual old-MM/new-noncritical-TT per-cast attribution neighbor, original code first."""
import json
from gamelab.bots.qa_specs_navigation import _walk
from gamelab.bots.qa_specs_static_native import assemble_observation, crit_text, hp_map
from gamelab.bots.qa_specs_wizard_ranks import Checks, TT, SC, STACK, spawn, wait_ready
MM = "wiz_magic_missiles"
PHASES = ("before_mm", "first_mm_crit", "before_tt", "actual_tt", "late_mm_crit", "finished")


def mm_lanes(t, ox=0, oy=0):
    rows,n,step=t["rows"],t["size"],t["step"];mid=n//2;result=[]
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        good=True
        for forward in range(-16,161,8):
            for side in range(-112,113,8):
                x=mid+round((ox+dx*forward-dy*side)/step)
                y=mid+round((oy+dy*forward+dx*side)/step)
                if not (0<=x<n and 0<=y<n and rows[y][x]!="#"):
                    good=False;break
            if not good:break
        if good:result.append(((dx,dy),(-dy,dx)))
    return result


def evaluate(data):
    phases = {p.get("phase"): p for p in data.get("phases", [])}
    samples = data.get("samples", [])
    complete = (data.get("complete") is True and not data.get("error") and data.get("truncated") is False
                and not data.get("retention_error") and 4000 <= data.get("ms", 0) <= 4100
                and 40 <= data.get("frames", 0) <= 200 and len(samples) == data.get("frames")
                and set(phases) == set(PHASES)
                and all(0 < b["now"]-a["now"] <= 100 for a,b in zip(samples,samples[1:])))
    flags={"complete":bool(complete)}
    if not complete:
        return {**flags,**{k:False for k in ("setup","one_mm","actual_tt","late_old_critical","one_bonus_per_cast")}}
    before,first,pre,tt,late,end=(phases[k] for k in PHASES)
    ids=set(hp_map(before))
    stable=(len(ids)==3 and all(set(hp_map(p))==ids and all(r.get("valid") is True and r.get("dead") is False
       and r.get("hpMax")==15000 and 0<r.get("hpExact",-1)<=15000.01 for r in p.get("targets",[])) for p in phases.values()))
    controlled=all(p.get("mm_crit")==1 and p.get("tt_crit")==p.get("spell_crit")==0 for p in phases.values())
    one=lambda key: sum(b.get(key,0)>a.get(key,0)+100 for a,b in zip(samples,samples[1:]))==1
    mm_crit=any(crit_text(r) and r.get("born",-1)>=data["mm_input_at"]-33 for r in first.get("crits",[]))
    owned=lambda p,kind:[r for r in p.get("projectiles",[]) if r.get("kind")==kind]
    setup=(stable and controlled and before.get("stacks")==0 and not before.get("projectiles") and not before.get("crits")
           and first.get("stacks")==pre.get("stacks")==2 and mm_crit and bool(owned(pre,"MM"))
           and all(not owned(p,"TT") for p in (before,first,pre)))
    mm=(setup and one("mm_cd") and data.get("mm_input_frames",0)>=2
        and sum(hp_map(first).values())<sum(hp_map(before).values())-.1
        and pre.get("mana",1e9)<before.get("mana",0)-1)
    actual_tt=(mm and one("tt_cd") and data.get("tt_input_frames",0)>=2
        and data.get("tt_input_at",-1)>data.get("first_crit_at",1e9)
        and data.get("tt_producer_at",-1)>data.get("tt_input_at",1e9)
        and len(owned(tt,"TT"))==1 and end.get("tt_cd",0)>0
        and tt.get("mana",1e9)<pre.get("mana",0)-1
        and data.get("held_ms_left",1)<=0 and data.get("releasing") is False)
    late_crits=[r for r in late.get("crits",[]) if crit_text(r) and r.get("born",-1)>data.get("tt_producer_at",1e9)+67]
    late_old=(actual_tt and bool(late_crits)
        and sum(hp_map(late).values())<sum(hp_map(pre).values())-.1
        and data.get("late_crit_at",1e9)<=data.get("mm_input_at",0)+1800)
    after=[r for r in samples if r.get("now",0)>=data.get("late_crit_at",1e9)]
    correct=late_old and after and all(r.get("stacks")==3 for r in after) and late.get("stacks")==end.get("stacks")==3
    return {"complete":bool(complete),"setup":bool(setup),"one_mm":bool(mm),"actual_tt":bool(actual_tt),
            "late_old_critical":bool(late_old),"one_bonus_per_cast":bool(correct)}


def run(p, **_):
    c=Checks(p);records=[]
    c.setup("staticmm", "wizard", "hwp_wizard_invocation", [TT,SC])
    if not c.enter_floor("staticmm"):
        return {**c.out,"notes":c.notes,"trials":records}
    _,direction,_,geometry=_walk(c,mm_lanes,"static_mm_lane",160,106,{"back":16,"length":160,"half_width":112,"fine_step":8,"source":"MMfirst500msfan+far100/80targets; actuallatecritical remains required"})
    c.flag("static_mm_lane_certified",direction is not None,str(geometry))
    if direction is None:return {**c.out,"notes":c.notes,"trials":records}
    c.button_for("staticmm_tt",TT,"skill2");c.button_for("staticmm_mm",MM,"skill1")
    try:
        for index in range(1,4):
            tag=f"static-mm-{index}"
            ready=wait_ready(c);targets=spawn(c,direction,[(26,0),(100,-80),(100,80)])
            c.set_stacks(STACK,0);c.gl("mana",250)
            original=c.gl("skillcrit",MM);crit=c.gl("skillcrit",MM,1)
            c.flag(f"mm_{index}_ready",ready and len(targets)==3 and crit.get("override_active") is True
                   and crit.get("crit_chance")==1 and crit.get("spell_crit_chance")==0,str(crit))
            queue=c.gl("qa_static_mm",tag,*direction)
            final=c.g.wait_gl(lambda e:e.get("ev")=="qa_static_mm_observe" and e.get("tag")==tag,20) if queue.get("ok") else {}
            observation=assemble_observation(c.g.gl,final,PHASES,"qa_static_mm") if final else {}
            flags=evaluate(observation)
            for key,value in flags.items():c.flag(f"mm_{index}_{key}",value,str({"final":final,"phases":observation.get("phases")}))
            restored=c.gl("skillcrit",MM,"restore");readback=c.gl("skillcrit",MM)
            c.flag(f"mm_{index}_restored",restored.get("ok") and readback.get("override_active") is False
                   and readback.get("crit_chance")==original.get("crit_chance"))
            records.append({"trial":index,"targets":targets,"crit":crit,"queue":queue,"observation":observation,"flags":flags,"restore":readback})
            (c.g.results/"static-mm.partial.json").write_text(json.dumps({"flags":c.out,"trials":records},indent=2)+"\n",encoding="utf-8")
    finally:
        c.gl("skillcrit",MM,"restore");c.g.shot("old MM native neighbor end",settle=False);c.to_town()
    return {**c.out,"notes":c.notes,"trials":records,
      "expected_source":"hwp_specs.lang93: each spell grants1, or2ifitCrits; nativefallbackInvocation291?296 currentlycreditslatestglobalcast. Ambiguity retained pending owner classification and strict nativeproof.",
      "scope":"Three fixed real MM?noncritTT sequences. Only MMcancrit; actual ownedproducers/nativeHP/crittexts/CD/mana/normalinputs. Controlledgodmode/zerocharge/mana/15kfixture; no ordinaryacquisition/exactcost/otherdelayedspell/co-op claim."}
