"""Native end-screen versus saved LastStats and actual board; isolated fixture only.

No new AS, counter setters, snapshot calls, synthetic party data or result setters.
Abandon uses the native pause-menu path. Failed uses native lethal damage/DeadMenu.
Controlled intro-complete Town fixture; no natural intro/progression claim.
Success, true co-op, large/scrolling lists and other locales remain separate.
"""
import json
import math
import re
import time
from dataclasses import asdict

from gamelab.bots.plan_checks import Checks as Base
from gamelab.bots.qa_firearms_input_sequence import sequence_protocol
from gamelab.hps import hash_string
from gamelab.bots.laststats_oracle import board_assertions, children as oracle_children, snapshot_assertions

NAME = "QALastStats"
KEY = "laststats.mine"  # literal dictionary key: never dotted inspect traversal
STATES = {"aborted": 4, "failed": 2}  # native Missions/MissionManager.as183
LABELS = {"aborted": "Abandoned", "failed": "Defeated"}


def parse_rows(reply, native):
    """Parse source-defined two-level stat rows; refuse the old helper's silent60cap."""
    if reply.get("ok") is not True or reply.get("visible") is not True:
        raise ValueError("stat group absent or hidden")
    nodes = reply.get("nodes")
    if not isinstance(nodes, list) or len(nodes) >= 60:
        raise ValueError("missing nodes or possibly capped60node tree")
    rows, headers, row = [], [], None
    category = None

    def finish():
        if row is None:
            return
        if category is None or set(row) != {"stat-title", "stat-text"}:
            raise ValueError("incomplete row/category")
        if any(not isinstance(v, str) or not v for v in row.values()):
            raise ValueError("blank stat title/value")
        rows.append(dict(cat=category[0], category_text=category[1],
                         title=row["stat-title"], text=row["stat-text"]))

    for node in nodes:
        if type(node.get("depth")) is not int or node["depth"] not in (1, 2):
            raise ValueError("unsupported UI depth")
        wid = node.get("id")
        if node["depth"] == 1:
            finish()
            row = None
            if node.get("type") == "TextWidget":
                if node.get("visible") is not True or not node.get("caption"):
                    raise ValueError("hidden/blank category")
                if native and (not wid or wid.startswith("stat-")):
                    raise ValueError("unexpected native category identity")
                if not native and wid != "stat-category-template":
                    raise ValueError("unexpected board category identity")
                category = (wid if native else None, node["caption"])
                headers.append(category)
            elif wid == "stat-separator" and not native:
                if node.get("visible") is not True:
                    raise ValueError("hidden generated separator")
            elif wid == "" and node.get("visible") is True:
                row = {}
            else:
                raise ValueError("unrecognized stat-group child")
        elif wid in ("stat-title", "stat-text"):
            if row is None or wid in row or node.get("visible") is not True:
                raise ValueError("orphan/duplicate/hidden stat text")
            row[wid] = node.get("caption")
        elif wid != "stat-bg":
            raise ValueError("unrecognized row child")
    finish()
    return dict(rows=rows, headers=headers, node_count=len(nodes))


def snapshot_matches(snapshot, native, state, name=NAME):
    try:
        snapshot_assertions(snapshot, native, state, name)
    except (ValueError, KeyError, TypeError):
        return False
    return True


class Checks(Base):
    def god(self, enabled):
        value = self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
        if type(value) not in (int, float) or value not in (0, 1):
            return False
        if bool(value) != enabled:
            self.hwp("god", .25)
        actual = self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
        return type(actual) in (int, float) and actual == int(enabled)

    @property
    def expected_path(self):
        return self.g.results / "qa-laststats-expected.json"

    def wait_window(self, name, timeout=12):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            state = self.gl("state")
            if state.get("window") == name:
                return state
            time.sleep(.1)
        return state

    def snapshot(self):
        root = self.gl("inspect", "player")
        if root.get("ok") is not True or not isinstance(root.get("keys"), list):
            raise ValueError("missing native serialized root key list")
        if "hwp" not in root["keys"]:
            return None
        bag = self.gl("inspect", "player", "hwp")
        if bag.get("ok") is not True or bag.get("truncated") is not False or not isinstance(bag.get("value"), dict):
            raise ValueError("missing/truncated native serialized HWP bag")
        return bag["value"].get(KEY)

    def close(self, board=False):
        if board:
            self.gl("press", "close-btn")
        else:
            self.g.key("escape")
        end = time.monotonic() + 5
        while time.monotonic() < end:
            state = self.gl("state")
            if not state.get("window"):
                if not board:
                    return True
                receipt = self._board_use
                terminal = self.g.wait_gl(lambda e: e.get("ev") == "inputsequence"
                                          and e.get("tag") == receipt["tag"], timeout=10) or {}
                done = [e for e in self.g.gl if e.get("ev") == "input_done"
                        and e.get("sequence") == receipt["tag"]]
                protocol = sequence_protocol(receipt["accepted"], terminal, done, [(1, ["use"])])
                samples = []
                for _ in range(2):
                    controller = self.gl("controller")
                    here = self.gl("state").get("player", {})
                    clock = self.gl("clock")
                    samples.append(dict(controller=controller, player=here, clock=clock))
                    time.sleep(.15)
                def idle(r):
                    left = r.get("held")
                    return (r.get("ok") is True and type(left) is int and left <= 0
                            and r.get("releasing") is False and r.get("down") == []
                            and all(type(r.get(k)) in (int, float) and math.isfinite(r[k])
                                    and abs(r[k]) < .0001 for k in ("mx", "my")))
                positions = [tuple(s["player"].get(k) for k in ("x", "y")) for s in samples]
                finite = all(type(v) in (int, float) and math.isfinite(v) for pos in positions for v in pos)
                clocks = [s["clock"] for s in samples]
                resumed = (all(s.get("ok") is True and type(s.get("sceneMs")) is int
                               and type(s.get("frames")) is int for s in clocks)
                           and clocks[1]["sceneMs"] > clocks[0]["sceneMs"]
                           and clocks[1]["frames"] > clocks[0]["frames"])
                released = (protocol["valid"] and all(idle(s["controller"]) for s in samples)
                            and finite and math.dist(*positions) <= 1 and resumed)
                self.out[receipt["prefix"] + "_input_release"] = bool(released)
                receipt.update(terminal=terminal, input_done=done, protocol=protocol,
                               released_samples=samples, actual_native_clock_resumed=bool(resumed))
                return bool(released)
            time.sleep(.1)
        return False

    def open_board(self, prefix):
        nearby = self.gl("near", 6000, "laststats_board")
        units = nearby.get("units", [])
        unique = nearby.get("ok") is True and nearby.get("count") == 1 and len(units) == 1
        self.flag(prefix + "_one_board", unique, str(nearby))
        if not unique:
            return False
        unit = units[0]
        walks, top = [], False
        # A paused window cannot complete Pilot.use: PilotFrame stops whilepaused.
        # Walk normally, stop that writer, verify this exact top usable, then
        # use c657's real one-frame input. Observe release only after closing.
        for dx, dy in ((24, 0), (0, 24), (-24, 0), (0, -24)):
            result = self.p.path_to(unit["x"] + dx, unit["y"] + dy, tol=4, timeout=45 if prefix == "fresh" else 15)
            self.p.stop()
            nearby = self.gl("usables")
            targets = [r for r in nearby.get("usables", [])
                       if r.get("unit", {}).get("unit") == unit["unit"]]
            top = (result.ok and nearby.get("ok") is True and len(nearby.get("usables", [])) < 32
                   and len(targets) == 1 and targets[0].get("top") is True
                   and targets[0].get("canUse") is True
                   and targets[0].get("unit", {}).get("name") == unit.get("name"))
            walks.append(dict(intent=asdict(result), usables=nearby, target_is_top=bool(top)))
            if top:
                break
        self.out[prefix + "_walks"] = walks
        if not top:
            self.flag(prefix + "_normal_use", False, "Normal path did not reach exact usable board")
            return False
        tag = "laststats-use-" + prefix + "-" + str(time.time_ns())
        accepted = self.gl("inputsequence", tag, "1/0/0/1/0/use")
        first = self.g.wait_gl(lambda e: e.get("ev") == "input_done"
                               and e.get("sequence") == tag, timeout=10) or {}
        self._board_use = dict(prefix=prefix, tag=tag, accepted=accepted, first_write=first,
                               unit=unit, normal_walk=walks)
        self.out[prefix + "_use"] = self._board_use
        state = self.wait_window("HWPLastStatsMenu")
        good = (accepted.get("ok") is True and first.get("sequence") == tag
                and first.get("frames", 0) >= 1 and state.get("window") == "HWPLastStatsMenu"
                )
        self.flag(prefix + "_normal_use", good, str(state))
        return good

    def board_status(self):
        # wtext cannot read TextInputWidget (it is not a TextWidget).
        # Existing module status supplies query/input only; tree reads prove rows.
        text = self.hwp("laststats board", .3, until="board open:")
        matches = list(re.finditer(
            r'board open: (?P<shown>\d+) of (?P<total>\d+) stats, (?P<players>\d+) players, '
            r'(?P<bars>\d+) bars, tab "(?P<tab>[^"]*)" (?P<tabi>\d+)/(?P<tabs>\d+), '
            r'filter "(?P<filter>[^"]*)", typing (?P<typing>[01]), '
            r'input "(?P<input>[^"]*)", rows: (?P<titles>[^\r\n]*)', text))
        if not matches:
            raise ValueError("missing current board status")
        status = matches[-1].groupdict()
        for key in ("shown", "total", "players", "bars", "typing", "tabi", "tabs"):
            status[key] = int(status[key])
        return dict(raw=text, value=status)

    def read_board(self, snap, query, prefix):
        state_before, saved_before = self.gl("state"), self.snapshot()
        raw = dict(header=self.gl("wtext", "subtitle"),
                   legend=self.gl("wchildren", "legend", 1),
                   list=self.gl("wchildren", "stat-group", 1),
                   siblings=self.gl("wchildren", "^empty", 1), rows={})
        receipt = dict(raw=raw, state_before=state_before, saved_before=saved_before,
                       expected_input=query)
        self.out.setdefault(prefix + "_board_reads", []).append(receipt)
        roots = oracle_children(raw["list"], 1)  # refuse the silent60 cap before more calls
        for n in roots:
            if re.fullmatch(r"stat-\d+", n["id"]):
                if n["id"] in raw["rows"]:
                    raise ValueError("duplicate row read identity")
                raw["rows"][n["id"]] = self.gl("wchildren", n["id"], 2)
        receipt["status"] = self.board_status()
        receipt["state_after"], receipt["saved_after"] = self.gl("state"), self.snapshot()
        status = receipt["status"]["value"]
        if (state_before.get("window") != "HWPLastStatsMenu"
                or receipt["state_after"].get("window") != "HWPLastStatsMenu"
                or saved_before != snap or receipt["saved_after"] != snap
                or status["input"] != query or status["filter"] != query.lower().strip(" ")):
            raise ValueError("board read crossed window/snapshot/query state")
        return receipt

    def assert_board(self, snap, native, query, prefix):
        receipt = self.read_board(snap, query, prefix)
        result = board_assertions([] if snap is None else [snap], NAME,
                                  dict(native["headers"]), {2: "Defeated", 4: "Abandoned"},
                                  receipt["raw"], query)
        status = receipt["status"]["value"]
        if (status["shown"], status["total"], status["players"], status["bars"], status["tab"], status["tabs"]) != (
                result["shown"], result["rows"], result["players"], result["visible_bar_lines"],
                result["tab"], result["tabs"]):
            raise ValueError("status/tree disagree")
        receipt["oracle"] = result
        return result

    def check_board(self, prefix, snap, native, label):
        if not self.open_board(prefix):
            return False
        required = ["metadata", "all_values", "close_unpauses", "input_release"]
        for key in ("metadata", "all_values"):
            self.flag(prefix + "_" + key, False)
        if prefix == "aborted":
            required += ["search_match", "search_nomatch", "search_clear"]
            for key in required[-3:]:
                self.flag(prefix + "_" + key, False)
        try:
            result = self.assert_board(snap, native, "", prefix)
            self.flag(prefix + "_metadata", True)
            self.flag(prefix + "_all_values", result["rows"] == len(snap["lines"]))
            self.g.shot(prefix + "-board")
            if prefix == "aborted":
                # Choose a measured title token that yields a proper nonempty subset.
                # If the controlled native data cannot provide one, stop as setup.
                titles = [s["title"].lower() for s in snap["lines"]]
                candidates = re.findall(r"[a-z]{3,12}", " ".join(titles))
                token = next((t for t in candidates if 0 < sum(t in s for s in titles) < len(titles)), None)
                sentinel = next(("qaxqznomatch" + str(i) for i in range(16)
                                 if not any(("qaxqznomatch" + str(i)) in s for s in titles)), None)
                if token is None or sentinel is None:
                    raise ValueError("measured title search fixture unavailable")
                sent = self.gl("func", "search", token.upper())
                if sent.get("ok") is not True:
                    raise ValueError("search OnFunc refused")
                matched = self.assert_board(snap, native, token.upper(), prefix)
                self.flag(prefix + "_search_match", 0 < matched["shown"] < result["rows"])
                self.g.shot(prefix + "-board-search")
                sent = self.gl("func", "search", sentinel)
                if sent.get("ok") is not True:
                    raise ValueError("nomatch OnFunc refused")
                no = self.assert_board(snap, native, sentinel, prefix)
                self.flag(prefix + "_search_nomatch", no["shown"] == 0)
                sent = self.gl("press", "search-clear")
                if sent.get("ok") is not True:
                    raise ValueError("search-clear button refused")
                cleared = self.assert_board(snap, native, "", prefix)
                self.flag(prefix + "_search_clear", cleared == result)
        finally:
            self.flag(prefix + "_close_unpauses", self.close(board=True))
        return all(self.out.get(prefix + "_" + key) is True for key in required)


    def capture(self, kind):
        prefix = kind
        start = self.gl("mission", "bandit_keep", 0)
        entered = start.get("ok") is True and self.wait_phase("mission", 90)
        self.flag(prefix + "_entered", entered)
        if not entered:
            return None
        # Protected, small native walking fixture; no stat/counter setters or cull.
        protected = self.god(True)
        scale = self.gl("clock").get("timescale")
        self.flag(prefix + "_controlled_fixture", protected and type(scale) in (int, float) and scale == 1)
        if not self.out[prefix + "_controlled_fixture"]:
            return None
        state = self.gl("state")
        pl = state.get("player", {})
        moves = []
        for dx, dy in ((24, 0), (0, 24), (-24, 0), (0, -24)):
            result = self.p.move(pl["x"] + dx, pl["y"] + dy, tol=3, timeout=4)
            current = self.gl("state").get("player", {})
            moved = math.hypot(current.get("x", pl["x"]) - pl["x"], current.get("y", pl["y"]) - pl["y"]) >= 8
            moves.append(dict(result=asdict(result), ok=bool(result.ok), actual=current, moved=moved))
            if result.ok and moved:
                break
        self.out[prefix + "_moves"] = moves
        self.flag(prefix + "_native_movement", any(m["ok"] and m["moved"] for m in moves))
        self.p.wait(2000, timeout=5)
        self.p.stop()
        self.p.reflex(potion=0, fire=0)
        # Discovery receipt only; do not assume the native collection's schema.
        # Actual correctness is compared independently with the native end UI.
        self.out[prefix + "_stats_run_before_finish"] = self.gl("inspect", "player", "stats-run.stats")
        if kind == "aborted":
            ended = self.gl("abort")
            self.flag(prefix + "_native_finish", ended.get("ok") is True and ended.get("state") == "aborted")
        else:
            self.god(False)
            god = self.gl("cvars", "cht_god").get("cvars", {}).get("cht_god")
            pool = self.gl("state").get("player", {})
            hit = self.gl("damageme", int(max(pool["hpMax"], pool["manaMax"]) * 3) + 1)
            self.out[prefix + "_stats_run_after_damage"] = self.gl("inspect", "player", "stats-run.stats")
            dead = self.wait_window("DeadMenu", 8)
            self.flag(prefix + "_native_finish", god == 0 and hit.get("dead") is True
                      and dead.get("player", {}).get("dead") is True and dead.get("window") == "DeadMenu", str(hit))
            if not self.out[prefix + "_native_finish"]:
                return None
            time.sleep(1.6)
            self.g.key("enter")
        town = self.wait_phase("town", 90)
        state = self.wait_window("MissionEndMenu") if town else {}
        self.flag(prefix + "_end_window", town and state.get("window") == "MissionEndMenu")
        if not self.out[prefix + "_end_window"]:
            return None
        time.sleep(2)
        selected = self.gl("press", "stats")
        raw = self.gl("wchildren", "stat-group", 2)
        native = parse_rows(raw, native=True)
        header = self.gl("wtext", "mission-title", "mission-state")
        snap = self.snapshot()
        metadata = (header.get("window") == "MissionEndMenu" and not header.get("missing")
                    and header.get("truncated") is False
                    and isinstance(snap, dict) and snap.get("mission") == header.get("texts", {}).get("mission-title"))
        self.flag(prefix + "_native_snapshot_equal", selected.get("ok") is True and metadata
                  and snapshot_matches(snap, native, STATES[kind]))
        self.out[prefix + "_capture"] = dict(snapshot=snap, native=native, raw=raw, header=header)
        self.g.shot(prefix + "-native-end-stats")
        self.flag(prefix + "_end_close", self.close())
        if self.out[prefix + "_native_snapshot_equal"] and self.out[prefix + "_end_close"]:
            good = self.check_board(prefix, snap, native, LABELS[kind])
            return dict(snapshot=snap, native=native, label=LABELS[kind], valid=bool(good))
        return None

    def prepare(self):
        self.g.console("e_cheats 1")
        made = self.gl("char", "paladin", NAME)
        town = self.wait_phase("town", 60)
        time.sleep(2)
        self.p.stop()
        self.p.reflex(potion=0, fire=0)
        self.flag("fresh_character", made.get("ok") is True and town
                  and self.gl("state").get("player", {}).get("name") == NAME)
        self.flag("fresh_no_snapshot", self.snapshot() is None)
        # A fresh record is on the story-intro island. The authored board spot
        # belongs to the main Town, whose native prefab/road set is story-gated.
        # Qualify this controlled Town fixture; do not relocate the board or
        # write counters/snapshots. Keep the original intro-island FAIL evidence.
        self.g.console("cht_set_flag mission_story_intro_find_npcs 1 1")
        refresh = self.gl("townrefresh")
        time.sleep(3)
        flags = self.gl("inspect", "town", "flags")
        values = flags.get("value")
        qualified = (refresh.get("ok") is True and flags.get("ok") is True
                     and flags.get("truncated") is False and isinstance(values, list)
                     and all(type(x) is int for x in values)
                     and hash_string("mission_story_intro_find_npcs")
                         in [x & 0xffffffff for x in values])
        self.out["main_town_fixture_receipt"] = dict(refresh=refresh, native_flags=flags,
            scope="Controlled native intro-complete Town only; no natural story credit")
        self.flag("main_town_fixture", qualified)
        if not qualified:
            return
        if not self.open_board("fresh"):
            return
        self.flag("fresh_empty_ui", False)
        try:
            result = self.assert_board(None, dict(headers=[]), "", "fresh")
            self.flag("fresh_empty_ui", result["players"] == 0 and result["rows"] == 0)
            self.g.shot("fresh-laststats-board")
        finally:
            self.flag("fresh_close_unpauses", self.close(board=True))

        first = self.capture("aborted")
        second = self.capture("failed") if first and first.get("valid") else None
        self.flag("snapshot_replaced", bool(first and second and second.get("valid")
                  and first["snapshot"]["state"] == 4 and second["snapshot"]["state"] == 2
                  and first["snapshot"] != second["snapshot"]))
        self.out["captures"] = dict(aborted=first, failed=second)
        good = all(v for v in self.out.values() if isinstance(v, bool)) and bool(second and second.get("valid"))
        self.flag("prepared", good)
        if good:
            self.expected_path.write_text(json.dumps(second, indent=2) + "\n", encoding="utf-8")
            save = self.gl("save")
            self.flag("native_save", save.get("ok") is True)

    def verify(self):
        expected = json.loads(self.expected_path.read_text(encoding="utf-8"))
        state = self.gl("state")
        snap = self.snapshot()
        self.flag("reload_record", expected.get("valid") is True and state.get("phase") == "town"
                  and state.get("player", {}).get("name") == NAME and state.get("player", {}).get("dead") is False)
        self.flag("reload_snapshot_exact", snap == expected["snapshot"]
                  and snapshot_matches(snap, expected["native"], 2))
        self.check_board("reload", snap, expected["native"], expected["label"])
        for number in (1, 2):
            refresh = self.gl("townrefresh")
            time.sleep(3)
            self.flag("rebuild" + str(number) + "_snapshot_exact", refresh.get("ok") is True
                      and self.snapshot() == expected["snapshot"])
            self.check_board("rebuild" + str(number), snap, expected["native"], expected["label"])


def run(p, section="prepare", **_):
    c = Checks(p)
    try:
        getattr(c, section)()
    except Exception as exc:
        c.flag(section + "_crashed", False, repr(exc))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-5000:]
    return c.out
