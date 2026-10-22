"""Behavioral overnight checks for the parked HoH1 ports.

These controlled ability cases use ordinary Skill.Activate through castat, at 1x,
against fresh real enemies. They do not imply natural run or co-op coverage.
Only the root run owner launches GameLab; this module just defines bot steps.
"""
from collections import deque
import math
import time

from gamelab.bots.plan_classesa import BRUTE, Checks as ClassChecks, dist


STUN = "tweak/buffs/status_effects.sval:stun_greater"
DUMMY = "gamelab/target_dummy_resist.unit"
DUMMY_FILTER = "target_dummy_resist"
QA_DUMMY = "gamelab/qa_class_target_dummy.unit"
QA_DUMMY_FILTER = "qa_class_target_dummy"
ACTIVE_CASES = {
    "shadow_strike": ("hwp_thief", "hwp_thief_assassin", "hwp_thief_shadow_strike", "leap", "stun"),
    "caltrops": ("hwp_thief", "hwp_thief_trickster", "hwp_thief_caltrops", "position", "slow"),
    "barbed_net": ("hwp_gladiator", "hwp_gladiator_retiarius", "hwp_gladiator_barbed_net", "position", "immobilize"),
    "whirl": ("hwp_gladiator", "hwp_gladiator_retiarius", "hwp_gladiator_whirl", "self", None),
    "crows": ("hwp_witch_hunter", "hwp_witch_hunter_inquisitor", "hwp_witch_hunter_crows", "position", "blindness"),
}


class Checks(ClassChecks):
    def actor(self, uid, filt="bandit_brute", radius=400):
        return next((a for a in self.gl("actorbuffs", radius, filt).get("actors", [])
                     if a["unit"] == uid), None)

    def tags(self, actor):
        records = (actor or {}).get("buffs", []) + [s for s in (actor or {}).get("stacks", [])
                                                    if s.get("count", 0) > 0]
        return sorted({tag for buff in records for tag in buff.get("tags", [])})

    @staticmethod
    def trident_lanes(terrain, ox=0, oy=0, front=26, back_neighbor=False, ray_distance=40, clearance_points=()):
        """Open feet, bodies and native head-height thrust rays, at grid precision."""
        rows, n, step = terrain.get("rows", []), terrain.get("size", 0), terrain.get("step", 8)
        center = n // 2

        def free(x, y):
            ix, iy = center + round((ox + x) / step), center + round((oy + y) / step)
            return 0 <= iy < len(rows) and 0 <= ix < len(rows[iy]) and rows[iy][ix] != "#"

        def body(x, y):
            return all(free(x + dx, y + dy) for dx in (-8, 0, 8) for dy in (-16, -8, 0))

        if not body(0, 0):
            return []
        for x, y, half_size in clearance_points:
            if not all(free(x + dx, y + dy) for dx in range(-half_size, half_size + 1, step)
                       for dy in range(-half_size, half_size + 1, step)):
                return []
        lanes = []
        for f in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for sign in (1, -1):
                side = (-f[0], -f[1]) if back_neighbor else (-f[1] * sign, f[0] * sign)
                perpendicular = (-f[1], f[0])
                if not body(f[0] * front, f[1] * front) or not body(side[0] * 40, side[1] * 40):
                    continue
                # MeleeSwing uses player y-PlayerCameraHeight (0 in pinned SDK).
                # Check all three rays and their full 40px reach, plus one grid cell.
                if all(free(f[0] * r + perpendicular[0] * w, f[1] * r + perpendicular[1] * w)
                       for r in range(0, ray_distance + 9, 4) for w in (-8, 0, 8)):
                    lanes.append((f, side))
        return lanes

    def to_trident_lane(self, front=26, back_neighbor=False, ray_distance=40, tag="trident", clearance_points=()):
        """Use shared native routes, then independently recertify the same footprint.

        The accepted class trident_lanes predicate, native ray width/distance,
        body/target footprints and clearance points remain unchanged. Native
        Pathfind/Pilot walking only selects a new real location; it cannot pass
        this geometry gate without a fresh complete fine grid and native rays.
        """
        from gamelab.bots.qa_specs_navigation import walk_trident_lane
        result = walk_trident_lane(self, front=front, back_neighbor=back_neighbor,
                                   ray_distance=ray_distance, tag=tag,
                                   clearance_points=clearance_points)
        # Callers keep their existing boolean geometry gate under this key.
        # Preserve native attempts before flag() replaces that structured value.
        geometry = self.out.get(tag + "_geometry")
        if isinstance(geometry, dict):
            self.out[tag + "_geometry_trace"] = geometry
        return result

    def trident(self):
        """Bounded fresh-input versus settled-input/direct-activation diagnostics.

        Retains all three trials of each setup, including misses. This isolates
        attack loading, input activation and geometry from moving fresh enemies.
        """
        if not self.new_char("hwp_gladiator", "QATrident") or not self.arena("trident"):
            return
        skills = self.gl("skills")
        stats = self.gl("benchstats")
        self.flag("trident_attack_loaded", any(s.get("id") == "hwp_attack_trident"
                                               for s in skills.get("skills", [])), str(skills))
        self.flag("trident_damage_available", stats.get("mhPhys", 0) > 0, str(stats))
        lane, note = self.to_trident_lane()
        self.flag("trident_open_floor", bool(lane), note)
        if not lane:
            return
        results = []
        setups = ("fresh_input", "settled_input", "settled_input_500", "settled_cast")
        for setup in setups:
            for trial in range(3):
                self.clear()
                f, side = lane
                points = [(f[0] * 26, f[1] * 26), (side[0] * 40, side[1] * 40)]
                cast = None
                if setup == "fresh_input":
                    _, targets = self.scene(points, aim=f, button="main", hold=350)
                    positions = targets
                else:
                    # Freeze in the spawn frame: a brute otherwise walks over
                    # twenty pixels before a second console command arrives.
                    before = {u["unit"] for u in self.brutes(600)}
                    px, py = self.me()
                    args = []
                    for dx, dy in points:
                        args += ["spawn", BRUTE, round(dx), round(dy), "+"]
                    args += ["buffnear", 300, "bandit_brute", STUN, 5000]
                    self.gl("multi", *args)
                    spawned = [u for u in self.brutes(600) if u["unit"] not in before]
                    targets = []
                    for dx, dy in points:
                        spawned.sort(key=lambda u: dist((u["x"], u["y"]), (px + dx, py + dy)))
                        targets.append(spawned.pop(0) if spawned else None)
                    time.sleep(0.5)
                    positions = [self.unit(t["unit"]) if t else None for t in targets]
                    if setup.startswith("settled_input"):
                        hold = 500 if setup == "settled_input_500" else 350
                        self.gl("input", hold, 0, 0, f[0], f[1], "main")
                    else:
                        cast, _ = self.scene(cast=("hwp_attack_trident", f[0] * 80, f[1] * 80),
                                             aim=f, hold=1200)
                time.sleep(0.8)
                after = [self.unit(t["unit"]) if t else None for t in targets]
                front_hit = bool(targets[0]) and (after[0] is None or after[0].get("hp", 1) < 0.9999)
                side_clear = bool(targets[1]) and after[1] is not None and after[1].get("hp") == 1.0
                row = {"setup": setup, "trial": trial, "direction": f, "before": positions,
                       "after": after, "front_hit": front_hit, "side_clear": side_clear,
                       "cast": cast, "player": self.me(), "floats": self.gl("floats")}
                results.append(row)
                self.notes.append("trident diagnostic: " + str(row))
                if setup == "settled_input" and trial == 0:
                    self.g.shot("trident-settled-targets")
        self.out["trident_trials"] = results
        for setup in setups:
            rows = [r for r in results if r["setup"] == setup]
            self.flag("trident_" + setup + "_hits", len(rows) == 3 and all(r["front_hit"] for r in rows),
                      str([r["front_hit"] for r in rows]))
            self.flag("trident_" + setup + "_narrow", len(rows) == 3 and all(r["side_clear"] for r in rows),
                      str([r["side_clear"] for r in rows]))
        self.to_town()

    def setup_mastery(self, cls, mastery, name):
        if not self.new_char(cls, name):
            return False
        self.hwp("levelup 20", 0.5)
        self.hwp("skillpoints 1000", 0.3)
        sub = self.gl("subclass", mastery)
        self.flag(name + "_mastery", sub.get("class") == mastery, str(sub))
        return sub.get("class") == mastery

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
        for rank in (0, 1, 5):
            if rank:
                learned = self.gl("skill", "hwp_gladiator_riposte", 1 if rank == 1 else 4)
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
        losses = []
        for rank in (1, 5):
            tag = f"{name}_r{rank}"
            learned = self.gl("skill", skill, rank if rank == 1 else 4)
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
            unit_path = QA_DUMMY if mode == "leap" else BRUTE
            unit_filter = QA_DUMMY_FILTER if mode == "leap" else "bandit_brute"
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
            if mode == "leap":
                initial = self.actor(target["unit"], unit_filter)
                self.flag(tag + "_target_hp", (initial or {}).get("hpMax") == 15000
                          and abs((initial or {}).get("hpExact", -1) - 15000) < 0.01, str(initial))
            # Immobilize holds a leap target without supplying the landing stun.
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
            loss = 1.0 - (after.get("hp", 1.0) if after else 0.0)
            losses.append(loss)
            buffs = self.actor(target["unit"], unit_filter)
            tags = self.tags(buffs)
            self.flag(tag + "_damage", cast.get("activated") and loss > 0.0001,
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
            self.clear()
        if len(losses) == 2:
            self.flag(name + "_damage_scales", losses[1] > losses[0],
                      f"fresh enemy hp lost, ranks1/5: {losses}; "
                      "a saturated comparison remains unverified")
        self.to_town()


def run(p, sections="shadow_strike", **_):
    c = Checks(p)
    for name in sections.split(","):
        try:
            if name in ACTIVE_CASES:
                c.active_case(name)
            else:
                getattr(c, name)()
        except Exception as exc:
            c.flag(name + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
