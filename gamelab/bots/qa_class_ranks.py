"""All5 HoH1 mastery active ranks and Riposte's complete real-hit matrix.

Reuses the independently retained original low/max controls. Actual Skill.Activate,
real landing/target HP/debuffs/outside control and Player.Damage are observed.
This controlled god-on arena ability suite does not claim ordinary-run input/UI;
Riposte explicitly switches god off before its actual incoming hits.
"""
import math
import time
from gamelab.bots.qa_classes import Checks as AbilityChecks, ACTIVE_CASES, QA_DUMMY, QA_DUMMY_FILTER, DUMMY, DUMMY_FILTER, STUN
from gamelab.bots.plan_classesa import BRUTE, dist


class Checks(AbilityChecks):
    def to_trident_lane(self, front=26, back_neighbor=False, ray_distance=40, tag="trident", clearance_points=()):
        from gamelab.bots.qa_specs_navigation import walk_trident_lane
        return walk_trident_lane(self,front=front,back_neighbor=back_neighbor,
                                 ray_distance=ray_distance,tag=tag,clearance_points=clearance_points)

    def to_open(self, need=48):
        # Preserve the original square clearance at the actual final centre,
        # but reach it through the engine path rather than guessed input time.
        lane, note = self.to_trident_lane(front=max(26,need+8), back_neighbor=True,
            ray_distance=max(40,need+8), tag="active_open"+str(need),
            clearance_points=((0,0,need),))
        return bool(lane), note

    def native_ready(self, skill, tag, timeout=25):
        end,rows = time.monotonic()+timeout,[]
        while time.monotonic()<end:
            row=next((r for r in self.gl("skills").get("skills",[]) if r.get("id")==skill),{})
            rows.append(row)
            if isinstance(row.get("cd"),(int,float)) and row["cd"]<=0:
                self.out[tag+"_cooldown_samples"]=rows
                self.flag(tag+"_cooldown_ready",True,str(row))
                return True
            time.sleep(.15)
        self.out[tag+"_cooldown_samples"]=rows
        self.flag(tag+"_cooldown_ready",False,str(rows))
        return False

    def riposte(self):
        """Real Player.Damage with a hostile actor; no god mode or modifier callbacks.

        The stationary magic dummy has zero physical armor. Fresh targets avoid
        reflection damage saturating a later measurement. Spell/ranged controls
        distinguish a melee-only effect from the unused generic Thorns modifier.
        """
        if not self.setup_mastery("hwp_gladiator", "hwp_gladiator_champion", "QARiposte"):
            return
        if not self.arena("riposte"):
            return
        for _ in range(3):
            if not self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"):
                break
            self.hwp("god", 0.3)
        god_off = not self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
        self.flag("riposte_god_off", god_off)
        all_ok = god_off
        rows = []
        for rank in (0, 1, 2, 3, 4, 5):
            if rank:
                learned = self.gl("skill", "hwp_gladiator_riposte", 1)
                self.flag(f"riposte_r{rank}_rank", learned.get("level") == rank, str(learned))
            for mode in ("melee", "ranged", "spell"):
                for amount in (2, 5):
                    tag = f"riposte_r{rank}_{mode}_{amount}"
                    before = {u["unit"] for u in self.gl("near", 400, DUMMY_FILTER).get("units", [])}
                    _, f = self.open_dirs()[0]
                    self.gl("spawn", DUMMY, round(f[0] * 48), round(f[1] * 48))
                    targets = [u for u in self.gl("near", 400, DUMMY_FILTER).get("units", [])
                               if u["unit"] not in before and not u.get("dead")]
                    if not targets:
                        self.flag(tag, False, "no fresh hostile dummy")
                        all_ok = False
                        continue
                    reply = self.gl("damagefrom", targets[0]["unit"], amount, mode)
                    hp0, hp1 = (reply.get(k) for k in ("attacker_hp0_exact", "attacker_hp_exact"))
                    reflected = hp0 - hp1 if None not in (hp0, hp1) else None
                    expected = rank * 10 if mode == "melee" else 0
                    ok = bool(reply.get("ok")) and reply.get("took", 0) > 0 and reflected is not None and abs(reflected - expected) < 0.2
                    self.flag(tag, ok, f"expected flat {expected}; observed {reflected}; raw {reply}")
                    all_ok &= ok
                    rows.append({"rank": rank, "mode": mode, "incoming": amount,
                                 "expected": expected, "reflected": reflected, "reply": reply})
                    self.gl("kill", 400, DUMMY_FILTER)
        self.out["riposte_observations"] = rows
        self.flag("riposte_flat_melee_only", all_ok, f"{len(rows)} same-frame attacker-HP measurements")
        self.to_town()


    def active_case(self, name):
        cls, mastery, skill, mode, required_tag = ACTIVE_CASES[name]
        if not self.setup_mastery(cls, mastery, "QA" + name):
            return
        if not self.arena(name):
            return
        lane = None
        if mode == "leap":
            lane, note = self.to_trident_lane(front=72, back_neighbor=True, ray_distance=72, tag=name)
            opened = bool(lane)
        else:
            opened, note = self.to_open(48)
        self.notes.append(name + " arena: " + note)
        self.flag(name + "_open_floor", opened, note)
        if not opened:
            return
        losses, trials = [], []
        for rank in range(1, 6):
            tag = f"{name}_r{rank}"
            learned = self.gl("skill", skill, 1)
            self.flag(tag + "_rank", learned.get("level") == rank, str(learned))
            self.clear()
            self.gl("kill", 800, QA_DUMMY_FILTER)
            if mode == "leap":
                if rank != 1:
                    lane, note = self.to_trident_lane(front=72, back_neighbor=True, ray_distance=72, tag=tag)
                self.flag(tag + "_open_floor", bool(lane), note)
                if not lane:
                    continue
                f, outside_direction = lane
            else:
                _, f = self.open_dirs()[0]
            offset = 28 if mode == "self" else 72
            dx, dy = round(f[0] * offset), round(f[1] * offset)
            # A known stationary 15k actor avoids saturated rank comparisons
            # and moving-body geometry; real enemy AI is a separate run axis.
            unit_path = QA_DUMMY
            unit_filter = QA_DUMMY_FILTER
            before = {u["unit"] for u in self.gl("near", 600, unit_filter).get("units", [])}
            p0 = self.me()
            freeze = "tweak/buffs/status_effects.sval:immobilize" if mode == "leap" else STUN
            args = ["spawn", unit_path, dx, dy, "+"]
            if mode == "leap":
                args += ["spawn", unit_path, round(outside_direction[0] * 40), round(outside_direction[1] * 40), "+"]
            args += ["buffnear", 300, unit_filter, freeze, 5000]
            self.gl("multi", *args)
            targets = [u for u in self.gl("near", 600, unit_filter).get("units", []) if u["unit"] not in before]
            target = min(targets, key=lambda u: dist((u["x"], u["y"]), (p0[0] + dx, p0[1] + dy))) if targets else None
            outside = next((u for u in targets if target and u["unit"] != target["unit"]), None)
            self.flag(tag + "_target", bool(target), str(target))
            if target is None:
                continue
            initial = self.actor(target["unit"], unit_filter)
            valid_hp = ((initial or {}).get("hpMax") == 15000
                        and abs((initial or {}).get("hpExact", -1) - 15000) < 0.01)
            self.flag(tag + "_target_hp", bool(valid_hp), str(initial))
            if not valid_hp:
                continue
            # Immobilize holds a leap target without supplying the landing stun.
            if not self.native_ready(skill,tag):
                continue
            self.gl("mana",999)
            fixture = self.gl("skillcrit",skill,0)
            noncrit = fixture.get("ok") and fixture.get("override_active") and fixture.get("crit_chance")==0 and fixture.get("spell_crit_chance")==0
            self.flag(tag+"_noncritical_fixture",bool(noncrit),str(fixture))
            if not noncrit:
                continue
            cast, _ = self.scene(cast=(skill, dx, dy), aim=f, hold=1200)
            stun_seen = False
            sampled_buffs = []
            if mode == "leap":
                # The minor stun lasts only 500 ms. Sample across the 450 ms leap
                # instead of checking after several unrelated round trips.
                until = time.monotonic() + 1.1
                for _ in range(4):
                    time.sleep(0.08)
                    sample = self.actor(target["unit"], unit_filter)
                    sampled_buffs.append(sample)
                    stun_seen |= "stun" in self.tags(sample)
                    if time.monotonic() >= until:
                        break
            else:
                time.sleep(0.65)
            after = self.unit(target["unit"], unit_filter)
            # UnitJson.hp is rounded to three decimals; retain the same
            # normalized metric using native absolute HP before serialization.
            hp0 = initial.get("hpExact") if initial else None
            hp1 = after.get("hpExact") if after else None
            hp_max = initial.get("hpMax") if initial else None
            precise = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                          and math.isfinite(v) for v in (hp0, hp1, hp_max)) and hp_max > 0
            self.flag(tag + "_precise_hp", bool(precise),
                      str({"hp0": hp0, "hp1": hp1, "hpMax": hp_max}))
            loss = (hp0 - hp1) / hp_max if precise else None
            losses.append(loss)
            buffs = self.actor(target["unit"], unit_filter)
            tags = self.tags(buffs)
            self.flag(tag + "_damage", cast.get("activated") and loss is not None and loss > 0.0001,
                      f"cast {cast}, target {target['unit']}, hp 1 -> "
                      f"{after.get('hp') if after else 'dead/removed'}, buffs {buffs}")
            if mode == "leap":
                moved = dist(p0, self.me())
                self.flag(tag + "_moves", moved > 30, f"moved {moved:.1f} px")
                # The fixture supplies immobilize, so only the landing can stun.
                self.flag(tag + "_landing_stun", stun_seen,
                          f"landing samples {sampled_buffs}; final buffs {buffs}")
                neighbor = self.actor(outside["unit"], unit_filter) if outside else None
                away = dist(self.me(), (neighbor["x"], neighbor["y"])) if neighbor else 0
                self.flag(tag + "_outside_radius", bool(neighbor) and away > 60
                          and neighbor.get("hpExact") == 15000 and "stun" not in self.tags(neighbor),
                          f"outside target {neighbor}, landing distance {away:.2f}")
            elif required_tag:
                self.flag(tag + "_debuff", required_tag in tags,
                          f"expected {required_tag}, tags {tags}, buffs {buffs}")
            if name in ("caltrops", "barbed_net"):
                count = sum(s.get("count", 0) for s in (buffs or {}).get("stacks", [])
                            if "bleeding" in s.get("tags", []))
                expected_stacks = 2 if name == "caltrops" else 3
                self.flag(tag + "_bleed", count == expected_stacks,
                          f"expected {expected_stacks} actual bleeding stacks, got {count}; actor {buffs}")
            trials.append({"rank":rank,"cast":cast,"target_before":target,"after":after,"tags":tags,
                           "buffs":buffs,"landing_samples":sampled_buffs,"player_before":p0,"player_after":self.me(),
                           "precise_hp_valid":bool(precise),"hp0":hp0,"hp1":hp1,"normalized_hp_loss":loss})
            self.clear()
        self.out[name+"_rank_trials"] = trials
        restored = self.gl("skillcrit",skill,"restore")
        self.flag(name+"_crit_restored",restored.get("ok") and not restored.get("override_active"),str(restored))
        if len(losses) == 5:
            self.flag(name + "_damage_scales", all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in losses)
                      and all(b>a for a,b in zip(losses,losses[1:])),
                      f"fresh enemy hp lost, all5ranks: {losses}; "
                      "a saturated comparison remains unverified")
        self.to_town()



def run(p,sections="shadow_strike",**_):
    c=Checks(p)
    for name in sections.split(","):
        try:
            c.active_case(name) if name in ACTIVE_CASES else getattr(c,name)()
        except Exception as exc:
            c.flag(name+"_crashed",False,repr(exc))
    c.out["notes"]=c.notes
    return c.out
