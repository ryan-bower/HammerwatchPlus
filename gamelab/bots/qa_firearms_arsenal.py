"""Natural firing and resource checks for every built Firearms gun/tier/hand path.

This is a fixture measurement on a cleared floor, with god mode disabled. A fan
of overlapping real damageable targets covers the paired-shot/full-auto
spread. No random attempt is retried; observations for every configuration remain.
"""
import math
import time

from gamelab.bots.qa_firearms_ranks import Checks as Base


class Checks(Base):
    def loadout(self, main, off, quality):
        return self.fixture_loadout(main, off, quality)

    def target_fan(self, d, distance):
        self.clear_dummies()
        d, _ = self.clear_dir(d, distance + 20)
        angle = math.atan2(d[1], d[0])
        origin = self.pos()
        # The old45px/-16,0,+16 fan left12.53px center gaps between radius5
        # targets. A pistol also starts6px off-axis and converges at100px.
        # Keep the existing gun/spread behavior; close holes in the fixture.
        max_step = min(10.0, math.degrees(2 * math.asin(4.5 / distance)))
        intervals = math.ceil(40 / max_step)
        intervals += intervals % 2  # a real center target, with symmetric sides
        angles = [-20 + 40 * i / intervals for i in range(intervals + 1)]
        targets, expected = [], {}
        for degrees in angles:
            a = angle + math.radians(degrees)
            dx, dy = math.cos(a) * distance, math.sin(a) * distance
            target = self.dummy(dx, dy)
            targets.append(target)
            expected[target] = [origin[0] + round(dx, 1), origin[1] + round(dy, 1)]
        observed = {u.get("unit"): u for u in self.gl("near", 250, "target_dummy").get("units", [])}
        rays = [self.gl("rayhit", origin[0], origin[1], *expected[t]) for t in targets]
        geometry = {
            "origin": origin, "direction": d, "distance": distance, "angles_deg": angles,
            "target_radius": 5, "neighbor_chord": 2 * distance * math.sin(math.radians(40 / intervals) / 2),
            "expected_centers": expected, "actual_targets": [observed.get(t) for t in targets], "wall_tile_rays": rays,
            "sources": {"collider": "gamecode/sdk/hoh2/doodads/generic/target_dummy_breakable.unit:44",
                        "muzzle_convergence": "mods/firearms/players/hwp/firearms/attacks_firearms.sval:449"},
            "limit": "Rays ignore damage takers; retained actual target centers/HP and cleared fixture also guard setup."
        }
        geometry["valid"] = len(set(targets)) == len(targets) and all(
            t in observed and not observed[t].get("dead") and observed[t].get("hpMax") == 500
            and observed[t].get("hpExact") == 500
            and math.hypot(observed[t].get("x", 1e9) - expected[t][0],
                           observed[t].get("y", 1e9) - expected[t][1]) < 0.3
            for t in targets) and all(r.get("ok") and not r.get("wall") and not r.get("tile") for r in rays)
        hp = self.hps(targets)
        return d, targets, hp, geometry

    def fire_case(self, tag, main, off, quality, button, rounds, capacity, hold_ms,
                  gadget=None, distance=45):
        if self.selected is not None and tag not in self.selected:
            return
        self.executed.append(tag)
        eq, equip_replies = self.loadout(main, off, quality)
        d, targets, hp0, geometry = self.target_fan(self.direction, distance)
        self.top_up()
        maximum = self.clip_max()
        clip0 = self.clip()
        bar0 = self.bar()
        mana0 = bar0.get("mana", -1)
        mana_mul = self.gl("state").get("player", {}).get("manaCostMul", 1)
        stats = self.gl("benchstats")
        self.gl("input", hold_ms, 0, 0, d[0], d[1], button)
        lowest = mana0
        end = time.monotonic() + hold_ms / 1000 + 0.85
        while time.monotonic() < end:
            lowest = min(lowest, self.bar().get("mana", mana0))
            time.sleep(0.06)
        clip1 = self.clip()
        hp1 = self.hps(targets)
        loss = sum(max(0, hp0[x] - hp1[x]) for x in targets if x in hp0 and x in hp1)
        spent = clip0 - clip1
        drop = mana0 - lowest
        resource = spent == rounds and drop < 0.1
        if gadget == "launcher":
            resource = spent == 0 and 3.4 * mana_mul <= drop <= 4.1 * mana_mul
        elif gadget == "flamer":
            resource = spent == 0 and 8 * mana_mul <= drop <= 14 * mana_mul
        elif gadget == "auto":
            resource = 7 * stats.get("mhSpeed", 1) <= spent <= 13 * stats.get("mhSpeed", 1) and drop < 0.1
        self.check(tag, eq and geometry["valid"] and maximum == capacity and clip0 == capacity and resource and loss > 0,
                   {"main": main, "off": off, "quality": quality, "button": button,
                    "gadget": gadget, "hold_ms": hold_ms, "expected_capacity": capacity,
                    "capacity": maximum, "clip": [clip0, clip1], "rounds_spent": spent,
                    "expected_rounds": rounds, "mana_start": mana0, "lowest_mana": lowest,
                    "mana_drop": round(drop, 4), "mana_cost_mul": mana_mul, "stats": stats, "targets": targets,
                    "target_hp_before": hp0, "target_hp_after": hp1, "target_geometry": geometry,
                    "total_target_hp_fraction_lost": loss, "equip_replies": equip_replies})

    def arsenal(self, selected=None):
        if selected is not None and (not isinstance(selected, list) or not selected
                                     or len(set(selected)) != len(selected)
                                     or not all(isinstance(s, str) for s in selected)):
            raise ValueError("selected must be a nonempty list of unique case IDs")
        self.selected = set(selected) if selected is not None else None
        self.executed = []
        self.new_char("QAArsenal")
        if not self.enter_floor("qa_arsenal"):
            return
        self.check("god_disabled", self.ordinary_damage(), {"fixture": "cleared isolated combat floor"})
        # Test high-tier weapon behavior independently of the character's stat build.
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        self.g.console("dbg_cht_ignore_equipment_requirements 1")
        self.direction = self.open_dirs(130)[0]
        for tier in (1, 2, 3):
            for quality in ("common", "epic"):
                suffix = f"{tier}_{quality}"
                for kind in ("rifle", "flamerifle", "autorifle"):
                    main = f"hwp_{kind}_0{tier}"
                    self.fire_case(f"{kind}_primary_{suffix}", main, None, quality,
                                   "main", 3, 30, 320)
                    gadget = {"rifle": "launcher", "flamerifle": "flamer", "autorifle": "auto"}[kind]
                    self.fire_case(f"{kind}_secondary_{suffix}", main, None, quality,
                                   "off", 0, 30, 1200 if gadget == "flamer" else 1000 if gadget == "auto" else 720,
                                   gadget=gadget, distance=35 if gadget == "flamer" else 90 if gadget == "launcher" else 45)

                if quality == "epic":
                    # Native VerifyItem rejects handguns: their base items have no
                    # skill-epic. All nine rifle-family epic paths above are legal.
                    continue

                pistol = f"hwp_glock_mh_0{tier}"
                pistol_off = f"hwp_glock_oh_0{tier}"
                cannon = f"hwp_hcannon_mh_0{tier}"
                cannon_off = f"hwp_hcannon_oh_0{tier}"
                configurations = [
                    ("pistol_solo", pistol, None, 10, 1, 180),
                    ("cannon_solo", cannon, None, 6, 1, 180),
                    ("pistol_dual", pistol, pistol_off, 20, 2, 420),
                    ("cannon_dual", cannon, cannon_off, 12, 2, 720),
                    ("pistol_cannon", pistol, cannon_off, 16, 3, 320),
                    ("cannon_pistol", cannon, pistol_off, 16, 3, 320),
                ]
                for name, main, off, capacity, count, duration in configurations:
                    self.fire_case(f"{name}_primary_{suffix}", main, off, quality,
                                   "main", count, capacity, duration)
                    if off:
                        self.fire_case(f"{name}_secondary_{suffix}", main, off, quality,
                                       "off", 2, capacity, 180)
                for kind, off, capacity in (("pistol", pistol_off, 10), ("cannon", cannon_off, 6)):
                    self.fire_case(f"{kind}_offhand_only_{suffix}", "mainhand_longsword_01", off,
                                   quality, "off", 1, capacity, 180)
        expected = self.selected if self.selected is not None else set(self.executed)
        self.check("arsenal_case_manifest_complete", set(self.executed) == expected
                   and len(self.executed) == (len(expected) if self.selected is not None else 72),
                   {"requested": selected if selected is not None else "all72 built legal paths",
                    "executed": self.executed, "missing": sorted(expected - set(self.executed))})
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        self.clear_dummies()
        self.to_town()


def run(p, **kwargs):
    c = Checks(p)
    try:
        c.arsenal(**kwargs)
    except Exception as exc:
        c.check("arsenal_crashed", False, {"error": repr(exc)})
    c.out["ok"] = bool(c.rows) and all(row["runtime"] == "PASS" for row in c.rows)
    c.out["rows"] = c.rows
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
