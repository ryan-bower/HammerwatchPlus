// Aerotheurge (Wizard; the ids keep the build's invocation name): Thunder Orb and Static Charge.
// - Thunder Orb (invocation/tempest_torrent.sval, the orb invocation/torrent.unit): a slow
//   NewProjectile that passes through enemies and stops at a wall (bounce speed 0). Its
//   PeriodicEffect runs HWPSpecsZap every 250 ms: tt-zaps zaps on the enemies within
//   tt-radius, the ones this orb has zapped least first, so a pack is swept and a lone target
//   takes them all. Focal Point (tt-overcharge): each zap on an enemy deals more for every
//   earlier zap of this orb on it, up to 10. Lightning Rod: tt-zaps and tt-radius up.
//   Thunderclap (tt-clap): the orb's destroyed-effects zap every enemy in range once at
//   tt-clap x the damage.
// - Static Charge (invocation/static_charge.sval): every spell cast adds a stack
//   (static_charge, max 5, 10 s reset by each new one) and its first crit one more
//   (HWPSpecsStaticCrit, g_scCast). The next spell cast at 5 releases it
//   (HWPSpecsStaticRelease): 3 strikes split over up to 3 enemies around the wizard, x1.5 when
//   all three hit one. Charged Font (sc-channel: max mana restored), Conduit (sc-conduit-lvl:
//   conduit_<lvl>_<stacks>, cast speed per stack, kept on by UpdateConduit).
namespace HWP
{
	namespace Specs
	{
		const uint STATIC_CHARGE = HashString("hwp_wiz_static_charge");
		const int STATIC_MAX = 5;

		// spell casts counted on the wizard's own client, and the one whose crit last added a
		// stack: a cast's crits add one stack between them
		int g_scCast = 0;
		int g_scCritCast = -1;

		// Charged Font's mana, given g_channelC ms after the release: the castspell trigger
		// runs before the cast pays its cost (Player.as:841, at the castpoint), so mana given at
		// once is lost to the cap when the wizard is near full
		int g_channelMana = 0;
		int g_channelC = 0;

		int g_conduitC = 0;
		void UpdateConduit(int ms)
		{
			g_channelC -= ms;
			if (g_channelMana > 0 && g_channelC <= 0)
			{
				auto p = cast<PlayerBase>(GetLocalPlayer());
				if (p !is null && !p.IsDead())
					p.GiveMana(g_channelMana, false);
				g_channelMana = 0;
			}
			g_conduitC -= ms;
			if (g_conduitC > 0)
				return;
			g_conduitC = 250;
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			auto def = Stack("static_charge");
			if (plr is null || def is null || plr.IsDead())
				return;
			int lvl = BindI(plr, STATIC_CHARGE, "sc-conduit-lvl", 0);
			int n = min(STATIC_MAX, plr.GetStacks(def));
			if (lvl > 0 && n > 0)
				Give(plr, plr, Buff("conduit_" + lvl + "_" + n), 1, 600);
		}
	}
}

// Zaps the enemies around pos with the child effects (Damage etc.), drawing a lightning beam
// from pos to each. targets: zaps per apply, spread over the enemies this instance has zapped
// least; all: every enemy in range once instead. mul (bindable, <= 0 does nothing) and
// overcharge (bindable: + per earlier zap on the same enemy, up to max-overcharge) scale the
// intensity; lone-mul when only one enemy is in range and it takes every zap.
class HWPSpecsZap : IEffect
{
	EffectList@ m_effects;
	int m_targets;
	int m_radius;
	bool m_all;
	float m_mul;
	float m_overcharge;
	int m_maxOvercharge;
	float m_loneMul;
	string m_beamFx;
	string m_hitFx;
	dictionary m_zapped;   // unit id -> zaps by this instance (one per projectile)

	HWPSpecsZap(UnitPtr unit, SValue& params)
	{
		@m_effects = LoadEffects(unit, params);
		m_targets = GetParamInt(unit, params, "targets", false, 3);
		m_radius = GetParamInt(unit, params, "radius", false, 70);
		m_all = GetParamBool(unit, params, "all", false, false);
		m_mul = GetParamFloat(unit, params, "mul", false, 1.0f);
		m_overcharge = GetParamFloat(unit, params, "overcharge", false, 0.0f);
		m_maxOvercharge = GetParamInt(unit, params, "max-overcharge", false, 10);
		m_loneMul = GetParamFloat(unit, params, "lone-mul", false, 1.0f);
		m_beamFx = GetParamString(unit, params, "beam-fx", false, "effects/generic/raycast/rogue_lightning_beam_1.effect");
		m_hitFx = GetParamString(unit, params, "hit-fx", false, "effects/generic/impacts/lightning_impact_2.effect");
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { PropagateWeaponInformation(m_effects, weapon); }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null && m_mul > 0; }

	int Zapped(Actor@ a)
	{
		int n = 0;
		m_zapped.get("" + a.m_unit.GetId(), n);
		return n;
	}

	void Zap(Actor@ owner, vec2 from, Actor@ a, float intensity, bool husk)
	{
		vec2 to = xy(a.m_unit.GetPosition());
		vec2 d = to - from;
		dictionary ps = { { "angle", atan(d.y, d.x) }, { "length", length(d) } };
		PlayEffect(m_beamFx, from, ps);
		PlayEffect(m_hitFx, to);
		ApplyEffects(m_effects, owner, a.m_unit, to, normalize(d), intensity, husk);
	}

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		if (!CanApply(owner, target, pos, dir, intensity))
			return false;
		auto enemies = HWP::Specs::EnemiesNear(pos, m_radius, owner.Team);
		if (enemies.length() == 0)
			return false;
		if (m_all)
		{
			for (uint i = 0; i < enemies.length(); i++)
				Zap(owner, pos, enemies[i], intensity * m_mul, husk);
			return true;
		}
		// least zapped first, then nearest
		array<Actor@> order;
		array<float> keys;
		for (uint i = 0; i < enemies.length(); i++)
		{
			float k = Zapped(enemies[i]) * 100000.0f + dist(pos, xy(enemies[i].m_unit.GetPosition()));
			uint at = 0;
			while (at < keys.length() && keys[at] <= k)
				at++;
			order.insertAt(at, enemies[i]);
			keys.insertAt(at, k);
		}
		float lone = (order.length() == 1 && m_targets > 1) ? m_loneMul : 1.0f;
		for (int z = 0; z < m_targets; z++)
		{
			auto a = order[z % order.length()];
			if (a.IsDead())
				continue;
			int n = Zapped(a);
			float oc = 1.0f + m_overcharge * min(n, m_maxOvercharge);
			m_zapped.set("" + a.m_unit.GetId(), n + 1);
			Zap(owner, pos, a, intensity * m_mul * oc * lone, husk);
		}
		return true;
	}
}

// Static Charge on a spell cast (castspell trigger in static_charge.sval): under 5 stacks the
// cast adds one; at 5 the stacks go, HWPSpecsZap (the child "zap" dict) strikes from the wizard and
// sc-channel of max mana comes back (UpdateConduit gives it, after the cast's cost). Decided on the wizard's own client; the other peers
// get the trigger with husk set and only draw it while they still see 5 stacks.
class HWPSpecsStaticRelease : IEffect
{
	HWPSpecsZap@ m_zap;
	float m_channel;

	HWPSpecsStaticRelease(UnitPtr unit, SValue& params)
	{
		auto zap = GetParamDictionary(unit, params, "zap", true);
		@m_zap = HWPSpecsZap(unit, zap);
		m_channel = GetParamFloat(unit, params, "channel", false, 0.0f);
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { m_zap.SetWeaponInformation(weapon); }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		auto def = HWP::Specs::Stack("static_charge");
		if (plr is null || def is null)
			return false;
		bool own = !husk && !owner.IsHusk();
		if (own)
			HWP::Specs::g_scCast++;
		if (plr.GetStacks(def) < HWP::Specs::STATIC_MAX)
		{
			if (own)
				plr.AddStacks(plr, def, 1);
			return own;
		}
		vec2 at = xy(owner.m_unit.GetPosition());
		m_zap.m_zapped.deleteAll();
		bool hit = m_zap.Apply(owner, owner.m_unit, at, dir, intensity, husk);
		if (husk || owner.IsHusk())
			return hit;
		plr.AddStacks(plr, def, -plr.GetStacks(def));
		PlayEffect("effects/generic/explosions/lightning_explosion_discharge_medium_2.effect", at);
		if (m_channel > 0)
		{
			HWP::Specs::g_channelMana = int(plr.m_record.MaxMana() * m_channel + 0.5f);
			HWP::Specs::g_channelC = 400;
		}
		HWP::Log("specs", "static charge: released" + (hit ? "" : " (no enemy near)")
			+ (m_channel > 0 ? ", " + int(m_channel * 100 + 0.5f) + "% mana" : ""));
		return true;
	}
}

// Static Charge's crit stack (criticalhit trigger in static_charge.sval): one more stack, for
// the first crit since the last spell cast only. Its own client.
class HWPSpecsStaticCrit : IEffect
{
	HWPSpecsStaticCrit(UnitPtr unit, SValue& params) {}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) {}
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		auto def = HWP::Specs::Stack("static_charge");
		if (husk || plr is null || def is null || plr.IsHusk() || HWP::Specs::g_scCritCast == HWP::Specs::g_scCast)
			return false;
		HWP::Specs::g_scCritCast = HWP::Specs::g_scCast;
		if (plr.GetStacks(def) >= HWP::Specs::STATIC_MAX)
			return false;
		plr.AddStacks(plr, def, 1);
		return true;
	}
}

// A projectile modifier that adds add (bindable, ms) to the projectile's ttl: Lingering Storm's
// tt-ttl-add on top of the level's tt-ttl (an orb's bind replaces a level's, it cannot add)
class HWPSpecsTtlAdd : ProjectileModifier
{
	int m_add;

	HWPSpecsTtlAdd(UnitPtr unit, SValue& params)
	{
		m_add = GetParamInt(unit, params, "add", false, 0);
	}

	void Initialize(NewProjectile@ behavior, SValue& params, Actor@ owner, ProjectileTarget@ target, uint weapon) override
	{
		behavior.m_ttl += m_add;
	}
}
