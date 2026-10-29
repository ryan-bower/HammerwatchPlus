"""The HoH1 Forsaken Tower (mission hwp_forsaken_tower_hoh1, mods/campaign README, the
"HoH1 tower" section): load each floor with `gl mission` and check it.

Per floor index (kwarg `floors`, "0,1,2" or "all"):
- the mission started and the level phase is "mission";
- no script exception, failed resource open or missing unit/prefab in the log since the
  start (the lines are kept in the notes; the base game's own load noise, NOISE, aside);
- a generated floor logged `HoH1 floor generated: N prefabs, start at X,Y` with N > 0, and
  the player stands within 200 px of that start;
- the player is spawned and alive; enemies (CompositeActorBehavior units) within 4000 px
  are counted (`actors`) and HoH1 units are in the scene around the player (`near`);
- a screenshot `floor-<index>-<id>`.
The result's `floors` holds what each floor reported.
"""
import re
import time

from gamelab.bots.plan_checks import Checks as Base

MISSION = "hwp_forsaken_tower_hoh1"
BAD = re.compile(r"Script exception|SValue param error|\[ERR\]|Failed to open|ERROR|[Cc]ould not find|[Mm]issing (unit|prefab)|Couldn't find")


# the base game logs these on every level load, with or without mods (any plan-* run)
NOISE = re.compile(r"Widget type of name '\w+' not registered|widget without an AddChild function"
                   r"|missing string 'description' \(file: tweak/pets\.sval\)|scripts/PetDef\.as\" line 17"
                   r"|Lobby::SetJoinable")


class Checks(Base):
    def floor_ids(self):
        r = self.gl("itc-mission", MISSION)
        return [lv.get("id", "?") for lv in r.get("levels") or []]

    def floor(self, i, fid):
        tag = f"floor{i}_{fid}"
        mark = len(self.g.read_log())
        r = self.gl("mission", MISSION, i, timeout=30)
        self.flag(tag + "_started", r.get("ok", False), f"{r}")
        ok = self.wait_phase("mission", 240)
        time.sleep(4)
        st = self.gl("state")
        p = st.get("player") or {}
        log = self.g.read_log()[mark:]
        bad = [ln for ln in log.splitlines() if BAD.search(ln) and not NOISE.search(ln)]
        rep = {"id": fid, "level": st.get("level", ""), "phase": st.get("phase"), "bad": bad[:12], "nbad": len(bad)}
        self.flag(tag + "_loaded", ok, f"phase {st.get('phase')} level {st.get('level')!r}")
        self.flag(tag + "_clean_log", not bad, f"{len(bad)} lines: {bad[:6]}")
        gen = re.findall(r"HoH1 floor generated: (\d+) prefabs, start at (-?[\d.]+),(-?[\d.]+)", log)
        if gen:
            n, sx, sy = int(gen[-1][0]), float(gen[-1][1]), float(gen[-1][2])
            px, py = float(p.get("x", 0)), float(p.get("y", 0))
            d = ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5
            rep.update(prefabs=n, start=[sx, sy], startDist=round(d))
            self.flag(tag + "_prefabs", n > 0, f"{n} prefabs")
            self.flag(tag + "_at_start", d < 200, f"player {px:.0f},{py:.0f} start {sx:.0f},{sy:.0f}")
        elif "gen" in fid or re.search(r"_\d$", fid) and not fid.startswith("battlements"):
            self.flag(tag + "_generated", False, "no 'HoH1 floor generated' line")
        self.flag(tag + "_player_alive", p.get("spawned") and not p.get("dead"), f"{p.get('hp')} at {p.get('x')},{p.get('y')}")
        a = self.gl("actors", 4000)
        acts = a.get("actors") or a.get("units") or []
        rep["enemies"] = len(acts)
        rep["enemyTypes"] = sorted({str(u.get("name") or "?").rsplit("/", 1)[-1] for u in acts})[:20]
        n = self.gl("near", 600)
        units = n.get("units") or []
        rep["near"] = len(units)
        rep["hoh1Units"] = sum(1 for u in units if "hoh1/" in str(u.get("name") or ""))
        self.out.setdefault("floors", []).append(rep)
        self.g.shot(f"floor-{i:02d}-{fid}")


def run(p, floors="all"):
    c = Checks(p)
    ids = c.floor_ids()
    c.flag("mission_found", bool(ids), f"{ids}")
    want = range(len(ids)) if floors == "all" else [int(x) for x in str(floors).split(",") if x.strip()]
    for i in want:
        if i >= len(ids):
            c.flag(f"floor{i}_exists", False, f"{len(ids)} floors")
            continue
        try:
            c.floor(i, ids[i])
        except Exception as e:  # one floor's failed read must not hide the rest
            c.flag(f"floor{i}_raised", False, repr(e))
    c.out["ok"] = all(v for k, v in c.out.items() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
