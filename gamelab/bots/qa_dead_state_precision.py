"""Controlled native death verifies exact record telemetry; no ability credit."""
import math
from gamelab.bots.plan_checks import Checks


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def run(p, **_):
    c = Checks(p)
    initial = c.gl("state")
    player = initial.get("player", {})
    fresh = (initial.get("phase") == "town" and player.get("class") == "paladin"
             and player.get("level") == 1 and player.get("dead") is False)
    c.flag("precision_fixture", fresh, str(initial))
    mission = c.start_floor(0) if fresh else False
    c.flag("precision_mission", mission, "native Bandit Keep entry only; no navigation or ability trial")
    if not mission:
        return {**c.out, "notes": c.notes, "scope": "setup failed; no telemetry measurement"}
    c.gl("timescale", 1)
    # Clear ordinary enemies as a labeled telemetry fixture to prevent unrelated
    # incoming damage between setup and the single atomic measurement.
    cleared = c.gl("kill", 6000, "tag:enemy")
    controls = c.gl("cvars", "cht_god", "g_timescale").get("cvars", {})
    valid_controls = ("cht_god" in controls and controls["cht_god"] in (0, False)
                      and controls.get("g_timescale") == 1)
    c.flag("precision_controls", valid_controls, str(controls))
    if not valid_controls:
        return {**c.out, "notes": c.notes, "scope": "controls failed; no telemetry measurement"}
    batch = c.g.gl_multi([["mana", 12.375], ["state"], ["damageme", 10000], ["state"]])
    if len(batch) != 4:
        c.flag("precision_batch", False, str(batch))
        return {**c.out, "notes": c.notes, "batch": batch}
    setup, before, hit, after = batch
    live, dead = before.get("player", {}), after.get("player", {})
    exact, raw = dead.get("manaExact"), hit.get("mana")
    fractional = (setup.get("ok") is True and number(setup.get("now"))
                  and abs(setup["now"] - 12.375) <= .002
                  and live.get("class") == "paladin" and live.get("dead") is False
                  and live.get("spawned") is True and number(live.get("manaExact"))
                  and abs(live["manaExact"] - 12.375) <= .002
                  and live.get("manaMax", 0) > 12.375)
    died = (hit.get("ok") is True and hit.get("took", 0) > live.get("hp", 0)
            and hit.get("dead") is True and after.get("phase") == "dead"
            and dead.get("dead") is True and dead.get("spawned") is False
            and dead.get("hp", 1) <= 0)
    present = number(exact) and number(raw)
    maximum = live.get("manaMax") == dead.get("manaMax") == hit.get("max")
    matches = (present and maximum and number(hit.get("mana0"))
               and abs(hit["mana0"] - 12.375) <= .002
               and abs(raw - 12.375) <= .002 and abs(exact - raw) <= .002)
    precision = (present and number(dead.get("mana"))
                 and abs(exact - dead["mana"]) >= .1
                 and dead["mana"] == math.floor(exact))
    c.flag("precision_fractional_setup", fractional, str(batch))
    c.flag("precision_native_death", died, str(batch))
    c.flag("precision_dead_exact_present", present, str(after))
    c.flag("precision_dead_matches_raw", matches, str(batch))
    c.flag("precision_distinguishes_integer", precision, str(after))
    return {**c.out, "notes": c.notes, "batch": batch, "cleared_fixture": cleared,
            "scope": "one controlled native fatal damage event; exact dead record mana telemetry only, no Barrier/ability/ordinary-run credit",
            "expected_source": ["mods/gamelab-probe/scripts/GameLab/Probe.as:188",
                                "mods/gamelab-hands/scripts/GameLab/Verbs_specs.as:108",
                                "mods/gamelab-hands/scripts/GameLab/Verbs_specs.as:191",
                                "gamecode/sdk/hoh2/scripts/Behaviors/Actors/Player/PlayerRecord.as:2644",
                                "gamecode/sdk/hoh2/scripts/Behaviors/Actors/Player/PlayerBase.as:943"]}
