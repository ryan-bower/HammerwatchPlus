// GameLab::ConsoleLines - the console lines scenarios used to type, as verbs. Typing opens the
// console, which pauses the game (docs/RE_NOTES.md, 2026-10-19), so gamelab/session.py turns
// every such line into one of these and sends it through the inbox (gamelab-probe Inbox.as).
namespace GameLab
{
	// setvar <name> <value...>: SetVar with the cvar's own type (GetVarType); a String cvar
	// takes the rest of the line. The engine runs the cvar's change callback as the console's
	// assignment does (measured by gamelab/scenarios/inbox-check.json: cht_god, hwp_line).
	void VerbSetVar(const string &in id, array<string>@ args)
	{
		if (args.length() < 2)
		{
			Fail(id, "usage: setvar <name> <value>");
			return;
		}
		string name = args[0];
		auto t = GetVarType(name);
		string v = args[1];
		Json@ j = Reply(id, true);
		j.Str("name", name).Int("type", int(t));
		if (t == cvar_type::Bool)
		{
			bool b = v == "1" || v == "true";
			SetVar(name, b);
			j.Bool("value", GetVarBool(name));
		}
		else if (t == cvar_type::Int)
		{
			SetVar(name, parseInt(v));
			j.Int("value", GetVarInt(name));
		}
		else if (t == cvar_type::Float)
		{
			SetVar(name, parseFloat(v));
			j.Num("value", GetVarFloat(name));
		}
		else if (t == cvar_type::String)
		{
			string s = v;
			for (uint i = 2; i < args.length(); i++)
				s += " " + args[i];
			SetVar(name, s);
			j.Str("value", GetVarString(name));
		}
		else
		{
			Fail(id, "setvar: no cvar " + name + " of a settable type (type " + int(t) + ")");
			return;
		}
		Emit(j);
	}

	// cheat <function> [args]: the bodies of the game's console functions the scenarios typed
	//   ply_kill                       Console::Player::KillCFunc (Console/Player.as:12)
	//   cht_revive                     Console::Cheats::ReviveCFunc (Console/Cheats.as:983)
	//   cht_set_flag <flag> <0|1> <0|1>  SetFlagCFunc (Console/Cheats.as:921)
	//   cht_give_material <type|all> <n> GiveMaterialCFunc (Console/Cheats.as:889)
	//   cht_add_all_dyes               Console::Cheats::addAllDyesCFunc (Console/Cheats.as:1231)
	//   cht_unlock_town_flags          Console::Cheats::UnlockTownFlagsCFunc (Console/Cheats.as:146)
	//   mission_start <missionId>      Console::Missions::StartMission (MissionGameMode.as:84)
	//   cht_finish_level               Console::Cheats::FinishLevelCFunc (Console/Cheats.as:1117)
	//   dbg_show_stash                 Console::Cheats::ShowPlayerStashCFunc (Console/Cheats.as:1070)
	//   show_chat                      ShowChatCFunc (GameModes/MainMenuGameMode.as:3)
	//   cht_give_health <n>            GiveHealthCFunc (Console/Cheats.as:716)
	//   cht_damage <n>                 DamageCFunc (Console/Cheats.as:723)
	//   cht_give_mana <n>              GiveManaCFunc (Console/Cheats.as:754)
	//   cht_clear_trinkets             ClearTrinketsCFunc (Console/Cheats.as:702)
	//   cht_give_specific_trinket <id> GiveSpecificTrinketCfunc (Console/Cheats.as:621)
	//   cht_spawn_specific_equipment <id>  SpawnSpecificEquipmentCfunc (Console/Cheats.as:487); in
	//                                  the game's script, so mod base items exist (the console's
	//                                  copy runs in the menu's and has none, verb dropitem)
	//   cht_add_blueprint <id>         addSingleBlueprintCFunc (Console/Cheats.as:1246)
	//   cht_add_all_blueprints         addAllBlueprintsCFunc (Console/Cheats.as:1160)
	void VerbCheat(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: cheat <ply_kill|cht_revive|cht_set_flag|cht_give_material|cht_add_all_dyes|cht_unlock_town_flags|mission_start|cht_finish_level|dbg_show_stash|show_chat|cht_give_health|cht_damage|cht_give_mana|cht_clear_trinkets|cht_give_specific_trinket|cht_spawn_specific_equipment|cht_add_blueprint|cht_add_all_blueprints> [args]");
			return;
		}
		string fn = args[0];
		if (fn == "ply_kill")
		{
			Console::Player::KillCFunc();
		}
		else if (fn == "cht_revive")
		{
			Console::Cheats::ReviveCFunc();
		}
		else if (fn == "cht_set_flag")
		{
			if (args.length() < 4)
			{
				Fail(id, "usage: cheat cht_set_flag <flag> <0|1> <0|1>");
				return;
			}
			string flag = args[1];
			bool value = args[2] == "1" || args[2] == "true";
			bool persistent = args[3] == "1" || args[3] == "true";
			if (!value)
				g_flags.Delete(flag);
			else
				g_flags.Set(flag, persistent ? FlagState::Town : FlagState::Level);
			(Network::Message("SyncFlag") << flag << value << persistent).SendToAll();
		}
		else if (fn == "cht_give_material")
		{
			if (args.length() < 3)
			{
				Fail(id, "usage: cheat cht_give_material <type|all> <n>");
				return;
			}
			auto plr = GetLocalPlayerRecord();
			if (plr is null)
			{
				Fail(id, "cheat cht_give_material: no local player record");
				return;
			}
			int amount = parseInt(args[2]);
			if (args[1] == "all")
			{
				for (uint i = 0; i < plr.materials.length(); i++)
					plr.GiveMaterial(MaterialType(i), amount, true);
			}
			else
				plr.GiveMaterial(ParseMaterialType(args[1]), amount, true);
		}
		else if (fn == "cht_add_all_dyes")
		{
			if (g_myTownRecord is null)
			{
				Fail(id, "cheat cht_add_all_dyes: no town record");
				return;
			}
			Console::Cheats::addAllDyesCFunc();
		}
		else if (fn == "cht_unlock_town_flags")
		{
			if (g_myTownRecord is null)
			{
				Fail(id, "cheat cht_unlock_town_flags: no town record");
				return;
			}
			Console::Cheats::UnlockTownFlagsCFunc();
		}
		else if (fn == "mission_start")
		{
			if (args.length() < 2)
			{
				Fail(id, "usage: cheat mission_start <missionId>");
				return;
			}
			auto missionDef = MissionDef::Get(args[1]);
			if (missionDef is null)
			{
				Fail(id, "cheat mission_start: no mission " + args[1]);
				return;
			}
			if (!Platform::HasDLC("holy") && missionDef.m_setHash == HashString("heaven"))
			{
				Fail(id, "cheat mission_start: blocked without the holy DLC, as the game blocks it");
				return;
			}
			MissionManager::SetMission(args[1]);
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null)
			{
				Fail(id, "cheat mission_start: not in a BaseGameMode");
				return;
			}
			gm.m_windowManager.AddWindowObject(MissionLoadoutMenu(gm.m_guiBuilder));
		}
		else if (fn == "cht_finish_level")
		{
			if (GetLocalPlayer() is null)
			{
				Fail(id, "cheat cht_finish_level: no local player");
				return;
			}
			Console::Cheats::FinishLevelCFunc();
		}
		else if (fn == "dbg_show_stash")
		{
			if (cast<BaseGameMode>(g_gameMode) is null || g_myTownRecord is null)
			{
				Fail(id, "cheat dbg_show_stash: no game mode or town record");
				return;
			}
			Console::Cheats::ShowPlayerStashCFunc();
		}
		else if (fn == "show_chat")
		{
			ShowChatCFunc();
		}
		else if (fn == "cht_give_health" || fn == "cht_damage" || fn == "cht_give_mana")
		{
			if (args.length() < 2)
			{
				Fail(id, "usage: cheat " + fn + " <n>");
				return;
			}
			auto ply = GetLocalPlayer();
			if (ply is null)
			{
				Fail(id, "cheat " + fn + ": no local player");
				return;
			}
			int n = parseInt(args[1]);
			if (fn == "cht_give_health")
				ply.Heal(n);
			else if (fn == "cht_damage")
				ply.Damage(DamageInfo(null, n, false, true, 0), vec2(), vec2());
			else
				ply.GiveMana(n);
		}
		else if (fn == "cht_clear_trinkets")
		{
			auto plr = GetLocalPlayerRecord();
			if (plr is null)
			{
				Fail(id, "cheat cht_clear_trinkets: no local player record");
				return;
			}
			plr.trinketInventory.Clear();
		}
		else if (fn == "cht_give_specific_trinket")
		{
			auto plr = GetLocalPlayerRecord();
			auto item = args.length() > 1 ? Item::Trinket::Get(args[1]) : null;
			if (plr is null || item is null)
			{
				Fail(id, "cheat cht_give_specific_trinket: " + (plr is null ? "no local player record" : "no trinket " + (args.length() > 1 ? args[1] : "")));
				return;
			}
			if (!CheckGlobalConditionals(item.m_dropConds))
			{
				Fail(id, "cheat cht_give_specific_trinket: conditional blocked " + args[1]);
				return;
			}
			plr.GiveItem(item);
		}
		else if (fn == "cht_spawn_specific_equipment")
		{
			auto plr = GetLocalPlayerRecord();
			auto baseItem = args.length() > 1 ? Equipment::BaseItem::Get(args[1]) : null;
			if (plr is null || plr.actor is null || baseItem is null)
			{
				Fail(id, "cheat cht_spawn_specific_equipment: " + (baseItem is null ? "no BaseItem " + (args.length() > 1 ? args[1] : "") : "no local player"));
				return;
			}
			if (!CheckGlobalConditionals(baseItem.m_conditionals))
			{
				Fail(id, "cheat cht_spawn_specific_equipment: conditional blocked " + args[1]);
				return;
			}
			Equipment::Generator gen;
			gen.m_ilvl = plr.level;
			gen.m_qualities = Item::Quality(int(pow(2, randi(4))));
			auto item = gen.GenerateItem(baseItem);
			auto spawnPos = plr.actor.m_unit.GetPosition() + xyz(randdir() * (randf() + 1.0f) * 25);
			Item::DropItem(item, spawnPos, 1, true, null);
		}
		else if (fn == "cht_add_blueprint" || fn == "cht_add_all_blueprints")
		{
			if (g_myTownRecord is null)
			{
				Fail(id, "cheat " + fn + ": no town record");
				return;
			}
			if (fn == "cht_add_all_blueprints")
				Console::Cheats::addAllBlueprintsCFunc();
			else if (args.length() < 2)
			{
				Fail(id, "usage: cheat cht_add_blueprint <id>");
				return;
			}
			else
				g_myTownRecord.m_blueprints.SetBlueprint(args[1]);
		}
		else
		{
			Fail(id, "cheat: unknown function " + fn);
			return;
		}
		Emit(Reply(id, true).Str("fn", fn));
	}
}
