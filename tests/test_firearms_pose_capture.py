"""Pure fake capture controls: no live game, AS execution or visual pass."""
import ast
import copy
from pathlib import Path
import unittest

from gamelab.bots.qa_firearms_pose_capture import PoseCapture,NAMES,frame_errors,bracket_errors,idle_controller,world_identity

ROOT=Path(__file__).resolve().parents[1]
EXPECTED=("hwp_rifle_01","")
ANCHOR=(-240,-48)


def frame(sequence=1,now=100):
    return dict(ok=True,tag="rifle-idle-down-pre",sequence=sequence,now=now,frame=1000+sequence,boots=3,_lvl=2,player=44,level="bandit_keep/keep_1",
        x=-240,y=-48,z=0,look_x=1,look_y=0,screen_x=320,screen_y=180,width=640,height=360,scale=.833,timescale=1,
        camera_x=-240,camera_y=-48,prev_x=-240,prev_y=-48,current_x=-240,current_y=-48,
        next_x=-240,next_y=-48,target_x=-240,target_y=-48,window="",gameplay_focus=True,
        main=dict(id="hwp_rifle_01",item_token=1,model_token=1),off=dict(id="",item_token=0,model_token=0))


class FakePath:
    def __init__(self,exists=True):self.exists=exists
    def is_file(self):return self.exists
    def __str__(self):return "fake-only.png"


class Fake:
    POSE_PATTERN="unused fake parser"
    def __init__(self):
        self.out={};self.states=[("down","-","idle")];self.calls=[];self.shots=[]
        self.before=frame();self.after=frame(2,116);self.after["tag"]="rifle-idle-down-post"
        self.image=FakePath();self.clock_reply=dict(ok=True,timescale=1)
        self.after_state=None
        self.g=self
    def gl(self,verb,*args):
        self.calls.append((verb,args))
        if verb=="timescale":return self.clock_reply
        if verb=="qa_poseframe":
            if len(args)!=1 or any(character.isspace() for character in args[0]):
                raise AssertionError("native one-token tag boundary")
            return copy.deepcopy(self.before if args[0].endswith("-pre") else self.after)
        raise AssertionError("unplanned fake API "+verb)
    def since(self,*args):return self.states
    def shot(self,name,settle):
        self.shots.append(name)
        if self.after_state is not None:self.states=self.after_state
        return self.image


def controller(fake):
    capture=PoseCapture(fake);capture.anchor=ANCHOR;capture.player=44;capture.world=world_identity(frame())
    return capture


class PoseCaptureTests(unittest.TestCase):
    def test_actual_camera_platform_displacement_cannot_authorize_later_capture(self):
        actual=frame();actual["y"]=58.34
        self.assertIn("not at legal anchor",frame_errors(actual,EXPECTED,ANCHOR,44))

    def test_bound_capture_retains_unreviewed_visual_and_eight_slots(self):
        fake=Fake();capture=controller(fake)
        capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
        self.assertEqual(fake.shots,[NAMES[0]])
        self.assertEqual(capture.rows[0]["status"],"captured")
        self.assertEqual(capture.rows[0]["visual_verdict"],"unreviewed")
        self.assertFalse(capture.complete)
        self.assertTrue(all(row["status"]=="unrun" for row in capture.rows[1:]))

    def test_missing_nonfinite_wrong_actor_hand_clock_focus_or_projection_stops_before_image(self):
        changes=[("player",45),("x",-200),("z",5),("window","pause"),("gameplay_focus",False),
                 ("screen_x",639),("screen_y",350),("timescale",.1),("next_y",20),
                 ("scale",float("nan")),("height",None),("now",True),("now",-1),("sequence",0)]
        for key,value in changes:
            fake=Fake();fake.before[key]=value;capture=controller(fake)
            with self.subTest(key=key),self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
            self.assertEqual(fake.shots,[])
            self.assertEqual(capture.rows[0]["status"],"invalid")
        for field,value in (("id","hwp_glock_mh_01"),("model_token",-1),("item_token",0)):
            fake=Fake();fake.before["main"][field]=value
            with self.assertRaises(RuntimeError):controller(fake).capture(NAMES[0],("down","-","idle"),0,EXPECTED)
            self.assertEqual(fake.shots,[])

    def test_stale_foreign_level_actor_position_camera_or_applied_model_invalidates_image(self):
        for key,value in (("sequence",1),("frame",1001),("now",100),("now",1000),("player",45),("level","other"),
                          ("x",-239),("camera_x",-239),("look_x",-1)):
            fake=Fake();fake.after[key]=value;capture=controller(fake)
            with self.subTest(key=key),self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
            self.assertEqual(len(fake.shots),1);self.assertEqual(capture.rows[0]["status"],"invalid")
        for field in ("model_token","item_token"):
            fake=Fake();fake.after["main"][field]+=1;capture=controller(fake)
            with self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)

    def test_missing_image_wrong_tag_or_pose_change_never_passes_capture(self):
        for kind in ("missing","tag","pose"):
            fake=Fake();capture=controller(fake)
            if kind=="missing":fake.image=FakePath(False)
            elif kind=="tag":fake.after["tag"]="foreign"
            else:fake.after_state=[("up","-","reloading")]
            with self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
            self.assertEqual(capture.rows[0]["status"],"invalid")

    def test_asymmetric_individually_valid_changed_viewport_and_projection_refuse_bracket(self):
        for key,value in (("width",1280),("height",720),("scale",1.666),("screen_x",322),("screen_y",182)):
            fake=Fake();fake.after[key]=value
            self.assertEqual(frame_errors(fake.before,EXPECTED,ANCHOR,44),[])
            self.assertEqual(frame_errors(fake.after,EXPECTED,ANCHOR,44),[])
            capture=controller(fake)
            with self.subTest(key=key),self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
            self.assertEqual(capture.rows[0]["status"],"invalid")

    def test_foreign_but_consistent_world_with_reused_actor_and_coordinates_refuses_before_image(self):
        for key,value in (("level","other"),("boots",4),("_lvl",3),("_preload",True)):
            fake=Fake();fake.before[key]=value;fake.after[key]=value;capture=controller(fake)
            with self.subTest(key=key),self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
            self.assertEqual(fake.shots,[])

    def test_required_transient_state_not_seen_does_not_capture_or_retry(self):
        fake=Fake();capture=controller(fake)
        with self.assertRaises(RuntimeError):capture.capture(NAMES[5],("kick","straight","firing"),0,EXPECTED,timeout=0)
        self.assertEqual(fake.shots,[]);self.assertEqual(fake.calls,[])
        self.assertEqual(capture.rows[5]["status"],"invalid")
        self.assertTrue(all(row["status"]=="unrun" for i,row in enumerate(capture.rows) if i!=5))

    def test_duplicate_frame_is_not_an_unchanged_retry(self):
        fake=Fake();capture=controller(fake)
        capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
        with self.assertRaises(RuntimeError):capture.capture(NAMES[0],("down","-","idle"),0,EXPECTED)
        self.assertEqual(len(fake.shots),1)

    def test_timescale_refusal_still_owns_one_cleanup_attempt(self):
        fake=Fake();fake.clock_reply=dict(ok=False,timescale=1);capture=controller(fake)
        with self.assertRaises(RuntimeError):capture.set_slow_clock()
        fake.clock_reply=dict(ok=True,timescale=1);capture.restore_clock()
        self.assertFalse(capture.clock_owned)
        self.assertEqual(fake.calls,[("timescale",(.1,)),("timescale",(1,))])

    def test_missing_restore_ack_does_not_silently_pass_or_retry_mutation(self):
        fake=Fake();capture=controller(fake);capture.clock_owned=True
        fake.clock_reply=dict(ok=False)
        for _ in range(2):
            with self.assertRaises(RuntimeError):capture.restore_clock()
        self.assertEqual(fake.calls,[("timescale",(1,))])
        fake=Fake();capture=controller(fake);capture.clock_owned=True;fake.clock_reply=dict(ok=True,timescale=True)
        with self.assertRaises(RuntimeError):capture.restore_clock()

    def test_dash_return_requires_released_input_and_matching_native_full_route(self):
        class Result:ok=True;result="done"
        class Moving(Fake):
            def __init__(self):
                super().__init__();self.at=(-240,58.34);self.p=self;self.walks=0
                self.ctrl=dict(ok=True,held=-16,releasing=False,down=[],mx=0,my=0)
                self.route=dict(ok=True,routed=True,complete=True,planner="Pilot.Repath",diameter=12,nodes=2,
                    fx=-240,fy=58.34,tx=-240,ty=-48,lastX=-240,lastY=-48,length=106.34)
            def gl(self,verb,*args):
                if verb=="controller":return self.ctrl
                if verb=="qa_routeleg":return self.route
                return super().gl(verb,*args)
            def pos(self):return self.at
            def path_to(self,*args,**kwargs):self.walks+=1;self.at=ANCHOR;return Result()
        from unittest.mock import patch
        good=Moving();capture=controller(good)
        with patch("gamelab.bots.qa_firearms_pose_capture.time.sleep"):capture.return_anchor()
        self.assertEqual(good.walks,1);self.assertEqual(good.at,ANCHOR)
        for key,value in (("complete",False),("routed",False),("planner","other"),("length",129),
                          ("length",float("nan")),("nodes",0),("tx",-230),("fx",-200)):
            bad=Moving();bad.route[key]=value
            with self.assertRaises(RuntimeError):controller(bad).return_anchor()
            self.assertEqual(bad.walks,0)
        for key,value in (("held",1),("down",["dash"]),("releasing",True),("my",1)):
            bad=Moving();bad.ctrl[key]=value
            with self.assertRaises(RuntimeError):controller(bad).return_anchor()
            self.assertEqual(bad.walks,0)
        for key,value in (("level","other"),("boots",4),("_lvl",3)):
            bad=Moving();bad.before[key]=value;bad.after[key]=value
            with self.assertRaises(RuntimeError):controller(bad).return_anchor()
            self.assertEqual(bad.walks,0)

    def test_native_probe_is_bounded_generic_and_product_read_only(self):
        source=(ROOT/"mods/gamelab-hands/scripts/GameLab/Verbs_qa_pose_frame.as").read_text()
        for forbidden in ("HWP::", "SetVar(","WriteInput(","RefreshScene(","Resources::", "m_modelTmp =", "SetPosition("):
            self.assertNotIn(forbidden,source)
        for token in ("g_qaPoseItems.length() >= 32","g_qaPoseModels.length() >= 64","record.actor !is player",
                      'RegisterVerb("qa_poseframe", "<tag>"',"ToScreenspace(world)","m_gameCam.m_nextPos",'QAPoseModelToken(item is null ? null : item.m_modelTmp)'):
            self.assertIn(token,source)

    def test_original_fifteen_flags_and_eight_names_remain_with_fail_closed_final_status(self):
        source=(ROOT/"gamelab/bots/fix_firearms_feel.py").read_text()
        tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Checks")
        methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        flags=[]
        for name in ("poses","rifle_poses","pistol_poses"):
            for node in ast.walk(methods[name]):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="flag" and isinstance(node.args[0],ast.Constant):
                    flags.append(node.args[0].value)
        import json
        scenario=json.loads((ROOT/"gamelab/scenarios/fix-firearms-poses.json").read_text())
        wanted=next(x for x in scenario["steps"] if x["do"]=="bot")["expect"]
        self.assertEqual(set(flags),set(wanted));self.assertEqual(len(flags),15)
        self.assertEqual(sum(x["do"]=="log_has" for x in scenario["steps"]),3)
        self.assertEqual(len(NAMES),8)
        self.assertIn('"pose: state" in st and self.pose_capture.complete',source)
        self.assertIn('self.pose_capture.return_anchor()',source)
        self.assertNotIn('self.gl("input", 120, 0, 1, 0, 1, "dash")',source)
        self.assertIn('finally:\n            self.pose_capture.restore_clock()',source)


if __name__=="__main__":unittest.main()
