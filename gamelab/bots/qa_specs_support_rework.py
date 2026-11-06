"""Controlled solo support/brand checks; forced setup, not party/ordinary-play proof."""
import re
import time

from gamelab.bots.qa_specs_banner_brand import Checks, BS, RC
from gamelab.bots.plan_specs import BUFFS
from gamelab.bots.qa_specs_branding_effects import Checks as BrandChecks, PB, claw_line

SPREE = "players/warrior/stacks_warrior.sval:killing_spree"
ESSENCE = "players/warlock/stacks_warlock.sval:essence"
EE = "hwp_wlk_essence_extraction"


def pool(c, name):
    text = c.specs()
    match = re.search(r"\b" + re.escape(name) + r" ([0-9.]+)", text)
    return (float(match.group(1)) if match else None), text


def run(pilot, **_):
    c = Checks(pilot)
    if c.prepare_banner("support"):
        c.hwp("skillpoints 200")
        c.rank(BS, 5, "support_standard")
        c.rank(RC, 5, "support_crusade")
        c.rank("killing_spree", 5, "support_spree")
        c.gl("orb", "hwp_war_bs_feared_crest", 3)
        c.set_stacks(SPREE, 0)
        direction = c.open_dir(230)
        c.gl("hurt", .9)
        baseline = c.gl("damageme", 20)
        cast = c.standard_cast(direction, reset=True, refill=True)
        shield = c.wait_buff("standard_shield")
        amount, text = pool(c, "standard")
        state = c.gl("state").get("player", {})
        c.out["banner_initial"] = {"cast": cast, "shield": shield, "pool": amount, "status": text, "state": state}
        c.flag("banner_shield_active", bool(cast.get("activated") and shield.get("on") and amount and amount > 0))
        c.flag("banner_shield_own_hp", amount is not None and abs(amount - state.get("hpMax", 0) * .05) < .1)
        hit = c.gl("damageme", 20)
        c.out["shield_damage"] = {"baseline": baseline, "shielded": hit}
        c.flag("banner_absorbs_damage", baseline.get("took", 0) > 0 and hit.get("took", -1) < baseline["took"] and hit.get("took", -1) >= 0)
        c.flag("banner_duration_scaled", bool(4500 < shield.get("left", 0) <= 6000))
        c.flag("banner_rallied", "rallied yes" in text)
        thrown = c.standard_cast(direction)
        # castat acknowledges activation before the native 150 ms cast point.
        until, left, samples = time.monotonic() + 2, None, []
        while time.monotonic() < until:
            after = c.specs()
            samples.append(after)
            left = re.search(r"; thrown (\d+) ms", after)
            if left:
                break
            time.sleep(.1)
        c.out["banner_throw"] = {"cast": thrown, "status": after, "samples": samples}
        c.flag("banner_throw_preserves_lifetime", bool(thrown.get("activated") and left and int(left.group(1)) > 10000))
        time.sleep(3.2)
        refreshed = c.has("standard_shield")["standard_shield"]
        c.flag("banner_pulse_replenishes", bool(refreshed.get("on") and refreshed.get("left", 0) > 3500))
        c.to_town()

    c.setup("soul", "warlock", "hwp_warlock_branding", [EE])
    c.gl("orb", "hwp_wlk_ee_essence_empowerment", 3)
    c.gl("orb", "hwp_wlk_ee_released_essence", 3)
    if c.enter_floor("soul"):
        c.set_stacks(ESSENCE, 0)
        before = c.gl("benchstats")
        gained = c.gl("givestacks", ESSENCE, 1)
        buffs = c.has("soul_guard", "soul_stride_3")
        after = c.gl("benchstats")
        amount, text = pool(c, "soul")
        c.out["soul_gain"] = {"gain": gained, "before": before, "after": after, "buffs": buffs, "pool": amount, "status": text}
        c.flag("soul_guard_active", bool(buffs["soul_guard"].get("on") and amount and amount > 0))
        c.flag("soul_stride_speed", abs(after.get("moveSpeed", 0) - before.get("moveSpeed", 0) * 1.2) < .003)
        # Native Essence itself increases max HP. Evaluate this gain's snapshot
        # against HP immediately BEFORE the gain, not five times the first shield.
        cap_basis = c.gl("state").get("player", {}).get("hpMax", 0)
        c.gl("givestacks", ESSENCE, 5)
        capped, captext = pool(c, "soul")
        c.out["soul_cap"] = {"max_hp_at_gain": cap_basis, "expected": cap_basis * .1, "observed": capped, "status": captext}
        c.flag("soul_guard_cap", bool(cap_basis > 0 and capped and abs(capped - cap_basis * .1) <= .1))
        c.gl("givestacks", ESSENCE, -999)
        retained, _ = pool(c, "soul")
        c.flag("soul_spend_keeps_shield", bool(retained and capped and abs(retained - capped) <= .1))
        time.sleep(4.5)
        gone = c.has("soul_guard", "soul_stride_3")
        restored = c.gl("benchstats")
        c.out["soul_expiry"] = {"buffs": gone, "stats": restored, "cap_status": captext}
        c.flag("soul_effects_expire", not any(b.get("on") for b in gone.values()) and abs(restored.get("moveSpeed", 0) - before.get("moveSpeed", 0)) < .003)
        c.to_town()
    b = BrandChecks(pilot)
    if b.prepare("rework_brand"):
        b.rank(PB, 5, "rework_brand")
        b.rank("demons_tail", 5, "rework_tail")
        b.gl("orb", "hwp_wlk_pb_proliferation", 3)
        targets = b.fresh(60, 80, homogeneous=True)
        if targets:
            branded, _ = b.brand_cast(PB, *b.direction)
            b.tails(1, *b.direction)
            before = b.specs()
            stored = re.search(r"\bstored (\d+)", before)
            detonated, log = b.brand_cast(PB, *b.direction, nocd=False)
            after = b.specs()
            carried = re.search(r"brands (\d+) stored (\d+) brandcharge (\d+)", after)
            claw = claw_line(log)
            b.out["brand_proliferation"] = {"before": before, "after": after, "log": log, "claw": claw, "targets": targets}
            b.flag("brand_manual_proliferates", bool(branded and detonated and carried and int(carried.group(1)) == 2))
            b.flag("brand_carries_investment", bool(stored and int(stored.group(1)) > 0 and carried and abs(int(carried.group(2)) - 2 * int(stored.group(1))) <= 3))
            b.flag("brand_manual_bonus", bool(claw and abs(claw["amount"] - (40 + claw["stored"] * claw["charge"]) * 1.25) <= 2))
            time.sleep(6.2)
            end = b.specs()
            b.out["brand_expiry"] = end
            b.flag("brand_chain_expires", "brands 0 stored 0" in end)
        b.to_town()
    return {**c.out, **b.out, "notes": c.notes + b.notes, "measurement_only": True, "party_effects_tested": False}
