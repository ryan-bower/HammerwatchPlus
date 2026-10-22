"""Test-plan checks for the 4th specializations (mods/specs).

Each section makes a fresh level-20 character of the base class (`gl char`, `hwp levelup 20`),
takes the spec with `gl subclass`, learns its two skills with `gl skill` and equips orbs with
`gl orb`, then casts in an emptied Bandit Keep floor with god mode on. The verbs are core
gamelab plus mods/gamelab-hands/scripts/GameLab/Verbs_specs.as: hasbuff (a buff by its path,
for the buffs that have no display name), evade (Player.Evade's real roll and triggers),
bind (a skill's live bind, to see the orbs took), dmgmuls (the damage multipliers), buffnear
(a buff on enemies) and damageme (a real hit on the local player, god mode off).

Sections: winddancer, bannerlord, invocation, stormbringer, branding, arcane. Single player: what only shows on a teammate (Shared Breath,
the standard's ally numbers) is checked as far as the bearer's own client goes."""
import re
import time

from gamelab.bots.plan_classesb import Checks as Base

BUFFS = "players/hwp/specs/buffs_specs.sval:"
STATUS = "tweak/buffs/status_effects.sval:"
DUMMY = "actors/humans/bandits/bandit_brute.unit"
# 500 hp, stands still, never blocks: for projectiles (a brute's SkillBlock stops arrows)
TARGET = "doodads/generic/target_dummy_breakable.unit"


class Checks(Base):
    def has(self, *names):
        """{name: hasbuff entry} for buffs_specs.sval names (or full paths)."""
        paths = [n if ":" in n else BUFFS + n for n in names]
        r = self.gl("hasbuff", *paths)
        return {n: b for n, b in zip(names, r.get("buffs") or [])}

    def wait_buff(self, name, timeout=3.0):
        end = time.time() + timeout
        while time.time() < end:
            b = self.has(name)[name]
            if b.get("on"):
                return b
            time.sleep(0.15)
        return self.has(name)[name]

    def bind(self, skill, name):
        return self.gl("bind", skill, name).get("value")

    def specs(self):
        return self.hwp("specs", 0.5, until="specs:")

    def setup(self, key, cls, sub, skills, orbs=()):
        r, pl, lv = self.new_char(cls, "Lab" + key.capitalize())
        time.sleep(0.5)
        pl = self.gl("state").get("player", {})
        self.flag(f"{key}_char", r.get("ok") and pl.get("class") == cls and pl.get("level", 0) >= 20,
                  f"{r} class {pl.get('class')} level {pl.get('level')}; levelup said {lv.strip()[-80:]!r}")
        took = self.gl("subclass", sub).get("class")
        self.hwp("skillpoints 40")
        # the spec's skills start at level 1 (starting-level): one SkillUp makes them 2
        lv = {s: self.gl("skill", s, 1).get("level", 0) for s in skills}
        self.lvl = lv
        self.flag(f"{key}_learned", took == sub and all(v >= 1 for v in lv.values()), f"subclass {took}, levels {lv}")
        for orb, n in orbs:
            self.gl("orb", orb, n)

    def set_stacks(self, path, n):
        """The local player's count of a stack, through givestacks (it adds): all off, then n."""
        self.gl("givestacks", path, -999)
        return self.gl("givestacks", path, n) if n > 0 else {}

    def status_num(self, label):
        """A number from `hwp specs` ("...; <label> N"), None when it isn't there."""
        m = re.findall(re.escape(label) + r" (-?\d+)", self.specs())
        return int(m[-1]) if m else None

    def open_dir(self, need=230):
        """A unit direction from the player with no wall for `need` px (rayhit, 8 tries), the
        clearest one when none is; for the skills that turn at walls."""
        import math
        x, y = self.pos()
        best = (-1.0, (1.0, 0.0))
        for k in range(8):
            d = (round(math.cos(k * math.pi / 4), 3), round(math.sin(k * math.pi / 4), 3))
            r = self.gl("rayhit", round(x, 1), round(y, 1), round(x + d[0] * need, 1), round(y + d[1] * need, 1))
            free = need if not r.get("wall") else float(r.get("wd", 0.0))
            if free >= need:
                return d
            best = max(best, (free, d))
        return best[1]

    def cast_skill(self, tag, skill, cost, done=None, fallback="skill3", aim=(1, 0)):
        button = self.button_for(tag, skill, fallback)
        presses, spent = self.cast(skill, button, cost, done=done, aim=aim)
        return presses, spent, button

    # --- Winddancer
    def winddancer(self):
        pg, sw = "hwp_rog_protective_gale", "hwp_rog_second_wind"
        self.setup("wind", "rogue", "hwp_rogue_winddancer", [pg, sw])
        if not self.enter_floor("wind"):
            return
        state = {}
        lvl = max(1, min(5, self.lvl[pg]))
        gale = f"gale_{lvl}"
        heal = (20, 30, 40, 50, 60)[max(1, min(5, self.lvl[sw])) - 1]

        def gale_on():
            b = self.has(gale)[gale]
            state["gale"] = b
            return bool(b.get("on"))

        presses, spent, button = self.cast_skill("wind_pg", pg, 40, done=gale_on)
        self.g.shot("wind gale", settle=False)
        g = state.get("gale", {})
        self.flag("wind_pg_cast", bool(g.get("on")), f"{pg} on {button}: {presses} press(es), mana -{spent}; {g}")
        self.flag("wind_pg_buff", g.get("on") and g.get("hud") and 4500 <= (g.get("left") or 0) <= 6000,
                  f"{gale} {g} (level {lvl}: 6000 ms, HUD icon)")

        # Second Wind: an evade heals 20 (level 1), then nothing for 4 s
        self.gl("hurt", 0.4)
        time.sleep(0.2)
        e = self.gl("evade", 80)
        self.g.shot("wind gust", settle=False)
        time.sleep(0.6)
        hp1 = self.gl("state").get("player", {}).get("hp")
        self.flag("wind_evade_chance", (e.get("chance") or 0) >= 0.14,
                  f"chance {e.get('chance')} with {gale} and the rogue's own (1.0 while Sidestep is up)")
        self.flag("wind_sw_heal", e.get("evaded") and abs(e.get("hp", 0) - e.get("hp0", 0) - heal) <= 2,
                  f"evade {e} (hp0 -> hp: the heal, {heal} at level {self.lvl[sw]}, lands in the evade's frame); "
                  f"hp {hp1} 0.6 s later")
        self.gl("hurt", 0.4)
        time.sleep(0.2)
        e2 = self.gl("evade", 80)
        time.sleep(0.6)
        hp2 = self.gl("state").get("player", {}).get("hp")
        self.flag("wind_sw_timeout", e2.get("evaded") and e2.get("hp", 0) - e2.get("hp0", 0) < 5,
                  f"second evade within 4 s {e2}; hp {hp2} 0.6 s later (regen only)")

        # orbs: Lasting Gale 3 (12 s), Tailwind 1, Lingering Breeze 2, Shared Breath
        for orb, n in (("hwp_rog_pg_lasting_gale", 3), ("hwp_rog_pg_tailwind", 1),
                       ("hwp_rog_sw_lingering_breeze", 2), ("hwp_rog_sw_shared_breath", 1)):
            self.gl("orb", orb, n)
        time.sleep(0.5)
        binds = {"pg-ttl": self.bind(pg, "pg-ttl"), "pg-tail": self.bind(pg, "pg-tail"),
                 "sw-breeze": self.bind(sw, "sw-breeze"), "sw-share": self.bind(sw, "sw-share")}
        self.flag("wind_orb_binds", binds["pg-ttl"] == "12000" and str(binds["pg-tail"]).endswith("gale_tailwind_1")
                  and str(binds["sw-breeze"]).endswith("breeze_2") and binds["sw-share"] not in (None, "", "0"),
                  f"{binds}")
        # the gale's cooldown (20 s) from the first cast
        end = time.time() + 22
        while time.time() < end and (self.skill_cd(pg) or 0) > 0:
            time.sleep(0.5)
        state.clear()
        presses, spent, button = self.cast_skill("wind_pg2", pg, 40, done=gale_on)
        b = self.has(gale, "gale_tailwind_1")
        self.flag("wind_lasting_gale", (b[gale].get("left") or 0) > 9000,
                  f"recast {presses} press(es): {gale} {b[gale]} (12 s with Lasting Gale 3)")
        self.flag("wind_tailwind", bool(b["gale_tailwind_1"].get("on")), f"gale_tailwind_1 {b['gale_tailwind_1']}")
        time.sleep(3.5)  # past the first gusts' 4 s timeout
        self.gl("hurt", 0.4)
        e3 = self.gl("evade", 80)
        br = self.wait_buff("breeze_2", 1.5)
        self.flag("wind_lingering_breeze", e3.get("evaded") and br.get("on") and br.get("hud"),
                  f"evade {e3}; breeze_2 {br}")
        # Shared Breath: the bearer never gets the share buff (the teammates do, on their client)
        share = f"gale_share_{heal}_2"
        sh = self.has(share)[share]
        self.flag("wind_share_not_self", sh.get("def") and not sh.get("on"), f"{share} on the rogue: {sh}")
        self.to_town()

    # --- Bannerlord
    def bannerlord(self):
        bs, rc = "hwp_war_battlefield_standard", "hwp_war_righteous_crusade"
        self.setup("banner", "warrior", "hwp_warrior_bannerlord", [bs, rc],
                   orbs=(("hwp_war_bs_feared_crest", 1), ("hwp_war_rc_war_drum", 1),
                         ("hwp_war_rc_shared_provisions", 1)))
        if not self.enter_floor("banner"):
            return
        self.gl("spawn", DUMMY, 40, 0)
        time.sleep(0.8)
        state = {}

        def dr_on():
            b = self.has("standard_dr")["standard_dr"]
            state["dr"] = b
            return bool(b.get("on"))

        m0 = self.mana_exact()
        presses, spent, button = self.cast_skill("banner_raise", bs, 40, done=dr_on)
        self.g.shot("banner raised", settle=False)
        st = self.specs()
        self.flag("banner_raise", bool(state.get("dr", {}).get("on")) and "carried" in st,
                  f"{bs} on {button}: {presses} press(es), mana -{spent}; standard_dr {state.get('dr')}; {st.strip()[-160:]}")
        dr = state.get("dr", {})
        want = 0.02 * max(1, min(5, self.lvl[bs]))
        self.flag("banner_dr_intensity", abs((dr.get("intensity") or 0) - want) < 0.005,
                  f"standard_dr {dr} ({want:.0%} at level {self.lvl[bs]})")
        ab = self.gl("actorbuffs", 150, "bandit_brute")
        # status effects have no display name: their tags tell them apart
        tags = [(b.get("tags"), b.get("left")) for a in ab.get("actors") or [] for b in a.get("buffs") or []]
        self.flag("banner_feared_crest", any("vulnerability" in (t or []) for t, _ in tags),
                  f"dummy buffs (tags, ms left) {tags}: an area Vulnerability (500 ms, renewed every 250)")
        self.flag("banner_war_drum", any("weakness" in (t or []) and 0 < (left or 0) <= 4000 for t, left in tags),
                  f"dummy buffs {tags}: weakness_minor (4 s)")
        time.sleep(1.2)
        st = self.specs()
        prov = re.search(r"provisions (-?\d+)", st)
        self.flag("banner_provisions", prov is not None and int(prov.group(1)) >= 1,
                  f"{st.strip()[-160:]} (1% per buff with a HUD icon: standard_dr at least)")

        # plant: free, during the cooldown, doubled
        m1 = self.mana_exact()
        state.clear()

        def planted_on():
            b = self.has("standard_dr_planted")["standard_dr_planted"]
            state["pl"] = b
            return bool(b.get("on"))

        self.press(button)
        time.sleep(0.8)
        self.g.shot("banner planted", settle=False)
        planted_on()
        st = self.specs()
        pl = state.get("pl", {})
        self.flag("banner_plant", bool(pl.get("on")) and "planted" in st,
                  f"standard_dr_planted {pl}; {st.strip()[-160:]}")
        m2 = self.mana_exact()
        self.flag("banner_plant_free", m2 >= m1 - 2, f"mana {m1} -> {m2} (regen only; the raise cost {m0 - m1:.1f})")
        self.flag("banner_plant_doubled", abs((pl.get("intensity") or 0) - 2 * want) < 0.005, f"{pl} ({2 * want:.0%} planted)")
        self.to_town()


    # --- Stormbringer
    def stormbringer(self):
        ec, gw = "hwp_ran_electric_circuit", "hwp_ran_gathering_winds"
        self.setup("storm", "ranger", "hwp_ranger_stormbringer", [ec, gw])
        if not self.enter_floor("storm"):
            return
        # one target on the line of fire, one beside it out of the 30 degree fan, in strike range,
        # the way the floor leaves open: the arrows turn at a wall
        fx, fy = self.open_dir()
        self.gl("spawn", TARGET, round(45 * fx, 1), round(45 * fy, 1))
        self.gl("spawn", TARGET, round(45 * fx - 40 * fy, 1), round(45 * fy + 40 * fx, 1))
        time.sleep(1.0)
        hp0 = self.dummy_hp("target_dummy")
        r0 = self.status_num("circuit returns") or 0
        b0 = self.status_num("back hits") or 0
        # a press aimed right (castat's direction does not reach the fan: it shoots on the aim)
        presses, spent, button = self.cast_skill("storm_ec", ec, 40, aim=(fx, fy))
        time.sleep(0.1)  # the press waited 0.6 s: the way out is done, the arrows turn at 0.8 s
        hp1 = self.dummy_hp("target_dummy")
        self.g.shot("storm circuit", settle=False)
        time.sleep(1.6)  # turned at 600 ms, back past the dummy
        hp2 = self.dummy_hp("target_dummy")
        r1 = self.status_num("circuit returns")
        b1 = self.status_num("back hits")
        lower = lambda a, b: a < b - 0.001
        self.flag("storm_ec_cast", presses > 0, f"{ec} on {button}: {presses} press(es), mana -{spent}")
        self.flag("storm_ec_hits", len(hp0) == 2 and all(lower(hp2.get(u, 0.0), hp0[u]) for u in hp0),
                  f"dummies {hp0} -> out {hp1} -> back {hp2} (the side one: lightning strikes only)")
        self.flag("storm_ec_return", r1 is not None and r1 - r0 >= 3 and b1 is not None and b1 - b0 >= 1,
                  f"aim {fx, fy}: returns {r0} -> {r1} (3 arrows), hits on the way back {b0} -> {b1}; hp after the way out {hp1}, "
                  f"after the way back {hp2}")

        for orb, n in (("hwp_ran_ec_charged_boomerang", 2), ("hwp_ran_ec_lightning_rod", 3), ("hwp_ran_ec_tailwind_catch", 1),
                       ("hwp_ran_gw_gale_force", 2), ("hwp_ran_gw_wind_ward", 2)):
            self.gl("orb", orb, n)
        time.sleep(0.5)
        binds = {k: self.bind(s_, k) for s_, k in ((ec, "ec-return-mul"), (ec, "ec-lone"), (ec, "ec-strikes"), (ec, "ec-radius"),
                                                    (ec, "ec-catch"), (gw, "gw-gale"), (gw, "gw-ward"), (gw, "gw-lvl"))}
        lvl = max(1, min(5, self.lvl[gw]))
        self.flag("storm_orb_binds", binds == {"ec-return-mul": "1.4", "ec-lone": "1", "ec-strikes": "5", "ec-radius": "84",
                                               "ec-catch": "1", "gw-gale": "2", "gw-ward": "0.03", "gw-lvl": str(lvl)}, f"{binds}")

        # Gathering Winds: every 5 kills of the ranger's give a stack (kill ... me: the ranger is the killer)
        tw = "players/hwp/specs/stacks_specs.sval:tailwind"
        self.gl("kill", 600, "target_dummy")
        time.sleep(0.5)
        self.set_stacks(tw, 0)
        time.sleep(0.3)

        def kills(n):
            for _ in range(n):
                self.gl("spawn", DUMMY, -60, 0)
            time.sleep(0.6)
            self.gl("kill", 400, "bandit_brute", "me")
            time.sleep(0.4)

        k0 = self.status_num("tailwind kills") or 0
        short = 5 - k0 % 5
        if short > 1:
            kills(short - 1)
        n0 = self.status_num("tailwind")
        kills(1)
        n1 = self.status_num("tailwind")
        k1 = self.status_num("tailwind kills")
        self.flag("storm_gw_stack", n0 == 0 and n1 == 1 and k1 == k0 + short,
                  f"kills {k0} -> {k1}: tailwind {n0} after {short - 1}, {n1} after {short}")
        # each stack ends 4 s after its own kill
        time.sleep(2.0)
        kills(5)
        time.sleep(2.4)  # the first stack's 4 s are over, the second's are not
        n2 = self.status_num("tailwind")
        time.sleep(2.2)
        n3 = self.status_num("tailwind")
        self.flag("storm_gw_expiry", n2 == 1 and n3 == 0, f"two stacks 2 s apart: {n2} at 4.4 s, {n3} at 6.6 s")
        kills(35)
        ncap = self.status_num("tailwind")
        sp = self.wait_buff(f"tailwind_{lvl}_5", 1.5)
        self.flag("storm_gw_cap", ncap == 5 and bool(sp.get("on")), f"35 kills: tailwind {ncap} (cap 5); tailwind_{lvl}_5 {sp}")
        # the stacks last 4 s: a fresh 5 for each of the next two checks
        self.set_stacks(tw, 5)
        ww = self.wait_buff("wind_ward", 1.5)
        want = round(0.03 * 5, 3)
        self.flag("storm_wind_ward", bool(ww.get("on")) and abs(float(ww.get("intensity", 0)) - want) < 0.001,
                  f"wind_ward {ww} (want intensity {want}: 3% x 5)")
        self.set_stacks(tw, 0)
        self.set_stacks(tw, 5)
        time.sleep(0.3)
        sec = "attack_2h_shortbow_secondary"
        g0 = self.status_num("gale arrows") or 0
        self.gl("castat", sec, 1, 0, "nocd")
        time.sleep(0.5)
        g1 = self.status_num("gale arrows")
        self.flag("storm_gale_force", g1 is not None and g1 - g0 == 2, f"at the cap a secondary: gale arrows {g0} -> {g1} (+2)")

        # Tailwind Catch: the arrows come back to the ranger standing still
        self.set_stacks(tw, 0)
        c0 = self.status_num("catches") or 0
        end = time.time() + 8
        while time.time() < end and (self.skill_cd(ec) or 0) > 0:
            time.sleep(0.5)
        self.cast_skill("storm_ec2", ec, 40, aim=(fx, fy))
        time.sleep(2.0)
        # one status line: the stacks last 4 s, so two reads a second apart can straddle the end
        st = self.specs()
        num = lambda label: (lambda m: int(m[-1]) if m else None)(re.findall(re.escape(label) + r" (-?\d+)", st))
        c1, n = num("catches"), num("tailwind")
        self.flag("storm_catch", c1 is not None and c1 - c0 >= 1 and (n or 0) >= 1,
                  f"catches {c0} -> {c1}, tailwind {n}")
        self.to_town()

    # --- Invocation
    def dummy_hp(self, name="bandit_brute"):
        """{unit id: hp fraction, 0 when dead} of the dummies around (near's name filter)."""
        return {u["unit"]: (0.0 if u.get("dead") else u.get("hp", 1.0))
                for u in self.gl("near", 400, name).get("units") or []}

    def invocation(self):
        tt, sc = "hwp_wiz_tempest_torrent", "hwp_wiz_static_charge"
        self.setup("inv", "wizard", "hwp_wizard_invocation", [tt, sc])
        if not self.enter_floor("inv"):
            return
        for dy in (-25, 0, 25):
            self.gl("spawn", DUMMY, 70, dy)
        time.sleep(1.0)
        hp0 = self.dummy_hp()
        mark = len(self.g.read_log())
        presses, spent, button = self.cast_skill("inv_tt", tt, 40)
        self.g.shot("inv torrent", settle=False)
        time.sleep(3.0)
        hp1 = self.dummy_hp()
        hit = [u for u, h in hp0.items() if hp1.get(u, 0.0) < h - 0.001]
        self.flag("inv_tt_cast", presses > 0, f"{tt} on {button}: {presses} press(es), mana -{spent}")
        self.flag("inv_tt_spread", len(hp0) == 3 and len(hit) == 3,
                  f"dummies hp before {hp0}, after {hp1}: {len(hit)} of {len(hp0)} zapped")

        for orb, n in (("hwp_wiz_tt_overcharge", 2), ("hwp_wiz_tt_lingering_storm", 2), ("hwp_wiz_tt_thunderclap", 1),
                       ("hwp_wiz_tt_lightning_rod", 3), ("hwp_wiz_sc_static_channel", 2), ("hwp_wiz_sc_conduit", 2)):
            self.gl("orb", orb, n)
        time.sleep(0.5)
        binds = {k: self.bind(s_, k) for s_, k in ((tt, "tt-overcharge"), (tt, "tt-ttl-add"), (tt, "tt-clap"), (tt, "tt-zaps"),
                                                    (tt, "tt-radius"), (sc, "sc-channel"), (sc, "sc-conduit-lvl"))}
        self.flag("inv_orb_binds", binds == {"tt-overcharge": "0.07", "tt-ttl-add": "2000", "tt-clap": "1.5", "tt-zaps": "5",
                                             "tt-radius": "95", "sc-channel": "0.2", "sc-conduit-lvl": "2"}, f"{binds}")

        # Static Charge: every spell cast adds a stack (no enemy left to crit on), 10 s, reset by each new one
        path = "players/hwp/specs/stacks_specs.sval:static_charge"
        self.gl("kill", 600, "bandit_brute")
        time.sleep(1.0)
        self.set_stacks(path, 0)
        mm = "wiz_magic_missiles"
        self.gl("castat", mm, -1, 0, "nocd")
        time.sleep(0.5)
        c1 = self.status_num("static charge")
        self.gl("castat", mm, -1, 0, "nocd")
        time.sleep(0.5)
        c2 = self.status_num("static charge")
        self.flag("inv_sc_cast", c1 == 1 and c2 == 2, f"two {mm} casts with no enemy: static charge {c1}, {c2}")
        time.sleep(7.0)
        self.gl("castat", mm, -1, 0, "nocd")
        time.sleep(4.0)  # 11.5 s after the second cast, 4 s after the third: the reset kept them
        c3 = self.status_num("static charge")
        time.sleep(6.5)
        c4 = self.status_num("static charge")
        self.flag("inv_sc_timer", c3 == 3 and c4 == 0, f"a third cast 7.5 s later: {c3} 4 s after it, {c4} 10.5 s after it")

        self.set_stacks(path, 3)
        cb = self.wait_buff("conduit_2_3", 1.5)
        self.flag("inv_conduit", bool(cb.get("on")), f"3 charges, Conduit 2: conduit_2_3 {cb} (+24% cast speed)")

        # a release on the next cast: 5 charges, the torrent's cooldown over
        self.set_stacks(path, 5)
        end = time.time() + 14
        while time.time() < end and (self.skill_cd(tt) or 0) > 0:
            time.sleep(0.5)
        self.gl("kill", 600, "bandit_brute")
        for dy in (-25, 0, 25):
            self.gl("spawn", DUMMY, 70, dy)
        time.sleep(1.0)
        hp0 = self.dummy_hp()
        mark = len(self.g.read_log())
        maxm = self.gl("mana", 100).get("max", 0)
        presses, spent, button = self.cast_skill("inv_tt2", tt, 40)
        time.sleep(0.6)
        m1 = self.mana_exact()
        log = self.g.read_log()[mark:]
        st = self.specs()
        # the release cast adds none; the torrent's own zaps can crit once: 0 or 1 after the release
        left = re.findall(r"static charge (\d+)", st)
        self.flag("inv_release", "static charge: released" in log and bool(left) and int(left[-1]) < 2,
                  f"log {[l for l in log.splitlines() if 'static charge' in l][-2:]}; {st.strip()[-120:]}")
        # from 100: the torrent's cost (50 at level 2), then 20% of max back, plus some regen
        want = 100 - 50 + 0.2 * maxm
        self.flag("inv_static_channel", "20% mana" in log and want - 3 <= m1 <= want + 25,
                  f"mana 100 -> {m1} (max {maxm}: want about {want:.0f}, regen on top)")
        time.sleep(5.5)  # 3 s + Lingering Storm 2 s, then Thunderclap
        hp2 = self.dummy_hp()
        self.flag("inv_tt_orbs", all(hp2.get(u, 0.0) < h - 0.001 for u, h in hp0.items()) and len(hp0) == 3,
                  f"dummies {hp0} -> {hp2} after the release and a 5 s torrent")
        self.to_town()

    # --- Branding
    def brand_cast(self, pb, dx, dy, nocd=True):
        """Pyrebrand through castat, mana topped up first (nocd: the cooldown is not what is under
        test). The brand goes to the enemy on the player's aim, not castat's direction, and the
        emulated aim lets go when its hold ends: the cast lands inside a hold. Returns (activated,
        the pyrebrand log lines it wrote)."""
        self.gl("mana", 250)
        self.gl("input", 700, 0, 0, dx, dy)
        time.sleep(0.1)
        mark = len(self.g.read_log())
        r = self.gl("castat", pb, dx, dy, *(["nocd"] if nocd else []))
        time.sleep(0.6)
        return bool(r.get("activated")), "\n".join(l for l in self.g.read_log()[mark:].splitlines() if "pyrebrand" in l)

    def tails(self, n, dx, dy, gap=0.4):
        """n Demon's Tails (the warlock's melee-tagged spell) along (dx, dy), aimed there."""
        self.gl("mana", 250)
        self.gl("input", int(n * gap * 1000) + 300, 0, 0, dx, dy)
        time.sleep(0.1)
        for _ in range(n):
            self.gl("castat", "demons_tail", dx, dy, "nocd")
            time.sleep(gap)

    def branding(self):
        pb, ee = "hwp_wlk_pyrebrand", "hwp_wlk_essence_extraction"
        ess = "players/warlock/stacks_warlock.sval:essence"
        num = lambda st, label: (lambda m: int(m[-1]) if m else None)(re.findall(re.escape(label) + r" (-?\d+)", st))
        self.setup("brand", "warlock", "hwp_warlock_branding", [pb, ee])
        if not self.enter_floor("brand"):
            return
        fx, fy = self.open_dir(150)
        self.gl("spawn", TARGET, round(60 * fx, 1), round(60 * fy, 1))
        time.sleep(1.0)
        base = int(self.bind(pb, "pb-base") or 0)
        pct = float(self.bind(pb, "pb-pct") or 0)

        # the press brands the dummy on the aim; Demon's Tail feeds it; the skill is ready again
        # (the brand lasts 6 s and every status read takes a while: few reads until the recast)
        self.gl("mana", 250)
        mark = len(self.g.read_log())
        presses, spent, button = self.cast_skill("brand_pb", pb, 40, aim=(fx, fy))
        self.tails(2, fx, fy)
        st = self.specs()
        log = self.g.read_log()[mark:]
        self.flag("brand_cast", presses > 0 and "pyrebrand: branded" in log and num(st, "brands") == 1,
                  f"{pb} on {button}: {presses} press(es), mana -{spent}; brands {num(st, 'brands')}; "
                  f"{[l for l in log.splitlines() if 'pyrebrand' in l][-2:]}")
        stored = num(st, "stored")
        self.flag("brand_feed", (stored or 0) > 0, f"2 Demon's Tails on the branded dummy: stored {stored} ({pct:.0%} of the damage)")

        # the recast (a real Activate, not nocd, so it only goes off with the cooldown held at 0:
        # brand_ready) the claw, the mana back, then the full cooldown
        ok, line = self.brand_cast(pb, fx, fy, nocd=False)
        self.g.shot("brand claw", settle=False)   # at once: the claw lasts 0.6 s
        self.flag("brand_ready", ok, f"the recast while a brand is up activated: {ok} (the cooldown held at 0)")
        m0 = 250.0
        time.sleep(0.3)
        m1 = self.mana_exact()
        cd = self.skill_cd(pb)
        st = self.specs()
        last = num(st, "last")
        self.flag("brand_claw", ok and "claw (recast)" in line and last is not None and last >= base + (stored or 0) - 1,
                  f"recast activated {ok}: {line[-120:]!r}; last claw {last} fire (base {base} + stored {stored}, at least)")
        self.flag("brand_refund", m1 >= m0 - 3 and (cd or 0) > 5000,
                  f"mana {m0} -> {m1} (the recast is free), cooldown after the claw {cd}")

        # running out: the claw on its own, then the full cooldown
        c0 = num(st, "claws") or 0
        self.brand_cast(pb, fx, fy)
        time.sleep(6.0)
        st = self.specs()
        cd = self.skill_cd(pb)
        self.flag("brand_expire", num(st, "claws") == c0 + 1 and (cd or 0) > 5000 and num(st, "brands") == 0,
                  f"6 s later: claws {c0} -> {num(st, 'claws')}, cooldown {cd}, brands {num(st, 'brands')}")

        # the victim dies first: the brand moves to the nearest enemy. Dummies only (a brute walks
        # off the aim): the victim 40 out, the next 60 from the ranger and 45 from the victim, so
        # a kill within 50 takes only the victim
        self.gl("kill", 400, "target_dummy")
        self.gl("spawn", TARGET, round(40 * fx, 1), round(40 * fy, 1))
        self.gl("spawn", TARGET, round(40 * fx - 45 * fy, 1), round(40 * fy + 45 * fx, 1))
        time.sleep(1.0)
        t0 = num(st, "transfers") or 0
        self.brand_cast(pb, fx, fy)
        self.gl("kill", 50, "target_dummy")
        time.sleep(0.6)
        st = self.specs()
        self.flag("brand_transfer", num(st, "transfers") == t0 + 1 and num(st, "brands") == 1,
                  f"transfers {t0} -> {num(st, 'transfers')}, brands {num(st, 'brands')}")
        self.brand_cast(pb, fx, fy)   # set it off: the next checks start with none

        # a lone victim dies with nobody to take the brand: no claw, but the full cooldown
        self.gl("kill", 400, "target_dummy")
        self.gl("spawn", TARGET, round(40 * fx, 1), round(40 * fy, 1))
        time.sleep(1.0)
        self.brand_cast(pb, fx, fy)
        self.g.shot("brand sigil", settle=False)
        self.gl("kill", 400, "target_dummy")
        time.sleep(0.6)
        st = self.specs()
        cd = self.skill_cd(pb)
        self.flag("brand_lone_cd", num(st, "brands") == 0 and (cd or 0) > 5000,
                  f"brands {num(st, 'brands')}, cooldown {cd} after the lone victim died")

        # the orbs
        for orb, n in (("hwp_wlk_pb_combustion", 3), ("hwp_wlk_pb_proliferation", 3),
                       ("hwp_wlk_ee_essence_empowerment", 3), ("hwp_wlk_ee_released_essence", 2)):
            self.gl("orb", orb, n)
        time.sleep(0.5)
        binds = {k: self.bind(s_, k) for s_, k in ((pb, "pb-combust"), (pb, "pb-spread"), (ee, "ee-emp"), (ee, "ee-released"),
                                                    (ee, "ee-cd"))}
        lv = max(1, min(5, self.lvl[ee]))
        self.flag("brand_orb_binds", binds == {"pb-combust": "0.04", "pb-spread": "100", "ee-emp": "0.03", "ee-released": "6",
                                               "ee-cd": str((2000, 1750, 1500, 1250, 1000)[lv - 1])}, f"{binds}")
        self.set_stacks(ess, 30)
        n = self.status_num("essence")
        self.flag("brand_ee_max", n == 10, f"30 Essence given: {n} kept (the vanilla 10: the passive no longer raises it)")

        # Essence Empowerment: + 3% of the physical multiplier to fire, per stack
        self.set_stacks(ess, 0)
        time.sleep(0.3)
        d0 = self.gl("dmgmuls")
        self.set_stacks(ess, 10)
        time.sleep(0.3)
        d1 = self.gl("dmgmuls")
        want = 0.03 * 10 * float(d1.get("physical") or 0)
        got = float(d1.get("fire") or 0) - float(d0.get("fire") or 0)
        self.flag("brand_empowerment", abs(got - want) < 0.01 and want > 0,
                  f"fire mul {d0.get('fire')} at 0 essence, {d1.get('fire')} at 10 (+{got:.3f}, want 10 x 3% x physical "
                  f"{d1.get('physical')} = {want:.3f})")

        # Combustion: the claw spends the Essence for a bigger claw; Proliferation's brand is 3 s
        self.gl("kill", 400, "target_dummy")
        self.gl("spawn", TARGET, round(50 * fx, 1), round(50 * fy, 1))
        time.sleep(1.0)
        _, line = self.brand_cast(pb, fx, fy)
        self.flag("brand_prolif_time", "for 3000 ms" in line, f"with Proliferation: {line[-80:]!r}")
        self.set_stacks(ess, 10)
        _, line = self.brand_cast(pb, fx, fy)
        n = self.status_num("essence")
        m = re.search(r"radius (\d+), \d+ hit, (\d+) essence spent", line)
        spent_n = int(m.group(2)) if m else 0
        self.flag("brand_combustion", bool(m) and spent_n >= 9 and int(m.group(1)) == int(40 * (1 + 0.04 * spent_n)) and n == 0,
                  f"{line[-120:]!r}; essence after {n} (radius 40 x (1 + 4% a stack))")

        # Proliferation: a dying victim's brand goes to all of them
        self.gl("kill", 400, "target_dummy")
        self.gl("spawn", TARGET, round(40 * fx, 1), round(40 * fy, 1))
        for k in (-1, 1):
            self.gl("spawn", TARGET, round(40 * fx + 45 * k * fy, 1), round(40 * fy - 45 * k * fx, 1))
        self.gl("spawn", TARGET, round(100 * fx, 1), round(100 * fy, 1))
        time.sleep(1.0)
        st = self.specs()
        t0 = num(st, "transfers") or 0
        self.brand_cast(pb, fx, fy)
        self.gl("kill", 50, "target_dummy")
        time.sleep(0.6)
        st = self.specs()
        self.flag("brand_proliferation", num(st, "transfers") == t0 + 3 and num(st, "brands") == 3,
                  f"transfers {t0} -> {num(st, 'transfers')}, brands {num(st, 'brands')} (3 dummies within 100)")
        time.sleep(3.0)

        # Essence Extraction: Drain Essence's own melee gain (Demon's Tail is tagged melee) runs
        # twice on a branded enemy. Isolate the hit gains from the other orbs: Combustion
        # spends stacks, Proliferation halves the brand to 3 s, and Released Essence can
        # add six stacks when that shortened brand expires and its claw kills the elite.
        # Baseline 20261022-003808 showed that exact claw/release before the old read.
        for _ in range(3):
            self.gl("orb", "hwp_wlk_pb_combustion", "down")
            self.gl("orb", "hwp_wlk_pb_proliferation", "down")
        for _ in range(2):
            self.gl("orb", "hwp_wlk_ee_released_essence", "down")
        isolated = {"combustion": self.bind(pb, "pb-combust"),
                    "proliferation": self.bind(pb, "pb-spread"),
                    "released": self.bind(ee, "ee-released")}
        self.gl("kill", 400, "target_dummy")
        # stunned: its swings knock the warlock back, which cancels the cast
        self.gl("spawn", "actors/humans/bandits/bandit_brute_elite.unit", round(45 * fx, 1), round(45 * fy, 1))
        time.sleep(0.3)
        stun = self.gl("buffnear", 200, "bandit_brute_elite", "tweak/buffs/status_effects.sval:stun_greater", 20000)
        self.notes.append(f"brand: elite stunned: {stun.get('actors')}")
        time.sleep(0.7)
        elite_hp0 = self.dummy_hp("bandit_brute_elite")
        self.set_stacks(ess, 0)
        st = self.specs()
        w0 = num(st, "twice") or 0
        r0 = num(st, "released") or 0
        ok, line = self.brand_cast(pb, fx, fy)
        self.flag("brand_essence_setup", ok and "for 6000 ms" in line and num(st, "essence") == 0
                  and all(value == "0" for value in isolated.values()),
                  f"isolated binds {isolated}; zero Essence {num(st, 'essence')}; {line[-100:]!r}")
        self.tails(4, fx, fy)
        st = self.specs()
        elite_hp1 = self.dummy_hp("bandit_brute_elite")
        w1, n = num(st, "twice"), num(st, "essence")
        d = (w1 or 0) - w0
        self.flag("brand_essence_target", len(elite_hp0) == 1 and num(st, "brands") == 1
                  and all(0 < elite_hp1.get(unit, 0) < hp for unit, hp in elite_hp0.items()),
                  f"same elite HP {elite_hp0} -> {elite_hp1}; brands {num(st, 'brands')} (still alive and branded)")
        self.flag("brand_essence_twice", d >= 2 and n == 2 * d and num(st, "released") == r0,
                  f"4 tails on a branded elite: second gains {w0} -> {w1}, essence {n}, released {r0} -> {num(st, 'released')} "
                  "(2 a gain: Drain Essence's and ours; no independent elite reward)")

        # End a surviving brand while Released Essence is still off, then restore the orb
        # for its own test below. The doubled-gain equality above is unchanged.
        if (num(st, "brands") or 0) > 0:
            self.brand_cast(pb, fx, fy)
        self.gl("orb", "hwp_wlk_ee_released_essence", 2)
        self.flag("brand_released_setup", self.bind(ee, "ee-released") == "6", "Released Essence rank 2 restored")

        # Released Essence: a fresh elite dies to the claw (with the doubled Essence the tails'
        # brand's own claw can kill the last one: run 20261021-230738)
        time.sleep(3.0)
        self.gl("kill", 400, "bandit_brute_elite")
        self.gl("spawn", "actors/humans/bandits/bandit_brute_elite.unit", round(45 * fx, 1), round(45 * fy, 1))
        time.sleep(0.3)
        self.gl("buffnear", 200, "bandit_brute_elite", "tweak/buffs/status_effects.sval:stun_greater", 20000)
        time.sleep(0.7)
        r0 = num(self.specs(), "released") or 0
        self.brand_cast(pb, fx, fy)
        self.set_stacks(ess, 0)
        self.gl("kill", 400, "bandit_brute_elite", 0.001)
        _, line = self.brand_cast(pb, fx, fy)
        time.sleep(0.4)   # the kill is watched for (UpdateBrands), not read in the claw's frame
        st = self.specs()
        r, n = num(st, "released"), num(st, "essence")
        self.flag("brand_released", (r or 0) - r0 >= 6 and (n or 0) >= 6, f"{line[-120:]!r}: released {r0} -> {r}, essence {n} (6 an elite)")

        # Essence Extraction, magic weapons: a wand's hits are an Essence gain once per ee-cd ms,
        # and two on a branded enemy. Proliferation remains off: its 3 s brand can end
        # inside the setup and the 2 s of hits.
        cdms = int(self.bind(ee, "ee-cd") or 0)
        self.gl("kill", 400, "target_dummy")
        self.gl("spawn", TARGET, round(50 * fx, 1), round(50 * fy, 1))
        r = self.gl("equip", "mainhand_wand_fire_01", 1, 1)
        self.notes.append(f"brand: wand: {r}")
        time.sleep(1.0)
        self.set_stacks(ess, 0)
        st = self.specs()
        h0, w0 = num(st, "essence hits") or 0, num(st, "twice") or 0
        self.gl("input", 3300, 0, 0, fx, fy, "main")
        time.sleep(3.6)
        st = self.specs()
        h1, w1, n = num(st, "essence hits") or 0, num(st, "twice") or 0, num(st, "essence")
        self.flag("brand_magic", 1 <= h1 - h0 <= 3300 // max(1, cdms) + 1 and w1 == w0 and n == h1 - h0,
                  f"3.3 s of wand attacks: gains {h0} -> {h1} (once per {cdms} ms), second gains {w0} -> {w1}, essence {n}")
        self.set_stacks(ess, 0)
        time.sleep(cdms / 1000)
        self.brand_cast(pb, fx, fy)
        st = self.specs()
        h0, w0 = num(st, "essence hits") or 0, num(st, "twice") or 0
        self.gl("input", 2000, 0, 0, fx, fy, "main")
        time.sleep(2.2)
        st = self.specs()
        h1, w1, n = num(st, "essence hits") or 0, num(st, "twice") or 0, num(st, "essence")
        self.flag("brand_magic_twice", h1 - h0 >= 1 and w1 - w0 == h1 - h0 and n == 2 * (h1 - h0),
                  f"2 s of wand attacks on a branded dummy: gains {h0} -> {h1}, second gains {w0} -> {w1}, essence {n}")
        # not checked here: the holy scepter and lantern (arcane-tagged too, but Holy DLC gear:
        # GenerateItem returns null in the lab) and the off hand (the warlock's tome drops a glyph
        # at its feet; an off-hand weapon hit fires the same Hit trigger, PlayerBase.as:881)
        self.to_town()

    # --- Arcane
    def blink(self, dx, dy, nocd=True):
        """Blink through castat inside an aim hold (the effect takes the player's aim). Returns
        (activated, the blink log line, the position before, after)."""
        self.gl("input", 600, 0, 0, dx, dy)
        time.sleep(0.1)
        p0 = self.pos()
        mark = len(self.g.read_log())
        r = self.gl("castat", "hwp_sor_blink", dx, dy, *(["nocd"] if nocd else []))
        time.sleep(0.5)
        line = "\n".join(l for l in self.g.read_log()[mark:].splitlines() if "blink:" in l or "feedback" in l)
        return bool(r.get("activated")), line, p0, self.pos()

    def arcane(self):
        bl, lm = "hwp_sor_blink", "hwp_sor_living_mana"
        num = lambda st, label: (lambda m: int(m[-1]) if m else None)(re.findall(re.escape(label) + r" (-?\d+)", st))
        # setup by hand: the max mana is read before the subclass, which teaches Living Mana
        r, pl, lv = self.new_char("sorcerer", "LabArcane")
        time.sleep(0.5)
        pl = self.gl("state").get("player", {})
        self.flag("arc_char", r.get("ok") and pl.get("class") == "sorcerer" and pl.get("level", 0) >= 20,
                  f"{r} class {pl.get('class')} level {pl.get('level')}")
        m0, h0 = pl.get("manaMax", 0), pl.get("hpMax", 0)
        took = self.gl("subclass", "hwp_sorcerer_arcane").get("class")
        self.hwp("skillpoints 40")
        self.lvl = {s: self.gl("skill", s, 1).get("level", 0) for s in (bl, lm)}
        self.flag("arc_learned", took == "hwp_sorcerer_arcane" and all(v >= 1 for v in self.lvl.values()),
                  f"subclass {took}, levels {self.lvl}")
        time.sleep(0.5)
        pl = self.gl("state").get("player", {})
        self.flag("arc_max_mana", abs(pl.get("manaMax", 0) - (m0 + h0)) <= 1,
                  f"max mana {m0} + max health {h0} -> {pl.get('manaMax')} (health {pl.get('hpMax')})")
        if not self.enter_floor("arc"):
            return
        fx, fy = self.open_dir(200)
        x0, y0 = self.pos()
        home = lambda: (self.gl("teleport", round(x0, 1), round(y0, 1)), time.sleep(0.2))

        # health follows the mana fraction
        self.gl("mana", 60)
        time.sleep(0.4)
        pl = self.gl("state").get("player", {})
        hpf, mf = pl.get("hp", 0) / max(1, pl.get("hpMax", 1)), pl.get("manaExact", 0) / max(1, pl.get("manaMax", 1))
        self.flag("arc_hp_mirror", abs(hpf - mf) < 0.03, f"mana {pl.get('manaExact')}/{pl.get('manaMax')} ({mf:.3f}), health {pl.get('hp')}/{pl.get('hpMax')} ({hpf:.3f})")

        # health given (a heal, a potion, regeneration) turns into mana; health taken drains it
        st = self.specs()
        c0, d0 = num(st, "converted") or 0, num(st, "drained") or 0
        hpmax = pl.get("hpMax", 1)
        pl = self.gl("state").get("player", {})
        f0 = pl.get("manaExact", 0) / max(1, pl.get("manaMax", 1))   # the health right now
        self.gl("hurt", round(f0 + 0.25, 3))
        time.sleep(0.4)
        st = self.specs()
        c1 = num(st, "converted") or 0
        want = (round(f0 + 0.25, 3) - f0) * hpmax
        # (health regeneration is converted the whole time too: a little on top)
        self.flag("arc_heal_converts", -2 <= (c1 - c0) - want <= 10,
                  f"health {f0:.3f} -> {f0 + 0.25:.3f} of {hpmax}: converted {c0} -> {c1} (want +{want:.1f}, regeneration on top)")
        pl = self.gl("state").get("player", {})
        hpf = pl.get("hp", 0) / max(1, hpmax)
        self.gl("hurt", round(max(0.02, hpf - 0.1), 3))
        time.sleep(0.4)
        st = self.specs()
        d1 = num(st, "drained") or 0
        self.flag("arc_loss_drains", abs((d1 - d0) - 0.1 * hpmax) <= 2,
                  f"health -10% of {hpmax} (as a buff's damage over time takes it): drained {d0} -> {d1}")

        # a hit drains the mana, the health stays the mana's
        self.god(False)
        self.gl("mana", 200)
        time.sleep(0.3)
        r = self.gl("damageme", 30)
        time.sleep(0.3)
        pl = self.gl("state").get("player", {})
        took, lost = r.get("took", 0), (r.get("mana0") or 0) - (r.get("mana") or 0)
        self.flag("arc_hit_drains", took > 0 and abs(lost - took) <= 1 and not r.get("dead") and pl.get("hp", 0) > 0,
                  f"30 pure: the hit took {took}, mana {r.get('mana0'):.1f} -> {r.get('mana'):.1f} (lost {lost:.1f}); "
                  f"health {r.get('hp0'):.3f} -> {r.get('hp'):.3f}, now {pl.get('hp')}/{hpmax}")

        cost = (20, 20, 25, 25, 30)[max(1, min(5, self.lvl[bl])) - 1]
        self.gl("kill", 400, "tag:enemy")

        # Blink: the dodge's distance (90, x 0.95 the teleport keeps off walls), pure where it lands
        self.god(True)
        home()
        px, py = -fy, fx
        self.gl("spawn", TARGET, round(86 * fx + 12 * px, 1), round(86 * fy + 12 * py, 1))
        time.sleep(1.0)
        hp0 = self.dummy_hp("target_dummy")
        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink(fx, fy)
        moved = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
        time.sleep(0.3)
        hp1 = self.dummy_hp("target_dummy")
        hit = [u for u, h in hp0.items() if hp1.get(u, 0.0) < h - 0.0001]
        self.g.shot("blink", settle=False)
        self.flag("arc_blink", ok and 80 <= moved <= 92 and "blink: " in line, f"activated {ok}, moved {moved:.1f} px: {line[-80:]!r}")
        self.flag("arc_blink_damage", ", 1 hit" in line and len(hit) == 1, f"{line[-60:]!r}; dummy hp {hp0} -> {hp1}")

        # the recast: the last elemental spell (Static Discharge) again from the start point,
        # a dash charge spent, its cooldown started over
        self.gl("kill", 400, "target_dummy")
        home()
        self.gl("input", 500, 0, 0, fx, fy)
        self.gl("castat", "static_discharge", fx, fy, "nocd")
        time.sleep(0.8)
        st = self.specs()
        dash0, last = num(st, "dashes"), re.findall(r"last spell (\w+)", st)
        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink(fx, fy)
        st = self.specs()
        self.flag("arc_recast", ok and "recast static_discharge" in line and num(st, "dashes") == (dash0 or 0) - 1,
                  f"last spell {last}; dashes {dash0} -> {num(st, 'dashes')}; {line[-80:]!r}")

        # no dash charge (the one charge comes back 5 s after: Tweak::BaseDashRechargeTime): Blink only
        home()
        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink(fx, fy)
        st = self.specs()
        self.flag("arc_no_dash", ok and "recast" not in line and num(st, "dashes") == 0,
                  f"dashes {num(st, 'dashes')}: {line[-80:]!r}")

        # a spell stops at 1 mana: the charge back, Blink from its cost + 5, then the recast's
        # whole cost (more than 5) out of what is left
        time.sleep(5.5)
        home()
        fl0 = num(self.specs(), "floored") or 0
        self.gl("mana", cost + 5)
        ok, line, p0, p1 = self.blink(fx, fy)
        m = self.mana_exact()
        fl1 = num(self.specs(), "floored") or 0
        # (regeneration refills it at once, so the floor is read off its counter, not the pool)
        self.flag("arc_floor", ok and "recast static_discharge" in line and fl1 > fl0 and m >= 1
                  and not self.gl("state").get("player", {}).get("dead"),
                  f"Blink ({cost} mana) from {cost + 5}, then the recast: {line[-60:]!r}; floored {fl0} -> {fl1}, mana after {m}")

        # the orbs
        for orb, n in (("hwp_sor_bl_void_barrier", 1), ("hwp_sor_bl_far_step", 3),
                       ("hwp_sor_lm_arcane_feedback", 3), ("hwp_sor_lm_mana_conduit", 3)):
            self.gl("orb", orb, n)
        time.sleep(0.5)
        binds = {k: self.bind(s_, k) for s_, k in ((bl, "bl-barrier"), (bl, "bl-far"), (lm, "lm-feedback"), (lm, "lm-conduit"),
                                                    (lm, "lm-regen"))}
        lv = max(1, min(5, self.lvl[lm]))
        self.flag("arc_orb_binds", binds == {"bl-barrier": "1000", "bl-far": "0.35", "lm-feedback": "120", "lm-conduit": "1",
                                             "lm-regen": str((0.5, 0.75, 1, 1.25, 1.5)[lv - 1])}, f"{binds}")

        # Far Step: 35% farther
        home()
        self.gl("mana", 200)
        ok, line, p0, p1 = self.blink(fx, fy)
        moved = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
        self.flag("arc_far_step", ok and 110 <= moved <= 124, f"moved {moved:.1f} px (90 x 1.35 x 0.95 = 115): {line[-60:]!r}")

        # Arcane Feedback: mana lost to damage is banked, the next spell takes it
        self.god(False)
        self.gl("mana", 200)
        r = self.gl("damageme", 40)
        st = self.specs()
        fb = num(st, "feedback")
        mark = len(self.g.read_log())
        self.gl("input", 500, 0, 0, fx, fy)
        self.gl("castat", "static_discharge", fx, fy, "nocd")
        time.sleep(0.4)
        st = self.specs()
        log = "\n".join(l for l in self.g.read_log()[mark:].splitlines() if "feedback" in l)
        want = int(1000 * (1 + (fb or 0) * 0.005) + 0.5)
        mod = num(st, "moddmg")
        self.flag("arc_feedback", (fb or 0) >= 1 and abs((fb or 0) - r.get("took", 0)) <= 1 and "arcane feedback" in log
                  and num(st, "used") == 1 and mod is not None and abs(mod - want) <= 2,
                  f"40 pure took {r.get('took')}: banked {fb}; {log[-90:]!r}; static discharge damage mul x{mod}/1000 (want {want})")
        # the bank skips Blink and waits for the next elemental spell
        self.gl("mana", 200)
        self.gl("damageme", 40)
        u0 = num(self.specs(), "used") or 0
        ok, line, p0, p1 = self.blink(fx, fy)
        u1 = num(self.specs(), "used") or 0
        self.gl("input", 500, 0, 0, fx, fy)
        self.gl("castat", "static_discharge", fx, fy, "nocd")
        time.sleep(0.4)
        u2 = num(self.specs(), "used") or 0
        self.flag("arc_feedback_blink", ok and u1 == u0 and u2 == u0 + 1,
                  f"feedback used {u0} -> {u1} after a Blink -> {u2} after Static Discharge")
        st = self.specs()
        # Mana Conduit: single player, no teammates, nothing sent
        self.flag("arc_conduit_solo", num(st, "conduit sent") == 0, f"conduit sent {num(st, 'conduit sent')} (no teammates)")

        # Void Barrier: a lethal hit within 1 s of a Blink leaves 1 mana
        home()
        self.gl("mana", 200)
        self.gl("input", 500, 0, 0, fx, fy)
        self.gl("castat", "hwp_sor_blink", fx, fy, "nocd")
        time.sleep(0.25)   # past the castpoint, well inside the barrier's second
        self.gl("mana", 40)
        r = self.gl("damageme", 500)
        st = self.specs()
        self.flag("arc_void_barrier", not r.get("dead") and (r.get("mana") or 0) <= 2 and num(st, "barrier saves") == 1,
                  f"500 pure from 40 mana right after a Blink: dead {r.get('dead')}, mana {r.get('mana')}, saves {num(st, 'barrier saves')}")

        # the regeneration: faster at low mana (+ lm-regen x the missing fraction)
        self.god(True)
        maxm = pl.get("manaMax", 1)
        gains = []
        for frac in (0.9, 0.05):
            self.gl("mana", int(maxm * frac))
            a = self.mana_exact()
            time.sleep(4.0)
            gains.append(self.mana_exact() - a)
        self.flag("arc_regen", gains[1] > gains[0] * 1.1 and gains[0] > 0,
                  f"4 s of regeneration at 90% mana +{gains[0]:.1f}, at 5% +{gains[1]:.1f} (lm-regen {binds.get('lm-regen')})")

        # running dry: a hit past the pool kills (last: the run ends here)
        self.god(False)
        time.sleep(1.2)   # the barrier is long gone
        self.gl("mana", 20)
        r = self.gl("damageme", 300)
        time.sleep(0.5)
        self.flag("arc_lethal", bool(r.get("dead")), f"300 pure from 20 mana: dead {r.get('dead')}, mana {r.get('mana')}, health {r.get('hp')}")
        self.gl("abort", "failed")
        self.wait_phase("town", 90)
        time.sleep(2)
        if self.gl("state").get("window"):
            self.g.key("escape")
            time.sleep(0.5)

def run(p, sections="winddancer,bannerlord,invocation,stormbringer,branding,arcane", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
