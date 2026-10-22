// Branding (Warlock): Pyrebrand and Essence Extraction.
// - Pyrebrand (branding/pyrebrand.sval): the cast brands the enemy nearest the aim
//   (HWPSpecsPyrebrand). While a brand is up pb-pct of the warlock's damage to the branded
//   enemy is stored on it (HWPSpecsBrandFeed, on QuantityTrigger::Damage, which runs on the
//   warlock's own client: CompositeActorBehavior calls the local player's DamagedActor), and the
//   skill stays ready (UpdateBrands holds its cooldown at 0). A recast, or the brand running out,
//   sets off the Hellfire Claw: fire for pb-base + the stored damage on every enemy within
//   CLAW_RADIUS of the branded one; then the full cooldown. A branded enemy that dies passes the
//   brand, stored damage and time left, to the nearest enemy within TRANSFER_RADIUS.
//   Combustion (pb-combust): the claw spends every Essence stack for that much more damage and
//   radius each. Proliferation (pb-spread): the brand lasts half as long and a dying brand goes
//   to every enemy within pb-spread, each with the whole stored damage.
// - Essence Extraction (branding/essence_extraction.sval): a magic weapon hit (arcane-tagged:
//   staff, wand, tome, scepter, lantern) is an Essence gain too, once per ee-cd ms, and a gain from a Pyrebranded enemy runs
//   twice: the magic one, and Drain Essence's own melee one (HWPSpecsEssenceHit). A gain is
//   what Drain Essence's hit effects do (GainEssence). Essence Empowerment (ee-emp, HWPSpecsEssenceFire): + ee-emp x the physical damage
//   multiplier to the fire damage multiplier per Essence stack. Released Essence (ee-released):
//   an elite or boss killed by the claw gives that many stacks.
// The brands are the warlock's own client's; the other peers see the pyrebrand debuff (kept
// on by UpdateBrands, the buff list syncs it) and the damage, not the claw's effect.
namespace HWP
{
	namespace Specs
	{
		const uint PYREBRAND = HashString("hwp_wlk_pyrebrand");
		const uint ESSENCE_EXTRACTION = HashString("hwp_wlk_essence_extraction");
		const string ESSENCE = "players/warlock/stacks_warlock.sval:essence";
		const uint DRAIN_ESSENCE = HashString("drain_essence");

		// assumed numbers (not in the design): the brand's time, its search cone and range, the
		// claw's radius, the transfer range and the most brands at once
		const int BRAND_TIME = 6000;
		const float AIM_CONE = 0.866f;   // cos 30 degrees
		const float AIM_RANGE = 250;
		const float NEAR_RANGE = 120;
		const float CLAW_RADIUS = 40;
		const float TRANSFER_RADIUS = 100;
		const uint MAX_BRANDS = 20;
		const int CLAW_KILL_WINDOW = 1000; // a claw's elite victim dying this soon counts as its kill

		class Brand
		{
			Actor@ m_target;
			vec2 m_pos;
			float m_stored;
			int m_left;
		}

		array<Brand@> g_brands;
		HWPSpecsPyrebrand@ g_pyre;   // the cast effect, for its claw effects
		int g_brandFxC = 0;
		int g_essenceC = 0;
		int g_refundMana = 0;
		int g_refundC = 0;
		bool g_resetPyre = false;
		bool g_brandsUp = false;      // brands were up at the end of the last update
		array<Actor@> g_clawVictims;  // elites and bosses the claw hit (Released Essence)
		int g_clawVictimC = 0;

		// counters for `hwp specs`
		int g_claws = 0;
		int g_clawHits = 0;
		int g_lastClaw = 0;
		int g_transfers = 0;
		int g_essenceHits = 0;
		int g_essenceTwice = 0;
		int g_released = 0;

		void ClearBrands()
		{
			g_brands.removeRange(0, g_brands.length());
			@g_pyre = null;
			g_brandFxC = 0;
			g_essenceC = 0;
			g_refundMana = 0;
			g_refundC = 0;
			g_resetPyre = false;
			g_brandsUp = false;
			g_clawVictims.removeRange(0, g_clawVictims.length());
			g_clawVictimC = 0;
			g_claws = g_clawHits = g_lastClaw = g_transfers = g_essenceHits = g_essenceTwice = g_released = 0;
		}

		Brand@ BrandOn(Actor@ a)
		{
			for (uint i = 0; i < g_brands.length(); i++)
			{
				if (g_brands[i].m_target is a)
					return g_brands[i];
			}
			return null;
		}

		void AddBrand(PlayerBase@ plr, Actor@ a, float stored, int left)
		{
			if (a is null || g_brands.length() >= MAX_BRANDS || BrandOn(a) !is null)
				return;
			Brand b;
			@b.m_target = a;
			b.m_pos = xy(a.m_unit.GetPosition());
			b.m_stored = stored;
			b.m_left = left;
			g_brands.insertLast(b);
			Give(plr, a, Buff("pyrebrand"), 1, 400);
		}

		int BrandTime(PlayerBase@ plr)
		{
			return BindF(plr, PYREBRAND, "pb-spread") > 0 ? BRAND_TIME / 2 : BRAND_TIME;
		}

		void FeedBrand(PlayerBase@ plr, Actor@ enemy, int value)
		{
			auto b = BrandOn(enemy);
			if (b is null || plr is null)
				return;
			b.m_stored += value * BindF(plr, PYREBRAND, "pb-pct");
		}

		Skills::PlayerSkill@ PyreSkill(PlayerBase@ plr)
		{
			return cast<Skills::PlayerSkill>(FindSkill(plr, PYREBRAND));
		}

		// mana back after the cast has paid for itself (see g_channelMana in Invocation.as)
		void Refund(PlayerBase@ plr)
		{
			auto sk = PyreSkill(plr);
			if (sk is null)
				return;
			g_refundMana = int(ManaCost(plr, sk) + 0.5f);
			g_refundC = 400;
		}

		// the Hellfire Claw on one brand; true when it hit something
		bool Claw(PlayerBase@ plr, Brand@ b, const string &in why)
		{
			if (plr is null || g_pyre is null)
				return false;
			vec2 at = (b.m_target !is null && !b.m_target.IsDead()) ? xy(b.m_target.m_unit.GetPosition()) : b.m_pos;
			auto ess = Stack(ESSENCE);
			int n = ess !is null ? plr.GetStacks(ess) : 0;
			float combust = BindF(plr, PYREBRAND, "pb-combust");
			float mul = 1.0f + (combust > 0 ? combust * n : 0.0f);
			float radius = CLAW_RADIUS * mul;
			float amount = (BindF(plr, PYREBRAND, "pb-base") + b.m_stored) * mul;

			PlayEffect("players/warlock/effects/demon_tail_impact.effect", at);
			dictionary ps = { { "radius", radius } };
			PlayEffect("players/warlock/effects/war_ritual.effect", at, ps);
			PlaySound3D(Resources::GetSoundEvent("event:/sfx/actors/aberrations/wisps/wisp_fire/wisp_fire_explode"), xyz(at));

			bool released = BindI(plr, ESSENCE_EXTRACTION, "ee-released") > 0;
			auto enemies = EnemiesNear(at, radius, plr.Team);
			for (uint i = 0; i < enemies.length(); i++)
			{
				auto a = enemies[i];
				ApplyEffects(g_pyre.m_claw, plr, a.m_unit, xy(a.m_unit.GetPosition()), vec2(0, -1), amount / 100.0f, false);
				g_clawHits++;
				// the host decides the kill, so a client sees it frames later: watched in UpdateBrands
				if (released && IsEliteOrBoss(a) && g_clawVictims.findByRef(a) < 0)
					g_clawVictims.insertLast(a);
			}
			if (released && g_clawVictims.length() > 0)
				g_clawVictimC = CLAW_KILL_WINDOW;
			// the claw had Empowerment's fire from these stacks; now it spends them
			if (combust > 0 && n > 0 && ess !is null)
			{
				plr.AddStacks(plr, ess, -n);
				// A recast can resolve more brands before the next native stat update.
				plr.m_record.RefreshStats();
			}
			g_claws++;
			g_lastClaw = int(amount + 0.5f);
			Log("specs", "pyrebrand: claw (" + why + ") " + g_lastClaw + " fire, radius " + int(radius)
				+ ", " + enemies.length() + " hit" + (combust > 0 ? ", " + n + " essence spent" : ""));
			return enemies.length() > 0;
		}

		void ClawAll(PlayerBase@ plr, const string &in why)
		{
			array<Brand@> brands = g_brands;   // a copy: the claws can add brands
			g_brands.removeRange(0, g_brands.length());
			g_brandsUp = false;                // the recast's own cooldown is the skill's
			for (uint i = 0; i < brands.length(); i++)
				Claw(plr, brands[i], why);
		}

		// a branded enemy died: the brand goes on (Proliferation: to all of them)
		void PassOn(PlayerBase@ plr, Brand@ b)
		{
			float spread = BindF(plr, PYREBRAND, "pb-spread");
			auto enemies = EnemiesNear(b.m_pos, spread > 0 ? spread : TRANSFER_RADIUS, plr.Team);
			Actor@ best = null;
			float bestD = 0;
			int passed = 0;
			for (uint i = 0; i < enemies.length(); i++)
			{
				if (BrandOn(enemies[i]) !is null)
					continue;
				if (spread > 0)
				{
					AddBrand(plr, enemies[i], b.m_stored, BrandTime(plr));
					passed++;
					continue;
				}
				float d = dist(b.m_pos, xy(enemies[i].m_unit.GetPosition()));
				if (best is null || d < bestD)
				{
					@best = enemies[i];
					bestD = d;
				}
			}
			if (best !is null)
			{
				AddBrand(plr, best, b.m_stored, b.m_left);
				passed++;
			}
			g_transfers += passed;
			Log("specs", "pyrebrand: target died, " + int(b.m_stored + 0.5f) + " stored passed to " + passed);
		}

		// one Essence gain, what Drain Essence's hit effects do (players/warlock/skills/
		// drain_essence.sval): a stack, Drain Blood's bleed on the enemy, Life and Energy Siphon's
		// health and mana, the sound and the gain effect. Its binds are read off Drain Essence.
		void GainEssence(PlayerBase@ plr, Actor@ enemy)
		{
			auto ess = Stack(ESSENCE);
			if (ess is null)
				return;
			plr.AddStacks(plr, ess, 1);
			auto bleed = Stack("tweak/buffs/stacks_actors.sval:bleeding");
			int bleeds = BindI(plr, DRAIN_ESSENCE, "bleeding-stacks");
			if (bleed !is null && bleeds > 0 && enemy !is null && !enemy.IsDead()
				&& randf() <= BindF(plr, DRAIN_ESSENCE, "bleeding-chance"))
				enemy.AddStacks(plr, bleed, bleeds);
			float life = BindF(plr, DRAIN_ESSENCE, "drain-life-amount");
			if (life > 0 && plr.GetHealth() < 1.0f)
				plr.Heal(int(life * plr.GetMaxHp()), false);
			float mana = BindF(plr, DRAIN_ESSENCE, "drain-energy-amount");
			if (mana > 0)
				plr.GiveMana(int(mana * plr.GetMaxMana()), false);
			PlaySound3D(Resources::GetSoundEvent("event:/sfx/player/classes/warlock/drain_essence/drain_essence"), plr.m_unit.GetPosition());
			PlayEffect("players/warlock/effects/gain_essence.effect", xy(plr.m_unit.GetPosition()));
		}

		void UpdateBrands(int ms)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			g_essenceC -= ms;
			g_refundC -= ms;
			if (g_refundMana > 0 && g_refundC <= 0)
			{
				if (plr !is null && !plr.IsDead())
					plr.m_record.mana = clamp(plr.m_record.mana + g_refundMana / float(max(1, plr.m_record.MaxMana())), 0.0f, 1.0f);
				g_refundMana = 0;
			}
			if (plr is null || plr.IsDead())
			{
				g_brands.removeRange(0, g_brands.length());
				g_clawVictims.removeRange(0, g_clawVictims.length());
				return;
			}

			// Released Essence: a claw's elite or boss victim that has died since
			if (g_clawVictims.length() > 0)
			{
				g_clawVictimC -= ms;
				auto ess = Stack(ESSENCE);
				int released = BindI(plr, ESSENCE_EXTRACTION, "ee-released");
				for (int i = int(g_clawVictims.length()) - 1; i >= 0; i--)
				{
					if (!g_clawVictims[i].IsDead())
						continue;
					if (ess !is null && released > 0)
					{
						plr.AddStacks(plr, ess, released);
						g_released += released;
					}
					g_clawVictims.removeAt(i);
				}
				if (g_clawVictimC <= 0)
					g_clawVictims.removeRange(0, g_clawVictims.length());
			}

			auto sk = PyreSkill(plr);
			if (g_resetPyre && sk !is null && sk.m_castingT < 0)
			{
				sk.m_cooldownC = 0;
				g_resetPyre = false;
			}

			// brands running out are all taken off before any claw: a claw's damage would feed
			// the others' stores (HWPSpecsBrandFeed) and they would compound
			array<Brand@> expired;
			for (int i = int(g_brands.length()) - 1; i >= 0; i--)
			{
				auto b = g_brands[i];
				if (b.m_target is null || b.m_target.IsDead() || !b.m_target.m_unit.IsValid())
				{
					g_brands.removeAt(i);
					PassOn(plr, b);
					continue;
				}
				b.m_pos = xy(b.m_target.m_unit.GetPosition());
				b.m_left -= ms;
				if (b.m_left <= 0)
				{
					g_brands.removeAt(i);
					expired.insertLast(b);
				}
			}
			for (uint i = 0; i < expired.length(); i++)
				Claw(plr, expired[i], "expired");

			g_brandFxC -= ms;
			if (g_brandFxC <= 0)
			{
				g_brandFxC = 150;
				auto def = Buff("pyrebrand");
				for (uint i = 0; i < g_brands.length(); i++)
					Give(plr, g_brands[i].m_target, def, 1, 400);
			}

			if (sk is null || sk.m_castingT >= 0)
				return;
			// held ready while a brand is up; the full cooldown once the last one is gone, however
			// it went (ran out, or died with nobody near to pass it to)
			if (g_brands.length() > 0)
				sk.m_cooldownC = 0;
			else if (g_brandsUp)
				sk.m_cooldownC = max(sk.m_cooldownC, int(sk.m_cooldown * sk.m_modCooldownMul));
			g_brandsUp = g_brands.length() > 0;
		}

		Actor@ AimTarget(PlayerBase@ plr, vec2 dir)
		{
			vec2 from = xy(plr.m_unit.GetPosition());
			if (length(dir) < 0.01f)
				dir = vec2(cos(plr.m_dirAngle), sin(plr.m_dirAngle));
			dir = normalize(dir);
			Actor@ best = null;
			float bestD = 0;
			auto enemies = EnemiesNear(from, AIM_RANGE, plr.Team);
			for (uint i = 0; i < enemies.length(); i++)
			{
				vec2 d = xy(enemies[i].m_unit.GetPosition()) - from;
				float l = length(d);
				if (l > 0.01f && dot(d / l, dir) < AIM_CONE)
					continue;
				if (best is null || l < bestD)
				{
					@best = enemies[i];
					bestD = l;
				}
			}
			if (best !is null)
				return best;
			for (uint i = 0; i < enemies.length(); i++)
			{
				float l = dist(from, xy(enemies[i].m_unit.GetPosition()));
				if (l <= NEAR_RANGE && (best is null || l < bestD))
				{
					@best = enemies[i];
					bestD = l;
				}
			}
			return best;
		}
	}
}

// Pyrebrand's cast: brands the enemy at the aim, or sets off the brands that are up (and gives
// the recast's mana back). The child "claw" effects are the claw's, at intensity damage / 100.
class HWPSpecsPyrebrand : IEffect
{
	EffectList@ m_claw;

	HWPSpecsPyrebrand(UnitPtr unit, SValue& params)
	{
		@m_claw = LoadEffects(unit, params, "claw-");
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { PropagateWeaponInformation(m_claw, weapon); }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		if (plr is null || husk || !HWP::Specs::IsLocal(owner))
			return true;
		@HWP::Specs::g_pyre = this;
		if (HWP::Specs::g_brands.length() > 0)
		{
			HWP::Specs::ClawAll(plr, "recast");
			HWP::Specs::Refund(plr);
			return true;
		}
		auto a = HWP::Specs::AimTarget(plr, dir);
		if (a is null)
		{
			HWP::Specs::Refund(plr);
			HWP::Specs::g_resetPyre = true;
			HWP::Log("specs", "pyrebrand: no target");
			return false;
		}
		HWP::Specs::AddBrand(plr, a, 0, HWP::Specs::BrandTime(plr));
		PlayEffect("players/warlock/effects/demon_tail_impact.effect", xy(a.m_unit.GetPosition()));
		HWP::Log("specs", "pyrebrand: branded " + (HWP::Specs::IsEliteOrBoss(a) ? "an elite" : "an enemy")
			+ " for " + HWP::Specs::BrandTime(plr) + " ms");
		return true;
	}
}

// On QuantityTrigger::Damage (the warlock's damage dealt): feeds the brand on the enemy hit
class HWPSpecsBrandFeed : Modifiers::TriggerEffectBase
{
	HWPSpecsBrandFeed(UnitPtr unit, SValue& params)
	{
		@m_params = params;
		m_quantityTrigger = Modifiers::QuantityTrigger::Damage;
	}

	Modifiers::TriggerEffectState@ MakeTriggerEffectState() override { return Modifiers::TriggerEffectState(); }

	void TriggerQuantityEffects(Modifiers::TriggerEffectState@ state, Actor@ owner, Actor@ enemy, Modifiers::QuantityTrigger trigger, int value, uint id, Skills::Skill@ skill) override
	{
		if (trigger != Modifiers::QuantityTrigger::Damage || enemy is null || value <= 0 || !HWP::Specs::IsLocal(owner))
			return;
		HWP::Specs::FeedBrand(cast<PlayerBase>(owner), enemy, value);
	}
}

// Essence Extraction (SkillTriggerEffect). "magic" (an arcane-tagged weapon's hit): an Essence
// gain once per ee-cd ms, two from a Pyrebranded enemy. Otherwise (a melee hit or melee spell
// hit, on Drain Essence's own 250 ms timeout, whose trigger gives the first gain): one more
// gain from a Pyrebranded enemy.
class HWPSpecsEssenceHit : IEffect
{
	bool m_magic;

	HWPSpecsEssenceHit(UnitPtr unit, SValue& params)
	{
		m_magic = GetParamBool(unit, params, "magic", false, false);
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		auto a = cast<Actor>(target.GetScriptBehavior());
		if (plr is null || a is null || husk || !HWP::Specs::IsLocal(owner) || a.Team == owner.Team)
			return false;
		bool branded = HWP::Specs::BrandOn(a) !is null;
		if (!m_magic)
		{
			if (!branded)
				return false;
			HWP::Specs::GainEssence(plr, a);
			HWP::Specs::g_essenceTwice++;
			return true;
		}
		if (HWP::Specs::g_essenceC > 0)
			return false;
		HWP::Specs::GainEssence(plr, a);
		if (branded)
		{
			HWP::Specs::GainEssence(plr, a);
			HWP::Specs::g_essenceTwice++;
		}
		HWP::Specs::g_essenceC = HWP::Specs::BindI(plr, HWP::Specs::ESSENCE_EXTRACTION, "ee-cd", 2000);
		HWP::Specs::g_essenceHits++;
		return true;
	}
}

// Essence Empowerment, put into the Essence stack (InjectModifiersIntoStack): the fire damage
// multiplier + per-stack x the physical damage multiplier for each stack. The stack's own
// intensity is (stacks - 1) / (max - 1), and Essence Harvester moves the max, so this counts
// the stacks itself. The stack's DummyModifier refreshes the modifiers on every change.
class HWPSpecsEssenceFire : Modifiers::ConvertStat
{
	float m_per;

	HWPSpecsEssenceFire(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		m_per = GetParamFloat(unit, params, "per-stack", false, 0.0f);
	}

	int Stacks(PlayerRecord@ player)
	{
		auto plr = cast<PlayerBase>(player.actor);
		auto def = HWP::Specs::Stack(HWP::Specs::ESSENCE);
		return (plr is null || def is null) ? 0 : plr.GetStacks(def);
	}

	void ModifyDetail(PlayerRecord@ player, PlayerStatsDetail@ stats, float intensity) override { }

	void Modify(PlayerRecord@ player, PlayerStats@ stats, float intensity) override
	{
		stats.FireDamageMul += stats.PhysicalDamageMul * m_per * Stacks(player);
	}
}
