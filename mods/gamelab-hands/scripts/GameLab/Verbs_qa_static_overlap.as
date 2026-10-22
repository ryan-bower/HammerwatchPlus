// GameLab-only two-real-cast overlap stress fixture. Explicit bounded setup moves
// the lab player100px and clears one cooldown; it never sets damage or crit events.
namespace GameLab
{
	bool g_qaOverlapBusy = false;
	class QAStaticOverlapTask : QueuedTasks::UpdatingTask
	{
		QAStaticObserveTask m_read;
		string m_tag;
		int m_t = 0, m_frames = 0, m_firstAt = -1, m_secondAt = -1;
		int m_firstFrames = 0, m_cdBefore = -1, m_cdAfter = -1;
		bool m_newOnly = false, m_oldStart = false, m_oldOnly = false, m_truncated = false;
		array<string> m_samples, m_phases;

		void Phase(const string &in name)
		{
			int now = int(g_scene.GetTime());
			vec2 pos = xy(m_read.m_player.m_unit.GetPosition());
			Json row;
			row.Str("phase", name).Int("t", m_t).Int("now", now).Int("stacks", m_read.m_player.GetStacks(m_read.m_stacks))
				.Raw("targets", m_read.TargetRows()).Raw("crits", m_read.CritRows(now)).Raw("projectiles", m_read.Projectiles())
				.Int("tt_cd", QAStaticCooldown(m_read.m_tt)).Num("tt_crit", m_read.m_tt.m_modCritChance)
				.Num("spell_crit", m_read.m_player.m_record.currStats.SpellCritChance)
				.Num("mana", m_read.m_player.m_record.mana * float(m_read.m_player.m_record.MaxMana()))
				.Num("player_x", pos.x).Num("player_y", pos.y);
			string payload = row.Close();
			m_phases.insertLast(payload);
			Json event;
			Emit(event.Str("ev", "qa_overlap_phase").Str("tag", m_tag).Raw("data", payload));
		}

		void Finish(bool complete, const string &in error)
		{
			g_qaOverlapBusy = false;
			g_qaStaticBusy = false;
			for (uint start = 0; start < m_samples.length(); start += 16)
			{
				array<string> part;
				for (uint i = start; i < m_samples.length() && i < start + 16; i++) part.insertLast(m_samples[i]);
				Json chunk;
				Emit(chunk.Str("ev", "qa_overlap_samples").Str("tag", m_tag).Int("offset", int(start)).Raw("samples", RawArray(part)));
			}
			Json event;
			Emit(event.Str("ev", "qa_static_overlap").Str("tag", m_tag).Bool("complete", complete).Str("error", error)
				.Int("ms", m_t).Int("frames", m_frames).Int("first_input_at", m_firstAt).Int("second_input_at", m_secondAt)
				.Int("first_input_frames", m_firstFrames).Int("second_input_frames", int(g_held.frames))
				.Int("cooldown_before_setup", m_cdBefore).Int("cooldown_after_setup", m_cdAfter)
				.Bool("truncated", m_truncated || m_read.m_truncated).Int("sample_count", int(m_samples.length()))
				.Int("phase_count", int(m_phases.length())).Num("origin_x", m_read.m_origin.x).Num("origin_y", m_read.m_origin.y)
				.Num("aim_x", m_read.m_direction.x).Num("aim_y", m_read.m_direction.y));
		}

		bool UpdateFrame(int ms) override
		{
			m_t += ms;
			m_frames++;
			auto plr = m_read.m_player;
			if (plr is null || !plr.m_unit.IsValid() || plr.IsDead() || GetLocalPlayer() !is plr)
			{
				Finish(false, "local actor changed/died"); return true;
			}
			vec2 expected = m_read.m_origin + (m_secondAt < 0 ? vec2() : m_read.m_direction * 100);
			if (dist(xy(plr.m_unit.GetPosition()), expected) > 1)
			{
				Finish(false, "unexpected fixture displacement"); return true;
			}
			if (m_firstAt < 0)
			{
				Phase("before_first");
				m_firstAt = int(g_scene.GetTime());
				array<string> buttons = {m_read.m_ttButton};
				Hold(m_tag + ".first", 600, vec2(), true, m_read.m_direction, buttons);
			}
			if (m_secondAt < 0 && m_t >= 900)
			{
				Phase("before_second");
				m_firstFrames = int(g_held.frames);
				m_cdBefore = QAStaticCooldown(m_read.m_tt);
				// Explicit lab prerequisite for an otherwise12s-cooldown skill:
				// two actual casts must coexist; this does not claim ordinary timing.
				vec3 pos = plr.m_unit.GetPosition();
				vec2 destination = m_read.m_origin + m_read.m_direction * 100;
				plr.m_unit.SetPosition(vec3(destination.x, destination.y, pos.z));
				auto skill = cast<Skills::PlayerSkill>(m_read.m_tt);
				skill.m_cooldownC = 0;
				m_cdAfter = skill.m_cooldownC;
				m_secondAt = int(g_scene.GetTime());
				Phase("second_setup");
				array<string> buttons = {m_read.m_ttButton};
				Hold(m_tag + ".second", 600, vec2(), true, m_read.m_direction, buttons);
			}
			Json sample;
			sample.Int("t", m_t).Int("now", int(g_scene.GetTime())).Int("stacks", plr.GetStacks(m_read.m_stacks))
				.Raw("hp", m_read.Health()).Int("tt_cd", QAStaticCooldown(m_read.m_tt));
			if (m_samples.length() < 200) m_samples.insertLast(sample.Close()); else m_truncated = true;
			if (!m_newOnly && m_t >= 2000) {m_newOnly = true; Phase("new_orb_only");}
			if (!m_oldStart && m_t >= 4400) {m_oldStart = true; Phase("old_orb_only_start");}
			if (!m_oldOnly && m_t >= 4700) {m_oldOnly = true; Phase("old_orb_only");}
			if (m_t < 4800) return false;
			Phase("finished"); Finish(true, ""); return true;
		}
	}

	void VerbQAStaticOverlap(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || args.length() != 3 || g_qaOverlapBusy || g_qaStaticBusy || QueuedTasks::g_instance is null)
		{Fail(id, "needs local player, idle observers, and <tag> <aimX> <aimY>"); return;}
		auto tt = QAStaticSkill(plr, QA_STATIC_TT);
		auto stacks = ActorBuffStackDef::Get("players/hwp/specs/stacks_specs.sval:static_charge");
		vec2 direction(parseFloat(args[1]), parseFloat(args[2]));
		if (tt is null || stacks is null || QAStaticSkill(plr, QA_STATIC_SC) is null || length(direction) < 0.5f
			|| g_held.msLeft > 0 || Releasing() || plr.GetStacks(stacks) != 0 || QAStaticCooldown(tt) > 0
			|| tt.m_modCritChance != 1 || plr.m_record.currStats.SpellCritChance != 0 || plr.m_record.CurrentMana() < 160)
		{Fail(id, "requires ready TT, zeroSC, TTcrit1/global0, mana160+, released input"); return;}
		auto producer = Resources::GetUnitProducer(QA_STATIC_PROJECTILE);
		if (producer !is null && g_scene.FetchAllUnitsOfType(producer).length() > 0)
		{Fail(id, "old Thunder Orb already present"); return;}
		QAStaticOverlapTask task;
		task.m_tag = args[0];
		@task.m_read.m_player = plr;
		@task.m_read.m_tt = tt;
		@task.m_read.m_stacks = stacks;
		task.m_read.m_origin = xy(plr.m_unit.GetPosition());
		task.m_read.m_direction = normalize(direction);
		task.m_read.m_ttButton = SkillButton(plr, tt);
		@producer = Resources::GetUnitProducer(QA_STATIC_TARGET);
		if (producer !is null)
		{
			auto units = g_scene.FetchAllUnitsOfType(producer);
			for (uint i = 0; i < units.length(); i++)
			{
				if (!units[i].IsValid() || units[i].IsDestroyed()) continue;
				auto actor = cast<Actor>(units[i].GetScriptBehavior());
				vec2 delta = xy(units[i].GetPosition()) - task.m_read.m_origin;
				float forward = dot(delta, task.m_read.m_direction);
				if (actor !is null && !actor.IsDead() && forward >= 179 && forward <= 181 && length(delta - task.m_read.m_direction * forward) <= 16)
					task.m_read.m_targets.insertLast(actor);
			}
		}
		bool valid = task.m_read.m_targets.length() == 3 && task.m_read.m_ttButton != "";
		for (uint i = 0; i < task.m_read.m_targets.length(); i++)
			valid = valid && task.m_read.m_targets[i].GetMaxHp() == 15000 && task.m_read.m_targets[i].GetHealth() > 0.99f;
		if (!valid) {Fail(id, "requires3 fresh native15k targets180px along aim, side<=16px"); return;}
		g_qaOverlapBusy = true;
		g_qaStaticBusy = true;
		QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.m_tag).Int("ms", 4800).Bool("bounded_cooldown_setup", true).Int("fixture_move", 100));
	}

	void Register_qa_static_overlap()
	{
		RegisterVerb("qa_static_overlap", "<tag> <aimX> <aimY>", Verb(VerbQAStaticOverlap));
	}
}
