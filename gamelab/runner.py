"""Inner GameLab runner: materialize the scenario's fixture, run its steps, score them.
Started by gamelab/launcher.py on the hidden desktop after preflight; never run directly
on the user's desktop.

    python -m gamelab.runner <scenario.json> <results dir> --mode lab

Writes <results>/inner.json (assertions, fixture, live verification) and gl.jsonl.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
from gamelab import env, hps, logparse, loot, winproc  # noqa: E402
from gamelab.session import CONSOLE_ECHO, Game, GameError  # noqa: E402
from gamelab import pilot as pilotlib  # noqa: E402
from gamelab import ui  # noqa: E402
import pin_build  # noqa: E402

FIXTURES = REPO / "gamelab" / "fixtures"
CACHE = FIXTURES / "cache"

# a plan scenario's steps, run in-engine by gamelab-pilot Plan.as: written before the boot,
# emptied before every fixture build and after the run (an empty plan runs nothing)
PLAN_FILE = REPO / "mods" / "gamelab-pilot" / "scripts" / "GameLab" / "PlanData.as"
PLAN_HEAD = ("// The plan a GameLab plan scenario runs (Plan.as). gamelab/runner.py writes this file before\n"
             "// the scenario's boot and empties it again after the run; empty, no plan runs.\n"
             "namespace GameLab\n{\n")
PLAN_EMPTY = PLAN_HEAD + "\tarray<string> PLAN_LINES;\n}\n"
# the step kinds a plan scenario may have: none of them types into the game console, which
# opens over the game and pauses it (the user's report on watch run 20261018-235249)
PLAN_STEP_KINDS = {"plan_wait", "shot", "shot_diff", "shot_changed", "shot_tint", "log_has", "log_lacks",
                   "mark", "log_clean", "sleep", "minimize"}


def write_plan(lines: list[str]) -> None:
    for line in lines:
        if "\n" in line or "\r" in line:
            raise GameError(f"a plan line holds a line break: {line!r}")
    body = ",\n".join('\t\t"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"' for x in lines)
    text = PLAN_HEAD + "\tarray<string> PLAN_LINES = {\n" + body + "\n\t};\n}\n" if lines else PLAN_EMPTY
    PLAN_FILE.write_text(text, encoding="utf-8", newline="\n")


class RunTimeout(GameError):
    """The scenario ran past its own deadline: verdict TIMEOUT, not FAIL."""


def dotted(obj, path: str):
    """Resolve "a.b.0.c" through dicts and lists; a KeyError instance when missing."""
    for part in path.split("."):
        if isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        elif isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return KeyError(path)
    return obj


SAVED_REF = re.compile(r"\{\$([\w.]+)\}")


def subst(value, saved: dict):
    """Replace each {$name.dotted.path} in a step argument with that saved reply's value
    (e.g. a unit id from a "near" reply handed to "pilot use"); a missing one is an error."""
    if not isinstance(value, str):
        return value

    def one(m):
        got = dotted(saved, m.group(1))
        if isinstance(got, KeyError):
            raise GameError(f"no saved value {m.group(1)!r} for {value!r}")
        return str(int(got)) if isinstance(got, float) and got.is_integer() else str(got)
    return SAVED_REF.sub(one, value)


def check(reply: dict, expect: dict) -> list[str]:
    """Mismatches between a [GL] reply and {dotted.path: value}. A value {"between": [lo, hi]}
    matches any number in that closed range (positions of units that move on their own);
    {"match": regex} a string it searches; {"not": v} anything but v (a missing path too);
    {"in": [v, ...]} any of those values."""
    bad = []
    for path, want in expect.items():
        got = dotted(reply, path)
        shown = '<missing>' if isinstance(got, KeyError) else repr(got)
        if isinstance(want, dict) and "between" in want:
            lo, hi = want["between"]
            if not isinstance(got, (int, float)) or not lo <= got <= hi:
                bad.append(f"{path}: want {lo}..{hi}, got {shown}")
            continue
        if isinstance(want, dict) and "match" in want:
            if not isinstance(got, str) or not re.search(want["match"], got):
                bad.append(f"{path}: want /{want['match']}/, got {shown}")
            continue
        if isinstance(want, dict) and "not" in want:
            if got == want["not"]:
                bad.append(f"{path}: want anything but {want['not']!r}, got {shown}")
            continue
        if isinstance(want, dict) and "in" in want:
            if isinstance(got, KeyError) or got not in want["in"]:
                bad.append(f"{path}: want one of {want['in']!r}, got {shown}")
            continue
        if isinstance(got, KeyError) or got != want:
            bad.append(f"{path}: want {want!r}, got {'<missing>' if isinstance(got, KeyError) else repr(got)}")
    return bad


class Run:
    def __init__(self, scenario: dict, results: Path, mode: str):
        self.scenario, self.results, self.mode = scenario, results, mode
        self.assertions: list[dict] = []
        self.passes = 0
        self.live: list[dict] = []
        self.game: Game | None = None        # the running game, finished by run() whatever happens
        self.out: dict = {}                     # inner.json, rewritten after every assertion
        self.menu: dict | None = None           # the probe's reply at the main menu (probe_menu)
        self.recipe: dict = {}
        self.extra: list[str] = []
        self.plan: list[dict] | None = None     # the plan runner's steps (run() sets them)
        # the launcher kills the runner at 3x the scenario timeout; stop ourselves first so a
        # timeout still reports what it collected
        self.deadline = time.time() + scenario.get("timeout", 300) * 3 - 30

    def assert_(self, name: str, ok: bool, detail: str = "") -> bool:
        self.assertions.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
        self.flush()
        return ok

    def flush(self, final: bool = False) -> None:
        """Write inner.json now, so a killed runner still leaves what it collected."""
        out = dict(self.out, assertions=self.assertions, live=self.live, passes=self.passes,
                   menu=self.menu, partial=not final)
        tmp = self.results / "inner.json.tmp"
        tmp.write_text(json.dumps(out, indent=1, default=repr), encoding="utf-8")
        # Windows refuses the rename while another process (a reader, the indexer,
        # antivirus) holds inner.json open: retry briefly (gambler-reroll 20261020-115933)
        for attempt in range(20):
            try:
                tmp.replace(self.results / "inner.json")
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)

    # ---- one boot of the game ----------------------------------------------

    def boot(self, expect_mods: bool, probe_menu: bool = False) -> Game:
        self.passes += 1
        game = Game(self.results, self.mode)
        # "transport": "console" (the console-* measurement scenarios only): every line typed
        # into the console, exempt from check_console
        game.transport = self.scenario.get("transport", game.transport)
        self.game = game
        game.start()
        try:
            if not game.wait_log("Started menu level", 90):
                raise GameError("main menu never loaded")
            # scripts compile before the menu: a mod that does not compile stops every mod script,
            # the probe included, so say so now rather than wait a minute for a boot event
            # (chest-watch 20261018-153312: 84 s to the same answer)
            if logparse.compile_failed(game.read_log()):
                raise GameError("mod scripts failed to compile")
            live = game.verify_live()
            self.live.append(live)
            if not (live["image_in_gamelab"] and live["known_folder_hooked"]
                    and (self.mode != "lab" or (live["in_job"] and live["child_of_runner"]))):
                raise GameError(f"live process not isolated: {live}")
            time.sleep(1.0)
            if probe_menu:
                # the menu side of the menu -> session boundary: does the probe answer here?
                try:
                    self.menu = game.gl_cmd("ping", timeout=8, via="console")
                except GameError as e:
                    self.menu = {"error": str(e)}
                game.note("menu_probe", reply=self.menu)
            # main menu -> Singleplayer / Continue. A posted Enter can be lost in watch mode
            # (20261017-195821 and -200812: no "Starting session" ever followed it while the
            # human was using other windows), so it is confirmed in the log and re-sent. With the
            # whole mod stack the menu takes Enter only after ~23 s (demo-firearms
            # 20261019-145828 and -150050: three tries by 18 s, all lost), so it keeps trying for 60 s.
            # Watch mode sends keys through the shim's SDL_PollEvent hook instead (session
            # shim_input), which needs no focus: the focus nudge only for a run without it.
            # The window is clickable from the menu on, so the human may play along.
            if self.mode == "watch":
                self.out.setdefault("first_frame_at", time.time())   # the menu is drawing
                game.note("allow_activation", **winproc.allow_activation(game.window()))
            if os.environ.get("GAMELAB_SIM_BLUR") == "1":
                # measurement: what Windows sends SDL when the user works in another window and
                # moves the mouse across the game's (WM_ACTIVATE inactive, WM_KILLFOCUS,
                # WM_MOUSEMOVE then WM_MOUSELEAVE), so lab can reproduce watch-mode input loss
                h = game.window()
                winproc.u32.PostMessageW(h, 0x0200, 0, (300 << 16) | 400)   # WM_MOUSEMOVE
                time.sleep(0.1)
                winproc.u32.PostMessageW(h, 0x02A3, 0, 0)                   # WM_MOUSELEAVE
                winproc.u32.PostMessageW(h, 0x0006, 0, 0)                   # WM_ACTIVATE, WA_INACTIVE
                winproc.u32.PostMessageW(h, 0x0008, 0, 0)                   # WM_KILLFOCUS
                time.sleep(0.5)
                game.note("sim_blur")
            give_up = time.time() + 60
            for attempt in range(30):
                if time.time() > give_up:
                    break
                if self.mode == "watch" and not game.shim_input:
                    winproc.sdl_focus(game.window())
                    time.sleep(0.2)
                # GAMELAB_MENU_CONTINUE=1 (measurement): no Enter, straight to menu-continue below
                if not (expect_mods and os.environ.get("GAMELAB_MENU_CONTINUE") == "1"):
                    game.key("enter")
                end, started = time.time() + 5, False
                while not started and time.time() < end:
                    started = bool(re.search(r"\] Starting session\s*$", game.read_log(), re.M))
                    time.sleep(0.25)
                if started:
                    break
                game.note("enter_lost", attempt=attempt + 1)
                if expect_mods:
                    # the keys arrive but Enter presses nothing: a mouse that passed over the
                    # watch-mode window put the menu in mouse mode (chest-watch 20261018-172146:
                    # three Enters lost, a typed `gl ping` answered). The menu button's own call
                    # (gamelab-hands menu-continue: ContinueGame) does not depend on the mode
                    try:
                        game.note("menu_continue", reply=game.gl_cmd("menu-continue", timeout=8, via="console"))
                    except GameError as e:
                        game.note("menu_continue", error=str(e))
                    end = time.time() + 5
                    while not started and time.time() < end:
                        started = bool(re.search(r"\] Starting session\s*$", game.read_log(), re.M))
                        time.sleep(0.25)
                    if started:
                        break
            if expect_mods:
                if game.wait_gl(lambda o: o.get("ev") == "boot", 60) is None:
                    raise GameError("gamelab-probe never booted (mods not enabled, or a script error)")
            elif not game.wait_log("SHOWING PickCharacterWindow", 60):
                raise GameError("session never reached PickCharacterWindow")
        except GameError as e:
            # a mod compile error stops every mod script, the probe included: name it
            errors = logparse.errors_in(game.read_log())
            self.finish(game)                      # stop the game, keep its logs, assert its exit
            raise GameError(f"{e}" + (f"; script errors: {'; '.join(errors[:5])}" if errors else "")) from None
        return game

    def finish(self, game: Game) -> None:
        code = game.stop()
        logs = self.results / "logs"
        logs.mkdir(exist_ok=True)
        shutil.copy2(game.log_path, logs / f"pass{self.passes}.HWR2.exe.log")
        self.check_console(game)
        shim = game.game_dir / "gamelab_capture.log"
        if shim.exists():
            shutil.copy2(shim, logs / f"pass{self.passes}.shim.log")
        game.close()
        self.game = None
        self.assert_(f"pass {self.passes} exited cleanly", code == 0, f"exit code {code}")

    def check_console(self, game: Game) -> None:
        """Every pass: nothing typed into the console once the session started. An open
        console pauses the game, so a playerbot never opens it (gamelab/session.py inbox).
        The main menu is left out: no module ticks there, so its fallbacks (the menu probe,
        menu-continue) type theirs, and nothing is running to pause. A scenario with
        "transport": "console" measures the console itself and is exempt, stamped."""
        typed = session_console_lines(game.read_log())
        # the paused fallback (Game.gl) types into a game that is stopped already: allowed
        # (weaponswap-guards 20261020-124248: two gear-swap probes behind the pause menu)
        paused = [t for t in typed if (t.split() + ["", ""])[1] in getattr(game, "paused_fallbacks", ())]
        typed = [t for t in typed if t not in paused]
        row = {"pass": self.passes, "console_lines": len(typed), "first": typed[:5], "paused_fallback": len(paused),
               "inbox_sent": game.inbox_sent, "inbox_resends": game.inbox_resends, "console_typed": game.console_typed,
               "transport": game.transport}
        self.out.setdefault("console", []).append(row)
        if self.scenario.get("transport") == "console" or game.transport == "console":
            self.out["console_exempt"] = True
            return
        self.assert_(f"pass {self.passes}: nothing typed into the game console in session",
                     not typed, f"{len(typed)} lines: " + "; ".join(typed[:5]))

    # ---- fixtures ------------------------------------------------------------

    def materialize(self, name: str) -> dict:
        recipe = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        build = pin_build.live()["build_id"]
        # a changed recipe, or a change to the GameLab mods whose verbs build it, is a
        # different fixture
        h = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode())
        for mod in sorted(recipe.get("binary_edits", {}).get("enable_mods", [])):
            root = REPO / "mods" / mod
            for f in sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []:
                h.update(f.relative_to(REPO).as_posix().encode())
                h.update(f.read_bytes())
        digest = h.hexdigest()[:8]
        cache = CACHE / f"{name}.{build}.{digest}"
        saves = env.GAME / "saves"
        info = {"name": name, "cache_key": cache.name, "recipe": recipe}
        if recipe.get("slot", 0) != 0:
            raise GameError("lab profile uses g_save_slot 0; fixture slots other than 0 are not supported")
        if saves.exists():
            shutil.rmtree(saves)
        if cache.is_dir() and any(cache.glob("*.hps")):
            shutil.copytree(cache, saves)
            info["cache"] = "hit"
            return info
        info["cache"] = "miss"
        # pass 1: the game writes a fresh, empty profile (null-save session, then a clean quit)
        game = self.boot(expect_mods=False)
        self.finish(game)
        save = hps.current_save(0, saves)
        if save is None:
            raise GameError("pass 1 wrote no profile")
        # the one binary edit the game cannot do in-game: enable the GameLab mods
        mods = recipe["binary_edits"]["enable_mods"]
        hps.enable(save, mods)
        # pass 2: create the character with the game's own functions, let it reach town, quit
        game = self.boot(expect_mods=True)
        ch = recipe["character"]
        # the character menu has to be up: `char` sent on the boot line, before the first
        # heartbeat, answered "no local player record" (fixture-ranger 20261017-163135)
        if game.wait_gl(lambda o: o.get("ev") == "hb" and o.get("phase") == "no_character", 60) is None:
            raise GameError("the character menu never came up (no 'no_character' heartbeat)")
        reply = game.gl_cmd("char", ch["class"], ch["name"])
        if not reply.get("ok"):
            raise GameError(f"char failed: {reply}")
        if game.wait_gl(lambda o: o.get("ev") == "hb" and o.get("phase") == "town", 60) is None:
            raise GameError("new character never reached town")
        # recipe "setup": more fixture verbs (gamelab-hands; each mirrors a game path), then
        # the game's own save, so the next session loads this town and not a null one
        for v in recipe.get("setup", []):
            reply = game.gl_cmd(v["verb"], *v.get("args", []))
            bad = check(reply, v.get("expect", {"ok": True}))
            if bad:
                raise GameError(f"fixture setup {v['verb']} failed: {'; '.join(bad)}")
        if recipe.get("setup") or recipe.get("save_town"):
            if not game.gl_cmd("save").get("ok"):
                raise GameError("fixture save failed")
        self.finish(game)
        if cache.exists():
            shutil.rmtree(cache)
        shutil.copytree(saves, cache)
        return info

    def enter_fixture(self, recipe: dict, extra_mods: list[str], *,
                      choice: str | None = None, readback: dict | None = None,
                      relaunch: bool = False) -> Game:
        if choice not in (None, "town", "resume"):
            raise GameError(f"unsupported restart choice: {choice!r}")
        if readback is not None and not isinstance(readback, dict):
            raise GameError("restart readback must be a mapping")
        expected = {**recipe["readback"], **(readback or {})}
        game = self.boot(expect_mods=True, probe_menu=self.scenario.get("probe_menu", False))
        hb = game.wait_gl(lambda o: o.get("ev") == "hb", 30)
        self.out.setdefault("first_frame_at", time.time())   # watch mode's focus window ends here
        if self.mode == "watch":
            # from here on a human click may activate the game window (WS_EX_NOACTIVATE off)
            game.note("allow_activation", **winproc.allow_activation(game.window()))
        if self.plan is not None:
            return self.enter_plan(game, recipe, extra_mods)
        selection = None
        if hb and hb.get("phase") == "no_character":
            reply = game.gl_cmd("pick", 0, *([choice] if choice is not None else []))
            selection = reply
            if not reply.get("ok"):
                raise GameError(f"pick failed: {reply}")
            if choice == "resume" and (reply.get("choice") != "resume" or not reply.get("run")):
                raise GameError(f"no saved run to resume: {reply}")
        elif choice is not None:
            raise GameError("explicit restart choice requires the character selection window")
        if relaunch:
            # a relaunch: the session the last pass saved, not the fixture (its class, skills and
            # level moved on); the mods and the profile are still checked
            if game.wait_gl(lambda o: o.get("ev") == "hb" and o.get("phase") in ("town", "mission"), 60) is None:
                raise GameError("the relaunched session never reached town or a mission")
            mods = game.gl_cmd("mods")
            enabled = sorted(m["id"] for m in mods.get("mods", []) if m.get("enabled"))
            want = sorted(recipe["binary_edits"]["enable_mods"] + extra_mods)
            self.assert_("relaunch: enabled mods unchanged", enabled == want, f"enabled={enabled}")
            want = self.profile_cvars()
            self.check_cvars(want, game.gl_cmd("cvars", *want).get("cvars", {}))
            return game
        self.out.setdefault("fixture_entries", []).append(
            {"choice": choice, "selection": selection, "readback": expected})
        if game.wait_gl(lambda o: o.get("ev") == "hb" and o.get("phase") == expected["phase"], 60) is None:
            raise GameError(f"never reached phase {expected['phase']}")
        # every recipe field is read back through the probes; a mismatch fails the run
        # recipe fields beyond the character (setup verbs) are read back through their own
        # probes; all of them, `state` and `mods` in one or two typed lines (gl_multi)
        probes = recipe.get("readback_probes", [])
        replies = game.gl_multi([["state"]] + [[rb["verb"], *rb.get("args", [])] for rb in probes] + [["mods"]])
        state, mods = replies[0], replies[-1]
        bad = check(state, expected)
        for rb, reply in zip(probes, replies[1:-1]):
            bad += [f"{rb['verb']}: {b}" for b in check(reply, rb["expect"])]
        self.assert_("fixture readback", not bad, "; ".join(bad))
        enabled = sorted(m["id"] for m in mods.get("mods", []) if m.get("enabled"))
        want = sorted(recipe["binary_edits"]["enable_mods"] + extra_mods)
        self.assert_("enabled mods are exactly the fixture's + the scenario's", enabled == want, f"enabled={enabled}")
        # preflight assertion 3: the profile actually loaded, read from the running game.
        # Every numeric / boolean cvar of the profile (false/true = 0/1); v_resolution is
        # checked on the captured frame size instead (the shot steps).
        want = self.profile_cvars()
        self.check_cvars(want, game.gl_cmd("cvars", *want).get("cvars", {}))
        if bad:
            raise GameError("fixture readback failed")
        return game

    def profile_cvars(self) -> dict:
        """Every numeric / boolean cvar of the mode's profile (false/true = 0/1); v_resolution
        is checked on the captured frame size instead (the shot steps)."""
        profile = env.cvars((env.SETTINGS / self.mode / "HWR2.exe.cfg").read_text())
        want = {}
        for k, v in profile.items():
            v = {"false": "0", "true": "1"}.get(v.lower(), v)
            try:
                want[k] = float(v)
            except ValueError:
                pass
        return want

    def check_cvars(self, want: dict, loaded: dict) -> None:
        wrong = [f"{k}={loaded.get(k)} (profile {want[k]})" for k in want
                 if loaded.get(k) is None or abs(loaded[k] - want[k]) > 1e-3]
        muted = all(loaded.get(k) == 0 for k in want if k.startswith("snd_volume"))
        self.assert_(f"{self.mode} profile loaded ({len(want)} cvars)" + (" (muted, low graphics)" if self.mode == "lab" else ""),
                     not wrong and (self.mode != "lab" or muted), "; ".join(wrong))

    # ---- plan scenarios (no console) -----------------------------------------

    def plan_steps(self, recipe: dict) -> list[dict]:
        """The plan as run: the fixture's character pick and readback first (what enter_fixture
        types for other scenarios), then the scenario's "plan". Each {"at", "name", "line"}."""
        probes = recipe.get("readback_probes", [])
        subs = [["state"]] + [[rb["verb"], *rb.get("args", [])] for rb in probes] + [["mods"]]
        steps = [{"at": "phase:no_character", "name": "pick", "line": "?pick 0"},
                 {"at": "town", "name": "fixture readback",
                  "line": "multi " + " + ".join(" ".join(map(str, c)) for c in subs), "_subs": len(subs)},
                 {"at": "town", "name": "profile cvars", "line": "cvars " + " ".join(self.profile_cvars())}]
        for i, ps in enumerate(self.scenario["plan"]):
            line = ps["do"] if isinstance(ps["do"], str) else " ".join(map(str, ps["do"]))
            steps.append(dict(ps, at=ps.get("at", "*"), name=ps.get("name", line),
                              line=("?" if ps.get("optional") else "") + line))
        for st in steps:
            if any("|" in str(st[f]) for f in ("at", "name", "line")):
                raise GameError(f"a plan step holds a '|': {st}")
        return steps

    def plan_wait(self, game: Game, pred, timeout: float) -> dict | None:
        """The first live (not preloaded) [GL] object matching pred, or the plan's own end
        event if the plan ended first; None on timeout."""
        return game.wait_gl(lambda o: not o.get("_preload") and (pred(o) or o.get("ev") == "plan"),
                            max(1.0, min(timeout, self.deadline - time.time())))

    def step_end(self, game: Game, k: int) -> dict | None:
        for o in game.gl:
            if not o.get("_preload") and o.get("ev") == "plan_step_end" and o.get("k") == k:
                return o
        return None

    def enter_plan(self, game: Game, recipe: dict, extra_mods: list[str]) -> Game:
        """enter_fixture for a plan scenario: the pick, the readback and the profile cvars are
        the plan's first steps (plan_steps), read from the log; nothing is typed."""
        o = self.plan_wait(game, lambda o: o.get("ev") == "plan_step_end" and o.get("k") == 1, 180)
        if o is None or o.get("ev") == "plan":
            raise GameError(f"the plan ended or stalled before the fixture readback: {o}")
        subs = self.plan[1]["_subs"]
        replies = []
        for n in range(subs):
            rid = f"p1.{n}"
            replies.append(next((x for x in game.gl if not x.get("_preload") and x.get("id") == rid), {}))
        probes = recipe.get("readback_probes", [])
        state, mods = replies[0], replies[-1]
        bad = check(state, recipe["readback"])
        for rb, reply in zip(probes, replies[1:-1]):
            bad += [f"{rb['verb']}: {b}" for b in check(reply, rb["expect"])]
        self.assert_("fixture readback", not bad, "; ".join(bad))
        enabled = sorted(m["id"] for m in mods.get("mods", []) if m.get("enabled"))
        want = sorted(recipe["binary_edits"]["enable_mods"] + extra_mods)
        self.assert_("enabled mods are exactly the fixture's + the scenario's", enabled == want, f"enabled={enabled}")
        o = self.plan_wait(game, lambda o: o.get("ev") == "plan_step_end" and o.get("k") == 2, 60)
        if o is None or o.get("ev") == "plan":
            raise GameError(f"the plan ended or stalled before the profile cvars: {o}")
        self.check_cvars(self.profile_cvars(), (o.get("reply") or {}).get("cvars", {}))
        if bad:
            raise GameError("fixture readback failed")
        return game

    def plan_report(self, game: Game) -> None:
        """Wait for the plan's end, then assert it: done, every step's expect, and no line
        typed into the console in this pass."""
        timeout = self.scenario.get("timeout", 300)
        fin = self.plan_wait(game, lambda o: False, timeout)
        steps = []
        for k, st in enumerate(self.plan):
            start = next((i for i, o in enumerate(game.gl) if not o.get("_preload")
                          and o.get("ev") == "plan_step" and o.get("k") == k), None)
            end = self.step_end(game, k)
            stop = game.gl.index(end) if end is not None else len(game.gl)
            hits = [o for o in game.gl[start:stop] if o.get("ev") == "hit" and not o.get("_preload")] if start is not None else []
            landed = [h for h in hits if h.get("landed")]
            row = {"k": k, "name": st["name"], "at": st["at"], "line": st["line"][:200],
                   "started": start is not None, "ok": (end or {}).get("ok"), "result": (end or {}).get("result"),
                   "reason": (end or {}).get("reason"), "ms": (end or {}).get("ms"),
                   "hits": len(hits), "landed": len(landed), "damage": sum(h.get("dmg", 0) for h in landed)}
            steps.append(row)
            if "expect" in st:
                bad = check(end or {}, st["expect"]) if end else ["the step never ended"]
                self.assert_(f"plan step {k} {st['name']}", not bad, "; ".join(bad))
        typed = logparse_console_lines(game.read_log())
        self.out["plan"] = {"end": fin, "steps": steps, "console_lines": typed}
        self.assert_("plan done", fin is not None and fin.get("ev") == "plan" and fin.get("result") == "done",
                     json.dumps(fin)[:400] if fin else "no plan event before the timeout")
        self.assert_("nothing typed into the game console", not typed, "; ".join(typed[:10]))

    # ---- scenario ------------------------------------------------------------

    def step(self, game: Game, s: dict, saved: dict) -> Game:
        """Run one step; returns the game (a new one after "restart")."""
        if time.time() > self.deadline:
            raise RunTimeout(f"scenario deadline passed before step {s}")
        kind = s["do"]
        if kind == "plan_wait":
            # {"end": <step name>} / {"start": <step name>}: that step of the plan; nothing: its end
            if "end" in s or "start" in s:
                ev, name = ("plan_step_end", s["end"]) if "end" in s else ("plan_step", s["start"])
                o = self.plan_wait(game, lambda o: o.get("ev") == ev and o.get("name") == name,
                                   s.get("timeout", self.scenario.get("timeout", 300)))
                ok = o is not None and o.get("ev") == ev and (ev == "plan_step" or bool(o.get("ok")))
                self.assert_(s.get("name", f"plan {'reached' if 'start' in s else 'finished'} {name}"), ok,
                             json.dumps(o)[:300] if o else "timeout")
            else:
                self.plan_wait(game, lambda o: False, s.get("timeout", self.scenario.get("timeout", 300)))
            return game
        if kind == "restart":
            # save -> load context boundary: quit (WM_CLOSE, the game saves) and enter again
            self.finish(game)
            return self.enter_fixture(self.recipe, self.extra, choice=s.get("choice"),
                                      readback=s.get("readback"))
        if kind == "relaunch":
            # Dev Arena [Relaunch] (mods/devarena Relaunch.as): wait for its log line, write the
            # override file from this pass's log (tools/devarena/overrides.py; restored when the
            # run ends), then quit and boot the saved session again, without the fixture readback
            from tools.devarena import overrides
            rx = re.compile(r"\[HWP:devarena\] relaunch (\{.*\})")
            since = saved.get(s["since"], {}).get("log_offset", 0) if "since" in s else 0
            end = time.time() + s.get("timeout", 30)
            while not (hit := rx.search(game.read_log()[since:])) and time.time() < end:
                time.sleep(0.25)
            self.assert_(s.get("name", "relaunch requested"), hit is not None, hit.group(0)[:300] if hit else "not found")
            if hit is None:
                raise GameError("no relaunch line")
            saved[s.get("save_as", "relaunch")] = {"ok": True, **json.loads(hit.group(1))}
            remember_written(self.results, overrides.SVAL)
            log = self.results / "relaunch.HWR2.exe.log"
            log.write_text(game.read_log(), encoding="utf-8")
            code = overrides.main(["sync", "--log", str(log)])
            self.assert_("relaunch: override file synced", code == 0, f"overrides.py sync exit {code}")
            self.finish(game)
            return self.enter_fixture(self.recipe, self.extra, relaunch=True)
        if kind == "overlays":
            # repro playbook 1.3: everything drawn over the world, required empty or expected
            reply = game.gl_cmd("overlays")
            if "save_as" in s:
                saved[s["save_as"]] = reply
            allow = s.get("allow", {})
            extra = [f"window {w}" for w in reply.get("windows", []) if w not in allow.get("windows", [])]
            if reply.get("tutorial") and reply["tutorial"] not in allow.get("tutorial", []):
                extra.append(f"tutorial {reply['tutorial']}")
            extra += [f"announce {a.get('style')}: {a.get('text')!r}" for a in reply.get("announces", [])
                      if a.get("style") not in allow.get("announce_styles", [])]
            if reply.get("bossBar") and not allow.get("bossBar"):
                extra.append("boss bar")
            seen = json.dumps({k: reply.get(k) for k in ("windows", "tutorial", "announces", "bossBar")})
            self.assert_(s.get("name", "overlays empty or expected"), bool(reply.get("ok")) and not extra,
                         ("; ".join(extra) + " | " if extra else "") + seen)
            return game
        if kind == "loot_check":
            # what the loot is, without a seeded RNG: the gain must be one the table can produce
            before = dotted(saved.get(s["than"], {}), s.get("path", "materials"))
            after = dotted(saved.get(s["now"], {}), s.get("path", "materials"))
            gained = ({k: after[k] - before.get(k, 0) for k in after}
                      if isinstance(after, dict) and isinstance(before, dict) else {})
            ok, why = loot.explain(loot.table(s["file"], s["entry"]), gained) if gained else (False, "no before/after replies")
            shown = {k: v for k, v in gained.items() if v}
            self.assert_(s.get("name", f"loot fits {s['entry']}"), ok, f"gained {shown}; {why}")
            return game
        if kind == "gl":
            reply = game.gl_cmd(s["verb"], *[subst(a, saved) for a in s.get("args", [])], timeout=s.get("timeout", 15))
            if "save_as" in s:
                saved[s["save_as"]] = reply
            if "expect" in s:
                bad = check(reply, s["expect"])
                self.assert_(s.get("name", f"gl {s['verb']}"), not bad, "; ".join(bad))
        elif kind == "pilot":
            # one blocking Pilot intent (gamelab/pilot.py); its Result is checked like a reply
            p = pilotlib.Pilot(game, self.results.name, explore=bool(self.scenario.get("explore")),
                                forget=self.scenario.get("forget_edges", []))
            fn = getattr(p, s["call"])
            kw = {k: s[k] for k in ("until", "timeout") if k in s}
            r = fn(*[subst(a, saved) for a in s.get("args", [])], **kw)
            got = r if isinstance(r, dict) else {"result": r.result, "reason": r.reason, "tick": r.tick,
                                                 "intent": r.intent, "event": r.event}
            if "save_as" in s:
                saved[s["save_as"]] = got
            if "expect" in s:
                bad = check(got, s["expect"])
                self.assert_(s.get("name", f"pilot {s['call']}"), not bad, "; ".join(bad) + f" | {got.get('result')}: {got.get('reason')}")
        elif kind == "bot":
            # a bot script (gamelab/bots/<bot>.py, run(pilot) -> dict), loaded fresh from disk;
            # "name" is the assertion's label
            p = pilotlib.Pilot(game, self.results.name, explore=bool(self.scenario.get("explore")),
                                forget=self.scenario.get("forget_edges", []))
            got = pilotlib.load_bot(s["bot"]).run(p, **s.get("kwargs", {}))
            got["intents"] = [{"intent": r.intent, "result": r.result, "reason": r.reason, "tick": r.tick} for r in p.log]
            # Assertion summaries intentionally stay short. Preserve the full returned
            # observations before scoring, including every failed fixed trial.
            result_file = self.results / "bot-results.jsonl"
            with result_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"bot": s["bot"], "kwargs": s.get("kwargs", {}),
                                    "pass": self.passes, "assertion_index": len(self.assertions),
                                    "result": got}, ensure_ascii=False) + "\n")
            self.out["bot_results_file"] = result_file.name
            # the whole result, for tables the 3000-char assertion detail cuts (bot-<name>.json)
            label = re.sub(r"[^A-Za-z0-9_.-]+", "_", s.get("name", f"bot {s['bot']}"))
            try:
                (self.results / f"bot-{label}.json").write_text(json.dumps(got, indent=1, default=str), encoding="utf-8")
            except (OSError, TypeError, ValueError) as e:
                print(f"[note] bot result not saved: {e}", flush=True)
            if "save_as" in s:
                saved[s["save_as"]] = got
            bad = check(got, s.get("expect", {}))
            self.assert_(s.get("name", f"bot {s['bot']}"), not bad, "; ".join(bad) + f" | {got.get('terminal')}")
        elif kind == "write_bot_file":
            # a bot revision while the game runs; restored in run()'s finally like write_mod_file
            f = pilotlib.BOTS / s["path"]
            if f.parent.resolve() != pilotlib.BOTS.resolve():
                raise GameError(f"write_bot_file: {s['path']} is not directly in gamelab/bots/")
            self.remember(f)
            f.write_text(f.read_text(encoding="utf-8").replace(s["replace"], s["with"]), encoding="utf-8")
            self.assert_(s.get("name", f"edited gamelab/bots/{s['path']}"), s["with"] in f.read_text(encoding="utf-8"))
        elif kind == "same_process":
            # {"mark": m} records the game's pid; {"since": m} asserts it is still that process
            # (a revision taken live, no restart in between)
            if "mark" in s:
                saved[s["mark"]] = {"ok": True, "pid": game.proc.pid, "pass": self.passes}
            else:
                was = saved.get(s["since"], {})
                self.assert_(s.get("name", "same game process, no restart"),
                             was.get("pid") == game.proc.pid and was.get("pass") == self.passes,
                             f"pid {was.get('pid')} -> {game.proc.pid}, pass {was.get('pass')} -> {self.passes}")
        elif kind == "wait_phase":
            # a new heartbeat: an old one from before a level change would pass at once
            hb = game.wait_gl(lambda o: o.get("ev") == "hb" and o.get("phase") == s["phase"], s.get("timeout", 60),
                              fresh=True)
            self.assert_(f"phase {s['phase']}", hb is not None)
        elif kind == "shot":
            png = game.shot(s["name"], settle=s.get("settle", True))
            # a real frame (not blank), at the profile's v_resolution (preflight assertion 3's
            # one non-cvar setting is checked here, on the captured frame); "size" ("WxH") is a
            # scenario's own in-session resolution (devarena/res-*)
            res = s.get("size") or env.cvars((env.SETTINGS / self.mode / "HWR2.exe.cfg").read_text()).get("v_resolution", "")
            size = frame_size(png) if png else None
            want = tuple(int(v) for v in res.split("x")) if "x" in res else size
            self.assert_(f"shot {s['name']}", png is not None and colours(png) > 64 and size == want,
                         f"{png.name if png else 'none'} colours={colours(png) if png else 0} size={size} want={want}")
        elif kind == "shot_diff":
            # passive capture tracks game state: between two shots of the same view, the pixels
            # that changed sit in `box` (fractions of the frame: x0, y0, x1, y1) far more densely
            # than anywhere else
            from PIL import Image, ImageChops
            shots = self.results / "shots"
            a = Image.open(shots / f"{s['before']}.png").convert("L")
            b = Image.open(shots / f"{s['after']}.png").convert("L")
            from PIL import ImageFilter
            mask = ImageChops.difference(a, b).point(lambda v: 255 if v > s.get("threshold", 40) else 0)
            # ambient animation (foliage sway) changes scattered single pixels; a min filter
            # (erosion) drops those and keeps solid regions such as a new sprite
            if s.get("denoise", 3):
                mask = mask.filter(ImageFilter.MinFilter(s.get("denoise", 3)))
            w, h = mask.size
            x0, y0, x1, y1 = s["box"]
            box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
            inside = sum(1 for v in mask.crop(box).getdata() if v)
            total = sum(1 for v in mask.getdata() if v)
            area_in = (box[2] - box[0]) * (box[3] - box[1])
            dens_in, dens_out = inside / area_in, (total - inside) / max(1, w * h - area_in)
            ok = inside >= s.get("min_px", 50) and dens_in > s.get("ratio", 10) * dens_out
            self.assert_(s.get("name", f"shot diff {s['before']} -> {s['after']}"), ok,
                         f"changed px inside={inside} outside={total - inside}; density in={dens_in:.4f} out={dens_out:.5f}")
        elif kind == "shot_changed":
            # the renderer agrees with telemetry that the view changed (a new level): most of
            # the frame differs between two shots. Named "shot ...", so a failure while every
            # probe passed makes the run INVALID, not FAIL. Calibrated on 41 pilot-crosslevel runs
            # (luminance diff > 10 on a 160x90 thumbnail): 68-82% of the frame changes when the
            # floor changed; 9-14% when the bot never left floor 0; <= 19% between two shots of
            # one floor
            from PIL import Image, ImageChops
            shots = self.results / "shots"
            a = Image.open(shots / f"{s['before']}.png").convert("L").resize((160, 90))
            b = Image.open(shots / f"{s['after']}.png").convert("L").resize((160, 90))
            changed = sum(1 for v in ImageChops.difference(a, b).getdata() if v > s.get("threshold", 10)) / (160 * 90)
            self.assert_(f"shot changed {s['before']} -> {s['after']}", changed >= s.get("min_frac", 0.4),
                         f"{changed:.0%} of the frame changed, want >= {s.get('min_frac', 0.4):.0%}")
        elif kind == "shot_tint":
            # the engine's nav overlay paints a red grid: the share of strongly red pixels
            # (R exceeds G and B by 50, 160x90 thumbnail) is <= 0.007 on plain town and
            # mission frames and 0.116-0.49 with r_draw_nav_data on (watch-overlays
            # 20261017-190809, floor-soak cut-nav). Frame-to-frame change cannot tell: two
            # plain town frames 0.5 s apart differ in 31% of pixels. Named "shot ...": a
            # failure while the cvars read back on is INVALID
            from PIL import Image
            px = list(Image.open(self.results / "shots" / f"{s['shot']}.png").convert("RGB").resize((160, 90)).getdata())
            red = sum(1 for r, g, b in px if r > g + 50 and r > b + 50) / len(px)
            lo, hi = s.get("min", 0.0), s.get("max", 1.0)
            self.assert_(f"shot tint {s['shot']}", lo <= red <= hi, f"red share {red:.3f}, want {lo}-{hi}")
        elif kind == "assert_more":
            # the numeric values under `path` sum higher in reply `now` than in reply `than`
            # ("now_path" reads `now` at a different path, e.g. a pilot Result's end event)
            def total(name, path):
                v = dotted(saved.get(name, {}), path)
                return sum(x for x in v.values() if isinstance(x, (int, float))) if isinstance(v, dict) else v
            before, after = total(s["than"], s["path"]), total(s["now"], s.get("now_path", s["path"]))
            ok = isinstance(before, (int, float)) and isinstance(after, (int, float)) and after > before
            self.assert_(s.get("name", f"{s['path']} grew"), ok, f"{s['than']}={before} {s['now']}={after}")
        elif kind == "assert_delta":
            # now - than at `path` (numbers): exactly `equals`, within `between`, or one of `in`
            # (a bet that wins, loses or ties: +bet, -bet, 0)
            a = dotted(saved.get(s["than"], {}), s["path"])
            b = dotted(saved.get(s["now"], {}), s.get("now_path", s["path"]))
            ok = isinstance(a, (int, float)) and isinstance(b, (int, float))
            d = b - a if ok else None
            if ok and "equals" in s:
                ok = abs(d - s["equals"]) < 1e-6
            if ok and "between" in s:
                ok = s["between"][0] <= d <= s["between"][1]
            if ok and "in" in s:
                ok = any(abs(d - v) < 1e-6 for v in s["in"])
            want = s.get("equals", s.get("between", s.get("in")))
            self.assert_(s.get("name", f"{s['path']} changed by {want}"), ok,
                         f"{s['than']}={a!r} {s['now']}={b!r} delta={d!r} want={want!r}")
        elif kind == "compare":
            # two saved replies: the `same` paths equal in both, the `differ` paths not
            a, b = saved.get(s["a"], {}), saved.get(s["b"], {})
            bad = [f"{p} changed: {dotted(a, p)!r} -> {dotted(b, p)!r}" for p in s.get("same", [])
                   if repr(dotted(a, p)) != repr(dotted(b, p))]
            bad += [f"{p} did not change: {dotted(a, p)!r}" for p in s.get("differ", [])
                    if repr(dotted(a, p)) == repr(dotted(b, p))]
            self.assert_(s.get("name", f"compare {s['a']} / {s['b']}"), not bad, "; ".join(bad))
        elif kind == "assert_dist":
            # distance between the {x, y} under `path` in replies `a` and `b`, within [min, max]
            pa, pb = dotted(saved.get(s["a"], {}), s["path"]), dotted(saved.get(s["b"], {}), s["path"])
            d = (((pa["x"] - pb["x"]) ** 2 + (pa["y"] - pb["y"]) ** 2) ** 0.5
                 if isinstance(pa, dict) and isinstance(pb, dict) else None)
            ok = d is not None and s.get("min", 0) <= d <= s.get("max", float("inf"))
            self.assert_(s.get("name", f"{s['path']} moved {s.get('min', 0)}..{s.get('max')}"), ok,
                         f"distance {None if d is None else round(d, 1)}")
        elif kind == "sval":
            # datatable export: the engine's parse of one .sval, written as sorted, indented JSON.
            # Multi-entry files are one resource per "<file>:<entry>" (tools/export_datatables.py).
            if "entries" in s:
                data, missing = {}, []
                for e in s["entries"]:
                    reply = game.gl_cmd("sval", f"{s['file']}:{e}", timeout=s.get("timeout", 30))
                    if reply.get("ok"):
                        data[e] = json.loads(reply["chunk"])
                    else:
                        missing.append(e)
                ok = bool(data) and not missing
                error = f"entries the engine does not have: {missing}" if missing else "no entries"
            else:
                reply = game.gl_cmd("sval", s["file"], timeout=s.get("timeout", 30))
                ok = bool(reply.get("ok"))
                data = json.loads(reply["chunk"]) if ok else None
                error = reply.get("error")
            if ok:
                out = REPO / s["dest"] / (s["file"] + ".json")  # a relative dest is under the repo
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            saved.setdefault("sval", {})[s["file"]] = "ok" if ok else error
        elif kind == "write_mod_file":
            # an edit made while the game runs (the reload-mark scenario). GameLab mods only;
            # the original bytes go back in run()'s finally, whatever happens.
            if not re.fullmatch(r"gamelab-[A-Za-z0-9_-]+", s["mod"]):
                raise GameError("write_mod_file is limited to gamelab-* mods")
            base = (REPO / "mods" / s["mod"]).resolve()
            f = (base / s["path"]).resolve()   # real paths: '..' and links cannot leave the mod
            if base not in f.parents:
                raise GameError(f"write_mod_file: {s['path']} escapes mods/{s['mod']}")
            self.remember(f)
            f.write_text(f.read_text(encoding="utf-8").replace(s["replace"], s["with"]), encoding="utf-8")
            self.assert_(s.get("name", f"edited mods/{s['mod']}/{s['path']}"), s["with"] in f.read_text(encoding="utf-8"))
        elif kind == "log_has":
            # a regex in this pass's game log (e.g. a mod's self-check line), waited for
            # ("since": a mark step's name = only the log written after it)
            rx = re.compile(s["pattern"])
            end = time.time() + s.get("timeout", 30)
            since = saved.get(s["since"], {}).get("log_offset", 0) if "since" in s else 0
            while not (hit := rx.search(game.read_log()[since:])) and time.time() < end:
                time.sleep(0.25)
            self.assert_(s.get("name", f"log has /{s['pattern']}/"), hit is not None, hit.group(0) if hit else "not found")
        elif kind == "log_capture":
            # the named groups of the last match of a regex in this pass's game log, saved as
            # {"match": {group: number or text}} under save_as (e.g. a logged x,y for assert_dist)
            rx = re.compile(s["pattern"])
            end = time.time() + s.get("timeout", 30)
            while not (hits := list(rx.finditer(game.read_log()))) and time.time() < end:
                time.sleep(0.25)
            if hits:
                groups = {}
                for k, v in hits[-1].groupdict().items():
                    try:
                        groups[k] = float(v)
                    except (TypeError, ValueError):
                        groups[k] = v
                saved[s["save_as"]] = {"match": groups}
            self.assert_(s.get("name", f"log captures /{s['pattern']}/"), bool(hits),
                         hits[-1].group(0) if hits else "not found")
        elif kind == "retry":
            # level-dependent setups (what a generated floor places): run the inner steps
            # again until a regex shows up in log lines they added, up to `times` attempts.
            # Inner steps assert as usual; only a missing hit after the last attempt fails.
            rx = re.compile(s["until"])
            times = int(s.get("times", 3))
            hit = None
            for attempt in range(1, times + 1):
                start = len(game.read_log())
                for inner in s["steps"]:
                    game = self.step(game, inner, saved)
                end = time.time() + s.get("timeout", 10)
                while not (hit := rx.search(game.read_log()[start:])) and time.time() < end:
                    time.sleep(0.25)
                if hit:
                    break
            self.assert_(s.get("name", f"retry until /{s['until']}/"), hit is not None,
                         f"attempt {attempt}/{times}: " + (hit.group(0) if hit else "not found"))
        elif kind == "log_lacks":
            # a regex that must not appear in this pass's game log (checked when the step runs)
            since = saved.get(s["since"], {}).get("log_offset", 0) if "since" in s else 0
            if s.get("settle"):
                time.sleep(s["settle"])
            hits = [m.group(0) for m in re.finditer(s["pattern"], game.read_log()[since:])]
            self.assert_(s.get("name", f"log lacks /{s['pattern']}/"), not hits, "; ".join(hits[:5]))
        elif kind == "bench_csv":
            # Dev Arena bench lines (tools/devarena/bench.py) since a mark: written as CSV into
            # this run's folder and gamelab/results/bench/, the game's stats re-checked
            from tools.devarena import bench
            since = saved.get(s["since"], {}).get("log_offset", 0) if "since" in s else 0
            text = game.read_log()[since:]
            path, rs = bench.write_csv(text, self.results.name)
            (self.results / "bench.csv").write_bytes(path.read_bytes())
            bad = bench.check_results(text)
            self.assert_(s.get("name", "bench CSV"), len(rs) >= s.get("min_rows", 1) and not bad,
                         f"{len(rs)} rows; " + "; ".join(bad[:5]))
        elif kind == "mark":
            # a point in this pass's log, for a later log_has / log_lacks "since"
            saved[s["name"]] = {"ok": True, "log_offset": len(game.read_log())}
        elif kind == "log_clean":
            # no script errors in files of the mods under test (the game's own baseline ERRs are ignored)
            bad = logparse.errors_in(game.read_log(), s.get("patterns", logparse.OURS), s.get("allow", ()))
            self.assert_(s.get("name", "no script errors in our files"), not bad, "; ".join(bad[:10]))
        elif kind == "printwindow":
            # OS-level capture of the hidden window, compared with the in-process frame taken
            # right after it: mean absolute difference per channel (0 = identical)
            from PIL import Image, ImageChops, ImageStat
            ref = game.shot(s.get("name", "printwindow") + "-ref")
            results = {}
            for flags in s.get("flags", [0, 2]):
                im = winproc.print_window(game.window(), flags)
                if im is None:
                    results[flags] = "PrintWindow failed"
                    continue
                im.save(self.results / "shots" / f"{s.get('name', 'printwindow')}-pw{flags}.png")
                r = Image.open(ref).convert("RGB").resize(im.size) if ref else None
                diff = sum(ImageStat.Stat(ImageChops.difference(im, r)).mean) / 3 if r else None
                results[flags] = {"colours": len(im.resize((64, 36)).getcolors(64 * 36)), "diff": diff}
            saved[s.get("save_as", "printwindow")] = results
            ok = any(isinstance(v, dict) and v["colours"] > 64 and v["diff"] is not None and v["diff"] < s.get("max_diff", 12)
                     for v in results.values())
            if s.get("want") == "blank":       # a pinned measurement: PrintWindow sees nothing here
                ok = all(isinstance(v, dict) and v["colours"] <= 4 for v in results.values()) and ref is not None
            self.assert_(s.get("name", "PrintWindow capture of the hidden window matches the frame"), ok, json.dumps(results))
        elif kind == "minimize":
            self.assert_("window minimized", winproc.minimize(game.window()))
        elif kind == "sleep":
            # in 1 s slices, so a watch demo the player quits doesn't hold the lock for its full sleep
            end = time.time() + s["seconds"]
            while time.time() < end and game.alive():
                time.sleep(min(1.0, max(0.0, end - time.time())))
        elif kind in ("play", "handoff"):
            # the game is the human's from here: the shim stops hiding the real mouse and focus
            # from it (watch arena 20261021-061402: no mouse at all). The shim log's "input
            # handed to the player" line is the proof; "handoff" is the same without the hold
            # "keep_focus" (a scripted test): the mouse is freed, SDL stays told it has focus
            keep = bool(s.get("keep_focus"))
            sent = winproc.shim_handoff(game.window(), keep)
            game.note("handoff", sent=sent, keep_focus=keep)
            if self.mode == "watch":
                self.assert_("input handed to the player", sent)
            if kind == "handoff":
                return game
            # a human session (watch mode): hold until the game is closed, "seconds" or the deadline
            end = min(time.time() + s.get("seconds", 4 * 3600), self.deadline - 30)
            while game.alive() and time.time() < end:
                time.sleep(1)
        elif kind == "key":
            game.key(s["key"], s.get("hold", 0.05))
        elif kind == "mouse":
            # posted mouse messages, a player's hand: "at" is a client fraction [fx, fy];
            # "button" left|right|middle|x1|x2 presses there for "hold" s, absent only moves
            w, h = winproc.client_size(game.window())
            fx, fy = s.get("at", [0.5, 0.5])
            winproc.mouse(game.window(), int(fx * (w - 1)), int(fy * (h - 1)), s.get("button"), s.get("hold", 0.1))
            game.note("mouse", at=[fx, fy], button=s.get("button"), size=[w, h])
        elif kind == "type":
            # text into whatever has the keyboard (a textinput pressed with menu "!click")
            game.type_text(s["text"], s.get("gap", 0.03))
        elif kind == "text":
            game.text(s["text"], s.get("gap", 0.03))
        elif kind == "console":
            # a raw console line, as a human would type it in watch mode (cvars, the engine's
            # own debug draws); the effect is asserted by later steps, never assumed. With
            # "expect"/"lacks", its reply in the log written after it is asserted (gamelab/ui.py)
            if "expect" in s or "lacks" in s:
                ui.console(self, game, s, saved)
            else:
                game.console(subst(s["line"], saved))
        elif kind in ui.STEPS:
            # click / hover a widget like a human, with posted mouse messages (gamelab/ui.py)
            ui.step(self, game, s, saved)
        else:
            raise GameError(f"unknown step {kind!r}")
        return game

    # ---- boundaries (repro playbook 3.1 / 3.2) ---------------------------------

    def boundaries(self, saved: dict) -> list[dict]:
        """The scenario's boundary rows, each probed on both sides: "before" and "after"
        name saved replies ("menu" is the main-menu probe). "survives" paths must be equal
        on both sides, "changes" paths must differ."""
        rows = []
        replies = dict(saved, menu=self.menu)
        for b in self.scenario.get("boundaries", []):
            before, after = replies.get(b["before"]), replies.get(b["after"])
            row = {k: b.get(k, "") for k in ("name", "kind", "copies", "reinit")}
            problems, cells = [], []
            for side, rep in (("before", before), ("after", after)):
                if not isinstance(rep, dict) or not rep.get("ok"):
                    problems.append(f"{side} side ({b[side]}) not probed: {rep}")
            for rule in ("survives", "changes"):
                for path in b.get(rule, []):
                    # "p" reads p on both sides; "p|q" reads p before and q after
                    pb, _, pa = path.partition("|")
                    x, y = dotted(before or {}, pb), dotted(after or {}, pa or pb)
                    x = None if isinstance(x, KeyError) else x
                    y = None if isinstance(y, KeyError) else y
                    cells.append({"path": path, "rule": rule, "before": x, "after": y})
                    if rule == "survives" and (x != y or x is None):
                        problems.append(f"{path} did not survive: {x!r} -> {y!r}")
                    if rule == "changes" and x == y:
                        problems.append(f"{path} did not change: {x!r}")
            row.update(cells=cells, ok=not problems)
            rows.append(row)
            self.assert_(f"boundary {b['name']}", not problems, "; ".join(problems))
        return rows

    def remember(self, f: Path) -> None:
        remember_written(self.results, f)

    def run(self) -> dict:
        out = self.out = {"scenario": self.scenario["name"], "mode": self.mode,
                          "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          # the travel graph this run planned against (gamelab/travel/)
                          "travel_revision": pilotlib.graph_revision(),
                          "explore": bool(self.scenario.get("explore"))}
        self.plan = None
        try:
            write_plan([])                     # a fixture build must not run a plan left behind
            if "plan" in self.scenario:
                bad = sorted({st["do"] for st in self.scenario["steps"]} - PLAN_STEP_KINDS)
                if bad:
                    raise GameError(f"a plan scenario types nothing into the console; these steps would: {bad}")
            fixture = self.materialize(self.scenario["fixture"])
            out["fixture"] = {k: fixture[k] for k in ("name", "cache_key", "cache")}
            # mods under test: enabled on top of the fixture's set, in this run's copy of the save
            extra = list(self.scenario.get("mods", []))
            if extra:
                hps.enable(hps.current_save(0, env.GAME / "saves"), fixture["recipe"]["binary_edits"]["enable_mods"] + extra)
                out["mods_under_test"] = extra
            self.recipe, self.extra = fixture["recipe"], extra
            if "plan" in self.scenario:
                self.plan = self.plan_steps(fixture["recipe"])
                write_plan([f"{st['at']}|{st['name']}|{st['line']}" for st in self.plan])
                out["plan_lines"] = len(self.plan)
            game = self.enter_fixture(fixture["recipe"], extra)
            saved: dict = {}
            out["saved"] = saved
            for s in self.scenario["steps"]:
                game = self.step(game, s, saved)
            if self.plan is not None:
                self.plan_report(game)
            out["boundaries"] = self.boundaries(saved)
            out["travel_revision_end"] = pilotlib.graph_revision()
            # the renderer floor (repro playbook 1.2): every run ends on one readable frame. A
            # minimized window presents nothing, so it is restored (not activated) first. A
            # `play` the human ended by closing the game has no window left: that is the
            # session's normal end, not an error (watch arena 20261021-061402 failed on it)
            if not game.alive() and any(st.get("do") == "play" for st in self.scenario["steps"]):
                out["closed_by_player"] = True
            else:
                if winproc.restore_noactivate(game.window()):
                    out["restored_for_end_shot"] = True
                    time.sleep(0.3)
                self.step(game, {"do": "shot", "name": "end"}, saved)
        except Exception as e:                     # noqa: BLE001 - every failure is a result
            out["timeout"] = isinstance(e, RunTimeout)
            out["error"] = f"{type(e).__name__}: {e}"
            out["traceback"] = traceback.format_exc()
            print(out["traceback"], flush=True)
        finally:
            if self.game is not None:
                self.finish(self.game)
            restore_written(self.results)
            write_plan([])
        self.flush(final=True)
        return json.loads((self.results / "inner.json").read_text(encoding="utf-8"))


def remember_written(results: Path, f: Path) -> None:
    """Journal a file's original bytes in the results dir before a step edits it, so the
    launcher can put it back (restore_written) even if it had to kill this runner."""
    journal = results / "written.json"
    entries = json.loads(journal.read_text(encoding="utf-8")) if journal.is_file() else []
    if any(e["path"] == str(f) for e in entries):
        return
    orig = None
    if f.is_file():
        orig = str(results / f"written-{len(entries)}.orig")
        Path(orig).write_bytes(f.read_bytes())
    entries.append({"path": str(f), "orig": orig})
    journal.write_text(json.dumps(entries, indent=1), encoding="utf-8")


def restore_written(results: Path) -> list[str]:
    """Put back every file a write_* step edited (journal from remember_written); the
    restored paths. Safe to call twice."""
    journal = results / "written.json"
    if not journal.is_file():
        return []
    done = []
    for e in json.loads(journal.read_text(encoding="utf-8")):
        f = Path(e["path"])
        if e["orig"] is None:
            f.unlink(missing_ok=True)
        else:
            f.write_bytes(Path(e["orig"]).read_bytes())
            Path(e["orig"]).unlink()
        done.append(str(f))
    journal.unlink()
    return done


def logparse_console_lines(log: str) -> list[str]:
    """Every gl line the console executed (it echoes each one: session.ECHO_LINE)."""
    return [m.group(0).strip() for m in re.finditer(r"> gl \S+ \S+[^\n]{0,80}", log)]


def session_console_lines(log: str) -> list[str]:
    """Every line the console executed (session.CONSOLE_ECHO) after the first "Starting
    session": the menu before it is not gameplay (Run.check_console)."""
    m = re.search(r"\] Starting session\s*$", log, re.M)
    return [] if m is None else CONSOLE_ECHO.findall(log, m.end())


def frame_size(png: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(png) as im:
        return im.size


def colours(png: Path) -> int:
    from PIL import Image
    im = Image.open(png).convert("RGB").resize((64, 36))
    return len(im.getcolors(64 * 36))           # 64x36 has at most 2304 colours


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario")
    ap.add_argument("results")
    ap.add_argument("--mode", choices=("lab", "watch"), required=True)
    a = ap.parse_args(argv)
    results = Path(a.results)
    results.mkdir(parents=True, exist_ok=True)
    scenario = json.loads(Path(a.scenario).read_text(encoding="utf-8"))
    out = Run(scenario, results, a.mode).run()
    return 0 if "error" not in out and all(x["ok"] for x in out["assertions"]) else 1


if __name__ == "__main__":
    sys.exit(main())
