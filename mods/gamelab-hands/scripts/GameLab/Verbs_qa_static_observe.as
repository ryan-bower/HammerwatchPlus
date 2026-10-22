// Draft: install/register only at a clean GameLab boundary.
// One bounded, 1x observation task. Its only actions are ordinary GameLab HeldInput
// requests. No damage, stacks, mana, cooldown, critical events or modifier hooks are set.
namespace GameLab
{
	const uint QA_STATIC_TT = HashString("hwp_wiz_tempest_torrent");
	const uint QA_STATIC_MM = HashString("wiz_magic_missiles");
	const uint QA_STATIC_SC = HashString("hwp_wiz_static_charge");
	const string QA_STATIC_TARGET = "gamelab/qa_class_target_dummy.unit";
	const string QA_STATIC_PROJECTILE = "players/hwp/specs/invocation/torrent.unit";
	bool g_qaStaticBusy = false;

	Skills::Skill@ QAStaticSkill(PlayerBase@ plr, uint sid)
	{
		for (uint i = 0; i < plr.m_skills.length(); i++)
			if (plr.m_skills[i] !is null && plr.m_skills[i].m_skillId == sid)
				return plr.m_skills[i];
		return null;
	}

	int QAStaticCooldown(Skills::Skill@ skill)
	{
		auto ps = cast<Skills::PlayerSkill>(skill);
		return ps is null ? -1 : ps.m_cooldownC;
	}

	// Actor.AddFloatingHurt emits a real crit as EnemyImmortal with numeric text
	// ending '!'; the same enum is also used for nonnumeric immortal messages.
	bool QAStaticCritText(const string &in text)
	{
		if (text.length() < 2 || text.substr(text.length() - 1) != "!")
			return false;
		for (uint i = 0; i + 1 < text.length(); i++)
			if ("0123456789".findFirst(text.substr(i, 1)) < 0)
				return false;
		return true;
	}

	class QAStaticObserveTask : QueuedTasks::UpdatingTask
	{
		string m_tag;
		PlayerBase@ m_player;
		Skills::Skill@ m_tt;
		Skills::Skill@ m_mm;
		ActorBuffStackDef@ m_stacks;
		array<Actor@> m_targets;
		vec2 m_direction;
		vec2 m_origin;
		string m_ttButton;
		string m_mmButton;
		int m_t = 0;
		int m_frames = 0;
		int m_ttAt = -1;
		int m_mmAt = -1;
		int m_ttInputFrames = 0;
		bool m_phase550 = false, m_phase850 = false, m_phase1400 = false, m_phase2300 = false;
		bool m_truncated = false;
		array<string> m_samples;
		array<string> m_phases;

		string Health()
		{
			array<string> values;
			for (uint i = 0; i < m_targets.length(); i++)
			{
				auto a = m_targets[i];
				double hp = a is null || !a.m_unit.IsValid() || a.m_unit.IsDestroyed() ? -1.0 : double(a.GetHealth()) * double(a.GetMaxHp());
				values.insertLast(formatFloat(hp, "", 0, 3));
			}
			return RawArray(values);
		}

		string TargetRows()
		{
			array<string> rows;
			for (uint i = 0; i < m_targets.length(); i++)
			{
				auto a = m_targets[i];
				Json row;
				if (a is null || !a.m_unit.IsValid() || a.m_unit.IsDestroyed())
					row.Bool("valid", false);
				else
				{
					vec3 pos = a.m_unit.GetPosition();
					row.Bool("valid", true).Int("unit", a.m_unit.GetId()).Int("hpMax", a.GetMaxHp())
						.Num("hpExact", double(a.GetHealth()) * double(a.GetMaxHp()))
						.Num("x", pos.x).Num("y", pos.y).Bool("dead", a.IsDead());
				}
				rows.insertLast(row.Close());
			}
			return RawArray(rows);
		}

		int NewCrits(int now)
		{
			int count = 0;
			for (uint i = 0; i < g_floatingTexts.length(); i++)
			{
				auto f = g_floatingTexts[i];
				if (f !is null && f.m_alive && f.m_type == FloatingTextType::EnemyImmortal
					&& QAStaticCritText(f.m_floatingText) && m_mmAt >= 0 && now - f.m_timeLived > m_mmAt + 250)
					count++;
			}
			return count;
		}

		string CritRows(int now)
		{
			array<string> rows;
			for (uint i = 0; i < g_floatingTexts.length(); i++)
			{
				auto f = g_floatingTexts[i];
				if (f is null || !f.m_alive || f.m_type != FloatingTextType::EnemyImmortal || !QAStaticCritText(f.m_floatingText))
					continue;
				if (rows.length() >= 32)
				{
					m_truncated = true;
					break;
				}
				Json row;
				row.Int("type", int(f.m_type)).Str("text", f.m_floatingText).Int("lived", f.m_timeLived)
					.Int("born", now - f.m_timeLived).Num("x", f.m_pos.x).Num("y", f.m_pos.y);
				rows.insertLast(row.Close());
			}
			return RawArray(rows);
		}

		string Projectiles()
		{
			array<string> rows;
			auto producer = Resources::GetUnitProducer(QA_STATIC_PROJECTILE);
			if (producer !is null)
			{
				auto units = g_scene.FetchAllUnitsOfType(producer);
				for (uint i = 0; i < units.length(); i++)
				{
					if (!units[i].IsValid() || units[i].IsDestroyed())
						continue;
					if (rows.length() >= 4)
					{
						m_truncated = true;
						break;
					}
					vec3 pos = units[i].GetPosition();
					Json row;
					row.Int("unit", units[i].GetId()).Num("x", pos.x).Num("y", pos.y);
					rows.insertLast(row.Close());
				}
			}
			return RawArray(rows);
		}

		void Phase(const string &in name)
		{
			int now = int(g_scene.GetTime());
			Json row;
			row.Str("phase", name).Int("t", m_t).Int("now", now).Int("stacks", m_player.GetStacks(m_stacks))
				.Raw("targets", TargetRows()).Raw("crits", CritRows(now)).Raw("projectiles", Projectiles())
				.Int("tt_cd", QAStaticCooldown(m_tt)).Int("mm_cd", QAStaticCooldown(m_mm))
				.Num("tt_crit", m_tt.m_modCritChance).Num("mm_crit", m_mm.m_modCritChance)
				.Num("spell_crit", m_player.m_record.currStats.SpellCritChance)
				.Num("mana", m_player.m_record.mana * float(m_player.m_record.MaxMana()));
			string payload = row.Close();
			m_phases.insertLast(payload);
			Json event;
			Emit(event.Str("ev", "qa_static_phase").Str("tag", m_tag).Raw("data", payload));
		}

		void Finish(bool complete, const string &in error)
		{
			g_qaStaticBusy = false;
			// Emit enforces a15000-character per-message limit. Bound each sample
			// payload independently and keep the final acknowledgement small.
			for (uint start = 0; start < m_samples.length(); start += 16)
			{
				array<string> part;
				for (uint i = start; i < m_samples.length() && i < start + 16; i++)
					part.insertLast(m_samples[i]);
				Json chunk;
				Emit(chunk.Str("ev", "qa_static_samples").Str("tag", m_tag).Int("offset", int(start))
					.Raw("samples", RawArray(part)));
			}
			Json event;
			event.Str("ev", "qa_static_observe").Str("tag", m_tag).Bool("complete", complete).Str("error", error)
				.Int("ms", m_t).Int("frames", m_frames).Int("tt_input_at", m_ttAt).Int("mm_input_at", m_mmAt)
				.Int("tt_input_frames", m_ttInputFrames).Int("mm_input_frames", int(g_held.frames))
				.Bool("truncated", m_truncated).Int("sample_count", int(m_samples.length())).Int("phase_count", int(m_phases.length()));
			Emit(event);
		}

		bool UpdateFrame(int ms) override
		{
			m_t += ms;
			m_frames++;
			if (m_player is null || !m_player.m_unit.IsValid() || m_player.IsDead() || GetLocalPlayer() !is m_player)
			{
				Finish(false, "local actor changed or died");
				return true;
			}
			if (dist(m_origin, xy(m_player.m_unit.GetPosition())) > 2)
			{
				Finish(false, "fixture player moved");
				return true;
			}
			if (m_ttAt < 0)
			{
				Phase("before_tt");
				m_ttAt = int(g_scene.GetTime());
				array<string> buttons = { m_ttButton };
				Hold(m_tag + ".tt", 600, vec2(), true, m_direction, buttons);
			}
			if (!m_phase550 && m_t >= 550) { m_phase550 = true; Phase("first_crit"); }
			if (!m_phase850 && m_t >= 850) { m_phase850 = true; Phase("later_crits"); }
			if (m_mmAt < 0 && m_t >= 900)
			{
				Phase("before_mm");
				m_ttInputFrames = int(g_held.frames);
				m_mmAt = int(g_scene.GetTime());
				array<string> buttons = { m_mmButton };
				Hold(m_tag + ".mm", 400, vec2(), true, m_direction, buttons);
			}
			int now = int(g_scene.GetTime());
			Json sample;
			sample.Int("t", m_t).Int("now", now).Int("stacks", m_player.GetStacks(m_stacks)).Raw("hp", Health())
				.Int("tt_cd", QAStaticCooldown(m_tt)).Int("mm_cd", QAStaticCooldown(m_mm)).Int("new_crits", NewCrits(now))
				.Num("mana", m_player.m_record.mana * float(m_player.m_record.MaxMana()));
			if (m_samples.length() < 200)
				m_samples.insertLast(sample.Close());
			else
				m_truncated = true;
			if (!m_phase1400 && m_t >= 1400) { m_phase1400 = true; Phase("after_mm"); }
			if (!m_phase2300 && m_t >= 2300) { m_phase2300 = true; Phase("old_orb_late"); }
			if (m_t < 2500)
				return false;
			Phase("finished");
			Finish(true, "");
			return true;
		}
	}

	// qa_static_observe <tag> <aimX> <aimY>: fixed 2500 scene-ms native observation.
	// Preconditions are deliberately strict; setup stays outside the measurement.
	void VerbQAStaticObserve(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || args.length() != 3 || g_qaStaticBusy || QueuedTasks::g_instance is null)
		{
			Fail(id, "qa_static_observe needs a local player, idle observer, and <tag> <aimX> <aimY>");
			return;
		}
		auto tt = QAStaticSkill(plr, QA_STATIC_TT);
		auto mm = QAStaticSkill(plr, QA_STATIC_MM);
		auto sc = QAStaticSkill(plr, QA_STATIC_SC);
		auto stacks = ActorBuffStackDef::Get("players/hwp/specs/stacks_specs.sval:static_charge");
		vec2 direction(parseFloat(args[1]), parseFloat(args[2]));
		if (tt is null || mm is null || sc is null || stacks is null || length(direction) < 0.5f
			|| g_held.msLeft > 0 || Releasing() || plr.GetStacks(stacks) != 0
			|| QAStaticCooldown(tt) > 0 || QAStaticCooldown(mm) > 0 || tt.m_modCritChance != 1
			|| mm.m_modCritChance != 0 || plr.m_record.currStats.SpellCritChance != 0
			|| plr.m_record.CurrentMana() < 80)
		{
			Fail(id, "requires ready TT/MM, zero stacks, TT crit1, MM/global crit0, mana>=80, and released input");
			return;
		}
		QAStaticObserveTask task;
		task.m_tag = args[0];
		@task.m_player = plr;
		@task.m_tt = tt;
		@task.m_mm = mm;
		@task.m_stacks = stacks;
		task.m_origin = xy(plr.m_unit.GetPosition());
		task.m_direction = normalize(direction);
		task.m_ttButton = SkillButton(plr, tt);
		task.m_mmButton = SkillButton(plr, mm);
		auto producer = Resources::GetUnitProducer(QA_STATIC_TARGET);
		if (producer !is null)
		{
			auto units = g_scene.FetchAllUnitsOfType(producer);
			for (uint i = 0; i < units.length(); i++)
			{
				if (!units[i].IsValid() || units[i].IsDestroyed())
					continue;
				auto a = cast<Actor>(units[i].GetScriptBehavior());
				if (a !is null && !a.IsDead() && dist(task.m_origin, xy(units[i].GetPosition())) <= 120)
					task.m_targets.insertLast(a);
			}
		}
		bool valid = task.m_targets.length() == 3 && task.m_ttButton != "" && task.m_mmButton != ""
			&& task.m_ttButton != task.m_mmButton;
		for (uint i = 0; i < task.m_targets.length(); i++)
			valid = valid && task.m_targets[i].GetMaxHp() == 15000 && task.m_targets[i].GetHealth() > 0.99f;
		if (!valid)
		{
			Fail(id, "requires exactly three fresh native15000HP targets and distinct actual TT/MM buttons");
			return;
		}
		g_qaStaticBusy = true;
		QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.m_tag).Int("ms", 2500).Str("tt_button", task.m_ttButton).Str("mm_button", task.m_mmButton));
	}

	void Register_qa_static_observe()
	{
		RegisterVerb("qa_static_observe", "<tag> <aimX> <aimY>", Verb(VerbQAStaticObserve));
		Register_qa_static_overlap();
		Register_qa_static_mm();
	}
}
