// The Forsaken Tower's generated floors, made by HoH1's own floor generator.
// tools/import_hoh1.py campaign copies HoH1's Generators/ scripts and its
// MakeDungeonGenerator from the player's install into the local
// scripts/HWP/Campaign/HoH1Gen/ (namespace HoH1Gen, paths under hoh1/), plus a
// class HWPHoH1GenFloor that implements HWP::Campaign::HoH1Floor. This file is
// the committed side: a HoH2 mission generator ("gen-class") that finds that
// class by name, so the module compiles and loads without the import.
//
// HoH2 runs a floor's generator before the level starts, then fabricates the
// prefabs it queued (host side) and spawns the players at a LevelStart script.
// HoH1 queued its prefabs the same way and only set g_spawnPos, so the floor's
// prefabs go to HoH2's queue and a LevelStart prefab is queued at the spot.
namespace HWP
{
	namespace Campaign
	{
		const string HOH1_FLOOR_CLASS = "HWPHoH1GenFloor";
		const string HOH1_START_PREFAB = "prefabs/hwp/hoh1_level_start.pfb";

		interface HoH1Floor
		{
			// HoH1's GenerateDungeon for one floor of its tower: theme ("mines",
			// "prison", "armory", "archives", "chambers"), act and level in the act
			// (0-based), the floor's index in the tower, its size in pixels
			void Generate(const string &in theme, int act, int level, int levelCount, int width, int height, int numPlrs);
			vec2 SpawnPos();
			uint PrefabCount();
			Prefab@ PrefabAt(uint i);
			vec3 PrefabPosAt(uint i);
		}
	}
}

class HWPHoH1Generator : ALevelGenerator
{
	string m_theme;
	int m_act;
	int m_level;
	int m_levelCount;

	void LoadParams(array<SValue@>@ params, MissionThemeDef@ themeDef) override
	{
		ALevelGenerator::LoadParams(params, themeDef);
		UnitPtr u;
		m_theme = GetParamString(u, params, "hoh1-theme", false, "mines");
		m_act = GetParamInt(u, params, "hoh1-act", false, 0);
		m_level = GetParamInt(u, params, "hoh1-level", false, 0);
		m_levelCount = GetParamInt(u, params, "hoh1-level-count", false, 0);
	}

	void Generate(SValue@ save) override
	{
		auto floor = cast<HWP::Campaign::HoH1Floor>(InstantiateClass(HWP::Campaign::HOH1_FLOOR_CLASS));
		if (floor is null)
		{
			PrintError("[HWP:campaign] HoH1 floor generator missing (tools/import_hoh1.py campaign)");
			return;
		}

		int plrs = max(1, Lobby::GetLobbyPlayerCount());
		HWP::Log("campaign", "HoH1 floor " + m_theme + " act " + m_act + " level " + m_level
			+ " (" + m_size.x + "x" + m_size.y + ", " + plrs + " players)");
		floor.Generate(m_theme, m_act, m_level, m_levelCount, m_size.x, m_size.y, plrs);

		// the start first: the rooms' start scripts measure from it (CheckSpawnDistance),
		// also when a saved floor fabricates its queue again
		vec2 spawn = floor.SpawnPos();
		auto start = Resources::GetPrefab(HWP::Campaign::HOH1_START_PREFAB);
		if (start !is null)
			g_prefabsToSpawn.insertLast(PrefabToSpawn(start, xyz(spawn)));

		uint n = floor.PrefabCount();
		for (uint i = 0; i < n; i++)
		{
			auto pfb = floor.PrefabAt(i);
			if (pfb !is null)
				g_prefabsToSpawn.insertLast(PrefabToSpawn(pfb, floor.PrefabPosAt(i)));
		}
		HWP::Log("campaign", "HoH1 floor generated: " + n + " prefabs, start at " + spawn.x + "," + spawn.y);
	}
}
