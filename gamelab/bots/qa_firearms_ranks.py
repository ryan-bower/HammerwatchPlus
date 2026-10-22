"""Additional Firearms behavior checks; run only through isolated GameLab scenarios.



Fixture setters establish characters/resources, but every measured cast uses its live

skill button. These empty-floor measurements do not prove an ordinary combat run.

All observations, including failed attempts, are returned in rows without retries.

"""

import time



from gamelab.bots.plan_firearms import SKILLS, hold, tooltip_cost

from gamelab.bots.plan_firearms_more import Checks as Base





FAMILIES = {

    "base": (None, [("hwp_fs_reload", "fs_reload.sval"), ("hwp_fs_frag", "fs_frag.sval")]),

    "marksman": ("hwp_firearms_sniper", [("hwp_fs_snipe", "sniper_snipe.sval")]),

    "demo": ("hwp_firearms_demolitions", [("hwp_fs_rpg", "demo_rpg.sval")]),

    "assault": ("hwp_firearms_assault", [("hwp_fs_burst", "assault_burst.sval")]),

    "engineer": ("hwp_firearms_engineer", [("hwp_fs_turret", "engineer_turret.sval")]),

}





class Checks(Base):

    def __init__(self, p):

        super().__init__(p)

        self.rows = []



    def ordinary_damage(self):

        """Turn off fixture god mode and verify readback before measurements."""

        if self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"):

            self.hwp("god", 0.3, until="god mode")

        return not bool(self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god"))



    def check(self, tag, ok, row):

        self.flag(tag, ok, str(row))

        self.rows.append({"case": tag, "runtime": "PASS" if ok else "FAIL", **row})



    def hps(self, ids, r=600):

        """Fractional HP with native absolute precision when the probe provides it."""

        live = {}

        for unit in self.gl("near", r, "target_dummy").get("units", []):

            maximum = unit.get("hpMax", 0)

            precise = unit.get("hpExact")

            fraction = precise / maximum if precise is not None and maximum > 0 else unit.get("hp", 1.0)

            live[unit["unit"]] = 0.0 if unit.get("dead") else fraction

        return {unit: live.get(unit, 0.0) for unit in ids}



    def enter_floor(self, tag):

        if not super().enter_floor(tag):

            return False

        # The script global resets on a level load even if its cvar still reads1.

        # Set the two values on this floor, then verify the actual equipment/skills.

        self.g.console("dbg_cht_ignore_equipment_requirements 0")

        self.g.console("dbg_cht_ignore_equipment_requirements 1")

        time.sleep(0.25)

        ok, row = self.fixture_loadout("hwp_rifle_01", None, "common")

        self.check(tag + "_floor_loadout", ok and row["clip_max"] == 30, row)

        return ok and row["clip_max"] == 30



    def fixture_loadout(self, main, off=None, quality="common", reset=True):

        """Controlled ilvl1 gear with reply, equipped-item and live-skill guards."""

        replies = []

        if reset and main != "hwp_rifle_01":

            replies.append(self.gl("equip", "hwp_rifle_01", "common", 1))

        # equip's native RollQuality path silently falls back to common for masks

        # without the Common bit. kit already supports fixed explicit qualities.

        if quality == "common":

            replies.append(self.gl("equip", main, quality, 1))

            if off:

                replies.append(self.gl("equip", off, quality, 1))

        else:

            replies.append(self.gl("kit", 20, quality, ",".join([main] + ([off] if off else [])), "seed=417"))

        time.sleep(0.9)  # old marker buffs live600ms

        item = self.gl("bagitems").get("main", {})

        skills = self.bar().get("skills", [])

        ids = [s.get("id") for s in skills]

        expected_off = ("hwp_attack_glock_off" if "glock_oh" in (off or "") else

                        "hwp_attack_hcannon_off" if "hcannon_oh" in (off or "") else None)

        maximum = self.clip_max()

        expected_quality = {"common": 1, "uncommon": 2, "rare": 4, "epic": 8}.get(quality)

        ok = (all(r.get("ok") for r in replies) and item.get("id") == main

              and item.get("quality") == expected_quality and maximum > 0)

        if quality == "epic" and "rifle" in main:

            ok = ok and "hwp_attack_rifle_epic" in ids

        if expected_off:

            ok = ok and expected_off in ids

        elif "rifle" in main or "glock_mh" in main or "hcannon_mh" in main:

            ok = ok and any(s.get("button") == "main" and s.get("id", "").startswith("hwp_attack_") for s in skills)

        row = {"main": main, "off": off, "requested_quality": quality, "requested_ilvl": 1 if quality == "common" else 20,

               "equip_replies": replies, "equipped_main": item, "live_skills": ids,

               "clip_max": maximum,

               "requirements_cvar": self.gl("cvars", "dbg_cht_ignore_equipment_requirements").get("cvars", {})}

        return ok, row



    def current_rank(self, sid):

        return self.gl("skill", sid, 0).get("level", -1)



    def learn_rank(self, sid, rank):

        current = self.current_rank(sid)

        if 0 <= current < rank:

            self.gl("skill", sid, rank - current)

            time.sleep(0.5)

        return self.current_rank(sid)



    def bank_clear(self):

        for name in ("rocket_charges", "grenade_charges", "gl_charges"):

            self.gl("givestacks", self.STACKS + name, -999)



    def skill_press(self, sid, sval, d):

        button = self.entry(self.bar(), sid).get("button")

        if not button:

            raise RuntimeError(f"{sid} has no live skill button")

        if sid == "hwp_fs_frag":

            return self.targeted(button, d[0] * 90, d[1] * 90, (16, 170))

        if sid == "hwp_fs_turret":

            return self.targeted(button, d[0] * 60, d[1] * 60, (0, 120))

        return self.gl("input", hold(sval), 0, 0, d[0], d[1], button)



    def reload_rank(self, rank, d):

        sid = "hwp_fs_reload"

        tag = f"reload_rank_{rank}"

        self.top_up()

        maximum = self.clip_max()

        self.gl("input", 60, 0, 0, d[0], d[1], "skill1")

        time.sleep(0.25)

        full = self.clip()

        full_cast = self.stacks("reload_cast")

        full_reloading = self.stacks("reloading")

        refused = (full == maximum and not self.entry(self.bar(), sid).get("cd", 0)

                   and full_cast == 0 and full_reloading == 0)

        # Spend rounds through the primary attack before the measured reload.

        self.gl("input", 60, 0, 0, d[0], d[1], "main")

        time.sleep(0.85)

        before = self.clip()

        mana0 = self.bar().get("mana", -1)

        started = time.monotonic()

        self.gl("input", 60, 0, 0, d[0], d[1], "skill1")

        samples = []

        while time.monotonic() - started < 3.3:

            elapsed = time.monotonic() - started

            clip = self.clip()

            samples.append([round(elapsed, 3), clip])

            if clip == maximum:

                break

            time.sleep(0.04)

        elapsed = samples[-1][0] if samples else 99

        after = self.clip()

        mana1 = self.bar().get("mana", -1)

        expected = (2000, 1800, 1600, 1400, 1200)[rank - 1] / 1000

        self.check(tag, refused and 0 < before < maximum and after == maximum

                   and abs(elapsed - expected) < 0.5 and mana1 >= mana0 - 0.05,

                   {"skill": sid, "rank": rank, "expected_seconds": expected,

                    "observed_seconds": elapsed, "full_clip_refused": refused,

                      "full_clip_reload_cast": full_cast, "full_clip_reloading": full_reloading,

                    "clip": [before, after, maximum], "mana": [mana0, mana1], "samples": samples})



    def cooldown_refusal(self, sid, button, d, cost, mana_regen, mana_gain):
        """One actual hotkey frame with same-frame native cooldown/resource guards.

        TargetAOE/DirectionCharge selection itself calls CanActivate in
        PlayerTargetingHelper.CheckUseSkill; no unrelated main-hand click follows.
        The matching input_done proves ApplyHeld really wrote the input. Native
        remaining milliseconds and elapsed scene time reject an expired guard.
        """
        bank = ("grenade_charges" if sid == "hwp_fs_frag" else
                "rocket_charges" if sid == "hwp_fs_rpg" else "gl_charges")
        pre = self.g.gl_multi([
            ("skills",), ("skillbar",), ("controller",),
            ("givestacks", self.STACKS + bank, 0),
            ("input", 1, 0, 0, d[0], d[1], button),
        ])
        reply = pre[-1]
        done = self.g.wait_gl(lambda e: e.get("ev") == "input_done"
                              and e.get("id") == reply.get("id"), timeout=3) or {}
        post = self.g.gl_multi([
            ("skills",), ("skillbar",), ("controller",),
            ("givestacks", self.STACKS + bank, 0),
        ])
        raw0, bar0, control0, bank0, _ = pre
        raw1, bar1, control1, bank1 = post
        sk0, sk1 = self.entry(raw0, sid), self.entry(raw1, sid)
        cd0, cd1 = sk0.get("cd", -1), sk1.get("cd", -1)
        elapsed = raw1.get("now", -1) - raw0.get("now", -1)
        mana0, mana1 = bar0.get("mana", -1), bar1.get("mana", -1)
        ids = [x.get("id", "").rsplit(".", 1)[0] for x in pre]
        same_frame = bool(ids[0]) and len(set(ids)) == 1
        gain_valid = (isinstance(mana_regen, (int, float)) and isinstance(mana_gain, (int, float))
                      and mana_regen >= 0 and mana_gain >= 0)
        regen_rate = mana_regen * mana_gain if gain_valid else None
        guards = {
            "all_native_replies": all(x.get("ok") for x in pre + post),
            "same_frame_input_guard": same_frame,
            "complete_skill_readbacks": not raw0.get("truncated") and not raw1.get("truncated")
                and cd0 >= 0 and cd1 >= 0,
            "same_live_skill_button": sk0.get("button") == button and sk1.get("button") == button,
            "matching_one_frame_input_done": done.get("frames") == 1 and done.get("id") == reply.get("id"),
            "input_counter_advanced": control1.get("frames", -1) > control0.get("frames", -1),
            "native_window_unexpired": 0 <= elapsed < cd0,
            "no_bank_bypass_available": bank0.get("stacks") == 0 and bank1.get("stacks") == 0,
            "initial_mana_affords": 0 <= mana0 and 0 <= mana1 and mana0 >= cost,
            # Player.as:1242 native regeneration is ManaRegen * ManaGain.
            "regen_cannot_hide_full_cost": gain_valid and regen_rate * elapsed / 1000 + 0.1 < cost,
        }
        return {"valid_native_attempt": bool(all(guards.values())), "guards": guards,
                "cooldown_not_restarted": 0 < cd1 <= cd0,
                "drop": max(0, mana0 - mana1), "cooldown_ms": [cd0, cd1],
                "scene_elapsed_ms": elapsed, "mana": [mana0, mana1],
                "native_mana_regen": mana_regen, "native_mana_gain": mana_gain,
                "native_regen_rate": regen_rate, "required_mana": cost, "bank": bank,
                "bank_counts": [bank0.get("stacks"), bank1.get("stacks")],
                "same_frame_guard": same_frame, "input_done": done,
                "before": pre, "after": post,
                "targeting_contract": "Cooling target/charge skills reject the hotkey before selecting a target; no unrelated main-hand click."}

    def active_rank(self, sid, sval, rank, d):

        tag = f"{sid}_rank_{rank}"

        self.ready(sid, 25)

        self.gl("kill", 800, "hwp/firearms/units/turret")

        self.clear_dummies()

        dd, _ = self.clear_dir(d, 110)

        dummy = self.dummy(dd[0] * 90, dd[1] * 90)

        before_hp = self.hps([dummy]).get(dummy)

        self.top_up()

        self.bank_clear()

        before_clip = self.clip()

        live = self.entry(self.bar(), sid)

        live_cost, button = live.get("mana"), live.get("button")

        tip = tooltip_cost(sval, rank)

        mul = self.gl("state").get("player", {}).get("manaCostMul", 1.0) or 1.0

        native_stats = self.gl("benchstats")
        mana_regen, mana_gain = native_stats.get("manaRegen"), native_stats.get("manaGain")

        w = self.cast_watch(sid, lambda: self.skill_press(sid, sval, dd), secs=1.6)

        # Attempt the refusal before diagnostic reads consume the live cooldown.

        denied = self.cooldown_refusal(sid, button, dd, tip * mul, mana_regen, mana_gain)

        after_hp = self.hps([dummy]).get(dummy)

        after_clip = self.clip()

        lo, hi = w["drop"] - 0.4, w["drop"] + w["rate"] * w["gap"] + 0.4

        paid = w["full"] and lo <= tip * mul <= hi and live_cost == tip

        damaged = dummy is not None and before_hp is not None and after_hp is not None and after_hp < before_hp

        self.check(tag, paid and damaged and after_clip == before_clip and w["cd"] > 0 and not w["others"],

                   {"skill": sid, "rank": rank, "dummy": dummy, "hp": [before_hp, after_hp],

                    "mana_cost_tooltip": tip, "live_cost": live_cost, "mana_cost_multiplier": mul,

                    "watch": w, "clip": [before_clip, after_clip]})



        # Retain a separate strict row; stale/native-incomplete attempts fail setup.

        self.check(tag + "_cooldown_refusal", denied["valid_native_attempt"]

                   and denied["cooldown_not_restarted"] and denied["drop"] < 0.1,

                   {"skill": sid, "rank": rank, "watch": denied})



        # Insufficient mana is a separate attempt after the cooldown really expires.

        self.ready(sid, 25)

        self.bank_clear()

        self.g.console("cht_give_mana -999")

        time.sleep(0.12)

        low = self.bar().get("mana", 1e9)

        insufficient = self.cast_watch(sid, lambda: self.skill_press(sid, sval, dd), secs=0.7)

        cd = self.entry(self.bar(), sid).get("cd", 0)

        self.check(tag + "_mana_refusal", 0 <= low < tip * mul - 1 and insufficient["drop"] < 0.1 and cd == 0,

                   {"skill": sid, "rank": rank, "setup_mana": low,

                    "required_mana": tip * mul, "cooldown_after": cd, "watch": insufficient})



    def ranks(self, family):

        subclass, skills = FAMILIES[family]

        self.new_char("QARank" + family[:8], subclass)

        if not self.enter_floor("qa_rank_" + family):

            return

        self.check("god_disabled", self.ordinary_damage(), {"fixture": "empty isolated combat floor"})

        self.hwp("skillpoints 999", 0.3, until="skill points")

        d = self.open_dirs(130)[0]

        for sid, sval in skills:

            for rank in range(1, 6):

                got = self.learn_rank(sid, rank)

                self.check(f"{sid}_rank_{rank}_setup", got == rank,

                           {"skill": sid, "rank": rank, "readback_rank": got, "source": str(SKILLS / sval)})

                if got != rank:

                    continue

                if sid == "hwp_fs_reload":

                    self.reload_rank(rank, d)

                else:

                    self.active_rank(sid, sval, rank, d)

        self.clear_dummies()

        self.to_town()



    def magazine_crit(self):

        """Planner steady-hands: each pistol's own magazine determines its crit bonus.



        The measured lone gun fires once, the dual pair once per hand. Both therefore

        have fourteen rounds per magazine at rank5; their per-shot bonus must match.

        The existing shared-clip implementation incorrectly doubles the dual bonus.

        """

        observations = []

        for dual in (False, True):

            self.new_char("QACritDual" if dual else "QACritSolo")

            if not self.enter_floor("qa_magazine_crit"):

                return

            eq, gear = self.fixture_loadout("hwp_glock_mh_01", "hwp_glock_oh_01" if dual else None)

            self.check("crit_dual_gear" if dual else "crit_solo_gear", eq, gear)

            if not eq:

                return

            self.ordinary_damage()

            self.hwp("skillpoints 999", 0.3, until="skill points")

            d, (dummy,) = self.line_dummies(self.open_dirs(130)[0], [90])

            before = self.probe(rolls=1)

            got = self.learn_rank("hwp_fs_steady", 5)

            self.top_up()

            maximum = self.clip_max()

            hp0 = self.hps([dummy])[dummy]

            self.gl("input", 60, 0, 0, d[0], d[1], "main")

            time.sleep(0.85)

            remaining = self.clip()

            hp1 = self.hps([dummy])[dummy]

            after = self.probe(rolls=1)

            added = after.get("mainCritDmg", 0) - before.get("mainCritDmg", 0)

            row = {"dual": dual, "rank": got, "clip_max": maximum, "clip_after_natural_cycle": remaining,

                   "gear": gear,

                   "hp": [hp0, hp1], "base_main_crit_damage": before.get("mainCritDmg"),

                   "main_crit_damage": after.get("mainCritDmg"), "added_crit_damage": round(added, 4),

                   "expected_added_crit_damage_per_gun": 0.28,

                   "expected_source": "planner/data/skills/steady-hands.json:15"}

            observations.append(row)

            setup = got == 5 and maximum == (30 if dual else 15) and remaining == (28 if dual else 14) and hp1 < hp0

            self.check("crit_dual_setup" if dual else "crit_solo_setup", setup, row)

            self.check("crit_dual_per_magazine" if dual else "crit_solo_per_magazine",

                       setup and abs(added - 0.28) < 0.005, row)

            self.clear_dummies()

            self.to_town()

        self.check("crit_pair_matches_solo", len(observations) == 2 and

                   abs(observations[0]["added_crit_damage"] - observations[1]["added_crit_damage"]) < 0.005,

                   {"observations": observations})





def run(p, family="base", section="ranks", **_):

    c = Checks(p)

    try:

        if section == "magazine_crit":

            c.magazine_crit()

        else:

            c.ranks(family)

    except Exception as exc:

        c.check("qa_crashed", False, {"error": repr(exc), "family": family, "section": section})

    c.out["ok"] = bool(c.rows) and all(row["runtime"] == "PASS" for row in c.rows)

    c.out["rows"] = c.rows

    c.out["notes"] = c.notes

    c.out["terminal"] = " | ".join(c.notes)[-3000:]

    return c.out
