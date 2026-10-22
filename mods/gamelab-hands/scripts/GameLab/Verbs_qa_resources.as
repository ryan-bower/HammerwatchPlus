// Read-only native-frame resource/stat trace. No resource setters or effect hooks.
namespace GameLab
{
	bool g_qaResourceBusy = false;
	const uint QA_RESOURCE_CAP = 256;
	const uint QA_RESOURCE_CHUNK = 16;

	class QAResourceTask : QueuedTasks::UpdatingTask
	{
		string m_tag;
		Player@ m_player;
		int m_start, m_left, m_elapsed = 0, m_frames = 0;
		int m_seen = 0, m_dropped = 0;
		array<string> m_rows;

		void Sample(int dt, bool final = false)
		{
			m_seen++;
			if (!final && m_rows.length() >= QA_RESOURCE_CAP - 1)
			{
				m_dropped++;
				return;
			}
			bool valid = m_player !is null && m_player.m_unit.IsValid()
				&& !m_player.m_unit.IsDestroyed() && !m_player.IsDead()
				&& m_player.m_record !is null;
			Json row;
			row.Int("now", int(g_scene.GetTime())).Int("elapsed", m_elapsed)
				.Int("dt", dt).Bool("final", final).Bool("valid", valid);
			if (valid)
			{
				auto rec = m_player.m_record;
				auto st = rec.currStats;
				int maxMana = rec.MaxMana(), maxHp = m_player.GetMaxHp();
				row.Int("maxMana", maxMana).Int("maxHp", maxHp)
					.Raw("mana", formatFloat(double(rec.mana) * double(maxMana), "", 0, 9))
					.Raw("manaFraction", formatFloat(rec.mana, "", 0, 9))
					.Raw("hp", formatFloat(double(rec.hp) * double(maxHp), "", 0, 9))
					.Raw("hpFraction", formatFloat(rec.hp, "", 0, 9))
					.Raw("statMana", formatFloat(float(st.Mana), "", 0, 9))
					.Raw("statHealth", formatFloat(float(st.Health), "", 0, 9))
					.Raw("manaRegen", formatFloat(float(st.ManaRegen), "", 0, 9))
					.Raw("manaGain", formatFloat(float(st.ManaGain), "", 0, 9))
					.Raw("healthRegen", formatFloat(float(st.HealthRegen), "", 0, 9))
					.Raw("healthGain", formatFloat(float(st.HealthGain), "", 0, 9))
					.Int("healthRegenC", m_player.m_healthRegenC);
			}
			m_rows.insertLast(row.Close());
		}

		bool UpdateFrame(int ms) override
		{
			m_elapsed += ms;
			m_left -= ms;
			m_frames++;
			bool final = m_left <= 0;
			Sample(ms, final);
			if (!final)
				return false;
			uint parts = (m_rows.length() + QA_RESOURCE_CHUNK - 1) / QA_RESOURCE_CHUNK;
			for (uint part = 0; part < parts; part++)
			{
				array<string> rows;
				for (uint i = part * QA_RESOURCE_CHUNK; i < m_rows.length()
					&& i < (part + 1) * QA_RESOURCE_CHUNK; i++)
					rows.insertLast(m_rows[i]);
				Json reply;
				Emit(reply.Str("ev", "resourceobserve").Str("tag", m_tag)
					.Int("part", part).Int("parts", parts).Int("stored", m_rows.length())
					.Int("seen", m_seen).Int("dropped", m_dropped)
					.Bool("truncated", m_dropped > 0).Int("start", m_start)
					.Int("end", int(g_scene.GetTime())).Int("ms", m_elapsed)
					.Int("frames", m_frames).Raw("samples", RawArray(rows)));
			}
			g_qaResourceBusy = false;
			return true;
		}
	}

	// resourceobserve <tag> <ms>: native frame mana/HP and the current stats
	// used by Player.Update regeneration. Read-only;100..6000ms,256 samples,
	//16 samples per part, explicit truncation. Does not read Living Mana binds.
	void VerbQAResources(const string &in id, array<string>@ args)
	{
		auto plr = cast<Player>(GetLocalPlayer());
		if (plr is null || plr.IsDead() || QueuedTasks::g_instance is null || args.length() != 2)
		{
			Fail(id, "usage: resourceobserve <tag> <ms>; needs a live local Player and task module");
			return;
		}
		int ms = int(parseInt(args[1]));
		if (g_qaResourceBusy || args[0].length() > 64 || ms < 100 || ms > 6000)
		{
			Fail(id, "resource observer busy, tag longer than64, or duration outside100..6000ms");
			return;
		}
		QAResourceTask task;
		task.m_tag = args[0];
		task.m_start = int(g_scene.GetTime());
		task.m_left = ms;
		@task.m_player = plr;
		task.Sample(0);
		g_qaResourceBusy = true;
		QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.m_tag).Int("ms", ms)
			.Int("sample_cap", QA_RESOURCE_CAP).Int("chunk", QA_RESOURCE_CHUNK));
	}

	void Register_qa_resources()
	{
		RegisterVerb("resourceobserve", "<tag> <ms>", Verb(VerbQAResources));
	}
}
