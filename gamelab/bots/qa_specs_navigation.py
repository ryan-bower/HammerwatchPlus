"""Bounded ordinary walking to fully recertified native QA geometry."""
from collections import deque
import math
import time


def valid_grid(t, step):
    rows, n = t.get("rows", []), t.get("size", 0)
    return bool(t.get("ok") and not t.get("truncated") and t.get("step") == step
                and 3 <= n <= 48 and n % 2 == 1 and len(rows) == n
                and all(isinstance(r, str) and len(r) == n for r in rows))


def connected(t):
    """Conservative body-envelope BFS. Coarse routes never drive input."""
    rows, n, step = t["rows"], t["size"], t["step"]
    mid = n // 2
    def clear(x, y):
        return all(0 <= y+dy < n and 0 <= x+dx < n and rows[y+dy][x+dx] != "#"
                   for dx in (-1, 0, 1) for dy in (-2, -1, 0))
    start = (mid, mid)
    if not clear(*start):
        return {}
    parent, queue = {start: None}, deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            node = (x+dx, y+dy)
            if node not in parent and clear(*node):
                parent[node] = (x, y)
                queue.append(node)
    return parent


def corridor_lanes(t, ox=0, oy=0):
    rows, n, step = t["rows"], t["size"], t["step"]
    mid = n // 2
    result = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        good = True
        for forward in range(-16, 145, 8):
            for side in range(-48, 49, 8):
                x = mid + round((ox+dx*forward-dy*side)/step)
                y = mid + round((oy+dy*forward+dx*side)/step)
                if not (0 <= x < n and 0 <= y < n and rows[y][x] != "#"):
                    good = False
                    break
            if not good:
                break
        if good:
            result.append(((dx, dy), (-dy, dx)))
    return result


def _guide_lanes(grid, cx, cy, predicate, cache):
    """Guide with the *recentered* predicate and one sampled-cell arrival margin.

    round((cell*step+x)/step) is not cell+round(x/step) at half-cell
    offsets. Reindex rows first, then invoke the unchanged center predicate.
    Out-of-window samples are unknown/blocked. A one-cell margin exceeds the
    native Pilot's4px endpoint tolerance; fresh final geometry is still required.
    """
    n, step = grid["size"], grid["step"]
    def at(x, y):
        key = (x, y)
        if key not in cache:
            rows = []
            for iy in range(n):
                sy = iy+y
                if not 0 <= sy < n or abs(x) >= n:
                    rows.append("#"*n)
                elif x >= 0:
                    rows.append(grid["rows"][sy][x:]+"#"*x)
                else:
                    rows.append("#"*(-x)+grid["rows"][sy][:x])
            centered = {**grid, "rows":rows,
                        "x":grid.get("x",0)+x*step,"y":grid.get("y",0)+y*step}
            cache[key] = predicate(centered,0,0)
        return cache[key]
    center = at(cx,cy)
    if not center:
        return [], {"center_lanes":[],"arrival_margin_px":step,"margin_clear":False}
    common = list(dict.fromkeys((tuple(d),tuple(s)) for d,s in center))
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            available = {(tuple(d),tuple(s)) for d,s in at(cx+dx,cy+dy)}
            common = [lane for lane in common if lane in available]
            if not common:
                return [], {"center_lanes":center,"arrival_margin_px":step,"margin_clear":False}
    return common, {"center_lanes":center,"arrival_margin_px":step,"margin_clear":True}


def _route_targets(fine, coarse, origin, predicate, visited, excluded):
    """Raster samples suggest goals; only native Pathfind certifies a route.

    A legal actor position can fail a conservative recentered raster envelope.
    Do not require that approximation to contain the route origin. Final spell
    geometry is still accepted solely from fresh fine samples and native rays.
    """
    candidates = {}
    for label, grid in (("fine", fine), ("coarse", coarse)):
        mid, step = grid["size"] // 2, grid["step"]
        guide_cache = {}
        for iy, row in enumerate(grid["rows"]):
            for ix, cell in enumerate(row):
                if cell == "#":
                    continue
                ox, oy = (ix-mid)*step, (iy-mid)*step
                distance = math.hypot(ox, oy)
                if distance < 8:
                    continue
                world = (origin[0]+ox, origin[1]+oy)
                key = (round(world[0]/8), round(world[1]/8))
                if key in excluded:
                    continue
                lanes, guide_geometry = _guide_lanes(grid, ix-mid, iy-mid, predicate, guide_cache)
                if not lanes:
                    continue
                revisit = min((math.dist(world, p) for p in visited), default=1000)
                score = distance + max(0, 80-revisit)*4
                item = {"goal": world, "key": key, "guide": label+" recentered footprint+arrival margin",
                        "score": score, "provisional_lanes": lanes,"guide_geometry":guide_geometry}
                if key not in candidates or score < candidates[key]["score"]:
                    candidates[key] = item
    if candidates:
        return sorted(candidates.values(), key=lambda q:q["score"])
    # Explore distinct native-reachable room/frontier points when the requested
    # large footprint is not yet visible. No exploration point can pass geometry.
    grid, mid = coarse, coarse["size"]//2
    for iy, row in enumerate(grid["rows"]):
        for ix, cell in enumerate(row):
            if cell == "#":
                continue
            ox, oy = (ix-mid)*grid["step"], (iy-mid)*grid["step"]
            distance = math.hypot(ox, oy)
            if not 64 <= distance <= 240:
                continue
            world = (origin[0]+ox, origin[1]+oy)
            key = (round(world[0]/8), round(world[1]/8))
            if key in excluded:
                continue
            revisit = min((math.dist(world, p) for p in visited), default=1000)
            free = sum(0 <= iy+y < grid["size"] and 0 <= ix+x < grid["size"]
                       and grid["rows"][iy+y][ix+x] != "#"
                       for y in range(-2,3) for x in range(-2,3))
            score = max(0, 128-revisit)*5 - free*3 - distance*.1
            candidates[key] = {"goal":world,"key":key,"guide":"native-path frontier",
                               "score":score,"provisional_lanes":[]}
    return sorted(candidates.values(), key=lambda q:q["score"])


def _departure_sector(origin, goal):
    """Guide-only octant; matches existing eight native exploration headings."""
    angle = math.atan2(goal[1]-origin[1], goal[0]-origin[0])
    return int(math.floor((angle+math.pi/8)/(math.pi/4))) % 8


def _blocked_departure(origin, goal, failures):
    # A failed local departure is not disproved by another far endpoint in the
    # same direction. Only suppress it while still within one fine8px cell.
    return any(math.dist(origin, f["actual"]) <= 8
               and _departure_sector(origin, goal) == f["sector"] for f in failures)


def _walk(c, predicate, tag, ray_distance, ray_half_width, requirements, extra_probe=None):
    attempts, visited, excluded = [], [], set()
    blocked_native = set()
    failed_departures = []
    started = time.monotonic()
    # Twenty movement attempts plus a mandatory terminal observation pass.
    # Reaching a guide on the last allowed move never grants geometry credit;
    # it must still face the unchanged fresh fine/ray predicate.
    for attempt in range(21):
        terminal_observation = attempt == 20 or time.monotonic()-started >= 150
        origin = c.pos()
        fine = c.gl("terrain", 160, 8)
        detail = {"attempt":attempt,"origin":origin,"fine":fine,
                  "requirements":requirements,"candidates":[]}
        attempts.append(detail)
        if (not valid_grid(fine,8) or
                math.dist(origin,(fine.get("x",1e9),fine.get("y",1e9))) > .01):
            detail["failure"] = "fine grid invalid, truncated or not at actual player"
            break
        for direction, side in predicate(fine,0,0):
            key = (round(origin[0]/4),round(origin[1]/4),direction)
            if key in blocked_native:
                continue
            dx,dy = direction
            rays = c.g.gl_multi([["rayhit",origin[0]-dy*w,origin[1]+dx*w,
                                  origin[0]-dy*w+dx*ray_distance,
                                  origin[1]+dx*w+dy*ray_distance]
                                 for w in (-ray_half_width,0,ray_half_width)])
            clear = (len(rays)==3 and all(r.get("ok") and r.get("wall") is False
                                         and r.get("tile") is False for r in rays))
            extra = extra_probe(c,fine,origin,direction) if clear and extra_probe else {"clear":True}
            actual = c.pos()
            stable = math.dist(actual,origin) <= 1
            detail["candidates"].append({"direction":direction,"rays":rays,
                 "clear":clear,"extra":extra,"player_after":actual,"stable":stable})
            if clear and extra["clear"] and stable:
                geometry={"attempts":attempts,"actual":actual,"lane":(direction,side),
                          "requirements":requirements,"native_ray_half_width":ray_half_width,
                          "native_ray_length":ray_distance,"teleports":0,
                          "route_source":"native Pilot.Repath bounded128px legs/Pilot.path_to diameter12; fresh final fine/rays"}
                c.out[tag+"_geometry"]=geometry
                return actual,direction,side,geometry
            blocked_native.add(key)
        if terminal_observation:
            detail["final_recertification_only"] = True
            break
        coarse = c.gl("terrain",240,16)
        detail["coarse"] = coarse
        if not valid_grid(coarse,16):
            detail["failure"] = "coarse guide grid invalid or truncated"
            break
        all_targets=_route_targets(fine,coarse,origin,predicate,visited,excluded)
        available=[t for t in all_targets if not _blocked_departure(origin,t["goal"],failed_departures)]
        targets=available[:8]
        detail["failed_departure_filtered"] = len(all_targets)-len(available)
        detail["route_candidates"]=targets
        if not targets:
            detail["failure"]="no distinct provisional goal or exploration frontier"
            break
        paths=c.g.gl_multi([["qa_routeleg",*t["goal"],128] for t in targets])
        detail["native_paths"]=paths
        if len(paths)!=len(targets):
            detail["failure"]="native path query protocol incomplete"
            break
        reachable=[]
        for target,path in zip(targets,paths):
            numbers=("fx","fy","lastX","lastY","legX","legY","legLength","length")
            valid=(path.get("ok") is True and path.get("planner")=="Pilot.Repath"
                   and path.get("routed") is True and isinstance(path.get("nodes"),int) and not isinstance(path["nodes"],bool) and path["nodes"]>0
                   and all(isinstance(path.get(k),(int,float)) and not isinstance(path[k],bool) and math.isfinite(path[k]) for k in numbers)
                   and path.get("diameter")==12 and path.get("limit")==128
                   and 0 < path["legLength"] <= 128.01
                   and math.dist(origin,(path["fx"],path["fy"])) <= .01
                   and 4 < math.dist(origin,(path["legX"],path["legY"])) <= path["legLength"]+.01
                   and path["length"] >= path["legLength"]-.01)
            complete=(valid and path.get("complete") is True
                      and math.dist(target["goal"],(path["lastX"],path["lastY"]))<=12)
            target["native_complete"]=complete
            target["native_routed_leg"]=bool(valid)
            if valid:
                # A partial native route is exploration only, never a goal or
                # spell certificate. Its bounded real leg can escape a pocket.
                reachable.append((target,path))
            else:
                excluded.add(tuple(target["key"]))
        if not reachable:
            detail["failure"]="queried goals have no usable native Pilot route leg; distinct candidates retained"
            continue
        target,path=min(reachable,key=lambda pair:(not pair[0]["native_complete"],
            pair[0]["score"]+pair[1].get("length",1e6)*.05))
        leg=(path["legX"],path["legY"])
        result=c.p.path_to(*leg,tol=4,timeout=6)
        actual=c.pos()
        detail["walk"]={"goal":target,"native_path":path,"bounded_leg":leg,"result":result.result,
                        "reason":result.reason,"tick":result.tick,
                        "accept":getattr(c.p,"last_accept",{}),"actual":actual,
                        "distance_moved":math.dist(actual,origin)}
        if result.result=="failed" and str(result.reason).startswith("stuck"):
            diagnostic=c.g.gl_multi([["usables"],["near",64]])
            failure={"actual":actual,"goal":leg,"sector":_departure_sector(actual,leg),
                     "native_usable_near":diagnostic}
            failed_departures.append(failure)
            detail["failed_departure"]=failure
        visited.append(origin)
        if path.get("legClipped") is False or result.result=="failed":
            excluded.add(tuple(target["key"]))
        # Native movement outcomes never grant spell-geometry credit. Each next
        # iteration re-reads actual coordinates and the entire original footprint.
        if result.result=="interrupted" and result.reason=="level_changed":
            detail["failure"]="native walk changed level unexpectedly"
            break
    geometry={"attempts":attempts,"requirements":requirements,"teleports":0,
              "error":"bounded native walking failed unchanged full fine/native-ray geometry recertification"}
    c.out[tag+"_geometry"]=geometry
    return None,None,None,geometry


def walk_trident_lane(c, front=26, back_neighbor=False, ray_distance=40, tag="trident", clearance_points=()):
    from gamelab.bots.qa_classes import Checks as ClassChecks
    predicate = lambda t,x,y: ClassChecks.trident_lanes(t,x,y,front=front,
                  back_neighbor=back_neighbor,ray_distance=ray_distance,clearance_points=clearance_points)
    requirements = {"front":front,"back_neighbor":back_neighbor,"ray_distance":ray_distance,
                    "clearance_points":clearance_points,"fine_step":8,"coarse_step":16}
    origin,direction,side,geometry = _walk(c,predicate,tag,ray_distance,8,requirements)
    return ((direction,side) if direction else None,
            "normal-walk full footprint and three native rays verified" if direction else geometry["error"])


def _gale_probe(c, terrain, origin, direction):
    dx,dy = direction
    commands, labels = [], []
    for angle in (0,10,-10):
        a=math.radians(angle)
        fx,fy=dx*math.cos(a)-dy*math.sin(a),dx*math.sin(a)+dy*math.cos(a)
        for width in (-6,0,6):
            start=(origin[0]-fy*width,origin[1]+fx*width)
            commands.append(["rayhit",*start,start[0]+fx*144,start[1]+fy*144])
            labels.append({"fan_angle":angle,"projectile_edge":width})
    rows,n,step=terrain["rows"],terrain["size"],terrain["step"]
    center=n//2
    target_points=[]
    for lateral in (0,math.tan(math.radians(10))*100,-math.tan(math.radians(10))*100):
        ox,oy=dx*100-dy*lateral,dy*100+dx*lateral
        clear=True
        # Entire conservative8px target square, including all circle5 edges.
        for x in (-8,-4,0,4,8):
            for y in (-8,-4,0,4,8):
                ix,iy=center+round((ox+x)/step),center+round((oy+y)/step)
                clear=clear and 0<=ix<n and 0<=iy<n and rows[iy][ix]!="#"
        target_points.append({"relative":[ox,oy],"circle_radius":5,"conservative_square_half":8,"fine_clear":clear})
        world=(origin[0]+ox,origin[1]+oy)
        commands.extend([["rayhit",world[0]-6,world[1],world[0]+6,world[1]],
                         ["rayhit",world[0],world[1]-6,world[0],world[1]+6]])
        labels.extend([{"target_cross":"horizontal","relative":[ox,oy]},
                       {"target_cross":"vertical","relative":[ox,oy]}])
    replies=c.g.gl_multi(commands)
    actual=c.pos()
    clear=(len(replies)==len(commands) and all(r.get("ok") and r.get("wall") is False
           and r.get("tile") is False for r in replies) and all(t["fine_clear"] for t in target_points)
           and math.dist(actual,origin)<=1)
    return {"clear":bool(clear),"targets":target_points,"probes":[{"source":label,"reply":reply}
            for label,reply in zip(labels,replies)],"player_after":actual}


def certified_corridor(c, gale=False):
    requirements = {"back":16,"length":144,"half_width":48,"fine_step":8,"coarse_step":16,
                    "gale_fan_angles":[0,10,-10] if gale else [],"projectile_radius":6 if gale else None}
    origin,direction,side,geometry = _walk(c,corridor_lanes,"certified_corridor",144,12,requirements,
                                         extra_probe=_gale_probe if gale else None)
    return origin,direction,geometry
