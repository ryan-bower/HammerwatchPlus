// HWP::Guard - keeps one mod's script error from taking the game down with it.
//
// An uncaught exception in a module's UpdateFrame aborts the game mode's whole
// UpdateFrame after the module loop: the later modules, screen shake, pings and
// the death check (the DeadMenu) stop running, every frame (docs/RE_NOTES.md,
// "Script errors"). A game update that renames something a mod calls does
// exactly that. So every HWP module entry point runs its body through a guard:
//
//   HWP::Guard m_guardUpdateFrame;
//   void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
//   {
//       if (m_guardUpdateFrame.Skip("abyss", "HWPAbyssModule.UpdateFrame"))
//           return;
//       if (m_guardUpdateFrame.Raw())
//       {
//           GuardedUpdateFrame(ms, gameInput, menuInput, paused);
//           m_guardUpdateFrame.Ok();
//           return;
//       }
//       try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
//       catch { m_guardUpdateFrame.Failed(); }
//   }
//
// (tests/test_guard.py fails when a module entry point is not wrapped.)
//
// A caught exception is silent (getExceptionInfo is not registered), so the
// guard logs the mod and entry point itself, and lets the call after the first
// failure run unguarded once: that one reaches the engine, which logs the
// script stack trace. After TRIP_STREAK failures in a row, or TRIP_TOTAL in all,
// the entry point stops running (a half-run body can repeat a side effect every
// frame) and the player gets one chat line. Modules are made again with each
// level, so the next level tries again.
//
// The setting guard.off (hwp set guard.off true) runs every body unguarded, for
// debugging. hwp guard lists every entry point that has failed this session.
//
// A game update can also break a script outright: then nothing compiles and the game
// stops on an empty main menu, which no script can guard against (docs/GAME_UPDATES.md).
// When the scripts still compile on a build they were not tested on, CheckBuild tells
// the player once per build.
namespace HWP
{
	namespace Guards
	{
		const int TRIP_STREAK = 30;
		const int TRIP_TOTAL = 300;

		// one line per entry point that has failed this session, kept across levels
		class Record
		{
			string mod;
			string label;
			int failures = 0;
			int trips = 0;
		}

		array<Record@> g_records;
		bool g_offRead = false;
		bool g_off = false;

		Record@ Get(const string &in mod, const string &in label)
		{
			for (uint i = 0; i < g_records.length(); i++)
				if (g_records[i].label == label)
					return g_records[i];
			Record@ r = Record();
			r.mod = mod;
			r.label = label;
			g_records.insertLast(r);
			return r;
		}

		bool Off()
		{
			if (!g_offRead)
			{
				g_offRead = true;
				g_off = HWP::Settings::GetBool("guard.off", false);
			}
			return g_off;
		}

		void OnSettingChanged(const string &in key)
		{
			if (key == "guard.off")
				g_offRead = false;
		}

		// the core module's constructor, once per level
		void Init()
		{
			g_offRead = false;
			HWP::Commands::Register("guard", "[build]  list the mod script errors caught this session, or the game build check",
				HWP::Commands::Handler(CmdGuard));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(OnSettingChanged));
		}

		// The first gameplay tick in town (core module): one chat line per new game build.
		// The setting guard.tested_build stands in for HWP::TESTED_BUILD (GameLab's guard
		// scenario sets it to see the line on the pinned build).
		void CheckBuild()
		{
			int build = Network::GetBuildVersion();
			int tested = HWP::Settings::GetInt("guard.tested_build", HWP::TESTED_BUILD);
			if (build == tested || HWP::Settings::GetInt("guard.told_build", 0) == build)
				return;
			HWP::Settings::SetInt("guard.told_build", build);
			HWP::Log("guard", "game build " + build + ", tested on " + tested);
			HWP::Commands::Reply(Resources::GetString(".hwp.guard.new_build", { { "build", build }, { "tested", tested } }));
		}

		void CmdGuard(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "build")
			{
				HWP::Commands::Reply("game build " + Network::GetBuildVersion() + ", tested on "
					+ HWP::Settings::GetInt("guard.tested_build", HWP::TESTED_BUILD));
				CheckBuild();
				return;
			}
			if (g_records.length() == 0)
			{
				HWP::Commands::Reply("no mod script errors this session" + (Off() ? " (guard.off is set)" : ""));
				return;
			}
			for (uint i = 0; i < g_records.length(); i++)
			{
				auto r = g_records[i];
				HWP::Commands::Reply(r.label + ": " + r.failures + " error(s), turned off " + r.trips + " time(s)");
			}
		}
	}

	class Guard
	{
		string m_mod;
		string m_label;
		int m_streak = 0;
		int m_total = 0;
		bool m_tripped = false;
		bool m_rawNext = false;

		// true while this entry point is turned off; names it on the first call
		bool Skip(const string &in mod, const string &in label)
		{
			if (m_label.isEmpty())
			{
				m_mod = mod;
				m_label = label;
			}
			return m_tripped;
		}

		// run the body without a try: guard.off, or the one run after the
		// first failure that lets the engine log the stack trace
		bool Raw()
		{
			if (HWP::Guards::Off())
				return true;
			if (!m_rawNext)
				return false;
			m_rawNext = false;
			return true;
		}

		void Ok()
		{
			m_streak = 0;
		}

		// once: a one-shot entry point (Load), turned off by its first failure
		void Failed(bool once = false)
		{
			m_streak++;
			m_total++;
			auto r = HWP::Guards::Get(m_mod, m_label);
			r.failures++;
			if (m_total == 1)
			{
				HWP::LogError("guard", m_label + " threw a script exception; the next call runs unguarded once so the engine logs where");
				m_rawNext = true;
			}
			if (!once && m_streak < HWP::Guards::TRIP_STREAK && m_total < HWP::Guards::TRIP_TOTAL)
				return;
			m_tripped = true;
			r.trips++;
			HWP::LogError("guard", m_label + " turned off until the next level after " + m_total
				+ " script exception(s), " + m_streak + " in a row");
			HWP::Commands::Reply(Resources::GetString(".hwp.guard.tripped", { { "mod", m_mod } }));
		}
	}
}
