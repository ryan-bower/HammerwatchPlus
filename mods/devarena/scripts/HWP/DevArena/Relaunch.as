// Relaunch (docs/devarena/SPEC.md HP5, "Decided during build" 26). A REFS edit (a unit or
// projectile reference) only takes on a fresh boot, so the footer offers [Relaunch]. The game
// cannot restart itself: the button saves everything the next boot needs and logs one line,
//   [HWP:devarena] relaunch {"preset":...,"tab":...,"dock":...,"level":...,"floor":...,"seed":...,"x":...,"y":...}
// and GameLab's "relaunch" step (gamelab/runner.py) syncs the override file from that log
// (tools/devarena/overrides.py: A/B versions), closes the game and boots it again.
//
// What rides where: the tuner versions and A/B slots in the override file; the toggles, golem
// settings, tab and dock in the town save (ArenaSave.as); the class, skills and gear are the
// character save itself; the preset label, floor, seed and position in the "relaunch" dict
// below. On the next boot TickRelaunch re-enters the same floor with the same generation seed
// (the way ReloadFloor does), puts the player back where they stood and logs
// "relaunch restored ...". The boot's character picker answers run-resume "no", which shows
// MissionEndMenu, and that clears the run's trinkets (ResetForNewMission, GUI/MissionEndMenu.as:
// 428; hp5-relaunch 20261021-012907), so their ids ride in the dict and are added back.
// Script globals do not survive the level change, so the dict rides
// the town save (with its stage) until it is restored, then is dropped: a later boot starts
// plain. A level change between the press and the restart is restored the same way.
namespace HWP
{
namespace DevArena
{
	bool g_rlSave;                 // this session: [Relaunch] was pressed, save the dict
	bool g_rlPending;              // this session: a saved dict waits to be restored
	string g_rlLevel;
	int g_rlMission;               // MissionDef hash
	int g_rlFloor;
	int g_rlSeed;
	int g_rlNgp;
	float g_rlX;
	float g_rlY;
	float g_rlFromStart;           // at the press: how far the player stood from the floor's start
	array<string> g_rlTrinkets;    // at the press: the trinket inventory, by id
	int g_rlStage;                 // 0 wait for a player, 1 mission started, 2 on the floor
	int g_rlWait;
	int g_relaunches;              // this level: [Relaunch] presses

	const int RL_SETTLE = 60;      // frames on the new floor before the teleport

	string RelaunchJson()
	{
		return "{\"preset\":" + GameLab::Quote(g_preset) + ",\"tab\":" + GameLab::Quote(g_tab)
			+ ",\"dock\":" + (g_dockOpen ? "true" : "false") + ",\"level\":" + GameLab::Quote(g_rlLevel)
			+ ",\"mission\":" + g_rlMission + ",\"floor\":" + g_rlFloor + ",\"seed\":" + g_rlSeed
			+ ",\"ngp\":" + g_rlNgp + ",\"x\":" + int(g_rlX) + ",\"y\":" + int(g_rlY) + ",\"fromStart\":" + int(g_rlFromStart) + "}";
	}

	// the [Relaunch] button
	void Relaunch()
	{
		auto plr = LocalPlayer();
		auto mm = MissionManager::g_module;
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		if (plr is null || mm is null || MissionDef::Get(mm.m_missionDefHash) is null || gm is null)
		{
			g_lastError = "relaunch: no arena floor running";
			return;
		}
		vec3 p = plr.m_unit.GetPosition();
		g_rlLevel = GetCurrentLevelFilename();
		g_rlMission = int(mm.m_missionDefHash);
		g_rlFloor = int(mm.m_missionLevelIndex);
		g_rlSeed = int(GameLab::g_genSeed);
		g_rlNgp = int(g_ngp + 0.5f);
		g_rlX = p.x;
		g_rlY = p.y;
		g_rlFromStart = dist(xy(p), g_arenaStart);
		g_rlTrinkets.resize(0);
		auto inv = plr.m_record.trinketInventory.m_items;
		for (uint i = 0; i < inv.length(); i++)
			g_rlTrinkets.insertLast(inv[i].m_id);
		g_rlSave = true;
		g_relaunches++;
		EmitOverride();
		gm.SavePlayerAndTown();
		g_lastAction = "relaunch: saved, restarting";
		g_lastError = "";
		HWP::Log("devarena", "relaunch " + RelaunchJson());
	}

	// da-arena: how far the player stands from the restored spot (-1: nothing restored here)
	float RelaunchDist()
	{
		auto plr = LocalPlayer();
		if (g_rlLevel == "" || g_rlPending || plr is null || GetCurrentLevelFilename() != g_rlLevel)
			return -1;
		return dist(xy(plr.m_unit.GetPosition()), vec2(g_rlX, g_rlY));
	}

	// the saved trinkets the inventory lacks, added back; how many
	int RestoreTrinkets(PlayerRecord@ rec)
	{
		array<string> have;
		auto inv = rec.trinketInventory.m_items;
		for (uint i = 0; i < inv.length(); i++)
			have.insertLast(inv[i].m_id);
		int added = 0;
		for (uint i = 0; i < g_rlTrinkets.length(); i++)
		{
			int at = have.find(g_rlTrinkets[i]);
			if (at >= 0)
			{
				have.removeAt(at);
				continue;
			}
			auto tr = Item::Trinket::Get(g_rlTrinkets[i]);
			if (tr is null)
				continue;
			rec.trinketInventory.Add(tr);
			added++;
		}
		if (added > 0)
		{
			rec.RefreshStats();
			rec.RefreshModifiers();
		}
		return added;
	}

	void SaveRelaunch(SValueBuilder& b)
	{
		b.PushString("preset", g_preset);
		if (!g_rlSave && !g_rlPending)
			return;
		b.PushDictionary("relaunch");
		b.PushString("level", g_rlLevel);
		b.PushInteger("mission", g_rlMission);
		b.PushInteger("floor", g_rlFloor);
		b.PushInteger("seed", g_rlSeed);
		b.PushInteger("ngp", g_rlNgp);
		b.PushInteger("x", int(g_rlX));
		b.PushInteger("y", int(g_rlY));
		b.PushInteger("stage", g_rlStage);
		b.PushInteger("from-start", int(g_rlFromStart));
		b.PushArray("trinkets");
		for (uint i = 0; i < g_rlTrinkets.length(); i++)
			b.PushString(g_rlTrinkets[i]);
		b.PopArray();
		b.PopDictionary();
	}

	void LoadRelaunch(SValue@ d)
	{
		UnitPtr u;
		if (g_preset == "")
			g_preset = GetParamString(u, d, "preset", false, "");
		auto r = d.GetDictionaryEntry("relaunch");
		if (r is null || r.GetType() != SValueType::Dictionary)
			return;
		g_rlLevel = GetParamString(u, r, "level", false, "");
		g_rlMission = GetParamInt(u, r, "mission", false, 0);
		g_rlFloor = GetParamInt(u, r, "floor", false, 0);
		g_rlSeed = GetParamInt(u, r, "seed", false, 0);
		g_rlNgp = GetParamInt(u, r, "ngp", false, 0);
		g_rlX = float(GetParamInt(u, r, "x", false, 0));
		g_rlY = float(GetParamInt(u, r, "y", false, 0));
		g_rlStage = GetParamInt(u, r, "stage", false, 0);
		g_rlFromStart = float(GetParamInt(u, r, "from-start", false, 0));
		g_rlTrinkets.resize(0);
		auto ta = GetParamArray(u, r, "trinkets", false);
		for (uint i = 0; ta !is null && i < ta.length(); i++)
			if (ta[i].GetType() == SValueType::String)
				g_rlTrinkets.insertLast(ta[i].GetString());
		g_rlPending = g_rlLevel != "";
		g_rlWait = 30;
		g_rlSave = false;
	}

	void TickRelaunch(bool paused)
	{
		if (!g_rlPending || paused)
			return;
		auto plr = LocalPlayer();
		if (plr is null || g_rlWait-- > 0)
			return;
		bool there = GetCurrentLevelFilename() == g_rlLevel && int(GameLab::g_genSeed) == g_rlSeed;
		if (!there && g_rlStage > 0)
		{
			g_rlPending = false;
			g_lastError = "relaunch: landed on " + GetCurrentLevelFilename() + " seed " + GameLab::g_genSeed;
			HWP::Log("devarena", "relaunch failed: " + g_lastError);
			return;
		}
		if (!there)
		{
			auto def = MissionDef::Get(uint(g_rlMission));
			if (def is null || g_rlFloor < 0 || g_rlFloor >= int(def.m_levels.length()))
			{
				g_rlPending = false;
				g_lastError = "relaunch: mission " + g_rlMission + " floor " + g_rlFloor + " is gone";
				HWP::Log("devarena", "relaunch failed: " + g_lastError);
				return;
			}
			auto rec = GetLocalPlayerRecord();
			g_ngp = float(max(0, min(rec is null ? 0 : rec.ngp, g_rlNgp)));
			GameLab::g_genSeed = uint(g_rlSeed);
			GameLab::g_genSeedPending = g_rlSeed != 0;
			g_rlStage = 1;
			HWP::Log("devarena", "relaunch entering " + g_rlLevel + " floor " + g_rlFloor + " seed " + g_rlSeed);
			MissionManager::SetMission(uint(g_rlMission), randi());
			MissionManager::g_module.m_missionLevelIndex = g_rlFloor;
			MissionManager::g_module.StartMission();
			return;
		}
		if (!there || g_arenaLevel != LevelKey())
			return;
		if (g_rlStage < 2)
		{
			g_rlStage = 2;
			g_rlWait = RL_SETTLE;
			return;
		}
		vec3 p = plr.m_unit.GetPosition();
		plr.m_unit.SetPosition(g_rlX, g_rlY, p.z, true);
		g_rlPending = false;
		int added = RestoreTrinkets(plr.m_record);
		auto preset = FindPreset(g_preset);
		array<string> bad;
		if (preset !is null)
			CheckPreset(preset, bad);
		g_lastAction = "relaunched" + (g_preset == "" ? "" : ": " + g_preset);
		HWP::Log("devarena", "relaunch restored " + RelaunchJson() + " trinkets " + added + "/" + g_rlTrinkets.length());
	}
}
}
