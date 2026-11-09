"""Pure LastStats consumer readback controls; no game, input, save or native calls.

The handwritten fixture and all twenty mutation/data assertions are retained
from the independently reviewed ignored trial. This installed test uses the
normal QA helper import and needs no machine path, environment override or
candidate loader. Passing it proves Python modeled readbacks only.
"""
import copy
import unittest

from gamelab.bots import laststats_oracle as O


def line(cat, title, text, value):
    return dict(cat=cat, title=title, text=text, value=value)


def snap(player, peer, lines):
    return dict(player=player, peer=peer, state=2, mission="Keep", count=len(lines), lines=lines)


def node(wid, kind="GroupWidget", caption="", visible=True, depth=1, w=316, h=11):
    return dict(id=wid, type=kind, caption=caption, visible=visible, depth=depth, x=10, y=20, w=w, h=h)


def reply(nodes, visible=True):
    return dict(ok=True, visible=visible, nodes=nodes)


def observation():
    # Party producer order remote/newest, then local. Expected UI local first.
    party = [snap("Remote", 1, [line("combat", "Damage", "55", 55),
                              line("travel", "Distance", "5 m", 5)]),
             snap("Local", 0, [line("combat", "Damage", "165", 165),
                               line("combat", "Blocks", "7", 7)])]
    # Explicit expected row order: combat Damage, combat Blocks, travel Distance.
    # widths150/50,150/hidden1,hidden1/150 are independent fixture facts.
    draws = [("Damage", ("165", 150, True), ("55", 50, True)),
             ("Blocks", ("7", 150, True), ("-", 1, False)),
             ("Distance", ("-", 1, False), ("5 m", 150, True))]
    obs = dict(header=dict(ok=True, window="HWPLastStatsMenu", missing="", truncated=False,
                           texts={"subtitle": "Keep - 2 player(s)"}),
               legend=reply([node("legend-0", "TextWidget", "Local (Defeated)"),
                             node("legend-1", "TextWidget", "Remote (Defeated)")]),
               siblings=reply([node("stat-group"), node("empty", "TextWidget",
                   "No run recorded yet. Finish (or abandon) an expedition and come back.", False),
                   node("nomatch", "TextWidget", "No stat matches the search.", False)]),
               # tabs (issue #98): the first tab (combat) is open, so its two rows show and the
               # headers, the separator and the travel row are hidden until a search
               list=reply([node("cat-combat", "TextWidget", "Combat", False), node("stat-0"), node("stat-1"),
                           node("sep-travel", "PanelWidget", visible=False),
                           node("cat-travel", "TextWidget", "Travel", False), node("stat-2", visible=False)]),
               rows={})
    for i, (title, *cells) in enumerate(draws):
        nodes = [node("stat-bg", "RectWidget", visible=i % 2 == 1),
                 node("stat-title-" + str(i), "TextWidget", title),
                 node("bar-template", visible=False)]
        nodes += [node("bar-name", "TextWidget", "Player", depth=2),
                  node("bar", "RectWidget", depth=2, w=1, h=8),
                  node("bar-value", "TextWidget", "0", depth=2)]
        for p, (text, width, visible) in enumerate(cells):
            suffix = str(i) + "-" + str(p)
            nodes += [node("bar-" + suffix),
                      node("bar-name-" + suffix, "TextWidget", ("Local", "Remote")[p], depth=2),
                      node("bar", "RectWidget", visible=visible, depth=2, w=width, h=8),
                      node("bar-value-" + suffix, "TextWidget", text, depth=2)]
        obs["rows"]["stat-" + str(i)] = reply(nodes, visible=i < 2)
    return party, obs


class ConsumerOracle(unittest.TestCase):
    def setUp(self):
        self.party, self.obs = observation()

    def check(self, query="", legacy=False, tab=None):
        return O.board_assertions(self.party, "Local", {"combat": "Combat", "travel": "Travel"},
                                  {2: "Defeated"}, self.obs, query, legacy, tab)

    def reject(self, mutate):
        mutate()
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.check()

    def cell(self, row, wid):
        return next(n for n in self.obs["rows"][row]["nodes"] if n["id"] == wid)

    def test_handwritten_union_local_first_and_absent_stats(self):
        before = copy.deepcopy((self.party, self.obs))
        result = self.check()
        self.assertEqual((result["rows"], result["shown"], result["players"], result["positive_rectangles"]),
                         (3, 2, 2, 3))
        self.assertEqual((result["tab"], result["tabs"]), ("combat", 2))
        self.assertEqual(before, (self.party, self.obs))

    def show(self, ids, visible):
        for n in self.obs["list"]["nodes"]:
            if n["id"] in ids:
                n["visible"] = visible
        for wid in ids:
            if wid in self.obs["rows"]:
                self.obs["rows"][wid]["visible"] = visible

    def test_other_tab_shows_only_its_rows(self):
        self.show(("stat-0", "stat-1"), False)
        self.show(("stat-2",), True)
        result = self.check(tab="travel")
        self.assertEqual((result["shown"], result["tab"], result["positive_rectangles"]), (1, "travel", 1))
        with self.assertRaises(ValueError):
            self.check()  # the combat tab's rows are hidden
        with self.assertRaises(ValueError):
            self.check(tab="loot")

    def test_tab_must_hide_headers_and_other_tabs(self):
        self.show(("stat-2",), True)
        with self.assertRaises(ValueError):
            self.check()
        self.show(("stat-2",), False)
        self.show(("cat-combat",), True)
        with self.assertRaises(ValueError):
            self.check()

    def test_search_spans_every_tab_with_headers(self):
        # "s" matches Blocks (combat) and Distance (travel), not Damage: both tabs' rows
        # show under their headers whichever tab was open
        self.show(("cat-combat", "sep-travel", "cat-travel", "stat-1", "stat-2"), True)
        self.show(("stat-0",), False)
        for tab in (None, "travel"):
            result = self.check(" S ", tab=tab)
            self.assertEqual((result["shown"], result["positive_rectangles"]), (2, 2))
        self.show(("cat-travel",), False)
        with self.assertRaises(ValueError):
            self.check("s")

    def test_wrong_formatted_value_rejected(self):
        self.reject(lambda: self.cell("stat-0", "bar-value-0-0").update(caption="164"))

    def test_wrong_bar_ratio_rejected(self):
        self.reject(lambda: [n.update(w=51) for n in self.obs["rows"]["stat-0"]["nodes"]
                             if n["id"] == "bar" and n["w"] == 50])

    def test_absent_bar_must_be_hidden(self):
        self.reject(lambda: [n.update(visible=True) for n in self.obs["rows"]["stat-1"]["nodes"]
                             if n["id"] == "bar" and n["w"] == 1])

    def test_wrong_player_cell_rejected(self):
        self.reject(lambda: self.cell("stat-0", "bar-name-0-1").update(caption="Local"))

    def test_missing_legend_rejected(self):
        self.reject(lambda: self.obs["legend"]["nodes"].pop())

    def test_duplicate_root_rejected(self):
        self.reject(lambda: self.obs["list"]["nodes"].append(copy.deepcopy(self.obs["list"]["nodes"][1])))

    def test_missing_row_read_rejected(self):
        self.reject(lambda: self.obs["rows"].pop("stat-2"))

    def test_root_cap_refused(self):
        self.reject(lambda: self.obs["list"]["nodes"].extend([node("overflow")] * 54))

    def test_nested_cap_refused(self):
        self.reject(lambda: self.obs["rows"]["stat-0"]["nodes"].extend([node("overflow")] * 46))

    def test_nested_duplicate_cell_rejected(self):
        self.reject(lambda: self.obs["rows"]["stat-0"]["nodes"].append(
            copy.deepcopy(self.cell("stat-0", "bar-value-0-1"))))

    def test_search_case_trim_and_category_hide(self):
        self.obs["list"]["nodes"][0]["visible"] = True
        self.obs["list"]["nodes"][2]["visible"] = False
        for n in self.obs["list"]["nodes"][3:]:
            n["visible"] = False
        self.obs["rows"]["stat-1"]["visible"] = False
        self.obs["rows"]["stat-2"]["visible"] = False
        self.assertEqual(self.check("  dAmAgE  ")["shown"], 1)
        self.obs["list"]["nodes"][3]["visible"] = True
        with self.assertRaises(ValueError):
            self.check("damage")

    def test_search_does_not_match_values_or_category(self):
        for n in self.obs["list"]["nodes"]:
            n["visible"] = False
        for r in self.obs["rows"].values():
            r["visible"] = False
        self.obs["siblings"]["nodes"][2]["visible"] = True
        self.assertEqual(self.check("combat")["shown"], 0)
        self.assertEqual(self.check("165")["shown"], 0)
        self.obs["siblings"]["nodes"][2]["visible"] = False
        with self.assertRaises(ValueError):
            self.check("165")

    def test_bool_value_rejected(self):
        self.reject(lambda: self.party[0]["lines"][0].update(value=True))

    def test_stale_snapshot_consumer_rejected(self):
        self.reject(lambda: self.party[1]["lines"][0].update(text="166", value=166))

    def test_empty_has_no_legend_rows_or_nomatch(self):
        self.party = []
        self.obs["header"]["texts"]["subtitle"] = ""
        self.obs["legend"]["nodes"] = []
        self.obs["list"]["nodes"] = []
        self.obs["rows"] = {}
        self.obs["siblings"]["nodes"][1]["visible"] = True
        self.assertEqual(self.check()["rows"], 0)
        self.obs["siblings"]["nodes"][2]["visible"] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_legacy_value_requires_explicit_scope(self):
        self.party[0]["lines"][0].pop("value")
        with self.assertRaises(ValueError):
            self.check()
        for n in self.obs["rows"]["stat-0"]["nodes"]:
            if n["id"] == "bar" and n["w"] == 50:
                n.update(w=1, visible=False)
        self.assertEqual(self.check(legacy=True)["positive_rectangles"], 2)

    def test_native_formatted_comparison_survives_new_numeric_field(self):
        snap = self.party[1]
        native = dict(headers=[("combat", "Combat")], rows=[
            dict(cat="combat", category_text="Combat", title="Damage", text="165"),
            dict(cat="combat", category_text="Combat", title="Blocks", text="7")])
        self.assertEqual(O.snapshot_assertions(snap, native, 2, "Local")["formatted_rows"], 2)
        native["rows"][0]["text"] = "164"
        with self.assertRaises(ValueError):
            O.snapshot_assertions(snap, native, 2, "Local")

    def test_native_duplicates_not_hidden_by_sets(self):
        snap = self.party[1]
        native = dict(headers=[("combat", "Combat")], rows=[
            dict(cat="combat", category_text="Combat", title="Damage", text="165"),
            dict(cat="combat", category_text="Combat", title="Blocks", text="7")])
        native["rows"].append(copy.deepcopy(native["rows"][0]))
        with self.assertRaises(ValueError):
            O.snapshot_assertions(snap, native, 2, "Local")

    def test_bar_rounding_zero_negative_and_tiny_positive(self):
        self.assertEqual([O.bar_width(v, m) for v, m in [(1, 4), (1, 301), (0, 10), (-7, 10), (55, 165)]],
                         [38, 2, 1, 1, 50])


if __name__ == "__main__":
    unittest.main(verbosity=2)
