// Winddancer (Rogue): Protective Gale and Second Wind. Both are data (svals); the script is
// the one part a buff def cannot do by itself:
// - Shared Breath (a Second Wind orb): teammates the rogue's Protective Gale reaches get
//   gale_share_<sw-heal>_<sw-breeze-lvl> (buffs_specs.sval), whose evade trigger releases the
//   rogue's gust from the teammate. A buff def never sees binds and a trigger in it always runs
//   at intensity 1 (Modifiers.as, TriggerEffectState), so each heal and breeze level is a def of
//   its own, picked here from the rogue's Second Wind.
//   Each teammate's gust has its own 4 s timeout (the planner wants it to share the rogue's:
//   a simplification, every peer would have to agree on one timer).
namespace HWP
{
	namespace Specs
	{
		const uint SECOND_WIND = HashString("hwp_rog_second_wind");
	}
}

// In Protective Gale's Explode, on each player it reaches: the owner's peer and the target's
// both run it, Give keeps the target's own client the one to apply
class HWPSpecsShareBreath : IEffect
{
	int m_duration;

	HWPSpecsShareBreath(UnitPtr unit, SValue& params)
	{
		m_duration = GetParamInt(unit, params, "duration", false, -1);
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) {}

	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override
	{
		return owner !is null && target.IsValid() && target != owner.m_unit;
	}

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		if (!CanApply(owner, target, pos, dir, intensity))
			return false;
		auto plr = cast<PlayerBase>(owner);
		if (HWP::Specs::BindF(plr, HWP::Specs::SECOND_WIND, "sw-share", 0) <= 0)
			return false;
		// the defs: heal 20-60 in steps of 10, breeze 0-3
		int heal = clamp((HWP::Specs::BindI(plr, HWP::Specs::SECOND_WIND, "sw-heal", 20) + 5) / 10 * 10, 20, 60);
		int breeze = clamp(HWP::Specs::BindI(plr, HWP::Specs::SECOND_WIND, "sw-breeze-lvl", 0), 0, 3);
		auto actor = cast<Actor>(target.GetScriptBehavior());
		auto def = HWP::Specs::Buff("gale_share_" + heal + "_" + breeze);
		if (def is null)
		{
			HWP::LogError("specs", "shared breath: no buff gale_share_" + heal + "_" + breeze);
			return false;
		}
		bool ok = HWP::Specs::Give(owner, actor, def, 1, m_duration);
		if (ok)
			HWP::Log("specs", "shared breath: gust " + heal + " (breeze " + breeze + ") for " + m_duration + " ms");
		return ok;
	}
}
