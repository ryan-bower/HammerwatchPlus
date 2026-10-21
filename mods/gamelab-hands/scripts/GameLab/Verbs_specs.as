// gamelab-hands: verbs for the 4th specializations' checks (plan_specs). hasbuff and bind only
// read; evade rolls the local player's real evade; stacks and mana set a
// stack count and the mana.
namespace GameLab
{
	const uint SPECS_CAP = 16;

	// hasbuff <path> [path ...]: for each buff path (file:name, as LoadActorBuff takes it),
	// whether the local player has it (ActorBuffList.m_buffs, matched on the def's
	// m_pathHash), its ms left, intensity and HUD icon flag. Buffs with no display name (the
	// buffs verb lists m_name) are found this way. Read-only, capped.
	void VerbHasBuff(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 1)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: hasbuff <path> [path ...]");
			return;
		}
		array<string> items;
		for (uint a = 0; a < args.length() && items.length() < SPECS_CAP; a++)
		{
			auto def = LoadActorBuff(args[a]);
			Json j;
			j.Str("path", args[a]).Bool("def", def !is null);
			ActorBuff@ found = null;
			for (uint i = 0; def !is null && i < plr.m_buffs.m_buffs.length(); i++)
			{
				auto b = plr.m_buffs.m_buffs[i];
				if (b !is null && b.m_def !is null && b.m_def.m_pathHash == def.m_pathHash)
					@found = b;
			}
			j.Bool("on", found !is null);
			if (found !is null)
				j.Int("left", found.m_duration).Int("dur", found.m_def.m_duration).Num("intensity", found.m_intensity)
					.Bool("hud", found.m_def.m_hud !is null);
			items.insertLast(j.Close());
		}
		Emit(Reply(id, true).Int("now", int(g_scene.GetTime())).Raw("buffs", RawArray(items))
			.Bool("truncated", args.length() > SPECS_CAP));
	}

	// evade [tries]: Player.Evade(null) until one rolls, at most tries times (default 40): the
	// real roll on currStats.EvadeChance and the Evasion modifiers, and on a success the evade
	// triggers (EffectTrigger::Evade), the PlayerEvaded message and the "Evaded" text, as when
	// an attack is dodged (Player.as:348). Replies the tries, whether one evaded, the chance
	// and the health before and after.
	void VerbEvade(const string &in id, array<string>@ args)
	{
		auto plr = cast<Player>(GetLocalPlayer());
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int tries = args.length() > 0 ? max(1, min(200, parseInt(args[0]))) : 40;
		int hp0 = plr.m_record.CurrentHealth();
		int n = 0;
		bool evaded = false;
		while (n < tries && !evaded)
		{
			n++;
			evaded = plr.Evade(null);
		}
		Emit(Reply(id, true).Int("tries", n).Bool("evaded", evaded).Num("chance", plr.m_record.currStats.EvadeChance)
			.Int("hp0", hp0).Int("hp", plr.m_record.CurrentHealth()).Int("hpMax", plr.m_record.MaxHealth()));
	}

	// bind <skillId> <name>: a learned skill's current bind (its level's and its orbs'), read
	// with PlayerBase.PrepareSkillFetchData + FetchData as a summon reads its skill's binds.
	// Read-only.
	void VerbBind(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || args.length() < 2)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: bind <skillId> <name>");
			return;
		}
		uint skill = HashString(args[0]);
		bool learned = false;
		for (uint i = 0; i < plr.m_skills.length(); i++)
		{
			if (plr.m_skills[i] !is null && plr.m_skills[i].m_skillId == skill)
				learned = true;
		}
		if (!learned)
		{
			Fail(id, "skill not live: " + args[0]);
			return;
		}
		plr.PrepareSkillFetchData(skill);
		auto sv = plr.FetchData(args[1]);
		string v = "";
		string t = "none";
		if (sv !is null)
		{
			if (sv.GetType() == SValueType::Integer) { t = "int"; v = "" + sv.GetInteger(); }
			else if (sv.GetType() == SValueType::Float) { t = "float"; v = "" + sv.GetFloat(); }
			else if (sv.GetType() == SValueType::String) { t = "string"; v = sv.GetString(); }
			else t = "other";
		}
		Emit(Reply(id, true).Str("skill", args[0]).Str("name", args[1]).Str("type", t).Str("value", v));
	}

	// stacks <path> <n>: sets the local player's count of a buff stack (file:id, as
	// ActorBuffStackDef::Get takes it) with PlayerBase.AddStacks(the difference), the call an
	// AddStacks effect makes; for the checks that need a count the game would take long to
	// build (Static Charge from spell crits). Replies the count before and after.
	void VerbStacks(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || args.length() < 2)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: stacks <path> <n>");
			return;
		}
		auto def = ActorBuffStackDef::Get(args[0]);
		if (def is null)
		{
			Fail(id, "no stack " + args[0]);
			return;
		}
		int was = plr.GetStacks(def);
		int want = max(0, parseInt(args[1]));
		if (want != was)
			plr.AddStacks(plr, def, want - was);
		Emit(Reply(id, true).Str("path", args[0]).Int("was", was).Int("now", plr.GetStacks(def)));
	}

	// mana <n>: sets the local player's mana to n (m_record.mana, a fraction of MaxMana), so a
	// check can see mana given back that the cap would otherwise eat. Replies before and after.
	void VerbMana(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || args.length() < 1)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: mana <n>");
			return;
		}
		float maxm = float(max(1, plr.m_record.MaxMana()));
		float was = plr.m_record.mana * maxm;
		plr.m_record.mana = clamp(parseFloat(args[0]) / maxm, 0.0f, 1.0f);
		Emit(Reply(id, true).Num("was", was).Num("now", plr.m_record.mana * maxm).Int("max", int(maxm)));
	}

	void Register_specs()
	{
		RegisterVerb("mana", "<n>", Verb(VerbMana));
		RegisterVerb("stacks", "<path> <n>", Verb(VerbStacks));
		RegisterVerb("hasbuff", "<path> [path ...]", Verb(VerbHasBuff));
		RegisterVerb("evade", "[tries]", Verb(VerbEvade));
		RegisterVerb("bind", "<skillId> <name>", Verb(VerbBind));
	}
}
