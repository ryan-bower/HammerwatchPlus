"""Fixed trident target-state/collision diagnostics; no attack-data changes.

The required dummy controls prove a real attack path. Brute misses are retained
as observations, with native Shot intersections, rather than declared bugs.
"""
import time

from gamelab.bots.plan_classesa import BRUTE
from gamelab.bots.qa_classes import Checks as AbilityChecks, QA_DUMMY, QA_DUMMY_FILTER, STUN


IMMOBILIZE = "tweak/buffs/status_effects.sval:immobilize"


class Checks(AbilityChecks):
    def clear_targets(self):
        self.gl("multi", "kill", 600, "bandit_brute", "+", "kill", 600, QA_DUMMY_FILTER)
        time.sleep(0.15)

    def trial(self, kind, unit_path, freeze, distance, yoffset, activation, direction):
        self.clear_targets()
        tag = f"{kind}_{distance}_{yoffset}_{activation}"
        dx, dy = round(direction[0] * distance), round(direction[1] * distance + yoffset)
        mark = len(self.g.gl)
        args = ["spawn", unit_path, dx, dy]
        if freeze:
            args += ["+", "buffnear", 300, "bandit_brute", freeze, 10000]
        self.gl("multi", *args)
        spawned = next((r for r in self.g.gl[mark:] if r.get("name") == unit_path and "unit" in r), {})
        uid = spawned.get("unit")
        filt = QA_DUMMY_FILTER if kind == "dummy" else "bandit_brute"
        time.sleep(0.5)
        before = self.actor(uid, filt) if uid is not None else None
        rays = self.gl("meleerays", direction[0], direction[1])
        intersected = any(r.get("unit") == uid for r in rays.get("hits", []))
        mark = len(self.g.gl)
        if activation == "input":
            action = self.gl("input", 500, 0, 0, direction[0], direction[1], "main")
        else:
            self.gl("multi", "input", 1200, 0, 0, direction[0], direction[1], "+",
                    "castat", "hwp_attack_trident", direction[0], direction[1], "nocd")
            action = next((r for r in self.g.gl[mark:] if r.get("skill") == "hwp_attack_trident" and "activated" in r), {})
        time.sleep(0.55)
        after = self.actor(uid, filt) if uid is not None else None
        floats = self.gl("floats")
        damage = before["hpExact"] - after["hpExact"] if before and after else None
        setup_ok = (bool(before) and before.get("hpExact") is not None and before.get("hpMax", 0) > 0
                    and rays.get("ok") and rays.get("truncated") == 0 and action.get("ok"))
        if freeze:
            expected = "stun" if freeze == STUN else "immobilize"
            setup_ok = setup_ok and expected in self.tags(before)
        row = {"tag": tag, "kind": kind, "distance": distance, "world_y_offset": yoffset,
               "activation": activation, "direction": direction, "spawn": spawned, "before": before,
               "native_rays": rays, "target_intersected": intersected, "action": action,
               "after": after, "actual_hp_lost": damage, "hit": damage is not None and damage > 0,
               "floats": floats, "setup_ok": bool(setup_ok)}
        self.notes.append("target-state diagnostic: " + str(row))
        return row

    def trident(self):
        if not self.new_char("hwp_gladiator", "QATridentStates") or not self.arena("trident_states"):
            return
        lane, note = self.to_trident_lane()
        self.flag("target_states_geometry", bool(lane), note)
        if not lane:
            return
        direction, _ = lane
        rows = []
        states = (("dummy", QA_DUMMY, None), ("stun", BRUTE, STUN), ("immobilize", BRUTE, IMMOBILIZE))
        for kind, path, freeze in states:
            for distance in (16, 26, 36):
                for offset in (0, 12):
                    rows.append(self.trial(kind, path, freeze, distance, offset, "input", direction))
            for offset in (0, 12):
                rows.append(self.trial(kind, path, freeze, 26, offset, "cast", direction))
        controls = [r for r in rows if r["kind"] == "dummy" and r["distance"] == 26 and r["world_y_offset"] == 0]
        self.flag("trident_dummy_control", len(controls) == 2 and all(r["hit"] for r in controls), str(controls))
        self.flag("target_states_complete", len(rows) == 24 and all(r["setup_ok"] for r in rows),
                  f"{len(rows)} fixed observations; misses remain in full result and raw gl trace")
        self.out["target_state_observations"] = rows
        self.out["target_state_summary"] = [{"tag": r["tag"], "intersection": r["target_intersected"],
                                             "hit": r["hit"], "damage": r["actual_hp_lost"]} for r in rows]
        self.clear_targets()
        self.to_town()


def run(p, **_):
    c = Checks(p)
    try:
        c.trident()
    except Exception as exc:
        c.flag("target_states_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
