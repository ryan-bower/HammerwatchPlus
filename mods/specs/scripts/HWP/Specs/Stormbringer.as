// Stormbringer (Ranger): Electric Circuit and Gathering Winds.
// - Electric Circuit (stormbringer/electric_circuit.sval, the arrow stormbringer/circuit.unit):
//   a fan of 3 piercing arrows. HWPSpecsReturn turns each one around at its range or at a wall
//   and flies it back to where it was shot, hitting everything again (Charged Boomerang:
//   ec-return-mul on the way back). Every hit runs HWPSpecsStrike: lightning on up to
//   ec-strikes other enemies within ec-radius of the one hit (Lightning Rod raises both;
//   Charged Boomerang's ec-lone strikes a lone target itself). Tailwind Catch (ec-catch): the
//   ranger catching the arrow on its way back adds a Tailwind stack.
// - Gathering Winds (stormbringer/gathering_winds.sval): a two-handed bow or crossbow's
//   secondary attack adds a Tailwind stack (stacks_specs.sval tailwind: +1% move, attack and
//   cast speed each, 5 s, reset by every add), up to gw-max for the level (AddTailwind).
//   Gale Force (gw-gale): at gw-max the bow and crossbow attacks shoot gw-gale more arrows
//   (HWPSpecsGaleForce). Wind Ward (gw-ward): wind_ward at gw-ward x stacks damage taken
//   off, kept on by UpdateWindWard.
namespace HWP
{
	namespace Specs
	{
		const uint GATHERING_WINDS = HashString("hwp_ran_gathering_winds");

		// counts since the session started, for `hwp specs` (the checks read them)
		int g_circuitReturns = 0;
		int g_circuitCatches = 0;
		int g_circuitBackHits = 0;
		int g_galeArrows = 0;

		// one Tailwind stack, capped at the level's gw-max; at the cap the stack's timer is
		// reset (a take and an add: the stack resets its timer on both)
		void AddTailwind(PlayerBase@ plr)
		{
			auto def = Stack("tailwind");
			int cap = BindI(plr, GATHERING_WINDS, "gw-max", 0);
			if (plr is null || def is null || cap <= 0 || plr.IsDead())
				return;
			int n = plr.GetStacks(def);
			if (n > cap)
				plr.AddStacks(plr, def, cap - n);
			else if (n == cap)
			{
				plr.AddStacks(plr, def, -1);
				plr.AddStacks(plr, def, 1);
			}
			else
				plr.AddStacks(plr, def, 1);
		}

		int g_wardC = 0;
		void UpdateWindWard(int ms)
		{
			g_wardC -= ms;
			if (g_wardC > 0)
				return;
			g_wardC = 250;
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			auto def = Stack("tailwind");
			if (plr is null || def is null || plr.IsDead())
				return;
			float ward = BindF(plr, GATHERING_WINDS, "gw-ward", 0);
			int n = plr.GetStacks(def);
			if (ward > 0 && n > 0)
				Give(plr, plr, Buff("wind_ward"), ward * n, 600);
		}
	}
}

// Electric Circuit's return. The arrow flies out for its ttl (its range), or until a wall, then
// turns for the point it was shot from, may hit the enemies it already hit, and goes at
// that point or when it reaches the ranger (a catch: Tailwind with catch). mul (bindable)
// scales the arrow's intensity on the way back.
class HWPSpecsReturn : ProjectileModifier
{
	NewProjectile@ m_proj;
	int m_out;
	int m_t;
	bool m_back;
	float m_mul;
	bool m_catch;
	vec2 m_home;

	HWPSpecsReturn(UnitPtr unit, SValue& params) {}

	void Initialize(NewProjectile@ behavior, SValue& params, Actor@ owner, ProjectileTarget@ target, uint weapon) override
	{
		@m_proj = behavior;
		m_mul = GetParamFloat(behavior.m_unit, params, "mul", false, 1.0f);
		m_catch = GetParamFloat(behavior.m_unit, params, "catch", false, 0.0f) > 0;
		m_out = behavior.m_ttl;
		behavior.m_ttl = m_out * 3 + 1000;
		m_home = behavior.m_pos;
	}

	void Turn()
	{
		m_back = true;
		HWP::Specs::g_circuitReturns++;
		m_proj.m_lastCollision = UnitPtr();
		m_proj.m_intensity *= m_mul;
		vec2 d = m_home - m_proj.m_pos;
		if (length(d) > 0.1f)
			m_proj.SetDirection(normalize(d));
		else
			m_proj.m_unit.Destroy();
	}

	void Update(int dt, vec2 from, vec2 to) override
	{
		if (m_proj.m_unit.IsDestroyed())
			return;
		m_t += dt;
		if (!m_back)
		{
			if (m_t >= m_out)
				Turn();
			return;
		}
		auto owner = cast<PlayerBase>(m_proj.m_owner);
		if (owner !is null && !owner.IsDead() && dist(to, xy(owner.m_unit.GetPosition())) <= 12)
		{
			if (m_catch && !m_proj.m_husk && HWP::Specs::IsLocal(owner))
			{
				HWP::Specs::AddTailwind(owner);
				HWP::Specs::g_circuitCatches++;
			}
			m_proj.m_unit.Destroy();
			return;
		}
		// past home (the step would carry it over): done
		if (dot(m_home - to, m_proj.m_dir) <= 0)
			m_proj.m_unit.Destroy();
	}

	// a bounce off a wall turns the arrow (or, on its way back, ends it). One off another
	// projectile is undone: the fan's arrows spawn on one spot, and NewProjectile.Initialize
	// bounces each off the ones there before it (its QueryRect; reversed, one bounce spent)
	void OnHit(UnitPtr unit, vec2 pos) override
	{
		if (m_back)
			HWP::Specs::g_circuitBackHits++;
	}

	void OnBounce(UnitPtr unit, vec2 pos, vec2 normal) override
	{
		if (cast<IProjectile>(unit.GetScriptBehavior()) !is null)
		{
			m_proj.m_bounces++;
			m_proj.SetDirection(m_proj.m_dir * -1.0f);
			return;
		}
		if (!m_back)
			Turn();
		else
			m_proj.m_unit.Destroy();
	}
}

// Lightning on up to count enemies within radius of the one hit (count and radius bindable),
// nearest first, never the one hit; lone (bindable, > 0): with no other enemy there, the one
// hit takes every strike. Each strike plays fx and applies the child effects at the enemy.
class HWPSpecsStrike : IEffect
{
	EffectList@ m_effects;
	int m_count;
	int m_radius;
	bool m_lone;
	string m_fx;

	HWPSpecsStrike(UnitPtr unit, SValue& params)
	{
		@m_effects = LoadEffects(unit, params);
		m_count = GetParamInt(unit, params, "count", false, 2);
		m_radius = GetParamInt(unit, params, "radius", false, 60);
		m_lone = GetParamFloat(unit, params, "lone", false, 0.0f) > 0;
		m_fx = GetParamString(unit, params, "fx", false, "effects/generic/other/lightning/lightning_strike_2.effect?brightness=0");
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { PropagateWeaponInformation(m_effects, weapon); }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null && m_count > 0; }

	void Strike(Actor@ owner, Actor@ a, vec2 dir, float intensity, bool husk)
	{
		vec2 at = xy(a.m_unit.GetPosition());
		PlayEffect(m_fx, at);
		PlayEffect("effects/generic/impacts/lightning_impact_5.effect", at);
		ApplyEffects(m_effects, owner, a.m_unit, at, dir, intensity, husk);
	}

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		if (!CanApply(owner, target, pos, dir, intensity))
			return false;
		auto hit = cast<Actor>(target.GetScriptBehavior());
		if (hit is null || hit.Team == owner.Team)
			return false;
		vec2 at = xy(target.GetPosition());
		auto near = HWP::Specs::EnemiesNear(at, m_radius, owner.Team);
		array<Actor@> order;
		array<float> keys;
		for (uint i = 0; i < near.length(); i++)
		{
			if (near[i] is hit)
				continue;
			float k = dist(at, xy(near[i].m_unit.GetPosition()));
			uint j = 0;
			while (j < keys.length() && keys[j] <= k)
				j++;
			order.insertAt(j, near[i]);
			keys.insertAt(j, k);
		}
		if (order.length() == 0)
		{
			if (!m_lone || hit.IsDead())
				return false;
			for (int i = 0; i < m_count; i++)
				Strike(owner, hit, dir, intensity, husk);
			return true;
		}
		for (uint i = 0; i < order.length() && int(i) < m_count; i++)
			Strike(owner, order[i], dir, intensity, husk);
		return true;
	}
}

// Gale Force, on a bow or crossbow attack (the attack trigger in gathering_winds.sval): at the
// level's gw-max Tailwind stacks, extra (bindable) more arrows of projectile along the
// ranger's aim, spread apart by spread degrees, as the attack's weapon (its damage). Shot on
// the ranger's own client (the trigger runs there); the other peers see the hits.
class HWPSpecsGaleForce : IEffect
{
	UnitProducer@ m_proj;
	int m_extra;
	float m_spread;
	uint m_weapon;

	HWPSpecsGaleForce(UnitPtr unit, SValue& params)
	{
		@m_proj = Resources::GetUnitProducer(GetParamString(unit, params, "projectile"));
		m_extra = GetParamInt(unit, params, "extra", false, 0);
		m_spread = GetParamInt(unit, params, "spread", false, 10) * PI / 180.0f;
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { m_weapon = weapon; }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null && m_extra > 0 && m_proj !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		auto def = HWP::Specs::Stack("tailwind");
		if (husk || plr is null || def is null || !CanApply(owner, target, pos, dir, intensity))
			return false;
		int cap = HWP::Specs::BindI(plr, HWP::Specs::GATHERING_WINDS, "gw-max", 0);
		if (cap <= 0 || plr.GetStacks(def) < cap)
			return false;
		vec2 from = xy(plr.m_unit.GetPosition());
		float aim = plr.m_dirAngle;
		for (int i = 0; i < m_extra; i++)
		{
			// +1: one side, +2: both sides
			float ang = aim + m_spread * (i % 2 == 0 ? 1 : -1) * (1 + i / 2);
			auto u = m_proj.Produce(g_scene, xyz(from + vec2(cos(ang), sin(ang)) * 8));
			auto p = cast<IProjectile>(u.GetScriptBehavior());
			if (p is null)
				continue;
			p.Initialize(owner, ProjectileTargetDir(vec2(cos(ang), sin(ang))), 1.0f, false, m_weapon);
			HWP::Specs::g_galeArrows++;
		}
		return true;
	}
}

// Gathering Winds' stack, on an attack (the attack trigger in gathering_winds.sval): only for
// the skills in skills (the two-handed bows' and crossbow's secondaries), as the trigger
// propagates the attack's skill id. Its own client.
class HWPSpecsTailwind : IEffect
{
	array<uint> m_skills;
	uint m_weapon;

	HWPSpecsTailwind(UnitPtr unit, SValue& params)
	{
		auto arr = GetParamArray(unit, params, "skills", true);
		for (uint i = 0; arr !is null && i < arr.length(); i++)
			m_skills.insertLast(HashString(arr[i].GetString()));
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { m_weapon = weapon; }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		if (husk || plr is null || m_skills.find(m_weapon) < 0)
			return false;
		HWP::Specs::AddTailwind(plr);
		return true;
	}
}
