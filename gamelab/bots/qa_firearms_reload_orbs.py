"""Every Explosive/Over-Reload rank through natural reload input.

Gold-window trials are a fixed protocol: one deliberate early miss calibrates
delivery, then three independent timed presses, all retained with native timings.
No retry-until-pass loop, perfect-buff setter or direct reload completion is used.
"""
import re
import time

from gamelab.bots.qa_firearms_variants import Checks as Base


class Checks(Base):
    def spend_burst(self, d):
        self.clear_dummies()
        self.top_up()
        before = self.clip()
        maximum = self.clip_max()
        self.gl("input", 320, 0, 0, d[0], d[1], "main")
        time.sleep(1)
        after = self.clip()
        return {"clip": [before, after], "capacity": maximum,
                "valid": before == maximum and before >= 30 and after == before - 3}

    def explosive_trial(self, d):
        spent = self.spend_burst(d)
        dd, dummy = self.tough(d, 100)
        hp0 = self.hps([dummy])[dummy]
        fixture = self.gl("skillcrit", "hwp_fs_reload", 1)
        tag, reply = self.track_start(3700, "reload_mag_rifle.unit")
        mark = self.log_pos()
        try:
            mana0 = self.bar().get("mana", -1)
            self.gl("input", 60, 0, 0, dd[0], dd[1], "skill1")
            event = self.track_finish(tag, 10)
            hp1 = self.hps([dummy])[dummy]
            crit_after = self.gl("skillcrit", "hwp_fs_reload")
        finally:
            restored = self.gl("skillcrit", "hwp_fs_reload", "restore")
        log = self.log_from(mark)
        thrown = re.findall(r"explosive reload: (\d+) rounds at (\d+)", log)
        damage = (hp0 - hp1) * 10000000
        return {"natural_ammo_spend": spent, "hp": [hp0, hp1], "damage": damage,
                "track": event, "native_throw_log": thrown, "fixture": fixture,
                "crit_after": crit_after, "restore": restored, "clip_after": self.clip(),
                "mana": [mana0, self.bar().get("mana", -1)],
                "valid": spent["valid"] and fixture.get("override_active")
                         and crit_after.get("override_active") and not restored.get("override_active")
                         and reply.get("ok") and event.get("truncated") == 0
                         and len(event.get("tracks", [])) == 1 and len(thrown) == 1
                         and int(thrown[0][0]) == spent["clip"][1] and self.clip() == 30
                         and hp0 > hp1 > 0 and damage > 0}

    def explosive(self):
        if not self.prepare("QAExplosiveRanks"):
            return
        d = self.open_dirs(160)[0]
        baseline = None
        for rank, each in enumerate((5, 8, 12), 1):
            ok, got = self.orb("hwp_fs_reload_explosive", 1)
            trial = self.explosive_trial(d)
            if rank == 1:
                baseline = trial["damage"]
            ratio = trial["damage"] / max(0.001, baseline)
            self.check(f"explosive_reload_rank_{rank}_real_magazine_damage", ok and got == rank and trial["valid"]
                       and trial["native_throw_log"] == [("27", str(each))]
                       and abs(ratio - each / 5) < 0.03,
                       {"orb": "hwp_fs_reload_explosive", "rank": rank,
                        "damage_per_remaining_round": each, "expected_damage_ratio": each / 5,
                        "actual_damage_ratio": ratio, "natural_reload_trial": trial})
        self.clear_dummies()
        self.to_town()

    def window_trial(self, d, early=False, lag=0):
        spent = self.spend_burst(d)
        mark = self.log_pos()
        sent = time.monotonic()
        start = self.gl("input", 60, 0, 0, d[0], d[1], "skill1")
        win = self.wait_log(r"over-reload: manual window (\d+)-(\d+) of (\d+) ms", mark, 1)
        if not win:
            return {"valid": False, "reason": "No native manual window; no gold press was injected.",
                    "spend": spent, "start_reply": start, "log": self.log_from(mark)}
        lo, hi, total = map(int, win.groups())
        target = 400 if early else (lo + hi) / 2
        time.sleep(max(0, sent + target / 1000 - lag - time.monotonic()))
        press = self.gl("input", 60, 0, 0, d[0], d[1], "skill1")
        time.sleep(2.2)
        log = self.log_from(mark)
        hits = re.findall(r"over-reload: manual perfect at (\d+)", log)
        misses = re.findall(r"over-reload: manual missed at (\d+)", log)
        native_at = int((hits or misses)[0]) if hits or misses else None
        in_gold = native_at is not None and lo <= native_at < hi
        correct = (len(hits) + len(misses) == 1 and bool(hits) == in_gold)
        return {"valid": spent["valid"] and start.get("ok") and press.get("ok") and correct,
                "early_control": early, "spend": spent, "window": [lo, hi, total], "target_ms": target,
                "native_pressed_at_ms": native_at, "perfect": bool(hits), "missed": bool(misses),
                "input_lag_correction_seconds": lag, "capacity_after": self.clip_max(),
                "clip_after": self.clip(), "log": log}

    def over(self):
        if not self.prepare("QAOverReloadRanks"):
            return
        d = self.open_dirs(160)[0]
        for rank, bonus in enumerate((5, 10, 15), 1):
            ok, got = self.orb("hwp_fs_reload_over", 1)
            early = self.window_trial(d, early=True)
            calibration_valid = (early["valid"] and early["missed"] and not early["perfect"]
                                 and early["capacity_after"] == early["clip_after"] == 30)
            self.check(f"over_reload_rank_{rank}_early_miss_control", ok and got == rank and calibration_valid,
                       {"orb": "hwp_fs_reload_over", "rank": rank, "natural_early_control": early})
            lag = ((early.get("native_pressed_at_ms") or 400) - 400) / 1000
            trials = [self.window_trial(d, lag=lag) for _ in range(3)]
            semantics = all(t["valid"] and t["clip_after"] == t["capacity_after"]
                            and t["capacity_after"] == (30 + bonus if t["perfect"] else 30) for t in trials)
            self.check(f"over_reload_rank_{rank}_native_perfect_capacity", calibration_valid and semantics
                       and any(t.get("perfect") for t in trials),
                       {"orb": "hwp_fs_reload_over", "rank": rank, "expected_base_capacity": 30,
                        "expected_nonstacking_bonus": bonus, "calibration": early, "fixed_three_gold_trials": trials,
                        "limit": "If all native presses miss their windows, positive effect coverage remains UNTESTED; no timing miss alone proves a gameplay bug."})
        self.to_town()


def run(p, section="explosive", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.check("reload_orbs_crashed", False, {"section": section, "error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
