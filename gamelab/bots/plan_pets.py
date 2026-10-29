"""Test-plan checks for the pets group (pets s2/s4/s5/s9/s10/s12), on top of
plan_checks' helpers. Everything goes through gl verbs, HWP console commands and the game's
own windows (gl use / press / presslist), never real input.

Sections, by scenario:
  plan-pets-a (the fixture's own GameLab character, made before HWP was enabled):
    legacy_record, dyer_nopet, petshop, dyer_choice, dye_pet | legacy_run, dye_floor,
    to_town | restart | dye_restart, dye_remove
  plan-pets-b (a fresh LabPets): pets_setup, smash, mend, stun, puzzle_wait, trap_wait,
    trap_leave, morale_on | morale_combat | morale_after
  plan-petrooms-vanilla (QoL without the Pets package: a vanilla pet, driven by petrooms'
    PetRooms.as): vanilla_setup, puzzle_wait, trap_wait, trap_leave

Verbs beyond plan_checks: presslist / querycmp / unitdestroy (Verbs_pets.as), buildup
(Verbs_farming.as), hurt / buffs (Verbs_classesb.as), actorbuffs (Verbs_classesa.as)."""
import json
import math
import re
import time

from gamelab.bots.plan_checks import Checks as Base

# the three dyes the town is given (tweak/player_colors.sval): blueprint -> mid colour
# (PetDye.Name writes the name in m_colors[1], encoded back to the sval's sRGB hex) and
# the tailor's price for the quality
DYES = {"dye_gray": ("414b57", 100), "dye_lemon": ("b8a434", 250), "dye_midnight": ("222270", 500)}


def dye_hex(h):
    """The DYES mid colour a menu's colour code shows (within 3 a channel for rounding), else
    the code as it is: a still-linear 0d1218 for 414b57 is a miss."""
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    for want, _ in DYES.values():
        if all(abs(c - int(want[i:i + 2], 16)) <= 3 for c, i in zip(rgb, (0, 2, 4))):
            return want
    return h
PUZZLE_PFB = "prefabs/puzzles/puzzle_lights_out_small.pfb"
PUZZLE_UNIT = "doodads/buttons/button_magic.unit"
# a trap room for petrooms (three trap spots within petwait.radius): pressure-plate spikes
TRAP_UNIT = "doodads/traps/floors/floor_spikes_pressure.unit"
# the floor's own traps the walks keep clear of (floor_traps): what generated floors place
FLOOR_TRAPS = [f"doodads/traps/{u}.unit" for u in (
    "floors/floor_spikes", "floors/floor_spikes_pressure", "floors/floor_spikes_cave_light",
    "floors/floor_spikes_pressure_crypt", "floors/floor_fire", "floors/floor_curse", "mines/spike_trap")] + [
    f"doodads/hwp/traps/hwp_glyph_{g}.unit" for g in ("bomb", "confusion", "dart")]
# "with the player": a following pet idles anywhere inside the base range-idle (100 px) and
# only walks once past it (144852: 86.8 px off and idle for 11 s, by design)
FOLLOW_PX = 110


class Checks(Base):
    # --- plumbing
    def window(self):
        return self.gl("state").get("window") or ""

    def close_windows(self):
        for _ in range(3):
            if not self.window():
                return
            self.g.key("escape")
            time.sleep(0.4)

    def player(self):
        return self.gl("state").get("player", {})

    def pet(self):
        """The HoH1/vanilla pet (a MiniPet unit) nearest the player, or {}."""
        us = self.gl("near", 1200, "pets/").get("units") or []
        us = [u for u in us if "pets/" in u.get("name", "")]
        return min(us, key=lambda u: u.get("dist", 1e9)) if us else {}

    def clear(self):
        """cull, then goblin totems by name: cull and kill tag:enemy leave them (live runs),
        and any live enemy within 350 px keeps Morale off."""
        self.gl("cull")
        self.gl("kill", 800, "totem")
        time.sleep(0.5)

    def foe_at(self, dist):
        """A spawn offset `dist` px out that the pathfinder reaches (a spawn into a wall is
        pushed elsewhere); (dist, 0) when none answers."""
        sp = self.spot(dist)
        return (sp[0], sp[1]) if sp else (dist, 0)

    def god(self, on=True):
        """hwp god toggles; toggle again when the reply says the other state."""
        want = "god mode on" if on else "god mode off"
        for _ in range(2):
            if want in self.hwp("god", 0.4, until="god mode"):
                return True
        return False

    def hp(self):
        pl = self.player()
        return pl.get("hp", 0), max(1, pl.get("hpMax", 1))

    def set_hp(self, frac):
        """gl hurt (PlayerRecord.hp); without that verb, cht_damage down to the fraction."""
        r = self.gl("hurt", frac)
        if r.get("ok"):
            time.sleep(0.3)
            return
        hp, mx = self.hp()
        if hp > frac * mx:
            self.g.console(f"cht_damage {int(hp - frac * mx)}")
        time.sleep(0.4)

    def hwp_keys(self):
        """The keys of the record's "hwp" dictionary, or None when the record has none."""
        r = self.gl("inspect", "player", "hwp")
        return r.get("keys") or [] if r.get("ok") else None

    def petdye(self):
        """hwp pet dye (pets.debug): (current dye text, pet unit file)."""
        out = self.hwp("pet dye", 0.6, until="| unit")
        # the log line has the reply's colour codes stripped (HWP::Commands::Reply prints Plain)
        m = re.findall(r"\[HWP\] (.*?) \| unit (\S+)", out)
        return m[-1] if m else ("", "")

    @staticmethod
    def dyed(cur, unit):
        """The pet wears a dye: a two-section pet (the text names both sections) is swapped
        for its dye-ready unit copy (players/pets/hwp/dye/); a one-section pet's text names
        a dye instead of "no dye"."""
        if ", " in cur.split(": ", 1)[-1]:
            return "/dye/" in unit
        return bool(cur) and "no dye" not in cur

    def spot(self, dist, avoid=()):
        """An offset `dist` px away the pathfinder reaches on a near-straight path (a detour
        round a wall is past a pet's leash), or None."""
        pl = self.player()
        for a in [0, 180, 90, 270, 45, 135, 225, 315]:
            if a in avoid:
                continue
            dx, dy = round(dist * math.cos(math.radians(a))), round(dist * math.sin(math.radians(a)))
            pf = self.gl("pathfind", pl.get("x", 0) + dx, pl.get("y", 0) + dy)
            if pf.get("ok") and pf.get("nodes", 0) > 0 and pf.get("length", 1e9) <= dist * 1.25:
                return dx, dy, a
        return None

    def unreachable(self, lo, hi):
        """An offset lo-hi px off the player the pathfinder has no route to, or None."""
        pl = self.player()
        for dist in (lo, (lo + hi) // 2, hi):
            for a in range(0, 360, 30):
                dx, dy = round(dist * math.cos(math.radians(a))), round(dist * math.sin(math.radians(a)))
                pf = self.gl("pathfind", pl.get("x", 0) + dx, pl.get("y", 0) + dy)
                if pf.get("ok") and pf.get("nodes", 0) == 0:
                    return dx, dy
        return None

    def gone(self, unit, filt, wait=8, r=1200):
        """Whether unit id `unit` (a `filt` match) leaves the floor within `wait` s."""
        end = time.time() + wait
        while time.time() < end:
            ids = {u["unit"] for u in self.gl("near", r, filt).get("units") or []}
            if unit not in ids:
                return True
            time.sleep(0.5)
        return False

    # --- pets s12: a character from before HWP
    def legacy_record(self):
        """The fixture character was made with only the GameLab mods: its record has no HWP pet
        toggles (no pets.options_set) and vanilla's pet-options 0."""
        po = self.gl("inspect", "player", "pet-options").get("value")
        keys = self.hwp_keys()
        self.legacy_keys = keys
        self.flag("legacy_char", po in (0, -1) and "pets.options_set" not in (keys or []),
                  f"pet-options {po}, hwp keys {keys}")

    def legacy_run(self):
        """pets s12: with the toggles never touched, the pet picks up gold, materials and a
        health pickup (owner below 30 %) at once."""
        self.hwp("set pets.debug true", 0.4)
        self.start_floor(0)
        self.gl("cull")
        time.sleep(1.5)
        g0 = self.gold()
        n, left = 0, -1
        for _ in range(3):
            n = self.gold_drop()
            left = self.gold_left(8)
            if left == 0 or not hasattr(self, "drop_dir"):
                break
            self.bad_dirs = getattr(self, "bad_dirs", set()) | {self.drop_dir}
            del self.drop_at
            self.dropped = []
        g1 = self.gold()
        self.flag("legacy_pet_gold", n > 0 and left == 0 and g1 > g0, f"{n} drop(s) at {self.drop_at}, {left} left, gold {g0} -> {g1}")
        w0 = (self.gl("inv").get("materials") or {}).get("wood", 0)
        d = self.gl("drop", "wood", 5, *self.drop_at)
        ok = d.get("ok") and self.gone(d.get("unit"), "materials/", 8)
        w1 = (self.gl("inv").get("materials") or {}).get("wood", 0)
        self.flag("legacy_pet_materials", ok and w1 > w0, f"drop {d.get('name')}, wood {w0} -> {w1}")
        # the floor's own heal pickups go first: the pet fetches the one nearest it, which was
        # a floor apple, not ours. The player stands still, ours is past their reach.
        cl = self.gl("unitdestroy", 1200, "pickups/health")
        self.set_hp(0.2)
        h0, mx = self.hp()
        p0 = self.player()
        a = self.gl("spawn", "items/pickups/health_apple.unit", *self.drop_at)
        ok = a.get("ok") and self.gone(a.get("unit"), "health_apple", 8)
        h1, _ = self.hp()
        p1 = self.player()
        moved = math.hypot(p1.get("x", 0) - p0.get("x", 0), p1.get("y", 0) - p0.get("y", 0))
        self.flag("legacy_pet_potion", ok and h1 > h0 and moved < 8,
                  f"cleared {cl.get('count')} floor heal(s), {a.get('name')} at {self.drop_at} fetched {ok}, "
                  f"player moved {moved:.0f}, hp {h0} -> {h1} / {mx}")
        self.set_hp(1.0)
        keys = self.hwp_keys()
        self.flag("legacy_toggles_untouched", "pets.options_set" not in (keys or []), f"hwp keys {keys}")

    # --- pets s9/s10: the tailor
    def tailor(self):
        """The tailor's building and NPC: the story flag its unit and building want, the building
        (gl build: the town builder's own AddBuilding), a refresh; spawned when still missing."""
        # cht_set_flag needs e_cheats, and a restarted game has it off again (run
        # 20261018-141404 pass 2: "can only be executed with e_cheats = 1"); without the flag
        # npc_dyer's conditionals destroy the dyer (NPCBehavior CheckForExistance)
        self.g.console("e_cheats 1")
        time.sleep(0.2)
        self.g.console("cht_set_flag mission_story_unlocked_dyer 1 1")
        time.sleep(0.3)
        b = self.gl("build", "tailor")
        self.gl("townrefresh")
        time.sleep(3)
        self.npc("npc_dyer", "actors/npcs/town/npc_dyer.unit")
        return b

    def use_dyer(self):
        """Use the tailor. A fixture character (gl char) has no portrait pieces, and the vanilla
        dyer's preview throws on a missing one (GetPortraitModel(null)) and leaves the game
        paused with the NPC stuck mid-interaction, so give it the defaults first."""
        if not getattr(self, "portrait_done", False):
            r = self.gl("portrait")
            self.portrait_done = bool(r.get("ok"))
            self.portrait_note = f"portrait {r.get('before')} -> {r.get('after')} pieces, added {r.get('added')}"
        self.close_windows()
        u = self.gl("use", "npc_dyer")
        time.sleep(0.8)
        return u, self.window()

    def dyer_nopet(self):
        """pets s9: without a pet out the tailor opens the vanilla dyer straight away."""
        b = self.tailor()
        u, w = self.use_dyer()
        self.flag("dyer_nopet_direct", "EquipmentDyerWindow" in w,
                  f"build {b.get('ok')}, {getattr(self, 'portrait_note', 'no portrait')}, use {u.get('ok')} {u.get('error') or u.get('unit')}, window {w!r}")
        self.close_windows()

    def dyer_choice(self):
        """pets s9: with a pet out the tailor asks Dye gear / Dye pet; gear is the vanilla dyer."""
        self.hwp("set pets.debug true", 0.4)
        u, w = self.use_dyer()
        txt = self.widget("pet-dye").get("text", "")
        self.flag("dyer_choice_opens", w == "HWPDyerChoice" and bool(self.widget("gear-btn")) and bool(self.widget("pet-btn")),
                  f"window {w!r}, {txt!r}")
        self.gl("press", "gear-btn")
        time.sleep(0.8)
        w2 = self.window()
        self.flag("dyer_gear_vanilla", "EquipmentDyerWindow" in w2, f"gear -> {w2!r}")
        self.close_windows()

    def dye_menu(self):
        """Tailor -> Dye pet; (window, dyes unlocked, rows)."""
        u, w = self.use_dyer()
        if w == "HWPDyerChoice":
            self.gl("press", "pet-btn")
            time.sleep(0.8)
            w = self.window()
        m = re.findall(r"\((\d+) dyes", self.widget("points").get("text", ""))
        return w, int(m[-1]) if m else -1, self.gl("presslist", "list").get("count", -1)

    def press_row(self, idx):
        """One row of the dye list: (gold paid, message). The menu is opened again when it
        closed under us (a console retype closes the open window)."""
        g0 = self.gold()
        r = self.gl("presslist", "list", idx)
        if not r.get("ok") and "no open window" in str(r.get("error")):
            self.dye_menu()
            r = self.gl("presslist", "list", idx)
        time.sleep(0.7)
        return g0 - self.gold(), self.widget("message").get("text", "") if r.get("ok") else f"presslist: {r.get('error')}"

    def dye_pet(self):
        """pets s10: the pet window lists the town's unlocked dyes in their colours at the
        quality's price; a pick pays and re-makes the pet in the dye."""
        self.hwp("set pets.debug true", 0.4)
        self.set_gold(100000)
        w0, n0, rows0 = self.dye_menu()
        self.close_windows()
        for bp in DYES:
            self.g.console("cht_add_blueprint " + bp)
            time.sleep(0.2)
        pet0 = self.pet()
        cur0, unit0 = self.petdye()
        w, n1, rows1 = self.dye_menu()
        self.flag("dye_menu_open", w == "HWPPetDyeMenu", f"{w0!r} then {w!r}, state {self.widget('state').get('text', '')!r}")
        self.flag("dye_lists_unlocked", n1 - n0 == len(DYES), f"{n0} -> {n1} unlocked, rows {rows0} -> {rows1}")
        on_page = min(max(n1, 0), 10)
        # rows: the section switch of a two-section pet, the remove row once dyed, the dyes,
        # then prev / next (PetDye.as HWPPetDyeMenu.Refresh)
        head = rows1 - on_page - (1 if n1 > 10 else 0)
        seen = {}
        for k in range(on_page):
            paid, msg = self.press_row(head + k if k == 0 else head + 1 + k)
            hexes = re.findall(r"\\c([0-9a-fA-F]{6})", msg)
            seen[dye_hex(hexes[-1].lower()) if hexes else f"?{k}"] = (paid, msg)
        self.close_windows()
        time.sleep(1)
        pet1 = self.pet()
        cur1, unit1 = self.petdye()
        want = {h: c for h, c in DYES.values()}
        self.flag("dye_in_colour", all(h in seen and "Dyed" in seen[h][1] for h in want),
                  "; ".join(f"{h}: {v[1]!r}" for h, v in seen.items()))
        self.flag("dye_price_paid", all(seen.get(h, (None,))[0] == c for h, c in want.items()),
                  ", ".join(f"{h} paid {v[0]}" for h, v in seen.items()))
        if n0 == 0:
            self.flag("dye_only_unlocked", set(seen) == set(want), f"listed {sorted(seen)}")
        else:
            self.notes.append(f"dye_only_unlocked: skipped, the town had {n0} dye(s) before")
        self.flag("dye_pet_remade", pet0.get("unit") != pet1.get("unit") and self.dyed(cur1, unit1),
                  f"pet {pet0.get('unit')} {unit0} ({cur0!r}) -> {pet1.get('unit')} {unit1} ({cur1!r})")

    def dye_floor(self):
        """pets s10: the dye is still on after a floor change (run from legacy_run's floor)."""
        self.hwp("set pets.debug true", 0.4)
        if self.gl("state").get("phase") != "mission":
            self.start_floor(0)
        cur0, unit0 = self.petdye()
        self.next_floor()
        time.sleep(3)
        cur1, unit1 = self.petdye()
        self.flag("dye_kept_floor", self.dyed(cur0, unit0) and self.dyed(cur1, unit1),
                  f"{cur0!r} {unit0} -> {cur1!r} {unit1}")

    def dye_restart(self):
        """pets s10: the dye is still on after quitting and loading the character."""
        self.hwp("set pets.debug true", 0.4)
        time.sleep(1)
        cur, unit = self.petdye()
        self.flag("dye_kept_restart", self.dyed(cur, unit), f"{cur!r} {unit}")

    def dye_remove(self):
        """pets s10: "Remove the dye" is free and gives the plain pet back. After the restart
        the tailor is set up again: npc_dyer only exists with the dyer's story flag
        (npc_dyer.unit), so a bare spawned one is "no usable unit"."""
        self.hwp("set pets.debug true", 0.4)
        self.tailor()
        self.set_gold(5000)
        cur0, unit0 = self.petdye()
        w, n, rows = self.dye_menu()
        # the remove row follows the section switch of a two-section pet
        two = ", " in cur0.split(": ", 1)[-1]
        paid, msg = self.press_row(1 if two else 0)
        self.close_windows()
        time.sleep(1)
        cur1, unit1 = self.petdye()
        self.flag("dye_remove_free", paid == 0 and "washes out" in msg, f"{w!r}, paid {paid}, {msg!r}")
        self.flag("dye_removed_plain", not self.dyed(cur1, unit1) and "/dye/" not in unit1,
                  f"{cur0!r} {unit0} -> {cur1!r} {unit1}")

    # --- pets s2/s4/s5: a fresh character's pet in a run
    def pets_setup(self):
        self.gl("char", "paladin", "LabPets")
        self.wait_phase("town", 60)
        time.sleep(2)
        self.petshop()
        self.hwp("set pets.debug true", 0.4)
        st = self.hwp("pet xp 20000", 0.8, until="level")
        self.flag("pets_ready", bool(self.pet()) and "point" in st, st.strip()[-160:])
        self.start_floor(0)
        self.gl("cull")
        # the floor's own spikes (the bandit keep has 9-15 round the start, 20261028-125555)
        # can make the start a trap room, where the pet waits instead of using its skills:
        # the skill checks run with room manners off, the room checks turn them on. (Not
        # unitdestroy: with the spikes gone, 160 of 161 pathfinds found no path, 125819.)
        self.hwp("set petwait.enabled false", 0.4)
        time.sleep(2)

    def spend(self, skill, n):
        out = ""
        for _ in range(n):
            out = self.hwp(f"pet skill {skill}", 0.4, until="level")
        return out.strip()[-120:]

    def pet_beside(self, near=60, wait=8):
        """The pet once it is within `near` px of the player: waited for, then the player is
        teleported beside it and it is waited for again."""
        for attempt in range(2):
            end = time.time() + wait
            pet = self.pet()
            while time.time() < end and not (pet and pet["dist"] < near):
                time.sleep(0.5)
                pet = self.pet()
            if (pet and pet["dist"] < near) or not pet or attempt:
                return pet
            self.gl("teleport", round(pet["x"]), round(pet["y"]))  # the pet stands on open ground
            time.sleep(1.5)
        return self.pet()

    def smash(self):
        """pets s4: a pot beside the pet stays whole without Smash and breaks once a point is in.
        The pet must be beside the player first (142551: 198 px off at the floor start). Smash
        breaks `value` breakables in its 110 px per tick, in the scene's order, not nearest
        first: 143104 started in a store room (188 breakables in 400 px) and the pet broke a
        barrel every 3 s ("smash rank 1: 1 target(s)") but not our pot. So the containers
        round the player go first."""
        pet = self.pet_beside()
        cl = self.gl("unitdestroy", 250, "doodads/containers/")
        time.sleep(0.5)
        pl = self.player()
        pet = self.pet() or pet
        # 24 px past the pet, on its far side from the player: a pot dropped on the player is
        # gone at once (145841, 150132: pet 24 / 17 px left of the player, +24 px in x put the
        # pot on the player and it never showed in `breakables`)
        ox, oy = pet.get("x", pl.get("x", 0)) - pl.get("x", 0), pet.get("y", pl.get("y", 0)) - pl.get("y", 0)
        od = math.hypot(ox, oy)
        ux, uy = (ox / od, oy / od) if od > 8 else (1.0, 0.0)
        dx, dy = round(ox + ux * 24), round(oy + uy * 24)
        v = self.gl("spawn", "doodads/containers/vase_small.unit", dx, dy)
        vx, vy = v.get("x", 0), v.get("y", 0)
        to_pet = math.hypot(vx - pet.get("x", vx), vy - pet.get("y", vy))

        def around():
            # breakables within Smash's reach of the pet's spot
            bs = self.gl("breakables", 300).get("breakables") or []
            return {b["unit"]: b["name"] for b in bs
                    if math.hypot(b["x"] - pet.get("x", 0), b["y"] - pet.get("y", 0)) <= 120}
        a0 = around()
        time.sleep(4)
        a1 = around()
        before = v.get("unit") in a1
        lost_ctrl = sorted(set(a0) - set(a1))
        mark = len(self.g.read_log())
        st = self.spend("smash", 1)
        rank = (re.findall(r"Smash (\d)", st) or ["?"])[-1]
        broke = False
        end = time.time() + 12
        while time.time() < end and not broke:
            time.sleep(0.5)
            broke = v.get("unit") not in around()
        fired = re.findall(r"smash rank \d+: (\d+) target", self.g.read_log()[mark:])
        others = sorted(n for u, n in a1.items() if u != v.get("unit") and u not in around())
        self.flag("smash_control", v.get("ok") and before and not lost_ctrl,
                  f"cleared {cl.get('count')} container(s); pot {v.get('unit')} at ({vx}, {vy}), {to_pet:.0f} px from the pet, "
                  f"whole after 4 s without Smash; {len(a1)} breakable(s) in reach, {len(lost_ctrl)} lost meanwhile")
        self.flag("smash_breaks_pots", before and broke,
                  f"Smash {rank}; pot {'broken' if broke else 'whole'} after {len(fired)} smash tick(s) {fired}; "
                  f"also broke {others}; pet {pet.get('dist')} px from the player")

    def hp_jumps(self, secs):
        """Heals of >= 7 % max hp from one 0.25 s sample to the next (Mend heals 4-10 %;
        regen is far slower), and the hp trace."""
        jumps, trace = [], []
        h0, mx = self.hp()
        end = time.time() + secs
        while time.time() < end:
            time.sleep(0.25)
            h1, mx = self.hp()
            if h1 - h0 >= 0.07 * mx:
                jumps.append(h1 - h0)
            trace.append(h1)
            h0 = h1
        return jumps, trace[::4], mx

    def mend(self):
        """pets s5: Mend heals the owner below 80 % hp and not above."""
        st = self.spend("mend", 5)
        self.set_hp(0.5)
        low, tl, mx = self.hp_jumps(10)
        self.set_hp(0.9)
        high, th, _ = self.hp_jumps(10)
        self.set_hp(1.0)
        self.flag("mend_heals_below_80", len(low) >= 1, f"{st}; at 50 %: heals {low}, hp {tl} / {mx}")
        self.flag("mend_idle_above_80", len(high) == 0, f"at 90 %: heals {high}, hp {th}")

    def stunned(self, filt, secs):
        """Whether an actor matching filt carries a stun-tagged buff within secs; its distances."""
        dists = []
        end = time.time() + secs
        while time.time() < end:
            for a in self.gl("actorbuffs", 400, filt).get("actors") or []:
                dists.append(round(a.get("dist", 0)))
                if any("stun" in b.get("tags", []) or "stun" in b.get("name", "") for b in a.get("buffs", [])):
                    return True, dists
            time.sleep(0.3)
        return False, dists

    def stun(self):
        """pets s5: Stun (rank 5, every 6 s) never takes an elite, and takes a goblin."""
        self.god(True)
        st = self.spend("stun", 5)
        self.clear()
        at = self.foe_at(60)
        mark = len(self.g.read_log())
        e = self.gl("spawn", "actors/humans/bandits/bandit_brute_elite.unit", *at)
        hit_e, de = self.stunned("bandit_brute_elite", 13)
        self.gl("kill", 600, "bandit_brute_elite")
        time.sleep(1)
        log_e = re.findall(r"stun rank \d+: \d+ target", self.g.read_log()[mark:])
        mark = len(self.g.read_log())
        gb = self.gl("spawn", "actors/beasts/goblins/goblin_redcap.unit", *at)
        hit_g, dg = self.stunned("goblin_redcap", 13)
        log_g = re.findall(r"\[HWP:pets\] (peer \d+ stun rank \d+: \d+ target)", self.g.read_log()[mark:])
        self.clear()
        near = sum(1 for d in de if d <= 160)
        self.flag("stun_skips_elite", e.get("ok") and not hit_e and near >= 10 and not log_e,
                  f"{st}; elite {e.get('name')} within 160 px in {near}/{len(de)} samples {de[:12]}, host log {log_e}")
        self.flag("stun_hits_goblin", gb.get("ok") and hit_g, f"{gb.get('name')} dists {dg[:12]}, host log {log_g[:2]}")

    def morale_state(self):
        """(buff on the player, its HUD icon shown, how): gl state's buff names; the icon from
        the buffs verb (ActorBuff.m_hudIcon visible), else any visible BuffWidget on the HUD
        (the floor is culled: no other buff is expected)."""
        on = ".hwp.pets.buff.morale" in (self.player().get("buffs") or [])
        b = self.gl("buffs")
        if b.get("ok"):
            mine = [x for x in b.get("buffs") or [] if x.get("name") == ".hwp.pets.buff.morale"]
            return on, any(x.get("icon") for x in mine), f"buffs {mine}"
        n = 0
        for root in self.gl("widgets", 6).get("roots", []):
            if str(root.get("root", "")).startswith("HUD"):
                n += sum(1 for x in root.get("nodes", []) if x.get("type") == "BuffWidget" and x.get("visible"))
        return on, n > 0, f"{n} visible BuffWidget(s) on the HUD"

    def foes(self):
        """Live actors within 350 px (Morale's combat radius), for the note."""
        return [(a.get("name", "").rsplit("/", 1)[-1], round(a.get("dist", 0)))
                for a in self.gl("actorbuffs", 350).get("actors") or []][:8]

    def morale_on(self):
        """pets s5: Morale out of combat: the buff and its icon."""
        self.clear()
        # a farming wild plot beside the player: an untargetable actor on another team, not a
        # foe (155331: one 213 px off kept Morale off)
        wp = self.gl("spawn", "doodads/hwp/wild/potato.unit", 70, 0)
        st = self.spend("morale", 5)
        time.sleep(3)
        on, icon, how = self.morale_state()
        self.flag("morale_out_of_combat", on, f"{st}; wild plot spawned {wp.get('ok')}; actors within 350: {self.foes()}")
        self.flag("morale_icon_shown", on and icon, how)

    def morale_combat(self):
        """pets s5: an enemy within 350 px: no Morale, no icon (the 2.6 s buff runs out)."""
        self.god(True)
        e = self.gl("spawn", "actors/humans/bandits/bandit_brute.unit", *self.foe_at(150))
        time.sleep(4)
        on, icon, how = self.morale_state()
        foes = [round(a.get("dist", 0)) for a in self.gl("actorbuffs", 400, "bandit_brute").get("actors") or []]
        self.flag("morale_gone_in_combat", e.get("ok") and foes and min(foes) <= 350 and not on and not icon,
                  f"enemy at {foes}; {how}")

    def morale_after(self):
        """pets s5: the enemy dead, Morale and its icon are back."""
        self.clear()
        time.sleep(3.5)
        on, icon, how = self.morale_state()
        self.flag("morale_back_after_combat", on and icon, f"{how}; actors within 350: {self.foes()}")
        self.god(False)

    def pet_samples(self, secs=2.0):
        """Pet positions over secs: (last pet, how far it moved from the first sample)."""
        first, last, moved = None, {}, 0.0
        end = time.time() + secs
        while time.time() < end:
            last = self.pet()
            if last:
                if first is None:
                    first = (last["x"], last["y"])
                moved = max(moved, math.hypot(last["x"] - first[0], last["y"] - first[1]))
            time.sleep(0.4)
        return last, moved

    def path_clear(self, x, y, fx, fy, most):
        """A path from (fx, fy) to (x, y) of at most `most` px (gl pathfind from a given
        point; nodes > 0: 0 is no path or a straight line)."""
        pf = self.gl("pathfind", round(x), round(y), 12, -1, -1, round(fx), round(fy))
        return bool(pf.get("ok")) and pf.get("nodes", 0) > 0 and pf.get("length", 1e9) <= most

    def floor_traps(self):
        """The floor's own traps round the player (petrooms counts them: the bandit keep's
        spike rooms, the campaign's glyphs), kept for the walks' checks (20261028-135632: the
        control walk and the walk-on each crossed a spike room of the floor's, and the pet
        rightly waited)."""
        # by unit file (gl unitsof): near's filter reads debug names, and a doodad's is empty
        # (20261028-140312: "near 1500 trap" found none)
        r = self.gl("unitsof", *FLOOR_TRAPS)
        pl = self.player()
        self.traps = [(u["x"], u["y"]) for f in FLOOR_TRAPS for u in (r.get(f) or {}).get("units") or []
                      if math.hypot(u["x"] - pl.get("x", 0), u["y"] - pl.get("y", 0)) < 1500]
        return self.traps

    def by_traps(self, ax, ay, bx, by, clear=150):
        """Whether the walk from a to b passes within `clear` px of one of the floor's traps,
        or of the test's own room while it stands (20261028-140025: a walk-on turned 135
        degrees ran back past the puzzle, and the pet waited again)."""
        for tx, ty in list(getattr(self, "traps", ())) + list(getattr(self, "rooms", ())):
            vx, vy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((tx - ax) * vx + (ty - ay) * vy) / max(1e-6, vx * vx + vy * vy)))
            if math.hypot(ax + t * vx - tx, ay + t * vy - ty) < clear:
                return True
        return False

    def walk_on(self, sx, sy, ux, uy, avoid=None):
        """A point 150 px from (sx, sy) along (ux, uy), or turned up to 135 degrees, on a
        near-straight path and 120 px or more from `avoid`, or None. (135: a pet parks at the
        last clear point of its owner's trail, by the start; 20261028-123250 had no walk-on
        within 90 degrees, and measured at the start the parked pet looked as near as a
        following one.)"""
        for turn in (0, 45, -45, 90, -90, 135, -135):
            c, s_ = math.cos(math.radians(turn)), math.sin(math.radians(turn))
            tx, ty = sx + 150 * (ux * c - uy * s_), sy + 150 * (ux * s_ + uy * c)
            if avoid and math.hypot(tx - avoid[0], ty - avoid[1]) < 120:
                continue
            if self.by_traps(sx, sy, tx, ty):
                continue
            if self.path_clear(tx, ty, sx, sy, 190):
                return round(tx), round(ty)
        return None

    def walk_in(self, x, y):
        """A walk the checks stand on (into the room, the control, back to the start, a
        walk-on): by path, else along the checked near-straight line (spikes block the pathfinder, 20261028-124224; the Pilot
        can fail a diagonal the pathfind passed, 130130, or report no_route on one, 133642),
        else teleported (131944: both failed out of a closed start room; 220 px is under the
        320 px trail jump, so the owner's trail runs on to it)."""
        r = self.p.path_to(x, y, tol=8, timeout=12)
        if not r.ok:
            r = self.p.move(x, y, tol=8, timeout=10)
        if not r.ok:
            self.gl("teleport", round(x), round(y))
            time.sleep(0.8)
            r = self.p.move(x, y, tol=12, timeout=3)
        return r

    def walk_away(self, sx, sy, spot, away):
        """A point 200-260 px from (sx, sy), on the `away` side (not back through the room:
        20261028-134937 walked on across the trap room, and the pet waited it out), 200 px or
        more from `spot`, with a path of at most 1.6 times that from (sx, sy), or None."""
        for r in (260, 200):
            for a in range(0, 360, 30):
                cx_, cy_ = math.cos(math.radians(a)), math.sin(math.radians(a))
                if cx_ * away[0] + cy_ * away[1] < 0.2:
                    continue
                tx, ty = sx + r * cx_, sy + r * cy_
                if math.hypot(tx - spot[0], ty - spot[1]) < 200 or self.by_traps(sx, sy, tx, ty):
                    continue
                if self.path_clear(tx, ty, sx, sy, r * 1.6):
                    return round(tx), round(ty)
        return None

    def puzzle_spot(self, budget=360):
        """(sx, sy, dx, dy, d, note): a start and a puzzle offset d (160-260 px) on a
        near-straight path, with room for the 150 px walk on beyond the start, away from the
        puzzle. Searched from where the player stands, then from points 300-700 px off it the
        pathfinder reaches (the floor generates differently each run: 141607 had no straight
        220 px path from its start); the player walks (or is teleported) to the start. At
        most `budget` pathfinds (about 0.05 s each)."""
        pl = self.player()
        ox, oy = pl.get("x", 0), pl.get("y", 0)
        self.floor_traps()

        def origins():
            # reached on foot first; then the rest, teleported to (20261028-130512: the start
            # room had no path out at all, 147 of 150 pathfinds)
            yield ox, oy
            far = []
            for r in (300, 500, 700):
                for a in range(0, 360, 45):
                    x, y = round(ox + r * math.cos(math.radians(a))), round(oy + r * math.sin(math.radians(a)))
                    pf = self.gl("pathfind", x, y)
                    if pf.get("ok") and pf.get("nodes", 0) > 0:
                        yield x, y
                    else:
                        far.append((x, y))
            yield from far

        used, n = 0, 0
        for sx, sy in origins():
            n += 1
            for d in (220, 190, 250, 170, 260, 160):
                for a in (0, 180, 90, 270, 45, 135, 225, 315):
                    if used >= budget:
                        return None
                    used += 1
                    dx, dy = round(d * math.cos(math.radians(a))), round(d * math.sin(math.radians(a)))
                    if self.by_traps(sx, sy, sx + dx, sy + dy):
                        continue
                    if not self.path_clear(sx + dx, sy + dy, sx, sy, d * 1.25):
                        continue
                    if self.walk_on(sx, sy, -dx / d, -dy / d) is None:
                        continue
                    note = f"start ({sx}, {sy}), origin {n}, {used} offset(s) tried, {len(self.traps)} floor trap(s) kept 150 px off"
                    if (sx, sy) != (ox, oy):
                        r = self.p.path_to(sx, sy, tol=8, timeout=20)
                        if not r.ok:
                            self.gl("teleport", sx, sy)
                            note += ", teleported"
                        else:
                            note += ", walked"
                        time.sleep(3)
                    return sx, sy, dx, dy, d, note
        return None

    def vanilla_setup(self):
        """A fresh character with a vanilla pet (no Pets package: the Pet Shop is the game's
        own, and petrooms drives the pet), then a run floor, in god mode (the trap rooms are
        real spikes)."""
        self.vanilla = True
        self.gl("char", "paladin", "LabPetRooms")
        self.wait_phase("town", 60)
        time.sleep(2)
        self.set_gold(60000)
        self.npc("npc_pets", "actors/npcs/town/npc_pets.unit")
        u = self.gl("use", "npc_pets")
        time.sleep(0.6)
        items = self.gl("shop").get("items") or []
        pick = next((i for i, it in enumerate(items) if it.get("gold", 0) > 0), None)
        if pick is not None:
            self.gl("shop", "buy", pick)
            time.sleep(1.5)
        self.close_windows()
        time.sleep(1)
        pet = self.pet()
        self.flag("vanilla_pet_out", bool(pet), f"{u.get('window')}, {len(items)} entries, bought "
                  f"{items[pick].get('title') if pick is not None else None}; pet {pet.get('name')}")
        self.start_floor(0)
        self.gl("cull")
        self.god(True)
        time.sleep(2)

    def place_traps(self, cx, cy):
        """Three pressure-plate spikes round (cx, cy) (gl spawn offsets are from the player)."""
        pl = self.player()
        ok = 0
        for ox, oy in ((0, 0), (14, 10), (-14, 10)):
            r = self.gl("spawn", TRAP_UNIT, round(cx + ox - pl.get("x", 0)), round(cy + oy - pl.get("y", 0)))
            ok += bool(r.get("ok"))
        return ok

    def puzzle_wait(self):
        """pets s2: the pet follows a walk; with a puzzle (vanilla lights-out) at the end of
        the same walk it stays outside, still, while the player is in, and follows again when
        the player comes out. querycmp says what each scene query sees of the buttons (PetWait
        fetches with FetchAllUnits: the buttons have no collision, QueryCircle misses them)."""
        self.room_wait("puzzle")

    def trap_wait(self):
        """petrooms: the same as puzzle_wait with a trap room (three pressure-plate spikes at
        the end of the walk) in place of the puzzle."""
        self.god(True)
        self.room_wait("trap")
        self.god(False)

    def room_wait(self, kind):
        self.hwp("set petwait.enabled true", 0.4)
        self.hwp("set petwait.debug true", 0.4)
        self.gl("cull")
        sp = self.puzzle_spot()
        if sp is None:
            self.flag("puzzle_spot", False, "no start with a straight 160-260 px path and room to walk on, "
                                            "from the floor start or 300-700 px round it")
            return
        sx, sy, dx, dy, d, where = sp
        self.notes.append(f"puzzle_spot: {where}, puzzle at +{dx},{dy} ({d} px)")
        # the walks run from the checked start itself, not from where the player stopped near
        # it (151101: 4 px off the start, and the walk from there had no route)
        self.p.path_to(sx, sy, tol=3, timeout=6)
        # control: the same walk with no puzzle. The pet must have caught up first (143629:
        # 321 px off after the walk, still trailing in from the skill sections); waited for
        # here, not teleported to, so the player stays on the start.
        end = time.time() + 12
        c0 = self.pet()
        while time.time() < end and not (c0 and c0["dist"] < FOLLOW_PX):
            time.sleep(0.5)
            c0 = self.pet()
        r = self.walk_in(sx + dx, sy + dy)
        time.sleep(2.5)
        c = self.pet()
        # (a vanilla pet trails lazily, within its 350 px leash: followed())
        self.flag("pet_follows_control", r.ok and bool(c) and c["dist"] < (350 if getattr(self, "vanilla", False) else FOLLOW_PX),
                  f"pet {c0.get('dist') if c0 else None} px off before, walk {r.result}, pet {c.get('dist')} px")
        # back to the start, which the room is placed from (20261028-141113: the walk back
        # failed and the puzzle went down 250 px off it)
        self.walk_in(sx, sy)
        time.sleep(2.5)
        if kind == "puzzle":
            pf = self.gl("prefab", PUZZLE_PFB, dx, dy)
        else:
            pl = self.player()
            pf = {"ok": self.place_traps(pl.get("x", 0) + dx, pl.get("y", 0) + dy) == 3}
        self.rooms = [(sx + dx, sy + dy)]
        time.sleep(1)
        r = self.walk_in(sx + dx, sy + dy)
        time.sleep(2.5)
        q = self.gl("querycmp", 140, PUZZLE_UNIT if kind == "puzzle" else TRAP_UNIT)
        p1, moved = self.pet_samples(2.0)
        # a step inside the room: the pet still does not move
        px, py = -dy / d * 30, dx / d * 30
        self.p.path_to(sx + dx + px, sy + dy + py, tol=6, timeout=6)
        time.sleep(1)
        p2, moved2 = self.pet_samples(1.6)
        # the step: where the pet is now against where it was parked before it (a follower
        # would have walked the 30 px before the samples start)
        shift = math.hypot(p2["x"] - p1["x"], p2["y"] - p1["y"]) if p1 and p2 else 1e9
        self.flag(f"pet_waits_outside_{kind}", pf.get("ok") and r.ok and bool(p1) and p1["dist"] > 90 and moved < 10
                  and moved2 < 10 and shift < 10,
                  f"{kind} {pf.get('ok')} at {dx},{dy}; walk {r.result}; pet {p1.get('dist')} px off, moved {moved:.0f} / {moved2:.0f} px, "
                  f"{shift:.0f} px over the step; "
                  f"querycmp {json.dumps({k: q.get(k) for k in ('querySensors', 'querySolid', 'fetchAll', 'fetchType', 'levelType', 'levelNearest', 'queryPuzzle', 'queryUnits')})}")
        # back out to the start: by path, else the walk-in in reverse in straight lines (the
        # step back, then the near-straight line; 143104 had no route out of the room), else
        # a teleport. Each still shows whether the pet closes in on the player.
        r = self.p.path_to(sx, sy, tol=8, timeout=12)
        how = f"path {r.result}"
        if not r.ok:
            self.p.move(sx + dx, sy + dy, tol=8, timeout=6)
            r = self.p.move(sx, sy, tol=8, timeout=10)
            how += f", straight back {r.result}"
        if not r.ok:
            t = self.gl("teleport", sx, sy)
            how += f", teleported {t.get('ok')}"
            r = None
        out_ok = r is None or r.ok
        time.sleep(3)
        # the pet parks by the start (run 20261018-140123: 15 px from it), so back at the start
        # a waiting pet can already look close: it must be with the player AND well off where
        # it waited. Where there is room, walk on 150 px away from the puzzle (or across) to a
        # point clear of the parking spot and measure there; else the walk-out stands
        # (142551: no walk-on target, the pet 83 px off its spot and 23 px from the player)
        p3, pl3 = self.pet(), self.player()
        r2 = None
        far = self.walk_on(sx, sy, -dx / d, -dy / d, (p1["x"], p1["y"]) if p1 else None)
        if not far and p1:
            # no straight walk-on clear of the spot (20261028-131401: a closed start room, the
            # pet parked 60 px from the start; 133241: "any walk-on" ended 74 px from the spot,
            # where an idling pet need not move): a routed walk 200 px or more off the spot
            far = self.walk_away(sx, sy, (p1["x"], p1["y"]), (-dx / d, -dy / d))
        if far:
            r2 = self.p.path_to(*far, tol=8, timeout=12)
            time.sleep(3.5)
            # a vanilla pet walks back at idle speed (20261028-131121: 59 px on from its spot,
            # 87 px off the player, at 3.5 s): given up to 10 s more
            end = time.time() + 10
            p3, pl3 = self.pet(), self.player()
            while time.time() < end and not self.followed(p3, pl3, p1):
                time.sleep(0.5)
                p3, pl3 = self.pet(), self.player()
        back = math.hypot(p3["x"] - p1["x"], p3["y"] - p1["y"]) if p1 and p3 else 0
        spot = math.hypot(pl3["x"] - p1["x"], pl3["y"] - p1["y"]) if p1 and pl3 else 0
        self.flag(f"pet_follows_after_{kind}", out_ok and self.followed(p3, pl3, p1),
                  f"out to ({sx}, {sy}): {how}; on to {far} {r2.result if r2 else '(no clear 150 px path: the walk-out measured)'}; "
                  f"player ({pl3.get('x')}, {pl3.get('y')}), pet ({p3.get('x')}, {p3.get('y')}) {p3.get('dist')} px off, "
                  f"{back:.0f} px from where it waited ({p1.get('x')}, {p1.get('y')}), the player {spot:.0f} px from it")
        # the Morale checks run on this floor next: take the room away so a wait that never
        # clears shows up here (pet_follows_after_<kind>), not as a missing buff
        self.gl("unitdestroy", 500, "button_magic" if kind == "puzzle" else "floor_spikes_pressure")
        self.rooms = []
        self.hwp("set petwait.enabled false", 0.4)

    def followed(self, pet, pl, spot):
        """The pet follows again after a wait at `spot`: it is off the spot (a held pet moves
        0 px; 30 px or more) and with the player. The base pet idles within 100 px of its
        owner (20261028-132900: back 83 px off, 54 px from its spot), so a following pet need
        not close in further. A vanilla pet follows lazily: past that it ambles to a spot by
        its owner at idle speed and only hurries past the 350 px leash (20261028-131629: the
        control walk, no room anywhere, left it 133 px behind), so for it within the leash is
        with the player. (A walk-on that stops short still counts, 155331.)"""
        if not pet or not spot:
            return False
        back = math.hypot(pet["x"] - spot["x"], pet["y"] - spot["y"])
        near = 350 if getattr(self, "vanilla", False) else FOLLOW_PX
        return back >= 30 and pet["dist"] < near

    def trap_leave(self):
        """petrooms: a pet in a trap room while its owner is outside walks out along the owner's
        trail and waits until the owner moves on. With petwait.radius 60, spikes 20 px past
        the pet (on its far side from the player, 90 px off) make the pet's spot a room and
        not the player's; out of it is 50 px or more from them (one spike within 60 px is
        not a room)."""
        self.hwp("set petwait.enabled true", 0.4)
        self.gl("cull")
        self.god(True)
        self.hwp("set petwait.radius 60", 0.4)
        pet = self.pet_beside(60)
        pl = self.player()
        if not pet:
            self.flag("pet_leaves_trap_room", False, "no pet")
            return
        # the player steps off to 90 px from the pet along the line between them: the step is
        # the trail the pet walks out on. A pet idles round its owner (a vanilla one picks a
        # new idle spot now and then: 20261028-122737 had walked up to 47 px of the player
        # when the spikes went down), so the line is read again right before the spikes, 15 px
        # past the pet, and the step is taken again while the player is under 70 px off it.
        self.hwp("set petwait.debug true", 0.4)
        # the pet must be in the room the spikes make: it can pick a new idle spot meanwhile
        # (20261028-134537: the spikes went down 131 px from it, no "pet in a room" logged), so
        # the log is read for petrooms' own word (petwait.debug), else the spikes go and the
        # line-up starts over
        r, ux, uy, placed, entered, tries = None, 1.0, 0.0, 0, False, 0
        while tries < 3 and not entered:
            tries += 1
            r = None
            for _ in range(3):
                pet, pl = self.pet(), self.player()
                ux, uy = pl["x"] - pet["x"], pl["y"] - pet["y"]
                n = math.hypot(ux, uy)
                ux, uy = (ux / n, uy / n) if n > 1 else (1.0, 0.0)
                if n >= 70:
                    break
                r = self.p.move(pet["x"] + ux * 90, pet["y"] + uy * 90, tol=6, timeout=6)
                time.sleep(0.8)
            else:
                # three steps that did not take (20261028-131121: the spikes went down 16 px from
                # the player): teleported the 90 px, a trail point like any other, turned off a
                # wall if need be (132436: still 29 px off), and the line read again
                for turn in (0, 45, -45, 90, -90, 135, -135, 180):
                    pet, pl = self.pet(), self.player()
                    if math.hypot(pl["x"] - pet["x"], pl["y"] - pet["y"]) >= 70:
                        break
                    c, s_ = math.cos(math.radians(turn)), math.sin(math.radians(turn))
                    self.gl("teleport", round(pet["x"] + 90 * (ux * c - uy * s_)), round(pet["y"] + 90 * (ux * s_ + uy * c)))
                    time.sleep(0.8)
                pet, pl = self.pet(), self.player()
                ux, uy = pl["x"] - pet["x"], pl["y"] - pet["y"]
                n = math.hypot(ux, uy)
                ux, uy = (ux / n, uy / n) if n > 1 else (1.0, 0.0)
            cx, cy = pet["x"] - ux * 15, pet["y"] - uy * 15
            mark = len(self.g.read_log())
            placed = self.place_traps(cx, cy)
            end = time.time() + 2
            while time.time() < end and not entered:
                time.sleep(0.25)
                entered = "[HWP:petrooms] pet in a room" in self.g.read_log()[mark:]
            if not entered:
                self.gl("unitdestroy", 500, "floor_spikes_pressure")
                time.sleep(0.5)
        # the way out is the owner's trail, which can be longer than the straight line
        # (20261028-122518: still walking 3.5 s on): let it settle, then it must stay put
        t0 = time.time()
        time.sleep(1.5)
        for _ in range(6):
            _, walking = self.pet_samples(1.6)
            if walking < 6:
                break
        settled = time.time() - t0
        p1, moved = self.pet_samples(2.0)
        pl1 = self.player()
        off = math.hypot(p1["x"] - cx, p1["y"] - cy) if p1 else 0
        own = math.hypot(pl1["x"] - cx, pl1["y"] - cy)
        self.flag("pet_leaves_trap_room", entered and placed == 3 and bool(p1) and off > 50 and moved < 10 and own > 60,
                  f"try {tries}, pet in the room {entered}; step {r.result if r else 'not needed'}; {placed} spikes at ({cx:.0f}, {cy:.0f}), {own:.0f} px from the player; "
                  f"pet settled after {settled:.1f} s {off:.0f} px from them and {p1.get('dist')} px from the player, "
                  f"then moved {moved:.0f} px while the player stood")
        far = self.walk_on(pl1["x"], pl1["y"], ux, uy, (cx, cy))
        r2 = self.walk_in(*(far or (pl1["x"] + ux * 150, pl1["y"] + uy * 150)))
        # a vanilla pet past its idle range walks to idle spots by its owner at idle speed:
        # given up to 10 s
        end, p2 = time.time() + 10, self.pet()
        while time.time() < end and not (p2 and p2["dist"] < FOLLOW_PX):
            time.sleep(0.5)
            p2 = self.pet()
        self.flag("pet_follows_after_leaving", bool(p2) and p2["dist"] < FOLLOW_PX,
                  f"walk on to {far} {r2.result}; pet {p2.get('dist')} px off after {10 - max(0, end - time.time()):.1f} s")
        self.gl("unitdestroy", 500, "floor_spikes_pressure")
        self.hwp("set petwait.radius 120", 0.4)
        self.hwp("set petwait.enabled false", 0.4)
        self.god(False)


def run(p, sections="", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
