"""Python client for mods/gamelab-pilot: blocking verbs over the gl channel.

    from gamelab.pilot import Pilot
    p = Pilot(game, run_id="20261017-...")
    r = p.path_to(120, 40, until=["hp_below:40", "under_attack"], timeout=30)
    if r.result == "interrupted": ...

Every intent verb blocks until the in-engine intent ends and returns a Result whose
`result` is one of RESULTS. `until=` takes names from the closed INTERRUPTS vocabulary
(a name with an argument is "name:arg"); anything else raises ValueError before a
command is sent, and the mod refuses it too.

level_changed: a level load reloads the script module, so the intent in the engine is
gone with it. The client sees the probe's next "boot" event instead (not a "[preload]"
one: the game preloads the next floor in a separate script context that constructs the
modules too, session.py tags those): an `exit` intent
ends "done" there, any other intent ends "interrupted" with reason "level_changed".

Travel: gamelab/travel/authored.json (hand-written edges) and learned.json (edges an
exit intent took). An exit that leads somewhere the graph did not know is appended to
learned.json with its run id, in an exploration run only (a scenario with "explore": true,
Pilot(explore=True)); any other run reports it as new_edge and leaves the graph alone, so
its results stay deterministic. graph_revision() is the sha8 of both files, pinned in
scenario results.

Bots (gamelab/bots/<name>.py) define run(pilot) and are loaded fresh by path on every
call (load_bot), so an edited bot runs on the next call without a game restart.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRAVEL = REPO / "gamelab" / "travel"
BOTS = REPO / "gamelab" / "bots"

INTERRUPTS = ("hp_below", "under_attack", "target_dead", "level_changed", "menu_open", "dead")
RESULTS = ("done", "failed", "timeout", "interrupted", "no_route")


@dataclass
class Result:
    result: str
    reason: str = ""
    intent: str = ""
    id: str = ""
    tick: int | None = None
    event: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.result == "done"


def check_until(until) -> list[str]:
    names = [until] if isinstance(until, str) else list(until or [])
    for u in names:
        if u.split(":", 1)[0] not in INTERRUPTS:
            raise ValueError(f"unknown interrupt {u!r}: the vocabulary is closed ({', '.join(INTERRUPTS)})")
    return names


def graph_revision() -> str:
    h = hashlib.sha256()
    for name in ("authored.json", "learned.json"):
        p = TRAVEL / name
        h.update(name.encode() + b"\0" + (p.read_bytes() if p.exists() else b""))
    return h.hexdigest()[:8]


def load_graph() -> dict:
    edges = []
    for name in ("authored.json", "learned.json"):
        p = TRAVEL / name
        if p.exists():
            edges += [dict(e, source=name) for e in json.loads(p.read_text(encoding="utf-8")).get("edges", [])]
    return {"edges": edges}


def known_edge(frm: str, to: str, forget=()) -> bool:
    """`forget`: (from, to) pairs treated as unknown (a scenario's "forget_edges")."""
    if (frm, to) in forget:
        return False
    return any(e["from"] == frm and e["to"] == to for e in load_graph()["edges"])


def learn_edge(frm: str, to: str, via: dict, run_id: str, forget=()) -> bool:
    """Append frm -> to to learned.json unless the graph already has it. True if new.
    A forgotten edge counts as new, and the fresh crossing replaces its stored entry, so
    the file always holds the edge, with the latest run that proved it."""
    if known_edge(frm, to, forget):
        return False
    p = TRAVEL / "learned.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "about": "Level transitions the Pilot took that authored.json did not list. Written by gamelab/pilot.py.",
        "edges": []}
    data["edges"] = [e for e in data["edges"] if (e["from"], e["to"]) != (frm, to)]
    data["edges"].append({"from": frm, "to": to, "via": via, "run": run_id,
                          "seen": time.strftime("%Y-%m-%d")})
    p.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return True


def load_bot(name: str):
    """The bot module, executed fresh from its file (no import cache): a revision runs as is."""
    path = BOTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"gamelab_bot_{name}_{time.time_ns()}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Pilot:
    def __init__(self, game, run_id: str = "", explore: bool = False, forget=()):
        self.game = game
        self.run_id = run_id
        self.explore = explore               # an exploration run: new transitions go to learned.json
        self.forget = {tuple(e) for e in forget}   # edges this run treats as unknown
        self.log: list[Result] = []          # every intent's result, in order

    # ---- plumbing -----------------------------------------------------------

    def cmd(self, *args, timeout: float = 15) -> dict:
        return self.game.gl_cmd(*args, timeout=timeout)

    def _intent(self, intent: str, *args, until=(), timeout: float = 30) -> Result:
        names = check_until(until)
        extra = [f"until={','.join(names)}"] if names else []
        start = len(self.game.gl)
        reply = self.cmd("pilot", intent, *args, *extra, f"timeout={int(timeout * 1000)}")
        self.last_accept = reply
        if intent == "exit" and reply.get("ok"):
            self.last_exit_accept = reply     # the exit's anchor/stand point, for the bot's probes
        if not reply.get("ok"):
            return self._done(Result("failed", reply.get("error", "refused"), intent, reply.get("id", "")))
        cid = reply["id"]
        t_accept = time.time()
        stall_at_accept = getattr(self.game, "stall_s", 0)
        end = time.time() + timeout + 10            # the engine times the intent; this is the backstop
        seen = start
        while time.time() < end:
            self.game.pump()
            for obj in self.game.gl[seen:]:
                if obj.get("ev") == "pilot" and obj.get("id") == cid:
                    return self._done(Result(obj["result"], obj.get("reason", ""), intent, cid, obj.get("tick"), obj))
                if obj.get("ev") == "boot" and not obj.get("_preload"):
                    # a level load: the script module (and the intent with it) is gone
                    if intent == "exit" or (intent == "loot" and "exit" in args):
                        return self._done(Result("done", "level_changed", intent, cid, None, obj))
                    return self._done(Result("interrupted", "level_changed", intent, cid, None, obj))
            seen = len(self.game.gl)
            if not self.game.alive():
                return self._done(Result("failed", "game exited", intent, cid))
            time.sleep(0.05)
        # The backstop is wall clock, the engine's timeout game time: a frame the scripts hold
        # (harness.stall) runs the first and not the second. Say so before stopping, and keep the
        # stop's outcome. cube-run 20261018-222736: loot c69 (480 s) hit this with 145 s of engine
        # ms against ~490 s of wall, the stop c70 got no reply inside a stall, and the engine
        # loop ran on (c69.75-.79) alongside the next bot's intents.
        last = next((o for o in reversed(self.game.gl[start:])
                     if str(o.get("id", "")) == cid or str(o.get("id", "")).startswith(cid + ".")), None)
        note = dict(intent=intent, id=cid, wall_s=round(time.time() - t_accept, 1), timeout_s=timeout,
                    stall_s=getattr(self.game, "stall_s", 0) - stall_at_accept,
                    silent_s=self.game.game_silent_s() if hasattr(self.game, "game_silent_s") else None)
        if last is not None:
            note.update(last_ev=last.get("ev") or "reply", last_id=last.get("id"), last_ms=last.get("ms"),
                        last_tick=last.get("tick"), last_t=last.get("_t"))
        # stop until the engine confirms nothing is left: a stop typed inside a stall can go
        # unanswered, and a loop left live drives the player beside the next bot's intents
        live = None
        for attempt in range(1, 5):
            try:
                r = self.cmd("pilot", "stop", timeout=30)
                note.update(stop="ok" if r.get("ok") else "refused", stopped=r.get("stopped"), stop_attempts=attempt)
                st = self.cmd("pilot", "status", timeout=30)
                live = [x for x in (st.get("loot"), st.get("intentId")) if x]
                if not live:
                    break
            except Exception as e:                   # noqa: BLE001 - retried, then reported
                note.update(stop="error", stop_error=str(e)[:200], stop_attempts=attempt)
                live = None
        note.update(stop_confirmed=live == [], still_live=live)
        self.game.note("pilot_backstop", **note)
        reason = "no end event from the engine"
        if live != []:
            reason += "; the stop was not confirmed (" + (",".join(live) if live else "no reply") + " may still run)"
        return self._done(Result("timeout", reason, intent, cid))

    def _done(self, r: Result) -> Result:
        self.log.append(r)
        self.game.note("pilot_result", intent=r.intent, id=r.id, result=r.result, reason=r.reason, tick=r.tick)
        return r

    # ---- intents (blocking) -------------------------------------------------

    def move(self, x, y, tol=10, **kw) -> Result:
        return self._intent("move", x, y, tol, **kw)

    def path_to(self, x, y, tol=10, **kw) -> Result:
        return self._intent("path_to", x, y, tol, **kw)

    def attack(self, unit="nearest", **kw) -> Result:
        return self._intent("attack", unit, **kw)

    def kite(self, unit="nearest", rng=70, focus=False, **kw) -> Result:
        """focus: switch to a caster or turret in sight (Pilot.as FocusCaster)."""
        return self._intent("kite", unit, rng, *(["focus"] if focus else []), **kw)

    def use(self, unit=None, **kw) -> Result:
        return self._intent("use", *([unit] if unit is not None else []), **kw)

    def potion(self, **kw) -> Result:
        return self._intent("potion", **kw)

    def wait(self, ms, **kw) -> Result:
        return self._intent("wait", ms, **kw)

    def exit(self, timeout: float = 60, **kw) -> Result:
        """Take the nearest level exit. On arrival in a new place, learn the edge."""
        here = self.scan(50)
        before = here.get("place", "?")
        r = self._intent("exit", timeout=timeout, **kw)
        if r.ok:
            after = self.arrived(90)
            acc = getattr(self, "last_accept", {}) or {}
            via = {"kind": "exit", "exit_x": round(acc.get("ux", acc.get("gx", 0))), "exit_y": round(acc.get("uy", acc.get("gy", 0))),
                   "stand_x": round(acc.get("ax", 0)), "stand_y": round(acc.get("ay", 0))}
            new = after != "?" and not known_edge(before, after, self.forget)
            r.event = dict(r.event, place_from=before, place_to=after, new_edge=new,
                           learned=learn_edge(before, after, via, self.run_id, self.forget) if new and self.explore else False)
            self.game.note("pilot_travel", place_from=before, place_to=after, new_edge=new,
                           learned=r.event["learned"], explore=self.explore, graph=graph_revision())
        return r

    def travel(self, place: str, x=None, y=None, timeout: float = 120, **kw) -> Result:
        """path_to(level, point): reach `place` through the travel graph, then (x, y) on it.
        A transition the graph does not know is no_route, returned at once; the bot never
        wanders in search of one. Exploration runs use exit() to learn new edges."""
        here = self.scan(50).get("place", "?")
        if here != place:
            if not known_edge(here, place):
                r = Result("no_route", f"no known transition {here} -> {place} (travel graph {graph_revision()})",
                           "travel", "")
                return self._done(r)
            r = self.exit(timeout=timeout, **kw)
            if not r.ok:
                return r
            if r.event.get("place_to") != place:
                return self._done(Result("failed", f"the exit led to {r.event.get('place_to')}, not {place}",
                                         "travel", r.id, event=r.event))
            if x is None:
                return r
        if x is None:
            return self._done(Result("done", "already there", "travel", ""))
        return self.path_to(x, y, **kw)

    def arrived(self, timeout: float = 90) -> str:
        """After a level change: wait for the new level's heartbeat, then for the player to
        spawn (scan answers), and return the new place."""
        start = len(self.game.gl)
        end = time.time() + timeout
        while time.time() < end:
            self.game.pump()
            if any(o.get("ev") == "hb" and o.get("phase") in ("mission", "town") for o in self.game.gl[start:]):
                sc = self.scan(50)
                if sc.get("ok"):
                    return sc.get("place", "?")
            time.sleep(0.5)
        return "?"

    # ---- eyes and control (immediate) --------------------------------------

    def scan(self, radius=300) -> dict:
        return self.cmd("scan", radius)

    def status(self) -> dict:
        return self.cmd("pilot", "status")

    def pause(self) -> dict:
        return self.cmd("pilot", "pause")

    def resume(self) -> dict:
        return self.cmd("pilot", "resume")

    def step(self, frames=1) -> dict:
        return self.cmd("pilot", "step", frames)

    def target(self, unit) -> dict:
        return self.cmd("pilot", "target", unit)

    def stop(self) -> dict:
        return self.cmd("pilot", "stop")

    def reflex(self, potion=None, fire=None, dodge=None, traps=None) -> dict:
        """Standing orders the engine runs every frame, in and between intents (no round trip):
        potion=<hp%> drinks below it, fire=<radius> aims and fires at the nearest enemy,
        dodge=<radius> sidesteps enemy projectiles seen within it ("dodge" events).
        "off" (or 0) turns one off; None leaves it as is. traps=weave|gate|dodge|none: how trap
        hazards are met (Pilot.as g_trapMode, default weave; "trap_wait"/"trap_go" events)."""
        args = [f"{k}={'off' if not v or v == 'off' else v}"
                for k, v in (("potion", potion), ("fire", fire), ("dodge", dodge)) if v is not None]
        if traps is not None:
            args.append(f"traps={traps}")
        return self.cmd("pilot", "reflex", *args)

    def state(self) -> dict:
        return self.cmd("state")

    def loot(self, radius=1500, prio=None, timeout: float = 420, exit: bool = False) -> Result:
        """The floor's reward loop, in-engine (Pilot.as LootFrame): visit every chest, sphere,
        trinket picker, imp, thunderbird, blueprint and dropped item within radius, nearest
        first, answering each window by `prio`. One gl command for the whole loop, so the
        console opens once; per-visit "loot_visit" / "loot_menu" events land in gl.jsonl.
        exit=True: then take the nearest exit in the same command. Success is the next
        level's boot ("done", "level_changed"; call arrived() for the place); a failed exit
        ends the loop "failed" with reason "exit <result>: ..."."""
        args = [radius] + ([f"prio={','.join(prio)}"] if prio else []) + (["exit"] if exit else [])
        return self._intent("loot", *args, timeout=timeout)

    def lootmap(self, radius=8000, route=False) -> dict:
        """Every reward still on the floor (Pilot.as VerbLootmap): usable chests, spheres,
        pickers..., items on the ground (trinkets marked), unbroken secret walls, material
        piles. route=True also asks whether the pilot's `use` routing reaches each usable."""
        return self.cmd("lootmap", radius, *(["route"] if route else []), timeout=90)

    def place_near(self, unit, max_r=160, reach=False) -> dict:
        """Measurement only, like teleport: put the player on the open point nearest a unit.
        reach=True: only a point routable from where the player stands."""
        return self.cmd("place_near", unit, max_r, *(["reach"] if reach else []))

    def hit_mark(self) -> int:
        """A mark for hit_summary: the live [GL] hit events seen so far."""
        return len(self.game.gl)

    def hit_summary(self, mark: int = 0) -> dict:
        """Every hit printed since `mark` (gamelab-pilot Hits.as "hit" events), grouped by kind,
        source and intent. Unlike `gl hits` this survives a level load, which clears the
        in-engine list (cube-run 20261018-192025: barracks_1's floor_looter read 0 after its exit).
        DoT ticks with an attacker are not printed, so they are missing here."""
        hits = [e for e in self.game.gl[mark:] if e.get("ev") == "hit"]
        out = {"hits": len(hits), "landed": 0, "avoided": 0, "damage": 0, "byKind": {}, "bySource": {}, "byIntent": {}}
        for h in hits:
            landed = bool(h.get("landed"))
            dmg = h.get("dmg", 0) if landed else 0
            out["landed" if landed else "avoided"] += 1
            out["damage"] += dmg
            src = f"{h.get('src')}|{h.get('kind')}"
            for group, key in (("byKind", h.get("kind")), ("bySource", src), ("byIntent", h.get("intent"))):
                g = out[group].setdefault(key, {"hits": 0, "landed": 0, "damage": 0, "max": 0})
                g["hits"] += 1
                g["landed"] += landed
                g["damage"] += dmg
                g["max"] = max(g["max"], dmg)
        return out

    def run_state(self) -> dict:
        """The run's build state: trinkets, temp skills, gear, run buffs, elixirs, materials."""
        return self.cmd("run")

    def menu(self, func: str = "auto", prio=None) -> dict:
        """Answer the top window in-engine through its own OnFunc: a dialog's "yes", or the
        tri-pick (skill sphere, trinket picker) whose id ranks first in `prio` (a build's
        skill/trinket id prefixes, best first). The reply lists the choices and the answer."""
        args = [func] + ([f"prio={','.join(prio)}"] if prio else [])
        return self.cmd("pilot", "menu", *args)

    def start(self, intent: str, *args, until=(), timeout: float = 30) -> dict:
        """Non-blocking: send an intent and return the accept reply (for pause/step/target)."""
        names = check_until(until)
        extra = [f"until={','.join(names)}"] if names else []
        return self.cmd("pilot", intent, *args, *extra, f"timeout={int(timeout * 1000)}")

    def wait_end(self, cid: str, timeout: float = 30) -> Result:
        obj = self.game.wait_gl(lambda o: o.get("ev") == "pilot" and o.get("id") == cid, timeout)
        if obj is None:
            return self._done(Result("timeout", "no end event", "", cid))
        return self._done(Result(obj["result"], obj.get("reason", ""), obj.get("intent", ""), cid, obj.get("tick"), obj))
