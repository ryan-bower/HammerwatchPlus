"""Bannerlord orb effects through native casts, damage, buffs and cooldowns at1x.

Controlled prerequisites use existing native ApplyBuff/crit fixtures. No positive
provisions stacks, incoming-hit callback, target damage or measured event is set.
Real ally recipients and enemy AI attacks remain explicit coverage gaps.
"""
import json
import math
import re
import time

from gamelab.bots.qa_specs_banner_brand import BS, RC, Checks as BannerChecks
from gamelab.bots.plan_specs import BUFFS
from gamelab.bots.qa_specs_wizard_ranks import spawn, targets, health, target_ok

MARTYR = "hwp_war_bs_martyrs_banner"
CREST = "hwp_war_bs_feared_crest"
DRUM = "hwp_war_rc_war_drum"
PROVISIONS = "hwp_war_rc_shared_provisions"
PROV_STACK = "players/hwp/specs/stacks_specs.sval:provisions"
STATUS = "tweak/buffs/status_effects.sval:"
SHRINES = ["tweak/buffs/shrine_buffs.sval:" + name
           for name in ("damage", "protection", "speed", "mana", "gold", "experience")]
CAP_BUFFS = SHRINES + [BUFFS + name for name in ("gale_1", "breeze_1", "standard_dr", "standard_dr_planted")]
CRIT = re.compile(r"[1-9]\d*!")


def damage_round(value):
    return 0 if value == 0 else max(1, int(value + 0.5))


def provisions_expected(hud_positive, quality):
    if not isinstance(hud_positive, int) or hud_positive < 0 or quality not in (0, 1, 2, 3):
        return None
    return min(30, hud_positive * quality)


def cooldown_total(start, state, skill):
    rows = [row for row in state.get("skills", []) if row.get("id") == skill]
    if (not state.get("ok") or state.get("truncated") or len(rows) != 1
            or not isinstance(state.get("now"), int) or not isinstance(start, int)
            or state["now"] < start or rows[0].get("cd", 0) <= 0):
        return None
    return rows[0]["cd"] + state["now"] - start


def cooldown_matches(control, measured, stacks):
    return (isinstance(control, (int, float)) and isinstance(measured, (int, float))
            and control > 1000 and 0 <= stacks <= 30
            # The reconstructed total also includes cast/animation time. CDR
            # applies to native Warcry's12000ms cooldown, not that extra phase.
            and abs((control - measured) - 12000 * stacks / 100) <= 100)


def crest_matches(control, actual, tier):
    # A single physical damage component is rounded after target DamageTakenMul.
    return (isinstance(control, (int, float)) and isinstance(actual, (int, float))
            and control > 0 and tier in (1, 2, 3)
            and abs(control - damage_round(control)) <= 0.05
            and abs(actual - damage_round(damage_round(control) * (1 + tier / 10))) <= 0.05)


class Checks(BannerChecks):
    def checkpoint(self, complete=False):
        path = self.g.results / "qa-specs-banner-orbs.partial.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"complete": complete, "checks": self.out,
                                         "notes": self.notes, "cases": self.cases}, indent=2), encoding="utf-8")
        temporary.replace(path)

    def prepare_orbs(self, tag):
        if not self.prepare_banner(tag):
            return None
        self.gl("timescale", 1)
        for orb in (MARTYR, CREST, DRUM, PROVISIONS):
            self.gl("orb", orb, -999)
        lane, note = self.to_trident_lane(front=72, back_neighbor=True, ray_distance=72, tag=tag)
        self.flag(tag + "_lane", bool(lane), note)
        return lane[0] if lane else None

    def wait_scene(self, duration):
        start = self.gl("clock").get("sceneMs")
        if not isinstance(start, int):
            return False
        deadline = time.monotonic() + duration / 1000 * 3 + 5
        while time.monotonic() < deadline:
            now = self.gl("clock").get("sceneMs", start)
            if now - start >= duration:
                return True
            time.sleep(0.2)
        return False

    def end_standard(self, direction, tag):
        mark = len(self.g.read_log())
        planted = self.standard_cast(direction)
        ttl = int(self.bind(BS, "std-ttl") or 10000)
        waited = self.wait_scene(ttl // 2 + 700)  # plant halves the remainder;600ms buff tail
        buffs = self.gl("hasbuff", BUFFS + "standard_dr", BUFFS + "standard_dr_planted")
        ended = waited and "standard: ended" in self.g.read_log()[mark:]
        off = not any(row.get("on") for row in buffs.get("buffs", []))
        self.flag(tag + "_expires", bool(planted.get("activated") and ended and off),
                  str({"plant": planted, "native_wait": waited, "buffs": buffs, "ended_log": ended}))
        return ended and off

    def martyr(self):
        direction = self.prepare_orbs("martyr")
        if direction is None:
            return
        before = spawn(self, direction, [(24, 0)])
        self.flag("martyr_target", target_ok(before, 1), str(before))
        if not target_ok(before, 1):
            return
        uid = next(iter(before))
        plain, plain_record = self.damage(uid)
        cast = self.standard_cast(direction, reset=True, refill=True)
        buff = self.wait_buff("standard_dr", 2)
        ordinary, ordinary_record = self.damage(uid)
        dr = float(self.bind(BS, "std-dr") or 0)
        control = (cast.get("activated") and buff.get("on") and plain > 0 and dr > 0
                   and ordinary < plain - 0.5 and abs(ordinary - plain * (1 - dr)) <= 1)
        self.flag("martyr_ordinary_standard_dr", bool(control), str({"baseline": plain_record,
                  "carried": ordinary_record, "cast": cast, "buff": buff, "source_dr": dr}))
        self.cases.append({"tag": "martyr_control", "baseline": plain_record, "carried": ordinary_record})
        self.end_standard(direction, "martyr_control")
        for quality, ally in enumerate((1.5, 2, 3), 1):
            tag = f"martyr_r{quality}"
            equipped = self.gl("orb", MARTYR, 1)
            own = float(self.bind(BS, "std-self-mul") or 0)
            other = float(self.bind(BS, "std-ally-mul") or 0)
            self.flag(tag + "_equipped", equipped.get("level") == quality and own == 0 and other == ally,
                      str({"orb": equipped, "self_mul": own, "ally_mul_readback_only": other}))
            raw, raw_record = self.damage(uid)
            raised = self.standard_cast(direction, reset=True, refill=True)
            time.sleep(0.6)
            active = self.gl("hasbuff", BUFFS + "standard_dr")
            loss, loss_record = self.damage(uid)
            actual = (control and raised.get("activated") and raw > 0 and raw == plain and loss == raw
                      and not any(row.get("on") for row in active.get("buffs", [])))
            self.flag(tag + "_self_loss", bool(actual), str({"baseline": raw_record,
                      "actual": loss_record, "active": active, "cast": raised}))
            self.cases.append({"tag": tag, "baseline": raw_record, "actual": loss_record,
                               "buff": active, "cast": raised, "ally_runtime": "BLOCKED: real second player required"})
            self.end_standard(direction, tag)
            self.checkpoint()

    def weapon_bench(self, direction, main, tag):
        initial = spawn(self, direction, [(24, 0)])
        crit = self.gl("skillcrit", main, 1)
        time.sleep(0.55)  # allow the Standard's250ms pulse to reach the fresh actor
        debuffs = targets(self)
        start, queued = self.g.gl_multi([["clock"], ["bench", tag, 1200, 100, "noskills"]])
        # Numeric critical text lives only500 native ms. Three fixed read-only
        # batches sample during the native bench instead of waiting for it to fade.
        floating_reads = []
        if queued.get("ok"):
            for _ in range(3):
                floating, clock = self.g.gl_multi([["floats"], ["clock"]])
                floating_reads.append({"floats": floating, "clock": clock})
        native = self.g.wait_gl(lambda row: row.get("ev") == "bench" and row.get("tag") == tag, 8) if queued.get("ok") else None
        native = native or {}
        actors, floating, clock = self.g.gl_multi([
            ["actorbuffs", 400, "qa_class_target_dummy"], ["floats"], ["clock"]])
        floating_reads.append({"floats": floating, "clock": clock})
        after = {row["unit"]: row for row in actors.get("actors", []) if "unit" in row}
        a, b = health(initial), health(after)
        delta = sum(a[unit] - b.get(unit, a[unit]) for unit in a)
        weapons = native.get("weapons", [])
        own = [row for row in weapons if row.get("weapon") == main]
        hits = own[0].get("hits", 0) if len(own) == 1 else 0
        numeric_crit = any(row.get("type") == 11 and CRIT.fullmatch(row.get("text", ""))
                           and start.get("sceneMs", 1e9) <= read["clock"].get("sceneMs", 0) - row.get("lived", 1e9)
                           <= start.get("sceneMs", -1) + native.get("ms", 0) + 66
                           for read in floating_reads for row in read["floats"].get("texts", []))
        valid = (target_ok(initial, 1) and target_ok(after, 1) and set(a) == set(b)
                 and queued.get("ok") and not native.get("error") and native.get("dummyCount") == 1
                 and 1200 <= native.get("ms", 0) <= 1300 and native.get("frames", 0) >= 20
                 and len(weapons) == 1 and hits >= 1 and delta > 0
                 and abs(delta - native.get("total", -999)) <= 0.1
                 and all(not read["floats"].get("truncated") for read in floating_reads)
                 and crit.get("crit_chance") == 1 and numeric_crit)
        return {"tag": tag, "valid": bool(valid), "per_hit": delta / hits if valid else None,
                "initial": initial, "after": after, "debuffs": debuffs, "crit": crit,
                "queued": queued, "native": native, "actual_hp_delta": delta,
                "float_reads": floating_reads, "native_start": start}

    def crest(self):
        direction = self.prepare_orbs("crest")
        if direction is None:
            return
        skills = self.gl("skills").get("skills", [])
        mains = [row.get("id") for row in skills if row.get("button") == "main"]
        stats = self.gl("benchstats")
        physical = (len(mains) == 1 and stats.get("mhPhys", 0) > 0
                    and all(stats.get(key, 0) == 0 for key in ("mhFire", "mhIce", "mhLight", "mhPoison")))
        self.flag("crest_physical_main", bool(physical), str({"skills": skills, "stats": stats}))
        if not physical:
            return
        main = mains[0]
        self.rank(BS, 5, "crest_standard")  #20s covers all3 fixed natural-attack trials
        original = self.gl("skillcrit", main)
        controls = [self.weapon_bench(direction, main, f"crest_control_{n}") for n in range(1, 4)]
        values = [row["per_hit"] for row in controls if row["valid"]]
        stable = len(values) == 3 and max(values) - min(values) <= 0.05
        control = sum(values) / len(values) if stable else None
        self.flag("crest_three_controls", stable, str(controls))
        self.cases.extend(controls)
        for quality, suffix in enumerate(("_minor", "", "_greater"), 1):
            tag = f"crest_r{quality}"
            equipped = self.gl("orb", CREST, 1)
            expected_path = STATUS + "vulnerability_area" + suffix
            self.flag(tag + "_equipped", equipped.get("level") == quality
                      and self.bind(BS, "std-enemy-debuff") == expected_path, str(equipped))
            raised = self.standard_cast(direction, reset=True, refill=True)
            self.wait_buff("standard_dr", 2)
            trials = [self.weapon_bench(direction, main, tag + f"_trial{n}") for n in range(1, 4)]
            debuffed = all(any(buff.get("debuff") and "vulnerability" in buff.get("tags", [])
                               and 0 < buff.get("left", 0) <= 500
                               for actor in row["debuffs"].values() for buff in actor.get("buffs", [])) for row in trials)
            actual = (stable and raised.get("activated") and debuffed
                      and all(row["valid"] and crest_matches(control, row["per_hit"], quality) for row in trials))
            self.flag(tag + "_native_damage", bool(actual), str({"baseline_per_hit": control,
                      "factor": 1 + quality / 10, "cast": raised, "trials": trials}))
            self.cases.extend(trials)
            self.end_standard(direction, tag)
            self.checkpoint()
        restored = self.gl("skillcrit", main, "restore")
        final = self.gl("skillcrit", main)
        self.flag("crest_crit_restored", restored.get("ok") and not final.get("override_active")
                  and final.get("crit_chance") == original.get("crit_chance"), str(final))

    def drum(self):
        direction = self.prepare_orbs("drum")
        if direction is None:
            return
        for quality in range(1, 4):
            tag = f"drum_r{quality}"
            equipped = self.gl("orb", DRUM, 1)
            self.flag(tag + "_equipped", equipped.get("level") == quality
                      and int(self.bind(RC, "drum-tier") or 0) == quality, str(equipped))
            initial = spawn(self, direction, [(24, 0)])
            snapshots = []
            for step in range(1, 5):
                commands = [["mana", 999], ["input", 1000, 0, 0, *direction],
                            ["clock"], ["castat", BS, *direction, "nocd"]]
                replies = self.g.gl_multi(commands)
                clock, cast = replies[-2:]
                time.sleep(0.35)
                state, now = self.g.gl_multi([["actorbuffs", 100, "qa_class_target_dummy"], ["clock"]])
                weak = [buff for actor in state.get("actors", []) for buff in actor.get("buffs", [])
                        if "weakness" in buff.get("tags", []) and buff.get("debuff")]
                expected = 2000 + 2000 * min(step, quality)
                elapsed = now.get("sceneMs", 0) - clock.get("sceneMs", 0)
                # Give() applies the pinned native Weakness definition. The cast action
                # occurs150ms after activation; native clocks bracket console latency.
                restored_ttl = weak[0].get("left", -999) + elapsed - 150 if len(weak) == 1 else None
                valid = (target_ok(initial, 1) and cast.get("activated") and len(weak) == 1
                         and not state.get("truncated") and restored_ttl is not None
                         and abs(restored_ttl - expected) <= 200)
                self.flag(tag + f"_step{step}", bool(valid), str({"cast": cast, "state": state,
                          "clock": [clock, now], "source_ttl": expected, "reconstructed_ttl": restored_ttl}))
                snapshots.append({"step": step, "cast": cast, "state": state, "clock": [clock, now],
                                  "expected_tier": min(step, quality), "expected_ttl": expected,
                                  "reconstructed_ttl": restored_ttl, "valid": bool(valid)})
            expired = self.wait_scene(9000)
            after = targets(self)
            off = not any("weakness" in buff.get("tags", []) for actor in after.values() for buff in actor.get("buffs", []))
            self.flag(tag + "_expires", expired and off, str(after))
            self.cases.append({"tag": tag, "initial": initial, "steps": snapshots, "after": after,
                               "outgoing_damage": "UNTESTED: damagefrom bypasses attacker outgoing scaling; requires actual native enemy attack"})
            self.checkpoint()

    def cooldown_measure(self, tag):
        before, cast = self.g.gl_multi([["clock"], ["castat", "warcry", 1, 0, "nocd"]])
        time.sleep(0.8)
        state = self.gl("skills")
        total = cooldown_total(before.get("sceneMs"), state, "warcry")
        return {"tag": tag, "before": before, "cast": cast, "skills": state,
                "total_ms": total, "valid": bool(cast.get("activated") and total is not None)}

    def provision_snapshot(self, quality, expected_positive):
        buffs, stack = self.g.gl_multi([["buffs"], ["givestacks", PROV_STACK, 0]])
        hud = sum(bool(row.get("hud")) for row in buffs.get("buffs", []))
        expected = provisions_expected(expected_positive, quality)
        return {"buffs": buffs, "stack_read_only_zero_delta": stack, "hud_including_one_debuff": hud,
                "positive_hud": expected_positive, "expected": expected,
                "valid": bool(buffs.get("ok") and not buffs.get("truncated")
                              and buffs.get("count") == len(buffs.get("buffs", []))
                              and hud == expected_positive + 1 and stack.get("stacks") == expected)}

    def refresh_provisions(self, paths, extra_positive_copy=False):
        # Existing helper's icon option makes a temporary native HUD-debuff copy,
        # explicitly testing the source !m_debuff filter; it never adds stacks.
        commands = [["givebuff", path, 5000] for path in paths]
        if extra_positive_copy:
            # A distinct bounded copy via the existing UI fixture brings11 real
            # positive HUD entries to33%, so the30% clamp is tested above its edge.
            commands.append(["givebuff", SHRINES[0], 5000, "icon"])
        commands += [["givebuff", BUFFS + "gale_tailwind_1", 5000],
                     ["givebuff", STATUS + "vulnerability_minor", 5000, "icon"], ["mana", 999]]
        replies = self.g.gl_multi(commands)
        count = len(paths) + int(extra_positive_copy)
        positives = replies[:count]
        negative = replies[count:count+2]
        setup = (all(row.get("applied") and row.get("hud") and not row.get("debuff") for row in positives)
                 and negative[0].get("applied") and not negative[0].get("hud") and not negative[0].get("debuff")
                 and negative[1].get("applied") and negative[1].get("hud") and negative[1].get("debuff"))
        time.sleep(0.65)
        return {"replies": replies, "valid": bool(setup), "fixture_positive_paths": paths,
                "extra_positive_ui_copy": extra_positive_copy}

    def provisions(self):
        direction = self.prepare_orbs("provisions")
        if direction is None:
            return
        learned = self.gl("skill", "warcry", 0)
        if learned.get("level", 0) < 1:
            learned = self.gl("skill", "warcry", 1)
        self.flag("provisions_warcry", learned.get("level", 0) >= 1, str(learned))
        baseline_buffs = self.gl("buffs")
        empty = not baseline_buffs.get("truncated") and not any(row.get("hud") for row in baseline_buffs.get("buffs", []))
        self.flag("provisions_empty_hud", bool(empty), str(baseline_buffs))
        setup = self.refresh_provisions(SHRINES[:2])
        control = self.cooldown_measure("provisions_control")
        self.flag("provisions_control", bool(empty and setup["valid"] and control["valid"]), str(control))
        for quality in range(1, 4):
            tag = f"provisions_r{quality}"
            equipped = self.gl("orb", PROVISIONS, 1)
            # Icon fixtures are distinct native definitions: a refresh does not
            # replace the previous HUD-debuff copy. Let all5000ms fixtures
            # expire naturally (rank1 Crusade at most5500ms +500ms poll).
            separated = self.wait_scene(6500)
            fresh = self.refresh_provisions(SHRINES[:2])
            fresh["previous_fixture_naturally_expired"] = separated
            before = self.provision_snapshot(quality, 2)
            cooldown = self.cooldown_measure(tag)
            after = self.provision_snapshot(quality, 2)
            valid = (equipped.get("level") == quality and separated and fresh["valid"] and before["valid"] and after["valid"]
                     and control["valid"] and cooldown["valid"]
                     and cooldown_matches(control["total_ms"], cooldown["total_ms"], 2 * quality))
            self.flag(tag + "_count_and_cooldown", bool(valid), str({"orb": equipped, "setup": fresh,
                      "before": before, "cooldown": cooldown, "after": after, "control": control}))
            self.cases.append({"tag": tag, "orb": equipped, "setup": fresh,
                               "before": before, "cooldown": cooldown, "after": after, "control": control})
            self.checkpoint()
        separated = self.wait_scene(6500)
        fresh = self.refresh_provisions(CAP_BUFFS, extra_positive_copy=True)
        fresh["previous_fixture_naturally_expired"] = separated
        before = self.provision_snapshot(3, 11)
        cap_cd = self.cooldown_measure("provisions_cap")
        after = self.provision_snapshot(3, 11)
        self.flag("provisions_r3_cap30", bool(separated and fresh["valid"] and before["valid"] and after["valid"]
                  and cap_cd["valid"] and cooldown_matches(control["total_ms"], cap_cd["total_ms"], 30)),
                  str({"setup": fresh, "before": before, "cooldown": cap_cd, "after": after}))
        self.cases.append({"tag": "provisions_r3_cap30", "setup": fresh, "before": before, "cooldown": cap_cd, "after": after})
        self.wait_scene(6500)
        buffs, stacks = self.g.gl_multi([["buffs"], ["givestacks", PROV_STACK, 0]])
        restored = self.cooldown_measure("provisions_expired")
        reverted = (not buffs.get("truncated") and not any(row.get("hud") for row in buffs.get("buffs", []))
                    and stacks.get("stacks") == 0 and restored["valid"]
                    and cooldown_matches(control["total_ms"], restored["total_ms"], 0))
        self.flag("provisions_natural_expiry_reverts", bool(reverted), str({"buffs": buffs, "stacks": stacks, "cooldown": restored}))
        self.cases.append({"tag": "provisions_expired", "buffs": buffs, "stacks": stacks, "cooldown": restored})


def run(pilot, section, **_):
    c = Checks(pilot)
    c.cases = []
    try:
        {"martyr": c.martyr, "crest": c.crest, "drum": c.drum, "provisions": c.provisions}[section]()
    except Exception as exc:
        c.notes.append("First failure preserved; runner owns teardown: " + repr(exc))
        c.checkpoint()
        raise
    c.to_town()
    c.checkpoint(True)
    return {**c.out, "notes": c.notes, "cases": c.cases, "measurement_only": True,
            "source": ["mods/specs/scripts/HWP/Specs/Bannerlord.as",
                       "mods/specs/players/hwp/specs/bannerlord/battlefield_standard.sval",
                       "mods/specs/players/hwp/specs/bannerlord/righteous_crusade.sval",
                       "gamecode/sdk/hoh2/tweak/buffs/status_effects.sval"],
            "not_covered": ["real teammate recipients/split and network (BLOCKED)",
                            "WarDrum actual enemy outgoing attack damage",
                            "Provisions rank1/2 cap with30/15 distinct native HUD buffs",
                            "ordinary gameplay acquisition/UI, death/transition/save lifecycle"]}
