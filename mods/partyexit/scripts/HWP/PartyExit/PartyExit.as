// Party exit. A floor's exit (WorldScript LevelExitAreaNext, and LevelExitAreaJump, which
// inherits its Use) loads the next floor only when every living player stands in its area.
// The override in scripts/WorldScript/Missions/LevelExitAreaNext.as asks Refusal() instead:
// the exit opens once partyexit.share percent of the living party (rounded up) is there,
// 3 of 4, 2 of 3, 2 of 2 at the default two thirds. Whoever is left behind goes along, as the
// dead do in vanilla. Off (partyexit.enabled) is the vanilla rule: everyone.
//
// Use runs on the machine of the player who pressed it and again through NetUse on every
// other one, so the count is made from each machine's own view of the party, as vanilla's is.
// The setting is host scope, so every machine counts with the host's share.
namespace HWP
{
	namespace PartyExit
	{
		// hwp partyexit phantom <outside> [inside]: living players that are not there, counted
		// as if they were in the party (solo tests of a party's exit)
		int g_phantomOutside = 0;
		int g_phantomInside = 0;

		bool Enabled()
		{
			return HWP::Settings::GetBool("partyexit.enabled", true);
		}

		int Share()
		{
			return clamp(HWP::Settings::GetInt("partyexit.share", 66), 1, 100);
		}

		// Players needed at the exit out of `living`: share percent, rounded up, at least one
		int Need(int living, int share)
		{
			if (living <= 0)
				return 0;
			return clamp((living * share + 99) / 100, 1, living);
		}

		bool InArea(WorldScript::LevelExitAreaNext@ exit, Actor@ actor)
		{
			return actor !is null && exit.IsInside(actor.m_unit);
		}

		// Empty when the exit may open for `user`; otherwise the line to announce
		string Refusal(WorldScript::LevelExitAreaNext@ exit, PlayerBase@ user)
		{
			int living = g_phantomOutside + g_phantomInside;
			int here = g_phantomInside;
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto plr = g_players[i];
				if (plr.peer == 255 || plr.IsDead())
					continue;
				living++;
				// the player who used it stands in the area (vanilla skips them for the same reason)
				if (plr.actor is user || InArea(exit, plr.actor))
					here++;
			}

			bool on = Enabled();
			int need = on ? Need(living, Share()) : living;
			if (here >= need)
			{
				if (here < living)
					HWP::Log("partyexit", "exit opens: " + here + " of " + living + " at the exit, " + need + " needed");
				return "";
			}

			string line = on ? Resources::GetString(".hwp.partyexit.need", {{ "need", need }, { "living", living }, { "here", here }})
				: Resources::GetString(".exit.notall");
			HWP::Log("partyexit", "exit refused: " + here + " of " + living + " at the exit, " + need + " needed: " + line);
			return line;
		}

		void CmdPartyExit(array<string>@ args)
		{
			if (args.length() > 1 && args[0] == "phantom")
			{
				g_phantomOutside = max(0, parseInt(args[1]));
				g_phantomInside = args.length() > 2 ? max(0, parseInt(args[2])) : 0;
			}
			string line = "party exit " + (Enabled() ? "on" : "off") + ", share " + Share() + "%: need";
			for (int n = 1; n <= 4; n++)
				line += " " + Need(n, Share()) + "/" + n;
			if (g_phantomOutside + g_phantomInside > 0)
				line += "; phantoms " + g_phantomOutside + " outside, " + g_phantomInside + " inside";
			HWP::Log("partyexit", line);
		}
	}
}

namespace Modules
{
	class HWPPartyExitModule : Module
	{
		HWPPartyExitModule()
		{
			super("hwp-partyexit");
			HWP::Commands::Register("partyexit", "[phantom <outside> [inside]]  how many of the party a floor exit needs; phantom counts extra living players for a solo test", HWP::Commands::Handler(HWP::PartyExit::CmdPartyExit));
			HWP::Log("partyexit", "self-check done: " + (HWP::PartyExit::Enabled() ? "on" : "off") + ", share " + HWP::PartyExit::Share()
				+ "%, 4 players need " + HWP::PartyExit::Need(4, HWP::PartyExit::Share()) + ", 3 need " + HWP::PartyExit::Need(3, HWP::PartyExit::Share()));
		}
	}
}
