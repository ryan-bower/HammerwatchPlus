// Read-only native-frame buff/stack/target-HP transitions. No input or effect hooks.
namespace GameLab
{
	bool g_qaBuffObserveBusy = false;
	const uint QA_OBSERVE_CAP = 64;
	const uint QA_OBSERVE_CHUNK = 16;

	class QABuffObserveTask : QueuedTasks::UpdatingTask
	{
		string m_tag, m_buffPath, m_stackPath;
		PlayerBase@ m_player;
		Actor@ m_target;
		ActorBuffDef@ m_buff;
		ActorBuffStackDef@ m_stack;
		int m_targetId = -1, m_start, m_left, m_elapsed = 0, m_frames = 0;
		int m_seen = 0, m_dropped = 0, m_previousLeft = -1, m_previousStacks = -1;
		bool m_previousOn = false, m_previousTarget = false, m_previousPlayer = false;
		bool m_havePrevious = false;
		double m_previousHp = -1;
		array<float> m_previousFactors;
		array<string> m_rows;

		void Sample(const string &in forced = "")
		{
			bool playerValid = m_player !is null && m_player.m_unit.IsValid() && !m_player.m_unit.IsDestroyed();
			ActorBuff@ buff = null;
			if (playerValid && m_buff !is null)
				for (uint i = 0; i < m_player.m_buffs.m_buffs.length(); i++)
				{
					auto b = m_player.m_buffs.m_buffs[i];
					if (b !is null && b.m_def !is null && b.m_def.m_pathHash == m_buff.m_pathHash)
						@buff = b;
				}
			bool on = buff !is null;
			int left = on ? buff.m_duration : -1;
			int stacks = playerValid && m_stack !is null ? m_player.GetStacks(m_stack) : -1;
			bool targetValid = m_target !is null && m_target.m_unit.IsValid() && !m_target.m_unit.IsDestroyed();
			int hpMax = targetValid ? m_target.GetMaxHp() : -1;
			double hp = targetValid ? double(m_target.GetHealth()) * double(hpMax) : -1;
			vec2 skillSpeed = playerValid ? m_player.m_buffs.SkillSpeed() : vec2(1);
			vec2 armor = playerValid ? m_player.m_buffs.ArmorMul() : vec2(1);
			array<float> factors = {
				playerValid ? m_player.m_buffs.MoveSpeedMul() : 1,
				skillSpeed.x, skillSpeed.y, armor.x, armor.y,
				playerValid ? m_player.m_buffs.DamageMul() : 1,
				playerValid ? float(m_player.m_record.currStats.EvadeChance) : -1
			};
			string why = forced;
			if (m_havePrevious)
			{
				if (on != m_previousOn) why += " buff";
				else if (on && left > m_previousLeft + 100) why += " refresh";
				if (stacks != m_previousStacks) why += " stack";
				if (targetValid != m_previousTarget || abs(hp - m_previousHp) > 0.001) why += " hp";
				if (playerValid != m_previousPlayer) why += " player";
				for (uint i = 0; i < factors.length(); i++)
					if (abs(factors[i] - m_previousFactors[i]) > 0.0001)
					{
						why += " factor";
						break;
					}
			}
			if (!m_havePrevious || why != "")
			{
				m_seen++;
				// Reserve one slot for the final snapshot even after the cap is reached.
				if (forced == "final" || m_rows.length() < QA_OBSERVE_CAP - 1)
				{
					Json row;
					row.Int("now", int(g_scene.GetTime())).Int("elapsed", m_elapsed).Str("reason", why)
						.Bool("player_valid", playerValid).Bool("buff_on", on).Int("buff_left", left)
						.Int("buff_dur", on ? buff.m_def.m_duration : -1).Num("buff_intensity", on ? buff.m_intensity : 0)
						.Int("stacks", stacks).Bool("target_valid", targetValid).Int("target_unit", m_targetId)
						.Int("target_hpMax", hpMax).Num("target_hpExact", hp)
						.Num("moveMul", factors[0]).Num("attackMul", factors[1]).Num("castMul", factors[2])
						.Num("armorMul", factors[3]).Num("resistanceMul", factors[4]).Num("damageMul", factors[5])
						.Num("evade", factors[6]);
					m_rows.insertLast(row.Close());
				}
				else m_dropped++;
			}
			m_havePrevious = true;
			m_previousOn = on; m_previousLeft = left; m_previousStacks = stacks;
			m_previousTarget = targetValid; m_previousHp = hp; m_previousPlayer = playerValid;
			m_previousFactors = factors;
		}

		bool UpdateFrame(int ms) override
		{
			m_elapsed += ms; m_left -= ms; m_frames++;
			if (m_left > 0) { Sample(); return false; }
			Sample("final");
			uint parts = (m_rows.length() + QA_OBSERVE_CHUNK - 1) / QA_OBSERVE_CHUNK;
			for (uint part = 0; part < parts; part++)
			{
				array<string> rows;
				for (uint i = part * QA_OBSERVE_CHUNK; i < m_rows.length() && i < (part + 1) * QA_OBSERVE_CHUNK; i++)
					rows.insertLast(m_rows[i]);
				Json reply;
				Emit(reply.Str("ev", "buffobserve").Str("tag", m_tag).Int("part", part).Int("parts", parts)
					.Int("stored", m_rows.length()).Int("seen", m_seen).Int("dropped", m_dropped)
					.Bool("truncated", m_dropped > 0).Int("start", m_start).Int("end", int(g_scene.GetTime()))
					.Int("ms", m_elapsed).Int("frames", m_frames).Str("buff", m_buffPath).Str("stack", m_stackPath)
					.Int("target_unit", m_targetId).Raw("events", RawArray(rows)));
			}
			g_qaBuffObserveBusy = false;
			return true;
		}
	}

	// buffobserve <tag> <ms> <buffPath|-> [stackPath|-] [targetUnitId]: observe the
	// local player's buff/stack and native buff factors, plus optional nearby Actor HP.
	// Initial/final and semantic transitions only, not duration countdown every frame.
	// Bounded100..60000ms;64events total,16 per part, explicit dropped/truncation.
	void VerbQABuffObserve(const string &in id, array<string>@ args)
	{
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null || QueuedTasks::g_instance is null || args.length() < 3 || args.length() > 5)
		{
			Fail(id, "usage: buffobserve <tag> <ms> <buffPath|-> [stackPath|-] [targetUnitId]; needs gameplay task module");
			return;
		}
		int ms = int(parseInt(args[1]));
		if (g_qaBuffObserveBusy || args[0].length() > 64 || ms < 100 || ms > 60000)
		{
			Fail(id, "observer busy, tag longer than64, or duration outside100..60000ms");
			return;
		}
		QABuffObserveTask task;
		task.m_tag = args[0]; task.m_left = ms; task.m_start = int(g_scene.GetTime()); @task.m_player = plr;
		task.m_buffPath = args[2]; task.m_stackPath = args.length() > 3 ? args[3] : "-";
		if (task.m_buffPath != "-") @task.m_buff = LoadActorBuff(task.m_buffPath);
		if (task.m_stackPath != "-") @task.m_stack = ActorBuffStackDef::Get(task.m_stackPath);
		if ((task.m_buffPath != "-" && task.m_buff is null) || (task.m_stackPath != "-" && task.m_stack is null))
		{
			Fail(id, "unknown buff or stack path"); return;
		}
		if (args.length() > 4)
		{
			task.m_targetId = int(parseInt(args[4]));
			auto unit = g_scene.GetUnit(task.m_targetId);
			if (unit.IsValid() && !unit.IsDestroyed()) @task.m_target = cast<Actor>(unit.GetScriptBehavior());
			if (task.m_target is null || task.m_target.IsDead()
				|| dist(xy(unit.GetPosition()), xy(plr.m_unit.GetPosition())) > 1200)
			{
				Fail(id, "target must be a live Actor within1200px"); return;
			}
		}
		task.Sample("initial");
		g_qaBuffObserveBusy = true;
		QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.m_tag).Int("ms", ms).Int("event_cap", QA_OBSERVE_CAP).Int("chunk", QA_OBSERVE_CHUNK));
	}

	void Register_qa_observe()
	{
		RegisterVerb("buffobserve", "<tag> <ms> <buffPath|-> [stackPath|-] [targetUnitId]", Verb(VerbQABuffObserve));
	}
}
