// Bounded native-frame first-impact measurements. Only ordinary HeldInput is posted.
namespace GameLab
{
	bool g_qaImpactBusy = false;
	class QASpecImpactTask : QueuedTasks::UpdatingTask
	{
		QAStaticObserveTask m_read;
		Skills::Skill@ m_skill;
		string m_tag, m_button, m_skillId;
		array<double> m_hp;
		string m_before, m_first;
		int m_t = 0, m_frames = 0, m_inputAt = -1, m_firstAt = -1;
		array<string> m_castTrace;
		bool m_castTraceTruncated = false;

		// Read only: native skill progress and actual producer presence each frame.
		//32 rows bound the payload below15k; overflow invalidates the measurement.
		void TraceCast(int ms)
		{
			if (m_castTrace.length() >= 32) { m_castTraceTruncated = true; return; }
			auto sk = cast<Skills::PlayerSkill>(m_skill);
			auto directional = cast<Skills::PlayerSkillDirectional>(m_skill);
			int timeline = -2;
			if (directional !is null && directional.m_timeline !is null)
				timeline = directional.m_timeline.m_castingT;
			int producers = 0;
			auto producer = Resources::GetUnitProducer(QA_STATIC_PROJECTILE);
			if (producer !is null)
			{
				auto units = g_scene.FetchAllUnitsOfType(producer);
				for (uint i = 0; i < units.length(); i++)
					if (units[i].IsValid() && !units[i].IsDestroyed()) producers++;
			}
			Json row;
			row.Int("now", int(g_scene.GetTime())).Int("dt", ms)
				.Int("ct", sk is null ? -2 : sk.m_castingT).Int("tl", timeline)
				.Int("cd", QAStaticCooldown(m_skill)).Int("pc", producers)
				.Num("speed", sk is null ? 0.0f : sk.GetTotalSkillCastSpeed());
			m_castTrace.insertLast(row.Close());
		}

		string Snapshot()
		{
			Json row;
			row.Int("now", int(g_scene.GetTime())).Int("elapsed", m_t).Raw("targets", m_read.TargetRows())
				.Raw("projectiles", m_read.Projectiles()).Int("stacks", m_read.m_player.GetStacks(m_read.m_stacks))
				.Int("cooldown", QAStaticCooldown(m_skill)).Num("skill_crit", m_skill.m_modCritChance)
				.Num("spell_crit", m_read.m_player.m_record.currStats.SpellCritChance)
				.Num("mana", m_read.m_player.m_record.mana * float(m_read.m_player.m_record.MaxMana()));
			return row.Close();
		}

		void Finish(bool complete, const string &in error)
		{
			g_qaImpactBusy = false;
			g_qaStaticBusy = false;
			Json result;
			Emit(result.Str("ev", "qa_spec_impact").Str("tag", m_tag).Str("skill", m_skillId)
				.Bool("complete", complete).Str("error", error).Bool("truncated", m_read.m_truncated || m_castTraceTruncated)
				.Int("ms", m_t).Int("frames", m_frames).Int("input_at", m_inputAt).Int("first_at", m_firstAt)
				.Int("input_frames", int(g_held.frames)).Raw("before", m_before)
				.Raw("first", m_first == "" ? "null" : m_first).Raw("after", Snapshot())
				.Bool("cast_trace_truncated", m_castTraceTruncated).Raw("cast_trace", RawArray(m_castTrace)));
		}

		bool UpdateFrame(int ms) override
		{
			m_t += ms; m_frames++;
			auto plr = m_read.m_player;
			if (plr is null || !plr.m_unit.IsValid() || plr.IsDead() || GetLocalPlayer() !is plr
				|| dist(xy(plr.m_unit.GetPosition()), m_read.m_origin) > 1)
			{ Finish(false, "local actor changed, died, or moved"); return true; }
			if (m_inputAt < 0)
			{
				m_inputAt = int(g_scene.GetTime());
				array<string> buttons = {m_button};
				Hold(m_tag + ".cast", 600, vec2(), true, m_read.m_direction, buttons);
			}
			TraceCast(ms);
			if (m_firstAt < 0)
				for (uint i = 0; i < m_read.m_targets.length(); i++)
				{
					auto a = m_read.m_targets[i];
					if (!a.m_unit.IsValid() || a.m_unit.IsDestroyed() || a.IsDead())
					{ Finish(false, "measurement target lost or died"); return true; }
					if (double(a.GetHealth()) * double(a.GetMaxHp()) < m_hp[i] - 0.01)
					{ m_firstAt = int(g_scene.GetTime()); m_first = Snapshot(); break; }
				}
			if (m_t < 900) return false;
			Finish(m_firstAt >= 0, m_firstAt < 0 ? "no actual HP loss within900 native ms" : "");
			return true;
		}
	}

	void VerbQASpecImpact(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || QueuedTasks::g_instance is null || args.length() != 4 || g_qaImpactBusy || g_qaStaticBusy)
		{ Fail(id, "requires idle native observer and <tag> <skillId> <aimX> <aimY>"); return; }
		auto skill = QAStaticSkill(plr, HashString(args[1]));
		auto stacks = ActorBuffStackDef::Get("players/hwp/specs/stacks_specs.sval:static_charge");
		vec2 aim(parseFloat(args[2]), parseFloat(args[3]));
		if (skill is null || stacks is null || length(aim) < 0.5f || g_held.msLeft > 0 || Releasing()
			|| QAStaticCooldown(skill) > 0 || skill.m_modCritChance != 0 || plr.m_record.currStats.SpellCritChance != 0)
		{ Fail(id, "needs ready actual skill, noncritical native setup and released input"); return; }
		auto producer = Resources::GetUnitProducer(QA_STATIC_PROJECTILE);
		if (producer !is null)
		{
			auto old = g_scene.FetchAllUnitsOfType(producer);
			if (old.length() > 0) { Fail(id, "old Thunder Orb present"); return; }
		}
		QASpecImpactTask task;
		task.m_tag = args[0]; task.m_skillId = args[1]; @task.m_skill = skill;
		@task.m_read.m_player = plr; @task.m_read.m_stacks = stacks;
		task.m_read.m_origin = xy(plr.m_unit.GetPosition()); task.m_read.m_direction = normalize(aim);
		task.m_button = SkillButton(plr, skill);
		@producer = Resources::GetUnitProducer(QA_STATIC_TARGET);
		if (producer !is null)
		{
			auto units = g_scene.FetchAllUnitsOfType(producer);
			for (uint i = 0; i < units.length(); i++)
			{
				if (!units[i].IsValid() || units[i].IsDestroyed()) continue;
				auto a = cast<Actor>(units[i].GetScriptBehavior());
				if (a !is null && !a.IsDead() && dist(task.m_read.m_origin, xy(units[i].GetPosition())) <= 400)
				{
					task.m_read.m_targets.insertLast(a);
					task.m_hp.insertLast(double(a.GetHealth()) * double(a.GetMaxHp()));
				}
			}
		}
		bool valid = task.m_button != "" && task.m_read.m_targets.length() > 0 && task.m_read.m_targets.length() <= 8;
		for (uint i = 0; i < task.m_read.m_targets.length(); i++)
			valid = valid && task.m_read.m_targets[i].GetMaxHp() == 15000 && task.m_read.m_targets[i].GetHealth() > 0.99f;
		if (!valid) { Fail(id, "needs1..8 fresh native15k targets and an actual mapped skill button"); return; }
		task.m_before = task.Snapshot();
		g_qaImpactBusy = true; g_qaStaticBusy = true; QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.m_tag).Str("button", task.m_button).Int("ms", 900));
	}

	void Register_qa_spec_impact()
	{
		RegisterVerb("qa_spec_impact", "<tag> <skillId> <aimX> <aimY>", Verb(VerbQASpecImpact));
	}
}
