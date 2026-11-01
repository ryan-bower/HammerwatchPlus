"""Durable fake controls: no game, process, network, or resource writers."""
import copy
import ast
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from gamelab.bots import qa_forgemaster_channel_repro as q

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_SOURCE = ROOT/"mods/gamelab-hands/scripts/GameLab/Verbs_qa_forgemaster_channel.as"
F1_SOURCE = ROOT/"mods/gamelab-hands/scripts/GameLab/Verbs_qa_input_target.as"
F1_SHA = "9654a0ef926deeaeb4ba947878dcd84a59de16ad549637bc5beb6e7fe5c3c9da"


def point_cost(n):
    return {"health_flat": 0, "mana_flat": n, "health_max_percent": 0, "mana_max_percent": 0,
            "health_current_percent": 0, "mana_current_percent": 0,
            "health_multiplier": 1, "mana_multiplier": 1, "dash": 0}


def healthy(case):
    cal = case == "CAL"
    cancel = case in ("C0", "C1")
    penance = case in ("P2", "P3", "C1")
    drain = case in ("P1", "P3")
    paid = case in ("P0", "P2")
    duration = 3000 if penance else 10000
    deadline = duration+100
    action = 0 if cal else 600 if cancel or drain else -1
    end = 1000 if cal else 1600 if cancel else deadline+500
    body_name = q.BODY_PREFIX+(q.NORMAL if penance else q.BOSS)
    nominal = 50 if penance else 70
    c = {"combined": point_cost(nominal), "free_health": False, "free_mana": False,
         "global_health_multiplier": 1, "global_mana_multiplier": 1,
         "scaled_health": 0, "scaled_mana": nominal, "use_points_health": 0,
         "use_points_mana": 0, "expense_health": 0, "expense_mana": nominal}
    samples = []
    mana, previous = 200., 0
    for now in range(0, end+1, 50):
        mana = min(200., mana+(now-previous)/1000)
        if paid and now == deadline:
            mana -= nominal
        raising = -1 if cal or now < 100 or now >= deadline or cancel and now > action else deadline-now
        body = not cal and not (cancel and now >= action or paid and now >= deadline)
        position = (70., 10.) if penance and now >= 350 else (0., 0.)
        if (cal or cancel) and now >= action+100:
            position = (position[0]+min(20., (now-action-100)/10), position[1])
        active_dash = case == "C1" and 200 <= now < 350
        charge = 0 if case == "C1" and now >= 200 else 1
        cd = 0 if case != "C1" or now < 200 else max(0, 1600-now)
        r = {"now": now, "dt": 50, "phase": "frame", "player": 1, "class": q.CLASS, "skill": q.NR,
             "owned_skill": True, "x": position[0], "y": position[1], "raising_left": raising,
             "stance_left": raising if penance else -1, "devouring_left": -1,
             "root": raising > 0, "silence": raising > 0, "disarm": raising > 0,
             "heresy": 3 if paid and now >= deadline else 4 if penance else 0,
             "favor": 0 if case == "P2" and now >= deadline else 5 if penance else 0,
             "favor_timer": 5000-now if penance else -1, "nr_cd": max(0, 20000-(now-deadline)) if case == "P0" and now >= deadline else 0,
             "nr_base_cd": 20000, "nr_cd_mul": 1., "dash_cd": cd, "dash_cast": 1 if active_dash else 0,
             "dash_base_cd": 1500, "dash_cd_mul": 1., "dash_dist": 90, "dash_remaining": 20. if active_dash else 0.,
             "dash_charges": charge, "dash_recharge": max(0, now-200) if charge == 0 else 0,
             "dash_max": 1, "dash_recharge_ms": 5000., "infinite_dashes": False,
             "body_valid": body, "body": -1 if cal else 2, "body_name": body_name if body else "",
             "body_position_current": body,
             "risen": [{"unit": 4, "name": q.RISEN_PREFIX+q.BOSS, "owned": True}] if case == "P0" and now >= deadline else [],
             "target": 3 if cal or cancel else -1, "target_valid": cal or cancel,
             "target_name": q.TARGET if cal or cancel else "", "target_max": 500 if cal or cancel else -1,
             "body_x": 70., "body_y": 0., "target_x": 170. if case == "C1" else 100.,
             "target_y": 10. if case == "C1" else 0., "geometry_checked": cal and now == 0,
             "shot_wall": False, "shot_hits": 1,
             "target_hp": 490. if (cal or cancel) and now >= action+450 else 500. if cal or cancel else None,
             "max_mana": 200, "max_health": 200, "mana": mana, "mana_fraction": mana/200,
             "stat_mana": 200., "mana_regen": 1., "mana_gain": 1., "cost": copy.deepcopy(c),
             "move_x": 1. if (cal or cancel) and action+100 <= now < action+300 else 0., "move_y": 0.,
             "button": "main" if (cal or cancel) and action+400 <= now < action+800 else "skill1" if not cal and now < 100 else "-",
             "cursor_world_x": 100., "cursor_world_y": 0., "projection_error": 0.}
        if now == action and (cancel or drain):
            before = copy.deepcopy(r); before["phase"] = "before_fixture"; before["body_valid"] = True; before["body_name"] = body_name
            before["body_position_current"] = True; before["cursor"] = None
            before["geometry_checked"] = cancel
            after = copy.deepcopy(before); after["phase"] = "after_fixture"
            if drain:
                mana = 0.; after["mana"] = after["mana_fraction"] = r["mana"] = r["mana_fraction"] = 0.
            else:
                after["body_valid"] = False; after["body_name"] = ""; after["body_position_current"] = False
            samples.extend([before, after])
        r["cursor"] = {"now": now, "dt": 50, "step": 0, "release": False, "buffer": 0, "gamepad": False,
            "x": r["x"], "y": r["y"], "screen_x": 10., "screen_y": 20., "world_x": r["cursor_world_x"],
            "world_y": r["cursor_world_y"], "round_error": 0., "manaExact": r["mana"], "hpExact": 200.}
        samples.append(r)
        previous = now
    head = {"ev": "forgechannel", "id": "owned-1", "tag": "fake-"+case, "case": case, "complete": True, "error": "",
            "stored": len(samples), "seen": len(samples), "dropped": 0, "truncated": False, "player": 1,
            "start": 0, "channel_at": -1 if cal else 100, "deadline": -1 if cal else deadline,
            "action_at": action, "end": end+100, "writes": len([r for r in samples if r["phase"] == "frame"])+2,
            "cursor_seen": len([r for r in samples if r["phase"] == "frame"]), "cursor_dropped": 0,
            "body": -1 if cal else 2, "body_name": "" if cal else body_name, "target": 3 if cal or cancel else -1,
            "target_name": q.TARGET if cal or cancel else "", "button": "skill1", "duration": duration,
            "released": True, "cursor_restored": True,
            "restore": [{"buffer": 0, "restored": True, "owned_last_value": True, "already_neutral": False}],
            "projection_failures": [], "actions": [], "phase": q.PHASE}
    if cancel or drain:
        before = next(r for r in samples if r["phase"] == "before_fixture")
        head["actions"] = [{"now": action, "kind": "drain" if drain else "remove_body", "raising_left": deadline-action,
                            "landed": case == "C1", "mana_before": before["mana"], "mana_after": 0. if drain else before["mana"]}]
    base_status = "forge: raises 0 penances 0 lunges 0; channel none locked 0 beam 0 dashpin 0; eat none"
    after_status = base_status.replace("raises 0", "raises 1") if case == "P0" else base_status.replace("penances 0", "penances 1") if case == "P2" else base_status
    row = {"case": case, "before": {"raw": "retained", "status": base_status},
           "after": {"raw": "retained", "status": after_status, "clock": {"sceneMs": end+100}}, "geometry": {"valid": True},
           "landed_geometry": {"valid": True}, "cost": {"ok": True, "skill": q.NR, "class": q.CLASS, "unit": 1,
                "matches": 1, "truncated": False, "combined": point_cost(nominal), "free_mana": False, "expense_mana": nominal},
           "accepted": {"ok": True, **{k: head[k] for k in ("id", "tag", "case", "player", "body", "target", "button")}}, "chunks": [],
           "rank_setup": {"levels": {q.NR: 2, q.COH: 2}, "nr_penance": 1, "coh_lunge": .02}}
    if case == "P3":
        row["pre_roll"] = {"valid": True, "heresy": 0, "body": 2, "ordinary_input": True, "rolled": True,
                           "raw": "forge bodies 1: | 2 humans/bandits/bandit_brute.unit at 70 0 ttl 59000 rolled glow1"}
    if cancel:
        row["calibration"] = healthy("CAL")
    repack(row, head, samples)
    return row


def repack(row, head, samples):
    count = len(samples)
    head = dict(head, stored=count, seen=count, parts=(count+1)//2)
    row["chunks"] = [dict(head, part=i//2, samples=samples[i:i+2]) for i in range(0, count, 2)]


def edit(row, predicate, **changes):
    samples = [copy.deepcopy(r) for c in row["chunks"] for r in c["samples"]]
    for r in samples:
        if predicate(r):
            r.update(copy.deepcopy(changes))
            if "body_valid" in changes:
                r["body_position_current"] = changes["body_valid"]
            if r.get("phase") == "frame" and type(r.get("cursor")) is dict:
                for key, native_key in (("x", "x"), ("y", "y"), ("mana", "manaExact")):
                    if key in changes:
                        r["cursor"][native_key] = changes[key]
    repack(row, row["chunks"][0], samples)


class ChannelControls(unittest.TestCase):
    def reject(self, row):
        self.assertFalse(q.evaluate(row)["healthy"], row.get("case"))

    def test_all_six_primary_healthy_controls(self):
        for case in q.PRIMARY:
            with self.subTest(case=case):
                result = q.evaluate(healthy(case))
                self.assertTrue(result["valid"], result["errors"])
                self.assertTrue(result["healthy"], {k: v for k, v in result.items() if k != "trace"})

    def test_pre_activation_drain_cannot_establish_completion_refusal(self):
        r = healthy("P1")
        for c in r["chunks"]:
            c["actions"][0]["now"] = 0
        self.reject(r)

    def test_original_free_raise_effect_is_valid_failure(self):
        r = healthy("P1")
        edit(r, lambda s: s["now"] >= 10100, body_valid=False, body_name="", heresy=3, nr_cd=20000,
             risen=[{"unit": 4, "name": q.RISEN_PREFIX+q.BOSS, "owned": True}])
        result = q.evaluate(r)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["payment"])
        self.assertFalse(result["healthy"])

    def test_original_free_penance_effect_is_valid_failure(self):
        r = healthy("P3")
        edit(r, lambda s: s["now"] >= 3100, body_valid=False, body_name="", heresy=3, favor=0)
        result = q.evaluate(r)
        self.assertTrue(result["valid"], result["errors"])
        self.assertFalse(result["consumer_effect"])
        self.assertFalse(result["healthy"])

    def test_original_lingering_locks_are_valid_failure(self):
        for case in ("C0", "C1"):
            with self.subTest(case=case):
                r = healthy(case)
                deadline = r["chunks"][0]["deadline"]
                edit(r, lambda s: s["now"] > 600, raising_left=deadline-600, root=True, silence=True, disarm=True,
                     x=70. if case == "C1" else 0., y=10. if case == "C1" else 0., target_hp=500.)
                result = q.evaluate(r)
                self.assertTrue(result["valid"], result["errors"])
                self.assertFalse(result["healthy"])

    def test_foreign_identity_cost_and_target_are_rejected(self):
        for change in ({"player": 999}, {"owned_skill": False}, {"target": 999}, {"target_name": "wrong.unit"}):
            with self.subTest(change=change):
                r = healthy("C0"); edit(r, lambda s: True, **change); self.reject(r)
        r = healthy("P0"); r["cost"]["class"] = "hwp_warlock_branding"; self.reject(r)
        r = healthy("P0"); r["cost"]["expense_mana"] = 57; self.reject(r)

    def test_late_cancel_and_missing_landing_are_rejected(self):
        for change in ({"raising_left": 1999}, {"landed": False}):
            r = healthy("C1")
            for c in r["chunks"]:
                c["actions"][0].update(change)
            self.reject(r)

    def test_missing_before_after_and_unexplained_disappearance(self):
        for key in ("before", "after"):
            r = healthy("C0"); r[key] = None; self.reject(r)
        r = healthy("C0"); edit(r, lambda s: s["now"] > 1000, target_valid=False, target_hp=None); self.reject(r)

    def test_trace_caps_duplicates_release_projection_and_clock(self):
        for field, value in (("truncated", True), ("released", False), ("cursor_restored", False), ("writes", 1)):
            r = healthy("P1")
            for c in r["chunks"]:
                c[field] = value
            self.reject(r)
        r = healthy("P1"); r["chunks"].append(copy.deepcopy(r["chunks"][-1])); self.reject(r)
        r = healthy("P1"); r["chunks"].pop(1); self.reject(r)
        r = healthy("P1"); edit(r, lambda s: s["now"] == 500, projection_error=.2); self.reject(r)
        r = healthy("P1"); edit(r, lambda s: s["now"] == 500, now="bad"); self.reject(r)

    def test_regen_modifier_max_pool_and_unaffordability_guards(self):
        for change in ({"max_mana": 300}, {"mana_regen": 50}, {"mana": 100, "mana_fraction": .5}):
            r = healthy("P1"); edit(r, lambda s: s["now"] > 600, **change); self.reject(r)
        r = healthy("P0"); edit(r, lambda s: s["now"] == 500, mana=0., mana_fraction=0.); self.reject(r)

    def test_no_independent_lunge_and_mandatory_h0_preroll(self):
        for change in ({"devouring_left": 100}, {"body_valid": False, "body_name": ""}):
            r = healthy("P3"); edit(r, lambda s: 650 <= s["now"] < 3000, **change); self.reject(r)
        for key, val in (("heresy", 4), ("ordinary_input", False), ("raw", "wrong body rolled"), ("body", 999)):
            r = healthy("P3"); r["pre_roll"][key] = val; self.reject(r)

    def test_actual_calibration_required_and_dash_refund_rejected(self):
        r = healthy("C1"); edit(r["calibration"], lambda s: True, target_hp=500.); self.reject(r)
        r = healthy("C1"); edit(r, lambda s: s["now"] > 600, dash_charges=1); self.reject(r)
        r = healthy("C1"); edit(r, lambda s: s["now"] > 600, dash_cd=0); self.reject(r)

    def test_raw_fx_after_deadline_counter_and_independent_lunge_guards(self):
        r = healthy("C1"); r["after"]["clock"]["sceneMs"] = 4000; self.reject(r)
        r = healthy("C0"); r["after"]["status"] = r["after"]["status"].replace("beam 0", "beam 1"); self.reject(r)
        r = healthy("P3"); r["after"]["status"] = r["after"]["status"].replace("lunges 0", "lunges 1"); self.reject(r)
        r = healthy("P0"); r["after"]["status"] = r["before"]["status"]; self.reject(r)
        r = healthy("P0"); r["rank_setup"]["levels"][q.NR] = 5; self.reject(r)

    def test_native_landed_geometry_and_positive_control_must_match(self):
        for changes in ({"shot_wall": True}, {"geometry_checked": False}, {"x": 30.}, {"target_x": 300.}):
            r = healthy("C1"); edit(r, lambda s: s["phase"] == "before_fixture", **changes); self.reject(r)

    def test_all_rows_retained_not_last_row(self):
        rows = [healthy(c) for c in q.PRIMARY]
        self.assertTrue(q.all_rows(rows, q.PRIMARY))
        for index in range(len(rows)):
            bad = copy.deepcopy(rows); bad[index]["before"] = None
            self.assertFalse(q.all_rows(bad, q.PRIMARY), index)
        self.assertFalse(q.all_rows(rows[:-1], q.PRIMARY))
        self.assertFalse(q.all_rows(rows[::-1], q.PRIMARY))


class TransportEnvelopeControls(unittest.TestCase):
    """Only receipt time varies; native headers, chunks and samples stay strict."""
    def annotated(self, case="CAL"):
        row = healthy(case)
        row["accepted"]["_t"] = 1.
        for index, chunk in enumerate(row["chunks"]):
            chunk["_t"] = 2.+index/1000
        return row

    def assert_trace(self, row, valid):
        result = q.trace(row["accepted"], row["chunks"])
        self.assertEqual(result["valid"], valid, result["errors"])
        return result

    def test_raw_native_rows_without_receipt_envelope_remain_valid(self):
        self.assert_trace(healthy("CAL"), True)

    def test_varying_receipt_times_preserve_native_healthy_result_and_raw_rows(self):
        row = self.annotated("P0")
        retained = copy.deepcopy(row)
        result = q.evaluate(row)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["healthy"], result["errors"])
        self.assertEqual(row, retained)
        self.assertEqual(result["trace"]["chunks"], retained["chunks"])

    def test_tied_receipt_times_and_large_transport_gaps_are_not_native_time(self):
        for mode in ("tied", "gaps"):
            row = self.annotated()
            for index, chunk in enumerate(row["chunks"]):
                chunk["_t"] = 1 if mode == "tied" else 1000+index*250.
            self.assert_trace(row, True)

    def test_invalid_receipt_values_in_acceptance_or_chunk_are_refused(self):
        for value in (None, True, "2.0", -1., float("nan"), float("inf"), -float("inf"), {}, []):
            for location in ("accepted", "chunk"):
                with self.subTest(value=repr(value), location=location):
                    row = self.annotated()
                    (row["accepted"] if location == "accepted" else row["chunks"][1])["_t"] = value
                    result = self.assert_trace(row, False)
                    self.assertIn("invalid/mixed/regressing transport timestamp envelope", result["errors"])

    def test_missing_receipt_on_any_annotated_row_is_not_raw_mode(self):
        for location in ("accepted", "first", "middle", "last"):
            row = self.annotated()
            target = row["accepted"] if location == "accepted" else row["chunks"][
                0 if location == "first" else -1 if location == "last" else 1]
            del target["_t"]
            self.assert_trace(row, False)

    def test_acceptance_only_or_one_chunk_only_receipt_is_mixed(self):
        for location in ("accepted", "chunk"):
            row = healthy("CAL")
            (row["accepted"] if location == "accepted" else row["chunks"][1])["_t"] = 1.
            self.assert_trace(row, False)

    def test_receipt_clock_regression_is_transport_refusal_not_native_reordering(self):
        row = self.annotated(); row["accepted"]["_t"] = 3.
        self.assert_trace(row, False)
        row = self.annotated(); row["chunks"][1]["_t"] = 1.5
        self.assert_trace(row, False)

    def test_native_header_and_other_context_fields_still_must_match(self):
        changes = (("id", "foreign"), ("tag", "foreign"), ("case", "P0"), ("player", 999),
            ("body", 999), ("target", 999), ("button", "main"), ("phase", "foreign"),
            ("complete", False), ("released", False), ("cursor_restored", False),
            ("projection_failures", ["foreign"]), ("restore", []), ("stored", 1))
        for field, value in changes:
            row = self.annotated(); row["chunks"][1][field] = value
            self.assert_trace(row, False)
        for field, value in (("_place", "floor"), ("_lvl", 2), ("native_extra", 1)):
            row = self.annotated()
            for chunk in row["chunks"]: chunk[field] = value
            row["chunks"][1][field] = "foreign"
            self.assert_trace(row, False)

    def test_duplicate_missing_and_reordered_parts_cannot_hide_behind_receipt_times(self):
        for change in ("duplicate", "missing", "reorder"):
            row = self.annotated()
            if change == "duplicate": row["chunks"][1] = copy.deepcopy(row["chunks"][0])
            elif change == "missing": row["chunks"].pop(1)
            else: row["chunks"][0], row["chunks"][1] = row["chunks"][1], row["chunks"][0]
            for index, chunk in enumerate(row["chunks"]): chunk["_t"] = 2.+index/1000
            self.assert_trace(row, False)

    def test_sample_cursor_owner_cost_and_native_clock_guards_remain_effective(self):
        for change in ("cursor", "owner", "sample_order", "cost"):
            row = self.annotated("P0")
            if change == "cursor": row["chunks"][0]["samples"][0]["cursor"]["buffer"] = 8
            elif change == "owner": row["chunks"][0]["samples"][0]["player"] = 999
            elif change == "sample_order": row["chunks"][0]["samples"].reverse()
            else: row["cost"]["expense_mana"] = 57
            result = q.evaluate(row)
            self.assertFalse(result["valid"], change)
            self.assertFalse(result["healthy"], change)


def method(text, name):
    match = re.search(r"\b(?:bool|void|string)\s+"+name+r"\s*\([^)]*\)[^{]*\{", text)
    if not match:
        return ""
    start, depth = match.end(), 1
    for index in range(start, len(text)):
        depth += (text[index] == "{")-(text[index] == "}")
        if depth == 0:
            return text[start:index]
    return ""


def caller_source_errors(text, parent):
    """Bind fake caller controls to the actual proposed AS and exact F1 API."""
    errors = []
    update = method(text, "UpdateFrame")
    tokens = ("m_cursorFrame++; @m_guardInput = null;", "m_record is null || m_record.playerClass is null",
        "m_world = xy(target.GetPosition());", "string guard = CursorGuard(input);",
        "if (!CursorCacheCurrent(input, g_inputFrames))", "uint writes = g_inputFrames;",
        "if (!CursorCacheCurrent(input, writes) || g_inputFrames != writes)",
        "WriteInput(input, move, true, vec2(0, -1), buttons, pressed);",
        "if (!PinAndRead(input, ms, false, 0, writes))", "m_cursorRows.length() != 1 || m_cursorDropped != 0",
        'Sample(ms, "frame", move, button);', "m_cursorRows.resize(0); @m_guardInput = null;",
        "age >= 200 && !m_confirmed", 'if (m_channelAt < 0 && button == "main") m_confirmed = true;',
        "dist(xy(declared.GetPosition()), m_bodySpot) > 0.1f")
    for token in tokens:
        if token not in update:
            errors.append("caller missing "+token)
    ordered = ("m_cursorFrame++", "auto input = GetInput();", "m_world = xy(target.GetPosition());",
        "string guard = CursorGuard(input);", "CursorCacheCurrent(input, g_inputFrames)", "uint writes = g_inputFrames;",
        'Sample(ms, "before_fixture"', "m_record.mana = 0", "CursorCacheCurrent(input, writes)",
        "WriteInput(input, move, true", "PinAndRead(input, ms, false, 0, writes)", 'Sample(ms, "frame"', "m_cursorRows.resize(0)")
    positions = [update.find(token) for token in ordered]
    if any(p < 0 for p in positions) or positions != sorted(positions):
        errors.append("final-target/guard/cache/fixture/one-writer/pin/retain/drain order")
    if update.count("CursorGuard(input)") != 1 or "input.MousePos =" in update or "ToScreenspace(" in update:
        errors.append("discarded inherited corrected point or guarded wrong target")
    if "age < 220" in update:
        errors.append("narrow confirmation interval")
    if update.find("m_record.playerClass is null") > update.find("m_record.playerClass.m_id"):
        errors.append("null class dereferenced before guard")
    pin = method(parent, "PinAndRead")
    cache = method(parent, "CursorCacheCurrent")
    if not ("input.MousePos = m_guardScreen;" in pin and "CursorCacheCurrent(input, writes)" in pin
            and "g_inputFrames != writes + 1" in pin and "m_guardFrame == m_cursorFrame" in cache):
        errors.append("pending F1 validated-cache API not present")
    return errors


class CacheFrame:
    """Independent F1 caller lifetime model, not an AngelScript execution."""
    def __init__(self):
        self.current = object(); self.frame = 0; self.now = 10; self.writes = 0
        self.cache = None; self.mouse = (0., 0.); self.original = self.mouse; self.cursor_rows = []

    def begin(self):
        self.frame += 1; self.cache = None

    def guard(self, final_world):
        # The correction solver is F1's separate scope. This fixture supplies a
        # known corrected point whose actual inverse is the target; raw forward
        # projection differs by(.6,.4), beyond the unchanged.1 world bound.
        self.cache = (self.current, self.frame, self.now, self.writes, tuple(final_world))

    def current_cache(self, handle, writes):
        return bool(self.cache and self.cache[:4] == (handle, self.frame, self.now, writes) and handle is self.current)

    def write(self, handle):
        before = self.writes
        if not self.current_cache(handle, before):
            return None
        self.writes += 1
        return before

    def pin(self, handle, before):
        if not self.current_cache(handle, before) or self.writes != before+1:
            return False
        self.mouse = self.cache[4]; self.cache = None
        self.cursor_rows.append(self.mouse)
        return True


class CallerControls(unittest.TestCase):
    def test_exact_pending_f1_source_and_s4_caller_order(self):
        parent = F1_SOURCE.read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(F1_SOURCE.read_bytes()).hexdigest(), F1_SHA)
        self.assertEqual(caller_source_errors(FIXTURE_SOURCE.read_text(encoding="utf-8"), parent), [])

    def test_actual_source_mutations_reject_old_cursor_and_stale_guard(self):
        text, parent = FIXTURE_SOURCE.read_text(encoding="utf-8"), F1_SOURCE.read_text(encoding="utf-8")
        for old, new in (("m_cursorFrame++; @m_guardInput = null;", ""),
                         ("m_world = xy(target.GetPosition());", ""),
                         ("if (!PinAndRead(input, ms, false, 0, writes))", "if (false)"),
                         ("age >= 200 && !m_confirmed", "age >= 200 && age < 220"),
                         ("m_record is null || m_record.playerClass is null", "m_record is null")):
            with self.subTest(old=old):
                self.assertIn(old, text)
                self.assertTrue(caller_source_errors(text.replace(old, new), parent))
        self.assertTrue(caller_source_errors(text.replace("m_cursorRows.resize(0);", "input.MousePos = ToScreenspace(xyz(m_world));"), parent))

    def test_corrected_point_and_changed_target_guard_are_consumed_once(self):
        frame = CacheFrame()
        for target in ((70., 0.), (170., 10.)):
            frame.begin(); frame.guard(target)
            before = frame.write(frame.current)
            self.assertIsNotNone(before)
            self.assertTrue(frame.pin(frame.current, before))
            self.assertEqual(frame.mouse, target)
            self.assertLessEqual(math_dist(frame.mouse, target), .1)
            self.assertFalse(frame.pin(frame.current, before))
        self.assertEqual(frame.writes, 2)
        self.assertEqual(frame.cursor_rows, [(70., 0.), (170., 10.)])
        raw = (170.-.6, 10.-.4)
        self.assertGreater(math_dist(raw, (170., 10.)), .1)
        stale = CacheFrame(); stale.begin(); stale.guard((70., 0.))
        before = stale.write(stale.current); self.assertTrue(stale.pin(stale.current, before))
        self.assertGreater(math_dist(stale.mouse, (170., 10.)), .1)  # old-target cache is a real anti-control

    def test_foreign_frame_handle_clock_writer_and_double_consume_refuse(self):
        for mutation in (lambda f: f.begin(), lambda f: setattr(f, "current", object()),
                         lambda f: setattr(f, "now", f.now+1), lambda f: setattr(f, "writes", f.writes+1)):
            frame = CacheFrame(); frame.begin(); frame.guard((70., 0.)); handle = frame.current
            mutation(frame)
            self.assertIsNone(frame.write(handle))
            self.assertEqual(frame.mouse, frame.original)
        frame = CacheFrame(); frame.begin(); frame.guard((70., 0.)); before = frame.write(frame.current)
        frame.writes += 1
        self.assertFalse(frame.pin(frame.current, before))
        self.assertEqual(frame.mouse, frame.original)

    def test_confirmation_cannot_skip_33ms_or_100ms_native_cadence(self):
        for dt in (1, 16, 33, 50, 99, 100):
            age, confirmed, pressed = 0, False, []
            while age <= 1000:
                if age >= 200 and not confirmed:
                    pressed.append(age); confirmed = True
                age += dt
            self.assertEqual(len(pressed), 1, dt)
            self.assertLessEqual(pressed[0], 299)
        self.assertFalse([age for age in range(0, 1001, 33) if 200 <= age < 220])

    def test_missing_part_collection_shares_one_absolute_deadline(self):
        class Game:
            def __init__(self, initial):
                self.gl = initial; self.clock = 0.; self.waits = []
            def wait_gl(self, predicate, timeout):
                self.waits.append(timeout)
                found = next((e for e in self.gl if predicate(e)), None)
                if found is None:
                    self.clock += timeout
                else:
                    self.clock += min(.25, timeout)
                return found
        for initial in ([], *[[{"ev": "forgechannel", "id": "x", "tag": "t", "part": 0, "parts": parts}]
                             for parts in (512, 1024)]):
            game = Game(initial)
            with patch.object(q.time, "monotonic", side_effect=lambda: game.clock):
                rows = q.collect(game, {"id": "x", "tag": "t"}, timeout=22)
            self.assertLessEqual(game.clock, 22)
            self.assertTrue(all(0 <= wait <= 22 for wait in game.waits))
            self.assertLessEqual(len(game.waits), 2)
            self.assertEqual(rows, initial)
            self.assertFalse(q.trace({"ok": True}, rows)["valid"])

    def test_nested_cursor_serialized_sample_and_part_size_budget(self):
        for case in (*q.PRIMARY, "CAL"):
            row = healthy(case)
            samples = [s for c in row["chunks"] for s in c["samples"]]
            for sample in samples:
                self.assertLessEqual(len(json.dumps(sample, separators=(",", ":"))), 3400)
            for chunk in row["chunks"]:
                self.assertLess(len(json.dumps(chunk, separators=(",", ":"))), 15000)
        # Worst allowed successful row size plus eight restore handles and
        # first-failure diagnostics still leaves Emit headroom at two rows.
        chunk = copy.deepcopy(healthy("C1")["chunks"][0])
        chunk["restore"] = [{"buffer": i, "restored": True, "owned_last_value": True, "already_neutral": False,
            "before_x": 99999999., "before_y": 99999999., "original_x": 99999999., "original_y": 99999999.} for i in range(8)]
        chunk["projection_failures"] = [{"diagnostic": "x"*3000}]
        chunk["samples"] = []
        for _ in range(2):
            raw = {"padding": ""}
            raw["padding"] = "x"*(3400-len(json.dumps(raw, separators=(",", ":"))))
            self.assertEqual(len(json.dumps(raw, separators=(",", ":"))), 3400)
            chunk["samples"].append(raw)
        self.assertLess(len(json.dumps(chunk, separators=(",", ":"))), 15000)


def math_dist(a, b):
    return sum((x-y)**2 for x, y in zip(a, b))**.5


class DispatchControls(unittest.TestCase):
    @staticmethod
    def rows(cases=("P0", "P1", "P2", "P3")):
        return [{"case": case, "before": None, "after": None, "accepted": {}, "chunks": []} for case in cases]

    def assert_stopped(self, rows, calls, scores, result):
        self.assertEqual(calls, ["P0"])
        self.assertEqual([row["case"] for row in rows], ["P0", "P1", "P2", "P3"])
        self.assertEqual(len(scores), 4)
        self.assertTrue(result["stopped_on_prerequisite"])
        self.assertEqual(result["dispatched_rows"], 1)
        self.assertEqual(result["after_case"], "P0")
        for row in rows[1:]:
            self.assertEqual(row["unrun"]["after_case"], "P0")
            self.assertIn("P0", row["unrun"]["cause"])
            self.assertTrue(row["unrun"]["no_setup_or_native_dispatch"])
            self.assertFalse(row["evaluation"]["valid"])
            self.assertFalse(row["evaluation"]["healthy"])
            self.assertIsNone(row["before"])
        self.assertFalse(q.all_rows(rows, ("P0", "P1", "P2", "P3")))

    def test_blocked_setup_stops_next_row_and_preserves_failure(self):
        rows, calls, scores, logs = self.rows(), [], [], [""]
        def trial(row):
            calls.append(row["case"])
            row["blocked"] = "actual geometry prerequisite failed"
            row["partial_raw"] = {"geometry": "retained original failure"}
            logs[0] += "original setup failure\n"
        result = q.run_rows(rows, trial, lambda: logs[0], lambda row: scores.append(row["case"]))
        self.assert_stopped(rows, calls, scores, result)
        self.assertEqual(rows[0]["partial_raw"]["geometry"], "retained original failure")
        self.assertEqual(rows[0]["log"], "original setup failure\n")

    def test_uncertain_ack_exception_dispatches_once_then_unrun(self):
        rows, calls, scores, mutation_dispatches = self.rows(), [], [], []
        def trial(row):
            calls.append(row["case"])
            row["before"] = {"state": "before uncertain acknowledgment"}
            mutation_dispatches.append((row["case"], "single HWP dispatch"))
            raise RuntimeError("unconfirmed HWP command sent once")
        result = q.run_rows(rows, trial, lambda: "", lambda row: scores.append(row["case"]))
        self.assert_stopped(rows, calls, scores, result)
        self.assertEqual(mutation_dispatches, [("P0", "single HWP dispatch")])
        self.assertIn("unconfirmed", rows[0]["exception"])
        self.assertIn("unconfirmed", rows[1]["unrun"]["cause"])

    def test_invalid_native_trace_stops_next_row_without_setup_retry(self):
        rows, calls, scores = self.rows(), [], []
        def trial(row):
            calls.append(row["case"])
            row.update(healthy(row["case"]))
            row["chunks"].pop()  # native receipt lost; raw partial trace is retained
        result = q.run_rows(rows, trial, lambda: "", lambda row: scores.append(row["case"]))
        self.assert_stopped(rows, calls, scores, result)
        self.assertTrue(rows[0]["chunks"])
        self.assertFalse(rows[0]["evaluation"]["valid"])

    def test_valid_product_failure_may_continue_independent_rows(self):
        rows, calls, scores = self.rows(("P1", "P2")), [], []
        def trial(row):
            calls.append(row["case"])
            row.update(healthy(row["case"]))
            if row["case"] == "P1":
                edit(row, lambda s: s["now"] >= 10100, body_valid=False, body_name="", heresy=3, nr_cd=20000,
                     risen=[{"unit": 4, "name": q.RISEN_PREFIX+q.BOSS, "owned": True}])
        result = q.run_rows(rows, trial, lambda: "", lambda row: scores.append(row["case"]))
        self.assertEqual(calls, ["P1", "P2"])
        self.assertFalse(result["stopped_on_prerequisite"])
        self.assertTrue(rows[0]["evaluation"]["valid"])
        self.assertFalse(rows[0]["evaluation"]["healthy"])
        self.assertTrue(rows[1]["evaluation"]["healthy"])
        self.assertFalse(q.all_rows(rows, ("P1", "P2")))

    def test_global_guard_marks_all_unrun_without_any_log_or_setup_call(self):
        rows, calls, reads, scores = self.rows(), [], [], []
        result = q.run_rows(rows, lambda row: calls.append(row["case"]), lambda: reads.append("read") or "",
                            lambda row: scores.append(row["case"]), initial_stop="global source SHA mismatch")
        self.assertEqual(calls, [])
        self.assertEqual(reads, [])
        self.assertEqual(len(scores), 4)
        self.assertEqual(result["dispatched_rows"], 0)
        self.assertTrue(all("global source SHA mismatch" in row["unrun"]["cause"] for row in rows))
        self.assertTrue(all(not row["evaluation"]["valid"] and not row["evaluation"]["healthy"] for row in rows))

    def test_real_run_delegates_to_tested_stop_scheduler(self):
        tree = ast.parse(Path(q.__file__).read_text(encoding="utf-8"))
        real_run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
        calls = [n for n in ast.walk(real_run) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run_rows"]
        self.assertEqual(len(calls), 2)  # normal and global-prerequisite refusal paths
        self.assertFalse(any(isinstance(n, (ast.For, ast.While)) for n in real_run.body))


if __name__ == "__main__":
    unittest.main()
