// gamelab-hands: verbs for the 4th specializations' checks (plan_specs). hasbuff, bind and dmgmuls only
// read; evade rolls the local player's real evade; mana sets the mana; buffnear buffs enemies;
// damageme and damagefrom hurt the local player through the real damage path.
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
				j.Int("left", found.m_duration).Int("dur", found.m_def.m_duration).Raw("intensity", formatFloat(found.m_intensity, "", 0, 9))
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

	// damageme <amount> [dot]: Player.Damage on the local player with <amount> pure damage, no
	// attacker (the trap path: Tweak::PlayerDmgTakenTrap scales it) and TrueStrike (no block), the
	// whole damage path (modifiers' DamageTaken included); "dot" marks it damage over time. God
	// mode (cht_god) returns 0 before any of it. Replies with what Damage returned (the health
	// the hit took), hp and mana before and after.
	void VerbDamageMe(const string &in id, array<string>@ args)
	{
		auto plr = cast<Player>(GetLocalPlayer());
		if (plr is null || args.length() < 1)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: damageme <amount> [dot]");
			return;
		}
		DamageInfo dmg(null);
		dmg.PureDamage = uint(max(0, parseInt(args[0])));
		dmg.TrueStrike = true;
		dmg.DoT = args.length() > 1 && args[1] == "dot";
		float maxm = float(max(1, plr.m_record.MaxMana()));
		float hp0 = plr.m_record.hp;
		float m0 = plr.m_record.mana * maxm;
		vec2 pos = xy(plr.m_unit.GetPosition());
		int took = plr.Damage(dmg, pos, vec2(0, -1));
		Emit(Reply(id, true).Int("took", took).Num("hp0", hp0).Num("hp", float(plr.m_record.hp)).Num("mana0", m0)
			.Num("mana", plr.m_record.mana * maxm).Int("max", int(maxm)).Bool("dead", plr.IsDead()));
	}

	// damagefrom <attackerUnitId> <amount> <melee|ranged|spell>: one real Player.Damage
	// call with a nearby live, non-player Actor on a different team as attacker. Mirrors
	// Player/Player.as Damage, including its melee-only currStats.Thorns branch; never calls
	// a modifier callback directly. Pure damage isolates melee/ranged reflection, FireDamage
	// marks a spell. TrueStrike removes block randomness. This is controlled measurement,
	// not evidence that an enemy naturally chose or executed an attack. Same-frame health
	// readbacks prevent regeneration between observations. Keep normalized health for
	// compatibility and emit HP units before JSON rounding for small reflection amounts.
	void VerbDamageFrom(const string &in id, array<string>@ args)
	{
		auto plr = cast<Player>(GetLocalPlayer());
		if (plr is null || plr.IsDead() || args.length() != 3)
		{
			Fail(id, "usage: damagefrom <attackerUnitId> <amount> <melee|ranged|spell>; needs a live local player");
			return;
		}
		int unitId = int(parseInt(args[0]));
		int amount = int(parseInt(args[1]));
		string mode = args[2];
		if (amount < 1 || amount > 1000 || (mode != "melee" && mode != "ranged" && mode != "spell"))
		{
			Fail(id, "amount must be 1..1000 and mode melee, ranged or spell");
			return;
		}
		auto unit = g_scene.GetUnit(unitId);
		if (!unit.IsValid() || unit.IsDestroyed())
		{
			Fail(id, "attacker unit is not live");
			return;
		}
		auto attacker = cast<Actor>(unit.GetScriptBehavior());
		if (attacker is null || attacker.IsDead() || cast<PlayerBase>(attacker) !is null
			|| attacker.Team == plr.Team || dist(xy(unit.GetPosition()), xy(plr.m_unit.GetPosition())) > 256.0f)
		{
			Fail(id, "attacker must be a live non-player actor on another team within 256px");
			return;
		}
		int hp0 = plr.m_record.CurrentHealth();
		float attackerHp0 = attacker.GetHealth();
		int attackerMaxHp = attacker.GetMaxHp();
		float thorns = float(plr.m_record.currStats.Thorns);
		DamageInfo dmg(attacker);
		if (mode == "spell")
			dmg.FireDamage = uint(amount);
		else
			dmg.PureDamage = uint(amount);
		dmg.Melee = mode == "melee";
		dmg.TrueStrike = true;
		int took = plr.Damage(dmg, xy(plr.m_unit.GetPosition()), vec2(0, -1));
		Emit(Reply(id, true).Int("amount", amount).Str("mode", mode).Int("took", took)
			.Int("hp0", hp0).Int("hp", plr.m_record.CurrentHealth()).Num("thorns", thorns)
			.Int("attacker_unit", unitId).Num("attacker_hp0", attackerHp0).Num("attacker_hp", attacker.GetHealth())
			.Num("attacker_hp0_exact", double(attackerHp0) * double(attackerMaxHp))
			.Num("attacker_hp_exact", double(attacker.GetHealth()) * double(attackerMaxHp))
			.Int("attacker_hpMax", attackerMaxHp).Bool("attacker_dead", attacker.IsDead()));
	}

	void Register_specs()
	{
		RegisterVerb("mana", "<n>", Verb(VerbMana));
		RegisterVerb("hasbuff", "<path> [path ...]", Verb(VerbHasBuff));
		RegisterVerb("evade", "[tries]", Verb(VerbEvade));
		RegisterVerb("bind", "<skillId> <name>", Verb(VerbBind));
		RegisterVerb("dmgmuls", "", Verb(VerbDmgMuls));
		RegisterVerb("buffnear", "<radius> <filter> <buffPath> [ms]", Verb(VerbBuffNear));
		RegisterVerb("damageme", "<amount> [dot]", Verb(VerbDamageMe));
		RegisterVerb("damagefrom", "<attackerUnitId> <amount> <melee|ranged|spell>", Verb(VerbDamageFrom));
		Register_qa_crit();
		Register_qa_static_observe();
		Register_qa_spec_impact();
		Register_qa_observe();
	}
}
