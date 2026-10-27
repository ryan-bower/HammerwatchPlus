// guard probe (gamelab/scenarios/guard.json): HWP::Guard around a module that throws.
// The module's UpdateFrame is wrapped exactly as tools/guard_modules.py wraps every HWP
// module (the tool skips gamelab mods, so the wrapper is written out here). From body
// frame 300 the body throws every frame. Expected: the guard logs the first failure, lets
// the next call through unguarded once (the engine logs the stack trace), turns the entry
// point off after TRIP_STREAK failures in a row, and sends one chat line. A screen shake
// entry added by a hook at hook frames 320 (while the body fails) and 600 (after the trip),
// read 120 frames later, shows the game mode's update after the module loop still runs
// (unguarded, it ages 0 ms: throw 20261027-030133).
namespace GameLabGuard
{
	int g_body = 0, g_hook = 0;
	ScreenShake@ g_shake;
	string g_shakePhase;

	class Holder { int x; }
	Holder@ g_null;

	class GameLabGuardModule : Modules::Module
	{
		GameLabGuardModule() { super("gamelab-guard"); }

		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("gamelab-guard", "GameLabGuardModule.UpdateFrame"))
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
			if (paused)
				return;
			g_body++;
			if (g_body >= 300)
				g_null.x++;
		}
	}

	[Hook]
	void GameModeUpdate(BaseGameMode@ gm, int ms, GameInput& gameInput, MenuInput& menuInput)
	{
		g_hook++;
		int f = g_hook;
		if (f % 120 == 0)
			print("[GL-guard] ticks body " + g_body + " hook " + f);
		auto agm = cast<AGameplayGameMode>(gm);
		if (agm is null)
			return;
		if (f == 320 || f == 600)
		{
			@g_shake = ScreenShake();
			g_shake.m_time = g_shake.m_timeC = 100000;
			g_shake.m_amount = 0;
			g_shake.m_range = -1;
			agm.m_screenShake.insertLast(g_shake);
			g_shakePhase = f == 320 ? "failing" : "tripped";
		}
		if ((f == 440 || f == 720) && g_shake !is null)
			print("[GL-guard] shake " + g_shakePhase + ": " + (100000 - g_shake.m_timeC) + " ms aged in 120 frames");
	}
}
