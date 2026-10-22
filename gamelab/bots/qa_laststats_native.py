"""Native end-screen versus saved LastStats and actual board; isolated fixture only.

No new AS, counter setters, snapshot calls, synthetic party data or result setters.
Abandon uses the native pause-menu path. Failed uses native lethal damage/DeadMenu.
Success, true co-op, large/scrolling lists and other locales remain separate.
"""
import json
import math
import time
from collections import Counter
from dataclasses import asdict

from gamelab.bots.plan_checks import Checks as Base
from gamelab.bots.qa_firearms_input_sequence import sequence_protocol

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
    if not isinstance(snapshot, dict) or type(snapshot.get("state")) is not int:
        return False
    lines = snapshot.get("lines")
    if (snapshot.get("state") != state or snapshot.get("player") != name
            or type(snapshot.get("peer")) is not int
            or type(snapshot.get("count")) is not int or not isinstance(lines, list)
            or snapshot["count"] != len(lines) or len(lines) < 2
            or not isinstance(snapshot.get("mission"), str) or not snapshot["mission"]):
        return False
    if any(not isinstance(line, dict) or set(line) != {"cat", "title", "text"}
           or any(not isinstance(v, str) or not v for v in line.values()) for line in lines):
        return False
    # Per-skill damage is explicitly excluded by README; no other category ignored.
    actual = Counter((r["cat"], r["title"], r["text"]) for r in native["rows"]
                     if r["cat"] != "skill_dmg")
    expected = Counter((r["cat"], r["title"], r["text"]) for r in lines)
    return expected == actual


def board_matches(snapshot, native, board):
    titles = dict(native["headers"])
    if any(line["cat"] not in titles for line in snapshot["lines"]):
        return False
    expected = Counter((titles[r["cat"]], r["title"], r["text"])
                       for r in snapshot["lines"])
    actual = Counter((r["category_text"], r["title"], r["text"]) for r in board["rows"])
    expected_headers, previous = [], None
    for line in snapshot["lines"]:
        if line["cat"] != previous:
            expected_headers.append(titles[line["cat"]])
            previous = line["cat"]
    return expected == actual and [h[1] for h in board["headers"]] == expected_headers


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
            result = self.p.path_to(unit["x"] + dx, unit["y"] + dy, tol=4, timeout=15)
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

    def check_board(self, prefix, snap, native, label):
        if not self.open_board(prefix):
            return False
        header = self.gl("wtext", "player", "player-index", "subtitle")
        texts = header.get("texts", {})
        valid = (header.get("window") == "HWPLastStatsMenu" and not header.get("missing")
                 and header.get("truncated") is False and texts.get("player") == NAME
                 and texts.get("player-index") == "1/1"
                 and texts.get("subtitle") == snap["mission"] + " - " + label)
        self.flag(prefix + "_metadata", valid, str(header))
        raw = self.gl("wchildren", "stat-group", 2)
        board = parse_rows(raw, native=False)
        self.flag(prefix + "_all_values", board_matches(snap, native, board))
        self.out[prefix + "_board"] = dict(header=header, raw=raw, parsed=board)
        self.g.shot(prefix + "-board")
        for direction in ("prev", "next"):
            press = self.gl("press", direction)
            after = parse_rows(self.gl("wchildren", "stat-group", 2), native=False)
            reread = self.gl("wtext", "player", "player-index", "subtitle")
            self.flag(prefix + "_" + direction + "_wrap", press.get("ok") is True
                      and after == board and reread.get("texts") == texts)
        self.flag(prefix + "_close_unpauses", self.close(board=True))
        return all(self.out.get(prefix + "_" + k) for k in
                   ("metadata", "all_values", "prev_wrap", "next_wrap", "close_unpauses", "input_release"))

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
        if not self.open_board("fresh"):
            return
        header = self.gl("wtext", "empty", "player", "player-index", "subtitle")
        visible = self.gl("wchildren", "^empty", 1)
        nodes = visible.get("nodes", [])
        empty = [n for n in nodes if n.get("id") == "empty"]
        self.flag("fresh_empty_ui", header.get("window") == "HWPLastStatsMenu"
                  and not header.get("missing") and header.get("truncated") is False
                  and "No run recorded yet" in header.get("texts", {}).get("empty", "")
                  and all(header.get("texts", {}).get(k) == "" for k in ("player", "player-index", "subtitle"))
                  and visible.get("ok") is True and len(nodes) < 60
                  and len(empty) == 1 and empty[0].get("visible") is True)
        self.g.shot("fresh-laststats-board")
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
