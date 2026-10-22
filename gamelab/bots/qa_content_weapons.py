"""Twelve endgame weapons through their native equipped attack buttons.

This is a controlled stat-point fixture, not progression or a balance benchmark.
Requirements remain enabled. The existing bench holds native main/off input;
noskills prevents spell casting, and independent exact HP loss guards attribution.
"""
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from gamelab.bots.plan_classesa import Checks as Base
from gamelab.hps import hash_string


SOURCE = Path(__file__).resolve().parents[2] / "mods/weapons/tweak/hwp/equipment_weapons_hwp.sval"
DUMMY = "gamelab/qa_weapons_target_dummy.unit"
DUMMY_HP = 150000


def definitions():
    root = ET.fromstring("<root>" + SOURCE.read_text(encoding="utf-8") + "</root>")
    return [{child.attrib.get("name"): (child.text or "").strip()
             for child in entry if child.tag in ("string", "int")}
            for entry in root.find("array").findall("dict")]


class Checks(Base):
    def __init__(self, p):
        super().__init__(p)
        self.rows = []

    def check(self, case, ok, **data):
        self.flag(case, ok, str(data))
        self.rows.append(dict(case=case, runtime="PASS" if ok else "FAIL", **data))

    def collect_trace(self, event, tag, timeout):
            first = self.g.wait_gl(lambda e: e.get("ev") == event and e.get("tag") == tag,
                                   timeout=timeout) or {}
            count = first.get("parts", 0)
            if not isinstance(count, int) or not 1 <= count <= 64:
                return {"valid": False, "parts": [first], "samples": []}
            parts = []
            for index in range(count):
                part = (first if first.get("part") == index else
                        self.g.wait_gl(lambda e: e.get("ev") == event and e.get("tag") == tag
                                       and e.get("part") == index, timeout=3) or {})
                parts.append(part)
            samples = [row for part in parts for row in part.get("samples", part.get("events", []))]
            valid = (all(p.get("parts") == count and p.get("part") == i
                         and p.get("dropped") == 0 and p.get("truncated") is False
                         and p.get("start") == first.get("start") and p.get("end") == first.get("end")
                         for i, p in enumerate(parts))
                     and len(samples) == first.get("stored") and bool(samples))
            complete = {}
            if event == "actorbuffobserve":
                # This observer stores every native frame plus its initial sample.
                # buffobserve above stores only semantic transitions and therefore
                # intentionally does not share this per-frame contract.
                complete = {
                    "all_headers_consistent": all(all(p.get(k) == first.get(k) for k in
                        ("stored", "seen", "frames", "ms", "unit", "buff")) for p in parts),
                    "every_native_frame_retained": first.get("stored") == first.get("seen")
                        == first.get("frames", -2) + 1,
                    "initial_and_final": bool(samples) and samples[0].get("elapsed") == 0
                        and samples[0].get("dt") == 0 and samples[0].get("now") == first.get("start")
                        and samples[-1].get("elapsed") == first.get("ms")
                        and samples[-1].get("now") == first.get("end")
                        and samples[-1].get("final") is True
                        and all(x.get("final") is False for x in samples[:-1]),
                    "sample_identity": all(x.get("unit") == first.get("unit") for x in samples),
                    "native_frame_continuity": all(
                        isinstance(b.get("dt"), int) and b["dt"] > 0
                        and b.get("elapsed", -1) - a.get("elapsed", -1) == b["dt"]
                        and 0 <= b.get("now", -1) - a.get("now", -1) <= b["dt"] + 1
                        for a, b in zip(samples, samples[1:])),
                }
                valid = valid and all(complete.values())
            return {"valid": valid, "parts": parts, "samples": samples, "completeness": complete}

    def wait_ready(self, skill):
        """Wait for the native raw cooldown; never reset a cooldown or activate it."""
        samples = []
        deadline = time.monotonic() + 8
        while True:
            reply = self.gl("skills")
            entries = [x for x in reply.get("skills", []) if x.get("id") == skill]
            raw = entries[0] if len(entries) == 1 else {}
            cd = raw.get("cd")
            valid = (reply.get("ok") is True and len(entries) == 1
                     and isinstance(cd, (int, float)) and not isinstance(cd, bool)
                     and math.isfinite(cd))
            samples.append(dict(native_reply=reply, selected=raw, finite=valid))
            if valid and cd <= 0:
                return dict(ready=True, samples=samples, selected=raw)
            if time.monotonic() >= deadline:
                return dict(ready=False, samples=samples, selected=raw)
            time.sleep(.15)

    def weapons(self, ms=3500):
        if not self.new_char("paladin", "QAEndWeapons"):
            return
        self.gl("xp", 1301032)
        self.hwp("statpoints 450", 0.3)
        assigned = [self.gl("assign", stat, 150) for stat in ("str", "dex", "int")]
        if not self.arena("custom_weapons"):
            return
        self.g.console("dbg_cht_ignore_equipment_requirements 0")
        fixture = self.gl("cvars", "dbg_cht_ignore_equipment_requirements")
        attributes = self.gl("benchstats")
        self.check("weapon_requirements_enabled", all(r.get("ok") for r in assigned)
                   and all(attributes.get(stat, 0) >= 150 for stat in ("str", "dex", "int"))
                   and fixture.get("cvars", {}).get("dbg_cht_ignore_equipment_requirements") in (0, False),
                   assign=assigned, native_attributes=attributes, requirements=fixture,
                   fixture_scope="Controlled extra stat points; no natural progression claim.")
        choices = self.open_dirs()
        lane_ok = bool(choices) and choices[0][0] >= 48
        self.check("weapon_clear_attack_lane", lane_ok, directions=choices)
        if not lane_ok:
            return
        _, (dx, dy) = choices[0]
        items = sorted(definitions(), key=lambda d: d["id"] == "hwp_oh_parrying_dirk")
        self.check("weapon_definition_count", len(items) == 12, ids=[d["id"] for d in items])
        for index, definition in enumerate(items):
            weapon, skill = definition["id"], definition["skill"]
            off = definition["slot"] == "offhand"
            self.gl("kill", 6000, "target_dummy")
            # Replacing the previous two-hander first clears both native hand slots.
            reset = self.gl("equip", "twohanded_shortbow_01", "common", 1)
            support = self.gl("equip", "mainhand_mace_01", "common", 1) if off else None
            equipped = self.gl("equip", weapon, "common", 35)
            time.sleep(0.3)
            bar = self.gl("skillbar")
            entry = next((s for s in bar.get("skills", []) if s.get("id") == skill), {})
            native_items = self.gl("inspect", "player", "equipped").get("value") or []
            present = any(isinstance(item, list) and len(item) >= 4
                          and int(item[1]) & 0xFFFFFFFF == hash_string(weapon) and item[3] == 35
                          for item in native_items)
            expected_button = "off" if off else "main"
            ready = (reset.get("ok") and (not off or support.get("ok")) and equipped.get("ok")
                     and equipped.get("quality") == 1 and equipped.get("ilvl") == 35 and present)
            self.check(weapon + "_equipped", ready, reply=equipped, reset=reset, support=support,
                       native_equipped=native_items, expected_skill=skill, native_entry=entry,
                       stats=self.gl("benchstats"))
            if not ready:
                continue
            if weapon == "hwp_oh_parrying_dirk":
                self.out["passive_dirk_skill_observation"] = dict(declared_skill=skill, native_entry=entry,
                    native_skillbar=bar,
                    scope="README declares a defensive passive. No prototype stab is required or enabled. Actual native parry is checked by qa-content-dirk-defense.")
                continue
            self.check(weapon + "_native_button", entry.get("button") == expected_button,
                       expected_skill=skill, expected_button=expected_button, native_entry=entry)
            if entry.get("button") != expected_button:
                continue
            # Native tome creates a stationary proximity glyph at the caster.
            # TripMine.Update tests actor CENTER distance<=24; the old28px target
            # never entered its trigger. Other weapons keep the original28px.
            target_distance = 16 if weapon == "hwp_oh_grimoire" else 28
            spawned = self.gl("spawn", DUMMY, round(dx * target_distance, 2), round(dy * target_distance, 2))
            unit_id = spawned.get("unit")
            before = next((u for u in self.gl("near", 100, "target_dummy").get("units", [])
                           if u.get("unit") == unit_id), {})
            valid_target = spawned.get("ok") and before.get("hpMax") == DUMMY_HP and before.get("hpExact") == DUMMY_HP
            glyph_inside_trigger = (weapon != "hwp_oh_grimoire" or
                                    isinstance(before.get("dist"), (int, float))
                                    and not isinstance(before.get("dist"), bool)
                                    and math.isfinite(before["dist"]) and 8 < before["dist"] <= 20)
            valid_target = valid_target and glyph_inside_trigger
            self.check(weapon + "_target", valid_target, spawn=spawned, target=before,
                       requested_target_distance=target_distance,
                       native_glyph_trigger_radius=24 if weapon == "hwp_oh_grimoire" else None,
                       actual_glyph_target_inside_trigger=bool(glyph_inside_trigger))
            if not valid_target:
                continue
            cooldown_ready = self.wait_ready(skill)
            self.check(weapon + "_native_ready_before_input", cooldown_ready["ready"],
                       natural_cooldown=cooldown_ready)
            if not cooldown_ready["ready"]:
                continue
            if weapon == "hwp_oh_bulwark":
                initial = self.gl("skillbar")
                initial_skill = next((s for s in initial.get("skills", []) if s.get("id") == skill), {})
                mana0 = initial.get("mana", 0)
                tag = "qa_endweapon_bulwark"
                watched = self.gl("actorbuffobserve", tag, 1900, unit_id,
                                  "tweak/buffs/status_effects.sval:stun")
                pressed = self.gl("input", 600, 0, 0, dx, dy, "off")
                done = self.g.wait_gl(lambda e: e.get("ev") == "input_done"
                                      and e.get("id") == pressed.get("id"), timeout=3) or {}
                observed = self.g.gl_multi([["actorbuffs", 100, "target_dummy"], ["skillbar"], ["skills"]])
                actors = observed[0].get("actors", [])
                target = next((a for a in actors if a.get("unit") == unit_id), {})
                buffs = target.get("buffs", [])
                trace = self.collect_trace("actorbuffobserve", tag, timeout=5)
                frames = trace["samples"]
                stunned = (trace["valid"] and bool(frames)
                           and frames[0].get("buff_on") is False
                           and all(x.get("valid") is True for x in frames)
                           and any(x.get("buff_on") is True and x.get("left", 0) > 0
                                   and x.get("duration") == 1500 for x in frames))
                live = next((s for s in observed[1].get("skills", []) if s.get("id") == skill), {})
                raw = next((s for s in observed[2].get("skills", []) if s.get("id") == skill), {})
                self.check(weapon + "_native_stun_cost_cooldown", initial_skill.get("cd") == 0
                           and watched.get("ok") is True and pressed.get("ok") is True
                           and bool(pressed.get("id")) and done.get("id") == pressed.get("id")
                           and done.get("frames", 0) > 1 and stunned and 0 < live.get("cd", 0) <= 1 and 0 < raw.get("cd", 0) <= 3000
                           and mana0 - observed[1].get("mana", mana0) > 2,
                           before_mana=mana0, before_skill=initial_skill, observed=observed, live_skill=live,
                           native_stun_trace=trace, observer_request=watched, input_request=pressed,
                           input_done=done,
                           raw_remaining_ms=raw.get("cd"),
                           rule="Native shield bash is stun utility, with no damage action; no HP-loss requirement.")
                continue
            tag = "qa_endweapon_" + str(index)
            request = self.gl("bench", tag, ms, 100, *( ["offonly"] if off else []), "noskills")
            bench = self.g.wait_gl(lambda o: o.get("ev") == "bench" and o.get("tag") == tag,
                                   ms / 1000 + 25) or {}
            after = next((u for u in self.gl("near", 100, "target_dummy").get("units", [])
                          if u.get("unit") == unit_id), {})
            hit = next((w for w in bench.get("weapons", []) if w.get("weapon") == skill), {})
            hp_loss = before.get("hpExact", 0) - after.get("hpExact", before.get("hpExact", 0))
            damage = sum(d.get("dmg", 0) for d in bench.get("dummies", []))
            self.check(weapon + "_native_attack_damage", request.get("ok") and bench.get("dummyCount") == 1
                       and bench.get("ms", 0) >= ms and hit.get("hits", 0) > 0 and hit.get("dmg", 0) > 0
                       and hp_loss > 0 and after.get("hpExact", 0) > 0
                       and after.get("hpMax") == DUMMY_HP and damage > 0 and hp_loss + 2 >= damage,
                       button=expected_button, before=before, after=after, hp_loss=hp_loss,
                       expected_skill=skill, native_attribution=hit, bench=bench,
                       limits="Common ilvl35 attacks only; later poison ticks may add HP loss after the bench event. Defensive proc rates, epic qualities and exact modifier balance remain unverified.")
        self.gl("kill", 6000, "target_dummy")
        self.to_town()


def run(p, **kwargs):
    c = Checks(p)
    try:
        c.weapons(**kwargs)
    except Exception as exc:
        c.check("endgame_weapons_crashed", False, error=repr(exc))
    required = {"weapon_requirements_enabled", "weapon_clear_attack_lane", "weapon_definition_count"}
    for definition in definitions():
        weapon = definition["id"]
        required.add(weapon + "_equipped")
        if weapon == "hwp_oh_parrying_dirk":
            continue
        required.update(weapon + suffix for suffix in
                        ("_native_button", "_target", "_native_ready_before_input"))
        required.add(weapon + ("_native_stun_cost_cooldown" if weapon == "hwp_oh_bulwark"
                               else "_native_attack_damage"))
    seen = [r.get("case") for r in c.rows]
    complete = len(seen) == len(set(seen)) and set(seen) == required
    c.out.update(ok=complete and all(r["runtime"] == "PASS" for r in c.rows), rows=c.rows,
                 required_cases=sorted(required), all_required_present=complete,
                 notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
