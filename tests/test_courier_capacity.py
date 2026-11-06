"""UNRUN source draft: actual courier driver controls with native-boundary fakes."""
import copy
import unittest
from types import SimpleNamespace
from unittest import mock
from gamelab.bots import fix_courier as driver

MACE = "mainhand_mace_01"
SWORD = "mainhand_longsword_01"

def item(base, index):
    return dict(index=index, id=base, name="Mace" if base == MACE else "Sword",
                slot="mainhand", quality=1, ilvl=1)

class Clock:
    def __init__(self): self.now = 0.0
    def time(self): return self.now
    def sleep(self, seconds): self.now += seconds

class Fake:
    def __init__(self, clock, mode="clean"):
        self.clock, self.mode = clock, mode
        self.out, self.notes, self.calls = {}, [], []
        self.bag, self.log = [], ""
        self.pet_ids = []
        self.phase, self.handed, self.closed = "town", False, False
        self.away_until, self.back_logged = None, False
        self.g = SimpleNamespace(read_log=lambda: self.log)
    def flag(self, name, ok, note=""):
        self.out[name] = bool(ok)
        if note: self.notes.append(note)
    def log_since(self, mark): return self.log[mark:]
    def hwp(self, line, *args, **kwargs):
        self.calls.append(("hwp", line))
        if line == "pet courier":
            if self.handed and not self.closed:
                return "Pet courier: 0/1 handed over this trip." if self.mode == "wrong_capacity" else "Pet courier: 1/1 handed over this trip."
            return "Pet courier: 0/1 handed over this trip."
        return ""
    def wait_phase(self, phase):
        self.calls.append(("wait_phase", phase))
        return self.mode != "phase_failure" and self.phase == phase
    def menu(self):
        self.calls.append(("menu",))
        return {"ok": True}
    def hover(self, widget, index):
        self.calls.append(("hover", widget, index, len(self.bag), self.handed))
        if not self.bag: raise AssertionError("driver tried empty-bag hover")
        nav = ["Back", "Equip", "Compare", "Destroy", "[Q] Drop"]
        if not self.handed or self.mode == "still_send_home": nav.append("[H] Send home")
        reply = dict(ok=True, window="PlayerMenu", type=driver.INVENTORY, item=self.bag[0]["name"], nav=nav,
                     clickable=[True] * len(nav))
        if self.handed:
            if self.mode == "hover_refusal": return {"ok": False, "error": "no item"}
            if self.mode == "hover_truncation": reply["truncated"] = True
            if self.mode == "hover_wrong_type": reply["type"] = 0
            if self.mode == "hover_missing_nav": reply.pop("nav")
            if self.mode == "hover_missing_clickable": reply.pop("clickable")
            if self.mode == "hover_other_item": reply["item"] = "foreign item"
            if self.mode == "drop_missing": reply["nav"].remove("[Q] Drop"); reply["clickable"].pop()
            if self.mode == "drop_disabled": reply["clickable"][4] = False
        return reply
    def press(self, key):
        self.calls.append(("press", key))
        if key != "h": raise AssertionError(key)
        self.handed = True
        self.bag.pop(0)
        if self.mode == "zero_remaining": self.bag.clear()
        self.log += "[HWP:pets] courier: Mace to the stash tab 'Pet deliveries' (1/1)\n"
    def close(self):
        self.calls.append(("close",))
        self.closed = True
        self.away_until = self.clock.now + 5
        self.log += "[HWP:pets] courier: the pet leaves with 1 item(s), back in 5 s\n"
        return True
    def gl(self, verb, *args):
        self.calls.append((verb, *args))
        if verb == "equip":
            if self.mode == "equip_refusal": return {"ok": False}
            self.bag.append(item(MACE if not self.bag else SWORD, len(self.bag)))
            return {"ok": True, "quality": 1, "ilvl": 1}
        if verb == "bagitems":
            if self.mode == "bag_refusal" and not self.handed: return {"ok": False}
            bag = [dict(row, index=i) for i, row in enumerate(self.bag)]
            reply = dict(ok=True, count=len(bag), bag=copy.deepcopy(bag))
            if self.mode == "bag_truncation" and not self.handed: reply["count"] += 1
            if self.mode == "bag_flagged_truncation" and not self.handed: reply["truncated"] = True
            return reply
        if verb == "mission":
            self.phase = "mission"
            return {"ok": self.mode != "mission_refusal"}
        if verb == "state":
            return dict(ok=True, phase="mission", window="OtherWindow" if self.mode == "post_window_wrong" else "PlayerMenu",
                        player={"dead": False}, paused=False)
        if verb == "near":
            if self.mode == "near_refusal": return {"ok": False}
            if self.mode == "near_truncation": return dict(ok=True, count=2, truncated=1, units=[{"unit": 100}])
            away = self.away_until is not None and self.clock.now < self.away_until
            if self.away_until is not None and not away and not self.back_logged:
                self.log += "[HWP:pets] courier: the pet is back\n"; self.back_logged = True
            unit_id = -2 if self.mode == "post_pet_changed" and self.handed and not self.closed else (-3 if self.closed and not away else -1)
            units = [] if away else [{"unit": unit_id}]
            self.pet_ids.extend(row["unit"] for row in units)
            return dict(ok=True, count=len(units), truncated=0, units=units)
        if verb == "stash":
            if not self.handed: return {"ok": False, "error": "tab not yet created"}
            return dict(ok=True, name="Pet deliveries", items=[MACE + "@1"])
        raise AssertionError((verb, args))

class CourierCapacityDriver(unittest.TestCase):
    def exercise(self, mode="clean"):
        clock = Clock(); fake = Fake(clock, mode)
        def bought(_):
            fake.calls.append(("buy_pet",))
            return "Native pet", mode != "buy_failure"
        with mock.patch.object(driver, "Checks", return_value=fake), \
             mock.patch.object(driver, "buy_pet", side_effect=bought), \
             mock.patch.object(driver, "time", clock):
            result = driver.run(None, check="courier")
        return result, fake

    def test_two_to_one_real_hover_and_capacity_consumer(self):
        result, fake = self.exercise()
        self.assertIs(result["ok"], True, result)
        self.assertEqual([call[1:] for call in fake.calls if call[0] == "equip"],
                         [(SWORD, "common", 1), (MACE, "common", 1)])
        self.assertEqual(sum(call == ("press", "h") for call in fake.calls), 1)
        post = [call for call in fake.calls if call[0] == "hover" and call[-1] is True]
        self.assertEqual(len(post), 1)
        self.assertEqual(post[0][-2], 1)  # actual remaining item; no empty synthetic observation
        self.assertIn(("hwp", "pet courier"), fake.calls)
        self.assertIn(-1, fake.pet_ids)  # actual local/transient ID semantics
        self.assertIn(-3, fake.pet_ids)  # a new ID on return is valid
        for name in ("pet_bought", "courier_bag_item", "run_started", "pet_in_run", "courier_hint",
                     "courier_hint_clickable", "courier_handed", "courier_in_stash", "courier_full_no_hint",
                     "pet_waits_for_close", "pet_leaves", "pet_back", "courier_status"):
            self.assertIs(result[name], True, result)

    def test_zero_remaining_never_supplies_capacity_absence(self):
        result, fake = self.exercise("zero_remaining")
        self.assertIs(result["ok"], False, result)
        self.assertIs(result["courier_handed"], False)
        self.assertIsNot(result.get("courier_full_no_hint"), True)
        self.assertFalse(any(call[0] == "hover" and call[-1] is True for call in fake.calls))
        self.assertNotIn(("close",), fake.calls)

    def test_refused_truncated_or_foreign_post_hover_stops_before_trip(self):
        for mode in ("hover_refusal", "hover_truncation", "hover_wrong_type", "hover_missing_nav", "hover_missing_clickable", "hover_other_item"):
            with self.subTest(mode=mode):
                result, fake = self.exercise(mode)
                self.assertIs(result["ok"], False, result)
                self.assertIsNot(result.get("courier_full_no_hint"), True)
                self.assertNotIn(("close",), fake.calls)

    def test_full_capacity_requires_drop_and_actual_one_of_one_status(self):
        for mode in ("still_send_home", "drop_missing", "drop_disabled", "wrong_capacity"):
            with self.subTest(mode=mode):
                result, fake = self.exercise(mode)
                self.assertIs(result["courier_full_no_hint"], False, result)
                self.assertIs(result["ok"], False)
                self.assertNotIn(("close",), fake.calls)

    def test_actual_open_window_and_same_solo_pet_are_required_without_pause_assumption(self):
        for mode in ("post_window_wrong", "post_pet_changed"):
            with self.subTest(mode=mode):
                result, fake = self.exercise(mode)
                self.assertIs(result["pet_waits_for_close"], False, result)
                self.assertIs(result["ok"], False)
                self.assertNotIn(("close",), fake.calls)

    def test_setup_failure_stops_before_mission_or_handoff(self):
        for mode in ("buy_failure", "equip_refusal", "bag_refusal", "bag_truncation", "bag_flagged_truncation"):
            with self.subTest(mode=mode):
                result, fake = self.exercise(mode)
                self.assertIs(result["ok"], False, result)
                self.assertFalse(any(call[0] == "mission" for call in fake.calls))
                self.assertNotIn(("press", "h"), fake.calls)

    def test_phase_and_pet_refusal_stop_before_inventory_handoff(self):
        for mode in ("mission_refusal", "phase_failure", "near_refusal", "near_truncation"):
            with self.subTest(mode=mode):
                result, fake = self.exercise(mode)
                self.assertIs(result["ok"], False, result)
                self.assertNotIn(("menu",), fake.calls)
                self.assertNotIn(("press", "h"), fake.calls)

if __name__ == "__main__":
    unittest.main()
