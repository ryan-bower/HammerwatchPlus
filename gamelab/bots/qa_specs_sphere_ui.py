"""Actual native sphere offers, physical use, native menu pick and widget capture.

This is controlled acquisition: original production spheres are spawned in an
emptied floor. Orb choices/RNG/skill state are never rewritten. The pick uses
the actual open menu callback, like the existing shop harness. Screenshots and
native widget text are evidence for subsequent independent visual/source review;
this bot does not claim complete layout or ordinary world-drop coverage.
"""
import json
import math
from dataclasses import asdict
import re
import time
from pathlib import Path

from gamelab.bots.qa_specs_ordinary import Checks
from gamelab.bots.qa_firearms_input_sequence import sequence_protocol

SPHERE = "items/skill_sphere.unit"


def plain(text):
    return re.sub(r"\\c[0-9a-fA-F]{6}|\\[dz]", "", text or "").strip()


def offer_valid(row, quality_values):
    if row.get("present") is False:
        return True
    if row.get("present") is not True or not isinstance(quality_values, dict):
        return False
    title, name, desc = map(plain, (row.get("rendered_name"), row.get("localized_name"),
                                  row.get("rendered_description")))
    return bool(row.get("eligible") and row.get("widget_present") and row.get("widget_visible")
                and row.get("name_widget") and row.get("description_widget") and row.get("icon")
                and row.get("id") and row.get("parent") and name and not name.startswith(".")
                and title.endswith(name + " " + str(row.get("next_level"))) and desc
                and not desc.startswith(".") and ".skills." not in desc and ".hwp." not in desc
                and not re.search(r"\{[a-z0-9_-]+\}", desc)
                and type(row.get("level")) is int and type(row.get("next_level")) is int
                and row["next_level"] == row["level"] + 1
                and type(row.get("quality")) is int and row["quality"] in quality_values.values())


def contact_sphere(c, uid, spawned, receipt):
    """Enter the original sphere sensor by bounded ordinary walking only.

    PowerupUsable registers through Collide, not a distance poll. A static
    sensor spawned on an already resting player may not have produced entry.
    No AddUsable/Use/SetUsed/collision writer is called by this fixture.
    """
    finite = lambda value: type(value) in (int, float) and math.isfinite(value)
    if (spawned.get("ok") is not True or spawned.get("unit") != uid
            or spawned.get("name") != SPHERE
            or not all(finite(spawned.get(k)) for k in ("x", "y"))):
        return {"ok": False, "usables": []}
    sx, sy = spawned["x"], spawned["y"]
    receipt["physical_contact"] = []
    nearby = {"ok": False, "usables": []}
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                   (1, 1), (1, -1), (-1, 1), (-1, -1)):
        away = c.p.path_to(sx + 48*dx, sy + 48*dy, tol=2, until=["dead"], timeout=6)
        outside = c.gl("state")
        player = outside.get("player", {})
        position = tuple(player.get(k) for k in ("x", "y"))
        distance = math.dist(position, (sx, sy)) if all(finite(v) for v in position) else None
        row = {"away": asdict(away), "outside": outside, "outside_distance": distance,
               "sensor_center": [sx, sy], "sensor_radius": 9, "pilot_body_diameter": 12}
        receipt["physical_contact"].append(row)
        if player.get("dead") is True:
            return nearby
        # The native9px sphere sensor plus the Pilot's12px body is fully
        # separated here, independent of whether the route ended successfully.
        if distance is None or not 28 <= distance <= 90:
            continue
        returned = c.p.path_to(sx, sy, tol=2, until=["dead"], timeout=8)
        inside = c.gl("state")
        player = inside.get("player", {})
        position = tuple(player.get(k) for k in ("x", "y"))
        distance = math.dist(position, (sx, sy)) if all(finite(v) for v in position) else None
        row.update(returned=asdict(returned), inside=inside, inside_distance=distance, usable_reads=[])
        if player.get("dead") is True:
            return nearby
        if distance is None or distance > 3:
            continue
        for _ in range(5):
            nearby = c.gl("usables")
            row["usable_reads"].append(nearby)
            targets = [u for u in nearby.get("usables", []) if u.get("unit", {}).get("unit") == uid]
            if (nearby.get("ok") is True and len(nearby.get("usables", [])) <= 32 and len(targets) == 1
                    and targets[0].get("top") is True and targets[0].get("canUse") is True
                    and targets[0].get("unit", {}).get("name") == SPHERE):
                return nearby
            time.sleep(.1)
    return nearby


def open_sphere(c, uid, spawned):
    """Physical native Use input, without waiting on a paused gameplay intent.

    GiveSkillSphereMenu pauses gameplay before marking the sphere used. A
    blocking Pilot.use cannot finish until after the choice, because its frame
    updater returns when paused. Require the actual top usable first, post one
    real Use frame, then observe the actual matching native menu independently.
    """
    nearby = c.gl("usables")
    receipt = {"before_usables": nearby, "valid": False, "menu_reads": []}
    initial = [u for u in nearby.get("usables", []) if u.get("unit", {}).get("unit") == uid]
    initial_ready = (nearby.get("ok") is True and len(nearby.get("usables", [])) <= 32 and len(initial) == 1
                     and initial[0].get("top") is True and initial[0].get("canUse") is True
                     and initial[0].get("unit", {}).get("name") == SPHERE)
    if not initial_ready:
        nearby = contact_sphere(c, uid, spawned, receipt)
    receipt["validated_usables"] = nearby
    targets = [row for row in nearby.get("usables", [])
               if row.get("unit", {}).get("unit") == uid]
    valid = (nearby.get("ok") is True and len(nearby.get("usables", [])) <= 32 and len(targets) == 1
             and targets[0].get("top") is True and targets[0].get("canUse") is True
             and targets[0].get("unit", {}).get("name") == SPHERE)
    receipt["valid"] = bool(valid)
    if not valid:
        return receipt, {}
    tag = "sphere-use-" + str(uid) + "-" + str(time.time_ns())
    accepted = c.gl("inputsequence", tag, "1/0/0/1/0/use")
    receipt["accepted"] = accepted
    receipt["sequence_tag"] = tag
    # EndStep emits this actual one-frame write receipt BEFORE native Use opens
    # the paused menu. Pump without reopening the console during focus wait;
    # wait for the release-tail terminal only AFTER the native pick resumes it.
    first_write = c.g.wait_gl(lambda row: row.get("ev") == "input_done"
                             and row.get("sequence") == tag, timeout=10) or {}
    receipt["first_write"] = first_write
    offered = {}
    for _ in range(12):
        offered = c.gl("sphereui")
        receipt["menu_reads"].append(offered)
        if offered.get("open") is True:
            break
        time.sleep(.1)
    receipt["valid"] = bool(valid and accepted.get("ok") is True and first_write.get("sequence") == tag
                            and first_write.get("frames", 0) >= 1 and offered.get("open") is True
                            and offered.get("sphere_unit_id") == uid)
    return receipt, offered


def run(pilot, cls, mode="one", max_picks=128):
    c, picks, seen = Checks(pilot), [], set()
    if mode not in ("one", "all") or not 1 <= max_picks <= 128:
        raise ValueError("requires one/all and a fixed1..128 menu-pick bound")
    inventory = json.loads((Path(__file__).resolve().parents[2]
                            / "docs/generated/qa_specs_inventory.json").read_text(encoding="utf-8"))
    skill_rows = [row for row in inventory["entries"] if row["skill_id"] in c.expected_skills(cls)]
    orb_rows = {orb["orb_id"]: orb for skill in skill_rows for orb in skill["orbs"]}
    wanted = {(oid, row["rank"]) for oid, orb in orb_rows.items() for row in orb["ranks"]}
    expected = {(oid, row["rank"]): {"quality": row["quality"], "expected": row["expected"],
                                    "source": orb["sources"]}
                for oid, orb in orb_rows.items() for row in orb["ranks"]}
    c.out["requested"] = {"class": cls, "mode": mode, "quality_count": len(wanted), "max_picks": max_picks}
    try:
        if not c.new_char(cls, "QAOrbUI" + cls.rsplit("_", 1)[-1]):
            return {**c.out, "notes": c.notes}
        c.gl("xp", 1301032)
        start = c.gl("state")
        skills = {sid: c.gl("skilltip", sid).get("level") for sid in c.expected_skills(cls)}
        no_orbs = {oid: c.gl("orb", oid, 0).get("level") for oid in orb_rows}
        fresh = (start.get("player", {}).get("class") == cls
                 and start.get("player", {}).get("level") == 20
                 and len(skill_rows) == 2 and all(level == 1 for level in skills.values())
                 and all(level == 0 for level in no_orbs.values()))
        c.flag("sphere_ui_fresh_native_class", bool(fresh), str({"state": start, "skills": skills, "orb_reads": no_orbs}))
        if not fresh:
            return {**c.out, "notes": c.notes}
        entered = c.gl("mission", "bandit_keep", 0)
        floor = entered.get("ok") and c.wait_phase("mission", 90)
        c.flag("sphere_ui_floor", bool(floor), str(entered))
        if not floor:
            return {**c.out, "notes": c.notes}
        time.sleep(2)
        c.god_on()
        c.gl("timescale", 1)
        c.gl("kill", 6000, "tag:enemy")
        controls = c.gl("cvars", "cht_god", "g_timescale").get("cvars", {})
        c.flag("sphere_ui_controlled_fixture", controls.get("cht_god") == 1 and controls.get("g_timescale") == 1,
               str(controls))
        all_valid = True
        for index in range(max_picks):
            before = c.gl("sphereui")
            valid_before = (before.get("ok") is True and before.get("open") is False
                            and before.get("possible_truncated") == 0
                            and c.gl("state").get("window") == "")
            if not valid_before or before.get("possible_count", 0) == 0:
                c.out["last_empty_or_invalid"] = before
                all_valid = False
                break
            # Native consumed spheres stay hidden/noncolliding; do not pretend
            # Actor-only kill removes these nonActor original fixtures. The
            # fixed128-pick bound limits scene objects, and usable-list state is
            # independently checked before and after every native acquisition.
            spawned = c.gl("spawn", SPHERE, 0, 0)
            uid = spawned.get("unit")
            if not spawned.get("ok") or not isinstance(uid, int):
                c.out["spawn_failed"] = spawned
                all_valid = False
                break
            time.sleep(.15)  # native sensor collision/usable registration
            used, offered = open_sphere(c, uid, spawned)
            cards = offered.get("offers", [])
            qualities = offered.get("quality_values", {})
            menu_valid = (used.get("valid") is True and offered.get("ok") is True and offered.get("open") is True
                          and offered.get("sphere_present") is True and offered.get("sphere_used") is False
                          and offered.get("sphere_unit_id") == uid and offered.get("sphere_unit") == SPHERE
                          and offered.get("possible_truncated") == 0
                          and len(cards) == 3 and isinstance(qualities, dict) and len(qualities) == 4
                          and all(offer_valid(row, qualities) for row in cards))
            options = [(i, row) for i, row in enumerate(cards, 1) if row.get("present") and row.get("eligible")]
            preferred = [(i, row) for i, row in options
                         if (row.get("id"), row.get("next_level")) in wanted - seen]
            choice = preferred[0] if preferred else options[0] if options else None
            record = {"index": index, "spawn": spawned, "normal_use": used,
                      "before": before, "menu": offered, "menu_valid": bool(menu_valid)}
            if not menu_valid or choice is None:
                picks.append(record)
                all_valid = False
                break
            number, card = choice
            pair = (card["id"], card["next_level"])
            is_requested = pair in wanted
            if is_requested:
                source = expected[pair]
                quality_ok = qualities.get(source["quality"]) == card["quality"]
                record["source_expected"] = source
                record["source_quality_matches"] = bool(quality_ok)
                shot = c.g.shot(f"sphere-ui-{cls}-{card['id']}-q{pair[1]}")
                record["screenshot"] = str(shot.relative_to(c.g.results)) if shot else None
                menu_valid &= bool(quality_ok and shot and shot.exists())
            picked = c.gl("sphereui", "pick", number)
            closed = c.gl("sphereui")
            terminal = c.g.wait_gl(lambda row: row.get("ev") == "inputsequence"
                                  and row.get("tag") == used["sequence_tag"], timeout=10) or {}
            done = [row for row in c.g.gl if row.get("ev") == "input_done"
                    and row.get("sequence") == used["sequence_tag"]]
            use_protocol = sequence_protocol(used["accepted"], terminal, done, [(1, ["use"])])
            post_usables = c.gl("usables")
            old_usable = [row for row in post_usables.get("usables", [])
                          if row.get("unit", {}).get("unit") == uid]
            usable_retired = (post_usables.get("ok") is True
                              and len(post_usables.get("usables", [])) <= 32
                              and all(row.get("canUse") is False and row.get("top") is False for row in old_usable))
            # glorb(times0) is a read-only native temporary-level lookup.
            actual_level = c.gl("orb", card["id"], 0)
            acquired = (menu_valid and picked.get("ok") is True and picked.get("selected") == card["id"]
                        and picked.get("choice") == number and picked.get("level0") == card["level"]
                        and picked.get("level") == card["next_level"] and picked.get("consumed") is True
                        and picked.get("window_closed") is True and closed.get("open") is False
                        and closed.get("possible_truncated") == 0
                         and use_protocol.get("valid") is True and usable_retired
                        and actual_level.get("ok") and actual_level.get("level") == card["next_level"])
            record.update({"selected": card, "pick": picked, "closed": closed, "independent_level": actual_level,
                            "native_acquisition_valid": bool(acquired), "use_input_done": done,
                            "use_terminal": terminal, "use_protocol": use_protocol,
                            "post_usables": post_usables, "used_sphere_retired": usable_retired,
                           "rendered_glyph_layout_review": "UNTESTED (actual screenshot retained for independent review)"})
            picks.append(record)
            all_valid &= bool(acquired)
            if is_requested and acquired:
                seen.add(pair)
            (c.g.results / "sphere-ui-partial.json").write_text(
                json.dumps({"class": cls, "mode": mode, "picks": picks, "seen": sorted(seen)}, indent=2) + "\n",
                encoding="utf-8")
            if not acquired or (mode == "one" and seen) or (mode == "all" and seen == wanted):
                break
        c.flag("sphere_ui_all_native_picks", bool(picks and all_valid and all(
               row.get("native_acquisition_valid") for row in picks)))
        c.flag("sphere_ui_requested_acquisition", bool(seen) if mode == "one" else seen == wanted)
        c.out["acquired_requested"] = sorted(seen)
        c.out["missing_requested"] = sorted(wanted - seen)
    except Exception as exc:
        c.flag("sphere_ui_exception", False, repr(exc))
    finally:
        c.out["picks"] = picks
    return {**c.out, "notes": c.notes,
            "scope": "Controlled original sphere/native physical-use/menu-callback acquisition and actual widget text/quality/identity. No direct orb grant or offer/RNG rewrite. Screenshots retained; rendered glyph/layout still requires independent review.",
            "not_covered": ["ordinary naturally dropped sphere discovery", "actual mouse/keyboard selection rather than native window callback",
                            "all skill-rank trainer UI/unlock/respec", "orb mechanics/true allies", "save/floor/death lifecycle"]}
