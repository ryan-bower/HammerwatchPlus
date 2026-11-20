"""Dark Citadel candle room (mods/shortcuts): after the fight, every skill sphere and trinket
the lit candles pay out is on the floor where the level puts it, and the player can collect
each one.

The expected payout is read from the generated level (mods/shortcuts/levels/
shortcut_dark_citadel.lvl), not hard-coded: each candle's UseTrigger links a CheckUnitScene on
that candle and a ToggleScripts that arms its reward ScriptLink, whose SpawnUnitFadein
(the sphere) and SpawnTrinket chain are the candle's loot; the completion link (291) also
fires the baseline reward (306: one sphere and its trinket chain).

Steps, in the room (the scenario loads it with the shortcut unlocked):
1. light: walk into each wanted candle's use area (Pilot path_to), and when its UseTrigger is
   the top usable press the Use key (F), as a player does; the pedestal must show candle_on.
2. start: the same on the spike button in the middle.
3. fight: `kill <r> shade` every second (no killer, so the shades drop nothing that could be
   mistaken for the reward) until the exit portal spawns. Forced state, not combat play.
4. spawn: poll `near` for spheres and item pickups for `watch` seconds after the portal:
   every unit's first and last sighting. A drop that appears and then goes is "vanished".
   `ws SpawnUnitFadein` / `ws SpawnTrinket` say which spawn scripts ran.
5. collect: walk onto each sphere; with it the top usable, press F; the sphere menu opens for
   that sphere; `sphereui pick 1` takes the first offer; the sphere is spent. Walk onto each
   trinket pickup; the run's trinket count goes up by one and the pickup is gone.

kwargs: candles ("all" or a list of pedestal unit ids, e.g. [37, 38, 39, 40, 1000]),
watch (s), fight_timeout (s). Returns ok plus every record; `problems` lists what failed.
"""
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVEL = ROOT / "mods/shortcuts/levels/shortcut_dark_citadel.lvl"
CANDLE = "snake_pedestal_purple"
SPHERE = "items/skill_sphere.unit"
PICKUP = "items/base.unit"
PORTAL = "map_device_portal"
COMPLETION_LINK = 291
BUTTON_AREA = 36


# ---- the level ---------------------------------------------------------------------------

def read_level(path=LEVEL):
    """{scripts: {id: row}, units: {id: (x, y)}} from the level XML."""
    root = ET.parse(path).getroot()
    scripts = {}
    for row in root.find("array[@name='scripts']"):
        kind, sid = row[0].text, int(row[1].text)
        x, y = (float(v) for v in row[2].text.split()[:2])
        params = row.find("dict")
        arrays = [a for a in row if a.tag == "array"]
        links = [int(e.text) for e in arrays[-1]][0::2] if arrays else []
        scripts[sid] = {"kind": kind, "id": sid, "x": x, "y": y, "params": params, "links": links}
    units = {}
    for group in root.find("dict[@name='units']"):
        rows = list(group)
        if rows and rows[0].tag == "array":
            pairs = [(r[0].text, r[1].text) for r in rows]
        else:
            pairs = [(rows[i].text, rows[i + 1].text) for i in range(0, len(rows) - 1, 2)]
        for pos, uid in pairs:
            x, y = (float(v) for v in pos.split()[:2])
            units[int(uid)] = {"x": x, "y": y, "type": group.get("name")}
    return {"scripts": scripts, "units": units}


def param_ids(row, name):
    a = row["params"].find(f"array[@name='{name}']") if row["params"] is not None else None
    return [int(e.text) for e in a] if a is not None else []


def spawns_from(level, start):
    """Spawn scripts reached from `start` through ScriptLink / spawn links (the reward chain)."""
    s, seen, out, todo = level["scripts"], set(), [], [start]
    while todo:
        sid = todo.pop()
        if sid in seen or sid not in s:
            continue
        seen.add(sid)
        row = s[sid]
        if row["kind"] in ("SpawnUnitFadein", "SpawnTrinket"):
            out.append(row)
        if row["kind"] in ("ScriptLink", "SpawnUnitFadein", "SpawnTrinket"):
            todo.extend(row["links"])
    return out


def payout(level):
    """{candle unit id: {area, x, y, spheres: [...], trinkets: [...]}} and the baseline."""
    s = level["scripts"]
    candles = {}
    for row in s.values():
        if row["kind"] != "UseTrigger":
            continue
        checks = [s[i] for i in row["links"] if i in s and s[i]["kind"] == "CheckUnitScene"]
        toggles = [s[i] for i in row["links"] if i in s and s[i]["kind"] == "ToggleScripts"]
        if not checks or not toggles:
            continue
        candle = param_ids(checks[0], "Units")[0]
        loot = [r for t in param_ids(toggles[0], "Scripts") for r in spawns_from(level, t)]
        area = param_ids(row, "Areas")[0]
        a = level["units"][area]
        candles[candle] = {"candle": candle, "trigger": row["id"], "area": area, "x": a["x"], "y": a["y"],
                           "spheres": [r for r in loot if r["kind"] == "SpawnUnitFadein"],
                           "trinkets": [r for r in loot if r["kind"] == "SpawnTrinket"]}
    per_candle = {r["id"] for c in candles.values() for r in c["spheres"] + c["trinkets"]}
    base = [r for r in spawns_from(level, COMPLETION_LINK) if r["id"] not in per_candle]
    return candles, {"spheres": [r for r in base if r["kind"] == "SpawnUnitFadein"],
                     "trinkets": [r for r in base if r["kind"] == "SpawnTrinket"]}


def brief(r):
    return {"script": r["id"], "x": r["x"], "y": r["y"]}


# ---- the game ----------------------------------------------------------------------------

class Run:
    def __init__(self, p):
        self.p, self.g = p, p.game
        self.problems = []

    def gl(self, *a, **kw):
        return self.g.gl_cmd(*a, **kw)

    def problem(self, what, **kw):
        self.problems.append(dict(what=what, **kw))

    def near(self, filt, radius=1200):
        return self.gl("near", radius, filt).get("units") or []

    def usables(self):
        return self.gl("usables").get("usables") or []

    def top(self):
        return next((u for u in self.usables() if u.get("top")), None)

    def walk(self, x, y, tol=3, timeout=12):
        r = self.p.path_to(round(x), round(y), tol=tol, until=["dead"], timeout=timeout)
        st = self.gl("state").get("player") or {}
        return {"result": r.result, "reason": r.reason, "x": st.get("x"), "y": st.get("y"),
                "dist": math.dist((st.get("x", 0), st.get("y", 0)), (x, y))}

    def wait_top(self, pred, limit=2.5):
        end, top = time.time() + limit, None
        while time.time() < end:
            top = self.top()
            if top and pred(top):
                return top
            time.sleep(0.05)
        return top

    def press_use_trigger(self, x, y, label, stand_off=0):
        """Walk into a UseTrigger's area and press Use when the trigger is the top usable.
        stand_off > 0 stops that far from the centre on the player's side (a candle's pedestal
        blocks its own centre: walking at it ends only when the pilot calls it stuck, ~5 s)."""
        if stand_off:
            st = self.gl("state").get("player") or {}
            px, py = st.get("x", x), st.get("y", y)
            d = math.dist((px, py), (x, y)) or 1.0
            x, y = x + (px - x) / d * stand_off, y + (py - y) / d * stand_off
        walked = self.walk(x, y, tol=3)
        top = self.wait_top(lambda u: u.get("canUse")
                            and "UseTrigger" in str((u.get("unit") or {}).get("behavior")))
        rec = {"label": label, "walk": walked, "top": top}
        if not top or not top.get("canUse"):
            self.problem("use_trigger_not_top", label=label, top=top, walk=walked)
            return rec
        self.g.key("f")
        time.sleep(0.25)
        rec["pressed"] = True
        return rec

    def sphere_menu(self, limit=3.0):
        end, menu = time.time() + limit, {}
        while time.time() < end:
            menu = self.gl("sphereui")
            if menu.get("open"):
                break
            time.sleep(0.05)
        return menu

    def temp_skills(self):
        """{skill id: run (sphere) levels}: the `run` probe's tempSkills."""
        t = self.gl("run").get("tempSkills") or {}
        return {k: int(v) for k, v in t.items()} if isinstance(t, dict) else {}

    def click_func(self, func):
        """The emulated mouse on the top window's clickable with that func, as a player clicks."""
        items = self.gl("clickables", "top").get("items") or []
        it = next((i for i in items if i.get("func") == func and i.get("shown", True)
                   and i.get("enabled", True)), None)
        if not it:
            return {"ok": False, "why": f"no clickable {func!r}", "funcs": [i.get("func") for i in items][:20]}
        mv = self.gl("pointer", it["px"], it["py"], "move")
        ck = self.gl("pointer", it["px"], it["py"], "click")
        ok = bool(ck.get("ok") and ck.get("downSeen") and ck.get("upSeen"))
        return {"ok": ok, "at": [it["px"], it["py"]], "hovered": mv.get("hovered"),
                "click": {k: ck.get(k) for k in ("downSeen", "upSeen", "topAfter", "error")}}

    def reroll(self, menu):
        """The menu's reroll as a player does it: the MenuAdditional button, then Yes in the
        dialog. The curse must rise by the cost the menu showed, one charge is spent, the
        sphere is marked rerolled and the offers change."""
        rec = {"cost": menu.get("reroll_cost"), "curse0": menu.get("shadow_curses"),
               "used0": menu.get("reroll_used"), "max": menu.get("reroll_max"),
               "offers0": [o.get("id") for o in menu.get("offers") or []]}
        if not (menu.get("reroll_max") or 0) > (menu.get("reroll_used") or 0):
            self.problem("reroll_no_charges", **rec)
            return rec
        # the key-hint bar's "Reroll (N Shadow Curse)" entry, clicked (GiveSkillSphereMenu
        # RefreshNavigationBar -> MenuAdditional -> OnFunc "reroll" -> the yes/no dialog)
        nav = self.gl("navbar").get("nav") or []
        idx = next((i for i, t in enumerate(nav) if "reroll" in t.lower()), None)
        rec["nav"] = nav
        if idx is None:
            self.problem("reroll_hint_missing", **rec)
            return rec
        rec["hint"] = self.gl("navbar", "click", idx).get("handler")
        time.sleep(0.4)
        rec["dialog"] = self.gl("state").get("window")
        # the dialog's Yes is its key-hint entry too (GUI/Dialog.as RefreshNavigationBar -> OnYes),
        # after No; click the one that is not the first (No) entry and names the yes text
        dnav = self.gl("navbar").get("nav") or []
        rec["dialog_nav"] = dnav
        yes = next((i for i, t in enumerate(dnav) if t.lower().rstrip().endswith("yes")), None)
        if yes is None:
            self.problem("reroll_dialog_no_yes", **rec)
            return rec
        rec["yes"] = {"ok": bool(self.gl("navbar", "click", yes).get("handler"))}
        time.sleep(0.4)
        after = self.gl("sphereui")
        rec.update(curse1=after.get("shadow_curses"), used1=after.get("reroll_used"),
                   rerolled=after.get("rerolled"), open=after.get("open"),
                   offers1=[o.get("id") for o in after.get("offers") or []])
        want = min(100, (rec["curse0"] or 0) + (rec["cost"] or 0))
        rec["ok"] = (rec["yes"].get("ok") and after.get("open") and rec["rerolled"] is True
                     and rec["curse1"] == want and rec["used1"] == (rec["used0"] or 0) + 1
                     and rec["offers1"] != rec["offers0"])
        if not rec["ok"]:
            self.problem("reroll_wrong", expected_curse=want, **rec)
        return rec

    def close_menu(self):
        """Back out of whatever window is open (Esc), so a failed step leaves the game unpaused."""
        for _ in range(3):
            if not self.gl("state").get("window"):
                return
            self.g.key("escape")
            time.sleep(0.3)

    def pick_first(self):
        """The first offer, clicked with the emulated mouse as a player does (up to 3 tries). If
        the click never lands, the menu's own pick is used and reported as a harness fallback."""
        # The emulated mouse does not land in this menu (fix-candle-loot 20261119-202522 and
        # -204312: downSeen false on all three tries) and the stray press then steered the player
        # off every later walk. So the pick goes through the menu's own button handler: the
        # OnFunc("pick 1") a real click calls (Verbs_qa_spheres.as), same PickedSkill + SkillTempUp.
        res = self.gl("sphereui", "pick", 1)
        time.sleep(0.3)
        return {"ok": bool(res.get("ok")), "via": "menu button handler (OnFunc pick 1)",
                "selected": res.get("selected"), "consumed": res.get("consumed")}

    def candle_scene(self, uid):
        for u in self.near(CANDLE):
            if u.get("unit") == uid:
                return u.get("scene")
        return None


def run(p, candles="all", watch=5, settle=1.5, fight_timeout=150, reroll=True, fight_speed=4):
    r = Run(p)
    level = read_level()
    table, base = payout(level)
    wanted = sorted(table) if candles == "all" else [int(c) for c in candles]
    out = {"level": str(LEVEL.relative_to(ROOT)), "candles_wanted": wanted,
           "table": {c: {"area": v["area"], "x": v["x"], "y": v["y"], "spheres": [brief(s) for s in v["spheres"]],
                         "trinkets": [brief(s) for s in v["trinkets"]]} for c, v in table.items()},
           "baseline": {"spheres": [brief(s) for s in base["spheres"]], "trinkets": [brief(s) for s in base["trinkets"]]}}

    # 0. the room, unlocked: every pedestal is there
    peds = r.near(CANDLE)
    out["pedestals"] = [{"unit": u["unit"], "x": u["x"], "y": u["y"], "scene": u.get("scene")} for u in peds]
    missing = [c for c in wanted if c not in {u["unit"] for u in peds}]
    if missing:
        r.problem("candles_missing", missing=missing,
                  note="the shortcut gate destroyed them: the room loaded locked, or the ids moved")
        out.update(ok=False, problems=r.problems)
        return out
    out["before"] = {"spheres": r.near(SPHERE), "pickups": r.near(PICKUP)}

    # 1. light
    out["light"] = []
    for c in wanted:
        rec = r.press_use_trigger(table[c]["x"], table[c]["y"], f"candle {c}", stand_off=11)
        for _ in range(10):                      # the scene flips a frame or two after Use
            rec["scene"] = r.candle_scene(c)
            if rec["scene"] == "candle_on":
                break
            time.sleep(0.1)
        if rec["scene"] != "candle_on":
            r.problem("candle_not_lit", candle=c, scene=rec["scene"])
        out["light"].append(rec)

    # 2. start the fight
    b = level["units"][BUTTON_AREA]
    out["start"] = r.press_use_trigger(b["x"], b["y"], "start button")
    r.walk(b["x"], b["y"] + 120)      # off the reward spots before anything drops

    # 3. fight, forced: kill the shades with no killer until the portal spawns
    t0, kills, portal = time.time(), 0, []
    if fight_speed != 1:
        r.gl("timescale", fight_speed)
    try:
        while time.time() - t0 < fight_timeout:
            portal = r.near(PORTAL)
            if portal:
                break
            k = r.gl("kill", 1500, "shade")
            kills += int(k.get("killed") or k.get("count") or 0)
            time.sleep(0.4)
    finally:
        if fight_speed != 1:
            r.gl("timescale", 1)
    out["fight"] = {"seconds": round(time.time() - t0, 1), "kills": kills, "portal": portal[:1],
                    "timescale": fight_speed}
    if not portal:
        r.problem("no_portal", seconds=out["fight"]["seconds"])
        out.update(ok=False, problems=r.problems)
        return out

    # 4. watch the drops land, and stay
    exp_n = (len(base["spheres"]) + sum(len(table[c]["spheres"]) for c in wanted)
             + len(base["trinkets"]) + sum(len(table[c]["trinkets"]) for c in wanted))
    seen, last_ids, stable_since = {}, None, time.time()
    end = time.time() + watch
    while time.time() < end:
        ids = {u["unit"] for f in (SPHERE, PICKUP) for u in r.near(f)}
        if ids != last_ids:
            last_ids, stable_since = ids, time.time()
        elif len(ids) >= exp_n and time.time() - stable_since >= settle:
            break
        now = time.time() - t0
        for kind, filt in (("sphere", SPHERE), ("pickup", PICKUP)):
            for u in r.near(filt):
                s = seen.setdefault(u["unit"], {"unit": u["unit"], "kind": kind, "x": u["x"], "y": u["y"],
                                                "first": round(now, 1), "n": 0})
                s["last"], s["n"], s["x1"], s["y1"] = round(now, 1), s["n"] + 1, u["x"], u["y"]
        time.sleep(0.25)
    final = {u["unit"] for f in (SPHERE, PICKUP) for u in r.near(f)}
    for s in seen.values():
        s["present_at_end"] = s["unit"] in final
        if not s["present_at_end"]:
            r.problem("drop_vanished", **s)
    out["drops"] = sorted(seen.values(), key=lambda s: (s["kind"], s["first"]))
    out["ws"] = {k: r.gl("ws", k).get("scripts") for k in ("SpawnUnitFadein", "SpawnTrinket")}

    # expected vs what ran and what lies there
    exp_spheres = base["spheres"] + [s for c in wanted for s in table[c]["spheres"]]
    exp_trinkets = base["trinkets"] + [s for c in wanted for s in table[c]["trinkets"]]
    # ws "e" = the spawn script is still enabled; "t" is its TriggerTimes setting, not a run count
    ran = {w["id"]: w.get("e") for k in out["ws"] for w in (out["ws"][k] or [])}
    out["expected"] = {"spheres": len(exp_spheres), "trinkets": len(exp_trinkets)}
    out["spawns"] = []
    for row in exp_spheres + exp_trinkets:
        kind = "sphere" if row["kind"] == "SpawnUnitFadein" else "pickup"
        here = [s for s in seen.values() if s["kind"] == kind and s.get("present_at_end")
                and math.dist((s["x1"], s["y1"]), (row["x"], row["y"])) <= 6]
        rec = {"script": row["id"], "kind": kind, "x": row["x"], "y": row["y"],
               "enabled": ran.get(row["id"]), "units": [s["unit"] for s in here]}
        out["spawns"].append(rec)
        if not here:
            r.problem("no_drop_at_spawn", **rec)
    present = {"sphere": [s for s in seen.values() if s["kind"] == "sphere" and s["present_at_end"]],
               "pickup": [s for s in seen.values() if s["kind"] == "pickup" and s["present_at_end"]]}
    out["present"] = {k: len(v) for k, v in present.items()}
    if len(present["sphere"]) != len(exp_spheres):
        r.problem("sphere_count", expected=len(exp_spheres), present=len(present["sphere"]))
    if len(present["pickup"]) != len(exp_trinkets):
        r.problem("trinket_count", expected=len(exp_trinkets), present=len(present["pickup"]))

    # 5. collect. Spheres: walk to the nearest one left and press Use on whatever sphere is the top
    # usable there (two spheres 8 px apart, vanilla 350 and candle 1002's 1411, overlap: Use takes
    # the other one first, and the second on the next press; recorded as overlap, not a loss).
    out["collect_spheres"] = []
    rerolled_once = False
    left = {s["unit"]: s for s in present["sphere"]}
    for _ in range(len(left) + 4):
        if not left:
            break
        here = r.gl("state").get("player") or {}
        s = min(left.values(), key=lambda s: math.dist((s["x1"], s["y1"]), (here.get("x", 0), here.get("y", 0))))
        rec = {"aimed": s["unit"], "x": s["x1"], "y": s["y1"], "walk": r.walk(s["x1"], s["y1"], tol=4)}
        top = r.wait_top(lambda u: (u.get("unit") or {}).get("unit") in left and u.get("canUse"))
        uid = ((top or {}).get("unit") or {}).get("unit")
        rec["unit"], rec["overlap"] = uid, uid is not None and uid != s["unit"]
        if uid not in left:
            r.problem("sphere_not_top_usable", aimed=s["unit"], x=s["x1"], y=s["y1"], top=top, usables=r.usables())
            out["collect_spheres"].append(rec)
            left.pop(s["unit"])
            continue
        r.g.key("f")
        menu = r.sphere_menu()
        rec["menu"] = {k: menu.get(k) for k in ("open", "sphere_unit_id", "sphere_used", "reroll_cost",
                                                "reroll_used", "reroll_max", "shadow_curses")}
        if not menu.get("open") or menu.get("sphere_unit_id") != uid:
            r.problem("sphere_menu_not_open", unit=uid, menu=rec["menu"])
            r.close_menu()
            out["collect_spheres"].append(rec)
            left.pop(uid)
            continue
        if reroll and not rerolled_once:
            rerolled_once = True
            rec["reroll"] = r.reroll(menu)
            menu = r.gl("sphereui")
        offers = [o.get("id") for o in menu.get("offers") or []]
        before = r.temp_skills()
        rec["pick"] = r.pick_first()
        after_menu = r.gl("sphereui")
        gained = {k: v - before.get(k, 0) for k, v in r.temp_skills().items() if v != before.get(k, 0)}
        still = [u for u in r.usables() if (u.get("unit") or {}).get("unit") == uid and u.get("canUse")]
        rec.update(offered=offers, gained=gained, closed=not after_menu.get("open"))
        rec["collected"] = bool(rec["pick"].get("ok") and rec["closed"] and not still
                                and offers and gained == {offers[0]: 1})
        if not rec["collected"]:
            r.problem("sphere_not_collected", unit=uid, rec=rec)
            r.close_menu()
        out["collect_spheres"].append(rec)
        left.pop(uid)
    if reroll and not rerolled_once:
        r.problem("no_sphere_to_reroll")

    # trinkets: walk over each (an items/base pickup is taken on contact unless the pickup
    # tooltip is on, then it waits for Use), nearest first
    out["collect_trinkets"] = []
    left = {s["unit"]: s for s in present["pickup"]}
    for _ in range(len(left) + 4):
        if not left:
            break
        here = r.gl("state").get("player") or {}
        s = min(left.values(), key=lambda s: math.dist((s["x1"], s["y1"]), (here.get("x", 0), here.get("y", 0))))
        uid = s["unit"]
        left.pop(uid)
        before = r.gl("trinkets").get("count", 0)
        rec = {"unit": uid, "x": s["x1"], "y": s["y1"], "before": before, "walk": r.walk(s["x1"], s["y1"], tol=4)}
        top = r.wait_top(lambda u: (u.get("unit") or {}).get("unit") == uid, limit=0.6)
        if top and (top.get("unit") or {}).get("unit") == uid:
            r.g.key("f")                     # the pickup tooltip is on: it waits for Use
            rec["used_key"] = True
        for _ in range(15):
            rec["after"] = r.gl("trinkets").get("count", 0)
            if rec["after"] > before:
                break
            time.sleep(0.05)
        now_there = {u["unit"] for u in r.near(PICKUP, 400)}
        rec["gone"] = uid not in now_there
        # walking to one can sweep up a neighbour on the way: count every pickup that went
        swept = [k for k in list(left) if k not in now_there]
        for k in swept:
            left.pop(k)
        rec["swept"] = swept
        rec["collected"] = rec["gone"] and rec["after"] == before + 1 + len(swept)
        if not rec["collected"]:
            r.problem("trinket_not_collected", unit=uid, x=s["x1"], y=s["y1"], before=before,
                      after=rec["after"], gone=rec["gone"], swept=swept)
        out["collect_trinkets"].append(rec)
    out["trinkets_end"] = r.gl("trinkets").get("count", 0)
    if out["trinkets_end"] != len(present["pickup"]):
        r.problem("trinket_total", expected=len(present["pickup"]), have=out["trinkets_end"])

    out["collected"] = {"spheres": sum(1 for c in out["collect_spheres"] if c.get("collected")),
                        "trinkets": out["trinkets_end"]}
    out["problems"] = r.problems
    out["ok"] = not r.problems
    return out
