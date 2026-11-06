"""One bounded native diagnostic pass plus three real saved-item reads.
This file never constructs/launches a Game. Root's lab runner supplies p.game.
"""
import time

from gamelab.bots.qa_town_economy_oracle import assess
from gamelab.bots.qa_item_transport_contract_oracle import (
    BASE_ITEM, CASES, F32, F64, REFUSALS, assess_case, assess_saved_item,
)


def run(p, **_):
    g = p.game
    flags,notes,rows,snapshots = {},[],[],[]
    required = ["contract_fixture"] + ["cal_"+case for case in CASES] + ["real_item_fixture","real_item_stable"]

    def flag(name, passed, detail):
        flags[name] = bool(passed)
        notes.append(name+": "+str(detail))

    try:
        state = g.gl_cmd("state")
    except Exception as exc:
        state = {"error":repr(exc)}
    player = state.get("player") or {}
    fixture_ok = (state.get("phase") == "town" and player.get("class") == "paladin"
                  and player.get("level") == 1 and player.get("dead") is False)
    flag("contract_fixture",fixture_ok,state)
    if fixture_ok:
        for case in CASES:
            try:
                reply = g.gl_cmd("qa_item_transport_calibrate",case)
                row = {"case":case,"observation":reply}
                rows.append(row)
                # Registration/identity errors are a failed prerequisite, not49 retries.
                if (not isinstance(reply,dict) or reply.get("ok") is not True or reply.get("schema") != "gamelab.item-calibration.v1"
                        or reply.get("case") != case):
                    row["error"] = "diagnostic binding/fixture identity refused"
                    flag("cal_"+case,False,row["error"])
                    break
                try:
                    row["assessment"] = assess_case(case,reply)
                    flag("cal_"+case,True,row["assessment"])
                except (ValueError,KeyError,TypeError,OverflowError) as exc:
                    row["error"] = repr(exc)
                    flag("cal_"+case,False,row["error"])
            except Exception as exc:
                if rows and rows[-1].get("case") == case:
                    rows[-1]["error"] = repr(exc)
                else:
                    rows.append({"case":case,"error":repr(exc)})
                flag("cal_"+case,False,repr(exc))
                break

    calibrated = fixture_ok and len(rows) == len(CASES) and all(flags.get("cal_"+case) is True for case in CASES)
    if calibrated:
        try:
            # Exact-base kit builds the requested quality before native Finalize.
            equip = g.gl_cmd("kit",1,"rare",BASE_ITEM,"seed=20261030")
            metadata = g.gl_cmd("bagitems").get("main") or {}
            item_ok = (equip.get("ok") is True and metadata.get("id") == BASE_ITEM
                       and metadata.get("quality") == 4 and metadata.get("ilvl") == 1)
            flag("real_item_fixture",item_ok,{"equip":equip,"actual":metadata})
            if item_ok:
                identities=[]
                for trial in range(3):
                    # The setup mutation is finished. Every remaining operation is read-only.
                    reply = g.gl_cmd("qa_item_identity",BASE_ITEM)
                    record = {"trial":trial,"observation":reply}
                    snapshots.append(record)
                    identity,summary = assess_saved_item(reply)
                    identities.append(identity)
                    record["assessment"] = summary
                    if trial < 2:
                        time.sleep(.1)
                after = g.gl_cmd("bagitems").get("main") or {}
                flag("real_item_stable",len(identities) == 3 and len(set(identities)) == 1
                     and after == metadata,{"snapshots":len(identities),"actual_after":after})
            else:
                flag("real_item_stable",False,"unobserved: native equipment prerequisite failed")
        except Exception as exc:
            flag("real_item_stable",False,repr(exc))
    else:
        flag("real_item_fixture",False,"unobserved: numeric/refusal calibration failed")
        flag("real_item_stable",False,"unobserved: calibration prerequisite failed")

    result=dict(flags)
    result.update(assess(flags,required))
    result.update(
        observed_case_count=len(rows), real_item_read_count=len(snapshots),
        numeric_cases_ok=all(flags.get("cal_"+case) is True for case in tuple(F32)+tuple(F64)+("vec2","vec3","vec4")),
        refusal_cases_ok=all(flags.get("cal_"+case) is True for case in REFUSALS),
        calibration_rows=rows, real_item_snapshots=snapshots,
        required_flags=required, notes=notes,
        terminal=" | ".join(notes)[-3000:],
        scope="native-contract only if actual lab run passes outer guards; no ordinary/realrestart/co-op claim",
    )
    return result
