// Controlled channel fixture, deliberately without optional Specs type references.
// Requires reviewed F1 inputtarget source9654a0ef926deeaeb4ba947878dcd84a59de16ad549637bc5beb6e7fe5c3c9da.
// Reuses its ownership/projection/cache/PinAndRead/restore implementation. No
// ability call, cooldown/buff/stat setter, synthetic completion or product hook.
namespace GameLab
{
    const string QA_FORGE_NR = "hwp_pri_necrotic_resurrection";
    const string QA_FORGE_CLASS = "hwp_priest_forgemaster";
    const string QA_FORGE_BODY = "players/hwp/specs/forgemaster/bodies/";
    const uint QA_FORGE_CAP = 2048;

    class QAForgeChannelTask : QATargetInputTask
    {
        string m_case, m_button, m_bodyName, m_targetName;
        int m_bodyId, m_targetId, m_duration, m_now = 0, m_channelAt = -1;
        int m_deadline = -1, m_actionAt = -1, m_finishAt = -1, m_release = 0;
        int m_seen = 0, m_dropped = 0, m_written = 0;
        bool m_changed = false, m_restored = false, m_released = false, m_confirmed = false;
        vec2 m_recover, m_bodySpot, m_targetSpot;
        Player@ m_player;
        Skills::Charge@ m_dash;
        PointCost@ m_cost;
        ActorBuffDef@ m_raising, m_stance, m_devouring;
        ActorBuffStackDef@ m_heresy, m_favor;
        array<string> m_samples, m_actions;

        string Exact(double value) { return formatFloat(value, "", 0, 9); }

        int BuffLeft(ActorBuffDef@ def)
        {
            int found = -1;
            for (uint i = 0; i < m_player.m_buffs.m_buffs.length(); i++)
            {
                auto b = m_player.m_buffs.m_buffs[i];
                if (b !is null && b.m_def !is null && b.m_def.m_pathHash == def.m_pathHash)
                { if (found >= 0) return -2; found = b.m_duration; }
            }
            return found;
        }

        string Cost()
        {
            auto rec = m_record;
            vec2 mul = rec.GetModifiers().SkillCostMul(m_player);
            bool freeHp = GetVarBool("cht_plr_free_health_cost");
            bool freeMana = GetVarBool("cht_plr_free_mana_cost") || m_player.m_buffs.FreeMana();
            if (freeHp) mul.x = 0; if (freeMana) mul.y = 0;
            vec2 maximum(float(rec.MaxHealth()), float(rec.MaxMana()));
            vec2 current = vec2(rec.hp, rec.mana) * maximum;
            auto scaled = m_cost.percentageMaxCost * maximum + m_cost.percentageCurrCost * current;
            scaled += vec2(m_cost.flatCost.x, m_cost.flatCost.y);
            scaled *= mul * m_cost.multiplier;
            auto adjust = rec.GetModifiers().UsePoints(m_player, scaled);
            vec2 expense = scaled + vec2(adjust.x, adjust.y) * mul;
            Json row;
            return row.Raw("combined", QAPointCost(m_cost)).Bool("free_health", freeHp).Bool("free_mana", freeMana)
                .Raw("global_health_multiplier", Exact(mul.x)).Raw("global_mana_multiplier", Exact(mul.y))
                .Raw("scaled_health", Exact(scaled.x)).Raw("scaled_mana", Exact(scaled.y))
                .Int("use_points_health", adjust.x).Int("use_points_mana", adjust.y)
                .Raw("expense_health", Exact(expense.x)).Raw("expense_mana", Exact(expense.y)).Close();
        }

        void Sample(int dt, const string &in phase, vec2 move, const string &in button)
        {
            m_seen++;
            if (m_samples.length() >= QA_FORGE_CAP) { m_dropped++; return; }
            auto body = g_scene.GetUnit(m_bodyId), target = g_scene.GetUnit(m_targetId);
            bool bodyValid = body.IsValid() && !body.IsDestroyed();
            vec2 bodyPos = bodyValid ? xy(body.GetPosition()) : vec2();
            auto actor = target.IsValid() && !target.IsDestroyed() ? cast<Actor>(target.GetScriptBehavior()) : null;
            bool targetValid = actor !is null && !actor.IsDead();
            bool geometryChecked = targetValid && ((phase == "before_fixture" && (m_case == "C0" || m_case == "C1"))
                || (m_case == "CAL" && m_seen == 1));
            bool shotWall = false; int shotHits = 0;
            vec2 playerPos = xy(m_player.m_unit.GetPosition());
            vec2 targetPos = targetValid ? xy(target.GetPosition()) : vec2();
            if (geometryChecked)
            {
                auto hits = g_scene.Raycast(playerPos, targetPos, ~0, RaycastType::Shot);
                shotHits = hits.length();
                if (hits.length() > 128) geometryChecked = false;
                for (uint i = 0; i < 128 && i < hits.length(); i++)
                {
                    RaycastResult result = hits[i];
                    UnitPtr hit = result.FetchUnit(g_scene);
                    if (hit.IsValid() && cast<IDamageTaker>(hit.GetScriptBehavior()) !is null) continue;
                    shotWall = true;
                }
            }
            auto rec = m_record;
            int favorTimer = -1;
            for (uint i = 0; i < m_player.m_buffs.m_stacks.length(); i++)
                if (m_player.m_buffs.m_stacks[i].m_def is m_favor)
                    favorTimer = m_player.m_buffs.m_stacks[i].m_timerTickC;
            array<string> risen;
            auto units = g_scene.FetchAllUnits(~0, xy(m_player.m_unit.GetPosition()), 1200);
            for (uint i = 0; i < units.length(); i++)
                if (units[i].IsValid() && !units[i].IsDestroyed()
                    && units[i].GetDebugName().findFirst("players/hwp/specs/forgemaster/risen/") == 0)
                {
                    auto a = cast<Actor>(units[i].GetScriptBehavior());
                    if (a is null || a.IsDead()) continue;
                    Json r;
                    risen.insertLast(r.Int("unit", units[i].GetId()).Str("name", units[i].GetDebugName())
                        .Bool("owned", GetPlayerOwner(a) is m_player).Close());
                }
            vec2 pos = xy(m_player.m_unit.GetPosition());
            Json row;
            row.Int("now", int(g_scene.GetTime())).Int("dt", dt).Str("phase", phase)
                .Int("player", m_playerId).Str("class", rec.playerClass.m_id).Str("skill", m_skillName)
                .Bool("owned_skill", m_skill.m_owner is m_player).Num("x", pos.x).Num("y", pos.y)
                .Int("raising_left", BuffLeft(m_raising)).Int("stance_left", BuffLeft(m_stance))
                .Int("devouring_left", BuffLeft(m_devouring)).Bool("root", m_player.m_buffs.LockMovement())
                .Bool("silence", m_player.m_buffs.Silence()).Bool("disarm", m_player.m_buffs.Disarm())
                .Int("heresy", m_player.GetStacks(m_heresy)).Int("favor", m_player.GetStacks(m_favor))
                .Int("favor_timer", favorTimer).Int("nr_cd", m_skill.m_cooldownC)
                .Int("nr_base_cd", m_skill.m_cooldown).Num("nr_cd_mul", m_skill.m_modCooldownMul)
                .Int("dash_cd", m_dash.m_cooldownC).Int("dash_cast", m_dash.m_castingC)
                .Int("dash_base_cd", m_dash.m_cooldown).Num("dash_cd_mul", m_dash.m_modCooldownMul)
                .Int("dash_dist", m_dash.m_dist).Num("dash_remaining", m_dash.m_distC)
                .Int("dash_charges", rec.dashCharges).Int("dash_recharge", m_player.m_dashRechargeC)
                .Int("dash_max", rec.currStats.MaxDashes).Num("dash_recharge_ms", rec.currStats.DashRechargeMul * Tweak::BaseDashRechargeTime)
                .Bool("infinite_dashes", CVars::ChtInfiniteDashes).Bool("body_valid", bodyValid).Int("body", m_bodyId)
                .Str("body_name", bodyValid ? body.GetDebugName() : "").Raw("risen", RawArray(risen))
                .Int("target", m_targetId).Bool("target_valid", targetValid)
                .Str("target_name", targetValid ? target.GetDebugName() : "")
                .Num("body_x", bodyPos.x).Num("body_y", bodyPos.y).Bool("body_position_current", bodyValid)
                .Num("target_x", targetPos.x).Num("target_y", targetPos.y)
                .Bool("geometry_checked", geometryChecked).Bool("shot_wall", shotWall).Int("shot_hits", shotHits)
                .Int("target_max", targetValid ? actor.GetMaxHp() : -1)
                .Raw("target_hp", targetValid ? formatFloat(double(actor.GetHealth()) * actor.GetMaxHp(), "", 0, 9) : "null")
                .Int("max_mana", rec.MaxMana()).Int("max_health", rec.MaxHealth())
                .Raw("mana", formatFloat(double(rec.mana) * rec.MaxMana(), "", 0, 9))
                .Raw("mana_fraction", formatFloat(rec.mana, "", 0, 9))
                .Raw("stat_mana", Exact(float(rec.currStats.Mana))).Raw("mana_regen", Exact(float(rec.currStats.ManaRegen)))
                .Raw("mana_gain", Exact(float(rec.currStats.ManaGain))).Raw("cost", Cost())
                .Num("move_x", move.x).Num("move_y", move.y).Str("button", button)
                .Num("cursor_world_x", m_world.x).Num("cursor_world_y", m_world.y)
                .Num("projection_error", dist(xy(ToWorldspace(GetInput().MousePos)), m_world))
                .Raw("cursor", phase == "frame" && m_cursorRows.length() == 1 ? m_cursorRows[0] : "null");
            string raw = row.Close();
            // Two rows plus bounded headers/restore fit the 15000-char Emit
            // guard. Over-budget rows are explicit truncation, never a pass.
            if (raw.length() > 3400) { m_dropped++; return; }
            m_samples.insertLast(raw);
        }

        bool Stop(const string &in why)
        {
            if (m_error.isEmpty()) m_error = why;
            m_release = 2;
            return false;
        }

        bool Done()
        {
            m_restored = RestoreCursor();
            if (!m_restored && m_error.isEmpty()) m_error = "cursor restore failed ownership";
            int parts = max(1, (int(m_samples.length()) + 1) / 2);
            for (int part = 0; part < parts; part++)
            {
                array<string> rows;
                for (int i = part * 2; i < min(int(m_samples.length()), (part + 1) * 2); i++) rows.insertLast(m_samples[i]);
                Json row;
                Emit(row.Str("ev", "forgechannel").Str("id", m_id).Str("tag", m_tag).Str("case", m_case)
                    .Bool("complete", m_error.isEmpty() && m_restored && m_released && m_dropped == 0).Str("error", m_error)
                    .Int("part", part).Int("parts", parts).Int("stored", m_samples.length()).Int("seen", m_seen)
                    .Int("dropped", m_dropped).Bool("truncated", m_dropped > 0).Int("player", m_playerId)
                    .Int("start", m_started).Int("channel_at", m_channelAt).Int("deadline", m_deadline)
                    .Int("action_at", m_actionAt).Int("end", int(g_scene.GetTime())).Int("writes", m_written)
                    .Int("cursor_seen", m_cursorSeen).Int("cursor_dropped", m_cursorDropped)
                    .Int("body", m_bodyId).Str("body_name", m_bodyName).Int("target", m_targetId)
                    .Str("target_name", m_targetName).Str("button", m_button).Int("duration", m_duration)
                    .Bool("released", m_released).Bool("cursor_restored", m_restored).Raw("restore", RawArray(m_restoreRows))
                    .Raw("projection_failures", RawArray(m_projectionFailures)).Raw("actions", RawArray(m_actions))
                    .Str("phase", "native_pre_player_update; fixture actions have adjacent before/after samples")
                    .Raw("samples", RawArray(rows)));
            }
            g_qaInputSequenceBusy = false;
            return true;
        }

        bool UpdateFrame(int ms) override
        {
            m_cursorFrame++; @m_guardInput = null;
            auto input = GetInput();
            if (m_release > 0)
            {
                // Never clear a new Hold or a foreign writer. Report incomplete instead.
                if (input is null || g_held.msLeft > 0 || g_inputFrames != m_expectedWrites)
                { if (m_error.isEmpty()) m_error = "release interrupted by foreign writer"; return Done(); }
                WriteInput(input, vec2(), false, vec2(), null, false); m_expectedWrites = g_inputFrames; m_written++;
                if (--m_release == 0) { m_released = true; return Done(); }
                return false;
            }
            if (m_record is null || m_record.playerClass is null || m_player is null || !SoleOwner()
                || m_player.IsDead() || m_record.playerClass.m_id != QA_FORGE_CLASS
                || QATargetSkill(m_player, QA_FORGE_NR) !is m_skill || !Network::IsServer())
                return Stop("sole live local class/skill/server identity changed");
            if (g_held.msLeft > 0 || Releasing() || g_inputFrames != m_expectedWrites)
                return Stop("another posted-input writer interfered");
            if (ms <= 0 || ms > 100) return Stop("native frame outside1..100ms");
            if (!Focus::Has(Focus::GAMEPLAY))
            {
                m_wait += ms;
                if (m_started >= 0 || m_wait > 3000) return Stop("gameplay focus unavailable/lost");
                return false;
            }
            m_now = int(g_scene.GetTime());
            if (m_started < 0)
            {
                if (++m_stable < 2) return false;
                m_started = m_now;
                if (m_case == "CAL") { m_actionAt = m_now; m_finishAt = m_now + 1000; }
            }
            int left = BuffLeft(m_raising);
            if (m_channelAt < 0 && left > 0)
            { m_channelAt = m_now; m_deadline = m_now + left; m_finishAt = m_deadline + 500; }
            if (m_case != "CAL" && m_channelAt < 0 && m_now - m_started > 1000)
                return Stop("no real raising buff after bounded native button/release/confirm");
            bool cancel = m_case == "C0" || m_case == "C1";
            bool drain = m_case == "P1" || m_case == "P3";
            bool landed = m_dash.m_castingC <= 0 && m_dash.m_distC <= 0
                && dist(xy(m_player.m_unit.GetPosition()), m_bodySpot + vec2(0, 10)) <= 2;
            bool intervene = !m_changed && m_channelAt >= 0 && (cancel || drain) && m_now - m_channelAt >= 500
                && (m_case != "C1" || landed);
            // Resolve the FINAL world target before the sole cursor guard.
            // A body->target change cannot reuse the body's same-frame cache.
            if ((cancel && (m_changed || intervene)) || m_case == "CAL")
            {
                auto target = g_scene.GetUnit(m_targetId);
                if (!target.IsValid() || target.IsDestroyed() || target.GetDebugName() != m_targetName)
                    return Stop("owned target disappeared; disappearance is not damage evidence");
                m_world = xy(target.GetPosition());
            }
            string guard = CursorGuard(input);
            if (!guard.isEmpty()) return Stop(guard);
            if (!CursorCacheCurrent(input, g_inputFrames)) return Stop("cursor projection cache changed before fixture/write");
            uint writes = g_inputFrames;
            if (intervene)
            {
                if (left <= 0 || (m_case == "C1" && left < 2000)) return Stop("intervention missed live remaining-time/landing gate");
                auto declared = g_scene.GetUnit(m_bodyId);
                if (!declared.IsValid() || declared.IsDestroyed() || declared.GetDebugName() != m_bodyName
                    || dist(xy(declared.GetPosition()), m_bodySpot) > 0.1f)
                    return Stop("declared body identity/position drifted before intervention");
                Sample(ms, "before_fixture", vec2(), "-");
                Json event;
                event.Int("now", m_now).Str("kind", drain ? "drain" : "remove_body").Int("raising_left", left)
                    .Bool("landed", landed).Raw("mana_before", Exact(double(m_record.mana) * m_record.MaxMana()));
                if (drain) m_record.mana = 0; // Single declared fixture write, AFTER native activation.
                else
                {
                    auto body = g_scene.GetUnit(m_bodyId);
                    if (!body.IsValid() || body.IsDestroyed() || body.GetDebugName() != m_bodyName)
                        return Stop("exact declared body changed before removal");
                    body.Destroy(); // Only the declared non-Actor body; never cull targets or risen.
                    m_finishAt = m_now + 1000;
                }
                event.Raw("mana_after", Exact(double(m_record.mana) * m_record.MaxMana())); m_actions.insertLast(event.Close());
                m_actionAt = m_now; m_changed = true;
                Sample(ms, "after_fixture", vec2(), "-");
            }
            if (m_case == "C1" && !m_changed && m_channelAt >= 0 && m_now - m_channelAt > 1000)
                return Stop("Penance approach never certified with>=2000ms remaining");
            vec2 move; string button = "-";
            if (m_channelAt < 0 && m_case != "CAL")
            {
                int age = m_now - m_started;
                if (age < 100) button = m_button;
                else if (age >= 200 && !m_confirmed) button = "main";
            }
            if ((cancel && m_changed) || m_case == "CAL")
            {
                int age = m_now - m_actionAt;
                if (age >= 100 && age < 300) move = m_recover;
                if (age >= 400 && age < 800) button = "main";
            }
            array<string> buttons;
            if (button != "-") buttons.insertLast(button);
            bool pressed = m_samples.length() == 0 || m_lastButton != button;
            if (!CursorCacheCurrent(input, writes) || g_inputFrames != writes)
                return Stop("cursor projection cache changed before the one input write");
            WriteInput(input, move, true, vec2(0, -1), buttons, pressed);
            m_expectedWrites = g_inputFrames; m_written++;
            if (m_channelAt < 0 && button == "main") m_confirmed = true;
            if (!PinAndRead(input, ms, false, 0, writes)) return Stop("cursor projection cache changed after input write");
            if (m_cursorRows.length() != 1 || m_cursorDropped != 0) return Stop("inherited cursor frame missing/over-budget");
            Sample(ms, "frame", move, button); m_lastButton = button;
            // Retain that exact inherited native cursor row inside our larger
            // frame trace, then drain its short buffer; no cursor evidence drops.
            m_cursorRows.resize(0); @m_guardInput = null;
            if (m_now - m_started > 12500) return Stop("bounded fixture deadline exceeded");
            if (m_finishAt >= 0 && m_now >= m_finishAt) m_release = 2;
            return false;
        }
        string m_lastButton = "-";
    }

    // forgechannel <tag> <P0|P1|P2|P3|C0|C1|CAL> <bodyId> <targetId|-1>
    // <recoverX> <recoverY> <favorPath>. Fixed durations/actions; no arbitrary writer.
    void VerbQAForgeChannel(const string &in id, array<string>@ args)
    {
        auto player = cast<Player>(GetLocalPlayer());
        if (args.length() != 7 || player is null || player.IsDead() || QueuedTasks::g_instance is null
            || player.m_record is null || player.m_record.playerClass is null || player.m_record.playerClass.m_id != QA_FORGE_CLASS
            || !Network::IsServer() || g_qaInputSequenceBusy || g_held.msLeft > 0 || Releasing()
            || args[0].isEmpty() || args[0].length() > 64 || !QAInputAxis(args[4]) || !QAInputAxis(args[5]))
        { Fail(id, "needs sole live Forgemaster/server, idle native writer, fixed case/body/target/direction/favor"); return; }
        const array<string> cases = {"P0", "P1", "P2", "P3", "C0", "C1", "CAL"};
        QAForgeChannelTask task;
        task.m_case = args[1]; task.m_tag = args[0]; task.m_id = id;
        task.m_bodyId = int(parseInt(args[2])); task.m_targetId = int(parseInt(args[3]));
        task.m_recover = vec2(parseFloat(args[4]), parseFloat(args[5]));
        @task.m_player = player; @task.m_record = player.m_record; @task.m_mode = cast<BaseGameMode>(g_gameMode);
        task.m_playerId = player.m_unit.GetId(); task.m_skillName = QA_FORGE_NR; @task.m_skill = QATargetSkill(player, QA_FORGE_NR);
        for (uint i = 0; i < player.m_skills.length(); i++)
            if (player.m_skills[i] !is null && player.m_skills[i].m_id == "dash_skill")
                @task.m_dash = cast<Skills::Charge>(player.m_skills[i]);
        @task.m_raising = LoadActorBuff("players/hwp/specs/buffs_specs.sval:raising");
        @task.m_stance = LoadActorBuff("players/hwp/specs/buffs_specs.sval:penance_stance");
        @task.m_devouring = LoadActorBuff("players/hwp/specs/buffs_specs.sval:devouring");
        @task.m_heresy = ActorBuffStackDef::Get("players/hwp/specs/stacks_specs.sval:heresy");
        @task.m_favor = ActorBuffStackDef::Get(args[6]);
        auto body = g_scene.GetUnit(task.m_bodyId), target = g_scene.GetUnit(task.m_targetId);
        bool cal = task.m_case == "CAL", cancel = task.m_case == "C0" || task.m_case == "C1";
        if (cases.find(task.m_case) < 0 || task.m_mode is null || !task.SoleOwner() || task.m_skill is null
            || task.m_skill.m_owner !is player
            || task.m_dash is null || task.m_raising is null || task.m_stance is null || task.m_devouring is null
            || task.m_heresy is null || task.m_favor is null || length(task.m_recover) > 1.0001f
            || (!cal && (!body.IsValid() || body.IsDestroyed() || body.GetDebugName().findFirst(QA_FORGE_BODY) != 0
                || dist(xy(body.GetPosition()), xy(player.m_unit.GetPosition())) > 140))
            || ((cal || cancel) && (!target.IsValid() || target.IsDestroyed()
                || target.GetDebugName() != "doodads/generic/target_dummy_breakable.unit"
                || cast<Actor>(target.GetScriptBehavior()) is null
                || dist(xy(target.GetPosition()), xy(player.m_unit.GetPosition())) > 300)))
        { Fail(id, "exact native skill/dash/buffs/body/owned target or bounded geometry guard failed"); return; }
        task.m_duration = (task.m_case == "P0" || task.m_case == "P1" || task.m_case == "C0") ? 10000 : 3000;
        @task.m_cost = task.m_skill.GetCost();
        if (!cal) { task.m_bodyName = body.GetDebugName(); task.m_bodySpot = xy(body.GetPosition()); task.m_world = task.m_bodySpot; }
        if (cal || cancel) { task.m_targetName = target.GetDebugName(); task.m_targetSpot = xy(target.GetPosition()); }
        if (cal) task.m_world = task.m_targetSpot;
        int same = 0;
        task.m_button = SkillButton(player, task.m_skill);
        for (uint i = 0; i < player.m_skills.length(); i++)
            if (player.m_skills[i] !is null && SkillButton(player, player.m_skills[i]) == task.m_button) same++;
        if (task.m_button.isEmpty() || same != 1 || task.BuffLeft(task.m_raising) != -1
            || task.BuffLeft(task.m_devouring) != -1 || task.m_skill.m_cooldownC > 0)
        { Fail(id, "needs unique actual NR spell button, no raising/devouring and naturally ready NR"); return; }
        task.m_expectedWrites = g_inputFrames; g_qaInputSequenceBusy = true; QueuedTasks::Queue(task);
        Emit(Reply(id, true).Str("tag", task.m_tag).Str("case", task.m_case).Int("player", task.m_playerId)
            .Int("body", task.m_bodyId).Int("target", task.m_targetId).Str("button", task.m_button));
    }

    void Register_qa_forgemaster_channel()
    {
        RegisterVerb("forgechannel", "<tag> <P0|P1|P2|P3|C0|C1|CAL> <bodyId> <targetId|-1> <recoverX> <recoverY> <favorPath>", Verb(VerbQAForgeChannel));
    }
}
