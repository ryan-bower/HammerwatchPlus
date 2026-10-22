"""All positive Cinders/Vanish ranks, fixed real hit samples; no probability fit.

Original endpoint cases remain unchanged and retain their own captures. The only
extension here is learning/measuring every positive rank, keeping rank0 Cinders.
"""
import time
from gamelab.bots.qa_class_crit import Checks as CritChecks
from gamelab.bots.qa_class_vanish import Checks as VanishChecks, SKILL, CLOAK

class Checks(CritChecks, VanishChecks):
    def cinders(self):
        if not self.prepare("hwp_witch_hunter", "hwp_witch_hunter_pyromancer", "QACinders"):
            return
        ward = "hwp_witch_hunter_ward"
        if not self.learn(ward, 1, "cinders_ward"):
            return
        rows, passed = [], True
        for rank, trials in [(0, 8)] + [(r, 40) for r in range(1, 6)]:
            learned = self.learn("hwp_witch_hunter_cinders", rank, f"cinders_r{rank}")
            count, valid = 0, 0
            for index in range(trials):
                tag = f"cinders_r{rank}_{index}"
                target = self.fresh_dummy(tag, offset=64)
                if not target:
                    continue
                direction = self.direction_to(target)
                cast = self.cast_once(ward, direction)
                time.sleep(0.2)
                after, floats = self.target_snapshot(target["unit"])
                damage = target["hpExact"] - after["hpExact"] if after else None
                hit = cast.get("activated") and damage is not None and damage > 0
                proc = "armor_break" in self.tags(after)
                valid += bool(hit)
                count += bool(hit and proc)
                rows.append({"rank": rank, "trial": index, "cast": cast, "before": target, "after": after,
                             "actual_hp_lost": damage, "armor_break": proc, "actual_spell_hit": bool(hit), "floats": floats})
            # Fixed samples never rerun until a random success. A zero outcome at
            # either built rank remains a failed observation for investigation.
            ok = learned and valid == trials and (count == 0 if rank == 0 else 0 < count < trials)
            self.flag(f"cinders_r{rank}_spell_proc", bool(ok), f"{count}/{valid} actual Ward hits proc armor break, fixed trials {trials}")
            passed &= bool(ok)
        self.flag("cinders_observed", passed and len(rows) == 208)
        self.out["cinders_trials"] = rows
        self.to_town()

    def vanish(self):
        if not self.prepare("hwp_thief", "hwp_thief_shadow", "QAVanish"):
            return
        off = self.god_off()
        self.flag("vanish_god_off", off)
        if not off:
            return
        all_rows, all_ok = [], True
        for rank in range(1, 6):
            tag = f"vanish_r{rank}"
            learned = self.learn(SKILL, rank, tag)
            time.sleep(3)  # let any prior2500ms cloak expire naturally
            _, initial_cloak = self.cloak()
            baseline = self.gl("benchstats")
            attacker = self.fresh_dummy(tag, offset=48)
            if not attacker:
                all_ok = False
                continue
            rows, births, proc_stats, proc_evades = [], [], [], []
            damage_ok, buff_shape_ok = True, not initial_cloak.get("on")
            for trial in range(120):
                mark = len(self.g.gl)
                self.gl("multi", "hurt", 0.9, "+", "damagefrom", attacker["unit"], 2, "ranged",
                        "+", "hasbuff", CLOAK)
                replies = self.g.gl[mark:]
                hit = next((r for r in replies if "attacker_unit" in r), {})
                readback = next((r for r in replies if "buffs" in r and "now" in r), {})
                buffs = readback.get("buffs", [])
                buff = buffs[0] if buffs else {}
                now = readback.get("now")
                real_hit = hit.get("ok") and hit.get("took", 0) > 0 and hit.get("hp0", 0) > hit.get("hp", 0)
                damage_ok &= bool(real_hit)
                new_proc = False
                if buff.get("on") and now is not None:
                    buff_shape_ok &= bool(buff.get("hud")) and 0 < buff.get("left", 0) <= 2500
                    born = now + buff.get("left", 0) - 2500
                    if not births or abs(born - births[-1]) > 200:
                        births.append(born)
                        new_proc = True
                row = {"trial": trial, "hit": hit, "now": now, "cloak": buff, "new_proc": new_proc,
                       "fixture": "health set0.9 before one real2-pure TrueStrike hit, god off"}
                if new_proc:
                    # Read after the command frame so native stat rebuild has run.
                    stats = self.gl("benchstats")
                    proc_stats.append(stats)
                    row["live_stats"] = stats
                    evade = self.gl("evade", 1)
                    proc_evades.append(evade)
                    row["actual_evade"] = evade
                rows.append(row)
            time.sleep(3)
            now, ended = self.cloak()
            restored = self.gl("benchstats")
            intervals = [b - a for a, b in zip(births, births[1:])]
            timed = len(births) >= 2 and all(interval >= 7800 for interval in intervals)
            effects = (bool(proc_stats) and all(s.get("evade", 0) >= 0.999 for s in proc_stats)
                       and all(e.get("evaded") for e in proc_evades))
            expiry = (not ended.get("on") and abs(restored.get("evade", -1) - baseline.get("evade", -99)) <= 0.002
                      and abs(restored.get("moveSpeed", -1) - baseline.get("moveSpeed", -99)) <= 0.02)
            ok = learned and damage_ok and buff_shape_ok and timed and effects and expiry
            self.flag(tag + "_actual_hurt_cloak", bool(ok),
                      f"fixed120 real hits; births {births}; intervals {intervals}; "
                      f"all damage {damage_ok}; actual stats {proc_stats}; expired {ended}; restored {restored}")
            all_ok &= bool(ok)
            all_rows.append({"rank": rank, "baseline": baseline, "initial_cloak": initial_cloak, "trials": rows,
                             "proc_births": births, "proc_intervals_ms": intervals, "proc_stats": proc_stats,
                             "proc_evades": proc_evades,
                             "speed_effect": "UNTESTED: cloak speed-mul is native ActorBuffList.MoveSpeedMul, outside currStats.MoveSpeed",
                             "final_now": now, "final_cloak": ended, "restored": restored})
        self.flag("vanish_observed", all_ok and len(all_rows) == 5)
        self.out["vanish_trials"] = all_rows
        self.to_town()

def run(p,sections="cinders,vanish",**_):
    c=Checks(p)
    for section in sections.split(","):
        try:
            getattr(c,section)()
        except Exception as exc:
            c.flag(section+"_crashed",False,repr(exc))
    c.out["notes"]=c.notes
    c.out["terminal"]=" | ".join(c.notes)[-5000:]
    return c.out
