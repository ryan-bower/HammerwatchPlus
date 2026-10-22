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

			array<string> stacks = { "provisions", "static_charge", "tailwind" };
			for (uint i = 0; i < stacks.length(); i++)
			{
				if (Stack(stacks[i]) is null)
					LogError("specs", "stack not registered: " + STACKS + stacks[i]);
			}

			// the buffs the scripts load by name (the svals' own are checked when they load)
			array<string> buffs = { "standard_dr", "standard_dr_planted", "crusade_5", "gale_share_20_0", "gale_share_60_3", "conduit_1_1", "conduit_2_5", "tailwind_1_1", "tailwind_5_5", "wind_ward", "pyrebrand" };
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
				auto tw = Stack("tailwind");
				ret += "; tailwind " + (tw !is null ? plr.GetStacks(tw) : -1);
				auto ess = Stack(ESSENCE);
				ret += "; essence " + (ess !is null ? plr.GetStacks(ess) : -1);
			}
			ret += "; circuit returns " + g_circuitReturns + " back hits " + g_circuitBackHits + " catches " + g_circuitCatches
				+ "; gale arrows " + g_galeArrows + "; tailwind kills " + g_twKills;
			float stored = 0;
			for (uint i = 0; i < g_brands.length(); i++)
				stored += g_brands[i].m_stored;
			ret += "; brands " + g_brands.length() + " stored " + int(stored + 0.5f) + "; claws " + g_claws + " hits " + g_clawHits
				+ " last " + g_lastClaw + "; transfers " + g_transfers + "; essence hits " + g_essenceHits + " released " + g_released;
			ret += "; blinks " + g_blinks + " hits " + g_blinkHits + " blink px " + g_lastBlink + "; recasts " + g_recasts + " " + g_lastRecast
				+ "; last spell " + LastSpellName(plr) + "; drained " + g_drained + " converted " + g_converted + " barrier saves " + g_barrierSaves
				+ "; feedback " + int(g_feedback + 0.5f) + " used " + g_fbUsed + " mul " + int(g_fbMul * 1000 + 0.5f) + "; conduit sent " + g_conduitSent + "; floored " + g_floored;
			if (plr !is null)
				ret += "; hp " + int(float(plr.m_record.hp) * 1000 + 0.5f) + " mana " + int(ManaPts(plr) + 0.5f) + "/" + plr.m_record.MaxMana()
					+ " dashes " + plr.m_record.dashCharges;
			Skills::Skill@ fb = null;
			if (plr !is null && g_fbSkill != 0)
				@fb = FindSkill(plr, g_fbSkill);
			if (fb !is null)
				ret += "; empowered " + fb.m_id + " moddmg " + int(fb.m_modDamageMul * 1000 + 0.5f);
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
			HWP::Net::OnRequest("specs.conduit", HWP::Net::RequestHandler(HWP::Specs::OnConduit));
			HWP::Net::OnEvent("specs.conduit_mana", HWP::Net::EventHandler(HWP::Specs::OnConduitMana));
		}

		void Start(StartMode sMode)
		{
			HWP::Specs::ClearStandards();
			HWP::Specs::g_provisionsC = 0;
			HWP::Specs::g_conduitC = 0;
			HWP::Specs::g_channelMana = 0;
			HWP::Specs::ClearTailwind();
			HWP::Specs::g_circuitReturns = 0;
			HWP::Specs::g_circuitCatches = 0;
			HWP::Specs::g_circuitBackHits = 0;
			HWP::Specs::g_galeArrows = 0;
			HWP::Specs::ClearBrands();
			HWP::Specs::ClearArcane();
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (paused)
				return;
			HWP::Specs::UpdateStandards(ms);
			HWP::Specs::UpdateProvisions(ms);
			HWP::Specs::UpdateConduit(ms);
			HWP::Specs::UpdateTailwind(ms);
			HWP::Specs::UpdateBrands(ms);
			HWP::Specs::UpdateArcane(ms);
		}
	}
}
