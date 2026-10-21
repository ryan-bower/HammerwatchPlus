"""Test-plan checks for the 4th specializations (mods/specs).

Each section makes a fresh level-20 character of the base class (`gl char`, `hwp levelup 20`),
takes the spec with `gl subclass`, learns its two skills with `gl skill` and equips orbs with
`gl orb`, then casts in an emptied Bandit Keep floor with god mode on. The verbs are core
gamelab plus mods/gamelab-hands/scripts/GameLab/Verbs_specs.as: hasbuff (a buff by its path,
for the buffs that have no display name), evade (Player.Evade's real roll and triggers) and
bind (a skill's live bind, to see the orbs took).

Sections: winddancer, bannerlord, invocation. Single player: what only shows on a teammate (Shared Breath,
the standard's ally numbers) is checked as far as the bearer's own client goes."""
import re
import time

from gamelab.bots.plan_classesb import Checks as Base

BUFFS = "players/hwp/specs/buffs_specs.sval:"
STATUS = "tweak/buffs/status_effects.sval:"
DUMMY = "actors/humans/bandits/bandit_brute.unit"


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

    def cast_skill(self, tag, skill, cost, done=None, fallback="skill3"):
        button = self.button_for(tag, skill, fallback)
        presses, spent = self.cast(skill, button, cost, done=done)
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


    # --- Invocation
    def dummy_hp(self):
        """{unit id: hp fraction, 0 when dead} of the dummies around."""
        return {u["unit"]: (0.0 if u.get("dead") else u.get("hp", 1.0)) for u in self.dummies(400)}

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
                       ("hwp_wiz_sc_static_channel", 2), ("hwp_wiz_sc_conduit", 2)):
            self.gl("orb", orb, n)
        time.sleep(0.5)
        binds = {k: self.bind(s_, k) for s_, k in ((tt, "tt-overcharge"), (tt, "tt-ttl-add"), (tt, "tt-clap"),
                                                    (sc, "sc-channel"), (sc, "sc-conduit-lvl"))}
        self.flag("inv_orb_binds", binds == {"tt-overcharge": "0.07", "tt-ttl-add": "2000", "tt-clap": "1.5",
                                             "sc-channel": "0.2", "sc-conduit-lvl": "2"}, f"{binds}")

        path = "players/hwp/specs/stacks_specs.sval:static_charge"
        self.gl("stacks", path, 3)
        cb = self.wait_buff("conduit_2_3", 1.5)
        self.flag("inv_conduit", bool(cb.get("on")), f"3 charges, Conduit 2: conduit_2_3 {cb} (+24% cast speed)")

        # a release on the next cast: 5 charges, the torrent's cooldown over
        self.gl("stacks", path, 5)
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
        # the torrent's own zaps can crit and start the count again: 0 or 1 after the release
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


def run(p, sections="winddancer,bannerlord,invocation", **_):
    c = Checks(p)
    for s in sections.split(","):
        try:
            getattr(c, s)()
        except Exception as e:  # a section's crash is its own failure, not the bot's
            c.flag(f"{s}_crashed", False, repr(e))
    c.out["notes"] = c.notes
    c.out["terminal"] = " | ".join(c.notes)[-3000:]
    return c.out
