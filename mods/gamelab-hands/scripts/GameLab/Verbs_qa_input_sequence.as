// QA-only native-frame input sequences. This calls the existing input writer;
// it never invokes abilities, changes resources, hooks effects or sends OS input.
namespace GameLab
{
    bool g_qaInputSequenceBusy = false;

    class QAInputStep
    {
        int ms;
        vec2 move, aim;
        array<string> buttons;
    }

    bool QAInputDigits(const string &in text)
    {
        if (text.isEmpty()) return false;
        for (uint i = 0; i < text.length(); i++)
            if (string("0123456789").findFirst(text.substr(i, 1)) < 0) return false;
        return true;
    }

    bool QAInputAxis(const string &in text)
    {
        string value = text;
        if (value.substr(0, 1) == "-") value = value.substr(1);
        auto parts = value.split(".");
        if (parts.length() > 2 || !QAInputDigits(parts[0])) return false;
        if (parts.length() == 2 && !QAInputDigits(parts[1])) return false;
        float n = parseFloat(text);
        return n == n && n >= -1 && n <= 1;
    }

    class QAInputSequenceTask : QueuedTasks::UpdatingTask
    {
        string m_id, m_tag, m_error;
        int m_playerId, m_created, m_started = -1, m_index = 0, m_wait = 0;
        int m_stepMs = 0, m_stepFrames = 0, m_first = -1, m_last = -1;
        int m_dtMin = 2147483647, m_dtMax = 0, m_tail = 0, m_frames = 0;
        vec2 m_posFirst, m_posLast;
        int m_totalMs = 0, m_stable = 0;
        uint m_expectedWrites;
        array<QAInputStep@> m_steps;
        array<string> m_rows;

        void EndStep()
        {
            auto step = m_steps[m_index];
            string stepId = m_id + ":" + m_index;
            Json row;
            row.Int("step", m_index).Str("id", stepId).Int("requested_ms", step.ms)
                .Int("actual_ms", m_stepMs).Int("frames", m_stepFrames)
                .Int("first_write", m_first).Int("last_write", m_last)
                .Int("dt_min", m_dtMin).Int("dt_max", m_dtMax)
                .Num("x_first", m_posFirst.x).Num("y_first", m_posFirst.y)
                .Num("x_last", m_posLast.x).Num("y_last", m_posLast.y)
                .Raw("buttons", StrArray(step.buttons));
            m_rows.insertLast(row.Close());
            Json done;
            Emit(done.Str("ev", "input_done").Str("id", stepId).Str("sequence", m_tag)
                .Int("step", m_index).Int("frames", m_stepFrames)
                .Int("first_write", m_first).Int("last_write", m_last)
                .Int("actual_ms", m_stepMs));
            m_index++;
            m_stepMs = 0; m_stepFrames = 0; m_first = -1; m_last = -1;
            m_dtMin = 2147483647; m_dtMax = 0;
            // The last button write must survive this frame's player update.
            // Start the empty release writes on subsequent native frames.
            if (m_index >= int(m_steps.length())) m_tail = 2;
        }

        bool Finish(bool released)
        {
            Json reply;
            Emit(reply.Str("ev", "inputsequence").Str("id", m_id).Str("tag", m_tag)
                .Bool("ok", m_error.isEmpty() && released).Str("error", m_error)
                .Int("player", m_playerId).Int("created", m_created)
                .Int("start", m_started).Int("end", int(g_scene.GetTime()))
                .Int("frames", m_frames).Int("total_ms", m_totalMs)
                .Int("completed_steps", m_rows.length()).Int("requested_steps", m_steps.length())
                .Bool("released", released).Raw("steps", RawArray(m_rows)));
            g_qaInputSequenceBusy = false;
            return true;
        }

        bool Abort(const string &in reason)
        {
            m_error = reason;
            // A separate live Hold owns the writer now. Do not erase that Hold.
            if (g_held.msLeft > 0) return Finish(false);
            m_tail = 2;
            return false;
        }

        bool UpdateFrame(int ms) override
        {
            auto input = GetInput();
            if (m_tail > 0)
            {
                if (input is null || g_held.msLeft > 0)
                {
                    if (m_error.isEmpty()) m_error = "release interrupted by missing input or another Hold";
                    return Finish(false);
                }
                if (g_inputFrames != m_expectedWrites && m_error.isEmpty())
                    m_error = "another writer interfered with release";
                if ((ms <= 0 || ms > 100) && m_error.isEmpty())
                    m_error = "invalid native release frame";
                WriteInput(input, vec2(), false, vec2(), null, false);
                m_expectedWrites = g_inputFrames;
                m_tail--;
                return m_tail == 0 ? Finish(true) : false;
            }
            m_wait += ms;
            auto player = GetLocalPlayer();
            if (input is null || player is null || player.IsDead()
                || !player.m_unit.IsValid() || player.m_unit.IsDestroyed()
                || player.m_unit.GetId() != m_playerId)
                return Abort("local player identity/death/input changed");
            if (g_held.msLeft > 0 || Releasing() || g_inputFrames != m_expectedWrites)
                return Abort("another native input writer or release interfered");
            if (ms <= 0 || ms > 100 || m_wait > 10000)
                return Abort("invalid native frame or bounded sequence deadline");
            // Has is read-only. This is the same previous-frame priority tested
            // by the player's GetInput(Focus::GAMEPLAY); do not claim focus.
            if (!Focus::Has(Focus::GAMEPLAY))
            {
                if (m_started >= 0) return Abort("gameplay focus lost during sequence");
                m_stable = 0;
                return m_wait > 3000 ? Abort("no gameplay focus within3000ms") : false;
            }
            if (m_started < 0)
            {
                // Two focused, writer-free frames precede any button press.
                if (++m_stable < 2) return false;
                m_started = int(g_scene.GetTime());
            }
            auto step = m_steps[m_index];
            int now = int(g_scene.GetTime());
            WriteInput(input, step.move, true, step.aim, step.buttons, m_stepFrames == 0);
            m_expectedWrites = g_inputFrames;
            if (m_first < 0) { m_first = now; m_posFirst = xy(player.m_unit.GetPosition()); }
            m_posLast = xy(player.m_unit.GetPosition());
            m_last = now; m_stepMs += ms; m_totalMs += ms; m_stepFrames++; m_frames++;
            m_dtMin = min(m_dtMin, ms); m_dtMax = max(m_dtMax, ms);
            if (m_stepMs >= step.ms) EndStep();
            return false;
        }
    }

    // inputsequence <tag> <ms/mx/my/ax/ay/buttons> ... (1..8 steps).
    // Axes are finite decimal values in[-1,1], move length<=1; '-' is no buttons.
    // A button must be released by a separate step before it can be pressed again.
    void VerbQAInputSequence(const string &in id, array<string>@ args)
    {
        auto player = GetLocalPlayer();
        if (player is null || player.IsDead() || QueuedTasks::g_instance is null
            || args.length() < 2 || args.length() > 9 || args[0].isEmpty()
            || args[0].length() > 64 || g_qaInputSequenceBusy || g_held.msLeft > 0 || Releasing())
        {
            Fail(id, "needs live player, idle input, tag<=64, and1..8 bounded steps");
            return;
        }
        QAInputSequenceTask task;
        int total = 0;
        for (uint i = 1; i < args.length(); i++)
        {
            auto fields = args[i].split("/");
            if (fields.length() != 6 || fields[0].length() > 4 || !QAInputDigits(fields[0]))
            {
                Fail(id, "step must be ms/mx/my/ax/ay/buttons"); return;
            }
            int ms = int(parseInt(fields[0]));
            if (ms < 1 || ms > 1000 || total + ms > 5000)
            {
                Fail(id, "each step1..1000ms; total<=5000ms"); return;
            }
            for (uint j = 1; j < 5; j++)
                if (!QAInputAxis(fields[j]))
                {
                    Fail(id, "axis must be a finite decimal in[-1,1]"); return;
                }
            QAInputStep step;
            step.ms = ms;
            step.move = vec2(parseFloat(fields[1]), parseFloat(fields[2]));
            step.aim = vec2(parseFloat(fields[3]), parseFloat(fields[4]));
            if (length(step.move) > 1.0001f)
            {
                Fail(id, "move stick length exceeds1"); return;
            }
            if (fields[5] != "-")
            {
                auto buttons = fields[5].split(",");
                for (uint j = 0; j < buttons.length(); j++)
                {
                    if (BUTTONS.find(buttons[j]) < 0 || step.buttons.find(buttons[j]) >= 0
                        || (task.m_steps.length() > 0
                            && task.m_steps[task.m_steps.length()-1].buttons.find(buttons[j]) >= 0))
                    {
                        Fail(id, "unknown/repeated button or missing release step"); return;
                    }
                    step.buttons.insertLast(buttons[j]);
                }
            }
            task.m_steps.insertLast(step); total += ms;
        }
        task.m_id = id; task.m_tag = args[0]; task.m_created = int(g_scene.GetTime());
        task.m_playerId = player.m_unit.GetId(); task.m_expectedWrites = g_inputFrames;
        g_qaInputSequenceBusy = true;
        QueuedTasks::Queue(task);
        Emit(Reply(id, true).Str("tag", task.m_tag).Int("steps", task.m_steps.length())
            .Int("requested_ms", total).Int("player", task.m_playerId));
    }

    void Register_qa_input_sequence()
    {
        RegisterVerb("inputsequence", "<tag> <ms/mx/my/ax/ay/buttons> ...", Verb(VerbQAInputSequence));
    }
}
