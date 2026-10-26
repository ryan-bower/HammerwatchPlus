// Aim hooks for the local player's skill targeting. The vanilla PlayerTargetingHelper
// (Behaviors/Actors/Player/PlayerTargetingHelper.as) works out an AOE skill's target in
// CalcGamepadTargetPos and CalcMouseTargetPos, and activates the skill in Update when the
// attack button is pressed (or the skill button released, with quickcast). Core already
// swaps the local player's helper for HWPSkillKeysHelper (SkillKeys.as); that helper calls
// these hooks, so a module can steer the reticle or act before the targeting step without
// a second helper class fighting over Player.m_targetHelper.
//
// - OnAdjust: given the position vanilla worked out (gamepad: the stick-driven reticle;
//   mouse: the cursor clamped to the skill's range), return where the reticle goes.
// - OnPreUpdate: runs before the vanilla targeting step each frame of player control.
//   Return true to say this frame's skill input is handled (vanilla Update's own true:
//   CheckUseSkill is skipped), e.g. after activating the targeted skill.
namespace HWP
{
	namespace Aim
	{
		funcdef vec2 Adjust(PlayerTargetingHelper@ helper, Skills::TargetingParams@ params, vec2 pos, bool gamepad);
		funcdef bool PreUpdate(PlayerTargetingHelper@ helper, int dt, vec2 aimDir);

		array<Adjust@> g_adjust;
		array<PreUpdate@> g_preUpdate;

		void OnAdjust(Adjust@ f) { g_adjust.insertLast(f); }
		void OnPreUpdate(PreUpdate@ f) { g_preUpdate.insertLast(f); }

		vec2 Apply(PlayerTargetingHelper@ helper, Skills::TargetingParams@ params, vec2 pos, bool gamepad)
		{
			for (uint i = 0; i < g_adjust.length(); i++)
				pos = g_adjust[i](helper, params, pos, gamepad);
			return pos;
		}

		bool Pre(PlayerTargetingHelper@ helper, int dt, vec2 aimDir)
		{
			for (uint i = 0; i < g_preUpdate.length(); i++)
			{
				if (g_preUpdate[i](helper, dt, aimDir))
					return true;
			}
			return false;
		}

		// What vanilla Update does when the targeted skill is fired: activate it at target,
		// let the other skills' charges go, trigger the cast effects, and stop targeting.
		void FireTargeted(PlayerTargetingHelper@ helper, vec2 target, vec2 aimDir)
		{
			auto skill = helper.m_targetingSkill;
			if (skill is null)
				return;
			if (skill.Activate(target, 1.0f))
			{
				helper.CancelOther(skill, aimDir);
				helper.TriggerModifierEffects(skill);
			}
			skill.m_isActive = false;
			@helper.m_targetingSkill = null;
		}
	}
}
