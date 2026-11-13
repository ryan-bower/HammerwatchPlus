"""Offline graph checks, not a substitute for engine combat/co-op/save testing."""
from collections import Counter
from itertools import combinations
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/generate"))
import make_shortcut_candles as generator

sys.path.insert(0, str(ROOT / "tools"))
import hwr_archive as hwr

TRIGGERS = (260, 232, 253, 246, 1100, 1110, 1120)


class Graph:
    def __init__(self):
        self.root = ET.parse(generator.OUT).getroot()
        self.rows = {int(row[1].text): row for row in self.root.find("array[@name='scripts']")}
        self.enabled = {id: row[3].text == "t" for id, row in self.rows.items()}
        self.scenes = {id: "candle_off" for id in (37, 38, 39, 40, 1000, 1002, 1004)}
        self.calls = Counter()
        self.count = 0
        self.destroyed = set()

    def execute(self, id):
        if not self.enabled[id]:
            return
        row = self.rows[id]
        self.calls[id] += 1
        params = row.find("dict")

        def ids(name):
            value = params.find(f"array[@name='{name}']")
            return [] if value is None else [int(x.text) for x in value]

        def number(name, default):
            value = params.find(f"int[@name='{name}']")
            return default if value is None else int(value.text)

        kind = row[0].text
        if kind == "ToggleScripts":
            for target in ids("Scripts"):
                state = number("State", 1)
                self.enabled[target] = not self.enabled[target] if state == 3 else state == 1
        elif kind == "CheckUnitScene":
            expected = params.find("string[@name='Scene']").text
            matches = all(self.scenes[unit] == expected for unit in ids("Units"))
            for target in ids("OnTrue" if matches else "OnFalse"):
                self.execute(target)
        elif kind == "SetUnitScene":
            for unit in ids("Units"):
                self.scenes[unit] = params.find("string[@name='State']").text
        elif kind == "ChangeVariables":
            assert ids("Variables") == [225]
            assert number("Function", 0) == 2
            self.count += number("ModConstant", 0)
        elif kind == "CheckVariables":
            assert ids("Variable") == [225]
            assert number("Function", 0) == 4
            for target in ids("OnTrue" if self.count > number("Value", 0) else "OnFalse"):
                self.execute(target)
        elif kind == "DestroyUnits":
            self.destroyed.update(ids("Units"))
        elif kind == "RandomCount":
            # The locked setup removes one random vanilla pair. Combat rolls need the engine.
            if id == 332:
                self.execute(ids("ToExecute")[0])

        for output in row.findall("array"):
            values = [int(x.text) for x in output]
            for target in values[::2]:
                self.execute(target)

    def destinations(self):
        return [row.find("dict/string[@name='LevelID']").text
                for id, row in self.rows.items()
                if row[0].text == "LevelExitAreaJump" and self.enabled[id]]


def test_generated_level_is_current_and_binary_packable():
    assert generator.OUT.read_bytes() == generator.render(generator.ORIGINAL)
    data = hwr.compile_svalue_xml("levels/shortcut_dark_citadel.lvl", generator.OUT.read_bytes())
    level, end = hwr.decode_svalue(data, 8)
    assert end == len(data)
    assert len(level["scripts"]) == 162


def test_all_candle_subsets_select_one_destination_only_after_completion():
    expected = ("dungeon_1",) * 4 + ("barracks_1", "courts_1", "dark_halls_1", "dark_halls_boss")
    for count in range(8):
        for lit in combinations(TRIGGERS, count):
            graph = Graph()
            for trigger in lit:
                graph.execute(trigger)
            assert graph.destinations() == []
            graph.execute(289)  # vanilla Completed: rewards/counter, exit choice, remove button
            assert graph.count == count
            assert graph.destinations() == [expected[count]]
            assert graph.calls[283] == 1  # one portal, even when multiple thresholds are tested


def test_extra_candles_toggle_off_and_lock_at_start():
    for trigger in TRIGGERS[4:]:
        graph = Graph()
        graph.execute(trigger)
        graph.execute(trigger)
        graph.execute(291)
        assert graph.count == 0
        graph.execute(320)  # vanilla StartChallenge disables every candle's UseTrigger
        graph.execute(trigger)
        assert all(scene == "candle_off" for scene in graph.scenes.values())


def test_each_extra_candle_joins_every_wave_without_extra_loot():
    graph = Graph()
    for trigger in TRIGGERS:
        graph.execute(trigger)
    for _ in range(4):
        graph.execute(328)
    # Five vanilla wave links (one always-on) plus the three added candles.
    assert graph.calls[235] == 4 * 8
    assert graph.calls[327] == 4 * 8
    graph.execute(291)
    # The seven extra-candle nodes never clone or trigger another loot producer.
    for id in (1105, 1115, 1125):
        row = graph.rows[id]
        assert [int(x.text) for x in row.findall("array")[-1]] == [266, 0]


def test_locked_shortcut_removes_and_disables_all_extensions():
    graph = Graph()
    graph.execute(348)  # CheckShortcut's existing OnFalse, unchanged by the extension
    assert {1000, 1002, 1004} <= graph.destroyed
    assert all(not graph.enabled[trigger] for trigger in TRIGGERS[4:])
    before = ET.parse(generator.ORIGINAL).find("array[@name='scripts']")
    old = next(row for row in before if row[1].text == "268")
    assert hwr.parse_svalue_xml(ET.tostring(old.find("dict"), encoding="unicode")) == hwr.parse_svalue_xml(
        ET.tostring(graph.rows[268].find("dict"), encoding="unicode"))


def test_no_duplicate_ids_or_unrelated_geometry_changes():
    graph = Graph()
    original = ET.parse(generator.ORIGINAL).getroot()
    assert hwr.parse_svalue_xml(ET.tostring(original.find("array[@name='tiles']"), encoding="unicode")) == hwr.parse_svalue_xml(
        ET.tostring(graph.root.find("array[@name='tiles']"), encoding="unicode"))
    ids = list(graph.rows)
    assert len(ids) == len(set(ids)) == len(graph.root.find("array[@name='scripts']"))
    for group in graph.root.find("dict[@name='units']"):
        for row in group:
            if row.tag == "array":
                ids.append(int(row[1].text))
            elif row.tag == "int":
                ids.append(int(row.text))
    assert len(ids) == len(set(ids))
    assert graph.root.find("dict[@name='units']").find(f"array[@name='{generator.CANDLE}']") is not None
