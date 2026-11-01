"""Read-only projection diagnostic contracts; no native transform implementation."""
import copy
import hashlib
import math
from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mods/gamelab-hands/scripts/GameLab/Verbs_qa_input_target.as"
PROTECTED = {'SoleOwner': 'ccdf98f22b98b55199dcbc72732b54643eb60afa13d1bc575fc65a35818e6a07', 'CursorIndex': '30c8cbebeddd89da4f1283c80a9fe230145deea3130a538037ed685dd5cb5e8e', 'PinAndRead': '3e2a01d291e7ab4cbda478f392e4109dfc88d38df101d20d02b61065e89d9d7a', 'RestoreCursor': '5a39ed3dc903e93a1fa4a3276c9d96b5f3580b9efbcda2e8a6ecefb1c21a490f', 'UpdateFrame': 'c0486325d57d3999e42f674d48d5d1bc41fa5e58127f39e7897613575b6bd2d9', 'VerbQAInputTarget': '47e8b3d74b707393ba9552cfc52fa6edadbc8b5f45ea43a2f8f135e1bee686c0', 'Register_qa_input_target': 'e1c12bde9af165f70f6bdfb1cc05e0498d07817cbee0370eb2b3a6b86383fac3', 'Finish': 'd8fd83648e0e3b453ee498087c2fe8a0bde6992556a3a44dd95c01bb1a495e7a', 'CursorGuard': '90dca9308d6ab33fd4c08dd6b2c066f5ce3eeabe5e6ecd01a2f3db8c8ce11897'}


def body(text, name):
    match = re.search(r"\b(?:bool|int|string|void)\s+" + name + r"\s*\([^)]*\)[^{]*\{", text)
    if not match:
        return ""
    start, depth = match.end(), 1
    for index in range(start, len(text)):
        depth += (text[index] == "{") - (text[index] == "}")
        if depth == 0:
            return text[start:index]
    raise ValueError("unterminated function")


def normalize(text):
    return re.sub(r"\s+", "", re.sub(r"//[^\n]*", "", text))


def preservation_errors(text):
    from gamelab.tests.test_qa_input_projection_calibration import calibration_source_errors
    errors = calibration_source_errors(text)
    for name, expected in PROTECTED.items():
        if name in ("CursorGuard", "PinAndRead", "UpdateFrame"):
            continue
        value = body(text, name)
        if name == "Finish":
            value = re.sub(r'\s*\.Int\("projection_failures_seen", m_projectionFailureSeen\)', '', value)
            value = re.sub(r'\s*\.Int\("projection_failures_dropped", m_projectionFailureSeen - int\(m_projectionFailures.length\(\)\)\)', '', value)
            value = re.sub(r'\s*\.Raw\("projection_failures", RawArray\(m_projectionFailures\)\)', '', value)
        elif name == "CursorGuard":
            value = value.replace('            vec3 projectionWorld = ToWorldspace(screen);\n', '')
            value = value.replace('xy(projectionWorld)', 'xy(ToWorldspace(screen))')
            value = re.sub(r'if \(dist\(xy\(ToWorldspace\(screen\)\), m_world\) > 0\.1f\)\s*\{\s*FailedProjection\(input, screen, projectionWorld\);\s*return "world screen roundtrip failed";\s*\}',
                           'if (dist(xy(ToWorldspace(screen)), m_world) > 0.1f) return "world screen roundtrip failed";', value)
        if hashlib.sha256(normalize(value).encode()).hexdigest() != expected:
            errors.append(name + " controller contract changed")
    return errors


def diagnostic_source_errors(text):
    errors = preservation_errors(text)
    diagnostic = body(text, "FailedProjection")
    if not diagnostic:
        return errors + ["missing failed projection diagnostics"]
    if 'm_projectionFailures.length() >= 1' not in diagnostic or 'm_projectionFailureSeen++' not in diagnostic:
        errors.append("diagnostic retention is not first-failure bounded")
    forbidden = ("WriteInput(", "PinAndRead(", "SetPosition(", "Focus::Set", "SendInput", "SetCursorPos", "input.MousePos =", "m_world =")
    if any(token in diagnostic for token in forbidden):
        errors.append("diagnostic mutates control/runtime state")
    for key in ("target", "screen", "world", "round_error", "guard_limit", "world_at_screen_plus_x", "world_at_screen_plus_y", "screen_back", "wnd_scale", "raw_width", "raw_height", "camera_pos", "camera_prev", "camera_current", "camera_next", "camera_target", "actor", "input_mouse"):
        if '.Raw("' + key + '"' not in diagnostic:
            errors.append("missing native projection field " + key)
    if 'formatFloat(double(value), "", 0, 9)' not in body(text, "ProjectionFloat"):
        errors.append("projection numbers lose native diagnostic precision")
    if 'return "null"' not in body(text, "ProjectionFloat"):
        errors.append("nonfinite diagnostic JSON is not bounded")
    if '.Raw("projection_failures", RawArray(m_projectionFailures))' not in body(text, "Finish"):
        errors.append("abort terminal does not retain diagnostics")
    return errors


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def native_viewport_matches(row):
    # Native int*float is rounded to float32 BEFORE formatFloat(...,9).
    # Reconstruct that order; allow only half a printed decimal unit, not a
    # general geometric tolerance or a looser dimension comparison.
    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]
    try:
        scale = f32(row["wnd_scale"])
        for axis in ("width", "height"):
            expected = f32(f32(row["wnd_" + axis]) * scale)
            if not math.isfinite(expected) or abs(row["raw_" + axis] - expected) > 5.1e-10:
                return False
    except (KeyError, TypeError, ValueError, OverflowError, struct.error):
        return False
    return True


def diagnostic_proof(event, accepted):
    # This certifies failure observability only, NEVER input/ability completion.
    if (type(accepted.get("id")) is not str or not accepted["id"]
            or type(accepted.get("player")) is not int or accepted["player"] <= 0
            or any(not finite(accepted.get(key)) for key in ("target_x", "target_y"))
            or any(type(event.get(key)) is not int for key in
                   ("player", "frames", "start", "end", "projection_failures_seen", "projection_failures_dropped"))):
        return False
    if (event.get("id") != accepted["id"] or event.get("player") != accepted["player"]
            or event.get("error") != "world screen roundtrip failed" or event.get("complete") is not False
            or event.get("frames") != 0 or event.get("start") != -1 or event.get("samples") != []
            or event.get("cursor_restored") is not True or event.get("restore") != []
            or event.get("projection_failures_seen") != 1 or event.get("projection_failures_dropped") != 0):
        return False
    rows = event.get("projection_failures")
    if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
        return False
    row = rows[0]
    for key, length in (("target", 3), ("screen", 2), ("world", 3), ("screen_back", 2),
                        ("world_at_screen_plus_x", 3), ("world_at_screen_plus_y", 3),
                        ("camera_pos", 2), ("camera_prev", 2), ("camera_current", 2),
                        ("camera_next", 2), ("camera_target", 2), ("actor", 3), ("input_mouse", 2)):
        value = row.get(key)
        if type(value) is not list or len(value) != length or not all(finite(item) for item in value):
            return False
    if (type(row.get("gameplay_focus")) is not bool or type(row.get("now")) is not int
            or not 0 <= row["now"] <= event["end"] or row["target"][2] != 0):
        return False
    if any(type(row.get(key)) is not int or row[key] <= 0 for key in ("wnd_width", "wnd_height")):
        return False
    if any(not finite(row.get(key)) for key in ("wnd_scale", "raw_width", "raw_height", "round_error", "guard_limit")):
        return False
    if row["wnd_scale"] <= 0 or abs(row["guard_limit"] - .1) > 1e-8:
        return False
    if not native_viewport_matches(row):
        return False
    if not 0 <= row["screen"][0] < row["raw_width"] or not 0 <= row["screen"][1] < row["raw_height"]:
        return False
    if math.dist(row["target"][:2], [accepted["target_x"], accepted["target_y"]]) > .001:
        return False
    error = math.dist(row["world"][:2], row["target"][:2])
    return error > row["guard_limit"] and abs(error-row["round_error"]) <= 1e-6


def synthetic():
    accepted = dict(id="c74", player=30655, target_x=-407.358, target_y=40.103)
    row = dict(now=17127, gameplay_focus=True, target=[-407.358,40.103,0], screen=[320.5,200],
               world=[-407,40,0], screen_back=[320.5,200], world_at_screen_plus_x=[-406.5,40,0],
               world_at_screen_plus_y=[-407,40.5,0], wnd_width=320,wnd_height=180,wnd_scale=2,
               raw_width=640,raw_height=360,guard_limit=.100000001,
               camera_pos=[-407,-29],camera_prev=[-407,-29],camera_current=[-407,-29],
               camera_next=[-407,-29],camera_target=[-407,-29],actor=[-407.358,-28.897,0],input_mouse=[0,0])
    row["round_error"] = math.dist(row["world"][:2],row["target"][:2])
    event = dict(id="c74",player=30655,error="world screen roundtrip failed",complete=False,frames=0,start=-1,end=17193,
                 samples=[],cursor_restored=True,restore=[],projection_failures_seen=1,
                 projection_failures_dropped=0,projection_failures=[row])
    return event,accepted


class ProjectionDiagnosticTests(unittest.TestCase):
    def test_existing_owner_restoration_input_schedule_and_strict_guard_are_preserved(self):
        self.assertEqual(preservation_errors(SOURCE.read_text()), [])

    def test_failure_source_retains_bounded_precise_native_observations(self):
        self.assertEqual(diagnostic_source_errors(SOURCE.read_text()), [])

    def test_source_negative_controls_detect_tolerance_writes_and_restoration_changes(self):
        source = SOURCE.read_text()
        for changed in (source.replace('> 0.1f', '> 1.0f', 1),
                        source.replace('m_projectionFailureSeen++;', 'input.MousePos = vec2(); m_projectionFailureSeen++;', 1),
                        source.replace('(ours || neutral)', '(true)', 1)):
            self.assertTrue(diagnostic_source_errors(changed))

    def test_synthetic_failure_is_observable_but_supplies_no_action_or_effect_credit(self):
        event,accepted=synthetic()
        self.assertTrue(diagnostic_proof(event,accepted))
        self.assertFalse(event["complete"])
        self.assertEqual(event["frames"],0)

    def test_actual_E005_compact_receipt_lacks_required_projection_facts(self):
        event,accepted=synthetic()
        for key in ("projection_failures", "projection_failures_seen", "projection_failures_dropped"):
            event.pop(key)
        self.assertFalse(diagnostic_proof(event,accepted))

    def test_missing_malformed_or_nonfinite_native_fields_refuse_diagnostic_credit(self):
        for key in ("screen","world","wnd_scale","camera_prev","input_mouse","world_at_screen_plus_x"):
            for value in (None,True,[],float("nan")):
                with self.subTest(key=key,value=value):
                    event,accepted=synthetic();event["projection_failures"][0][key]=value
                    self.assertFalse(diagnostic_proof(event,accepted))

    def test_foreign_target_player_or_inconsistent_projection_error_refuse(self):
        for change in ("player","target","error","viewport"):
            event,accepted=synthetic()
            if change=="player":event["player"]+=1
            elif change=="target":event["projection_failures"][0]["target"][0]+=1
            elif change=="error":event["projection_failures"][0]["round_error"]+=1
            else:event["projection_failures"][0]["screen"][0]=99999
            self.assertFalse(diagnostic_proof(event,accepted))

    def test_truncated_duplicate_and_unrestored_receipts_refuse(self):
        for key,value in (("projection_failures_dropped",1),("projection_failures_seen",2),
                          ("projection_failures_seen",True),("frames",False),
                          ("cursor_restored",False),("frames",1)):
            event,accepted=synthetic();event[key]=value
            self.assertFalse(diagnostic_proof(event,accepted))


if __name__ == "__main__":
    unittest.main()
