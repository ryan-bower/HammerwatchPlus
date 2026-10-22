// Read-only native PointCost/Player.UsePoints observation. This never spends
// points, activates a skill, refreshes stats/modifiers, or changes a cost.
namespace GameLab
{
	string QAPointCost(PointCost@ cost)
	{
		Json row;
		return row.Int("health_flat", cost.flatCost.x).Int("mana_flat", cost.flatCost.y)
			.Raw("health_max_percent", formatFloat(cost.percentageMaxCost.x, "", 0, 9))
			.Raw("mana_max_percent", formatFloat(cost.percentageMaxCost.y, "", 0, 9))
			.Raw("health_current_percent", formatFloat(cost.percentageCurrCost.x, "", 0, 9))
			.Raw("mana_current_percent", formatFloat(cost.percentageCurrCost.y, "", 0, 9))
			.Raw("health_multiplier", formatFloat(cost.multiplier.x, "", 0, 9))
			.Raw("mana_multiplier", formatFloat(cost.multiplier.y, "", 0, 9))
			.Int("dash", cost.dashCost).Close();
	}

	void VerbQASkillCost(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (args.length() != 2 || plr is null || plr.IsDead() || plr.m_record is null
			|| plr.m_record.playerClass is null || plr.m_record.playerClass.m_id != args[1]
			|| plr.m_skills.length() > 128)
		{ Fail(id, "usage: skillcost <exactSkillId> <expectedClass>; requires matching live local class and <=128 skills"); return; }
		Skills::Skill@ skill;
		int matches = 0;
		for (uint i = 0; i < plr.m_skills.length(); i++)
		{
			if (plr.m_skills[i] !is null && plr.m_skills[i].m_id == args[0])
			{ @skill = plr.m_skills[i]; matches++; }
		}
		auto active = cast<Skills::PlayerSkill>(skill);
		if (matches != 1 || active is null || skill.m_owner !is plr)
		{ Fail(id, "requires exactly one native owned PlayerSkill with the exact requested id"); return; }
		auto rec = plr.m_record;
		auto cost = skill.GetCost(); // PlayerSkill.GetCost combines into a new PointCost.
		auto modifiers = rec.GetModifiers();
		vec2 mul = modifiers.SkillCostMul(plr);
		bool freeHealth = GetVarBool("cht_plr_free_health_cost");
		bool freeMana = GetVarBool("cht_plr_free_mana_cost") || plr.m_buffs.FreeMana();
		if (freeHealth) mul.x = 0;
		if (freeMana) mul.y = 0;
		vec2 maximum(float(rec.MaxHealth()), float(rec.MaxMana()));
		if (maximum.x <= 0 || maximum.y <= 0)
		{ Fail(id, "native maximum pools must be positive"); return; }
		vec2 current = vec2(rec.hp, rec.mana) * maximum;
		// Exactly Player.UsePoints773..789, without UsePoints(spend) or any writer.
		auto scaled = cost.percentageMaxCost * maximum + cost.percentageCurrCost * current;
		scaled += vec2(cost.flatCost.x, cost.flatCost.y);
		scaled *= mul * cost.multiplier;
		auto use = modifiers.UsePoints(plr, scaled);
		auto expense = scaled + vec2(use.x, use.y) * mul;
		auto reply = Reply(id, true).Str("skill", skill.m_id).Str("class", rec.playerClass.m_id)
			.Int("unit", plr.m_unit.GetId()).Int("now", int(g_scene.GetTime())).Int("matches", matches)
			.Int("skill_count", plr.m_skills.length()).Bool("truncated", false).Int("type", int(skill.m_type))
			.Raw("base", QAPointCost(active.m_cost)).Raw("modified", QAPointCost(skill.m_modCost))
			.Raw("combined", QAPointCost(cost)).Bool("free_health", freeHealth).Bool("free_mana", freeMana)
			.Int("max_health", rec.MaxHealth()).Int("max_mana", rec.MaxMana())
			.Raw("health_fraction", formatFloat(rec.hp, "", 0, 9))
			.Raw("mana_fraction", formatFloat(rec.mana, "", 0, 9))
			.Raw("global_health_multiplier", formatFloat(mul.x, "", 0, 9))
			.Raw("global_mana_multiplier", formatFloat(mul.y, "", 0, 9))
			.Raw("scaled_health", formatFloat(scaled.x, "", 0, 9))
			.Raw("scaled_mana", formatFloat(scaled.y, "", 0, 9))
			.Int("use_points_health", use.x).Int("use_points_mana", use.y)
			.Raw("expense_health", formatFloat(expense.x, "", 0, 9))
			.Raw("expense_mana", formatFloat(expense.y, "", 0, 9));
		Emit(reply);
	}

	void Register_qa_skill_cost()
	{
		RegisterVerb("skillcost", "<exactSkillId> <expectedClass>", Verb(VerbQASkillCost));
	}
}
