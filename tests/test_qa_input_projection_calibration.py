"""Pure proposal controls. These do not execute AngelScript or prove live hits."""
import copy
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/gamelab-hands/scripts/GameLab/Verbs_qa_input_target.as"

# Exact retained c68 row from run20261030-135859. Native input frames remained0.
RECORDED = dict(
    now=16104, gameplay_focus=True, target=[-367.416992188,-10.649999619,0],
    screen=[386.33303833,170.833297729], world=[-368.000396729,-11.000045776,0],
    round_error=.680362523, guard_limit=.100000001,
    world_at_screen_plus_x=[-366.800415039,-11.000045776,0],
    world_at_screen_plus_y=[-368.000396729,-9.800052643,0],
    screen_back=[385.846862793,170.541610718], wnd_width=768,wnd_height=432,
    wnd_scale=.833333313,raw_width=640,raw_height=360,
    camera_pos=[-447.416625977,.350033998],camera_prev=[-447.416625977,.350033998],
    camera_current=[-447.416625977,.350033998],camera_next=[-447.416625977,.350033998],
    camera_target=[-447.416625977,.350033998],actor=[-447.416625977,.350033998,0],input_mouse=[0,0])


def finite(value):
    return type(value) in (int,float) and math.isfinite(value) and -1e8 <= value <= 1e8


def point(value, size):
    return type(value) in (tuple,list) and len(value)==size and all(finite(v) for v in value)


def viewport(screen, dimensions):
    return (point(screen,2) and point(dimensions,2) and min(dimensions)>0
            and 0 <= screen[0] < dimensions[0] and 0 <= screen[1] < dimensions[1])


def projection(target, screen, dimensions, inverse):
    """Independent fake API driver: one local proposal, actual inverse validation."""
    if not point(target,2) or not viewport(screen,dimensions):
        return None
    world=inverse(screen)
    if not point(world,3):
        return None
    error=math.dist(world[:2],target)
    if not finite(error):
        return None
    if error <= .1:
        return tuple(screen)
    px=(screen[0]+1,screen[1]);py=(screen[0],screen[1]+1)
    if not viewport(px,dimensions) or not viewport(py,dimensions):
        return None
    plus_x,plus_y=inverse(px),inverse(py)
    if not point(plus_x,3) or not point(plus_y,3):
        return None
    x=(plus_x[0]-world[0],plus_x[1]-world[1])
    y=(plus_y[0]-world[0],plus_y[1]-world[1])
    determinant=x[0]*y[1]-x[1]*y[0]
    metric=sum(v*v for v in x+y)
    if not finite(determinant) or not finite(metric) or not(metric>0 and abs(determinant)>=.01*metric):
        return None
    residual=(target[0]-world[0],target[1]-world[1])
    delta=((residual[0]*y[1]-residual[1]*y[0])/determinant,
           (x[0]*residual[1]-x[1]*residual[0])/determinant)
    if not point(delta,2) or max(map(abs,delta))>1:
        return None
    candidate=(screen[0]+delta[0],screen[1]+delta[1])
    if not viewport(candidate,dimensions):
        return None
    actual=inverse(candidate)
    if not point(actual,3) or not math.dist(actual[:2],target)<=.1:
        return None
    return candidate


def recorded_inverse():
    calls=[]
    screen=RECORDED["screen"];world=RECORDED["world"]
    x=[a-b for a,b in zip(RECORDED["world_at_screen_plus_x"],world)]
    y=[a-b for a,b in zip(RECORDED["world_at_screen_plus_y"],world)]
    def inverse(at):
        calls.append(tuple(at))
        # This fake affine mapping is just a control compatible with the three
        # retained probes. Only a future actual candidate query can establish it.
        return tuple(world[i]+x[i]*(at[0]-screen[0])+y[i]*(at[1]-screen[1]) for i in range(3))
    return inverse,calls


class FakeHandle:
    def __init__(self):
        self.mouse=(0,0)


class FakeFrame:
    """Cache lifetime model; does not replace the source-order guard checks."""
    def __init__(self):
        self.current=FakeHandle();self.frame=0;self.now=10;self.writes=0
        self.cache=None;self.mouse_writes=0
    def begin(self):
        self.frame+=1;self.cache=None
    def guard(self, screen):
        self.cache=(self.current,self.frame,self.now,self.writes,tuple(screen))
    def valid(self, handle, writes):
        return (self.cache is not None and self.cache[0] is handle and self.current is handle
                and self.cache[1:4]==(self.frame,self.now,writes))
    def write(self, handle):
        before=self.writes
        if not self.valid(handle,before):return False
        self.writes+=1
        return True
    def pin(self, handle, before):
        if not self.valid(handle,before) or self.writes!=before+1:return False
        handle.mouse=self.cache[4];self.mouse_writes+=1;self.cache=None
        return True


def body(text,name):
    match=re.search(r"\b(?:bool|int|string|void)\s+"+name+r"\s*\([^)]*\)[^{]*\{",text)
    if not match:return ""
    start=match.end();depth=1
    for index in range(start,len(text)):
        depth+=(text[index]=="{")-(text[index]=="}")
        if depth==0:return text[start:index]
    return ""


def calibration_source_errors(text):
    """Review anchors for changed methods; unchanged methods retain old hashes."""
    errors=[]
    methods={name:body(text,name) for name in
             ("CursorFinite","CursorFinite2","CursorFinite3","CursorViewport","CursorProjection",
              "CursorCacheCurrent","CursorGuard","PinAndRead","UpdateFrame")}
    required={
        "CursorFinite":("value == value","value >= -100000000.0f","value <= 100000000.0f"),
        "CursorFinite2":("CursorFinite(value.x)","CursorFinite(value.y)"),
        "CursorFinite3":("CursorFinite(value.x)","CursorFinite(value.y)","CursorFinite(value.z)"),
        "CursorViewport":("CursorFinite2(screen)","CursorFinite(width)","CursorFinite(height)",
                          "width > 0 && height > 0","screen.x >= 0 && screen.y >= 0","screen.x < width && screen.y < height"),
        "CursorProjection":("screen = ToScreenspace(xyz(m_world));","if (!CursorViewport(screen)) return false;",
             "if (!CursorFinite3(world)) return false;","if (!CursorFinite(error)) return false;","if (error > 0.1f)",
             "!CursorViewport(screen + vec2(1, 0)) || !CursorViewport(screen + vec2(0, 1))",
             "if (!CursorFinite3(plusX) || !CursorFinite3(plusY)) return false;",
             "!CursorFinite(determinant) || !CursorFinite(metric)",
             "metric > 0 && abs(determinant) >= 0.01f * metric",
             "!CursorFinite2(delta) || abs(delta.x) > 1 || abs(delta.y) > 1",
             "if (!CursorViewport(candidate)) return false;","vec3 actual = ToWorldspace(candidate);",
             "if (!CursorFinite3(actual) || !(dist(xy(actual), m_world) <= 0.1f)) return false;","screen = candidate;"),
        "CursorCacheCurrent":("input !is null && m_guardInput is input && GetInput() is input",
             "m_guardFrame == m_cursorFrame","m_guardTime == int(g_scene.GetTime())","m_guardWrites == writes"),
        "CursorGuard":("if (!SoleOwner())", "input is null || input.UsingGamepad",
             "m_skillName != \"-\" && QATargetSkill(cast<PlayerBase>(GetLocalPlayer()), m_skillName) !is m_skill",
             "if (!CursorProjection(screen))", "if (!CursorViewport(original)) return \"world cursor is outside native viewport\";",
             "FailedProjection(input, original, ToWorldspace(original));",
             "slot < 0 && m_cursorInputs.length() >= 8", "dist(input.MousePos, m_cursorLast[slot]) > 0.01f",
             "dist(input.MousePos, m_cursorOriginal[slot]) > 0.01f", "@m_guardInput = input; m_guardScreen = screen;",
             "m_guardFrame = m_cursorFrame; m_guardTime = int(g_scene.GetTime()); m_guardWrites = g_inputFrames;"),
        "PinAndRead":("if (!CursorCacheCurrent(input, writes) || g_inputFrames != writes + 1) return false;",
             "input.MousePos = m_guardScreen;","@m_guardInput = null;", "vec2 world = xy(ToWorldspace(input.MousePos));"),
        "UpdateFrame":("m_cursorFrame++; @m_guardInput = null;", "string error = CursorGuard(input);",
             "if (!error.isEmpty()) return Abort(error);", "if (!CursorCacheCurrent(input, g_inputFrames)) return Abort(",
             "QAInputSequenceTask::UpdateFrame(ms)","PinAndRead(input, ms, releaseFrame, index, writes)","@m_guardInput = null;")}
    for name,tokens in required.items():
        for token in tokens:
            if token not in methods[name]:errors.append(name+" missing "+token)
    project=methods["CursorProjection"];pin=methods["PinAndRead"];update=methods["UpdateFrame"]
    if re.search(r"\b(?:for|while|do)\b",re.sub(r"//[^\n]*","",project)):
        errors.append("projection retries/iteration")
    if project.count("ToWorldspace(candidate)")!=1:errors.append("candidate inverse count")
    if "ToScreenspace(" in pin:errors.append("pin discarded guarded screen")
    if "CursorCacheCurrent" in pin and "input.MousePos =" in pin and pin.index("CursorCacheCurrent")>pin.index("input.MousePos ="):
        errors.append("pin cache checked after cursor write")
    if "CursorCacheCurrent" in update and "QAInputSequenceTask::UpdateFrame" in update and update.index("CursorCacheCurrent")>update.index("QAInputSequenceTask::UpdateFrame"):
        errors.append("cache checked after button write")
    for name in ("CursorProjection","CursorGuard","CursorCacheCurrent"):
        if any(token in methods[name] for token in ("input.MousePos =","WriteInput(","m_world =","SetPosition(","Focus::Set")):
            errors.append(name+" mutated protected state")
    return errors


class CalibrationTests(unittest.TestCase):
    def test_recorded_basis_one_local_candidate_is_only_a_prediction(self):
        inverse,calls=recorded_inverse()
        candidate=projection(RECORDED["target"][:2],RECORDED["screen"],(640,360),inverse)
        self.assertIsNotNone(candidate)
        self.assertAlmostEqual(candidate[0],386.819216194,places=6)
        self.assertAlmostEqual(candidate[1],171.125004529,places=6)
        self.assertEqual(len(calls),4)
        self.assertEqual(calls[-1],candidate)
        self.assertNotEqual(candidate,tuple(RECORDED["screen"]))

    def test_existing_good_roundtrip_uses_no_basis_or_correction(self):
        calls=[]
        def inverse(at):calls.append(tuple(at));return (4,5,0)
        self.assertEqual(projection((4,5),(10,20),(640,360),inverse),(10,20))
        self.assertEqual(calls,[(10,20)])

    def test_coupled_and_reflected_local_bases_are_solved(self):
        for x,y in (((2,.3),(-.5,1)),((-1,0),(0,1))):
            def inverse(at):return (x[0]*(at[0]-10)+y[0]*(at[1]-20),x[1]*(at[0]-10)+y[1]*(at[1]-20),0)
            target=inverse((10.4,20.3))[:2]
            candidate=projection(target,(10,20),(640,360),inverse)
            self.assertIsNotNone(candidate)
            self.assertLess(math.dist(inverse(candidate)[:2],target),1e-9)

    def test_nonlinear_native_candidate_rejects_without_second_proposal(self):
        good,calls=recorded_inverse()
        def inverse(at):
            value=good(at)
            if len(calls)==4:return (value[0]+.2,value[1],value[2])
            return value
        self.assertIsNone(projection(RECORDED["target"][:2],RECORDED["screen"],(640,360),inverse))
        self.assertEqual(len(calls),4)

    def test_unchanged_strict_point_one_boundary(self):
        for error,valid in ((.099,True),(.101,False)):
            good,calls=recorded_inverse()
            def inverse(at):
                value=good(at)
                return (value[0]+error,value[1],0) if len(calls)==4 else value
            result=projection(RECORDED["target"][:2],RECORDED["screen"],(640,360),inverse)
            self.assertEqual(result is not None,valid)

    def test_singular_nearly_singular_anisotropic_and_zero_bases_reject(self):
        for x,y in (((0,0),(0,0)),((1,0),(2,0)),((1,0),(1,.00001)),((.000001,0),(0,1))):
            calls=[]
            def inverse(at):
                calls.append(at)
                return (x[0]*(at[0]-10)+y[0]*(at[1]-20),x[1]*(at[0]-10)+y[1]*(at[1]-20),0)
            self.assertIsNone(projection((.4,.3),(10,20),(640,360),inverse))
            self.assertEqual(len(calls),3)

    def test_nonfinite_malformed_basis_and_candidate_reject(self):
        for stage in (1,2,3,4):
            for bad in (None,[],[1,2],[1,2,float("nan")],[float("inf"),0,0],[True,0,0],[1e9,0,0]):
                good,calls=recorded_inverse()
                def inverse(at):
                    value=good(at)
                    return bad if len(calls)==stage else value
                self.assertIsNone(projection(RECORDED["target"][:2],RECORDED["screen"],(640,360),inverse))
                self.assertLessEqual(len(calls),4)

    def test_invalid_viewport_and_probe_edges_do_not_query_outside(self):
        for screen,dimensions in (((640,20),(640,360)),((10,20),(0,360)),((10,20),(640,float("nan"))),((639.5,20),(640,360))):
            calls=[]
            def inverse(at):calls.append(at);return (0,0,0)
            self.assertIsNone(projection((.5,.5),screen,dimensions,inverse))
            self.assertLessEqual(len(calls),1)

    def test_excessive_or_outside_local_candidate_rejects_before_validation(self):
        for target,screen in (((2,0),(10,20)),((-.5,.3),(.2,20))):
            calls=[]
            def inverse(at):calls.append(at);return (at[0]-screen[0],at[1]-screen[1],0)
            self.assertIsNone(projection(target,screen,(640,360),inverse))
            self.assertEqual(len(calls),3)

    def test_guarded_point_is_consumed_once_and_does_not_revert(self):
        frame=FakeFrame();frame.begin();handle=frame.current
        frame.guard((386.819216194,171.125004529));before=frame.writes
        self.assertTrue(frame.write(handle));self.assertTrue(frame.pin(handle,before))
        self.assertEqual(handle.mouse,(386.819216194,171.125004529))
        self.assertFalse(frame.pin(handle,before));self.assertEqual(frame.mouse_writes,1)

    def test_missing_stale_handle_frame_clock_or_writer_cache_blocks_input(self):
        for change in ("missing","frame","clock","writes","handle","current"):
            frame=FakeFrame();frame.begin();handle=frame.current;frame.guard((10,20))
            if change=="missing":frame.cache=None
            elif change=="frame":frame.frame+=1
            elif change=="clock":frame.now+=1
            elif change=="writes":frame.writes+=1
            elif change=="handle":handle=FakeHandle()
            else:frame.current=FakeHandle()
            before=frame.writes
            self.assertFalse(frame.write(handle));self.assertEqual(frame.writes,before)
            self.assertEqual(frame.mouse_writes,0)

    def test_new_invocation_invalidates_old_cache_even_at_same_scene_time(self):
        frame=FakeFrame();frame.begin();frame.guard((10,20));frame.begin()
        self.assertFalse(frame.write(frame.current));self.assertEqual(frame.writes,0)

    def test_stale_postwrite_cache_does_not_pin_foreign_or_old_point(self):
        for change in ("frame","clock","writer","handle"):
            frame=FakeFrame();frame.begin();handle=frame.current;frame.guard((10,20));before=frame.writes
            self.assertTrue(frame.write(handle))
            if change=="frame":frame.frame+=1
            elif change=="clock":frame.now+=1
            elif change=="writer":frame.writes+=1
            else:frame.current=FakeHandle()
            self.assertFalse(frame.pin(handle,before));self.assertEqual(handle.mouse,(0,0))

    def test_source_guards_cache_order_and_single_actual_validation(self):
        self.assertEqual(calibration_source_errors(SOURCE.read_text()),[])

    def test_source_mutations_detect_unsafe_fallback_tolerance_and_cache(self):
        source=SOURCE.read_text()
        for before,after in (("<= 0.1f","<= 1.0f"),("input.MousePos = m_guardScreen;","input.MousePos = ToScreenspace(xyz(m_world));"),
             ("m_guardFrame == m_cursorFrame","true"),("m_guardTime == int(g_scene.GetTime())","true"),
             ("GetInput() is input","true"),("m_guardWrites == writes","true"),
             ("abs(delta.x) > 1","abs(delta.x) > 100"),("abs(determinant) >= 0.01f * metric","true"),
             ("vec3 actual = ToWorldspace(candidate);","vec3 actual = xyz(m_world);")):
            self.assertIn(before,source)
            self.assertTrue(calibration_source_errors(source.replace(before,after,1)),before)

    def test_actual_c68_float32_serialization_receipt_is_complete_but_no_action(self):
        from test_qa_input_projection import diagnostic_proof
        accepted=dict(id="c68",player=29241,target_x=-367.417,target_y=-10.65)
        event=dict(id="c68",player=29241,error="world screen roundtrip failed",complete=False,
            frames=0,start=-1,end=16170,samples=[],cursor_restored=True,restore=[],
            projection_failures_seen=1,projection_failures_dropped=0,projection_failures=[copy.deepcopy(RECORDED)])
        self.assertTrue(diagnostic_proof(event,accepted))
        self.assertEqual(event["frames"],0);self.assertFalse(event["complete"])
        for key,delta in (("raw_width",1e-5),("raw_height",1e-5),("wnd_width",1),("wnd_height",1)):
            bad=copy.deepcopy(event);bad["projection_failures"][0][key]+=delta
            self.assertFalse(diagnostic_proof(bad,accepted),key)


if __name__=="__main__":
    unittest.main()
