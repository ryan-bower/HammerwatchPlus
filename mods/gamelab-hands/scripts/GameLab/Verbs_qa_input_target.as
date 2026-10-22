// Additive QA controller: existing inputsequence guards/buttons, current local
// input cursor only. No ability calls, target-helper writes, stat writes or OS input.
namespace GameLab
{
    bool QATargetNumber(const string &in text)
    {
        if (text.length() > 24) return false;
        string value = text;
        if (value.substr(0, 1) == "-") value = value.substr(1);
        auto parts = value.split(".");
        if (parts.length() > 2 || !QAInputDigits(parts[0])) return false;
        if (parts.length() == 2 && !QAInputDigits(parts[1])) return false;
        float n = parseFloat(text);
        return n == n && n >= -100000 && n <= 100000;
    }

    Skills::PlayerSkill@ QATargetSkill(PlayerBase@ player, const string &in name)
    {
        if (player is null || name == "-") return null;
        if (player.m_record is null || player.m_record.playerClass is null
            || player.m_skills.length() > 128) return null;
        uint sid = HashString(name);
        auto definition = player.m_record.playerClass.GetSkillDef(sid);
        if (definition is null || definition.m_id != name) return null;
        Skills::PlayerSkill@ found;
        uint matches = 0;
        for (uint i = 0; i < player.m_skills.length(); i++)
            if (player.m_skills[i] !is null && player.m_skills[i].m_skillId == sid)
            {
                @found = cast<Skills::PlayerSkill>(player.m_skills[i]);
                if (found is null) return null;
                matches++;
            }
        return matches == 1 ? found : null;
    }

    class QATargetInputTask : QAInputSequenceTask
    {
        PlayerRecord@ m_record;
        BaseGameMode@ m_mode;
        Skills::PlayerSkill@ m_skill;
        string m_skillName;
        vec2 m_world;
        array<GameInput@> m_cursorInputs;
        array<vec2> m_cursorOriginal, m_cursorLast;
        array<string> m_cursorRows, m_restoreRows;
        int m_cursorSeen = 0, m_cursorDropped = 0;
        bool m_cursorRestored = false;

        bool SoleOwner()
        {
            auto player = cast<PlayerBase>(GetLocalPlayer());
            if (m_record is null || !m_record.local || GetLocalPlayerRecord() !is m_record
                || cast<BaseGameMode>(g_gameMode) !is m_mode || player is null
                || m_record.actor !is player || player.m_unit.GetId() != m_playerId
                || g_players.length() > 16)
                return false;
            for (uint i = 0; i < g_players.length(); i++)
                if (g_players[i] !is null && g_players[i] !is m_record) return false;
            return true;
        }

        int CursorIndex(GameInput@ input)
        {
            for (uint i = 0; i < m_cursorInputs.length(); i++)
                if (m_cursorInputs[i] is input) return int(i);
            return -1;
        }

        string CursorGuard(GameInput@ input)
        {
            if (!SoleOwner()) return "cursor requires unchanged sole local actor/record/mode";
            if (input is null || input.UsingGamepad) return "cursor requires current native mouse input";
            if (m_skillName != "-" && QATargetSkill(cast<PlayerBase>(GetLocalPlayer()), m_skillName) !is m_skill)
                return "selected native skill identity changed";
            vec2 screen = ToScreenspace(xyz(m_world));
            float width = m_mode.m_wndWidth * m_mode.m_wndScale;
            float height = m_mode.m_wndHeight * m_mode.m_wndScale;
            if (!(width > 0 && height > 0 && screen.x >= 0 && screen.y >= 0
                  && screen.x < width && screen.y < height)) return "world cursor is outside native viewport";
            if (dist(xy(ToWorldspace(screen)), m_world) > 0.1f) return "world screen roundtrip failed";
            int slot = CursorIndex(input);
            if (slot < 0 && m_cursorInputs.length() >= 8) return "cursor input handle cap";
            if (slot >= 0 && dist(input.MousePos, m_cursorLast[slot]) > 0.01f
                && dist(input.MousePos, m_cursorOriginal[slot]) > 0.01f)
                return "cursor changed outside the owned point or original neutral point";
            return "";
        }

        void PinAndRead(GameInput@ input, int ms, bool releaseFrame, int stepIndex)
        {
            int slot = CursorIndex(input);
            if (slot < 0)
            {
                slot = int(m_cursorInputs.length());
                m_cursorInputs.insertLast(input);
                m_cursorOriginal.insertLast(input.MousePos);
                m_cursorLast.insertLast(input.MousePos);
            }
            // Only this current local input handle is touched, never the global
            // g_inputs history. The native projection is recomputed each frame.
            input.MousePos = ToScreenspace(xyz(m_world));
            m_cursorLast[slot] = input.MousePos;
            auto player = cast<PlayerBase>(GetLocalPlayer());
            vec2 at = xy(player.m_unit.GetPosition()), aim = player.GetDirection();
            vec2 world = xy(ToWorldspace(input.MousePos));
            int timeline = -2;
            vec2 pos, direction;
            auto directional = cast<Skills::PlayerSkillDirectional>(m_skill);
            auto positioned = cast<Skills::PlayerSkillPosition>(m_skill);
            if (directional !is null && directional.m_timeline !is null)
            {
                timeline = directional.m_timeline.m_castingT;
                pos = directional.m_timeline.m_posTarget;
                direction = directional.m_timeline.m_dirTarget;
            }
            else if (positioned !is null && positioned.m_timeline !is null)
            {
                timeline = positioned.m_timeline.m_castingT;
                pos = positioned.m_timeline.m_posTarget;
                direction = positioned.m_timeline.m_dirTarget;
            }
            Json row;
            row.Int("now", int(g_scene.GetTime())).Int("dt", ms).Int("step", stepIndex)
                .Bool("release", releaseFrame).Int("buffer", slot).Bool("gamepad", input.UsingGamepad)
                .Num("x", at.x).Num("y", at.y).Num("screen_x", input.MousePos.x).Num("screen_y", input.MousePos.y)
                .Num("world_x", world.x).Num("world_y", world.y).Num("round_error", dist(world, m_world))
                .Num("actor_dir_x", aim.x).Num("actor_dir_y", aim.y)
                .Int("ct", m_skill is null ? -2 : m_skill.m_castingT)
                .Int("cd", m_skill is null ? -2 : m_skill.m_cooldownC).Int("timeline", timeline)
                .Num("cast_x", pos.x).Num("cast_y", pos.y).Num("cast_dir_x", direction.x).Num("cast_dir_y", direction.y)
                .Raw("manaExact", formatFloat(double(m_record.mana) * double(m_record.MaxMana()), "", 0, 9))
                .Raw("hpExact", formatFloat(double(m_record.hp) * double(m_record.MaxHealth()), "", 0, 9));
            string sample = row.Close();
            m_cursorSeen++;
            if (m_cursorRows.length() >= 256 || sample.length() > 1400) m_cursorDropped++;
            else m_cursorRows.insertLast(sample);
        }

        bool RestoreCursor()
        {
            bool owner = SoleOwner(), restored = true;
            for (uint i = 0; i < m_cursorInputs.length(); i++)
            {
                auto input = m_cursorInputs[i];
                bool neutral = owner && input !is null && dist(input.MousePos, m_cursorOriginal[i]) <= 0.01f;
                bool ours = owner && input !is null && dist(input.MousePos, m_cursorLast[i]) <= 0.01f;
                vec2 before = input is null ? vec2() : input.MousePos;
                if (ours) input.MousePos = m_cursorOriginal[i];
                bool ok = (ours || neutral) && dist(input.MousePos, m_cursorOriginal[i]) <= 0.01f;
                Json row;
                row.Int("buffer", i).Bool("owned_last_value", ours).Bool("already_neutral", neutral).Bool("restored", ok)
                    .Num("before_x", before.x).Num("before_y", before.y)
                    .Num("original_x", m_cursorOriginal[i].x).Num("original_y", m_cursorOriginal[i].y);
                m_restoreRows.insertLast(row.Close());
                restored = restored && ok;
            }
            return restored;
        }

        bool Finish(bool released) override
        {
            m_cursorRestored = RestoreCursor();
            if (!m_cursorRestored && m_error.isEmpty()) m_error = "cursor restore lost ownership or last value";
            bool done = QAInputSequenceTask::Finish(released);
            int count = int(m_cursorRows.length()), parts = max(1, (count + 7) / 8);
            bool complete = m_error.isEmpty() && released && m_cursorRestored && m_cursorDropped == 0
                && m_cursorSeen == m_frames + 1 && count == m_cursorSeen;
            for (int part = 0; part < parts; part++)
            {
                array<string> rows;
                for (int i = part * 8; i < min(count, part * 8 + 8); i++) rows.insertLast(m_cursorRows[i]);
                Json reply;
                Emit(reply.Str("ev", "inputtarget").Str("id", m_id).Str("tag", m_tag)
                    .Bool("complete", complete).Str("error", m_error).Int("part", part).Int("parts", parts)
                    .Int("stored", count).Int("seen", m_cursorSeen).Int("dropped", m_cursorDropped)
                    .Bool("truncated", m_cursorDropped > 0).Int("start", m_started).Int("end", int(g_scene.GetTime()))
                    .Int("frames", m_frames).Str("skill", m_skillName).Int("player", m_playerId)
                    .Num("target_x", m_world.x).Num("target_y", m_world.y)
                    .Bool("cursor_restored", m_cursorRestored).Raw("restore", RawArray(m_restoreRows))
                    .Str("phase", "post_input_write_before_player_update; final neutral release restores cursor")
                    .Raw("samples", RawArray(rows)));
            }
            return done;
        }

        bool UpdateFrame(int ms) override
        {
            auto input = GetInput();
            if (m_error.isEmpty())
            {
                string error = CursorGuard(input);
                if (!error.isEmpty()) return Abort(error);
            }
            uint writes = g_inputFrames;
            bool releaseFrame = m_tail > 0;
            int index = m_index;
            bool finished = QAInputSequenceTask::UpdateFrame(ms);
            // Finish restored the cursor on the final neutral release frame.
            // Step frames plus the first neutral release are sampled here.
            if (!finished && m_error.isEmpty() && g_inputFrames == writes + 1)
                PinAndRead(input, ms, releaseFrame, index);
            return finished;
        }
    }

    // Same bounded step language as inputsequence; the original controller is
    // unchanged. A selected native active skill is optional read-only telemetry.
    void VerbQAInputTarget(const string &in id, array<string>@ args)
    {
        auto player = cast<PlayerBase>(GetLocalPlayer());
        if (player is null || player.IsDead() || QueuedTasks::g_instance is null
            || args.length() < 5 || args.length() > 12 || args[0].isEmpty() || args[0].length() > 64
            || args[1].isEmpty() || args[1].length() > 128 || !QATargetNumber(args[2]) || !QATargetNumber(args[3])
            || g_qaInputSequenceBusy || g_held.msLeft > 0 || Releasing())
        { Fail(id, "needs live idle local actor, tag, skill-or-minus, worldXY and1..8 bounded steps"); return; }
        QATargetInputTask task;
        @task.m_record = GetLocalPlayerRecord(); @task.m_mode = cast<BaseGameMode>(g_gameMode);
        task.m_skillName = args[1]; @task.m_skill = QATargetSkill(player, args[1]);
        task.m_world = vec2(parseFloat(args[2]), parseFloat(args[3]));
        task.m_playerId = player.m_unit.GetId();
        if (task.m_mode is null || !task.SoleOwner() || (args[1] != "-" && task.m_skill is null)
            || dist(task.m_world, xy(player.m_unit.GetPosition())) > 1200)
        { Fail(id, "needs sole local record/mode, actual selected active skill and world target within1200px"); return; }
        int total = 0;
        for (uint i = 4; i < args.length(); i++)
        {
            auto fields = args[i].split("/");
            if (fields.length() != 6 || fields[0].length() > 4 || !QAInputDigits(fields[0]))
            { Fail(id, "step must be ms/mx/my/ax/ay/buttons"); return; }
            int ms = int(parseInt(fields[0]));
            if (ms < 1 || ms > 1000 || total + ms > 5000)
            { Fail(id, "each step1..1000ms; total<=5000ms"); return; }
            for (uint j = 1; j < 5; j++)
                if (!QAInputAxis(fields[j])) { Fail(id, "axis must be finite decimal in[-1,1]"); return; }
            QAInputStep step;
            step.ms = ms; step.move = vec2(parseFloat(fields[1]), parseFloat(fields[2]));
            step.aim = vec2(parseFloat(fields[3]), parseFloat(fields[4]));
            if (length(step.move) > 1.0001f) { Fail(id, "move stick length exceeds1"); return; }
            if (fields[5] != "-")
            {
                auto buttons = fields[5].split(",");
                for (uint j = 0; j < buttons.length(); j++)
                {
                    if (BUTTONS.find(buttons[j]) < 0 || step.buttons.find(buttons[j]) >= 0
                        || (task.m_steps.length() > 0 && task.m_steps[task.m_steps.length()-1].buttons.find(buttons[j]) >= 0))
                    { Fail(id, "unknown/repeated button or missing release step"); return; }
                    step.buttons.insertLast(buttons[j]);
                }
            }
            task.m_steps.insertLast(step); total += ms;
        }
        task.m_id = id; task.m_tag = args[0]; task.m_created = int(g_scene.GetTime());
        task.m_expectedWrites = g_inputFrames;
        g_qaInputSequenceBusy = true; QueuedTasks::Queue(task);
        Emit(Reply(id, true).Str("tag", task.m_tag).Int("steps", task.m_steps.length())
            .Int("requested_ms", total).Int("player", task.m_playerId).Str("skill", task.m_skillName)
            .Num("target_x", task.m_world.x).Num("target_y", task.m_world.y));
    }

    void Register_qa_input_target()
    {
        RegisterVerb("inputtarget", "<tag> <skillId|-> <worldX> <worldY> <ms/mx/my/ax/ay/buttons> ...", Verb(VerbQAInputTarget));
    }
}
