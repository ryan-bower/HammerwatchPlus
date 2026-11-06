"""Capture prerequisites, never an automated visual pose verdict."""
import math
import time

NAMES=("rifle idle down","rifle firing straight","rifle reloading up","rifle launcher high",
       "pistols idle up","pistols firing main kick","pistols firing off kick","pistols reloading down")


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def idle_controller(reply):
    return (reply.get("ok") is True and type(reply.get("held")) is int and reply["held"]<=0
            and reply.get("releasing") is False and reply.get("down")==[]
            and all(finite(reply.get(key)) and abs(reply[key])<.0001 for key in ("mx","my")))


def world_identity(row):
    # Native probe construction identity + session.Game's observed non-preload
    # boot generation. No invented durable world GUID or visibility identity.
    if not isinstance(row,dict):return None
    if (row.get("_preload") is True or not isinstance(row.get("level"),str) or not row["level"]
            or any(type(row.get(key)) is not int or row[key]<=0 for key in ("boots","_lvl"))):
        return None
    return row["level"],row["boots"],row["_lvl"]


def frame_errors(row, expected, anchor, player=None, clock=1, world=None):
    errors=[]
    if not expected[0] or any(not isinstance(item_id,str) for item_id in expected):
        return ["missing declared equipment identity"]
    numbers=("x","y","z","look_x","look_y","screen_x","screen_y","width","height","scale","timescale",
             "camera_x","camera_y","prev_x","prev_y","current_x","current_y","next_x","next_y","target_x","target_y")
    if not isinstance(row,dict) or row.get("ok") is not True or any(not finite(row.get(key)) for key in numbers):
        return ["missing/malformed/nonfinite snapshot"]
    if (type(row.get("now")) is not int or type(row.get("sequence")) is not int
            or type(row.get("frame")) is not int or row["frame"]<0
            or type(row.get("player")) is not int or row["player"]<=0
            or not isinstance(row.get("level"),str) or not row["level"]):
        errors.append("missing native identity/clock")
    elif row["now"]<0 or row["sequence"]<=0:
        errors.append("invalid native identity/clock")
    if world_identity(row) is None or (world is not None and world_identity(row)!=world):
        errors.append("certified anchor world identity changed")
    if player is not None and row.get("player")!=player:errors.append("actor identity changed")
    if row.get("window")!="" or row.get("gameplay_focus") is not True:errors.append("menu/focus prerequisite")
    if abs(row["timescale"]-clock)>.0001:errors.append("wrong native timescale")
    if math.dist((row["x"],row["y"]),anchor)>2 or abs(row["z"])>.1:errors.append("not at legal anchor")
    if not (row["width"]>=320 and row["height"]>=240 and row["scale"]>0
            and 96<=row["screen_x"]<=row["width"]-96 and 80<=row["screen_y"]<=row["height"]-100):
        errors.append("actor projection lacks capture margin")
    camera=(row["camera_x"],row["camera_y"])
    if any(math.dist(camera,(row[key+"_x"],row[key+"_y"]))>.5 for key in ("prev","current","next","target")):
        errors.append("camera unsettled")
    for hand,item_id in zip(("main","off"),expected):
        value=row.get(hand)
        if (not isinstance(value,dict) or value.get("id")!=item_id
                or type(value.get("item_token")) is not int or type(value.get("model_token")) is not int
                or value["item_token"]<0 or value["model_token"]<0
                or (bool(item_id)!=(value["item_token"]>0))):
            errors.append(hand+" equipment/handle binding")
    return errors


def bracket_errors(before,after,expected,anchor,player,clock,world=None):
    errors=frame_errors(before,expected,anchor,player,clock,world)+frame_errors(after,expected,anchor,player,clock,world)
    if errors:return errors
    if (after["sequence"]!=before["sequence"]+1 or not 0<after["now"]-before["now"]<=250
            or after["frame"]<=before["frame"] or world_identity(before)!=world_identity(after)):
        errors.append("stale/foreign capture bracket")
    # Window dimensions/scale are constant during a valid capture. Compare
    # their actual native serialized values exactly; no transform tolerance.
    if any(before[key]!=after[key] for key in ("width","height","scale")):
        errors.append("viewport changed during capture")
    # One raw screenshot pixel is a capture-stability limit, not a projection
    # inverse, visibility, pose-angle or duration tolerance.
    if math.dist((before["screen_x"],before["screen_y"]),(after["screen_x"],after["screen_y"]))>1:
        errors.append("actor projection moved during capture")
    if math.dist((before["x"],before["y"]),(after["x"],after["y"]))>.5:errors.append("actor moved during capture")
    if math.dist((before["look_x"],before["look_y"]),(after["look_x"],after["look_y"]))>.01:
        errors.append("actor direction changed during capture")
    if math.dist((before["camera_x"],before["camera_y"]),(after["camera_x"],after["camera_y"]))>.5:
        errors.append("camera moved during capture")
    if any(before[hand]!=after[hand] for hand in ("main","off")):errors.append("equipped item/model changed during capture")
    return errors


class PoseCapture:
    def __init__(self,c):
        self.c=c;self.anchor=None;self.player=None;self.world=None;self.direction=None;self.clock=1
        self.clock_owned=False;self.restore_attempted=False
        self.rows=[dict(name=name,status="unrun",visual_verdict="unreviewed") for name in NAMES]
        c.out["pose_captures"]=self.rows
        self.clock_rows=[];c.out["pose_clock"]=self.clock_rows

    def establish_anchor(self):
        from gamelab.bots.qa_firearms_missing_orbs import Checks as Dash
        from gamelab.bots.qa_specs_navigation import _walk
        origin,direction,_,geometry=_walk(self.c,Dash.dash_lanes,"pose_capture_anchor",110,6,
            {"bidirectional_length":110,"native_body_diameter":12,"max_path_length":137.5,
             "fine_step":8,"coarse_step":16,"purpose":"legal dash path, landing and return; no render claim"},
            extra_probe=Dash.dash_probe)
        self.c.out["pose_anchor_geometry"]=geometry
        if direction is None:raise RuntimeError("pose capture legal corridor unavailable")
        self.anchor=tuple(origin);self.direction=direction
        before=self.c.gl("qa_poseframe","pose-anchor-pre")
        time.sleep(.12)
        after=self.c.gl("qa_poseframe","pose-anchor-post")
        expected=(before.get("main",{}).get("id"),before.get("off",{}).get("id"))
        self.player=before.get("player")
        self.world=world_identity(before)
        errors=bracket_errors(before,after,expected,self.anchor,self.player,1,self.world)
        self.c.out["pose_anchor_binding"]={"before":before,"after":after,"world":self.world,"errors":errors}
        if errors:raise RuntimeError("pose anchor/camera prerequisites: "+str(errors))

    def return_anchor(self):
        # Only after the certified real dash, never teleport or modify the camera.
        current=self.c.pos()
        receipt={"status":"invalid","before":current,"anchor":self.anchor}
        self.c.out["pose_anchor_return"]=receipt
        receipt["world_before"]=self.c.gl("qa_poseframe","pose-return-pre")
        if (world_identity(receipt["world_before"])!=self.world
                or receipt["world_before"].get("player")!=self.player):
            raise RuntimeError("anchor return world/actor changed")
        if math.dist(current,self.anchor)>114:raise RuntimeError("dash exceeded certified landing")
        receipt["controller"]=self.c.gl("controller")
        if not idle_controller(receipt["controller"]):raise RuntimeError("dash input has not released")
        route=self.c.gl("qa_routeleg",*self.anchor,128)
        receipt["route"]=route
        if (route.get("ok") is not True or route.get("routed") is not True or route.get("complete") is not True
                or route.get("planner")!="Pilot.Repath" or route.get("diameter")!=12
                or type(route.get("nodes")) is not int or route["nodes"]<=0
                or not finite(route.get("length")) or not math.dist(current,self.anchor)-12<=route["length"]<=128
                or any(not finite(route.get(key)) for key in ("fx","fy","tx","ty","lastX","lastY"))
                or math.dist(current,(route.get("fx",1e9),route.get("fy",1e9)))>1
                or math.dist(self.anchor,(route.get("tx",1e9),route.get("ty",1e9)))>.01
                or math.dist(self.anchor,(route.get("lastX",1e9),route.get("lastY",1e9)))>12):
            raise RuntimeError("no certified legal anchor return route")
        result=self.c.p.path_to(*self.anchor,tol=2,timeout=15)
        receipt.update(result=result.result,actual=self.c.pos())
        if not result.ok or math.dist(self.c.pos(),self.anchor)>2:raise RuntimeError("anchor return failed")
        receipt["world_after"]=self.c.gl("qa_poseframe","pose-return-post")
        if (world_identity(receipt["world_after"])!=self.world
                or receipt["world_after"].get("player")!=self.player):
            raise RuntimeError("anchor return world/actor changed")
        time.sleep(.3)
        receipt["status"]="returned"

    def set_slow_clock(self):
        self.clock_owned=True;self.restore_attempted=False
        reply=self.c.gl("timescale",.1)
        self.clock_rows.append({"requested":.1,"reply":reply})
        if reply.get("ok") is not True or not finite(reply.get("timescale")) or abs(reply["timescale"]-.1)>.0001:
            raise RuntimeError("slow capture clock refused")
        self.clock=.1

    def restore_clock(self):
        if not self.clock_owned:return
        if self.restore_attempted:raise RuntimeError("clock restore unconfirmed; no repeated mutation")
        self.restore_attempted=True
        reply=self.c.gl("timescale",1)
        self.clock_rows.append({"requested":1,"reply":reply})
        if reply.get("ok") is not True or not finite(reply.get("timescale")) or reply["timescale"]!=1:
            raise RuntimeError("clock restore refused")
        self.clock=1;self.clock_owned=False

    def capture(self,name,wanted,marker,expected,timeout=1.5):
        row=self.rows[NAMES.index(name)]
        tag=name.replace(" ","-")  # GL arguments are whitespace-delimited.
        if row["status"]!="unrun":raise RuntimeError("duplicate capture refused")
        row.update(status="invalid",wanted=list(wanted),expected_items=list(expected),visual_verdict="unreviewed")
        deadline=time.monotonic()+timeout
        # Bound waiting for a producer state; this does not retry a screenshot.
        while time.monotonic()<deadline:
            states=self.c.since(marker,self.c.POSE_PATTERN)
            if states and tuple(states[-1])==tuple(wanted):break
            time.sleep(.025)
        else:
            row["errors"]=["required fresh pose state not observed"]
            raise RuntimeError("required fresh pose state not observed: "+name)
        before=self.c.gl("qa_poseframe",tag+"-pre")
        row["before"]=before
        errors=frame_errors(before,expected,self.anchor,self.player,self.clock,self.world)
        if before.get("tag")!=tag+"-pre":errors.append("foreign capture tag")
        if errors:row["errors"]=errors;raise RuntimeError("capture prerequisites failed: "+str(errors))
        path=self.c.g.shot(name,settle=False)
        after=self.c.gl("qa_poseframe",tag+"-post")
        states=self.c.since(marker,self.c.POSE_PATTERN)
        errors=bracket_errors(before,after,expected,self.anchor,self.player,self.clock,self.world)
        if before.get("tag")!=tag+"-pre" or after.get("tag")!=tag+"-post":errors.append("foreign capture tag")
        if not path or not path.is_file():errors.append("actual image missing")
        if not states or tuple(states[-1])!=tuple(wanted):errors.append("pose changed across capture")
        row.update(after=after,path=str(path) if path else None,errors=errors)
        if errors:raise RuntimeError("capture invalid: "+str(errors))
        row.update(status="captured",scope="bound prerequisites only; actual image/angle/per-hand render review required")

    @property
    def complete(self):
        return all(row["status"]=="captured" for row in self.rows)
