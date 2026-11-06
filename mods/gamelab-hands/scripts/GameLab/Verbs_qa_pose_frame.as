// Read-only capture prerequisites. Opaque model handles are not pose/visibility proof.
// No optional Firearms namespace dependency: safe for hands without the feature mod.
namespace GameLab
{
    array<Equipment::Equipment@> g_qaPoseItems;
    array<CustomUnitModel@> g_qaPoseModels;
    int g_qaPoseSequence = 0;

    int QAPoseItemToken(Equipment::Equipment@ item)
    {
        if (item is null) return 0;
        for (uint i = 0; i < g_qaPoseItems.length(); i++)
            if (g_qaPoseItems[i] is item) return int(i) + 1;
        if (g_qaPoseItems.length() >= 32) return -1;
        g_qaPoseItems.insertLast(item);
        return int(g_qaPoseItems.length());
    }

    int QAPoseModelToken(CustomUnitModel@ model)
    {
        if (model is null) return 0;
        for (uint i = 0; i < g_qaPoseModels.length(); i++)
            if (g_qaPoseModels[i] is model) return int(i) + 1;
        if (g_qaPoseModels.length() >= 64) return -1;
        g_qaPoseModels.insertLast(model);
        return int(g_qaPoseModels.length());
    }

    string QAPoseHand(Equipment::Equipment@ item)
    {
        auto typed = cast<Equipment::Item>(item);
        Json hand;
        hand.Str("id", typed is null || typed.baseItem is null ? "" : typed.baseItem.m_id)
            .Int("item_token", QAPoseItemToken(item))
            .Int("model_token", QAPoseModelToken(item is null ? null : item.m_modelTmp));
        return hand.Close();
    }

    void VerbQAPoseFrame(const string &in id, array<string>@ args)
    {
        auto player = cast<PlayerBase>(GetLocalPlayer());
        auto record = GetLocalPlayerRecord();
        auto mode = cast<BaseGameMode>(g_gameMode);
        if (args.length() != 1 || args[0].isEmpty() || args[0].length() > 96
            || player is null || record is null || !record.local || record.actor !is player
            || player.IsDead() || !player.m_unit.IsValid() || player.m_unit.IsDestroyed()
            || mode is null || g_players.length() > 16)
        { Fail(id, "needs tag and live sole local actor/record/mode"); return; }
        for (uint i = 0; i < g_players.length(); i++)
            if (g_players[i] !is null && g_players[i] !is record)
            { Fail(id, "needs sole local record"); return; }
        vec3 world = player.m_unit.GetPosition();
        vec2 screen = ToScreenspace(world);
        vec2 direction = player.GetDirection();
        Emit(Reply(id, true).Str("tag", args[0]).Int("sequence", ++g_qaPoseSequence)
            .Int("boots", g_boots).Int("frame", g_frames)
            .Int("now", int(g_scene.GetTime())).Int("player", player.m_unit.GetId())
            .Str("level", GetCurrentLevelFilename()).Str("window", TopWindow())
            .Bool("gameplay_focus", Focus::Has(Focus::GAMEPLAY))
            .Num("x", world.x).Num("y", world.y).Num("z", world.z)
            .Num("look_x", direction.x).Num("look_y", direction.y)
            .Num("screen_x", screen.x).Num("screen_y", screen.y)
            .Num("width", mode.m_wndWidth * mode.m_wndScale).Num("height", mode.m_wndHeight * mode.m_wndScale)
            .Num("scale", mode.m_wndScale).Num("timescale", GetVarFloat("g_timescale"))
            .Num("camera_x", mode.m_camPos.x).Num("camera_y", mode.m_camPos.y)
            .Num("prev_x", mode.m_gameCam.m_prevPos.x).Num("prev_y", mode.m_gameCam.m_prevPos.y)
            .Num("current_x", mode.m_gameCam.m_pos.x).Num("current_y", mode.m_gameCam.m_pos.y)
            .Num("next_x", mode.m_gameCam.m_nextPos.x).Num("next_y", mode.m_gameCam.m_nextPos.y)
            .Num("target_x", mode.m_gameCam.m_target.x).Num("target_y", mode.m_gameCam.m_target.y)
            .Raw("main", QAPoseHand(player.GetEquipment(EquippedItemsSlots::MainHand)))
            .Raw("off", QAPoseHand(player.GetEquipment(EquippedItemsSlots::OffHand)))
            .Str("scope", "read-only current cached model/item handle identities and projection; no visibility, occlusion, pose correctness or rendered-frame assertion"));
    }

    void Register_qa_pose_frame()
    {
        RegisterVerb("qa_poseframe", "<tag>", Verb(VerbQAPoseFrame));
    }
}
