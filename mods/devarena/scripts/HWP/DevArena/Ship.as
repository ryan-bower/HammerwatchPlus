// Ship check (docs/devarena/SPEC.md HP6, "Decided during build" 27): a spec mod as the game
// loaded it, and as the real Subclass Picker NPC shows it. Read-only; the pick itself is the
// player's (the NPC's Use key, the picker's arrows and its MenuContext key: gamelab/bots/
// devarena_pick_spec.py). tools/devarena/ship_check.py turns the reply and the tooltip lint into
// the report.
namespace HWP
{
namespace DevArena
{
	const uint SHIP_SKILL_CAP = 16;
	const uint SHIP_PARAM_CAP = 8;

	PlayerClass@ ShipClass(const string &in id)
	{
		for (uint i = 0; i < PlayerClass::Instances.length(); i++)
			if (PlayerClass::Instances[i].m_id == id)
				return PlayerClass::Instances[i];
		return null;
	}

	PlayerClass@ ShipClassByHash(uint h)
	{
		for (uint i = 0; i < PlayerClass::Instances.length(); i++)
			if (PlayerClass::Instances[i].m_idHash == h)
				return PlayerClass::Instances[i];
		return null;
	}

	// a lang key as text (PlayerSkillDef stores its name already resolved, PlayerClass.as:69;
	// a description stays a key, :70); a missing key comes back as itself
	string ShipText(const string &in s)
	{
		return s.substr(0, 1) == "." ? Resources::GetString(s) : s;
	}

	bool Resolved(const string &in text)
	{
		return text != "" && text.substr(0, 1) != ".";
	}

	string ShipSkillJson(PlayerSkillDef@ def, array<string>@ unresolved)
	{
		string name = ShipText(def.m_name);
		if (!Resolved(name))
			unresolved.insertLast(def.m_id + ".name");
		if (def.m_description != "" && !Resolved(ShipText(def.m_description)))
			unresolved.insertLast(def.m_id + ".description");
		array<string> ps;
		for (uint i = 0; i < def.m_descParams.length() && i < SHIP_PARAM_CAP; i++)
		{
			auto dp = def.m_descParams[i];
			ps.insertLast(dp.m_name + "=" + join(dp.m_levels, "/"));
		}
		int cost = 0;
		for (uint i = 0; i < def.m_levelSkillCost.length(); i++)
			cost += def.m_levelSkillCost[i];
		GameLab::Json j;
		j.Str("id", def.m_id).Str("name", name).Bool("icon", def.m_icon !is null)
			.Int("levels", def.m_levelParams.length()).Int("cost", cost).Int("mods", def.m_modSkills.length())
			.Raw("params", GameLab::StrArray(ps)).Bool("paramsCut", def.m_descParams.length() > SHIP_PARAM_CAP);
		return j.Close();
	}

	// da-ship <classId>: read-only. The class as PlayerClass parsed it (name and description
	// resolved through the lang files, icon, parent, skills with their tooltip params and star
	// cost, every unresolved lang key), where the picker lists it among its siblings
	// (SubclassPickWindow's order, SubclassPickShopContent.as:28-49), the player (class, level,
	// whether it is picked), and the picker window when it is on top: the class it shows and its
	// texts.
	void VerbShip(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			GameLab::Fail(id, "usage: da-ship <classId>");
			return;
		}
		auto cls = ShipClass(args[0]);
		if (cls is null)
		{
			GameLab::Fail(id, "no class '" + args[0] + "'");
			return;
		}
		auto j = GameLab::Reply(id, true).Str("class", cls.m_id);
		array<string> unresolved;
		string name = ShipText(cls.m_name);
		if (!Resolved(name))
			unresolved.insertLast("class.name");
		string desc = ShipText(cls.m_description);
		if (cls.m_description != "" && !Resolved(desc))
			unresolved.insertLast("class.description");
		j.Str("name", name).Str("description", desc).Bool("icon", cls.m_icon !is null);
		auto parent = ShipClassByHash(cls.parent);
		j.Str("parent", parent is null ? "" : parent.m_id);

		array<string> siblings;
		int at = -1;
		for (uint i = 0; i < PlayerClass::Instances.length(); i++)
		{
			if (PlayerClass::Instances[i].parent != cls.parent)
				continue;
			if (PlayerClass::Instances[i] is cls)
				at = siblings.length();
			siblings.insertLast(PlayerClass::Instances[i].m_id);
		}
		j.Raw("siblings", GameLab::StrArray(siblings)).Int("pickerIndex", at);

		array<string> skills;
		int cost = 0;
		for (uint i = 0; i < cls.m_skillDefs.length() && i < SHIP_SKILL_CAP; i++)
		{
			skills.insertLast(ShipSkillJson(cls.m_skillDefs[i], unresolved));
			for (uint k = 0; k < cls.m_skillDefs[i].m_levelSkillCost.length(); k++)
				cost += cls.m_skillDefs[i].m_levelSkillCost[k];
		}
		j.Int("skillCount", cls.m_skillDefs.length()).Bool("skillsCut", cls.m_skillDefs.length() > SHIP_SKILL_CAP)
			.Int("stars", cost).Raw("skills", GameLab::RawArray(skills));
		if (cls.m_skillDefs.length() >= 2)
		{
			// what the picker window shows for it (SetCurrSubclass: the last two skill defs)
			j.Str("pickerActive", cls.m_skillDefs[cls.m_skillDefs.length() - 2].m_id)
				.Str("pickerPassive", cls.m_skillDefs[cls.m_skillDefs.length() - 1].m_id);
		}
		j.Raw("unresolved", GameLab::StrArray(unresolved)).Int("unresolvedCount", unresolved.length());

		auto plr = LocalPlayer();
		auto rec = GetLocalPlayerRecord();
		j.Str("playerClass", (plr is null || plr.m_record.playerClass is null) ? "" : plr.m_record.playerClass.m_id)
			.Int("playerLevel", rec is null ? 0 : rec.level)
			.Bool("picked", plr !is null && plr.m_record.playerClass is cls);

		auto gm = cast<BaseGameMode>(g_gameMode);
		auto top = (gm is null || gm.m_windowManager is null) ? null : gm.m_windowManager.GetCurrentWindow();
		auto win = cast<SubclassPickWindow>(top);
		j.Str("window", top is null ? "" : Reflect::GetTypeName(top)).Bool("picker", win !is null);
		if (win !is null && win.m_classes.length() > 0)
		{
			int idx = win.m_currPickedIndex;
			j.Str("shows", (idx >= 0 && idx < int(win.m_classes.length())) ? win.m_classes[idx].m_id : "")
				.Int("shownIndex", idx).Int("offered", win.m_classes.length());
			array<string> ids = { "picked-class", "class-curr", "skill-active-name", "skill-passive-name" };
			for (uint i = 0; i < ids.length(); i++)
			{
				auto t = cast<TextWidget>(win.m_widget.GetWidgetById(ids[i]));
				j.Str(ids[i], t is null ? "" : t.m_str);
			}
		}
		GameLab::Emit(j);
	}

	// da-tierup <buildingId>: setup (cheat). What the town builder's upgrade does
	// (Town/BuildingBuilder.as:91-99: IncrementVariationOnBuilding, SavePlayerAndTown) minus
	// the cost and the cutscene; TownRecord.Refresh rebuilds the plot. HP6 takes the guild hall
	// to tier 3, where the Subclass Picker stands (guild_hall_tier_3.pfb and up). Refused when
	// not built or while a window is open. Same as gamelab-it-pets' itpets_tierup, which needs
	// the pets mod.
	void VerbTierUp(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			GameLab::Fail(id, "usage: da-tierup <buildingId>");
			return;
		}
		auto def = BuildingManagement::BuildingDef::Get(HashString(args[0]));
		if (def is null || g_myTownRecord is null)
		{
			GameLab::Fail(id, "no building '" + args[0] + "' (or no town record)");
			return;
		}
		int before = g_myTownRecord.GetVariationOnBuilding(def.m_idHash);
		if (before < 0)
		{
			GameLab::Fail(id, "'" + args[0] + "' is not built");
			return;
		}
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null && gm.m_windowManager !is null && gm.m_windowManager.GetCurrentWindow() !is null)
		{
			GameLab::Fail(id, "close the window first");
			return;
		}
		g_myTownRecord.IncrementVariationOnBuilding(def);
		auto ag = cast<AGameplayGameMode>(g_gameMode);
		if (ag !is null)
			ag.SavePlayerAndTown();
		GameLab::Emit(GameLab::Reply(id, true).Int("before", before)
			.Int("after", g_myTownRecord.GetVariationOnBuilding(def.m_idHash)).Int("max", int(def.m_variations.length()) - 1));
	}
}
}
