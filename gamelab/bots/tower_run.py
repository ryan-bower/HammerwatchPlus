"""A playthrough of the HoH1 Forsaken Tower (mission hwp_forsaken_tower_hoh1, mods/campaign
README, "HoH1 tower"): the first floor loaded with `gl mission`, every later floor reached
only through the floor's own exit, to the end of the tower.

On each floor (god mode on; the character is the fixture's, carried floor to floor):
- arrival: the level phase "mission", the player alive, what the floor holds (enemies,
  world scripts by type, chests and doors, pickups, traps), a screenshot;
- enemies act: the enemies near the player (or near the nearest enemy, the player put beside
  it) move or cast within a few seconds;
- a tour (not on boss floors): the player is put on every enabled area trigger, tripwire and
  trap shooter in turn (rooms spawn their groups, tripwires fire), the enemies around killed by
  the player as it goes; the shooters' trigger counts and the danger areas' scenes are then
  compared with arrival: the traps that fired;
- every enemy killed by the player (the drops land, rooms that count deaths open), the
  pickups collected by walking onto them, keys and gold read back from the record;
- chests and doors used (`itc-use`, the Use key's call): opened, or refused for a missing key;
- every enabled UseTrigger (levers, buttons, books) used, except the exit's own and the town
  shortcuts' (HoH2's LevelExit goes back to town); wells, shrines and imps used;
- a boss floor runs its fight as tower_bosses does (RECIPES' start steps), each boss killed by
  the player until HoH1's SetBossKilled logs;
- the exit: a hand-made level's from the level file (tower_bosses.Level.exit_use), a generated
  floor's found by pairing the floor's UseTriggers with its HoH1LevelExitNext the way an exit
  prefab lays them out (exit_layouts, read from the imported prefabs). The player is put in
  the stairs' area (its AllPlayersAreaTrigger switches the UseTrigger on) and uses it, and the
  next floor loads;
- the log stays clean (the base game's load noise aside), and the character keeps its level
  and experience from floor to floor.
After the last floor's boss, where the run goes is noted. The result's `floors` holds what each
floor reported; each run_* flag lists the floors that failed it.
"""
import re
import time
import xml.etree.ElementTree as ET

from gamelab.bots.tower_bosses import Checks as Base, EXITS, LEVELS, RECIPES, Level, _val, _xy, level_name
from gamelab.bots.tower_floors import MISSION

PREFABS = LEVELS.parent / "prefabs"
FAR = 20000
TOUR_CAP = 48        # points visited per floor
USE_CAP = 40         # UseTriggers, chests, doors used per floor
PICKUP_CAP = 64      # pickups walked onto per sweep
COUNT_TYPES = ("UseTrigger", "AreaTrigger", "AllPlayersAreaTrigger", "AreaRayTrigger", "ProjectileShooter",
               "SecretFound", "ShopArea", "Well", "Shrine", "Imp", "RandomLoot", "Teleport", "HoH1LevelExitNext",
               "LevelExit", "SpawnEnemyGroup", "DangerArea")
USABLE_SCRIPTS = ("Well", "Shrine", "Imp")
PICKUP_BEHAVIORS = ("Pickup", "HoH1Item")   # Pickup, MaterialPickup, UnitPickup, TimedPickup


def exit_layouts():
    """[((exit - use), (area - use), prefab)] for every UseTrigger that runs a HoH1LevelExitNext
    in an imported prefab: where a generated floor's stairs put the exit script and the area
    that switches the UseTrigger on, relative to the UseTrigger."""
    out = []
    for f in sorted(PREFABS.rglob("*.pfb")):
        text = f.read_text(encoding="utf-8")
        if "HoH1LevelExitNext" not in text:
            continue
        root = ET.fromstring(re.sub(r"^<!--.*?-->", "", text, flags=re.S))
        top = {c.get("name"): c for c in root}
        scripts, shapes = {}, {}
        for s in top.get("scripts", []):
            v = [_val(c) for c in s]
            ex = v[-1] if isinstance(v[-1], list) else []
            scripts[v[1]] = {"type": v[0], "pos": _xy(v[2]), "ex": ex[0::2],
                             "params": next((x for x in v if isinstance(x, dict)), {})}
        for group in top.get("units", []):
            if group.get("name", "").startswith(":Physics"):
                for u in group:
                    uv = [_val(c) for c in u]
                    shapes[uv[1]] = _xy(uv[0])
        for s in scripts.values():
            areas = s["params"].get("Areas") or []
            if s["type"] != "UseTrigger" or not areas or areas[0] not in shapes:
                continue
            for t in s["ex"]:
                if scripts.get(t, {}).get("type") == "HoH1LevelExitNext":
                    (ux, uy), (ex_, ey), (ax, ay) = s["pos"], scripts[t]["pos"], shapes[areas[0]]
                    out.append(((ex_ - ux, ey - uy), (ax - ux, ay - uy), f.relative_to(PREFABS).as_posix()))
    return out


AREA_TYPES = ("AreaTrigger", "AllPlayersAreaTrigger", "AreaRayTrigger")
CHECK_SIBLINGS = 4   # a prefab instance is told apart by this many of its other scripts


def _prefab_scripts(f):
    root = ET.fromstring(re.sub(r"^<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S))
    top = {c.get("name"): c for c in root}
    scripts, shapes = [], {}
    for s in top.get("scripts", []):
        v = [_val(c) for c in s]
        scripts.append({"type": v[0], "id": v[1], "pos": _xy(v[2]),
                        "params": next((x for x in v if isinstance(x, dict)), {})})
    for group in top.get("units", []):
        if group.get("name", "").startswith(":Physics"):
            for u in group:
                uv = [_val(c) for c in u]
                shapes[uv[1]] = _xy(uv[0])
    return scripts, shapes


def prefab_areas():
    """[(trigger type, trigger position, [area centres], [(type, position) of the prefab's other
    scripts], prefab)] for every area trigger in an imported prefab whose areas aren't on the
    script: HoH1's editor puts an area trigger's script anywhere (the Vampire's cross room keeps
    its AreaTrigger 300 px from its area), so a bot standing on the script trips nothing"""
    out = []
    for f in sorted(PREFABS.rglob("*.pfb")):
        text = f.read_text(encoding="utf-8")
        if not any(f"<string>{t}</string>" in text for t in AREA_TYPES):
            continue
        scripts, shapes = _prefab_scripts(f)
        for s in scripts:
            if s["type"] not in AREA_TYPES:
                continue
            areas = [shapes[a] for a in s["params"].get("Areas") or [] if a in shapes]
            if not areas or all(dist(a, s["pos"]) < 24 for a in areas):
                continue
            sib = [(o["type"], o["pos"]) for o in scripts if o is not s][:CHECK_SIBLINGS]
            if sib:
                out.append((s["type"], s["pos"], areas, sib, f.relative_to(PREFABS).as_posix()))
    return out


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def short(name):
    return str(name or "?").rsplit("/", 1)[-1]


class Checks(Base):
    def ws(self, kind):
        return self.gl("ws", kind).get("scripts") or []

    def ws_at(self, kind, pos):
        """a world script of that type at pos (this floor's, cached)"""
        if kind not in self._ws:
            self._ws[kind] = [(s["x"], s["y"]) for s in self.ws(kind)]
        return any(abs(x - pos[0]) < 1 and abs(y - pos[1]) < 1 for x, y in self._ws[kind])

    def trigger_areas(self, kind, s, name):
        """where to stand to trip an area trigger: its areas' centres (the level file's, or the
        prefab instance's it was spawned with), else its own position"""
        if name and (LEVELS / f"{name}.lvl").is_file():
            lv = self._levels.setdefault(name, Level(name))
            sc = lv.scripts.get(s.get("id"))
            if sc:
                got = [lv.shapes[a] for a in sc["params"].get("Areas") or [] if a in lv.shapes]
                if got:
                    return got
        for t, spos, areas, sib, _ in self.area_layouts:
            if t != kind:
                continue
            ox, oy = s["x"] - spos[0], s["y"] - spos[1]
            if all(self.ws_at(k, (ox + x, oy + y)) for k, (x, y) in sib):
                return [(ox + x, oy + y) for x, y in areas]
        return [(s["x"], s["y"])]

    def actors(self, r=FAR):
        # a trap glyph is an actor the archives can't have killed: the traps probe counts it instead;
        # an ally is no enemy (the dragon floor's iceblocks are on the player's team, cover from the breath)
        return [a for a in self.gl("actors", r).get("actors") or [] if not a.get("dead") and not a.get("ally")
                and "/trap" not in str(a.get("name") or "")]

    def record(self):
        """the character's level and experience, keys and run materials"""
        r = self.gl("run")
        p = self.gl("state").get("player") or {}
        return {"level": p.get("level"), "xp": p.get("xp"), "keys": r.get("keys"),
                "materials": r.get("materials")}

    def dealer(self):
        """HoH1's gambler window, if a use opened it (HoH1/Interfaces.as): up to two trinkets bet
        and rolled, as a player does, then closed; what it listed and what it gave"""
        w = self.gl("itc-host")
        if w.get("top") != "HoH1ItemDealer":
            return None
        d = {"listed": w.get("items"), "before": len(w.get("trinkets") or [])}
        if w.get("items"):
            c = self.gl("itc-host", "check", min(2, w["items"]))
            d["chances"] = c.get("chances")
            g = self.gl("itc-host", "func", "gamble")
            d.update(final=g.get("final"), after=len(g.get("trinkets") or []), bet=c.get("itemsChecked"))
        self.gl("itc-host", "func", "close")
        d["closed"] = "HoH1ItemDealer" not in (self.gl("itc-host").get("hosts") or [])
        return d

    def end_window(self, rep):
        """the last floor: HoH1's end window after Thundersnow (HoH1EndOfGame), its CONTINUE
        ending the mission as won, back to town"""
        end, w = time.time() + 20, {}
        while time.time() < end and w.get("top") != "HoH1EndOfGame":
            w = self.gl("itc-host")
            time.sleep(0.5)
        self.g.shot("run-end-window")
        rep["endWindow"] = {"top": w.get("top"), "texts": (w.get("texts") or [])[:3]}
        self.gl("itc-host", "func", "town")
        rep["endTown"] = self.wait_phase("town", 120)

    def tp(self, x, y, wait=0.35):
        self.gl("teleport", round(x, 1), round(y, 1))
        time.sleep(wait)

    def dismiss(self):
        """an open dialog answered as the player does (a shrine's buff shows one and pauses the
        game: Shrine.Use, ShowDialog "a" + PauseGame); the window names that were open"""
        seen = []
        for _ in range(4):
            w = self.gl("state").get("window") or ""
            if not w:
                break
            seen.append(w)
            r = self.gl("pressfunc", "a")
            if not r.get("ok"):
                self.gl("func", "a")
            time.sleep(0.5)
        return seen

    def kill_near(self, r=400):
        return self.gl("kill", r, "hoh1/actors/", "me")

    # --- enemies
    def activity(self, units, wait=2.5):
        """of the enemies in units (an `actors` list), how many moved, cast or were moving"""
        before = {u["unit"]: u for u in units}
        time.sleep(wait)
        after = {u["unit"]: u for u in self.actors(1200)}
        act = 0
        for k, u in before.items():
            v = after.get(k)
            if v is None:
                continue
            if v.get("casting") or v.get("moving") or abs(v["x"] - u["x"]) + abs(v["y"] - u["y"]) > 4:
                act += 1
        return act

    def clear(self, rounds=4):
        killed = []
        for _ in range(rounds):
            if not self.actors():
                break
            k = self.gl("kill", FAR, "hoh1/actors/", "me")
            killed += [short(n) for n in k.get("names") or []]
            time.sleep(1.5)
        return killed, self.actors()

    def collect(self):
        """walk onto the pickups, nearest first"""
        got, seen = 0, set()
        for _ in range(3):
            n = self.gl("near", FAR).get("units") or []
            picks = [u for u in n if any(b in str(u.get("behavior") or "") for b in PICKUP_BEHAVIORS)
                     and u.get("unit") not in seen]
            if not picks:
                break
            for u in picks[:PICKUP_CAP]:
                seen.add(u.get("unit"))
                self.tp(u["x"], u["y"], 0.15)
                got += 1
        return got

    # --- the exit
    def find_exit(self, name):
        """(UseTrigger id, [area centres], exit script position, how it was found) or None. Several
        exit prefabs put the exit script at the same offset from the UseTrigger but the area
        elsewhere, so a generated floor's exit gets each such prefab's area, tried in turn"""
        if name and (LEVELS / f"{name}.lvl").is_file():
            lv = Level(name)
            e = lv.exit_use()
            if e:
                ex = lv.exit_script(e[0])
                return e[0], [e[1]], lv.scripts[ex]["pos"], "level"
        uses = [u for u in self.ws("UseTrigger") if "id" in u]
        for ex in self.ws("HoH1LevelExitNext"):
            for u in uses:
                fits = [((u["x"] + ax, u["y"] + ay), pfb) for (dx, dy), (ax, ay), pfb in self.layouts
                        if abs(ex["x"] - u["x"] - dx) < 2 and abs(ex["y"] - u["y"] - dy) < 2]
                if fits:
                    return u["id"], [a for a, _ in fits], (ex["x"], ex["y"]), ",".join(f for _, f in fits)
        return None

    def exit_on(self, pos, sid):
        """the exit script at pos and its UseTrigger sid both on (a generated floor's stairs switch
        the exit script on from their area; a boss level switches the UseTrigger on after the fight)"""
        return (any(s.get("e") for k in EXITS for s in self.ws(k) if dist((s["x"], s["y"]), pos) < 1)
                and any(u.get("e") for u in self.ws("UseTrigger") if u.get("id") == sid))

    def take_exit(self, rep, name):
        e = self.find_exit(name)
        rep["exit"] = e and {"id": e[0], "area": e[1], "how": e[3]}
        if not e:
            return False
        # the stairs' UseTrigger is always on: its area's AllPlayersAreaTrigger switches the exit
        # script itself on (a ToggleScripts), and off again when the player leaves
        sid, areas, pos, _ = e
        rep["dialogsBeforeExit"] = self.dismiss()
        before = self.gl("state").get("level")
        for area in areas:
            self.tp(*area, 1.0)
            end = time.time() + (15 if len(areas) == 1 else 4)
            while time.time() < end and not self.exit_on(pos, sid):
                time.sleep(0.5)
            if self.exit_on(pos, sid):
                rep["exitArea"] = area
                break
        rep["exitOpen"] = self.exit_on(pos, sid)
        if not rep["exitOpen"]:
            # what the exit's room holds (a chambers exit is the Vampire's challenge room)
            dbg = {}
            for k in ("UseTrigger", "AreaTrigger", "AllPlayersAreaTrigger", "Variable", "TimerTrigger", "Teleport",
                      "GlobalEventTrigger", "CheckVariables", "UnitDestroyedTrigger", "SpawnUnitWithEffect", "CheckFlag"):
                near = [s for s in self.ws(k) if dist((s["x"], s["y"]), pos) < 900]
                if near:
                    dbg[k] = near[:12]
            dbg["actors"] = [(short(a.get("name")), round(a["x"]), round(a["y"])) for a in self.actors() if dist((a["x"], a["y"]), pos) < 900][:12]
            rep["exitDebug"] = dbg
        emark = len(self.g.read_log())
        u = self.gl("itc-use", f"#{sid}", 3000)
        rep["exitUse"] = {k: u.get(k) for k in ("canUse", "used")}
        booted = self.wait_boot(emark, 90)
        self.wait_phase("mission", 90)
        time.sleep(3)
        after = self.gl("state")
        rep["next"] = {"booted": booted, "phase": after.get("phase"), "level": after.get("level"), "before": before}
        return bool(booted) and after.get("phase") == "mission"

    # --- a floor
    def floor(self, n, fid, name):
        self._ws = {}
        st = self.gl("state")
        p = st.get("player") or {}
        rep = {"n": n, "id": fid, "name": name, "level": st.get("level"), "phase": st.get("phase"),
               "alive": bool(p.get("spawned")) and not p.get("dead")}
        mark = self.mark
        self.god_on()
        rep["record"] = self.record()
        rep["scripts"] = {k: len(self.ws(k)) for k in COUNT_TYPES}
        acts = self.actors()
        rep["enemies"] = len(acts)
        rep["enemyTypes"] = sorted({short(a.get("name")) for a in acts})[:30]
        self.g.shot(f"run-{n:02d}-{fid}-arrive")
        # enemies act: around the player, else beside the nearest enemy
        near = self.actors(900)
        rep["active"] = self.activity(near) if near else 0
        if acts and not rep["active"]:
            # beside the nearest enemy of each kind in turn (a ballista at rest neither moves nor casts)
            px, py = self.pos()
            kinds = {}
            for a in sorted(acts, key=lambda a: dist((a["x"], a["y"]), (px, py))):
                kinds.setdefault(short(a.get("name")), a)
            for a in list(kinds.values())[:4]:
                self.tp(a["x"] - 60, a["y"])
                rep["active"] = self.activity(self.actors(900), 4)
                if rep["active"]:
                    break
        shooters0 = {(round(s["x"]), round(s["y"])): s["t"] for s in self.ws("ProjectileShooter")}
        traps0 = self.gl("traps", FAR)
        areas0 = {a.get("unit"): str(a.get("scenes") or a.get("scene")) for a in traps0.get("areas") or []}
        rep["traps"] = {"shooters": len(shooters0), "areas": len(areas0), "actors": len(traps0.get("actors") or [])}
        if name in RECIPES:
            self.boss(rep, name)
        else:
            self.tour(rep)
        # the traps that fired
        shooters1 = {(round(s["x"]), round(s["y"])): s["t"] for s in self.ws("ProjectileShooter")}
        rep["traps"]["shotsFired"] = sum(1 for k, t in shooters1.items() if t > shooters0.get(k, t))
        traps1 = self.gl("traps", FAR)
        rep["traps"]["areasToggled"] = sum(1 for a in traps1.get("areas") or []
                                           if a.get("unit") in areas0 and str(a.get("scenes") or a.get("scene")) != areas0[a.get("unit")])
        rep["traps"]["rays"] = len(traps1.get("rays") or []) + (rep.get("tour") or {}).get("raysSeen", 0)
        # every enemy down, the drops collected, the floor's things used
        killed, left = self.clear()
        rep["killed"], rep["left"] = len(killed), [short(a.get("name")) for a in left][:10]
        rep["behaviors"] = sorted({str(u.get("behavior") or "") for u in self.gl("near", FAR).get("units") or []})[:40]
        rep["pickups"] = self.collect()
        self.use_things(rep, name)
        rep["pickups"] += self.collect()
        traps2 = self.gl("traps", FAR)
        rep["traps"]["areasToggledByUse"] = sum(1 for a in traps2.get("areas") or []
                                                if a.get("unit") in areas0 and str(a.get("scenes") or a.get("scene")) != areas0[a.get("unit")])
        rep["traps"]["raysByUse"] = rep["use"]["rays"] + len(traps2.get("rays") or [])
        rep["recordAfter"] = self.record()
        self.g.shot(f"run-{n:02d}-{fid}-cleared")
        bad = self.bad_lines(mark)
        rep["bad"], rep["nbad"] = bad[:12], len(bad)
        return rep

    def tour(self, rep):
        pts = []
        for k in AREA_TYPES:
            for s in self.ws(k):
                if s.get("e"):
                    pts += self.trigger_areas(k, s, rep.get("name"))
        pts += [(s["x"], s["y"]) for s in self.ws("ProjectileShooter")]
        avoid = [(s["x"], s["y"]) for k in ("LevelExit", "HoH1LevelExitNext") for s in self.ws(k)]
        pts = [p for p in pts if all(dist(p, a) > 220 for a in avoid)]
        rays = 0
        for x, y in pts[:TOUR_CAP]:
            self.tp(x, y, 0.5)
            rays += self.rays()
            self.kill_near(300)
            rays += self.rays()
        rep["tour"] = {"points": len(pts), "visited": min(len(pts), TOUR_CAP), "raysSeen": rays}

    def boss(self, rep, name):
        number, files, steps = RECIPES[name]
        lv = Level(name)
        rep["bossStart"] = [str(self.step(lv, s))[:120] for s in steps]
        found = self.wait_boss(files, 12)
        if len(found) < len(files):
            # HoH1's chambers: a vampire cross picked up on the floors before turns the boss
            # room's ActivateBoss area off (boss_chambers CheckFlag vampire_cross1-4); the
            # vampire wakes once the crosses are placed on the altars (the safe areas'
            # UseTriggers count "crosses" down). A player places them: so does the bot.
            ids = [u["id"] for u in self.ws("UseTrigger") if u.get("e") and "id" in u and u["id"] != (self.find_exit(name) or [None])[0]]
            rep["bossAltars"] = [(i, self.gl("itc-use", f"#{i}", FAR).get("used")) for i in ids[:USE_CAP]]
            found = self.wait_boss(files, 30)
        rep["bossSpawned"] = len(found) >= len(files)
        time.sleep(6)
        bb = self.gl("bossbars")
        rep["bossbar"] = {"shown": bb.get("shown"), "title": bb.get("title")}
        kmark = len(self.g.read_log())
        line = f"HoH1 boss {number} killed"
        rounds = 0
        while rounds < 3 and line not in self.g.read_log()[kmark:]:
            rounds += 1
            for f in files:
                self.gl("kill", 4000, "/" + f.rsplit("/", 1)[-1], "me")
                time.sleep(2.5)
            end = time.time() + 8
            while time.time() < end and line not in self.g.read_log()[kmark:]:
                time.sleep(0.5)
        rep["bossKilled"] = line in self.g.read_log()[kmark:]
        self.g.shot(f"run-boss-{name}")

    def wait_boss(self, files, seconds):
        found, end = [], time.time() + seconds
        while time.time() < end and len(found) < len(files):
            time.sleep(1)
            found = self.boss_units(files)
        return found

    def rays(self):
        """trap shots in flight around the player"""
        return len(self.gl("traps", 600).get("rays") or [])

    def use_things(self, rep, name):
        avoid = [(s["x"], s["y"]) for s in self.ws("LevelExit")]
        # every UseTrigger that runs an exit (a floor can hold a hidden second one): not used here
        exit_ids = {u["id"] for ex in self.ws("HoH1LevelExitNext") for u in self.ws("UseTrigger") if "id" in u
                    for (dx, dy), _, _ in self.layouts if abs(ex["x"] - u["x"] - dx) < 2 and abs(ex["y"] - u["y"] - dy) < 2}
        e = self.find_exit(name)
        if e:
            exit_ids.add(e[0])
        res = {"chests": [], "doors": [], "uses": [], "usables": [], "rays": 0}
        # chests first (keys come out of some), doors after
        for kind, beh in (("chests", "HoH1Chest"), ("doors", "HoH1Door")):
            units = [u for u in self.gl("near", FAR, beh).get("units") or [] if beh in str(u.get("behavior") or "")]
            for u in units[:USE_CAP]:
                self.tp(u["x"], u["y"] + 20, 0.3)
                r = self.gl("itc-use", f"#{u['unit']}", 400)
                time.sleep(0.3)
                res[kind].append({"unit": u["unit"], "name": short(u.get("name")), "canUse": r.get("canUse"), "used": r.get("used"),
                                  "dialog": self.dismiss()})
                res["rays"] += self.rays()
            if kind == "chests":
                self.collect()
        # levers, buttons, books: every enabled UseTrigger but the exit's and the shortcuts'
        for s in [s for s in self.ws("UseTrigger") if s.get("e") and "id" in s and s["id"] not in exit_ids
                  and all(dist((s["x"], s["y"]), a) > 220 for a in avoid)][:USE_CAP]:
            before = self.gl("state").get("level")
            r = self.gl("itc-use", f"#{s['id']}", FAR)
            time.sleep(0.4)
            res["uses"].append({"id": s["id"], "c": s.get("c"), "t": s.get("t"), "canUse": r.get("canUse"), "used": r.get("used"),
                                "dialog": self.dismiss()})
            res["rays"] += self.rays()
            if not r.get("canUse"):
                # still on? (HoH1's levers switch each other off: a use before this one may have)
                now = [u for u in self.ws("UseTrigger") if u.get("id") == s["id"]]
                res["uses"][-1]["eNow"] = bool(now and now[0].get("e"))
            if s["id"] not in self.dealt:
                d = self.dealer()
                if d:
                    self.dealt.add(s["id"])
                    res["uses"][-1]["dealer"] = d
            if self.gl("state").get("level") != before:   # a use that left the floor is a finding: stop
                res["uses"][-1]["leftFloor"] = True
                break
        for kind in USABLE_SCRIPTS:
            for s in [s for s in self.ws(kind) if "id" in s][:6]:
                self.tp(s["x"], s["y"] + 24, 0.3)
                r = self.gl("itc-use", f"#{s['id']}", 400)
                time.sleep(0.4)
                res["usables"].append({"kind": kind, "canUse": r.get("canUse"), "used": r.get("used"), "dialog": self.dismiss()})
        rep["use"] = res

    def run_tower(self, start=0, count=0):
        self.layouts = exit_layouts()
        self.area_layouts = prefab_areas()
        self._levels, self._ws, self.dealt = {}, {}, set()
        self.notes.append(f"area layouts: {len(self.area_layouts)} area triggers off their areas in the prefabs")
        self.flag("run_layouts", len(self.layouts) >= 6, f"{len(self.layouts)}: {[l[2] for l in self.layouts]}")
        levels = self.levels()
        self.flag("run_mission", len(levels) >= 20, str(levels))
        self.mark = len(self.g.read_log())
        r = self.gl("mission", MISSION, start, timeout=30)
        ok = bool(r.get("ok")) and self.wait_phase("mission", 240)
        self.flag("run_started", ok, str(r))
        time.sleep(4)
        floors = []
        last = min(len(levels), start + count) if count else len(levels)
        for n in range(start, last):
            if not ok:
                break
            _, fid, lvl = levels[n]
            name = level_name(lvl) if lvl else ""
            try:
                rep = self.floor(n, fid, name)
                if n + 1 < len(levels):
                    self.mark = len(self.g.read_log())
                    rep["exitTaken"] = ok = self.take_exit(rep, name)
                else:
                    self.end_window(rep)
            except Exception as e:  # a floor's crash ends the run, reported
                rep = {"n": n, "id": fid, "crash": repr(e)[:300]}
                ok = False
            floors.append(rep)
            self.notes.append(f"floor {n} {fid}: " + str({k: v for k, v in rep.items() if k not in ("record", "recordAfter", "scripts")})[:1800])
        self.out["floors"] = floors
        self.report(floors, last - start)

    def report(self, floors, want):
        def fl(k, bad, detail=""):
            self.flag(k, not bad, f"{bad}{detail}")
        stuck = [(f["n"], f.get("id"), f.get("exit"), f.get("exitUse"), f.get("next"), f.get("crash"))
                 for f in floors if f.get("crash") or (f is not floors[-1] and not f.get("exitTaken"))]
        fl("run_all_floors", stuck if stuck or len(floors) == want else [("reached", len(floors))], f" reached {len(floors)} of {want}")
        fl("run_alive", [f["n"] for f in floors if "alive" in f and not f["alive"]])
        fl("run_clean_log", [(f["n"], f.get("nbad"), f.get("bad", [])[:3]) for f in floors if f.get("nbad")])
        # a boss floor holds only its boss (the armory's wraiths stand as statues until the fight): run_bosses checks it
        # a floor with no spawners either is empty by design (the bridge, HoH1's walk to the dragon)
        fl("run_enemies", [(f["n"], f.get("id")) for f in floors if "enemies" in f and not f["enemies"] and "bossKilled" not in f
                           and (f.get("scripts") or {}).get("SpawnEnemyGroup")])
        fl("run_enemies_act", [(f["n"], f.get("id"), f.get("enemies")) for f in floors
                               if f.get("enemies") and not f.get("active") and "bossKilled" not in f])
        fl("run_enemies_cleared", [(f["n"], f.get("left")) for f in floors if f.get("left")])
        # traps fire in every act. A floor can hold traps that stay silent for a player who
        # doesn't set them off: a locked chest room's (no key for its gold or silver chest), an
        # archives hidden-chest puzzle's (a wrong move fires them); those floors are listed
        def fired(f):
            return sum(f["traps"].get(k, 0) for k in ("shotsFired", "areasToggled", "rays", "areasToggledByUse", "raysByUse"))
        # a boss floor's danger areas are its fight's (no tour there): run_bosses covers it
        trapped = [f for f in floors if (f.get("traps") or {}).get("shooters", 0) + (f.get("traps") or {}).get("areas", 0) > 0
                   and "bossKilled" not in f]
        acts = {}
        for f in trapped:
            acts.setdefault(str(f.get("id", "")).rsplit("_", 1)[0], []).append(f)
        silent = [(f["n"], f.get("id"), f.get("traps")) for f in trapped if not fired(f)]
        fl("run_traps_fire", [a for a, fs in acts.items() if not any(fired(f) for f in fs)],
           f" (acts with traps: {sorted(acts)}; floors with traps that stayed silent: {silent})")
        fl("run_chests", [(f["n"], c) for f in floors for c in (f.get("use") or {}).get("chests", []) if c.get("canUse") and not c.get("used")])
        # a UseTrigger whose trigger times ran out (t 0: a one-time lever already pulled by the level),
        # or that the floor's own scripts switched off before its turn (eNow), can't be used
        fl("run_uses", [(f["n"], u) for f in floors for u in (f.get("use") or {}).get("uses", [])
                        if (not u.get("used") and u.get("t") != 0 and u.get("eNow", True)) or u.get("leftFloor")])
        fl("run_usables", [(f["n"], u) for f in floors for u in (f.get("use") or {}).get("usables", []) if u.get("canUse") and not u.get("used")])
        fl("run_bosses", [(f["n"], f.get("id"), f.get("bossSpawned"), f.get("bossKilled")) for f in floors
                          if "bossKilled" in f and not (f.get("bossSpawned") and f.get("bossKilled"))])
        # HoH1's gambler: a bet rolled (the trinkets bet gone, one new one, shown as the final item), the window closed
        fl("run_dealer", [(f["n"], u["dealer"]) for f in floors for u in (f.get("use") or {}).get("uses", []) if u.get("dealer")
                          and not (u["dealer"].get("closed") and (not u["dealer"].get("listed") or (u["dealer"].get("final")
                                   and u["dealer"]["after"] == u["dealer"]["before"] - u["dealer"]["bet"] + 1)))])
        last = floors[-1] if floors else {}
        fl("run_end", [] if "endWindow" not in last else [(last.get("n"), last.get("endWindow"), last.get("endTown"))]
           if not (last["endWindow"].get("top") == "HoH1EndOfGame" and last.get("endTown")) else [])
        lv = [(f["n"], (f.get("record") or {}).get("level"), (f.get("record") or {}).get("xp")) for f in floors if "record" in f]
        drops = [(a, b) for a, b in zip(lv, lv[1:]) if (b[1] or 0) < (a[1] or 0) or (b[2] or 0) < (a[2] or 0)]
        fl("run_character_kept", drops, f" level/xp per floor {lv}")
        self.out["summary"] = [
            {"n": f["n"], "id": f.get("id"), "enemies": f.get("enemies"), "active": f.get("active"), "killed": f.get("killed"),
             "traps": f.get("traps"), "tour": f.get("tour"), "chests": len((f.get("use") or {}).get("chests", [])),
             "doors": len((f.get("use") or {}).get("doors", [])), "uses": len((f.get("use") or {}).get("uses", [])),
             "pickups": f.get("pickups"), "exit": (f.get("exit") or {}).get("how")} for f in floors]


def run(p, start=0, count=0, **_):
    """start: the first floor's index (`gl mission` loads it); count: how many floors to play (0: to the end)"""
    c = Checks(p)
    c.run_tower(int(start), int(count))
    c.out["notes"] = c.notes
    return c.out
