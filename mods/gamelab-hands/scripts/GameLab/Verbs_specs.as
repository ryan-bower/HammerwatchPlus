// gamelab-hands: verbs for the 4th specializations' checks (plan_specs). hasbuff, bind and dmgmuls only
// read; evade rolls the local player's real evade; mana sets the mana; buffnear buffs enemies.
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

	// dmgmuls: read-only. The local player's damage multipliers by type as the record's current
	// stats hold them (PlayerRecord.currStats: PhysicalDamageMul, FireDamageMul, ...; 1 = none),
	// what PlayerBase.DamageActor scales each part of a hit by (PlayerBase.as:928).
	void VerbDmgMuls(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		auto st = plr.m_record.currStats;
		Emit(Reply(id, true).Num("physical", st.PhysicalDamageMul).Num("fire", st.FireDamageMul).Num("ice", st.IceDamageMul)
			.Num("lightning", st.LightningDamageMul).Num("poison", st.PoisonDamageMul).Num("pure", st.PureDamageMul));
	}

	// buffnear <radius> <filter> <buffPath> [ms]: ApplyBuff(ActorBuff(player, def, 1, false, 0, ms))
	// on every live actor within radius whose .unit path or behavior type contains filter (as
	// kill matches), never the local player, as a debuff effect on a hit does; ms -1 or left
	// out keeps the def's duration. The enemy's own checks run (no-buffs, immune tags, debuff
	// scale: CompositeActorBehavior.ApplyBuff), so the reply says which took it. For holding an
	// enemy still (tweak/buffs/status_effects.sval:stun_greater) while a check runs. Capped.
	void VerbBuffNear(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 3)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: buffnear <radius> <filter> <buffPath> [ms]");
			return;
		}
		ActorBuffDef@ def = LoadActorBuff(args[2]);
		if (def is null)
		{
			Fail(id, "no buff '" + args[2] + "'");
			return;
		}
		int radius = int(parseInt(args[0]));
		int ms = args.length() > 3 ? int(parseInt(args[3])) : -1;
		vec2 center = xy(plr.m_unit.GetPosition());
		auto units = g_scene.FetchAllUnits(~0, center, radius);
		array<string> items;
		int n = 0, applied = 0;
		for (uint i = 0; i < units.length(); i++)
		{
			if (!units[i].IsValid() || units[i].IsDestroyed() || units[i] == plr.m_unit)
				continue;
			if (dist(center, xy(units[i].GetPosition())) > radius)
				continue;
			auto actor = cast<Actor>(units[i].GetScriptBehavior());
			if (actor is null || actor.IsDead())
				continue;
			if (units[i].GetDebugName().findFirst(args[1]) < 0 && Reflect::GetTypeName(actor).findFirst(args[1]) < 0)
				continue;
			bool ok = actor.ApplyBuff(ActorBuff(plr, def, 1.0f, false, 0, ms));
			n++;
			if (ok)
				applied++;
			if (items.length() < SPECS_CAP)
				items.insertLast(units[i].GetDebugName() + (ok ? " applied" : " refused"));
		}
		Emit(Reply(id, true).Int("count", n).Int("applied", applied).Str("actors", join(items, "; "))
			.Bool("truncated", uint(n) > items.length()));
	}

	void Register_specs()
	{
		RegisterVerb("mana", "<n>", Verb(VerbMana));
		RegisterVerb("hasbuff", "<path> [path ...]", Verb(VerbHasBuff));
		RegisterVerb("evade", "[tries]", Verb(VerbEvade));
		RegisterVerb("bind", "<skillId> <name>", Verb(VerbBind));
		RegisterVerb("dmgmuls", "", Verb(VerbDmgMuls));
		RegisterVerb("buffnear", "<radius> <filter> <buffPath> [ms]", Verb(VerbBuffNear));
	}
}
