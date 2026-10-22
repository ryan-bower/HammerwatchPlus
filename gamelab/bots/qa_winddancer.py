"""Winddancer rank/orb behavior through input, live stats, HP and timed heals.

Base Gale uses ordinary bound-button input and its real cooldown. Orb/heal
fixtures explicitly reset only the supporting Gale cooldown via castat; native
evade/Heal/TimedTriggerEffect still execute. No direct modifier callbacks.
"""
import time

from gamelab.bots.plan_specs import BUFFS, Checks as SpecChecks
from gamelab.bots.plan_classesa import Checks as GeometryChecks
from gamelab.bots.qa_observe import collect as collect_observer


PG = "hwp_rog_protective_gale"
SW = "hwp_rog_second_wind"
LASTING = "hwp_rog_pg_lasting_gale"
TAILWIND = "hwp_rog_pg_tailwind"
BREEZE = "hwp_rog_sw_lingering_breeze"
SHARED = "hwp_rog_sw_shared_breath"
GAILS = [f"gale_{n}" for n in range(1, 6)]
TAILS = [f"gale_tailwind_{n}" for n in range(1, 4)]
BREEZES = [f"breeze_{n}" for n in range(1, 4)]


class Checks(SpecChecks):
    def me(self):
        return self.pos()

    def prepare(self, name):
        self.setup(name, "rogue", "hwp_rogue_winddancer", [])
        valid = self.out.get(name + "_char") and self.out.get(name + "_learned")
        return bool(valid) and self.enter_floor(name)

    def rank(self, skill, desired, tag):
        current = self.gl("skill", skill, 0).get("level", -1)
        reply = self.gl("skill", skill, desired - current) if 0 <= current < desired else {"level": current}
        self.flag(tag + "_rank", reply.get("level") == desired, str(reply))
        return reply.get("level") == desired

    def orb(self, skill, desired, tag):
        reply = self.gl("orb", skill, 1)
        self.flag(tag + "_orb", reply.get("level") == desired, str(reply))
        return reply.get("level") == desired

    def poll(self, name):
        reply = self.gl("hasbuff", BUFFS + name)
        buffs = reply.get("buffs", [])
        return reply.get("now"), buffs[0] if buffs else {}

    def clear_wind(self, tag, timeout=16):
        names = GAILS + TAILS + BREEZES
        until = time.monotonic() + timeout
        samples = []
        while time.monotonic() < until:
            reply = self.gl("hasbuff", *[BUFFS + name for name in names])
            active = [b for b in reply.get("buffs", []) if b.get("on")]
            samples.append({"now": reply.get("now"), "active": active})
            if not active:
                self.out[tag + "_expiry_setup"] = samples
                return True
            time.sleep(0.2)
        self.flag(tag + "_old_buffs_expired", False, str(samples))
        return False

    def support_gale(self, tag):
        """Controlled support cast, with held aim; not a cooldown/input claim."""
        mark = len(self.g.gl)
        self.gl("multi", "mana", 999, "+", "input", 1000, 0, 0, 1, 0, "+", "castat", PG, 1, 0, "nocd")
        reply = next((r for r in self.g.gl[mark:] if r.get("skill") == PG and "activated" in r), {})
        buff = self.wait_buff("gale_1", 2)
        ok = bool(reply.get("activated")) and bool(buff.get("on"))
        self.flag(tag + "_support_gale", ok, str({"cast": reply, "buff": buff}))
        return ok

    def expiry(self, name, expected_ms, first=None):
        now, buff = first or self.poll(name)
        samples = [{"now": now, "buff": buff}]
        if now is None or not buff.get("on") or buff.get("left") is None:
            return False, samples
        expiry = now + buff["left"]
        last, gone = now, None
        until = time.monotonic() + expected_ms / 1000 + 4
        while time.monotonic() < until:
            now, entry = self.poll(name)
            samples.append({"now": now, "buff": entry})
            if not entry.get("on"):
                gone = now
                break
            last = now
            time.sleep(0.1)
        valid = (gone is not None and last <= expiry + 100 and gone >= expiry - 100
                 and gone - last <= 1500 and expected_ms - 2500 <= buff["left"] <= expected_ms)
        return valid, samples

    def gale(self):
        if not self.prepare("gale_ranks"):
            return
        rows, passed = [], True
        for rank, chance in enumerate((0.15, 0.18, 0.21, 0.24, 0.30), 1):
            tag = f"gale_r{rank}"
            if not self.clear_wind(tag) or not self.rank(PG, rank, tag):
                passed = False
                continue
            until = time.monotonic() + 23
            while (self.skill_cd(PG) or 0) > 0 and time.monotonic() < until:
                time.sleep(0.3)
            cooldown = self.skill_cd(PG)
            # Native active cooldowns retain a small negative overshoot (-31ms
            # in the original all-rank run); every nonpositive value is ready.
            ready = cooldown is not None and cooldown <= 0
            # Native Rogue Evasion automatically charges one guaranteed Sidestep
            # after10s. Consume it through the real Evade path outside Gale, then
            # measure Gale's6s window before the10s native recharge can confound it.
            # No buff/stack is added, removed, or reset directly by this fixture.
            until = time.monotonic() + 12
            charged = self.gl("benchstats")
            while charged.get("evade", 0) < 0.999 and time.monotonic() < until:
                time.sleep(0.2)
                charged = self.gl("benchstats")
            consumed = self.gl("evade", 1)
            baseline = self.gl("benchstats")
            isolated = (charged.get("evade", 0) >= 0.999 and consumed.get("evaded")
                        and abs(baseline.get("evade", -1) - 0.10) <= 0.002)
            self.flag(tag + "_sidestep_control", bool(isolated),
                      str({"charged": charged, "consumed": consumed, "baseline": baseline}))
            self.gl("mana", 999)
            observer_tag = f"gale{rank}_{int(time.time() * 1000)}"
            observer_started = self.gl("buffobserve", observer_tag, 12000, BUFFS + f"gale_{rank}")
            pressed, spent, button = self.cast_skill(tag, PG, 40 + 5 * (rank - 1),
                                                    done=lambda: self.has(f"gale_{rank}")[f"gale_{rank}"].get("on"))
            first = self.poll(f"gale_{rank}")
            stats = self.gl("benchstats")
            expected = 1 - (1 - baseline.get("evade", 0)) * (1 - chance)
            effect = (isolated and ready and pressed > 0 and first[1].get("on") and first[1].get("hud")
                      and abs(stats.get("evade", -1) - expected) <= 0.002
                      and abs(spent - (40 + 5 * (rank - 1))) <= 6)
            self.flag(tag + "_cast_effect", effect, str({"presses": pressed, "button": button, "spent": spent,
                                                        "baseline": baseline, "stats": stats, "buff": first[1]}))
            polled_lifetime, samples = self.expiry(f"gale_{rank}", 6000, first)
            self.flag(tag + "_poll_resolution", polled_lifetime, str(samples))
            restored = self.gl("benchstats")
            observer = collect_observer(self.g, observer_tag, 15) if observer_started.get("ok") else {
                "usable": False, "errors": ["observer start failed"], "start_reply": observer_started, "events": []}
            on = next((e for e in observer.get("events", []) if e.get("buff_on")), None)
            off = next((e for e in observer.get("events", []) if on is not None
                        and e.get("now", 0) > on["now"] and not e.get("buff_on")), None)
            lifetime = (observer.get("usable") and on is not None and off is not None
                        and on.get("buff_dur") == 6000 and 5900 <= on.get("buff_left", 0) <= 6000
                        and abs(off["now"] - (on["now"] + on["buff_left"])) <= 67)
            self.flag(tag + "_six_seconds", bool(lifetime), str(observer))
            # Use the native expiry window: a Python reply after the12s observer
            # completes can arrive after vanilla Sidestep's10s recharge.
            reverted_rows = [e for e in observer.get("events", []) if off is not None
                             and not e.get("buff_on") and 0 <= e.get("now", 0) - off["now"] <= 200
                             and abs(e.get("evade", -1) - baseline.get("evade", -99)) <= 0.002]
            reverted = bool(observer.get("usable") and reverted_rows)
            self.flag(tag + "_reverts", reverted, str({"native": reverted_rows, "polled": restored}))
            passed &= effect and lifetime and reverted
            rows.append({"rank": rank, "presses": pressed, "button": button, "spent": spent,
                         "ready_cooldown_ms": cooldown,
                         "sidestep_charged": charged, "sidestep_consumed": consumed,
                         "expected_evade": expected, "baseline": baseline, "stats": stats,
                         "samples": samples, "native_observer": observer, "restored": restored})
        self.flag("gale_all_ranks", passed and len(rows) == 5)
        self.out["gale_trials"] = rows
        self.to_town()

    def second_wind(self):
        if not self.prepare("second_wind_ranks"):
            return
        equipped = self.gl("orb", LASTING, 3)
        self.flag("sw_support_lasting", equipped.get("level") == 3, str(equipped))
        rows, passed = [], equipped.get("level") == 3
        for rank, heal in enumerate((20, 30, 40, 50, 60), 1):
            tag = f"second_wind_r{rank}"
            if not self.clear_wind(tag) or not self.rank(SW, rank, tag) or not self.support_gale(tag):
                passed = False
                continue
            self.gl("hurt", 0.15)
            first = self.gl("evade", 80)
            self.gl("hurt", 0.15)
            blocked = self.gl("evade", 80)
            time.sleep(4.2)
            self.gl("hurt", 0.15)
            recovered = self.gl("evade", 80)
            delta = lambda reply: reply.get("hp", 0) - reply.get("hp0", 0)
            ok = (all(r.get("evaded") for r in (first, blocked, recovered))
                  and abs(delta(first) - heal) <= 1 and abs(delta(blocked)) <= 1
                  and abs(delta(recovered) - heal) <= 1)
            row = {"rank": rank, "heal": heal, "first": first, "blocked": blocked, "recovered": recovered,
                   "fixture": "Lasting Gale3 only supplies a long native evade-chance window"}
            self.flag(tag + "_heal_and_timeout", ok, str(row))
            passed &= ok
            rows.append(row)
        self.flag("second_wind_all_ranks", passed and len(rows) == 5)
        self.out["second_wind_trials"] = rows
        self.to_town()

    def lasting(self):
        if not self.prepare("lasting_gale_ranks"):
            return
        rows, passed = [], True
        for rank, ttl in enumerate((8000, 10000, 12000), 1):
            tag = f"lasting_r{rank}"
            if not self.clear_wind(tag) or not self.orb(LASTING, rank, tag) or not self.support_gale(tag):
                passed = False
                continue
            first = self.poll("gale_1")
            bind = self.bind(PG, "pg-ttl")
            valid, samples = self.expiry("gale_1", ttl, first)
            ok = bind == str(ttl) and valid
            self.flag(tag + "_actual_duration", ok, str({"bind": bind, "samples": samples}))
            passed &= ok
            rows.append({"rank": rank, "ttl": ttl, "bind": bind, "samples": samples})
        self.flag("lasting_all_ranks", passed and len(rows) == 3)
        self.out["lasting_trials"] = rows
        self.to_town()

    def move_sample(self, direction, ms=500):
        before = self.pos()
        reply = self.gl("input", ms, direction[0], direction[1])
        time.sleep(ms / 1000 + 0.25)
        after = self.pos()
        forward = (after[0] - before[0]) * direction[0] + (after[1] - before[1]) * direction[1]
        return {"before": before, "after": after, "direction": direction, "ms": ms, "forward": forward, "reply": reply}

    def movement_lane(self):
        walks = []
        for _ in range(8):
            terrain = self.gl("terrain", 160, 8)
            clear, direction = GeometryChecks.open_dirs(self)[0]
            if clear >= 130:
                return direction, {"terrain": terrain, "walks": walks, "clear": clear}
            if clear < 64:
                break
            walks.append(self.move_sample(direction, 280))
        return None, {"terrain": terrain, "walks": walks, "clear": clear}

    def tailwind(self):
        if not self.prepare("tailwind_ranks"):
            return
        rows, passed = [], True
        for rank, multiplier in enumerate((1.10, 1.15, 1.20), 1):
            tag = f"tailwind_r{rank}"
            if not self.clear_wind(tag) or not self.orb(TAILWIND, rank, tag):
                passed = False
                continue
            baseline = self.gl("benchstats")
            direction, terrain = self.movement_lane()
            if direction is None:
                self.flag(tag + "_movement_setup", False, str(terrain))
                passed = False
                continue
            ordinary = self.move_sample(direction)
            reverse = (-direction[0], -direction[1])
            returned = self.move_sample(reverse)
            if not self.support_gale(tag):
                passed = False
                continue
            time.sleep(0.7)  # after Gale's movement-slow casting animation
            stats = self.gl("benchstats")
            buff = self.has(f"gale_tailwind_{rank}")[f"gale_tailwind_{rank}"]
            boosted = self.move_sample(direction)
            self.move_sample(reverse)
            ratio = boosted["forward"] / ordinary["forward"] if ordinary["forward"] > 0 else 0
            stat_ok = abs(stats.get("moveSpeed", -1) - baseline.get("moveSpeed", -99) * multiplier) <= 0.02
            # Stats carry the exact multiplier. Travel validates actual motion,
            # with frame/console timing retained rather than pretending perfect clocks.
            motion_ok = ordinary["forward"] > 20 and boosted["forward"] > 20 and 0.9 <= ratio <= 1.45
            active = bool(buff.get("on")) and abs(stats.get("mhSpeed", -1) - baseline.get("mhSpeed", -99)) <= 0.002
            expired = self.clear_wind(tag + "_end")
            restored = self.gl("benchstats")
            reverts = expired and abs(restored.get("moveSpeed", -1) - baseline.get("moveSpeed", -99)) <= 0.02
            row = {"rank": rank, "multiplier": multiplier, "baseline": baseline, "stats": stats,
                   "terrain": terrain, "ordinary": ordinary, "returned": returned, "boosted": boosted,
                   "observed_travel_ratio": ratio, "buff": buff, "restored": restored}
            ok = stat_ok and motion_ok and active and reverts
            self.flag(tag + "_actual_speed", ok, str(row))
            passed &= ok
            rows.append(row)
        self.flag("tailwind_all_ranks", passed and len(rows) == 3)
        self.out["tailwind_trials"] = rows
        self.to_town()

    def breeze_snapshot(self, name):
        mark = len(self.g.gl)
        self.gl("multi", "hasbuff", BUFFS + name, "+", "floats", "+", "state")
        replies = self.g.gl[mark:]
        readback = next((r for r in replies if "buffs" in r and "now" in r), {})
        buffs = readback.get("buffs", [])
        return {"now": readback.get("now"), "buff": buffs[0] if buffs else {},
                "texts": next((r.get("texts", []) for r in replies if "texts" in r), []),
                "player": next((r.get("player", {}) for r in replies if "player" in r), {})}

    def breeze(self):
        if not self.prepare("lingering_breeze_ranks"):
            return
        self.gl("orb", LASTING, 3)
        self.rank(SW, 5, "breeze_heal_support")
        rows, passed = [], True
        for rank, heal in enumerate((2, 4, 6), 1):
            tag, name = f"breeze_r{rank}", f"breeze_{rank}"
            if not self.clear_wind(tag) or not self.orb(BREEZE, rank, tag) or not self.support_gale(tag):
                passed = False
                continue
            self.gl("hurt", 0.15)
            evade = self.gl("evade", 80)
            samples, births = [], []
            until = time.monotonic() + 6.3
            while time.monotonic() < until:
                sample = self.breeze_snapshot(name)
                samples.append(sample)
                if sample["now"] is not None:
                    for text in sample["texts"]:
                        if text.get("type") != 1 or text.get("num") != heal:
                            continue
                        born = sample["now"] - text.get("lived", 0)
                        if not any(abs(born - old) < 150 for old in births):
                            births.append(born)
                time.sleep(0.12)
            on = [s for s in samples if s["buff"].get("on")]
            off = [s for s in samples if not s["buff"].get("on")]
            hp0 = evade.get("hp", 0)
            hp1 = samples[-1]["player"].get("hp", 0) if samples else 0
            no_cap = bool(samples) and all(s["player"].get("hp", 0) < s["player"].get("hpMax", 0) for s in samples)
            cadence = len(births) == 4 and all(800 <= b - a <= 1200 for a, b in zip(sorted(births), sorted(births)[1:]))
            deadline = on[0]["now"] + on[0]["buff"].get("left", 0) if on else 0
            stopped = bool(off) and all(b < deadline + 100 for b in births)
            ok = (evade.get("evaded") and bool(on) and on[0]["buff"].get("hud")
                  and cadence and stopped and no_cap and hp1 - hp0 >= heal * 4 - 1)
            row = {"rank": rank, "heal_each": heal, "evade": evade, "heal_births": births,
                   "samples": samples, "hp_after_burst": hp0, "hp_end": hp1,
                   "oracle": "PlayerHealed text is emitted by actual Heal; passive regeneration emits no text"}
            self.flag(tag + "_actual_timed_heals", ok, str(row))
            passed &= ok
            rows.append(row)
        self.flag("breeze_all_ranks", passed and len(rows) == 3)
        self.out["breeze_trials"] = rows
        self.to_town()


def run(p, sections="gale,second_wind,lasting,tailwind,breeze", **_):
    c = Checks(p)
    for section in sections.split(","):
        try:
            getattr(c, section)()
        except Exception as exc:
            c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
