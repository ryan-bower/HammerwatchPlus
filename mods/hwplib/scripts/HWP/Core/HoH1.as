// HWP::HoH1 - the features that use the player's own Heroes of Hammerwatch 1 content.
// HoH1 assets are never shipped: tools/hoh1/import_hoh1.py cuts them from the player's own HoH1
// install and `build.py --with-local` packs them (README, Installing). Without them each
// feature keeps a stand-in (HoH2 themes, placeholder icons), so no package needs HoH1 to run.
// The player is told once which features are on stand-ins:
//
//   HWP::HoH1::Report("pets", imported > 0, ".hwp.pets.hoh1");   // when the mod knows
//
// The key names what the player gets without HoH1. The core module calls Tell on the
// town's TELL_TICK-th gameplay tick, after every mod's self-check: one chat line per save
// for each set of features on stand-ins (the setting hoh1.told). hwp hoh1 lists them all.
// Script globals reset with every level, so the mods report again on each one.
//
// The lobby check (issue #123). A floor or pet made from the import hangs every player whose
// game lacks the same files (game night 10.28.26: the host's Battlements floor hung every client
// on wait_loaded_level). build.py stamps the import (hoh1/hwp_import_stamp.sval, a fingerprint of
// every imported file; absent without the import). Every client sends its stamp to the host on
// each level (REPORT, and again when the host asks), and the host decides for the lobby: HoH1
// floors, the HoH1 tower and HoH1 pets play only when the host setting hoh1.content is on (the
// default), the host has the import and every player's stamp is the host's (Enabled). Until
// every player has answered the answer is no, so a level always starts on the stand-ins and the
// HoH1 content comes back once everyone has reported (the hoh1.lobby notification). The host
// broadcasts the verdict (LOBBY); a client goes by it. A player whose stamp is missing or
// differs is named to everyone in red when they join (WARNED_KEY remembers whom, so a player is
// not named again on every floor), and the features that fall back say so when they do (Warn).
namespace HWP
{
	namespace HoH1
	{
		const int TELL_TICK = 60;
		const string STAMP_FILE = "hoh1/hwp_import_stamp.sval";
		const string REPORT = "hoh1.report";    // client -> host: {who, stamp}
		const string ASK = "hoh1.ask";          // host -> everyone: report again
		const string LOBBY = "hoh1.lobby";      // host -> everyone: {ok, known, why}
		const string WARN = "hoh1.warn";        // host -> everyone: {text}, a red chat line
		const string WARN_REQ = "hoh1.warn_req";  // client -> host: broadcast this warning
		const string NOTIFY = "hoh1.lobby";     // HWP::Commands::NotifySettingChanged key
		const int SILENT_MS = 10000;            // no report this long: an update without the check
		const uint8 FAKE_PEER = 254;            // `hwp hoh1 fake`: a lab stand-in for a second player

		class Feature
		{
			string mod;
			bool present;
			bool imported;   // present before hoh1.content: off only because of the setting
			string key;
		}

		array<Feature@> g_features;

		// ---- this game's import --------------------------------------------------------------

		bool g_stampRead = false;
		string g_stamp;

		// the import's fingerprint, "" without one (a release, or no HoH1 import)
		string Stamp()
		{
			if (!g_stampRead)
			{
				g_stampRead = true;
				g_stamp = HWP::SV::Str(Resources::GetSValue(STAMP_FILE), "stamp", "");
			}
			return g_stamp;
		}

		// the host setting (default on); off forces the stand-ins everywhere
		bool SettingOn() { return HWP::Settings::GetBool("hoh1.content", true); }

		// this machine could show HoH1 content: for what never leaves it (trinket icons) and for
		// the once-per-save stand-in notice; the lobby does not matter there
		bool LocalOn() { return SettingOn() && !Stamp().isEmpty(); }

		// ---- the lobby (host) ----------------------------------------------------------------

		class Peer
		{
			uint8 peer;
			string who;
			string stamp;    // what it reported
			bool heard = false;
			bool silent = false;   // never reported within SILENT_MS
			int waitMs = 0;
		}

		array<Peer@> g_peers;

		Peer@ FindPeer(uint8 peer)
		{
			for (uint i = 0; i < g_peers.length(); i++)
				if (g_peers[i].peer == peer)
					return g_peers[i];
			return null;
		}

		// the lab peer exists only with e_cheats 1: a hoh1.fake left in a real save does nothing
		string Fake() { return GetVarBool("e_cheats") ? HWP::Settings::GetString("hoh1.fake", "") : ""; }

		bool g_synced = false;   // host: SyncPeers ran this level

		// every other player in the game now, and the lab's fake one
		void SyncPeers(int ms)
		{
			g_synced = true;
			array<uint8> live;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].local || g_players[i].peer == 255)
					continue;
				live.insertLast(g_players[i].peer);
				if (FindPeer(g_players[i].peer) is null)
				{
					Peer@ p = Peer();
					p.peer = g_players[i].peer;
					p.who = Lobby::GetPlayerName(g_players[i].peer);
					g_peers.insertLast(p);
				}
			}
			string fake = Fake();
			if (!fake.isEmpty())
			{
				live.insertLast(FAKE_PEER);
				Peer@ f = FindPeer(FAKE_PEER);
				if (f is null)
				{
					@f = Peer();
					f.peer = FAKE_PEER;
					f.who = "Lab peer";
					g_peers.insertLast(f);
				}
				if (fake != "silent")
				{
					f.heard = true;
					f.stamp = fake == "match" ? Stamp() : (fake == "other" ? "0000fake0000" : "");
				}
			}
			for (int i = int(g_peers.length()) - 1; i >= 0; i--)
			{
				auto p = g_peers[i];
				if (live.find(p.peer) < 0)
				{
					g_peers.removeAt(i);
					continue;
				}
				if (p.heard || p.silent)
					continue;
				p.waitMs += ms;
				if (p.waitMs >= SILENT_MS)
				{
					p.silent = true;
					HWP::Log("hoh1", "lobby: no HoH1 report from " + p.who + " in " + (SILENT_MS / 1000) + " s");
				}
			}
		}

		bool Matches(Peer@ p) { return p.heard && !p.silent && p.stamp == Stamp(); }

		// host: every other player has answered (or was given up on)
		bool HostKnown()
		{
			// the lobby's own count first: module constructors run before the PlayerRecords are
			// activated, so g_players can be empty while three friends are loading (PR #127 review)
			if (Lobby::IsInLobby())
			{
				int answered = 0;
				for (uint i = 0; i < g_peers.length(); i++)
					if (g_peers[i].peer != FAKE_PEER && (g_peers[i].heard || g_peers[i].silent))
						answered++;
				if (answered < Lobby::GetLobbyPlayerCount() - 1)
					return false;
			}
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].local || g_players[i].peer == 255)
					continue;
				auto p = FindPeer(g_players[i].peer);
				if (p is null || !(p.heard || p.silent))
					return false;
			}
			for (uint i = 0; i < g_peers.length(); i++)
				if (!(g_peers[i].heard || g_peers[i].silent))
					return false;
			return true;
		}

		// host: HoH1 content may play in this lobby now. Read live, so it is right from the
		// module constructors on: a solo game is yes at once, a co-op one no until all reported.
		bool HostOk()
		{
			if (!SettingOn() || Stamp().isEmpty() || !HostKnown())
				return false;
			for (uint i = 0; i < g_peers.length(); i++)
				if (!Matches(g_peers[i]))
					return false;
			return true;
		}

		// why HoH1 content is off in this lobby, for the warnings ("" when it is on)
		string HostWhy()
		{
			if (!SettingOn())
				return Resources::GetString(".hwp.hoh1.why_off");
			if (Stamp().isEmpty())
				return Resources::GetString(".hwp.hoh1.why_host");
			array<string> parts;
			for (uint i = 0; i < g_peers.length(); i++)
			{
				auto p = g_peers[i];
				if (Matches(p))
					continue;
				string key = p.silent ? ".hwp.hoh1.why_silent" : (!p.heard ? ".hwp.hoh1.why_pending"
					: (p.stamp.isEmpty() ? ".hwp.hoh1.why_none" : ".hwp.hoh1.why_differs"));
				parts.insertLast(Resources::GetString(key, { { "who", p.who } }));
			}
			return join(parts, "; ");
		}

		// ---- the lobby (every machine) -------------------------------------------------------

		bool g_ok = false;       // client: the host's verdict this level
		bool g_known = false;    // client: the host has answered this level
		string g_why;            // client: the host's reason
		bool g_lastOk = false;   // what the hoh1.lobby notification last said
		bool g_lastKnown = false;
		bool g_notified = false;  // this level's first verdict went out
		bool g_sentOk = false;   // host: the verdict last broadcast
		bool g_sentKnown = false;
		string g_sentWhy = "-";
		bool g_started = false;

		// HoH1 floors, the HoH1 tower and HoH1 pets may play: the setting, the import and the lobby
		bool Enabled()
		{
			if (Network::IsServer())
				return HostOk();
			return g_ok && LocalOn();
		}

		// the lobby verdict is final for this level (every player reported, or was given up on).
		// On the host only after the first peer sync of the level: a module that ticks before
		// the core's first Update would otherwise take an empty peer list for a final answer.
		bool Known() { return Network::IsServer() ? g_synced && HostKnown() : g_known; }

		// the fallback warnings' test: this machine has the import and the setting is on, the
		// lobby has answered, and still no HoH1 content (a player lacks or differs). Not on a
		// release build (no import: vanilla, nothing to warn about) nor when the host turned it off.
		bool Lacks() { return SettingOn() && !Stamp().isEmpty() && Known() && !Enabled(); }

		string Why()
		{
			if (Network::IsServer())
				return HostWhy();
			if (!LocalOn() && g_ok)
				return Resources::GetString(".hwp.hoh1.why_you");
			return g_why;
		}

		SValue@ Verdict()
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushBoolean("ok", HostOk());
			b.PushBoolean("known", HostKnown());
			b.PushString("why", HostWhy());
			b.PopDictionary();
			return b.Build();
		}

		// tell every listener (campaign floors, pets) when the verdict changes
		void Changed()
		{
			bool ok = Enabled();
			bool known = Known();
			// the first tick always notifies: what a constructor applied before any peer sync
			// must not stand just because the first verdict matches the initial values
			if (g_notified && ok == g_lastOk && known == g_lastKnown)
				return;
			g_notified = true;
			g_lastOk = ok;
			g_lastKnown = known;
			HWP::Log("hoh1", "lobby: HoH1 content " + (ok ? "on" : "off") + (known ? "" : " (waiting for reports)")
				+ (ok ? "" : ": " + Why()));
			HWP::Commands::NotifySettingChanged(NOTIFY);
		}

		SValue@ ReportPayload()
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("who", Lobby::GetPlayerName(uint8(Lobby::GetLocalPeer())));
			b.PushString("stamp", Stamp());
			b.PopDictionary();
			return b.Build();
		}

		void OnReport(uint8 peer, SValue@ data)
		{
			if (!Network::IsServer() || peer == uint8(Lobby::GetLocalPeer()))
				return;
			auto p = FindPeer(peer);
			if (p is null)
			{
				@p = Peer();
				p.peer = peer;
				g_peers.insertLast(p);
			}
			p.who = HWP::SV::Str(data, "who", "player " + (int(peer) + 1));
			p.stamp = HWP::SV::Str(data, "stamp", "");
			p.heard = true;
			p.silent = false;
			HWP::Log("hoh1", "lobby: " + p.who + " reports HoH1 import " + (p.stamp.isEmpty() ? "none" : p.stamp)
				+ (p.stamp == Stamp() ? " (same as mine)" : " (mine: " + (Stamp().isEmpty() ? "none" : Stamp()) + ")"));
			// the verdict for this player even when it did not change (a client on a new level)
			HWP::Net::Send(peer, LOBBY, Verdict());
		}

		void OnAsk(SValue@ data)
		{
			if (!Network::IsServer())
				HWP::Net::Request(REPORT, ReportPayload());
		}

		void OnLobby(SValue@ data)
		{
			if (Network::IsServer())
				return;
			g_ok = HWP::SV::Bool(data, "ok", false);
			g_known = HWP::SV::Bool(data, "known", false);
			g_why = HWP::SV::Str(data, "why", "");
			Changed();
		}

		// A red chat line on every machine. From a client the host broadcasts it.
		void Warn(const string &in text)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("text", text);
			b.PopDictionary();
			if (Network::IsServer())
				HWP::Net::Broadcast(WARN, b.Build());
			else
				HWP::Net::Request(WARN_REQ, b.Build());
		}

		void OnWarnReq(uint8 peer, SValue@ data)
		{
			if (!Network::IsServer())
				return;
			string text = HWP::SV::Str(data, "text", "");
			if (!text.isEmpty())
				Warn(text);
		}

		void OnWarn(SValue@ data)
		{
			string text = HWP::SV::Str(data, "text", "");
			if (text.isEmpty())
				return;
			HWP::Log("hoh1", "warning: " + HWP::Commands::Plain(text));
			HWP::Commands::Reply("\\cff6060" + text + "\\d");
		}

		// host: name every player without a matching import once, when they join (the saved
		// list hoh1.warned); a player who leaves, or now matches, is named again next time
		void WarnJoins()
		{
			if (!SettingOn() || Stamp().isEmpty() || !HWP::Settings::CanSave())
				return;
			auto warned = HWP::Settings::GetString("hoh1.warned", "").split("\n");
			array<string> keep;
			bool changed = false;
			for (uint i = 0; i < g_peers.length(); i++)
			{
				auto p = g_peers[i];
				if (!(p.heard || p.silent) || Matches(p))
					continue;
				keep.insertLast(p.who);
				if (warned.find(p.who) >= 0)
					continue;
				changed = true;
				string key = p.silent ? ".hwp.hoh1.why_silent" : (p.stamp.isEmpty() ? ".hwp.hoh1.why_none" : ".hwp.hoh1.why_differs");
				Warn(Resources::GetString(".hwp.hoh1.join", { { "why", Resources::GetString(key, { { "who", p.who } }) } }));
			}
			// a name not in the lobby any more, or matching now: forget it (only once every
			// player has answered, so a level's first ticks don't forget everyone). Until then
			// the names just warned are added, so the warning goes out once, not every tick.
			if (!HostKnown())
			{
				if (changed)
				{
					for (uint i = 0; i < keep.length(); i++)
						if (warned.find(keep[i]) < 0)
							warned.insertLast(keep[i]);
					HWP::Settings::SetString("hoh1.warned", join(warned, "\n"));
				}
				return;
			}
			for (uint i = 0; i < warned.length(); i++)
				if (!warned[i].isEmpty() && keep.find(warned[i]) < 0)
					changed = true;
			if (changed)
				HWP::Settings::SetString("hoh1.warned", join(keep, "\n"));
		}

		// every gameplay tick, town and dungeon (CoreModule)
		void Update(int ms)
		{
			if (!g_started)
			{
				g_started = true;
				// first tick: the connection is up. A client reports; the host asks everyone,
				// in case a client's report went out before this level's host was listening.
				if (Network::IsServer())
					HWP::Net::Broadcast(ASK, HWP::Net::Empty());
				else
					HWP::Net::Request(REPORT, ReportPayload());
			}
			if (Network::IsServer())
			{
				SyncPeers(ms);
				bool ok = HostOk();
				bool known = HostKnown();
				string why = HostWhy();
				if (ok != g_sentOk || known != g_sentKnown || why != g_sentWhy)
				{
					g_sentOk = ok;
					g_sentKnown = known;
					g_sentWhy = why;
					if (g_peers.length() > 0)
						HWP::Net::Broadcast(LOBBY, Verdict());
				}
				WarnJoins();
			}
			Changed();
		}

		void RegisterLobby()
		{
			HWP::Net::OnRequest(REPORT, HWP::Net::RequestHandler(OnReport));
			HWP::Net::OnRequest(WARN_REQ, HWP::Net::RequestHandler(OnWarnReq));
			HWP::Net::OnEvent(ASK, HWP::Net::EventHandler(OnAsk));
			HWP::Net::OnEvent(LOBBY, HWP::Net::EventHandler(OnLobby));
			HWP::Net::OnEvent(WARN, HWP::Net::EventHandler(OnWarn));
		}

		// ---- the stand-in notice -------------------------------------------------------------

		void Report(const string &in mod, bool present, const string &in key)
		{
			bool imported = present;
			// the setting and this game's import only: the lobby has its own warnings, and a
			// co-op level reports before every player has answered
			present = present && LocalOn();
			for (uint i = 0; i < g_features.length(); i++)
			{
				if (g_features[i].mod == mod)
				{
					g_features[i].present = present;
					g_features[i].imported = imported;
					g_features[i].key = key;
					return;
				}
			}
			Feature@ f = Feature();
			f.mod = mod;
			f.present = present;
			f.imported = imported;
			f.key = key;
			g_features.insertLast(f);
		}

		// the mods on stand-ins, sorted: what hoh1.told remembers
		array<string>@ Missing()
		{
			array<string> ids;
			for (uint i = 0; i < g_features.length(); i++)
			{
				if (!g_features[i].present)
					ids.insertLast(g_features[i].mod);
			}
			ids.sortAsc();
			return ids;
		}

		string Phrase(const string &in mod)
		{
			for (uint i = 0; i < g_features.length(); i++)
				if (g_features[i].mod == mod)
					return Resources::GetString(g_features[i].key);
			return mod;
		}

		void Tell()
		{
			auto ids = Missing();
			auto told = join(ids, ",");
			if (HWP::Settings::GetString("hoh1.told", "") == told)
				return;
			// "" when nothing is on stand-ins, so the same set later is told again
			HWP::Settings::SetString("hoh1.told", told);
			if (ids.length() == 0)
				return;
			array<string> phrases;
			bool off = true;   // every one imported, off by the setting: say how to turn it on
			for (uint i = 0; i < ids.length(); i++)
			{
				phrases.insertLast(Phrase(ids[i]));
				for (uint j = 0; j < g_features.length(); j++)
					if (g_features[j].mod == ids[i] && !g_features[j].imported)
						off = false;
			}
			HWP::Log("hoh1", "on stand-ins: " + told);
			HWP::Commands::Reply(Resources::GetString(off ? ".hwp.hoh1.off" : ".hwp.hoh1.missing", { { "list", join(phrases, "; ") } }));
		}

		// `hwp hoh1 [fake none|other|match|silent|clear]`
		void CmdHoH1(array<string>@ args)
		{
			if (args.length() >= 2 && args[0] == "fake")
			{
				if (!Network::IsServer() || !GetVarBool("e_cheats"))
				{
					HWP::Commands::Reply("hoh1 fake: host only, and needs e_cheats 1 (a lab tool)");
					return;
				}
				string what = args[1];
				if (what != "none" && what != "other" && what != "match" && what != "silent" && what != "clear")
				{
					HWP::Commands::Reply("usage: hwp hoh1 fake none|other|match|silent|clear");
					return;
				}
				// saved, so the lab's stand-in player is there on the next floor too
				HWP::Settings::SetString("hoh1.fake", what == "clear" ? "" : what);
				auto p = FindPeer(FAKE_PEER);
				if (p !is null)
					g_peers.removeAt(g_peers.findByRef(p));
				HWP::Commands::Reply("hoh1 fake: " + (what == "clear" ? "off" : "a lab peer whose import is " + what));
				return;
			}
			HWP::Commands::Reply("hoh1.content: " + (SettingOn() ? "on" : "off") + ", import " + (Stamp().isEmpty() ? "none" : Stamp())
				+ ", lobby " + (Enabled() ? "on" : "off") + (Known() ? "" : " (waiting for reports)")
				+ (Enabled() ? "" : ": " + Why()));
			if (Network::IsServer())
			{
				for (uint i = 0; i < g_peers.length(); i++)
				{
					auto p = g_peers[i];
					HWP::Commands::Reply("  " + p.who + ": " + (p.silent ? "no report" : (!p.heard ? "waiting"
						: (p.stamp.isEmpty() ? "no import" : p.stamp))) + (Matches(p) ? " (match)" : ""));
				}
			}
			if (g_features.length() == 0)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.hoh1.none"));
				return;
			}
			for (uint i = 0; i < g_features.length(); i++)
			{
				auto f = g_features[i];
				HWP::Commands::Reply(f.mod + ": " + (f.present ? Resources::GetString(".hwp.hoh1.present")
					: Resources::GetString(f.key)));
			}
		}

		void Init()
		{
			HWP::Commands::Register("hoh1", " the features that use Heroes of Hammerwatch 1 content, whether it is installed and whether this lobby plays it; 'fake none|other|match|silent|clear' (host, lab) adds a stand-in player with that import",
				HWP::Commands::Handler(CmdHoH1));
			RegisterLobby();
		}
	}
}
