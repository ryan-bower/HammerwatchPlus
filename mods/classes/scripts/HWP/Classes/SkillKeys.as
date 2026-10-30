// Extra skill keys for the HoH1 specs with more than three actives (the thief's
// Assassin and Shadow 4, Trickster 5, the gladiator's Retiarius 4; every other class
// has 3). The engine's GameInput has only Skill1, Skill2 and Skill3, and
// PlayerTargetingHelper.GetSkillInput (Behaviors/Actors/Player/
// PlayerTargetingHelper.as:713-750) gives the 3rd and every later active spell
// Skill3, so all of them would fire on one press.
//
// Core's targeting helper (mods/core/scripts/HWP/Core/TargetHelper.as) runs two hooks
// registered here: Poll every frame of player control, and SkillInput, which answers
// the 4th, 5th and 6th active with raw keys set on the Plus tab (default 4, 5, 6;
// vanilla binds 1 2 3 Q E V). Everything else (the targeting modes, the input buffer,
// another skill's button cancelling a charge, quickcast) is vanilla code reading those
// keys, so Skill3 fires only the 3rd active. The HUD shows the extra skills with their
// key (SkillKeysHUD.as).
//
// Keyboard only: a gamepad still reaches only the first three actives (the
// vanilla skill wheel, RadialMenuItemType::ExpandPlayerSkill, is never added
// to the action menu, RadialMenu.as).
// GameLab: gamelab-hands' input verb holds "hwp_skill4".."hwp_skill6" by
// writing "4,5,..." to GlobalCache EMU_KEY, and gives a spell its own key only
// while ON_KEY is "1" (no symbol shared, so either mod loads without the other).
namespace HWP
{
	namespace SkillKeys
	{
		const int COUNT = 3;                          // Skill 4, 5, 6
		const array<int> DEFAULTS = { 33, 34, 35 };   // SDL scancodes for 4, 5, 6
		const string EMU_KEY = "hwp_skillkeys_held";
		const string ON_KEY = "hwp_skillkeys_on";

		array<int> g_scancode = { 33, 34, 35 };
		array<bool> g_down = { false, false, false };
		array<bool> g_pressed = { false, false, false };
		array<bool> g_released = { false, false, false };
		int g_version = 0;   // bumped when a key changes: the HUD relabels

		string SettingName(int k) { return "skillkeys.skill" + (k + 4); }

		string KeyName(int k)
		{
			if (k < 0 || k >= COUNT)
				return "";
			return HWP::Options::KeyName(g_scancode[k]);
		}

		// at most 4 characters: the HUD slot's key label is 28 pixels wide
		string ShortName(int k)
		{
			if (k < 0 || k >= COUNT)
				return "";
			return HWP::Options::ShortKeyName(g_scancode[k]);
		}

		void RefreshSettings()
		{
			for (int k = 0; k < COUNT; k++)
			{
				int was = g_scancode[k];
				g_scancode[k] = HWP::Settings::GetInt(SettingName(k), DEFAULTS[k]);
				// a new key that is held right now (just pressed to bind it) must not
				// cast, and one that is not must not give a Released: start from its state
				if (g_scancode[k] != was)
					g_down[k] = HWP::Options::KeyDown(g_scancode[k]);
			}
			g_version++;
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("skillkeys.") == 0)
				RefreshSettings();
		}

		// the row in the player menu's Plus tab: click, then press the new key
		class SkillKeyOption : HWP::Options::KeyOption
		{
			int m_k;

			SkillKeyOption(int k)
			{
				m_k = k;
			}

			string Title() override { return Resources::GetString(".hwp.skillkeys.option", { { "n", "" + (m_k + 4) } }); }
			int Scancode() override { return g_scancode[m_k]; }
			void SetScancode(int scancode) override
			{
				if (scancode == DEFAULTS[m_k])
					HWP::Settings::Reset(SettingName(m_k));
				else
					HWP::Settings::SetInt(SettingName(m_k), scancode);
				RefreshSettings();
			}
		}

		// The extra key a skill listens on (0 = Skill 4), or -1 for a skill
		// the vanilla buttons serve. The same walk as GetSkillInput: the
		// active spells after m_skills[0], in order; the 4th on are ours.
		int Extra(array<Skills::Skill@>@ skills, Skills::Skill@ skill)
		{
			if (skills is null || skill is null || skill.m_type != PlayerSkillType::Spell)
				return -1;
			if (skill.GetTargetingMode() == Skills::TargetingMode::Passive)
				return -1;
			int idx = 0;
			for (uint i = 1; i < skills.length(); i++)
			{
				auto s = skills[i];
				if (s is skill)
					return (idx >= 3 && idx - 3 < COUNT) ? idx - 3 : -1;
				if (s is null || s.GetTargetingMode() == Skills::TargetingMode::Passive || s.m_type != PlayerSkillType::Spell)
					continue;
				idx++;
			}
			return -1;
		}

		// the active spells GetSkillInput counts
		int ActiveCount(array<Skills::Skill@>@ skills)
		{
			int n = 0;
			for (uint i = 1; skills !is null && i < skills.length(); i++)
			{
				auto s = skills[i];
				if (s !is null && s.m_type == PlayerSkillType::Spell && s.GetTargetingMode() != Skills::TargetingMode::Passive)
					n++;
			}
			return n;
		}

		bool TypingInChat()
		{
			auto main = cast<MainMenuGameMode>(g_gameMode);
			return main !is null && main.m_wChat !is null && main.m_wChat.m_wInput !is null && main.m_wChat.m_wInput.m_typing;
		}

		// the raw scancode poll cannot tell a skill key from typing a digit
		bool InputBusy()
		{
			auto cb = GetControlBindings();
			if (cb !is null && cb.IsExpectingTextInput())
				return true;
			return TypingInChat() || HWP::Options::TabOpen();
		}

		bool Emulated(const string &in held, int k)
		{
			if (held.isEmpty())
				return false;
			return held.split(",").find("" + (k + 4)) >= 0;
		}

		// once per frame of player control (core's targeting helper, OnUpdate)
		void Poll()
		{
			string held = GlobalCache::Get(EMU_KEY);
			bool busy = InputBusy();
			for (int k = 0; k < COUNT; k++)
			{
				// (an emulated hold is no typing: it counts with the console open)
				bool down = (!busy && HWP::Options::KeyDown(g_scancode[k])) || Emulated(held, k);
				g_pressed[k] = down && !g_down[k];
				g_released[k] = !down && g_down[k];
				g_down[k] = down;
			}
		}

		void Tick(PlayerTargetingHelper@ helper, int dt)
		{
			Poll();
		}

		// the vanilla answer is Skill3 for every active past the 3rd; those read
		// their own key instead (the ButtonState is a copy, its fields rewritten)
		ButtonState SkillInput(PlayerTargetingHelper@ helper, Skills::Skill@ skill, ButtonState btn)
		{
			int k = Extra(helper.m_player.m_skills, skill);
			if (k >= 0)
			{
				btn.Down = g_down[k];
				btn.Pressed = g_pressed[k];
				btn.Released = g_released[k];
			}
			return btn;
		}

		// hwp skillkeys: the keys and which skill each one casts
		void CmdSkillKeys(array<string>@ args)
		{
			string keys = "";
			for (int k = 0; k < COUNT; k++)
				keys += (k > 0 ? ", " : "") + "skill " + (k + 4) + " = " + KeyName(k) + " (" + g_scancode[k] + ")";
			HWP::Commands::Reply(keys);
			auto plr = GetLocalPlayer();
			if (plr is null)
				return;
			string list = "";
			for (uint i = 0; i < plr.m_skills.length(); i++)
			{
				int k = Extra(plr.m_skills, plr.m_skills[i]);
				if (k >= 0)
					list += (list.isEmpty() ? "" : ", ") + plr.m_skills[i].m_id + " on " + KeyName(k);
			}
			HWP::Commands::Reply("active skills: " + ActiveCount(plr.m_skills) + (list.isEmpty() ? "" : "; " + list)
				+ (cast<HWPTargetingHelper>(plr.m_targetHelper) is null ? " (helper not installed)" : ""));
		}
	}
}

namespace Modules
{
	class HWPSkillKeysModule : Module, HWP::ModuleStart
	{
		HWPSkillKeysModule()
		{
			super("hwp-skillkeys");
			for (int k = 0; k < HWP::SkillKeys::COUNT; k++)
				HWP::Options::Register("skill" + (k + 4), HWP::SkillKeys::SkillKeyOption(k));
			HWP::Commands::Register("skillkeys", " show the extra skill keys (Skill 4-6) and what they cast", HWP::Commands::Handler(HWP::SkillKeys::CmdSkillKeys));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::SkillKeys::OnSettingChanged));
			HWP::TargetHelper::OnUpdate(HWP::TargetHelper::Tick(HWP::SkillKeys::Tick));
			HWP::TargetHelper::OnSkillInput(HWP::TargetHelper::SkillInput(HWP::SkillKeys::SkillInput));
		}

		void Start(StartMode sMode)
		{
			GlobalCache::Set(HWP::SkillKeys::EMU_KEY, ""); // a GameLab hold does not outlive its level
			GlobalCache::Set(HWP::SkillKeys::ON_KEY, "1");
			HWP::SkillKeys::RefreshSettings();
			for (int k = 0; k < HWP::SkillKeys::COUNT; k++)
				HWP::SkillKeys::g_down[k] = false;
		}
	}
}
