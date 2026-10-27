// Three extra mission layouts for the equipment-map drops ("pink maps"):
// MissionDef::LoadSingle files under tweak/hwp/missions/. They join the
// vanilla equipment_map set, so MissionMap items roll them like Bandit Keep,
// Ghostly Crypt and Spider Caves. Themes, enemy schemes and boss levels are
// vanilla; the combinations are new.
//
// maps.enabled off hides them (MissionDef.m_hidden, which only the random
// picks check: MissionDef::FetchMissionsFromSet / FetchRandomMissions), so new
// map drops roll only the vanilla maps. A map item already rolled keeps its
// mission and still plays.
namespace HWP
{
	namespace Maps
	{
		array<string> IDS = { "hwp_goblin_warrens", "hwp_sunken_dungeon", "hwp_high_court" };
		array<string> SCHEMES = { "bats_white_1", "beetles_black_1", "beetles_black_burrow", "beetles_green_2", "bone_blockade_1", "cult_3", "forest_mix_1", "goblins_1", "goblins_2", "goblins_3", "mandrakes_1", "tower_barracks_1", "tower_courts_1", "tower_crypt_1", "trolls_1", "trolls_2", "undead_court_1", "undead_court_2", "undead_guard_1", "undead_guard_2", "undead_horde_1", "undead_horde_2", "wasps_1", "wolves_1" };
		bool g_checked = false;
		bool g_enabled = true;

		MissionDef@ Find(const string &in id)
		{
			return MissionDef::Get(HashString(id));
		}

		// every machine: the missions in or out of the random picks
		void Apply()
		{
			g_enabled = HWP::Settings::GetBool("maps.enabled", true);
			for (uint i = 0; i < IDS.length(); i++)
			{
				auto def = Find(IDS[i]);
				if (def !is null)
					def.m_hidden = !g_enabled;
			}
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("maps.") == 0)
				Apply();
		}

		// Missions are loaded with the other tweak data; checked at gameplay load.
		void SelfCheck()
		{
			if (g_checked)
				return;
			g_checked = true;
			int found = 0;
			for (uint i = 0; i < IDS.length(); i++)
			{
				auto def = Find(IDS[i]);
				if (def is null)
					HWP::LogError("maps", "mission " + IDS[i] + " not registered (tweak/hwp/missions/)");
				else
					found++;
			}
			int schemes = 0;
			for (uint i = 0; i < SCHEMES.length(); i++)
			{
				if (EnemyPlacementScheme::Get("actors/enemies.sval:" + SCHEMES[i]) !is null)
					schemes++;
				else
					HWP::LogError("maps", "missing enemy scheme " + SCHEMES[i]);
			}
			HWP::Log("maps", "self-check done: " + found + "/" + IDS.length() + " missions, " + schemes + "/" + SCHEMES.length() + " schemes");
		}

		void CmdMaps(array<string>@ args)
		{
			auto rec = GetLocalPlayerRecord();
			int found = 0;
			int eligible = 0;
			for (uint i = 0; i < IDS.length(); i++)
			{
				auto def = Find(IDS[i]);
				if (def is null)
					continue;
				found++;
				bool ok = rec !is null && CheckConditionals(def.m_conditionals, rec);
				if (ok)
					eligible++;
				auto span = def.GetLevelSpan();
				HWP::Commands::Reply(Resources::GetString(".hwp.maps.row", {
					{ "name", Resources::GetString(def.m_name) }, { "floors", int(def.m_levels.length()) },
					{ "span", "" + span.x + "-" + span.y }, { "flag", ok ? "" : Resources::GetString(".hwp.maps.locked") } }));
			}
			HWP::Commands::Reply(Resources::GetString(".hwp.maps.status", { { "found", found }, { "total", int(IDS.length()) }, { "eligible", eligible } }));
			if (!g_enabled)
				HWP::Commands::Reply(Resources::GetString(".hwp.maps.off"));
		}
	}
}

namespace Modules
{
	class HWPMapsModule : Module, HWP::ModuleStart
	{
		HWPMapsModule()
		{
			super("hwp-maps");
			HWP::Commands::Register("maps", " list the HammerwatchPlus map layouts", HWP::Commands::Handler(HWP::Maps::CmdMaps));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Maps::OnSettingChanged));
			HWP::Maps::Apply();
		}

		void Start(StartMode sMode)
		{
			HWP::Maps::Apply();
			HWP::Maps::g_checked = false;
			HWP::Maps::SelfCheck();
		}

		// the town starts with a null save, so Load never runs there (docs/RE_NOTES.md,
		// mod lifecycle): run the check on the first gameplay frame as well
		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("maps", "HWPMapsModule.UpdateFrame"))
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
			HWP::Maps::SelfCheck();
		}
	}
}
