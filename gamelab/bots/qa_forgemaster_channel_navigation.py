"""S4 setup only: legal bounded walking, fresh complete200px certification.

Raster candidates and native path arrival never grant channel-fixture credit.
No teleport, seed change, activation, buff/resource/cooldown or product writer.
"""
import math

from gamelab.bots import qa_specs_navigation as nav

AXES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def lengths(terrain, step):
    """Same cardinal three-cell strip as S4's old guard, complete grids only."""
    if (type(terrain) is not dict or type(step) is not int or step not in (8, 10, 16)
            or terrain.get("ok") is not True or terrain.get("truncated") is not False or not nav.valid_grid(terrain, step)):
        return []
    rows, n = terrain["rows"], terrain["size"]
    center = n//2
    out = []
    for dx, dy in AXES:
        far = 0
        for k in range(1, center+1):
            cells = [(center+dx*k+dy*s, center+dy*k+dx*s) for s in (-1, 0, 1)]
            if not all(0 <= x < n and 0 <= y < n and rows[y][x] in ".@" for x, y in cells):
                break
            far = k*step
        out.append({"direction": (dx, dy), "side": (-dy, dx), "free": far})
    return out


def guide_lanes(terrain, ox=0, oy=0):
    # _walk rec enters the actual source grid before calling this predicate.
    # Its160/8 fine grid cannot hold200px;128px guides only propose movement.
    if ox != 0 or oy != 0:
        return []
    return [(r["direction"], r["side"]) for r in lengths(terrain, terrain.get("step")) if r["free"] >= 128]


class MapRefusal(RuntimeError):
    def __init__(self, evidence):
        super().__init__("incomplete or foreign final terrain certificate")
        self.evidence = evidence


def owned_nr(reply):
    return (type(reply) is dict and reply.get("ok") is True and reply.get("class") == "hwp_priest_forgemaster"
        and reply.get("skill") == "hwp_pri_necrotic_resurrection" and reply.get("matches") == 1
        and reply.get("truncated") is False and type(reply.get("unit")) is int and reply["unit"] > 0)


def prepare_forge_lane(c, tag):
    """Reuse native qa_routeleg/Pilot route validation; no cached-origin fallback."""
    probes = []
    before = c.gl("skillcost", "hwp_pri_necrotic_resurrection", "hwp_priest_forgemaster")
    if not owned_nr(before):
        return None, {"valid": False, "owner_before": before, "failure": "no exact owned local Forgemaster NR before walking", "teleports": 0}
    def full_probe(checks, guide, origin, direction):
        terrain = checks.gl("terrain", 220, 10)  #45x45, below native48-cell cap
        proof = {"clear": False, "terrain": terrain, "origin": origin, "direction": direction}
        probes.append(proof)
        complete = (type(terrain) is dict and terrain.get("ok") is True and terrain.get("truncated") is False
            and nav.valid_grid(terrain, 10) and terrain["size"] == 45
            and all(type(terrain.get(k)) in (int, float) and math.isfinite(terrain[k]) for k in ("x", "y"))
            and math.dist(origin, (terrain["x"], terrain["y"])) <= .01
            and terrain["rows"][22][22] == "@")
        if not complete:
            proof["failure"] = "full45x45/nontruncated grid is not at the current actual endpoint"
            raise MapRefusal(proof)  #Do not retry/move on an invalid observation.
        lanes = lengths(terrain, 10)
        matching = [r for r in lanes if r["direction"] == tuple(direction)]
        actual = checks.pos()
        proof.update(lanes=lanes, player_after=actual,
            free=matching[0]["free"] if len(matching) == 1 else 0,
            clear=bool(len(matching) == 1 and matching[0]["free"] >= 200 and math.dist(actual, origin) <= .01))
        return proof

    requirements = {"length": 200, "three_cell_step": 10, "full_radius": 220, "full_size": 45,
        "guide_only_length": 128, "guide_steps": [8, 16], "max_moves": 3, "max_seconds": 12,
        "per_leg_timeout": 6, "max_leg_length": 128, "native_route_diameter": 12}
    try:
        origin, direction, side, walk = nav._walk(c, guide_lanes, tag+"_forge_lane", 200, 10,
            requirements, extra_probe=full_probe, max_moves=3, max_seconds=12)
    except MapRefusal as exc:
        return None, {"valid": False, "owner_before": before, "probes": probes, "failure": str(exc), "refusal": exc.evidence, "teleports": 0}
    after = c.gl("skillcost", "hwp_pri_necrotic_resurrection", "hwp_priest_forgemaster")
    actual_endpoint = c.pos()
    matching = [candidate for attempt in walk.get("attempts", []) for candidate in attempt.get("candidates", [])
        if tuple(candidate.get("direction", ())) == tuple(direction or ())
        and candidate.get("clear") is True and candidate.get("stable") is True
        and candidate.get("extra", {}).get("clear") is True]
    proof = matching[-1]["extra"] if matching else {}
    certified = (owned_nr(after) and after["unit"] == before["unit"]
        and origin is not None and direction is not None and side is not None and proof
        and proof.get("free", 0) >= 200 and math.dist(origin, proof["origin"]) <= .01
        and math.dist(origin, proof["player_after"]) <= .01 and math.dist(actual_endpoint, origin) <= .01)
    geometry = {"valid": bool(certified), "direction": direction, "free": proof.get("free", 0),
        "origin": actual_endpoint, "native_arrival": origin, "probes": probes, "walk": walk, "teleports": 0,
        "owner_before": before, "owner_after": after,
        "requirements": requirements, "scope": "setup certificate only; no channel/payment/cancel effect credit"}
    if not certified:
        geometry["failure"] = "native arrival lacks unchanged complete200px current endpoint geometry"
        return None, geometry
    c.start = tuple(actual_endpoint)  #inherited origin() must not send later fixtures back to mission start
    return tuple(direction), geometry
