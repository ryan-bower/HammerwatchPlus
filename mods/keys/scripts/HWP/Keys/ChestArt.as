// Alt-art chests (tweak/hwp/chest_art.sval): a chest shows the sprite picked for its
// area of the run. tools/class_units.py gives our chest copies a scene per sprite
// (the original is "vanilla"); HWPChest switches to the one for its area on its
// first tick, and to the ace one once a gold chest rolls ace.
//
// An area is an act of the mission: it starts where a floor's act-name (the region
// banner, MissionLevel.m_actNameBase, from the level or its theme) differs from the
// floor before; a floor with no act-name belongs to the area before it. Every machine
// counts it alike from the mission definition, so no message is needed. Outside a
// mission (town, campaign levels) chests keep their own art.
namespace HWP
{
	namespace Keys
	{
		namespace ChestArt
		{
			const string FILE = "tweak/hwp/chest_art.sval";

			int g_areaOverride = 0; // hwp chestart area <n> (keys.debug)

			class Entry
			{
				string m_unit;
				bool m_ace;
				array<string> m_areas;
			}
			array<Entry@> g_entries;
			bool g_loaded = false;

			void Load()
			{
				if (g_loaded)
					return;
				g_loaded = true;
				auto sv = Resources::GetSValue(FILE);
				if (sv is null)
				{
					HWP::LogError("keys", "no " + FILE + "; chests keep their own art");
					return;
				}
				UnitPtr u;
				auto arr = GetParamArray(u, sv, "chests", false);
				if (arr is null)
					return;
				for (uint i = 0; i < arr.length(); i++)
				{
					Entry e;
					e.m_unit = GetParamString(u, arr[i], "unit");
					e.m_ace = GetParamBool(u, arr[i], "ace", false, false);
					auto areas = GetParamArray(u, arr[i], "areas", false);
					if (areas !is null)
						for (uint j = 0; j < areas.length(); j++)
							e.m_areas.insertLast(areas[j].GetString());
					if (e.m_areas.length() > 0)
						g_entries.insertLast(e);
				}
				HWP::Log("keys", "chest art: " + g_entries.length() + " chest kinds");
			}

			// the mission level being played, and its index in the mission (-1: none)
			int LevelIndex(MissionLevel@ &out level)
			{
				@level = null;
				auto gm = cast<MissionGameModeBase>(g_gameMode);
				if (gm is null || gm.m_missionLevel is null || gm.m_missionLevel.m_mission is null)
					return -1;
				@level = gm.m_missionLevel;
				array<MissionLevel@>@ levels = level.m_mission.m_levels;
				for (uint i = 0; i < levels.length(); i++)
					if (levels[i] is level)
						return int(i);
				return -1;
			}

			// 1-based area of the current floor; 0 outside a mission
			int Area()
			{
				if (g_areaOverride > 0)
					return g_areaOverride;
				MissionLevel@ level;
				int idx = LevelIndex(level);
				if (idx < 0)
					return 0;
				array<MissionLevel@>@ levels = level.m_mission.m_levels;
				int area = 1;
				string act = "";
				for (int i = 0; i <= idx; i++)
				{
					string a = levels[i].m_actNameBase;
					if (a.isEmpty())
						continue;
					if (!act.isEmpty() && a != act)
						area++;
					act = a;
				}
				return area;
			}

			// the scene for this chest unit in this area: "" when it has no alt art
			string SceneFor(const string &in unit, bool ace, int area)
			{
				Load();
				if (area <= 0)
					return "";
				for (uint i = 0; i < g_entries.length(); i++)
				{
					auto e = g_entries[i];
					if (e.m_ace != ace || e.m_unit != unit)
						continue;
					return e.m_areas[min(area, int(e.m_areas.length())) - 1];
				}
				return "";
			}

			// hwp chestart                 this floor's area and act
			// hwp chestart area <n>|off    (keys.debug) chests produced from now on use area n
			void CmdChestArt(array<string>@ args)
			{
				if (args.length() >= 2 && args[0] == "area")
				{
					if (!HWP::Keys::g_debug)
					{
						HWP::Commands::Reply(Resources::GetString(".hwp.keys.debug_off"));
						return;
					}
					g_areaOverride = args[1] == "off" ? 0 : max(0, parseInt(args[1]));
				}
				MissionLevel@ level;
				int idx = LevelIndex(level);
				HWP::Commands::Reply("chest art: area " + Area() + (g_areaOverride > 0 ? " (override)" : "")
					+ "; mission level " + idx + (level !is null ? " " + level.m_id + ", act " + level.m_actNameBase : "")
					+ "; " + g_entries.length() + " chest kinds");
			}
		}
	}
}
