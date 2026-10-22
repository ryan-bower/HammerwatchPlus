"""HoH1 base active low/max effects through native casts, HP and units.

Knives/Gladius use ordinary bound buttons, with expiring noncrit fixtures to
keep rank comparisons controlled. Position casts use the existing explicit
castat fixture; they do not claim normal cursor targeting/cooldown coverage.
Grappling Hook has only one rank, already covered by the baseline movement test.
"""
import time

from gamelab.bots.qa_class_procs import Checks as ProcChecks
from gamelab.bots.qa_classes import QA_DUMMY, QA_DUMMY_FILTER
from gamelab.bots.qa_observe import collect


class Checks(ProcChecks):
    def targets(self, points):
        self.clear()
        self.gl("kill", 1200, QA_DUMMY_FILTER)
        replies = self.g.gl_multi([["spawn", QA_DUMMY, round(x), round(y)] for x, y in points]
                                  + [["actorbuffs", 300, QA_DUMMY_FILTER]])
        ids = [r["unit"] for r in replies if "unit" in r]
        actors = [a for r in replies for a in r.get("actors", []) if a.get("unit") in ids]
        valid = len(ids) == len(points) == len(actors) and all(a.get("hpMax") == 15000
                         and abs(a.get("hpExact", 0) - 15000) < 0.01 for a in actors)
        return actors if valid else None

    def snapshots(self, before):
        actors = self.gl("actorbuffs", 300, QA_DUMMY_FILTER).get("actors", [])
        ids = {a["unit"] for a in before}
        after = [a for a in actors if a.get("unit") in ids]
        valid = len(after) == len(before) and all(not a.get("dead") and a.get("hpExact", 0) > 0 for a in after)
        loss = sum(a["hpExact"] for a in before) - sum(a.get("hpExact", 0) for a in after) if valid else None
        return after, loss

    def normal_button(self, skill):
        rows = self.gl("skills").get("skills", [])
        entry = next((r for r in rows if r.get("id") == skill), {})
        button = entry.get("button")
        return button if button and sum(r.get("button") == button for r in rows) == 1 else None

    def raw_ready(self, skill, tag, timeout=20):
        """Observe native cooldown expiration; never reset or reduce it."""
        deadline, samples = time.monotonic()+timeout, []
        while time.monotonic() < deadline:
            current = next((s for s in self.gl("skills").get("skills", []) if s.get("id")==skill), {})
            samples.append(current)
            if isinstance(current.get("cd"),(int,float)) and current["cd"] <= 0:
                self.out[tag+"_cooldown_observations"] = samples
                self.flag(tag+"_cooldown_ready", True, str(current))
                return True
            time.sleep(.15)
        self.out[tag+"_cooldown_observations"] = samples
        self.flag(tag+"_cooldown_ready", False, str(samples))
        return False

    def projectile(self, key):
        knives = key == "knives"
        skill = "hwp_thief_knives" if knives else "hwp_gladiator_gladius"
        filt = "rog_throwing_knife" if knives else "whirling_axe"
        lane, note = self.to_trident_lane(front=72, back_neighbor=True, ray_distance=120, tag=key,
                                          clearance_points=() if knives else ((0, 0, 40),))
        self.flag(key + "_geometry", bool(lane), note)
        if not lane:
            return
        f = lane[0]
        rows, damage, passed = [], [], True
        for rank in (1, 5):
            tag = f"{key}_r{rank}"
            learned = self.learn(skill, rank, tag)
            self.clear()
            self.gl("kill", 1200, QA_DUMMY_FILTER)
            button = self.normal_button(skill)
            self.flag(tag + "_bound_button", bool(button))
            if not learned or not button:
                passed = False
                continue
            # Both native projectile effects retain this spell's WeaponInfo.
            # The main-hand stats supply Gladius damage, not its crit skill type.
            # skillcrit supports exactly one selected override per player.
            ids = [skill]
            fixtures = [self.gl("skillcrit", sid, 0) for sid in dict.fromkeys(ids)]
            fixture_ok = all(r.get("ok") and r.get("override_active") and r.get("crit_chance") == 0 and r.get("spell_crit_chance") == 0 for r in fixtures)
            try:
                self.gl("mana", 999)
                if not self.raw_ready(skill,tag+"_trajectory"):
                    passed = False
                    continue
                event, _ = self.track(1500 if knives else 4500, 600, filt,
                                     lambda: self.gl("input", 500, 0, 0, *f, button))
                tracks = (event or {}).get("tracks", [])
                count_ok = len(tracks) == (3 if rank == 1 else 5) if knives else len(tracks) == 1
                count_ok &= not bool((event or {}).get("truncated"))
                return_observation = None
                if not knives:
                    t = tracks[0] if tracks else {}
                    # The original required return-trajectory test is retained
                    # in classA. This new case proves damage; terrain beyond
                    # the verified near-target lane is not a new return oracle.
                    return_observation = t.get("dmax", 0) > 40 and t.get("dminafter", 1000) <= 30
                self.flag(tag + "_native_projectiles", bool(count_ok), str(event))
                points = [(f[0] * 72, f[1] * 72)] if knives else [(24, 0), (-24, 0), (0, 24), (0, -24)]
                before = self.targets(points)
                self.flag(tag + "_target_fixture", bool(before), str(before))
                if not before:
                    passed = False
                    continue
                self.gl("mana", 999)
                if not self.raw_ready(skill,tag+"_damage"):
                    passed = False
                    continue
                cast = self.gl("input", 500, 0, 0, *f, button)
                time.sleep(0.9 if knives else 4.2)
                after, loss = self.snapshots(before) if before else ([], None)
                hit = bool(fixture_ok and before and loss is not None and loss > 0)
                self.flag(tag + "_actual_damage", hit, str({"before": before, "after": after, "loss": loss}))
                passed &= bool(count_ok and hit)
                damage.append(loss)
                rows.append({"rank": rank, "noncrit_fixture": fixtures, "trajectory": event, "return_observed": return_observation,
                             "input": cast, "before": before, "after": after, "damage": loss})
            finally:
                restores = [self.gl("skillcrit", sid, "restore") for sid in dict.fromkeys(ids)]
                restored = all(r.get("ok") and not r.get("override_active") for r in restores)
                self.flag(tag + "_crit_restored", restored, str(restores))
                passed &= restored
        scaled = len(damage) == 2 and all(isinstance(x, (int, float)) for x in damage) and damage[1] > damage[0]
        self.flag(key + "_damage_scales", scaled, str(damage))
        self.flag(key + "_low_max", passed and scaled and len(rows) == 2)
        self.out[key + "_trials"] = rows

    def area(self, key):
        skill = {"smoke": "hwp_thief_smoke", "net": "hwp_gladiator_net", "ward": "hwp_witch_hunter_ward"}[key]
        required = {"smoke": {"blindness", "slow"}, "net": {"immobilize"}, "ward": {"vulnerability"}}[key]
        # Native QueryCircle includes the dummy's radius5 collider. A probe at
        # +64 (Smoke/Ward R56->72) or+48 (Net R40->56) is outside rank1 and
        # inside rank5 with margins on both sides. All targets share one clear lane.
        edge = 48 if key == "net" else 64
        lane, note = self.to_trident_lane(front=80 + edge, back_neighbor=True,
                                          ray_distance=80 + edge, tag=key)
        self.flag(key + "_geometry", bool(lane), note)
        if not lane:
            return
        f, outside = lane
        rows, damages, passed = [], [], True
        for rank in (1, 5):
            tag = f"{key}_r{rank}"
            learned = self.learn(skill, rank, tag)
            before = self.targets([(f[0] * 80, f[1] * 80), (f[0] * (80 + edge), f[1] * (80 + edge)),
                                   (outside[0] * 40, outside[1] * 40)])
            if not before:
                self.flag(tag + "_fixture", False)
                passed = False
                continue
            px, py = self.me()
            inside = min(before, key=lambda a: (a["x"] - px - f[0] * 80) ** 2 + (a["y"] - py - f[1] * 80) ** 2)
            probe = min(before, key=lambda a: (a["x"] - px - f[0] * (80 + edge)) ** 2 + (a["y"] - py - f[1] * (80 + edge)) ** 2)
            neighbor = next(a for a in before if a["unit"] not in (inside["unit"], probe["unit"]))
            if not self.raw_ready(skill,tag):
                passed = False
                continue
            self.gl("mana",999)
            cast, _ = self.scene(cast=(skill, f[0] * 80, f[1] * 80), aim=f)
            time.sleep(0.45)
            after, _ = self.snapshots(before)
            hit = next((a for a in after if a["unit"] == inside["unit"]), None)
            boundary = next((a for a in after if a["unit"] == probe["unit"]), None)
            away = next((a for a in after if a["unit"] == neighbor["unit"]), None)
            tags = set(self.tags(hit))
            applied = learned and cast.get("activated") and hit is not None and required <= tags
            untouched = away is not None and away.get("hpExact") == 15000 and not required.intersection(self.tags(away))
            loss = 15000 - hit.get("hpExact", 15000) if hit else None
            damage_ok = loss is not None and (loss > 0 if key == "ward" else abs(loss) < 0.001)
            boundary_ok = boundary is not None and (required <= set(self.tags(boundary)) if rank == 5
                           else not required.intersection(self.tags(boundary)))
            if key == "ward":
                boundary_ok &= boundary is not None and (boundary.get("hpExact", 15000) < 15000 if rank == 5
                                                         else boundary.get("hpExact") == 15000)
            self.flag(tag + "_effect", bool(applied and damage_ok), str({"cast": cast, "actor": hit, "expected_tags": sorted(required)}))
            self.flag(tag + "_outside_control", untouched, str(away))
            self.flag(tag + "_rank_radius_probe", bool(boundary_ok), str({"distance_from_center": edge, "actor": boundary}))
            passed &= bool(applied and damage_ok and untouched and boundary_ok)
            damages.append(loss)
            rows.append({"rank": rank, "before": before, "after": after, "cast": cast, "inside_damage": loss,
                         "scope": "controlled native position activation; center/outside controls and one collider-aware rank-discriminating radius point, not an exact boundary sweep"})
        if key == "ward":
            scaled = len(damages) == 2 and all(isinstance(x, (int, float)) for x in damages) and damages[1] > damages[0]
            self.flag("ward_damage_scales", scaled, str(damages))
            passed &= scaled
        self.flag(key + "_low_max", passed and len(rows) == 2)
        self.out[key + "_trials"] = rows

    def pyre(self):
        lane, note = self.to_trident_lane(front=50, back_neighbor=True, ray_distance=80,
                                          clearance_points=((0, 0, 32),), tag="pyre")
        self.flag("pyre_geometry", bool(lane), note)
        if not lane:
            return
        f = lane[0]
        rows, damage, passed = [], [], True
        for rank, hp in ((1, 200), (5, 600)):
            tag = f"pyre_r{rank}"
            learned = self.learn("hwp_witch_hunter_pyre", rank, tag)
            self.gl("kill", 1200, "witchhunter/units/pyre")
            before = self.targets([(f[0] * 50, f[1] * 50)])
            if not before:
                self.flag(tag + "_fixture", False)
                passed = False
                continue
            observer_tag = f"pyrehp{time.time_ns()}"
            owned = []
            def cast():
                self.gl("buffobserve", observer_tag, 11000, "-", "-", before[0]["unit"])
                activated, _ = self.scene(cast=("hwp_witch_hunter_pyre", f[0] * 80, f[1] * 80), aim=f)
                time.sleep(0.4)
                for unit in self.gl("near", 250, "witchhunter/units/pyre").get("units", []):
                    owned.append(self.gl("summonmove", unit["unit"]))
                return activated
            if not self.raw_ready("hwp_witch_hunter_pyre",tag):
                passed = False
                continue
            self.gl("mana",999)
            track, activated = self.track(11500, 500, "witchhunter/units/pyre", cast)
            observed = collect(self.g, observer_tag, 20)
            after, loss = self.snapshots(before)
            time.sleep(2)
            ended, later_loss = self.snapshots(before)
            tracks = (track or {}).get("tracks", [])
            life = tracks[0].get("t1", 0) - tracks[0].get("t0", 0) if len(tracks) == 1 else 0
            hp_ok = len(owned) == 1 and owned[0].get("ok") and owned[0].get("hpMax") == hp
            native_hp = [e.get("target_hpExact") for e in observed.get("events", []) if e.get("target_valid")]
            burns = bool(observed.get("usable") and len(set(native_hp)) >= 3 and loss is not None and loss > 0)
            expires = 7400 <= life <= 8800 and loss is not None and later_loss == loss
            ok = bool(learned and activated.get("activated") and hp_ok and burns and expires)
            self.flag(tag + "_hp_burn_expiry", ok, str({"owned": owned, "life": life, "loss": loss, "later_loss": later_loss}))
            rows.append({"rank": rank, "cast": activated, "owned": owned, "track": track, "native_hp": observed,
                         "before": before, "after": after, "after_expiry": ended, "damage": loss})
            damage.append(loss)
            passed &= ok
        scaled = len(damage) == 2 and all(isinstance(x, (int, float)) for x in damage) and damage[1] > damage[0]
        self.flag("pyre_damage_scales", scaled, str(damage))
        self.flag("pyre_low_max", passed and scaled and len(rows) == 2)
        self.out["pyre_trials"] = rows

    def family(self, key):
        cls = {"thief": "hwp_thief", "gladiator": "hwp_gladiator", "witchhunter": "hwp_witch_hunter"}[key]
        if not self.prepare(cls, None, "QABase" + key):
            return
        if key == "thief":
            self.projectile("knives")
            self.area("smoke")
        elif key == "gladiator":
            self.projectile("gladius")
            self.area("net")
        else:
            self.pyre()
            self.area("ward")
        self.to_town()


def run(p, family="thief", **_):
    c = Checks(p)
    try:
        c.family(family)
    except Exception as exc:
        c.flag(family + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
