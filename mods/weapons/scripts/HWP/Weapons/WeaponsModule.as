// Twelve extra endgame weapons (ilvl 35, four per slot) merged into the base
// equipment tables through the <loader> in tweak/hwp/equipment_weapons_hwp.sval.
// They reuse base graphics, models and attack skills and differ in their
// modifier profiles (hybrid damage types, crit, speed, parry, block). The
// base drop and shop code picks them up like any other BaseItem.
//
// The drop roll (Equipment::Generator::GenerateBaseItem) weighs each base item
// by spawnChance and skips it outside ilvl..ilvlMax. weapons.weight scales the
// twelve's spawnChance; weapons.enabled off sets their ilvlMax below every item
// level, so no new one drops. Weapons already owned keep working.
namespace HWP
{
	namespace Weapons
	{
		array<string> IDS = { "hwp_mh_warhammer", "hwp_mh_frostbrand", "hwp_mh_stiletto", "hwp_mh_stormrod", "hwp_oh_bulwark", "hwp_oh_grimoire", "hwp_oh_handcannon", "hwp_oh_parrying_dirk", "hwp_2h_warbow", "hwp_2h_executioner", "hwp_2h_tempest", "hwp_2h_twinfangs" };
		bool g_checked = false;
		bool g_enabled = true;
		float g_weight = 1.0f;
		// equipment_weapons_hwp.sval sets neither spawn-chance nor ilvl-max: BaseItem's
		// defaults, so setting them again never compounds
		const float BASE_CHANCE = 1.0f;
		const int BASE_MAX = 999999999;

		// every machine: the twelve in or out of the random drops, at their weight
		void Apply()
		{
			g_enabled = HWP::Settings::GetBool("weapons.enabled", true);
			g_weight = clamp(HWP::Settings::GetFloat("weapons.weight", 1.0f), 0.0f, 10.0f);
			for (uint i = 0; i < IDS.length(); i++)
			{
				auto item = Equipment::BaseItem::Get(IDS[i]);
				if (item is null)
					continue;
				item.spawnChance = BASE_CHANCE * g_weight;
				item.ilvlMax = g_enabled ? BASE_MAX : -1;
			}
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("weapons.") == 0)
				Apply();
		}

		// Items are registered after the modules are made, so the check runs at
		// gameplay load (g_checked is reset in Start).
		void SelfCheck()
		{
			if (g_checked)
				return;
			g_checked = true;
			HWP::CheckEquipment("weapons", IDS);
			HWP::Log("weapons", "self-check done: " + IDS.length() + " weapons");
		}

		void CmdWeapons(array<string>@ args)
		{
			int found = 0;
			for (uint i = 0; i < IDS.length(); i++)
			{
				auto item = Equipment::BaseItem::Get(IDS[i]);
				if (item is null)
					continue;
				found++;
				HWP::Commands::Reply(item.name + " - " + Resources::GetString(".hwp.weapons." + IDS[i] + ".desc"));
			}
			HWP::Commands::Reply(Resources::GetString(".hwp.weapons.count", { { "n", found }, { "total", int(IDS.length()) } }));
			HWP::Commands::Reply(Resources::GetString(g_enabled ? ".hwp.weapons.drops" : ".hwp.weapons.off", { { "weight", "" + g_weight } }));
		}
	}
}

namespace Modules
{
	class HWPWeaponsModule : Module, HWP::ModuleStart
	{
		HWPWeaponsModule()
		{
			super("hwp-weapons");
			HWP::Commands::Register("weapons", " list the HammerwatchPlus weapons", HWP::Commands::Handler(HWP::Weapons::CmdWeapons));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Weapons::OnSettingChanged));
		}

		void Start(StartMode sMode)
		{
			HWP::Weapons::Apply();
			HWP::Weapons::g_checked = false;
			HWP::Weapons::SelfCheck();
		}

		// the town starts with a null save, so Load never runs there (docs/RE_NOTES.md,
		// mod lifecycle): run the check on the first gameplay frame as well
		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("weapons", "HWPWeaponsModule.UpdateFrame"))
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
			HWP::Weapons::SelfCheck();
		}
	}
}
