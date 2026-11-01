"""Magazine setup: bounded native walking to a fresh five-ray firing fixture.

Raster lanes and path arrival are guides. Only the unchanged fan/body guards
at the settled current actor position authorize births. No shot or refill here.
"""
import math
import time
from functools import lru_cache

from gamelab.bots import qa_firearms_magazine_fixture as f
from gamelab.bots import qa_specs_navigation as nav

HEADINGS = tuple((round(math.cos(k*math.pi/4), 12),
                  round(math.sin(k*math.pi/4), 12)) for k in range(8))
REQUIREMENTS = {"fan_angles": list(f.ANGLES), "target_distance": 45,
                "fan_ray_distance": 81, "near_radius": 95,
                "blocker_clearance": 12, "actor_stability": .3,
                "max_moves": 4, "max_seconds_soft": 30,
                "native_leg_limit": 128, "native_diameter": 12,
                "path_tolerance": 4, "path_timeout": 6,
                "rpc_timeout": 5, "teleports": 0}


def blocked(origin, points, rays, nearby):
    """Only explicit, well-formed obstruction permits seeking another location."""
    f.need(type(rays) is list and len(rays) == 5, "missing five native fan rays")
    for ray in rays:
        f.need(type(ray) is dict and ray.get("ok") is True
               and all(type(ray.get(k)) is bool for k in ("wall", "tile")),
               "malformed fan ray; do not seek")
        if ray["wall"]:
            f.need(all(f.finite(ray.get(k)) for k in ("wx", "wy", "wd"))
                   and 0 <= ray["wd"] <= 82 and isinstance(ray.get("wname"), str)
                   and type(ray.get("wsensor")) is bool,
                   "malformed fan wall hit; do not seek")
        if ray["tile"]:
            f.need(all(f.finite(ray.get(k)) for k in ("tx", "ty", "td"))
                   and 0 <= ray["td"] <= 82 and type(ray.get("th")) is int,
                   "malformed fan tile hit; do not seek")
    for unit in f.complete(nearby):
        f.need(type(unit) is dict and isinstance(unit.get("name"), str)
               and isinstance(unit.get("behavior"), str)
               and ("dead" not in unit or type(unit["dead"]) is bool),
               "malformed nearby identity; do not seek")
        if unit.get("behavior") in f.BLOCKERS and unit.get("dead") is not True:
            f.need(all(f.finite(unit.get(k)) for k in ("x", "y")),
                   "malformed fan blocker; do not seek")
        f.need(unit.get("dead") is True or "target_dummy" not in unit["name"],
               "old live dummy remains; do not seek")
    try:
        f.geometry(origin, points, rays, nearby)
    except f.FixtureError as exc:
        f.need(str(exc) in ("uncertified fan ray", "actor/breakable blocks fan ray"),
               "invalid fan observation; do not seek: " + str(exc))
        return True
    return False


@lru_cache(maxsize=16)
def footprint(step, direction):
    dx, dy = direction
    front, back, width = 96+step, -16-step, 48+step
    corners = [(dx*a-dy*b, dy*a+dx*b) for a in (back, front) for b in (-width, width)]
    radius = math.ceil(max(max(abs(x), abs(y)) for x, y in corners)/step)
    cells = tuple((x, y) for y in range(-radius, radius+1) for x in range(-radius, radius+1)
                  if back <= x*step*dx+y*step*dy <= front
                  and abs(-x*step*dy+y*step*dx) <= width)
    return corners, cells


def lanes(terrain, ox=0, oy=0, preferred=(1, 0)):
    """Conservative rotated raster/body guide; native fan remains decisive."""
    if (type(terrain) is not dict or ox != 0 or oy != 0
            or type(terrain.get("size")) is not int
            or type(terrain.get("step")) is not int or terrain["step"] not in (8, 16)
            or not nav.valid_grid(terrain, terrain["step"])):
        return []
    step, n = terrain["step"], terrain["size"]
    if type(step) is not int or step not in (8, 16):
        return []
    mid, rows, result = n//2, terrain["rows"], []
    ordered = sorted(HEADINGS, key=lambda d: (-(d[0]*preferred[0]+d[1]*preferred[1]), d))
    for dx, dy in ordered:
        # Includes actor body, all five81px rays and12px blocker envelope.
        # One extra cell is conservative; _route_targets adds its arrival margin.
        corners, cells = footprint(step, (dx, dy))
        if any(abs(x) > mid*step or abs(y) > mid*step for x, y in corners):
            continue
        if cells and all(0 <= mid+x < n and 0 <= mid+y < n
                         and rows[mid+y][mid+x] in ".@" for x, y in cells):
            result.append(((dx, dy), (-dy, dx)))
    return result


def same_binding(row, previous):
    """Moving identity: unlike actor(row, origin), legal walking may change XY."""
    f.actor(row)
    f.need(f.world(row) == f.world(previous) and row["player"] == previous["player"]
           and row["now"] >= previous["now"] and row["frame"] >= previous["frame"]
           and row["_t"] >= previous["_t"]
           and all((row[h]["id"], row[h]["item_token"]) ==
                   (previous[h]["id"], previous[h]["item_token"]) for h in ("main", "off")),
           "navigation world/player/item identity or clock changed")
    return row


def quiet(status, controller):
    f.need(type(status) is dict and status.get("ok") is True
           and status.get("paused") is False and status.get("intent") == ""
           and not status.get("intentId") and f.finite(status.get("reflexFire"))
           and status["reflexFire"] <= 0 and f.finite(status.get("reflexPotion"))
           and status["reflexPotion"] <= 0 and f.idle(controller)
           and type(controller.get("frames")) is int and controller["frames"] >= 0,
           "navigation requires idle controller/Pilot and disabled reflexes")


class BoundedReads:
    def __init__(self, game):
        self.game = game
        self.gl = game.gl

    def gl_multi(self, commands):
        return self.game.gl_multi(commands, timeout=5)


class Adapter:
    def __init__(self, checks, origin, evidence, sleep):
        self.checks, self.last, self.evidence, self.sleep = checks, origin, evidence, sleep
        self.out, self.reads = checks.out, BoundedReads(checks.g)
        self.g, self.p = self, self

    def frame(self, tag):
        row = self.checks.gl("qa_poseframe", tag, timeout=5)
        f.fresh(row, self.last)
        self.last = same_binding(row, self.last)
        return row

    def pos(self):
        row = self.frame("fs-mag-seek-position")
        return row["x"], row["y"]

    def gl(self, verb, *args):
        row = self.checks.gl(verb, *args, timeout=5)
        f.fresh(row, self.last)
        f.need(verb == "terrain" and row.get("ok") is True
               and row.get("truncated") is False and nav.valid_grid(row, args[1])
               and row.get("size") == int(args[0]*2/args[1])+1
               and all(f.finite(row.get(k)) for k in ("x", "y"))
               and math.dist((row["x"], row["y"]), (self.last["x"], self.last["y"])) <= .01,
               "incomplete/foreign/recentered navigation terrain")
        return row

    def gl_multi(self, commands):
        rows = f.read_batch(self.reads, commands, self.last)
        if all(c[0] == "rayhit" for c in commands):
            # The three guide rays must also refuse malformed data immediately.
            for row in rows:
                blocked(self.last, f.offsets((1, 0)), [row]*5,
                        {"ok": True, "count": 0, "truncated": 0, "units": []})
        return rows

    def settle(self, tag):
        batches = []
        for index in range(2):
            if index:
                self.sleep(.1)
            rows = f.read_batch(self.reads, [["qa_poseframe", tag], ["controller"], ["pilot", "status"]], self.last)
            batches.append(rows)
            self.evidence.setdefault("idle_brackets", []).append(rows)
            same_binding(rows[0], self.last)
            f.actor(rows[0], self.last)
            quiet(rows[2], rows[1])
            self.last = rows[0]
        f.need(batches[1][0]["frame"] >= batches[0][0]["frame"]+2
               and batches[1][1]["frames"] == batches[0][1]["frames"],
               "no two-native-frame stable idle input observation")
        return self.last

    def path_to(self, x, y, tol, timeout):
        f.need(tol == 4 and timeout == 6, "navigation path bounds changed")
        self.settle("fs-mag-prewalk")
        event = {"goal": [x, y], "tol": tol, "timeout": timeout, "dispatch_attempted": True}
        self.evidence.setdefault("navigation_writes", []).append(event)
        try:
            result = self.checks.p.path_to(x, y, tol=tol, timeout=timeout)
            event.update(result=result.result, reason=result.reason,
                         accept=getattr(self.checks.p, "last_accept", {}))
            self.last_accept = getattr(self.checks.p, "last_accept", {})
            f.need(result.result not in ("timeout", "interrupted"), "navigation outcome requires reconciliation")
            # Give existing native release tail time before read-only admission.
            self.sleep(.12)
            self.frame("fs-mag-arrival")  # Moving identity, not the old stationary origin.
            self.settle("fs-mag-postwalk")
            return result
        except Exception as exc:
            event["error"] = repr(exc)
            raise

    def probe(self, direction, tag, walk_origin=None):
        origin = self.frame(tag+"-origin")
        if walk_origin is not None:
            f.need(math.dist((origin["x"], origin["y"]), walk_origin) <= .3,
                   "native fan origin drifted after guide")
        terrain = self.gl("terrain", 160, 8)
        points = f.offsets(direction)
        rows = f.read_batch(self.reads, [["near", 95]] + [
            ["rayhit", origin["x"], origin["y"], origin["x"]+p[0]*81/45,
             origin["y"]+p[1]*81/45] for p in points] + [["qa_poseframe", tag+"-after"]], origin)
        proof = {"origin": origin, "direction": direction, "terrain": terrain, "batch": rows, "clear": False}
        self.evidence.setdefault("fan_probes", []).append(proof)
        same_binding(rows[-1], self.last)
        f.actor(rows[-1], origin)
        self.last = rows[-1]
        obstructed = blocked(origin, points, rows[1:6], rows[0])
        proof["clear"] = not obstructed and (tuple(direction), (-direction[1], direction[0])) in lanes(terrain)
        return proof


def prepare(checks, origin, direction, tag, record, *, walk=None, sleep=time.sleep):
    """One bounded search. No mutation retry or geometry credit from arrival."""
    evidence = {"status": "UNRUN", "requirements": REQUIREMENTS,
                "navigation_writes": [], "fan_probes": [], "teleports": 0,
                "initial_origin": origin, "initial_batch": record.get("geometry_batch"),
                "scope": "setup only; external sole-writer ownership remains required"}
    record["navigation"] = evidence
    adapter = Adapter(checks, origin, evidence, sleep)
    try:
        # Previous owned shot cleanup must be complete before navigation starts.
        f.need(all(r is record or not r.get("input_dispatched")
                   or (r.get("status") == "VALID_FIXTURE_EFFECT_SEPARATELY_REQUIRED"
                       and r.get("binding", {}).get("valid") is True and not r.get("cleanup_errors"))
                   for r in checks.out.get("magazine_fixture_receipts", [])),
               "prior magazine input lacks owned completion/restoration")
        adapter.settle(tag+"-admit")
        predicate = lambda t, x, y: lanes(t, x, y, direction)
        extra = lambda c, grid, xy, dd: adapter.probe(dd, tag+"-seek", xy)
        walk = nav._walk if walk is None else walk
        xy, dd, side, geometry = walk(adapter, predicate, tag+"_fan", 81, 12,
                                     REQUIREMENTS, extra_probe=extra, max_moves=4, max_seconds=30)
        evidence["walk"] = geometry
        f.need(xy is not None and dd is not None and side == (-dd[1], dd[0])
               and tuple(dd) in HEADINGS, "bounded walking found no complete native fan")
        adapter.settle(tag+"-final-idle")
        proof = adapter.probe(tuple(dd), tag+"-final", xy)
        f.need(proof["clear"], "final fresh five-ray/body fan certification failed")
        evidence.update(status="CERTIFIED_SETUP_ONLY", final=proof)
        return proof["batch"][-1], tuple(dd), proof["batch"]
    except Exception as exc:
        evidence.update(status="INVALID_UNRUN_SETUP", error=repr(exc))
        raise f.FixtureError("magazine legal-anchor setup failed: " + repr(exc)) from exc
