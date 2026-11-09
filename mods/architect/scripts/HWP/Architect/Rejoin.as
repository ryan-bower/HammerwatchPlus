// Back into the host's run-start setup (issues #65 and #96). A client that left the setup
// (Back, MissionLoadoutMenu override) or never got it uses the run's entrance again:
//
// - the town's north-exit door (a UseTrigger running the StartMission world script). A
//   client's use reaches the host (UseUnitSecure, Networking/PlayerHandler.as:518) and runs
//   StartMission there with the client's PlayerHusk as the instigator, which vanilla drops
//   (cast<Player> is null, WorldScript/Missions/StartMission.as:28). The StartMission
//   override hands it to EntranceUsedByClient instead.
// - a mission board or portal (MissionShopContent override): the client asks with
//   architect.rejoin.
// - `hwp architect rejoin` from the console.
//
// The host checks that its setup is open and not starting, then sends the client the
// mission and every player's ready state; the client opens its own window, as vanilla's
// OpenMissionLoadoutMenu does (Networking/GameModeHandler.as:65), unless one is already up.
//
//   architect.rejoin       client -> host   {}
//   architect.rejoin_open  host -> peer     { mission, seed, peers: [int], status: [int] }
//   architect.no_setup     host -> peer     {}                   nothing to join
namespace HWP
{
	namespace Architect
	{
		const string REJOIN = "architect.rejoin";
		const string REJOIN_OPEN = "architect.rejoin_open";
		const string NO_SETUP = "architect.no_setup";

		// ---- client ---------------------------------------------------------------

		void RequestRejoin()
		{
			if (Network::IsServer() || OpenLoadoutMenu() !is null)
				return;
			HWP::Log("architect", "asking the host to rejoin its run-start setup");
			HWP::Net::Request(REJOIN, HWP::Net::Empty());
		}

		void OnRejoinOpen(SValue@ data)
		{
			if (Network::IsServer())
				return;
			if (OpenLoadoutMenu() !is null)
			{
				HWP::Log("architect", "rejoin: the run-start setup is already open here");
				return;
			}
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return;

			// the others' ready states: this machine ignored their status messages while it
			// had no window (GameModeHandler::SetMissionLoadoutStatus walks the open windows)
			auto peers = HWP::SV::Ints(data, "peers");
			auto status = HWP::SV::Ints(data, "status");
			int me = Lobby::GetLocalPeer();
			for (uint i = 0; i < peers.length() && i < status.length(); i++)
			{
				if (peers[i] == me)
					continue;
				for (uint j = 0; j < g_players.length(); j++)
				{
					if (g_players[j] !is null && int(g_players[j].peer) == peers[i])
						g_players[j].userdata.set("loadout_status", status[i]);
				}
			}

			MissionManager::SetMission(uint(HWP::SV::Int(data, "mission", 0)), uint(HWP::SV::Int(data, "seed", 0)));
			auto menu = MissionLoadoutMenu(gm.m_guiBuilder);
			gm.m_windowManager.AddWindowObject(menu);
			menu.RefreshReadyTexts();
			HWP::Log("architect", "rejoined the host's run-start setup");
		}

		void OnNoSetup(SValue@ data)
		{
			HWP::Commands::Reply(Resources::GetString(".hwp.architect.no_setup"));
		}

		// ---- host -----------------------------------------------------------------

		void OnRejoin(uint8 peer, SValue@ data)
		{
			HostRejoin(peer, "request");
		}

		// StartMission (override) with a PlayerHusk as the instigator: a client at the door
		void EntranceUsedByClient(UnitPtr unit)
		{
			if (!Network::IsServer() || !unit.IsValid())
				return;
			auto husk = cast<PlayerHusk>(unit.GetScriptBehavior());
			if (husk is null || husk.m_record is null)
				return;
			HostRejoin(uint8(husk.m_record.peer), "entrance");
		}

		bool HostRejoin(uint8 peer, const string &in via)
		{
			if (!Network::IsServer() || int(peer) == Lobby::GetLocalPeer())
				return false;
			if (!Enabled()) // the module off: vanilla, which ignores a client at the door
				return false;
			auto menu = OpenLoadoutMenu();
			if (menu is null || MissionManager::g_module is null || MissionManager::g_module.m_missionDefHash == 0
				|| menu.GetLoadoutStatus() == MissionLoadoutStatus::Started)
			{
				HWP::Log("architect", "rejoin (" + via + ") from " + PayerName(peer) + ": no run-start setup open");
				HWP::Net::Send(peer, NO_SETUP, HWP::Net::Empty());
				return false;
			}

			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("mission", int(MissionManager::g_module.m_missionDefHash));
			b.PushInteger("seed", int(MissionManager::g_module.m_missionRewardSeed));
			b.PushArray("peers");
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i] !is null && g_players[i].peer != 255)
					b.PushInteger(int(g_players[i].peer));
			}
			b.PopArray();
			b.PushArray("status");
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i] !is null && g_players[i].peer != 255)
					b.PushInteger(int(menu.GetLoadoutStatus(g_players[i])));
			}
			b.PopArray();
			b.PopDictionary();
			HWP::Net::Send(peer, REJOIN_OPEN, b.Build());
			HWP::Log("architect", "rejoin (" + via + "): " + PayerName(peer) + " is back in the run-start setup");
			return true;
		}
	}
}
