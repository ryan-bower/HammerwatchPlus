"""Actual Gladius native collision/payload diagnostics; no synthetic hit calls.

The original four-cardinal-target capture is retained. This separate case uses
actual targets centered on the independently certified outgoing lane and records
native m_lastCollision/penetration plus instantiated damage during normal input.
"""
import math
import struct
import time

from gamelab.bots.qa_class_base import Checks as Base
from gamelab.bots.qa_classes import QA_DUMMY_FILTER
from gamelab.hps import hash_string

SKILL = "hwp_gladiator_gladius"
PRODUCER = "players/hwp/gladiator/projectiles/gladius.unit"
ELEMENTS = ("physical", "fire", "ice", "lightning", "poison", "pure")
# Native whirling_axe.inc authors100; NewProjectile.as1135 adds1.
NATIVE_INITIAL_PENETRATION = 101


def uint32(value):
    return value & 0xffffffff if type(value) is int else None


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def native_damage_round(value):
    value = f32(value)
    if value == 0:
        return 0
    rounded = int(f32(value + (0.5 if value > 0 else -0.5)))
    return 1 if 0 < value < 1 else -1 if -1 < value < 0 else rounded


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def first_contact_model(rows, ids, rank, probe):
    """Predict from native inputs, never measured HP or runtime fitted constants.

    Native PlayerDamage truncates uint32 before PlayerBase power/element rounding.
    Pure-physical hand, zero target armor/buffs, isolated first contact and no crit
    are mandatory fixture gates; later per-contact growth is preserved, not fitted.
    """
    coefficient = f32((1.2, 1.4, 1.6, 1.8, 2.0)[rank-1])
    births = [r for r in rows if r.get("reason") == "birth" and r.get("projectile") is True]
    contacts = [r for r in rows if r.get("projectile") is True
                and r.get("collision_unit") in ids and r.get("penetration") == 100
                and r.get("collision_valid") is True and r.get("collision_actor") is True]
    first_hp = next((r for r in rows if r.get("reason") == "target_hp"
                     and any(finite(a.get("hpExact")) and a["hpExact"] < 15000 for a in r.get("targets", []))), {})
    birth, contact = (births[0] if len(births) == 1 else {}), (contacts[0] if len(contacts) == 1 else {})
    payloads = birth.get("payload", {}).get("damage", [])
    payload = payloads[0] if len(payloads) == 1 else {}
    hand, model = payload.get("hand", {}), payload.get("model", {})
    typed = all(finite(hand.get(k)) for k in ELEMENTS) and all(finite(model.get(k)) for k in
        ("spellPower", "powerDivisor", "globalDamageMul", "buffDamageMul", "physicalDamageMul", "skillDamageMul",
         "spellCritChance", "skillCritChance"))
    factor_fixture = bool(typed and hand["physical"] > 0 and all(hand[k] == 0 for k in ELEMENTS if k != "physical")
        and model.get("skill_valid") is True and model.get("spell") is True and model["powerDivisor"] == 200
        and model["spellPower"] >= 0 and model["spellCritChance"] == model["skillCritChance"] == 0
        and model["globalDamageMul"] == model["buffDamageMul"] == model["physicalDamageMul"] == model["skillDamageMul"] == 1
        and probe.get("ok") is True and probe.get("rolls") == 0 and probe.get("skill") == SKILL
        and type(probe.get("damageMul")) is list and len(probe["damageMul"]) == 2
        and all(finite(x) and x == 1 for x in probe["damageMul"])
        and finite(probe.get("spellCrit")) and finite(probe.get("skillCrit"))
        and probe.get("spellCrit") == probe.get("skillCrit") == 0
        and probe.get("skillDmgMul") == 1)
    coefficient_ok = bool(payload.get("kind") == "PlayerDamage" and payload.get("primary") is True
        and payload.get("merged") == 0 and uint32(payload.get("weapon_info")) == uint32(hash_string(SKILL))
        and finite(payload.get("mul")) and abs(payload["mul"] - coefficient) <= 0.000001)
    all_targets = [a for r in (birth, contact, first_hp) for a in r.get("targets", [])]
    target_fixture = bool(len(all_targets) == 6 and all(a.get("native_props") is True and a.get("valid") is True
        and a.get("dead") is False and a.get("hpMax") == 15000 and a.get("armor") == 0
        and all(a.get(k) == 0 for k in ("resFire", "resIce", "resLightning", "resPoison"))
        and a.get("damageTakenMul") == 1 and a.get("receiveCritChance") == 0
        and finite(a.get("armorMulPhysical")) and a["armorMulPhysical"] == 1
        and finite(a.get("modifierSpell")) and a["modifierSpell"] == 1 for a in all_targets))
    chronology = bool(birth and contact and birth.get("owner_is_player") is True
        and contact.get("owner_is_player") is True and birth.get("penetration") == 101 and birth.get("intensity") == 1
        and contact.get("now", 0) > birth.get("now", 0) and finite(contact.get("intensity"))
        and abs(contact["intensity"] - coefficient) <= 0.001)
    changed = [a for a in first_hp.get("targets", []) if finite(a.get("hpExact")) and a["hpExact"] < 15000]
    isolated = bool(chronology and first_hp and first_hp.get("now") == contact.get("now") and len(changed) == 1
        and changed[0].get("unit") == contact.get("collision_unit")
        and all(a.get("hpExact") == 15000 for a in first_hp.get("targets", []) if a.get("unit") != contact.get("collision_unit")))
    expected, raw, observed = None, None, 15000-changed[0]["hpExact"] if len(changed) == 1 else None
    if factor_fixture and coefficient_ok:
        # Damage.as185, PlayerBase.as840..853/936, Armor.as26..44.
        raw = int(f32(f32(f32(1) * coefficient) * f32(hand["physical"])))
        power = f32(f32(f32(model["powerDivisor"]) + f32(model["spellPower"])) / f32(model["powerDivisor"]))
        mul = f32(f32(model["buffDamageMul"]) * f32(model["globalDamageMul"]))
        mul = f32(mul * power)
        mul = f32(mul * f32(model["skillDamageMul"]))
        mul = f32(mul * f32(changed[0]["modifierSpell"] if isolated else 1))
        expected = native_damage_round(f32(f32(raw * mul) * f32(model["physicalDamageMul"])))
    #15k float32 health fraction one-ULP is~0.000894HP; difference of2 endpoints
    # plus9dp serialization fits0.003HP. Zeroarmor andDamageTaken1 preserve integer.
    amplitude = bool(factor_fixture and target_fixture and coefficient_ok and isolated
        and expected is not None and expected > 0 and finite(observed) and abs(observed-expected) <= 0.003)
    return {"coefficient_ok": coefficient_ok, "fixture_ok": factor_fixture and target_fixture,
            "chronology_ok": chronology, "isolated": isolated, "amplitude_ok": amplitude,
            "coefficient": coefficient, "hand": hand, "native_factors": model, "critprobe": probe,
            "raw_player_damage_uint32": raw, "expected_first_hp": expected, "observed_first_hp": observed,
            "hp_tolerance": 0.003, "birth": birth, "first_contact": contact, "first_hp": first_hp}


class Checks(Base):
    def measure(self, rank, direction, producer):
        label = "gladius_contact_r" + str(rank)
        learned = self.learn(SKILL, rank, label)
        button = self.normal_button(SKILL)
        targets = self.targets([(direction[0]*24, direction[1]*24),
                                (direction[0]*48, direction[1]*48)])
        self.flag(label + "_targets", bool(targets and len(targets) == 2), str(targets))
        if not targets or not learned or not button:
            return
        ids = {a["unit"] for a in targets}
        origin = self.pos()
        line = all(abs((a["x"]-origin[0])*direction[1]-(a["y"]-origin[1])*direction[0]) <= 1
                   and 20 <= math.dist(origin, (a["x"], a["y"])) <= 50 for a in targets)
        self.flag(label + "_actual_target_alignment", line, str({"origin":origin,"direction":direction,"targets":targets}))
        fixture = self.gl("skillcrit", SKILL, 0)
        self.flag(label + "_noncrit_fixture", fixture.get("ok") is True
                  and fixture.get("override_active") is True and fixture.get("crit_chance") == 0
                  and fixture.get("spell_crit_chance") == 0, str(fixture))
        try:
            self.gl("mana", 999)
            if not self.raw_ready(SKILL, label):
                return
            before = self.gl("state")
            probe = self.gl("critprobe", 0, 100, QA_DUMMY_FILTER, SKILL)
            tag = label + "_" + str(time.time_ns())
            accepted = self.g.gl_multi([["qa_class_projectile", tag, 4500, producer, *(a["unit"] for a in targets)],
                                        ["input", 500, 0, 0, *direction, button]])
            done = self.g.wait_gl(lambda e:e.get("ev") == "qa_class_projectile"
                                 and e.get("tag") == tag and e.get("phase") == "done", timeout=12) or {}
            rows = [e for e in self.g.gl if e.get("ev") == "qa_class_projectile"
                    and e.get("tag") == tag and e.get("phase") == "sample"]
            after, loss = self.snapshots(targets)
            state, skills = self.g.gl_multi([["state"], ["skills"]])
            protocol = (len(accepted) == 2 and all(a.get("ok") is True for a in accepted)
                        and done.get("complete") is True and done.get("error") == ""
                        and done.get("truncated") is False and done.get("producer") == producer
                        and done.get("seen") == done.get("count") == len(rows)
                        and [r.get("index") for r in rows] == list(range(len(rows)))
                        and 4500 <= done.get("ms", -1) <= 4600 and done.get("frames", 0) >= 10
                        and done.get("projectiles") == 1 and done.get("live") == 0
                        and all({a.get("unit") for a in r.get("targets", [])} == ids
                                and all(a.get("valid") is True and a.get("hpMax") == 15000
                                        for a in r["targets"]) for r in rows))
            projectile_rows = [r for r in rows if r.get("projectile") is True]
            contacts = [r for r in projectile_rows if r.get("collision_unit") in ids
                        and r.get("collision_valid") is True and r.get("collision_actor") is True
                        and type(r.get("penetration")) is int and 0 <= r["penetration"] < NATIVE_INITIAL_PENETRATION]
            payloads = [r.get("payload", {}) for r in projectile_rows]
            payload_ok = bool(payloads) and all(p.get("present") is True and p.get("truncated") == 0
                and p.get("damage_count") == 1 and len(p.get("damage", [])) == 1
                and p["damage"][0].get("kind") == "PlayerDamage" and p["damage"][0].get("merged") == 0
                and p["damage"][0].get("primary") is True
                and uint32(p["damage"][0].get("weapon_info")) == uint32(hash_string(SKILL))
                and finite(p["damage"][0].get("mul")) for p in payloads)
            amplitude = first_contact_model(rows, ids, rank, probe)
            current = next((s for s in skills.get("skills", []) if s.get("id") == SKILL), {})
            paid = (before.get("ok") is True and state.get("ok") is True
                    and isinstance(before.get("player", {}).get("manaExact"), (int,float))
                    and isinstance(state.get("player", {}).get("manaExact"), (int,float))
                    and before["player"]["manaExact"] > state["player"]["manaExact"])
            # Native event birth/contact proves activation even if the full
            #4500ms observation naturally outlasts the3s cooldown/mana refill.
            activated = bool(projectile_rows and protocol)
            detail = {"rank":rank,"before":before,"after_state":state,"final_skill":current,
                      "mana_still_lower_at_end":paid,"targets":targets,"after":after,"loss":loss,
                      "accepted":accepted,"done":done,"rows":rows,"contacts":contacts,
                      "payloads":payloads,"noncrit_fixture":fixture,"first_contact_model":amplitude}
            self.flag(label + "_observer_protocol", protocol, str(done))
            self.flag(label + "_normal_cast_registered", activated, str({"button":button,"births":len(projectile_rows)}))
            self.flag(label + "_native_contact", bool(protocol and line and contacts), str(contacts))
            self.flag(label + "_payload_readback", protocol and payload_ok, str(payloads))
            self.flag(label + "_native_weapon_coefficient", protocol and amplitude["coefficient_ok"], str(amplitude))
            self.flag(label + "_native_damage_fixture", protocol and amplitude["fixture_ok"], str(amplitude))
            self.flag(label + "_first_contact_intensity", protocol and amplitude["chronology_ok"], str(amplitude))
            self.flag(label + "_first_contact_isolated", protocol and amplitude["isolated"], str(amplitude))
            self.flag(label + "_first_contact_amplitude", protocol and amplitude["amplitude_ok"], str(amplitude))
            self.flag(label + "_actual_damage", bool(protocol and line and contacts and payload_ok
                                                       and isinstance(loss,(int,float)) and loss > 0), str(detail))
            self.out.setdefault("gladius_contact_trials", []).append(detail)
        finally:
            restore = self.gl("skillcrit", SKILL, "restore")
            self.flag(label + "_crit_restored", restore.get("ok") is True
                      and restore.get("override_active") is False, str(restore))

    def diagnose(self, producer):
        if not self.prepare("hwp_gladiator", None, "QAGladiusContact"):
            return
        lane, note = self.to_trident_lane(front=72, back_neighbor=True, ray_distance=120,
                                          tag="gladius_contact", clearance_points=((0,0,40),))
        self.flag("gladius_contact_geometry", bool(lane), note)
        if not lane:
            return
        for rank in range(1, 6):
            self.measure(rank, lane[0], producer)
        self.to_town()


def run(p, producer=PRODUCER, **_):
    c = Checks(p)
    try:
        c.diagnose(producer)
    except Exception as exc:
        c.flag("gladius_contact_crashed", False, repr(exc))
    c.out.update(notes=c.notes, terminal=" | ".join(c.notes)[-5000:])
    return c.out
