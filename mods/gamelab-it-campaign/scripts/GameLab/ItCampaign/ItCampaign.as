// GameLab integration-test verbs for the campaign group (campaign, wavemode, abyss).
// Only vanilla symbols: the mods under test are read through what the game parsed
// (MissionDef, the level's SurvivalMission module), so this compiles in any scenario.
//
// Read-only: itc-mission, itc-survival, itc-prefab.
// Setup (labelled, each mirrors a game path): itc-kill, itc-use, itc-abandon.
namespace GameLab
{
	const uint ITC_LEVEL_CAP = 40;
	const uint ITC_KILL_CAP = 40;

	string ItCampaignLevelJson(MissionLevel@ lvl, uint index)
	{
		Json l;
		l.Int("i", index).Str("id", lvl.m_id).Str("level", lvl.m_level)
			.Str("theme", lvl.m_themeDef is null ? "" : lvl.m_themeDef.m_id)
			.Int("diff", lvl.m_diffLevel).Int("diffNgp", lvl.m_diffLevelNgp)
			.Str("module", lvl.m_moduleData is null ? "" : GetParamString(UnitPtr(), lvl.m_moduleData, "class", false, ""));
		return l.Close();
	}

	// itc-mission <missionId>|current: read-only. A MissionDef as the game parsed it
	// (Missions/MissionDef.as, MissionLevel.as): name (key and resolved), set hash,
	// hidden/test, base diff, span (GetLevelSpan), whether its conditionals pass for the
	// local player (CheckConditionals, what FetchMissionsFromSet filters on), and every
	// level (id, .lvl, theme, diff, diff-level-ngp, module class), capped at ITC_LEVEL_CAP.
	// "current" is MissionManager::GetCurrentMission() plus the level index, g_ngp and
	// whether the game is in town.
	void VerbItCampaignMission(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: itc-mission <missionId>|current");
			return;
		}
		bool current = args[0] == "current";
		MissionDef@ def = current ? MissionManager::GetCurrentMission() : MissionDef::Get(args[0]);
		if (def is null)
		{
			Fail(id, current ? "no current mission" : "no mission '" + args[0] + "'");
			return;
		}
		array<string> levels;
		for (uint i = 0; i < def.m_levels.length() && i < ITC_LEVEL_CAP; i++)
			levels.insertLast(ItCampaignLevelJson(def.m_levels[i], i));
		auto rec = GetLocalPlayerRecord();
		auto span = def.m_levels.length() > 0 ? def.GetLevelSpan() : ivec2(0, 0);
		auto j = Reply(id, true).Str("mission", def.m_id).Str("nameKey", def.m_name)
			.Str("name", Resources::GetString(def.m_name)).Int("setHash", int64(def.m_setHash))
			.Bool("hidden", def.m_hidden).Bool("test", def.m_test).Num("spawnChance", def.m_spawnChance)
			.Int("baseDiff", def.m_baseDiffLevel).Int("spanLo", span.x).Int("spanHi", span.y)
			.Bool("conditionsOk", rec !is null && CheckConditionals(def.m_conditionals, rec))
			.Int("count", def.m_levels.length())
			.Int("truncated", def.m_levels.length() > ITC_LEVEL_CAP ? int(def.m_levels.length() - ITC_LEVEL_CAP) : 0)
			.Raw("levels", RawArray(levels));
		if (current)
		{
			int index = MissionManager::g_module is null ? -1 : int(MissionManager::g_module.m_missionLevelIndex);
			j.Int("index", index).Str("levelId", index >= 0 && index < int(def.m_levels.length()) ? def.m_levels[index].m_id : "")
				.Bool("inTown", g_inTown);
		}
		float ngp = g_ngp;
		j.Num("ngp", ngp);
		Emit(j);
	}

	// itc-survival: read-only. The current level's SurvivalMission module
	// (Missions/SurvivalMission.as, made from the level's "module" data by
	// MissionGameMode.as:182-187), found in the game mode's m_modules: clock, XP and goal
	// (GetXPGoal), spawn events, whether the boss spawned or the clock ran out, whether
	// the "boss" param resolved to a prefab (Resources::GetPrefab), the rank reward
	// globals. found=false (ok) when the level has none.
	void VerbItCampaignSurvival(const string &in id, array<string>@ args)
	{
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		SurvivalMission@ sm = null;
		if (gm !is null)
		{
			for (uint i = 0; i < gm.m_modules.length() && sm is null; i++)
				@sm = cast<SurvivalMission>(gm.m_modules[i]);
		}
		float ngp = g_ngp;
		auto j = Reply(id, true).Bool("found", sm !is null).Int("survivalReward", g_survivalReward)
			.Num("ngp", ngp).Bool("inTown", g_inTown);
		if (sm !is null)
		{
			j.Int("timer", sm.m_timerC).Int("timeLimit", sm.m_timeLimit).Int("xp", sm.m_experienceC)
				.Int("expGoal", sm.m_expGoal).Int("goal", sm.GetXPGoal()).Int("rank", sm.m_rank)
				.Num("rankMultiplier", sm.m_rankMultiplier).Num("xpMultiplier", sm.m_xpMultiplier)
				.Num("rankXpMultiplier", sm.m_rankXPMultiplier)
				.Int("spawnEvents", sm.m_spawnEventC).Int("numSpawnEvents", sm.m_numSpawnEvents)
				.Int("spawnActions", sm.m_spawnEventActions.length())
				.Bool("spawnedBoss", sm.m_spawnedBoss).Bool("failedFromTime", sm.m_failedFromTime)
				.Bool("bossPrefabNull", sm.m_bossPrefab is null).Int("maxRankReward", sm.m_maxRankReward)
				.Str("stat", sm.m_increasedRank);
		}
		Emit(j);
	}

	// itc-prefab <path>: read-only. Whether the path resolves as a prefab
	// (Resources::GetPrefab, what SurvivalMission's "boss" param goes through) and as a
	// unit producer (Resources::GetUnitProducer).
	void VerbItCampaignPrefab(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: itc-prefab <path>");
			return;
		}
		Emit(Reply(id, true).Str("path", args[0]).Bool("prefab", Resources::GetPrefab(args[0]) !is null)
			.Bool("unit", Resources::GetUnitProducer(args[0]) !is null));
	}

	// itc-kill <filter|*> [radius]: SETUP, a cheat. The cht_kill_all cheat's body
	// (Console/Cheats.as:970-980, gamelab-hands `cull`) with the local player as the
	// killer: CompositeActorBehavior::Kill(killer, 0) -> OnDeath -> killer.KilledActor
	// (CompositeActorBehavior.as:576-581, 870-871) -> Player::KilledActor, which runs the
	// PlayerKilledActor hook (Player.as:232-271), as a player's own killing blow does.
	// Live enemy actors within radius (default 400) of the player whose unit file or
	// behaviour type contains filter ("*" = any). Untargetable ones are killed too and
	// counted. The kill list is capped at ITC_KILL_CAP.
	void VerbItCampaignKill(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: itc-kill <filter|*> [radius]");
			return;
		}
		PlayerBase@ plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		string filter = args[0];
		int radius = args.length() > 1 ? int(parseInt(args[1])) : 400;
		vec2 center = xy(plr.m_unit.GetPosition());
		auto units = g_scene.FetchActorsWithOtherTeam(g_team_player, center, radius);
		array<string> killed;
		int matched = 0;
		int untargetable = 0;
		for (uint i = 0; i < units.length(); i++)
		{
			if (!units[i].IsValid() || units[i].IsDestroyed())
				continue;
			ref@ b = units[i].GetScriptBehavior();
			Actor@ a = cast<Actor>(b);
			if (a is null || a.IsDead())
				continue;
			string name = units[i].GetDebugName();
			if (filter != "*" && name.findFirst(filter) < 0 && Reflect::GetTypeName(b).findFirst(filter) < 0)
				continue;
			matched++;
			if (!a.IsTargetable())
				untargetable++;
			if (killed.length() < ITC_KILL_CAP)
				killed.insertLast(name);
			a.Kill(plr, 0);
		}
		Emit(Reply(id, true).Str("filter", filter).Int("radius", radius).Int("found", units.length())
			.Int("killed", matched).Int("untargetable", untargetable)
			.Int("truncated", matched > int(ITC_KILL_CAP) ? matched - int(ITC_KILL_CAP) : 0)
			.Raw("names", StrArray(killed)));
	}

	// itc-use <filter/#id> [radius]: SETUP. What the Use key does for the nearest usable unit
	// within radius (default 300) whose unit file or behaviour type contains filter, or
	// with "#<id>" the unit of that id (a level's world script has its script id: the
	// UseTrigger an exit pad's area belongs to, whose unit stands elsewhere)
	// (Player.as:1341-1356: CanUse, then Use; on a netsynced unit the host also sends
	// UseUnit), without the sensor contact the key needs. Replies canUse and used.
	void VerbItCampaignUse(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: itc-use <filter> [radius]");
			return;
		}
		PlayerBase@ plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int radius = args.length() > 1 ? int(parseInt(args[1])) : 300;
		int byId = args[0].findFirst("#") == 0 ? int(parseInt(args[0].substr(1))) : -1;
		vec2 center = xy(plr.m_unit.GetPosition());
		auto units = g_scene.FetchAllUnits(~0, center, radius);
		IUsable@ best = null;
		UnitPtr bestUnit;
		float bestD = 1e12f;
		for (uint i = 0; i < units.length(); i++)
		{
			if (!units[i].IsValid() || units[i].IsDestroyed())
				continue;
			ref@ b = units[i].GetScriptBehavior();
			auto usable = cast<IUsable>(b);
			if (usable is null)
				continue;
			if (byId >= 0 ? units[i].GetId() != byId
				: units[i].GetDebugName().findFirst(args[0]) < 0 && Reflect::GetTypeName(b).findFirst(args[0]) < 0)
				continue;
			float d = dist(center, xy(units[i].GetPosition()));
			if (d < bestD)
			{
				bestD = d;
				@best = usable;
				bestUnit = units[i];
			}
		}
		if (best is null)
		{
			Fail(id, "no usable '" + args[0] + "' within " + radius);
			return;
		}
		bool canUse = best.CanUse(plr);
		if (canUse)
		{
			UnitPtr unit = best.GetUseUnit();
			UnitProducer@ prod = unit.GetUnitProducer();
			if (prod !is null && prod.GetNetSyncMode() == NetSyncMode::None)
				best.Use(plr);
			else if (Network::IsServer())
			{
				(Network::Message("UseUnit") << unit << plr.m_unit).SendToAll();
				best.Use(plr);
			}
		}
		Emit(Reply(id, true).Int("unit", bestUnit.GetId()).Str("name", bestUnit.GetDebugName())
			.Num("dist", bestD).Bool("canUse", canUse).Bool("used", canUse));
	}

	// itc-abandon: SETUP. The pause menu's Abandon -> yes (GUI/WindowMainMenu.as:177-181:
	// GlobalCache main_restart = 1), which HWR2GameMode::UpdateFrame turns into
	// MissionManager::AbortMission(Aborted) -> ChangeLevel(levels/town.lvl)
	// (GameModes/HWR2GameMode.as:188-191, Missions/MissionManager.as:83-94).
	void VerbItCampaignAbandon(const string &in id, array<string>@ args)
	{
		if (g_inTown)
		{
			Fail(id, "in town: nothing to abandon");
			return;
		}
		GlobalCache::Set("main_restart", "1");
		Emit(Reply(id, true).Str("did", "main_restart"));
	}
}

namespace Modules
{
	class GameLabItCampaignModule : Module
	{
		GameLabItCampaignModule()
		{
			super("gamelab-it-campaign");
			GameLab::RegisterVerb("itc-mission", "<missionId>|current", GameLab::Verb(GameLab::VerbItCampaignMission));
			GameLab::RegisterVerb("itc-survival", "", GameLab::Verb(GameLab::VerbItCampaignSurvival));
			GameLab::RegisterVerb("itc-prefab", "<path>", GameLab::Verb(GameLab::VerbItCampaignPrefab));
			GameLab::RegisterVerb("itc-kill", "<filter|*> [radius]", GameLab::Verb(GameLab::VerbItCampaignKill));
			GameLab::RegisterVerb("itc-use", "<filter|#id> [radius]", GameLab::Verb(GameLab::VerbItCampaignUse));
			GameLab::RegisterVerb("itc-abandon", "", GameLab::Verb(GameLab::VerbItCampaignAbandon));
		}
	}
}
