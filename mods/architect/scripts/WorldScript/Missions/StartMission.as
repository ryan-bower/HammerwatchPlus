// HWP override of scripts/WorldScript/Missions/StartMission.as (mods/architect, "Run-start
// screen" in its README). Every change is marked HWP; pristine copy: StartMission.as.orig
namespace WorldScript
{
	[WorldScript color="255 255 100" icon="system/icons.png;192;288;32;32"]
	class StartMission
	{
		[Editable]
		UnitFeed Instigator;

		[Editable default=""]
		string ID;

		SValue@ ServerExecute()
		{
			auto missionDef = MissionDef::Get(HashString(ID));
			if (missionDef is null)
			{
				PrintError("Mission ID \"" + ID + "\" is invalid.");
				return null;
			}

			// HWP: a client at the door (its UseTrigger runs this on the host with the client's
			// PlayerHusk, which vanilla drops below) rejoins the host's open run-start setup;
			// checked before the host's conditionals, which say nothing about a rejoin
			UnitPtr unit = Instigator.FetchFirst();
			if (unit.IsValid() && cast<Player>(unit.GetScriptBehavior()) is null)
			{
				HWP::Architect::EntranceUsedByClient(unit);
				return null;
			}

			if (!CheckConditionals(missionDef.m_conditionals, GetLocalPlayerRecord().actor)) // Local player?
			{
				PrintError("Mission with ID \"" + ID + "\" did not meet conditionals.");
				return null;
			}

			// HWP: the instigator was fetched and checked above

			MissionManager::SetMission(missionDef.m_id);

			auto gm = cast<BaseGameMode>(g_gameMode);
			gm.m_windowManager.AddWindowObject(MissionLoadoutMenu(gm.m_guiBuilder));

			return null;
		}
	}
}
