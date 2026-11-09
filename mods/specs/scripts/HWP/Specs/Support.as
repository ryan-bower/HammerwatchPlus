// Recipient-authoritative shield pools and shared native Killing Spree.
// Never mutate global buff/stack definitions: each local recipient owns its pool.
namespace HWP
{
	namespace Specs
	{
		const string SPREE = "players/warrior/stacks_warrior.sval:killing_spree";
		const uint SPREE_SKILL = HashString("killing_spree");
		float g_standardShield = 0, g_soulShield = 0;
		int g_standardShieldLeft = 0, g_soulShieldLeft = 0;
		float g_sharedDamage = 0, g_sharedCrit = 0, g_sharedRegen = 0;
		int g_sharedDuration = 0;
		int g_sharedScaledDuration = 0;
		bool g_sharedSpree = false;
		int g_rallyC = 0;

		float SpreeBind(PlayerBase@ p, const string &in key, float fallback)
		{
			auto value = Bind(p, SPREE_SKILL, key);
			return value !is null && value.GetType() == SValueType::Vector2 ? value.GetVector2().y : fallback;
		}

		int SupportDuration(PlayerBase@ p, int duration)
		{
			return int(duration * p.m_record.GetModifiers().BuffScale(p));
		}

		void Shield(PlayerBase@ p, float gain, float cap, int duration, bool soul = false, float healthBasis = -1)
		{
			if (!IsLocal(p) || p.IsDead())
				return;
			float hp = healthBasis > 0 ? healthBasis : p.GetMaxHp();
			if (soul)
			{
				g_soulShield = min(hp * cap, g_soulShield + hp * gain);
				g_soulShieldLeft = SupportDuration(p, duration);
			}
			else
			{
				// Multiple origins/sources replenish, never add separate Standard pools.
				g_standardShield = max(g_standardShield, hp * min(gain, cap));
				g_standardShieldLeft = max(g_standardShieldLeft, SupportDuration(p, duration));
			}
			Give(p, p, Buff(soul ? "soul_guard" : "standard_shield"), 1,
				soul ? g_soulShieldLeft : g_standardShieldLeft);
			Give(p, p, Buff("support_shield"), 1, max(g_soulShieldLeft, g_standardShieldLeft));
			PlayEffect("players/warlock/effects/gain_essence.effect", xy(p.m_unit.GetPosition()));
		}

		void EssenceSupport(PlayerBase@ p, int count)
		{
			float guard = BindF(p, ESSENCE_EXTRACTION, "ee-guard");
			if (guard > 0)
				Shield(p, guard * count, guard * 5, 4000, true);
			int stride = BindI(p, ESSENCE_EXTRACTION, "ee-stride");
			if (stride > 0)
				Give(p, p, Buff("soul_stride_" + stride), 1, 3000);
		}

		void RefreshSharedSpree(PlayerBase@ p, int count)
		{
			auto def = Stack(SPREE);
			if (count > 0)
				p.AddStacks(p, def, count);
			for (uint i = 0; i < p.m_buffs.m_stacks.length(); i++)
			{
				auto s = p.m_buffs.m_stacks[i];
				if (s.m_def is def)
					s.m_timerTickC = max(s.m_timerTickC, max(g_sharedScaledDuration, SupportDuration(p, g_sharedDuration)));
			}
		}

		void Rally(PlayerBase@ source, PlayerBase@ recipient, int count)
		{
			if (!IsLocal(recipient) || count <= 0 || !Learned(source, SPREE_SKILL))
				return;
			// Keep the strongest inherited components until this one native pool expires.
			g_sharedDamage = max(g_sharedDamage, SpreeBind(source, "spree-dmg", 1) - 1);
			g_sharedCrit = max(g_sharedCrit, SpreeBind(source, "spree-crit-chance", 0));
			g_sharedRegen = max(g_sharedRegen, SpreeBind(source, "stack-regen", 1) - 1);
			g_sharedDuration = max(g_sharedDuration, 6000 + BindI(source, SPREE_SKILL, "stack-duration-add"));
			g_sharedScaledDuration = max(g_sharedScaledDuration, SupportDuration(recipient, g_sharedDuration));
			g_sharedSpree = true;
			// Multiple Bannerlords share a recipient-side grant cadence.
			if (g_rallyC <= 0) { RefreshSharedSpree(recipient, count); g_rallyC = 3000; }
			else RefreshSharedSpree(recipient, 0);
			Give(recipient, recipient, Buff("rallied_spree"), 1, 400);
			recipient.m_record.RefreshStats();
		}

		void ClearSupport()
		{
			g_standardShield = g_soulShield = 0;
			g_standardShieldLeft = g_soulShieldLeft = 0;
			g_sharedDamage = g_sharedCrit = g_sharedRegen = 0;
			g_sharedDuration = 0;
			g_sharedScaledDuration = 0;
			g_sharedSpree = false;
			g_rallyC = 0;
			HWP::AllyStatus::ReportShield(0);
		}

		// the pool as a fraction of the bar the party sees: record.hp, which Living Mana keeps at
		// the mana fraction (UpdateArcane)
		void ReportShield(PlayerBase@ p)
		{
			float pool = Learned(p, LIVING_MANA) ? p.m_record.MaxMana() : p.GetMaxHp();
			HWP::AllyStatus::ReportShield((g_standardShield + g_soulShield) / max(1.0f, pool));
		}

		void UpdateSupport(int ms)
		{
			auto p = cast<PlayerBase>(GetLocalPlayer());
			if (p is null || p.IsDead()) { ClearSupport(); return; }
			g_standardShieldLeft -= ms;
			g_rallyC -= ms;
			g_soulShieldLeft -= ms;
			if (g_standardShieldLeft <= 0) g_standardShield = 0;
			if (g_soulShieldLeft <= 0) g_soulShield = 0;
			ReportShield(p);
			if (!g_sharedSpree) return;
			if (p.GetStacks(Stack(SPREE)) <= 0)
			{
				g_sharedSpree = false;
				g_sharedDamage = g_sharedCrit = g_sharedRegen = 0;
				g_sharedDuration = 0;
				g_sharedScaledDuration = 0;
				p.m_record.RefreshStats();
				return;
			}
			Give(p, p, Buff("rallied_spree"), 1, 400);
		}
	}
}

// An allied aura upgrades an owner's passive to the stronger tier, rather than
// multiplying a second Crusade bonus onto it. Other duration modifiers still work.
class HWPSpecsCrusadeDuration : Modifiers::Modifier
{
	float m_scale;
	HWPSpecsCrusadeDuration(UnitPtr unit, SValue& params) { m_scale = GetParamFloat(unit, params, "scale", true); }
	Modifiers::ModDynamism HasBuffScale() override { return Modifiers::ModDynamism::Dynamic; }
	float BuffScale(PlayerBase@ p, float intensity) override
	{
		auto value = HWP::Specs::Bind(p, HWP::Specs::CRUSADE, "crusade");
		float own = value !is null && value.GetType() == SValueType::Vector2 ? value.GetVector2().x : 1;
		return max(1.0f, m_scale / max(1.0f, own));
	}
}

class HWPSpecsShield : Modifiers::Modifier
{
	HWPSpecsShield(UnitPtr unit, SValue& params) {}
	Modifiers::ModDynamism HasDamageTakenMul() override { return Modifiers::ModDynamism::Dynamic; }
	float DamageTakenMul(PlayerBase@ p, Actor@ attacker, DamageInfo &di, float intensity) override
	{
		if (!HWP::Specs::IsLocal(p)) return 1;
		float damage = di.PhysicalDamage + di.FireDamage + di.IceDamage + di.LightningDamage + di.PoisonDamage + di.PureDamage;
		if (damage <= 0) return 1;
		float blocked = min(damage, HWP::Specs::g_standardShield);
		HWP::Specs::g_standardShield -= blocked;
		float soul = min(damage - blocked, HWP::Specs::g_soulShield);
		HWP::Specs::g_soulShield -= soul;
		return 1 - (blocked + soul) / damage;
	}
}

class HWPSpecsEssenceSupport : Modifiers::TriggerEffectBase
{
	HWPSpecsEssenceSupport(UnitPtr unit, SValue& params)
	{
		@m_params = params;
		m_quantityTrigger = Modifiers::QuantityTrigger::StackGained;
	}
	Modifiers::TriggerEffectState@ MakeTriggerEffectState() override { return Modifiers::TriggerEffectState(); }
	void TriggerQuantityEffects(Modifiers::TriggerEffectState@ state, Actor@ owner, Actor@ enemy, Modifiers::QuantityTrigger trigger, int value, uint id, Skills::Skill@ skill) override
	{
		auto essence = HWP::Specs::Stack(HWP::Specs::ESSENCE);
		if (HWP::Specs::IsLocal(owner) && value > 0 && essence !is null && id == essence.m_idHash)
			HWP::Specs::EssenceSupport(cast<PlayerBase>(owner), value);
	}
}

class HWPSpecsRalliedKill : Modifiers::TriggerEffectBase
{
	HWPSpecsRalliedKill(UnitPtr unit, SValue& params) { @m_params = params; m_trigger = Modifiers::EffectTrigger::Kill; }
	Modifiers::TriggerEffectState@ MakeTriggerEffectState() override { return Modifiers::TriggerEffectState(); }
	void TriggerEffects(Modifiers::TriggerEffectState@ state, Actor@ owner, Actor@ enemy, Modifiers::EffectTrigger trigger, Skills::Skill@ skill) override
	{
		if (!HWP::Specs::IsLocal(owner) || !HWP::Specs::g_sharedSpree) return;
		auto p = cast<PlayerBase>(owner);
		// Native Warriors already have their own kill trigger: don't award twice.
		HWP::Specs::RefreshSharedSpree(p, HWP::Specs::Learned(p, HWP::Specs::SPREE_SKILL) ? 0 : 1);
	}
}

class HWPSpecsRalliedStats : Modifiers::StatModifier
{
	HWPSpecsRalliedStats(UnitPtr unit, SValue& params) { super(unit, params); Ordering = int(Modifiers::ModifierOrdering::AttribMul); }
	void Modify(PlayerRecord@ record, PlayerStats@ stats, float intensity) override
	{
		auto p = cast<PlayerBase>(GetLocalPlayer());
		if (p is null || p.m_record !is record || !HWP::Specs::g_sharedSpree) return;
		int n = p.GetStacks(HWP::Specs::Stack(HWP::Specs::SPREE));
		float fraction = n / 10.0f;
		float nativeCrit = HWP::Specs::SpreeBind(p, "spree-crit-chance", 0) * fraction;
		float sharedCrit = max(nativeCrit, HWP::Specs::g_sharedCrit * fraction);
		float critMul = (1 - sharedCrit) / max(0.001f, 1 - nativeCrit);
		stats.SpellCritChance = 1 - (1 - stats.SpellCritChance) * critMul;
		stats.MainHand.CritChance = 1 - (1 - stats.MainHand.CritChance) * critMul;
		stats.OffHand.CritChance = 1 - (1 - stats.OffHand.CritChance) * critMul;
		// Native Killer Physique interpolates 1.0 -> 1.2/1.4/1.8 over
		// stack intensity (n - 1) / 9, rather than the planner's per-stack shorthand.
		float regenFraction = max(0, n - 1) / 9.0f;
		float nativeRegen = (HWP::Specs::SpreeBind(p, "stack-regen", 1) - 1) * regenFraction;
		stats.HealthRegen *= (1 + max(nativeRegen, HWP::Specs::g_sharedRegen * regenFraction)) / (1 + nativeRegen);
	}
}

class HWPSpecsRalliedDamage : Modifiers::Modifier
{
	HWPSpecsRalliedDamage(UnitPtr unit, SValue& params) {}
	Modifiers::ModDynamism HasDamageMul() override { return Modifiers::ModDynamism::Dynamic; }
	vec2 DamageMul(PlayerBase@ p, Actor@ enemy, float intensity) override
	{
		if (!HWP::Specs::IsLocal(p) || !HWP::Specs::g_sharedSpree) return vec2(1);
		float fraction = p.GetStacks(HWP::Specs::Stack(HWP::Specs::SPREE)) / 10.0f;
		float own = (HWP::Specs::SpreeBind(p, "spree-dmg", 1) - 1) * fraction;
		return vec2((1 + max(own, HWP::Specs::g_sharedDamage * fraction)) / (1 + own));
	}
}

class HWPSpecsRalliedGain : Modifiers::TriggerEffectBase
{
	HWPSpecsRalliedGain(UnitPtr unit, SValue& params) { @m_params = params; m_quantityTrigger = Modifiers::QuantityTrigger::StackGained; }
	Modifiers::TriggerEffectState@ MakeTriggerEffectState() override { return Modifiers::TriggerEffectState(); }
	void TriggerQuantityEffects(Modifiers::TriggerEffectState@ state, Actor@ owner, Actor@ enemy, Modifiers::QuantityTrigger trigger, int value, uint id, Skills::Skill@ skill) override
	{
		auto def = HWP::Specs::Stack(HWP::Specs::SPREE);
		if (HWP::Specs::IsLocal(owner) && HWP::Specs::g_sharedSpree && def !is null && id == def.m_idHash && value > 0)
			HWP::Specs::RefreshSharedSpree(cast<PlayerBase>(owner), 0);
	}
}
