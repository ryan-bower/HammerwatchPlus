"""Setup bot: stand the player inside the nearest exit's area, without walking there (the walk
is the Pilot's exit intent's job, and a random floor can leave it with no route). As
exit_areas.py does: the sensor nearest the centroid of the units the exit's areas report inside,
then the measurement verb teleport onto it. Returns whether the player is inside an area and
whether the exit is the top usable."""
import math


def run(p):
    ex = p.cmd("exitareas", 600)
    ins = [u for a in ex.get("areas", []) for u in a.get("inside", []) if u["unit"]]
    sensors = [s for s in ex.get("sensors", []) if s["name"].startswith(":Physics")]
    if not ins or not sensors:
        return {"in_area": False, "why": "no area units or sensors", "exit": ex}
    cx = sum(u["x"] for u in ins) / len(ins)
    cy = sum(u["y"] for u in ins) / len(ins)
    sensor = min(sensors, key=lambda s: math.hypot(s["x"] - cx, s["y"] - cy))
    p.cmd("teleport", sensor["x"], sensor["y"])
    p.wait(500)
    after = p.cmd("exitareas", 600)
    in_area = any(a.get("playerInside") for a in after.get("areas", []))
    usables = p.cmd("usables")
    return {"in_area": in_area, "sensor": sensor, "areas": after.get("areas"), "usables": usables}
