"""Fixed Vanish hurt-proc trials through real, god-off Player.Damage.

Direct health refill is labeled a survival fixture. TrueStrike pure hits bypass
the cloak's evade stat; no modifier callback is invoked. All120 trials per
rank are retained even when no proc occurs, with no rerun-until-success.
"""
import time

from gamelab.bots.qa_class_procs import Checks as ProcChecks


SKILL = "hwp_thief_vanish"
CLOAK = "tweak/hwp/buffs_classes.sval:hwp_thief_cloak"


class Checks(ProcChecks):
    def god_off(self):
        for _ in range(3):
            settings = self.gl("cvars", "cht_god").get("cvars", {})
            if "cht_god" not in settings:
                return False
            if not settings["cht_god"]:
                return True
            self.hwp("god", 0.2)
        return False

    def cloak(self):
        reply = self.gl("hasbuff", CLOAK)
        buffs = reply.get("buffs", [])
        return reply.get("now"), buffs[0] if buffs else {}

    def vanish(self):
        if not self.prepare("hwp_thief", "hwp_thief_shadow", "QAVanish"):
            return
        off = self.god_off()
        self.flag("vanish_god_off", off)
        if not off:
            return
        all_rows, all_ok = [], True
        for rank in (1, 5):
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
        self.flag("vanish_observed", all_ok and len(all_rows) == 2)
        self.out["vanish_trials"] = all_rows
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.vanish()
    except Exception as exc:
        c.flag("vanish_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
