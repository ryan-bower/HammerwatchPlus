// The Dark Citadel's top (bugs 10.22.26 line 39): two Dark Halls floors (the eyeball
// floors), then the two HoH1 Battlements floors (giants, breaking glass walkways) and
// the Avatar. Vanilla ships one Dark Halls floor with dark_halls_2 commented out; the
// import (tools/hoh1/import_hoh1.py campaign) splices the Battlements into the mission file
// (tweak/missions/missions_dark_citadel.sval, packed with --with-local). Doctor never
// re-imports an existing import, so an older generated file may lack dark_halls_2:
// the second Dark Halls floor is added here at runtime from the loaded MissionDef,
// and the Battlements floors are leveled to the floors around them. Without the
// import (no hwp_battlements_1 in the mission) the vanilla floors stay, and the log
// says which.
// HoH1 content off in this lobby (StandIns.as, issue #123): the run goes as vanilla's does,
// dark_halls_1 straight to the Avatar (Link). dark_halls_2 and the Battlements stay in the list,
// the Battlements as generated Dark Halls floors, so a save already at one of those indices
// (mission-level is the floor index) plays it and goes on to the Avatar; nothing new reaches them.
namespace HWP
{
	namespace Campaign
	{
		namespace Citadel
		{
			const string MISSION = "dark_citadel";
			const string HALLS_1 = "dark_halls_1";
			const string HALLS_2 = "dark_halls_2";
			const string BATTLEMENTS_1 = "hwp_battlements_1";
			const string BATTLEMENTS_2 = "hwp_battlements_2";
			const string BOSS = "dark_halls_boss";
			const int HALLS_2_DIFF = 22;       // vanilla's commented-out dark_halls_2
			const int BATTLEMENTS_DIFF = 22;   // like dark_halls_2 and the Avatar

			string g_summary;      // the last Fix() result, for hwp campaign citadel and the self-check
			bool g_hoh1 = false;   // the Battlements floors are in the mission

			int IndexOf(MissionDef@ def, const string &in id)
			{
				for (uint i = 0; i < def.m_levels.length(); i++)
				{
					if (def.m_levels[i].m_id == id)
						return int(i);
				}
				return -1;
			}

			string FloorList(MissionDef@ def, int from)
			{
				string s;
				for (uint i = uint(max(0, from)); i < def.m_levels.length(); i++)
					s += (s.isEmpty() ? "" : ", ") + i + ":" + def.m_levels[i].m_id;
				return s;
			}

			// the vanilla dark_halls_2 entry, as the commented-out block in the mission file
			MissionLevel@ MakeHalls2(MissionDef@ def)
			{
				SValueBuilder sb;
				sb.PushDictionary();
				sb.PushString("id", HALLS_2);
				sb.PushString("mission-theme", "theme_dark_halls");
				sb.PushInteger("diff-level", HALLS_2_DIFF);
				sb.PushInteger("diff-level-ngp", HALLS_2_DIFF);
				sb.PushArray("flags");
				sb.PushString("place_well");
				sb.PopArray();
				sb.PopDictionary();
				// kept alive: the level hands out handles into its params (module data)
				SValue@ params = sb.Build();
				return MissionLevel(def, UnitPtr(), params);
			}

			// Who goes where after dark_halls_1. hoh1: halls_1 -> halls_2 -> battlements_1 ->
			// battlements_2 -> boss. Not: each of them -> boss, as vanilla's one Dark Halls floor.
			// Progression follows m_idNext by id (MissionModule::NextLevel), not the index.
			bool g_linkedHoH1 = true;

			void Link(bool hoh1)
			{
				auto def = MissionDef::Get(HashString(MISSION));
				if (def is null || !g_hoh1)
					return;
				int halls1 = IndexOf(def, HALLS_1);
				int halls2 = IndexOf(def, HALLS_2);
				int bat1 = IndexOf(def, BATTLEMENTS_1);
				int bat2 = IndexOf(def, BATTLEMENTS_2);
				if (halls1 < 0 || halls2 < 0 || bat1 < 0 || bat2 < 0 || IndexOf(def, BOSS) < 0)
					return;
				def.m_levels[halls1].m_idNext = hoh1 ? HALLS_2 : BOSS;
				def.m_levels[halls2].m_idNext = hoh1 ? BATTLEMENTS_1 : BOSS;
				def.m_levels[bat1].m_idNext = hoh1 ? BATTLEMENTS_2 : BOSS;
				def.m_levels[bat2].m_idNext = BOSS;
				if (hoh1 != g_linkedHoH1)
					HWP::Log("campaign", "Dark Citadel: " + Chain(def, halls1));
				g_linkedHoH1 = hoh1;
			}

			// "dark_halls_1 -> dark_halls_boss", the floors a run walks from 'from'
			string Chain(MissionDef@ def, int from)
			{
				string chain;
				int at = from;
				for (int n = 0; n < 6 && at >= 0 && at < int(def.m_levels.length()); n++)
				{
					chain += (chain.isEmpty() ? "" : " -> ") + def.m_levels[at].m_id;
					if (def.m_levels[at].m_id == BOSS)
						break;
					at = IndexOf(def, def.m_levels[at].m_idNext);
				}
				return chain;
			}

			// Runs from the module constructor (every level load, before any generation);
			// idempotent. hoh1: HWP::HoH1 says this lobby plays HoH1 floors. Returns the floor
			// list it ended with.
			string Fix() { return Fix(StandIns::On()); }

			string Fix(bool hoh1)
			{
				auto def = MissionDef::Get(HashString(MISSION));
				if (def is null)
				{
					g_summary = "Dark Citadel: mission not found";
					HWP::LogError("campaign", g_summary);
					return g_summary;
				}
				int halls1 = IndexOf(def, HALLS_1);
				int bat1 = IndexOf(def, BATTLEMENTS_1);
				int bat2 = IndexOf(def, BATTLEMENTS_2);
				int boss = IndexOf(def, BOSS);
				g_hoh1 = bat1 >= 0 && bat2 >= 0;
				if (halls1 < 0 || boss < 0)
				{
					g_summary = "Dark Citadel: unexpected floors (" + FloorList(def, 0) + "), left alone";
					HWP::LogError("campaign", g_summary);
					return g_summary;
				}
				if (!g_hoh1)
				{
					g_summary = "vanilla Dark Citadel floors (HoH1 import absent): " + FloorList(def, halls1);
					HWP::Log("campaign", g_summary);
					return g_summary;
				}
				if (!hoh1)
				{
					auto halls = def.m_levels[halls1];
					for (int i = bat1; i <= bat2; i++)
					{
						auto lvl = def.m_levels[i];
						if (lvl.m_level.findFirst("hoh1/") != 0)
							continue;
						// leveled here too: the leveling below reaches only the stand-in
						lvl.m_diffLevel = max(lvl.m_diffLevel, BATTLEMENTS_DIFF);
						lvl.m_diffLevelNgp = max(lvl.m_diffLevelNgp, BATTLEMENTS_DIFF);
						StandIns::Swap(def, i, StandIns::Generated(def, lvl.m_id, "theme_dark_halls",
							max(lvl.m_diffLevel, BATTLEMENTS_DIFF), max(lvl.m_diffLevelNgp, BATTLEMENTS_DIFF), lvl.m_idNext, halls.m_actNameBase));
					}
					HWP::Log("campaign", "HoH1 content off: Dark Citadel " + BATTLEMENTS_1 + ", " + BATTLEMENTS_2 + " are generated Dark Halls floors, skipped");
				}
				if (IndexOf(def, HALLS_2) < 0)
				{
					auto first = def.m_levels[halls1];
					auto second = MakeHalls2(def);
					second.m_idNext = first.m_idNext.isEmpty() ? BATTLEMENTS_1 : first.m_idNext;
					first.m_idNext = HALLS_2;
					def.m_levels.insertAt(halls1 + 1, second);
					HWP::Log("campaign", "Dark Citadel: added " + HALLS_2 + " (theme_dark_halls, diff " + HALLS_2_DIFF + ") after " + HALLS_1);
					bat1 = IndexOf(def, BATTLEMENTS_1);
					bat2 = IndexOf(def, BATTLEMENTS_2);
				}
				// the Battlements scale like the floors around them (the generated file may
				// carry an older 21/21 for the first one)
				for (int i = bat1; i <= bat2; i++)
				{
					auto lvl = def.m_levels[i];
					if (lvl.m_diffLevel < BATTLEMENTS_DIFF)
						lvl.m_diffLevel = BATTLEMENTS_DIFF;
					if (lvl.m_diffLevelNgp < BATTLEMENTS_DIFF)
						lvl.m_diffLevelNgp = BATTLEMENTS_DIFF;
				}
				// on: halls_1 -> halls_2 -> battlements_1 -> battlements_2 -> boss; off: halls_1 -> boss
				Link(hoh1);
				g_summary = "Dark Citadel: " + FloorList(def, halls1) + "; chain " + Chain(def, halls1);
				HWP::Log("campaign", g_summary);
				return g_summary;
			}

			// Host, every gameplay frame: on dark_halls_1 and on the Avatar, once the lobby's verdict
			// is final (every player reported), say in red to everyone that the run skips the HoH1
			// Battlements and why (issue #123). Once per level: globals reset with each one.
			bool g_warned = false;

			void WarnFallback()
			{
				if (g_warned || g_inTown || !Network::IsServer() || !HWP::HoH1::Known())
					return;
				if (!HWP::HoH1::Lacks())
				{
					g_warned = true;   // on, off by the host, or a build without HoH1: nothing to warn
					return;
				}
				auto def = MissionManager::GetCurrentMission();
				if (def is null || def.m_id != MISSION)
					return;
				int at = int(MissionManager::g_module.m_missionLevelIndex);
				if (at < 0 || at >= int(def.m_levels.length()))
					return;
				string id = def.m_levels[at].m_id;
				if (id != HALLS_1 && id != BOSS)
					return;
				g_warned = true;
				if (StandIns::On())
					return;
				string why = HWP::HoH1::Why();
				HWP::Log("campaign", "Dark Citadel " + id + ": the HoH1 Battlements are skipped (" + HWP::Commands::Plain(why) + ")");
				HWP::HoH1::Warn(Resources::GetString(id == BOSS ? ".hwp.campaign.citadel_skipped" : ".hwp.campaign.citadel_skip", { { "why", why } }));
			}

			// the mission floor index of a floor id, for gl mission dark_citadel <index>
			int FloorIndex(const string &in id)
			{
				auto def = MissionDef::Get(HashString(MISSION));
				return def is null ? -1 : IndexOf(def, id);
			}
		}
	}
}
