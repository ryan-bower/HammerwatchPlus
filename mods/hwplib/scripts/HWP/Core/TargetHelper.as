// The local player's PlayerTargetingHelper (Behaviors/Actors/Player/PlayerTargetingHelper.as)
// is swapped for HWPTargetingHelper once its actor exists (the Player ctor makes a vanilla
// one, again on every spawn; script methods are virtual). The helper changes nothing by
// itself: it runs the hooks modules register, so several modules share one helper instead
// of fighting over Player.m_targetHelper.
//
// - OnUpdate: first thing in every frame of player control (Player.as calls the helper's
//   Update only while the controls are not frozen), e.g. polling raw keys.
// - OnSkillInput: rewrites the ButtonState vanilla GetSkillInput gives a skill (the
//   classes module's Skill 4-6 keys, mods/classes/scripts/HWP/Classes/SkillKeys.as).
// - The aim hooks (Aim.as) get the reticle vanilla worked out, and run before the
//   vanilla targeting step.
namespace HWP
{
	namespace TargetHelper
	{
		funcdef void Tick(PlayerTargetingHelper@ helper, int dt);
		funcdef ButtonState SkillInput(PlayerTargetingHelper@ helper, Skills::Skill@ skill, ButtonState btn);

		array<Tick@> g_tick;
		array<SkillInput@> g_skillInput;

		void OnUpdate(Tick@ f) { g_tick.insertLast(f); }
		void OnSkillInput(SkillInput@ f) { g_skillInput.insertLast(f); }

		void Install()
		{
			auto plr = GetLocalPlayer();
			if (plr is null || plr.m_targetHelper is null)
				return;
			if (cast<HWPTargetingHelper>(plr.m_targetHelper) !is null)
				return;
			if (plr.m_targetHelper.m_targetingSkill !is null)
				return;
			plr.m_targetHelper.OnDestroyed();
			@plr.m_targetHelper = HWPTargetingHelper(plr);
			HWP::Log("core", "targeting helper installed");
		}
	}
}

class HWPTargetingHelper : PlayerTargetingHelper
{
	HWPTargetingHelper(Player@ player)
	{
		super(player);
	}

	bool Update(int dt, vec2 aimDir) override
	{
		for (uint i = 0; i < HWP::TargetHelper::g_tick.length(); i++)
			HWP::TargetHelper::g_tick[i](this, dt);
		if (HWP::Aim::Pre(this, dt, aimDir))
			return true;
		return PlayerTargetingHelper::Update(dt, aimDir);
	}

	vec2 CalcGamepadTargetPos(float targetingDist, vec2 aimDir, Skills::TargetingParams@ params, int dt) override
	{
		return HWP::Aim::Apply(this, params, PlayerTargetingHelper::CalcGamepadTargetPos(targetingDist, aimDir, params, dt), true);
	}

	vec2 CalcMouseTargetPos(vec2 mousePos, Skills::TargetingParams@ params, int idt = -1) override
	{
		return HWP::Aim::Apply(this, params, PlayerTargetingHelper::CalcMouseTargetPos(mousePos, params, idt), false);
	}

	ButtonState GetSkillInput(Skills::Skill@ skill) override
	{
		ButtonState btn = PlayerTargetingHelper::GetSkillInput(skill);
		for (uint i = 0; i < HWP::TargetHelper::g_skillInput.length(); i++)
			btn = HWP::TargetHelper::g_skillInput[i](this, skill, btn);
		return btn;
	}
}

namespace Modules
{
	class HWPTargetHelperModule : Module
	{
		HWPTargetHelperModule()
		{
			super("hwp-targethelper");
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("hwplib", "HWPTargetHelperModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			HWP::TargetHelper::Install();
		}
	}
}
