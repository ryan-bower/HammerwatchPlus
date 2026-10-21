// The specs module: the self-check (the six subclasses and their stacks are loaded), the
// `hwp specs` status command and the per-frame updates of the scripted skill parts.
namespace HWP
{
	namespace Specs
	{
		const array<string> SUBCLASSES = { "hwp_ranger_stormbringer", "hwp_wizard_invocation",
			"hwp_sorcerer_arcane", "hwp_rogue_winddancer", "hwp_warrior_bannerlord", "hwp_warlock_branding" };

		bool g_checked = false;

		void SelfCheck()
		{
			if (g_checked)
				return;
			g_checked = true;
			int found = 0;
			for (uint i = 0; i < SUBCLASSES.length(); i++)
			{
				bool ok = false;
				for (uint j = 0; j < PlayerClass::Instances.length(); j++)
				{
					if (PlayerClass::Instances[j].m_id == SUBCLASSES[i])
						ok = true;
				}
				if (ok)
					found++;
				else
					LogError("specs", "subclass not registered: " + SUBCLASSES[i]);
			}
			Log("specs", found + " of " + SUBCLASSES.length() + " subclasses registered");

			array<string> stacks = { "provisions", "static_charge" };
			for (uint i = 0; i < stacks.length(); i++)
			{
				if (Stack(stacks[i]) is null)
					LogError("specs", "stack not registered: " + STACKS + stacks[i]);
			}

			// the buffs the scripts load by name (the svals' own are checked when they load)
			array<string> buffs = { "standard_dr", "standard_dr_planted", "crusade_5", "gale_share_20_0", "gale_share_60_3", "conduit_1_1", "conduit_2_5" };
			for (uint i = 0; i < buffs.length(); i++)
			{
				if (Buff(buffs[i]) is null)
					LogError("specs", "buff not registered: " + BUFFS + buffs[i]);
			}
		}

		void CmdStatus(array<string>@ args)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			string ret = "specs: " + g_standards.length() + " standard(s)";
			for (uint i = 0; i < g_standards.length(); i++)
			{
				auto s = g_standards[i];
				ret += "; " + (s.m_planted ? "planted" : "carried") + " " + s.m_left + " ms dr " + s.m_dr
					+ " r " + s.m_radius;
			}
			if (plr !is null)
			{
				auto prov = Stack("provisions");
				ret += "; provisions " + (prov !is null ? plr.GetStacks(prov) : -1);
				auto sc = Stack("static_charge");
				ret += "; static charge " + (sc !is null ? plr.GetStacks(sc) : -1);
			}
			HWP::Commands::Reply(ret);
		}
	}
}

namespace Modules
{
	class HWPSpecsModule : Module, HWP::ModuleStart
	{
		HWPSpecsModule()
		{
			super("hwp-specs");
			HWP::Commands::Register("specs", "  4th specializations status (standards, stacks)", HWP::Commands::Handler(HWP::Specs::CmdStatus));
			HWP::Specs::SelfCheck();
		}

		void Start(StartMode sMode)
		{
			HWP::Specs::ClearStandards();
			HWP::Specs::g_provisionsC = 0;
			HWP::Specs::g_conduitC = 0;
			HWP::Specs::g_channelMana = 0;
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (paused)
				return;
			HWP::Specs::UpdateStandards(ms);
			HWP::Specs::UpdateProvisions(ms);
			HWP::Specs::UpdateConduit(ms);
		}
	}
}
