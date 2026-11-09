// Last-run statistics for the whole party.
//
// The snapshot is taken in the module constructor: modules are rebuilt inside
// the town game mode's constructor, before PostStart shows the MissionEndMenu
// whose constructor resets PlayerRecord.statsRun. (Module::Load is no good: the
// engine skips it whenever the level starts without a save.) Each machine
// snapshots its own player, keeps it in the player record (HWP data bag, key
// "laststats.mine") and reports it to the host, which rebroadcasts every
// snapshot it knows; the notice board in town pages through them.
// Setting laststats.enabled (host): off, the host places no board (and takes away
// one that stands); snapshots are still taken and kept, so the board has the last
// run when it is turned back on.
//
// Winner winner chicken dinner (issue #96): a run that ends Succeeded (the last floor's
// exit: MissionModule.NextLevel finds no next level and calls AbortMission(Succeeded),
// which every machine gets as SetMissionState before the town loads) shows a big banner
// to every player once they are back in town. The same PlayerRecordLoad hook sees it (the
// state is gone by Start, see above); each machine checks its own local player, so the
// whole party gets it without a message of ours. The banner waits until the run's summary
// window (MissionEndMenu) is closed, then shows the hwp_winner announce
// (tweak/hwp/announce_laststats.sval) and a chat line. The Wave Arena is left out: its
// champion's exit portal ends it Succeeded too, but the arena has no win. Setting
// laststats.winner (local, on).
namespace HWP
{
	namespace LastStats
	{
		const string KEY_MINE = "laststats.mine";
		const string REPORT = "laststats.report"; // client -> host: one snapshot
		const string SYNC = "laststats.sync";     // host -> all: every snapshot
		const string BOARD_UNIT = "doodads/hwp/laststats_board.unit";

		array<SValue@> g_party; // newest first, one per player name

		bool Enabled() { return HWP::Settings::GetBool("laststats.enabled", true); }

		string StateName(int state)
		{
			if (state == int(MissionManager::MissionState::Succeeded))
				return Resources::GetString(".hwp.laststats.state.succeeded");
			if (state == int(MissionManager::MissionState::Failed))
				return Resources::GetString(".hwp.laststats.state.failed");
			if (state == int(MissionManager::MissionState::Aborted))
				return Resources::GetString(".hwp.laststats.state.aborted");
			return Resources::GetString(".hwp.laststats.state.unknown");
		}

		bool IsFinishedState(MissionManager::MissionState st)
		{
			return st == MissionManager::MissionState::Succeeded
				|| st == MissionManager::MissionState::Failed
				|| st == MissionManager::MissionState::Aborted;
		}

		string MissionName(uint missionHash)
		{
			string name = "?";
			auto def = MissionDef::Get(missionHash);
			if (def !is null)
				name = def.m_name;
			if (name.findFirst(".") == 0)
				name = Resources::GetString(name);
			return name;
		}

		// ---- winner winner chicken dinner ---------------------------------------

		const string WIN_STYLE = "hwp_winner";
		const int WIN_DELAY_MS = 600; // after the summary window closes
		// the mission the local player just won (PlayerRecordLoad, town only); empty: none
		string g_winMission;
		bool g_winStyleLogged = false;

		bool WinnerOn() { return Enabled() && HWP::Settings::GetBool("laststats.winner", true); }

		// a finished run that counts as a win: Succeeded, and not the Wave Arena (wavemode's
		// survival mission, which its champion's exit portal ends Succeeded too)
		bool IsWin(PlayerRecord@ rec)
		{
			if (rec is null || rec.currMissionState != MissionManager::MissionState::Succeeded)
				return false;
			auto def = MissionDef::Get(rec.currMission);
			if (def is null)
				return false;
			return def.m_id != "hwp_wave_arena";
		}

		// true while the run's summary window (vanilla MissionEndMenu) is open
		bool SummaryOpen()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return false;
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
			{
				if (cast<MissionEndMenu>(gm.m_windowManager.m_objects[i]) !is null)
					return true;
			}
			return false;
		}

		// the banner and the chat line, on this machine
		bool ShowWinner(const string &in mission)
		{
			auto hud = GetHUD();
			if (hud is null)
				return false;
			string title = Resources::GetString(".hwp.laststats.winner");
			string sub = Resources::GetString(".hwp.laststats.winner.sub", { { "mission", mission } });
			if (HUDAnnounceStyle::Get(WIN_STYLE) !is null)
				hud.AddAnnounce(title, sub, WIN_STYLE);
			else
			{
				// the style sval did not load: the floor-name banner is the closest vanilla look
				if (!g_winStyleLogged)
				{
					g_winStyleLogged = true;
					HWP::LogError("laststats", "announce style " + WIN_STYLE + " missing (tweak/hwp/announce_laststats.sval); using region_enter");
				}
				hud.AddAnnounce(title, sub, "region_enter");
			}
			SValueBuilder b;
			b.PushString("\\cffd700" + title + "\\d " + sub);
			SendSystemMessage("AddChat", b.Build());
			HWP::Log("laststats", "winner banner: " + mission);
			return true;
		}

		// ---- snapshot ---------------------------------------------------------

		// Same selection as MissionEndMenu: every visible, categorised stat that
		// is not zero. Lines are stored pre-formatted so the receiver needs no
		// StatDef lookup. Per-skill damage lines need the player actor, which
		// does not exist yet at Load time, so they are not part of the snapshot.
		SValue@ Snapshot(PlayerRecord@ plr)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("player", plr.GetName());
			b.PushInteger("peer", plr.peer);

			b.PushString("mission", MissionName(plr.currMission));
			b.PushInteger("state", int(plr.currMissionState));

			int n = 0;
			b.PushArray("lines");
			for (uint i = 0; i < Stats::StatDef::Instances.length(); i++)
			{
				auto stat = Stats::StatDef::Instances[i];
				if (stat.m_hidden || stat.m_category.isEmpty())
					continue;
				auto val = plr.statsRun.GetStatCurr(stat.m_idHash);
				if (val == 0)
					continue;

				b.PushDictionary();
				b.PushString("cat", stat.m_category);
				b.PushString("title", Resources::GetString(stat.m_name));
				b.PushString("text", stat.GetStatFormatted(val));
				b.PushInteger("value", int(val)); // the board's bars scale on this (2026-10-25)
				b.PopDictionary();
				n++;
			}
			b.PopArray();
			b.PushInteger("count", n);
			b.PopDictionary();
			return b.Build();
		}

		// The run's snapshot, taken when the town loads the local character
		// (PlayerRecordLoad) and kept until Start: the town's MissionEndMenu
		// (PostStart) clears the run's state and stats before any HWP Start
		// runs, and the module constructors run before the record is loaded.
		SValue@ g_pending;

		void OnRecordLoad(PlayerRecord@ rec)
		{
			if (rec is null || !rec.local)
				return;
			if (IsWin(rec))
				g_winMission = MissionName(rec.currMission);
			if (rec.statsRun is null || !IsFinishedState(rec.currMissionState))
				return;
			if (g_pending !is null)
				g_pending.Delete();
			@g_pending = Snapshot(rec);
		}

		SValue@ Mine()
		{
			return HWP::SaveData::Local().Get(KEY_MINE);
		}

		// ---- party list -------------------------------------------------------

		void Remember(SValue@ snap)
		{
			if (snap is null)
				return;
			auto name = HWP::SV::Str(snap, "player");
			for (int i = int(g_party.length()) - 1; i >= 0; i--)
			{
				if (HWP::SV::Str(g_party[i], "player") == name)
					g_party.removeAt(i);
			}
			g_party.insertAt(0, snap.Copy()); // snap may be a received message, freed after the handler
		}

		SValue@ PackParty()
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("count", int(g_party.length()));
			for (uint i = 0; i < g_party.length(); i++)
				b.PushSimple("" + i, g_party[i].Copy());
			b.PopDictionary();
			return b.Build();
		}

		// host: a peer reported its snapshot
		void OnReport(uint8 peer, SValue@ data)
		{
			if (data is null)
				return;
			Remember(data);
			HWP::Log("laststats", "got snapshot of " + HWP::SV::Str(data, "player") + " from peer " + peer
				+ " (" + HWP::SV::Int(data, "count") + " stats); party size " + g_party.length());
			HWP::Net::Broadcast(SYNC, PackParty());
		}

		// everyone: the host's full list
		void OnSync(SValue@ data)
		{
			int count = HWP::SV::Int(data, "count");
			array<SValue@> list;
			for (int i = 0; i < count; i++)
			{
				auto snap = HWP::SV::Field(data, "" + i);
				if (snap !is null)
					list.insertLast(snap.Copy());
			}
			g_party = list;
		}

		// ---- notice board -----------------------------------------------------

		// Next to the fountain of town_square_4 (prefab at grid -38,8 -> world
		// -608,128; the well sits at local offset 104,16). Overridable with
		// "hwp set laststats.board_x <n>" / board_y while the spot is tuned.
		vec3 BoardPos()
		{
			return vec3(float(HWP::Settings::GetInt("laststats.board_x", -440)),
				float(HWP::Settings::GetInt("laststats.board_y", 110)), 0.0f);
		}

		UnitPtr SpawnBoard()
		{
			auto prod = Resources::GetUnitProducer(BOARD_UNIT);
			if (prod is null)
			{
				HWP::LogError("laststats", "missing " + BOARD_UNIT);
				return UnitPtr();
			}
			auto pos = BoardPos();
			UnitPtr u = prod.Produce(g_scene, pos);
			HWP::Log("laststats", "spawned the notice board at " + pos.x + "," + pos.y);
			return u;
		}

		// hwp laststats sample [n]: n (2) made-up snapshots ("Sample 1".. and the local
		// player's name first) over the first visible stats, deterministic values, so the
		// board can be looked at without a run. In memory only (not the bag); the host
		// syncs them to the party like real reports. A test aid.
		void Sample(int count)
		{
			if (count < 1)
				count = 1;
			if (count > 4)
				count = 4;
			auto local = GetLocalPlayerRecord();
			for (int k = 0; k < count; k++)
			{
				SValueBuilder b;
				b.PushDictionary();
				string name = (k == 0 && local !is null) ? local.GetName() : ("Sample " + (k + 1));
				b.PushString("player", name);
				b.PushInteger("peer", k);
				b.PushString("mission", "Sample run");
				b.PushInteger("state", int(MissionManager::MissionState::Failed));
				int n = 0;
				b.PushArray("lines");
				for (uint i = 0; i < Stats::StatDef::Instances.length() && n < 24; i++)
				{
					auto stat = Stats::StatDef::Instances[i];
					if (stat.m_hidden || stat.m_category.isEmpty())
						continue;
					// a different spread per player; the 2nd player skips every 5th stat
					if (k > 0 && (n % 5) == 4 && k == 1)
					{
						n++;
						continue;
					}
					int val = 100 + 37 * n + 251 * k * (1 + (n % 3));
					b.PushDictionary();
					b.PushString("cat", stat.m_category);
					b.PushString("title", Resources::GetString(stat.m_name));
					b.PushString("text", stat.GetStatFormatted(val));
					b.PushInteger("value", val);
					b.PopDictionary();
					n++;
				}
				b.PopArray();
				b.PushInteger("count", n);
				b.PopDictionary();
				auto snap = b.Build();
				Remember(snap);
				snap.Delete(); // Remember keeps a copy
			}
			HWP::Log("laststats", "sample: " + count + " snapshots, party size " + g_party.length());
			if (Network::IsServer())
				HWP::Net::Broadcast(SYNC, PackParty());
		}

		void CmdLastStats(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "sample")
			{
				Sample(args.length() > 1 ? int(parseInt(args[1])) : 2);
				HWP::Commands::Reply("laststats: " + g_party.length() + " snapshots on the board");
				return;
			}
			if (args.length() > 0 && args[0] == "winner")
			{
				// test aid: the win banner now, as after a won run (ignores laststats.winner)
				bool shown = ShowWinner(MissionName(MissionManager::g_module.m_missionDefHash));
				HWP::Commands::Reply(shown ? "laststats: winner banner shown" : "laststats: no HUD");
				return;
			}
			if (args.length() > 0 && args[0] == "board")
			{
				string status = g_openMenu is null ? "board closed" : g_openMenu.Status();
				HWP::Log("laststats", status);
				HWP::Commands::Reply(status);
				return;
			}
			auto mine = Mine();
			if (mine is null)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.laststats.empty"));
				return;
			}
			HWP::Commands::Reply(HWP::SV::Str(mine, "mission") + " - " + StateName(HWP::SV::Int(mine, "state"))
				+ ": " + HWP::SV::Int(mine, "count") + " stats; party snapshots known: " + g_party.length());
		}
	}
}

namespace Modules
{
	class HWPLastStatsModule : Module, HWP::ModuleStart
	{
		int m_reportDelay = -1;
		int m_winDelay = -1; // >= 0: the win banner is due (counts down once the summary is closed)
		// false: the town starts with a null save, so Load never runs there and the
		// board must spawn from the constructor's state (docs/RE_NOTES.md, mod lifecycle)
		bool m_boardDone = false;
		int m_boardDelay = 0;
		HWP::Town::Kept m_board;

		HWPLastStatsModule()
		{
			super("hwp-laststats");
			HWP::Net::OnRequest(HWP::LastStats::REPORT, HWP::Net::RequestHandler(HWP::LastStats::OnReport));
			HWP::Net::OnEvent(HWP::LastStats::SYNC, HWP::Net::EventHandler(HWP::LastStats::OnSync));
			HWP::Commands::Register("laststats", " [sample [n] | board | winner]: what the notice board knows; sample makes test snapshots, board logs the open window, winner shows the win banner", HWP::Commands::Handler(HWP::LastStats::CmdLastStats));
			TakeSnapshot();
		}

		void Start(StartMode sMode)
		{
			// the constructor runs before the town's player records are loaded, so
			// the PlayerRecordLoad hook's snapshot is only waiting by now
			TakeSnapshot();
			m_boardDone = false;
			m_boardDelay = 0;
			m_board.Reset();
			m_reportDelay = 2000; // (re)send whatever we have so late joiners get it too
			// a won run: the banner once the summary window is closed (town only; the
			// mission state is the one the town loaded the character with)
			m_winDelay = -1;
			if (!g_inTown)
				HWP::LastStats::g_winMission = "";
			else if (!HWP::LastStats::g_winMission.isEmpty())
			{
				m_winDelay = HWP::LastStats::WIN_DELAY_MS;
				HWP::Log("laststats", "won " + HWP::LastStats::g_winMission + ": banner after the summary");
			}
		}

		// Stores the run's snapshot. The town's MissionEndMenu clears the finished
		// mission state before Start, so the PlayerRecordLoad hook takes the
		// snapshot (g_pending). The state check is the fallback for a record that
		// is already loaded when the module is built.
		void TakeSnapshot()
		{
			auto plr = GetLocalPlayerRecord();
			if (plr is null || plr.statsRun is null)
				return;
			SValue@ snap = HWP::LastStats::g_pending;
			@HWP::LastStats::g_pending = null;
			if (snap is null)
			{
				if (!HWP::LastStats::IsFinishedState(plr.currMissionState))
					return;
				@snap = HWP::LastStats::Snapshot(plr);
			}

			string desc = HWP::SV::Str(snap, "mission") + ": " + HWP::SV::Int(snap, "count")
				+ " stats, " + HWP::LastStats::StateName(HWP::SV::Int(snap, "state"));
			HWP::SaveData::Local().Set(HWP::LastStats::KEY_MINE, snap);
			HWP::LastStats::Remember(snap);
			snap.Delete(); // the bag and the party list keep copies
			HWP::Log("laststats", "snapshot of " + plr.GetName() + ", " + desc);
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("laststats", "HWPLastStatsModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			if (m_reportDelay >= 0)
			{
				m_reportDelay -= ms;
				if (m_reportDelay < 0)
				{
					m_reportDelay = -1;
					auto mine = HWP::LastStats::Mine();
					if (mine !is null)
						HWP::Net::Request(HWP::LastStats::REPORT, mine.Copy()); // the bag keeps its own
				}
			}

			if (m_winDelay >= 0)
			{
				if (HWP::LastStats::SummaryOpen())
					m_winDelay = HWP::LastStats::WIN_DELAY_MS;
				else
				{
					m_winDelay -= ms;
					if (m_winDelay < 0)
					{
						m_winDelay = -1;
						string mission = HWP::LastStats::g_winMission;
						HWP::LastStats::g_winMission = "";
						if (HWP::LastStats::WinnerOn())
							HWP::LastStats::ShowWinner(mission);
						else
							HWP::Log("laststats", "won " + mission + ": banner off (laststats.winner / laststats.enabled)");
					}
				}
			}

			if (!HWP::LastStats::Enabled())
			{
				// turned off: the host takes the board away; on again, Due below brings it back
				if (Network::IsServer() && m_board.m_unit.IsValid() && !m_board.m_unit.IsDestroyed())
				{
					m_board.m_unit.Destroy();
					HWP::Log("laststats", "off: removed the notice board");
				}
				m_board.Reset();
				m_boardDone = true;
				return;
			}

			if (!m_boardDone)
			{
				m_boardDelay += ms;
				if (m_boardDelay >= 500)
				{
					m_boardDone = true;
					if (g_inTown && Network::IsServer())
						m_board.Set(HWP::LastStats::SpawnBoard());
				}
			}
			else if (m_board.Due(ms)) // a building upgrade reloaded the town, or the board was turned back on
				m_board.Set(HWP::LastStats::SpawnBoard());
		}
	}
}

namespace HWPLastStats
{
	[Hook]
	void PlayerRecordLoad(PlayerRecord@ record, SValue@ data)
	{
		HWP::LastStats::OnRecordLoad(record);
	}
}
