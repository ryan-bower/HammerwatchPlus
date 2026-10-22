"""Controlled Bannerlord rank effects, not ordinary play or teammate proof.

Standard uses the native skill path and real incoming damage. Righteous Crusade
uses native ApplyBuff, live movement and natural expiry. Cooldown resets only
isolate Standard rank measurements; the free plant is tested without a reset.
"""
import re
import time

from gamelab.bots.plan_specs import BUFFS, Checks as SpecChecks
from gamelab.bots.qa_classes import Checks as GeometryChecks, QA_DUMMY

BS = "hwp_war_battlefield_standard"
RC = "hwp_war_righteous_crusade"
WARCRY = "players/warrior/buffs_warrior.sval:warcry_1"


class Checks(SpecChecks):
    trident_lanes = staticmethod(GeometryChecks.trident_lanes)
    to_trident_lane = GeometryChecks.to_trident_lane

    def me(self):
        return self.pos()

    def prepare_banner(self, name):
        self.setup(name, "warrior", "hwp_warrior_bannerlord", [])
        if not self.out.get(name + "_char") or not self.out.get(name + "_learned"):
            return False
        if not self.enter_floor(name):
            return False
        if self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"):
            self.hwp("god", 0.3)
        off = not self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
        self.flag(name + "_god_off", off)
        return off

    def rank(self, skill, wanted, tag):
        current = self.gl("skill", skill, 0).get("level", -1)
        reply = self.gl("skill", skill, wanted - current) if 0 <= current < wanted else {"level": current}
        ok = reply.get("level") == wanted
        self.flag(tag + "_rank", ok, str(reply))
        return ok

    def damage(self, uid):
        # The HP snapshot and Player.Damage execute in one native frame.
        replies = self.g.gl_multi([["hurt", 0.9], ["damagefrom", uid, 100, "spell"]])
        hit = replies[-1]
        return hit.get("hp0", 0) - hit.get("hp", 0), hit

    def standard_cast(self, direction, reset=False, refill=False):
        commands = []
        if refill:
            commands.append(["mana", 999])
        commands.append(["input", 1000, 0, 0, *direction])
        commands.append(["castat", BS, *direction, *(["nocd"] if reset else [])])
        return self.g.gl_multi(commands)[-1]

    def banner_ranks(self):
        if not self.prepare_banner("standard_ranks"):
            return
        lane, note = self.to_trident_lane(front=72, back_neighbor=True, ray_distance=72, tag="standard")
        self.flag("standard_lane", bool(lane), note)
        if not lane:
            return
        direction = lane[0]
        self.gl("spawn", QA_DUMMY, round(direction[0] * 72), round(direction[1] * 72))
        actors = self.gl("near", 150, "qa_class_target_dummy").get("units", [])
        target_ok = len(actors) == 1 and actors[0].get("hpMax") == 15000
        self.flag("standard_damage_actor", target_ok, str(actors))
        if not target_ok:
            return
        uid, rows, passed = actors[0]["unit"], [], True
        for rank, (ttl, cooldown) in enumerate(zip((10000, 13000, 15000, 17000, 20000),
                                                  (60000, 55000, 50000, 45000, 40000)), 1):
            tag = f"standard_r{rank}"
            if not self.rank(BS, rank, tag):
                passed = False
                continue
            baseline, b0 = self.damage(uid)
            self.gl("mana", 999)
            mana0 = self.mana_exact()
            mark = len(self.g.read_log())
            raised = self.standard_cast(direction, reset=True)
            carry = self.wait_buff("standard_dr", 2)
            time.sleep(0.7)
            mana1, cd = self.mana_exact(), self.skill_cd(BS)
            carried, b1 = self.damage(uid)
            raise_log = self.g.read_log()[mark:]
            dr = 0.02 * rank
            carrying = (raised.get("activated") and carry.get("on")
                        and abs(carry.get("intensity", -1) - dr) <= 0.0005
                        and baseline > 0 and abs(carried - baseline * (1 - dr)) <= 1
                        and cd is not None and cooldown - 4000 <= cd <= cooldown
                        and 35 <= mana0 - mana1 <= 41
                        and f"raised for {ttl} ms" in raise_log)
            self.flag(tag + "_carried_damage", bool(carrying), str({"cast": raised, "buff": carry,
                      "baseline": b0, "actual": b1, "mana": [mana0, mana1], "cooldown": cd}))
            mana2 = self.mana_exact()
            mark = len(self.g.read_log())
            planted = self.standard_cast(direction)
            plant_buff = self.wait_buff("standard_dr_planted", 2)
            time.sleep(0.8)  # native 600ms carried-buff tail must be over
            planting, b2 = self.damage(uid)
            mana3 = self.mana_exact()
            plant_log = self.g.read_log()[mark:]
            match = re.search(r"standard: planted, (\d+) ms left", plant_log)
            plant_left = int(match.group(1)) if match else None
            plant_ok = (planted.get("activated") and plant_buff.get("on")
                        and abs(plant_buff.get("intensity", -1) - 2 * dr) <= 0.0005
                        and abs(planting - baseline * (1 - 2 * dr)) <= 1
                        and mana3 >= mana2 - 1 and plant_left is not None
                        and 0 < plant_left < ttl / 2)
            self.flag(tag + "_free_planted_damage", bool(plant_ok), str({"cast": planted,
                      "buff": plant_buff, "actual": b2, "mana": [mana2, mana3], "left": plant_left}))
            expiry = time.monotonic() + ttl / 2000 + 3
            samples = []
            ended = False
            while time.monotonic() < expiry:
                reply = self.gl("hasbuff", BUFFS + "standard_dr", BUFFS + "standard_dr_planted")
                samples.append(reply)
                if not any(b.get("on") for b in reply.get("buffs", [])):
                    ended = True
                    break
                time.sleep(0.15)
            restored, b3 = self.damage(uid)
            revert = ended and restored == baseline
            self.flag(tag + "_expires_reverts", revert, str({"ended": ended, "baseline": b0, "actual": b3}))
            passed &= bool(carrying and plant_ok and revert)
            rows.append({"rank": rank, "expected": {"ttl_ms": ttl, "cooldown_ms": cooldown, "dr": dr},
                         "baseline": b0, "carried": b1, "planted": b2, "restored": b3,
                         "carry_buff": carry, "plant_buff": plant_buff, "expiry_samples": samples,
                         "raise_log": raise_log, "plant_log": plant_log})
        self.out["standard_rank_trials"] = rows
        self.flag("standard_all_ranks", passed and len(rows) == 5)
        self.to_town()

    def righteous_ranks(self):
        if not self.prepare_banner("righteous_ranks"):
            return
        rows, passed = [], True
        for rank in range(1, 6):
            tag = f"righteous_r{rank}"
            if not self.rank(RC, rank, tag):
                passed = False
                continue
            baseline = self.gl("benchstats")
            applied, initial, during = self.g.gl_multi([["givebuff", WARCRY],
                                                       ["hasbuff", WARCRY], ["benchstats"]])
            buff = (initial.get("buffs") or [{}])[0]
            expected = 8000 + 800 * rank
            effect = (applied.get("applied") and buff.get("on")
                      and abs(buff.get("left", -9999) - expected) <= 34
                      and abs(during.get("moveSpeed", 0) - (baseline.get("moveSpeed", 0) + 0.1)) <= 0.002)
            self.flag(tag + "_duration_and_effect", bool(effect), str({"applied": applied, "buff": buff,
                      "expected_ms": expected, "baseline": baseline, "during": during}))
            samples, gone = [], False
            until = time.monotonic() + expected / 1000 + 3
            while time.monotonic() < until:
                reply = self.gl("hasbuff", WARCRY)
                samples.append(reply)
                if not any(b.get("on") for b in reply.get("buffs", [])):
                    gone = True
                    break
                time.sleep(0.1)
            after = self.gl("benchstats")
            restored = gone and abs(after.get("moveSpeed", 0) - baseline.get("moveSpeed", -999)) <= 0.002
            self.flag(tag + "_natural_expiry_reverts", restored, str(after))
            rows.append({"rank": rank, "expected_ms": expected, "initial": initial,
                         "baseline": baseline, "during": during, "samples": samples, "after": after})
            passed &= bool(effect and restored)
        self.out["righteous_rank_trials"] = rows
        self.flag("righteous_all_ranks", passed and len(rows) == 5)
        self.to_town()


def run(pilot, section, **_):
    c = Checks(pilot)
    {"banner_ranks": c.banner_ranks, "righteous_ranks": c.righteous_ranks}[section]()
    return {**c.out, "notes": c.notes, "measurement_only": True,
            "expected_source": ["mods/specs/scripts/HWP/Specs/Bannerlord.as",
                                "mods/specs/players/hwp/specs/bannerlord/battlefield_standard.sval",
                                "mods/specs/players/hwp/specs/bannerlord/righteous_crusade.sval"]}
