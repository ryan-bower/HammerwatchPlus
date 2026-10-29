// HWP::Builds - which HammerwatchPlus update each package is, and telling players when the
// updates differ (issue #24).
//
// tools/build.py stamps every package with its update: the last commit's date and short hash,
// with "+" for a local build with uncommitted changes. The package's generated check module
// calls Package with it at boot. From that:
// - Packages of different updates enabled in one game: Tell names each odd package's update next
//   to the running library's, on every town visit. It also covers packages built before update
//   stamps, which only call Packages::Mismatch.
// - Players running different updates in one lobby: the game's own mod check compares mod ids,
//   not what is in them, so they get in. A client arriving in town sends its updates to the host
//   (Report), the host answers with its own (OnReport), and each side is told which packages
//   differ and whose are older. A host that never answers, or a client that never reports, runs
//   an update from before these reports and is named as older.
//
// Packages of other updates call Package: never rename it or change its signature. This file
// can come from a newer package than the rest of the library (the game keeps the first copy of
// each path, and older packages don't have this one), so it uses only what every published
// library has.
namespace HWP
{
	namespace Builds
	{
		const string REPORT = "builds.report";  // client -> host: the client's packages
		const string ANSWER = "builds.answer";  // host -> that client: the host's
		const int SILENT_MS = 45000;            // in town this long without one: an older update

		class Pack
		{
			string name;    // HWP-qol
			string update;  // "2026-10-29 1a2b3c4"
			string stamp;   // the library it was built with
			Pack(const string &in n, const string &in u, const string &in s) { name = n; update = u; stamp = s; }
		}

		array<Pack@> g_packs;
		string g_loadedStamp;

		// every package's check module (tools/build.py stamp_entries), at boot and every level
		void Package(const string &in name, const string &in update, const string &in stamp, const string &in loadedStamp)
		{
			g_loadedStamp = loadedStamp;
			for (uint i = 0; i < g_packs.length(); i++)
			{
				if (g_packs[i].name == name)
				{
					g_packs[i].update = update;
					g_packs[i].stamp = stamp;
					return;
				}
			}
			g_packs.insertLast(Pack(name, update, stamp));
		}

		// The running library's update: that of a package built with it. "" when it came from a
		// package from before update stamps, or there are no packages (unpacked).
		string Library()
		{
			for (uint i = 0; i < g_packs.length(); i++)
				if (g_packs[i].stamp == g_loadedStamp)
					return g_packs[i].update;
			return "";
		}

		// this game's update, for the player: the library's, or "unpacked"
		string Mine()
		{
			if (g_packs.length() == 0)
				return Resources::GetString(".hwp.builds.unpacked");
			return Show(Library());
		}

		// "2026-10-29 1a2b3c4" -> "2026-10-29 (1a2b3c4)"
		string Show(const string &in update)
		{
			if (update == "")
				return Resources::GetString(".hwp.builds.unstamped");
			int sp = update.findFirst(" ");
			if (sp < 0)
				return update;
			return update.substr(0, sp) + " (" + update.substr(sp + 1) + ")";
		}

		// by date: -1 a is older, 1 newer, 0 the same day; "" (before stamps) is older than any
		int Compare(const string &in a, const string &in b)
		{
			if (a == b)
				return 0;
			if (a == "")
				return -1;
			if (b == "")
				return 1;
			string da = a.substr(0, 10);
			string db = b.substr(0, 10);
			if (da < db)
				return -1;
			if (da > db)
				return 1;
			return 0;
		}

		string Relation(const string &in a, const string &in b)
		{
			int c = Compare(a, b);
			return Resources::GetString(c < 0 ? ".hwp.builds.older" : (c > 0 ? ".hwp.builds.newer" : ".hwp.builds.sameday"));
		}

		// the newest update among these packages ("" when none is stamped)
		string Newest(array<string>@ updates)
		{
			string best;
			for (uint i = 0; i < updates.length(); i++)
				if (Compare(updates[i], best) > 0)
					best = updates[i];
			return best;
		}

		// "update 2026-10-29 (1a2b3c4): HWP-qol, HWP-keys" for every update the packages are from, the
		// running library's first
		string Summary()
		{
			if (g_packs.length() == 0)
				return Resources::GetString(".hwp.builds.unpacked");
			array<string> updates;
			array<string> names;
			for (uint i = 0; i < g_packs.length(); i++)
			{
				int at = updates.find(g_packs[i].update);
				if (at < 0)
				{
					updates.insertLast(g_packs[i].update);
					names.insertLast(g_packs[i].name);
				}
				else
					names[at] += ", " + g_packs[i].name;
			}
			// the running library's update first
			int lib = updates.find(Library());
			if (lib > 0)
			{
				updates.insertAt(0, updates[lib]);
				names.insertAt(0, names[lib]);
				updates.removeAt(lib + 1);
				names.removeAt(lib + 1);
			}
			array<string> parts;
			for (uint i = 0; i < updates.length(); i++)
				parts.insertLast(Resources::GetString(".hwp.builds.summary", { { "update", Show(updates[i]) }, { "list", names[i] } }));
			return join(parts, "; ");
		}

		// Packages of different updates in this game: the odd ones and the running library's update.
		void Tell()
		{
			string lib = Library();
			array<string> parts;
			for (uint i = 0; i < g_packs.length(); i++)
			{
				if (g_packs[i].stamp == g_loadedStamp)
					continue;
				parts.insertLast(g_packs[i].name + " " + Show(g_packs[i].update) + ", " + Relation(g_packs[i].update, lib));
			}
			// packages from before update stamps only call Packages::Mismatch
			for (uint i = 0; i < HWP::Packages::g_mismatched.length(); i++)
			{
				string name = HWP::Packages::g_mismatched[i];
				if (Find(name) is null)
					parts.insertLast(name + " " + Show("") + ", " + Relation("", lib));
			}
			if (parts.length() == 0)
				return;
			string text = Resources::GetString(".hwp.builds.mixed", { { "library", Show(lib) }, { "list", join(parts, "; ") } });
			HWP::Log("core", "mixed updates: " + join(parts, "; ") + "; library " + Show(lib));
			HWP::Commands::Reply(text);
		}

		Pack@ Find(const string &in name)
		{
			for (uint i = 0; i < g_packs.length(); i++)
				if (g_packs[i].name == name)
					return g_packs[i];
			return null;
		}

		// ---- between players --------------------------------------------------------------

		// "HWP-qol=2026-10-29 1a2b3c4\nHWP-keys=..."
		string Packed()
		{
			array<string> lines;
			for (uint i = 0; i < g_packs.length(); i++)
				lines.insertLast(g_packs[i].name + "=" + g_packs[i].update);
			return join(lines, "\n");
		}

		SValue@ Payload()
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("who", Lobby::GetPlayerName(uint8(Lobby::GetLocalPeer())));
			b.PushString("packs", Packed());
			b.PopDictionary();
			return b.Build();
		}

		// `hwp builds fake <name>=<update>`: read every received report and answer as if the other
		// side ran that, so one lab game can stand in for two; `fake silent`: ignore them (an
		// older update that never reports); `fake clear`.
		array<string> g_fake;
		bool g_fakeSilent = false;

		dictionary@ Unpack(const string &in packed)
		{
			dictionary d;
			auto lines = packed.split("\n");
			for (uint i = 0; i < lines.length(); i++)
			{
				int eq = lines[i].findFirst("=");
				if (eq > 0)
					d.set(lines[i].substr(0, eq), lines[i].substr(eq + 1));
			}
			for (uint i = 0; i < g_fake.length(); i++)
			{
				int eq = g_fake[i].findFirst("=");
				d.set(g_fake[i].substr(0, eq), g_fake[i].substr(eq + 1));
			}
			return d;
		}

		// What differs between my packages and theirs, grouped by the two updates: "HWP-qol,
		// HWP-keys: yours 2026-10-29 (1a2b3c4), theirs 2026-10-20 (0f0f0f0)". Empty when the same.
		string Differences(dictionary@ theirs, string &out mineNewest, string &out theirsNewest)
		{
			array<string> mineUpdates;
			array<string> theirUpdates;
			array<string> keys;    // "<mine>|<theirs>"
			array<string> names;
			auto theirNames = theirs.getKeys();
			array<string> all;
			for (uint i = 0; i < g_packs.length(); i++)
				all.insertLast(g_packs[i].name);
			for (uint i = 0; i < theirNames.length(); i++)
				if (all.find(theirNames[i]) < 0)
					all.insertLast(theirNames[i]);
			for (uint i = 0; i < all.length(); i++)
			{
				auto mine = Find(all[i]);
				string m = mine is null ? "-" : mine.update;
				string t = "-";
				if (theirs.exists(all[i]))
					theirs.get(all[i], t);
				if (m != "-")
					mineUpdates.insertLast(m);
				if (t != "-")
					theirUpdates.insertLast(t);
				if (m == t)
					continue;
				string key = m + "|" + t;
				int at = keys.find(key);
				if (at < 0)
				{
					keys.insertLast(key);
					names.insertLast(all[i]);
				}
				else
					names[at] += ", " + all[i];
			}
			mineNewest = Newest(mineUpdates);
			theirsNewest = Newest(theirUpdates);
			array<string> parts;
			for (uint i = 0; i < keys.length(); i++)
			{
				auto two = keys[i].split("|");
				parts.insertLast(Resources::GetString(".hwp.builds.differ", {
					{ "list", names[i] },
					{ "mine", two[0] == "-" ? Resources::GetString(".hwp.builds.absent") : Show(two[0]) },
					{ "theirs", two[1] == "-" ? Resources::GetString(".hwp.builds.absent") : Show(two[1]) } }));
			}
			return join(parts, "; ");
		}

		// tell this player how their packages compare with another player's
		void Against(const string &in who, const string &in packed)
		{
			string mineNewest;
			string theirsNewest;
			string diff = Differences(Unpack(packed), mineNewest, theirsNewest);
			if (diff == "")
			{
				HWP::Log("core", "updates match " + who);
				return;
			}
			int c = Compare(mineNewest, theirsNewest);
			string advice = Resources::GetString(c < 0 ? ".hwp.builds.advice.you" : (c > 0 ? ".hwp.builds.advice.them" : ".hwp.builds.advice.both"), { { "who", who } });
			HWP::Log("core", "updates differ from " + who + ": " + diff);
			HWP::Commands::Reply(Resources::GetString(".hwp.builds.peer", { { "who", who }, { "list", diff }, { "advice", advice } }));
		}

		// peers in town that haven't reported (host) or a host that hasn't answered (client)
		array<uint8> g_waitPeers;
		array<int> g_waitMs;
		array<uint8> g_heardPeers;
		int g_silentMs = SILENT_MS;

		void Wait(uint8 peer)
		{
			if (g_waitPeers.find(peer) < 0 && g_heardPeers.find(peer) < 0)
			{
				g_waitPeers.insertLast(peer);
				g_waitMs.insertLast(0);
			}
		}

		void Heard(uint8 peer)
		{
			int at = g_waitPeers.find(peer);
			if (at >= 0)
			{
				g_waitPeers.removeAt(at);
				g_waitMs.removeAt(at);
			}
			if (g_heardPeers.find(peer) < 0)
				g_heardPeers.insertLast(peer);
		}

		// heard from or given up on: waited for again (`hwp builds report`, `fake silent`)
		void Forget(uint8 peer)
		{
			int at = g_heardPeers.find(peer);
			if (at >= 0)
				g_heardPeers.removeAt(at);
		}

		// client, arriving in town
		void Report()
		{
			if (Network::IsServer())
				return;
			Wait(255); // the host
			HWP::Net::Request(REPORT, Payload());
		}

		void OnReport(uint8 peer, SValue@ data)
		{
			if (!Network::IsServer() || g_fakeSilent)
				return;
			Heard(peer);
			Against(HWP::SV::Str(data, "who", "player " + (peer + 1)), HWP::SV::Str(data, "packs"));
			HWP::Net::Send(peer, ANSWER, Payload());
		}

		void OnAnswer(SValue@ data)
		{
			if (g_fakeSilent)
				return;
			Heard(255);
			Against(HWP::SV::Str(data, "who", Resources::GetString(".hwp.builds.thehost")), HWP::SV::Str(data, "packs"));
		}

		// every gameplay tick in town (CoreModule)
		void Update(int ms)
		{
			if (Network::IsServer())
			{
				for (uint i = 0; i < g_players.length(); i++)
					if (g_players[i].peer != 255 && !g_players[i].local)
						Wait(g_players[i].peer);
			}
			for (int i = int(g_waitPeers.length()) - 1; i >= 0; i--)
			{
				g_waitMs[i] += ms;
				if (g_waitMs[i] < g_silentMs)
					continue;
				uint8 peer = g_waitPeers[i];
				Heard(peer);
				string who = peer == 255 ? Resources::GetString(".hwp.builds.thehost") : Lobby::GetPlayerName(peer);
				HWP::Log("core", "no update report from " + who + " in " + (g_silentMs / 1000) + " s");
				HWP::Commands::Reply(Resources::GetString(".hwp.builds.silent", { { "who", who }, { "mine", Mine() } }));
			}
		}

		// `hwp builds [report | fake <name>=<update> | fake silent | fake clear]`
		void Cmd(array<string>@ args)
		{
			string sub = args.length() > 0 ? args[0] : "";
			if (sub == "report")
			{
				// one lab game: the report goes to itself (a host's request runs locally)
				Forget(255);
				Wait(255);
				HWP::Net::Request(REPORT, Payload());
				HWP::Commands::Reply("update report sent");
				return;
			}
			if (sub == "fake" && args.length() > 1)
			{
				string what = args[1];
				for (uint i = 2; i < args.length(); i++)
					what += " " + args[i];
				if (what == "clear")
				{
					g_fake.removeRange(0, g_fake.length());
					g_fakeSilent = false;
					g_silentMs = SILENT_MS;
				}
				else if (what == "silent")
				{
					g_fakeSilent = true;
					g_silentMs = 3000;
					if (Network::IsServer())
					{
						Forget(uint8(Lobby::GetLocalPeer()));
						Wait(uint8(Lobby::GetLocalPeer()));
					}
				}
				else if (what.findFirst("=") > 0)
					g_fake.insertLast(what);
				HWP::Commands::Reply("update fake: " + (g_fakeSilent ? "silent" : (g_fake.length() == 0 ? "none" : join(g_fake, ", "))));
				return;
			}
			HWP::Commands::Reply("HammerwatchPlus " + Summary());
		}
	}
}
