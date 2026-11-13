namespace WorldScript
{
	[WorldScript color="255 100 100" icon="system/icons.png;480;256;32;32"]
	class HWPShortcutExit : LevelExitAreaJump
	{
		void TriggerLevelExit() override
		{
			// QoL also ships without the campaign or a matching HoH1 import on every peer.
			// NextLevel treats an unknown id as mission success, so never pass it one.
			auto def = MissionManager::GetCurrentMission();
			if (def is null)
				return;
			if (HWP::HoH1::Enabled())
			{
				for (uint i = 0; i < def.m_levels.length(); i++)
				{
					if (def.m_levels[i].m_id == LevelID)
					{
						MissionManager::NextLevel(LevelID);
						return;
					}
				}
			}
			HWP::HoH1::Warn(Resources::GetString(".hwp.shortcuts.fallback"));
			MissionManager::NextLevel("dark_halls_1");
		}
	}
}
