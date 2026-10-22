// Deadeye (Ranger; the ids keep the build's stormbringer name): Lightning Arrow and Gathering Winds.
// - Lightning Arrow (stormbringer/electric_circuit.sval, the arrow stormbringer/circuit.unit):
//   a fan of 3 piercing arrows. HWPSpecsReturn turns each one around at its range or at a wall
//   and flies it back to where it was shot, hitting everything again (Boomerang:
//   ec-return-mul on the way back). Every hit runs HWPSpecsStrike: lightning on up to
//   ec-strikes other enemies within ec-radius of the one hit (Storm Arrow raises both;
//   Boomerang's ec-lone strikes a lone target itself). Tailwind Catch (ec-catch): the
//   ranger catching the arrow on its way back adds a Tailwind stack.
// - Gathering Winds (stormbringer/gathering_winds.sval): every TAILWIND_KILLS kills add a
//   Tailwind stack (HWPSpecsKillTailwind), up to TAILWIND_MAX, each lasting TAILWIND_MS on its
//   own (g_twExp; a stack past the cap replaces the oldest). The speed is tailwind_<gw-lvl>_<n>
//   (buffs_specs.sval: 2-4% move, attack and cast speed per stack by level), kept on by
//   UpdateTailwind. Gale Force (gw-gale): at TAILWIND_MAX the bow and crossbow attacks shoot
//   gw-gale more arrows (HWPSpecsGaleForce). Wind Ward (gw-ward): wind_ward at gw-ward x
//   stacks damage taken off.
namespace HWP
{
	namespace Specs
	{
		const uint GATHERING_WINDS = HashString("hwp_ran_gathering_winds");
		const int TAILWIND_MAX = 5;
		const int TAILWIND_MS = 4000;
		const int TAILWIND_KILLS = 5;

		// counts since the session started, for `hwp specs` (the checks read them)
		int g_circuitReturns = 0;
		int g_circuitCatches = 0;
		int g_circuitBackHits = 0;
		int g_galeArrows = 0;
		int g_twKills = 0;

		// when each Tailwind stack ends (g_twNow ms), oldest first
		array<int> g_twExp;
		int g_twNow = 0;

		void ClearTailwind()
		{
			g_twExp.removeRange(0, g_twExp.length());
			g_twNow = 0;
			g_twKills = 0;
			g_wardC = 0;
		}

		// g_twExp follows the stack's count when something else changed it (givestacks, the
		// def's own timer, a death): the oldest go first, an added one gets a full timer
		void FollowTailwind(int n)
		{
			while (int(g_twExp.length()) > n)
				g_twExp.removeAt(0);
			while (int(g_twExp.length()) < n)
				g_twExp.insertLast(g_twNow + TAILWIND_MS);
		}

		// one Tailwind stack for TAILWIND_MS; at the cap it replaces the oldest (a take and an
		// add, so the stack's own timer starts again too)
		void AddTailwind(PlayerBase@ plr)
		{
			auto def = Stack("tailwind");
			if (plr is null || def is null || plr.IsDead() || BindI(plr, GATHERING_WINDS, "gw-lvl", 0) <= 0)
				return;
			FollowTailwind(plr.GetStacks(def));
			g_twExp.insertLast(g_twNow + TAILWIND_MS);
			if (int(g_twExp.length()) > TAILWIND_MAX)
			{
				g_twExp.removeAt(0);
				plr.AddStacks(plr, def, -1);
			}
			plr.AddStacks(plr, def, 1);
		}

		int g_wardC = 0;
		void UpdateTailwind(int ms)
		{
			g_twNow += ms;
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			auto def = Stack("tailwind");
			if (plr is null || def is null)
				return;
			FollowTailwind(plr.GetStacks(def));
			int gone = 0;
			while (g_twExp.length() > 0 && g_twExp[0] <= g_twNow)
			{
				g_twExp.removeAt(0);
				gone++;
			}
			if (gone > 0)
				plr.AddStacks(plr, def, -gone);

			g_wardC -= ms;
			if (g_wardC > 0)
				return;
			g_wardC = 250;
			int n = min(TAILWIND_MAX, plr.GetStacks(def));
			if (plr.IsDead() || n <= 0)
				return;
			int lvl = BindI(plr, GATHERING_WINDS, "gw-lvl", 0);
			if (lvl > 0)
				Give(plr, plr, Buff("tailwind_" + lvl + "_" + n), 1, 600);
			float ward = BindF(plr, GATHERING_WINDS, "gw-ward", 0);
			if (ward > 0)
				Give(plr, plr, Buff("wind_ward"), ward * n, 600);
		}
	}
}

// Lightning Arrow's return. The arrow flies out for its ttl (its range), or until a wall, then
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
	int m_turnAt = -1;
	vec2 m_turnPos;

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
		m_turnAt = int(g_scene.GetTime());
		m_turnPos = m_proj.m_pos;
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
		// NewProjectile raycasts the entire outbound step before calling Update.
		// Its OnBounce can already have turned us during that step. That segment
		// is still outbound and must not catch the ranger or end a return at home.
		vec2 step = to - from;
		if (m_turnAt == int(g_scene.GetTime()) || dot(step, m_proj.m_dir) <= 0)
			return;
		auto owner = cast<PlayerBase>(m_proj.m_owner);
		vec2 nearest = to;
		if (owner !is null && dot(step, step) > 0.0001f)
		{
			vec2 at = xy(owner.m_unit.GetPosition());
			nearest = from + step * clamp(dot(at - from, step) / dot(step, step), 0.0f, 1.0f);
		}
		if (owner !is null && !owner.IsDead() && dist(nearest, xy(owner.m_unit.GetPosition())) <= 12)
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
		if (m_back && m_turnAt == int(g_scene.GetTime()))
		{
			// More hits from the same native raycast are still the old outbound
			// segment, including a second fixture on the wall we just reached.
			// Keep the first turn point and direction instead of ending the arrow.
			m_proj.m_bounces++;
			m_proj.m_pos = m_turnPos;
			m_proj.m_lastCollision = UnitPtr();
			vec2 home = m_home - m_turnPos;
			if (length(home) > 0.1f)
				m_proj.SetDirection(normalize(home));
			return;
		}
		if (cast<IProjectile>(unit.GetScriptBehavior()) !is null)
		{
			m_proj.m_bounces++;
			// Native reflection is its own inverse, including oblique collisions.
			m_proj.SetDirection(m_proj.m_dir - normal * (2 * dot(m_proj.m_dir, normal)));
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

// Gale Force, on a bow or crossbow attack (the attack trigger in gathering_winds.sval): at
// TAILWIND_MAX Tailwind stacks, extra (bindable) more arrows of projectile along the
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
		if (plr.GetStacks(def) < HWP::Specs::TAILWIND_MAX)
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

// Gathering Winds' stack, on a kill (the kill trigger in gathering_winds.sval): every
// TAILWIND_KILLS kills of the ranger's add one. Its own client.
class HWPSpecsKillTailwind : IEffect
{
	HWPSpecsKillTailwind(UnitPtr unit, SValue& params) {}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) {}
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		if (husk || plr is null || !HWP::Specs::IsLocal(plr))
			return false;
		HWP::Specs::g_twKills++;
		if (HWP::Specs::g_twKills % HWP::Specs::TAILWIND_KILLS == 0)
			HWP::Specs::AddTailwind(plr);
		return true;
	}
}
