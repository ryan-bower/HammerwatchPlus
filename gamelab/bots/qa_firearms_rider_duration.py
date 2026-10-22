"""Stunning Shock built ranks during fixed natural solo-pistol firing.

The250ms first rank expires before the next solo-pistol round. Observed native
time-left therefore isolates one application. Rank2 also proves longer real stun.
"""
import re
import time

from gamelab.bots.qa_firearms_passives import Checks as Base


class Checks(Base):
    def observe(self, d):
        dd, dummy = self.tough(d, 80)
        hp0 = self.hps([dummy])[dummy]
        trials = []
        for trial in range(3):
            self.top_up()
            self.hwp("firearms elements reset", 0.2, until="elements: reset")
            self.gl("input", 10000, 0, 0, dd[0], dd[1], "main")
            end = time.monotonic() + 10.5
            samples = []
            while time.monotonic() < end:
                response = self.gl("actorbuffs", 400, "target_dummy")
                active = [b for a in response.get("actors", []) for b in a.get("buffs", [])
                          if "stun" in b.get("tags", [])]
                if active:
                    samples.append({"native_left_ms": [b.get("left", -1) for b in active], "reply": response})
                time.sleep(0.05)
            shots = self.hwp("firearms shots", 0.2, until="shots:")
            parsed = re.findall(r"shots: \d+ rounds, gaps ([\d ]+)", shots)
            gaps = list(map(int, parsed[-1].split())) if parsed else []
            trials.append({"trial": trial + 1, "fired": self.fired(), "positive_stun_observations": samples,
                           "hp": self.hps([dummy])[dummy], "native_recent_shot_gaps_ms": gaps,
                           "min_native_gap_ms": min(gaps, default=0)})
        hp1 = self.hps([dummy])[dummy]
        left = [n for trial in trials for sample in trial["positive_stun_observations"]
                for n in sample["native_left_ms"]]
        return {"fixed_three_holds": trials, "hp": [hp0, hp1],
                "lightning_rounds": sum(t["fired"].get("lightning", 0) for t in trials),
                "left_ms": left, "max_left_ms": max(left, default=0),
                "valid": hp0 > hp1 > 0 and all(t["min_native_gap_ms"] > 250 for t in trials)
                         and sum(t["fired"].get("lightning", 0) for t in trials) >= 3}

    def stun(self):
        if not self.prepare("QAStunDuration"):
            return
        ok, gear = self.fixture_loadout("hwp_glock_mh_01")
        level = self.learn_rank("hwp_fs_scavenger", 5)
        bias_ok, bias_rank = self.orb("hwp_fs_scavenger_lightning", 3)
        d = self.open_dirs(150)[0]
        self.check("stun_duration_natural_solo_fixture", ok and level == 5 and bias_ok and bias_rank == 3,
                   {"actual_gear": gear, "scavenger_rank": level, "lightning_bias_rank": bias_rank})
        control = self.observe(d)
        self.check("stun_duration_without_rider_control", control["valid"] and not control["left_ms"], control)
        for rank, duration in enumerate((250, 500), 1):
            ok, got = self.orb("hwp_fs_scavenger_stun", 1)
            live = self.observe(d)
            custom = self.custom(self.probe(rolls=1), "hwp-ele-stun")
            if rank == 1:
                observed = 100 <= live["max_left_ms"] <= 250 and all(0 < x <= 250 for x in live["left_ms"])
            else:
                observed = 300 <= live["max_left_ms"] <= 3000 and all(0 < x <= 3000 for x in live["left_ms"])
            self.check(f"stunning_shock_rank_{rank}_natural_duration", ok and got == rank and live["valid"]
                       and custom == duration and observed,
                       {"orb": "hwp_fs_scavenger_stun", "rank": rank, "native_custom_duration_ms": custom,
                        "natural_firing_observations": live,
                        "scope": "Fixed3x10s holds, actual HP loss and naturally rolled lightning. Rank1 applications are shorter than the solo shot interval; rank2 can accumulate up to the3s cap."})
        self.clear_dummies()
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.stun()
    except Exception as exc:
        c.check("rider_duration_crashed", False, {"error": repr(exc)})
    c.out.update(ok=bool(c.rows) and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
