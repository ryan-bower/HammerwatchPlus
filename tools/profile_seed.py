"""Build requested characters through an isolated, source-pinned GameLab run."""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from gamelab import env
from tools import build, gamepaths, qa_batch
from gamelab.hps import hash_string
from tools.save_builder import CLASSES, TOWN_PRESETS, Plan


def modules_for(packages: list[str]) -> list[str]:
    modules = [build.load_module(path) for path in gamepaths.module_dirs()]
    declarations, _ = build.load_packages(modules)
    known = {p["id"] for p in declarations} | {"all"}
    unknown = set(packages) - known
    if unknown:
        raise ValueError("Unknown packages: " + ", ".join(sorted(unknown)))
    return list(dict.fromkeys(mid for pkg in declarations if "all" in packages or pkg["id"] in packages
                              for mid in pkg["closure"]))


def available_classes(packages: list[str]) -> dict[str, str]:
    modules = modules_for(packages)
    return {key: label for key, label in CLASSES.items()
            if not key.startswith("hwp_") or (key == "hwp_firearms" and "firearms" in modules)
            or (key != "hwp_firearms" and "classes" in modules)}


def required_unlocks(plan: Plan) -> list[str]:
    flags = set()
    for character in plan.characters:
        if character.class_id.startswith("hwp_"):
            continue
        path = gamepaths.GAMECODE / "datatables" / "players" / character.class_id / f"class_{character.class_id}.sval.json"
        entries = json.loads(path.read_text(encoding="utf-8"))
        definition = next(entry for entry in entries if entry.get("id") == character.class_id)
        for condition in definition.get("conditionals", []):
            if (len(condition) == 3 and condition[:2] == ["local flag", "is"]
                    and condition[2].startswith("unlocked_class_")):
                flags.add(condition[2])
    return sorted(flags)


def town_flags(plan: Plan) -> list[str]:
    """The roster's required class unlocks, then the town preset's flags, each once."""
    return list(dict.fromkeys([*required_unlocks(plan), *TOWN_PRESETS[plan.town].flags]))


def town_probe(plan: Plan) -> dict | None:
    """The `towntiers` readback for the preset. The exact tiers depend on the enabled mods (the
    tavern mod adds tavern tiers), so the play builder checks the shape; the town-preset-*
    scenarios check exact vanilla tiers."""
    tiers = TOWN_PRESETS[plan.town].tiers
    if tiers is None:
        return None
    if tiers == 100:
        expect = {"ok": True, "built": {"between": [1, 64]}, "unmaxed": 0, "truncated": False,
                  "buildings.guild_hall.v": {"between": [1, 99]}}
    else:
        expect = {"ok": True, "built": {"between": [1, 64]}, "truncated": False,
                  "buildings.guild_hall.v": {"between": [1, 99]}}
    return {"verb": "towntiers", "expect": expect}


def scenario(plan: Plan, packages: list[str], name: str) -> dict:
    plan.validate(available_classes(packages))
    modules = modules_for(packages)
    first = plan.characters[0] if plan.characters else None
    setup = ([{"verb": "levelup", "args": [first.level - 1],
               "expect": {"ok": True, "level": first.level}}] if first and first.level > 1 else [])
    flags = town_flags(plan)
    setup += [{"verb": "townflag", "args": [flag, "on"], "expect": {"ok": True, "value": True}}
              for flag in flags]
    tiers = TOWN_PRESETS[plan.town].tiers
    if tiers is not None:
        # after the flags: the buildings' conditionals read them
        setup.append({"verb": "townpreset", "args": [tiers], "expect": {"ok": True, "pct": tiers, "capped": False}})
    setup.append({"verb": "townmoney", "args": [plan.starting_gold],
                  "expect": {"ok": True, "gold": plan.starting_gold}})
    readback = ({"phase": "town", "player.class": first.class_id, "player.name": first.name,
                 "player.level": first.level, "player.dead": False} if first else {"phase": "no_character"})
    probe = town_probe(plan)
    fixture = {"name": "play-builder", "slot": 0,
               "binary_edits": {"enable_mods": ["gamelab-probe", "gamelab-hands", "gamelab-pilot", *modules]},
               "character": {"class": first.class_id, "name": first.name} if first else None, "setup": setup,
               "save_town": True,
               "readback_probes": [{"verb": "townflag", "args": [flag], "expect": {"ok": True, "value": True}}
                                   for flag in flags] + ([probe] if probe else [])
                                  + [{"verb": "townmoney", "expect": {"ok": True, "gold": plan.starting_gold}}],
               "readback": readback}
    return {"name": name, "about": "Native pre-launch character/save preparation; no real save writes",
            "fixture": fixture, "mods": modules, "export_profile": True,
            "timeout": 240 + 30 * len(plan.characters),
            "steps": [{"do": "bot", "bot": "play_profile", "kwargs": {"characters": [asdict(c) for c in plan.characters],
                                                                         "starting_gold": plan.starting_gold},
                       "expect": {"ok": True}, "name": "requested characters created and levelled"}]}


def verified_export(result: Path, plan: Plan) -> bytes:
    from tools.play_profile import characters_in, gold_in, town_in

    run = json.loads((result / "run.json").read_text(encoding="utf-8"))
    assertions = run.get("assertions") if isinstance(run, dict) else None
    teardown = run.get("teardown") if isinstance(run, dict) else None
    if (not isinstance(run, dict) or run.get("verdict") != "PASS" or run.get("error")
            or run.get("partial") is not False or run.get("build_drift") is not False
            or not isinstance(teardown, dict) or teardown.get("clean") is not True
            or not isinstance(assertions, list) or not assertions
            or not all(isinstance(row, dict) and row.get("ok") is True for row in assertions)):
        raise RuntimeError(f"Character preparation refused: {result}; incomplete or unsafe outer result")
    data = (result / "profile.hps").read_bytes()
    wanted = sorted((c.class_id, c.level, c.name) for c in plan.characters)
    observed = sorted((c["class"], c["level"], c["name"]) for c in characters_in(data))
    if observed != wanted:
        raise RuntimeError(f"Saved roster differs from the request: {observed} != {wanted}")
    if gold_in(data) != plan.starting_gold:
        raise RuntimeError(f"Saved gold differs from the request: {gold_in(data)} != {plan.starting_gold}")
    preset = TOWN_PRESETS[plan.town]
    if preset.flags or preset.tiers is not None:
        town = town_in(data)
        missing = [flag for flag in preset.flags if hash_string(flag) not in town["flags"]]
        if missing:
            raise RuntimeError(f"Saved town lacks the {preset.label} flags: {', '.join(missing)}")
        # Exact tiers depend on the enabled mods and are read back in game (towntiers);
        # the export only refuses a preset town whose guild hall was never raised.
        if preset.tiers is not None and town["buildings"].get(hash_string("guild_hall"), -1) < 1:
            raise RuntimeError(f"Saved town has no raised guild hall for the {preset.label} preset")
    return data


def generate(plan: Plan, packages: list[str]) -> tuple[bytes, str]:
    name = "play-builder-" + uuid.uuid4().hex[:12]
    root = gamepaths.GAMELAB / "results"
    request = root / (name + ".json")
    root.mkdir(parents=True, exist_ok=True)
    request.write_text(json.dumps(scenario(plan, packages, name), indent=2), encoding="utf-8")
    before = qa_batch.fingerprint()
    command = [sys.executable, "-m", "gamelab", "run", str(request), "--mode", "lab"]
    code = subprocess.run(command, cwd=gamepaths.REPO).returncode
    after = qa_batch.fingerprint()
    results = list(root.glob(f"*-{name}-lab"))
    if len(results) != 1:
        raise RuntimeError(f"Character preparation exited {code}; expected one result, found {len(results)}. See {request}")
    result = results[0]
    (result / "source.json").write_text(json.dumps({"before": before, "after": after}, indent=2), encoding="utf-8")
    if code or before != after:
        raise RuntimeError(f"Character preparation failed (exit {code}, source changed={before != after}); see {result / 'run.json'}")
    return verified_export(result, plan), result.name
