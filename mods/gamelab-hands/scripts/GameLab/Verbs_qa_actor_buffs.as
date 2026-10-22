// Bounded read-only native Actor buff/HP/factor trace. No Firearms script types,
// effect hooks, input, setters, optional-module globals or retained UnitPtr handles.
namespace GameLab
{
    bool g_qaActorBuffBusy = false;
    const uint QA_ACTOR_BUFF_CAP = 1024;
    const uint QA_ACTOR_BUFF_CHUNK = 16;

    class QAActorBuffTask : QueuedTasks::UpdatingTask
    {
        string m_tag, m_path;
        int m_unitId, m_start, m_left, m_elapsed = 0, m_frames = 0, m_seen = 0, m_dropped = 0;
        ActorBuffDef@ m_def;
        array<string> m_rows;

        void Sample(int dt, bool final = false)
        {
            m_seen++;
            if (!final && m_rows.length() >= QA_ACTOR_BUFF_CAP - 1)
            {
                m_dropped++;
                return;
            }
            // Resolve each frame, so an actor's destruction never leaves a
            // behavior handle which the observer will call in a later frame.
            auto unit = g_scene.GetUnit(m_unitId);
            Actor@ actor = null;
            if (unit.IsValid() && !unit.IsDestroyed())
                @actor = cast<Actor>(unit.GetScriptBehavior());
            bool valid = actor !is null && !actor.IsDead();
            Json row;
            row.Int("now", int(g_scene.GetTime())).Int("elapsed", m_elapsed).Int("dt", dt)
                .Bool("final", final).Bool("valid", valid).Int("unit", m_unitId);
            if (valid)
            {
                auto list = actor.GetBuffList();
                ActorBuff@ found = null;
                int matches = 0;
                if (list !is null)
                    for (uint i = 0; i < list.m_buffs.length(); i++)
                    {
                        auto buff = list.m_buffs[i];
                        if (buff !is null && buff.m_def !is null && buff.m_def.m_pathHash == m_def.m_pathHash)
                        {
                            @found = buff;
                            matches++;
                        }
                    }
                int maxHp = actor.GetMaxHp();
                auto composite = cast<CompositeActorBehavior>(actor);
                row.Int("hpMax", maxHp).Raw("hpExact", formatFloat(double(actor.GetHealth()) * double(maxHp), "", 0, 9))
                    .Int("actor_tick_rate", composite !is null ? composite.m_props.m_tickRate : -1)
                    .Raw("actor_last_world_update", formatFloat(composite !is null ? composite.m_lastUpdate : -1, "", 0, 9))
                    .Raw("world_time", formatFloat(g_worldTime, "", 0, 9))
                    .Bool("list_valid", list !is null).Int("matches", matches).Bool("buff_on", found !is null)
                    .Int("left", found !is null ? found.m_duration : -1)
                    .Int("duration", found !is null ? found.m_def.m_duration : -1)
                    .Raw("intensity", formatFloat(found !is null ? found.m_intensity : 0, "", 0, 9));
                if (list !is null)
                {
                    vec2 miss = list.MissChance();
                    // Expose independent native ice affliction inputs alongside
                    // the actual combined factor. No assumption that ice is0.
                    row.Raw("moveMul", formatFloat(list.MoveSpeedMul(), "", 0, 9))
                        .Raw("missAttack", formatFloat(miss.x, "", 0, 9))
                        .Raw("missSpell", formatFloat(miss.y, "", 0, 9))
                        .Raw("icePool", formatFloat(list.m_iceDmgPool, "", 0, 9))
                        .Raw("iceSlowMax", formatFloat(Tweak::IceSlowMax, "", 0, 9))
                        .Raw("iceSlowPow", formatFloat(Tweak::IceSlowPow, "", 0, 9));
                }
            }
            m_rows.insertLast(row.Close());
        }

        bool UpdateFrame(int ms) override
        {
            m_elapsed += ms; m_left -= ms; m_frames++;
            bool final = m_left <= 0;
            Sample(ms, final);
            if (!final)
                return false;
            uint parts = (m_rows.length() + QA_ACTOR_BUFF_CHUNK - 1) / QA_ACTOR_BUFF_CHUNK;
            for (uint part = 0; part < parts; part++)
            {
                array<string> rows;
                for (uint i = part * QA_ACTOR_BUFF_CHUNK; i < m_rows.length() && i < (part + 1) * QA_ACTOR_BUFF_CHUNK; i++)
                    rows.insertLast(m_rows[i]);
                Json reply;
                Emit(reply.Str("ev", "actorbuffobserve").Str("tag", m_tag).Int("part", part).Int("parts", parts)
                    .Int("stored", m_rows.length()).Int("seen", m_seen).Int("dropped", m_dropped)
                    .Bool("truncated", m_dropped > 0).Int("start", m_start).Int("end", int(g_scene.GetTime()))
                    .Int("ms", m_elapsed).Int("frames", m_frames).Int("unit", m_unitId).Str("buff", m_path)
                    .Raw("samples", RawArray(rows)));
            }
            g_qaActorBuffBusy = false;
            return true;
        }
    }

    // actorbuffobserve <tag> <ms> <unitId> <buffPath>: native per-frame live-Actor
    // buff counter, exact HP, MoveSpeedMul/MissChance and ice-affliction inputs.
    // Read-only;100..12000ms,1024 samples,16/part; explicit truncation/validity.
    void VerbQAActorBuffObserve(const string &in id, array<string>@ args)
    {
        auto player = GetLocalPlayer();
        if (player is null || QueuedTasks::g_instance is null || args.length() != 4)
        {
            Fail(id, "usage: actorbuffobserve <tag> <ms> <unitId> <buffPath>; needs live gameplay task module");
            return;
        }
        int ms = int(parseInt(args[1])), unitId = int(parseInt(args[2]));
        auto unit = g_scene.GetUnit(unitId);
        Actor@ actor = null;
        if (unit.IsValid() && !unit.IsDestroyed())
            @actor = cast<Actor>(unit.GetScriptBehavior());
        auto def = LoadActorBuff(args[3]);
        if (g_qaActorBuffBusy || args[0].length() > 64 || ms < 100 || ms > 12000
            || def is null || actor is null || actor.IsDead() || actor.GetBuffList() is null
            || dist(xy(unit.GetPosition()), xy(player.m_unit.GetPosition())) > 1200)
        {
            Fail(id, "observer busy, invalid bound/buff, or target is not a live Actor within1200px");
            return;
        }
        QAActorBuffTask task;
        task.m_tag = args[0]; task.m_path = args[3]; task.m_unitId = unitId;
        task.m_start = int(g_scene.GetTime()); task.m_left = ms; @task.m_def = def;
        task.Sample(0);
        g_qaActorBuffBusy = true;
        QueuedTasks::Queue(task);
        Emit(Reply(id, true).Str("tag", task.m_tag).Int("ms", ms).Int("unit", unitId)
            .Int("sample_cap", QA_ACTOR_BUFF_CAP).Int("chunk", QA_ACTOR_BUFF_CHUNK));
    }

    void Register_qa_actor_buffs()
    {
        RegisterVerb("actorbuffobserve", "<tag> <ms> <unitId> <buffPath>", Verb(VerbQAActorBuffObserve));
    }
}
