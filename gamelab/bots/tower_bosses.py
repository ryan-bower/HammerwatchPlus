"""The HoH1 Forsaken Tower's bosses (mission hwp_forsaken_tower_hoh1, mods/campaign README,
"HoH1 tower"): each boss floor's fight, started and ended the way the HoH1 level does.

Per boss level (RECIPES, with the level's own script ids; the areas, script positions
and exits are read from the imported level, mods/campaign/hoh1/levels/<level>.lvl):
- `gl mission` to the floor, god mode on;
- the fight's trigger as a player meets it: into the area of its AreaTrigger (or
  AllPlayersAreaTrigger), its UseTrigger used;
- the boss units (the ones its CreateBossBar shows) appear within 30 s;
- the fight runs FIGHT_S seconds with the boss and the player alive, a screenshot
  mid-fight;
- the HUD's boss bar shows a bar per boss unit, titled with the boss's HoH1 name
  (TITLES: HoH1's bestiary name, from the imported hwp_campaign_hoh1.lang, or the
  level's own; `gl bossbars`);
- before the fight, a level's speech bubble (BUBBLES): its UseTrigger used, the bubble open
  over the player with HoH1's text (`gl bubbles`), a screenshot;
- each boss unit killed in turn with the player as the killer (`kill <file> me`, a few
  seconds apart as in a fight: the Wraiths' level counts their deaths through one
  ScriptLink) until HoH1's SetBossKilled runs ("HoH1 boss N killed", WorldScripts.as);
- the log stays clean (the base game's load noise aside);
- the exit's UseTrigger (most levels keep it off until the boss dies) is enabled; standing in its area
  (whose AllPlayersAreaTrigger enables the LevelExitNext) and using it loads the next
  floor. After the dragon, where it leads is noted.
The result's `bosses` holds what each fight reported.
"""
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from gamelab.bots.plan_checks import Checks as Base
from gamelab.bots.tower_floors import BAD, MISSION, NOISE

LEVELS = Path(__file__).resolve().parents[2] / "mods" / "campaign" / "hoh1" / "levels"
FIGHT_S = 15
EXITS = ("LevelExitNext", "HoH1LevelExitNext")
# level -> (boss number its SetBossKilled logs, boss unit files, steps that start the fight)
RECIPES = {
    # AreaTrigger 943 (area 20) -> SpawnUnit 942 SpawnGolem
    "boss_mines": (1, ["hoh1/actors/bosses/golem/golem_rock.unit"], [("area", 943)]),
    # AreaTrigger 627 ActivateBoss -> SpawnUnitWithEffect 629 Warden
    "boss_prison": (2, ["hoh1/actors/bosses/warden/warden.unit"], [("area", 627)]),
    # UseTrigger 954 on the teleport pad enables Teleport 717 (the same spot) ->
    # ScriptLink 666 ActivateBoss: the three Wraiths' intros, then the Wraiths
    "boss_armory": (3, ["hoh1/actors/bosses/wraith/wraith_scythe.unit", "hoh1/actors/bosses/wraith/wraith_mage.unit",
                        "hoh1/actors/bosses/wraith/wraith_staff.unit"],
                    [("area", 954), ("wait", 1.5), ("use", 954), ("wait", 2), ("area", 717)]),
    # AllPlayersAreaTrigger 4791 (all in the ring) enables ScriptLink 4750 Boss_Stage1, which
    # UseTrigger 4670 StartBoss (the book) runs -> SpawnUnit 4783 IntroEyeBoss -> 4678 EyeBoss
    "boss_archives": (4, ["hoh1/actors/bosses/eye/eye.unit"],
                      [("area", 4791, 0, 64), ("wait", 1.5), ("use", 4670)]),
    # no crosses found: CheckFlag 757 -> ToggleScripts 744 enables AreaTrigger 636 ->
    # SpawnUnitWithEffect 618 Vampire
    "boss_chambers": (6, ["hoh1/actors/bosses/vampire/vampire.unit"], [("wait", 2), ("area", 636)]),
    # AreaTrigger 968 EnableBoss -> SpawnUnit 967 dragon (+1 s)
    "boss_dragon": (5, ["hoh1/actors/bosses/dragon/dragon.unit"], [("area", 968)]),
}

# level -> the boss bar titles it may show (the first bar's name; the Wraiths' three
# CreateBossBar rows run together)
TITLES = {
    "boss_mines": {"Stone Guardian"},
    "boss_prison": {"Warden"},
    "boss_armory": {"Councilor of War", "Councilor of Magic", "Councilor of Wisdom"},
    "boss_archives": {"Watcher"},
    "boss_chambers": {"Vampire Lord"},
    "boss_dragon": {"Thundersnow"},
}

# level -> (a UseTrigger whose HoH1ShowSpeechBubble talks over the user, HoH1's text)
BUBBLES = {
    # the painting: "dialogue.player.painting.2"
    "boss_armory": (1014, "That's one depressing painting..."),
}


def one_line(s):
    return " ".join(str(s).replace("\\n", "\n").split())


def level_name(lvl):
    return lvl.rsplit("/", 1)[-1].removesuffix(".lvl")


def _val(e):
    if e.tag == "dict":
        return {c.get("name"): _val(c) for c in e}
    if e.tag == "array":
        return [_val(c) for c in e]
    if e.tag == "int":
        return int(e.text or 0)
    if e.tag == "bool":
        return (e.text or "").strip() == "true"
    return (e.text or "").strip()


def _xy(text):
    x, y = str(text).split()[:2]
    return float(x), float(y)


class Level:
    """An imported HoH1 level's world scripts (id -> type, position, params, what it
    executes) and its area shapes (id -> centre)."""

    def __init__(self, name):
        text = (LEVELS / f"{name}.lvl").read_text(encoding="utf-8")
        root = ET.fromstring(re.sub(r"^<!--.*?-->", "", text, flags=re.S))
        top = {c.get("name"): c for c in root}
        self.scripts, self.shapes = {}, {}
        for s in top["scripts"]:
            v = [_val(c) for c in s]
            ex = v[-1] if isinstance(v[-1], list) else []
            self.scripts[v[1]] = {"type": v[0], "pos": _xy(v[2]), "ex": ex[0::2],
                                  "params": next((x for x in v if isinstance(x, dict)), {})}
        for group in top["units"]:
            if group.get("name", "").startswith(":Physics"):
                for u in group:
                    uv = [_val(c) for c in u]
                    self.shapes[uv[1]] = _xy(uv[0])

    def area(self, sid):
        return self.shapes[self.scripts[sid]["params"]["Areas"][0]]

    def exit_use(self):
        """the UseTrigger that runs a LevelExitNext from an area (the archives keep an unused
        one without): its id, its area's centre and its own position"""
        for sid, s in self.scripts.items():
            if s["type"] == "UseTrigger" and s["params"].get("Areas") and any(self.scripts.get(t, {}).get("type") in EXITS for t in s["ex"]):
                return sid, self.area(sid), s["pos"]
        return None


class Checks(Base):
    def levels(self):
        r = self.gl("itc-mission", MISSION)
        return [(i, lv.get("id", "?"), lv.get("level") or "") for i, lv in enumerate(r.get("levels") or [])]

    def bad_lines(self, mark):
        return [ln for ln in self.g.read_log()[mark:].splitlines() if BAD.search(ln) and not NOISE.search(ln)]

    def bosses(self, files):
        r = self.gl("unitsof", *files)
        return [u for f in files for u in (r.get(f) or {}).get("units") or []]

    def god_on(self):
        if "god mode off" in self.hwp("god", 0.3, until="god mode"):
            self.hwp("god", 0.3, until="god mode")

    def step(self, lv, s):
        if s[0] == "area":
            x, y = lv.area(s[1])
            if len(s) > 2:
                x, y = x + s[2], y + s[3]
            return self.gl("teleport", x, y)
        if s[0] == "use":
            return self.gl("itc-use", f"#{s[1]}", 3000)
        if s[0] == "wait":
            time.sleep(s[1])
            return {}
        raise ValueError(s)

    def wait_boot(self, mark, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            new = self.g.read_log()[mark:]
            if any('[GL] {"ev":"boot"' in ln and "[preload]" not in ln for ln in new.splitlines()):
                return True
            time.sleep(0.5)
        return False

    def use_trigger_on(self, pos):
        r = self.gl("ws", "UseTrigger")
        return any(s.get("e") for s in r.get("scripts") or []
                   if abs(float(s.get("x", 0)) - pos[0]) < 1 and abs(float(s.get("y", 0)) - pos[1]) < 1)

    def fight(self, i, fid, lvl):
        name = level_name(lvl)
        number, files, steps = RECIPES[name]
        lv = Level(name)
        tag = f"boss{i}_{name}"
        rep = {"floor": i, "id": fid, "level": name}
        mark = len(self.g.read_log())
        r = self.gl("mission", MISSION, i, timeout=30)
        ok = bool(r.get("ok")) and self.wait_phase("mission", 240)
        self.flag(tag + "_loaded", ok, f"{r}")
        time.sleep(4)
        self.god_on()
        exit_use = lv.exit_use()
        if exit_use:
            rep["exitShutBefore"] = not self.use_trigger_on(exit_use[2])
        if name in BUBBLES:
            sid, text = BUBBLES[name]
            u = self.gl("itc-use", f"#{sid}", 3000)
            time.sleep(1)
            open_ = self.gl("bubbles").get("bubbles") or []
            rep["bubbles"] = open_
            self.flag(tag + "_bubble", u.get("used") and any(one_line(b.get("text")) == text for b in open_),
                      f"use {u}, open {open_}")
            self.g.shot(f"boss-{i:02d}-{name}-bubble")
        rep["start"] = [str(self.step(lv, s))[:160] for s in steps]
        found = []
        end = time.time() + 30
        while time.time() < end and len(found) < len(files):
            time.sleep(1)
            found = self.bosses(files)
        self.flag(tag + "_spawned", len(found) >= len(files), f"{len(found)} of {files}")
        # the fight: the boss acts on a live player for a while
        time.sleep(FIGHT_S / 2)
        self.g.shot(f"boss-{i:02d}-{name}-fight")
        bb = self.gl("bossbars")
        units = sorted(str(b.get("unit") or "").rsplit("/", 1)[-1] for b in bb.get("bars") or [])
        rep["bossbar"] = {"shown": bb.get("shown"), "title": bb.get("title"), "units": units}
        self.flag(tag + "_bossbar", bool(bb.get("shown")) and bb.get("title") in TITLES[name]
                  and all(f.rsplit("/", 1)[-1] in units for f in files),
                  f"{rep['bossbar']}, want a title in {sorted(TITLES[name])}")
        time.sleep(FIGHT_S / 2)
        alive = self.bosses(files)
        p = self.gl("state").get("player") or {}
        start = {u.get("unit"): (float(u.get("x", 0)), float(u.get("y", 0))) for u in found}
        rep["moved"] = sum(1 for u in alive if u.get("unit") in start
                           and abs(start[u["unit"]][0] - float(u.get("x", 0))) + abs(start[u["unit"]][1] - float(u.get("y", 0))) > 8)
        self.flag(tag + "_fights", len(alive) >= len(files) and p.get("spawned") and not p.get("dead"),
                  f"{len(alive)} after {FIGHT_S}s ({rep['moved']} moved), player hp {p.get('hp')}")
        # each boss killed in turn, the player the killer, until HoH1's SetBossKilled runs
        kmark = len(self.g.read_log())
        line = f"HoH1 boss {number} killed"
        killed, rounds = [], 0
        while rounds < 3 and line not in self.g.read_log()[kmark:]:
            rounds += 1
            for f in files:
                # "/wraith_scythe.unit", not its statue "statue_wraith_scythe.unit"
                k = self.gl("kill", 4000, "/" + f.rsplit("/", 1)[-1], "me")
                killed += [n.rsplit("/", 1)[-1] for n in k.get("names") or []]
                time.sleep(2.5)
            end = time.time() + 8
            while time.time() < end and line not in self.g.read_log()[kmark:]:
                time.sleep(0.5)
        rep["killed"] = killed
        self.flag(tag + "_boss_killed", line in self.g.read_log()[kmark:], f"{killed} in {rounds} rounds")
        self.g.shot(f"boss-{i:02d}-{name}-dead")
        # the exit HoH1 opens after the fight (some after a delay), taken
        if not exit_use:
            self.flag(tag + "_exit_found", name == "boss_dragon", "no UseTrigger runs a LevelExitNext")
        else:
            sid, area, pos = exit_use
            end = time.time() + 15
            while time.time() < end and not self.use_trigger_on(pos):
                time.sleep(1)
            opened = self.use_trigger_on(pos)
            # most levels switch it on only after the fight (the archives' is on throughout)
            self.flag(tag + "_exit_open", opened, f"UseTrigger {sid}: shut before the fight {rep.get('exitShutBefore')}, open after {opened}")
            before = self.gl("state").get("level")
            emark = len(self.g.read_log())
            self.gl("teleport", *area)
            time.sleep(1.5)
            u = self.gl("itc-use", f"#{sid}", 3000)
            rep["exitUse"] = {k: u.get(k) for k in ("unit", "canUse", "used")}
            booted = self.wait_boot(emark)
            self.wait_phase("mission", 60)
            after = self.gl("state")
            rep["after"] = {"booted": booted, "phase": after.get("phase"), "level": after.get("level")}
            self.flag(tag + "_next_floor", booted and after.get("level") != before and after.get("phase") == "mission",
                      f"{before} -> {after.get('phase')} {after.get('level')}")
        bad = self.bad_lines(mark)
        rep["bad"] = bad[:12]
        self.flag(tag + "_clean_log", not bad, f"{len(bad)}: {bad[:6]}")
        self.out.setdefault("bosses", []).append(rep)


def run(p, floors="all"):
    c = Checks(p)
    levels = [lv for lv in c.levels() if level_name(lv[2]) in RECIPES]
    c.flag("boss_floors_found", len(levels) == len(RECIPES), f"{levels}")
    want = None if floors == "all" else {int(x) for x in str(floors).split(",") if x.strip()}
    for i, fid, lvl in levels:
        if want is not None and i not in want:
            continue
        try:
            c.fight(i, fid, lvl)
        except Exception as e:  # one boss's failed read must not hide the rest
            c.flag(f"boss{i}_raised", False, repr(e))
    c.out["ok"] = all(v for k, v in c.out.items() if isinstance(v, bool))
    c.out["notes"] = c.notes
    return c.out
