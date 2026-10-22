"""Natural grenade, missile and shotgun variant effects at every built rank.

Native per-frame tracks measure actual projectile counts/area lifetimes. Fixed
damage controls use expiring crit setup; no damage/TTL/target-HP setter is used.
"""
import re
import time

from gamelab.bots.plan_firearms_more import RESIST
from gamelab.bots.qa_firearms_passives import Checks as Base


class Checks(Base):
    def track_start(self, ms, filt):
        self._track_index = getattr(self, "_track_index", 0) + 1
        tag = f"fa{int(time.time() * 1000)}x{self._track_index}"
        reply = self.gl("track", tag, ms, 500, filt)
        return tag, reply

    def track_finish(self, tag, timeout):
        return self.g.wait_gl(lambda event: event.get("ev") == "track" and event.get("tag") == tag,
                              timeout) or {}

    def buffs(self):
        return [buff for actor in self.gl("actorbuffs", 400, "target_dummy").get("actors", [])
                for buff in actor.get("buffs", [])]

    @staticmethod
    def area_countdown(path, event, duration, subtype, exempt=False):
        """Validate actual native TTL/callback progress, not a fitted wall lifetime."""
        area = path.get("area", {})
        changes = area.get("ttl_transitions", [])
        frames = event.get("frames", 0)
        frame_ms = event.get("ms", 0) / frames if frames else 999
        frequency = area.get("freq0", 0)
        initial_seen = area.get("ttl0") == duration
        trace_valid = (len(changes) >= 2 and area.get("truncated") == 0
                       and changes[0][1] == area.get("ttl0") and changes[-1][1] == area.get("ttl1")
                       and all(a[0] > b[0] and 0 < a[1] < b[1] for b, a in zip(changes, changes[1:])))
        # SetUpdateFrequency's first phase is not specified by available source.
        # Exclude its initial debit from time-vs-counter comparison. Later native
        # TTL debits must match elapsed callback intervals at observed frame precision.
        cadence = trace_valid and all(abs((a[0] - b[0]) - (b[1] - a[1])) <= 2 * frame_ms
                                      for b, a in zip(changes[1:], changes[2:]))
        deadline = changes[-1][0] + frequency if changes else -1
        final_counter = area.get("ttl1", -1)
        terminal = (0 < final_counter <= frequency + 2 * frame_ms
                    and abs(area.get("scene1", -999) - deadline) <= 2 * frame_ms
                    and event.get("ms", 0) - path.get("t1", 0) >= 150)
        owner = area.get("owner0", -1)
        identity = (area.get("type") == subtype and isinstance(owner, int) and owner > 0
                    and area.get("owner1") == owner)
        producer = (not exempt or (area.get("producer_exempt0") is True
                    and area.get("producer_exempt1") is True and area.get("summon_cap1") == 1000))
        valid = (initial_seen and identity and producer and frequency == area.get("freq1") == 500
                 and 0 < frame_ms <= 50 and trace_valid and cadence and terminal)
        return {"valid": bool(valid), "initialized_authored_ttl_seen": initial_seen,
                "native_identity_valid": identity, "native_producer_valid": producer,
                "native_ttl_trace_valid": bool(trace_valid), "later_callback_cadence_valid": bool(cadence),
                "native_terminal_deadline_valid": bool(terminal), "expected_ttl_ms": duration,
                "measured_frame_ms": frame_ms, "expected_terminal_scene_ms": deadline,
                "post_start_cadence_intervals": max(0, len(changes) - 2),
                "native_area": area,
                "scope": "1s areas have only one positive post-start counter; no multi-step cadence claim."}

    def grenades(self):
        variants = [("stun", (1000, 2000, 3000), "grenade_frag_stun.unit"),
                    ("fire", (4000, 6000, 8000), "grenade_incendiary_area.unit"),
                    ("gas", (3000, 4000, 5000), "grenade_gas_cloud.unit")]
        for variant, durations, filt in variants:
            if not self.prepare("QAGrenade" + variant):
                return
            d = self.open_dirs(150)[0]
            for rank, duration in enumerate(durations, 1):
                ok, got = self.orb("hwp_fs_frag_" + variant, 1)
                self.ready("hwp_fs_frag", 15)
                self.top_up()
                dd, dummy = self.tough(d, 90)
                initial = self.hps([dummy])[dummy]
                # Targeted grenade input performs several native cursor/button reads
                # before the150ms cast and projectile/fuse. The original+2200
                # window ended while every Fire/Gas area was still alive.
                track_budget_ms = duration + 6000
                tag, tracked = self.track_start(track_budget_ms, filt)
                clip = self.clip()
                self.skill_press("hwp_fs_frag", "fs_frag.sval", dd)
                samples = []
                started = time.monotonic()
                while time.monotonic() - started < 1.6:
                    samples.append({"elapsed": time.monotonic() - started, "buffs": self.buffs(),
                                    "hp": self.hps([dummy])[dummy]})
                    time.sleep(0.04)
                early = self.hps([dummy])[dummy]
                event = self.track_finish(tag, track_budget_ms / 1000 + 4)
                final = self.hps([dummy])[dummy]
                paths = event.get("tracks", [])
                tags = {t for s in samples for b in s["buffs"] for t in b.get("tags", [])}
                life = paths[0].get("t1", 0) - paths[0].get("t0", 0) if len(paths) == 1 else -1
                end_gap = event.get("ms", 0) - paths[0].get("t1", 0) if len(paths) == 1 else -1
                # A per-frame track reports its final present sample, not a
                # destruction event. Require a real absence tail; a track ending
                # on the last sample is censored and cannot establish a lifetime.
                complete = end_gap >= 150
                common = (ok and got == rank and tracked.get("ok") and event.get("truncated") == 0
                          and len(paths) == 1 and complete and initial > final > 0 and self.clip() == clip)
                if variant == "stun":
                    remaining = {t: max((b.get("left", -1) for s in samples for b in s["buffs"]
                                        if t in b.get("tags", [])), default=-1) for t in ("stun", "slow")}
                    expired = self.buffs()
                    effect = (all(duration - 350 <= left <= duration for left in remaining.values())
                              and not any(t in b.get("tags", []) for b in expired for t in ("stun", "slow")))
                else:
                    remaining = {}
                    countdown = self.area_countdown(paths[0], event, duration, "DangerAreaBehaviorP") if len(paths) == 1 else {"valid": False}
                    effect = countdown["valid"] and final < early
                    effect = effect and ("blindness" in tags if variant == "fire" else "hwp_gassed" in tags)
                self.check(f"frag_{variant}_rank_{rank}_natural_effect", common and effect,
                           {"orb": "hwp_fs_frag_" + variant, "rank": rank, "expected_duration_ms": duration,
                            "native_track": event, "track_budget_ms": track_budget_ms,
                            "track_absence_tail_ms": end_gap, "track_complete": complete,
                            "measured_unit_lifetime_ms": life,
                            "native_countdown_oracle": countdown if variant != "stun" else None,
                            "native_debuff_max_left_ms": remaining, "early_fixed_observations": samples,
                            "hp": [initial, early, final], "clip_before": clip, "clip_after": self.clip()})
            self.clear_dummies()
            self.to_town()

    def observed_hp_finish(self, tag, timeout=20):
        """Collect every bounded native-frame observer part without changing input."""
        first = self.g.wait_gl(lambda e: e.get("ev") == "buffobserve" and e.get("tag") == tag, timeout) or {}
        parts = {first.get("part", -1): first} if first else {}
        count = first.get("parts", 0)
        for _ in range(max(0, min(4, count) - 1)):
            row = self.g.wait_gl(lambda e: e.get("ev") == "buffobserve" and e.get("tag") == tag
                                 and e.get("part") not in parts, 3) or {}
            if row:
                parts[row.get("part", -1)] = row
        events = [event for i in sorted(parts) for event in parts[i].get("events", [])]
        valid = (1 <= count <= 4 and set(parts) == set(range(count)) and events
                 and all(not x.get("truncated") and x.get("dropped") == 0 for x in parts.values()))
        return {"parts": list(parts.values()), "events": events, "valid": bool(valid),
                "start": first.get("start", -1), "end": first.get("end", -1)}

    @staticmethod
    def native_round(value):
        # Pinned Behaviors/Armor.as:26: positive nonzero damage has a one-HP floor.
        return max(1, int(value + 0.5)) if value > 0 else 0

    def rocket_prediction(self, trial, variant, rank):
        """Predict HP from source components and measured caster fields, never variant HP."""
        stats, probe, elements = trial["caster_fields"]
        observed = trial["native_hp_observer"]["events"]
        buff_mul = observed[0]["damageMul"]
        multiplier = (buff_mul * stats["damageMul"] * (200 + stats["spellPower"]) / 200
                      * probe["skillDmgMul"] * (probe["spellCritDmg"] + probe["skillCritDmg"])
                      * probe["damageMul"][1])
        # RPG is unupgraded in this fresh fixture. Damage.FillDamage rounds the
        # intensity-scaled200 first; PlayerBase then rounds caster scaling; native
        # ApplyArmor rounds against the pinned1000resistance (divisor6).
        def direct(element, intensity=1):
            raw = self.native_round(200 * intensity)
            outgoing = self.native_round(raw * multiplier * elements[element])
            return self.native_round(outgoing / 6)
        def fire(intensity=1):
            damage = direct("fire", intensity)
            return damage + int(damage * 0.33)
        components = {}
        if variant == "magic":
            components = {"ice_direct": direct("ice"), "fire_with_native_pool": fire((0.25, 0.4)[rank - 1])}
        elif variant == "fatboy":
            poison = direct("poison", (0.4, 0.6)[rank - 1])
            components = {"fire_with_native_pool": fire(), "poison_direct": poison,
                          "native_poison_pool": int(poison * 0.8)}
        elif variant == "quad":
            components = {"four_fire_hits_and_native_pools": 4 * fire()}
        else:
            components = {"fire_with_native_pool": fire()}
        want_skill_mul = ((0.8, 1.0)[rank - 1] if variant == "magic" else
                          (0.3, 0.35)[rank - 1] if variant == "quad" else 1.0)
        independent_setup = (all(x.get("ok") for x in (stats, probe, elements))
                             and probe.get("skill") == "hwp_fs_rpg" and probe.get("rolls") == 0
                             and abs(probe["skillDmgMul"] - want_skill_mul) < 0.0001
                             and all(abs(x["damageMul"] - buff_mul) < 0.0001 for x in observed)
                             and all(elements.get(e, 0) > 0 for e in ("fire", "ice", "poison")))
        return {"expected_total_hp": sum(components.values()), "native_components": components,
                "captured_caster_multiplier": multiplier, "source_skill_multiplier": want_skill_mul,
                "valid": bool(independent_setup),
                "source": ["Damage.as:134", "PlayerBase.as:840-932", "Armor.as:11-39",
                           "CompositeActorBehavior.as:723-756", "ActorBuffList.as:543-547",
                           "Data/Misc.as:55-67", "rocket.inc", "rocket_magic_burn.unit", "demo_rpg.sval"]}

    def rocket_trial(self, d, filt):
        self.ready("hwp_fs_rpg", 25)
        self.bank_clear()
        self.top_up()
        dd, dummy = self.tough(d, 90, RESIST)
        hp0 = self.hps([dummy])[dummy]
        fixture = self.gl("skillcrit", "hwp_fs_rpg", 1)
        caster = self.g.gl_multi([["benchstats"], ["critprobe", 0, 400, "target_dummy", "hwp_fs_rpg"],
                                  ["dmgmuls"]])
        tag, tracked = self.track_start(2600, filt)
        observer_tag = tag + "hp"
        observer_reply = self.gl("buffobserve", observer_tag, 14000, "-", "-", dummy)
        start = time.monotonic()
        changes, samples = [], []
        previous = hp0
        try:
            clip = self.clip()
            self.gl("input", 720, 0, 0, dd[0], dd[1], "skill3")
            while time.monotonic() - start < 2.15:
                # HP and blindness share one native console frame; the former
                # sequential reads hid462ms before the first Fatboy buff sample.
                near, actors, clock = self.g.gl_multi([
                    ["near", 600, "target_dummy"], ["actorbuffs", 400, "target_dummy"], ["clock"]])
                unit = next((u for u in near.get("units", []) if u.get("unit") == dummy), {})
                maximum = unit.get("hpMax", 0)
                hp = (0.0 if unit.get("dead") else unit.get("hpExact", 0) / maximum) if maximum > 0 else 0.0
                native_buffs = [b for actor in actors.get("actors", []) if actor.get("unit") == dummy
                                for b in actor.get("buffs", [])]
                sample_valid = (near.get("ok") and actors.get("ok") and clock.get("ok")
                                and actors.get("truncated") == 0 and maximum == 600
                                and unit.get("hpExact") is not None)
                if hp < previous:
                    changes.append({"elapsed": time.monotonic() - start, "damage": (previous - hp) * 600})
                previous = hp
                samples.append({"elapsed": time.monotonic() - start, "hp": hp, "buffs": native_buffs,
                                "scene_ms": clock.get("sceneMs"), "native_sample_valid": bool(sample_valid),
                                "native_hp_row": unit,
                                "native_reply_ids": [near.get("id"), actors.get("id"), clock.get("id")]})
                time.sleep(0.03)
            event = self.track_finish(tag, 7)
            observer = self.observed_hp_finish(observer_tag)
            hp1 = self.hps([dummy])[dummy]
            crit_after = self.gl("skillcrit", "hwp_fs_rpg")
        finally:
            restored = self.gl("skillcrit", "hwp_fs_rpg", "restore")
        paths = event.get("tracks", [])
        rows = observer["events"]
        native_changes = []
        prior = 600
        for row in rows:
            if row.get("target_hpExact", prior) < prior - 0.05:
                native_changes.append({"scene_ms": row["now"], "damage": prior - row["target_hpExact"]})
            prior = row.get("target_hpExact", prior)
        # Observer starts after track starts: start+relative last projectile sight
        # is a conservative upper bound on the actual last projectile scene time.
        # Alive fresh600HP bounds poisonpool<=479; native20%/250ms drain needs at
        # most28ticks=7s.8s after last projectile also covers400ms Magic delay.
        latest_projectile_bound = observer["start"] + max((p["t1"] for p in paths), default=14000) + 33
        settled_ms = observer["end"] - latest_projectile_bound
        native_valid = (observer_reply.get("ok") and observer["valid"] and rows
                        and all(x.get("player_valid") and x.get("target_valid") and x.get("target_hpMax") == 600
                                for x in rows) and abs(rows[0]["target_hpExact"] - 600) < 0.05
                        and settled_ms >= 8000 and abs(rows[-1]["target_hpExact"] - hp1 * 600) < 0.05)
        damage = (hp0 - hp1) * 600
        return {"damage": damage, "hp": [hp0, hp1], "clip": [clip, self.clip()], "track": event,
                "changes": changes, "observations": samples, "native_hp_changes": native_changes,
                "caster_fields": caster, "native_hp_observer": observer, "settled_native_ms": settled_ms,
                "projectile_lifetimes_ms": [p["t1"] - p["t0"] for p in paths],
                "fixture": fixture, "crit_after": crit_after, "restore": restored,
                "valid": fixture.get("override_active") and crit_after.get("override_active")
                         and crit_after.get("crit_chance") == 1 and not restored.get("override_active")
                         and tracked.get("ok") and event.get("truncated") == 0 and hp0 > hp1 > 0
                         and bool(native_valid) and all(x["native_sample_valid"] for x in samples)
                         and damage > 0 and self.clip() == clip}

    def missiles(self):
        if not self.prepare("QAMissileRanks", "hwp_firearms_demolitions"):
            return
        d = self.open_dirs(150)[0]
        control = [self.rocket_trial(d, "rocket.unit") for _ in range(3)]
        baseline = sum(x["damage"] for x in control)
        controls = [self.rocket_prediction(x, "control", 1) for x in control]
        self.check("missile_real_damage_control", baseline > 0 and all(x["valid"] and y["valid"]
                   and len(x["track"].get("tracks", [])) == 1
                   and abs(x["damage"] - y["expected_total_hp"]) < 0.1 for x, y in zip(control, controls)),
                   {"fixed_controls": control, "independent_source_predictions": controls})
        for variant in ("fatboy", "magic", "quad"):
            for rank in (1, 2):
                ok, got = self.orb("hwp_fs_rpg_" + variant, 1)
                trials = [self.rocket_trial(d, "rocket_" + variant + ".unit") for _ in range(3)]
                predictions = [self.rocket_prediction(x, variant, rank) for x in trials]
                ratio = sum(x["damage"] for x in trials) / max(0.001, baseline)
                want_count = 4 if variant == "quad" else 1
                special = True
                if variant == "fatboy":
                    duration = (2000, 4000)[rank - 1]
                    special = all(max((b.get("left", -1) for s in x["observations"] for b in s["buffs"]
                                       if "blindness" in b.get("tags", [])), default=-1) >= duration - 400 for x in trials)
                elif variant == "magic":
                    special = all(len(x["native_hp_changes"]) >= 2 and
                                  250 < x["native_hp_changes"][1]["scene_ms"] - x["native_hp_changes"][0]["scene_ms"] < 650
                                  for x in trials)
                self.check(f"rpg_{variant}_rank_{rank}_natural_effect", ok and got == rank and special
                           and all(x["valid"] and y["valid"] and len(x["track"].get("tracks", [])) == want_count
                                   and abs(x["damage"] - y["expected_total_hp"]) < 0.1 for x, y in zip(trials, predictions)),
                           {"orb": "hwp_fs_rpg_" + variant, "rank": rank,
                            "expected_projectile_count": want_count, "actual_real_damage_ratio": ratio,
                            "independent_source_predictions": predictions, "fixed_trials": trials,
                            "control_damage": baseline,
                            "oracle": "Exact settled native integer HP from source components and actual caster fields; raw elemental shares are not total-HP ratios."})
            self.orb_off("hwp_fs_rpg_" + variant)
        self.clear_dummies()
        self.to_town()

    def shotgun_trial(self, d, duration=0):
        self.ready("hwp_fs_burst", 10)
        self.top_up()
        dd, dummy = self.tough(d, 96)
        hp0 = self.hps([dummy])[dummy]
        fixture = self.gl("skillcrit", "hwp_fs_burst", 1)
        mark = self.log_pos()
        tag, tracked = self.track_start(duration + 1800, "dragons_breath.unit")
        try:
            self.gl("input", 720, 0, 0, dd[0], dd[1], "skill3")
            event = self.track_finish(tag, duration / 1000 + 7)
            hp1 = self.hps([dummy])[dummy]
            crit_after = self.gl("skillcrit", "hwp_fs_burst")
        finally:
            restored = self.gl("skillcrit", "hwp_fs_burst", "restore")
        log = self.log_from(mark)
        damage = (hp0 - hp1) * 10000000
        return {"damage": damage, "hp": [hp0, hp1], "track": event, "log": log,
                "shell_count": len(re.findall(r"shotgun: \d+ hit", log)),
                "fixture": fixture, "crit_after": crit_after, "restore": restored,
                "valid": fixture.get("override_active") and crit_after.get("override_active")
                         and not restored.get("override_active") and tracked.get("ok")
                         and event.get("truncated") == 0 and hp0 > hp1 > 0}

    def shotgun(self):
        if not self.prepare("QABurstOrbRanks", "hwp_firearms_assault"):
            return
        d = self.open_dirs(170)[0]
        control = self.shotgun_trial(d)
        self.check("shotgun_real_damage_control", control["valid"] and control["shell_count"] == 2, control)
        ok, rank = self.orb("hwp_fs_burst_triple", 1)
        triple = self.shotgun_trial(d)
        ratio = triple["damage"] / max(0.001, control["damage"])
        self.check("triple_barrel_real_third_shell", ok and rank == 1 and triple["valid"]
                   and triple["shell_count"] == 3 and abs(ratio - 1.5) < 0.03,
                   {"orb": "hwp_fs_burst_triple", "rank": rank, "real_damage_ratio": ratio,
                    "control": control, "natural_three_shell_cast": triple})
        self.orb_off("hwp_fs_burst_triple")
        previous = control["damage"]
        for rank, duration in enumerate((1000, 3000), 1):
            ok, got = self.orb("hwp_fs_burst_breath", 1)
            trial = self.shotgun_trial(d, duration)
            paths = trial["track"].get("tracks", [])
            lifetimes = [x.get("t1", 0) - x.get("t0", 0) for x in paths]
            countdowns = [self.area_countdown(path, trial["track"], duration, "HWPFirearmsBreathArea", exempt=True)
                          for path in paths]
            expected_radii = sorted([48] * 2 + [96] * 4 + [140.8] * 6)
            actual_radii = sorted(path.get("dmax", -1) for path in paths)
            spatial = len(actual_radii) == 12 and all(abs(a - b) < 0.5 for a, b in zip(actual_radii, expected_radii))
            self.check(f"dragons_breath_rank_{rank}_real_fire_and_ground", ok and got == rank and trial["valid"]
                       and trial["shell_count"] == 2 and len(paths) == 12
                       and spatial and all(x["valid"] for x in countdowns) and trial["damage"] > previous * 1.08,
                       {"orb": "hwp_fs_burst_breath", "rank": rank, "expected_ground_lifetime_ms": duration,
                        "native_ground_lifetimes_ms": lifetimes, "native_ground_countdown_oracles": countdowns,
                        "expected_ground_radii": expected_radii, "actual_ground_radii": actual_radii,
                        "previous_rank_or_control_damage": previous,
                        "natural_two_shell_cast_and_ground": trial})
            previous = trial["damage"]
        self.clear_dummies()
        self.to_town()


def run(p, section="grenades", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("variant_effect_crashed", False, {"section": section, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
