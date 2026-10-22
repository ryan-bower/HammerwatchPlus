// GameLab-only, bounded critical-chance setup for real cast/damage regressions.
// One expiring ActorBuff sets a selected skill's crit modifier and zeros global spell
// crit, so other spells are controlled noncritical sources. Native rebuild restores both.
// DamageActor, PlayerBase.DamageDealt and CriticalHit dispatch are never bypassed.
namespace GameLab
{
	const string QA_CRIT_BUFF = "gamelab/qa_crit_buffs.sval:qa_skill_crit";
	const int QA_CRIT_MAX_MS = 60000;
	bool g_qaCritActive = false;
	uint g_qaCritSkill = 0;
	float g_qaCritChance = 0;
	float g_qaCritOriginal = 0;
	PlayerBase@ g_qaCritOwner;
	ActorBuffDef@ g_qaCritDef;

	// Native ModifySkills resets m_modCritChance before applying ordered SkillModifiers.
	// A buff-owned modifier survives that rebuild; a one-off assignment would not.
	class QASkillCrit : Modifiers::SkillModifier
	{
		QASkillCrit(UnitPtr unit, SValue& params)
		{
			super(unit, params);
			Ordering = 1000000;
		}

		void Modify(Skills::Skill@ skill, float intensity) override
		{
			if (g_qaCritActive && skill !is null && skill.m_skillId == g_qaCritSkill)
				skill.m_modCritChance = g_qaCritChance;
		}
	}

	// A separate native stat modifier controls the class/gear spell-crit contribution.
	// The skill modifier above cannot cancel that independently rebuilt contribution.
	class QASpellCrit : Modifiers::StatModifier
	{
		QASpellCrit(UnitPtr unit, SValue& params)
		{
			super(unit, params);
			Ordering = 1000000;
		}

		void Modify(PlayerRecord@ player, PlayerStats@ stats, float intensity) override
		{
			if (g_qaCritActive && g_qaCritOwner !is null && player is g_qaCritOwner.m_record)
				stats.SpellCritChance = 0;
		}
	}

	ActorBuff@ QACritBuff()
	{
		if (g_qaCritOwner is null || !g_qaCritOwner.m_unit.IsValid() || g_qaCritDef is null)
			return null;
		for (uint i = 0; i < g_qaCritOwner.m_buffs.m_buffs.length(); i++)
		{
			auto b = g_qaCritOwner.m_buffs.m_buffs[i];
			if (b !is null && b.m_def !is null && b.m_def.m_pathHash == g_qaCritDef.m_pathHash && b.m_duration > 0)
				return b;
		}
		return null;
	}

	void QACritRebuild(PlayerBase@ plr)
	{
		plr.RefreshModifiers();
		// Make this reply an immediate readback as well as preserving future native rebuilds.
		plr.m_record.modifiers.ModifySkills(plr, plr.m_skills);
	}

	void QACritRestore()
	{
		g_qaCritActive = false;
		if (g_qaCritOwner !is null && g_qaCritOwner.m_unit.IsValid() && g_qaCritDef !is null)
		{
			// Match only this uniquely named lab fixture; preserve every unrelated buff.
			for (int i = int(g_qaCritOwner.m_buffs.m_buffs.length()) - 1; i >= 0; i--)
			{
				auto b = g_qaCritOwner.m_buffs.m_buffs[i];
				if (b !is null && b.m_def !is null && b.m_def.m_pathHash == g_qaCritDef.m_pathHash)
				{
					b.Clear();
					g_qaCritOwner.m_buffs.m_buffs.removeAt(i);
				}
			}
			QACritRebuild(g_qaCritOwner);
		}
		@g_qaCritOwner = null;
		@g_qaCritDef = null;
		g_qaCritSkill = 0;
	}

	bool QACritNumber(const string &in value)
	{
		int dots = 0;
		int digits = 0;
		for (uint i = 0; i < value.length(); i++)
		{
			string c = value.substr(i, 1);
			if (c == ".")
				dots++;
			else if ("0123456789".findFirst(c) >= 0)
				digits++;
			else
				return false;
		}
		return digits > 0 && dots <= 1;
	}

	// skillcrit <skillId> [0..1|restore]: without the second argument, reports fields
	// and cleans any expired override or override belonging to a previous local actor.
	// At most one local skill may be overridden at once; every set expires in 60 s of
	// scene time. Restore uses the current native modifiers, not a stale field snapshot.
	void VerbSkillCrit(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || args.length() < 1 || args.length() > 2)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: skillcrit <skillId> [0..1|restore]");
			return;
		}
		if (g_qaCritActive && (g_qaCritOwner !is plr || QACritBuff() is null))
			QACritRestore();
		uint sid = HashString(args[0]);
		Skills::Skill@ skill = null;
		for (uint i = 0; i < plr.m_skills.length(); i++)
		{
			if (plr.m_skills[i] !is null && plr.m_skills[i].m_skillId == sid)
				@skill = plr.m_skills[i];
		}
		if (skill is null)
		{
			Fail(id, "skill not live: " + args[0]);
			return;
		}
		bool changed = false;
		float original = skill.m_modCritChance;
		if (g_qaCritActive && g_qaCritSkill == sid)
			original = g_qaCritOriginal;
		if (args.length() > 1)
		{
			if (g_qaCritActive && g_qaCritSkill != sid)
			{
				Fail(id, "restore the current skillcrit override before selecting another skill");
				return;
			}
			if (args[1] == "restore")
			{
				QACritRestore();
				changed = true;
			}
			else
			{
				float chance = parseFloat(args[1]);
				if (!QACritNumber(args[1]) || !(chance >= 0 && chance <= 1))
				{
					Fail(id, "crit chance must be a decimal from 0 through 1");
					return;
				}
				auto def = LoadActorBuff(QA_CRIT_BUFF);
				if (def is null)
				{
					Fail(id, "missing lab crit buff fixture");
					return;
				}
				g_qaCritOriginal = original;
				g_qaCritSkill = sid;
				g_qaCritChance = chance;
				@g_qaCritOwner = plr;
				@g_qaCritDef = def;
				g_qaCritActive = true;
				bool applied = plr.ApplyBuff(ActorBuff(plr, def, 1.0f, false, 0, QA_CRIT_MAX_MS));
				if (!applied || QACritBuff() is null)
				{
					QACritRestore();
					Fail(id, "local player refused the lab crit buff");
					return;
				}
				QACritRebuild(plr);
				changed = true;
			}
		}
		auto buff = QACritBuff();
		Emit(Reply(id, true).Str("skill", args[0]).Bool("set", changed)
			.Num("crit_chance", skill.m_modCritChance).Num("crit_damage", skill.m_modCritDamage)
			.Num("spell_crit_chance", plr.m_record.currStats.SpellCritChance)
			.Bool("override_active", g_qaCritActive && g_qaCritSkill == sid && buff !is null)
			.Num("original_crit_chance", original).Int("left", buff is null ? 0 : buff.m_duration)
			.Int("max_ms", QA_CRIT_MAX_MS));
	}

	void Register_qa_crit()
	{
		RegisterVerb("skillcrit", "<skillId> [0..1|restore]", Verb(VerbSkillCrit));
	}
}
