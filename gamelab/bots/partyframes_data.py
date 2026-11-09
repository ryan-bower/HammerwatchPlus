"""Solo host-path check for HWP::AllyStatus: a real Bannerlord shield and a real potion upgrade,
read back from what returned through the host's relay. Forced setup, and a client's path needs
two clients, which GameLab can't run: not party proof."""
import re
import time

from gamelab.bots.qa_specs_banner_brand import Checks, BS

LINE = re.compile(r"\(local\): shield ([0-9.e-]+), potions (\d+)/(\d+), relayed shield ([0-9.e-]+), potions (\d+)/(\d+)")


def status(c):
    text = c.hwp("partyframes", 0.5, until="relayed")
    match = LINE.search(text)
    if not match:
        return None, text
    keys = ("shield", "left", "total", "relayed", "relayed_left", "relayed_total")
    return {k: float(v) for k, v in zip(keys, match.groups())}, text


def run(pilot, **_):
    c = Checks(pilot)
    if c.prepare_banner("frames"):
        c.hwp("skillpoints 200")
        c.rank(BS, 5, "frames_standard")
        direction = c.open_dir(230)
        c.gl("hurt", .9)
        cast = c.standard_cast(direction, reset=True, refill=True)
        c.wait_buff("standard_shield")
        time.sleep(.6)  # past the throttle
        up, text = status(c)
        c.out["shield_up"] = {"cast": cast, "status": up, "text": text}
        c.flag("frames_shield_relayed", bool(up and abs(up["relayed"] - .05) < .01), str(up))

        c.gl("damageme", 20)
        time.sleep(.6)
        hit, text = status(c)
        c.out["shield_hit"] = {"status": hit, "text": text}
        c.flag("frames_shield_drops", bool(up and hit and hit["relayed"] < up["relayed"]), str(hit))

        # the standard's pulses keep renewing the shield, so hit it down rather than wait it out
        gone, text = hit, ""
        for _ in range(6):
            c.gl("hurt", .5)
            c.gl("damageme", 20)
            time.sleep(.3)  # no throttle on reaching zero
            gone, text = status(c)
            if gone and gone["relayed"] == 0:
                break
        c.out["shield_gone"] = {"status": gone, "text": text}
        c.flag("frames_shield_zero", bool(gone and gone["relayed"] == 0), str(gone))

        c.gl("upgrade", "apothecary", "potion-charges", 0)
        time.sleep(.6)
        potions, text = status(c)
        c.out["potions"] = {"status": potions, "text": text}
        c.flag("frames_potions_relayed", bool(potions and potions["total"] > 0 and potions["relayed_total"] == potions["total"]
                                              and potions["relayed_left"] == potions["left"]), str(potions))
        c.gl("hurt", .5)
    return {**c.out, "notes": c.notes, "measurement_only": True, "party_effects_tested": False}
